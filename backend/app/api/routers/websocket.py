"""
WebSocket 路由
"""
import asyncio
import json
from datetime import datetime
from typing import Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


class ConnectionManager:
    """WebSocket 连接管理器"""
    
    def __init__(self):
        # 全局日志连接
        self.log_connections: Set[WebSocket] = set()
        # 任务专属连接 {task_id: set of websockets}
        self.task_connections: dict[str, Set[WebSocket]] = {}
    
    async def connect_logs(self, websocket: WebSocket):
        """连接全局日志"""
        await websocket.accept()
        self.log_connections.add(websocket)
    
    async def disconnect_logs(self, websocket: WebSocket):
        """断开全局日志"""
        self.log_connections.discard(websocket)
    
    async def connect_task(self, task_id: str, websocket: WebSocket):
        """连接任务专属通道"""
        await websocket.accept()
        if task_id not in self.task_connections:
            self.task_connections[task_id] = set()
        self.task_connections[task_id].add(websocket)
    
    async def disconnect_task(self, task_id: str, websocket: WebSocket):
        """断开任务通道"""
        if task_id in self.task_connections:
            self.task_connections[task_id].discard(websocket)
            if not self.task_connections[task_id]:
                del self.task_connections[task_id]
    
    async def broadcast_log(self, message: dict):
        """广播日志到所有连接"""
        dead_connections = set()
        
        for connection in self.log_connections:
            try:
                await connection.send_json(message)
            except:
                dead_connections.add(connection)
        
        # 清理断开的连接
        self.log_connections -= dead_connections
    
    async def broadcast_task(self, task_id: str, message: dict):
        """广播到特定任务的连接"""
        if task_id not in self.task_connections:
            return
        
        dead_connections = set()
        
        for connection in self.task_connections[task_id]:
            try:
                await connection.send_json(message)
            except:
                dead_connections.add(connection)
        
        # 清理断开的连接
        self.task_connections[task_id] -= dead_connections


# 全局连接管理器
manager = ConnectionManager()


@router.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    """全局日志 WebSocket"""
    await manager.connect_logs(websocket)
    
    try:
        while True:
            # 保持连接活跃
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0
                )
                # 可以处理客户端发送的命令
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                # 发送心跳
                await websocket.send_json({"type": "heartbeat"})
    except WebSocketDisconnect:
        await manager.disconnect_logs(websocket)


@router.websocket("/ws/task/{task_id}")
async def websocket_task(websocket: WebSocket, task_id: str):
    """任务专属 WebSocket"""
    await manager.connect_task(task_id, websocket)
    
    try:
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0
                )
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "heartbeat"})
    except WebSocketDisconnect:
        await manager.disconnect_task(task_id, websocket)


# 便捷函数：发送日志
async def send_log(level: str, message: str, email: str = None, task_id: str = None):
    """发送日志消息"""
    import logging
    logger = logging.getLogger(__name__)
    
    log_data = {
        "type": "log",
        "timestamp": datetime.utcnow().isoformat(),
        "level": level,
        "message": message,
        "email": email,
        "task_id": task_id,
    }
    
    # 调试：打印连接数
    logger.info(f"[WS] send_log: {level} - {message[:50]}... (connections: {len(manager.log_connections)})")
    
    # 广播到全局日志
    await manager.broadcast_log(log_data)
    
    # 如果有 task_id，也广播到任务通道
    if task_id:
        await manager.broadcast_task(task_id, log_data)


# 便捷函数：发送任务进度
async def send_task_progress(
    task_id: str,
    status: str,
    success_count: int,
    failure_count: int,
    total_count: int,
    current_email: str = None,
    progress: float = None,
    current_step: str = None
):
    """发送任务进度更新"""
    # 如果显式传入了 progress（如来自 task.progress 属性），则使用它，否则按计数计算
    if progress is None:
        progress = (success_count + failure_count) / total_count * 100 if total_count > 0 else 0
    
    progress_data = {
        "type": "progress",
        "task_id": task_id,
        "status": status,
        "success_count": success_count,
        "failure_count": failure_count,
        "progress": round(progress, 1),
        "current_step": current_step,
        "current_email": current_email,
    }
    
    await manager.broadcast_task(task_id, progress_data)
    await manager.broadcast_log(progress_data)


# 日志 Handler
import logging

class WebSocketLogHandler(logging.Handler):
    """把日志转发到 WebSocket 的 Handler"""
    
    def emit(self, record):
        try:
            # 过滤不需要的日志，避免循环和噪音
            if record.name.startswith("uvicorn") or record.name.startswith("watchfiles") or record.name == "app.api.routers.websocket":
                return
            
            msg = self.format(record)
            
            # 在异步循环中发送
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    loop.create_task(self._async_emit(record.levelname, msg))
            except RuntimeError:
                pass # No running loop
        except Exception:
            self.handleError(record)

    async def _async_emit(self, level: str, message: str):
        # 构造简单消息
        log_data = {
            "type": "log",
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
        }
        await manager.broadcast_log(log_data)
