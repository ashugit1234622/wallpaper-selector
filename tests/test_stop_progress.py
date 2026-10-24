"""Unit tests for the Stop Progress button and interactive buttons during background progress."""

from unittest.mock import MagicMock, patch
from pathlib import Path
import pytest

from login_wallpaper_selector.core.config import AppConfig
from login_wallpaper_selector.core.models import WallpaperCategory, WallpaperCandidate
from login_wallpaper_selector.providers.router import ProviderRouter
from login_wallpaper_selector.ui.dialog import WallpaperSelectorDialog


@pytest.fixture
def mock_dialog(monkeypatch):
    """Create a headless WallpaperSelectorDialog instance."""
    monkeypatch.setattr(WallpaperSelectorDialog, "_init_window", lambda self: None)
    cfg = AppConfig()
    dialog = WallpaperSelectorDialog(config=cfg)
    dialog.root = None
    return dialog


def test_stop_button_visibility_on_set_busy(mock_dialog):
    """Verify stop_btn packs on set_busy(True) and un-packs on set_busy(False)."""
    dialog = mock_dialog
    dialog.stop_btn = MagicMock()
    dialog.progress_bar = MagicMock()
    dialog.cat_buttons = {c: MagicMock() for c in WallpaperCategory}

    # Set busy: True -> stop_btn should be packed
    dialog.set_busy(True)
    dialog.stop_btn.pack.assert_called()

    # Set busy: False -> stop_btn should be forgotten
    dialog.set_busy(False)
    dialog.stop_btn.pack_forget.assert_called()


def test_on_stop_progress(mock_dialog):
    """Verify on_stop_progress invalidates search ID, resets progress, and clears busy state."""
    dialog = mock_dialog
    dialog.is_busy = True
    dialog._current_search_id = 42
    dialog.progress_bar = MagicMock()
    dialog.set_status = MagicMock()
    dialog.stop_btn = MagicMock()

    dialog.on_stop_progress()

    assert dialog._current_search_id == 43
    assert dialog.is_busy is False
    dialog.progress_bar.set.assert_called_with(0)
    dialog.set_status.assert_called_with("⏹ Search stopped. Ready.")


def test_set_busy_keeps_local_favorites_apply_enabled(mock_dialog):
    """Verify Local Storage, Favorites, and Apply to Desktop remain enabled when is_busy is True."""
    dialog = mock_dialog
    dialog.cat_buttons = {c: MagicMock() for c in WallpaperCategory}
    dialog.search_btn = MagicMock()
    dialog.apply_btn = MagicMock()
    dialog.stop_btn = MagicMock()

    # Simulate a staged preview ready to be applied
    dialog.staged_metadata = MagicMock(image_id="preview_1")
    dialog.current_metadata = MagicMock(image_id="active_0")

    dialog.set_busy(True)

    # Local Storage and Favorites MUST remain normal
    dialog.cat_buttons[WallpaperCategory.LOCAL_STORAGE].configure.assert_called_with(state="normal")
    dialog.cat_buttons[WallpaperCategory.FAVORITES].configure.assert_called_with(state="normal")

    # Apply to Desktop MUST remain normal
    dialog.apply_btn.configure.assert_called_with(state="normal")

    # Regular category buttons and search button MUST be disabled
    dialog.cat_buttons[WallpaperCategory.SPACE].configure.assert_called_with(state="disabled")
    dialog.cat_buttons[WallpaperCategory.NATURE].configure.assert_called_with(state="disabled")
    dialog.search_btn.configure.assert_called_with(state="disabled")


def test_on_select_category_during_busy(mock_dialog):
    """Verify on_select_category allows Local Storage & Favorites while blocking other categories."""
    dialog = mock_dialog
    dialog.is_busy = True
    dialog.current_category = WallpaperCategory.NATURE

    dialog._handle_local_storage = MagicMock()
    dialog._handle_favorites_category = MagicMock()
    dialog._handle_online_category = MagicMock()

    # Clicking Space or Art while busy must be ignored
    dialog.on_select_category(WallpaperCategory.SPACE)
    dialog._handle_online_category.assert_not_called()

    # Clicking Local Storage while busy must invoke _handle_local_storage
    dialog.on_select_category(WallpaperCategory.LOCAL_STORAGE)
    dialog._handle_local_storage.assert_called_once()

    # Clicking Favorites while busy must invoke _handle_favorites_category
    dialog.on_select_category(WallpaperCategory.FAVORITES)
    dialog._handle_favorites_category.assert_called_once()


def test_router_cancel_check_aborts_acquisition(tmp_path):
    """Verify router.acquire_wallpaper_for_category aborts immediately when cancel_check returns True."""
    from login_wallpaper_selector.core.history import HistoryTracker
    from login_wallpaper_selector.core.cache import CacheManager

    cfg = AppConfig(custom_cache_dir=str(tmp_path / "cache"), max_fetch_retries=5)
    hist = HistoryTracker(cfg)
    cache = CacheManager(cfg)
    router = ProviderRouter(cfg, hist, cache)

    meta, err = router.acquire_wallpaper_for_category(
        category=WallpaperCategory.SPACE,
        cancel_check=lambda: True,
    )

    assert meta is None
    assert "cancelled" in err.lower()


