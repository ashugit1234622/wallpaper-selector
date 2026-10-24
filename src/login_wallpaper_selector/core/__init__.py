"""Core package for Login Wallpaper Selector."""
from .models import WallpaperCategory, WallpaperPosition, WallpaperCandidate, WallpaperMetadata, ImageDimensions, ColorPalette, WallpaperMood
from .seasonal import Season, get_current_season, augment_query_with_season
from .favorites import FavoritesManager, FavoriteRecord
from .keyword_expander import generate_keyword_query_for_tier, normalize_keyword
from .ranking import rank_wallpaper_candidates, check_candidate_relevance_gate
from .search_history import SearchHistoryManager, SearchRecord
from .recent_history import RecentWallpaperManager
from .time_of_day import (
    TimeOfDaySlot,
    get_current_time_of_day_slot,
    get_time_of_day_keywords,
    select_time_of_day_keywords,
    TIME_OF_DAY_THEMES,
    TIME_OF_DAY_KEYWORDS,
)
from .hotkey import GlobalHotkeyListener
from .notifications import send_toast_notification
from .power import get_system_power_status, is_running_on_battery, is_battery_saver_active

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
    "RecentWallpaperManager",
    "TimeOfDaySlot",
    "get_current_time_of_day_slot",
    "get_time_of_day_keywords",
    "select_time_of_day_keywords",
    "TIME_OF_DAY_THEMES",
    "TIME_OF_DAY_KEYWORDS",
    "GlobalHotkeyListener",
    "send_toast_notification",
    "get_system_power_status",
    "is_running_on_battery",
    "is_battery_saver_active",
]
