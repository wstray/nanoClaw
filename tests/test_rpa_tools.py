"""Tests for Robocorp RPA tools."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nanoclaw.tools.rpa_tools import (
    rpa_list,
    rpa_register,
    rpa_run,
    rpa_unregister,
)


@pytest.fixture
def mock_config(tmp_path: Path):
    """Mock config with temporary robots file."""
    robots_file = tmp_path / "robots.json"

    with patch("nanoclaw.tools.rpa_tools.get_config") as mock_get_config:
        config = MagicMock()
        config.tools.robocorp.rcc_path = ""
        config.tools.robocorp.default_timeout = 300
        config.tools.robocorp.robots_file = str(robots_file)
        mock_get_config.return_value = config
        yield robots_file


@pytest.fixture
def sample_robot_dir(tmp_path: Path) -> Path:
    """Create a sample robot directory with robot.yaml."""
    robot_dir = tmp_path / "sample_robot"
    robot_dir.mkdir()
    (robot_dir / "robot.yaml").write_text("tasks:\n  Run:")
    return robot_dir


@pytest.mark.asyncio
async def test_rpa_register_success(mock_config: Path, sample_robot_dir: Path) -> None:
    """rpa_register should register a valid robot."""
    result = await rpa_register("test-bot", str(sample_robot_dir))

    assert "Registered" in result
    assert "test-bot" in result
    assert str(sample_robot_dir) in result

    # Verify registry file
    registry = json.loads(mock_config.read_text())
    assert registry["test-bot"] == str(sample_robot_dir)


@pytest.mark.asyncio
async def test_rpa_register_invalid_path(mock_config: Path, tmp_path: Path) -> None:
    """rpa_register should fail for non-existent path."""
    invalid_path = tmp_path / "does_not_exist"
    result = await rpa_register("test-bot", str(invalid_path))

    assert "ERROR" in result
    assert "not exist" in result.lower()


@pytest.mark.asyncio
async def test_rpa_register_missing_robot_yaml(mock_config: Path, tmp_path: Path) -> None:
    """rpa_register should fail if robot.yaml is missing."""
    empty_dir = tmp_path / "empty_robot"
    empty_dir.mkdir()

    result = await rpa_register("test-bot", str(empty_dir))

    assert "ERROR" in result
    assert "robot.yaml" in result


@pytest.mark.asyncio
async def test_rpa_register_empty_name(mock_config: Path, sample_robot_dir: Path) -> None:
    """rpa_register should fail for empty name."""
    result = await rpa_register("", str(sample_robot_dir))

    assert "ERROR" in result
    assert "cannot be empty" in result.lower()


@pytest.mark.asyncio
async def test_rpa_list_empty(mock_config: Path) -> None:
    """rpa_list should indicate when no robots are registered."""
    result = await rpa_list()

    assert "No robots registered" in result


@pytest.mark.asyncio
async def test_rpa_list_with_robots(mock_config: Path, sample_robot_dir: Path) -> None:
    """rpa_list should show registered robots."""
    # Register a robot first
    await rpa_register("my-bot", str(sample_robot_dir))

    result = await rpa_list()

    assert "my-bot" in result
    assert str(sample_robot_dir) in result
    assert "OK" in result


@pytest.mark.asyncio
async def test_rpa_list_missing_robot(mock_config: Path, tmp_path: Path) -> None:
    """rpa_list should show missing status for deleted robots."""
    # Register a robot, then delete the directory
    robot_dir = tmp_path / "temp_robot"
    robot_dir.mkdir()
    (robot_dir / "robot.yaml").write_text("tasks:")

    await rpa_register("temp-bot", str(robot_dir))

    # Delete the directory and its contents
    import shutil
    shutil.rmtree(robot_dir)

    result = await rpa_list()

    assert "temp-bot" in result
    assert "PATH NOT FOUND" in result or "MISSING" in result


@pytest.mark.asyncio
async def test_rpa_unregister_success(mock_config: Path, sample_robot_dir: Path) -> None:
    """rpa_unregister should remove a registered robot."""
    # Register first
    await rpa_register("delete-me", str(sample_robot_dir))

    # Unregister
    result = await rpa_unregister("delete-me")

    assert "Removed" in result
    assert "delete-me" in result

    # Verify registry is empty
    registry = json.loads(mock_config.read_text())
    assert "delete-me" not in registry


@pytest.mark.asyncio
async def test_rpa_unregister_not_found(mock_config: Path) -> None:
    """rpa_unregister should handle non-existent robot."""
    result = await rpa_unregister("non-existent")

    assert "not registered" in result.lower()


@pytest.mark.asyncio
async def test_rpa_unregister_empty_name(mock_config: Path) -> None:
    """rpa_unregister should fail for empty name."""
    result = await rpa_unregister("")

    assert "ERROR" in result
    assert "cannot be empty" in result.lower()


@pytest.mark.asyncio
async def test_rpa_run_robot_not_found(mock_config: Path) -> None:
    """rpa_run should fail for unregistered robot."""
    result = await rpa_run("unknown-bot")

    assert "ERROR" in result
    assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_rpa_run_rcc_not_found(mock_config: Path, sample_robot_dir: Path) -> None:
    """rpa_run should fail when RCC is not installed."""
    # Register a robot
    await rpa_register("test-bot", str(sample_robot_dir))

    with patch("nanoclaw.tools.rpa_tools.shutil.which") as mock_which:
        mock_which.return_value = None

        result = await rpa_run("test-bot")

        assert "ERROR" in result
        assert "rcc" in result.lower()
        assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_rpa_run_success(mock_config: Path, sample_robot_dir: Path) -> None:
    """rpa_run should execute robot successfully."""
    # Register a robot
    await rpa_register("test-bot", str(sample_robot_dir))

    # Mock subprocess
    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate = AsyncMock(return_value=(
        b"Robot execution successful",
        b""
    ))

    with patch(
        "nanoclaw.tools.rpa_tools.asyncio.create_subprocess_exec",
        return_value=mock_process
    ):
        with patch("nanoclaw.tools.rpa_tools.shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/rcc"

            result = await rpa_run("test-bot")

            assert "test-bot" in result
            assert "Exit code: 0" in result
            assert "Robot execution successful" in result


@pytest.mark.asyncio
async def test_rpa_run_with_task(mock_config: Path, sample_robot_dir: Path) -> None:
    """rpa_run should pass task parameter."""
    # Register a robot
    await rpa_register("test-bot", str(sample_robot_dir))

    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate = AsyncMock(return_value=(b"", b""))

    with patch(
        "nanoclaw.tools.rpa_tools.asyncio.create_subprocess_exec",
        return_value=mock_process
    ) as mock_exec:
        with patch("nanoclaw.tools.rpa_tools.shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/rcc"

            await rpa_run("test-bot", task="specific-task")

            # Verify task was passed
            call_args = mock_exec.call_args[0]
            assert "--task" in call_args
            assert "specific-task" in call_args


@pytest.mark.asyncio
async def test_rpa_run_with_variables(mock_config: Path, sample_robot_dir: Path) -> None:
    """rpa_run should pass variables parameter."""
    # Register a robot
    await rpa_register("test-bot", str(sample_robot_dir))

    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate = AsyncMock(return_value=(b"", b""))

    with patch(
        "nanoclaw.tools.rpa_tools.asyncio.create_subprocess_exec",
        return_value=mock_process
    ) as mock_exec:
        with patch("nanoclaw.tools.rpa_tools.shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/rcc"

            await rpa_run("test-bot", variables='{"url": "https://example.com"}')

            # Verify variables were passed
            call_args = mock_exec.call_args[0]
            assert "--variable" in call_args


@pytest.mark.asyncio
async def test_rpa_run_invalid_variables(mock_config: Path, sample_robot_dir: Path) -> None:
    """rpa_run should fail for invalid JSON variables."""
    # Register a robot
    await rpa_register("test-bot", str(sample_robot_dir))

    with patch("nanoclaw.tools.rpa_tools.shutil.which") as mock_which:
        mock_which.return_value = "/usr/bin/rcc"

        result = await rpa_run("test-bot", variables="not valid json")

        assert "ERROR" in result
        assert "Invalid JSON" in result


@pytest.mark.asyncio
async def test_rpa_run_timeout(mock_config: Path, sample_robot_dir: Path) -> None:
    """rpa_run should handle timeout."""
    # Register a robot
    await rpa_register("test-bot", str(sample_robot_dir))

    mock_process = AsyncMock()
    mock_process.communicate = AsyncMock(
        side_effect=asyncio.TimeoutError()
    )
    mock_process.kill = MagicMock()
    mock_process.wait = AsyncMock()

    with patch(
        "nanoclaw.tools.rpa_tools.asyncio.create_subprocess_exec",
        return_value=mock_process
    ):
        with patch("nanoclaw.tools.rpa_tools.shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/rcc"

            result = await rpa_run("test-bot")

            assert "TIMEOUT" in result


@pytest.mark.asyncio
async def test_rpa_run_non_zero_exit(mock_config: Path, sample_robot_dir: Path) -> None:
    """rpa_run should report non-zero exit code."""
    # Register a robot
    await rpa_register("test-bot", str(sample_robot_dir))

    mock_process = AsyncMock()
    mock_process.returncode = 1
    mock_process.communicate = AsyncMock(return_value=(
        b"",
        b"Error occurred"
    ))

    with patch(
        "nanoclaw.tools.rpa_tools.asyncio.create_subprocess_exec",
        return_value=mock_process
    ):
        with patch("nanoclaw.tools.rpa_tools.shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/rcc"

            result = await rpa_run("test-bot")

            assert "Exit code: 1" in result
            assert "Error occurred" in result


@pytest.mark.asyncio
async def test_rpa_run_output_json_parsing(
    mock_config: Path, sample_robot_dir: Path
) -> None:
    """rpa_run should parse output.json if present."""
    # Create output directory and file
    output_dir = sample_robot_dir / "output"
    output_dir.mkdir()
    output_json = output_dir / "output.json"
    output_data = {"status": "success", "items": 42}
    output_json.write_text(json.dumps(output_data))

    # Register a robot
    await rpa_register("test-bot", str(sample_robot_dir))

    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate = AsyncMock(return_value=(b"", b""))

    with patch(
        "nanoclaw.tools.rpa_tools.asyncio.create_subprocess_exec",
        return_value=mock_process
    ):
        with patch("nanoclaw.tools.rpa_tools.shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/rcc"

            result = await rpa_run("test-bot")

            assert "Results:" in result
            assert '"status": "success"' in result
            assert "42" in result


# -----------------------------------------------------------------------------
# Config Robot Loading Tests
# -----------------------------------------------------------------------------

def test_load_config_robots_success(mock_config: Path, sample_robot_dir: Path) -> None:
    """load_config_robots should register robots from config."""
    with patch("nanoclaw.tools.rpa_tools.get_config") as mock_get_config:
        config = MagicMock()
        config.tools.robocorp.rcc_path = ""
        config.tools.robocorp.default_timeout = 300
        config.tools.robocorp.robots_file = str(mock_config)
        config.tools.robocorp.robots = {
            "config-bot": str(sample_robot_dir)
        }
        mock_get_config.return_value = config

        from nanoclaw.tools.rpa_tools import load_config_robots
        registered = load_config_robots()

        assert "config-bot" in registered

        # Verify registry
        registry = json.loads(mock_config.read_text())
        assert registry["config-bot"] == str(sample_robot_dir)


def test_load_config_robots_already_registered(
    mock_config: Path, sample_robot_dir: Path
) -> None:
    """load_config_robots should skip already registered robots."""
    # Pre-register a robot
    registry = {"existing-bot": str(sample_robot_dir)}
    mock_config.write_text(json.dumps(registry))

    with patch("nanoclaw.tools.rpa_tools.get_config") as mock_get_config:
        config = MagicMock()
        config.tools.robocorp.rcc_path = ""
        config.tools.robocorp.default_timeout = 300
        config.tools.robocorp.robots_file = str(mock_config)
        config.tools.robocorp.robots = {
            "existing-bot": str(sample_robot_dir)  # Same name, should skip
        }
        mock_get_config.return_value = config

        from nanoclaw.tools.rpa_tools import load_config_robots
        registered = load_config_robots()

        # Should be empty since robot already registered
        assert registered == []


def test_load_config_robots_invalid_path(mock_config: Path) -> None:
    """load_config_robots should skip invalid robot paths."""
    with patch("nanoclaw.tools.rpa_tools.get_config") as mock_get_config:
        config = MagicMock()
        config.tools.robocorp.rcc_path = ""
        config.tools.robocorp.default_timeout = 300
        config.tools.robocorp.robots_file = str(mock_config)
        config.tools.robocorp.robots = {
            "invalid-bot": "/nonexistent/path"
        }
        mock_get_config.return_value = config

        from nanoclaw.tools.rpa_tools import load_config_robots
        registered = load_config_robots()

        # Should be empty since path is invalid
        assert registered == []


def test_load_config_robots_empty_config(mock_config: Path) -> None:
    """load_config_robots should handle empty config."""
    with patch("nanoclaw.tools.rpa_tools.get_config") as mock_get_config:
        config = MagicMock()
        config.tools.robocorp.rcc_path = ""
        config.tools.robocorp.default_timeout = 300
        config.tools.robocorp.robots_file = str(mock_config)
        config.tools.robocorp.robots = {}
        mock_get_config.return_value = config

        from nanoclaw.tools.rpa_tools import load_config_robots
        registered = load_config_robots()

        assert registered == []
