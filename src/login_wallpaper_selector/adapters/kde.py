"""KDE Plasma wallpaper adapter via D-Bus evaluateScript."""

from __future__ import annotations
import subprocess
from pathlib import Path
from typing import Optional
from .base import BaseWallpaperAdapter
from ..core.models import WallpaperPosition


class KdePlasmaWallpaperAdapter(BaseWallpaperAdapter):
    @property
    def platform_name(self) -> str:
        return "KDE Plasma Desktop"

    def set_wallpaper(self, image_path: Path, mode: str = WallpaperPosition.FILL.value) -> bool:
        if not image_path.exists() or not image_path.is_file():
            return False

        abs_path = str(image_path.resolve())
        # FillMode: 2 = Scaled & Cropped (Fill), 0 = Scaled (Fit)
        fill_mode = "2" if mode.lower() == WallpaperPosition.FILL.value.lower() else "0"

        script = f"""
        var allDesktops = desktops();
        for (var i=0; i<allDesktops.length; i++) {{
            var d = allDesktops[i];
            d.currentConfigGroup = ['Wallpaper', 'org.kde.image', 'General'];
            d.writeConfig('Image', 'file://{abs_path}');
            d.writeConfig('FillMode', {fill_mode});
        }}
        """

        try:
            subprocess.run(
                [
                    "qdbus",
                    "org.kde.plasmashell",
                    "/PlasmaShell",
                    "org.kde.PlasmaShell.evaluateScript",
                    script,
                ],
                check=True,
                capture_output=True,
            )
            return True
        except Exception:
            return False

    def get_current_wallpaper(self) -> Optional[str]:
        return None
