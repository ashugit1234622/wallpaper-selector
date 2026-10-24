"""Unit tests for the CleanMyTV Android TV bridge integration."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from PIL import Image

from login_wallpaper_selector.core.tv_bridge import (
    TvBridge,
    get_cleanmytv_dir,
    resolve_tv_host,
    prepare_tv_wallpaper,
    ensure_bridge_script,
    DEFAULT_TV_HOST,
)


@pytest.fixture
def sample_image(tmp_path: Path) -> Path:
    """Create a temporary test image (2000x1000 - wider than 16:9)."""
    img_path = tmp_path / "test_wide.png"
    img = Image.new("RGBA", (2000, 1000), color=(100, 150, 200, 255))
    img.save(img_path, "PNG")
    return img_path


@pytest.fixture
def sample_tall_image(tmp_path: Path) -> Path:
    """Create a temporary test image (1000x2000 - portrait)."""
    img_path = tmp_path / "test_tall.jpg"
    img = Image.new("RGB", (1000, 2000), color=(200, 100, 50))
    img.save(img_path, "JPEG")
    return img_path


def test_resolve_tv_host():
    """Verify host resolution with explicit config, fallback, and defaults."""
    assert resolve_tv_host("192.168.1.99") == "192.168.1.99"
    assert resolve_tv_host("  192.168.1.50  ") == "192.168.1.50"


def test_get_cleanmytv_dir(tmp_path: Path):
    """Verify CleanMyTV directory resolution."""
    custom_dir = tmp_path / "my_clean_tv"
    custom_dir.mkdir()
    assert get_cleanmytv_dir(str(custom_dir)) == custom_dir


def test_prepare_tv_wallpaper_rgb_and_crop(sample_image: Path, sample_tall_image: Path):
    """Verify prepare_tv_wallpaper converts RGBA to RGB JPEG and crops to 16:9."""
    # Test wide image with 16:9 crop
    out_wide = prepare_tv_wallpaper(sample_image, crop_16_9=True)
    assert out_wide.exists()
    assert out_wide.suffix.lower() == ".jpg"
    with Image.open(out_wide) as img:
        assert img.mode == "RGB"
        ratio = img.width / float(img.height)
        assert abs(ratio - (16.0 / 9.0)) < 0.05

    # Test tall image with 16:9 crop
    out_tall = prepare_tv_wallpaper(sample_tall_image, crop_16_9=True)
    assert out_tall.exists()
    with Image.open(out_tall) as img:
        assert img.mode == "RGB"
        ratio = img.width / float(img.height)
        assert abs(ratio - (16.0 / 9.0)) < 0.05


def test_prepare_tv_wallpaper_missing_file(tmp_path: Path):
    """Verify FileNotFoundError on missing source."""
    missing = tmp_path / "non_existent.jpg"
    with pytest.raises(FileNotFoundError):
        prepare_tv_wallpaper(missing)


def test_tv_bridge_test_connection_success():
    """Verify test_connection returns True when bridge script reports success."""
    bridge = TvBridge(host="192.168.1.37")

    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = json.dumps({
        "status": "ok",
        "mode": "test",
        "model": "MiTV-MZTU0",
        "device": "river",
    })
    mock_res.stderr = ""

    with patch("subprocess.run", return_value=mock_res):
        success, message = bridge.test_connection()
        assert success is True
        assert "MiTV-MZTU0" in message


def test_tv_bridge_test_connection_failure():
    """Verify test_connection returns False and error message on failure."""
    bridge = TvBridge(host="192.168.1.37")

    mock_res = MagicMock()
    mock_res.returncode = 1
    mock_res.stdout = json.dumps({
        "status": "error",
        "code": "connection_failed",
        "message": "Connection refused to 192.168.1.37:5555",
    })
    mock_res.stderr = ""

    with patch("subprocess.run", return_value=mock_res):
        success, message = bridge.test_connection()
        assert success is False
        assert "Connection refused" in message


def test_tv_bridge_apply_wallpaper_success(sample_image: Path):
    """Verify apply_wallpaper executes and triggers progress callback and success."""
    bridge = TvBridge(host="192.168.1.37")

    progress_events = []
    def on_progress(pct, msg):
        progress_events.append((pct, msg))

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout.readline.side_effect = [
        json.dumps({"status": "connecting", "message": "Connecting...", "progress": 0.1}) + "\n",
        json.dumps({"status": "pushing", "message": "Uploading chunk 1/2...", "progress": 0.5}) + "\n",
        json.dumps({"status": "ok", "message": "Wallpaper updated successfully!", "progress": 1.0}) + "\n",
        "",
    ]
    mock_proc.stderr.read.return_value = ""

    with patch("subprocess.Popen", return_value=mock_proc):
        success, msg = bridge.apply_wallpaper(sample_image, on_progress=on_progress)
        assert success is True
        assert "Wallpaper updated" in msg
        assert len(progress_events) >= 3


def test_tv_bridge_apply_wallpaper_missing_file(tmp_path: Path):
    """Verify apply_wallpaper fails gracefully if image file doesn't exist."""
    bridge = TvBridge()
    missing = tmp_path / "does_not_exist.jpg"
    success, msg = bridge.apply_wallpaper(missing)
    assert success is False
    assert "not found" in msg.lower()


