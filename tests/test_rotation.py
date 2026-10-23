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


def test_history_tracker_reload(tmp_path: Path):
    cfg = AppConfig(custom_cache_dir=str(tmp_path / "cache"))
    tracker1 = HistoryTracker(cfg)
    tracker2 = HistoryTracker(cfg)

    # Tracker 1 records an image
    tracker1.record(item_id="img_sync_1", category="Space", title="Galaxy")
    assert len(tracker1.records) == 1

    # Tracker 2 before reload has 0 records
    assert len(tracker2.records) == 0

    # Tracker 2 after reload has 1 record
    reloaded = tracker2.reload()
    assert len(reloaded) == 1
    assert reloaded[0].image_id == "img_sync_1"


def test_scheduler_reloads_history_on_check(tmp_path: Path):
    cfg = AppConfig(custom_cache_dir=str(tmp_path / "cache"), rotation_interval_minutes=30)
    tracker = HistoryTracker(cfg)
    daemon = WallpaperRotationDaemon(config=cfg, history=tracker)

    # Initially no records -> due immediately
    assert daemon.is_rotation_due() is True

    # Another process/tracker writes a record
    other_tracker = HistoryTracker(cfg)
    other_tracker.record(item_id="img_recent", category="Space")

    # daemon.is_rotation_due() should reload history and determine it is NOT due
    assert daemon.is_rotation_due() is False
    assert daemon.get_seconds_until_next_rotation() > 1700.0


def test_auto_rotate_preserves_staged_preview(tmp_path: Path, monkeypatch):
    """When a scheduled rotation completes, an active manual staged preview MUST NOT be overwritten."""
    from login_wallpaper_selector.ui.dialog import WallpaperSelectorDialog

    monkeypatch.setattr(WallpaperSelectorDialog, "_init_window", lambda self: None)
    cfg = AppConfig(custom_cache_dir=str(tmp_path / "cache"), rotation_enabled=True)
    dialog = WallpaperSelectorDialog(config=cfg)

    staged_meta = WallpaperMetadata(
        image_id="manual_search_1",
        category="Space",
        provider="Wallhaven",
        source_url="https://example.com/source",
        download_url="https://example.com/image.jpg",
        local_path=str(tmp_path / "manual.jpg"),
        sha256="manual_sha",
        title="Manual Nebula Preview",
        creator="Artist",
        license="CC0",
        license_url=None,
        attribution_required=False,
        attribution_text="",
        width=1920,
        height=1080,
        aspect_ratio=1.778,
        mode="Fill",
    )
    dialog.staged_metadata = staged_meta

    rotated_meta = WallpaperMetadata(
        image_id="auto_rotated_2",
        category="Nature",
        provider="Unsplash",
        source_url="https://example.com/source",
        download_url="https://example.com/image2.jpg",
        local_path=str(tmp_path / "auto.jpg"),
        sha256="auto_sha",
        title="Auto Forest",
        creator="Artist2",
        license="CC0",
        license_url=None,
        attribution_required=False,
        attribution_text="",
        width=1920,
        height=1080,
        aspect_ratio=1.778,
        mode="Fill",
    )

    # Mock daemon rotate_now to return rotated_meta
    monkeypatch.setattr(
        WallpaperRotationDaemon,
        "rotate_now",
        lambda self, *a, **kw: (rotated_meta, None),
    )

    # Trigger scheduled auto-rotate
    status_messages = []
    dialog.set_status = lambda msg, **kw: status_messages.append(msg)

    # Perform background rotation worker synchronously for testing
    dialog._perform_scheduled_auto_rotate()
    # Wait for thread to complete
    time.sleep(0.3)

    # CRITICAL ASSERTION: The staged preview must NOT be replaced!
    assert dialog.staged_metadata is not None
    assert dialog.staged_metadata.image_id == "manual_search_1"
    assert dialog.staged_metadata.title == "Manual Nebula Preview"
    assert any("preserved" in m.lower() for m in status_messages)


