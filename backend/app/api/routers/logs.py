"""日志查看 API 路由"""
import os
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Query

from app.core import settings

logger = logging.getLogger(__name__)
router = APIRouter()


def _parse_log_ts(line: str) -> Optional[str]:
    """提取日志行开头的 timestamp，如 '2026-07-25 22:50:20,432'"""
    if len(line) < 23:
        return None
    # 日志格式: "2026-07-25 22:50:20,432 - name - LEVEL - msg"
    ts = line[:23]
    # 验证是不是日期格式
    if ts[4] == '-' and ts[7] == '-':
        return ts
    return None


@router.get("/api/logs", tags=["日志"])
async def get_logs(
    lines: int = Query(200, ge=10, le=5000, description="返回行数"),
    since: Optional[str] = Query(None, description="只返回此时间戳之后的行（日志格式: 2026-07-25 22:50:20,432）"),
):
    """返回后端日志文件的最新 N 行，支持 since 参数只返回新日志"""
    log_file = settings.logs_dir / "app.log"
    if not log_file.exists():
        return {"lines": [], "total": 0, "file": str(log_file)}

    try:
        with open(log_file, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
    except Exception as e:
        return {"lines": [], "total": 0, "error": str(e)}

    if since:
        # 只返回时间戳 >= since 的行
        filtered = [l for l in all_lines if _parse_log_ts(l) and _parse_log_ts(l) >= since]
        result = filtered[-lines:] if len(filtered) > lines else filtered
    else:
        result = all_lines[-lines:]

    # 提取最后一条日志的时间戳，供前端下次轮询使用
    last_ts = None
    for l in reversed(result):
        ts = _parse_log_ts(l)
        if ts:
            last_ts = ts
            break

    return {
        "lines": result,
        "total": len(result),
        "file": str(log_file),
        "last_ts": last_ts,
    }