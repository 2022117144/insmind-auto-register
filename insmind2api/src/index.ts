/**
 * insMind AI Generation API Service v1.3
 * 
 * v1.3: Added media upload (STS + OSS) for img2vid support.
 * Accounts are fetched from backend DB — no more accounts.json.
 */

// ===== Global crash guards =====
process.on('unhandledRejection', (reason, promise) => {
    console.error(`⚠️ Unhandled rejection caught: ${reason instanceof Error ? reason.message : reason}`);
    // Don't crash — just log and continue
});
process.on('uncaughtException', (err) => {
    console.error(`⚠️ Uncaught exception caught: ${err.message}`);
    // Don't crash — just log and continue
});

import Koa from 'koa';
import cors from '@koa/cors';
import Router from 'koa-router';
import { koaBody } from 'koa-body';
import https from 'https';
import http from 'http';
import crypto from 'crypto';
import child_process from 'child_process';
import fs from 'fs';
import { initTokenRefresh, parseTokenProd } from './token-refresh';

// OSS accelerate endpoint IP (static — bypasses DNS + proxy issues on Windows)
const OSS_ACCELERATE_IP = '47.253.30.33';

const app = new Koa();
const router = new Router({ prefix: '/api' });

const BACKEND_URL = 'http://127.0.0.1:8005';

// In-memory account token pool
interface InsMindAccount {
    email: string;
    token: string;       // token.prod (outer JWT)
    userId: string;
    credits: number;
    refreshToken?: string;
    tokenExpiresAt?: number;
    orgId?: string;      // token.org_id.prod cookie
}

// STS response from /api/tb-dam/asset/upload/tokens
interface StsResponse {
    security_token: string;
    access_key_id: string;
    access_key_secret: string;
    expiration: string;
    endpoint: string;
    region: string;
    bucket_name: string;
    host: string;           // CDN host
    path: string;           // directory
    object_name: string;    // full path including dir
    [key: string]: any;
}

let accounts: InsMindAccount[] = [];
let currentAccountIndex = 0;

// Fetch accounts from backend DB
async function refreshAccounts(): Promise<void> {
    try {
        const data = await new Promise<string>((resolve, reject) => {
            const req = http.get(`${BACKEND_URL}/api/insmind/accounts`, (res) => {
                let d = '';
                res.on('data', (c: Buffer) => d += c.toString());
                res.on('end', () => resolve(d));
            });
            req.on('error', reject);
            req.setTimeout(5000, () => { req.destroy(new Error('Timeout')); });
        });
        const raw: any[] = JSON.parse(data);
        accounts = raw.map(a => ({
            email: a.email || '',
            token: a.token || '',
            userId: a.user_id || (a as any).userId || '0',
            credits: a.credits || 0,
            refreshToken: a.refresh_token || (a as any).refreshToken,
            orgId: a.org_id || (a as any).orgId,
            tokenExpiresAt: undefined,
        }));
        console.log(`[Accounts] Refreshed from backend: ${accounts.length} accounts`);
    } catch (e: any) {
        console.log(`[Accounts] Backend refresh failed: ${e.message}, keeping ${accounts.length} cached`);
    }
}

// Start periodic refresh
setInterval(() => refreshAccounts(), 30000);

// Initial load
refreshAccounts().then(() => {
    console.log(`📧 Accounts pool: ${accounts.length}`);
    initTokenRefresh(() => accounts);
    console.log('🔄 Token refresh initialized (check every 5 min)');
});

function getNextAccount(): InsMindAccount | null {
    // Try each account in round-robin, skip expired ones (auto-clean)
    for (let attempt = 0; attempt < accounts.length * 2; attempt++) {
        const idx = currentAccountIndex % accounts.length;
        currentAccountIndex++;
        const account = accounts[idx];
        if (!account) continue;

        // Parse expiry from token
        const parsed = parseTokenProd(account.token);
        if (parsed && parsed.expiresAt < Date.now()) {
            console.log(`🧹 Removing expired account: ${account.email}`);
            accounts.splice(idx, 1);
            if (accounts.length === 0) return null;
            continue;
        }
        return account;
    }
    return null;
}

// Scene code mapping
const SCENE_CODE_MAP: Record<string, string> = {
    'Pixverse-V6.0': 'Pixversev60',
    'Wan-2.7': 'Wan27',
    'Wan-2.2': 'Wan22',
    'Kling-3.0': 'Kling30',
    'Seedance-2.0': 'Seedance20',
    'Seedance-2.0-Mini': 'Seedance20Mini',
    'VEO-3.1': 'VEO31',
};

