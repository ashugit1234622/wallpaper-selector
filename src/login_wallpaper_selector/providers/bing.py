"""Microsoft Bing Daily and Archive Wallpaper provider."""

from __future__ import annotations
import random
from typing import List, Optional, Set
import httpx

from .base import BaseImageProvider
from ..core.models import WallpaperCategory, WallpaperCandidate


class BingImageProvider(BaseImageProvider):
    """Fetches curated 1080p/4K landscape and nature wallpapers from Microsoft Bing Archive."""

    ARCHIVE_URL = "https://www.bing.com/HPImageArchive.aspx"
    BASE_URL = "https://www.bing.com"
    USER_AGENT = "LoginWallpaperSelector/1.0 (contact@mywallpaperapp.org)"

    def __init__(self, timeout_seconds: float = 10.0):
        self.timeout_seconds = timeout_seconds

    @property
    def name(self) -> str:
        return "Bing Wallpaper Archive"

    def supports_category(self, category: Optional[WallpaperCategory]) -> bool:
        return category is None or category in (WallpaperCategory.NATURE, WallpaperCategory.SPACE)

    def fetch_candidates(
        self,
        category: Optional[WallpaperCategory] = None,
        query: Optional[str] = None,
        limit: int = 8,
        exclude_ids: Optional[Set[str]] = None,
        color: Optional[Any] = None,
        custom_color_hex: Optional[str] = None,
        mood: Optional[Any] = None,
        **kwargs,
    ) -> List[WallpaperCandidate]:
        if not self.supports_category(category):
            return []

        seen_ids = set(exclude_ids or set())
        candidates: List[WallpaperCandidate] = []

        headers = {"User-Agent": self.USER_AGENT}

        # Query up to 2 offset batches (idx=0 and idx=7) to get a pool of up to 16 recent images
        offsets = [0, 7]
        random.shuffle(offsets)

        try:
            with httpx.Client(timeout=self.timeout_seconds, headers=headers) as client:
                for idx in offsets:
                    params = {
                        "format": "js",
                        "idx": str(idx),
                        "n": "8",
                        "mkt": "en-US",
                    }
                    resp = client.get(self.ARCHIVE_URL, params=params)
                    if resp.status_code != 200:
                        continue

                    data = resp.json().get("images", [])
                    for item in data:
                        raw_url = item.get("url")
                        if not raw_url:
                            continue

                        hsh = item.get("hsh") or item.get("startdate") or str(hash(raw_url))
                        candidate_id = f"bing_{hsh[:16]}"
                        if candidate_id in seen_ids:
                            continue
                        seen_ids.add(candidate_id)

                        title = item.get("title") or item.get("headline") or "Bing Daily Wallpaper"
                        copyright_text = item.get("copyright") or "Microsoft Bing"
                        copyright_link = item.get("copyrightlink") or self.BASE_URL

                        # If category is SPACE, prioritize space/cosmos related keywords in title/copyright
                        if category == WallpaperCategory.SPACE:
                            text = f"{title} {copyright_text}".lower()
                            space_terms = ("space", "galaxy", "nebula", "planet", "star", "aurora", "telescope", "sky", "milky way", "astronomy", "eclipse")
                            if not any(term in text for term in space_terms):
                                # If query specifically requested space and this is not space-related, skip
                                continue

                        download_url = f"{self.BASE_URL}{raw_url}" if raw_url.startswith("/") else raw_url

                        candidate = WallpaperCandidate(
                            id=candidate_id,
                            category=category or WallpaperCategory.NATURE,
                            provider_name=self.name,
                            title=title,
                            download_url=download_url,
                            source_url=copyright_link,
                            creator=copyright_text,
                            license_name="Bing Daily Wallpaper (Personal Desktop Use)",
                            license_url="https://www.microsoft.com/en-us/legal/terms-of-use",
                            attribution_required=True,
                            attribution_text=copyright_text,
                            preview_url=download_url,
                            width=1920,
                            height=1080,
                            mime_type="image/jpeg",
                            raw_metadata=item,
                        )
                        candidates.append(candidate)
                        if len(candidates) >= limit:
                            break

                    if len(candidates) >= limit:
                        break

        except Exception:
            return []

        return candidates
