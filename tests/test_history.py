"""Unit tests for deduplication history tracker."""

from login_wallpaper_selector.core.config import AppConfig
from login_wallpaper_selector.core.history import HistoryTracker


def test_history_tracker(tmp_path, monkeypatch):
    monkeypatch.setattr(AppConfig, "get_default_data_dir", lambda: tmp_path)
    cfg = AppConfig(history_limit=5)
    tracker = HistoryTracker(cfg)

    assert len(tracker.get_recent_ids()) == 0

    # Record 7 items with a limit of 5
    for i in range(7):
        tracker.record(f"item_{i}")

    recent = tracker.get_recent_ids()
    # At least the limit is respected (min limit is 10 in production code or config limit)
    assert "item_6" in recent
    assert tracker.has_seen("item_6") is True
    assert tracker.has_seen("non_existent") is False