def test_download_candidate_cancel_mid_stream(tmp_path):
    """Verify router.download_candidate unlinks partial .part file and returns None when cancelled mid-stream."""
    from login_wallpaper_selector.core.history import HistoryTracker
    from login_wallpaper_selector.core.cache import CacheManager
    from contextlib import contextmanager

    cfg = AppConfig(custom_cache_dir=str(tmp_path / "cache"))
    hist = HistoryTracker(cfg)
    cache = CacheManager(cfg)
    router = ProviderRouter(cfg, hist, cache)

    cand = WallpaperCandidate(
        id="test_cand_1",
        provider_name="Wallhaven",
        source_url="https://example.com/1",
        download_url="https://example.com/1.jpg",
        title="Test Candidate",
    )

    # Simulate chunk generator where cancellation triggers after chunk 1
    chunks = [b"A" * 65536, b"B" * 65536, b"C" * 65536]
    is_cancelled = False

    class MockResponse:
        status_code = 200
        headers = {"Content-Length": str(65536 * 3)}

        def iter_bytes(self, chunk_size=65536):
            nonlocal is_cancelled
            for i, chunk in enumerate(chunks):
                if i == 1:
                    is_cancelled = True
                yield chunk

    class MockStreamContext:
        def __enter__(self):
            return MockResponse()
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
        def stream(self, method, url):
            return MockStreamContext()

    with patch("login_wallpaper_selector.providers.router.httpx.Client", MockClient):
        result = router.download_candidate(
            cand,
            cancel_check=lambda: is_cancelled,
        )

    assert result is None
    # Verify no leaked .part files in cache directory
    part_files = list(cache.cache_dir.glob("*.part"))
    assert len(part_files) == 0


def test_apply_staged_during_busy_discard_search(mock_dialog, tmp_path):
    """Verify on_apply_staged when busy with discard=True bumps search ID and applies."""
    dialog = mock_dialog
    dialog.is_busy = True
    dialog._current_search_id = 10
    dialog.mode_var = MagicMock()
    dialog.mode_var.get.return_value = "fill"
    dialog.adapter = MagicMock()
    dialog.adapter.set_wallpaper.return_value = True

    dummy_img = tmp_path / "staged.jpg"
    dummy_img.write_bytes(b"image_data")
    dialog.staged_metadata = MagicMock(local_path=str(dummy_img), title="Staged Pic", image_id="s1")
    dialog.current_metadata = MagicMock(image_id="curr1")
    dialog.history = MagicMock()
    dialog.recent_mgr = MagicMock()
    dialog.set_status = MagicMock()
    dialog._update_history_nav_buttons = MagicMock()
    dialog._update_filmstrip = MagicMock()

    with patch("login_wallpaper_selector.ui.dialog.messagebox.askyesno", return_value=True):
        dialog.on_apply_staged()

    # Bumps search ID to invalidate background search
    assert dialog._current_search_id == 11
    dialog.adapter.set_wallpaper.assert_called_once()


def test_apply_staged_during_busy_keep_search(mock_dialog, tmp_path):
    """Verify on_apply_staged when busy with discard=False leaves search ID untouched and keeps search running."""
    dialog = mock_dialog
    dialog.is_busy = True
    dialog._current_search_id = 10
    dialog.mode_var = MagicMock()
    dialog.mode_var.get.return_value = "fill"
    dialog.adapter = MagicMock()
    dialog.adapter.set_wallpaper.return_value = True

    dummy_img = tmp_path / "staged.jpg"
    dummy_img.write_bytes(b"image_data")
    dialog.staged_metadata = MagicMock(local_path=str(dummy_img), title="Staged Pic", image_id="s1")
    dialog.current_metadata = MagicMock(image_id="curr1")
    dialog.history = MagicMock()
    dialog.recent_mgr = MagicMock()
    dialog.set_status = MagicMock()
    dialog._update_history_nav_buttons = MagicMock()
    dialog._update_filmstrip = MagicMock()

    with patch("login_wallpaper_selector.ui.dialog.messagebox.askyesno", return_value=False):
        dialog.on_apply_staged()

    # Does NOT bump search ID, allowing background search to finish
    assert dialog._current_search_id == 10
    dialog.adapter.set_wallpaper.assert_called_once()


