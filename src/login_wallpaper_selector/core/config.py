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
            return cls(
                default_position=data.get("default_position", WallpaperPosition.FILL.value),
                cache_quota_mb=int(data.get("cache_quota_mb", 500)),
                session_delay_seconds=int(data.get("session_delay_seconds", 3)),
                request_timeout_seconds=int(data.get("request_timeout_seconds", 12)),
                history_limit=int(data.get("history_limit", 50)),
                theme=data.get("theme", "System"),
                show_preview=bool(data.get("show_preview", True)),
                custom_cache_dir=data.get("custom_cache_dir"),
                max_fetch_retries=int(data.get("max_fetch_retries", 5)),
                also_set_lockscreen=bool(data.get("also_set_lockscreen", False)),
                anti_repetition_days=int(data.get("anti_repetition_days", 14)),
                anti_repetition_enabled=bool(data.get("anti_repetition_enabled", True)),
                desktop_layout_awareness=bool(data.get("desktop_layout_awareness", True)),
                rotation_enabled=bool(data.get("rotation_enabled", False)),
                rotation_interval_minutes=int(data.get("rotation_interval_minutes", 180)),
                rotation_category=str(data.get("rotation_category", "Any")),
                seasonal_theme_enabled=bool(data.get("seasonal_theme_enabled", False)),
                preview_before_apply=bool(data.get("preview_before_apply", True)),
            )
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
