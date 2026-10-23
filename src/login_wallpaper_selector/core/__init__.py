"""Core package for Login Wallpaper Selector."""
from .models import WallpaperCategory, WallpaperPosition, WallpaperCandidate, WallpaperMetadata, ImageDimensions, ColorPalette, WallpaperMood
from .seasonal import Season, get_current_season, augment_query_with_season
from .favorites import FavoritesManager, FavoriteRecord
from .keyword_expander import generate_keyword_query_for_tier, normalize_keyword
from .ranking import rank_wallpaper_candidates, check_candidate_relevance_gate
from .search_history import SearchHistoryManager, SearchRecord

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
    "generate_keyword_query_for_tier",
    "normalize_keyword",
    "rank_wallpaper_candidates",
    "check_candidate_relevance_gate",
    "SearchHistoryManager",
    "SearchRecord",
]
