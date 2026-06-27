import sys
import asyncio

# Windows 下使用 Playwright 必须使用 ProactorEventLoop
if sys.platform == "win32":
    try:
        from asyncio import WindowsProactorEventLoopPolicy

        if not isinstance(
            asyncio.get_event_loop_policy(), WindowsProactorEventLoopPolicy
        ):
            asyncio.set_event_loop_policy(WindowsProactorEventLoopPolicy())
    except Exception:
        pass

"""
Dreamina Auto Register - FastAPI 主入口
"""
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pathlib import Path

from app.core import settings, ensure_directories, init_db
from app.middleware.error_handler import global_exception_handler
import app.models  # 确保模型被加载
from app.services.register_engine import register_engine
from app.services.insmind_register_engine import insmind_register_engine
from app.services.clash_manager import clash_manager
from app.services.cloudflare_kv import cf_kv_client
from app.services.task_scheduler import task_scheduler
from app.services.db_migration import (
    ensure_proxy_node_columns,
    ensure_accounts_login_status_column,
    ensure_accounts_generation_columns,
    ensure_content_generation_jobs_table,
    ensure_task_records_email_source_column,
    ensure_insmind_accounts_refresh_token_column,
    ensure_insmind_accounts_org_id_column,
)
import logging
from logging.handlers import TimedRotatingFileHandler

