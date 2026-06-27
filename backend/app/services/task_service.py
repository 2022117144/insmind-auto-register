
"""
Dreamina Auto Register - 任务管理服务
"""
from typing import List, Optional
import json
import uuid
import random
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException

from app.models import TaskRecord, EmailDomain, ProxyNode
from app.models.outlook_mailbox import OutlookMailbox
from app.schemas import TaskCreate
from app.services.task_scheduler import task_scheduler
from app.services.random_generator import random_generator
from app.api.routers.websocket import send_log

logger = logging.getLogger(__name__)

class TaskService:
    """任务管理服务"""
    
    @staticmethod
    async def create_task(db: AsyncSession, task_data: TaskCreate) -> TaskRecord:
        """
        创建并初始化批量注册任务
        支持两种邮件来源模式:
          - cloudflare: 按域名+前缀自动生成邮箱，通过 CF KV 获取验证码
          - outlook: 从 outlook_mailboxes 表分配预设邮箱，通过 OutlookManager API 获取验证码
        """
        email_source = task_data.email_source or "cloudflare"
        
        # ===== Cloudflare 模式：验证域名 =====
        if email_source == "cloudflare":
            if not task_data.domain_ids:
                raise HTTPException(status_code=400, detail="cloudflare 模式必须提供 domain_ids")
            
            stmt = select(EmailDomain).where(EmailDomain.id.in_(task_data.domain_ids))
            result = await db.execute(stmt)
            domains = result.scalars().all()
            
            if len(domains) != len(task_data.domain_ids):
                raise HTTPException(status_code=400, detail="部分域名不存在")
            
            unavailable_domains = [d.domain for d in domains if not d.is_available]
            if unavailable_domains:
                raise HTTPException(
                    status_code=400,
                    detail=f"以下域名不可用: {', '.join(unavailable_domains)}"
                )
        else:
            domains = []

        # ===== Outlook 模式：预取可用邮箱 =====
        outlook_mailboxes = []
        if email_source == "outlook":
            stmt = select(OutlookMailbox).where(
                OutlookMailbox.is_enabled == True
            ).order_by(OutlookMailbox.last_used_at.asc().nullsfirst())
            result = await db.execute(stmt)
            outlook_mailboxes = result.scalars().all()
            if len(outlook_mailboxes) < task_data.total_count:
                raise HTTPException(
                    status_code=400,
                    detail=f"可用 Outlook 邮箱不足，需要 {task_data.total_count} 个，当前可用 {len(outlook_mailboxes)} 个"
                )

        # ===== 获取代理资源 =====
        proxy_stmt = select(ProxyNode).where(ProxyNode.is_enabled == True).order_by(ProxyNode.usage_count.asc())
        proxy_result = await db.execute(proxy_stmt)
        active_proxies = proxy_result.scalars().all()

        if not active_proxies:
            proxy_stmt_all = select(ProxyNode).order_by(ProxyNode.usage_count.asc())
            proxy_result_all = await db.execute(proxy_stmt_all)
            all_proxies = proxy_result_all.scalars().all()
        else:
            all_proxies = active_proxies

        created_tasks = []

        # ===== 循环创建任务 =====
        for i in range(task_data.total_count):
            # 3.1 决定邮箱
            assigned_email = None
            if email_source == "outlook":
                mailbox = outlook_mailboxes[i]
                assigned_email = mailbox.email
                # 标记为已使用（后续注册成功后会再次禁用），更新使用时间
                mailbox.last_used_at = datetime.utcnow()
            elif domains:
                domain = domains[i % len(domains)].domain
                pattern = task_data.email_prefix_pattern
                prefix = random_generator.generate_email_local_part(pattern)
                assigned_email = f"{prefix}@{domain}"

            # 3.2 分配代理信息
            assigned_proxy_region = None
            assigned_proxy_name = None

            if all_proxies:
                if task_data.proxy_strategy == 'random':
                    proxy = random.choice(all_proxies)
                else:  # round_robin / least_used
                    proxy = all_proxies[i % len(all_proxies)]

                assigned_proxy_name = proxy.name
                assigned_proxy_region = proxy.region_tag
                # Fallback region detection
                if not assigned_proxy_region and proxy.name:
                    name = proxy.name
                    if '🇯🇵' in name or '日本' in name: assigned_proxy_region = '日本'
                    elif '🇺🇸' in name or '美国' in name: assigned_proxy_region = '美国'
                    elif '🇸🇬' in name or '新加坡' in name: assigned_proxy_region = '新加坡'
                    elif '🇭🇰' in name or '香港' in name: assigned_proxy_region = '香港'
                    elif '🇹🇼' in name or '台湾' in name: assigned_proxy_region = '台湾'
                    elif '🇰🇷' in name or '韩国' in name: assigned_proxy_region = '韩国'
                    elif '🇬🇧' in name or '英国' in name: assigned_proxy_region = '英国'
                    elif '🇩🇪' in name or '德国' in name: assigned_proxy_region = '德国'
                    elif '🇫🇷' in name or '法国' in name: assigned_proxy_region = '法国'

            # 3.3 创建记录
            task = TaskRecord(
                task_id=str(uuid.uuid4()),
                total_count=1,
                domain_mode=task_data.domain_mode,
                domain_ids=json.dumps(task_data.domain_ids or []),
                proxy_strategy=task_data.proxy_strategy,
                email_prefix_pattern=task_data.email_prefix_pattern,
                email_source=email_source,
                assigned_email=assigned_email,
                assigned_proxy_region=assigned_proxy_region,
                assigned_proxy_name=assigned_proxy_name,
                status="queued",
                max_retries=task_data.max_retries,
            )

            db.add(task)
            created_tasks.append(task)

        await db.commit()

        # 4. 提交调度
        if not task_scheduler.running:
            await task_scheduler.start()

        for task in created_tasks:
            await db.refresh(task)
            await send_log("INFO", f"任务 {task.task_id} ({task.assigned_email}) 已创建并加入队列 [来源: {email_source}]", task_id=task.task_id)
            await task_scheduler.submit_batch(task)

        return created_tasks[-1] if created_tasks else None

    @staticmethod
    async def get_tasks(
        db: AsyncSession, 
        status: Optional[str] = None, 
        page: int = 1, 
        page_size: int = 20
    ) -> List[TaskRecord]:
        """获取任务列表"""
        stmt = select(TaskRecord).order_by(TaskRecord.created_at.desc())
        
        if status:
            stmt = stmt.where(TaskRecord.status == status)
        
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_task_by_id(db: AsyncSession, task_id: str) -> Optional[TaskRecord]:
        """获取单个任务详情"""
        stmt = select(TaskRecord).where(TaskRecord.task_id == task_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def start_task(db: AsyncSession, task_id: str) -> TaskRecord:
        """启动任务"""
        task = await TaskService.get_task_by_id(db, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        if task.status == "running":
            raise HTTPException(status_code=400, detail=f"任务状态 {task.status} 无法启动")
        
        task.status = "running"
        await db.commit()
        
        if not task_scheduler.running:
            await task_scheduler.start()
            
        await task_scheduler.submit_batch(task)
        return task

    @staticmethod
    async def pause_task(db: AsyncSession, task_id: str) -> TaskRecord:
        """暂停任务"""
        task = await TaskService.get_task_by_id(db, task_id)
        if not task:
             raise HTTPException(status_code=404, detail="任务不存在")
             
        if task.status != "running":
            raise HTTPException(status_code=400, detail="只能暂停运行中的任务")
            
        task.status = "paused"
        await db.commit()
        return task

    @staticmethod
    async def cancel_task(db: AsyncSession, task_id: str) -> TaskRecord:
        """取消任务"""
        task = await TaskService.get_task_by_id(db, task_id)
        if not task:
             raise HTTPException(status_code=404, detail="任务不存在")
             
        if task.status == "completed":
            raise HTTPException(status_code=400, detail="任务已完成，无法取消")
            
        task.status = "cancelled"
        await db.commit()
        return task
        
    @staticmethod
    async def delete_task(db: AsyncSession, task_id: str):
        """删除任务"""
        task = await TaskService.get_task_by_id(db, task_id)
        if not task:
             raise HTTPException(status_code=404, detail="任务不存在")
             
        if task.status == "running":
            raise HTTPException(status_code=400, detail="运行中的任务无法删除")
            
        await db.delete(task)
        await db.commit()
