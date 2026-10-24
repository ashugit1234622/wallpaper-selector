"""Unit tests for RecentWallpaperManager and ◀ / ▶ history navigation."""

import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from login_wallpaper_selector.core.models import WallpaperMetadata
from login_wallpaper_selector.core.config import AppConfig
from login_wallpaper_selector.core.recent_history import RecentWallpaperManager
from login_wallpaper_selector.ui.dialog import WallpaperSelectorDialog


def _create_dummy_wallpaper_file(tmp_path: Path, name: str) -> Path:
    f = tmp_path / name
    f.write_bytes(b"dummy image bytes")
    return f


def _create_sample_meta(img_id: str, file_path: Path, title: str = "") -> WallpaperMetadata:
    return WallpaperMetadata(
        image_id=img_id,
        category="Nature",
        provider="Wallhaven",
        source_url="https://example.com",
        download_url="https://example.com/download.jpg",
        local_path=str(file_path),
        sha256="abc123",
        title=title or f"Wallpaper {img_id}",
        creator="Artist",
        license="CC0",
        license_url=None,
        attribution_required=False,
        attribution_text=f"By Artist - {img_id}",
        width=1920,
        height=1080,
        aspect_ratio=1.778,
        mode="Fill",
    )


def test_metadata_roundtrip(tmp_path: Path):
    f = _create_dummy_wallpaper_file(tmp_path, "wall1.jpg")
    meta = _create_sample_meta("w1", f, "Mountain Sunset")
    d = meta.to_dict()
    restored = WallpaperMetadata.from_dict(d)

    assert restored.image_id == "w1"
    assert restored.title == "Mountain Sunset"
    assert restored.local_path == str(f)
    assert restored.width == 1920
    assert restored.aspect_ratio == 1.778


def test_recent_manager_add_and_fifo_limit(tmp_path: Path):
    cfg = AppConfig(custom_cache_dir=str(tmp_path))
    mgr = RecentWallpaperManager(config=cfg, max_items=5)

    files = [_create_dummy_wallpaper_file(tmp_path, f"wall_{i}.jpg") for i in range(7)]
    metas = [_create_sample_meta(f"id_{i}", files[i], f"Title {i}") for i in range(7)]

    # Add 4 items
    for i in range(4):
        mgr.add(metas[i])
    assert len(mgr.get_items()) == 4
    assert [m.image_id for m in mgr.get_items()] == ["id_0", "id_1", "id_2", "id_3"]

    # Add 5th item
    mgr.add(metas[4])
    assert len(mgr.get_items()) == 5

    # Add 6th item -> should evict id_0 (oldest)
    mgr.add(metas[5])
    assert len(mgr.get_items()) == 5
    assert [m.image_id for m in mgr.get_items()] == ["id_1", "id_2", "id_3", "id_4", "id_5"]

    # Add 7th item -> should evict id_1
    mgr.add(metas[6])
    assert len(mgr.get_items()) == 5
    assert [m.image_id for m in mgr.get_items()] == ["id_2", "id_3", "id_4", "id_5", "id_6"]


def test_recent_manager_readd_moves_to_end(tmp_path: Path):
    cfg = AppConfig(custom_cache_dir=str(tmp_path))
    mgr = RecentWallpaperManager(config=cfg, max_items=5)

    f1 = _create_dummy_wallpaper_file(tmp_path, "w1.jpg")
    f2 = _create_dummy_wallpaper_file(tmp_path, "w2.jpg")
    f3 = _create_dummy_wallpaper_file(tmp_path, "w3.jpg")

    m1 = _create_sample_meta("id1", f1)
    m2 = _create_sample_meta("id2", f2)
    m3 = _create_sample_meta("id3", f3)

    mgr.add(m1)
    mgr.add(m2)
    mgr.add(m3)
    assert [m.image_id for m in mgr.get_items()] == ["id1", "id2", "id3"]

    # Re-add m1 -> should move to end
    mgr.add(m1)
    assert [m.image_id for m in mgr.get_items()] == ["id2", "id3", "id1"]


def test_recent_manager_file_validation(tmp_path: Path):
    cfg = AppConfig(custom_cache_dir=str(tmp_path))
    mgr = RecentWallpaperManager(config=cfg, max_items=5)

    # Missing file cannot be added
    ghost_meta = _create_sample_meta("ghost", tmp_path / "non_existent.jpg")
    mgr.add(ghost_meta)
    assert len(mgr.get_items()) == 0

    # If file deleted later, get_items filters it out
    f1 = _create_dummy_wallpaper_file(tmp_path, "temp.jpg")
    m1 = _create_sample_meta("t1", f1)
    mgr.add(m1)
    assert len(mgr.get_items()) == 1

    f1.unlink()
    assert len(mgr.get_items()) == 0


