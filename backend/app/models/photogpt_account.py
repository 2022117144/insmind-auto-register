"""PhotoGPT 账号模型"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from app.core.database import Base


class PhotoGPTAccount(Base):
    """PhotoGPT 账号表（图片生成账号池）"""

    __tablename__ = "photogpt_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)

    email = Column(String(255), unique=True, index=True, nullable=False, comment="临时邮箱地址")
    access_token = Column(Text, comment="PhotoGPT 登录 token (Bearer)")
    password = Column(String(255), default="", comment="账号密码")
    credits = Column(Integer, default=20, comment="免费点数")
    credits_used = Column(Integer, default=0, comment="已使用点数")

    status = Column(String(20), default="active", comment="状态: active/expired/banned")
    active = Column(Boolean, default=True, comment="是否启用")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True, comment="上次使用时间")
    gen_locked_until = Column(DateTime, nullable=True, comment="生成锁定至（10分钟超时）")