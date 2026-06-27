"""
Dreamina Auto Register System - 核心配置
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import sys
import os
from pathlib import Path


def get_base_dir():
    """获取程序运行根目录 (EXE所在目录)"""
    if getattr(sys, "frozen", False):
        return Path(os.path.dirname(sys.executable))
    return Path(".")


def get_resource_path(relative_path: str) -> Path:
    """获取资源文件路径 (支持 PyInstaller 打包)"""
    if getattr(sys, "frozen", False):
        # PyInstaller 会将资源放在 _MEIPASS 中 (通常是 _internal 目录)
        base_path = Path(getattr(sys, "_MEIPASS", os.path.dirname(sys.executable)))
        return base_path / relative_path
    return Path(".") / relative_path


BASE_DIR = get_base_dir()


class Settings(BaseSettings):
    """系统配置"""

    # 应用配置
    app_name: str = "insMind Auto Register"
    debug: bool = Field(default=False, description="调试模式")

    database_url: str = Field(
        default=f"sqlite+aiosqlite:///{BASE_DIR}/data/dreamina.db",
        description="SQLite 数据库连接字符串",
    )

    # Dreamina 配置
    dreamina_url: str = Field(
        default="https://dreamina.capcut.com/ai-tool/login",
        description="Dreamina 目标站点地址",
    )
    jimeng_api_url: str = Field(
        default="http://127.0.0.1:5105", description="独立运行的 JimengService API 地址"
    )
    register_timeout: int = Field(default=300, description="注册总超时（秒）")
    verification_timeout: int = Field(default=180, description="验证码等待超时（秒）")
    page_load_timeout: int = Field(default=60, description="页面加载超时（秒）")
    selector_timeout: int = Field(default=30, description="选择器等待超时（秒）")
    max_retry_count: int = Field(default=2, description="最大重试次数")
    register_interval_min: int = Field(default=10, description="注册间隔最小值（秒）")
    register_interval_max: int = Field(default=30, description="注册间隔最大值（秒）")

    # insMind 配置
    insmind_url: str = Field(
        default="https://www.insmind.com",
        description="insMind 目标站点地址",
    )
    insmind_register_timeout: int = Field(default=300, description="注册总超时（秒）")
    insmind_verification_timeout: int = Field(default=180, description="验证码等待超时（秒）")
    insmind_concurrency: int = Field(default=5, description="insMind 最大并发注册数")

    # 密码配置（insMind 无需密码，保留仅兼容）
    password_length: int = Field(default=14, description="密码长度")
    password_include_special: bool = Field(default=True, description="是否包含特殊字符")

    # 浏览器配置
    browser_headless: bool = Field(default=False, description="无头模式")

    # Clash Verge 配置
    clash_controller_url: str = Field(
        default="http://127.0.0.1:9090", description="Clash External Controller 地址"
    )
    clash_secret: Optional[str] = Field(default=None, description="Clash 密钥")
    clash_proxy_port: int = Field(default=7890, description="Clash 代理端口")
    clash_proxy_protocol: str = Field(
        default="http", description="代理协议 http/socks5"
    )
    clash_proxy_group: str = Field(default="良心云", description="目标代理组名称")
    proxy_pool_controller_port: int = Field(
        default=9108, description="代理池 External Controller 端口"
    )

    # Local Proxy Pool specific
    clash_config_path: Optional[str] = Field(
        default=None, description="Clash 配置文件路径 (用于生成本地代理池)"
    )
    mihomo_binary_path: Optional[str] = Field(
        default=None, description="Mihomo/Clash Meta 可执行文件路径"
    )
    proxy_pool_start_port: int = Field(default=20000, description="代理池起始端口")
    proxy_pool_size: int = Field(default=10, description="代理池大小 (最大并发连接数)")
    proxy_pool_keywords: str = Field(
        default="HK,SG,JP,US,KR,TW,香港,新加坡,日本,美国,韩国,台湾",
        description="代理筛选关键字 (逗号分隔)",
    )
    max_concurrency: int = Field(default=1, description="最大并发注册任务数")

    # 内容生成配置
    gen_max_concurrency: int = Field(default=8, description="内容生成最大并发数")
    gen_credit_rules: str = Field(default="{}", description="内容生成积分规则 JSON")
    gen_async_enabled: bool = Field(default=True, description="是否启用异步生成")
    gen_image_async_poll_interval: int = Field(
        default=5, description="图片异步轮询间隔（秒）"
    )
    gen_video_async_poll_interval: int = Field(
        default=20, description="视频异步轮询间隔（秒）"
    )

    # Proxy preflight
    ipinfo_token: Optional[str] = Field(default=None, description="ipinfo.io token")

    # 外部代理配置
    # 外部代理配置
    ext_proxy_file_path: Optional[str] = Field(
        default=str(BASE_DIR / "proxies.txt"),
        description="外部代理列表文件路径 (HTTP/SOCKS5)",
    )

    # Cloudflare KV 配置
    cf_account_id: Optional[str] = Field(
        default=None, description="Cloudflare Account ID"
    )
    cf_kv_namespace_id: Optional[str] = Field(
        default=None, description="KV Namespace ID"
    )
    cf_api_token: Optional[str] = Field(
        default=None, description="Cloudflare API Token"
    )
    kv_poll_interval: int = Field(default=3, description="KV 轮询间隔（秒）")
    kv_poll_timeout: int = Field(default=180, description="KV 查询超时（秒）")

    # Outlook Manager 配置
    outlook_manager_url: Optional[str] = Field(
        default=None,
        description="OutlookManager API 服务地址 (e.g. http://localhost:8089)",
    )
    outlook_manager_api_key: Optional[str] = Field(
        default=None, description="OutlookManager 外部 API Key (X-API-Key)"
    )
    outlook_poll_interval: int = Field(
        default=5, description="Outlook 邮件轮询间隔（秒）"
    )
    outlook_poll_timeout: int = Field(
        default=120, description="Outlook 邮件等待超时（秒）"
    )

    # 路径配置
    data_dir: Path = Field(default=BASE_DIR / "data", description="数据目录")
    logs_dir: Path = Field(default=BASE_DIR / "logs", description="日志目录")
    screenshots_dir: Path = Field(
        default=BASE_DIR / "data" / "screenshots", description="截图目录"
    )
    browser_states_dir: Path = Field(
        default=BASE_DIR / "data" / "browser_states", description="浏览器状态目录"
    )

    # 日志配置
    log_retention_days: int = Field(default=30, description="日志保留天数")
    screenshot_retention_days: int = Field(default=7, description="截图保留天数")

    from pydantic import field_validator

    @field_validator(
        "mihomo_binary_path", "clash_config_path", "ext_proxy_file_path", mode="before"
    )
    @classmethod
    def clean_paths(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v.strip("\"'").replace("\\", "/")
        return v

    class Config:
        case_sensitive = False
        env_file_encoding = "utf-8"


# 延迟实例化以便进行可能的路径微调
settings = Settings(_env_file=str(BASE_DIR / ".env"))
print(f"DEBUG: Loading config from {BASE_DIR / '.env'}")


# 确保目录存在
def ensure_directories():
    """确保所有必需的目录存在"""
    for dir_path in [
        settings.data_dir,
        settings.logs_dir,
        settings.screenshots_dir,
        settings.browser_states_dir,
    ]:
        dir_path.mkdir(parents=True, exist_ok=True)

    # 外部代理文件处理 (仅检查不自动创建目录，因为它是个文件)
    if settings.ext_proxy_file_path:
        ext_path = Path(settings.ext_proxy_file_path)
        if not ext_path.is_absolute():
            # 默认为项目根目录
            pass
