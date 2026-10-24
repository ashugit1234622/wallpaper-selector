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
        assert "Fetching new desktop wallpaper" in mock_toast.call_args[0][1]


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


def test_hotkey_fallback_when_combo_taken():
    """Verify listener automatically falls back to a non-conflicting combination if initial registration fails."""
    listener = GlobalHotkeyListener(combo="Win+Alt+W")

    def mock_register(hwnd, id, mod, vk):
        # Fail Win+Alt+W (0x0008 | 0x0001) but succeed Ctrl+Alt+W (0x0002 | 0x0001)
        if (mod & MOD_WIN) != 0:
            return 0
        return 1

    with patch("os.name", "nt"), \
         patch("ctypes.windll.user32.RegisterHotKey", side_effect=mock_register), \
         patch("ctypes.windll.user32.UnregisterHotKey", return_value=1), \
         patch("ctypes.windll.user32.PeekMessageW", return_value=0), \
         patch("time.sleep"):
        success = listener.start()
        assert success is True
        assert listener.is_fallback is True
        assert listener.active_combo == "Ctrl+Alt+W"
        listener.stop()


def test_on_hotkey_triggered_enforces_desktop_resolution(monkeypatch):
    """Verify on_hotkey_triggered calls daemon.rotate_now with search_for_tv=False (desktop resolution)."""
    monkeypatch.setattr(WallpaperSelectorDialog, "_init_window", lambda self: setattr(self, "root", MagicMock()))
    monkeypatch.setattr(WallpaperSelectorDialog, "_build_widgets", lambda self: None)
    config = AppConfig(rotation_enabled=True, rotation_interval_minutes=30)
    config.search_for_tv = True  # TV toggle is ON
    dialog = WallpaperSelectorDialog(config=config)
    dialog.staged_metadata = None
    dialog.current_metadata = MagicMock(image_id="curr_1")
    dialog._schedule_next_rotation_check = MagicMock()
    dialog._record_fetched_wallpaper = MagicMock()
    dialog._update_preview_and_attribution = MagicMock()
    dialog.set_status = MagicMock()

    mock_daemon = MagicMock()
    mock_meta = MagicMock(title="Desktop Mountain", category="Nature", time_of_day_info=None)
    mock_daemon.rotate_now.return_value = (mock_meta, None)

    def sync_thread(target, *args, **kwargs):
        m = MagicMock()
        m.start.side_effect = target
        return m

    with patch("login_wallpaper_selector.core.scheduler.WallpaperRotationDaemon", return_value=mock_daemon), \
         patch("threading.Thread", side_effect=sync_thread), \
         patch("login_wallpaper_selector.ui.dialog.send_toast_notification"):
        dialog.on_hotkey_triggered()

    # Verify search_for_tv=False was explicitly passed despite config.search_for_tv being True
    mock_daemon.rotate_now.assert_called_once()
    kwargs = mock_daemon.rotate_now.call_args[1]
    assert kwargs.get("search_for_tv") is False

    # Execute UI update callback
    ui_callback = dialog.root.after.call_args[0][1]
    ui_callback()

    # Verify preview was updated since there was no staged unapplied preview
    assert dialog.current_metadata == mock_meta
    # Verify auto-rotate timer was reset starting from now (30m * 60 * 1000 = 1800000ms)
    dialog._schedule_next_rotation_check.assert_called_once_with(delay_ms=1800000)


def test_on_hotkey_triggered_preserves_staged_preview(monkeypatch):
    """Verify on_hotkey_triggered does not overwrite user's active manual staged preview."""
    monkeypatch.setattr(WallpaperSelectorDialog, "_init_window", lambda self: setattr(self, "root", MagicMock()))
    monkeypatch.setattr(WallpaperSelectorDialog, "_build_widgets", lambda self: None)
    config = AppConfig()
    dialog = WallpaperSelectorDialog(config=config)
    staged = MagicMock(image_id="staged_preview")
    current = MagicMock(image_id="curr_active")
    dialog.staged_metadata = staged
    dialog.current_metadata = current
    dialog._schedule_next_rotation_check = MagicMock()
    dialog._record_fetched_wallpaper = MagicMock()
    dialog._update_preview_and_attribution = MagicMock()
    dialog.set_status = MagicMock()

    mock_daemon = MagicMock()
    mock_meta = MagicMock(title="Background Space", category="Space", time_of_day_info=None)
    mock_daemon.rotate_now.return_value = (mock_meta, None)

    def sync_thread(target, *args, **kwargs):
        m = MagicMock()
        m.start.side_effect = target
        return m

    with patch("login_wallpaper_selector.core.scheduler.WallpaperRotationDaemon", return_value=mock_daemon), \
         patch("threading.Thread", side_effect=sync_thread), \
         patch("login_wallpaper_selector.ui.dialog.send_toast_notification"):
        dialog.on_hotkey_triggered()

    ui_callback = dialog.root.after.call_args[0][1]
    ui_callback()

    # Staged preview preserved, current_metadata NOT changed to mock_meta
    assert dialog.current_metadata == current
    status_str = dialog.set_status.call_args[0][0]
    assert "Active manual preview preserved" in status_str

