"""Art Institute of Chicago Open Access API provider for the Art category."""

from __future__ import annotations
import random
from typing import List, Optional, Set
import httpx

from .base import BaseImageProvider
from .license import LicenseValidator
from ..core.models import WallpaperCategory, WallpaperCandidate


class ArtInstituteChicagoProvider(BaseImageProvider):
    SEARCH_ENDPOINT = "https://api.artic.edu/api/v1/artworks/search"
    USER_AGENT = "LoginWallpaperSelector/1.0 (Desktop Wallpaper Application)"

    ART_QUERIES = [
        "landscape painting",
        "impressionism landscape",
        "monet landscape",
        "post-impressionism painting",
        "classical landscape mountains",
        "renaissance landscape",
        "japanese woodblock landscape",
        "seascape oil painting",
    ]

    def __init__(self, timeout_seconds: int = 12):
        self.timeout = timeout_seconds

    @property
    def name(self) -> str:
        return "Art Institute of Chicago"

    def supports_category(self, category: WallpaperCategory) -> bool:
        return category == WallpaperCategory.ART

    def fetch_candidates(
        self,
        category: WallpaperCategory,
        query: Optional[str] = None,
        limit: int = 10,
        exclude_ids: Optional[Set[str]] = None,
    ) -> List[WallpaperCandidate]:
        if not self.supports_category(category):
            return []

        search_query = query or random.choice(self.ART_QUERIES)
        exclude = exclude_ids or set()
        candidates: List[WallpaperCandidate] = []

        params = {
            "q": search_query,
            "query[term][is_public_domain]": "true",
            "fields": "id,title,artist_display,image_id,thumbnail",
            "limit": min(30, max(15, limit * 2)),
        }

        headers = {"User-Agent": self.USER_AGENT}

        try:
            with httpx.Client(timeout=self.timeout, headers=headers) as client:
                resp = client.get(self.SEARCH_ENDPOINT, params=params)
                if resp.status_code != 200:
                    return []

                data = resp.json()
                artworks = data.get("data", [])
                random.shuffle(artworks)

                for item in artworks:
                    if len(candidates) >= limit:
                        break

                    item_id = str(item.get("id", ""))
                    image_id = item.get("image_id")
                    if not item_id or not image_id or item_id in exclude:
                        continue

                    # Thumbnail check for landscape orientation if available
                    thumb = item.get("thumbnail") or {}
                    w = thumb.get("width", 0)
                    h = thumb.get("height", 0)
                    if w > 0 and h > 0 and (w / h) < 1.15:
                        continue  # Skip tall/vertical portraits for wallpaper

                    title = item.get("title", "Artwork")
                    artist = item.get("artist_display", "Unknown Artist")
                    
                    # Direct high-res IIIF URL (2048px wide)
                    download_url = f"https://www.artic.edu/iiif/2/{image_id}/full/2048,/0/default.jpg"
                    preview_url = f"https://www.artic.edu/iiif/2/{image_id}/full/500,/0/default.jpg"
                    source_url = f"https://www.artic.edu/artworks/{item_id}"
                    license_name = "CC0 Public Domain"

                    req_attr, attr_text = LicenseValidator.format_attribution(
                        title=title,
                        creator=artist,
                        license_name=license_name,
                        source_url=source_url,
                        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
                    )

                    candidate = WallpaperCandidate(
                        id=f"artic_{item_id}",
                        category=category,
                        provider_name=self.name,
                        title=title,
                        download_url=download_url,
                        source_url=source_url,
                        creator=artist,
                        license_name=license_name,
                        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
                        attribution_required=req_attr,
                        attribution_text=attr_text,
                        preview_url=preview_url,
                        raw_metadata=item,
                    )
                    candidates.append(candidate)

        except Exception:
            pass

        return candidates
