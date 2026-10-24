"""Windows Global System Hotkey Listener.

Registers background global hotkeys (e.g. Win+Alt+W, Ctrl+Alt+W, Win+Shift+W)
using native Windows user32 APIs without third-party dependencies.
"""

from __future__ import annotations
import ctypes
from ctypes import wintypes
import os
import threading
import time
from typing import Callable, Optional, Tuple

# Windows Virtual Key Codes and Modifier Constants
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

HOTKEY_COMBOS = {
    "Win+Alt+W": (MOD_WIN | MOD_ALT | MOD_NOREPEAT, 0x57),  # 0x57 = 'W'
    "Ctrl+Alt+W": (MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, 0x57),
    "Win+Shift+W": (MOD_WIN | MOD_SHIFT | MOD_NOREPEAT, 0x57),
}


class GlobalHotkeyListener:
    """Manages registering, listening for, and unregistering Windows global hotkeys."""

    def __init__(self, combo: str = "Win+Alt+W", on_triggered: Optional[Callable[[], None]] = None):
        self.combo = combo
        self.on_triggered = on_triggered
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._thread_id: Optional[int] = None
        self._hotkey_id = 1001

    @classmethod
    def is_supported(cls) -> bool:
        return os.name == "nt"

    def start(self) -> bool:
        """Start listening for the global hotkey on a background daemon thread."""
        if not self.is_supported():
            return False
        if self._thread and self._thread.is_alive():
            return True

        self._stop_event.clear()
        started_event = threading.Event()
        success = [False]

        def _worker():
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            self._thread_id = kernel32.GetCurrentThreadId()

            modifiers, vk = HOTKEY_COMBOS.get(self.combo, (MOD_WIN | MOD_ALT | MOD_NOREPEAT, 0x57))

            # Register hotkey for this background thread
            res = user32.RegisterHotKey(None, self._hotkey_id, modifiers, vk)
            if not res:
                # Try without MOD_NOREPEAT for maximum compatibility
                res = user32.RegisterHotKey(None, self._hotkey_id, modifiers & ~MOD_NOREPEAT, vk)

            success[0] = bool(res)
            started_event.set()

            if not res:
                return

            msg = wintypes.MSG()
            while not self._stop_event.is_set():
                has_msg = user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1)  # 1 = PM_REMOVE
                if has_msg:
                    if msg.message == WM_QUIT:
                        break
                    elif msg.message == WM_HOTKEY and msg.wParam == self._hotkey_id:
                        if self.on_triggered:
                            try:
                                self.on_triggered()
                            except Exception:
                                pass
                else:
                    time.sleep(0.05)

            user32.UnregisterHotKey(None, self._hotkey_id)

        self._thread = threading.Thread(target=_worker, daemon=True, name="GlobalHotkeyThread")
        self._thread.start()
        started_event.wait(timeout=1.0)
        return success[0]

    def stop(self) -> None:
        """Stop hotkey listening and unregister from Windows."""
        self._stop_event.set()
        if self._thread_id and os.name == "nt":
            try:
                ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)
        self._thread = None
        self._thread_id = None

    def update_combo(self, new_combo: str) -> bool:
        """Dynamically rebind hotkey to a new combination."""
        if new_combo == self.combo and self._thread and self._thread.is_alive():
            return True
        self.stop()
        self.combo = new_combo
        return self.start()
