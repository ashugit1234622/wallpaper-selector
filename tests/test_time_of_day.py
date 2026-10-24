"""Unit tests for Dynamic Time-of-Day wallpaper themes and rotation integration."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from login_wallpaper_selector.core.time_of_day import (
    TimeOfDaySlot,
    get_current_time_of_day_slot,
    get_time_of_day_keywords,
    select_time_of_day_keywords,
    TIME_OF_DAY_THEMES,
    TIME_OF_DAY_KEYWORDS,
)
from login_wallpaper_selector.core.models import WallpaperCategory, WallpaperMetadata
from login_wallpaper_selector.core.config import AppConfig
from login_wallpaper_selector.core.scheduler import WallpaperRotationDaemon


def test_time_of_day_slot_hour_ranges():
    # Morning: 7 AM to 11 AM (7 <= hour < 11)
    assert get_current_time_of_day_slot(datetime(2026, 10, 24, 7, 0)) == TimeOfDaySlot.MORNING
    assert get_current_time_of_day_slot(datetime(2026, 10, 24, 9, 30)) == TimeOfDaySlot.MORNING
    assert get_current_time_of_day_slot(datetime(2026, 10, 24, 10, 59)) == TimeOfDaySlot.MORNING

    # Midday: 11 AM to 2 PM (11 <= hour < 14)
    assert get_current_time_of_day_slot(datetime(2026, 10, 24, 11, 0)) == TimeOfDaySlot.MIDDAY
    assert get_current_time_of_day_slot(datetime(2026, 10, 24, 12, 45)) == TimeOfDaySlot.MIDDAY
    assert get_current_time_of_day_slot(datetime(2026, 10, 24, 13, 59)) == TimeOfDaySlot.MIDDAY

    # Afternoon: 2 PM to 6 PM (14 <= hour < 18)
    assert get_current_time_of_day_slot(datetime(2026, 10, 24, 14, 0)) == TimeOfDaySlot.AFTERNOON
    assert get_current_time_of_day_slot(datetime(2026, 10, 24, 16, 20)) == TimeOfDaySlot.AFTERNOON
    assert get_current_time_of_day_slot(datetime(2026, 10, 24, 17, 59)) == TimeOfDaySlot.AFTERNOON

    # Evening and Night: 6 PM to 7 AM (hour >= 18 or hour < 7)
    assert get_current_time_of_day_slot(datetime(2026, 10, 24, 18, 0)) == TimeOfDaySlot.NIGHT
    assert get_current_time_of_day_slot(datetime(2026, 10, 24, 21, 0)) == TimeOfDaySlot.NIGHT
    assert get_current_time_of_day_slot(datetime(2026, 10, 24, 23, 59)) == TimeOfDaySlot.NIGHT
    assert get_current_time_of_day_slot(datetime(2026, 10, 24, 0, 0)) == TimeOfDaySlot.NIGHT
    assert get_current_time_of_day_slot(datetime(2026, 10, 24, 3, 30)) == TimeOfDaySlot.NIGHT
    assert get_current_time_of_day_slot(datetime(2026, 10, 24, 6, 59)) == TimeOfDaySlot.NIGHT


def test_time_of_day_keywords_match_spec():
    expected_morning = [
        "Sunrise", "Sunshine", "Flowers", "Nature", "Mountains",
        "Beach", "Blue Sky", "Rainbow", "Spring", "Birds",
        "Garden", "Green", "Colorful", "Happy", "Bright",
        "Morning", "Sunset", "Butterflies", "Lake", "Happiness",
    ]
    expected_midday = [
        "Forest", "Trees", "Waterfall", "Ocean", "River",
        "Mountains", "Wildlife", "Flowers", "Nature", "Lake",
        "Green", "Desert", "Beach", "Garden", "Sunlight",
        "Earth", "Jungle", "Animals", "Landscape", "Tropical",
    ]
    expected_afternoon = [
        "Space", "Galaxy", "Nebula", "Planets", "Stars",
        "Moon", "Saturn", "Astronaut", "Earth", "Universe",
        "Cosmos", "Rocket", "Astronomy", "Sci-Fi", "Cyberpunk",
        "Fantasy", "Robots", "Futuristic", "Aliens", "Comet",
    ]
    expected_night = [
        "Dark", "Horror", "Creepy", "Ghost", "Haunted",
        "Scary", "Night", "Moonlight", "Fog", "Castle",
        "Skull", "Gothic", "Shadow", "Raven", "Bats",
        "Cemetery", "Vampire", "Zombie", "Abandoned", "Mystery",
        "Monster", "Skeleton", "Witch", "Demon", "Graveyard",
        "Storm", "Eerie", "Halloween", "Darkness", "Nightmare",
    ]

    assert get_time_of_day_keywords(TimeOfDaySlot.MORNING) == expected_morning
    assert get_time_of_day_keywords(TimeOfDaySlot.MIDDAY) == expected_midday
    assert get_time_of_day_keywords(TimeOfDaySlot.AFTERNOON) == expected_afternoon
    assert get_time_of_day_keywords(TimeOfDaySlot.NIGHT) == expected_night


def test_select_time_of_day_keywords():
    slot = TimeOfDaySlot.AFTERNOON
    all_kws = get_time_of_day_keywords(slot)

    # Primary and fallback must be distinct
    primary, fallback = select_time_of_day_keywords(slot)
    assert primary in all_kws
    assert fallback in all_kws
    assert primary != fallback

    # Avoid recent keywords
    recent = ["Nebula", "Galaxy", "Space", "Planets"]
    p2, f2 = select_time_of_day_keywords(slot, recent_keywords=recent)
    assert p2.lower() not in [r.lower() for r in recent]
    assert f2.lower() not in [r.lower() for r in recent]


def test_metadata_time_of_day_roundtrip(tmp_path: Path):
    f = tmp_path / "sample.jpg"
    f.write_bytes(b"image")

    meta = WallpaperMetadata(
        image_id="tod_1",
        category="General",
        provider="Wallhaven",
        source_url="https://example.com",
        download_url="https://example.com/dl.jpg",
        local_path=str(f),
        sha256="123",
        title="Cosmic Nebula",
        creator="Artist",
        license="CC0",
        license_url=None,
        attribution_required=False,
        attribution_text="By Artist",
        width=1920,
        height=1080,
        aspect_ratio=1.778,
        mode="Fill",
        time_of_day_slot="Afternoon",
        time_of_day_keyword="Nebula",
        time_of_day_info="Afternoon Theme: 'Nebula'",
    )

    d = meta.to_dict()
    assert d["time_of_day_slot"] == "Afternoon"
    assert d["time_of_day_keyword"] == "Nebula"
    assert d["time_of_day_info"] == "Afternoon Theme: 'Nebula'"

    restored = WallpaperMetadata.from_dict(d)
    assert restored.time_of_day_slot == "Afternoon"
    assert restored.time_of_day_keyword == "Nebula"
    assert restored.time_of_day_info == "Afternoon Theme: 'Nebula'"


def test_daemon_rotate_now_uses_time_of_day(tmp_path: Path):
    f = tmp_path / "tod_applied.jpg"
    f.write_bytes(b"content")

    cfg = AppConfig(custom_cache_dir=str(tmp_path))
    daemon = WallpaperRotationDaemon(config=cfg)

    fake_meta = WallpaperMetadata(
        image_id="img_100",
        category="General",
        provider="Wallhaven",
        source_url="https://example.com",
        download_url="https://example.com/dl.jpg",
        local_path=str(f),
        sha256="456",
        title="Morning Rays",
        creator="Photographer",
        license="CC0",
        license_url=None,
        attribution_required=False,
        attribution_text="By Photographer",
        width=1920,
        height=1080,
        aspect_ratio=1.778,
        mode="Fill",
    )

    daemon.router.acquire_wallpaper_for_category = MagicMock(return_value=(fake_meta, None))
    daemon.adapter.set_wallpaper = MagicMock(return_value=True)

    with patch("login_wallpaper_selector.core.scheduler.get_current_time_of_day_slot", return_value=TimeOfDaySlot.MORNING):
        meta, err = daemon.rotate_now()

    assert err is None
    assert meta is not None
    assert meta.time_of_day_slot == "Morning"
    assert meta.time_of_day_keyword in get_time_of_day_keywords(TimeOfDaySlot.MORNING)
    assert "Morning Theme:" in meta.time_of_day_info

    # Router was called with category=None and keyword set
    call_kwargs = daemon.router.acquire_wallpaper_for_category.call_args[1]
    assert call_kwargs.get("category") is None
    assert call_kwargs.get("keyword") == meta.time_of_day_keyword


def test_daemon_rotate_now_fallback_retry(tmp_path: Path):
    f = tmp_path / "fallback.jpg"
    f.write_bytes(b"content")

    cfg = AppConfig(custom_cache_dir=str(tmp_path))
    daemon = WallpaperRotationDaemon(config=cfg)

    fake_meta = WallpaperMetadata(
        image_id="img_fallback",
        category="General",
        provider="Wallhaven",
        source_url="https://example.com",
        download_url="https://example.com/dl.jpg",
        local_path=str(f),
        sha256="789",
        title="Night Gothic Castle",
        creator="Artist",
        license="CC0",
        license_url=None,
        attribution_required=False,
        attribution_text="By Artist",
        width=1920,
        height=1080,
        aspect_ratio=1.778,
        mode="Fill",
    )

    # First keyword search fails, second succeeds
    daemon.router.acquire_wallpaper_for_category = MagicMock(side_effect=[
        (None, "First keyword failed"),
        (fake_meta, None),
    ])
    daemon.adapter.set_wallpaper = MagicMock(return_value=True)

    with patch("login_wallpaper_selector.core.scheduler.get_current_time_of_day_slot", return_value=TimeOfDaySlot.NIGHT):
        meta, err = daemon.rotate_now()

    assert err is None
    assert meta is not None
    assert meta.time_of_day_slot == "Evening and Night"
    assert daemon.router.acquire_wallpaper_for_category.call_count == 2


def test_daemon_rotate_now_explicit_category_overrides_tod(tmp_path: Path):
    f = tmp_path / "space.jpg"
    f.write_bytes(b"content")

    cfg = AppConfig(custom_cache_dir=str(tmp_path))
    daemon = WallpaperRotationDaemon(config=cfg)

    fake_meta = WallpaperMetadata(
        image_id="img_space",
        category="Space",
        provider="NASA",
        source_url="https://example.com",
        download_url="https://example.com/dl.jpg",
        local_path=str(f),
        sha256="abc",
        title="Deep Space",
        creator="NASA",
        license="Public Domain",
        license_url=None,
        attribution_required=False,
        attribution_text="NASA",
        width=1920,
        height=1080,
        aspect_ratio=1.778,
        mode="Fill",
    )

    daemon.router.acquire_wallpaper_for_category = MagicMock(return_value=(fake_meta, None))
    daemon.adapter.set_wallpaper = MagicMock(return_value=True)

    meta, err = daemon.rotate_now(category=WallpaperCategory.SPACE)
    assert err is None
    assert meta is not None
    call_kwargs = daemon.router.acquire_wallpaper_for_category.call_args[1]
    assert call_kwargs.get("category") == WallpaperCategory.SPACE
    assert "keyword" not in call_kwargs or call_kwargs.get("keyword") is None
