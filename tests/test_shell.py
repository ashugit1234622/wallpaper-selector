"""Tests for Desktop Utility Suite AppShell and navigation."""

import pytest
from unittest.mock import MagicMock
from login_wallpaper_selector.core.config import AppConfig
from login_wallpaper_selector.ui.shell import AppShell
from login_wallpaper_selector.ui.dialog import WallpaperSelectorDialog


def test_app_shell_initialization(monkeypatch):
    monkeypatch.setattr(AppShell, "_init_window", lambda self: setattr(self, "root", MagicMock()))
    monkeypatch.setattr(AppShell, "_build_shell", lambda self: None)
    monkeypatch.setattr(AppShell, "switch_tool", lambda self, tool: None)

    cfg = AppConfig()
    shell = AppShell(config=cfg)
    assert shell.config == cfg
    assert shell.active_tool == "wallpaper"


def test_app_shell_tool_switching(monkeypatch):
    monkeypatch.setattr(AppShell, "_init_window", lambda self: setattr(self, "root", MagicMock()))
    monkeypatch.setattr(AppShell, "_build_shell", lambda self: None)

    shell = AppShell(config=AppConfig())
    shell.wallpaper_frame = MagicMock()
    shell.organizer_frame = MagicMock()
    shell.nav_wallpaper_btn = MagicMock()
    shell.nav_organizer_btn = MagicMock()

    # Switch to organizer
    shell.switch_tool("organizer")
    assert shell.active_tool == "organizer"
    shell.wallpaper_frame.pack_forget.assert_called()
    shell.organizer_frame.pack.assert_called()

    # Switch to wallpaper
    shell.switch_tool("wallpaper")
    assert shell.active_tool == "wallpaper"
    shell.organizer_frame.pack_forget.assert_called()
    shell.wallpaper_frame.pack.assert_called()


def test_wallpaper_dialog_parent_frame_handling(monkeypatch):
    monkeypatch.setattr(WallpaperSelectorDialog, "_init_window", lambda self: None)
    cfg = AppConfig()
    parent = MagicMock()
    dialog = WallpaperSelectorDialog(config=cfg, parent_frame=parent)
    assert dialog.parent_frame == parent
    assert dialog.config == cfg


def test_app_shell_close_minimizes_when_rotation_enabled(monkeypatch):
    monkeypatch.setattr(AppShell, "_init_window", lambda self: setattr(self, "root", MagicMock()))
    monkeypatch.setattr(AppShell, "_build_shell", lambda self: None)
    monkeypatch.setattr(AppShell, "switch_tool", lambda self, tool: None)

    cfg = AppConfig(rotation_enabled=True)
    shell = AppShell(config=cfg)

    minimized = []
    quit_called = []
    monkeypatch.setattr(shell, "_minimize_to_tray", lambda: minimized.append(True))
    monkeypatch.setattr(shell, "quit_app", lambda: quit_called.append(True))

    shell.on_close_window()
    assert len(minimized) == 1
    assert len(quit_called) == 0


def test_app_shell_close_quits_when_rotation_disabled(monkeypatch):
    monkeypatch.setattr(AppShell, "_init_window", lambda self: setattr(self, "root", MagicMock()))
    monkeypatch.setattr(AppShell, "_build_shell", lambda self: None)
    monkeypatch.setattr(AppShell, "switch_tool", lambda self, tool: None)

    cfg = AppConfig(rotation_enabled=False)
    shell = AppShell(config=cfg)

    minimized = []
    quit_called = []
    monkeypatch.setattr(shell, "_minimize_to_tray", lambda: minimized.append(True))
    monkeypatch.setattr(shell, "quit_app", lambda: quit_called.append(True))

    shell.on_close_window()
    assert len(minimized) == 0
    assert len(quit_called) == 1
