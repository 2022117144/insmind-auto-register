import httpx
import logging
from typing import Optional, Dict, Any

from app.core.config import settings

logger = logging.getLogger(__name__)

# 区域匹配映射表 (用于将各种名字解析为统一的国家简码)
REGION_PREFIX_MAP = {
    "US": "us",
    "USA": "us",
    "美国": "us",
    "HK": "hk",
    "HONGKONG": "hk",
    "香港": "hk",
    "JP": "jp",
    "JAPAN": "jp",
    "日本": "jp",
    "SG": "sg",
    "SINGAPORE": "sg",
    "新加坡": "sg",
    "TW": "tw",
    "TAIWAN": "tw",
    "台湾": "tw",
    "CA": "ca",
    "CANADA": "ca",
    "加拿大": "ca",
    "GB": "gb",
    "UK": "gb",
    "英国": "gb",
    "DE": "de",
    "GERMANY": "de",
    "德国": "de",
    "KR": "kr",
    "KOREA": "kr",
    "韩国": "kr",
    "CN": "cn",
    "CHINA": "cn",
    "中国": "cn",
}

# 物理区域 -> Jimeng API Token 前缀映射
# Jimeng 通常按大区路由，欧美->us, 东南亚->sg等
JIMENG_TOKEN_PREFIX_MAP = {
    "us": "us",
    "ca": "ca",
    "gb": "gb",
    "de": "de",
    "fr": "fr",
    "nl": "nl",
    "eu": "eu",
    "hk": "hk",
    "tw": "tw",
    "kr": "hk",
    "jp": "jp",
    "sg": "sg",
    "my": "sg",
    "th": "sg",
    "id": "sg",
    "cn": "cn"
}


