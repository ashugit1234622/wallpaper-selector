"""Unit tests for BingImageProvider with mocks."""

from login_wallpaper_selector.core.models import WallpaperCategory
from login_wallpaper_selector.providers.bing import BingImageProvider


def test_bing_provider_parsing(monkeypatch):
    provider = BingImageProvider()

    mock_bing_json = {
        "images": [
            {
                "startdate": "20261022",
                "hsh": "abc789hash",
                "url": "/th?id=OHR.ScenicLake_1920x1080.jpg",
                "title": "Autumn Reflections at Lake",
                "copyright": "Jane Nature Photographer (© Bing)",
                "copyrightlink": "https://www.bing.com/search?q=Scenic+Lake",
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
        lambda self, url, *args, **kwargs: MockResponse(mock_bing_json),
    )

    candidates = provider.fetch_candidates(WallpaperCategory.NATURE, limit=1)
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.id == "bing_abc789hash"
    assert cand.download_url == "https://www.bing.com/th?id=OHR.ScenicLake_1920x1080.jpg"
    assert cand.width == 1920
    assert cand.height == 1080
    assert cand.title == "Autumn Reflections at Lake"
    assert "Bing" in cand.provider_name


def test_bing_space_filter(monkeypatch):
    provider = BingImageProvider()

    mock_bing_json = {
        "images": [
            {
                "hsh": "hash1",
                "url": "/th?id=OHR.Desert_1920x1080.jpg",
                "title": "Sahara Desert Dunes",
                "copyright": "Desert Photo",
            },
            {
                "hsh": "hash2",
                "url": "/th?id=OHR.AuroraSky_1920x1080.jpg",
                "title": "Northern Lights over Aurora Sky",
                "copyright": "Night Sky Aurora",
            },
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
        lambda self, url, *args, **kwargs: MockResponse(mock_bing_json),
    )

    candidates = provider.fetch_candidates(WallpaperCategory.SPACE, limit=5)
    # Desert dunes should be filtered out, AuroraSky kept
    assert len(candidates) == 1
    assert candidates[0].id == "bing_hash2"
