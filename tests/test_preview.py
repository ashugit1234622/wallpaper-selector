"""Unit tests for the Desktop Screen-Fit and Crop Wallpaper Preview engine."""

from pathlib import Path
from PIL import Image
import pytest

from login_wallpaper_selector.core.display import generate_desktop_preview_image, get_native_screen_resolution
from login_wallpaper_selector.core.models import WallpaperPosition


def create_test_pattern_image(path: Path, width: int, height: int) -> Path:
    img = Image.new("RGB", (width, height), color=(40, 80, 120))
    img.save(path, format="JPEG")
    return path


def test_preview_nonexistent_file(tmp_path):
    res = generate_desktop_preview_image(tmp_path / "nonexistent.jpg")
    assert res is None


def test_preview_fill_mode(tmp_path):
    test_img = create_test_pattern_image(tmp_path / "landscape.jpg", 3840, 2160)
    preview = generate_desktop_preview_image(
        test_img,
        mode=WallpaperPosition.FILL.value,
        max_preview_width=500,
        max_preview_height=200,
    )
    assert preview is not None
    assert isinstance(preview, Image.Image)
    assert preview.width <= 500
    assert preview.height <= 200
    # Aspect ratio should match screen
    screen_w, screen_h = get_native_screen_resolution()
    expected_ratio = screen_w / screen_h
    actual_ratio = preview.width / preview.height
    assert pytest.approx(actual_ratio, rel=0.08) == expected_ratio


def test_preview_fit_mode_pillarbox_for_portrait(tmp_path):
    # Tall portrait image (1080 x 1920)
    test_img = create_test_pattern_image(tmp_path / "portrait.jpg", 1080, 1920)
    preview = generate_desktop_preview_image(
        test_img,
        mode=WallpaperPosition.FIT.value,
        max_preview_width=480,
        max_preview_height=270,
    )
    assert preview is not None
    assert preview.width == 480 or preview.height == 270


def test_preview_fit_mode_letterbox_for_ultrawide(tmp_path):
    # Ultra-wide image (3840 x 1080) in Fit mode
    test_img = create_test_pattern_image(tmp_path / "ultrawide.jpg", 3840, 1080)
    preview = generate_desktop_preview_image(
        test_img,
        mode=WallpaperPosition.FIT.value,
        max_preview_width=500,
        max_preview_height=200,
    )
    assert preview is not None
    assert isinstance(preview, Image.Image)
    assert preview.width <= 500
    assert preview.height <= 200


def test_preview_layout_aware_smart_crop(tmp_path):
    test_img = create_test_pattern_image(tmp_path / "layout_test.jpg", 3840, 2160)
    preview_aware = generate_desktop_preview_image(
        test_img,
        mode=WallpaperPosition.FILL.value,
        layout_aware=True,
    )
    preview_unaware = generate_desktop_preview_image(
        test_img,
        mode=WallpaperPosition.FILL.value,
        layout_aware=False,
    )
    assert preview_aware is not None
    assert preview_unaware is not None
    assert preview_aware.size == preview_unaware.size


def test_dialog_preview_staging_and_apply(tmp_path, monkeypatch):
    """Test dialog preview staging, mode switching, and apply flow."""
    import tkinter as tk
    from unittest.mock import MagicMock
    from login_wallpaper_selector.core.config import AppConfig
    from login_wallpaper_selector.core.models import WallpaperMetadata, WallpaperPosition
    from login_wallpaper_selector.ui.dialog import WallpaperSelectorDialog

    # Mock tkinter / customtkinter window creation so headless CI passes
    monkeypatch.setattr(WallpaperSelectorDialog, "_init_window", lambda self: None)

    cfg = AppConfig(preview_before_apply=True)
    dialog = WallpaperSelectorDialog(config=cfg)
    dialog.adapter = MagicMock()
    dialog.mode_var = MagicMock()
    dialog.mode_var.get.return_value = WallpaperPosition.FILL.value
    dialog.layout_var = MagicMock()
    dialog.layout_var.get.return_value = True
    dialog.lockscreen_var = MagicMock()
    dialog.lockscreen_var.get.return_value = False
    dialog.apply_btn = MagicMock()
    dialog.set_status = MagicMock()
    dialog._render_preview_image = MagicMock()

    test_file = create_test_pattern_image(tmp_path / "staged.jpg", 1920, 1080)
    meta = WallpaperMetadata(
        image_id="test-123",
        category="Nature",
        provider="Unsplash",
        source_url="https://example.com/source",
        download_url="https://example.com/dl",
        local_path=str(test_file),
        sha256="abc",
        title="Alpine Lake",
        creator="Photographer",
        license="Unsplash",
        license_url=None,
        attribution_required=True,
        attribution_text="Photo by Photographer on Unsplash",
        width=1920,
        height=1080,
        aspect_ratio=1.778,
        mode=WallpaperPosition.FILL.value,
    )

    # Stage metadata (as when candidate is found)
    dialog.staged_metadata = meta
    assert dialog.current_metadata is None

    # Trigger mode change (e.g. user toggles Fill -> Fit in GUI)
    dialog.mode_var.get.return_value = WallpaperPosition.FIT.value
    dialog.on_mode_change()
    assert dialog.config.default_position == WallpaperPosition.FIT.value
    dialog._render_preview_image.assert_called_with(meta, mode=WallpaperPosition.FIT.value)

    # User clicks "✓ Apply to Desktop"
    dialog.adapter.set_wallpaper.return_value = True
    dialog.root = MagicMock()
    dialog.on_apply_staged()

    # Verify adapter called with correct target path
    dialog.adapter.set_wallpaper.assert_called_once_with(Path(test_file), mode=WallpaperPosition.FIT.value)


def test_dialog_defaults_to_fill_mode_on_open(monkeypatch):
    """Verify that whenever the dialog opens, the display mode defaults to Fill."""
    from login_wallpaper_selector.core.config import AppConfig
    from login_wallpaper_selector.core.models import WallpaperPosition
    from login_wallpaper_selector.ui.dialog import WallpaperSelectorDialog

    monkeypatch.setattr(WallpaperSelectorDialog, "_init_window", lambda self: None)

    # Even if previous config had Fit, opening app must set it to Fill
    cfg = AppConfig(default_position=WallpaperPosition.FIT.value)
    dialog = WallpaperSelectorDialog(config=cfg)
    assert dialog.config.default_position == WallpaperPosition.FILL.value


def test_dialog_responsive_layout_and_scrollable_container(monkeypatch):
    """Verify that dialog widgets construct a scrollable container and responsive resize handler."""
    from unittest.mock import MagicMock
    from login_wallpaper_selector.core.config import AppConfig
    from login_wallpaper_selector.ui.dialog import WallpaperSelectorDialog

    monkeypatch.setattr(WallpaperSelectorDialog, "_init_window", lambda self: None)

    cfg = AppConfig()
    dialog = WallpaperSelectorDialog(config=cfg)
    dialog.root = MagicMock()
    dialog.attrib_lbl = MagicMock()
    dialog.status_lbl = MagicMock()

    # Simulate resize event configure
    event = MagicMock()
    event.widget = dialog.root
    event.width = 600
    dialog._on_window_configure(event)

    # Wraplength should be adjusted for 600px width
    expected_wrap = 600 - 70
    dialog.attrib_lbl.configure.assert_called_with(wraplength=expected_wrap)
    dialog.status_lbl.configure.assert_called_with(wraplength=expected_wrap)



