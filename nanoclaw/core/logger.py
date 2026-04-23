"""Structured logging for nanoClaw."""

from __future__ import annotations

import logging
import os
import sys
from typing import Optional

from nanoclaw.core.jsonl_logger import JSONLLogger, LogLevel

# Global verbose flag - also check env var at startup
_verbose = os.environ.get("NANOCLAW_VERBOSE", "").lower() in ("1", "true", "yes")


def set_verbose(verbose: bool) -> None:
    """Enable or disable verbose (DEBUG) logging for all nanoclaw loggers."""
    global _verbose
    _verbose = verbose
    level = logging.DEBUG if verbose else logging.INFO

    # Update root nanoclaw logger and its handlers
    root = logging.getLogger("nanoclaw")
    root.setLevel(level)
    for handler in root.handlers:
        handler.setLevel(level)

    # Also update root logger if no handlers on nanoclaw
    if not root.handlers:
        # Ensure nanoclaw logger has a handler
        setup_logger("nanoclaw", level)


class JSONLHandler(logging.Handler):
    """Custom logging handler that forwards to JSONL logger."""

    def __init__(self, jsonl_logger: JSONLLogger):
        super().__init__()
        self.jsonl_logger = jsonl_logger

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to JSONL."""
        try:
            # Import asyncio only when needed to avoid sync/async mixing issues
            import asyncio

            # Get or create event loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # Create async task for logging
            if loop.is_running():
                # If loop is running, create task
                asyncio.create_task(self._async_emit(record))
            else:
                # If loop is not running, run directly
                loop.run_until_complete(self._async_emit(record))

        except Exception:
            # Don't crash the app if logging fails
            self.handleError(record)

    async def _async_emit(self, record: logging.LogRecord) -> None:
        """Async emit method."""
        try:
            # Map logging levels to our LogLevel enum
            level_map = {
                logging.DEBUG: LogLevel.DEBUG,
                logging.INFO: LogLevel.INFO,
                logging.WARNING: LogLevel.WARNING,
                logging.ERROR: LogLevel.ERROR,
                logging.CRITICAL: LogLevel.CRITICAL,
            }
            level = level_map.get(record.levelno, LogLevel.INFO)

            await self.jsonl_logger.log_system(
                level=level,
                component=record.name,
                message=record.getMessage(),
                exception=self.format(record) if record.exc_info else None,
                context={
                    "function": record.funcName,
                    "line": record.lineno,
                    "path": record.pathname,
                },
            )
        except Exception:
            # Silently fail to avoid infinite loops
            pass

    # Update all existing child loggers
    for name in list(logging.Logger.manager.loggerDict.keys()):
        if name.startswith("nanoclaw"):
            child = logging.getLogger(name)
            child.setLevel(level)
            for handler in child.handlers:
                handler.setLevel(level)


def setup_logger(
    name: str = "nanoclaw",
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    jsonl_logger: Optional[JSONLLogger] = None,
) -> logging.Logger:
    """
    Set up a logger with console and optional file output.

    Args:
        name: Logger name
        level: Logging level
        log_file: Optional file path for logging
        jsonl_logger: Optional JSONL logger for structured logging

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Use verbose level if set globally
    if _verbose:
        level = logging.DEBUG

    logger.setLevel(level)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # Format: timestamp - level - message
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # JSONL handler (optional)
    if jsonl_logger and jsonl_logger.config.log_system_logs:
        jsonl_handler = JSONLHandler(jsonl_logger)
        jsonl_handler.setLevel(level)
        logger.addHandler(jsonl_handler)

    return logger


# Global logger instance
logger = setup_logger()


def get_logger(name: str = "nanoclaw") -> logging.Logger:
    """Get a logger instance."""
    child = logging.getLogger(name)
    # Apply verbose level if set globally
    if _verbose:
        child.setLevel(logging.DEBUG)
    return child
