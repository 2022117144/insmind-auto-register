"""
Dreamina Auto Register - Clash 代理管理服务
"""
import asyncio
import httpx
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


@dataclass
class ClashNode:
    """Clash 节点信息"""
    name: str
    node_type: str
    udp: bool = False
    history: Optional[List[Dict]] = None


class ClashManager:
    """Clash Verge 代理管理器"""
    
    def __init__(self):
        self.base_url = settings.clash_controller_url
        self.secret = settings.clash_secret
        self._client: Optional[httpx.AsyncClient] = None
        self._resolved_group: Optional[str] = None  # 缓存宽松匹配结果
        self.last_switch_error: Optional[str] = None
    
    @property
    def proxy_group(self) -> str:
        """每次从配置读取代理组名（支持运行时修改 .env 后重启生效）"""
        return self._resolved_group or settings.clash_proxy_group
    
    @property
    def headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {"Content-Type": "application/json"}
        if self.secret:
            headers["Authorization"] = f"Bearer {self.secret}"
        return headers
    
    async def get_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self.headers,
                timeout=10.0
            )
        return self._client
    
    async def close(self):
        """关闭客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    async def check_connection(self) -> bool:
        """检查 Clash 连接状态"""
        try:
            client = await self.get_client()
            resp = await client.get("/version")
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Clash 连接失败: {e}")
            return False
    
    async def get_proxies(self) -> Dict[str, Any]:
        """获取所有代理信息"""
        client = await self.get_client()
        resp = await client.get("/proxies")
        resp.raise_for_status()
        return resp.json()
    
    async def get_proxy_group_nodes(self) -> List[ClashNode]:
        """获取指定代理组下的所有节点"""
        proxies = await self.get_proxies()
        
        # 每次重新匹配，确保切换订阅后能找到新的代理组
        config_group = settings.clash_proxy_group
        group = proxies.get("proxies", {}).get(config_group)
        
        if group:
            self._resolved_group = config_group
        else:
            # 尝试宽松匹配 (针对带有 Emoji 的场景)
            self._resolved_group = None
            for group_name, group_data in proxies.get("proxies", {}).items():
                if group_data.get("type") in ["Selector", "URLTest", "Fallback", "LoadBalance"]:
                    # 去掉 Emoji 后比较核心名称
                    clean_config = config_group.strip()
                    clean_group = group_name.strip()
                    if clean_config.lower() in clean_group.lower() or clean_group.lower() in clean_config.lower():
                        logger.info(f"由于未找到精确匹配 '{config_group}'，已自动匹配到实际代理组 -> '{group_name}'")
                        self._resolved_group = group_name
                        group = group_data
                        break
        
        if not group:
            logger.warning(f"代理组 '{config_group}' 不存在，可用组: {[k for k,v in proxies.get('proxies', {}).items() if v.get('type') in ['Selector','URLTest','Fallback','LoadBalance']]}")
            return []
        
        nodes = []
        all_proxies = proxies.get("proxies", {})
        
        for node_name in group.get("all", []):
            node_info = all_proxies.get(node_name, {})
            # 跳过特殊节点
            if node_info.get("type") in ["Selector", "URLTest", "Fallback", "LoadBalance"]:
                continue
            
            nodes.append(ClashNode(
                name=node_name,
                node_type=node_info.get("type", "unknown"),
                udp=node_info.get("udp", False),
                history=node_info.get("history", [])
            ))
        
        return nodes
    
    async def switch_node(self, node_name: str) -> bool:
        """切换到指定节点"""
        try:
            client = await self.get_client()
            
            # 切换节点
            resp = await client.put(
                f"/proxies/{self.proxy_group}",
                json={"name": node_name}
            )
            
            if resp.status_code != 204:
                self.last_switch_error = f"status={resp.status_code} body={resp.text}"
                logger.error(f"切换节点失败: {self.last_switch_error}")
                return False
            
            # 关闭所有现有连接
            await self.close_all_connections()
            
            # 等待切换生效
            await asyncio.sleep(3.0)
            
            self.last_switch_error = None
            logger.info(f"已切换到节点: {node_name}")
            return True
            
        except Exception as e:
            self.last_switch_error = f"{type(e).__name__}: {e}"
            logger.error(f"切换节点异常: {self.last_switch_error}")
            return False
    
    async def close_all_connections(self) -> bool:
        """关闭所有连接"""
        try:
            client = await self.get_client()
            resp = await client.delete("/connections")
            return resp.status_code == 204
        except Exception as e:
            logger.error(f"关闭连接失败: {e}")
            return False
    
    async def test_node_delay(self, node_name: str, url: str = "http://www.gstatic.com/generate_204", timeout: int = 5000) -> Optional[int]:
        """测试节点延迟"""
        try:
            client = await self.get_client()
            resp = await client.get(
                f"/proxies/{node_name}/delay",
                params={"url": url, "timeout": timeout}
            )
            
            if resp.status_code == 200:
                data = resp.json()
                return data.get("delay")
            return None
        except Exception as e:
            logger.error(f"测试延迟失败: {e}")
            return None
    
    async def get_current_node(self) -> Optional[str]:
        """获取当前选中的节点"""
        proxies = await self.get_proxies()
        group = proxies.get("proxies", {}).get(self.proxy_group)
        if group:
            return group.get("now")
        return None


# 全局实例
clash_manager = ClashManager()
