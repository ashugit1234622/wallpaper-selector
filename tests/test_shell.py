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
