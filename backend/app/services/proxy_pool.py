"""
Dreamina Auto Register - 代理池管理服务
"""
import asyncio
import httpx
import logging
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Optional, Set, Any
from dataclasses import dataclass, asdict
from pathlib import Path
from app.core.config import settings

logger = logging.getLogger(__name__)




@dataclass
class ProxyConfig:
    """代理配置信息"""
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    protocol: str = "http"  # http, socks5
    name: str = "unknown"
    group: str = "default"
    node_id: Optional[int] = None
    usage_count: int = 0
    latency: Optional[int] = None
    is_healthy: bool = True
    region_tag: str = "UN" # Unknown
    is_enabled: bool = True
    
    @property
    def url(self) -> str:
        """生成 Playwright 可用的代理 URL"""
        auth = ""
        if self.username and self.password:
            auth = f"{self.username}:{self.password}@"
        return f"{self.protocol}://{auth}{self.host}:{self.port}"
    
    @property
    def unique_id(self) -> str:
        """全局唯一标识，解决诸如 IPRoyal 等同 host 同 port 但 auth 不同的并发调度阻塞问题"""
        auth_str = f"{self.username or ''}:{self.password or ''}"
        return f"{self.host}:{self.port}:{auth_str}"
    
    def to_dict(self) -> Dict:
        return asdict(self)


