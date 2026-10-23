"""Unit tests for the Smart Search Retry System."""

from pathlib import Path
from unittest.mock import MagicMock
from PIL import Image
import pytest

from login_wallpaper_selector.core.config import AppConfig
from login_wallpaper_selector.core.history import HistoryTracker
from login_wallpaper_selector.core.cache import CacheManager
from login_wallpaper_selector.core.models import WallpaperCategory, WallpaperCandidate, WallpaperMood
from login_wallpaper_selector.providers.router import (
    ProviderRouter,
    get_retry_tier_query,
    RETRY_QUERY_TIERS,
)


def create_dummy_image(path: Path) -> Path:
    img = Image.new("RGB", (1000, 1000), color=(30, 40, 50))
    img.save(path, format="JPEG")
    return path


def test_retry_query_tiers_exist_for_all_categories():
    for cat in [WallpaperCategory.SPACE, WallpaperCategory.NATURE, WallpaperCategory.ART, WallpaperCategory.PORTRAIT]:
        assert cat in RETRY_QUERY_TIERS
        for tier in range(1, 6):
            assert tier in RETRY_QUERY_TIERS[cat]
            assert len(RETRY_QUERY_TIERS[cat][tier]) > 0
            query = get_retry_tier_query(cat, tier)
            assert isinstance(query, str)
            assert len(query) > 0


def test_progressive_query_variation_across_attempts():
    queries = [get_retry_tier_query(WallpaperCategory.NATURE, attempt) for attempt in range(1, 6)]
    # Tiers should be non-empty strings
    assert all(len(q) > 0 for q in queries)
    # Tier 5 is universal fallback ("nature", "landscape", etc.)
    assert queries[4].lower() in ["nature", "landscape", "mountains", "forest"]


def test_circuit_breaker_throttles_failing_provider(tmp_path):
    cfg = AppConfig(custom_cache_dir=str(tmp_path / "cache"), max_fetch_retries=5)
    hist = HistoryTracker(cfg)
    cache = CacheManager(cfg)
    router = ProviderRouter(cfg, hist, cache)

    # Mock failing provider that throws 429
    failing_provider = MagicMock()
    failing_provider.name = "FailingAPI"
    failing_provider.supports_category.return_value = True
    failing_provider.fetch_candidates.side_effect = Exception("429 Too Many Requests - Rate Limit Exceeded")

    # Mock healthy provider
    healthy_provider = MagicMock()
    healthy_provider.name = "HealthyAPI"
    healthy_provider.supports_category.return_value = True
    healthy_cand = WallpaperCandidate(
        id="healthy_1",
        category=WallpaperCategory.SPACE,
        provider_name="HealthyAPI",
        title="Cosmic Wonder",
        download_url="https://example.com/cosmic.jpg",
        source_url="https://example.com",
    )
    healthy_provider.fetch_candidates.return_value = [healthy_cand]

    # Patch router providers
    router.get_providers_for_category = lambda cat: [failing_provider, healthy_provider]

    tried_sources = {}
    # Attempt 1: failing provider fails with 429, healthy provider succeeds
    candidates1 = router.fetch_candidates(
        WallpaperCategory.SPACE,
        limit=5,
        query="galaxy query 1",
        tried_sources=tried_sources,
    )

    assert len(candidates1) == 1
    assert candidates1[0].id == "healthy_1"
    assert tried_sources["FailingAPI"]["throttled"] is True

    # Attempt 2: failing provider should be skipped entirely by circuit breaker!
    failing_provider.fetch_candidates.reset_mock()
    candidates2 = router.fetch_candidates(
        WallpaperCategory.SPACE,
        limit=5,
        query="galaxy query 2",
        tried_sources=tried_sources,
    )

    assert len(candidates2) == 1
    # Failing provider was NOT called again because circuit was open
    failing_provider.fetch_candidates.assert_not_called()


def test_query_deduplication_prevents_repeated_calls(tmp_path):
    cfg = AppConfig(custom_cache_dir=str(tmp_path / "cache"), max_fetch_retries=5)
    hist = HistoryTracker(cfg)
    cache = CacheManager(cfg)
    router = ProviderRouter(cfg, hist, cache)

    mock_provider = MagicMock()
    mock_provider.name = "MockAPI"
    mock_provider.supports_category.return_value = True
    mock_provider.fetch_candidates.return_value = []

    router.get_providers_for_category = lambda cat: [mock_provider]

    tried_sources = {}
    query_str = "same exact query"

    # Call 1
    router.fetch_candidates(WallpaperCategory.NATURE, limit=5, query=query_str, tried_sources=tried_sources)
    assert mock_provider.fetch_candidates.call_count == 1

    # Call 2 with identical query on same provider
    router.fetch_candidates(WallpaperCategory.NATURE, limit=5, query=query_str, tried_sources=tried_sources)
    # The duplicate query is skipped
    assert mock_provider.fetch_candidates.call_count == 1
