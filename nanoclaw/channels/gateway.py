"""Central message router between channels, agent, and scheduler."""

from __future__ import annotations

import asyncio
import signal
from typing import TYPE_CHECKING, Any, Callable, Optional

from nanoclaw.core.llm import ConnectionPool
from nanoclaw.core.logger import get_logger

if TYPE_CHECKING:
    from nanoclaw.core.config import Config

logger = get_logger(__name__)


class Gateway:
    """Central message router between channels, agent, and scheduler."""

    def __init__(self, config: "Config"):
        """
        Initialize Gateway.

        Args:
            config: Application configuration
        """
        self.config = config
        self.channels: dict[str, Any] = {}
        self.scheduler: Any = None
        self.dashboard: Any = None
        self._agent: Any = None
        self._stop_event: Optional[asyncio.Event] = None

    @property
    def agent(self) -> Any:
        """Lazy-load agent to avoid circular imports."""
        if self._agent is None:
            from nanoclaw.core.agent import get_agent

            self._agent = get_agent()
        return self._agent

    async def start(self) -> None:
        """Start all components."""
        # Set global gateway reference
        set_gateway(self)

        # Debug: verify logger state
        import logging
        root = logging.getLogger("nanoclaw")
        logger.debug(f"Logger state: level={root.level}, handlers={len(root.handlers)}")

        # Log provider and model
        provider, _, _, base_url = self.config.get_active_provider()
        model = self.config.get_default_model()
        if base_url:
            logger.info(f"Provider: {provider} ({base_url})")
        else:
            logger.info(f"Provider: {provider}")
        logger.info(f"Model: {model}")

        # Start Telegram if enabled
        if self.config.channels.telegram.enabled:
            from nanoclaw.channels.telegram import TelegramChannel

            telegram = TelegramChannel(self.config.channels.telegram, self)
            await telegram.start()
            self.channels["telegram"] = telegram
            logger.info("Telegram channel started")

        # Start cron scheduler
        from nanoclaw.cron.scheduler import Scheduler

        self.scheduler = Scheduler(self.config, self)
        await self.scheduler.start()
        logger.info("Cron scheduler started")

        # Start dashboard if enabled
        if self.config.dashboard.enabled:
            from nanoclaw.dashboard.server import Dashboard

            self.dashboard = Dashboard(self.config, self)
            await self.dashboard.start(port=self.config.dashboard.port)

        logger.info("nanoClaw is running!")

        # Keep running until shutdown signal
        self._stop_event = asyncio.Event()

        # Set up signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._handle_signal)
            except NotImplementedError:
                # Windows doesn't support add_signal_handler
                pass

        await self._stop_event.wait()
        await self.stop()

    def _handle_signal(self) -> None:
        """Handle shutdown signal."""
        logger.info("Shutdown signal received...")
        if self._stop_event:
            self._stop_event.set()

    async def handle_incoming(
        self,
        channel_id: str,
        user_id: str,
        message: str,
        confirm_callback: Optional[Callable] = None,
    ) -> str:
        """
        Route incoming message to agent, return response.

        Args:
            channel_id: Channel identifier
            user_id: User identifier
            message: User's message
            confirm_callback: Optional confirmation callback

        Returns:
            Agent response
        """
        session_id = f"{channel_id}:{user_id}"
        logger.debug(f"Gateway handling message for session {session_id}")

        # Set shell confirm callback
        from nanoclaw.tools.shell import set_confirm_callback

        set_confirm_callback(confirm_callback)

        try:
            response = await self.agent.run(
                user_message=message,
                session_id=session_id,
                confirm_callback=confirm_callback,
            )
            return response
        except Exception as e:
            logger.error(f"Agent error: {e}")
            return f"Sorry, something went wrong: {e}"

    async def send_proactive(
        self, text: str, channel: str = "telegram"
    ) -> None:
        """
        Send proactive message via specified channel.

        Args:
            text: Message text
            channel: Target channel name
        """
        if channel in self.channels:
            await self.channels[channel].send_proactive(text)

    async def stop(self) -> None:
        """Graceful shutdown of all components."""
        logger.info("Stopping nanoClaw...")

        # Stop channels
        for name, channel in self.channels.items():
            try:
                await channel.stop()
                logger.info(f"Stopped {name} channel")
            except Exception as e:
                logger.error(f"Error stopping {name}: {e}")

        # Stop scheduler
        if self.scheduler:
            await self.scheduler.stop()
            logger.info("Stopped scheduler")

        # Stop dashboard
        if self.dashboard:
            await self.dashboard.stop()
            logger.info("Stopped dashboard")

        # Close connection pool
        await ConnectionPool.close()

        logger.info("nanoClaw stopped.")


# Global gateway instance
_gateway: Optional[Gateway] = None


def get_gateway() -> Optional[Gateway]:
    """Get the global Gateway instance."""
    return _gateway


def set_gateway(gateway: Gateway) -> None:
    """Set the global Gateway instance."""
    global _gateway
    _gateway = gateway
