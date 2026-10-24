"""Dedicated 4K UHD Wallpaper repository provider for TV and high-resolution displays.

Curates verified Ultra-HD landscape wallpapers (minimum 3840x2160) specifically optimized
for TV toggle searches, large screens, and high-DPI desktop setups.
"""

from __future__ import annotations
import logging
import random
import re
from typing import List, Optional, Set, Dict, Any
import httpx

from .base import BaseImageProvider
from .uhd_4k_catalog import UHD_4K_CATALOG
from ..core.models import WallpaperCategory, WallpaperCandidate, ColorPalette, WallpaperMood
from ..core.color_analyzer import get_palette_keyword

logger = logging.getLogger(__name__)


class Uhd4kProvider(BaseImageProvider):
    """Fetches verified 4K UHD (3840x2160+) wallpapers from curated repositories and 4K open archives."""

    WIKIMEDIA_ENDPOINT = "https://commons.wikimedia.org/w/api.php"
    USER_AGENT = "LoginWallpaperSelector/1.0 (contact@mywallpaperapp.org; 4k-uhd-provider)"

    def __init__(self, timeout_seconds: float = 10.0):
        self.timeout_seconds = timeout_seconds
        self._catalog = UHD_4K_CATALOG

    @property
    def name(self) -> str:
        return "4K UHD Curated"

    def supports_category(self, category: Optional[WallpaperCategory]) -> bool:
        return category is None or category in (
            WallpaperCategory.NATURE,
            WallpaperCategory.SPACE,
            WallpaperCategory.ART,
            WallpaperCategory.PORTRAIT,
        )

    def supports_color_filtering(self) -> bool:
        return True

    def fetch_candidates(
        self,
        category: Optional[WallpaperCategory] = None,
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

        # ── 1. Match from Curated 4K Catalog ──────────────────────────────────
        cat_key = category.name if category else None
        matching_entries: List[Dict[str, Any]] = []

        for entry in self._catalog:
            if entry["id"] in exclude:
                continue

            # Category filter
            if cat_key and entry.get("category") != cat_key:
                continue

            # Keyword query filter
            if query and query.strip():
                q_words = [w.lower() for w in re.split(r'[-_\s+]+', query.strip()) if len(w) > 2]
                # Filter out generic TV/resolution keywords from search term
                q_words = [w for w in q_words if w not in ("16:9", "16x9", "4k", "uhd", "wallpaper", "landscape", "widescreen")]
                if q_words:
                    entry_text = f"{entry.get('title', '')} {' '.join(entry.get('tags', []))}".lower()
                    if not any(w in entry_text for w in q_words):
                        continue

            # Mood filter
            if mood and mood != WallpaperMood.ANY:
                entry_moods = entry.get("moods", [])
                if mood.name in ("DARK", "VIBRANT", "CALM", "MINIMAL") and entry_moods:
                    if mood.name not in entry_moods:
                        # Allow soft fallback if no other matches, but deprioritize
                        pass

            # Color filter
            if color and color != ColorPalette.ANY:
                pal_kw = "black and white" if color == ColorPalette.MONOCHROME else (get_palette_keyword(color) or "")
                if pal_kw:
                    entry_text = f"{entry.get('title', '')} {' '.join(entry.get('tags', []))}".lower()
                    if color == ColorPalette.MONOCHROME and not any(k in entry_text for k in ("monochrome", "black", "white", "dark", "shadow", "mist")):
                        continue

            matching_entries.append(entry)

        # Shuffle matching entries to ensure fresh discovery
        random.shuffle(matching_entries)

        # Prioritize mood matches if requested
        if mood and mood != WallpaperMood.ANY and mood.name in ("DARK", "VIBRANT", "CALM", "MINIMAL"):
            matching_entries.sort(key=lambda e: 0 if mood.name in e.get("moods", []) else 1)

        for entry in matching_entries:
            cand_cat = category or (WallpaperCategory[entry["category"]] if entry.get("category") in WallpaperCategory.__members__ else WallpaperCategory.NATURE)
            candidate = WallpaperCandidate(
                id=entry["id"],
                category=cand_cat,
                provider_name=self.name,
                title=entry["title"],
                download_url=entry["cdn_url"],
                source_url=entry.get("raw_url") or entry["cdn_url"],
                creator=entry.get("creator", "Curated 4K Repository"),
                license_name=entry.get("license", "CC0 / Open Wallpaper"),
                license_url="https://creativecommons.org/publicdomain/zero/1.0/",
                attribution_required=False,
                attribution_text="",
                preview_url=entry["cdn_url"],
                width=entry.get("width", 3840),
                height=entry.get("height", 2160),
                mime_type="image/jpeg",
                raw_metadata=entry,
            )
            candidates.append(candidate)
            if len(candidates) >= limit:
                break

        # ── 2. Dynamic 4K Open Search Tier (Wikimedia 4K Archive) ─────────────
        # If query was specified and we have room, query live open 4K archives
        if len(candidates) < limit and query and query.strip():
            clean_q = " ".join([w for w in query.split() if w.lower() not in ("16:9", "16x9", "4k", "uhd", "wallpaper", "landscape", "widescreen")])
            if clean_q:
                try:
                    dyn_candidates = self._fetch_dynamic_wikimedia_4k(
                        category=category,
                        search_term=clean_q,
                        limit=limit - len(candidates),
                        exclude_ids=exclude,
                    )
                    candidates.extend(dyn_candidates)
                except Exception as e:
                    logger.debug("Dynamic 4K archive search failed: %s", e)

        return candidates[:limit]

    def _fetch_dynamic_wikimedia_4k(
        self,
        category: Optional[WallpaperCategory],
        search_term: str,
        limit: int,
        exclude_ids: Set[str],
    ) -> List[WallpaperCandidate]:
        """Query live open-access 4K repository (filewidth:>3840 fileheight:>2160)."""
        search_query = f"filewidth:>3840 fileheight:>2160 -nudity {search_term}"
        params = {
            "action": "query",
            "generator": "search",
            "gsrsearch": search_query,
            "gsrnamespace": 6,
            "gsrlimit": min(20, max(5, limit * 2)),
            "prop": "imageinfo",
            "iiprop": "url|size|mime",
            "format": "json",
            "formatversion": 2,
        }
        headers = {"User-Agent": self.USER_AGENT}

        candidates: List[WallpaperCandidate] = []
        with httpx.Client(timeout=self.timeout_seconds, headers=headers) as client:
            resp = client.get(self.WIKIMEDIA_ENDPOINT, params=params)
            if resp.status_code != 200:
                return []
            pages = resp.json().get("query", {}).get("pages", [])
            random.shuffle(pages)

            for page in pages:
                if len(candidates) >= limit:
                    break
                page_id = str(page.get("pageid", ""))
                cand_id = f"uhd_wm_{page_id}"
                if not page_id or cand_id in exclude_ids:
                    continue

                imageinfos = page.get("imageinfo", [])
                if not imageinfos:
                    continue
                info = imageinfos[0]
                w = info.get("width", 0)
                h = info.get("height", 0)
                url = info.get("url")
                mime = info.get("mime", "")

                # Strict 4K UHD landscape verification
                if w < 3840 or h < 2160 or (w / h) < 1.3:
                    continue
                if not url or mime not in ("image/jpeg", "image/png", "image/webp"):
                    continue

                raw_title = page.get("title", "").replace("File:", "").rsplit(".", 1)[0].replace("_", " ")
                clean_title = re.sub(r'\s+', ' ', raw_title).strip()

                candidate = WallpaperCandidate(
                    id=cand_id,
                    category=category or WallpaperCategory.NATURE,
                    provider_name=self.name,
                    title=f"{clean_title.title()} (4K UHD)",
                    download_url=url,
                    source_url=info.get("descriptionurl") or url,
                    creator="Wikimedia Commons Contributor",
                    license_name="Creative Commons / Public Domain",
                    license_url="https://creativecommons.org/licenses/",
                    attribution_required=False,
                    attribution_text="",
                    preview_url=url,
                    width=w,
                    height=h,
                    mime_type=mime,
                    raw_metadata=page,
                )
                candidates.append(candidate)

        return candidates
