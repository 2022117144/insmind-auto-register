"""
系统设置 API 路由
"""

from fastapi import APIRouter
from app.core.config import settings
from app.schemas import SettingsResponse, SettingsUpdate, MessageResponse

router = APIRouter()


@router.get("", response_model=SettingsResponse)
async def get_settings():
    """获取系统设置"""
    return SettingsResponse(
        dreamina_url=settings.dreamina_url,
        register_timeout=settings.register_timeout,
        verification_timeout=settings.verification_timeout,
        max_retry_count=settings.max_retry_count,
        max_concurrency=settings.max_concurrency,
        gen_async_enabled=settings.gen_async_enabled,
        gen_image_async_poll_interval=settings.gen_image_async_poll_interval,
        gen_video_async_poll_interval=settings.gen_video_async_poll_interval,
        register_interval_min=settings.register_interval_min,
        register_interval_max=settings.register_interval_max,
        password_length=settings.password_length,
        password_include_special=settings.password_include_special,
        browser_headless=settings.browser_headless,
        clash_controller_url=settings.clash_controller_url,
        clash_secret=settings.clash_secret,
        clash_proxy_port=settings.clash_proxy_port,
        clash_proxy_group=settings.clash_proxy_group,
        proxy_pool_keywords=settings.proxy_pool_keywords,
        mihomo_binary_path=settings.mihomo_binary_path,
        clash_config_path=settings.clash_config_path,
        proxy_pool_controller_port=settings.proxy_pool_controller_port,
        proxy_pool_start_port=settings.proxy_pool_start_port,
        proxy_pool_size=settings.proxy_pool_size,
        ext_proxy_file_path=settings.ext_proxy_file_path,
        ipinfo_token=settings.ipinfo_token,
        cf_account_id=settings.cf_account_id,
        cf_kv_namespace_id=settings.cf_kv_namespace_id,
        cf_api_token=settings.cf_api_token,
        outlook_manager_url=settings.outlook_manager_url,
        outlook_manager_api_key=settings.outlook_manager_api_key,
        outlook_poll_interval=settings.outlook_poll_interval,
        outlook_poll_timeout=settings.outlook_poll_timeout,
    )


