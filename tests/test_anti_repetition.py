"""Unit tests for the time-based anti-repetition cooldown system."""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from login_wallpaper_selector.core.config import AppConfig
from login_wallpaper_selector.core.history import HistoryTracker
from login_wallpaper_selector.core.models import HistoryRecord


def test_record_and_cooldown(tmp_path):
    cfg = AppConfig(custom_cache_dir=str(tmp_path), anti_repetition_days=14, anti_repetition_enabled=True)
    tracker = HistoryTracker(cfg)

    tracker.record("wallpaper_123", category="Space", sha256="abc123hash", title="Hubble Deep Field")

    assert tracker.is_in_cooldown("wallpaper_123") is True
    assert tracker.is_in_cooldown("unknown_id") is False
    assert tracker.is_in_cooldown("other_id", sha256="abc123hash") is True

    cooldown_ids = tracker.get_cooldown_ids()
    assert "wallpaper_123" in cooldown_ids
    assert "abc123hash" in cooldown_ids


def test_cooldown_expiration(tmp_path):
    cfg = AppConfig(custom_cache_dir=str(tmp_path), anti_repetition_days=14, anti_repetition_enabled=True)
    tracker = HistoryTracker(cfg)

    # Manually inject a record from 20 days ago
    past_date = datetime.now(timezone.utc) - timedelta(days=20)
    tracker._records.append(
        HistoryRecord(
            image_id="old_wallpaper",
            applied_at=past_date.isoformat(),
            category="Nature",
            sha256="oldhash",
            title="Old Mountain",
        )
    )
    tracker._save()

    # With 14-day cooldown, 20 days ago is expired
    assert tracker.is_in_cooldown("old_wallpaper", cooldown_days=14) is False
    assert "old_wallpaper" not in tracker.get_cooldown_ids(cooldown_days=14)

    # With 30-day cooldown, 20 days ago is still in cooldown
    assert tracker.is_in_cooldown("old_wallpaper", cooldown_days=30) is True
    assert "old_wallpaper" in tracker.get_cooldown_ids(cooldown_days=30)


def test_anti_repetition_disabled(tmp_path):
    cfg = AppConfig(custom_cache_dir=str(tmp_path), anti_repetition_enabled=False)
    tracker = HistoryTracker(cfg)

    tracker.record("recent_img", category="Art", sha256="some_sha")
    # When disabled, cooldown check returns False
    assert tracker.is_in_cooldown("recent_img") is False
    assert len(tracker.get_cooldown_ids()) == 0


def test_legacy_history_migration(tmp_path):
    history_file = tmp_path / "history.json"
    history_file.write_text(json.dumps(["legacy_id_1", "legacy_id_2"]), encoding="utf-8")

    cfg = AppConfig(custom_cache_dir=str(tmp_path), anti_repetition_days=14)
    tracker = HistoryTracker(cfg)

    assert tracker.has_seen("legacy_id_1") is True
    assert tracker.has_seen("legacy_id_2") is True
    assert tracker.is_in_cooldown("legacy_id_1") is True

    # Check that saving preserved records as objects
    tracker.record("new_id_3")
    data = json.loads(history_file.read_text(encoding="utf-8"))
    assert all(isinstance(x, dict) for x in data)
    assert any(x["image_id"] == "legacy_id_1" for x in data)
    assert any(x["image_id"] == "new_id_3" for x in data)


def test_prune_expired_records(tmp_path):
    cfg = AppConfig(custom_cache_dir=str(tmp_path))
    tracker = HistoryTracker(cfg)

    now = datetime.now(timezone.utc)
    # 100 days ago
    tracker._records.append(
        HistoryRecord(image_id="ancient_img", applied_at=(now - timedelta(days=100)).isoformat())
    )
    # 10 days ago
    tracker._records.append(
        HistoryRecord(image_id="recent_img", applied_at=(now - timedelta(days=10)).isoformat())
    )
    tracker._save()

    pruned = tracker.prune_expired(retention_days=90)
    assert pruned == 1
    assert tracker.has_seen("ancient_img") is False
    assert tracker.has_seen("recent_img") is True


def test_duplicate_record_updates_timestamp(tmp_path):
    cfg = AppConfig(custom_cache_dir=str(tmp_path))
    tracker = HistoryTracker(cfg)

    old_time = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    tracker._records.append(
        HistoryRecord(image_id="repeat_img", applied_at=old_time, title="First View")
    )
    tracker._save()

    # Re-recording should update to current time and not duplicate
    tracker.record("repeat_img", title="Second View")
    assert len(tracker._records) == 1
    assert tracker._records[0].title == "Second View"
    assert tracker._records[0].applied_at != old_time
