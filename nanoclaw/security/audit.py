"""Audit logging for all agent actions."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import sqlite3
import uuid
from pathlib import Path
from typing import Optional

from nanoclaw.core.logger import get_logger

logger = get_logger(__name__)


def _get_hmac_key() -> bytes:
    """
    Get or create a persistent HMAC key for audit log integrity.

    The key is stored in the config directory alongside the database.
    """
    from nanoclaw.core.config import get_data_path

    key_path = get_data_path() / ".audit_hmac_key"
    if key_path.exists():
        return key_path.read_bytes()
    key = uuid.uuid4().bytes + uuid.uuid4().bytes  # 32 bytes
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(key)
    try:
        key_path.chmod(0o600)
    except OSError:
        pass
    return key


class AuditLog:
    """Immutable log of every agent action with HMAC integrity."""

    def __init__(self, db_path: str | Path):
        """
        Initialize AuditLog.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._hmac_key = _get_hmac_key()
        self._init_db()

    def _init_db(self) -> None:
        """Create audit log table if not exists."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL DEFAULT (datetime('now')),
                session_id TEXT,
                action_type TEXT NOT NULL,
                tool_name TEXT,
                input_summary TEXT,
                output_summary TEXT,
                status TEXT NOT NULL DEFAULT 'success',
                tokens_used INTEGER DEFAULT 0,
                execution_ms INTEGER DEFAULT 0,
                integrity_hash TEXT
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)"
        )
        # Add integrity_hash column to existing databases
        try:
            conn.execute("ALTER TABLE audit_log ADD COLUMN integrity_hash TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        conn.commit()
        conn.close()

    def _compute_hmac(
        self,
        timestamp: str,
        session_id: str,
        action_type: str,
        tool_name: str,
        input_summary: str,
        output_summary: str,
        status: str,
        tokens: int,
        ms: int,
    ) -> str:
        """Compute HMAC-SHA256 over an audit row's content."""
        message = (
            f"{timestamp}|{session_id}|{action_type}|{tool_name}|"
            f"{input_summary}|{output_summary}|{status}|{tokens}|{ms}"
        )
        return hmac.new(
            self._hmac_key, message.encode(), hashlib.sha256
        ).hexdigest()

    async def log(
        self,
        action_type: str,
        tool_name: Optional[str] = None,
        input_summary: str = "",
        output_summary: str = "",
        status: str = "success",
        tokens: int = 0,
        ms: int = 0,
        session_id: Optional[str] = None,
    ) -> None:
        """
        Log an action to the audit log.

        Args:
            action_type: Type of action (tool_call, response, blocked, etc.)
            tool_name: Name of tool if applicable
            input_summary: Truncated input (max 500 chars)
            output_summary: Truncated output (max 500 chars)
            status: success, error, blocked, denied, timeout
            tokens: Tokens used
            ms: Execution time in milliseconds
            session_id: Session identifier
        """
        # Truncate summaries
        input_summary = input_summary[:500] if input_summary else ""
        output_summary = output_summary[:500] if output_summary else ""

        def _insert() -> None:
            conn = sqlite3.connect(self.db_path)
            # Get the timestamp that will be used
            cursor = conn.execute("SELECT datetime('now')")
            timestamp = cursor.fetchone()[0]

            integrity = self._compute_hmac(
                timestamp,
                session_id or "",
                action_type,
                tool_name or "",
                input_summary,
                output_summary,
                status,
                tokens,
                ms,
            )

            conn.execute(
                """
                INSERT INTO audit_log
                (timestamp, session_id, action_type, tool_name, input_summary,
                 output_summary, status, tokens_used, execution_ms, integrity_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    timestamp,
                    session_id,
                    action_type,
                    tool_name,
                    input_summary,
                    output_summary,
                    status,
                    tokens,
                    ms,
                    integrity,
                ),
            )
            conn.commit()
            conn.close()

        await asyncio.to_thread(_insert)

    async def get_recent(self, limit: int = 50) -> list[dict]:
        """
        Get recent audit log entries.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of log entry dictionaries
        """

        def _query() -> list[dict]:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM audit_log
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]

        return await asyncio.to_thread(_query)

    async def get_stats_today(self) -> dict:
        """
        Get today's statistics.

        Returns:
            Dictionary with today's stats
        """

        def _query() -> dict:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute(
                """
                SELECT
                    COUNT(*) as total_actions,
                    COUNT(CASE WHEN action_type = 'response' THEN 1 END) as messages,
                    COUNT(CASE WHEN action_type = 'tool_call' THEN 1 END) as tool_calls,
                    COUNT(CASE WHEN status = 'error' THEN 1 END) as errors,
                    COUNT(CASE WHEN status = 'blocked' THEN 1 END) as blocked,
                    SUM(tokens_used) as total_tokens
                FROM audit_log
                WHERE date(timestamp) = date('now')
                """
            )
            row = cursor.fetchone()
            conn.close()
            return {
                "total_actions": row[0] or 0,
                "messages": row[1] or 0,
                "tool_calls": row[2] or 0,
                "errors": row[3] or 0,
                "blocked": row[4] or 0,
                "total_tokens": row[5] or 0,
            }

        return await asyncio.to_thread(_query)

    async def verify_integrity(self) -> tuple[int, int]:
        """
        Verify HMAC integrity of all audit log entries.

        Returns:
            (valid_count, tampered_count) tuple
        """

        def _verify() -> tuple[int, int]:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM audit_log ORDER BY id")
            valid = 0
            tampered = 0
            for row in cursor:
                row_dict = dict(row)
                stored_hash = row_dict.get("integrity_hash")
                if not stored_hash:
                    # Legacy entry without hash — skip
                    continue
                expected = self._compute_hmac(
                    row_dict["timestamp"],
                    row_dict.get("session_id") or "",
                    row_dict["action_type"],
                    row_dict.get("tool_name") or "",
                    row_dict.get("input_summary") or "",
                    row_dict.get("output_summary") or "",
                    row_dict["status"],
                    row_dict.get("tokens_used") or 0,
                    row_dict.get("execution_ms") or 0,
                )
                if hmac.compare_digest(stored_hash, expected):
                    valid += 1
                else:
                    tampered += 1
                    logger.warning(f"Tampered audit entry id={row_dict['id']}")
            conn.close()
            return valid, tampered

        return await asyncio.to_thread(_verify)

    async def export_json(self, since: Optional[str] = None) -> str:
        """
        Export audit log as JSON.

        Args:
            since: Optional ISO timestamp to filter from

        Returns:
            JSON string of audit entries
        """
        import json

        def _query() -> str:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            if since:
                cursor = conn.execute(
                    "SELECT * FROM audit_log WHERE timestamp >= ? ORDER BY timestamp",
                    (since,),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM audit_log ORDER BY timestamp"
                )
            rows = cursor.fetchall()
            conn.close()
            return json.dumps([dict(row) for row in rows], indent=2)

        return await asyncio.to_thread(_query)


# Global instance
_audit_log: Optional[AuditLog] = None


def get_audit_log() -> AuditLog:
    """Get the global AuditLog instance."""
    global _audit_log
    if _audit_log is None:
        from nanoclaw.core.config import get_data_path

        _audit_log = AuditLog(get_data_path() / "nanoclaw.db")
    return _audit_log


def set_audit_log(audit: AuditLog) -> None:
    """Set the global AuditLog instance."""
    global _audit_log
    _audit_log = audit