def test_prepare_tv_wallpaper_exact_4k_output(tmp_path: Path):
    """Verify prepare_tv_wallpaper produces exactly 3840x2160 UHD output."""
    small_img_path = tmp_path / "small_source.png"
    Image.new("RGBA", (1920, 1080), color=(50, 120, 220, 255)).save(small_img_path)

    out = prepare_tv_wallpaper(small_img_path, crop_16_9=True)
    assert out.exists()
    with Image.open(out) as img:
        assert img.size == (3840, 2160)
        assert img.mode == "RGB"


def test_router_tv_4k_resolution_filtering(tmp_path: Path):
    """Verify router skips images under 3840x2160 in TV mode and accepts 4K images."""
    from login_wallpaper_selector.providers.router import ProviderRouter
    from login_wallpaper_selector.core.config import AppConfig
    from login_wallpaper_selector.core.history import HistoryTracker
    from login_wallpaper_selector.core.cache import CacheManager
    from login_wallpaper_selector.core.models import WallpaperCandidate, WallpaperCategory

    cfg = AppConfig(custom_cache_dir=str(tmp_path / "cache"), max_fetch_retries=5)
    hist = HistoryTracker(cfg)
    cache = CacheManager(cfg)
    router = ProviderRouter(cfg, hist, cache)

    # Candidate 1: 1080p (low res)
    cand_1080p = WallpaperCandidate(
        id="cand_1080p",
        category=WallpaperCategory.NATURE,
        provider_name="TestProvider",
        title="1080p Image",
        download_url="https://example.com/1080p.jpg",
        source_url="https://example.com/1080p",
        creator="Photographer",
        license_name="CC0",
        license_url="",
        attribution_required=False,
        attribution_text="",
        preview_url="",
        width=1920,
        height=1080,
    )

    # Candidate 2: 4K UHD
    cand_4k = WallpaperCandidate(
        id="cand_4k",
        category=WallpaperCategory.NATURE,
        provider_name="TestProvider",
        title="4K UHD Image",
        download_url="https://example.com/4k.jpg",
        source_url="https://example.com/4k",
        creator="Photographer",
        license_name="CC0",
        license_url="",
        attribution_required=False,
        attribution_text="",
        preview_url="",
        width=3840,
        height=2160,
    )

    # Mock fetch_candidates to return both candidates
    router.fetch_candidates = MagicMock(return_value=[cand_1080p, cand_4k])

    # Mock download_candidate to save corresponding real image files
    def fake_download(cand, progress_cb=None):
        out_f = tmp_path / f"{cand.id}.jpg"
        if cand.id == "cand_1080p":
            Image.new("RGB", (1920, 1080), color=(100, 100, 100)).save(out_f)
        else:
            Image.new("RGB", (3840, 2160), color=(120, 150, 180)).save(out_f)
        return out_f

    router.download_candidate = MagicMock(side_effect=fake_download)

    meta, err = router.acquire_wallpaper_for_category(
        category=WallpaperCategory.NATURE,
        search_for_tv=True,
    )

    assert meta is not None
    assert meta.image_id == "cand_4k"
    assert meta.width == 3840
    assert meta.height == 2160
