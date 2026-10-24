"""Unit tests for WallpaperGalleryDialog archive and favorites modal."""

from pathlib import Path
from unittest.mock import MagicMock, patch
from PIL import Image
import pytest

from login_wallpaper_selector.core.config import AppConfig
from login_wallpaper_selector.core.models import WallpaperMetadata
from login_wallpaper_selector.core.favorites import FavoritesManager, FavoriteRecord
from login_wallpaper_selector.core.recent_history import RecentWallpaperManager
from login_wallpaper_selector.core.history import HistoryTracker
from login_wallpaper_selector.ui.gallery_dialog import WallpaperGalleryDialog


def _create_test_image(path: Path, width: int = 200, height: int = 120) -> Path:
    img = Image.new("RGB", (width, height), color=(70, 130, 180))
    img.save(path, format="JPEG")
    return path


def _create_sample_metadata(tmp_path: Path, img_id: str, title: str, category: str = "Nature", provider: str = "Wallhaven") -> WallpaperMetadata:
    p = _create_test_image(tmp_path / f"{img_id}.jpg")
    return WallpaperMetadata(
        image_id=img_id,
        category=category,
        provider=provider,
        source_url="https://example.com",
        download_url="https://example.com/img.jpg",
        local_path=str(p),
        sha256="hash123",
        title=title,
        creator="Photographer",
        license="CC0",
        license_url=None,
        attribution_required=False,
        attribution_text=f"By Photographer - {title}",
        width=1920,
        height=1080,
        aspect_ratio=1.778,
        mode="Fill",
    )


@pytest.fixture
def mock_gallery(monkeypatch, tmp_path: Path):
    """Fixture providing an initialized WallpaperGalleryDialog with UI building mocked out."""
    def _mock_build(self):
        self.scroll_frame = MagicMock()
        self.status_lbl = MagicMock()
        self.search_entry = MagicMock()

    monkeypatch.setattr(WallpaperGalleryDialog, "_build_widgets", _mock_build)
    monkeypatch.setattr("login_wallpaper_selector.ui.gallery_dialog.ctk.CTkFont", MagicMock())
    monkeypatch.setattr("login_wallpaper_selector.ui.gallery_dialog.ctk.CTkLabel", MagicMock())
    monkeypatch.setattr("login_wallpaper_selector.ui.gallery_dialog.ctk.CTkButton", MagicMock())
    monkeypatch.setattr("login_wallpaper_selector.ui.gallery_dialog.ctk.CTkFrame", MagicMock())
    monkeypatch.setattr("login_wallpaper_selector.ui.gallery_dialog.ctk.CTkImage", MagicMock())
    mock_toplevel = MagicMock()
    monkeypatch.setattr("login_wallpaper_selector.ui.gallery_dialog.ctk.CTkToplevel", mock_toplevel)
    monkeypatch.setattr("login_wallpaper_selector.ui.gallery_dialog.tk.Toplevel", mock_toplevel)

    cfg = AppConfig(custom_cache_dir=str(tmp_path))
    fav_mgr = FavoritesManager(config=cfg)
    rec_mgr = RecentWallpaperManager(config=cfg, max_items=10)
    hist_tracker = HistoryTracker(config=cfg)

    parent = MagicMock()
    on_apply = MagicMock()
    on_fav_toggle = MagicMock()

    dialog = WallpaperGalleryDialog(
        parent=parent,
        config=cfg,
        favorites_mgr=fav_mgr,
        recent_mgr=rec_mgr,
        history_tracker=hist_tracker,
        on_apply=on_apply,
        on_favorite_toggled=on_fav_toggle,
    )

    return dialog, fav_mgr, rec_mgr, hist_tracker, on_apply, on_fav_toggle, tmp_path, mock_toplevel


def test_gallery_init(mock_gallery):
    dialog = mock_gallery[0]
    assert dialog._current_tab == "history"
    assert dialog._search_query == ""
    assert isinstance(dialog.cards_data, list)


def test_gallery_collect_history_items(mock_gallery):
    dialog, fav_mgr, rec_mgr, _, _, _, tmp_path, _ = mock_gallery

    meta1 = _create_sample_metadata(tmp_path, "img_1", "Alpine Peaks", "Mountains", "Wallhaven")
    meta2 = _create_sample_metadata(tmp_path, "img_2", "Cosmic Nebula", "Space", "Unsplash")

    rec_mgr.add(meta1)
    rec_mgr.add(meta2)
    fav_mgr.toggle_favorite(meta2)  # Mark meta2 as favorite

    dialog._current_tab = "history"
    items = dialog._collect_items()

    assert len(items) == 2
    titles = [it["title"] for it in items]
    assert "Alpine Peaks" in titles
    assert "Cosmic Nebula" in titles

    nebula_item = next(it for it in items if it["title"] == "Cosmic Nebula")
    assert nebula_item["is_fav"] is True

    alpine_item = next(it for it in items if it["title"] == "Alpine Peaks")
    assert alpine_item["is_fav"] is False


