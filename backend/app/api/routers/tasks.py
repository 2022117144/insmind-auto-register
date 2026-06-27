"""
任务管理 API 路由
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import get_db
from app.schemas import (
    TaskCreate, TaskResponse, TaskDetail, MessageResponse
)
from app.services.task_service import TaskService

router = APIRouter()


@router.post("", response_model=TaskResponse)
async def create_task(
    task_data: TaskCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建注册任务（创建 N 个独立任务，自动加入队列）"""
    return await TaskService.create_task(db, task_data)


@router.get("", response_model=List[TaskResponse])
async def list_tasks(
    status: Optional[str] = Query(None, description="状态筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """获取任务列表"""
    return await TaskService.get_tasks(db, status, page, page_size)


@router.get("/{task_id}", response_model=TaskDetail)
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """获取任务详情"""
    return await TaskService.get_task_by_id(db, task_id)


@router.post("/{task_id}/start", response_model=MessageResponse)
async def start_task(
    task_id: str, 
    db: AsyncSession = Depends(get_db)
):
    """启动任务"""
    await TaskService.start_task(db, task_id)
    return MessageResponse(message=f"任务 {task_id} 已启动")


@router.post("/{task_id}/pause", response_model=MessageResponse)
async def pause_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """暂停任务"""
    await TaskService.pause_task(db, task_id)
    return MessageResponse(message=f"任务 {task_id} 已暂停")


@router.post("/{task_id}/cancel", response_model=MessageResponse)
async def cancel_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """取消任务"""
    await TaskService.cancel_task(db, task_id)
    return MessageResponse(message=f"任务 {task_id} 已取消")


@router.delete("/{task_id}", response_model=MessageResponse)
async def delete_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """删除任务"""
    await TaskService.delete_task(db, task_id)
    return MessageResponse(message=f"任务 {task_id} 已删除")
