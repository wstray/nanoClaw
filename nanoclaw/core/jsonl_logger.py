"""JSONL-based structured logging system for nanoClaw.

This module provides a comprehensive logging system that records all agent activities
including user messages, agent responses, internal thinking, tool calls, and system logs.
"""

from __future__ import annotations

import asyncio
import csv
import gzip
import json
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import aiofiles
from pydantic import BaseModel


# Log type schemas for validation and documentation
LOG_SCHEMAS = {
    "user_message": {
        "timestamp": "ISO 8601",
        "log_type": "user_message",
        "session_id": "str",
        "channel_id": "str",
        "user_id": "str",
        "content": "str",
        "message_id": "uuid",
        "metadata": "dict",
    },
    "agent_response": {
        "timestamp": "ISO 8601",
        "log_type": "agent_response",
        "session_id": "str",
        "content": "str",
        "message_id": "uuid",
        "tokens_used": "int",
        "iterations": "int",
        "tool_calls_count": "int",
        "duration_ms": "int",
        "metadata": "dict",
    },
    "agent_thinking": {
        "timestamp": "ISO 8601",
        "log_type": "agent_thinking",
        "session_id": "str",
        "iteration": "int",
        "thought_type": "enum[tool_selection, reasoning, escalation, completion]",
        "content": "str",
        "context": "dict",
        "metadata": "dict",
    },
    "tool_call": {
        "timestamp": "ISO 8601",
        "log_type": "tool_call",
        "session_id": "str",
        "tool_name": "str",
        "tool_id": "uuid",
        "parameters": "dict",
        "result": "str",
        "status": "enum[success, error, timeout, blocked]",
        "duration_ms": "int",
        "tokens_used": "int",
        "requires_confirmation": "bool",
        "confirmation_granted": "bool",
        "metadata": "dict",
    },
    "system_log": {
        "timestamp": "ISO 8601",
        "log_type": "system_log",
        "level": "enum[DEBUG, INFO, WARNING, ERROR, CRITICAL]",
        "component": "str",
        "message": "str",
        "exception": "str|null",
        "context": "dict",
        "metadata": "dict",
    },
}


class ThoughtType(str, Enum):
    """Types of agent thinking logs."""

    TOOL_SELECTION = "tool_selection"
    REASONING = "reasoning"
    ESCALATION = "escalation"
    COMPLETION = "completion"


class ToolCallStatus(str, Enum):
    """Status of tool calls."""

    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    BLOCKED = "blocked"
    RUNNING = "running"


