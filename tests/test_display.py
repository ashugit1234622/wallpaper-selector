"""Unit tests for monitor resolution detection and 1:1 display rendering."""

from pathlib import Path
from PIL import Image
from login_wallpaper_selector.core.display import (
    get_native_screen_resolution,
    get_screen_aspect_ratio,
    render_wallpaper_for_screen,
)
from login_wallpaper_selector.core.models import WallpaperPosition


def test_native_resolution_detection():
    w, h = get_native_screen_resolution()
    assert isinstance(w, int) and w >= 800
    assert isinstance(h, int) and h >= 600

    ratio = get_screen_aspect_ratio()
    assert isinstance(ratio, float) and ratio > 0.5


def test_render_wallpaper_for_screen_fill(tmp_path):
    source = tmp_path / "source.jpg"
    out_fill = tmp_path / "out_fill.jpg"

    # Create a source image with arbitrary dimensions (e.g. 3000x2000)
    img = Image.new("RGB", (3000, 2000), color=(120, 80, 200))
    img.save(source, format="JPEG")

    # Render to target 1920x1080
    success = render_wallpaper_for_screen(
        source_path=source,
        output_path=out_fill,
        target_width=1920,
        target_height=1080,
        mode=WallpaperPosition.FILL.value,
    )
    assert success is True
    assert out_fill.exists()

    with Image.open(out_fill) as out_img:
        assert out_img.size == (1920, 1080)


def test_render_wallpaper_for_screen_fit(tmp_path):
    source = tmp_path / "source_tall.jpg"
    out_fit = tmp_path / "out_fit.jpg"

    # Create a tall portrait image (e.g. 1500x2500)
    img = Image.new("RGB", (1500, 2500), color=(60, 180, 120))
    img.save(source, format="JPEG")

    # Render to target 1920x1080 in FIT mode
    success = render_wallpaper_for_screen(
        source_path=source,
        output_path=out_fit,
        target_width=1920,
        target_height=1080,
        mode=WallpaperPosition.FIT.value,
    )
    assert success is True
    assert out_fit.exists()

    with Image.open(out_fit) as out_img:
        assert out_img.size == (1920, 1080)
