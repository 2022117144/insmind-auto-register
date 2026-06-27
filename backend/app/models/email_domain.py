"""
Dreamina Auto Register - 邮箱域名模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.timezone import get_beijing_time


class EmailDomain(Base):
    """Cloudflare 邮箱域名配置表"""
    __tablename__ = "email_domains"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 域名信息
    domain = Column(String(255), unique=True, nullable=False, comment="域名")
    cf_zone_id = Column(String(64), comment="Cloudflare Zone ID")
    
    # 状态
    is_enabled = Column(Boolean, default=True, comment="是否启用")
    
    # 使用统计
    usage_count = Column(Integer, default=0, comment="已使用次数")
    usage_limit = Column(Integer, default=0, comment="使用上限（0=无限制）")
    
    # 备注
    note = Column(String(512), comment="备注")
    
    # 时间戳
    created_at = Column(DateTime, default=get_beijing_time, comment="创建时间")
    
    # 关系
    accounts = relationship("Account", back_populates="domain")
    
    def __repr__(self):
        return f"<EmailDomain(id={self.id}, domain={self.domain})>"
    
    @property
    def is_available(self) -> bool:
        """检查域名是否可用"""
        if not self.is_enabled:
            return False
        if self.usage_limit > 0 and self.usage_count >= self.usage_limit:
            return False
        return True
