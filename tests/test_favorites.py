"""Unit tests for the Favorites & Ratings system."""

from pathlib import Path
from PIL import Image
import pytest

from login_wallpaper_selector.core.config import AppConfig
from login_wallpaper_selector.core.models import WallpaperMetadata
from login_wallpaper_selector.core.favorites import FavoritesManager, FavoriteRecord


def make_dummy_file(path: Path) -> Path:
    img = Image.new("RGB", (100, 100), color=(10, 20, 30))
    img.save(path, format="JPEG")
    return path


def test_favorites_toggle_and_persistence(tmp_path):
    data_dir = tmp_path / "data"
    cfg = AppConfig(custom_cache_dir=str(data_dir))
    fav_mgr = FavoritesManager(cfg)

    dummy_path = make_dummy_file(tmp_path / "image1.jpg")

    meta = WallpaperMetadata(
        image_id="img_101",
        category="Nature",
        provider="Wallhaven",
        source_url="https://example.com/1",
        download_url="https://example.com/1.jpg",
        local_path=str(dummy_path),
        sha256="abcdef123456",
        title="Alpine Vista",
        creator="Photographer",
        license="CC0",
        license_url=None,
        attribution_required=False,
        attribution_text="",
        width=1920,
        height=1080,
        aspect_ratio=1.778,
        mode="Fill",
        dominant_color_hex="#10b981",
        mood="Peaceful",
    )

    # Initial state
    assert not fav_mgr.is_favorite("img_101")

    # Toggle ON
    status = fav_mgr.toggle_favorite(meta)
    assert status is True
    assert fav_mgr.is_favorite("img_101")

    # Reload from disk in a fresh instance
    fresh_mgr = FavoritesManager(cfg)
    assert fresh_mgr.is_favorite("img_101")

    # Toggle OFF
    status_off = fresh_mgr.toggle_favorite(meta)
    assert status_off is False
    assert not fresh_mgr.is_favorite("img_101")


def test_star_ratings(tmp_path):
    cfg = AppConfig(custom_cache_dir=str(tmp_path / "data"))
    fav_mgr = FavoritesManager(cfg)
    dummy_path = make_dummy_file(tmp_path / "image2.jpg")

    meta = WallpaperMetadata(
        image_id="img_202",
        category="Space",
        provider="NASA",
        source_url="https://example.com/2",
        download_url="https://example.com/2.jpg",
        local_path=str(dummy_path),
        sha256="123456abcdef",
        title="Carina Nebula",
        creator="NASA",
        license="Public Domain",
        license_url=None,
        attribution_required=False,
        attribution_text="",
        width=3840,
        height=2160,
        aspect_ratio=1.778,
        mode="Fill",
    )

    # Set rating to 5 stars
    fav_mgr.set_rating("img_202", 5, metadata=meta)
    assert fav_mgr.get_rating("img_202") == 5

    # Change rating to 3 stars
    fav_mgr.set_rating("img_202", 3)
    assert fav_mgr.get_rating("img_202") == 3

    # Clamping tests: rating > 5 clamps to 5, rating < 0 clamps to 0
    fav_mgr.set_rating("img_202", 10)
    assert fav_mgr.get_rating("img_202") == 5
    fav_mgr.set_rating("img_202", -2)
    assert fav_mgr.get_rating("img_202") == 0


def test_favorites_filtering_and_random(tmp_path):
    cfg = AppConfig(custom_cache_dir=str(tmp_path / "data"))
    fav_mgr = FavoritesManager(cfg)

    file_a = make_dummy_file(tmp_path / "a.jpg")
    file_b = make_dummy_file(tmp_path / "b.jpg")

    meta_a = WallpaperMetadata(
        image_id="a",
        category="Nature",
        provider="Wallhaven",
        source_url="",
        download_url="",
        local_path=str(file_a),
        sha256="",
        title="Nature A",
        creator="",
        license="",
        license_url=None,
        attribution_required=False,
        attribution_text="",
        width=1920,
        height=1080,
        aspect_ratio=1.778,
        mode="Fill",
    )
    meta_b = WallpaperMetadata(
        image_id="b",
        category="Art",
        provider="The Met",
        source_url="",
        download_url="",
        local_path=str(file_b),
        sha256="",
        title="Art B",
        creator="",
        license="",
        license_url=None,
        attribution_required=False,
        attribution_text="",
        width=1920,
        height=1080,
        aspect_ratio=1.778,
        mode="Fill",
    )

    fav_mgr.toggle_favorite(meta_a)
    fav_mgr.set_rating("a", 5)

    fav_mgr.toggle_favorite(meta_b)
    fav_mgr.set_rating("b", 2)

    # Filter by min_rating 4
    high_rated = fav_mgr.get_favorites(min_rating=4)
    assert len(high_rated) == 1
    assert high_rated[0].image_id == "a"

    # Filter by category
    art_favs = fav_mgr.get_favorites(category="Art")
    assert len(art_favs) == 1
    assert art_favs[0].image_id == "b"

    # Random favorite
    rand = fav_mgr.get_random_favorite()
    assert rand is not None
    assert rand.image_id in ("a", "b")


def test_taste_profile_learning(tmp_path):
    cfg = AppConfig(custom_cache_dir=str(tmp_path / "data"))
    fav_mgr = FavoritesManager(cfg)

    file_1 = make_dummy_file(tmp_path / "1.jpg")
    file_2 = make_dummy_file(tmp_path / "2.jpg")

    meta_1 = WallpaperMetadata(
        image_id="1",
        category="Space",
        provider="NASA",
        source_url="",
        download_url="",
        local_path=str(file_1),
        sha256="",
        title="Pillars",
        creator="",
        license="",
        license_url=None,
        attribution_required=False,
        attribution_text="",
        width=1920,
        height=1080,
        aspect_ratio=1.778,
        mode="Fill",
        dominant_color_hex="#0284c7",
        mood="Cinematic",
    )
    meta_2 = WallpaperMetadata(
        image_id="2",
        category="Space",
        provider="NASA",
        source_url="",
        download_url="",
        local_path=str(file_2),
        sha256="",
        title="Galaxy",
        creator="",
        license="",
        license_url=None,
        attribution_required=False,
        attribution_text="",
        width=1920,
        height=1080,
        aspect_ratio=1.778,
        mode="Fill",
        dominant_color_hex="#0284c7",
        mood="Cinematic",
    )

    fav_mgr.toggle_favorite(meta_1)
    fav_mgr.set_rating("1", 5)

    fav_mgr.toggle_favorite(meta_2)
    fav_mgr.set_rating("2", 4)

    profile = fav_mgr.compute_taste_profile()
    assert profile["total_favorites"] == 2
    assert profile["top_category"] == "Space"
    assert profile["top_mood"] == "Cinematic"
    assert profile["category_counts"]["Space"] > 0
