"""Autostart adapter factory to return platform-specific startup manager."""

from __future__ import annotations
import sys
from .base import BaseAutostartAdapter
from .windows_autostart import WindowsAutostartAdapter
from .linux_autostart import LinuxAutostartAdapter
from .macos_autostart import MacAutostartAdapter


def get_autostart_adapter() -> BaseAutostartAdapter:
    """Return the appropriate autostart adapter for the current operating system."""
    if sys.platform == "win32":
        return WindowsAutostartAdapter()
    elif sys.platform == "darwin":
        return MacAutostartAdapter()
    return LinuxAutostartAdapter()