// ============ Helpers ============

// Extract the inner access_token from the token.prod JWT
function getInnerToken(account: InsMindAccount): string {
    const parsed = parseTokenProd(account.token);
    return parsed ? parsed.accessToken : account.token;
}

function makeRequest(options: http.RequestOptions, body?: string): Promise<{ status: number; data: string }> {
    return new Promise((resolve, reject) => {
        const req = https.request(options, (res) => {
            let data = '';
            res.on('data', (chunk: Buffer) => { data += chunk.toString(); });
            res.on('end', () => resolve({ status: res.statusCode || 500, data }));
        });
        req.on('error', reject);
        if (body) req.write(body);
        req.end();
    });
}

// ============ Media Upload (OSS STS) ============

/**
 * Get STS upload token from insMind API.
 * Returns STS credentials + OSS upload info.
 */
async function getStsToken(account: InsMindAccount, format: string): Promise<StsResponse> {
    const body = JSON.stringify({
            format: format,
            content_id: '',
            dir: '',
            device_id: 'undefined',
        });

    const result = await makeRequest({
        hostname: 'www.insmind.com',
        path: '/api/tb-dam/asset/upload/tokens',
        method: 'POST',
        timeout: 15000,
        headers: {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(body),
            'Authorization': `Bearer ${getInnerToken(account)}`,
            'x-product-type': 'INDIVIDUAL_FREE',
            'x-channel-id': '781',
            'x-business-id': '124',
            'x-device-id': 'node-uploader',
            'origin': 'https://www.insmind.com',
            'referer': 'https://www.insmind.com/creation',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Cookie': account.orgId ? `token.prod=${account.token}; token.org_id.prod=${account.orgId}` : `token.prod=${account.token}`,
        },
    }, body);

    if (result.status !== 200) {
        throw new Error(`STS token request failed: ${result.status} ${result.data.substring(0, 100)}`);
    }

    return JSON.parse(result.data) as StsResponse;
}

/**
 * Calculate OSS authorization header using STS credentials.
 */
function calculateOssAuth(
    method: string, path: string, headers: Record<string, string>,
    sts: StsResponse, date: string
): string {
    const contentType = headers['Content-Type'] || '';
    const contentMd5 = headers['Content-MD5'] || '';
    const ossHeaders = Object.entries(headers)
        .filter(([k]) => k.startsWith('x-oss-'))
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([k, v]) => `${k.toLowerCase()}:${v}`)
        .join('\n');
    const resource = `/${sts.bucket_name}${path}`;
    const stringToSign = `${method}\n${contentMd5}\n${contentType}\n${date}\n${ossHeaders ? ossHeaders + '\n' : ''}${resource}`;
    const hmac = crypto.createHmac('sha1', sts.access_key_secret);
    hmac.update(stringToSign);
    const signature = hmac.digest('base64');
    return `OSS ${sts.access_key_id}:${signature}`;
}

/**
 * Upload a data URL to OSS using STS credentials.
 * Uses curl.exe with --resolve to bypass DNS/proxy issues on Windows.
 * Returns the CDN URL of the uploaded file.
 */