# 配置日志
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        TimedRotatingFileHandler(
            filename=settings.logs_dir / "app.log",
            when="midnight",
            interval=1,
            backupCount=2,
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("insMind Auto Register 启动中...")

    # 确保目录存在
    ensure_directories()

    # 初始化数据库
    await init_db()
    logger.info("数据库初始化完成")

    # 轻量迁移：确保 proxy_nodes 外部代理字段存在
    await ensure_proxy_node_columns()

    # 轻量迁移：确保 accounts 登录状态字段存在
    await ensure_accounts_login_status_column()

    # 轻量迁移：确保 task_records.email_source 字段存在（Outlook 模式支持）
    from app.services.db_migration import ensure_task_records_email_source_column

    await ensure_task_records_email_source_column()

    # 轻量迁移：确保内容生成字段和表存在
    await ensure_accounts_generation_columns()
    await ensure_content_generation_jobs_table()

    # 轻量迁移：确保 insmind_accounts refresh_token 列存在
    await ensure_insmind_accounts_refresh_token_column()

    # 轻量迁移：确保 insmind_accounts org_id 列存在
    await ensure_insmind_accounts_org_id_column()

    # 初始化 WebSocket 日志转发
    from app.api.routers.websocket import WebSocketLogHandler

    root_logger = logging.getLogger()
    ws_handler = WebSocketLogHandler()
    ws_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    root_logger.addHandler(ws_handler)
    logger.info("WebSocket 日志转发已启用")

    # 初始化注册引擎（兼容旧 Dreamina + 新 insMind）
    try:
        await register_engine.initialize()
        logger.info("Dreamina 注册引擎初始化完成（兼容旧模块）")
    except Exception as e:
        logger.debug(f"Dreamina 注册引擎初始化跳过: {e}")

    try:
        await insmind_register_engine.initialize()
        logger.info("insMind 注册引擎初始化完成")
    except Exception as e:
        logger.error(f"insMind 注册引擎初始化失败: {e}")
        logger.warning("注册功能暂不可用，但不影响其他模块。")

    # 检查 Clash 连接
    if await clash_manager.check_connection():
        logger.info("Clash 连接正常")
    else:
        logger.warning("Clash 连接失败，请检查 Clash Verge 是否运行")

    # 检查 Cloudflare KV 配置
    if cf_kv_client.is_configured:
        kv_test = await cf_kv_client.test_connection()
        if kv_test["success"]:
            logger.info("Cloudflare KV 连接正常")
        else:
            logger.warning(f"Cloudflare KV 连接失败: {kv_test.get('error')}")
    else:
        logger.warning("Cloudflare KV 未配置")

    # 启动本地代理池 (如果配置)
    from app.services.proxy_pool_runner import pool_runner
    from app.services.proxy_pool import proxy_pool
    from app.core.database import async_session_factory
    from sqlalchemy import select
    from app.models.proxy_node import ProxyNode

    async with async_session_factory() as db:
        # 1. 强制同步外部代理配置
        await proxy_pool.load_from_file(clear_existing=True)
        ext_proxies = [p for p in proxy_pool.proxies if p.group == "external"]
        ext_keys_in_file = {p.unique_id for p in ext_proxies}

        # 删除废弃外服节点
        existing_ext_stmt = select(ProxyNode).where(ProxyNode.source == "external")
        existing_ext = list((await db.execute(existing_ext_stmt)).scalars().all())
        for node in existing_ext:
            key = f"{node.host}:{node.port}:{getattr(node, 'username', '') or ''}:{getattr(node, 'password', '') or ''}"
            if key not in ext_keys_in_file:
                await db.delete(node)

        # 插入或激活外服节点
        ext_map = {
            f"{node.host}:{node.port}:{getattr(node, 'username', '') or ''}:{getattr(node, 'password', '') or ''}": node
            for node in existing_ext
        }

        for p in ext_proxies:
            if p.unique_id in ext_map:
                node = ext_map[p.unique_id]
                p.is_enabled = node.is_enabled
                p.node_id = node.id
                # 同步最新的协议信息
                if node.protocol != p.protocol:
                    node.protocol = p.protocol
            else:
                new_node = ProxyNode(
                    name=p.name,
                    host=p.host,
                    port=p.port,
                    username=p.username,
                    password=p.password,
                    protocol=p.protocol,
                    source="external",
                    is_enabled=True,
                    region_tag=None,
                )
                db.add(new_node)
        await db.commit()

        # 2. 从数据库提取启用的节点用于启动 Mihomo
        stmt = select(ProxyNode).where(ProxyNode.is_enabled == True)
        enabled_nodes = (await db.execute(stmt)).scalars().all()

        enabled_clash_names = []
        enabled_external = []
        for n in enabled_nodes:
            if str(getattr(n, "source", "")) == "external":
                enabled_external.append(n)
            else:
                enabled_clash_names.append(n.name)

        # 3. 启动并加载本地多端口代理池 (Mihomo/Clash)
        active_ports_info = []

        external_for_runner = []
        for p in enabled_external:
            external_for_runner.append(
                {
                    "name": p.name or f"ext-{p.host}:{p.port}",
                    "type": str(p.protocol or "socks5").lower(),
                    "protocol": str(p.protocol or "socks5").lower(),
                    "server": str(p.host),
                    "port": int(p.port),
                    "username": str(p.username or ""),
                    "password": str(p.password or ""),
                    "skip-cert-verify": True,
                    "udp": False,
                    "__is_external": True,
                }
            )

        if enabled_clash_names or external_for_runner:
            active_ports_info = await pool_runner.start(
                allowed_proxy_names=enabled_clash_names,
                external_proxies=external_for_runner,
            )

        if active_ports_info:
            ports_list = [item["port"] for item in active_ports_info]
            logger.info(
                f"本地代理池已启动，端口范围: {min(ports_list) if ports_list else '-'} - {max(ports_list) if ports_list else '-'} ({len(ports_list)} nodes)"
            )

            ports_to_load = []

            def normalize_name(name):
                return str(name).strip() if name else ""

            node_map_normalized = {
                normalize_name(str(getattr(n, "name", ""))): n for n in enabled_nodes
            }

            for item in active_ports_info:
                node_name = item.get("name")
                normalized_name = normalize_name(str(node_name) if node_name else "")
                node = node_map_normalized.get(normalized_name)

                if node:
                    ports_to_load.append(
                        {
                            "port": item["port"],
                            "node_name": node.name,
                            "node_id": node.id,
                            "usage_count": node.usage_count or 0,
                            "region_tag": node.region_tag,
                            "group": "external"
                            if str(getattr(node, "source", "")) == "external"
                            else node.region_tag,
                            "original_host": item.get("original_host"),
                            "original_port": item.get("original_port"),
                            "original_username": item.get("original_username"),
                            "original_password": item.get("original_password"),
                            "original_protocol": item.get("original_protocol"),
                            "is_external": item.get("is_external"),
                        }
                    )
                else:
                    ports_to_load.append(item)

            # 立即加载到 proxy_pool
            await proxy_pool.load_from_local_ports(
                ports_to_load, preserve_external=False
            )

    # 启动任务调度器
    await task_scheduler.start()

    # 启动内容生成队列
    from app.services.content_generation import content_generation_service

    await content_generation_service.start()

    # 恢复重启前未完成的任务
    try:
        from sqlalchemy import select
        from app.models import TaskRecord

        async with async_session_factory() as db:
            stmt = select(TaskRecord).where(
                TaskRecord.status.in_(["queued", "running"])
            )
            pending_tasks = (await db.execute(stmt)).scalars().all()
            for task in pending_tasks:
                old_status = task.status
                task.status = "failed"
                task.completed_at = datetime.utcnow()
                task.current_step = f"Interrupted by system restart (was {old_status})"
                logger.info(f"清理残留任务 {task.task_id}: {old_status} -> failed")
            await db.commit()
            if pending_tasks:
                logger.info(f"已清理 {len(pending_tasks)} 个由于系统重启而中断的任务")
    except Exception as e:
        logger.error(f"恢复中断任务失败: {e}")

    logger.info("Dreamina Auto Register 启动完成!")

    yield

    # 关闭时
    logger.info("Dreamina Auto Register 关闭中...")
    await task_scheduler.stop()
    from app.services.content_generation import content_generation_service

    await content_generation_service.stop()
    await register_engine.shutdown()
    await insmind_register_engine.shutdown()
    await clash_manager.close()
    await cf_kv_client.close()
    pool_runner.stop()
    logger.info("insMind Auto Register 已关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.app_name,
    description="insMind 国际版自动注册系统 API",
    version="3.0.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本地开发允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册全局异常处理
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(StarletteHTTPException, global_exception_handler)
app.add_exception_handler(RequestValidationError, global_exception_handler)

# 静态文件（截图）已停用

# 静态文件（缩略图）
thumbnails_dir = settings.data_dir / "thumbnails"
thumbnails_dir.mkdir(parents=True, exist_ok=True)
app.mount(
    "/thumbnails",
    StaticFiles(directory=str(thumbnails_dir.absolute())),
    name="thumbnails",
)

# 静态文件（本地输出原图/视频）
outputs_dir = settings.data_dir / "outputs"
outputs_dir.mkdir(parents=True, exist_ok=True)
app.mount(
    "/outputs", StaticFiles(directory=str(outputs_dir.absolute())), name="outputs"
)


# =========================
# 导入并注册路由
# =========================
from app.api.routers import (
    tasks,
    accounts,
    proxies,
    domains,
    settings as settings_router,
    websocket,
    dashboard,
    content_generation,
)
from app.api.routers import outlook_mailboxes
from app.api.routers import insmind_accounts
from app.api.routers import photogpt_accounts
from app.api.routers import photogpt_generation

app.include_router(tasks.router, prefix="/api/tasks", tags=["任务管理"])
app.include_router(accounts.router, prefix="/api/accounts", tags=["账号管理"])
app.include_router(proxies.router, prefix="/api/proxies", tags=["代理管理"])
app.include_router(domains.router, prefix="/api/domains", tags=["域名管理"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["系统设置"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["仪表盘"])
app.include_router(websocket.router, tags=["WebSocket"])
app.include_router(
    outlook_mailboxes.router, prefix="/api/outlook-mailboxes", tags=["Outlook 邮箱"]
)
app.include_router(
    insmind_accounts.router, prefix="/api", tags=["insMind 账号"]
)
app.include_router(
    photogpt_accounts.router, prefix="/api", tags=["PhotoGPT 账号"]
)
app.include_router(
    photogpt_generation.router, prefix="/api", tags=["PhotoGPT 生成"]
)
app.include_router(content_generation.router, prefix="/api/content", tags=["内容生成"])


# HEALTH CHECK REMOVED - SERVED BY SPA


@app.get("/api/health", tags=["健康检查"])
async def health_check():
    """详细健康检查"""
    clash_status = await clash_manager.check_connection()
    kv_status = cf_kv_client.is_configured

    return {
        "status": "healthy",
        "services": {
            "clash": "connected" if clash_status else "disconnected",
            "cloudflare_kv": "configured" if kv_status else "not_configured",
        },
    }


# 静态文件服务配置
# 1. 挂载 assets 目录 (JS/CSS)
# 前端构建产物在项目根目录的 frontend/dist/ 下
import os
from pathlib import Path
from app.core import BASE_DIR

# Frontend dist path: project_root/frontend/dist
from pathlib import Path
import sys, os
# 从当前文件位置推算: main.py 在 backend/app/
app_dir = Path(__file__).resolve().parent.parent  # backend/
project_root = app_dir.parent  # 项目根目录
frontend_dist = project_root / "frontend" / "dist"
assets_path = frontend_dist / "assets"

if assets_path.exists():
    app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")
    logger.info(f"已挂载前端静态资源: {assets_path}")


# 2. 挂载入口 HTML 并支持 SPA 路由
@app.get("/{path:path}")
async def serve_spa(path: str):
    # 排除 API 路由
    if path.startswith("api/"):
        raise StarletteHTTPException(status_code=404)

    index_file = frontend_dist / "index.html"
    if index_file.exists():
        from fastapi.responses import FileResponse

        return FileResponse(index_file)

    return {
        "detail": "Frontend assets not found. Please run 'npm run build' in frontend directory."
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app", host="0.0.0.0", port=8005, reload=settings.debug, loop="asyncio"
    )
