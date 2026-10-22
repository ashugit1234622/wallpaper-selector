"""Unit tests for TheMetImageProvider with mocks."""

from login_wallpaper_selector.core.models import WallpaperCategory
from login_wallpaper_selector.providers.the_met import TheMetImageProvider


def test_the_met_provider_parsing(monkeypatch):
    provider = TheMetImageProvider()

    mock_search_json = {
        "total": 1,
        "objectIDs": [191566],
    }

    mock_object_json = {
        "objectID": 191566,
        "isPublicDomain": True,
        "primaryImage": "https://images.metmuseum.org/CRDImages/ep/original/DT1567.jpg",
        "primaryImageSmall": "https://images.metmuseum.org/CRDImages/ep/web-large/DT1567.jpg",
        "title": "Self-Portrait with a Straw Hat",
        "artistDisplayName": "Vincent van Gogh",
        "objectDate": "1887",
        "objectURL": "https://www.metmuseum.org/art/collection/search/191566",
    }

    class MockResponse:
        def __init__(self, json_data, status_code=200):
            self.status_code = status_code
            self._json = json_data

        def json(self):
            return self._json

    def mock_get(self, url, *args, **kwargs):
        if "/search" in str(url):
            return MockResponse(mock_search_json)
        return MockResponse(mock_object_json)

    monkeypatch.setattr("httpx.Client.get", mock_get)

    candidates = provider.fetch_candidates(WallpaperCategory.PORTRAIT, limit=1)
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.id == "themet_191566"
    assert "Self-Portrait" in cand.title
    assert cand.creator == "Vincent van Gogh"
    assert "DT1567.jpg" in cand.download_url
    assert "CC0" in cand.license_name
    assert cand.category == WallpaperCategory.PORTRAIT


def test_the_met_provider_skips_non_public_domain(monkeypatch):
    provider = TheMetImageProvider()

    mock_search_json = {
        "total": 1,
        "objectIDs": [999999],
    }

    mock_object_json = {
        "objectID": 999999,
        "isPublicDomain": False,  # Not public domain
        "primaryImage": "https://images.metmuseum.org/test.jpg",
        "title": "Modern Protected Art",
    }

    class MockResponse:
        def __init__(self, json_data):
            self.status_code = 200
            self._json = json_data

        def json(self):
            return self._json

    def mock_get(self, url, *args, **kwargs):
        if "/search" in str(url):
            return MockResponse(mock_search_json)
        return MockResponse(mock_object_json)

    monkeypatch.setattr("httpx.Client.get", mock_get)

    candidates = provider.fetch_candidates(WallpaperCategory.ART, limit=1)
    assert len(candidates) == 0
