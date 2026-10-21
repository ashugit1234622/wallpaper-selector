"""Linux XDG autostart adapter."""

from __future__ import annotations
import os
from pathlib import Path
from typing import Optional
from .base import BaseAutostartAdapter


class LinuxAutostartAdapter(BaseAutostartAdapter):
    """Manages login startup entry via ~/.config/autostart/login-wallpaper-selector.desktop."""

    def __init__(self):
        config_home = os.environ.get("XDG_CONFIG_HOME")
        if config_home:
            self.autostart_dir = Path(config_home) / "autostart"
        else:
            self.autostart_dir = Path.home() / ".config" / "autostart"
        self.desktop_file = self.autostart_dir / "login-wallpaper-selector.desktop"

    @property
    def platform_name(self) -> str:
        return "Linux XDG Autostart"

    def is_enabled(self) -> bool:
        return self.desktop_file.exists()

    def get_registered_command(self) -> Optional[str]:
        if not self.desktop_file.exists():
            return None
        try:
            with open(self.desktop_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("Exec="):
                        return line[5:].strip()
        except Exception:
            pass
        return None

    def enable(self, command: str) -> bool:
        try:
            self.autostart_dir.mkdir(parents=True, exist_ok=True)
            content = f"""[Desktop Entry]
Type=Application
Version=1.0
Name=Login Wallpaper Selector
Comment=Prompts user to select a desktop wallpaper category upon login
Exec={command}
Terminal=false
StartupNotify=false
Categories=Utility;DesktopSettings;
X-GNOME-Autostart-enabled=true
"""
            with open(self.desktop_file, "w", encoding="utf-8") as f:
                f.write(content)
            self.desktop_file.chmod(0o755)
            return True
        except Exception:
            return False

    def disable(self) -> bool:
        try:
            if self.desktop_file.exists():
                self.desktop_file.unlink()
            return True
        except Exception:
            return False
