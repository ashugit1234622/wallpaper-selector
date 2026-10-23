"""Unit tests for SearchHistoryManager persistence, auto-healing, and suggestions."""

import json
from pathlib import Path
import pytest

from login_wallpaper_selector.core.config import AppConfig
from login_wallpaper_selector.core.models import WallpaperCategory, WallpaperMetadata
from login_wallpaper_selector.core.search_history import SearchHistoryManager, SearchRecord


def _make_dummy_meta(title: str = "Test") -> WallpaperMetadata:
    return WallpaperMetadata(
        image_id="dummy_1",
        category="Space",
        provider="test",
        source_url="http://example.com",
        download_url="http://example.com/img.jpg",
        local_path="C:/tmp/test.jpg",
        sha256="",
        title=title,
        creator="Artist",
        license="CC0",
        license_url=None,
        attribution_required=False,
        attribution_text="Test",
        width=1920,
        height=1080,
        aspect_ratio=1.778,
        mode="Fill",
    )


def test_search_history_recording(tmp_path: Path):
    cfg = AppConfig.load()
    cfg.custom_cache_dir = str(tmp_path)
    mgr = SearchHistoryManager(cfg)

    # Record successful search
    meta = _make_dummy_meta("Supernova Explosion")
    rec = mgr.record_search("Supernova", "Space", success=True, metadata=meta)
    assert rec.keyword == "Supernova"
    assert rec.successful is True
    assert rec.image_id == "dummy_1"
    assert rec.title == "Supernova Explosion"

    # Record failed search
    mgr.record_search("NonexistentXYZQuery", "Nature", success=False)
    rec_fail = mgr.get_record("NonexistentXYZQuery")
    assert rec_fail is not None
    assert rec_fail.successful is False


def test_suggestions_prioritize_recent_successes(tmp_path: Path):
    cfg = AppConfig.load()
    cfg.custom_cache_dir = str(tmp_path)
    mgr = SearchHistoryManager(cfg)

    mgr.record_search("James Webb", "Space", success=True, metadata=_make_dummy_meta("JWST"))
    mgr.record_search("Cyberpunk City", "Space", success=True, metadata=_make_dummy_meta("Cyberpunk"))

    suggestions = mgr.get_suggestions(WallpaperCategory.SPACE, limit=4)
    # The recent successful searches should be at the front
    assert "Cyberpunk City" in suggestions[:2]
    assert "James Webb" in suggestions[:2]


def test_corrupt_json_auto_healing(tmp_path: Path):
    cfg = AppConfig.load()
    cfg.custom_cache_dir = str(tmp_path)
    history_file = tmp_path / "search_history.json"
    history_file.write_text("CORRUPTED_JSON{{{bad_format...", encoding="utf-8")

    mgr = SearchHistoryManager(cfg)
    # Should not raise exception and should auto-heal to empty
    assert len(mgr.records) == 0

    # Recording a new search should cleanly overwrite corrupt file
    mgr.record_search("Black Hole", "Space", success=True, metadata=_make_dummy_meta("Black Hole"))
    assert history_file.exists()
    data = json.loads(history_file.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert len(data) == 1


def test_clear_search_history(tmp_path: Path):
    cfg = AppConfig.load()
    cfg.custom_cache_dir = str(tmp_path)
    mgr = SearchHistoryManager(cfg)

    mgr.record_search("Andromeda", "Space", success=True)
    assert len(mgr.records) == 1

    mgr.clear_history()
    assert len(mgr.records) == 0
    assert len(mgr.get_recent_searches()) == 0
