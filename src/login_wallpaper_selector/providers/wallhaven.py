"""Wallhaven image provider for high-resolution desktop wallpapers."""

from __future__ import annotations
import random
import string
from typing import List, Optional, Set
import httpx

from .base import BaseImageProvider
from ..core.models import WallpaperCategory, WallpaperCandidate, ColorPalette, WallpaperMood
from ..core.color_analyzer import get_wallhaven_color_code
from ..core.mood_matcher import augment_query_with_mood


class WallhavenProvider(BaseImageProvider):
    """Fetches high-resolution, SFW wallpapers from the Wallhaven open API."""

    SEARCH_URL = "https://wallhaven.cc/api/v1/search"
    USER_AGENT = "LoginWallpaperSelector/1.0 (contact@mywallpaperapp.org)"

    # Category query terms for fresh, varied selections
    SPACE_QUERIES = ["space", "galaxy", "nebula", "astronomy", "cosmos", "deep space", "milky way"]
    NATURE_QUERIES = ["nature", "mountains", "forest", "landscape", "ocean", "aurora", "lake", "sunset landscape"]
    ART_QUERIES = ["artwork", "digital art", "concept art", "fantasy art", "illustration", "painting"]
    PORTRAIT_QUERIES = ["portrait", "cinematic portrait", "character portrait", "person portrait"]

    def __init__(self, timeout_seconds: float = 10.0):
        self.timeout_seconds = timeout_seconds

    @property
    def name(self) -> str:
        return "Wallhaven"

    def supports_category(self, category: WallpaperCategory) -> bool:
        return category in (
            WallpaperCategory.SPACE,
            WallpaperCategory.NATURE,
            WallpaperCategory.ART,
            WallpaperCategory.PORTRAIT,
        )

    def _generate_seed(self) -> str:
        """Generate random 6-character seed for Wallhaven random sorting."""
        return "".join(random.choices(string.ascii_letters + string.digits, k=6))

    def fetch_candidates(
        self,
        category: WallpaperCategory,
        query: Optional[str] = None,
        limit: int = 15,
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

        # Map category to search query and category flags
        # Categories: 100 = General, 010 = Anime, 001 = People
        if category == WallpaperCategory.SPACE:
            search_query = query or random.choice(self.SPACE_QUERIES)
            cat_flag = "100"
        elif category == WallpaperCategory.NATURE:
            search_query = query or random.choice(self.NATURE_QUERIES)
            cat_flag = "100"
        elif category == WallpaperCategory.ART:
            search_query = query or random.choice(self.ART_QUERIES)
            cat_flag = "100"
        elif category == WallpaperCategory.PORTRAIT:
            search_query = query or random.choice(self.PORTRAIT_QUERIES)
            cat_flag = "001"
        else:
            return []

        if mood and mood != WallpaperMood.ANY:
            search_query = augment_query_with_mood(search_query, mood, category)

        params = {
            "q": search_query,
            "categories": cat_flag,
            "purity": "100",  # Strict SFW
            "ratios": "16x9,16x10",  # Native widescreen ratios
            "atleast": "1920x1080",  # High-definition minimum
            "sorting": "random",
            "seed": self._generate_seed(),
        }

        # Apply color filter if selected
        if color and color != ColorPalette.ANY:
            color_code = get_wallhaven_color_code(color, custom_color_hex)
            if color_code:
                params["colors"] = color_code

        headers = {"User-Agent": self.USER_AGENT}

        try:
            with httpx.Client(timeout=self.timeout_seconds, headers=headers) as client:
                resp = client.get(self.SEARCH_URL, params=params)
                if resp.status_code != 200:
                    return []

                data = resp.json().get("data", [])
                for item in data:
                    item_id = item.get("id")
                    if not item_id:
                        continue

                    candidate_id = f"wallhaven_{item_id}"
                    if candidate_id in exclude:
                        continue

                    download_url = item.get("path")
                    if not download_url:
                        continue

                    resolution = item.get("resolution", "1920x1080")
                    width = item.get("dimension_x")
                    height = item.get("dimension_y")

                    candidate = WallpaperCandidate(
                        id=candidate_id,
                        category=category,
                        provider_name=self.name,
                        title=f"{search_query.title()} ({resolution})",
                        download_url=download_url,
                        source_url=item.get("url") or f"https://wallhaven.cc/w/{item_id}",
                        creator="Wallhaven Community",
                        license_name="Wallhaven Wallpaper (Personal Desktop Use)",
                        license_url="https://wallhaven.cc/faq#terms",
                        attribution_required=False,
                        attribution_text="",
                        preview_url=item.get("thumbs", {}).get("small"),
                        width=width,
                        height=height,
                        mime_type=f"image/{item.get('file_type', 'jpeg').split('/')[-1]}",
                        raw_metadata=item,
                    )
                    candidates.append(candidate)
                    if len(candidates) >= limit:
                        break

        except Exception:
            return []

        return candidates