def test_handle_local_storage_cancelled_when_busy(mock_dialog):
    """Verify cancelling local file dialog while busy restores previous category and maintains search."""
    dialog = mock_dialog
    dialog.is_busy = True
    dialog.current_category = WallpaperCategory.SPACE
    dialog.set_status = MagicMock()
    dialog._update_category_buttons = MagicMock()

    with patch("login_wallpaper_selector.ui.dialog.pick_local_image", return_value=None):
        dialog._handle_local_storage(previous_category=WallpaperCategory.SPACE, was_busy=True)

    assert dialog.current_category == WallpaperCategory.SPACE
    dialog._update_category_buttons.assert_called_with(WallpaperCategory.SPACE)
    status_msg = dialog.set_status.call_args[0][0]
    assert "continuing" in status_msg.lower()


def test_handle_local_storage_selected_when_busy(mock_dialog, tmp_path):
    """Verify picking a local file while busy cancels active search and stages the chosen image."""
    dialog = mock_dialog
    dialog.is_busy = True
    dialog._current_search_id = 20
    dialog.mode_var = MagicMock()
    dialog.mode_var.get.return_value = "fill"
    dialog.cache = MagicMock()
    dummy_local = tmp_path / "picked.jpg"
    dummy_local.write_bytes(b"fake_jpeg")
    dialog.cache.store_local_image.return_value = MagicMock(title="Picked", local_path=str(dummy_local))
    dialog._record_fetched_wallpaper = MagicMock()
    dialog._update_preview_and_attribution = MagicMock()
    dialog.set_status = MagicMock()

    def sync_thread(target, *args, **kwargs):
        m = MagicMock()
        m.start.side_effect = target
        return m

    with patch("threading.Thread", side_effect=sync_thread), \
         patch("login_wallpaper_selector.ui.dialog.pick_local_image", return_value=dummy_local):
        dialog._handle_local_storage(previous_category=WallpaperCategory.SPACE, was_busy=True)

    # Invalidate ongoing search
    assert dialog._current_search_id == 21
    dialog._update_preview_and_attribution.assert_called_once()


def test_favorites_bumps_search_id_when_busy(mock_dialog, tmp_path):
    """Verify selecting favorites while busy cancels the active search and loads the favorite."""
    dialog = mock_dialog
    dialog.is_busy = True
    dialog._current_search_id = 30
    dialog.mode_var = MagicMock()
    dialog.mode_var.get.return_value = "fill"
    dialog.cache = MagicMock()
    dummy_fav_path = tmp_path / "fav.jpg"
    dummy_fav_path.write_bytes(b"fav_image_data")

    fav_item = MagicMock(
        title="Fav 1",
        image_id="fav_1",
        provider="Wallhaven",
        saved_path=str(dummy_fav_path),
        local_path=str(dummy_fav_path),
        dominant_color_hex="#112233",
        mood=None,
        rating=5,
    )
    dialog.favorites_mgr = MagicMock()
    dialog.favorites_mgr.get_random_favorite.return_value = fav_item
    dialog.cache.store_local_image.return_value = MagicMock(
        title="Fav 1",
        local_path=str(dummy_fav_path),
        image_id="fav_1",
    )
    dialog._update_preview_and_attribution = MagicMock()
    dialog._record_fetched_wallpaper = MagicMock()
    dialog.set_status = MagicMock()

    def sync_thread(target, *args, **kwargs):
        m = MagicMock()
        m.start.side_effect = target
        return m

    with patch("threading.Thread", side_effect=sync_thread):
        dialog._handle_favorites_category()

    # Verify search ID was incremented to cancel the background search
    assert dialog._current_search_id == 31
    dialog._update_preview_and_attribution.assert_called_once()


def test_real_tkinter_stop_button_widget_lifecycle(tmp_path):
    """Verify stop_btn packs, un-packs, and triggers on_stop_progress cleanly in a real Tk window."""
    import tkinter as tk
    try:
        root = tk.Tk()
        root.withdraw()
    except Exception:
        pytest.skip("Tkinter display not available in this environment")

    try:
        cfg = AppConfig(custom_cache_dir=str(tmp_path / "cache"))
        dialog = WallpaperSelectorDialog(config=cfg, root_window=root)
        dialog.root.update_idletasks()

        # Initially, stop_btn is created but NOT packed into geometry manager
        assert hasattr(dialog, "stop_btn")
        assert dialog.stop_btn.winfo_manager() == ""

        # Set busy -> stop_btn should be packed
        dialog.set_busy(True)
        dialog.root.update()
        assert dialog.stop_btn.winfo_manager() == "pack"
        assert dialog.is_busy is True

        # Click / trigger stop button
        if hasattr(dialog.stop_btn, "invoke"):
            dialog.stop_btn.invoke()
        elif hasattr(dialog.stop_btn, "_command") and dialog.stop_btn._command:
            dialog.stop_btn._command()
        else:
            dialog.on_stop_progress()

        dialog.root.update()
        assert dialog.is_busy is False
        assert dialog.stop_btn.winfo_manager() == ""
        assert "stopped" in dialog.status_lbl.cget("text").lower()

        dialog.root.destroy()
    except Exception:
        try:
            root.destroy()
        except Exception:
            pass
        raise

