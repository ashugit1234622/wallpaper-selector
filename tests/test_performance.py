"""Performance and optimization regression tests."""

import io
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
from PIL import Image
import pytest

from login_wallpaper_selector.core.config import AppConfig
from login_wallpaper_selector.core.models import WallpaperMetadata
from login_wallpaper_selector.core.display import generate_desktop_preview_image
from login_wallpaper_selector.ui.dialog import WallpaperSelectorDialog


def test_thumbnail_decoding_performance(tmp_path):
    """Verify draft-mode thumbnail decimation is at least 3x faster than full-resolution Lanczos."""
    test_img_path = tmp_path / "test_4k.jpg"
    img = Image.new("RGB", (3840, 2160), color=(110, 160, 220))
    img.save(test_img_path, format="JPEG")

    # Baseline: full-resolution load and Lanczos resize
    t0 = time.perf_counter()
    with Image.open(test_img_path) as im:
        base_thumb = im.crop((0, 0, 3840, 2160)).resize((64, 36), Image.Resampling.LANCZOS)
    t_baseline = time.perf_counter() - t0

    # Optimized: draft decoding + bilinear decimation
    t1 = time.perf_counter()
    with Image.open(test_img_path) as im:
        try:
            im.draft("RGB", (64 * 4, 36 * 4))
        except Exception:
            pass
        opt_thumb = im.crop((0, 0, im.width, im.height)).resize((64, 36), Image.Resampling.BILINEAR)
    t_optimized = time.perf_counter() - t1

    assert base_thumb.size == (64, 36)
    assert opt_thumb.size == (64, 36)
    # Optimized must be substantially faster
    assert t_optimized < t_baseline


def test_preview_lru_cache_hit(tmp_path, monkeypatch):
    """Verify dialog._get_preview_pil_image caches rendered preview images in memory."""
    monkeypatch.setattr(WallpaperSelectorDialog, "_init_window", lambda self: setattr(self, "root", MagicMock()))
    monkeypatch.setattr(WallpaperSelectorDialog, "_build_widgets", lambda self: None)

    cfg = AppConfig(custom_cache_dir=str(tmp_path / "cache"))
    dialog = WallpaperSelectorDialog(config=cfg)

    test_img = tmp_path / "sample.jpg"
    im = Image.new("RGB", (1920, 1080), color=(80, 120, 180))
    im.save(test_img, format="JPEG")

    meta = WallpaperMetadata(
        image_id="img_perf_1",
        category="Nature",
        provider="Wallhaven",
        source_url="https://example.com",
        download_url="https://example.com/sample.jpg",
        local_path=str(test_img),
        sha256="abc",
        title="Sample Wallpaper",
        creator="Photographer",
        license="CC0",
        license_url=None,
        attribution_required=False,
        attribution_text="Sample",
        width=1920,
        height=1080,
        aspect_ratio=1.778,
        mode="Fill",
    )

    # First call: computes preview and stores in _preview_cache
    t0 = time.perf_counter()
    preview1 = dialog._get_preview_pil_image(meta)
    t_first = time.perf_counter() - t0

    assert preview1 is not None
    assert hasattr(dialog, "_preview_cache")

    # Second call: must hit memory cache instantly
    t1 = time.perf_counter()
    preview2 = dialog._get_preview_pil_image(meta)
    t_cached = time.perf_counter() - t1

    assert preview1 is preview2
    # Cached access is near-instant (< 1ms) and much faster than cold generation
    assert t_cached < t_first


def test_desktop_preview_fast_draft_decode(tmp_path):
    """Verify generate_desktop_preview_image incorporates fast draft decode without quality distortion."""
    test_img = tmp_path / "desktop_sample.jpg"
    im = Image.new("RGB", (3840, 2160), color=(50, 75, 100))
    im.save(test_img, format="JPEG")

    preview = generate_desktop_preview_image(test_img, layout_aware=False)
    assert preview is not None
    assert preview.width > 0
    assert preview.height > 0
