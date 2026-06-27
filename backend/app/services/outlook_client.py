"""
Dreamina Auto Register - Outlook 邮件客户端
通过 OutlookManager 外部 API 轮询获取 Dreamina 发送的验证码
"""
import asyncio
import re
import httpx
from datetime import datetime, timezone
from typing import Optional
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Dreamina/CapCut 发件关键字（用于过滤邮件 subject）
_SENDER_KEYWORDS = ["dreamina", "capcut", "即梦", "jianying"]
# 验证码正则：匹配独立的 6 位字母数字组合（因为有可能是 934J3N 这种含有字母的码）
_CODE_PATTERN = re.compile(r'\b([A-Za-z0-9]{6})\b')

# 常见的 6 字母非验证码单词黑名单
_BLACKLIST_WORDS = {
    "capcut", "please", "verify", "thanks", "update", "notice", "action", 
    "system", "online", "submit", "secure", "button", "clicks", "choose", 
    "create", "window", "tiktok", "select", "change", "access", "policy",
    "review", "accept", "device", "safely", "detail", "ignore"
}


class OutlookClient:
    """调用 OutlookManager 外部 API，轮询等待并提取 Dreamina 验证码"""

    @property
    def _base_url(self) -> Optional[str]:
        url = settings.outlook_manager_url
        if url:
            return url.rstrip("/")
        return None

    @property
    def _headers(self) -> dict:
        return {"X-API-Key": settings.outlook_manager_api_key or ""}

    @property
    def is_configured(self) -> bool:
        return bool(settings.outlook_manager_url and settings.outlook_manager_api_key)

    async def _get_mail_list(self, client: httpx.AsyncClient, email: str, top: int = 10) -> list:
        """获取收件箱和垃圾箱邮件列表并合并"""
        url = f"{self._base_url}/api/v1/external/mail"
        all_mails = []
        for folder in ["inbox", "junkemail"]:
            params = {"email_address": email, "folder": folder, "top": top}
            try:
                resp = await client.get(url, params=params, headers=self._headers, timeout=10.0)
                if resp.status_code == 200:
                    all_mails.extend(resp.json().get("items", []))
            except Exception as e:
                logger.warning(f"[OutlookClient] 获取邮件列表失败 ({email} - {folder}): {e}")
        
        # 按 received_at 降序排序
        all_mails.sort(key=lambda x: x.get('received_at', ''), reverse=True)
        return all_mails

    async def _get_mail_detail(self, client: httpx.AsyncClient, email: str, message_id: str) -> Optional[str]:
        """获取邮件详情并返回 body_content"""
        url = f"{self._base_url}/api/v1/external/mail/{message_id}"
        params = {"email_address": email}
        try:
            resp = await client.get(url, params=params, headers=self._headers, timeout=15.0)
            resp.raise_for_status()
            data = resp.json()
            return data.get("body_content", "")
        except Exception as e:
            logger.warning(f"[OutlookClient] 获取邮件详情失败 ({message_id}): {e}")
            return None

    def _extract_code(self, text: str) -> Optional[str]:
        """从文本中提取 6 位验证码（支持纯数字及数字字母混合）"""
        # 首先尝试直接匹配 "code is 123456" 等明确的前缀模式，准确率最高
        prefix_match = re.search(r'(?:code\s+is|code:)\s*([A-Za-z0-9]{6})\b', text, re.IGNORECASE)
        if prefix_match:
            return prefix_match.group(1)

        # 降级：提取所有独立的 6 位字母/数字组合
        matches = _CODE_PATTERN.findall(text)
        
        # 为了避免提取到纯字母组成的正常英语单词，优先选择包含数字的6位字符串
        # 备选列表分为含数字和不含数字两种优先级
        has_digit_candidates = []
        pure_alpha_candidates = []

        for m in matches:
            if m.isdigit() and 1900 <= int(m) <= 2099:
                continue # 排除年份
            if m.lower() in _BLACKLIST_WORDS:
                continue # 排除常见单词

            if any(char.isdigit() for char in m):
                has_digit_candidates.append(m)
            else:
                pure_alpha_candidates.append(m)

        # 优先返回含数字的验证码
        if has_digit_candidates:
            return has_digit_candidates[0]
        # 如果只有纯字母的候选者，也只能返回它
        if pure_alpha_candidates:
            return pure_alpha_candidates[0]
        
        return None

    def _is_dreamina_mail(self, subject: str, body_preview: str) -> bool:
        """判断邮件是否来自 Dreamina/CapCut"""
        text = (subject + " " + body_preview).lower()
        return any(kw in text for kw in _SENDER_KEYWORDS)

    async def poll_verification_code(self, email: str, timeout: Optional[int] = None) -> Optional[str]:
        """
        轮询 OutlookManager API，等待 Dreamina 验证码邮件。
        """
        if not self.is_configured:
            logger.error("[OutlookClient] OutlookManager 未配置（OUTLOOK_MANAGER_URL / OUTLOOK_MANAGER_API_KEY）")
            return None

        timeout_sec = timeout or settings.outlook_poll_timeout
        interval = settings.outlook_poll_interval
        
        # 记录开始轮询的时间（放宽2分钟的容差，防止服务器时间差或邮件接收延迟）
        start_time_ts = datetime.now(timezone.utc).timestamp() - 120
        seen_ids: set = set()

        logger.info(f"[OutlookClient] 开始轮询验证码，邮箱={email}，超时={timeout_sec}s")

        async with httpx.AsyncClient(follow_redirects=True) as client:
            elapsed = 0.0
            while elapsed < timeout_sec:
                mails = await self._get_mail_list(client, email, top=5)

                for mail in mails:
                    msg_id = mail.get("id", "")
                    if msg_id in seen_ids:
                        continue
                    
                    # 时间过滤：只处理在此次任务发起之后的邮件
                    received_at_str = mail.get("received_at")
                    if received_at_str:
                        try:
                            # 处理形如 2026-03-02T22:14:55Z 的格式
                            dt_str = received_at_str.replace("Z", "+00:00")
                            mail_ts = datetime.fromisoformat(dt_str).timestamp()
                            if mail_ts < start_time_ts:
                                seen_ids.add(msg_id)
                                continue
                        except Exception as e:
                            logger.error(f"[OutlookClient] 时间解析失败 {received_at_str}: {e}")

                    subject = mail.get("subject", "")
                    body_preview = mail.get("body_preview", "")

                    # 过滤非 Dreamina 邮件
                    if not self._is_dreamina_mail(subject, body_preview):
                        seen_ids.add(msg_id)
                        continue

                    # 先尝试从标题+预览中提取（快速路径），特别是标题可能直接包含验证码
                    code = self._extract_code(subject + " " + body_preview)
                    if not code:
                        # 获取完整邮件详情
                        body = await self._get_mail_detail(client, email, msg_id)
                        if body:
                            code = self._extract_code(body)

                    seen_ids.add(msg_id)

                    if code:
                        logger.info(f"[OutlookClient] 验证码获取成功: {email} -> {code}")
                        return code
                    else:
                        logger.debug(f"[OutlookClient] 找到疑似邮件但未提取到验证码: subject={subject}")

                await asyncio.sleep(interval)
                elapsed += interval

        logger.warning(f"[OutlookClient] 验证码等待超时：{email}（已等待 {timeout_sec}s）")
        return None


# 全局单例
outlook_client = OutlookClient()
