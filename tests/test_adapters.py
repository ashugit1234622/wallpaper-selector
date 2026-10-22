"""Unit tests for platform wallpaper and autostart adapters."""

import sys
import pytest
from login_wallpaper_selector.adapters.factory import get_wallpaper_adapter
from login_wallpaper_selector.autostart.factory import get_autostart_adapter


def test_adapter_factory():
    wp_adapter = get_wallpaper_adapter()
    assert wp_adapter is not None

    auto_adapter = get_autostart_adapter()
    assert auto_adapter is not None

    if sys.platform == "win32":
        assert "Windows" in wp_adapter.platform_name
        assert "Windows" in auto_adapter.platform_name


@pytest.mark.skipif(sys.platform != "win32", reason="Windows specific test")
def test_windows_autostart_adapter_toggle():
    auto_adapter = get_autostart_adapter()
    test_cmd = 'python -m login_wallpaper_selector --on-login'

    # Save original state
    was_enabled = auto_adapter.is_enabled()
    original_cmd = auto_adapter.get_registered_command()

    try:
        # Enable test command
        success = auto_adapter.enable(test_cmd)
        assert success is True
        assert auto_adapter.is_enabled() is True
        assert auto_adapter.get_registered_command() == test_cmd

        # Disable
        success_disable = auto_adapter.disable()
        assert success_disable is True
        assert auto_adapter.is_enabled() is False

    finally:
        # Restore original state if it was enabled
        if was_enabled and original_cmd:
            auto_adapter.enable(original_cmd)
        else:
            auto_adapter.disable()


def test_windows_adapter_set_lockscreen(tmp_path, monkeypatch):
    from unittest.mock import MagicMock
    import subprocess
    from login_wallpaper_selector.adapters.windows import WindowsWallpaperAdapter

    adapter = WindowsWallpaperAdapter()

    # Non-existent file returns False immediately
    assert adapter.set_lockscreen(tmp_path / "non_existent.jpg") is False

    # Create dummy image
    test_img = tmp_path / "lock.jpg"
    test_img.write_bytes(b"dummy image data")

    # Mock successful PowerShell execution
    mock_success = MagicMock(returncode=0)
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: mock_success)
    assert adapter.set_lockscreen(test_img) is True

    # Mock failed execution
    mock_fail = MagicMock(returncode=1)
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: mock_fail)
    assert adapter.set_lockscreen(test_img) is False


def test_gnome_adapter_set_lockscreen(tmp_path, monkeypatch):
    from unittest.mock import MagicMock
    import subprocess
    from login_wallpaper_selector.adapters.gnome import GnomeWallpaperAdapter

    adapter = GnomeWallpaperAdapter()

    assert adapter.set_lockscreen(tmp_path / "non_existent.jpg") is False

    test_img = tmp_path / "lock.jpg"
    test_img.write_bytes(b"dummy image data")

    mock_run = MagicMock(returncode=0)
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: mock_run)
    assert adapter.set_lockscreen(test_img) is True
