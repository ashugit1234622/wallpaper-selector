"""NASA Image and Video Library API provider for the Space category."""

from __future__ import annotations
import random
import urllib.parse
from typing import List, Optional, Set
import httpx

from .base import BaseImageProvider
from .license import LicenseValidator
from ..core.models import WallpaperCategory, WallpaperCandidate, WallpaperMood
from ..core.mood_matcher import augment_query_with_mood


class NasaImageProvider(BaseImageProvider):
    SEARCH_ENDPOINT = "https://images-api.nasa.gov/search"
    USER_AGENT = "LoginWallpaperSelector/1.0 (Desktop Wallpaper Application)"

    SPACE_QUERIES = [
        "nebula landscape",
        "deep field galaxy",
        "hubble space telescope landscape",
        "james webb space telescope deep field",
        "earth from space horizon",
        "saturn rings cassini",
        "andromeda galaxy",
        "stellar nursery carina nebula",
        "pillars of creation",
    ]

    def __init__(self, timeout_seconds: int = 12):
        self.timeout = timeout_seconds

    @property
    def name(self) -> str:
        return "NASA Image and Video Library"

    def supports_category(self, category: Optional[WallpaperCategory]) -> bool:
        return category is None or category == WallpaperCategory.SPACE

    def fetch_candidates(
        self,
        category: Optional[WallpaperCategory] = None,
        query: Optional[str] = None,
        limit: int = 10,
        exclude_ids: Optional[Set[str]] = None,
        color: Optional[Any] = None,
        custom_color_hex: Optional[str] = None,
        mood: Optional[WallpaperMood] = None,
        **kwargs,
    ) -> List[WallpaperCandidate]:
        if not self.supports_category(category):
            return []

        search_query = query or random.choice(self.SPACE_QUERIES)
        if mood and mood != WallpaperMood.ANY:
            search_query = augment_query_with_mood(search_query, mood, category)
        exclude = exclude_ids or set()
        candidates: List[WallpaperCandidate] = []

        params = {
            "q": search_query,
            "media_type": "image",
        }

        headers = {"User-Agent": self.USER_AGENT}

        try:
            with httpx.Client(timeout=self.timeout, headers=headers) as client:
                resp = client.get(self.SEARCH_ENDPOINT, params=params)
                if resp.status_code != 200:
                    return []

                data = resp.json()
                items = data.get("collection", {}).get("items", [])
                random.shuffle(items)

                for item in items:
                    if len(candidates) >= limit:
                        break

                    data_list = item.get("data", [])
                    if not data_list:
                        continue
                    info = data_list[0]
                    nasa_id = info.get("nasa_id")
                    if not nasa_id or nasa_id in exclude:
                        continue

                    title = info.get("title", "NASA Astronomy Image")
                    photographer = info.get("photographer") or info.get("secondary_creator") or info.get("center") or "NASA"
                    description = info.get("description", "")

                    # Reject if non-NASA copyright notice is explicitly indicated
                    if "copyright" in description.lower() and "esa" not in description.lower():
                        continue

                    # Asset manifest collection URL
                    asset_collection_url = item.get("href")
                    if not asset_collection_url:
                        continue

                    # Thumbnail preview
                    preview_url = None
                    for link in item.get("links", []):
                        if link.get("rel") == "preview":
                            preview_url = link.get("href")
                            break

                    # Resolve direct high-res image URL from manifest
                    best_image_url = self._resolve_best_image_url(client, asset_collection_url)
                    if not best_image_url:
                        continue

                    source_url = f"https://images.nasa.gov/details-{urllib.parse.quote(nasa_id)}"
                    license_name = "Public Domain (NASA / US Government Work)"
                    req_attr, attr_text = LicenseValidator.format_attribution(
                        title=title,
                        creator=photographer,
                        license_name=license_name,
                        source_url=source_url,
                        license_url="https://www.nasa.gov/multimedia/guidelines/index.html",
                    )

                    candidate = WallpaperCandidate(
                        id=f"nasa_{nasa_id}",
                        category=category or WallpaperCategory.SPACE,
                        provider_name=self.name,
                        title=title,
                        download_url=best_image_url,
                        source_url=source_url,
                        creator=photographer,
                        license_name=license_name,
                        license_url="https://www.nasa.gov/multimedia/guidelines/index.html",
                        attribution_required=req_attr,
                        attribution_text=attr_text,
                        preview_url=preview_url,
                        raw_metadata=info,
                    )
                    candidates.append(candidate)

        except Exception:
            pass

        return candidates

    def _resolve_best_image_url(self, client: httpx.Client, collection_url: str) -> Optional[str]:
        """Fetch collection.json and pick orig or large jpg."""
        try:
            resp = client.get(collection_url)
            if resp.status_code != 200:
                return None
            asset_urls = resp.json()
            if not isinstance(asset_urls, list):
                return None

            # Filter for jpg / png
            image_urls = [u for u in asset_urls if isinstance(u, str) and u.lower().endswith((".jpg", ".jpeg", ".png"))]
            if not image_urls:
                return None

            # Preference: ~large.jpg (optimal desktop wallpaper), ~orig.jpg, ~medium.jpg
            for pattern in ["~large.jpg", "~large.jpeg", "~orig.jpg", "~orig.png", "~medium.jpg"]:
                for u in image_urls:
                    if pattern in u.lower():
                        return u

            return image_urls[0]
        except Exception:
            return None
