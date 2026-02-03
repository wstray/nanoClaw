"""Tool tests for file, memory, shell, and registry."""

from __future__ import annotations

from pathlib import Path

import pytest

from nanoclaw.memory.store import MemoryStore, set_memory_store
from nanoclaw.security.sandbox import (
    FileGuard,
    ShellSandbox,
    set_file_guard,
    set_shell_sandbox,
)
from nanoclaw.tools.files import file_list, file_read, file_write
from nanoclaw.tools.memory_tools import memory_save, memory_search
from nanoclaw.tools.registry import get_tool_registry
from nanoclaw.tools.shell import shell_exec


@pytest.mark.asyncio
async def test_file_tools_roundtrip(tmp_path: Path) -> None:
    """File tools should write, read, and list files."""
    set_file_guard(FileGuard(tmp_path))
    result = await file_write("notes.txt", "hello")
    assert "Written" in result

    content = await file_read("notes.txt")
    assert content == "hello"

    listing = await file_list(".")
    assert "notes.txt" in listing


@pytest.mark.asyncio
async def test_file_read_blocks_escape(tmp_path: Path) -> None:
    """file_read should block path traversal."""
    set_file_guard(FileGuard(tmp_path))
    output = await file_read("../secret.txt")
    assert "ACCESS DENIED" in output


@pytest.mark.asyncio
async def test_memory_tools_save_and_search(tmp_path: Path) -> None:
    """Memory tools should save and search facts."""
    store = MemoryStore(tmp_path / "mem.db")
    set_memory_store(store)

    await memory_save("User likes coffee", category="preference")
    result = await memory_search("coffee")
    assert "User likes coffee" in result


@pytest.mark.asyncio
async def test_shell_exec_blocked(tmp_path: Path) -> None:
    """shell_exec should block dangerous commands."""
    set_shell_sandbox(ShellSandbox(tmp_path))
    output = await shell_exec("rm -rf /")
    assert output.startswith("BLOCKED")


def test_tool_registry_includes_core_tools() -> None:
    """Tool registry should include core tools."""
    registry = get_tool_registry()
    names = set(registry.get_tool_names())
    expected = {
        "file_read",
        "file_write",
        "file_list",
        "shell_exec",
        "web_search",
        "web_fetch",
        "memory_save",
        "memory_search",
        "spawn_task",
    }
    assert expected.issubset(names)
