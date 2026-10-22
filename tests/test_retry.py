"""Unit tests for the 5-attempt resilient wallpaper acquisition engine."""

from pathlib import Path
from unittest.mock import MagicMock
from PIL import Image

from login_wallpaper_selector.core.config import AppConfig
from login_wallpaper_selector.core.history import HistoryTracker
from login_wallpaper_selector.core.cache import CacheManager
from login_wallpaper_selector.core.models import WallpaperCategory, WallpaperCandidate, WallpaperMetadata
from login_wallpaper_selector.providers.router import ProviderRouter


def create_mock_image(path: Path) -> Path:
    img = Image.new("RGB", (1920, 1080), color=(50, 100, 150))
    img.save(path, format="JPEG")
    return path


def test_retry_immediate_success(tmp_path, monkeypatch):
    cfg = AppConfig(custom_cache_dir=str(tmp_path / "cache"), max_fetch_retries=5)
    hist = HistoryTracker(cfg)
    cache = CacheManager(cfg)
    router = ProviderRouter(cfg, hist, cache)

    mock_cand = WallpaperCandidate(
        id="cand_success_1",
        category=WallpaperCategory.SPACE,
        provider_name="MockNASA",
        title="Cosmic Wonder",
        download_url="https://example.com/cosmic.jpg",
        source_url="https://example.com",
    )

    call_counts = {"fetch": 0, "status": []}

    def mock_fetch(category, limit=6):
        call_counts["fetch"] += 1
        return [mock_cand]

    def mock_download(candidate, progress_callback=None):
        temp_img = tmp_path / "temp.jpg"
        return create_mock_image(temp_img)

    monkeypatch.setattr(router, "fetch_candidates", mock_fetch)
    monkeypatch.setattr(router, "download_candidate", mock_download)

    def status_cb(msg, attempt, total):
        call_counts["status"].append(attempt)

    meta, err = router.acquire_wallpaper_for_category(
        WallpaperCategory.SPACE,
        mode="Fill",
        status_callback=status_cb,
    )

    assert meta is not None
    assert err is None
    assert meta.image_id == "cand_success_1"
    # Immediate success on attempt 1 -> only 1 fetch call and attempt 1
    assert call_counts["fetch"] == 1
    assert call_counts["status"] == [1]


def test_retry_recovery_on_attempt_3(tmp_path, monkeypatch):
    cfg = AppConfig(custom_cache_dir=str(tmp_path / "cache"), max_fetch_retries=5)
    hist = HistoryTracker(cfg)
    cache = CacheManager(cfg)
    router = ProviderRouter(cfg, hist, cache)

    attempts_log = []
    attempt_counter = {"count": 0}

    def mock_fetch(category, limit=6):
        attempt_counter["count"] += 1
        return [
            WallpaperCandidate(
                id=f"cand_{attempt_counter['count']}",
                category=WallpaperCategory.NATURE,
                provider_name="MockProvider",
                title=f"Nature View {attempt_counter['count']}",
                download_url=f"https://example.com/nature_{attempt_counter['count']}.jpg",
                source_url="https://example.com",
            )
        ]

    def mock_download(candidate, progress_callback=None):
        # Fail attempts 1 and 2, succeed on attempt 3
        if "cand_1" in candidate.id or "cand_2" in candidate.id:
            return None
        temp_img = tmp_path / "temp_recovered.jpg"
        return create_mock_image(temp_img)

    monkeypatch.setattr(router, "fetch_candidates", mock_fetch)
    monkeypatch.setattr(router, "download_candidate", mock_download)
    # Patch time.sleep to run instantly during test
    monkeypatch.setattr("time.sleep", lambda s: None)

    def status_cb(msg, attempt, total):
        attempts_log.append(attempt)

    meta, err = router.acquire_wallpaper_for_category(
        WallpaperCategory.NATURE,
        mode="Fill",
        status_callback=status_cb,
    )

    assert meta is not None
    assert err is None
    assert meta.image_id == "cand_3"
    # Status callback logged attempts 1, 2, and 3
    assert 1 in attempts_log
    assert 2 in attempts_log
    assert 3 in attempts_log


def test_retry_exhaustion_5_attempts(tmp_path, monkeypatch):
    cfg = AppConfig(custom_cache_dir=str(tmp_path / "cache"), max_fetch_retries=5)
    hist = HistoryTracker(cfg)
    cache = CacheManager(cfg)
    router = ProviderRouter(cfg, hist, cache)

    attempts_seen = []

    def mock_fetch(category, limit=6):
        return [
            WallpaperCandidate(
                id="failing_cand",
                category=WallpaperCategory.ART,
                provider_name="MockProvider",
                title="Failing Painting",
                download_url="https://example.com/broken.jpg",
                source_url="https://example.com",
            )
        ]

    # Download always fails
    monkeypatch.setattr(router, "fetch_candidates", mock_fetch)
    monkeypatch.setattr(router, "download_candidate", lambda c, p=None: None)
    monkeypatch.setattr("time.sleep", lambda s: None)

    def status_cb(msg, attempt, total):
        attempts_seen.append(attempt)

    meta, err = router.acquire_wallpaper_for_category(
        WallpaperCategory.ART,
        mode="Fill",
        status_callback=status_cb,
        max_retries=5,
    )

    assert meta is None
    assert "after 5 attempts" in err
    # Verifies all 5 attempts were executed
    assert 1 in attempts_seen
    assert 2 in attempts_seen
    assert 3 in attempts_seen
    assert 4 in attempts_seen
    assert 5 in attempts_seen
