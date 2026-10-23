"""Core package for Login Wallpaper Selector."""
from .models import WallpaperCategory, WallpaperPosition, WallpaperCandidate, WallpaperMetadata, ImageDimensions, ColorPalette, WallpaperMood
from .seasonal import Season, get_current_season, augment_query_with_season
from .favorites import FavoritesManager, FavoriteRecord

__all__ = [
    "WallpaperCategory",
    "WallpaperPosition",
    "WallpaperCandidate",
    "WallpaperMetadata",
    "ImageDimensions",
    "ColorPalette",
    "WallpaperMood",
    "Season",
    "get_current_season",
    "augment_query_with_season",
    "FavoritesManager",
    "FavoriteRecord",
]
