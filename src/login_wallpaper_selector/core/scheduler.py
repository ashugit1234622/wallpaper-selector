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


from .time_of_day import get_current_time_of_day_slot, select_time_of_day_keywords, TimeOfDaySlot
from .power import is_running_on_battery


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
        """Fetch and apply a fresh wallpaper adhering to rotation preferences.
        
        When no explicit category override is provided, dynamically applies the
        curated Time-of-Day theme (Morning, Midday, Afternoon, Evening/Night) using
        independent unrepeated keywords with automatic fallback.
        """
        target_category = category
        if not target_category:
            cfg_cat = getattr(self.config, "rotation_category", "Any")
            if cfg_cat and cfg_cat.lower() != "any":
                for c in self.ONLINE_CATEGORIES:
                    if c.value.lower() == cfg_cat.lower():
                        target_category = c
                        break

        mode = self.config.default_position
        meta: Optional[WallpaperMetadata] = None
        err: Optional[str] = None
        time_slot: Optional[TimeOfDaySlot] = None
        time_kw: Optional[str] = None

        if not target_category:
            # ── Dynamic Time-of-Day Theme Selection ──────────────────────────
            time_slot = get_current_time_of_day_slot()
            recent_titles = [r.title for r in getattr(self.history, "records", [])[-20:]]
            primary_kw, fallback_kw = select_time_of_day_keywords(time_slot, recent_keywords=recent_titles)

            if status_callback:
                status_callback(f"Rotating with {time_slot.value} theme: '{primary_kw}'...", 1, 2)

            # 1. Search primary keyword as a single independent term
            meta, err = self.router.acquire_wallpaper_for_category(
                category=None,
                keyword=primary_kw,
                mode=mode,
                progress_callback=progress_callback,
                status_callback=status_callback,
            )
            time_kw = primary_kw

            # 2. If primary fails, retry with alternative fallback keyword from same slot
            if not meta and fallback_kw and fallback_kw != primary_kw:
                if status_callback:
                    status_callback(f"Retrying {time_slot.value} theme with fallback: '{fallback_kw}'...", 2, 2)
                meta, err = self.router.acquire_wallpaper_for_category(
                    category=None,
                    keyword=fallback_kw,
                    mode=mode,
                    progress_callback=progress_callback,
                    status_callback=status_callback,
                )
                time_kw = fallback_kw

            # 3. Safety net: if both keyword attempts fail, fallback to a category search
            if not meta:
                fallback_cat = random.choice(self.ONLINE_CATEGORIES)
                meta, err = self.router.acquire_wallpaper_for_category(
                    category=fallback_cat,
                    mode=mode,
                    progress_callback=progress_callback,
                    status_callback=status_callback,
                    color=color,
                    mood=mood,
                )
        else:
            # Explicit category rotation
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

        # Tag with Time-of-Day theme info if applicable
        if time_slot and time_kw:
            meta.time_of_day_slot = time_slot.value
            meta.time_of_day_keyword = time_kw
            meta.time_of_day_info = f"{time_slot.value} Theme: '{time_kw}'"

        # Apply to desktop
        target_mon = getattr(self.config, "target_monitor_id", None)
        if target_mon:
            try:
                success = self.adapter.set_wallpaper(Path(meta.local_path), mode=mode, monitor_id=target_mon)
            except TypeError:
                success = self.adapter.set_wallpaper(Path(meta.local_path), mode=mode)
        else:
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
                if getattr(self.config, "pause_on_battery", True) and is_running_on_battery():
                    _log("[*] Wallpaper rotation paused: system running on battery power.")
                elif self.is_rotation_due():
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
