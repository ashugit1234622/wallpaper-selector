"""Unit tests for Uhd4kProvider and 4K TV toggle search integration."""

from pathlib import Path
from unittest.mock import MagicMock, patch
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
from login_wallpaper_selector.providers.uhd_4k import Uhd4kProvider
from login_wallpaper_selector.providers.router import ProviderRouter


def test_uhd_4k_provider_properties():
    provider = Uhd4kProvider()
    assert provider.name == "4K UHD Curated"
    assert provider.supports_color_filtering() is True
    assert provider.supports_category(WallpaperCategory.NATURE) is True
    assert provider.supports_category(WallpaperCategory.SPACE) is True
    assert provider.supports_category(WallpaperCategory.ART) is True
    assert provider.supports_category(WallpaperCategory.PORTRAIT) is True
    assert provider.supports_category(None) is True


def test_uhd_4k_fetch_candidates_nature():
    provider = Uhd4kProvider()
    candidates = provider.fetch_candidates(WallpaperCategory.NATURE, limit=5)
    assert len(candidates) > 0
    assert len(candidates) <= 5

    for cand in candidates:
        assert cand.provider_name == "4K UHD Curated"
        assert cand.width >= 3840
        assert cand.height >= 2160
        assert "cdn.jsdelivr.net" in cand.download_url or "githubusercontent.com" in cand.download_url
        assert cand.title.endswith("(4K UHD)")
        assert cand.license_name == "CC0 / Open Wallpaper"


def test_uhd_4k_fetch_candidates_space():
    provider = Uhd4kProvider()
    candidates = provider.fetch_candidates(WallpaperCategory.SPACE, limit=5)
    assert len(candidates) > 0
    for cand in candidates:
        assert cand.category == WallpaperCategory.SPACE
        assert cand.width >= 3840
        assert cand.height >= 2160


def test_uhd_4k_fetch_candidates_art_and_portrait():
    provider = Uhd4kProvider()
    art_cands = provider.fetch_candidates(WallpaperCategory.ART, limit=3)
    assert len(art_cands) > 0
    for cand in art_cands:
        assert cand.category == WallpaperCategory.ART

    portrait_cands = provider.fetch_candidates(WallpaperCategory.PORTRAIT, limit=3)
    assert len(portrait_cands) > 0
    for cand in portrait_cands:
        assert cand.category == WallpaperCategory.PORTRAIT


def test_uhd_4k_fetch_candidates_exclusion():
    provider = Uhd4kProvider()
    initial = provider.fetch_candidates(WallpaperCategory.NATURE, limit=3)
    assert len(initial) > 0

    exclude = {c.id for c in initial}
    subsequent = provider.fetch_candidates(WallpaperCategory.NATURE, limit=5, exclude_ids=exclude)
    for c in subsequent:
        assert c.id not in exclude


def test_uhd_4k_mood_and_color_filtering():
    provider = Uhd4kProvider()
    dark_cands = provider.fetch_candidates(
        WallpaperCategory.NATURE,
        mood=WallpaperMood.DARK,
        limit=5,
    )
    assert len(dark_cands) > 0
    for c in dark_cands:
        assert c.width >= 3840

    mono_cands = provider.fetch_candidates(
        WallpaperCategory.NATURE,
        color=ColorPalette.MONOCHROME,
        limit=5,
    )
    assert len(mono_cands) > 0


def test_uhd_4k_dynamic_wikimedia_tier():
    provider = Uhd4kProvider()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "query": {
            "pages": [
                {
                    "pageid": 999999,
                    "title": "File:Majestic Alpine Mountain Vista 4k.jpg",
                    "imageinfo": [
                        {
                            "width": 5120,
                            "height": 2880,
                            "url": "https://upload.wikimedia.org/wikipedia/commons/sample_4k.jpg",
                            "mime": "image/jpeg",
                            "descriptionurl": "https://commons.wikimedia.org/wiki/File:sample.jpg",
                        }
                    ],
                }
            ]
        }
    }

    with patch("httpx.Client.get", return_value=mock_response):
        cands = provider._fetch_dynamic_wikimedia_4k(
            category=WallpaperCategory.NATURE,
            search_term="Alpine Mountain",
            limit=2,
            exclude_ids=set(),
        )
        assert len(cands) == 1
        assert cands[0].width == 5120
        assert cands[0].height == 2880
        assert cands[0].id == "uhd_wm_999999"


def test_router_get_providers_for_category_prioritizes_uhd_4k_in_tv_mode(tmp_path: Path):
    cfg = AppConfig.load()
    cfg.custom_cache_dir = str(tmp_path)
    hist = HistoryTracker(cfg)
    cache = CacheManager(cfg)
    router = ProviderRouter(cfg, hist, cache)

    # In TV mode (search_for_tv=True), uhd_4k must be index 0
    tv_providers = router.get_providers_for_category(WallpaperCategory.NATURE, search_for_tv=True)
    assert tv_providers[0] == router.uhd_4k
    assert router.wallhaven in tv_providers
    assert router.bing in tv_providers

    # In normal desktop mode (search_for_tv=False), Wallhaven remains first for Nature
    desktop_providers = router.get_providers_for_category(WallpaperCategory.NATURE, search_for_tv=False)
    assert desktop_providers[0] == router.wallhaven


def test_router_fetch_candidates_tv_mode_with_uhd_4k(tmp_path: Path):
    cfg = AppConfig.load()
    cfg.custom_cache_dir = str(tmp_path)
    hist = HistoryTracker(cfg)
    cache = CacheManager(cfg)
    router = ProviderRouter(cfg, hist, cache)

    candidates = router.fetch_candidates(WallpaperCategory.NATURE, limit=4, search_for_tv=True)
    assert len(candidates) > 0
    # Top candidates must come from 4K UHD Curated repo with 4K resolution
    assert any(c.provider_name == "4K UHD Curated" for c in candidates)
    for c in candidates:
        if c.width is not None and c.height is not None:
            assert c.width >= 3840
            assert c.height >= 2160