class JimengClient:
    """
    Client for the standalone Jimeng API service.
    Directly calls native endpoints like /token/check, /token/points, /token/receive.
    """

    def __init__(
        self,
        session_id: str,
        region: Optional[str] = None,
        proxy_url: Optional[str] = None,
    ):
        self.session_id = session_id
        self.region = region
        self.proxy_url = proxy_url

    def _get_formatted_token(self) -> str:
        """
        根据区域和代理配置格式化 Token。
        格式: [ProxyURL@][RegionPrefix-]session_id
        """
        raw_session = self.session_id
        # 如果 session_id 已经包含了区域前缀（如 us-xxx），先提取原始 session
        prefix = ""
        if "-" in raw_session:
            parts = raw_session.split("-", 1)
            # 常见包含前缀的情况
            if parts[0].lower() in JIMENG_TOKEN_PREFIX_MAP.values():
                prefix = parts[0].lower()
                raw_session = parts[1]

        # 确定最终使用的前缀
        final_prefix = prefix
        if self.region:
            reg = self.region.lower()
            if reg in JIMENG_TOKEN_PREFIX_MAP:
                final_prefix = JIMENG_TOKEN_PREFIX_MAP[reg]
            else:
                # 兜底：看是否有现成的前缀
                mapped = REGION_PREFIX_MAP.get(self.region.upper())
                if mapped and mapped in JIMENG_TOKEN_PREFIX_MAP:
                    final_prefix = JIMENG_TOKEN_PREFIX_MAP[mapped]

        token = raw_session
        if final_prefix and final_prefix != "cn":
            token = f"{final_prefix}-{token}"

        # 添加代理前缀
        if self.proxy_url:
            token = f"{self.proxy_url}@{token}"

        return token

    @staticmethod
    def resolve_region(
        node_name: Optional[str], region_tag: Optional[str] = None
    ) -> Optional[str]:
        """尝试从节点名称或标签中解析出标准区域编码"""
        # 1. 优先使用已有的 region_tag
        if region_tag and region_tag.lower() not in ["default", "none", "", "un"]:
            tag = region_tag.lower()
            if tag in ["us", "hk", "jp", "sg", "tw", "ca", "gb", "de", "kr", "cn"]:
                return tag

            # 强化查表逻辑
            for key, code in REGION_PREFIX_MAP.items():
                if key.lower() == tag:
                    return code

            # 如果 tag 本身是国家代码（如 'tw', 'gb'），也尝试返回
            if len(tag) == 2:
                return tag

        # 2. 如果没有有效标签，解析节点名称
        if not node_name:
            return None

        name = node_name.upper()
        # 增加一些常见的缩写匹配
        for key, code in REGION_PREFIX_MAP.items():
            if key in name:
                return code

        # 增加对常见简称的正则匹配
        import re

        codes = ["US", "HK", "JP", "SG", "CN", "TW", "KR", "GB", "CA", "DE"]
        for c in codes:
            if re.search(rf"(?i)\b{c}\b", name):
                return c.lower()

        return None

    @staticmethod
    async def resolve_region_by_ip(proxy_node_name: Optional[str]) -> Optional[str]:
        """
        当 proxy_node_name 为 ext-IP:PORT 格式时，通过 IP 地理位置 API 探测区域。
        结果缓存在类变量中避免重复请求。
        """
        if not proxy_node_name:
            return None

        # 解析 ext-IP:PORT 格式
        import re

        match = re.match(r"^ext-(\d+\.\d+\.\d+\.\d+):(\d+)$", proxy_node_name)
        if not match:
            return None

        ip = match.group(1)

        # 检查缓存
        if not hasattr(JimengClient, "_ip_region_cache"):
            JimengClient._ip_region_cache = {}
        if ip in JimengClient._ip_region_cache:
            return JimengClient._ip_region_cache[ip]

        # 通过 ip-api.com 查询
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"http://ip-api.com/json/{ip}?fields=status,countryCode"
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status") == "success":
                        country = data.get("countryCode", "").lower()
                        # 映射到 jimeng 支持的区域
                        region_map = {
                            "us": "us",
                            "hk": "hk",
                            "jp": "jp",
                            "sg": "sg",
                            "cn": "cn",
                            "tw": "hk",
                            "kr": "hk",
                            "gb": "us",
                            "de": "us",
                            "fr": "us",
                            "nl": "us",
                        }
                        region = region_map.get(country, "hk")  # 海外默认 hk
                        JimengClient._ip_region_cache[ip] = region
                        logger.info(
                            f"[JimengClient] IP {ip} 地理位置探测: {country} -> region={region}"
                        )
                        return region
        except Exception as e:
            logger.warning(f"[JimengClient] IP 地理位置探测失败 ({ip}): {e}")

        return None

    @staticmethod
    async def resolve_region_async(
        node: Any, db: Optional[Any] = None
    ) -> Optional[str]:
        """
        [深度解析] 异步解析区域。
        如果静态解析失败，则通过 proxy_pool 触发 IP 地理位置检测。
        """
        from app.services.proxy_pool import proxy_pool, ProxyConfig

        # 1. 先尝试静态解析
        region = JimengClient.resolve_region(node.name, node.region_tag)
        if region and region != "un":
            return region

        # 2. 如果是外部代理 (含有 IP:Port)，尝试在线探测
        if node.host and node.port:
            logger.info(
                f"[JimengClient] Static resolve failed for {node.host}, triggering Geo-detection..."
            )
            p_config = ProxyConfig(
                host=node.host,
                port=node.port,
                username=getattr(node, "username", None),
                password=getattr(node, "password", None),
                protocol=getattr(node, "protocol", "http"),
                name=node.name,
            )
            await proxy_pool.validate_all_proxies([p_config])

            if p_config.region_tag and p_config.region_tag != "UN":
                detected_region = p_config.region_tag.lower()
                logger.info(
                    f"[JimengClient] Geo-detected region for {node.host}: {detected_region}"
                )

                # 同步回数据库 (如果提供了 db)
                if db:
                    from sqlalchemy import update
                    from app.models import ProxyNode

                    try:
                        await db.execute(
                            update(ProxyNode)
                            .where(ProxyNode.id == node.id)
                            .values(region_tag=detected_region)
                        )
                        await db.commit()
                        logger.info(
                            f"[JimengClient] Updated ProxyNode {node.id} region_tag to {detected_region}"
                        )
                    except Exception as e:
                        logger.error(f"Failed to sync detected region to DB: {e}")

                return detected_region

        return "un"

    async def _resolve_fallback_url(self, fallback) -> Optional[str]:
        """将 fallback 代理转换为可用的 URL"""
        if fallback.group == "external" or fallback.host == "127.0.0.1":
            return fallback.url
        try:
            from app.services.clash_manager import clash_manager

            switched = await clash_manager.switch_node(fallback.name)
            if switched and settings.clash_proxy_port:
                protocol = settings.clash_proxy_protocol or "http"
                return f"{protocol}://127.0.0.1:{settings.clash_proxy_port}"
        except Exception as e:
            logger.error(f"[JimengClient] 兜底切换节点失败: {e}")
        return None

    async def _with_proxy_fallback(self, operation, operation_name: str):
        """通用代理兜底包装：失败 → 换代理 → 重试（最多 2 次兜底）"""
        from app.services.proxy_pool import proxy_pool

        res, is_proxy_err = await operation()
        if not is_proxy_err:
            return res

        tried_urls = {self.proxy_url}
        for attempt in range(2):
            fallback = await proxy_pool.acquire_proxy(strategy="least_used")
            if not fallback:
                break
            try:
                fallback_url = await self._resolve_fallback_url(fallback)
                if not fallback_url or fallback_url in tried_urls:
                    continue
                tried_urls.add(fallback_url)
                logger.warning(
                    f"[JimengClient] {operation_name} 代理异常，兜底重试 #{attempt + 1}: {fallback_url}"
                )
                self.proxy_url = fallback_url
                res, is_proxy_err = await operation()
                if not is_proxy_err:
                    return res
            finally:
                await proxy_pool.release_proxy(fallback)
        return res

    @staticmethod
    def _is_proxy_error(resp) -> bool:
        """判断 HTTP 响应是否为代理相关错误"""
        text = resp.text.lower()
        return (
            "econnrefused" in text
            or "timeout" in text
            or "proxy" in text
            or resp.status_code >= 500
        )

    async def check_token_status(self) -> bool:
        """检查 Token 有效性，遭遇代理故障时自动兜底重试"""

        async def _do() -> tuple[bool, bool]:
            token = self._get_formatted_token()
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        f"{settings.jimeng_api_url}/token/check", json={"token": token}
                    )
                    if resp.status_code == 200:
                        return resp.json().get("live", False), False
                    else:
                        logger.error(
                            f"[JimengClient] API Token Status Error {resp.status_code}: {resp.text} | Token Prefix sent: {token[:30]}..."
                        )
                        return False, self._is_proxy_error(resp)
            except Exception as e:
                logger.error(
                    f"[JimengClient] Connection Error (check_token_status): {e}"
                )
                return False, True

        return await self._with_proxy_fallback(_do, "Token检查")

    async def get_credits(self) -> Optional[Dict[str, int]]:
        """获取积分信息，遭遇代理故障时自动兜底重试"""

        async def _do() -> tuple[Optional[Dict[str, int]], bool]:
            token = self._get_formatted_token()
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        f"{settings.jimeng_api_url}/token/points",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    if resp.status_code == 200:
                        results = resp.json()
                        if results and isinstance(results, list):
                            data = results[0].get("points", {})
                            return {
                                "gift": int(data.get("giftCredit", 0)),
                                "purchase": int(data.get("purchaseCredit", 0)),
                                "vip": int(data.get("vipCredit", 0)),
                                "total": int(data.get("totalCredit", 0)),
                            }, False
                        return None, False
                    else:
                        return None, self._is_proxy_error(resp)
            except Exception as e:
                logger.error(f"[JimengClient] Failed to get credits: {e}")
                return None, True

        return await self._with_proxy_fallback(_do, "获取积分")

    async def daily_checkin(self) -> Optional[Dict[str, Any]]:
        """每日签到/领取积分，遭遇代理故障时自动兜底重试"""

        async def _do() -> tuple[Optional[Dict[str, Any]], bool]:
            token = self._get_formatted_token()
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        f"{settings.jimeng_api_url}/token/receive",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    if resp.status_code == 200:
                        results = resp.json()
                        if results and isinstance(results, list):
                            data = results[0]
                            credits = data.get("credits", {})
                            return {
                                "success": data.get("received", False),
                                "credits": {
                                    "gift": int(credits.get("giftCredit", 0)),
                                    "purchase": int(credits.get("purchaseCredit", 0)),
                                    "vip": int(credits.get("vipCredit", 0)),
                                    "total": int(credits.get("totalCredit", 0)),
                                },
                            }, False
                        return {"success": False}, False
                    else:
                        return {"success": False}, self._is_proxy_error(resp)
            except Exception as e:
                logger.error(f"[JimengClient] Failed to perform checkin: {e}")
                return {"success": False}, True

        return await self._with_proxy_fallback(_do, "每日签到")
