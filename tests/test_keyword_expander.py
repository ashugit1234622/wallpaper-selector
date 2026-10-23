"""Unit tests for keyword expansion and provider-aware query generation."""

import pytest
from login_wallpaper_selector.core.keyword_expander import (
    normalize_keyword,
    find_curated_subject,
    generate_keyword_query_for_tier,
    CURATED_SUBJECT_CONCEPTS,
)
from login_wallpaper_selector.core.models import WallpaperCategory, ColorPalette, WallpaperMood


def test_normalize_keyword():
    assert normalize_keyword("  Black  Hole   ") == "Black Hole"
    assert normalize_keyword("CYBERPUNK") == "CYBERPUNK"
    assert normalize_keyword("a!@#$b%^&*()c") == "a b c"
    assert normalize_keyword("") == ""


def test_find_curated_subject():
    assert find_curated_subject("black hole") == "black hole"
    assert find_curated_subject("futuristic cyberpunk city") == "cyberpunk"
    assert find_curated_subject("unknown query xyz") is None


def test_tier1_exact_query():
    q_wall = generate_keyword_query_for_tier(
        "Black Hole",
        attempt=1,
        category=WallpaperCategory.SPACE,
        provider_style="wallpaper",
    )
    # Tier 1 should preserve exact keyword
    assert "black hole" in q_wall.lower()

    q_museum = generate_keyword_query_for_tier(
        "Sunflower",
        attempt=1,
        category=WallpaperCategory.ART,
        provider_style="museum",
    )
    # Museum style should be clean query without fluff
    assert q_museum.lower() == "sunflower"


def test_tier2_synonym_expansion():
    q = generate_keyword_query_for_tier(
        "black hole",
        attempt=2,
        category=WallpaperCategory.SPACE,
        provider_style="wallpaper",
    )
    # Tier 2 uses curated expansion
    assert "black hole" in q.lower()


def test_tier3_mood_color_harmony():
    q = generate_keyword_query_for_tier(
        "Forest",
        attempt=3,
        category=WallpaperCategory.NATURE,
        provider_style="wallpaper",
        color=ColorPalette.GREEN,
        mood=WallpaperMood.PEACEFUL,
    )
    # Should include subject "forest" and mood or color hints
    assert "forest" in q.lower()
    assert any(term in q.lower() for term in ["calm", "serene", "green", "tranquil", "peaceful"])


def test_tier4_category_anchored():
    q = generate_keyword_query_for_tier(
        "cyberpunk",
        attempt=4,
        category=WallpaperCategory.SPACE,
        provider_style="wallpaper",
    )
    assert "cyberpunk" in q.lower()


def test_tier5_semantic_fallback_preserves_subject():
    q = generate_keyword_query_for_tier(
        "Waterfall",
        attempt=5,
        category=WallpaperCategory.NATURE,
        provider_style="wallpaper",
    )
    # Even at tier 5, the core subject must NEVER be stripped away
    assert "waterfall" in q.lower()


def test_provider_styles_omit_fluff_for_museum_and_science():
    # Museum style strips terms like "wallpaper", "vista", etc.
    q_met = generate_keyword_query_for_tier(
        "Water Lilies",
        attempt=2,
        category=WallpaperCategory.ART,
        provider_style="museum",
    )
    assert "wallpaper" not in q_met.lower()
    assert "vista" not in q_met.lower()
    assert "water lilies" in q_met.lower()
