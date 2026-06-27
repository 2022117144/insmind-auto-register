"""
Dreamina Auto Register - 代理节点模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime
from app.core.database import Base
from app.core.timezone import get_beijing_time


class ProxyNode(Base):
    __tablename__ = "proxy_nodes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 节点信息（从 Clash 获取）
    name = Column(String(255), unique=True, nullable=False, comment="节点名称")
    node_type = Column(String(50), comment="节点类型: ss/vmess/trojan等")

    # 外部代理连接信息（用于 external source）
    host = Column(String(255), comment="代理主机")
    port = Column(Integer, comment="代理端口")
    username = Column(String(255), comment="代理用户名")
    password = Column(String(255), comment="代理密码")
    protocol = Column(String(20), comment="代理协议: http/socks5")

    # 节点来源
    source = Column(String(20), default="clash", comment="来源: clash/external")
    
    # 本地管理状态
    region_tag = Column(String(10), comment="地域标签: US/JP/SG等")
    is_enabled = Column(Boolean, default=True, comment="是否参与注册")
    
    # 健康状态
    latency = Column(Integer, comment="延迟(ms)")
    is_healthy = Column(Boolean, default=None, comment="是否健康")
    last_tested_at = Column(DateTime, comment="最近测试时间")
    
    # 使用统计
    usage_count = Column(Integer, default=0, comment="累计使用次数")
    
    # 时间戳
    created_at = Column(DateTime, default=get_beijing_time, comment="创建时间")
    
    def __repr__(self):
        return f"<ProxyNode(id={self.id}, name={self.name})>"
    
    @property
    def status_icon(self) -> str:
        """获取状态图标"""
        return "⚪"
