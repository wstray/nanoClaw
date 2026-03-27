"""File operation tools (sandboxed to workspace)."""

from __future__ import annotations

import os
import sys

from nanoclaw.security.sandbox import SecurityError, get_file_guard
from nanoclaw.tools.registry import tool

# Platform detection for Windows compatibility
_IS_WINDOWS = sys.platform.startswith("win")


def _open_file_for_read(path: os.PathLike | str) -> int:
    """Open file for reading with platform-appropriate security.

    On Unix: Use O_NOFOLLOW to atomically reject symlinks.
    On Windows: Symlink checking is done by FileGuard before opening.
    """
    if _IS_WINDOWS:
        return os.open(str(path), os.O_RDONLY)
    else:
        return os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW)


def _open_file_for_write(path: os.PathLike | str) -> int:
    """Open file for writing with platform-appropriate security.

    On Unix: Use O_NOFOLLOW to atomically reject symlinks.
    On Windows: Symlink checking is done by FileGuard before opening.
    Note: mode parameter is ignored on Windows (uses ACLs instead).
    """
    if _IS_WINDOWS:
        return os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    else:
        return os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o644)


@tool(
    name="file_read",
    description="Read the contents of a file from the workspace.",
    parameters={
        "path": {
            "type": "string",
            "description": (
                "File path relative to workspace "
                "(e.g., 'report.md', 'data/results.csv')"
            ),
        }
    },
)
async def file_read(path: str) -> str:
    """Read file from workspace."""
    guard = get_file_guard()

    try:
        safe_path = guard.validate_path(path)
    except SecurityError as e:
        return str(e)

    if not safe_path.exists():
        return f"File not found: {path}"

    if not safe_path.is_file():
        return f"Not a file: {path}"

    if not guard.is_safe_to_read(safe_path):
        return f"ACCESS DENIED: cannot read sensitive file: {path}"

    # Use platform-appropriate file opening (symlink check already done by is_safe_to_read)
    try:
        fd = _open_file_for_read(safe_path)
    except OSError as e:
        if not _IS_WINDOWS and e.errno == 40:  # ELOOP — is a symlink (Unix only)
            return f"ACCESS DENIED: symlink points outside workspace: {path}"
        return f"Error reading file: {e}"

    try:
        # Read 16KB to guarantee 4000+ chars even with 4-byte UTF-8
        raw = os.read(fd, 16384)
        content = raw.decode("utf-8", errors="replace")
    except Exception as e:
        return f"Error reading file: {e}"
    finally:
        os.close(fd)

    if len(content) > 4000:
        content = content[:4000] + "\n...[truncated]"

    return content


@tool(
    name="file_write",
    description="Create or overwrite a file in the workspace.",
    parameters={
        "path": {
            "type": "string",
            "description": "File path relative to workspace",
        },
        "content": {
            "type": "string",
            "description": "Content to write",
        },
    },
)
async def file_write(path: str, content: str) -> str:
    """Write file to workspace."""
    guard = get_file_guard()

    try:
        safe_path = guard.validate_path(path)
    except SecurityError as e:
        return str(e)

    # Block writes to sensitive paths
    if not guard.is_safe_to_write(safe_path):
        return f"ACCESS DENIED: cannot write to sensitive path: {path}"

    try:
        # Create parent directories if needed
        safe_path.parent.mkdir(parents=True, exist_ok=True)

        # Use platform-appropriate file opening (symlink check already done by is_safe_to_write)
        fd = _open_file_for_write(safe_path)
        try:
            os.write(fd, content.encode("utf-8"))
        finally:
            os.close(fd)
    except OSError as e:
        if not _IS_WINDOWS and e.errno == 40:  # ELOOP — is a symlink (Unix only)
            return f"ACCESS DENIED: symlink at write target: {path}"
        return f"Error writing file: {e}"
    except Exception as e:
        return f"Error writing file: {e}"

    size = safe_path.stat().st_size
    return f"Written {size} bytes to {path}"


@tool(
    name="file_list",
    description="List files and directories in the workspace.",
    parameters={
        "path": {
            "type": "string",
            "description": "Directory path relative to workspace. Use '.' for root.",
        }
    },
    required=[],  # path is optional, defaults to '.'
)
async def file_list(path: str = ".") -> str:
    """List directory contents in workspace."""
    guard = get_file_guard()

    try:
        safe_path = guard.validate_path(path)
    except SecurityError as e:
        return str(e)

    if not safe_path.exists():
        return f"Directory not found: {path}"

    if not safe_path.is_dir():
        return f"Not a directory: {path}"

    # Dotfile prefixes to hide from listing
    HIDDEN_PREFIXES = (".env", ".git", ".ssh", ".aws", ".kube", ".docker", ".gnupg")

    entries = []
    try:
        for item in sorted(safe_path.iterdir()):
            name_lower = item.name.lower()
            if any(name_lower.startswith(prefix) for prefix in HIDDEN_PREFIXES):
                continue
            if item.is_dir():
                entries.append(f"[DIR]  {item.name}/")
            else:
                size = item.stat().st_size
                entries.append(f"[FILE] {item.name} ({size}B)")
    except Exception as e:
        return f"Error listing directory: {e}"

    return "\n".join(entries) if entries else "(empty directory)"
