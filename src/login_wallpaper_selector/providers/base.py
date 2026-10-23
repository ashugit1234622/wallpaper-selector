"""Base provider interface for open-content image sources."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Optional, Set
from ..core.models import WallpaperCategory, WallpaperCandidate


class BaseImageProvider(ABC):
    """Abstract interface for querying open-content image repositories."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the provider (e.g. 'NASA Image and Video Library')."""
        pass

    @abstractmethod
    def supports_category(self, category: WallpaperCategory) -> bool:
        """Whether this provider can supply images for the given category."""
        pass

    @abstractmethod
    def fetch_candidates(
        self,
        category: WallpaperCategory,
        query: Optional[str] = None,
        limit: int = 15,
        exclude_ids: Optional[Set[str]] = None,
        color: Optional[ColorPalette] = None,
        custom_color_hex: Optional[str] = None,
        mood: Optional[WallpaperMood] = None,
        **kwargs,
    ) -> List[WallpaperCandidate]:
        pass

    def supports_color_filtering(self) -> bool:
        """Whether this provider supports palette or color query filtering."""
        return True
