"""Skill auto-loader for dynamic skill discovery."""

from __future__ import annotations

import importlib.util
import os
import stat
import sys
from pathlib import Path

from nanoclaw.core.logger import get_logger

logger = get_logger(__name__)


def _get_current_uid() -> int:
    """Get current user ID, with Windows compatibility."""
    if sys.platform == "win32":
        return 0  # Windows doesn't have UID, return 0 to skip check
    return _get_current_uid()


def _is_safe_skill_file(path: Path) -> bool:
    """
    Check that a skill file is owned by the current user
    and not writable by group/others.
    """
    try:
        st = path.stat()
        # Must be owned by the current user (skip on Windows)
        if sys.platform != "win32" and st.st_uid != _get_current_uid():
            logger.warning(
                f"Skipping skill {path.name}: not owned by current user "
                f"(owner uid={st.st_uid}, current uid={_get_current_uid()})"
            )
            return False
        # Must not be writable by group or others (skip on Windows)
        if sys.platform != "win32" and st.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            logger.warning(
                f"Skipping skill {path.name}: writable by group/others "
                f"(mode={oct(st.st_mode)})"
            )
            return False
        return True
    except OSError as e:
        logger.warning(f"Skipping skill {path.name}: cannot stat: {e}")
        return False


def load_skills_from_directory(skills_dir: str | Path) -> int:
    """
    Load all Python skills from a directory.

    Skills are Python files with @tool decorated functions.
    Files starting with _ are ignored.
    Files not owned by the current user or writable by others are skipped.

    Args:
        skills_dir: Path to skills directory

    Returns:
        Number of skills loaded
    """
    skills_path = Path(skills_dir)
    if not skills_path.exists():
        return 0

    # Check directory permissions (skip on Windows)
    if sys.platform != "win32":
        try:
            dir_stat = skills_path.stat()
            if dir_stat.st_uid != _get_current_uid():
                logger.warning(f"Skills directory not owned by current user: {skills_dir}")
                return 0
            if dir_stat.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
                logger.warning(f"Skills directory writable by others: {skills_dir}")
                return 0
        except OSError:
            return 0

    loaded = 0
    for py_file in skills_path.glob("*.py"):
        if py_file.name.startswith("_"):
            continue

        if not _is_safe_skill_file(py_file):
            continue

        try:
            spec = importlib.util.spec_from_file_location(py_file.stem, py_file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                loaded += 1
                logger.debug(f"Loaded skill: {py_file.name}")
        except Exception as e:
            logger.error(f"Failed to load skill {py_file.name}: {e}")

    return loaded


def get_builtin_skills_path() -> Path:
    """Get path to built-in skills directory."""
    return Path(__file__).parent


def get_user_skills_path() -> Path:
    """Get path to user skills directory."""
    return Path.home() / ".nanoclaw" / "skills"
