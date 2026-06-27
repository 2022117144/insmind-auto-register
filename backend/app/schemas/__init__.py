"""
Dreamina Auto Register - Pydantic Schemas
"""

from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr


# ==================== Account Schemas ====================


class AccountBase(BaseModel):
    """账号基础模式"""

    email: str
    password: str


class AccountCreate(AccountBase):
    """创建账号"""

    domain_id: int
    birth_date: date
    proxy_node_name: Optional[str] = None
    task_id: Optional[str] = None


class AccountUpdate(BaseModel):
    """更新账号"""

    session_id: Optional[str] = None
    full_cookie: Optional[str] = None
    all_tokens: Optional[str] = None
    browser_state_path: Optional[str] = None
    status: Optional[str] = None
    failure_reason: Optional[str] = None
    screenshot_path: Optional[str] = None
    is_valid: Optional[str] = None


class AccountResponse(AccountBase):
    """账号响应"""

    id: int
    domain_id: Optional[int] = None
    session_id: Optional[str] = None
    status: str
    is_valid: str
    last_login_status: Optional[str] = None
    proxy_node_name: Optional[str] = None
    region: Optional[str] = None
    created_at: datetime

    # 新增字段
    credits_total: int = 0
    credits_gift: int = 0
    credits_purchase: int = 0
    credits_vip: int = 0
    health_status: Optional[str] = None
    last_credit_check_at: Optional[datetime] = None
    last_checkin_at: Optional[datetime] = None
    task_id: Optional[str] = None

    # 内容生成池
    gen_enabled: bool = False
    gen_enabled_at: Optional[datetime] = None
    gen_last_used_at: Optional[datetime] = None
    gen_locked_until: Optional[datetime] = None
    gen_auto_disabled_reason: Optional[str] = None

    class Config:
        from_attributes = True


class AccountDetail(AccountResponse):
    """账号详情"""

    full_cookie: Optional[str] = None
    all_tokens: Optional[str] = None
    browser_state_path: Optional[str] = None
    failure_reason: Optional[str] = None
    birth_date: Optional[date] = None
    screenshot_path: Optional[str] = None
    last_verified_at: Optional[datetime] = None
    retry_count: int = 0
    updated_at: Optional[datetime] = None


# ==================== Content Generation Schemas ====================


class ContentGenerationRequest(BaseModel):
    job_type: str = Field(..., description="image/video")
    prompt: str = Field(..., description="提示词")
    model: Optional[str] = None
    ratio: Optional[str] = None
    resolution: Optional[str] = None
    duration: Optional[int] = None
    input_images: Optional[List[str]] = None
    async_mode: Optional[bool] = True
    function_mode: Optional[str] = None


class ContentGenerationJobResponse(BaseModel):
    id: int
    job_type: str
    status: str
    prompt: Optional[str] = None
    model: Optional[str] = None
    ratio: Optional[str] = None
    resolution: Optional[str] = None
    duration: Optional[int] = None
    function_mode: Optional[str] = None
    input_images: Optional[List[str]] = None
    output_urls: Optional[List[str]] = None
    thumbnail_urls: Optional[List[str]] = None
    local_urls: Optional[List[str]] = None
    error_message: Optional[str] = None
    remote_task_id: Optional[str] = None
    remote_history_id: Optional[str] = None
    remote_kind: Optional[str] = None
    remote_status: Optional[str] = None
    remote_fail_code: Optional[str] = None
    remote_error_message: Optional[str] = None
    account_id: Optional[int] = None
    region: Optional[str] = None
    submitted_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ==================== Task Schemas ====================


class TaskCreate(BaseModel):
    """创建任务"""

    total_count: int = Field(..., ge=1, le=100, description="注册数量")
    domain_mode: str = Field(default="manual", description="域名模式")
    domain_ids: Optional[List[int]] = Field(
        default=None, description="域名ID列表（cloudflare 模式必填）"
    )
    proxy_strategy: str = Field(default="least_used", description="代理策略")
    email_prefix_pattern: str = Field(default="reg_{random6}", description="邮箱前缀")
    max_retries: int = Field(default=3, description="最大重试次数")
    email_source: str = Field(
        default="cloudflare", description="邮件来源: cloudflare / outlook"
    )


class TaskResponse(BaseModel):
    """任务响应"""

    id: int
    task_id: str
    status: str
    total_count: int
    success_count: int
    failure_count: int
    failure_reason: Optional[str] = None
    progress: float
    current_step: Optional[str] = None
    assigned_email: Optional[str] = None
    assigned_proxy_region: Optional[str] = None
    assigned_proxy_name: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TaskDetail(TaskResponse):
    """任务详情"""

    domain_mode: str
    domain_ids: Optional[str] = None
    proxy_strategy: str
    email_prefix_pattern: str
    email_source: str = "cloudflare"


# ==================== Outlook Mailbox Schemas ====================


class OutlookMailboxCreate(BaseModel):
    """创建单个 Outlook 邮箱"""

    email: str
    note: Optional[str] = None


class OutlookMailboxBatchCreate(BaseModel):
    """批量创建 Outlook 邮箱"""

    emails: List[str] = Field(..., description="邮箱地址列表")
    note: Optional[str] = None


class OutlookMailboxUpdate(BaseModel):
    """更新 Outlook 邮箱"""

    is_enabled: Optional[bool] = None
    note: Optional[str] = None


