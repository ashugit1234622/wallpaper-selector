"""Configuration management for Login Wallpaper Selector."""

from __future__ import annotations
import json
import os
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional
from platformdirs import user_config_dir, user_cache_dir, user_data_dir

from .models import WallpaperPosition


@dataclass
class AppConfig:
    default_position: str = WallpaperPosition.FILL.value
    cache_quota_mb: int = 500
    session_delay_seconds: int = 3
    request_timeout_seconds: int = 12
    history_limit: int = 50
    theme: str = "System"  # "System", "Dark", "Light"
    show_preview: bool = True
    custom_cache_dir: Optional[str] = None
    max_fetch_retries: int = 5
    also_set_lockscreen: bool = False
    anti_repetition_days: int = 14
    anti_repetition_enabled: bool = True
    desktop_layout_awareness: bool = True
    rotation_enabled: bool = False
    rotation_interval_minutes: int = 180
    rotation_category: str = "Any"
    seasonal_theme_enabled: bool = False
    preview_before_apply: bool = True
    check_for_updates_on_startup: bool = True
    github_repo: str = "ashugit1234622/wallpaper-selector"
    last_update_check_timestamp: Optional[str] = None
    update_check_interval_hours: int = 4
    global_hotkey_enabled: bool = True
    global_hotkey_combo: str = "Ctrl+Alt+W"
    pause_on_battery: bool = True
    target_monitor_id: Optional[str] = None  # None means all monitors

    organizer_last_folder: Optional[str] = None
    organizer_mode: str = "by_type"  # "by_type", "by_date", "by_type_and_date"
    organizer_destination: Optional[str] = None
    organizer_recursive: bool = False
    organizer_conflict_policy: str = "keep_both"  # "keep_both", "skip"

    # Android TV (CleanMyTV) Bridge integration
    search_for_tv: bool = False
    tv_host: str = "192.168.1.37"
    cleanmytv_dir: str = r"C:\Users\Ashirwad\Desktop\projects\clean my tv"

    @classmethod
    def get_config_file_path(cls) -> Path:
        base_dir = Path(user_config_dir("LoginWallpaperSelector", appauthor=False))
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir / "config.json"

    @classmethod
    def get_default_cache_dir(cls) -> Path:
        base_dir = Path(user_cache_dir("LoginWallpaperSelector", appauthor=False))
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir

    @classmethod
    def get_default_data_dir(cls) -> Path:
        base_dir = Path(user_data_dir("LoginWallpaperSelector", appauthor=False))
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir

    @classmethod
    def load(cls) -> "AppConfig":
        config_path = cls.get_config_file_path()
        if not config_path.exists():
            cfg = cls()
            cfg.save()
            return cfg

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            import dataclasses
            valid_fields = {f.name for f in dataclasses.fields(cls)}
            filtered = {k: v for k, v in data.items() if k in valid_fields}
            # Migrate legacy Windows-conflicting Win+Alt+W default to Ctrl+Alt+W
            if filtered.get("global_hotkey_combo") == "Win+Alt+W":
                filtered["global_hotkey_combo"] = "Ctrl+Alt+W"
            return cls(**filtered)
        except Exception:
            return cls()

    def save(self) -> None:
        config_path = self.get_config_file_path()
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, indent=2)
        except Exception as e:
            # Non-fatal if config saving fails
            pass
