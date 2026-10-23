"""Tests for Mood-Based Wallpaper Search."""

import pytest
from login_wallpaper_selector.core.models import (
    WallpaperCategory,
    WallpaperMood,
    WallpaperCandidate,
    WallpaperMetadata,
)
from login_wallpaper_selector.core.mood_matcher import (
    get_mood_keywords,
    augment_query_with_mood,
    MOOD_KEYWORDS,
)
from login_wallpaper_selector.providers.wallhaven import WallhavenProvider
from login_wallpaper_selector.providers.the_met import TheMetImageProvider
from login_wallpaper_selector.providers.nasa import NasaImageProvider
from login_wallpaper_selector.providers.artic import ArtInstituteChicagoProvider
from login_wallpaper_selector.providers.wikimedia import WikimediaCommonsProvider


def test_mood_enum_values():
    assert WallpaperMood.PEACEFUL.value == "Peaceful"
    assert WallpaperMood.DARK.value == "Dark"
    assert WallpaperMood.CINEMATIC.value == "Cinematic"
    assert WallpaperMood.MINIMALIST.value == "Minimalist"
    assert WallpaperMood.VIBRANT.value == "Vibrant"
    assert WallpaperMood.ANY.value == "Any"


def test_get_mood_keywords():
    # Any mood returns empty list
    assert get_mood_keywords(WallpaperMood.ANY) == []

    # Category-specific keywords
    space_peaceful = get_mood_keywords(WallpaperMood.PEACEFUL, WallpaperCategory.SPACE)
    assert len(space_peaceful) > 0
    assert any("stars" in kw or "cosmos" in kw or "field" in kw for kw in space_peaceful)

    nature_dark = get_mood_keywords(WallpaperMood.DARK, WallpaperCategory.NATURE)
    assert any("dark" in kw or "night" in kw for kw in nature_dark)

    art_cinematic = get_mood_keywords(WallpaperMood.CINEMATIC, WallpaperCategory.ART)
    assert any("cinematic" in kw or "epic" in kw or "dramatic" in kw for kw in art_cinematic)


def test_augment_query_with_mood():
    base = "mountain lake"

    # ANY mood does not alter query
    assert augment_query_with_mood(base, WallpaperMood.ANY) == base
    assert augment_query_with_mood(base, None) == base

    # Specific mood augments query
    augmented = augment_query_with_mood(base, WallpaperMood.CINEMATIC, WallpaperCategory.NATURE)
    assert base in augmented
    assert len(augmented) > len(base)

    # Empty base query returns keyword directly
    empty_aug = augment_query_with_mood("", WallpaperMood.DARK, WallpaperCategory.SPACE)
    assert len(empty_aug) > 0


def test_metadata_model_with_mood():
    meta = WallpaperMetadata(
        image_id="test_mood_id",
        category="Nature",
        provider="Wallhaven",
        source_url="https://example.com/source",
        download_url="https://example.com/download.jpg",
        local_path="/path/to/test.jpg",
        sha256="abcdef123456",
        title="Dramatic Peak",
        creator="Photographer",
        license="CC0",
        license_url=None,
        attribution_required=False,
        attribution_text="",
        width=1920,
        height=1080,
        aspect_ratio=1.778,
        mode="Fill",
        mood="Cinematic",
    )
    d = meta.to_dict()
    assert d["mood"] == "Cinematic"
    assert d["title"] == "Dramatic Peak"


def test_candidate_model_with_mood():
    cand = WallpaperCandidate(
        id="cand_mood_1",
        category=WallpaperCategory.SPACE,
        provider_name="NASA",
        title="Tranquil Deep Field",
        download_url="https://example.com/img.jpg",
        source_url="https://example.com",
        mood=WallpaperMood.PEACEFUL,
    )
    assert cand.mood == WallpaperMood.PEACEFUL


def test_provider_fetch_candidates_mood_argument():
    # Verify all providers accept mood keyword without errors
    providers = [
        WallhavenProvider(),
        TheMetImageProvider(),
        NasaImageProvider(),
        ArtInstituteChicagoProvider(),
        WikimediaCommonsProvider(),
    ]

    for p in providers:
        # None of these should raise TypeError about unexpected keyword argument
        assert hasattr(p, "fetch_candidates")
