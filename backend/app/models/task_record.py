"""
Dreamina Auto Register - 任务记录模型
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base
from app.core.timezone import get_beijing_time


class TaskRecord(Base):
    """注册任务记录表"""

    __tablename__ = "task_records"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 任务标识
    task_id = Column(
        String(36), unique=True, index=True, nullable=False, comment="任务UUID"
    )

    # 状态
    status = Column(
        String(20),
        default="created",
        comment="状态: created/running/paused/completed/cancelled",
    )

    # 当前执行的具体步骤 (用于细粒度进度显示)
    current_step = Column(
        String(50), nullable=True, comment="当前步骤: navigate/fill_form/wait_code/etc."
    )

    # 数量统计
    total_count = Column(Integer, default=0, comment="计划注册总数")
    success_count = Column(Integer, default=0, comment="成功数")
    failure_count = Column(Integer, default=0, comment="失败数")

    # 重试状态
    retry_count = Column(Integer, default=0, comment="当前已重试次数")
    max_retries = Column(Integer, default=3, comment="最大重试次数")

    # 域名配置
    domain_mode = Column(
        String(20), default="manual", comment="域名选择模式: manual/auto_rotate"
    )
    domain_ids = Column(Text, comment="域名ID列表 JSON")

    # 代理配置
    proxy_strategy = Column(
        String(20),
        default="round_robin",
        comment="代理分配策略: round_robin/random/least_used",
    )

    # 邮箱配置
    email_prefix_pattern = Column(
        String(100), default="reg_{random6}", comment="邮箱前缀模式"
    )
    email_source = Column(
        String(20), default="cloudflare", comment="邮件来源: cloudflare / outlook"
    )

    # 分配的资源（用于前端显示）
    assigned_email = Column(String(255), comment="分配的完整邮箱地址")
    assigned_proxy_region = Column(String(50), comment="分配的代理地域标签")
    assigned_proxy_name = Column(String(255), comment="分配的代理节点名称")

    # 时间戳
    created_at = Column(DateTime, default=get_beijing_time, comment="创建时间")
    completed_at = Column(DateTime, comment="完成时间")

    # 关系
    accounts = relationship(
        "Account",
        back_populates="task",
        primaryjoin="TaskRecord.task_id==Account.task_id",
        foreign_keys="Account.task_id",
    )

    def __repr__(self):
        return f"<TaskRecord(task_id={self.task_id}, status={self.status})>"

    @property
    def progress(self) -> float:
        """分阶段计算进度百分比"""
        # 1. 终态进度
        if self.status == "completed":
            return 100.0
        if self.status == "cancelled":
            return self.calculate_base_progress()
        if self.status == "failed":
            # 只有当任务状态明确为 failed 时才返回由失败数计算的进度 (通常是退出)
            # 如果只是单次运行失败但还在重试中，状态还是 running
            return self.calculate_base_progress()
        if self.status == "created" or self.status == "queued":
            return 0.0

        # 2. 运行中进度步进映射
        step_mapping = {
            "init": 2,
            "create_browser": 10,
            "navigate": 20,
            "click_privacy": 25,
            "click_signin": 30,
            "click_continue_email": 35,
            "switch_to_signup": 40,
            "fill_register_form": 50,
            "wait_verification_code": 65,
            "input_verification_code": 80,
            "fill_birth_date": 90,
            "extract_session": 95,
            "save_state": 100,
        }

        current_step_raw = self.current_step
        # 处理重试中的特殊步骤文本，例如 "Retrying (1/3)..."
        if current_step_raw and current_step_raw.startswith("Retrying"):
            # 重试时进度回退到初始化阶段或保持极低进度，让用户感到“重启”
            step_progress = 5.0
        else:
            step_progress = (
                step_mapping.get(current_step_raw, 0.0) if current_step_raw else 0.0
            )

        # 结合整体批次完成度进行平滑处理
        if self.total_count <= 1:
            return step_progress

        # 批次任务的进度：(已成功数 + 已彻底失败数) / 总数
        # 注意：这里的 failure_count 只有在耗尽重试后才会增加
        base_progress = (
            (self.success_count + self.failure_count) / self.total_count * 100
        )

        # 仅对运行中的这一个槽位增加步进补偿 (当前任务在总进度中占的比例)
        step_contribution = (step_progress / 100) * (1 / self.total_count) * 100

        return min(base_progress + step_contribution, 99.9)

    def calculate_base_progress(self) -> float:
        """基础完成度计算"""
        if self.total_count == 0:
            return 0.0
        return (self.success_count + self.failure_count) / self.total_count * 100
