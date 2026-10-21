"""macOS LaunchAgent autostart adapter."""

from __future__ import annotations
import plistlib
from pathlib import Path
from typing import Optional
from .base import BaseAutostartAdapter


class MacAutostartAdapter(BaseAutostartAdapter):
    """Manages login startup entry via ~/Library/LaunchAgents/com.user.login-wallpaper-selector.plist."""

    LABEL = "com.user.login-wallpaper-selector"

    def __init__(self):
        self.launch_agents_dir = Path.home() / "Library" / "LaunchAgents"
        self.plist_file = self.launch_agents_dir / f"{self.LABEL}.plist"

    @property
    def platform_name(self) -> str:
        return "macOS LaunchAgent"

    def is_enabled(self) -> bool:
        return self.plist_file.exists()

    def get_registered_command(self) -> Optional[str]:
        if not self.plist_file.exists():
            return None
        try:
            with open(self.plist_file, "rb") as f:
                data = plistlib.load(f)
                args = data.get("ProgramArguments", [])
                return " ".join(args)
        except Exception:
            return None

    def enable(self, command: str) -> bool:
        try:
            self.launch_agents_dir.mkdir(parents=True, exist_ok=True)
            # Split command arguments safely
            import shlex
            args = shlex.split(command)

            data = {
                "Label": self.LABEL,
                "ProgramArguments": args,
                "RunAtLoad": True,
                "LimitLoadToSessionType": "Aqua",
                "ProcessType": "Interactive",
            }

            with open(self.plist_file, "wb") as f:
                plistlib.dump(data, f)
            return True
        except Exception:
            return False

    def disable(self) -> bool:
        try:
            if self.plist_file.exists():
                self.plist_file.unlink()
            return True
        except Exception:
            return False
