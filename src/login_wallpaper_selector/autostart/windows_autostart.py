"""Windows HKCU Run autostart adapter."""

from __future__ import annotations
import winreg
from typing import Optional
from .base import BaseAutostartAdapter


class WindowsAutostartAdapter(BaseAutostartAdapter):
    """Manages login startup entry via HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run."""

    REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
    APP_NAME = "LoginWallpaperSelector"

    @property
    def platform_name(self) -> str:
        return "Windows HKCU Run"

    def is_enabled(self) -> bool:
        cmd = self.get_registered_command()
        return bool(cmd)

    def get_registered_command(self) -> Optional[str]:
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.REG_PATH, 0, winreg.KEY_READ)
            val, _ = winreg.QueryValueEx(key, self.APP_NAME)
            winreg.CloseKey(key)
            return str(val)
        except Exception:
            return None

    def enable(self, command: str) -> bool:
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.REG_PATH,
                0,
                winreg.KEY_SET_VALUE | winreg.KEY_READ,
            )
            winreg.SetValueEx(key, self.APP_NAME, 0, winreg.REG_SZ, command)
            winreg.CloseKey(key)
            return True
        except Exception:
            return False

    def disable(self) -> bool:
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                self.REG_PATH,
                0,
                winreg.KEY_SET_VALUE | winreg.KEY_READ,
            )
            try:
                winreg.DeleteValue(key, self.APP_NAME)
            except FileNotFoundError:
                pass
            winreg.CloseKey(key)
            return True
        except Exception:
            return False
