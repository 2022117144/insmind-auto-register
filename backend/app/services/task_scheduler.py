"""
Dreamina Auto Register - 任务调度并发管理器
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from uuid import uuid4

from app.models import TaskRecord
from app.services.proxy_pool import proxy_pool, ProxyConfig
from app.services.register_engine import register_engine
from app.core.database import async_session_factory
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class Job:
    """内部工作任务"""
    job_id: str
    parent_task_id: str
    email_params: Optional[Dict] = None  # 指定邮箱参数，用于重新入队
    proxy_strategy: str = "least_used"
    retry_count: int = 0
    max_retries: int = 3


from app.core.config import settings

class TaskScheduler:
    """并发调度器"""
    
    def __init__(self, max_concurrency: Optional[int] = None):
        self.max_concurrency = max_concurrency or settings.max_concurrency
        self.queue: asyncio.Queue[Job] = asyncio.Queue()
        self.workers: List[asyncio.Task] = []
        self.running = False
        
        # 统计数据
        self.active_workers = 0
        self.completed_jobs = 0
        self.failed_jobs = 0
    
    async def start(self):
        """启动调度器"""
        if self.running:
            return
            
        self.running = True
        logger.info(f"启动任务调度器 (并发数: {self.max_concurrency})")
        
        # 启动 Worker
        for i in range(self.max_concurrency):
            t = asyncio.create_task(self._worker_loop(i))
            self.workers.append(t)
            
    async def stop(self):
        """停止调度器"""
        self.running = False
        # 发送停止信号
        for _ in self.workers:
            await self.queue.put(None)
        
        # 等待所有 Worker 完成当前任务
        if self.workers:
            await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()
        logger.info("任务调度器已停止")
    
    async def submit_batch(self, task_record: TaskRecord):
        """提交批次任务"""
        total = task_record.total_count
        logger.info(f"提交批次任务 {task_record.task_id}, 总数: {total}")
        
        # 为该任务生成 N 个 Job
        # 这里其实是一个简化，我们假设 DB 里已经有一个 TaskRecord
        # 但我们需要追踪 100 个具体的注册动作
        # 实际情况可能是：TaskRecord 是一个“批次”，具体的“注册”动作在内存中生成 Job
        
        for _ in range(total):
            job = Job(
                job_id=str(uuid4()),
                parent_task_id=task_record.task_id,
                proxy_strategy=task_record.proxy_strategy or "least_used",
                max_retries=task_record.max_retries
            )
            await self.queue.put(job)
            
    async def _worker_loop(self, worker_id: int):
        """工作线程循环"""
        import random
        from app.core.config import settings
        logger.debug(f"Worker {worker_id} started")
        
        while self.running:
            try:
                # 获取任务 (带超时，以便响应停止信号)
                try:
                    job = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                
                # 停止信号
                if job is None:
                    break
                    
                self.active_workers += 1
                logger.info(f"Worker {worker_id} 开始处理 Job {job.job_id} (Task {job.parent_task_id})")
                
                proxy = None
                try:
                    # 开启数据库会话
                    async with async_session_factory() as db:
                    # 1. 申请代理
                        if job.proxy_strategy == "none":
                            proxy = None
                            logger.info(f"Worker {worker_id}: 任务指定不使用代理 (strategy=none)")
                        else:
                            proxy = await proxy_pool.acquire_proxy(
                                usage_id=job.job_id,
                                strategy=job.proxy_strategy
                            )
                            if not proxy:
                                pool_status = await proxy_pool.get_detailed_status()
                                logger.warning(
                                    "Worker %s: 无可用代理，Job %s 重新入队 (pool=%s)",
                                    worker_id, job.job_id, pool_status
                                )
                                await self.queue.put(job) # 重新放回
                                await asyncio.sleep(5.0)  # 避让
                                raise Exception("No proxy available")

                        # 2. 检查任务是否已被暂停或取消
                        stmt = select(TaskRecord.status).where(TaskRecord.task_id == job.parent_task_id)
                        res = await db.execute(stmt)
                        current_status = res.scalar_one_or_none()
                        
                        if current_status in ["paused", "cancelled"]:
                            logger.info(f"Job {job.job_id} 对应的任务已 {current_status}，跳过执行")
                            continue

                        # 3. 更新任务状态为处理中并记录代理信息
                        await self._update_task_start(db, job.parent_task_id, proxy)

                        # 4. 执行注册
                        try:
                            result = await register_engine.execute_with_proxy(
                                 db=db,
                                 task_id=job.parent_task_id,
                                 proxy_config=proxy
                            )
                        except Exception as e:
                            # 识别并处理注册引擎抛出的中断异常 (如果是嵌套异常)
                            from app.services.register_engine import TaskInterruptedError
                            if isinstance(e, TaskInterruptedError) or "Task is cancelled" in str(e) or "Task is paused" in str(e):
                                logger.warning(f"Worker {worker_id}: 检测到任务 {job.parent_task_id} 中断信号，退出 Job")
                                continue
                            raise # 抛出其他异常按原有流程处理
                          
                        if result["success"]:
                            self.completed_jobs += 1
                            await self._update_task_progress(db, job.parent_task_id, success=True)
                        elif result.get("proxy_error"):
                            # 代理连接失败：标记代理不健康，不消耗重试次数，换代理重试
                            proxy.is_healthy = False
                            logger.warning(f"Job {job.job_id} 代理故障 [{proxy.name}]，标记为不健康并重新入队")
                            await self.queue.put(job)
                        else:
                            error_detail = result.get("error", "Unknown error")
                            
                            # 处理中断导致的 failure
                            if "Task is" in error_detail:
                                logger.info(f"Job {job.job_id} 由于任务状态改变而提前终止")
                                continue

                            self.failed_jobs += 1
                            if job.retry_count < job.max_retries:
                                # 重试前检查任务状态，防止用户已停止任务但系统仍在重试
                                stmt = select(TaskRecord.status).where(TaskRecord.task_id == job.parent_task_id)
                                res_status = await db.execute(stmt)
                                task_current_status = res_status.scalar_one_or_none()
                                
                                if task_current_status in ["paused", "cancelled"]:
                                    logger.info(f"Job {job.job_id} 失败且任务处于 {task_current_status} 状态，放弃重试")
                                    self.failed_jobs += 1
                                    await self._update_task_progress(db, job.parent_task_id, success=False)
                                    continue

                                job.retry_count += 1
                                logger.info(f"Job {job.job_id} 失败 [{error_detail}]，尝试重试 ({job.retry_count}/{job.max_retries})")

                                # Update TaskRecord retry_count in DB
                                try:
                                    stmt = (
                                        update(TaskRecord)
                                        .where(TaskRecord.task_id == job.parent_task_id)
                                        .values(
                                            retry_count=job.retry_count,
                                            current_step=f"Retrying ({job.retry_count}/{job.max_retries})...",
                                            status="running" # Ensure status is running
                                        )
                                    )
                                    await db.execute(stmt)
                                    await db.commit()
                                except Exception as e:
                                    logger.error(f"Failed to update retry count for task {job.parent_task_id}: {e}")

                                await self.queue.put(job)
                            else:
                                logger.error(f"Job {job.job_id} 彻底失败: {error_detail}")
                                await self._update_task_progress(db, job.parent_task_id, success=False)

                except Exception as e:
                    if str(e) == "No proxy available":
                        pass # Valid case, already handled logging
                    else:
                        logger.error(f"Worker {worker_id} 执行异常: {e}")
                        self.failed_jobs += 1

                finally:
                    # 4. 释放代理
                    if proxy:
                        await proxy_pool.release_proxy(proxy)
                    
                    self.active_workers -= 1
                    self.queue.task_done()
                    
                    # 5. 冷却时间 (Cool-down)
                    interval = random.uniform(
                        settings.register_interval_min, 
                        settings.register_interval_max
                    )
                    logger.debug(f"Worker {worker_id} 进入冷却: {interval:.2f}s")
                    await asyncio.sleep(interval)
                    
            except Exception as e:
                 logger.error(f"Worker {worker_id} loop error: {e}")
                 await asyncio.sleep(1.0)

    async def _update_task_start(self, db: AsyncSession, task_id: str, proxy: Optional[ProxyConfig]):
        """任务开始时的状态更新"""
        try:
            stmt = select(TaskRecord).where(TaskRecord.task_id == task_id)
            result = await db.execute(stmt)
            task = result.scalar_one_or_none()
            
            if task:
                task.status = "running"
                task.current_step = "Initializing browser..."
                if proxy:
                    task.assigned_proxy_name = proxy.name
                    # 直接使用 ProxyConfig 上经 IP 检测得到的 region_tag
                    if proxy.region_tag and proxy.region_tag != "UN":
                        task.assigned_proxy_region = proxy.region_tag
                    elif proxy.group and proxy.group not in ("default", "external"):
                        task.assigned_proxy_region = proxy.group
                else:
                    task.assigned_proxy_name = "Direct / No Proxy"
                await db.commit()
        except Exception as e:
            logger.error(f"更新任务开始状态失败: {e}")

    async def _update_task_progress(self, db: AsyncSession, task_id: str, success: bool):
        """原子更新数据库进度"""
        try:
            # 1. Atomic Increment via SQL
            if success:
                stmt = (
                    update(TaskRecord)
                    .where(TaskRecord.task_id == task_id)
                    .values(success_count=TaskRecord.success_count + 1)
                    .execution_options(synchronize_session="fetch")
                )
            else:
                stmt = (
                    update(TaskRecord)
                    .where(TaskRecord.task_id == task_id)
                    .values(failure_count=TaskRecord.failure_count + 1)
                    .execution_options(synchronize_session="fetch")
                )
            await db.execute(stmt)
            
            # 2. Check Status (in same transaction)
            q = select(TaskRecord).where(TaskRecord.task_id == task_id)
            result = await db.execute(q)
            task = result.scalar_one_or_none()
            
            if task:
                total = task.total_count
                current = task.success_count + task.failure_count
                
                # Update status if finished
                if current >= total:
                    if bool(task.success_count >= total):
                        if str(getattr(task, "status", "")) != "completed":
                            task.status = "completed"
                            task.completed_at = datetime.utcnow()
                            logger.info(f"Task {task_id} completed (Total: {total})")
                    else:
                        task.status = "failed"
                        task.completed_at = datetime.utcnow()
                        logger.info(f"Task {task_id} failed (Total: {total})")
                elif task.status == "created":
                    task.status = "running"
                
                await db.commit()
                
                # 发送 WebSocket 通知 (可选)
                
        except Exception as e:
            logger.error(f"更新进度失败: {e}")

# 全局实例
task_scheduler = TaskScheduler()
