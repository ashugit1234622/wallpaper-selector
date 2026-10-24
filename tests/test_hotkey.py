"""Unit tests for Global Windows Hotkey and Toast Notifications."""

import os
from unittest.mock import MagicMock, patch
import pytest

from login_wallpaper_selector.core.hotkey import GlobalHotkeyListener, HOTKEY_COMBOS, MOD_WIN, MOD_ALT, MOD_CONTROL, MOD_SHIFT
from login_wallpaper_selector.core.notifications import send_toast_notification
from login_wallpaper_selector.core.config import AppConfig
from login_wallpaper_selector.ui.dialog import WallpaperSelectorDialog


def test_hotkey_combos_mapping():
    """Verify predefined hotkey combinations map to correct Win32 virtual keys and modifier bitmasks."""
    assert "Win+Alt+W" in HOTKEY_COMBOS
    assert "Ctrl+Alt+W" in HOTKEY_COMBOS
    assert "Win+Shift+W" in HOTKEY_COMBOS

    mods_win_alt, vk_win_alt = HOTKEY_COMBOS["Win+Alt+W"]
    assert vk_win_alt == 0x57  # 'W'
    assert (mods_win_alt & MOD_WIN) != 0
    assert (mods_win_alt & MOD_ALT) != 0

    mods_ctrl_alt, vk_ctrl_alt = HOTKEY_COMBOS["Ctrl+Alt+W"]
    assert vk_ctrl_alt == 0x57
    assert (mods_ctrl_alt & MOD_CONTROL) != 0
    assert (mods_ctrl_alt & MOD_ALT) != 0

    mods_win_shift, vk_win_shift = HOTKEY_COMBOS["Win+Shift+W"]
    assert vk_win_shift == 0x57
    assert (mods_win_shift & MOD_WIN) != 0
    assert (mods_win_shift & MOD_SHIFT) != 0


def test_hotkey_listener_lifecycle():
    """Verify listener initialization and stop methods."""
    callback = MagicMock()
    listener = GlobalHotkeyListener(combo="Win+Alt+W", on_triggered=callback)
    assert listener.combo == "Win+Alt+W"
    assert listener.on_triggered == callback

    # Test stop before start doesn't crash
    listener.stop()


def test_send_toast_notification_with_tray():
    """Verify toast notification uses system tray manager when running."""
    mock_tray = MagicMock()
    mock_tray._is_running = True
    mock_tray._icon = MagicMock()

    def sync_thread(target, daemon=True):
        m = MagicMock()
        m.start.side_effect = target
        return m

    with patch("threading.Thread", side_effect=sync_thread):
        send_toast_notification("Test Title", "Test Message", tray_mgr=mock_tray)

    mock_tray.notify.assert_called_once_with("Test Message", "Test Title")


def test_send_toast_notification_fallback():
    """Verify PowerShell toast notification fallback on Windows when tray is absent."""
    def sync_thread(target, daemon=True):
        m = MagicMock()
        m.start.side_effect = target
        return m

    with patch("threading.Thread", side_effect=sync_thread), \
         patch("subprocess.run") as mock_run, \
         patch("os.name", "nt"):
        send_toast_notification("Alert Title", "Alert Message", tray_mgr=None)

    assert mock_run.called
    call_args = mock_run.call_args[0][0]
    assert "powershell" in call_args[0]
    script_str = " ".join(call_args)
    assert "Alert Title" in script_str
    assert "Alert Message" in script_str


def test_dialog_hotkey_debouncing(monkeypatch):
    """Verify dialog debounces rapid hotkey triggers to prevent concurrent rotation spam."""
    monkeypatch.setattr(WallpaperSelectorDialog, "_init_window", lambda self: setattr(self, "root", MagicMock()))
    monkeypatch.setattr(WallpaperSelectorDialog, "_build_widgets", lambda self: None)
    config = AppConfig()
    dialog = WallpaperSelectorDialog(config=config)

    dialog._is_hotkey_rotating = True
    with patch("login_wallpaper_selector.ui.dialog.send_toast_notification") as mock_toast:
        dialog.on_hotkey_triggered()
        mock_toast.assert_not_called()

    dialog._is_hotkey_rotating = False
    with patch("login_wallpaper_selector.ui.dialog.send_toast_notification") as mock_toast, \
         patch("threading.Thread") as mock_thread:
        dialog.on_hotkey_triggered()
        assert dialog._is_hotkey_rotating is True
        mock_toast.assert_called_once()
        assert "Fetching new wallpaper" in mock_toast.call_args[0][1]


def test_dialog_hotkey_toggle_and_combo(monkeypatch):
    """Verify on_hotkey_toggle and on_hotkey_combo_change update config and listener."""
    monkeypatch.setattr(WallpaperSelectorDialog, "_init_window", lambda self: setattr(self, "root", MagicMock()))
    monkeypatch.setattr(WallpaperSelectorDialog, "_build_widgets", lambda self: None)
    config = AppConfig()
    dialog = WallpaperSelectorDialog(config=config)

    dialog.hotkey_var = MagicMock()
    dialog.hotkey_var.get.return_value = False
    dialog._hotkey_listener = MagicMock()

    with patch.object(config, "save") as mock_save:
        dialog.on_hotkey_toggle()
        assert config.global_hotkey_enabled is False
        assert dialog._hotkey_listener is None
        mock_save.assert_called_once()

    with patch.object(config, "save") as mock_save, \
         patch.object(dialog, "_start_global_hotkey") as mock_start:
        dialog.on_hotkey_combo_change("Ctrl+Alt+W")
        assert config.global_hotkey_combo == "Ctrl+Alt+W"
        mock_save.assert_called_once()
        mock_start.assert_not_called()

        config.global_hotkey_enabled = True
        dialog.on_hotkey_combo_change("Win+Shift+W")
        assert config.global_hotkey_combo == "Win+Shift+W"
        mock_start.assert_called_once()
