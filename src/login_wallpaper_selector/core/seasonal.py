"""Seasonal wallpaper theme recommendations and query augmentation."""

from __future__ import annotations
import random
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Tuple

from .models import WallpaperCategory, ColorPalette


class Season(str, Enum):
    SPRING = "Spring"
    SUMMER = "Summer"
    AUTUMN = "Autumn"
    WINTER = "Winter"


SEASON_DISPLAY: dict[Season, Tuple[str, str]] = {
    Season.SPRING: ("🌸", "Spring"),
    Season.SUMMER: ("☀️", "Summer"),
    Season.AUTUMN: ("🍂", "Autumn"),
    Season.WINTER: ("❄️", "Winter"),
}

SEASONAL_KEYWORDS: dict[Season, dict[str, List[str]]] = {
    Season.AUTUMN: {
        "default": ["autumn foliage", "golden amber leaves", "fall landscape", "misty autumn morning"],
        "Nature": ["autumn forest golden leaves", "fall foliage misty morning", "scenic autumn mountains", "vibrant maple tree amber"],
        "Space": ["harvest moon night sky", "amber nebula cosmos", "autumn night sky stars", "golden celestial nebula"],
        "Art": ["autumn landscape oil painting", "golden hour fall impressionism", "warm autumn fine art", "october landscape classical"],
        "Portrait": ["autumn scarf portrait golden hour", "fall atmospheric portrait natural lighting", "warm autumn gaze portrait"],
    },
    Season.WINTER: {
        "default": ["winter landscape", "snow covered frost", "frozen alpine scenery", "cozy winter atmosphere"],
        "Nature": ["snow covered alpine mountains", "frozen lake winter frost", "misty snowy pine forest", "aurora borealis snowy landscape"],
        "Space": ["winter night sky starry", "cold deep blue cosmos", "crystalline starlight nebula", "orion winter nebula"],
        "Art": ["winter snow scene classical painting", "frozen river fine art", "chiaroscuro winter landscape", "monet snow impressionism"],
        "Portrait": ["winter cozy portrait soft light", "snowfall portrait natural light", "dramatic winter atmospheric portrait"],
    },
    Season.SPRING: {
        "default": ["spring bloom", "fresh green meadows", "wildflowers morning mist", "vibrant spring landscape"],
        "Nature": ["cherry blossoms blooming spring", "fresh green meadows wildflowers", "spring misty morning forest", "blooming mountain garden"],
        "Space": ["spring galaxy vernal equinox", "vibrant radiant cosmos", "colorful stellar nursery", "celestial bloom nebula"],
        "Art": ["spring garden monet impressionism", "botanical fine art watercolor", "vibrant floral landscape", "impressionist garden bloom"],
        "Portrait": ["spring natural portrait soft light", "flower field portrait golden light", "radiant spring gaze portrait"],
    },
    Season.SUMMER: {
        "default": ["summer sunshine", "azure ocean coast", "vibrant golden hour sunset", "sunlit meadow"],
        "Nature": ["tropical ocean turquoise beach", "sunny coastal cliffs waves", "vibrant summer sunset over sea", "sunflower field summer sky"],
        "Space": ["summer milky way lake reflection", "radiant solar flare sun", "vivid summer cosmos panorama", "deep space summer starfield"],
        "Art": ["summer seaside oil painting", "sunlit meadow impressionism", "vibrant Mediterranean coastal art", "golden summer afternoon painting"],
        "Portrait": ["golden hour beach portrait", "summer sunlit portrait natural light", "warm summer glow portrait"],
    },
}

SEASONAL_PALETTES: dict[Season, List[ColorPalette]] = {
    Season.AUTUMN: [ColorPalette.WARM, ColorPalette.MONOCHROME],
    Season.WINTER: [ColorPalette.BLUE, ColorPalette.MONOCHROME],
    Season.SPRING: [ColorPalette.GREEN, ColorPalette.WARM],
    Season.SUMMER: [ColorPalette.BLUE, ColorPalette.WARM],
}


def get_current_season(dt: Optional[datetime] = None) -> Season:
    """Determine meteorological season based on datetime (defaults to current UTC date)."""
    if dt is None:
        dt = datetime.now(timezone.utc)

    month = dt.month
    if month in (3, 4, 5):
        return Season.SPRING
    elif month in (6, 7, 8):
        return Season.SUMMER
    elif month in (9, 10, 11):
        return Season.AUTUMN
    else:  # month in (12, 1, 2)
        return Season.WINTER


def get_season_display(season: Season) -> Tuple[str, str]:
    """Return (emoji_icon, friendly_name) for season."""
    return SEASON_DISPLAY.get(season, ("🌱", season.value))


def get_seasonal_keywords(season: Season, category: Optional[WallpaperCategory] = None) -> List[str]:
    """Retrieve curated keyword list for season and category."""
    cat_map = SEASONAL_KEYWORDS.get(season, {})
    cat_key = category.value if category else "default"
    return cat_map.get(cat_key, cat_map.get("default", []))


def augment_query_with_season(
    base_query: str,
    season: Season,
    category: Optional[WallpaperCategory] = None,
) -> str:
    """Enrich base search query with evocative seasonal descriptors."""
    keywords = get_seasonal_keywords(season, category)
    if not keywords:
        return base_query

    # Avoid duplicating season keywords if already present
    lower_query = base_query.lower() if base_query else ""
    for kw in keywords:
        if kw.lower() in lower_query:
            return base_query

    chosen_kw = random.choice(keywords)
    if not base_query:
        return chosen_kw

    return f"{base_query} {chosen_kw}"


def get_recommended_palette_for_season(season: Season) -> ColorPalette:
    """Return primary recommended color palette harmonized with the current season."""
    palettes = SEASONAL_PALETTES.get(season, [ColorPalette.ANY])
    return palettes[0]
