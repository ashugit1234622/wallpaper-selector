"""Unit tests for the Seasonal Wallpaper Themes engine."""

from datetime import datetime, timezone
import pytest

from login_wallpaper_selector.core.models import WallpaperCategory, ColorPalette
from login_wallpaper_selector.core.seasonal import (
    Season,
    get_current_season,
    get_season_display,
    get_seasonal_keywords,
    augment_query_with_season,
    get_recommended_palette_for_season,
)


def test_season_detection_by_month():
    # Spring: Mar, Apr, May
    assert get_current_season(datetime(2026, 3, 15, tzinfo=timezone.utc)) == Season.SPRING
    assert get_current_season(datetime(2026, 4, 1, tzinfo=timezone.utc)) == Season.SPRING
    assert get_current_season(datetime(2026, 5, 31, tzinfo=timezone.utc)) == Season.SPRING

    # Summer: Jun, Jul, Aug
    assert get_current_season(datetime(2026, 6, 1, tzinfo=timezone.utc)) == Season.SUMMER
    assert get_current_season(datetime(2026, 7, 20, tzinfo=timezone.utc)) == Season.SUMMER
    assert get_current_season(datetime(2026, 8, 31, tzinfo=timezone.utc)) == Season.SUMMER

    # Autumn: Sep, Oct, Nov
    assert get_current_season(datetime(2026, 9, 1, tzinfo=timezone.utc)) == Season.AUTUMN
    assert get_current_season(datetime(2026, 10, 23, tzinfo=timezone.utc)) == Season.AUTUMN
    assert get_current_season(datetime(2026, 11, 30, tzinfo=timezone.utc)) == Season.AUTUMN

    # Winter: Dec, Jan, Feb
    assert get_current_season(datetime(2026, 12, 1, tzinfo=timezone.utc)) == Season.WINTER
    assert get_current_season(datetime(2027, 1, 15, tzinfo=timezone.utc)) == Season.WINTER
    assert get_current_season(datetime(2027, 2, 28, tzinfo=timezone.utc)) == Season.WINTER


def test_season_display_metadata():
    for season in Season:
        icon, name = get_season_display(season)
        assert isinstance(icon, str) and len(icon) > 0
        assert name == season.value


def test_seasonal_keywords_for_all_categories():
    for season in Season:
        for cat in [WallpaperCategory.NATURE, WallpaperCategory.SPACE, WallpaperCategory.ART, WallpaperCategory.PORTRAIT]:
            keywords = get_seasonal_keywords(season, cat)
            assert isinstance(keywords, list)
            assert len(keywords) >= 3
            for kw in keywords:
                assert isinstance(kw, str) and len(kw.strip()) > 0


def test_augment_query_with_season():
    # Nature in Autumn
    base = "mountain lake"
    augmented = augment_query_with_season(base, Season.AUTUMN, WallpaperCategory.NATURE)
    assert base in augmented
    assert len(augmented) > len(base)

    # Empty base query
    aug_empty = augment_query_with_season("", Season.WINTER, WallpaperCategory.NATURE)
    assert len(aug_empty.strip()) > 0

    # No duplication if seasonal keyword already in query
    kw = "snow covered alpine mountains"
    aug_dup = augment_query_with_season(f"epic {kw}", Season.WINTER, WallpaperCategory.NATURE)
    assert aug_dup == f"epic {kw}"


def test_recommended_palettes_for_seasons():
    assert get_recommended_palette_for_season(Season.AUTUMN) in (ColorPalette.WARM, ColorPalette.MONOCHROME)
    assert get_recommended_palette_for_season(Season.WINTER) in (ColorPalette.BLUE, ColorPalette.MONOCHROME)
    assert get_recommended_palette_for_season(Season.SPRING) in (ColorPalette.GREEN, ColorPalette.WARM)
    assert get_recommended_palette_for_season(Season.SUMMER) in (ColorPalette.BLUE, ColorPalette.WARM)
