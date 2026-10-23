"""Unit tests for keyword search routing, candidate evaluation, and strict failure in router.py."""

from pathlib import Path
from unittest.mock import MagicMock
from PIL import Image
import pytest

from login_wallpaper_selector.core.config import AppConfig
from login_wallpaper_selector.core.history import HistoryTracker
from login_wallpaper_selector.core.cache import CacheManager
from login_wallpaper_selector.core.models import (
    WallpaperCategory,
    WallpaperCandidate,
    ColorPalette,
    WallpaperMood,
)
from login_wallpaper_selector.providers.router import ProviderRouter


def create_dummy_image(path: Path) -> Path:
    img = Image.new("RGB", (1920, 1080), color=(10, 20, 30))
    img.save(path, format="JPEG")
    return path


def test_keyword_provider_selection_excludes_bing(tmp_path: Path):
    cfg = AppConfig.load()
    cfg.custom_cache_dir = str(tmp_path)
    hist = HistoryTracker(cfg)
    cache = CacheManager(cfg)
    router = ProviderRouter(cfg, hist, cache)

    # Bing must NEVER be selected for text-based keyword queries
    providers = router.get_providers_for_category(WallpaperCategory.SPACE, keyword="Supermassive Black Hole")
    provider_names = [p.name.lower() for p in providers]
    assert "bing" not in provider_names


def test_keyword_provider_affinity(tmp_path: Path):
    cfg = AppConfig.load()
    cfg.custom_cache_dir = str(tmp_path)
    hist = HistoryTracker(cfg)
    cache = CacheManager(cfg)
    router = ProviderRouter(cfg, hist, cache)

    # For art keyword, should prefer Met, Artic, Wallhaven, etc.
    providers = router.get_providers_for_category(WallpaperCategory.ART, keyword="Van Gogh Sunflower")
    provider_names = [p.name.lower() for p in providers]
    assert any(name in provider_names for name in ["the met", "artic", "wallhaven", "unsplash", "wikimedia"])


def test_keyword_search_successful_match(tmp_path: Path):
    cfg = AppConfig.load()
    cfg.custom_cache_dir = str(tmp_path)
    hist = HistoryTracker(cfg)
    cache = CacheManager(cfg)
    router = ProviderRouter(cfg, hist, cache)

    matching_cand = WallpaperCandidate(
        id="black_hole_1",
        category=WallpaperCategory.SPACE,
        provider_name="TestProvider",
        title="Supermassive Black Hole Singularity",
        download_url="http://example.com/black_hole.jpg",
        source_url="http://example.com/item/1",
        creator="Astrophotographer",
        license_name="CC0",
        license_url=None,
        attribution_required=False,
        attribution_text="Black Hole Image",
        width=1920,
        height=1080,
    )

    img_path = tmp_path / "downloaded.jpg"
    create_dummy_image(img_path)

    router.fetch_candidates = MagicMock(return_value=[matching_cand])
    router.download_candidate = MagicMock(return_value=img_path)

    meta, err = router.acquire_wallpaper_for_category(
        WallpaperCategory.SPACE,
        keyword="Black Hole",
    )

    assert err is None
    assert meta is not None
    assert "Black Hole" in meta.title


def test_keyword_search_strict_failure_never_returns_unrelated_image(tmp_path: Path):
    """When all candidates fail the relevance gate, router MUST return clean failure rather than arbitrary wallpaper."""
    cfg = AppConfig.load()
    cfg.custom_cache_dir = str(tmp_path)
    hist = HistoryTracker(cfg)
    cache = CacheManager(cfg)
    router = ProviderRouter(cfg, hist, cache)

    # Irrelevant candidate with zero overlap with "Black Hole"
    irrelevant_cand = WallpaperCandidate(
        id="beach_1",
        category=WallpaperCategory.SPACE,
        provider_name="TestProvider",
        title="Tropical Sandy Beach at Sunset",
        download_url="http://example.com/beach.jpg",
        source_url="http://example.com/item/1",
        creator="Traveler",
        license_name="CC0",
        license_url=None,
        attribution_required=False,
        attribution_text="Beach Image",
        width=3840,
        height=2160,
    )

    router.fetch_candidates = MagicMock(return_value=[irrelevant_cand])

    meta, err = router.acquire_wallpaper_for_category(
        WallpaperCategory.SPACE,
        keyword="Black Hole",
    )

    # Must fail cleanly with informative message
    assert meta is None
    assert err is not None
    assert "No suitable wallpaper found for 'Black Hole'" in err


