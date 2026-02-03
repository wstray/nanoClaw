"""Skill auto-loader for dynamic skill discovery."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from nanoclaw.core.logger import get_logger

logger = get_logger(__name__)


def load_skills_from_directory(skills_dir: str | Path) -> int:
    """
    Load all Python skills from a directory.

    Skills are Python files with @tool decorated functions.
    Files starting with _ are ignored.

    Args:
        skills_dir: Path to skills directory

    Returns:
        Number of skills loaded
    """
    skills_path = Path(skills_dir)
    if not skills_path.exists():
        return 0

    loaded = 0
    for py_file in skills_path.glob("*.py"):
        if py_file.name.startswith("_"):
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