async function uploadMedia(account: InsMindAccount, dataUrl: string): Promise<string> {
    const matches = dataUrl.match(/^data:(image\/(\w+));base64,(.+)$/);
    if (!matches) throw new Error('Invalid data URL format');

    const mimeType = matches[1];
    const format = matches[2];
    const base64Data = matches[3];
    const imageBuffer = Buffer.from(base64Data, 'base64');

    const sts = await getStsToken(account, format);
    const ext = format === 'jpeg' ? 'jpg' : format;
    const objectKey = `${sts.path}/${Date.now()}.${ext}`;

    const date = new Date().toUTCString();

    const bucket = sts.bucket_name;
    const hostname = `${bucket}.oss-accelerate.aliyuncs.com`;
    const url = `https://${hostname}/${objectKey}`;
    const cdnUrl = `${sts.host}/${objectKey}`;

    // Manual OSS signature — same algorithm as Python backend (proven working)
    const stringToSign = `PUT\n\n${mimeType}\n${date}\nx-oss-security-token:${sts.security_token}\n/${bucket}/${objectKey}`;
    const sig = crypto.createHmac('sha1', sts.access_key_secret).update(stringToSign).digest('base64');
    const auth = `OSS ${sts.access_key_id}:${sig}`;
        console.log(`🔑 Signing: [${stringToSign.substring(0, 80)}...] sig=${sig.substring(0, 20)}...`);

            // Write temp file then upload via curl.exe with --resolve (bypasses proxy SSL interception)
            const tmpPath = `${process.env.TEMP || '/tmp'}/insmind-oss-${Date.now()}.${ext}`;
            fs.writeFileSync(tmpPath, imageBuffer);

            let result: string = 'unknown';
            try {
                result = await new Promise<string>((resolve) => {
                    const curl = child_process.spawn('C:/Windows/System32/curl.exe', [
                '-s', '--max-time', '30',
                '-w', '%{http_code}',
                '-X', 'PUT',
                '-H', `Content-Type: ${mimeType}`,
                '-H', `Date: ${date}`,
                '-H', `Authorization: ${auth}`,
                '-H', `x-oss-security-token: ${sts.security_token}`,
                '--data-binary', `@${tmpPath}`,
                '--insecure',
                '--resolve', `${hostname}:443:${OSS_ACCELERATE_IP}`,
                url,
            ], { stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true });

            let stdout = '';
            let stderr = '';
            curl.stdout.on('data', (d: Buffer) => stdout += d.toString());
            curl.stderr.on('data', (d: Buffer) => stderr += d.toString());
            curl.on('close', (code) => {
                if (code !== 0) {
                    resolve(`ERROR:curl_exit_${code} ${stderr.substring(0, 100)}`);
                } else {
                    resolve(stdout.trim());
                }
            });
            curl.on('error', (err) => resolve(`ERROR:${err.message}`));
        });

        if (result === '200') {
            console.log(`✅ OSS upload success: ${cdnUrl}`);
            return cdnUrl;
        }

        console.log(`⚠️ OSS upload failed (primary): ${result}`);
    } finally {
        try { fs.unlinkSync(tmpPath); } catch {}
    }

    // Fallback: try standby endpoint
    const standbyHost = (sts as any).standby_endpoint ? (sts as any).standby_endpoint.hostname || new URL((sts as any).standby_endpoint).hostname : null;
    if (standbyHost) {
        const standbyUrl = `https://${standbyHost}/${bucket}/${objectKey}`;
        console.log(`⚠️ Trying standby: ${standbyHost}`);
        try {
            const result2 = await new Promise<string>((resolve) => {
                const curl = child_process.spawn('C:/Windows/System32/curl.exe', [
                    '-s', '--max-time', '30', '-w', '%{http_code}',
                    '-X', 'PUT',
                    '-H', `Content-Type: ${mimeType}`,
                    '-H', `Date: ${date}`,
                    '-H', `Authorization: ${auth}`,
                    '-H', `x-oss-security-token: ${sts.security_token}`,
                    '--data-binary', `@${tmpPath}`,
                    '--insecure',
                    url,
                ], { stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true });
                let o = ''; let e = '';
                curl.stdout.on('data', (d: Buffer) => o += d.toString());
                curl.stderr.on('data', (d: Buffer) => e += d.toString());
                curl.on('close', (code) => resolve(code === 0 ? o.trim() : `ERROR:${e.substring(0, 100)}`));
                curl.on('error', (err) => resolve(`ERROR:${err.message}`));
            });
            if (result2 === '200') {
                console.log(`✅ OSS upload success (standby): ${cdnUrl}`);
                return cdnUrl;
            }
        } catch { /* ignore */ }
    }

    throw new Error(`OSS upload failed: ${result || 'unknown'}`);
}

// ============ Account Management ============

// List accounts in the pool
router.get('/accounts', async (ctx) => {
    ctx.body = {
        total: accounts.length,
        accounts: accounts.map(a => ({
            email: a.email,
            userId: a.userId,
            credits: a.credits,
        })),
    };
});

// Add an account to the pool
router.post('/accounts', async (ctx) => {
    const { email, token, userId, credits = 0, refreshToken, orgId } = ctx.request.body as any;
    if (!email || !token) {
        ctx.status = 400;
        ctx.body = { error: 'email and token required' };
        return;
    }
    // Avoid duplicates
    const existing = accounts.find(a => a.email === email);
    if (!existing) {
        accounts.push({ email, token, userId: String(userId || '0'), credits, refreshToken, orgId });
    } else {
        existing.token = token;
        existing.userId = String(userId || existing.userId);
        if (orgId) existing.orgId = orgId;
    }
    ctx.body = { success: true, total: accounts.length };
});

