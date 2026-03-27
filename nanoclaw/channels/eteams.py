"""Eteams IM channel using WebSocket."""

from __future__ import annotations

import asyncio
import logging
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

        # Silence noisy logging
        logging.getLogger("websockets").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

    async def start(self) -> None:
        """Start eteams channel - login and connect WebSocket."""
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
            logger.error(f"Failed to import eteams_client: {e}")
            logger.error("Make sure eteams_client.py is in the project root")
            return

        # Create login config - password field contains the encrypted password
        login_config = LoginConfig(
            base_url=self.config.base_url,
            phone=self.config.phone,
            password=self.config.encrypted_password,  # Pass encrypted as password
            device_type=self.config.device_type,
        )

        # Create client
        self.client = EteamsClient(login_config)

        # Register message callback
        self.client.register_message_callback(self._handle_message_callback)

        # Start client (login + connect WebSocket)
        try:
            await self.client.start(enable_im=True)
        except Exception as e:
            logger.error(f"Eteams client start failed: {e}")
            return

        self._running = True
        logger.info("Eteams channel started")

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
        content = message_data.get("content", "")

        if not content:
            return

        if content.startswith("Assistant:"):
            return    

        logger.info(f"Eteams message from sender_uid={sender_uid}, content={content[:50]}...")
        logger.info(f"Allow list: {self.config.allow_from}")

        # Check whitelist
        if sender_uid not in self.config.allow_from:
            logger.warning(f"Unauthorized user: {sender_uid}")
            await self._send_message(sender_uid, "Not authorized.")
            return

        # Check if this is a confirmation response
        if await self._check_confirmation_response(sender_uid, content):
            return

        # Route to agent via gateway
        response = await self.gateway.handle_incoming(
            channel_id="eteams",
            user_id=sender_uid,
            message=content,
            confirm_callback=lambda q: self._ask_confirmation(sender_uid, q),
        )

        # Send response
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

        # Send question with instructions
        await self._send_message(
            user_id,
            f"{question}\n\nReply 'yes' to confirm, 'no' to cancel.\n"
            f"(ID: {confirm_id[-8:]})",
        )

        try:
            result = await asyncio.wait_for(future, timeout=300)
            return result
        except asyncio.TimeoutError:
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
            return

        # Split long messages
        MAX_LEN = 2000
        messages = []
        for i in range(0, len(text), MAX_LEN):
            messages.append(text[i : i + MAX_LEN])

        for msg in messages:
            try:
                await self.client.send_text_message(
                    to_uid=user_id,
                    content=msg,
                )
            except Exception as e:
                logger.error(f"Failed to send message: {e}")

            # Small delay between messages
            await asyncio.sleep(0.1)

    async def send_proactive(self, text: str) -> None:
        """Send proactive message (from cron or background task)."""
        for user_id in self.config.allow_from:
            await self._send_message(user_id, text)

    async def stop(self) -> None:
        """Graceful shutdown."""
        self._running = False

        if self._client_task:
            self._client_task.cancel()

        if self.client:
            try:
                await self.client.stop()
            except Exception as e:
                logger.error(f"Error stopping eteams client: {e}")

        logger.info("Eteams channel stopped")
