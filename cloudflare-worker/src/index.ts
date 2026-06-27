/**
 * Dreamina Email Worker
 * 接收 Cloudflare Email Routing 的邮件，提取验证码存储到 KV
 */

export interface Env {
    EMAIL_CODES: KVNamespace;
}

interface EmailMessage {
    from: string;
    to: string;
    headers: Headers;
    raw: ReadableStream;
    rawSize: number;
}

export default {
    async email(message: EmailMessage, env: Env, ctx: ExecutionContext): Promise<void> {
        const to = message.to;
        const from = message.from;

        console.log(`收到邮件: ${from} -> ${to}`);

        try {
            // 1. 尝试从邮件标题中提取（最直接可靠）
            const subject = message.headers.get("Subject") || "";
            console.log(`邮件标题: ${subject}`);
            const subjectMatch = subject.match(/\b([A-Z0-9]{6})\b/);

            let code: string | null = null;
            if (subjectMatch) {
                code = subjectMatch[1];
                console.log(`从标题提取到验证码: ${code}`);
            }

            // 2. 如果标题没找到，再读取原始正文内容
            const rawEmail = await new Response(message.raw).text();

            if (!code) {
                // 增强的提取逻辑：支持字母+数字，且不限大写
                const allMatches = rawEmail.match(/[A-Za-z0-9]{6}/g);
                console.log(`正文候选码: ${allMatches ? allMatches.join(', ') : '无'}`);

                const bodyMatch = rawEmail.match(/\b([A-Z0-9]{6})\b/);
                if (bodyMatch) {
                    code = bodyMatch[1];
                    console.log(`从正文提取到验证码: ${code}`);
                } else if (allMatches && allMatches.length > 0) {
                    code = allMatches[0].toUpperCase();
                    console.log(`使用兜底逻辑从正文提取到候选码: ${code}`);
                }
            }

            if (code) {
                // 存储到 KV
                await env.EMAIL_CODES.put(to, code, {
                    expirationTtl: 600
                });
                console.log(`✅ 验证码已成功存储到 KV: ${to} -> ${code}`);
            } else {
                console.log('❌ 未能匹配到任何 6 位验证码');
                await env.EMAIL_CODES.put(`debug:${to}`, rawEmail.substring(0, 2000), {
                    expirationTtl: 600
                });
            }

        } catch (error) {
            console.error('处理邮件失败:', error);
        }
    },

    // HTTP 接口用于查询验证码（可选）
    async fetch(request: Request, env: Env): Promise<Response> {
        const url = new URL(request.url);

        if (url.pathname === '/code') {
            const email = url.searchParams.get('email');

            if (!email) {
                return new Response('Missing email parameter', { status: 400 });
            }

            const code = await env.EMAIL_CODES.get(email);

            if (code) {
                return new Response(JSON.stringify({ email, code }), {
                    headers: { 'Content-Type': 'application/json' }
                });
            } else {
                return new Response(JSON.stringify({ email, code: null }), {
                    headers: { 'Content-Type': 'application/json' }
                });
            }
        }

        return new Response('Dreamina Email Worker', { status: 200 });
    }
};