// === Models List ===
router.get('/models', async (ctx) => {
    const IMAGE_MODELS = [
        { id: 'jimeng-4.5', name: 'Jimeng 4.5', points: 10 },
        { id: 'jimeng-5.0', name: 'Jimeng 5.0', points: 20 },
    ];
    const VIDEO_MODELS = [
        { id: 'Pixverse-V6.0', name: 'Pixverse V6.0', points: 50 },
        { id: 'Wan-2.7', name: 'Wan 2.7', points: 80 },
        { id: 'Wan-2.2', name: 'Wan 2.2', points: 20 },
        { id: 'Kling-3.0', name: 'Kling 3.0', points: 60 },
        { id: 'Seedance-2.0', name: 'Seedance 2.0', points: 40 },
        { id: 'Seedance-2.0-Mini', name: 'Seedance 2.0 Mini', points: 20 },
        { id: 'VEO-3.1', name: 'VEO 3.1', points: 70 },
    ];
    ctx.body = {
        image: IMAGE_MODELS,
        video: VIDEO_MODELS,
    };
});

// ============ SSE Helper (text-to-video — uses resp.text()) ============

async function sseFetch(url: string, bodyStr: string, headers: Record<string, string>, timeoutMs = 300000): Promise<string> {
    try {
        const resp = await fetch(url, {
            method: 'POST',
            headers,
            body: bodyStr,
            signal: AbortSignal.timeout(timeoutMs),
        });
        return await resp.text();
    } catch {
        return '';
    }
}

// ============ SSE Helper (image-to-video — uses streaming reader) ============

async function sseFetchStream(url: string, bodyStr: string, headers: Record<string, string>, timeoutMs = 300000): Promise<string> {
    let resp: Response | null = null;
    try {
        resp = await fetch(url, { method: 'POST', headers, body: bodyStr });
        if (!resp.body) return '';

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let result = '';
        const deadline = Date.now() + timeoutMs;

        try {
            while (Date.now() < deadline) {
                let chunk: ReadableStreamReadResult<Uint8Array>;
                let timer: ReturnType<typeof setTimeout> | undefined;
                try {
                    chunk = await Promise.race([
                        reader.read(),
                        new Promise<never>((_, reject) => {
                            timer = setTimeout(() => reject(new Error('timeout')), 15000);
                        }),
                    ]);
                    clearTimeout(timer);
                    timer = undefined;
                } catch {
                    if (timer) clearTimeout(timer);
                    break;
                }
                if (chunk.done) break;
                result += decoder.decode(chunk.value, { stream: true });
                // Don't break on function_call — keep reading for video URL
            }
        } catch { /* ignore */ }

        try { reader.cancel(); } catch {}
        return result;
    } catch (fetchErr: any) {
        console.log(`⚠️ sseFetchStream error: ${fetchErr.message}`);
        return '';
    }
}

// ============ Pricing ============

router.post('/v1/videos/pricing', async (ctx) => {
    const { model = 'Pixverse-V6.0', duration = 10, resolution = '360P' } = ctx.request.body as any;
    const baseCosts: Record<string, number> = {
        'Pixverse-V6.0': 50, 'Wan-2.7': 80, 'Wan-2.2': 20,
        'Kling-3.0': 60, 'Seedance-2.0': 40, 'Seedance-2.0-Mini': 20, 'VEO-3.1': 70,
    };
    const baseCost = baseCosts[model] || 50;
    const resolutionMultiplier: Record<string, number> = { '360P': 1, '480P': 1.2, '540P': 1.5, '720P': 2, '1080P': 3 };
    const durationMultiplier = Math.ceil(duration / 5);
    ctx.body = { cost: Math.round(baseCost * (resolutionMultiplier[resolution] || 1) * durationMultiplier), model, duration, resolution, currency: 'points' };
});

// ============ Text-to-Video Generation ============