class ProxyPoolManager:
    """代理池管理器"""
    
    def __init__(self):
        self.proxies: List[ProxyConfig] = []
        self.active_proxies: Set[str] = set()  # 正在被使用的代理 (host:port)
        self.lock = asyncio.Lock()
        self.current_index = 0  # Round Robin index
        self.external_port_map: Dict[str, int] = {}
        
        # Clash API
        self.clash_api_url = settings.clash_controller_url
        self.clash_secret = settings.clash_secret
    


    async def _quick_preflight(self, proxy: ProxyConfig, timeout: float = 5.0) -> Optional[int]:
        """Quick preflight check for a single proxy. Returns latency ms if ok."""
        import time
        try:
            start = time.time()
            client_kwargs = {"timeout": timeout, "verify": False}
            
            # 解决直接从 Python 走 HTTP 测试会被 GFW 针对拉黑的问题
            # 将直接请求替换为走该外部节点对应的本地 Mihomo 映射端口(2000X)
            mapped_port = None
            if proxy.group == "external":
                if proxy.host == "127.0.0.1":
                    mapped_port = proxy.port
                else:
                    mapped_port = self.external_port_map.get(proxy.unique_id)
                if mapped_port:
                    logger.debug(f"Preflight mapping success: {proxy.name} -> 127.0.0.1:{mapped_port}")

            if mapped_port:
                client_kwargs["proxy"] = f"http://127.0.0.1:{mapped_port}"
            elif proxy.group == "external":
                logger.warning(
                    "Preflight skipped for external proxy without mapped port: %s",
                    proxy.unique_id
                )
                return None
            elif proxy.url:
                if proxy.protocol.lower().startswith("socks"):
                    from httpx_socks import AsyncProxyTransport
                    client_kwargs["transport"] = AsyncProxyTransport.from_url(proxy.url)
                else:
                    client_kwargs["proxy"] = proxy.url

            async with httpx.AsyncClient(**client_kwargs) as client:
                # 使用无严格限流的 Cloudflare 探针做轻量级测速
                resp = await client.get("https://cp.cloudflare.com/cdn-cgi/trace", follow_redirects=True)
                if resp.status_code == 200 and "loc=" in resp.text:
                    return int((time.time() - start) * 1000)
        except Exception:
            return None
        return None

    async def load_from_local_ports(self, ports_data: List[Dict[str, Any]], preserve_external: bool = False) -> int:
        """
        从本地端口列表加载代理 (用于本地多端口代理池)
        Args:
            ports_data: 包含端口和元数据的列表, 如 [{"port": 10001, "node_name": "...", "node_id": 1, "usage_count": 0}]
        """
        async with self.lock:
            # 仅清除“非外部”代理 (通常是 internal/clash 代理)
            if preserve_external:
                self.proxies = [p for p in self.proxies if p.group == "external"]
            else:
                self.proxies = []
            # 清除活跃状态 (因为端口变了，旧的活跃状态失效)
            self.active_proxies = set()
            self.current_index = 0
            self.external_port_map = {}
            
            for item in ports_data:
                port = item.get("port")
                if not port: continue
                
                group = item.get("group") or item.get("region_tag") or "default"
                if item.get("is_external"):
                    group = "external"

                config = ProxyConfig(
                    host="127.0.0.1",
                    port=port,
                    name=item.get("node_name") or item.get("name") or f"port-{port}",
                    node_id=item.get("node_id"),
                    usage_count=item.get("usage_count", 0),
                    group=group,
                    is_enabled=item.get("is_enabled", True)
                )
                self.proxies.append(config)

                if group == "external" or item.get("is_external"):
                    ext_host = item.get("original_host")
                    ext_port = item.get("original_port")
                    ext_user = item.get("original_username") or ""
                    ext_pass = item.get("original_password") or ""
                    if ext_host and ext_port:
                        ext_key = f"{ext_host}:{ext_port}:{ext_user}:{ext_pass}"
                        self.external_port_map[ext_key] = port
            
            logger.info(f"内存代理池已加载 {len(self.proxies)} 个本地端口节点")
            
            # 对本次加载的本地节点进行健康和地域检测
            to_validate = [p for p in self.proxies if p.host == "127.0.0.1"]
            if to_validate:
                asyncio.create_task(self.validate_all_proxies(to_validate))
                
            return len(self.proxies)

    async def load_from_list(self, proxy_urls: List[str], group: str = "external", clear_existing: bool = False) -> int:
        """从 URL 或 IP:Port:User:Pass 格式列表加载外部代理"""
        if clear_existing:
            async with self.lock:
                self.proxies = [p for p in self.proxies if p.group != group]
                
        import re
        import hashlib
        new_count = 0
        added_proxies = []
        
        def get_auth_hash(usr: str, pwd: str = "") -> str:
            auth_str = f"{usr or ''}:{pwd or ''}"
            if auth_str == ":": return ""
            return hashlib.md5(auth_str.encode()).hexdigest()[:8]
        
        for line in proxy_urls:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            p = None
            try:
                # 1. 尝试标准格式 protocol://[user:pass@]host:port
                if "://" in line:
                    pattern = r"^(?P<protocol>https?|socks5)://(?:(?P<user>[^:]+):(?P<pass>[^@]+)@)?(?P<host>[^:]+):(?P<port>\d+)$"
                    match = re.match(pattern, line)
                    if match:
                        p = ProxyConfig(
                            host=match.group("host"),
                            port=int(match.group("port")),
                            username=match.group("user"),
                            password=match.group("pass"),
                            protocol=match.group("protocol"),
                            name=f"ext-{match.group('host')}:{match.group('port')}-{get_auth_hash(match.group('user'), match.group('pass'))}",
                            group=group
                        )
                # 2. 尝试 IP:Port:User:Pass 格式 (常用购买格式)
                elif line.count(':') == 3 and '@' not in line:
                    parts = line.split(':')
                    p = ProxyConfig(
                        host=parts[0],
                        port=int(parts[1]),
                        username=parts[2],
                        password=parts[3],
                        protocol="http",
                        name=f"ext-{parts[0]}:{parts[1]}-{get_auth_hash(parts[2], parts[3])}",
                        group=group
                    )
                # 3. 尝试 User:Pass@Host:Port 格式 (IPRoyal 等原生导出格式)
                elif '@' in line:
                    # 分割 User:Pass 和 Host:Port
                    auth_part, server_part = line.split('@', 1)
                    user_pass = auth_part.split(':', 1)
                    host_port = server_part.split(':', 1)
                    
                    if len(user_pass) == 2 and len(host_port) == 2:
                        p = ProxyConfig(
                            host=host_port[0],
                            port=int(host_port[1]),
                            username=user_pass[0],
                            password=user_pass[1],
                            # IPRoyal 等住宅代理通常建议使用 SOCKS5 以获得更好的链路稳定性
                            protocol="socks5" if "socks" in line.lower() or "iproyal" in line.lower() or "@" in line else "http",
                            name=f"ext-{host_port[0]}:{host_port[1]}-{get_auth_hash(user_pass[0], user_pass[1])}",
                            group=group
                        )
                # 4. 尝试 IP:Port 无密码格式
                else:
                    parts = line.split(':')
                    if len(parts) == 2:
                        p = ProxyConfig(
                            host=parts[0],
                            port=int(parts[1]),
                            protocol="http",
                            name=f"ext-{parts[0]}:{parts[1]}",
                            group=group
                        )
                
                if p:
                    p.is_enabled = True
                    # 去重检查 (基于 host:port:username，支持 IPRoyal 同网关多会话)
                    key = f"{p.host}:{p.port}:{p.username}"
                    existing_keys = {f"{ap.host}:{ap.port}:{ap.username}" for ap in self.proxies}
                    if key not in existing_keys:
                        added_proxies.append(p)
                        new_count += 1
            except Exception as e:
                logger.error(f"解析外部代理失败 {line}: {e}")
                
        if added_proxies:
            async with self.lock:
                self.proxies.extend(added_proxies)
                logger.info(f"内存代理池已追加 {new_count} 个外部代理节点 (Group: {group})")

            # 异步启动验证和地域检测
            asyncio.create_task(self.validate_all_proxies(added_proxies))
        
        return new_count

    async def load_from_file(self, file_path: Optional[str] = None, clear_existing: bool = False) -> int:
        """从文件加载外部代理"""
        file_path_value = file_path or settings.ext_proxy_file_path

        if not file_path_value:
            logger.warning("未配置外部代理文件路径")
            return 0

        path = Path(file_path_value)
        paths_to_try = []

        def add_path(p: Path):
            if p not in paths_to_try:
                paths_to_try.append(p)

        add_path(path)

        if not path.is_absolute():
            backend_dir = Path(settings.data_dir).parent
            add_path(backend_dir / path)
            add_path(backend_dir.parent / path)

        chosen_path = None
        for candidate in paths_to_try:
            if candidate.exists():
                chosen_path = candidate
                break

        if not chosen_path:
            logger.warning(
                "外部代理文件不存在，已尝试: " + ", ".join(str(p.resolve()) for p in paths_to_try)
            )
            return 0

        logger.info(f"正在尝试加载外部代理文件: {chosen_path.resolve()}")

        try:
            with open(chosen_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                return await self.load_from_list(lines, clear_existing=clear_existing)
        except Exception as e:
            logger.error(f"读取外部代理文件失败 {file_path_value}: {e}")
            return 0

    async def validate_all_proxies(self, proxies_to_check: List[ProxyConfig]):
        """并发验证代理并检测真实出口IP及地理位置"""
        logger.info(f"开始验证 {len(proxies_to_check)} 个新加载的代理...")
        
        async def check_one(p: ProxyConfig):
            import time
            start_time = time.time()
            try:
                # 显式禁用 trust_env 避免拾取系统代理设置导致 BrokenResourceError
                client_kwargs = {
                    "timeout": 30.0, 
                    "verify": False, 
                    "trust_env": False,
                    "headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
                }
        
                # 同上: 走映射池端口，安全隧道穿透
                mapped_port = None
                if p.group == "external":
                    if p.host == "127.0.0.1":
                        mapped_port = p.port
                    else:
                        mapped_port = self.external_port_map.get(p.unique_id)
                    if mapped_port:
                        logger.debug(f"Latency test mapping success: {p.name} -> 127.0.0.1:{mapped_port}")

                skip_probe = False
                if mapped_port:
                    client_kwargs["proxy"] = f"http://127.0.0.1:{mapped_port}"
                elif p.group == "external":
                    logger.warning(
                        "Latency test skipped for external proxy without mapped port: %s",
                        p.unique_id
                    )
                    p.is_healthy = False
                    p.latency = 9999
                    skip_probe = True
                elif p.url:
                    if p.protocol.lower().startswith("socks"):
                        from httpx_socks import AsyncProxyTransport
                        client_kwargs["transport"] = AsyncProxyTransport.from_url(p.url)
                    else:
                        client_kwargs["proxy"] = p.url
                
                # Trace exactly what proxy URL we are hitting
                proxy_display = client_kwargs.get("proxy") or (f"SOCKS5:{p.url}" if "transport" in client_kwargs else "DIRECT")
                logger.debug(f"Validating node {p.name} via {proxy_display}")

                loc_success = False
                real_country = "UN"
                real_ip = "Unknown"
                last_err = "missing mapped port" if skip_probe else ""

                if not skip_probe:
                    async with httpx.AsyncClient(**client_kwargs) as client:
                        # 预检并获取真实地理位置（多级降级策略避开限流）
                        endpoints = [
                            # 首选: Cloudflare (无频率限制，速度极快)
                            {"type": "cf", "url": "https://cp.cloudflare.com/cdn-cgi/trace"},
                            # 备选 1: ip-api (45次/分钟限流)
                            {"type": "ipapi", "url": "http://ip-api.com/json/?fields=status,countryCode,query"},
                            # 备选 2: ipinfo (无token每天1000次)
                            {"type": "ipinfo", "url": "https://ipinfo.io/json"}
                        ]

                        for ep in endpoints:
                            req_url = ep["url"]
                            try:
                                # 增加一个 url 的 token 注入
                                if ep["type"] == "ipinfo" and hasattr(settings, "ipinfo_token") and settings.ipinfo_token:
                                    req_url += f"?token={settings.ipinfo_token}"

                                resp = await client.get(req_url, timeout=20.0, follow_redirects=True)
                                if resp.status_code == 200:
                                    if ep["type"] == "cf":
                                        text = resp.text
                                        for line in text.split('\n'):
                                            if line.startswith("ip="): real_ip = line.split("=")[1].strip()
                                            elif line.startswith("loc="): real_country = line.split("=")[1].strip().upper()
                                        if real_country and real_ip:
                                            loc_success = True
                                            break
                                    elif ep["type"] == "ipapi":
                                        data = resp.json()
                                        if data.get("status") == "success":
                                            real_country = data.get("countryCode", "").upper()
                                            real_ip = data.get("query", "")
                                            loc_success = True
                                            break
                                    elif ep["type"] == "ipinfo":
                                        data = resp.json()
                                        real_country = data.get("country", "").upper()
                                        real_ip = data.get("ip", "")
                                        if real_country and real_ip:
                                            loc_success = True
                                            break
                            except Exception as e:
                                last_err = f"{type(e).__name__}: {str(e)}"
                                logger.error(f"Endpoint test failed for node {p.name} at {req_url}: {last_err}")
                                continue

                    if loc_success:
                        p.is_healthy = True
                        p.latency = int((time.time() - start_time) * 1000)
                        p.region_tag = real_country
                        logger.info(
                            f"地理预检成功: {p.host}:{p.port} Latency: {p.latency}ms Region: {p.region_tag} IP: {real_ip}"
                        )
                    else:
                        logger.debug(f"所有地理预检端点均失败 {p.host}:{p.port} 最后错误: {last_err}")

                if not loc_success:
                    p.is_healthy = False
                    p.latency = 9999
                    # 通过名字匹配地域 (Fallback 降级匹配)
                    if p.is_healthy and (p.region_tag == "UN" or not p.region_tag):
                        name_u = (p.name or "").upper()
                        mapping = {
                            "HK": ["HK", "香港"], "SG": ["SG", "新加坡", "狮城"], "JP": ["JP", "日本", "东京", "大阪"],
                            "US": ["US", "美国", "洛杉矶", "圣何塞"], "KR": ["KR", "韩国", "首尔"],
                            "TW": ["TW", "台湾", "台北", "新北"], "GB": ["UK", "GB", "英国", "伦敦"],
                            "DE": ["DE", "德国", "法兰克福"], "FR": ["FR", "法国", "巴黎"],
                            "NL": ["NL", "荷兰"], "CA": ["CA", "加拿大"], "AU": ["AU", "澳洲", "澳大利亚"],
                            "ES": ["ES", "西班牙"], "IT": ["IT", "意大利"], "RU": ["RU", "俄罗斯"],
                            "IN": ["IN", "印度"], "BR": ["BR", "巴西"], "ZA": ["ZA", "南非"],
                            "TR": ["TR", "土耳其"], "MY": ["MY", "马来西亚"], "TH": ["TH", "泰国"],
                            "VN": ["VN", "越南"], "PH": ["PH", "菲律宾"], "ID": ["ID", "印尼", "印度尼西亚"],
                            "CH": ["CH", "瑞士"], "SE": ["SE", "瑞典"], "NO": ["NO", "挪威"],
                            "DK": ["DK", "丹麦"], "FI": ["FI", "芬兰"], "IE": ["IE", "爱尔兰"],
                            "AT": ["AT", "奥地利"], "PL": ["PL", "波兰"], "CZ": ["CZ", "捷克"],
                            "GR": ["GR", "希腊"], "PT": ["PT", "葡萄牙"], "AR": ["AR", "阿根廷"],
                            "CL": ["CL", "智利"], "MX": ["MX", "墨西哥"], "AE": ["AE", "阿联酋", "迪拜"],
                            "IL": ["IL", "以色列"], "SA": ["SA", "沙特"], "RO": ["RO", "罗马尼亚"]
                        }
                        for code, kws in mapping.items():
                            if any(kw.upper() in name_u for kw in kws):
                                p.region_tag = code
                                logger.info(f"按节点名称解析国家成功: {p.name} -> {code}")
                                break

            except Exception as e:
                logger.warning(f"代理验证失败 {p.host}:{p.port} [{p.protocol}] url={p.url!r} : {type(e).__name__}: {e}")
                p.is_healthy = False
                p.latency = 9999
            
            # 探测完成后同步回数据库
            if p.node_id:
                try:
                    from app.core.database import async_session_factory
                    from app.models.proxy_node import ProxyNode
                    from sqlalchemy import update
                    from datetime import datetime
                    async with async_session_factory() as db:
                        update_vals = {
                            "is_healthy": p.is_healthy,
                            "latency": p.latency,
                            "last_tested_at": datetime.utcnow()
                        }
                        if p.region_tag and p.region_tag != "UN":
                            update_vals["region_tag"] = p.region_tag
                            
                        await db.execute(
                            update(ProxyNode)
                            .where(ProxyNode.id == p.node_id)
                            .values(**update_vals)
                        )
                        await db.commit()
                except Exception as e:
                    logger.error(f"同步代理 {p.name} 状态到数据库失败: {e}")
        
        # 限制并发数为 5
        semaphore = asyncio.Semaphore(5)
        async def sem_check(p):
            async with semaphore:
                await check_one(p)
        
        await asyncio.gather(*(sem_check(p) for p in proxies_to_check))
        
        # 统计结果
        healthy_count = sum(1 for p in proxies_to_check if p.is_healthy)
        logger.info(f"代理验证完成: {len(proxies_to_check)} 个节点中 {healthy_count} 个可用")
        
        # 从总池中移除彻底不健康的外部节点 (如果在外部加载中)
        # 注意：这里我们保留，但在 acquire 时过滤

    async def load_from_clash(self) -> int:
        """
        从 Clash 控制器加载代理
        注意：这依赖于 Clash API 返回详细节点信息。
        如果返回的是 selector/urltest，我们需要递归查找或只取叶子节点。
        """
        # 如果配置了本地代理池且已有端口，优先使用本地代理池
        if settings.clash_config_path and settings.mihomo_binary_path:
             from app.services.proxy_pool_runner import pool_runner
             if pool_runner.active_ports_info:
                  logger.info("检测到本地代理池运行中，尝试补充数据库映射后再加载...")
                  from app.core.database import async_session_factory
                  from app.models.proxy_node import ProxyNode
                  from sqlalchemy import select
                  
                  async with async_session_factory() as db:
                      stmt = select(ProxyNode).where(ProxyNode.source != "external")
                      nodes = (await db.execute(stmt)).scalars().all()
                      def normalize_name(name):
                          return str(name).strip() if name else ""
                      node_map = {normalize_name(n.name): n for n in nodes}
                      
                  enriched_ports = []
                  for item in pool_runner.active_ports_info:
                      node_name = item.get("name")
                      norm_name = normalize_name(node_name)
                      node = node_map.get(norm_name)
                      if node:
                          enriched_ports.append({
                              "port": item["port"],
                              "name": node_name,
                              "node_name": node.name,
                              "node_id": node.id,
                              "usage_count": node.usage_count or 0,
                              "region_tag": node.region_tag,
                              "is_enabled": bool(node.is_enabled)
                          })
                      else:
                          enriched_ports.append(item)
                          
                  return await self.load_from_local_ports(enriched_ports)
        
        logger.info(f"正在从 Clash 加载代理: {self.clash_api_url}")
        headers = {}
        if self.clash_secret:
            headers["Authorization"] = f"Bearer {self.clash_secret}"
            
        try:
            async with httpx.AsyncClient(timeout=10.0, trust_env=False) as client:
                resp = await client.get(
                    f"{self.clash_api_url}/proxies",
                    headers=headers
                )
                
                if resp.status_code != 200:
                    logger.error(f"Clash API 错误: {resp.status_code}")
                    return 0
                
                data = resp.json()
                proxies_data = data.get("proxies", {})
                
                loaded_count = 0
                new_proxies = []
                
                for name, info in proxies_data.items():
                    # 跳过特殊节点类型
                    node_type = info.get("type", "")
                    if node_type in ["Selector", "URLTest", "Fallback", "LoadBalance", "Direct", "Reject", "Relay", "Match", "Compatible"]:
                        # logger.debug(f"Skipping proxy type {node_type}: {name}")
                        continue
                    
                    # 过滤流量/到期/官网/群组等非节点信息
                    skip_keywords = ["流量", "Traffic", "Expire", "到期", "官网", "频道", "群", "重置", "本次", "剩余", "套餐", "网站"]
                    if any(k in name for k in skip_keywords):
                        # logger.debug(f"Skipping info node: {name}")
                        continue
                    
                    if "server" in info and "port" in info:
                        # 这是一个远程节点的信息
                        protocol = "socks5"
                        if node_type.lower() in ["vmess", "trojan", "shadowsocks", "socks5", "ssr", "snell"]:
                             protocol = "http" # Fallback/treat as http proxy port locally for most clients
                        elif node_type.lower() in ["http", "https"]:
                             protocol = "http"
                             
                        p = ProxyConfig(
                            host=info["server"],
                            port=int(info["port"]),
                            username=info.get("username") or info.get("user") or info.get("cipher") or "", # cipher for ss
                            password=info.get("password") or info.get("uuid") or "",
                            protocol=protocol,
                            name=name,
                            group=info.get("now", "clash")
                        )
                        new_proxies.append(p)
                        loaded_count += 1
                        logger.debug(f"Loaded proxy: {name} ({p.host}:{p.port})")
                    else:
                        pass # logger.warning(f"Skipping proxy {name}: Missing server/port. Keys: {list(info.keys())}")

                # for 循环结束后，批量加入代理池，但不进行探测（因为 remote_ip 无法直连）
                if new_proxies:
                    async with self.lock:
                        self.proxies.extend(new_proxies)
                    self.current_index = 0
                    logger.info(f"成功加载 {loaded_count} 个 Clash 代理节点")

                return loaded_count
                
        except Exception as e:
            logger.error(f"加载代理失败: {e}")
            return 0

    async def acquire_proxy(self, usage_id: Optional[str] = None, strategy: str = "least_used") -> Optional[ProxyConfig]:
        """
        获取一个闲置的代理
        Args:
            usage_id: 使用标识 (如 task_id)
            strategy: 分配策略 (least_used, round_robin)
        """
        async with self.lock:
            total = len(self.proxies)
            if total == 0:
                logger.warning("代理池为空")
                return None
            
            # 获取当前所有空闲且健康的代理
            idle_proxies = [
                p
                for p in self.proxies
                if p.is_healthy
                and p.is_enabled
                and p.unique_id not in self.active_proxies
            ]

            # 若无空闲代理，尝试快速自愈一小批不健康代理
            if not idle_proxies:
                revive_candidates = [
                    p for p in self.proxies
                    if (not p.is_healthy)
                    and p.is_enabled
                    and p.unique_id not in self.active_proxies
                ]
                if revive_candidates:
                    revived = 0
                    for p in revive_candidates[:3]:
                        latency = await self._quick_preflight(p)
                        if latency is not None:
                            p.is_healthy = True
                            p.latency = latency
                            revived += 1
                    if revived:
                        idle_proxies = [
                            p
                            for p in self.proxies
                            if p.is_healthy
                            and p.is_enabled
                            and p.unique_id not in self.active_proxies
                        ]
            
            if not idle_proxies:
                enabled_count = sum(1 for p in self.proxies if p.is_enabled)
                healthy_count = sum(1 for p in self.proxies if p.is_healthy)
                active_count = len(self.active_proxies)

                group_stats = {}
                for p in self.proxies:
                    group = p.group or "default"
                    stat = group_stats.setdefault(
                        group,
                        {"total": 0, "enabled": 0, "healthy": 0, "active": 0, "idle": 0}
                    )
                    stat["total"] += 1
                    if p.is_enabled:
                        stat["enabled"] += 1
                    if p.is_healthy:
                        stat["healthy"] += 1
                    if p.unique_id in self.active_proxies:
                        stat["active"] += 1
                    if p.is_enabled and p.is_healthy and p.unique_id not in self.active_proxies:
                        stat["idle"] += 1

                logger.warning(
                    "没有可用的闲置代理 (total=%s enabled=%s healthy=%s active=%s group_stats=%s)",
                    total, enabled_count, healthy_count, active_count, group_stats
                )
                return None

            selected_proxy = None
            
            if strategy == "least_used":
                # 最少使用优先
                selected_proxy = min(idle_proxies, key=lambda p: p.usage_count)
            else:
                # 默认 Round Robin (在空闲节点中查找)
                # 为了保持 RR 语义，我们在全局索引基础上找下一个可用的
                for i in range(total):
                    idx = (self.current_index + i) % total
                    p = self.proxies[idx]
                    if p.unique_id not in self.active_proxies:
                        selected_proxy = p
                        self.current_index = (idx + 1) % total
                        break
            
            if selected_proxy:
                key = selected_proxy.unique_id
                self.active_proxies.add(key)
                selected_proxy.usage_count += 1
                
                # 异步同步到数据库 (不阻塞主流程)
                if selected_proxy.node_id:
                    asyncio.create_task(self._sync_usage_to_db(selected_proxy.node_id, selected_proxy.usage_count))
                
                usage_label = usage_id or "unknown"
                logger.debug(f"分配代理 [{strategy}]: {selected_proxy.name} (usage: {selected_proxy.usage_count}) -> {usage_label}")
                return selected_proxy
            
            return None

    async def _sync_usage_to_db(self, node_id: int, usage_count: int):
        """同步使用次数到数据库"""
        from app.core.database import async_session_factory
        from app.models.proxy_node import ProxyNode
        from sqlalchemy import update
        try:
            async with async_session_factory() as db:
                await db.execute(
                    update(ProxyNode)
                    .where(ProxyNode.id == node_id)
                    .values(usage_count=usage_count)
                )
                await db.commit()
        except Exception as e:
            logger.error(f"同步代理使用次数失败 (ID: {node_id}): {e}")

    async def release_proxy(self, proxy: ProxyConfig):
        """释放代理"""
        if not proxy:
            return
            
        async with self.lock:
            key = proxy.unique_id
            if key in self.active_proxies:
                self.active_proxies.remove(key)
                logger.debug(f"释放代理: {proxy.name}")

    def get_status(self) -> Dict:
        """获取池状态"""
        enabled_count = sum(1 for p in self.proxies if p.is_enabled)
        return {
            "total": enabled_count,
            "active": len(self.active_proxies),
            "idle": enabled_count - len(self.active_proxies)
        }

    async def get_detailed_status(self) -> Dict[str, int]:
        """获取更详细的池状态"""
        async with self.lock:
            total = len(self.proxies)
            enabled = sum(1 for p in self.proxies if p.is_enabled)
            healthy = sum(1 for p in self.proxies if p.is_healthy)
            active = len(self.active_proxies)
            idle = sum(
                1 for p in self.proxies
                if p.is_healthy and p.is_enabled and p.unique_id not in self.active_proxies
            )
            return {
                "total": total,
                "enabled": enabled,
                "healthy": healthy,
                "active": active,
                "idle": idle,
            }

# 全局实例
proxy_pool = ProxyPoolManager()
