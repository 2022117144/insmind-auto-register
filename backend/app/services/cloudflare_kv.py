"""
Dreamina Auto Register - Cloudflare KV 验证码获取服务 (Centralized Poller)
"""
import asyncio
import httpx
from typing import Optional, Dict, Any, Set
from datetime import datetime
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class CloudflareKVClient:
    """Cloudflare KV 客户端 (支持聚合轮询)"""
    
    def __init__(self):
        self.account_id = settings.cf_account_id
        self.namespace_id = settings.cf_kv_namespace_id
        self.api_token = settings.cf_api_token
        self.poll_interval = settings.kv_poll_interval # 默认 3-5秒
        self.poll_timeout = settings.kv_poll_timeout
        self._client: Optional[httpx.AsyncClient] = None
        
        # 聚合轮询相关
        self._pending_emails: Set[str] = set()
        self._results_cache: Dict[str, str] = {} # email -> code
        self._poller_task: Optional[asyncio.Task] = None
        self._notify_events: Dict[str, asyncio.Event] = {} # email -> Event
        self._lock = asyncio.Lock()
    
    @property
    def base_url(self) -> str:
        return f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/storage/kv/namespaces/{self.namespace_id}"
    
    @property
    def headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
    
    @property
    def is_configured(self) -> bool:
        """检查是否已配置"""
        return all([self.account_id, self.namespace_id, self.api_token])
    
    async def get_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers=self.headers,
                timeout=30.0
            )
        return self._client
    
    async def _poller_loop(self):
        """后台轮询循环"""
        logger.info("KV 聚合轮询器已启动")
        while True:
            try:
                if not self._pending_emails:
                    # 如果没有等待的任务，稍微休眠长一点，或者直接等待
                    await asyncio.sleep(1.0)
                    continue
                
                # 收集当前需要查询的 key
                # 策略:
                # 1. 如果 keys 数量少 (<10)，可以使用 Multi-Get (API并行)
                # 2. 如果 keys 数量多，应该使用 List Keys API 拿所有最近更新的
                
                # 这里为了简单且尽量少用额度，我们采用并发 Get 模式，但限制并发数
                # 或者如果有 List API，List 是更好的（一次请求拿所有）
                
                # 使用 List API 拿前缀 (假设 key 就是 email)
                # KV List API 支持 prefix，但不支持 multiple keys
                # 如果 email 前缀分散，List 效率低。
                
                # 折中方案：对每个 pending email 发起一次 Get，但控制在此 Loop 内
                # 这样 20 个任务 每 3 秒 轮询一次，仍然是 20 QPS
                # 还是有点高。
                
                # 优化：Cloudflare KV 写入延迟通常在 1s-60s
                # 如果我们能 List namespace keys limited to recent time? 不支持
                
                # 既然用户担心 concurrency rate limit，我们必须聚合。
                # 假设所有注册用的 email 都有统一前缀 (例如 "reg_")
                # 那么我们可以 list keys with prefix="reg_"
                
                # 这里先实现：并发 Get，但通过 Semaphore 限制速率
                
                current_emails = list(self._pending_emails)
                # 每次轮询 最多处理 5 个并发请求，避免突发
                # 实际上这个 Loop 应该每 3 秒运行一次“批次”
                
                results = await self._batch_get_values(current_emails)
                
                for email, code in results.items():
                    if code:
                        self._results_cache[email] = code
                        # 触发事件
                        if email in self._notify_events:
                            self._notify_events[email].set()
                        # 从 pending 中移除 (在 poll_verification_code 中移除更安全? 不，这里移除防止重复查询)
                        async with self._lock:
                            if email in self._pending_emails:
                                self._pending_emails.remove(email)
                                logger.info(f"聚合轮询: 成功获取 {email} -> {code}")
                
            except Exception as e:
                logger.error(f"KV 轮询循环异常: {e}")
            
            await asyncio.sleep(self.poll_interval)

    async def _batch_get_values(self, emails: list) -> Dict[str, str]:
        """批量获取值"""
        results = {}
        client = await self.get_client()
        
        async def fetch(email):
            try:
                resp = await client.get(f"{self.base_url}/values/{email}")
                if resp.status_code == 200:
                    val = resp.text
                    # 简单解析
                    if "code" in val:
                         import json
                         try:
                             data = json.loads(val)
                             return email, str(data.get("code") or data.get("verification_code"))
                         except:
                             pass
                    if len(val) == 6:
                        return email, val
                return email, None
            except:
                return email, None

        # 限制并发为 5
        tasks = []
        # 分批处理
        chunk_size = 5
        for i in range(0, len(emails), chunk_size):
            chunk = emails[i:i+chunk_size]
            tasks = [fetch(e) for e in chunk]
            batch_results = await asyncio.gather(*tasks)
            for e, c in batch_results:
                if c:
                    results[e] = c
            # 小暂停，遵守速率限制
            await asyncio.sleep(0.5)
            
        return results

    async def start_poller(self):
        if self._poller_task is None or self._poller_task.done():
            self._poller_task = asyncio.create_task(self._poller_loop())

    async def stop_poller(self):
        if self._poller_task:
            self._poller_task.cancel()
            try:
                await self._poller_task
            except:
                pass
            self._poller_task = None
            
    async def poll_verification_code(self, email: str, timeout: Optional[int] = None) -> Optional[str]:
        """
        等待验证码 (聚合版)
        """
        if timeout is None:
            timeout = self.poll_timeout # 60s
            
        # 1. 加入等待队列
        event = asyncio.Event()
        async with self._lock:
            self._pending_emails.add(email)
            self._notify_events[email] = event
            # 确保 Poller 运行
            await self.start_poller()
            
        # 2. 等待 Event 或超时
        try:
            # 检查缓存（可能已经由 Poller 获取）
            if email in self._results_cache:
                return self._results_cache.pop(email)
                
            await asyncio.wait_for(event.wait(), timeout=timeout)
            return self._results_cache.pop(email, None)
            
        except asyncio.TimeoutError:
            logger.warning(f"验证码等待超时: {email}")
            async with self._lock:
                if email in self._pending_emails:
                    self._pending_emails.remove(email)
                if email in self._notify_events:
                    del self._notify_events[email]
            return None
            
    async def close(self):
        """关闭客户端"""
        await self.stop_poller()
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    # ... 保留 test_connection 等辅助方法 ...
    async def test_connection(self) -> Dict[str, Any]:
        """测试连接"""
        try:
            client = await self.get_client()
            # 尝试列出 key verify access
            resp = await client.get(f"{self.base_url}/keys?limit=10")
            if resp.status_code == 200:
                return {"success": True, "message": "Connection successful"}
            else:
                return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


# 全局实例
cf_kv_client = CloudflareKVClient()
