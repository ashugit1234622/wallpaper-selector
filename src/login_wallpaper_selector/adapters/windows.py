"""Windows native wallpaper adapter using SystemParametersInfoW and IDesktopWallpaper COM API."""

from __future__ import annotations
import os
import sys
import winreg
from pathlib import Path
from typing import Optional
from .base import BaseWallpaperAdapter
from ..core.models import WallpaperPosition


class WindowsWallpaperAdapter(BaseWallpaperAdapter):
    """Applies wallpapers on Windows 10/11 supporting Fill and Fit modes."""

    SPI_SETDESKWALLPAPER = 20
    SPIF_UPDATEINIFILE = 0x01
    SPIF_SENDCHANGE = 0x02

    @property
    def platform_name(self) -> str:
        return "Windows Desktop"

    def _set_registry_style(self, mode: str) -> None:
        """Configure WallpaperStyle and TileWallpaper in HKCU."""
        try:
            # 10 = Fill (crop/zoom keeping aspect ratio), 6 = Fit (letterbox keeping aspect ratio)
            style_value = "10" if mode.lower() == WallpaperPosition.FILL.value.lower() else "6"
            tile_value = "0"

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Control Panel\Desktop",
                0,
                winreg.KEY_SET_VALUE | winreg.KEY_READ,
            )
            winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, style_value)
            winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, tile_value)
            winreg.CloseKey(key)
        except Exception:
            pass

    def _set_via_com(self, abs_path: str, mode: str) -> bool:
        """Attempt to set wallpaper across all monitors via IDesktopWallpaper COM interface."""
        try:
            import ctypes
            from ctypes import wintypes
            import comtypes
            import comtypes.client

            # CLSID and IID for IDesktopWallpaper
            CLSID_DesktopWallpaper = comtypes.GUID("{C2CF3110-460E-4fc1-B9D0-8A1C0C9CC4BD}")
            
            # Position enum: DWPOS_FIT = 3, DWPOS_FILL = 4
            position = 4 if mode.lower() == WallpaperPosition.FILL.value.lower() else 3

            desktop_wp = comtypes.client.CreateObject(CLSID_DesktopWallpaper)
            # In IDesktopWallpaper: SetWallpaper(monitorID, wallpaperPath)
            # Passing None/NULL for monitorID sets it for all monitors
            desktop_wp.SetPosition(position)
            desktop_wp.SetWallpaper(None, abs_path)
            return True
        except Exception:
            return False

    def _set_via_system_parameters_info(self, abs_path: str) -> bool:
        """Fallback to SystemParametersInfoW."""
        try:
            import ctypes
            user32 = ctypes.windll.user32
            result = user32.SystemParametersInfoW(
                self.SPI_SETDESKWALLPAPER,
                0,
                abs_path,
                self.SPIF_UPDATEINIFILE | self.SPIF_SENDCHANGE,
            )
            return bool(result)
        except Exception:
            return False

    def set_wallpaper(self, image_path: Path, mode: str = WallpaperPosition.FILL.value) -> bool:
        if not image_path.exists() or not image_path.is_file():
            return False

        abs_path = str(image_path.resolve())

        # 1. Update registry style so Windows shell applies Fill/Fit correctly
        self._set_registry_style(mode)

        # 2. Try IDesktopWallpaper COM interface first (handles multi-monitor)
        com_success = self._set_via_com(abs_path, mode)
        if com_success:
            return True

        # 3. Fallback to SystemParametersInfoW
        return self._set_via_system_parameters_info(abs_path)

    def get_current_wallpaper(self) -> Optional[str]:
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop")
            val, _ = winreg.QueryValueEx(key, "WallPaper")
            winreg.CloseKey(key)
            return val
        except Exception:
            return None