def test_gallery_collect_favorites_items(mock_gallery):
    dialog, fav_mgr, _, _, _, _, tmp_path, _ = mock_gallery

    meta1 = _create_sample_metadata(tmp_path, "fav_1", "Golden Gate Bridge", "Architecture", "Pexels")
    meta2 = _create_sample_metadata(tmp_path, "fav_2", "Tropical Sunset", "Beach", "Unsplash")

    fav_mgr.toggle_favorite(meta1)
    fav_mgr.toggle_favorite(meta2)

    dialog._current_tab = "favorites"
    items = dialog._collect_items()

    assert len(items) == 2
    for it in items:
        assert it["is_fav"] is True
    titles = [it["title"] for it in items]
    assert "Golden Gate Bridge" in titles
    assert "Tropical Sunset" in titles


def test_gallery_tab_switch(mock_gallery):
    dialog = mock_gallery[0]

    dialog._refresh_gallery = MagicMock()

    dialog._on_tab_change("⭐ Saved Favorites")
    assert dialog._current_tab == "favorites"
    dialog._refresh_gallery.assert_called_once()

    dialog._on_tab_change("🕒 Recent History")
    assert dialog._current_tab == "history"
    assert dialog._refresh_gallery.call_count == 2


def test_gallery_search_filter(mock_gallery):
    dialog = mock_gallery[0]

    dialog.cards_data = [
        {"id": "1", "title": "Mighty Mountains", "category": "Landscape", "provider": "Wallhaven", "path": "p1", "is_fav": False},
        {"id": "2", "title": "Cyberpunk City", "category": "Sci-Fi", "provider": "Wallhaven", "path": "p2", "is_fav": False},
        {"id": "3", "title": "Deep Space Nebula", "category": "Space", "provider": "NASA", "path": "p3", "is_fav": True},
    ]

    dialog._create_card = MagicMock()

    # Search for "Space"
    dialog.search_entry.get.return_value = "space"
    dialog._on_search_change()
    assert dialog._search_query == "space"
    # Should render 1 card (Deep Space Nebula)
    assert dialog._create_card.call_count == 1
    call_item = dialog._create_card.call_args[0][1]
    assert call_item["title"] == "Deep Space Nebula"

    # Search for "Wallhaven" (provider filter)
    dialog._create_card.reset_mock()
    dialog.search_entry.get.return_value = "wallhaven"
    dialog._on_search_change()
    assert dialog._create_card.call_count == 2

    # Clear search
    dialog._create_card.reset_mock()
    dialog._clear_search()
    assert dialog._search_query == ""
    assert dialog._create_card.call_count == 3


def test_gallery_apply_item(mock_gallery):
    dialog, _, _, _, on_apply, _, tmp_path, _ = mock_gallery

    meta = _create_sample_metadata(tmp_path, "apply_1", "Autumn Forest")
    item = {
        "id": meta.image_id,
        "title": meta.title,
        "category": meta.category,
        "provider": meta.provider,
        "path": meta.local_path,
        "is_fav": False,
        "raw": meta,
    }

    dialog._apply_item(item)
    on_apply.assert_called_once_with(meta)
    dialog.status_lbl.configure.assert_called()


def test_gallery_toggle_favorite(mock_gallery):
    dialog, fav_mgr, _, _, _, on_fav_toggle, tmp_path, _ = mock_gallery

    meta = _create_sample_metadata(tmp_path, "fav_toggle_1", "Ocean Waves")
    item = {
        "id": meta.image_id,
        "title": meta.title,
        "category": meta.category,
        "provider": meta.provider,
        "path": meta.local_path,
        "is_fav": False,
        "raw": meta,
    }

    dialog._refresh_gallery = MagicMock()

    dialog._toggle_favorite(item)

    assert item["is_fav"] is True
    assert fav_mgr.is_favorite(meta.image_id) is True
    on_fav_toggle.assert_called_once()
    dialog._refresh_gallery.assert_called_once()

    # Toggle off
    dialog._toggle_favorite(item)
    assert item["is_fav"] is False
    assert fav_mgr.is_favorite(meta.image_id) is False


def test_gallery_thumbnail_caching(mock_gallery):
    dialog, _, _, _, _, _, tmp_path, _ = mock_gallery

    img_path = _create_test_image(tmp_path / "thumb_test.jpg", width=120, height=80)
    thumb1 = dialog._get_thumbnail_image(str(img_path))
    assert thumb1 is not None
    assert str(img_path) in dialog._thumbnail_cache

    # Subsequent retrieval uses cache
    thumb2 = dialog._get_thumbnail_image(str(img_path))
    assert thumb1 is thumb2


def test_gallery_lightbox(mock_gallery):
    dialog, _, _, _, on_apply, _, tmp_path, mock_toplevel = mock_gallery
    mock_lb_win = MagicMock()
    mock_toplevel.return_value = mock_lb_win

    meta = _create_sample_metadata(tmp_path, "lb_1", "Aurora Lights")
    item = {
        "id": meta.image_id,
        "title": meta.title,
        "category": meta.category,
        "provider": meta.provider,
        "path": meta.local_path,
        "is_fav": False,
        "raw": meta,
    }

    dialog._open_lightbox(item)
    mock_toplevel.assert_called()
    mock_lb_win.title.assert_called_with("Preview: Aurora Lights")
