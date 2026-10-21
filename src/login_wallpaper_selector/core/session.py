"""Session readiness detector to ensure the GUI dialog launches only after the desktop environment is active."""

from __future__ import annotations
import os
import sys
import time
from typing import Callable, Optional


class SessionDetector:
    """Detects when the desktop session is ready for graphical interaction."""

    def __init__(self, stabilization_delay_seconds: int = 3, max_wait_seconds: int = 30):
        self.stabilization_delay = stabilization_delay_seconds
        self.max_wait = max_wait_seconds

    def is_desktop_ready(self) -> bool:
        """Non-blocking check whether desktop environment is currently rendered."""
        if sys.platform == "win32":
            return self._is_windows_ready()
        elif sys.platform.startswith("linux"):
            return self._is_linux_ready()
        elif sys.platform == "darwin":
            return self._is_macos_ready()
        return True

    def _is_windows_ready(self) -> bool:
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            # Check for Progman (Program Manager / Windows Desktop window)
            hwnd_progman = user32.FindWindowW("Progman", None)
            if hwnd_progman and user32.IsWindowVisible(hwnd_progman):
                return True
            
            # Alternative: WorkerW (often present behind icons in modern Windows 10/11)
            hwnd_worker = user32.FindWindowW("WorkerW", None)
            if hwnd_worker and user32.IsWindowVisible(hwnd_worker):
                return True
            return False
        except Exception:
            return True

    def _is_linux_ready(self) -> bool:
        # Check display environment variables
        has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
        if not has_display:
            return False
        return True

    def _is_macos_ready(self) -> bool:
        return True

    def wait_until_ready(self, log_fn: Optional[Callable[[str], None]] = None) -> bool:
        """Poll until desktop is ready or timeout expires, then wait stabilization delay."""
        start_time = time.time()
        ready = False

        if log_fn:
            log_fn("Verifying desktop session readiness...")

        while time.time() - start_time < self.max_wait:
            if self.is_desktop_ready():
                ready = True
                break
            time.sleep(0.5)

        if ready:
            if log_fn:
                log_fn(f"Desktop ready. Waiting {self.stabilization_delay}s stabilization delay...")
            time.sleep(self.stabilization_delay)
            return True
        else:
            if log_fn:
                log_fn("Session timeout reached; proceeding with startup.")
            return False
