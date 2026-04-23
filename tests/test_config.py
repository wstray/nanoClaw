"""Configuration tests for shell environment variables."""

from pathlib import Path

import pytest

from nanoclaw.core.config import ShellConfig, Config


def test_shell_config_defaults() -> None:
    """ShellConfig should have sensible defaults."""
    config = ShellConfig()
    assert config.enabled is True
    assert config.timeout == 30
    assert config.confirm_dangerous is True
    assert config.inherit_env is False
    assert config.env_vars == {}


def test_shell_config_with_env_vars() -> None:
    """ShellConfig should load environment variables from JSON."""
    data = {
        "enabled": True,
        "timeout": 30,
        "confirmDangerous": True,
        "inheritEnv": False,
        "envVars": {
            "PATH": "D:\\tools",
            "CUSTOM_VAR": "value",
        },
    }
    config = ShellConfig(**data)
    assert config.inherit_env is False
    assert config.env_vars["PATH"] == "D:\\tools"
    assert config.env_vars["CUSTOM_VAR"] == "value"


def test_shell_config_env_vars_alias() -> None:
    """ShellConfig should support camelCase alias."""
    config = ShellConfig(envVars={"TEST": "value"})
    assert config.env_vars == {"TEST": "value"}


def test_shell_config_inherit_env_alias() -> None:
    """ShellConfig should support inheritEnv alias."""
    config = ShellConfig(inheritEnv=True)
    assert config.inherit_env is True
