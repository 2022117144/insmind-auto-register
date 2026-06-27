"""insMind Auto Register - insMind 账号模型"""

import base64
import json
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.core.database import Base
from app.core.timezone import get_beijing_time


def check_insmind_token_valid(token: str) -> bool:
    """
    验证 insMind token.prod 是否过期。
    token 是 base64 编码的 JSON，含 access_token_expires_at 字段。
    """
    if not token:
        return False
    try:
        padded = token + "=" * (4 - len(token) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        expires_str = payload.get("access_token_expires_at")
        if not expires_str:
            return False
        expires = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
        return expires > datetime.now(timezone.utc)
    except Exception:
        return False


class InsMindAccount(Base):
    """insMind 注册账号表（与旧 Dreamina Account 表完全隔离）"""

    __tablename__ = "insmind_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 账号信息
    email = Column(
        String(255), unique=True, index=True, nullable=False, comment="临时邮箱地址"
    )
    token = Column(Text, comment="insMind 登录态 token (token.prod)")
    refresh_token = Column(
        Text, default="", comment="insMind refresh_token (用于无刷新头的原始 cookie 传递)"
    )
    user_id = Column(
        String(100), default="", comment="insMind 用户 ID (x-user-id)"
    )
    org_id = Column(
        String(100), default="", comment="insMind 租户 ID (org_id cookie)"
    )

    # 积分与健康状态
    credits = Column(Integer, default=0, comment="剩余免费额度")
    status = Column(
        String(20),
        default="active",
        comment="状态: active/expired/banned",
    )

    # 时间戳
    created_at = Column(DateTime, default=get_beijing_time, comment="创建时间")
    updated_at = Column(
        DateTime,
        default=get_beijing_time,
        onupdate=get_beijing_time,
        comment="更新时间",
    )

    def __repr__(self):
        return (
            f"<InsMindAccount(id={self.id}, email={self.email}, status={self.status})>"
        )
