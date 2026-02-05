"""Background task spawning tool."""

from __future__ import annotations

import asyncio
import time

from nanoclaw.core.logger import get_logger
from nanoclaw.tools.registry import tool

logger = get_logger(__name__)

# Concurrency limit for background tasks
_MAX_BACKGROUND_TASKS = 3
_active_background_tasks = 0
_bg_lock = asyncio.Lock()


@tool(
    name="spawn_task",
    description=(
        "Start a long-running task in the background. "
        "Use for research, analysis, or any task taking more than 30 seconds. "
        "The result will be sent to the user when complete."
    ),
    parameters={
        "task_description": {
            "type": "string",
            "description": "Detailed description of what to accomplish",
        }
    },
)
async def spawn_task(task_description: str) -> str:
    """Spawn a background sub-agent. Returns immediately."""
    global _active_background_tasks

    async with _bg_lock:
        if _active_background_tasks >= _MAX_BACKGROUND_TASKS:
            return (
                f"DENIED: maximum concurrent background tasks ({_MAX_BACKGROUND_TASKS}) "
                f"reached. Wait for existing tasks to finish."
            )
        _active_background_tasks += 1

    async def background_work() -> None:
        """Execute the background task."""
        global _active_background_tasks
        try:
            # Import here to avoid circular imports
            from nanoclaw.core.agent import get_agent
            from nanoclaw.channels.gateway import get_gateway

            agent = get_agent()
            gateway = get_gateway()

            session_id = f"bg_{int(time.time())}"
            result = await agent.run(task_description, session_id)

            if gateway:
                await gateway.send_proactive(
                    f"Background task complete:\n\n{result}"
                )
        except Exception as e:
            logger.error(f"Background task failed: {e}")
            try:
                from nanoclaw.channels.gateway import get_gateway

                gateway = get_gateway()
                if gateway:
                    await gateway.send_proactive(f"Background task failed: {e}")
            except Exception:
                pass
        finally:
            async with _bg_lock:
                _active_background_tasks -= 1

    asyncio.create_task(background_work())
    return "Task started in background. I'll message you when it's done."
