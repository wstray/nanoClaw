"""Eteams IM channel using WebSocket."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

from nanoclaw.core.logger import get_logger

if TYPE_CHECKING:
    from nanoclaw.channels.gateway import Gateway
    from nanoclaw.core.config import EteamsConfig

logger = get_logger(__name__)


class EteamsChannel:
    """
    Eteams IM channel using WebSocket.
    Receives messages from eteams platform and routes them to the agent.
    """

    def __init__(self, config: "EteamsConfig", gateway: "Gateway"):
        """
        Initialize EteamsChannel.

        Args:
            config: Eteams configuration
            gateway: Gateway for message routing
        """
        self.config = config
        self.gateway = gateway
        self.client: Any = None
        self._running = False
        self._client_task: Optional[asyncio.Task] = None
        self._pending_confirmations: dict[str, asyncio.Future] = {}

        # Setup file logging
        self._setup_file_logger()

        # Silence noisy logging
        logging.getLogger("websockets").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

    def _setup_file_logger(self) -> None:
        """Setup file logger for EteamsChannel."""
        # Create logs directory
        log_dir = Path.cwd() / "logs"
        log_dir.mkdir(exist_ok=True)

        # Create log file with date
        log_file = log_dir / f"eteams_{datetime.now().strftime('%Y%m%d')}.log"

        # Add file handler to the channel-specific logger
        channel_logger = logging.getLogger(f"{__name__}.EteamsChannel")
        channel_logger.setLevel(logging.INFO)

        # Avoid duplicate handlers
        if not any(h for h in channel_logger.handlers if isinstance(h, logging.FileHandler)):
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.INFO)

            # Detailed format for file logging
            formatter = logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler.setFormatter(formatter)
            channel_logger.addHandler(file_handler)

        self._file_logger = channel_logger

    def _log_to_file(self, level: str, message: str) -> None:
        """
        Log message to file.

        Args:
            level: Log level (INFO, WARNING, ERROR, DEBUG)
            message: Log message
        """
        log_func = getattr(self._file_logger, level.lower(), self._file_logger.info)
        log_func(message)

    async def start(self) -> None:
        """Start eteams channel - login and connect WebSocket."""
        self._log_to_file("INFO", "EteamsChannel starting...")

        try:
            # Import eteams client
            import sys
            from pathlib import Path

            # Add project root to path for importing eteams_client
            project_root = Path(__file__).parent.parent.parent
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))

            from eteams_client import EteamsClient, LoginConfig
        except ImportError as e:
            error_msg = f"Failed to import eteams_client: {e}"
            logger.error(error_msg)
            logger.error("Make sure eteams_client.py is in the project root")
            self._log_to_file("ERROR", error_msg)
            return

        # Create login config - password field contains the encrypted password
        login_config = LoginConfig(
            base_url=self.config.base_url,
            phone=self.config.phone,
            password=self.config.encrypted_password,  # Pass encrypted as password
            device_type=self.config.device_type,
        )

        self._log_to_file("INFO", f"Login config created: base_url={self.config.base_url}, phone={self.config.phone}")

        # Create client
        self.client = EteamsClient(login_config)

        # Register message callback
        self.client.register_message_callback(self._handle_message_callback)

        # Start client (login + connect WebSocket)
        try:
            await self.client.start(enable_im=True)
            self._log_to_file("INFO", "Eteams client started successfully")
        except Exception as e:
            error_msg = f"Eteams client start failed: {e}"
            logger.error(error_msg)
            self._log_to_file("ERROR", error_msg)
            return

        self._running = True
        logger.info("Eteams channel started")
        self._log_to_file("INFO", "EteamsChannel is now running")

    async def _handle_message_callback(self, message_data: dict[str, Any]) -> None:
        """
        Handle incoming IM message via callback.

        Message data format:
        {
            'msg_id': str,
            'msg_type': str,
            'sender_name': str,
            'sender_uid': str,
            'sender_cid': str,
            'content': str,
            'raw_data': dict
        }
        """
        sender_uid = message_data.get("sender_uid", "")
        sender_name = message_data.get("sender_name", "")
        content = message_data.get("content", "")

        if not content:
            return

        if content.startswith("Assistant:"):
            return

        logger.info(f"Eteams message from sender_uid={sender_uid}, content={content[:50]}...")
        logger.info(f"Allow list: {self.config.allow_from}")

        # Log incoming message
        self._log_to_file("INFO", f"Received message from {sender_name} ({sender_uid}): {content[:100]}")

        # Check whitelist
        if sender_uid not in self.config.allow_from:
            warning_msg = f"Unauthorized user attempted access: {sender_uid}"
            logger.warning(f"Unauthorized user: {sender_uid}")
            self._log_to_file("WARNING", warning_msg)
            await self._send_message(sender_uid, "Not authorized.")
            return

        # Check if this is a confirmation response
        if await self._check_confirmation_response(sender_uid, content):
            self._log_to_file("INFO", f"Confirmation response from {sender_uid}: {content}")
            return

        # Route to agent via gateway
        self._log_to_file("INFO", f"Routing message to gateway for processing")
        response = await self.gateway.handle_incoming(
            channel_id="eteams",
            user_id=sender_uid,
            message=content,
            confirm_callback=lambda q: self._ask_confirmation(sender_uid, q),
        )

        # Send response
        self._log_to_file("INFO", f"Sending response to {sender_uid}: {response[:100]}")
        await self._send_message(sender_uid, response)

    async def _ask_confirmation(self, user_id: str, question: str) -> bool:
        """
        Send confirmation question to user and wait for response.

        User replies "yes"/"y" to confirm, "no"/"n" to cancel.
        """
        confirm_id = f"{user_id}:{asyncio.get_event_loop().time()}"

        # Store the confirmation request
        future: asyncio.Future[bool] = asyncio.get_event_loop().create_future()
        self._pending_confirmations[confirm_id] = future

        self._log_to_file("INFO", f"Ask confirmation from {user_id}: {question[:50]}...")

        # Send question with instructions
        await self._send_message(
            user_id,
            f"{question}\n\nReply 'yes' to confirm, 'no' to cancel.\n"
            f"(ID: {confirm_id[-8:]})",
        )

        try:
            result = await asyncio.wait_for(future, timeout=300)
            result_str = "CONFIRMED" if result else "CANCELLED"
            self._log_to_file("INFO", f"Confirmation {confirm_id[-8:]}: {result_str}")
            return result
        except asyncio.TimeoutError:
            self._log_to_file("WARNING", f"Confirmation {confirm_id[-8:]} timed out")
            return False
        finally:
            self._pending_confirmations.pop(confirm_id, None)

    async def _check_confirmation_response(self, user_id: str, message: str) -> bool:
        """Check if message is a confirmation response."""
        for confirm_id, future in list(self._pending_confirmations.items()):
            if confirm_id.startswith(user_id):
                msg_lower = message.strip().lower()
                if msg_lower in ("yes", "y", "确认"):
                    future.set_result(True)
                    return True
                elif msg_lower in ("no", "n", "取消", "cancel"):
                    future.set_result(False)
                    return True
        return False

    async def _send_message(self, user_id: str, text: str) -> None:
        """Send message to user via eteams client."""
        if not self.client or not self.client.im_ws:
            self._log_to_file("WARNING", f"Cannot send message: client not initialized")
            return

        # Split long messages
        MAX_LEN = 2000
        messages = []
        for i in range(0, len(text), MAX_LEN):
            messages.append(text[i : i + MAX_LEN])

        self._log_to_file("INFO", f"Sending {len(messages)} message(s) to {user_id}")

        for idx, msg in enumerate(messages, 1):
            try:
                await self.client.send_text_message(
                    to_uid=user_id,
                    content=msg,
                )
                self._log_to_file("DEBUG", f"Message part {idx}/{len(messages)} sent successfully")
            except Exception as e:
                error_msg = f"Failed to send message part {idx}/{len(messages)}: {e}"
                logger.error(error_msg)
                self._log_to_file("ERROR", error_msg)

            # Small delay between messages
            await asyncio.sleep(0.1)

    async def send_proactive(self, text: str) -> None:
        """Send proactive message (from cron or background task)."""
        self._log_to_file("INFO", f"Sending proactive message to {len(self.config.allow_from)} user(s): {text[:100]}")
        for user_id in self.config.allow_from:
            await self._send_message(user_id, text)

    async def stop(self) -> None:
        """Graceful shutdown."""
        self._log_to_file("INFO", "EteamsChannel stopping...")

        self._running = False

        if self._client_task:
            self._log_to_file("INFO", "Cancelling client task")
            self._client_task.cancel()

        if self.client:
            try:
                await self.client.stop()
                self._log_to_file("INFO", "Eteams client stopped successfully")
            except Exception as e:
                error_msg = f"Error stopping eteams client: {e}"
                logger.error(error_msg)
                self._log_to_file("ERROR", error_msg)

        logger.info("Eteams channel stopped")
        self._log_to_file("INFO", "EteamsChannel stopped")
