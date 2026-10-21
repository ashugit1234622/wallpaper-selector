"""Provider router orchestrating searches, fallbacks, and atomic image downloading."""

from __future__ import annotations
import random
import time
from pathlib import Path
from typing import List, Optional, Tuple
import httpx

from .base import BaseImageProvider
from .nasa import NasaImageProvider
from .wikimedia import WikimediaCommonsProvider
from .artic import ArtInstituteChicagoProvider
from ..core.models import WallpaperCategory, WallpaperCandidate, WallpaperMetadata
from ..core.config import AppConfig
from ..core.history import HistoryTracker
from ..core.cache import CacheManager


class ProviderRouter:
    """Coordinates search, candidate selection, and atomic downloading across providers."""

    def __init__(self, config: AppConfig, history: HistoryTracker, cache: CacheManager):
        self.config = config
        self.history = history
        self.cache = cache

        # Registered providers
        self.nasa = NasaImageProvider(timeout_seconds=config.request_timeout_seconds)
        self.wikimedia = WikimediaCommonsProvider(timeout_seconds=config.request_timeout_seconds)
        self.artic = ArtInstituteChicagoProvider(timeout_seconds=config.request_timeout_seconds)

    def get_providers_for_category(self, category: WallpaperCategory) -> List[BaseImageProvider]:
        """Ordered list of providers (primary followed by fallbacks)."""
        if category == WallpaperCategory.SPACE:
            return [self.nasa, self.wikimedia]
        elif category == WallpaperCategory.ART:
            return [self.artic, self.wikimedia]
        elif category in (WallpaperCategory.NATURE, WallpaperCategory.PORTRAIT):
            return [self.wikimedia]
        return []

    def fetch_candidates(self, category: WallpaperCategory, limit: int = 10) -> List[WallpaperCandidate]:
        """Fetch candidate images for a category, trying primary and fallback providers."""
        providers = self.get_providers_for_category(category)
        exclude_ids = self.history.get_recent_ids()
        all_candidates: List[WallpaperCandidate] = []

        for provider in providers:
            try:
                candidates = provider.fetch_candidates(
                    category=category,
                    limit=limit,
                    exclude_ids=exclude_ids,
                )
                if candidates:
                    all_candidates.extend(candidates)
                    if len(all_candidates) >= limit:
                        break
            except Exception:
                continue

        # If all candidates were excluded by history and list is empty, retry without history exclusion
        if not all_candidates and providers:
            for provider in providers:
                try:
                    candidates = provider.fetch_candidates(
                        category=category,
                        limit=limit,
                        exclude_ids=set(),
                    )
                    if candidates:
                        all_candidates.extend(candidates)
                        break
                except Exception:
                    continue

        return all_candidates

    def download_candidate(
        self,
        candidate: WallpaperCandidate,
        progress_callback: Optional[callable] = None,
    ) -> Optional[Path]:
        """Download candidate image streaming to a temporary .part file with verification."""
        temp_file = self.cache.cache_dir / f"download_{int(time.time()*1000)}.part"
        headers = {"User-Agent": "LoginWallpaperSelector/1.0"}

        try:
            with httpx.Client(timeout=self.config.request_timeout_seconds * 2, headers=headers, follow_redirects=True) as client:
                with client.stream("GET", candidate.download_url) as response:
                    if response.status_code != 200:
                        return None

                    total_bytes = int(response.headers.get("Content-Length", 0))
                    downloaded = 0

                    with open(temp_file, "wb") as f:
                        for chunk in response.iter_bytes(chunk_size=65536):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if progress_callback and total_bytes > 0:
                                    progress_callback(downloaded, total_bytes)

            return temp_file
        except Exception:
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass
            return None

    def acquire_wallpaper_for_category(
        self,
        category: WallpaperCategory,
        mode: str,
        progress_callback: Optional[callable] = None,
    ) -> Tuple[Optional[WallpaperMetadata], Optional[str]]:
        """Fetch, download, validate, cache, and record a wallpaper for an online category.
        
        Returns:
            Tuple of (WallpaperMetadata, error_message)
        """
        candidates = self.fetch_candidates(category, limit=8)
        if not candidates:
            return None, "No online images could be found or network is unreachable."

        random.shuffle(candidates)

        for candidate in candidates:
            temp_path = self.download_candidate(candidate, progress_callback)
            if not temp_path:
                continue

            metadata = self.cache.atomic_save_download(
                candidate=candidate,
                temp_download_path=temp_path,
                mode=mode,
            )

            if metadata:
                self.history.record(candidate.id)
                return metadata, None

        return None, "Downloaded images failed format or integrity verification."
