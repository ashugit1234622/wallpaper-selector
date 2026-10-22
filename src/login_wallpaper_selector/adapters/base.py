"""Base wallpaper adapter interface."""

from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
from ..core.models import WallpaperPosition


class BaseWallpaperAdapter(ABC):
    """Abstract interface for applying wallpapers to the desktop."""

    @property
    @abstractmethod
    def platform_name(self) -> str:
        pass

    @abstractmethod
    def set_wallpaper(self, image_path: Path, mode: str = WallpaperPosition.FILL.value) -> bool:
        """Apply the specified image file as desktop wallpaper using Fill or Fit mode."""
        pass

    @abstractmethod
    def get_current_wallpaper(self) -> Optional[str]:
        """Retrieve path to currently applied wallpaper if accessible."""
        pass

    def set_lockscreen(self, image_path: Path) -> bool:
        """Optional: Apply the specified image file as system lockscreen wallpaper."""
        return False
