"""Unit tests for Windows Power and Battery Status Monitor."""

from unittest.mock import MagicMock, patch
import pytest

from login_wallpaper_selector.core.power import (
    get_system_power_status,
    is_running_on_battery,
    is_battery_saver_active,
    SYSTEM_POWER_STATUS,
)


def test_power_status_desktop_no_battery():
    """Verify that a desktop machine with no battery is reported as AC online and not on battery."""
    mock_status = SYSTEM_POWER_STATUS()
    mock_status.ACLineStatus = 1  # AC Online
    mock_status.BatteryFlag = 128  # No system battery
    mock_status.BatteryLifePercent = 255  # Unknown
    mock_status.SystemStatusFlag = 0  # Saver off

    with patch("os.name", "nt"), \
         patch("ctypes.windll.kernel32.GetSystemPowerStatus") as mock_get:
        def fill_status(ref):
            ref._obj.ACLineStatus = mock_status.ACLineStatus
            ref._obj.BatteryFlag = mock_status.BatteryFlag
            ref._obj.BatteryLifePercent = mock_status.BatteryLifePercent
            ref._obj.SystemStatusFlag = mock_status.SystemStatusFlag
            return 1
        mock_get.side_effect = fill_status

        status = get_system_power_status()
        assert status["is_supported"] is True
        assert status["has_battery"] is False
        assert status["on_battery"] is False
        assert status["ac_online"] is True
        assert status["battery_saver"] is False
        assert is_running_on_battery() is False
        assert is_battery_saver_active() is False


def test_power_status_laptop_on_battery():
    """Verify that an unplugged laptop is correctly detected as on battery."""
    mock_status = SYSTEM_POWER_STATUS()
    mock_status.ACLineStatus = 0  # Offline / On battery
    mock_status.BatteryFlag = 1  # High
    mock_status.BatteryLifePercent = 85
    mock_status.SystemStatusFlag = 0

    with patch("os.name", "nt"), \
         patch("ctypes.windll.kernel32.GetSystemPowerStatus") as mock_get:
        def fill_status(ref):
            ref._obj.ACLineStatus = mock_status.ACLineStatus
            ref._obj.BatteryFlag = mock_status.BatteryFlag
            ref._obj.BatteryLifePercent = mock_status.BatteryLifePercent
            ref._obj.SystemStatusFlag = mock_status.SystemStatusFlag
            return 1
        mock_get.side_effect = fill_status

        status = get_system_power_status()
        assert status["is_supported"] is True
        assert status["has_battery"] is True
        assert status["on_battery"] is True
        assert status["ac_online"] is False
        assert status["percent"] == 85
        assert is_running_on_battery() is True


def test_power_status_battery_saver_active():
    """Verify detection when Windows Battery Saver mode is on."""
    mock_status = SYSTEM_POWER_STATUS()
    mock_status.ACLineStatus = 0
    mock_status.BatteryFlag = 2  # Low
    mock_status.BatteryLifePercent = 18
    mock_status.SystemStatusFlag = 1  # Battery Saver ON

    with patch("os.name", "nt"), \
         patch("ctypes.windll.kernel32.GetSystemPowerStatus") as mock_get:
        def fill_status(ref):
            ref._obj.ACLineStatus = mock_status.ACLineStatus
            ref._obj.BatteryFlag = mock_status.BatteryFlag
            ref._obj.BatteryLifePercent = mock_status.BatteryLifePercent
            ref._obj.SystemStatusFlag = mock_status.SystemStatusFlag
            return 1
        mock_get.side_effect = fill_status

        assert is_battery_saver_active() is True
        assert is_running_on_battery() is True


def test_power_status_non_windows_fallback():
    """Verify safe fallback on non-Windows operating systems."""
    with patch("os.name", "posix"):
        status = get_system_power_status()
        assert status["is_supported"] is False
        assert status["on_battery"] is False
        assert status["ac_online"] is True
        assert is_running_on_battery() is False
        assert is_battery_saver_active() is False
