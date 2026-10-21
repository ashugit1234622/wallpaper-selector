"""Adapters package for wallpaper switching."""
from .base import BaseWallpaperAdapter
from .factory import get_wallpaper_adapter
from .windows import WindowsWallpaperAdapter
from .gnome import GnomeWallpaperAdapter
from .kde import KdePlasmaWallpaperAdapter
from .macos import MacWallpaperAdapter

__all__ = [
    "BaseWallpaperAdapter",
    "get_wallpaper_adapter",
    "WindowsWallpaperAdapter",
    "GnomeWallpaperAdapter",
    "KdePlasmaWallpaperAdapter",
    "MacWallpaperAdapter",
]
