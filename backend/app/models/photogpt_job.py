"""PhotoGPT 生成任务模型"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from app.core.database import Base


class PhotoGPTJob(Base):
    """PhotoGPT 生成任务表（与 insMind ContentGenerationJob 隔离）"""

    __tablename__ = "photogpt_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)

    status = Column(
        String(20),
        default="submitted",
        index=True,
        comment="状态: submitting/submitted/processing/success/failed",
    )
    prompt = Column(Text, comment="提示词")
    model = Column(String(100), default="gpt-image-2", comment="模型")
    aspect_ratio = Column(String(20), default="1:1", comment="比例")
    resolution = Column(String(20), default="1K", comment="分辨率")
    quality = Column(String(20), default="medium", comment="质量")
    output_num = Column(Integer, default=1, comment="生成数量")
    input_urls = Column(Text, nullable=True, comment="输入图片 URL（JSON 数组）")

    project_id = Column(String(100), nullable=True, comment="PhotoGPT project_id")
    output_urls = Column(Text, nullable=True, comment="输出图片 URL（JSON 数组）")
    error_message = Column(Text, nullable=True, comment="错误信息")

    account_id = Column(Integer, nullable=True, comment="使用的 PhotoGPT 账号 ID")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)