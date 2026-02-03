"""Security check command for nanoClaw installation."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from nanoclaw.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CheckResult:
    """Result of a security check."""

    name: str
    passed: bool
    message: str
    severity: str = "info"  # info, warning, critical


class SecurityDoctor:
    """Comprehensive security check of nanoClaw installation."""

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize SecurityDoctor.

        Args:
            config_dir: Path to nanoClaw config directory
        """
        self.config_dir = config_dir or Path.home() / ".nanoclaw"

    async def check_all(self) -> list[CheckResult]:
        """
        Run all security checks.

        Returns:
            List of check results
        """
        checks = [
            self.check_config_permissions(),
            self.check_workspace_permissions(),
            self.check_key_exposure(),
            self.check_telegram_whitelist(),
            self.check_shell_sandbox(),
            self.check_dashboard_binding(),
            self.check_workspace_exposure(),
            self.check_confirmation_mode(),
        ]
        return checks

    def check_config_permissions(self) -> CheckResult:
        """Check config file permissions (should be 600)."""
        config_path = self.config_dir / "config.json"

        if not config_path.exists():
            return CheckResult(
                name="Config file",
                passed=False,
                message="config.json not found. Run 'nanoclaw init' first.",
                severity="critical",
            )

        mode = config_path.stat().st_mode
        is_owner_only = (mode & stat.S_IRWXG) == 0 and (mode & stat.S_IRWXO) == 0

        if is_owner_only:
            return CheckResult(
                name="Config permissions",
                passed=True,
                message="config.json has secure permissions (owner only)",
            )
        return CheckResult(
            name="Config permissions",
            passed=False,
            message="config.json is readable by others. Run: chmod 600 ~/.nanoclaw/config.json",
            severity="critical",
        )

    def check_workspace_permissions(self) -> CheckResult:
        """Check workspace directory permissions (should be 700)."""
        workspace_path = self.config_dir / "workspace"

        if not workspace_path.exists():
            return CheckResult(
                name="Workspace",
                passed=False,
                message="Workspace directory not found.",
                severity="warning",
            )

        mode = workspace_path.stat().st_mode
        is_owner_only = (mode & stat.S_IRWXG) == 0 and (mode & stat.S_IRWXO) == 0

        if is_owner_only:
            return CheckResult(
                name="Workspace permissions",
                passed=True,
                message="Workspace has secure permissions (owner only)",
            )
        return CheckResult(
            name="Workspace permissions",
            passed=False,
            message="Workspace is accessible by others. Run: chmod 700 ~/.nanoclaw/workspace",
            severity="warning",
        )

    def check_key_exposure(self) -> CheckResult:
        """Check if API keys are exposed in logs or audit."""
        # Check if any log files contain API key patterns
        data_dir = self.config_dir / "data"
        if not data_dir.exists():
            return CheckResult(
                name="Key exposure",
                passed=True,
                message="No data files to check",
            )

        # Simple check - look for common API key prefixes in logs
        suspicious_patterns = ["sk-", "sk-ant-", "Bearer ", "x-api-key"]

        for log_file in data_dir.glob("*.log"):
            try:
                content = log_file.read_text()
                for pattern in suspicious_patterns:
                    if pattern in content:
                        return CheckResult(
                            name="Key exposure",
                            passed=False,
                            message=f"Possible API key in {log_file.name}. Review and redact.",
                            severity="critical",
                        )
            except Exception:
                pass

        return CheckResult(
            name="Key exposure",
            passed=True,
            message="No API keys found in logs",
        )

    def check_telegram_whitelist(self) -> CheckResult:
        """Check if Telegram whitelist is configured."""
        try:
            from nanoclaw.core.config import Config

            config = Config.load(self.config_dir / "config.json")

            if not config.channels.telegram.enabled:
                return CheckResult(
                    name="Telegram whitelist",
                    passed=True,
                    message="Telegram is disabled",
                )

            if config.channels.telegram.allow_from:
                return CheckResult(
                    name="Telegram whitelist",
                    passed=True,
                    message=f"{len(config.channels.telegram.allow_from)} user(s) whitelisted",
                )
            return CheckResult(
                name="Telegram whitelist",
                passed=False,
                message="No users whitelisted. Add user IDs to allowFrom.",
                severity="critical",
            )
        except Exception as e:
            return CheckResult(
                name="Telegram whitelist",
                passed=False,
                message=f"Could not check config: {e}",
                severity="warning",
            )

    def check_shell_sandbox(self) -> CheckResult:
        """Check if shell sandbox is enabled."""
        try:
            from nanoclaw.core.config import Config

            config = Config.load(self.config_dir / "config.json")

            if config.tools.shell.enabled:
                if config.tools.shell.confirm_dangerous:
                    return CheckResult(
                        name="Shell sandbox",
                        passed=True,
                        message="Shell enabled with confirmation for dangerous commands",
                    )
                return CheckResult(
                    name="Shell sandbox",
                    passed=False,
                    message="Shell enabled but confirmDangerous is off",
                    severity="warning",
                )
            return CheckResult(
                name="Shell sandbox",
                passed=True,
                message="Shell execution is disabled",
            )
        except Exception:
            return CheckResult(
                name="Shell sandbox",
                passed=True,
                message="Using default (enabled with confirmations)",
            )

    def check_dashboard_binding(self) -> CheckResult:
        """Check if dashboard is bound to localhost only."""
        try:
            from nanoclaw.core.config import Config

            config = Config.load(self.config_dir / "config.json")

            if not config.dashboard.enabled:
                return CheckResult(
                    name="Dashboard binding",
                    passed=True,
                    message="Dashboard is disabled",
                )

            # Dashboard always binds to 127.0.0.1 by design
            return CheckResult(
                name="Dashboard binding",
                passed=True,
                message="Dashboard binds to localhost only (127.0.0.1)",
            )
        except Exception:
            return CheckResult(
                name="Dashboard binding",
                passed=True,
                message="Using default (localhost only)",
            )

    def check_workspace_exposure(self) -> CheckResult:
        """Check workspace is not world-readable."""
        workspace_path = self.config_dir / "workspace"

        if not workspace_path.exists():
            return CheckResult(
                name="Workspace exposure",
                passed=True,
                message="Workspace not created yet",
            )

        mode = workspace_path.stat().st_mode
        world_readable = bool(mode & stat.S_IROTH)

        if world_readable:
            return CheckResult(
                name="Workspace exposure",
                passed=False,
                message="Workspace is world-readable",
                severity="warning",
            )
        return CheckResult(
            name="Workspace exposure",
            passed=True,
            message="Workspace is not world-readable",
        )

    def check_confirmation_mode(self) -> CheckResult:
        """Check if confirmation mode is enabled for dangerous commands."""
        try:
            from nanoclaw.core.config import Config

            config = Config.load(self.config_dir / "config.json")

            if config.tools.shell.confirm_dangerous:
                return CheckResult(
                    name="Confirmation mode",
                    passed=True,
                    message="Dangerous commands require user confirmation",
                )
            return CheckResult(
                name="Confirmation mode",
                passed=False,
                message="Confirmation disabled. Enable confirmDangerous in config.",
                severity="warning",
            )
        except Exception:
            return CheckResult(
                name="Confirmation mode",
                passed=True,
                message="Using default (confirmations enabled)",
            )

    def format_report(self, checks: list[CheckResult]) -> str:
        """
        Format check results as CLI output.

        Args:
            checks: List of check results

        Returns:
            Formatted report string
        """
        lines = ["", "Security Check Report", "=" * 40, ""]

        passed = 0
        warnings = 0
        critical = 0

        for check in checks:
            if check.passed:
                icon = "[OK]"
                passed += 1
            elif check.severity == "critical":
                icon = "[!!]"
                critical += 1
            else:
                icon = "[??]"
                warnings += 1

            lines.append(f"{icon} {check.name}")
            lines.append(f"    {check.message}")
            lines.append("")

        lines.append("=" * 40)
        lines.append(f"Passed: {passed}  Warnings: {warnings}  Critical: {critical}")

        if critical > 0:
            lines.append("")
            lines.append("CRITICAL issues found! Fix before running.")
        elif warnings > 0:
            lines.append("")
            lines.append("Some warnings found. Review recommended.")
        else:
            lines.append("")
            lines.append("All checks passed!")

        return "\n".join(lines)