@router.put("", response_model=MessageResponse)
async def update_settings(data: SettingsUpdate):
    """
    更新系统设置
    """
    updates = {}

    # 更新内存中的设置
    if data.dreamina_url is not None:
        settings.dreamina_url = data.dreamina_url
        updates["DREAMINA_URL"] = data.dreamina_url
    if data.register_timeout is not None:
        settings.register_timeout = data.register_timeout
        updates["REGISTER_TIMEOUT"] = str(data.register_timeout)
    if data.verification_timeout is not None:
        settings.verification_timeout = data.verification_timeout
        updates["VERIFICATION_TIMEOUT"] = str(data.verification_timeout)
    if data.max_retry_count is not None:
        settings.max_retry_count = data.max_retry_count
        updates["MAX_RETRY_COUNT"] = str(data.max_retry_count)
    if data.max_concurrency is not None:
        settings.max_concurrency = data.max_concurrency
        updates["MAX_CONCURRENCY"] = str(data.max_concurrency)
    if data.gen_async_enabled is not None:
        settings.gen_async_enabled = data.gen_async_enabled
        updates["GEN_ASYNC_ENABLED"] = str(data.gen_async_enabled).lower()
    if data.gen_image_async_poll_interval is not None:
        settings.gen_image_async_poll_interval = data.gen_image_async_poll_interval
        updates["GEN_IMAGE_ASYNC_POLL_INTERVAL"] = str(
            data.gen_image_async_poll_interval
        )
    if data.gen_video_async_poll_interval is not None:
        settings.gen_video_async_poll_interval = data.gen_video_async_poll_interval
        updates["GEN_VIDEO_ASYNC_POLL_INTERVAL"] = str(
            data.gen_video_async_poll_interval
        )
    if data.register_interval_min is not None:
        settings.register_interval_min = data.register_interval_min
        updates["REGISTER_INTERVAL_MIN"] = str(data.register_interval_min)
    if data.register_interval_max is not None:
        settings.register_interval_max = data.register_interval_max
        updates["REGISTER_INTERVAL_MAX"] = str(data.register_interval_max)
    if data.password_length is not None:
        settings.password_length = data.password_length
        updates["PASSWORD_LENGTH"] = str(data.password_length)
    if data.password_include_special is not None:
        settings.password_include_special = data.password_include_special
        updates["PASSWORD_INCLUDE_SPECIAL"] = str(data.password_include_special).lower()
    if data.browser_headless is not None:
        settings.browser_headless = data.browser_headless
        updates["BROWSER_HEADLESS"] = str(data.browser_headless).lower()
    if data.clash_controller_url is not None:
        settings.clash_controller_url = data.clash_controller_url
        updates["CLASH_CONTROLLER_URL"] = data.clash_controller_url
    if data.clash_secret is not None:
        settings.clash_secret = data.clash_secret
        updates["CLASH_SECRET"] = data.clash_secret
    if data.clash_proxy_port is not None:
        settings.clash_proxy_port = data.clash_proxy_port
        updates["CLASH_PROXY_PORT"] = str(data.clash_proxy_port)
    if data.clash_proxy_group is not None:
        settings.clash_proxy_group = data.clash_proxy_group
        updates["CLASH_PROXY_GROUP"] = data.clash_proxy_group
    if data.proxy_pool_keywords is not None:
        settings.proxy_pool_keywords = data.proxy_pool_keywords
        updates["PROXY_POOL_KEYWORDS"] = data.proxy_pool_keywords

    # Local Pool Settings
    if data.mihomo_binary_path is not None:
        clean_path = data.mihomo_binary_path.strip("\"'").replace("\\", "/")
        settings.mihomo_binary_path = clean_path
        updates["MIHOMO_BINARY_PATH"] = clean_path
    if data.clash_config_path is not None:
        clean_path = data.clash_config_path.strip("\"'").replace("\\", "/")
        settings.clash_config_path = clean_path
        updates["CLASH_CONFIG_PATH"] = clean_path
    if data.proxy_pool_start_port is not None:
        settings.proxy_pool_start_port = data.proxy_pool_start_port
        updates["PROXY_POOL_START_PORT"] = str(data.proxy_pool_start_port)
    if data.proxy_pool_controller_port is not None:
        settings.proxy_pool_controller_port = data.proxy_pool_controller_port
        updates["PROXY_POOL_CONTROLLER_PORT"] = str(data.proxy_pool_controller_port)
    if data.proxy_pool_size is not None:
        settings.proxy_pool_size = data.proxy_pool_size
        updates["PROXY_POOL_SIZE"] = str(data.proxy_pool_size)
    if data.ext_proxy_file_path is not None:
        clean_path = data.ext_proxy_file_path.strip("\"'").replace("\\", "/")
        settings.ext_proxy_file_path = clean_path
        updates["EXT_PROXY_FILE_PATH"] = clean_path
    if data.ipinfo_token is not None:
        settings.ipinfo_token = data.ipinfo_token
        updates["IPINFO_TOKEN"] = data.ipinfo_token

    # Cloudflare Settings
    if data.cf_account_id is not None:
        settings.cf_account_id = data.cf_account_id
        updates["CF_ACCOUNT_ID"] = data.cf_account_id
    if data.cf_kv_namespace_id is not None:
        settings.cf_kv_namespace_id = data.cf_kv_namespace_id
        updates["CF_KV_NAMESPACE_ID"] = data.cf_kv_namespace_id
    if data.cf_api_token is not None:
        settings.cf_api_token = data.cf_api_token
        updates["CF_API_TOKEN"] = data.cf_api_token

    # Outlook Manager Settings
    if data.outlook_manager_url is not None:
        settings.outlook_manager_url = data.outlook_manager_url
        updates["OUTLOOK_MANAGER_URL"] = data.outlook_manager_url
    if data.outlook_manager_api_key is not None:
        settings.outlook_manager_api_key = data.outlook_manager_api_key
        updates["OUTLOOK_MANAGER_API_KEY"] = data.outlook_manager_api_key
    if data.outlook_poll_interval is not None:
        settings.outlook_poll_interval = data.outlook_poll_interval
        updates["OUTLOOK_POLL_INTERVAL"] = str(data.outlook_poll_interval)
    if data.outlook_poll_timeout is not None:
        settings.outlook_poll_timeout = data.outlook_poll_timeout
        updates["OUTLOOK_POLL_TIMEOUT"] = str(data.outlook_poll_timeout)

    # 尝试写入 .env 文件
    try:
        from pathlib import Path

        env_path = Path(".env")
        if env_path.exists():
            lines = env_path.read_text(encoding="utf-8").splitlines()
            new_lines = []
            updated_keys = set()

            for line in lines:
                if "=" in line and not line.strip().startswith("#"):
                    key = line.split("=", 1)[0].strip()
                    if key in updates:
                        new_lines.append(
                            f"{key}={updates[key]}"
                        )  # Removed quotes to be safer? No, usually quotes are good. But .env parsers vary. Let's keep quotes if strings.
                        updated_keys.add(key)
                        continue
                new_lines.append(line)

            # 追加未找到的配置
            for key, value in updates.items():
                if key not in updated_keys:
                    new_lines.append(f"{key}={value}")  # Keep consistent

            env_path.write_text("\n".join(new_lines), encoding="utf-8")
    except Exception as e:
        print(f"Failed to update .env: {e}")

    return MessageResponse(message="设置已更新并保存至配置文件")
