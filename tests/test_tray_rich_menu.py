"""Unit tests for Rich System Tray Menu Actions and Tooltip Updates."""

from unittest.mock import MagicMock, patch
import pytest

from login_wallpaper_selector.ui.tray import SystemTrayManager


def test_tray_rich_menu_callbacks():
    """Verify that rich menu items execute their respective callbacks."""
    on_show = MagicMock()
    on_rotate = MagicMock()
    on_favorite = MagicMock()
    on_open_folder = MagicMock()
    on_copy_path = MagicMock()
    on_quit = MagicMock()
    get_title = MagicMock(return_value="Aurora Borealis")

    tray = SystemTrayManager(
        on_show=on_show,
        on_rotate_now=on_rotate,
        on_quit=on_quit,
        on_favorite=on_favorite,
        on_open_folder=on_open_folder,
        on_copy_path=on_copy_path,
        get_current_title=get_title,
        app_name="TestApp",
    )

    tray._handle_show()
    on_show.assert_called_once()

    tray._handle_rotate_now()
    on_rotate.assert_called_once()

    tray._handle_favorite()
    on_favorite.assert_called_once()

    tray._handle_open_folder()
    on_open_folder.assert_called_once()

    tray._handle_copy_path()
    on_copy_path.assert_called_once()

    tray._handle_quit()
    on_quit.assert_called_once()


def test_tray_tooltip_update():
    """Verify dynamic tooltip updating on the tray icon."""
    tray = SystemTrayManager(on_show=MagicMock(), app_name="TestApp")
    mock_icon = MagicMock()
    tray._icon = mock_icon
    tray._is_running = True

    tray.update_tooltip("TestApp: Cosmic Wonder (Paused - On Battery)")
    assert mock_icon.title == "TestApp: Cosmic Wonder (Paused - On Battery)"
