"""Unit tests for Windows Multi-Monitor Wallpaper Adapter Support."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from login_wallpaper_selector.adapters.windows import WindowsWallpaperAdapter
from login_wallpaper_selector.core.models import WallpaperPosition


def test_get_monitors_enumeration():
    """Verify that get_monitors correctly enumerates connected display paths via IDesktopWallpaper."""
    adapter = WindowsWallpaperAdapter()

    mock_desktop_wp = MagicMock()
    mock_desktop_wp.GetMonitorDevicePathCount.return_value = 2
    mock_desktop_wp.GetMonitorDevicePathAt.side_effect = lambda idx: f"\\\\?\\DISPLAY#MONITOR_{idx + 1}"

    with patch("comtypes.client.CreateObject", return_value=mock_desktop_wp):
        monitors = adapter.get_monitors()
        assert len(monitors) == 2
        assert monitors[0] == ("\\\\?\\DISPLAY#MONITOR_1", "Display 1")
        assert monitors[1] == ("\\\\?\\DISPLAY#MONITOR_2", "Display 2")


def test_set_wallpaper_specific_monitor(tmp_path):
    """Verify that set_wallpaper passes monitor_id to SetWallpaper."""
    adapter = WindowsWallpaperAdapter()
    test_img = tmp_path / "test.jpg"
    test_img.write_text("fake image content")

    mock_desktop_wp = MagicMock()
    with patch("comtypes.client.CreateObject", return_value=mock_desktop_wp), \
         patch.object(adapter, "_set_registry_style"):
        
        # Test specific monitor
        res = adapter.set_wallpaper(test_img, mode="Fill", monitor_id="\\\\?\\DISPLAY#MONITOR_2")
        assert res is True
        mock_desktop_wp.SetPosition.assert_called_with(4)  # Fill
        mock_desktop_wp.SetWallpaper.assert_called_with("\\\\?\\DISPLAY#MONITOR_2", str(test_img.resolve()))

        # Test all monitors (monitor_id = None)
        res_all = adapter.set_wallpaper(test_img, mode="Fit", monitor_id=None)
        assert res_all is True
        mock_desktop_wp.SetPosition.assert_called_with(3)  # Fit
        mock_desktop_wp.SetWallpaper.assert_called_with(None, str(test_img.resolve()))
