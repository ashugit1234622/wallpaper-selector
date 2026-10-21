"""Wikimedia Commons API provider for Nature, Portrait, Art, and Space categories."""

from __future__ import annotations
import random
import urllib.parse
from typing import List, Optional, Set
import httpx

from .base import BaseImageProvider
from .license import LicenseValidator
from ..core.models import WallpaperCategory, WallpaperCandidate, ImageDimensions


class WikimediaCommonsProvider(BaseImageProvider):
    API_ENDPOINT = "https://commons.wikimedia.org/w/api.php"
    USER_AGENT = "LoginWallpaperSelector/1.0 (https://github.com/login-wallpaper-selector; app@example.com)"

    CATEGORY_QUERIES = {
        WallpaperCategory.NATURE: [
            "filetype:bitmap landscape nature mountains lake wallpaper -portrait -nudity -gore",
            "filetype:bitmap scenic landscape forest river -portrait -nudity",
            "filetype:bitmap national park landscape scenic -portrait",
            "incategory:Featured_pictures_of_landscapes -nudity",
        ],
        WallpaperCategory.PORTRAIT: [
            "filetype:bitmap historical portrait oil painting public domain -nude -nudity",
            "filetype:bitmap renaissance portrait painting -nudity -nude",
            "incategory:Featured_pictures_of_people -nudity",
        ],
        WallpaperCategory.ART: [
            "filetype:bitmap impressionism landscape painting -nude -nudity",
            "filetype:bitmap classical landscape oil painting public domain -nude",
            "incategory:Featured_pictures_of_art -nudity",
        ],
        WallpaperCategory.SPACE: [
            "filetype:bitmap deep space nebula telescope wallpaper -nudity",
            "incategory:Featured_pictures_of_astronomy -nudity",
        ],
    }

    def __init__(self, timeout_seconds: int = 12):
        self.timeout = timeout_seconds

    @property
    def name(self) -> str:
        return "Wikimedia Commons"

    def supports_category(self, category: WallpaperCategory) -> bool:
        return category in self.CATEGORY_QUERIES

    def fetch_candidates(
        self,
        category: WallpaperCategory,
        query: Optional[str] = None,
        limit: int = 10,
        exclude_ids: Optional[Set[str]] = None,
    ) -> List[WallpaperCandidate]:
        if not self.supports_category(category):
            return []

        queries = self.CATEGORY_QUERIES.get(category, [])
        search_query = query or (random.choice(queries) if queries else "landscape")
        exclude = exclude_ids or set()
        candidates: List[WallpaperCandidate] = []

        params = {
            "action": "query",
            "generator": "search",
            "gsrsearch": search_query,
            "gsrnamespace": 6,  # File namespace
            "gsrlimit": min(30, max(15, limit * 2)),
            "prop": "imageinfo",
            "iiprop": "url|size|mime|extmetadata",
            "iiextmetadatafilter": "LicenseShortName|UsageTerms|Artist|Credit|LicenseUrl|ImageDescription",
            "format": "json",
            "formatversion": 2,
        }

        headers = {"User-Agent": self.USER_AGENT}

        try:
            with httpx.Client(timeout=self.timeout, headers=headers) as client:
                resp = client.get(self.API_ENDPOINT, params=params)
                if resp.status_code != 200:
                    return []

                data = resp.json()
                pages = data.get("query", {}).get("pages", [])
                random.shuffle(pages)

                for page in pages:
                    if len(candidates) >= limit:
                        break

                    page_id = str(page.get("pageid", ""))
                    if not page_id or page_id in exclude:
                        continue

                    title = page.get("title", "")
                    clean_title = title.replace("File:", "").rsplit(".", 1)[0].replace("_", " ")

                    imageinfos = page.get("imageinfo", [])
                    if not imageinfos:
                        continue
                    info = imageinfos[0]

                    width = info.get("width", 0)
                    height = info.get("height", 0)
                    mime = info.get("mime", "")
                    url = info.get("url")
                    desc_url = info.get("descriptionurl") or f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(title)}"

                    if not url or mime not in ("image/jpeg", "image/png", "image/webp"):
                        continue

                    # Filter for landscape wallpaper quality
                    dims = ImageDimensions(width=width, height=height)
                    if dims.width < 1600 or not dims.is_landscape:
                        continue

                    extmetadata = info.get("extmetadata", {})
                    lic_entry = extmetadata.get("LicenseShortName", {})
                    license_name = lic_entry.get("value", "")

                    if not LicenseValidator.is_valid_license(license_name):
                        continue

                    artist_entry = extmetadata.get("Artist", {})
                    artist = LicenseValidator.clean_text(artist_entry.get("value", "Wikimedia Contributor"))
                    lic_url_entry = extmetadata.get("LicenseUrl", {})
                    lic_url = lic_url_entry.get("value")

                    req_attr, attr_text = LicenseValidator.format_attribution(
                        title=clean_title,
                        creator=artist,
                        license_name=license_name,
                        source_url=desc_url,
                        license_url=lic_url,
                    )

                    thumb_url = info.get("thumburl") or url

                    candidate = WallpaperCandidate(
                        id=f"wiki_{page_id}",
                        category=category,
                        provider_name=self.name,
                        title=clean_title,
                        download_url=url,
                        source_url=desc_url,
                        creator=artist,
                        license_name=license_name,
                        license_url=lic_url,
                        attribution_required=req_attr,
                        attribution_text=attr_text,
                        preview_url=thumb_url,
                        width=width,
                        height=height,
                        mime_type=mime,
                        raw_metadata=info,
                    )
                    candidates.append(candidate)

        except Exception:
            pass

        return candidates
