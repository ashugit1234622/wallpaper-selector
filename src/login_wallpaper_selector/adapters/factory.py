"""Wallpaper adapter factory to auto-detect and instantiate the platform adapter."""

from __future__ import annotations
import os
import sys
from .base import BaseWallpaperAdapter
from .windows import WindowsWallpaperAdapter
from .gnome import GnomeWallpaperAdapter
from .kde import KdePlasmaWallpaperAdapter
from .macos import MacWallpaperAdapter


def get_wallpaper_adapter() -> BaseWallpaperAdapter:
    """Return the appropriate wallpaper adapter for the current operating system."""
    if sys.platform == "win32":
        return WindowsWallpaperAdapter()
    elif sys.platform == "darwin":
        return MacWallpaperAdapter()
    elif sys.platform.startswith("linux"):
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").upper()
        if "KDE" in desktop or "PLASMA" in desktop:
            return KdePlasmaWallpaperAdapter()
        else:
            # Default to GNOME (works on GNOME, Cinnamon, Unity, etc.)
            return GnomeWallpaperAdapter()
    
    # Fallback to Windows if on win32 else Gnome
    return WindowsWallpaperAdapter() if sys.platform == "win32" else GnomeWallpaperAdapter()
