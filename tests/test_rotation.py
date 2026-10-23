"""Tests for Smart Wallpaper Rotation and Scheduler Daemon."""

import pytest
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from PIL import Image

from login_wallpaper_selector.core.config import AppConfig
from login_wallpaper_selector.core.models import (
    WallpaperCategory,
    WallpaperCandidate,
    WallpaperMetadata,
    HistoryRecord,
)
from login_wallpaper_selector.core.history import HistoryTracker
from login_wallpaper_selector.core.cache import CacheManager
from login_wallpaper_selector.providers.router import ProviderRouter
from login_wallpaper_selector.core.scheduler import (
    parse_interval_minutes,
    WallpaperRotationDaemon,
)


def test_parse_interval_minutes():
    assert parse_interval_minutes(45) == 45
    assert parse_interval_minutes("30m") == 30
    assert parse_interval_minutes("30min") == 30
    assert parse_interval_minutes("1h") == 60
    assert parse_interval_minutes("3h") == 180
    assert parse_interval_minutes("daily") == 1440
    assert parse_interval_minutes("24h") == 1440
    assert parse_interval_minutes("unknown") == 180


def test_rotation_due_calculation(tmp_path: Path):
    cfg = AppConfig(
        custom_cache_dir=str(tmp_path / "cache"),
        rotation_interval_minutes=60,
    )
    hist = HistoryTracker(cfg)
    daemon = WallpaperRotationDaemon(config=cfg, history=hist)

    # 1. No history records -> due immediately
    assert daemon.is_rotation_due() is True
    assert daemon.get_seconds_until_next_rotation() == 0.0

    # 2. Record from 10 minutes ago -> not due
    recent_time = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    hist.records.append(HistoryRecord(image_id="recent_1", applied_at=recent_time))
    assert daemon.is_rotation_due() is False
    assert daemon.get_seconds_until_next_rotation() > 2500.0  # ~50 mins remaining

    # 3. Record from 70 minutes ago -> interval of 60m has elapsed -> due
    old_time = (datetime.now(timezone.utc) - timedelta(minutes=70)).isoformat()
    hist.records = [HistoryRecord(image_id="old_1", applied_at=old_time)]
    assert daemon.is_rotation_due() is True
    assert daemon.get_seconds_until_next_rotation() == 0.0


def test_rotate_now_execution(tmp_path: Path, monkeypatch):
    cfg = AppConfig(custom_cache_dir=str(tmp_path / "cache"), rotation_interval_minutes=60)
    hist = HistoryTracker(cfg)
    cache = CacheManager(cfg)
    router = ProviderRouter(cfg, hist, cache)
    daemon = WallpaperRotationDaemon(cfg, hist, cache, router)

    # Mock acquire_wallpaper_for_category
    mock_meta = WallpaperMetadata(
        image_id="rotated_cand_1",
        category="Nature",
        provider="Wallhaven",
        source_url="https://example.com/source",
        download_url="https://example.com/image.jpg",
        local_path=str(tmp_path / "mock_wallpaper.jpg"),
        sha256="1234567890abcdef",
        title="Rotated Vista",
        creator="MockArtist",
        license="CC0",
        license_url=None,
        attribution_required=False,
        attribution_text="",
        width=1920,
        height=1080,
        aspect_ratio=1.778,
        mode="Fill",
    )

    # Create dummy local file so adapter check passes
    img = Image.new("RGB", (100, 100), color=(50, 100, 150))
    img.save(Path(mock_meta.local_path))

    monkeypatch.setattr(router, "acquire_wallpaper_for_category", lambda *a, **kw: (mock_meta, None))
    monkeypatch.setattr(daemon.adapter, "set_wallpaper", lambda p, mode: True)

    meta, err = daemon.rotate_now()
    assert err is None
    assert meta is not None
    assert meta.image_id == "rotated_cand_1"
    assert meta.title == "Rotated Vista"


def test_daemon_run_loop_stop(tmp_path: Path, monkeypatch):
    cfg = AppConfig(
        custom_cache_dir=str(tmp_path / "cache"),
        rotation_enabled=False,
    )
    hist = HistoryTracker(cfg)
    daemon = WallpaperRotationDaemon(cfg, hist)

    stop_ev = threading.Event()
    logs = []

    # Run loop in thread and signal stop immediately
    def _run():
        daemon.run_loop(stop_event=stop_ev, check_interval_sec=1, log_fn=logs.append)

    th = threading.Thread(target=_run)
    th.start()
    time.sleep(0.1)
    stop_ev.set()
    th.join(timeout=2.0)

    assert not th.is_alive()
    assert any("started" in l for l in logs)
    assert any("stopped" in l for l in logs)
