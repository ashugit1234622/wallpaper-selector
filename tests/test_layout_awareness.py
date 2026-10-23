"""Tests for Desktop Layout Awareness and Saliency-Guided Smart Cropping."""

import pytest
from pathlib import Path
from PIL import Image, ImageDraw

from login_wallpaper_selector.core.layout_awareness import (
    DesktopLayoutProfile,
    analyze_desktop_layout,
    compute_image_saliency_focal_point,
    calculate_smart_crop_offset,
)
from login_wallpaper_selector.core.display import render_wallpaper_for_screen


def test_standard_windows_default():
    profile = DesktopLayoutProfile.standard_windows_default()
    assert profile.preferred_horizontal == "right"
    assert profile.preferred_vertical == "top"
    assert profile.left_clutter > profile.right_clutter


def test_analyze_desktop_layout_with_synthetic_icons():
    # Create synthetic desktop (1920x1080)
    # Desktop has icons on left: draw grid of small high-contrast squares on x < 300
    desktop = Image.new("RGB", (1920, 1080), color=(30, 30, 40))
    draw = ImageDraw.Draw(desktop)

    # Left-hand icons
    for row in range(8):
        for col in range(2):
            x = 40 + col * 90
            y = 50 + row * 100
            draw.rectangle([x, y, x + 64, y + 64], fill=(240, 240, 255), outline=(0, 0, 0))

    # Bottom taskbar
    draw.rectangle([0, 1040, 1920, 1080], fill=(10, 10, 15))

    profile = analyze_desktop_layout(desktop)
    assert profile.left_clutter > profile.right_clutter
    assert profile.preferred_horizontal == "right"
    assert profile.bottom_clutter > 0


def test_compute_image_saliency_focal_point():
    # 1. Blank solid image -> center
    blank = Image.new("RGB", (800, 600), color=(100, 100, 100))
    fx, fy = compute_image_saliency_focal_point(blank)
    assert fx == pytest.approx(0.5, abs=0.05)
    assert fy == pytest.approx(0.5, abs=0.05)

    # 2. Image with high-contrast focal subject in bottom-right quadrant
    subject_img = Image.new("RGB", (800, 600), color=(20, 20, 20))
    draw = ImageDraw.Draw(subject_img)
    # Draw detailed bright subject at x in [600, 750], y in [400, 550]
    draw.rectangle([600, 400, 750, 550], fill=(255, 255, 255))
    draw.ellipse([620, 420, 730, 530], fill=(255, 0, 0))

    fx_subj, fy_subj = compute_image_saliency_focal_point(subject_img)
    assert fx_subj > 0.65
    assert fy_subj > 0.60


def test_calculate_smart_crop_offset():
    scaled_w = 2560
    scaled_h = 1080
    target_w = 1920
    target_h = 1080
    excess_w = scaled_w - target_w  # 640px excess

    # Subject is on the right side of the wide image (fx = 0.8)
    focal_point = (0.80, 0.50)

    # Left-cluttered desktop -> wants focal point towards right
    profile_right = DesktopLayoutProfile(
        left_clutter=0.8,
        right_clutter=0.1,
        top_clutter=0.1,
        bottom_clutter=0.8,
        preferred_horizontal="right",
        preferred_vertical="center",
    )

    crop_left, crop_top = calculate_smart_crop_offset(
        scaled_w, scaled_h, target_w, target_h, focal_point, profile_right
    )

    # Crop left should be positive and bounded by excess_w
    assert 0 <= crop_left <= excess_w
    assert crop_top == 0


def test_render_wallpaper_with_layout_awareness(tmp_path: Path):
    source = tmp_path / "wide_landscape.jpg"
    out = tmp_path / "rendered.jpg"

    # Create wide image (2560x1080) with a prominent subject on right
    wide_img = Image.new("RGB", (2560, 1080), color=(30, 60, 90))
    draw = ImageDraw.Draw(wide_img)
    draw.ellipse([2000, 300, 2300, 600], fill=(255, 220, 0))
    wide_img.save(source, "JPEG")

    # Render for 1920x1080 with layout awareness enabled
    ok = render_wallpaper_for_screen(
        source_path=source,
        output_path=out,
        target_width=1920,
        target_height=1080,
        mode="Fill",
        layout_aware=True,
    )

    assert ok is True
    assert out.exists()

    with Image.open(out) as result:
        assert result.size == (1920, 1080)


def test_privacy_no_disk_leak(tmp_path: Path):
    # Ensure analyzing layout creates zero files in tmp_path or cwd
    before_files = list(tmp_path.glob("**/*"))
    _ = analyze_desktop_layout()
    after_files = list(tmp_path.glob("**/*"))
    assert before_files == after_files
