"""Persistent cron scheduler with SQLite storage."""

from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from nanoclaw.core.logger import get_logger

if TYPE_CHECKING:
    from nanoclaw.channels.gateway import Gateway
    from nanoclaw.core.config import Config

logger = get_logger(__name__)


class Scheduler:
    """Persistent cron jobs. Stored in SQLite, survives restart."""

    def __init__(self, config: "Config", gateway: "Gateway"):
        """
        Initialize Scheduler.

        Args:
            config: Application configuration
            gateway: Gateway for message routing
        """
        self.config = config
        self.gateway = gateway
        self.running = False
        self._task: Optional[asyncio.Task] = None
        self._db_path = self._get_db_path()

    def _get_db_path(self) -> Path:
        """Get database path."""
        from nanoclaw.core.config import get_data_path

        return get_data_path() / "nanoclaw.db"

    async def start(self) -> None:
        """Start checking jobs every 60 seconds."""
        self.running = True
        self._task = asyncio.create_task(self._loop())
        logger.debug("Scheduler started")

    async def _loop(self) -> None:
        """Main scheduler loop."""
        while self.running:
            try:
                await self._check_and_run()
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
            await asyncio.sleep(60)

    async def _check_and_run(self) -> None:
        """Check all jobs, run those that are due."""
        jobs = await self._get_enabled_jobs()
        now = datetime.utcnow()

        for job in jobs:
            should_run = False

            if job["cron_expr"]:
                try:
                    from croniter import croniter  # type: ignore[import-untyped]

                    last_run = (
                        datetime.fromisoformat(job["last_run"])
                        if job["last_run"]
                        else now - timedelta(days=1)
                    )
                    cron = croniter(job["cron_expr"], last_run)
                    next_run = cron.get_next(datetime)
                    should_run = next_run <= now
                except ImportError:
                    logger.warning("croniter not installed, skipping cron expression jobs")
                except Exception as e:
                    logger.error(f"Cron parse error for job {job['id']}: {e}")

            elif job["interval_seconds"]:
                if job["last_run"]:
                    last = datetime.fromisoformat(job["last_run"])
                    should_run = (now - last).total_seconds() >= job["interval_seconds"]
                else:
                    should_run = True

            if should_run:
                asyncio.create_task(self._execute_job(job))
                await self._update_last_run(job["id"])

    async def _execute_job(self, job: dict) -> None:
        """Run a cron job: send message to agent, forward response to user."""
        try:
            # Sanitize cron message through PromptGuard before sending to agent
            from nanoclaw.security.prompt_guard import get_prompt_guard

            guard = get_prompt_guard()
            message = job["message"]
            detected, matched = guard.check_injection(message)
            if detected:
                logger.warning(
                    f"Cron job '{job['name']}' message contains injection pattern: {matched}"
                )
                return  # Drop the job silently

            response = await self.gateway.handle_incoming(
                channel_id="cron",
                user_id="system",
                message=message,
            )
            await self.gateway.send_proactive(
                f"**{job['name']}**\n\n{response}",
                channel=job.get("channel", "telegram"),
            )
        except Exception as e:
            logger.error(f"Cron job '{job['name']}' failed: {e}")

    async def _get_enabled_jobs(self) -> list[dict]:
        """Get all enabled jobs."""

        def _query() -> list[dict]:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM cron_jobs WHERE enabled = 1"
            )
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]

        return await asyncio.to_thread(_query)

    async def _update_last_run(self, job_id: int) -> None:
        """Update job's last_run timestamp."""

        def _update() -> None:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "UPDATE cron_jobs SET last_run = datetime('now') WHERE id = ?",
                (job_id,),
            )
            conn.commit()
            conn.close()

        await asyncio.to_thread(_update)

    async def add_job(
        self,
        name: str,
        message: str,
        cron_expr: Optional[str] = None,
        interval_seconds: Optional[int] = None,
        channel: str = "telegram",
    ) -> int:
        """
        Add a new cron job.

        Args:
            name: Job name
            message: Message to send to agent
            cron_expr: Cron expression (e.g., '0 9 * * *')
            interval_seconds: Interval in seconds (alternative to cron)
            channel: Target channel

        Returns:
            Job ID
        """

        def _insert() -> int:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.execute(
                """
                INSERT INTO cron_jobs (name, message, cron_expr, interval_seconds, channel)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name, message, cron_expr, interval_seconds, channel),
            )
            conn.commit()
            job_id = cursor.lastrowid
            conn.close()
            return job_id or 0

        return await asyncio.to_thread(_insert)

    async def remove_job(self, job_id: int) -> None:
        """Remove a cron job."""

        def _delete() -> None:
            conn = sqlite3.connect(self._db_path)
            conn.execute("DELETE FROM cron_jobs WHERE id = ?", (job_id,))
            conn.commit()
            conn.close()

        await asyncio.to_thread(_delete)

    async def list_jobs(self) -> list[dict]:
        """List all cron jobs."""

        def _query() -> list[dict]:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM cron_jobs ORDER BY id")
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]

        return await asyncio.to_thread(_query)

    async def toggle_job(self, job_id: int, enabled: bool) -> None:
        """Enable or disable a job."""

        def _update() -> None:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "UPDATE cron_jobs SET enabled = ? WHERE id = ?",
                (1 if enabled else 0, job_id),
            )
            conn.commit()
            conn.close()

        await asyncio.to_thread(_update)

    async def stop(self) -> None:
        """Stop the scheduler."""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


# Global scheduler instance
_scheduler: Optional[Scheduler] = None


def get_scheduler() -> Scheduler:
    """Get the global Scheduler instance."""
    global _scheduler
    if _scheduler is None:
        from nanoclaw.channels.gateway import get_gateway
        from nanoclaw.core.config import get_config

        config = get_config()
        gateway = get_gateway()
        # Create a minimal scheduler without gateway for CLI use
        _scheduler = Scheduler(config, gateway)  # type: ignore
    return _scheduler


def set_scheduler(scheduler: Scheduler) -> None:
    """Set the global Scheduler instance."""
    global _scheduler
    _scheduler = scheduler
