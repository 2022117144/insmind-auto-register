"""
仪表盘统计 API 路由
"""
from datetime import datetime, timedelta
from typing import Dict, List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core import get_db
from app.models import Account
from app.services.proxy_pool import proxy_pool

router = APIRouter()

@router.get("/stats")
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """获取仪表盘核心指标"""
    # 1. 账号基础统计
    total_stmt = select(func.count(Account.id))
    success_stmt = select(func.count(Account.id)).where(Account.status.in_(["success", "active"]))
    failed_stmt = select(func.count(Account.id)).where(Account.status == "failed")
    
    total = (await db.execute(total_stmt)).scalar() or 0
    success = (await db.execute(success_stmt)).scalar() or 0
    failed = (await db.execute(failed_stmt)).scalar() or 0
    
    success_rate = (success / total * 100) if total > 0 else 0
    
    # 2. 今日成功统计
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_success_stmt = select(func.count(Account.id)).where(
        Account.status.in_(["success", "active"]),
        Account.created_at >= today_start
    )
    today_success = (await db.execute(today_success_stmt)).scalar() or 0
    
    # 3. 代理池统计
    pool_status = proxy_pool.get_status()
    
    # 4. 注册趋势 (最近 7 天)
    trend_data = []
    for i in range(6, -1, -1):
        date = (datetime.now() - timedelta(days=i)).date()
        date_start = datetime.combine(date, datetime.min.time())
        date_end = datetime.combine(date, datetime.max.time())
        
        count_stmt = select(func.count(Account.id)).where(
            Account.created_at.between(date_start, date_end)
        )
        count = (await db.execute(count_stmt)).scalar() or 0
        trend_data.append({
            "name": date.strftime("%m-%d"),
            "total": count
        })
    
    return {
        "accounts": {
            "total": total,
            "success": success,
            "failed": failed,
            "success_rate": round(success_rate, 1),
            "today_success": today_success
        },
        "proxies": {
            "total": pool_status["total"],
            "active": pool_status["active"],
            "online_ratio": f"{pool_status['active']}/{pool_status['total']}" if pool_status['total'] > 0 else "0/0"
        },
        "trends": trend_data
    }
