"""macOS desktop wallpaper adapter via AppleScript."""

from __future__ import annotations
import subprocess
from pathlib import Path
from typing import Optional
from .base import BaseWallpaperAdapter
from ..core.models import WallpaperPosition


class MacWallpaperAdapter(BaseWallpaperAdapter):
    @property
    def platform_name(self) -> str:
        return "macOS Desktop"

    def set_wallpaper(self, image_path: Path, mode: str = WallpaperPosition.FILL.value) -> bool:
        if not image_path.exists() or not image_path.is_file():
            return False

        abs_path = str(image_path.resolve())
        # AppleScript command
        script = f'tell application "System Events" to tell every desktop to set picture to "{abs_path}"'

        try:
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
            return True
        except Exception:
            return False

    def get_current_wallpaper(self) -> Optional[str]:
        try:
            script = 'tell application "System Events" to get picture of current desktop'
            res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=True)
            return res.stdout.strip()
        except Exception:
            return None
