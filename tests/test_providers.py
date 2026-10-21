"""Unit tests for NASA, Wikimedia, and Art Institute providers with mocks."""

from unittest.mock import MagicMock
from login_wallpaper_selector.core.models import WallpaperCategory
from login_wallpaper_selector.providers.nasa import NasaImageProvider
from login_wallpaper_selector.providers.wikimedia import WikimediaCommonsProvider
from login_wallpaper_selector.providers.artic import ArtInstituteChicagoProvider


def test_nasa_provider_parsing(monkeypatch):
    provider = NasaImageProvider()

    mock_search_json = {
        "collection": {
            "items": [
                {
                    "data": [
                        {
                            "nasa_id": "PIA99999",
                            "title": "Mock Nebula View",
                            "photographer": "Hubble Space Telescope",
                            "description": "A stunning landscape view of a deep nebula.",
                        }
                    ],
                    "href": "https://images-assets.nasa.gov/image/PIA99999/collection.json",
                    "links": [{"rel": "preview", "href": "https://example.com/thumb.jpg"}],
                }
            ]
        }
    }

    mock_manifest_json = [
        "https://images-assets.nasa.gov/image/PIA99999/PIA99999~orig.jpg",
        "https://images-assets.nasa.gov/image/PIA99999/PIA99999~large.jpg",
        "https://images-assets.nasa.gov/image/PIA99999/PIA99999~medium.jpg",
    ]

    class MockResponse:
        def __init__(self, json_data):
            self.status_code = 200
            self._json = json_data

        def json(self):
            return self._json

    def mock_get(self, url, *args, **kwargs):
        if "collection.json" in str(url):
            return MockResponse(mock_manifest_json)
        return MockResponse(mock_search_json)

    monkeypatch.setattr("httpx.Client.get", mock_get)

    candidates = provider.fetch_candidates(WallpaperCategory.SPACE, limit=1)
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.id == "nasa_PIA99999"
    assert cand.title == "Mock Nebula View"
    assert "large.jpg" in cand.download_url
    assert "Public Domain" in cand.license_name


def test_wikimedia_provider_parsing(monkeypatch):
    provider = WikimediaCommonsProvider()

    mock_wiki_json = {
        "query": {
            "pages": [
                {
                    "pageid": 12345,
                    "title": "File:Scenic Mountain Lake.jpg",
                    "imageinfo": [
                        {
                            "url": "https://upload.wikimedia.org/wikipedia/commons/test.jpg",
                            "width": 3840,
                            "height": 2160,
                            "mime": "image/jpeg",
                            "descriptionurl": "https://commons.wikimedia.org/wiki/File:Scenic_Mountain_Lake.jpg",
                            "extmetadata": {
                                "LicenseShortName": {"value": "CC BY-SA 4.0"},
                                "Artist": {"value": "Jane Nature Photographer"},
                                "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0/"},
                            },
                        }
                    ],
                }
            ]
        }
    }

    class MockResponse:
        def __init__(self, json_data):
            self.status_code = 200
            self._json = json_data

        def json(self):
            return self._json

    monkeypatch.setattr("httpx.Client.get", lambda url, *args, **kwargs: MockResponse(mock_wiki_json))

    candidates = provider.fetch_candidates(WallpaperCategory.NATURE, limit=1)
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.id == "wiki_12345"
    assert cand.license_name == "CC BY-SA 4.0"
    assert cand.attribution_required is True
    assert cand.creator == "Jane Nature Photographer"


def test_artic_provider_parsing(monkeypatch):
    provider = ArtInstituteChicagoProvider()

    mock_artic_json = {
        "data": [
            {
                "id": 54321,
                "title": "Water Lilies",
                "artist_display": "Claude Monet",
                "image_id": "monet-image-uuid-1234",
                "thumbnail": {"width": 1920, "height": 1080},
            }
        ]
    }

    class MockResponse:
        def __init__(self, json_data):
            self.status_code = 200
            self._json = json_data

        def json(self):
            return self._json

    monkeypatch.setattr("httpx.Client.get", lambda url, *args, **kwargs: MockResponse(mock_artic_json))

    candidates = provider.fetch_candidates(WallpaperCategory.ART, limit=1)
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.id == "artic_54321"
    assert "Claude Monet" in cand.creator
    assert "monet-image-uuid-1234" in cand.download_url
    assert "CC0" in cand.license_name
