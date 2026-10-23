"""Smart Wallpaper Rotation Scheduler and Background Daemon.

Periodically switches desktop (and optionally lock screen) wallpapers at
configurable intervals (e.g. 30 minutes, 3 hours, daily) across categories.
"""

from __future__ import annotations
import random
import time
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple, Callable

from .config import AppConfig
from .models import WallpaperCategory, WallpaperMetadata, WallpaperMood, ColorPalette
from .history import HistoryTracker
from .cache import CacheManager
from ..providers.router import ProviderRouter
from ..adapters.factory import get_wallpaper_adapter


INTERVAL_MAP = {
    "30m": 30,
    "30min": 30,
    "1h": 60,
    "60m": 60,
    "3h": 180,
    "180m": 180,
    "daily": 1440,
    "24h": 1440,
}


def parse_interval_minutes(val: str | int) -> int:
    """Parse user interval string or integer into minutes."""
    if isinstance(val, int):
        return max(5, val)
    clean = str(val).strip().lower()
    if clean in INTERVAL_MAP:
        return INTERVAL_MAP[clean]
    try:
        minutes = int(clean)
        return max(5, minutes)
    except ValueError:
        return 180  # Default 3 hours


class WallpaperRotationDaemon:
    """Manages scheduled automatic wallpaper changes and single-shot rotations."""

    ONLINE_CATEGORIES = [
        WallpaperCategory.SPACE,
        WallpaperCategory.NATURE,
        WallpaperCategory.ART,
        WallpaperCategory.PORTRAIT,
    ]

    def __init__(
        self,
        config: Optional[AppConfig] = None,
        history: Optional[HistoryTracker] = None,
        cache: Optional[CacheManager] = None,
        router: Optional[ProviderRouter] = None,
    ):
        self.config = config or AppConfig.load()
        self.history = history or HistoryTracker(self.config)
        self.cache = cache or CacheManager(self.config)
        self.router = router or ProviderRouter(self.config, self.history, self.cache)
        self.adapter = get_wallpaper_adapter()
        self._stop_event = threading.Event()

    def get_seconds_until_next_rotation(self) -> float:
        """Calculate how many seconds remain until the next scheduled wallpaper rotation."""
        if hasattr(self.history, "reload"):
            try:
                self.history.reload()
            except Exception:
                pass
        records = self.history.records
        if not records:
            return 0.0

        latest = records[-1]
        try:
            clean_str = latest.applied_at.replace("Z", "+00:00")
            if "+00:00+00:00" in clean_str:
                clean_str = clean_str.replace("+00:00+00:00", "+00:00")
            applied_dt = datetime.fromisoformat(clean_str)
            if applied_dt.tzinfo is None:
                applied_dt = applied_dt.replace(tzinfo=timezone.utc)
            now_dt = datetime.now(timezone.utc)
            elapsed = (now_dt - applied_dt).total_seconds()
            required = self.config.rotation_interval_minutes * 60.0
            return max(0.0, required - elapsed)
        except Exception:
            return 0.0

    def is_rotation_due(self) -> bool:
        """Check if interval threshold has passed since the last applied wallpaper."""
        return self.get_seconds_until_next_rotation() <= 0.0

    def rotate_now(
        self,
        category: Optional[WallpaperCategory] = None,
        mood: Optional[WallpaperMood] = None,
        color: Optional[ColorPalette] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        status_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> Tuple[Optional[WallpaperMetadata], Optional[str]]:
        """Fetch and apply a fresh wallpaper adhering to rotation preferences."""
        # Determine category
        target_category = category
        if not target_category:
            cfg_cat = getattr(self.config, "rotation_category", "Any")
            if cfg_cat and cfg_cat.lower() != "any":
                for c in self.ONLINE_CATEGORIES:
                    if c.value.lower() == cfg_cat.lower():
                        target_category = c
                        break
            if not target_category:
                target_category = random.choice(self.ONLINE_CATEGORIES)

        mode = self.config.default_position
        meta, err = self.router.acquire_wallpaper_for_category(
            category=target_category,
            mode=mode,
            progress_callback=progress_callback,
            status_callback=status_callback,
            color=color,
            mood=mood,
        )

        if not meta:
            return None, err

        # Apply to desktop
        success = self.adapter.set_wallpaper(Path(meta.local_path), mode=mode)
        if not success:
            return None, "Downloaded image successfully, but desktop adapter could not set wallpaper."

        # Optionally set lock screen
        if self.config.also_set_lockscreen:
            try:
                self.adapter.set_lockscreen(Path(meta.local_path))
            except Exception:
                pass

        return meta, None

    def run_loop(
        self,
        stop_event: Optional[threading.Event] = None,
        check_interval_sec: int = 15,
        log_fn: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Continuous rotation loop for background execution."""
        event = stop_event or self._stop_event
        _log = log_fn or print

        _log(f"[*] Wallpaper Rotation Daemon started (Interval: {self.config.rotation_interval_minutes}m, Category: {self.config.rotation_category})")

        while not event.is_set():
            # Reload config dynamically in case user changed interval in GUI
            self.config = AppConfig.load()

            if self.config.rotation_enabled:
                if self.is_rotation_due():
                    _log("[*] Scheduled wallpaper rotation is due. Acquiring fresh wallpaper...")
                    meta, err = self.rotate_now()
                    if meta:
                        _log(f"✓ Rotated to: '{meta.title}' ({meta.category})")
                    else:
                        _log(f"✗ Rotation failed: {err}")
                else:
                    rem = int(self.get_seconds_until_next_rotation())
                    _log(f"[*] Next rotation in {rem // 60}m {rem % 60}s...")

            event.wait(check_interval_sec)

        _log("[*] Wallpaper Rotation Daemon stopped.")

    def stop(self) -> None:
        """Signal the daemon loop to terminate cleanly."""
        self._stop_event.set()