def test_auto_rotate_updates_preview_when_no_staged_preview(tmp_path: Path, monkeypatch):
    """When no manual preview is staged, scheduled auto-rotation updates current_metadata."""
    from login_wallpaper_selector.ui.dialog import WallpaperSelectorDialog

    monkeypatch.setattr(WallpaperSelectorDialog, "_init_window", lambda self: None)
    cfg = AppConfig(custom_cache_dir=str(tmp_path / "cache"), rotation_enabled=True)
    dialog = WallpaperSelectorDialog(config=cfg)
    dialog.staged_metadata = None

    rotated_meta = WallpaperMetadata(
        image_id="auto_rotated_3",
        category="Nature",
        provider="Unsplash",
        source_url="https://example.com/source",
        download_url="https://example.com/image3.jpg",
        local_path=str(tmp_path / "auto3.jpg"),
        sha256="auto_sha_3",
        title="Auto Mountain",
        creator="Artist3",
        license="CC0",
        license_url=None,
        attribution_required=False,
        attribution_text="",
        width=1920,
        height=1080,
        aspect_ratio=1.778,
        mode="Fill",
    )

    monkeypatch.setattr(
        WallpaperRotationDaemon,
        "rotate_now",
        lambda self, *a, **kw: (rotated_meta, None),
    )
    dialog._update_preview_and_attribution = lambda meta, staged=False: None
    dialog.set_status = lambda *a, **kw: None

    dialog._perform_scheduled_auto_rotate()
    time.sleep(0.3)

    assert dialog.current_metadata is not None
    assert dialog.current_metadata.image_id == "auto_rotated_3"


def test_on_apply_staged_clears_staged_metadata(tmp_path: Path, monkeypatch):
    """Applying a staged preview clears staged_metadata and commits current_metadata."""
    from login_wallpaper_selector.ui.dialog import WallpaperSelectorDialog

    monkeypatch.setattr(WallpaperSelectorDialog, "_init_window", lambda self: None)
    cfg = AppConfig(custom_cache_dir=str(tmp_path / "cache"))
    dialog = WallpaperSelectorDialog(config=cfg)

    img_file = tmp_path / "test_apply.jpg"
    img = Image.new("RGB", (100, 100), color=(10, 20, 30))
    img.save(img_file)

    staged_meta = WallpaperMetadata(
        image_id="stage_to_apply",
        category="Space",
        provider="Wallhaven",
        source_url="https://example.com/source",
        download_url="https://example.com/image.jpg",
        local_path=str(img_file),
        sha256="dummy_sha",
        title="To Apply",
        creator="Artist",
        license="CC0",
        license_url=None,
        attribution_required=False,
        attribution_text="",
        width=100,
        height=100,
        aspect_ratio=1.0,
        mode="Fill",
    )
    dialog.staged_metadata = staged_meta
    dialog.set_status = lambda *a, **kw: None
    monkeypatch.setattr(dialog.adapter, "set_wallpaper", lambda p, mode: True)

    class DummyVar:
        def get(self):
            return "Fill"
    dialog.mode_var = DummyVar()

    dialog.on_apply_staged()
    time.sleep(0.2)

    assert dialog.current_metadata == staged_meta
    assert dialog.staged_metadata is None


def test_window_close_minimizes_when_rotation_enabled(tmp_path: Path, monkeypatch):
    from login_wallpaper_selector.ui.dialog import WallpaperSelectorDialog

    monkeypatch.setattr(WallpaperSelectorDialog, "_init_window", lambda self: None)
    cfg = AppConfig(custom_cache_dir=str(tmp_path / "cache"), rotation_enabled=True)
    dialog = WallpaperSelectorDialog(config=cfg)

    minimized = []
    quit_called = []
    monkeypatch.setattr(dialog, "_minimize_to_tray", lambda: minimized.append(True))
    monkeypatch.setattr(dialog, "quit_app", lambda: quit_called.append(True))

    dialog.on_close_window()
    assert len(minimized) == 1
    assert len(quit_called) == 0


def test_window_close_quits_when_rotation_disabled(tmp_path: Path, monkeypatch):
    from login_wallpaper_selector.ui.dialog import WallpaperSelectorDialog

    monkeypatch.setattr(WallpaperSelectorDialog, "_init_window", lambda self: None)
    cfg = AppConfig(custom_cache_dir=str(tmp_path / "cache"), rotation_enabled=False)
    dialog = WallpaperSelectorDialog(config=cfg)

    minimized = []
    quit_called = []
    monkeypatch.setattr(dialog, "_minimize_to_tray", lambda: minimized.append(True))
    monkeypatch.setattr(dialog, "quit_app", lambda: quit_called.append(True))

    dialog.on_close_window()
    assert len(minimized) == 0
    assert len(quit_called) == 1


def test_system_tray_manager_callbacks():
    from login_wallpaper_selector.ui.tray import SystemTrayManager

    events = []
    mgr = SystemTrayManager(
        on_show=lambda: events.append("show"),
        on_rotate_now=lambda: events.append("rotate"),
        on_quit=lambda: events.append("quit"),
    )

    mgr._handle_show()
    assert "show" in events

    mgr._handle_rotate_now()
    assert "rotate" in events

    mgr._handle_quit()
    assert "quit" in events
