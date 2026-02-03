"""File operation tools (sandboxed to workspace)."""

from __future__ import annotations

from nanoclaw.security.sandbox import SecurityError, get_file_guard
from nanoclaw.tools.registry import tool


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

    try:
        content = safe_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Error reading file: {e}"

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

    try:
        # Create parent directories if needed
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        safe_path.write_text(content, encoding="utf-8")
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

    entries = []
    try:
        for item in sorted(safe_path.iterdir()):
            if item.is_dir():
                entries.append(f"[DIR]  {item.name}/")
            else:
                size = item.stat().st_size
                entries.append(f"[FILE] {item.name} ({size}B)")
    except Exception as e:
        return f"Error listing directory: {e}"

    return "\n".join(entries) if entries else "(empty directory)"
