"""GNOME Desktop wallpaper adapter via GSettings."""

from __future__ import annotations
import subprocess
from pathlib import Path
from typing import Optional
from .base import BaseWallpaperAdapter
from ..core.models import WallpaperPosition


class GnomeWallpaperAdapter(BaseWallpaperAdapter):
    @property
    def platform_name(self) -> str:
        return "GNOME Desktop"

    def set_wallpaper(self, image_path: Path, mode: str = WallpaperPosition.FILL.value) -> bool:
        if not image_path.exists() or not image_path.is_file():
            return False

        uri = image_path.resolve().as_uri()
        # 'zoom' for Fill (crop to cover), 'scaled' for Fit (letterbox)
        pic_option = "zoom" if mode.lower() == WallpaperPosition.FILL.value.lower() else "scaled"

        try:
            # Set light and dark theme background URIs
            subprocess.run(
                ["gsettings", "set", "org.gnome.desktop.background", "picture-uri", uri],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", uri],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["gsettings", "set", "org.gnome.desktop.background", "picture-options", pic_option],
                check=True,
                capture_output=True,
            )
            return True
        except Exception:
            return False

    def set_lockscreen(self, image_path: Path) -> bool:
        if not image_path.exists() or not image_path.is_file():
            return False
        uri = image_path.resolve().as_uri()
        try:
            subprocess.run(
                ["gsettings", "set", "org.gnome.desktop.screensaver", "picture-uri", uri],
                check=True,
                capture_output=True,
            )
            return True
        except Exception:
            return False

    def get_current_wallpaper(self) -> Optional[str]:
        try:
            res = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.background", "picture-uri"],
                capture_output=True,
                text=True,
                check=True,
            )
            val = res.stdout.strip().strip("'").strip('"')
            if val.startswith("file://"):
                val = val[7:]
            return val
        except Exception:
            return None
