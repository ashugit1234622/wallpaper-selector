"""Mood-based query augmentation and aesthetic classification for wallpapers."""

from __future__ import annotations
import random
from typing import List, Optional

from .models import WallpaperCategory, WallpaperMood


MOOD_KEYWORDS: dict[WallpaperMood, dict[str, List[str]]] = {
    WallpaperMood.PEACEFUL: {
        "default": ["serene", "tranquil", "peaceful calm", "soft light"],
        "Space": ["calm starry night", "serene cosmos", "silent stars", "tranquil deep field"],
        "Nature": ["serene landscape", "calm lake reflection", "tranquil forest", "peaceful misty morning"],
        "Art": ["peaceful landscape painting", "tranquil impressionism", "calm waters painting", "quiet garden"],
        "Portrait": ["gentle peaceful portrait", "soft serene gaze", "calm natural lighting"],
    },
    WallpaperMood.DARK: {
        "default": ["dark moody", "shadowy night", "low key", "deep dark tones"],
        "Space": ["dark deep space", "black nebula", "shadowy dark matter", "dark night sky stars"],
        "Nature": ["dark moody forest", "night mountains dramatic", "misty dark pine trees", "shadowy canyon"],
        "Art": ["dark chiaroscuro painting", "dramatic shadows oil painting", "night scene classic", "moody romanticism"],
        "Portrait": ["low key dark portrait", "dramatic shadows portrait", "moody atmospheric portrait"],
    },
    WallpaperMood.CINEMATIC: {
        "default": ["cinematic lighting", "epic vista", "dramatic sky", "atmospheric widescreen"],
        "Space": ["cinematic space vista", "epic galaxy widescreen", "dramatic celestial nebula", "cinematic planet"],
        "Nature": ["cinematic landscape vista", "epic mountains dramatic lighting", "cinematic nature widescreen", "dramatic sunset clouds"],
        "Art": ["cinematic composition painting", "epic classical landscape", "dramatic atmospheric painting"],
        "Portrait": ["cinematic portrait lighting", "dramatic cinematic gaze", "widescreen film portrait"],
    },
    WallpaperMood.MINIMALIST: {
        "default": ["minimalist", "clean negative space", "simple composition", "isolated subject"],
        "Space": ["minimalist astronomy", "single star negative space", "simple crescent moon", "isolated clean planet"],
        "Nature": ["minimalist landscape", "simple horizon line", "lone tree negative space", "zen minimal nature"],
        "Art": ["minimalist painting", "simple brushstrokes", "japanese ink wash landscape", "zen minimal art"],
        "Portrait": ["minimalist portrait", "clean solid background portrait", "minimal silhouette"],
    },
    WallpaperMood.VIBRANT: {
        "default": ["vibrant colorful", "vivid radiant", "saturated rich colors", "golden hour glowing"],
        "Space": ["vibrant colorful nebula", "supernova radiant colors", "vivid cosmos", "colorful emission nebula"],
        "Nature": ["vibrant golden hour", "colorful autumn foliage", "vivid saturated landscape", "vibrant wildflower field"],
        "Art": ["vibrant impressionist colors", "rich color oil painting", "fauvism colorful landscape"],
        "Portrait": ["vibrant glowing portrait", "golden hour glowing portrait", "colorful expressive portrait"],
    },
}


def get_mood_keywords(mood: WallpaperMood, category: Optional[WallpaperCategory] = None) -> List[str]:
    """Retrieve keyword list associated with a given mood and optional category."""
    if mood == WallpaperMood.ANY or mood not in MOOD_KEYWORDS:
        return []

    cat_map = MOOD_KEYWORDS[mood]
    cat_key = category.value if category else "default"
    return cat_map.get(cat_key, cat_map.get("default", []))


def augment_query_with_mood(
    base_query: str,
    mood: Optional[WallpaperMood],
    category: Optional[WallpaperCategory] = None,
) -> str:
    """Combine base query with high-relevance mood descriptors."""
    if not mood or mood == WallpaperMood.ANY:
        return base_query

    keywords = get_mood_keywords(mood, category)
    if not keywords:
        return f"{base_query} {mood.value.lower()}"

    chosen_keyword = random.choice(keywords)
    if not base_query:
        return chosen_keyword

    # If base query already contains the keyword, don't duplicate
    if chosen_keyword.lower() in base_query.lower():
        return base_query

    return f"{base_query} {chosen_keyword}"
