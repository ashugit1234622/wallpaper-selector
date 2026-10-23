"""The Metropolitan Museum of Art image provider for classical masterworks and portraits."""

from __future__ import annotations
import random
from typing import List, Optional, Set
import httpx

from .base import BaseImageProvider
from ..core.models import WallpaperCategory, WallpaperCandidate, ColorPalette, WallpaperMood
from ..core.color_analyzer import get_palette_keyword
from ..core.mood_matcher import augment_query_with_mood


class TheMetImageProvider(BaseImageProvider):
    """Fetches high-resolution CC0 public domain art and portraits from The Met Open Access API."""

    SEARCH_URL = "https://collectionapi.metmuseum.org/public/collection/v1.1/search"
    OBJECT_URL = "https://collectionapi.metmuseum.org/public/collection/v1/objects"
    USER_AGENT = "LoginWallpaperSelector/1.0 (contact@mywallpaperapp.org)"

    ART_QUERIES = [
        "landscape painting",
        "impressionism",
        "oil on canvas",
        "japanese woodblock print",
        "monet",
        "van gogh",
        "rembrandt",
        "cezanne",
        "hokusai",
    ]
    PORTRAIT_QUERIES = [
        "portrait painting",
        "self portrait",
        "oil portrait",
        "renaissance portrait",
        "baroque portrait",
    ]

    def __init__(self, timeout_seconds: float = 10.0):
        self.timeout_seconds = timeout_seconds

    @property
    def name(self) -> str:
        return "The Metropolitan Museum of Art"

    def supports_category(self, category: WallpaperCategory) -> bool:
        return category in (WallpaperCategory.ART, WallpaperCategory.PORTRAIT)

    def fetch_candidates(
        self,
        category: WallpaperCategory,
        query: Optional[str] = None,
        limit: int = 10,
        exclude_ids: Optional[Set[str]] = None,
        color: Optional[ColorPalette] = None,
        custom_color_hex: Optional[str] = None,
        mood: Optional[WallpaperMood] = None,
        **kwargs,
    ) -> List[WallpaperCandidate]:
        if not self.supports_category(category):
            return []

        exclude = exclude_ids or set()
        candidates: List[WallpaperCandidate] = []

        if category == WallpaperCategory.ART:
            search_query = query or random.choice(self.ART_QUERIES)
        elif category == WallpaperCategory.PORTRAIT:
            search_query = query or random.choice(self.PORTRAIT_QUERIES)
        else:
            return []

        if mood and mood != WallpaperMood.ANY:
            search_query = augment_query_with_mood(search_query, mood, category)

        if color and color != ColorPalette.ANY:
            color_kw = get_palette_keyword(color)
            if color_kw:
                search_query = f"{search_query} {color_kw}"

        search_params = {
            "hasImages": "true",
            "isPublicDomain": "true",
            "q": search_query,
        }
        headers = {"User-Agent": self.USER_AGENT}

        try:
            with httpx.Client(timeout=self.timeout_seconds, headers=headers) as client:
                search_resp = client.get(self.SEARCH_URL, params=search_params)
                if search_resp.status_code != 200:
                    return []

                data = search_resp.json()
                object_ids = data.get("objectIDs", [])
                if not object_ids:
                    return []

                # Sample up to 30 IDs randomly from the top 100 to get fresh images every time
                pool = object_ids[:100]
                random.shuffle(pool)

                for obj_id in pool:
                    candidate_id = f"themet_{obj_id}"
                    if candidate_id in exclude:
                        continue

                    try:
                        obj_resp = client.get(f"{self.OBJECT_URL}/{obj_id}")
                        if obj_resp.status_code != 200:
                            continue

                        obj_data = obj_resp.json()
                        if not obj_data.get("isPublicDomain"):
                            continue

                        primary_image = obj_data.get("primaryImage")
                        if not primary_image or not primary_image.startswith("http"):
                            continue

                        title = obj_data.get("title") or "Metropolitan Museum Artwork"
                        artist = obj_data.get("artistDisplayName") or obj_data.get("culture") or "Unknown Artist"
                        object_date = obj_data.get("objectDate")
                        if object_date:
                            display_title = f"{title} ({object_date})"
                        else:
                            display_title = title

                        candidate = WallpaperCandidate(
                            id=candidate_id,
                            category=category,
                            provider_name=self.name,
                            title=display_title,
                            download_url=primary_image,
                            source_url=obj_data.get("objectURL") or f"https://www.metmuseum.org/art/collection/search/{obj_id}",
                            creator=artist,
                            license_name="CC0 1.0 Universal (Public Domain)",
                            license_url="https://creativecommons.org/publicdomain/zero/1.0/",
                            attribution_required=False,
                            attribution_text=f"{title} by {artist}, The Metropolitan Museum of Art (CC0)",
                            preview_url=obj_data.get("primaryImageSmall"),
                            mime_type="image/jpeg",
                            raw_metadata=obj_data,
                        )
                        candidates.append(candidate)
                        if len(candidates) >= limit:
                            break
                    except Exception:
                        continue

        except Exception:
            return []

        return candidates
