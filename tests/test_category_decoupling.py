"""Unit tests verifying that categories are only considered when clicked,

and that searching or choosing color/mood operates category-free.
"""

from pathlib import Path
from unittest.mock import MagicMock
import pytest

from login_wallpaper_selector.core.config import AppConfig
from login_wallpaper_selector.core.models import WallpaperCategory, ColorPalette, WallpaperMood
from login_wallpaper_selector.ui.dialog import WallpaperSelectorDialog


def test_select_category_clears_search_and_sets_category(monkeypatch):
    monkeypatch.setattr(WallpaperSelectorDialog, "_init_window", lambda self: None)
    monkeypatch.setattr(WallpaperSelectorDialog, "_handle_online_category", lambda self, cat: None)

    dialog = WallpaperSelectorDialog(config=AppConfig())
    dialog.search_entry = MagicMock()
    dialog.current_keyword = "some previous keyword"
    dialog.cat_buttons = {c: MagicMock() for c in WallpaperCategory}

    dialog.on_select_category(WallpaperCategory.SPACE)

    assert dialog.current_category == WallpaperCategory.SPACE
    assert dialog.current_keyword == ""
    dialog.search_entry.delete.assert_called_with(0, "end")


def test_trigger_search_clears_category_and_searches_globally(monkeypatch):
    monkeypatch.setattr(WallpaperSelectorDialog, "_init_window", lambda self: None)
    
    dialog = WallpaperSelectorDialog(config=AppConfig())
    dialog.current_category = WallpaperCategory.SPACE
    dialog.cat_buttons = {c: MagicMock() for c in WallpaperCategory}
    dialog.set_busy = MagicMock()
    dialog.set_status = MagicMock()

    mock_acquire = MagicMock(return_value=(None, "search test"))
    dialog.router.acquire_wallpaper_for_category = mock_acquire

    # Calling search with a keyword
    dialog.on_trigger_search("cyberpunk")

    # Category must be cleared so it is NOT considered
    assert dialog.current_category is None
    assert dialog.current_keyword == "cyberpunk"


def test_select_color_clears_category_and_fetches_random(monkeypatch):
    monkeypatch.setattr(WallpaperSelectorDialog, "_init_window", lambda self: None)
    
    dialog = WallpaperSelectorDialog(config=AppConfig())
    dialog.current_category = WallpaperCategory.NATURE
    dialog.cat_buttons = {c: MagicMock() for c in WallpaperCategory}
    dialog.color_chips = {c: MagicMock() for c in ColorPalette}
    dialog.set_status = MagicMock()
    mock_fetch_random = MagicMock()
    dialog._fetch_random_wallpaper = mock_fetch_random

    dialog.on_select_color(ColorPalette.BLUE)

    assert dialog.current_category is None
    assert dialog.selected_color == ColorPalette.BLUE
    mock_fetch_random.assert_called_once_with(color=ColorPalette.BLUE, mood=dialog.selected_mood)


def test_select_mood_clears_category_and_fetches_random(monkeypatch):
    monkeypatch.setattr(WallpaperSelectorDialog, "_init_window", lambda self: None)
    
    dialog = WallpaperSelectorDialog(config=AppConfig())
    dialog.current_category = WallpaperCategory.ART
    dialog.cat_buttons = {c: MagicMock() for c in WallpaperCategory}
    dialog.mood_chips = {m: MagicMock() for m in WallpaperMood}
    dialog.set_status = MagicMock()
    mock_fetch_random = MagicMock()
    dialog._fetch_random_wallpaper = mock_fetch_random

    dialog.on_select_mood(WallpaperMood.DARK)

    assert dialog.current_category is None
    assert dialog.selected_mood == WallpaperMood.DARK
    mock_fetch_random.assert_called_once_with(color=dialog.selected_color, mood=WallpaperMood.DARK)


def test_category_toggle_off_on_second_click(monkeypatch):
    monkeypatch.setattr(WallpaperSelectorDialog, "_init_window", lambda self: None)
    dialog = WallpaperSelectorDialog(config=AppConfig())
    dialog.cat_buttons = {c: MagicMock() for c in WallpaperCategory}
    dialog.set_status = MagicMock()
    dialog.set_busy = MagicMock()

    # First click toggles ON
    mock_online = MagicMock()
    monkeypatch.setattr(dialog, "_handle_online_category", mock_online)
    dialog.on_select_category(WallpaperCategory.SPACE)
    assert dialog.current_category == WallpaperCategory.SPACE
    mock_online.assert_called_once_with(WallpaperCategory.SPACE)

    # Second click toggles OFF
    dialog.on_select_category(WallpaperCategory.SPACE)
    assert dialog.current_category is None


def test_retry_when_category_off_fetches_random(monkeypatch):
    monkeypatch.setattr(WallpaperSelectorDialog, "_init_window", lambda self: None)
    dialog = WallpaperSelectorDialog(config=AppConfig())
    dialog.current_category = None
    dialog.current_keyword = ""
    dialog.search_entry = MagicMock()
    dialog.search_entry.get.return_value = ""
    mock_fetch_random = MagicMock()
    dialog._fetch_random_wallpaper = mock_fetch_random

    dialog.on_retry()

    mock_fetch_random.assert_called_once_with(color=dialog.selected_color, mood=dialog.selected_mood)