def test_blank_keyword_uses_standard_category_search(tmp_path: Path):
    """When keyword is None or empty, standard category search operates normally."""
    cfg = AppConfig.load()
    cfg.custom_cache_dir = str(tmp_path)
    hist = HistoryTracker(cfg)
    cache = CacheManager(cfg)
    router = ProviderRouter(cfg, hist, cache)

    cand = WallpaperCandidate(
        id="nature_1",
        category=WallpaperCategory.NATURE,
        provider_name="TestProvider",
        title="Forest Landscape",
        download_url="http://example.com/nature.jpg",
        source_url="http://example.com/item/1",
        creator="Photographer",
        license_name="CC0",
        license_url=None,
        attribution_required=False,
        attribution_text="Forest",
        width=1920,
        height=1080,
    )

    img_path = tmp_path / "nature.jpg"
    create_dummy_image(img_path)

    router.fetch_candidates = MagicMock(return_value=[cand])
    router.download_candidate = MagicMock(return_value=img_path)

    meta, err = router.acquire_wallpaper_for_category(
        WallpaperCategory.NATURE,
        keyword=None,  # Blank keyword
    )

    assert err is None
    assert meta is not None
    assert meta.title == "Forest Landscape"


def test_global_keyword_search_without_category(tmp_path: Path):
    """When category is None, keyword search queries across general providers without category restriction."""
    cfg = AppConfig.load()
    cfg.custom_cache_dir = str(tmp_path)
    hist = HistoryTracker(cfg)
    cache = CacheManager(cfg)
    router = ProviderRouter(cfg, hist, cache)

    cand = WallpaperCandidate(
        id="cyberpunk_1",
        category=None,
        provider_name="Wallhaven",
        title="Futuristic Cyberpunk City",
        download_url="http://example.com/cyberpunk.jpg",
        source_url="http://example.com/item/cyberpunk",
        creator="Artist",
        license_name="CC0",
        license_url=None,
        attribution_required=False,
        attribution_text="Cyberpunk",
        width=1920,
        height=1080,
    )

    img_path = tmp_path / "cyberpunk.jpg"
    create_dummy_image(img_path)

    router.fetch_candidates = MagicMock(return_value=[cand])
    router.download_candidate = MagicMock(return_value=img_path)

    meta, err = router.acquire_wallpaper_for_category(
        category=None,  # No category restriction
        keyword="cyberpunk",
    )

    assert err is None
    assert meta is not None
    assert "Cyberpunk" in meta.title


def test_category_free_random_aesthetic_search(tmp_path: Path):
    """When category is None and no keyword is given, router discovers random wallpapers adhering to mood and color."""
    cfg = AppConfig.load()
    cfg.custom_cache_dir = str(tmp_path)
    hist = HistoryTracker(cfg)
    cache = CacheManager(cfg)
    router = ProviderRouter(cfg, hist, cache)

    cand = WallpaperCandidate(
        id="dark_blue_1",
        category=None,
        provider_name="Wallhaven",
        title="Dark Moody Horizon",
        download_url="http://example.com/dark_blue.jpg",
        source_url="http://example.com/item/dark_blue",
        creator="Photographer",
        license_name="CC0",
        license_url=None,
        attribution_required=False,
        attribution_text="Dark Moody Horizon",
        width=1920,
        height=1080,
    )

    img_path = tmp_path / "dark_blue.jpg"
    create_dummy_image(img_path)

    router.fetch_candidates = MagicMock(return_value=[cand])
    router.download_candidate = MagicMock(return_value=img_path)

    meta, err = router.acquire_wallpaper_for_category(
        category=None,
        color=ColorPalette.BLUE,
        mood=WallpaperMood.DARK,
    )

    assert err is None
    assert meta is not None
    assert meta.title == "Dark Moody Horizon"

