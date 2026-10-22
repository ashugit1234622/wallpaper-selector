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
from .wallhaven import WallhavenProvider
from .the_met import TheMetImageProvider
from .bing import BingImageProvider
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
        self.wallhaven = WallhavenProvider(timeout_seconds=config.request_timeout_seconds)
        self.the_met = TheMetImageProvider(timeout_seconds=config.request_timeout_seconds)
        self.bing = BingImageProvider(timeout_seconds=config.request_timeout_seconds)

    USER_AGENT = "LoginWallpaperSelector/1.0 (contact@mywallpaperapp.org)"

    def get_providers_for_category(self, category: WallpaperCategory) -> List[BaseImageProvider]:
        """Ordered list of providers (primary followed by secondary and fallbacks)."""
        if category == WallpaperCategory.SPACE:
            return [self.nasa, self.wallhaven, self.bing, self.wikimedia]
        elif category == WallpaperCategory.NATURE:
            return [self.wallhaven, self.bing, self.wikimedia]
        elif category == WallpaperCategory.ART:
            return [self.the_met, self.wallhaven, self.wikimedia, self.artic]
        elif category == WallpaperCategory.PORTRAIT:
            return [self.the_met, self.wallhaven, self.wikimedia]
        return []

    def fetch_candidates(self, category: WallpaperCategory, limit: int = 10) -> List[WallpaperCandidate]:
        """Fetch candidate images for a category, interleaving results across available providers."""
        providers = self.get_providers_for_category(category)
        if not providers:
            return []

        exclude_ids = self.history.get_recent_ids()
        all_candidates: List[WallpaperCandidate] = []

        # Interleave candidates from providers to ensure a diverse mix
        provider_candidates: List[List[WallpaperCandidate]] = []
        target_per_provider = max(3, (limit // len(providers)) + 2)

        for provider in providers:
            try:
                candidates = provider.fetch_candidates(
                    category=category,
                    limit=target_per_provider,
                    exclude_ids=exclude_ids,
                )
                if candidates:
                    provider_candidates.append(candidates)
            except Exception:
                continue

        # Interleave candidates round-robin
        while any(provider_candidates) and len(all_candidates) < limit:
            for p_list in provider_candidates:
                if p_list and len(all_candidates) < limit:
                    all_candidates.append(p_list.pop(0))

        # If all candidates were excluded by history and list is empty, retry without history exclusion
        if not all_candidates:
            for provider in providers:
                try:
                    candidates = provider.fetch_candidates(
                        category=category,
                        limit=limit,
                        exclude_ids=set(),
                    )
                    if candidates:
                        all_candidates.extend(candidates)
                        if len(all_candidates) >= limit:
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
        headers = {"User-Agent": self.USER_AGENT}

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
        status_callback: Optional[callable] = None,
        max_retries: Optional[int] = None,
    ) -> Tuple[Optional[WallpaperMetadata], Optional[str]]:
        """Fetch, download, validate, cache, and record a wallpaper for an online category with retries.
        
        Tries at least 5 times across available repositories until a successful image is fetched.

        Returns:
            Tuple of (WallpaperMetadata, error_message)
        """
        total_attempts = max(5, max_retries or getattr(self.config, "max_fetch_retries", 5))
        accumulated_excludes = set(self.history.get_recent_ids())

        for attempt in range(1, total_attempts + 1):
            if status_callback:
                status_callback(
                    f"Attempt {attempt}/{total_attempts}: Finding {category.value} wallpaper...",
                    attempt,
                    total_attempts,
                )

            candidates = self.fetch_candidates(category, limit=6)
            # Filter out any candidates that already failed in previous attempts
            valid_candidates = [c for c in candidates if c.id not in accumulated_excludes]

            if not valid_candidates:
                # If all were excluded, retry fresh batch
                valid_candidates = candidates

            if valid_candidates:
                random.shuffle(valid_candidates)
                for candidate in valid_candidates:
                    temp_path = self.download_candidate(candidate, progress_callback)
                    if not temp_path:
                        accumulated_excludes.add(candidate.id)
                        continue

                    metadata = self.cache.atomic_save_download(
                        candidate=candidate,
                        temp_download_path=temp_path,
                        mode=mode,
                    )

                    if metadata:
                        self.history.record(candidate.id)
                        return metadata, None
                    else:
                        accumulated_excludes.add(candidate.id)

            if attempt < total_attempts:
                if status_callback:
                    status_callback(
                        f"Attempt {attempt}/{total_attempts} failed. Retrying in 1s...",
                        attempt,
                        total_attempts,
                    )
                time.sleep(1.0)

        return None, f"Failed to acquire {category.value} wallpaper after {total_attempts} attempts."