def test_recent_manager_disk_persistence(tmp_path: Path):
    cfg = AppConfig(custom_cache_dir=str(tmp_path))
    mgr1 = RecentWallpaperManager(config=cfg, max_items=5)

    f1 = _create_dummy_wallpaper_file(tmp_path, "p1.jpg")
    f2 = _create_dummy_wallpaper_file(tmp_path, "p2.jpg")
    mgr1.add(_create_sample_meta("p1", f1, "Persisted 1"))
    mgr1.add(_create_sample_meta("p2", f2, "Persisted 2"))

    assert (tmp_path / "recent_previews.json").exists()

    # Create new manager instance from same directory
    mgr2 = RecentWallpaperManager(config=cfg, max_items=5)
    items = mgr2.get_items()
    assert len(items) == 2
    assert items[0].title == "Persisted 1"
    assert items[1].title == "Persisted 2"


def test_dialog_history_navigation_buttons(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(WallpaperSelectorDialog, "_init_window", lambda self: setattr(self, "root", MagicMock()))
    monkeypatch.setattr(WallpaperSelectorDialog, "_build_widgets", lambda self: None)

    cfg = AppConfig(custom_cache_dir=str(tmp_path))
    dialog = WallpaperSelectorDialog(config=cfg)

    dialog.prev_hist_btn = MagicMock()
    dialog.next_hist_btn = MagicMock()
    dialog.attrib_lbl = MagicMock()
    dialog.preview_label = MagicMock()
    dialog._render_preview_image = MagicMock()

    # Initial state with empty history
    dialog._update_history_nav_buttons()
    dialog.prev_hist_btn.configure.assert_called_with(state="disabled", fg_color="transparent", text_color="#6b6b6b")
    dialog.next_hist_btn.configure.assert_called_with(state="disabled", fg_color="transparent", text_color="#6b6b6b")

    # Add 1 item
    f1 = _create_dummy_wallpaper_file(tmp_path, "d1.jpg")
    m1 = _create_sample_meta("d1", f1, "Wallpaper One")
    dialog._record_fetched_wallpaper(m1)

    assert dialog._recent_index == 0
    # Single item: neither prev nor next is possible
    dialog.prev_hist_btn.configure.assert_called_with(state="disabled", fg_color="transparent", text_color="#6b6b6b")
    dialog.next_hist_btn.configure.assert_called_with(state="disabled", fg_color="transparent", text_color="#6b6b6b")

    # Add 2nd item
    f2 = _create_dummy_wallpaper_file(tmp_path, "d2.jpg")
    m2 = _create_sample_meta("d2", f2, "Wallpaper Two")
    dialog._record_fetched_wallpaper(m2)

    assert dialog._recent_index == 1
    # At latest item (index 1 of 2): prev is enabled, next is disabled
    dialog.prev_hist_btn.configure.assert_called_with(state="normal", fg_color="#333333", text_color="#f3f3f3")
    dialog.next_hist_btn.configure.assert_called_with(state="disabled", fg_color="transparent", text_color="#6b6b6b")

    # Click Prev
    dialog.on_history_prev()
    assert dialog._recent_index == 0
    assert dialog.staged_metadata.image_id == "d1"
    # At oldest item: prev is disabled, next is enabled
    dialog.prev_hist_btn.configure.assert_called_with(state="disabled", fg_color="transparent", text_color="#6b6b6b")
    dialog.next_hist_btn.configure.assert_called_with(state="normal", fg_color="#333333", text_color="#f3f3f3")

    # Click Next
    dialog.on_history_next()
    assert dialog._recent_index == 1
    assert dialog.staged_metadata.image_id == "d2"
    dialog.prev_hist_btn.configure.assert_called_with(state="normal", fg_color="#333333", text_color="#f3f3f3")
    dialog.next_hist_btn.configure.assert_called_with(state="disabled", fg_color="transparent", text_color="#6b6b6b")


def test_keyboard_navigation_focus_protection(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(WallpaperSelectorDialog, "_init_window", lambda self: setattr(self, "root", MagicMock()))
    monkeypatch.setattr(WallpaperSelectorDialog, "_build_widgets", lambda self: None)

    cfg = AppConfig(custom_cache_dir=str(tmp_path))
    dialog = WallpaperSelectorDialog(config=cfg)

    dialog.on_history_prev = MagicMock()
    dialog.on_history_next = MagicMock()

    # Normal focus (not entry)
    dialog.root.focus_get.return_value = MagicMock()
    dialog._on_key_left()
    dialog.on_history_prev.assert_called_once()

    dialog._on_key_right()
    dialog.on_history_next.assert_called_once()

    # Focus inside a CTkEntry or text input
    class MockEntry:
        pass
    dialog.root.focus_get.return_value = MockEntry()
    dialog.on_history_prev.reset_mock()
    dialog.on_history_next.reset_mock()

    dialog._on_key_left()
    dialog.on_history_prev.assert_not_called()

    dialog._on_key_right()
    dialog.on_history_next.assert_not_called()


def test_dialog_filmstrip_rendering_and_jumping(monkeypatch, tmp_path: Path):
    from PIL import Image

    monkeypatch.setattr(WallpaperSelectorDialog, "_init_window", lambda self: setattr(self, "root", MagicMock()))
    monkeypatch.setattr(WallpaperSelectorDialog, "_build_widgets", lambda self: None)

    cfg = AppConfig(custom_cache_dir=str(tmp_path))
    dialog = WallpaperSelectorDialog(config=cfg)

    dialog.filmstrip_frame = MagicMock()
    dialog.prev_hist_btn = MagicMock()
    dialog.next_hist_btn = MagicMock()
    dialog.attrib_lbl = MagicMock()
    dialog.preview_label = MagicMock()
    dialog._render_preview_image = MagicMock()

    # Create real test images with PIL so thumbnails can be generated
    files = []
    for i in range(3):
        p = tmp_path / f"film_{i}.jpg"
        img = Image.new("RGB", (100, 60), color=(i * 40, i * 40, i * 40))
        img.save(p)
        files.append(p)

    m0 = _create_sample_meta("f0", files[0], "Film 0")
    m1 = _create_sample_meta("f1", files[1], "Film 1")
    m2 = _create_sample_meta("f2", files[2], "Film 2")

    dialog._record_fetched_wallpaper(m0)
    dialog._record_fetched_wallpaper(m1)
    dialog._record_fetched_wallpaper(m2)

    assert len(dialog.filmstrip_buttons) == 3
    assert dialog._recent_index == 2

    # Click on the first thumbnail (index 0)
    dialog.on_select_history_index(0)
    assert dialog._recent_index == 0
    assert dialog.staged_metadata.image_id == "f0"

    # Click on index 1
    dialog.on_select_history_index(1)
    assert dialog._recent_index == 1
    assert dialog.staged_metadata.image_id == "f1"


def test_thumbnail_generation_and_caching(monkeypatch, tmp_path: Path):
    from PIL import Image

    monkeypatch.setattr(WallpaperSelectorDialog, "_init_window", lambda self: setattr(self, "root", MagicMock()))
    monkeypatch.setattr(WallpaperSelectorDialog, "_build_widgets", lambda self: None)

    cfg = AppConfig(custom_cache_dir=str(tmp_path))
    dialog = WallpaperSelectorDialog(config=cfg)

    img_path = tmp_path / "thumb_source.jpg"
    img = Image.new("RGB", (200, 100), color="blue")
    img.save(img_path)

    meta = _create_sample_meta("thumb_test", img_path, "Thumb Test")

    thumb1 = dialog._get_or_create_thumbnail(meta, width=54, height=30)
    assert thumb1 is not None

    cache_key = f"{img_path}_54x30"
    assert cache_key in dialog._thumbnail_cache

    # Second call returns cached thumbnail
    thumb2 = dialog._get_or_create_thumbnail(meta, width=54, height=30)
    assert thumb2 is thumb1


def test_slide_animation_fallback(monkeypatch, tmp_path: Path):
    from PIL import Image

    monkeypatch.setattr(WallpaperSelectorDialog, "_init_window", lambda self: setattr(self, "root", MagicMock()))
    monkeypatch.setattr(WallpaperSelectorDialog, "_build_widgets", lambda self: None)

    cfg = AppConfig(custom_cache_dir=str(tmp_path))
    dialog = WallpaperSelectorDialog(config=cfg)
    dialog.preview_label = MagicMock()

    p1 = tmp_path / "slide1.jpg"
    p2 = tmp_path / "slide2.jpg"
    Image.new("RGB", (300, 150), color="red").save(p1)
    Image.new("RGB", (300, 150), color="green").save(p2)

    m1 = _create_sample_meta("s1", p1, "Slide 1")
    m2 = _create_sample_meta("s2", p2, "Slide 2")

    # In mock root environment, _animate_slide_transition safely finishes without throwing
    dialog._animate_slide_transition(m1, m2, direction="left")
    assert dialog._last_rendered_pil_img is not None
    assert dialog._is_animating_slide is False

    dialog._animate_slide_transition(m2, m1, direction="right")
    assert dialog._last_rendered_pil_img is not None
    assert dialog._is_animating_slide is False