class OutlookMailboxResponse(BaseModel):
    """Outlook 邮箱响应"""

    id: int
    email: str
    note: Optional[str] = None
    is_enabled: bool
    usage_count: int
    last_used_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== Domain Schemas ====================


class DomainCreate(BaseModel):
    """创建域名"""

    domain: str
    cf_zone_id: Optional[str] = None
    usage_limit: int = Field(default=0, ge=0)
    note: Optional[str] = None


class DomainUpdate(BaseModel):
    """更新域名"""

    cf_zone_id: Optional[str] = None
    is_enabled: Optional[bool] = None
    usage_limit: Optional[int] = None
    note: Optional[str] = None


class DomainResponse(BaseModel):
    """域名响应"""

    id: int
    domain: str
    cf_zone_id: Optional[str] = None
    is_enabled: bool
    usage_count: int
    usage_limit: int
    is_available: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== Proxy Schemas ====================


class ProxyNodeResponse(BaseModel):
    """代理节点响应"""

    id: int
    name: str
    node_type: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    protocol: Optional[str] = None
    source: Optional[str] = None
    region_tag: Optional[str] = None
    is_enabled: bool
    latency: Optional[int] = None
    is_healthy: Optional[bool] = None
    status_icon: Optional[str] = None
    usage_count: int
    last_tested_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProxyNodeUpdate(BaseModel):
    """更新代理节点"""

    region_tag: Optional[str] = None
    is_enabled: Optional[bool] = None
    name: Optional[str] = None
    node_type: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    protocol: Optional[str] = None
    source: Optional[str] = None


# ==================== Settings Schemas ====================


class SettingsResponse(BaseModel):
    """系统设置响应"""

    dreamina_url: str
    register_timeout: int
    verification_timeout: int
    max_retry_count: int
    max_concurrency: int = 1
    gen_async_enabled: bool = True
    gen_image_async_poll_interval: int = 5
    gen_video_async_poll_interval: int = 20
    register_interval_min: int
    register_interval_max: int
    password_length: int
    password_include_special: bool
    browser_headless: bool
    clash_controller_url: str
    clash_secret: Optional[str] = None
    clash_proxy_port: int
    clash_proxy_group: str
    proxy_pool_keywords: str = ""
    mihomo_binary_path: Optional[str] = None
    clash_config_path: Optional[str] = None
    proxy_pool_controller_port: int = 9108
    proxy_pool_start_port: int = 20000
    proxy_pool_size: int = 10
    ext_proxy_file_path: Optional[str] = None
    ipinfo_token: Optional[str] = None
    cf_account_id: Optional[str] = None
    cf_kv_namespace_id: Optional[str] = None
    cf_api_token: Optional[str] = None
    # Outlook Manager
    outlook_manager_url: Optional[str] = None
    outlook_manager_api_key: Optional[str] = None
    outlook_poll_interval: int = 5
    outlook_poll_timeout: int = 120


class SettingsUpdate(BaseModel):
    """更新系统设置"""

    dreamina_url: Optional[str] = None
    register_timeout: Optional[int] = None
    verification_timeout: Optional[int] = None
    max_retry_count: Optional[int] = None
    max_concurrency: Optional[int] = None
    gen_async_enabled: Optional[bool] = None
    gen_image_async_poll_interval: Optional[int] = None
    gen_video_async_poll_interval: Optional[int] = None
    register_interval_min: Optional[int] = None
    register_interval_max: Optional[int] = None
    password_length: Optional[int] = None
    password_include_special: Optional[bool] = None
    browser_headless: Optional[bool] = None
    clash_controller_url: Optional[str] = None
    clash_secret: Optional[str] = None
    clash_proxy_port: Optional[int] = None
    clash_proxy_group: Optional[str] = None
    proxy_pool_keywords: Optional[str] = None
    mihomo_binary_path: Optional[str] = None
    clash_config_path: Optional[str] = None
    proxy_pool_controller_port: Optional[int] = None
    proxy_pool_start_port: Optional[int] = None
    proxy_pool_size: Optional[int] = None
    ext_proxy_file_path: Optional[str] = None
    ipinfo_token: Optional[str] = None
    cf_account_id: Optional[str] = None
    cf_kv_namespace_id: Optional[str] = None
    cf_api_token: Optional[str] = None
    # Outlook Manager
    outlook_manager_url: Optional[str] = None
    outlook_manager_api_key: Optional[str] = None
    outlook_poll_interval: Optional[int] = None
    outlook_poll_timeout: Optional[int] = None


# ==================== WebSocket Schemas ====================


class LogMessage(BaseModel):
    """日志消息"""

    timestamp: datetime
    level: str  # INFO / WARNING / ERROR
    message: str
    email: Optional[str] = None
    task_id: Optional[str] = None


class TaskProgress(BaseModel):
    """任务进度"""

    task_id: str
    status: str
    success_count: int
    failure_count: int
    progress: float
    current_step: Optional[str] = None
    current_email: Optional[str] = None


# ==================== Common Schemas ====================


class PaginationParams(BaseModel):
    """分页参数"""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class PaginatedResponse(BaseModel):
    """分页响应"""

    total: int
    page: int
    page_size: int
    items: List


class MessageResponse(BaseModel):
    """通用消息响应"""

    message: str
    success: bool = True
