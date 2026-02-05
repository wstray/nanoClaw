"""Lightweight admin dashboard with aiohttp."""

from __future__ import annotations

import secrets
import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import aiohttp.web

from nanoclaw.core.logger import get_logger

if TYPE_CHECKING:
    from nanoclaw.channels.gateway import Gateway
    from nanoclaw.core.config import Config

logger = get_logger(__name__)


class Dashboard:
    """
    Lightweight admin dashboard.
    Single HTML page served by aiohttp.
    Localhost only by default.
    """

    def __init__(self, config: "Config", gateway: "Gateway"):
        """
        Initialize Dashboard.

        Args:
            config: Application configuration
            gateway: Gateway instance
        """
        self.config = config
        self.gateway = gateway
        self._password: Optional[str] = config.dashboard.password
        self.app = aiohttp.web.Application(
            client_max_size=1024 * 1024,  # 1 MB
            middlewares=[self._auth_middleware],
        )
        self.runner: Optional[aiohttp.web.AppRunner] = None
        self._start_time = time.time()
        self._setup_routes()

    @aiohttp.web.middleware
    async def _auth_middleware(
        self, request: aiohttp.web.Request, handler
    ) -> aiohttp.web.StreamResponse:
        """Bearer token auth middleware for /api/* endpoints."""
        if self._password and request.path.startswith("/api/"):
            auth_header = request.headers.get("Authorization", "")
            expected = f"Bearer {self._password}"
            if not secrets.compare_digest(auth_header, expected):
                return aiohttp.web.json_response(
                    {"error": "Unauthorized"}, status=401
                )
        return await handler(request)

    def _setup_routes(self) -> None:
        """Set up HTTP routes."""
        self.app.router.add_get("/", self._serve_html)
        self.app.router.add_get("/api/status", self._api_status)
        self.app.router.add_get("/api/memory", self._api_memory)
        self.app.router.add_get("/api/audit", self._api_audit)
        self.app.router.add_get("/api/cron", self._api_cron_list)
        self.app.router.add_post("/api/cron", self._api_cron_add)
        self.app.router.add_delete("/api/cron/{id}", self._api_cron_remove)
        self.app.router.add_get("/api/skills", self._api_skills)

    async def start(self, port: int = 18790) -> None:
        """
        Start dashboard server.

        Args:
            port: Port to listen on
        """
        self.runner = aiohttp.web.AppRunner(self.app)
        await self.runner.setup()

        # LOCALHOST ONLY - not accessible from outside
        site = aiohttp.web.TCPSite(self.runner, "127.0.0.1", port)
        await site.start()

        logger.info(f"Dashboard: http://localhost:{port}")
        if self._password:
            masked = self._password[:4] + "****" if len(self._password) > 4 else "****"
            logger.info(f"Dashboard auth enabled (token: {masked})")
        else:
            logger.warning("Dashboard has no password set — API is unauthenticated")

    async def _serve_html(
        self, request: aiohttp.web.Request
    ) -> aiohttp.web.Response:
        """Serve the single-page dashboard HTML."""
        html_path = Path(__file__).parent / "index.html"
        if html_path.exists():
            return aiohttp.web.FileResponse(html_path)  # type: ignore[return-value]
        return aiohttp.web.Response(
            text="Dashboard HTML not found", status=404
        )

    async def _api_status(
        self, request: aiohttp.web.Request
    ) -> aiohttp.web.Response:
        """Return current status as JSON."""
        from nanoclaw.memory.store import get_memory_store
        from nanoclaw.security.audit import get_audit_log

        try:
            memory = get_memory_store()
            stats = await memory.get_stats()
        except Exception:
            stats = {}

        try:
            audit = get_audit_log()
            today = await audit.get_stats_today()
        except Exception:
            today = {}

        uptime = int(time.time() - self._start_time)
        hours, remainder = divmod(uptime, 3600)
        minutes, seconds = divmod(remainder, 60)

        channels_status = {}
        for name in self.gateway.channels:
            channels_status[name] = {"status": "connected"}

        return aiohttp.web.json_response(
            {
                "status": "online",
                "uptime": f"{hours}h {minutes}m {seconds}s",
                "channels": channels_status,
                "model": self.config.get_default_model(),
                "stats": stats,
                "today": today,
            }
        )

    async def _api_memory(
        self, request: aiohttp.web.Request
    ) -> aiohttp.web.Response:
        """Return all memories."""
        from nanoclaw.memory.store import get_memory_store

        memory = get_memory_store()
        memories = await memory.get_all_memories()
        return aiohttp.web.json_response(memories)

    async def _api_audit(
        self, request: aiohttp.web.Request
    ) -> aiohttp.web.Response:
        """Return recent audit log entries."""
        from nanoclaw.security.audit import get_audit_log

        try:
            limit = int(request.query.get("limit", "50"))
        except (ValueError, TypeError):
            return aiohttp.web.json_response(
                {"error": "Invalid limit parameter"}, status=400
            )
        limit = max(1, min(limit, 500))

        audit = get_audit_log()
        entries = await audit.get_recent(limit=limit)
        return aiohttp.web.json_response(entries)

    async def _api_cron_list(
        self, request: aiohttp.web.Request
    ) -> aiohttp.web.Response:
        """Return all cron jobs."""
        from nanoclaw.cron.scheduler import get_scheduler

        scheduler = get_scheduler()
        jobs = await scheduler.list_jobs()
        return aiohttp.web.json_response(jobs)

    async def _api_cron_add(
        self, request: aiohttp.web.Request
    ) -> aiohttp.web.Response:
        """Add a new cron job."""
        from nanoclaw.cron.scheduler import get_scheduler

        try:
            data = await request.json()
        except Exception:
            return aiohttp.web.json_response(
                {"error": "Invalid JSON"}, status=400
            )

        name = data.get("name")
        message = data.get("message")
        cron_expr = data.get("cron_expr")
        interval = data.get("interval_seconds")

        if not name or not message:
            return aiohttp.web.json_response(
                {"error": "name and message required"}, status=400
            )

        scheduler = get_scheduler()
        job_id = await scheduler.add_job(
            name=name,
            message=message,
            cron_expr=cron_expr,
            interval_seconds=interval,
        )

        return aiohttp.web.json_response({"id": job_id, "name": name})

    async def _api_cron_remove(
        self, request: aiohttp.web.Request
    ) -> aiohttp.web.Response:
        """Remove a cron job."""
        from nanoclaw.cron.scheduler import get_scheduler

        try:
            job_id = int(request.match_info["id"])
        except (ValueError, TypeError):
            return aiohttp.web.json_response(
                {"error": "Invalid job ID"}, status=400
            )
        scheduler = get_scheduler()
        await scheduler.remove_job(job_id)
        return aiohttp.web.json_response({"removed": job_id})

    async def _api_skills(
        self, request: aiohttp.web.Request
    ) -> aiohttp.web.Response:
        """Return list of available skills/tools."""
        from nanoclaw.tools.registry import get_tool_registry

        registry = get_tool_registry()
        tools = []
        for name, info in registry.tools.items():
            tools.append(
                {
                    "name": name,
                    "description": info.description,
                }
            )
        return aiohttp.web.json_response(tools)

    async def stop(self) -> None:
        """Stop dashboard server."""
        if self.runner:
            await self.runner.cleanup()
