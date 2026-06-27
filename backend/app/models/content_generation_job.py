"""
Dreamina Auto Register - 内容生成任务模型
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.timezone import get_beijing_time


class ContentGenerationJob(Base):
    """内容生成任务表"""

    __tablename__ = "content_generation_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_type = Column(String(20), nullable=False, comment="类型: image/video")
    status = Column(
        String(20),
        default="queued",
        index=True,
        comment="状态: queued/submitting/submitted/processing/success/failed/cancelled",
    )

    prompt = Column(Text, comment="提示词")
    model = Column(String(100), comment="模型")
    ratio = Column(String(20), comment="比例")
    resolution = Column(String(20), comment="分辨率")
    duration = Column(Integer, comment="视频时长(秒)")
    function_mode = Column(String(50), comment="功能模式")

    input_images = Column(Text, comment="输入图片 JSON")
    output_urls = Column(Text, comment="输出 URL JSON")
    thumbnail_urls = Column(Text, comment="缩略图 URL JSON")
    local_urls = Column(Text, comment="本地全尺寸资源 URL JSON")
    error_message = Column(Text, comment="失败原因")
    remote_task_id = Column(String(100), index=True, comment="远端异步任务ID")
    remote_history_id = Column(String(100), comment="远端history_record_id")
    remote_kind = Column(String(50), comment="远端任务类型")
    remote_status = Column(String(50), comment="远端任务状态")
    remote_fail_code = Column(String(100), comment="远端失败码")
    remote_error_message = Column(Text, comment="远端错误信息")

    account_id = Column(Integer, ForeignKey("accounts.id"), comment="关联账号ID")
    region = Column(String(50), comment="区域")
    submitted_at = Column(DateTime, comment="提交到远端时间")
    finished_at = Column(DateTime, comment="远端完成时间")

    created_at = Column(DateTime, default=get_beijing_time, comment="创建时间")
    updated_at = Column(
        DateTime,
        default=get_beijing_time,
        onupdate=get_beijing_time,
        comment="更新时间",
    )

    account = relationship("Account")

    def __repr__(self):
        return f"<ContentGenerationJob(id={self.id}, type={self.job_type}, status={self.status})>"
