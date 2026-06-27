"""
Dreamina Auto Register - Outlook 邮箱管理模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.core.database import Base
from app.core.timezone import get_beijing_time


class OutlookMailbox(Base):
    """Outlook 邮箱列表表 - 预设的 Outlook 邮箱，用于注册"""
    __tablename__ = "outlook_mailboxes"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 邮箱地址（唯一）
    email = Column(String(255), unique=True, nullable=False, index=True, comment="Outlook 邮箱地址")

    # 状态控制
    is_enabled = Column(Boolean, default=True, comment="是否可用（注册成功后自动禁用）")

    # 使用统计
    usage_count = Column(Integer, default=0, comment="已使用次数（成功注册次数）")
    last_used_at = Column(DateTime, nullable=True, comment="最近一次使用时间")

    # 备注
    note = Column(String(512), nullable=True, comment="备注信息")

    # 时间戳
    created_at = Column(DateTime, default=get_beijing_time, comment="创建时间")

    def __repr__(self):
        return f"<OutlookMailbox(id={self.id}, email={self.email}, is_enabled={self.is_enabled})>"