router.post('/v1/videos/generations', async (ctx) => {
    const body = ctx.request.body as any;
    const { prompt, model = 'Pixverse-V6.0', duration = 10, resolution = '360P', aspect_ratio = '16:9' } = body;

    const account = getNextAccount();
    if (!account) {
        ctx.status = 402;
        ctx.body = { error: 'No accounts available' };
        return;
    }
    if (!account.orgId) {
        ctx.status = 400;
        ctx.body = { error: 'Account has no orgId' };
        return;
    }

    const sceneCode = SCENE_CODE_MAP[model] || 'Pixversev60';
    const taskId = `insmind-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`;

    const payload = {
        content: {
            type: 'plain',
            scene_code: sceneCode,
            prompt: [{ type: 'text', content: prompt || '' }],
            parameters: {
                ratio: aspect_ratio === '16:9' ? '' : aspect_ratio,
                resolution: resolution,
                duration: String(duration),
                styleCode: sceneCode,
            },
            duration: String(duration),
            resolution: resolution,
            text: prompt || '',
        },
        name: 'user',
        role: 'user',
        local_thread_id: taskId,
        local_message_id: `${taskId}-msg`,
        thread_id: '',
        attachments: [],
        extra: {
            prompt_suffix: `Using video tool: ${model},Resolution: ${resolution},Duration: ${duration} seconds`,
            enable_websearch: false,
        },
    };

    const bodyStr = JSON.stringify(payload);
    const sseHeaders: Record<string, string> = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getInnerToken(account)}`,
        'x-user-id': account.userId,
        'x-content-id': taskId,
        'x-product-type': 'INDIVIDUAL_FREE',
        'x-channel-id': '781',
        'origin': 'https://www.insmind.com',
        'referer': 'https://www.insmind.com/creation',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Cookie': account.orgId ? `token.prod=${account.token}; token.org_id.prod=${account.orgId}` : `token.prod=${account.token}`,
    };

    let rawData: string;
    try {
        rawData = await sseFetch('https://sse.insmind.com/api/ai-agent/v1/thread/completion', bodyStr, sseHeaders);
                console.log(`📡 SSE response: ${rawData.length} chars`);
                if (rawData.length > 0) console.log(`📄 SSE snippet: ${rawData.substring(0, 500)}`);
    } catch (fetchErr: any) {
        console.error(`❌ SSE fetch failed: ${fetchErr.message}`);
        ctx.status = 502;
        ctx.body = { error: 'SSE request failed', detail: fetchErr.message };
        return;
    }

    try {
        let videoUrl: string | null = null;
        const m1 = rawData.match(/https:\/\/[^\"\\, ]+\.mp4/);
        const m2 = rawData.match(/https?:\\\/\\\/[^\"\\, ]+\.mp4/);
        if (m1) videoUrl = m1[0];
        else if (m2) videoUrl = m2[0].replace(/\\\//g, '/');

        // If no video URL in SSE response, try polling records API
        const tidMatch = rawData.match(/"thread_id"\s*:\s*"([^"]+)"/);
        const pollTaskId = tidMatch ? tidMatch[1] : taskId;
        if (!videoUrl && (rawData.includes('function_call') || rawData.includes('Pixverse') || rawData.includes('video-generation'))) {
            console.log(`⏳ function_call detected, polling records with task_id=${pollTaskId.substring(0, 20)}... after 30s`);
            await new Promise(resolve => setTimeout(resolve, 30000));
            try {
                const pollResult = await makeRequest({
                    hostname: 'www.insmind.com',
                    path: `/api/dam/ai/records?task_id=${pollTaskId}`,
                    method: 'GET',
                    headers: {
                        'Authorization': `Bearer ${getInnerToken(account)}`,
                        'x-product-type': 'INDIVIDUAL_FREE',
                        'x-channel-id': '781',
                        'origin': 'https://www.insmind.com',
                        'referer': 'https://www.insmind.com/creation',
                        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    },
                });
                if (pollResult.status === 200) {
                                    const records = JSON.parse(pollResult.data);
                                    const items = Array.isArray(records) ? records : (records?.data ?? []);
                                    if (items.length > 0) {
                                        const latest = items[0];
                                        // Video URL can be in generation_result or assets[].url
                                        const videoUrlFromRecord = latest?.generation_result 
                                            || latest?.assets?.find((a: any) => a?.url?.includes('.mp4'))?.url
                                            || latest?.result_ext?.content_url;
                                        if (videoUrlFromRecord) videoUrl = videoUrlFromRecord;
                                    }
                                }
            } catch { /* ignore poll error */ }
        }

        ctx.body = {
            id: taskId, status: 'processing', model, prompt,
            duration, resolution, aspect_ratio,
            account: account.email,
            video_url: videoUrl,
            response: rawData,
            poll_interval_seconds: 15,
        };
    } catch (err: any) {
        ctx.status = 502;
        ctx.body = { error: 'Failed to process SSE response', detail: err.message, task_id: taskId };
    }
});

// ============ Image-to-Video Generation (with conversation + confirmation) ============

function _guessMime(url: string): string {
    return url.endsWith('.webp') ? 'image/webp'
        : url.endsWith('.jpg') || url.endsWith('.jpeg') ? 'image/jpeg'
        : url.endsWith('.gif') ? 'image/gif'
        : url.endsWith('.png') ? 'image/png'
        : 'image/jpeg';
}

router.post('/v1/videos/generations-image', async (ctx) => {
    const { prompt, model = 'Pixverse-V6.0', duration = 10, resolution = '360P', aspect_ratio = '16:9', image_url, image_urls, account_email } = ctx.request.body as any;

    // Support both single image_url and array image_urls
    const inputUrls: string[] = image_urls || (image_url ? [image_url] : []);
    if (inputUrls.length === 0) {
        ctx.status = 400;
        ctx.body = { error: 'image_url or image_urls is required for image-to-video generation' };
        return;
    }

    // Use the specified account if provided (avoids round-robin mismatch with OSS upload)
    let account: InsMindAccount | null = null;
    if (account_email) {
        account = accounts.find(a => a.email === account_email) || null;
    }
    if (!account) {
        account = getNextAccount();
    }
    if (!account) {
        ctx.status = 402;
        ctx.body = { error: 'No accounts available' };
        return;
    }
    if (!account.orgId) {
        ctx.status = 400;
        ctx.body = { error: 'Account has no orgId' };
        return;
    }

    const sceneCode = SCENE_CODE_MAP[model] || 'Pixversev60';
    const taskId = `insmind-img-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`;

    // Step 1: Upload each data URL to OSS
    const cdnUrls: string[] = [];
    for (let i = 0; i < inputUrls.length; i++) {
        const url = inputUrls[i];
        let cdnUrl = url;
        if (typeof url === 'string' && url.startsWith('data:')) {
            console.log(`🖼️ [${i + 1}/${inputUrls.length}] Uploading data URL to OSS... (${(url.length / 1024).toFixed(0)}KB)`);
            try {
                cdnUrl = await uploadMedia(account, url);
                console.log(`🖼️ [${i + 1}/${inputUrls.length}] CDN URL: ${cdnUrl}`);
            } catch (uploadErr: any) {
                console.log(`⚠️ [${i + 1}/${inputUrls.length}] Upload failed, falling back to data URL: ${uploadErr.message}`);
                cdnUrl = url;
            }
        }
        cdnUrls.push(cdnUrl);
    }

    // Step 2: Build SSE payload — all images in BOTH prompt (as media) and attachments
    const mediaPromptItems = cdnUrls.map((url, i) => ({
        type: 'media' as const,
        url,
        mime: _guessMime(url),
        name: `${i + 1}.${_guessMime(url).split('/')[1]}`,
    }));
    const attachmentItems = cdnUrls.map((url, i) => ({
        url,
        mime_type: _guessMime(url),
        name: `input.${i + 1}.${_guessMime(url).split('/')[1]}`,
    }));

    const convPayload = {
        content: {
            type: 'plain',
            scene_code: sceneCode,
            prompt: [
                ...mediaPromptItems,
                { type: 'text', content: prompt || '' }
            ],
            parameters: {
                ratio: aspect_ratio === '16:9' ? '' : aspect_ratio,
                resolution: resolution,
                duration: String(duration),
                styleCode: sceneCode,
            },
            duration: String(duration),
            resolution: resolution,
            text: prompt || '',
        },
        name: 'user',
        role: 'user',
        local_thread_id: taskId,
        local_message_id: `${taskId}-msg`,
        thread_id: '',
        attachments: attachmentItems,
        extra: {
            prompt_suffix: `Using video tool: ${model},Resolution: ${resolution},Duration: ${duration} seconds`,
            enable_websearch: false,
        },
    };

    const sseHeaders: Record<string, string> = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getInnerToken(account)}`,
        'x-user-id': account.userId,
        'x-content-id': taskId,
        'x-product-type': 'INDIVIDUAL_FREE',
        'x-channel-id': '781',
        'origin': 'https://www.insmind.com',
        'referer': 'https://www.insmind.com/creation',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Cookie': account.orgId ? `token.prod=${account.token}; token.org_id.prod=${account.orgId}` : `token.prod=${account.token}`,
    };

    // Step 3: First SSE — send image(s) and prompt, read full response like text-to-video
    let finalRawData: string;
    try {
        finalRawData = await sseFetch('https://sse.insmind.com/api/ai-agent/v1/thread/completion', JSON.stringify(convPayload), sseHeaders, 300000);
            console.log(`📡 SSE response (1st): ${finalRawData.length} chars, model=${model}, resolution=${resolution}, duration=${duration}`);
            console.log(`📄 SSE snippet: ${finalRawData.substring(0, 500)}`);
    } catch (fetchErr: any) {
        console.error(`❌ SSE fetch failed: ${fetchErr.message}`);
        ctx.status = 502;
        ctx.body = { error: 'SSE request failed', detail: fetchErr.message };
        return;
    }

    // Step 4: Check if 1st SSE already has video URL (single-turn completion like text-to-video)
    let rawData = finalRawData;
    const firstMp4 = rawData.match(/https:\/\/[^\"\\, ]+\.mp4/) || rawData.match(/https?:\\\/\\\/[^\"\\, ]+\.mp4/);
    if (firstMp4) {
        const videoUrl = firstMp4[0].replace(/\\\\/g, '/');
        console.log(`✅ Video URL found in 1st SSE response`);
        ctx.body = {
            id: taskId, status: 'processing', model, prompt,
            duration, resolution, aspect_ratio,
            account: account.email,
            video_url: videoUrl,
            cdn_urls: cdnUrls,
            image_url: image_url || (image_urls ? image_urls[0] : undefined),
            image_count: inputUrls.length,
            conversation: 'single-turn',
            response: rawData,
            poll_interval_seconds: 15,
        };
        return;
    }

    // Step 5: Extract thread_id and send confirmation to execute the function_call
    const threadMatch = rawData.match(/"thread_id"\s*:\s*"([^"]+)"/);
    let threadId = threadMatch ? threadMatch[1] : '';

    if (threadId) {
        console.log(`💬 Confirming function_call on thread ${threadId}`);
        const confirmPayload = JSON.parse(JSON.stringify(convPayload));
        confirmPayload.thread_id = threadId;
        confirmPayload.local_message_id = `${taskId}-confirm`;
        confirmPayload.content.prompt = [
            { type: 'text', content: `Yes, use ${model} to generate the video now. ${prompt}` }
        ];

        try {
                    const confirmResult = await sseFetch('https://sse.insmind.com/api/ai-agent/v1/thread/completion', JSON.stringify(confirmPayload), sseHeaders, 300000);
                    console.log(`📡 SSE response (2nd): ${confirmResult.length} chars`);
                    // Update rawData with confirmation result for video URL extraction
                    if (confirmResult.length > 0) rawData = confirmResult;
        } catch (confirmErr: any) {
            console.error(`❌ SSE confirmation failed: ${confirmErr.message}`);
        }
    }

    // Step 6: Detect if 2nd SSE is still a function_call (Seedance multi-turn pattern)
    if (rawData && (rawData.includes('"type":"function_call"') || rawData.includes('"type": "function_call"')) && threadId) {
        console.log(`💬 Third confirmation on thread ${threadId} (Seedance multi-turn)`);
        const thirdPayload = JSON.parse(JSON.stringify(convPayload));
        thirdPayload.thread_id = threadId;
        thirdPayload.local_message_id = `${taskId}-third`;
        thirdPayload.content.prompt = [
            { type: 'text', content: `Yes, execute ${model} now. ${prompt}` }
        ];
        try {
            const thirdResult = await sseFetch(
                'https://sse.insmind.com/api/ai-agent/v1/thread/completion',
                JSON.stringify(thirdPayload), sseHeaders, 300000
            );
            console.log(`📡 SSE response (3rd): ${thirdResult.length} chars`);
            console.log(`📄 SSE snippet (3rd): ${thirdResult.substring(0, 500)}`);
            if (thirdResult.length > 0) rawData = thirdResult;
        } catch (thirdErr: any) {
            console.error(`❌ SSE third confirmation failed: ${thirdErr.message}`);
        }
    }

    // Step 7: Try to extract video URL or poll records
    try {
        let videoUrl: string | null = null;
        // Check BOTH finalRawData (1st SSE) and rawData (2nd/3rd SSE) for mp4 URLs
        for (const src of [rawData, finalRawData].filter(Boolean)) {
            const m1 = src.match(/https:\/\/[^\"\\, ]+\.mp4/);
            const m2 = src.match(/https?:\\\/\\\/[^\"\\, ]+\.mp4/);
            if (m1) { videoUrl = m1[0]; break; }
            if (m2) { videoUrl = m2[0].replace(/\\\\/g, '/'); break; }
        }

        const hasGenCall = ['Pixverse', 'Wan-2', 'Kling', 'Seedance', 'VEO', 'video-generation'].some(kw => rawData.includes(kw) || finalRawData.includes(kw));
        if (!videoUrl && hasGenCall) {
            console.log(`⏳ video-generation detected, polling records up to 3 times`);
            for (let attempt = 0; attempt < 3; attempt++) {
                await new Promise(resolve => setTimeout(resolve, 30000));
                try {
                    const pollResult = await makeRequest({
                        hostname: 'www.insmind.com',
                        path: `/api/dam/ai/records?task_id=${threadId || taskId}`,
                        method: 'GET',
                        headers: {
                            'Authorization': `Bearer ${getInnerToken(account)}`,
                            'x-product-type': 'INDIVIDUAL_FREE',
                            'x-channel-id': '781',
                            'origin': 'https://www.insmind.com',
                            'referer': 'https://www.insmind.com/creation',
                            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        },
                    });
                    if (pollResult.status === 200) {
                                            const records = JSON.parse(pollResult.data);
                                            const items = Array.isArray(records) ? records : (records?.data ?? []);
                                            if (items.length > 0) {
                                                const latest = items[0];
                                                // Video URL can be in generation_result or assets[].url
                                                const videoUrlFromRecord = latest?.generation_result 
                                                    || latest?.assets?.find((a: any) => a?.url?.includes('.mp4'))?.url
                                                    || latest?.result_ext?.content_url;
                                                if (videoUrlFromRecord) {
                                                    videoUrl = videoUrlFromRecord;
                                                    console.log(`✅ Video found: ${videoUrl.substring(0, 60)}...`);
                                                    break;
                                                }
                                            }
                                        }
                } catch { /* ignore poll error */ }
            }
        }

        ctx.body = {
            id: taskId, status: 'processing', model, prompt,
            duration, resolution, aspect_ratio,
            account: account.email,
            video_url: videoUrl,
            cdn_urls: cdnUrls,
            image_url: image_url || (image_urls ? image_urls[0] : undefined),
            image_count: inputUrls.length,
            conversation: threadId && rawData.includes('function_call') ? 'three-turn' : 'two-turn',
            response: rawData,
            poll_interval_seconds: 15,
        };
    } catch (err: any) {
        ctx.status = 502;
        ctx.body = { error: 'Failed to process img2vid response', detail: err.message, task_id: taskId };
    }
});

// ============ Task Status Polling ============

router.get('/v1/tasks/:id', async (ctx) => {
    const account = getNextAccount();
    if (!account) {
        ctx.body = { id: ctx.params.id, status: 'unknown', message: 'No account for status check' };
        return;
    }
    try {
        const result = await makeRequest({
            hostname: 'www.insmind.com',
            path: '/api/dam/ai/records?page=1&size=10&type=video',
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${getInnerToken(account)}`,
                'x-product-type': 'INDIVIDUAL_FREE',
                'x-channel-id': '781',
                'origin': 'https://www.insmind.com',
                'referer': 'https://www.insmind.com/creation',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            },
        });
        if (result.status === 200) {
            try { ctx.body = { id: ctx.params.id, status: 'completed', records: JSON.parse(result.data) }; }
            catch { ctx.body = { id: ctx.params.id, status: 'processing', raw: result.data.substring(0, 200) }; }
        } else {
            ctx.body = { id: ctx.params.id, status: 'processing', message: 'Still generating...' };
        }
    } catch {
        ctx.body = { id: ctx.params.id, status: 'processing', message: 'Status check failed, retrying...' };
    }
});

app.use(cors());
app.use(koaBody());
app.use(router.routes()).use(router.allowedMethods());

const PORT = 5105;
app.listen(PORT, () => {
    console.log(`🚀 insMind2API v1.3 running on http://127.0.0.1:${PORT}`);
    console.log(`📋 Media upload enabled (STS + OSS for img2vid)`);
    console.log(`📧 Accounts pool: ${accounts.length} (add via POST /api/accounts)`);
    initTokenRefresh(() => accounts);
    console.log('🔄 Token refresh initialized (check every 5 min)');
});
