"""Autostart package for Login Wallpaper Selector."""
from .base import BaseAutostartAdapter
from .factory import get_autostart_adapter
from .windows_autostart import WindowsAutostartAdapter
from .linux_autostart import LinuxAutostartAdapter
from .macos_autostart import MacAutostartAdapter

__all__ = [
    "BaseAutostartAdapter",
    "get_autostart_adapter",
    "WindowsAutostartAdapter",
    "LinuxAutostartAdapter",
    "MacAutostartAdapter",
]
