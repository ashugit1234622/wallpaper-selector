"""Tests for Color-Based Image Discovery."""

import pytest
from pathlib import Path
from PIL import Image

from login_wallpaper_selector.core.models import ColorPalette, WallpaperCategory
from login_wallpaper_selector.core.color_analyzer import (
    rgb_to_hex,
    hex_to_rgb,
    extract_dominant_color,
    extract_dominant_color_from_file,
    classify_rgb_to_palette,
    compute_color_match_score,
    get_wallhaven_color_code,
    get_palette_keyword,
)
from login_wallpaper_selector.providers.wallhaven import WallhavenProvider
from login_wallpaper_selector.providers.artic import ArtInstituteChicagoProvider
from login_wallpaper_selector.providers.bing import BingImageProvider


def test_hex_conversions():
    assert rgb_to_hex(255, 0, 128) == "#ff0080"
    assert hex_to_rgb("#ff0080") == (255, 0, 128)
    assert hex_to_rgb("00ff00") == (0, 255, 0)
    assert hex_to_rgb("#f0a") == (255, 0, 170)
    assert hex_to_rgb("invalid") == (0, 0, 0)


def test_classify_rgb_to_palette():
    # Pure blues
    assert classify_rgb_to_palette((0, 100, 255)) == ColorPalette.BLUE
    assert classify_rgb_to_palette((20, 150, 220)) == ColorPalette.BLUE

    # Pure greens
    assert classify_rgb_to_palette((0, 200, 50)) == ColorPalette.GREEN
    assert classify_rgb_to_palette((50, 220, 80)) == ColorPalette.GREEN

    # Pure purples
    assert classify_rgb_to_palette((160, 40, 220)) == ColorPalette.PURPLE
    assert classify_rgb_to_palette((200, 50, 200)) == ColorPalette.PURPLE

    # Warm colors (reds, oranges, warm yellows)
    assert classify_rgb_to_palette((255, 40, 20)) == ColorPalette.WARM
    assert classify_rgb_to_palette((255, 140, 0)) == ColorPalette.WARM
    assert classify_rgb_to_palette((250, 210, 30)) == ColorPalette.WARM

    # Monochrome / Desaturated / Dark
    assert classify_rgb_to_palette((20, 20, 20)) == ColorPalette.MONOCHROME
    assert classify_rgb_to_palette((128, 128, 128)) == ColorPalette.MONOCHROME
    assert classify_rgb_to_palette((245, 245, 245)) == ColorPalette.MONOCHROME


def test_extract_dominant_color(tmp_path: Path):
    # Create a solid blue image
    img = Image.new("RGB", (200, 200), color=(10, 80, 220))
    extracted = extract_dominant_color(img)
    # Extracted should be in the blue hue
    assert classify_rgb_to_palette(extracted) == ColorPalette.BLUE

    # Test file extraction
    img_path = tmp_path / "test_warm.png"
    warm_img = Image.new("RGB", (100, 100), color=(230, 80, 15))
    warm_img.save(img_path)

    extracted_file = extract_dominant_color_from_file(img_path)
    assert classify_rgb_to_palette(extracted_file) == ColorPalette.WARM


def test_compute_color_match_score():
    blue_rgb = (0, 100, 255)
    # ANY matches perfectly
    assert compute_color_match_score(blue_rgb, ColorPalette.ANY) == 1.0

    # Matching palette
    assert compute_color_match_score(blue_rgb, ColorPalette.BLUE) == 1.0

    # Mismatching palette
    assert compute_color_match_score(blue_rgb, ColorPalette.GREEN) == 0.0

    # Custom hex distance matching
    # Exact match -> 1.0
    assert compute_color_match_score((0, 100, 255), ColorPalette.CUSTOM, custom_hex="#0064ff") > 0.98
    # Close match -> high score > 0.8
    assert compute_color_match_score((0, 110, 250), ColorPalette.CUSTOM, custom_hex="#0064ff") > 0.85
    # Far match -> low score
    assert compute_color_match_score((255, 0, 0), ColorPalette.CUSTOM, custom_hex="#0064ff") < 0.5


def test_wallhaven_color_code_mapping():
    assert get_wallhaven_color_code(ColorPalette.ANY) is None
    assert get_wallhaven_color_code(ColorPalette.BLUE) == "0066cc"
    assert get_wallhaven_color_code(ColorPalette.PURPLE) == "793db8"
    assert get_wallhaven_color_code(ColorPalette.GREEN) == "00cc7a"
    assert get_wallhaven_color_code(ColorPalette.WARM) == "e64a19"
    assert get_wallhaven_color_code(ColorPalette.MONOCHROME) == "000000"
    assert get_wallhaven_color_code(ColorPalette.CUSTOM, "#ff5500") == "ff5500"


def test_palette_keyword():
    assert get_palette_keyword(ColorPalette.BLUE) == "blue"
    assert get_palette_keyword(ColorPalette.GREEN) == "green"
    assert get_palette_keyword(ColorPalette.WARM) == "warm"
    assert get_palette_keyword(ColorPalette.ANY) is None


def test_provider_color_integration():
    wallhaven = WallhavenProvider()
    assert wallhaven.supports_color_filtering() is True

    artic = ArtInstituteChicagoProvider()
    assert artic.supports_color_filtering() is True

    bing = BingImageProvider()
    assert bing.supports_color_filtering() is True
