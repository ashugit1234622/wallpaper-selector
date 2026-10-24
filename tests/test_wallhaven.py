"""Unit tests for WallhavenProvider with mocks."""

from login_wallpaper_selector.core.models import WallpaperCategory
from login_wallpaper_selector.providers.wallhaven import WallhavenProvider


def test_wallhaven_provider_parsing(monkeypatch):
    provider = WallhavenProvider()

    mock_wallhaven_json = {
        "data": [
            {
                "id": "abc123",
                "url": "https://wallhaven.cc/w/abc123",
                "path": "https://w.wallhaven.cc/full/ab/wallhaven-abc123.jpg",
                "resolution": "2560x1440",
                "dimension_x": 2560,
                "dimension_y": 1440,
                "file_type": "image/jpeg",
                "thumbs": {"small": "https://th.wallhaven.cc/small/ab/abc123.jpg"},
            }
        ]
    }

    class MockResponse:
        def __init__(self, json_data, status_code=200):
            self.status_code = status_code
            self._json = json_data

        def json(self):
            return self._json

    monkeypatch.setattr(
        "httpx.Client.get",
        lambda self, url, *args, **kwargs: MockResponse(mock_wallhaven_json),
    )

    candidates = provider.fetch_candidates(WallpaperCategory.NATURE, limit=1)
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.id == "wallhaven_abc123"
    assert cand.download_url == "https://w.wallhaven.cc/full/ab/wallhaven-abc123.jpg"
    assert cand.width == 2560
    assert cand.height == 1440
    assert cand.category == WallpaperCategory.NATURE
    assert "Wallhaven" in cand.provider_name


def test_wallhaven_provider_exclusion(monkeypatch):
    provider = WallhavenProvider()

    mock_wallhaven_json = {
        "data": [
            {
                "id": "excluded_item",
                "path": "https://w.wallhaven.cc/full/ex/wallhaven-excluded_item.jpg",
                "resolution": "1920x1080",
            }
        ]
    }

    class MockResponse:
        def __init__(self, json_data):
            self.status_code = 200
            self._json = json_data

        def json(self):
            return self._json

    monkeypatch.setattr(
        "httpx.Client.get",
        lambda self, url, *args, **kwargs: MockResponse(mock_wallhaven_json),
    )

    candidates = provider.fetch_candidates(
        WallpaperCategory.SPACE,
        limit=5,
        exclude_ids={"wallhaven_excluded_item"},
    )
    assert len(candidates) == 0


def test_wallhaven_4k_tv_mode(monkeypatch):
    provider = WallhavenProvider()

    captured_params = {}

    mock_wallhaven_json = {
        "data": [
            {
                "id": "item_1080p",
                "path": "https://w.wallhaven.cc/full/10/wallhaven-1080p.jpg",
                "resolution": "1920x1080",
                "dimension_x": 1920,
                "dimension_y": 1080,
            },
            {
                "id": "item_4k",
                "path": "https://w.wallhaven.cc/full/4k/wallhaven-4k.jpg",
                "resolution": "3840x2160",
                "dimension_x": 3840,
                "dimension_y": 2160,
            },
        ]
    }

    class MockResponse:
        def __init__(self, json_data):
            self.status_code = 200
            self._json = json_data

        def json(self):
            return self._json

    def mock_get(self, url, *args, **kwargs):
        captured_params.update(kwargs.get("params", {}))
        return MockResponse(mock_wallhaven_json)

    monkeypatch.setattr("httpx.Client.get", mock_get)

    candidates = provider.fetch_candidates(WallpaperCategory.NATURE, limit=5, search_for_tv=True)
    assert captured_params.get("atleast") == "3840x2160"
    assert captured_params.get("ratios") == "16x9"

    # Only 4K item should be accepted; 1080p item must be excluded
    assert len(candidates) == 1
    assert candidates[0].id == "wallhaven_item_4k"
    assert candidates[0].width == 3840
    assert candidates[0].height == 2160
