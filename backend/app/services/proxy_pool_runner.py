import yaml
import subprocess
import atexit
import logging
import asyncio
import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
from app.core.config import settings

logger = logging.getLogger(__name__)


class ProxyPoolRunner:
    """
    负责启动一个临时的 Mihomo 实例，
    将用户的节点映射到本地的一组端口 (listeners)，
    从而实现真正的并发 IP 出口。
    """

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.active_ports: List[int] = []
        self.active_ports_info: List[Dict[str, Any]] = []

    def _load_user_config(self) -> dict:
        if (
            not settings.clash_config_path
            or not Path(settings.clash_config_path).exists()
        ):
            logger.warning("未配置 Clash 配置文件路径或文件不存在")
            return {}

        try:
            with open(settings.clash_config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"读取 Clash 配置失败: {e}")
            return {}

    async def start(
        self,
        allowed_proxy_names: Optional[List[str]] = None,
        external_proxies: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        self.stop()  # Ensure previous instance is dead

        if (
            not settings.mihomo_binary_path
            or not Path(settings.mihomo_binary_path).exists()
        ):
            logger.warning("未找到 Mihomo 可执行文件，跳过本地代理池启动")
            return []

        # Handle explicit empty list - don't start anything if BOTH are empty
        if (
            allowed_proxy_names is not None
            and not allowed_proxy_names
            and not external_proxies
        ):
            logger.info("未提供任何允许的代理节点或外部节点，跳过本地代理池启动")
            return []

        config = self._load_user_config()
        if not config:
            return []

        all_proxies = config.get("proxies", [])
        if not all_proxies:
            logger.warning("Clash 配置中未找到 proxies")
            return []

        valid_proxies = []
        if allowed_proxy_names is not None:
            allowed_set = set(allowed_proxy_names)
            for p in all_proxies:
                if p.get("name") in allowed_set:
                    valid_proxies.append(p)
        else:
            # Common keywords for informational nodes in subscriptions
            skip_keywords = [
                "流量",
                "Traffic",
                "Expire",
                "到期",
                "官网",
                "频道",
                "群",
                "重置",
                "本次",
                "剩余",
                "套餐",
                "网站",
            ]

            for p in all_proxies:
                # 1. Check type
                if p.get("type") in [
                    "Selector",
                    "URLTest",
                    "Fallback",
                    "LoadBalance",
                    "Direct",
                    "Reject",
                    "Relay",
                    "Match",
                    "Compatible",
                ]:
                    continue

                # 2. Check name keywords
                name = p.get("name", "")
                if any(k in name for k in skip_keywords):
                    continue

                valid_proxies.append(p)

        selected_proxies = valid_proxies
        if external_proxies:
            selected_proxies.extend(external_proxies)

        if not selected_proxies:
            logger.warning("未找到有效/启用的代理节点")
            return []

        count = len(selected_proxies)

        listeners = []
        rules = []
        self.active_ports_info = []  # Store detailed info
        self.active_ports = []  # Backward compatibility if needed, but we should use info

        start_port = settings.proxy_pool_start_port

        for i, p in enumerate(selected_proxies):
            port = start_port + i
            listeners.append(
                {
                    "name": f"pool-{port}",
                    "type": "mixed",
                    "port": port,
                }
            )

            rules.append(f"IN-PORT,{port},{p['name']}")

            is_external = bool(
                p.get("__is_external") or str(p.get("name", "")).startswith("ext-")
            )
            self.active_ports_info.append(
                {
                    "port": port,  # Local pool port
                    "name": p["name"],
                    "type": p.get("type", "unknown"),
                    "original_host": p.get("server"),
                    "original_port": p.get("port"),
                    "original_username": p.get("username"),
                    "original_password": p.get("password"),
                    "original_protocol": p.get("protocol") or p.get("type"),
                    "is_external": is_external,
                    "group": "external" if is_external else p.get("group"),
                }
            )
        # Resolve hostnames to real IPs to bypass local DNS hijacking (Fake-IP)
        # Apply to ALL nodes (clash and external) to ensure they bypass the desktop Clash's Fake-IP (198.18.x.x)
        hosts_map = await self._resolve_hostnames(selected_proxies)

        # 将桌面 Clash 插入节点列表开头 (不再需要，依靠系统代理/TUN)
        proxies_to_write = []

        for p in selected_proxies:
            p_copy = dict(p)
            # 简化逻辑：依靠本地 Clash Verge 的系统代理/TUN 模式来处理出海
            # 不再手动设置 dialer-proxy，避免多重嵌套导致的握手超时或回环
            if p.get("__is_external") or p.get("name", "").startswith("ext-"):
                p_copy["udp"] = False
                if "protocol" in p:
                    p_copy["type"] = p["protocol"]
                elif "type" in p:
                    p_copy["type"] = p["type"]
                else:
                    p_copy["type"] = "socks5"
                p_copy["skip-cert-verify"] = True
            proxies_to_write.append(p_copy)

        pool_config = {
            "mode": "rule",
            "log-level": "info",
            "external-controller": f"127.0.0.1:{settings.proxy_pool_controller_port}",
            "secret": "jimeng-pool",
            "ipv6": False,
            "allow-lan": False,
            "dns": {
                "enable": True,
                "ipv6": False,
                "nameserver": ["223.5.5.5", "1.1.1.1"],
                "default-nameserver": ["223.5.5.5", "1.1.1.1"],
            },
            "hosts": hosts_map,
            "proxies": proxies_to_write,
            "listeners": listeners,
            "rules": rules,
        }

        config_path = Path("jimeng_pool_config.yaml")
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(pool_config, f, allow_unicode=True)

        cmd = [settings.mihomo_binary_path, "-d", ".", "-f", str(config_path)]

        logger.info(
            f"正在启动本地代理池进程，端口范围: {start_port} - {start_port + count - 1}"
        )
        try:
            self.process = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            import time

            time.sleep(2)  # 给 2s 时间让 Mihomo 初始化并监听端口
            logger.info(f"本地代理池启动成功, PID: {self.process.pid}")
            return self.active_ports_info
        except Exception as e:
            logger.error(f"启动 Mihomo 失败: {e}")
            return []

    async def _resolve_hostnames(self, proxies: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Extract server domains from proxies and resolve them to real IPs using HTTPDNS.
        This bypasses local DNS poisoning/Fake-IP issues.
        """
        import httpx

        # Debug logging to file
        def debug_log(msg):
            logger.debug(msg)

        debug_log("Starting _resolve_hostnames (async)")

        domains = set()
        for p in proxies:
            # 跳过原本就在 hosts 中的 IP，以及外部代理节点 (以免触发 Clash 的 Fake-IP 或 DIRECT 路由逻辑错误)
            if p.get("__is_external") or p.get("name", "").startswith("ext-"):
                continue
            server = p.get("server")
            if server and not server.replace(".", "").isdigit():
                domains.add(server)

        debug_log(f"Found domains: {domains}")

        if not domains:
            return {}

        hosts_map = {}

        async def resolve_one(domain: str):
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    # Use DNSPod HTTPDNS (119.29.29.29)
                    url = f"http://119.29.29.29/d?dn={domain}"
                    debug_log(f"Requesting {url}")
                    resp = await client.get(url)
                    debug_log(f"Response: {resp.status_code} {resp.text}")

                    if resp.status_code == 200:
                        ip = resp.text.strip().split(";")[0]  # Handle multiple IPs
                        if ip and ip.count(".") == 3:  # Basic IP check
                            return domain, ip
            except Exception as e:
                debug_log(f"Exception for {domain}: {e}")
                logger.warning(f"Failed to resolve {domain}: {e}")
            return domain, None

        # Concurrent resolution
        results = await asyncio.gather(*(resolve_one(d) for d in domains))
        for domain, ip in results:
            if ip:
                hosts_map[domain] = ip

        debug_log(f"Returning hosts_map: {hosts_map}")
        return hosts_map

    def stop(self):
        """外科手术式清理：仅杀掉关联到本项目的 Mihomo 进程"""
        logger.info("正在执行本地代理池精准清理...")
        import subprocess

        try:
            # 1. 优先杀掉自己管理的进程（带子进程树）
            if self.process and hasattr(self.process, "pid"):
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(self.process.pid)],
                    capture_output=True,
                    check=False,
                )

            # 2. 精准寻找加载了 jimeng_pool_config.yaml 的僵尸进程并清理
            # 使用 PowerShell 的 Get-CimInstance 配合 CommandLine 过滤，避免误杀用户的桌面 Clash Verge
            ps_cmd = (
                "Get-CimInstance Win32_Process | "
                "Where-Object { $_.CommandLine -like '*jimeng_pool_config.yaml*' } | "
                "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
            )
            subprocess.run(
                ["powershell", "-Command", ps_cmd], capture_output=True, check=False
            )

            self.process = None
            logger.info("本地代理池精准清理完成")
        except Exception as e:
            logger.error(f"Stop process error: {e}")

        if hasattr(self, "log_file") and self.log_file:
            try:
                self.log_file.close()
            except:
                pass


# 全局实例
pool_runner = ProxyPoolRunner()

# 注册退出清理
atexit.register(pool_runner.stop)
