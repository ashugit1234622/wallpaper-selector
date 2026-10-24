"""Windows Power and Battery Status Monitor.

Queries native Win32 GetSystemPowerStatus via ctypes to detect AC power connection,
battery presence, discharge state, and Windows 10/11 Battery Saver mode without external dependencies.
"""

from __future__ import annotations
import ctypes
import os
from typing import Dict, Any


if os.name == "nt":
    class SYSTEM_POWER_STATUS(ctypes.Structure):
        _fields_ = [
            ("ACLineStatus", ctypes.c_ubyte),
            ("BatteryFlag", ctypes.c_ubyte),
            ("BatteryLifePercent", ctypes.c_ubyte),
            ("SystemStatusFlag", ctypes.c_ubyte),
            ("BatteryLifeTime", ctypes.c_ulong),
            ("BatteryFullLifeTime", ctypes.c_ulong),
        ]
else:
    SYSTEM_POWER_STATUS = None  # type: ignore


def get_system_power_status() -> Dict[str, Any]:
    """Retrieve current system power status metrics.
    
    Returns:
        Dict containing:
            - is_supported (bool)
            - has_battery (bool)
            - on_battery (bool): True if unplugged from AC and discharging on battery.
            - ac_online (bool): True if connected to AC wall power.
            - percent (int): 0-100 or -1 if unknown.
            - battery_saver (bool): True if Windows Battery Saver is active.
    """
    if os.name != "nt" or SYSTEM_POWER_STATUS is None:
        return {
            "is_supported": False,
            "has_battery": False,
            "on_battery": False,
            "ac_online": True,
            "percent": -1,
            "battery_saver": False,
        }

    status = SYSTEM_POWER_STATUS()
    try:
        kernel32 = ctypes.windll.kernel32
        success = kernel32.GetSystemPowerStatus(ctypes.byref(status))
        if not success:
            return {
                "is_supported": False,
                "has_battery": False,
                "on_battery": False,
                "ac_online": True,
                "percent": -1,
                "battery_saver": False,
            }

        ac_line = status.ACLineStatus
        battery_flag = status.BatteryFlag
        percent = status.BatteryLifePercent
        saver = status.SystemStatusFlag

        # BatteryFlag == 128 means no system battery (Desktop computer)
        has_battery = (battery_flag != 128 and battery_flag != 255)
        # ACLineStatus == 0 means unplugged and on battery power
        on_battery = (ac_line == 0 and has_battery)
        ac_online = (ac_line == 1 or not has_battery)
        battery_saver_active = bool(saver == 1)

        return {
            "is_supported": True,
            "has_battery": has_battery,
            "on_battery": on_battery,
            "ac_online": ac_online,
            "percent": int(percent) if 0 <= percent <= 100 else -1,
            "battery_saver": battery_saver_active,
        }
    except Exception:
        return {
            "is_supported": False,
            "has_battery": False,
            "on_battery": False,
            "ac_online": True,
            "percent": -1,
            "battery_saver": False,
        }


def is_running_on_battery() -> bool:
    """Return True if system is running on battery power (unplugged from AC)."""
    return get_system_power_status().get("on_battery", False)


def is_battery_saver_active() -> bool:
    """Return True if Windows 10/11 Battery Saver mode is currently active."""
    return get_system_power_status().get("battery_saver", False)
