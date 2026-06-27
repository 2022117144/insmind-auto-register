"""
Database migration helpers for lightweight schema updates.
"""

from sqlalchemy import text
from app.core.database import async_session_factory
import logging

logger = logging.getLogger(__name__)


async def ensure_proxy_node_columns():
    """Ensure proxy_nodes has external proxy columns."""
    columns = [
        ("host", "VARCHAR(255)"),
        ("port", "INTEGER"),
        ("username", "VARCHAR(255)"),
        ("password", "VARCHAR(255)"),
        ("protocol", "VARCHAR(20)"),
        ("source", "VARCHAR(20) DEFAULT 'clash'"),
    ]

    async with async_session_factory() as session:
        result = await session.execute(text("PRAGMA table_info(proxy_nodes)"))
        existing_cols = {row[1] for row in result.fetchall()}

        for col_name, col_def in columns:
            if col_name in existing_cols:
                continue
            try:
                await session.execute(
                    text(f"ALTER TABLE proxy_nodes ADD COLUMN {col_name} {col_def}")
                )
                logger.info(f"Added column proxy_nodes.{col_name}")
            except Exception as exc:
                logger.error(f"Failed to add column {col_name}: {exc}")

        await session.commit()


async def ensure_accounts_login_status_column():
    """Ensure accounts has last_login_status column for consistency checks."""
    async with async_session_factory() as session:
        result = await session.execute(text("PRAGMA table_info(accounts)"))
        existing_cols = {row[1] for row in result.fetchall()}

        if "last_login_status" not in existing_cols:
            try:
                await session.execute(
                    text(
                        "ALTER TABLE accounts ADD COLUMN last_login_status VARCHAR(20)"
                    )
                )
                logger.info("Added column accounts.last_login_status")
                await session.commit()
            except Exception as exc:
                logger.error(f"Failed to add accounts.last_login_status: {exc}")


async def ensure_task_records_email_source_column():
    """Ensure task_records has email_source column for outlook mode support."""
    async with async_session_factory() as session:
        result = await session.execute(text("PRAGMA table_info(task_records)"))
        existing_cols = {row[1] for row in result.fetchall()}

        if "email_source" not in existing_cols:
            try:
                await session.execute(
                    text(
                        "ALTER TABLE task_records ADD COLUMN email_source VARCHAR(20) DEFAULT 'cloudflare'"
                    )
                )
                logger.info("Added column task_records.email_source")
                await session.commit()
            except Exception as exc:
                logger.error(f"Failed to add task_records.email_source: {exc}")


async def ensure_accounts_generation_columns():
    """Ensure accounts has content generation pool columns."""
    columns = [
        ("gen_enabled", "BOOLEAN DEFAULT 0"),
        ("gen_enabled_at", "DATETIME"),
        ("gen_last_used_at", "DATETIME"),
        ("gen_locked_until", "DATETIME"),
        ("gen_auto_disabled_reason", "VARCHAR(255)"),
    ]

    async with async_session_factory() as session:
        result = await session.execute(text("PRAGMA table_info(accounts)"))
        existing_cols = {row[1] for row in result.fetchall()}

        for col_name, col_def in columns:
            if col_name in existing_cols:
                continue
            try:
                await session.execute(
                    text(f"ALTER TABLE accounts ADD COLUMN {col_name} {col_def}")
                )
                logger.info(f"Added column accounts.{col_name}")
            except Exception as exc:
                logger.error(f"Failed to add accounts.{col_name}: {exc}")

        await session.commit()


async def ensure_insmind_accounts_refresh_token_column():
    """Ensure insmind_accounts has refresh_token column for token refresh support."""
    async with async_session_factory() as session:
        result = await session.execute(text("PRAGMA table_info(insmind_accounts)"))
        existing_cols = {row[1] for row in result.fetchall()}

        if "refresh_token" not in existing_cols:
            try:
                await session.execute(
                    text(
                        "ALTER TABLE insmind_accounts ADD COLUMN refresh_token TEXT DEFAULT ''"
                    )
                )
                logger.info("Added column insmind_accounts.refresh_token")
                await session.commit()
            except Exception as exc:
                logger.error(f"Failed to add insmind_accounts.refresh_token: {exc}")


async def ensure_insmind_accounts_org_id_column():
    """Ensure insmind_accounts has org_id column for tenant activation support."""
    async with async_session_factory() as session:
        result = await session.execute(text("PRAGMA table_info(insmind_accounts)"))
        existing_cols = {row[1] for row in result.fetchall()}

        if "org_id" not in existing_cols:
            try:
                await session.execute(
                    text(
                        "ALTER TABLE insmind_accounts ADD COLUMN org_id VARCHAR(100) DEFAULT ''"
                    )
                )
                await session.commit()
                logger.info("Added column insmind_accounts.org_id")
            except Exception as exc:
                logger.error(f"Failed to add insmind_accounts.org_id: {exc}")


async def ensure_content_generation_jobs_table():
    """Ensure content_generation_jobs table exists and has async task columns."""
    async with async_session_factory() as session:
        result = await session.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='content_generation_jobs'"
            )
        )
        exists = result.scalar() is not None
        if not exists:
            try:
                await session.execute(
                    text(
                        """
                    CREATE TABLE content_generation_jobs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        job_type VARCHAR(20) NOT NULL,
                        status VARCHAR(20) DEFAULT 'queued',
                        prompt TEXT,
                        model VARCHAR(100),
                        ratio VARCHAR(20),
                        resolution VARCHAR(20),
                        duration INTEGER,
                        function_mode VARCHAR(50),
                        input_images TEXT,
                        output_urls TEXT,
                        thumbnail_urls TEXT,
                        local_urls TEXT,
                        error_message TEXT,
                        remote_task_id TEXT,
                        remote_history_id TEXT,
                        remote_kind TEXT,
                        remote_status TEXT,
                        remote_fail_code TEXT,
                        remote_error_message TEXT,
                        account_id INTEGER,
                        region VARCHAR(50),
                        submitted_at DATETIME,
                        finished_at DATETIME,
                        created_at DATETIME,
                        updated_at DATETIME,
                        FOREIGN KEY(account_id) REFERENCES accounts(id)
                    )
                    """
                    )
                )
                logger.info("Created table content_generation_jobs")
                await session.commit()
            except Exception as exc:
                logger.error(f"Failed to create content_generation_jobs: {exc}")
        else:
            col_result = await session.execute(
                text("PRAGMA table_info(content_generation_jobs)")
            )
            existing_cols = {row[1] for row in col_result.fetchall()}
            columns = [
                ("thumbnail_urls", "TEXT"),
                ("local_urls", "TEXT"),
                ("function_mode", "VARCHAR(50)"),
                ("remote_task_id", "TEXT"),
                ("remote_history_id", "TEXT"),
                ("remote_kind", "TEXT"),
                ("remote_status", "TEXT"),
                ("remote_fail_code", "TEXT"),
                ("remote_error_message", "TEXT"),
                ("submitted_at", "DATETIME"),
                ("finished_at", "DATETIME"),
            ]

            for col_name, col_def in columns:
                if col_name in existing_cols:
                    continue
                try:
                    await session.execute(
                        text(
                            f"ALTER TABLE content_generation_jobs ADD COLUMN {col_name} {col_def}"
                        )
                    )
                    logger.info(f"Added column content_generation_jobs.{col_name}")
                    await session.commit()
                except Exception as exc:
                    logger.error(
                        f"Failed to add {col_name} to content_generation_jobs: {exc}"
                    )