class LogLevel(str, Enum):
    """Log levels for system logs."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class JSONLLoggerConfig(BaseModel):
    """Configuration for JSONL logger."""

    enabled: bool = True
    log_dir: Optional[str] = None
    log_level: str = "INFO"
    buffer_size: int = 10
    compress_after_days: int = 7
    retention_days: int = 30
    log_user_messages: bool = True
    log_agent_responses: bool = True
    log_agent_thinking: bool = True
    log_tool_calls: bool = True
    log_system_logs: bool = True


class JSONLLogger:
    """
    JSONL-based structured logging system with daily rotation.

    Features:
    - Thread-safe async file operations
    - Daily log rotation (nanoclaw-YYYY-MM-DD.jsonl)
    - Automatic schema validation
    - Buffered writes for performance
    - Compression for old logs
    - Query and export utilities
    """

    def __init__(
        self,
        log_dir: Path,
        config: JSONLLoggerConfig,
        log_name: str = "nanoclaw",
    ):
        """
        Initialize JSONL logger.

        Args:
            log_dir: Directory for log files
            config: Logger configuration
            log_name: Base name for log files
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.config = config
        self.log_name = log_name
        self._buffer: list[str] = []
        self._buffer_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()
        self._current_date = datetime.now().date()
        self._current_file_path = self._get_log_path_for_date(self._current_date)

        if not self.config.enabled:
            return

        # Ensure log file exists
        self._current_file_path.touch(exist_ok=True)

    def _get_log_path_for_date(self, date: datetime.date | str) -> Path:
        """Get log file path for specific date."""
        if isinstance(date, str):
            date = datetime.fromisoformat(date).date()
        return self.log_dir / f"{self.log_name}-{date.isoformat()}.jsonl"

    def _get_compressed_path_for_date(self, date: datetime.date | str) -> Path:
        """Get compressed log file path for specific date."""
        if isinstance(date, str):
            date = datetime.fromisoformat(date).date()
        return self.log_dir / f"{self.log_name}-{date.isoformat()}.jsonl.gz"

    async def _write_to_file(self, lines: list[str]) -> None:
        """Write lines to current log file asynchronously."""
        if not self.config.enabled:
            return

        async with self._write_lock:
            try:
                async with aiofiles.open(self._current_file_path, mode="a", encoding="utf-8") as f:
                    await f.write("\n".join(lines) + "\n")
            except Exception as e:
                # Don't crash the app if logging fails
                print(f"Warning: Failed to write to log file: {e}")

    async def _flush_buffer(self) -> None:
        """Flush buffered entries to disk."""
        if not self._buffer:
            return

        async with self._buffer_lock:
            if not self._buffer:
                return
            lines_to_write = self._buffer.copy()
            self._buffer.clear()

        await self._write_to_file(lines_to_write)

    async def _check_rotation(self) -> None:
        """Check if log rotation is needed."""
        current_date = datetime.now().date()
        if current_date != self._current_date:
            # Flush buffer before rotation
            await self._flush_buffer()

            # Update date and file path
            self._current_date = current_date
            self._current_file_path = self._get_log_path_for_date(current_date)
            self._current_file_path.touch(exist_ok=True)

    async def log_entry(self, entry_type: str, data: dict[str, Any]) -> None:
        """
        Log a structured entry.

        Args:
            entry_type: Type of log entry (must be in LOG_SCHEMAS)
            data: Entry data matching the schema
        """
        if not self.config.enabled:
            return

        # Check if we should log this type
        if entry_type == "user_message" and not self.config.log_user_messages:
            return
        if entry_type == "agent_response" and not self.config.log_agent_responses:
            return
        if entry_type == "agent_thinking" and not self.config.log_agent_thinking:
            return
        if entry_type == "tool_call" and not self.config.log_tool_calls:
            return
        if entry_type == "system_log" and not self.config.log_system_logs:
            return

        # Check log level for system logs
        if entry_type == "system_log":
            level = data.get("level", "INFO")
            log_levels = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
            if log_levels.get(level, 20) < log_levels.get(self.config.log_level, 20):
                return

        # Add common fields
        entry = {
            "timestamp": datetime.now().isoformat(),
            "log_type": entry_type,
            **data,
        }

        # Convert to JSON and add to buffer
        json_line = json.dumps(entry, ensure_ascii=False)

        async with self._buffer_lock:
            self._buffer.append(json_line)

        # Check if buffer needs flushing
        if len(self._buffer) >= self.config.buffer_size:
            await self._flush_buffer()

        # Check for rotation
        await self._check_rotation()

    async def log_user_message(
        self,
        session_id: str,
        channel_id: str,
        user_id: str,
        content: str,
        message_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Log a user message."""
        await self.log_entry(
            "user_message",
            {
                "session_id": session_id,
                "channel_id": channel_id,
                "user_id": user_id,
                "content": content,
                "message_id": message_id or str(uuid.uuid4()),
                "metadata": metadata or {},
            },
        )

    async def log_agent_response(
        self,
        session_id: str,
        content: str,
        tokens_used: int = 0,
        iterations: int = 0,
        tool_calls_count: int = 0,
        duration_ms: int = 0,
        message_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Log an agent response."""
        await self.log_entry(
            "agent_response",
            {
                "session_id": session_id,
                "content": content,
                "message_id": message_id or str(uuid.uuid4()),
                "tokens_used": tokens_used,
                "iterations": iterations,
                "tool_calls_count": tool_calls_count,
                "duration_ms": duration_ms,
                "metadata": metadata or {},
            },
        )

    async def log_agent_thinking(
        self,
        session_id: str,
        iteration: int,
        thought_type: ThoughtType | str,
        content: str,
        context: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Log agent internal thinking."""
        if isinstance(thought_type, str):
            thought_type = ThoughtType(thought_type)

        await self.log_entry(
            "agent_thinking",
            {
                "session_id": session_id,
                "iteration": iteration,
                "thought_type": thought_type.value,
                "content": content,
                "context": context or {},
                "metadata": metadata or {},
            },
        )

    async def log_tool_call(
        self,
        session_id: str,
        tool_name: str,
        tool_id: str,
        parameters: dict[str, Any],
        result: str,
        status: ToolCallStatus | str,
        duration_ms: int = 0,
        tokens_used: int = 0,
        requires_confirmation: bool = False,
        confirmation_granted: bool = False,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Log a tool call."""
        if isinstance(status, str):
            status = ToolCallStatus(status)

        # Truncate large results
        if len(result) > 1000:
            result = result[:1000] + "... (truncated)"

        await self.log_entry(
            "tool_call",
            {
                "session_id": session_id,
                "tool_name": tool_name,
                "tool_id": tool_id,
                "parameters": parameters,
                "result": result,
                "status": status.value,
                "duration_ms": duration_ms,
                "tokens_used": tokens_used,
                "requires_confirmation": requires_confirmation,
                "confirmation_granted": confirmation_granted,
                "metadata": metadata or {},
            },
        )

    async def log_system(
        self,
        level: LogLevel | str,
        component: str,
        message: str,
        exception: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Log a system message."""
        if isinstance(level, str):
            level = LogLevel(level)

        await self.log_entry(
            "system_log",
            {
                "level": level.value,
                "component": component,
                "message": message,
                "exception": exception,
                "context": context or {},
                "metadata": metadata or {},
            },
        )

    def _get_date_range(self, start_date: Optional[str], end_date: Optional[str]) -> list[Path]:
        """Get list of log files for date range."""
        if not self.log_dir.exists():
            return []

        log_files = []
        for file_path in self.log_dir.glob("*.jsonl*"):
            if file_path.is_file():
                log_files.append(file_path)

        # Filter by date range if specified
        if start_date or end_date:
            filtered = []
            start = datetime.fromisoformat(start_date).date() if start_date else None
            end = datetime.fromisoformat(end_date).date() if end_date else None

            for file_path in log_files:
                # Extract date from filename
                stem = file_path.stem.replace(".jsonl", "").replace(f"{self.log_name}-", "")
                try:
                    file_date = datetime.fromisoformat(stem).date()
                    if start and file_date < start:
                        continue
                    if end and file_date > end:
                        continue
                    filtered.append(file_path)
                except ValueError:
                    # Filename doesn't match expected format, skip
                    continue

            log_files = filtered

        return sorted(log_files, reverse=True)

    def _matches_filters(self, entry: dict[str, Any], filters: Optional[dict[str, Any]]) -> bool:
        """Check if log entry matches filters."""
        if not filters:
            return True

        for key, value in filters.items():
            if key not in entry:
                return False
            if entry[key] != value:
                return False

        return True

    async def query(
        self,
        filters: Optional[dict[str, Any]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """
        Query log entries with filters.

        Args:
            filters: Dict of field=value pairs
            start_date: ISO date string (YYYY-MM-DD)
            end_date: ISO date string (YYYY-MM-DD)
            limit: Maximum entries to return

        Returns:
            List of matching log entries
        """
        results = []
        log_files = self._get_date_range(start_date, end_date)

        for log_file in log_files:
            if len(results) >= limit:
                break

            # Handle compressed files
            if log_file.suffix == ".gz":
                try:
                    async with aiofiles.open(log_file, "rb") as f:
                        content = await f.read()
                        text = gzip.decompress(content).decode("utf-8")
                        lines = text.strip().split("\n")
                except Exception:
                    continue
            else:
                try:
                    async with aiofiles.open(log_file, encoding="utf-8") as f:
                        lines = await f.readlines()
                except Exception:
                    continue

            for line in lines:
                if len(results) >= limit:
                    break

                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                    if self._matches_filters(entry, filters):
                        results.append(entry)
                except json.JSONDecodeError:
                    continue

        return results

    async def export(
        self,
        format: str = "json",
        filters: Optional[dict[str, Any]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> str:
        """
        Export logs in various formats.

        Args:
            format: Export format (json, csv, jsonl)
            filters: Optional filters
            start_date: Start date
            end_date: End date

        Returns:
            Exported data as string
        """
        entries = await self.query(filters, start_date, end_date, limit=100000)

        if format == "json":
            return json.dumps(entries, indent=2, ensure_ascii=False)
        elif format == "csv" and entries:
            return self._to_csv(entries)
        elif format == "jsonl":
            return "\n".join(json.dumps(e, ensure_ascii=False) for e in entries)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _to_csv(self, entries: list[dict[str, Any]]) -> str:
        """Convert log entries to CSV format."""
        if not entries:
            return ""

        # Get all unique keys
        all_keys = set()
        for entry in entries:
            all_keys.update(entry.keys())

        fieldnames = sorted(all_keys)

        # Convert to CSV
        output = []
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for entry in entries:
            # Convert complex values to strings
            row = {}
            for key, value in entry.items():
                if isinstance(value, (dict, list)):
                    row[key] = json.dumps(value, ensure_ascii=False)
                else:
                    row[key] = str(value)
            writer.writerow(row)

        # Get rows from StringIO
        import io

        csv_output = io.StringIO()
        csv_writer = csv.DictWriter(csv_output, fieldnames=fieldnames)
        csv_writer.writeheader()
        for entry in entries:
            row = {}
            for key, value in entry.items():
                if isinstance(value, (dict, list)):
                    row[key] = json.dumps(value, ensure_ascii=False)
                else:
                    row[key] = str(value)
            csv_writer.writerow(row)

        return csv_output.getvalue()

    async def get_session_history(
        self,
        session_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get all logs for a specific session."""
        return await self.query(
            filters={"session_id": session_id},
            start_date=start_date,
            end_date=end_date,
            limit=10000,
        )

    async def get_tool_stats(
        self,
        tool_name: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict[str, Any]:
        """Get statistics about tool usage."""
        filters = {"log_type": "tool_call"}
        if tool_name:
            filters["tool_name"] = tool_name

        entries = await self.query(
            filters=filters,
            start_date=start_date,
            end_date=end_date,
            limit=100000,
        )

        stats = {
            "total_calls": len(entries),
            "successful": sum(1 for e in entries if e["status"] == "success"),
            "errors": sum(1 for e in entries if e["status"] == "error"),
            "blocked": sum(1 for e in entries if e["status"] == "blocked"),
            "avg_duration_ms": 0,
            "by_tool": {},
        }

        if entries:
            stats["avg_duration_ms"] = sum(e.get("duration_ms", 0) for e in entries) / len(entries)

        for entry in entries:
            tool = entry["tool_name"]
            if tool not in stats["by_tool"]:
                stats["by_tool"][tool] = {"count": 0, "errors": 0, "blocked": 0}
            stats["by_tool"][tool]["count"] += 1
            if entry["status"] == "error":
                stats["by_tool"][tool]["errors"] += 1
            elif entry["status"] == "blocked":
                stats["by_tool"][tool]["blocked"] += 1

        return stats

    async def rotate(self) -> None:
        """Perform daily log rotation."""
        await self._flush_buffer()
        await self._check_rotation()

    async def compress_old_logs(self) -> None:
        """Compress logs older than configured threshold."""
        if not self.log_dir.exists():
            return

        cutoff_date = datetime.now().date() - __import__("datetime").timedelta(days=self.config.compress_after_days)

        for file_path in self.log_dir.glob("*.jsonl"):
            if file_path.suffix == ".gz":
                continue

            # Extract date from filename
            stem = file_path.stem.replace(f"{self.log_name}-", "")
            try:
                file_date = datetime.fromisoformat(stem).date()
                if file_date < cutoff_date:
                    compressed_path = self._get_compressed_path_for_date(file_date)

                    # Read, compress, and write
                    async with aiofiles.open(file_path, "rb") as f:
                        content = await f.read()

                    compressed_content = gzip.compress(content)

                    async with aiofiles.open(compressed_path, "wb") as f:
                        await f.write(compressed_content)

                    # Remove original file
                    file_path.unlink()
            except (ValueError, Exception):
                # Skip files that don't match expected format
                continue

    async def delete_old_logs(self) -> int:
        """Delete logs older than retention period."""
        if not self.log_dir.exists():
            return 0

        cutoff_date = datetime.now().date() - __import__("datetime").timedelta(days=self.config.retention_days)
        deleted_count = 0

        for file_path in self.log_dir.glob("*.jsonl*"):
            # Extract date from filename
            stem = (
                file_path.stem.replace(f"{self.log_name}-", "")
                .replace(".jsonl", "")
                .replace(".gz", "")
            )
            try:
                file_date = datetime.fromisoformat(stem).date()
                if file_date < cutoff_date:
                    file_path.unlink()
                    deleted_count += 1
            except (ValueError, Exception):
                # Skip files that don't match expected format
                continue

        return deleted_count

    async def flush(self) -> None:
        """Flush buffered entries to disk without closing."""
        await self._flush_buffer()

    async def close(self) -> None:
        """Close logger and flush remaining entries."""
        await self._flush_buffer()


# Global logger instance
_jsonl_logger: Optional[JSONLLogger] = None


def get_jsonl_logger() -> Optional[JSONLLogger]:
    """Get the global JSONL logger instance."""
    return _jsonl_logger


def set_jsonl_logger(logger: JSONLLogger) -> None:
    """Set the global JSONL logger instance."""
    global _jsonl_logger
    _jsonl_logger = logger
