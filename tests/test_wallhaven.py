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
