"""Unit tests for Local Storage handling and file validation."""

from pathlib import Path
from PIL import Image
from login_wallpaper_selector.core.config import AppConfig
from login_wallpaper_selector.core.cache import CacheManager
from login_wallpaper_selector.core.models import WallpaperPosition


def test_store_local_image_valid(tmp_path):
    cfg = AppConfig(custom_cache_dir=str(tmp_path / "cache"))
    cache = CacheManager(cfg)

    # Create a local user image
    user_images_dir = tmp_path / "user_pictures"
    user_images_dir.mkdir()
    source_img = user_images_dir / "my_photo.png"
    img = Image.new("RGB", (1920, 1080), color=(50, 100, 150))
    img.save(source_img, format="PNG")

    meta = cache.store_local_image(source_img, mode=WallpaperPosition.FILL.value)
    assert meta is not None
    assert meta.category == "Local Storage"
    assert meta.title == "my_photo.png"
    assert meta.width == 1920
    assert meta.height == 1080
    assert Path(meta.local_path).exists()
    # Source file MUST not be moved or deleted!
    assert source_img.exists()


def test_store_local_image_corrupt(tmp_path):
    cfg = AppConfig(custom_cache_dir=str(tmp_path / "cache"))
    cache = CacheManager(cfg)

    corrupt_file = tmp_path / "bad.png"
    corrupt_file.write_bytes(b"NOT_AN_IMAGE_PAYLOAD")

    meta = cache.store_local_image(corrupt_file)
    assert meta is None
    # Source file remains intact
    assert corrupt_file.exists()


def test_store_local_image_missing(tmp_path):
    cfg = AppConfig(custom_cache_dir=str(tmp_path / "cache"))
    cache = CacheManager(cfg)

    meta = cache.store_local_image(tmp_path / "does_not_exist.jpg")
    assert meta is None
