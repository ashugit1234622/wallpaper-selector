"""Provider router orchestrating searches, fallbacks, and atomic image downloading."""

from __future__ import annotations
import random
import time
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import httpx

from .base import BaseImageProvider
from .nasa import NasaImageProvider
from .wikimedia import WikimediaCommonsProvider
from .artic import ArtInstituteChicagoProvider
from .wallhaven import WallhavenProvider
from .the_met import TheMetImageProvider
from .bing import BingImageProvider
from ..core.models import WallpaperCategory, WallpaperCandidate, WallpaperMetadata, ColorPalette, WallpaperMood
from ..core.seasonal import Season, get_current_season, augment_query_with_season, get_season_display
from ..core.config import AppConfig
from ..core.history import HistoryTracker
from ..core.cache import CacheManager
from ..core.color_analyzer import (
    extract_dominant_color_from_file,
    rgb_to_hex,
    compute_color_match_score,
    compute_image_stats_from_file,
    validate_image_matches_selection,
    compute_image_compatibility_score,
    get_palette_keyword,
)
from ..core.mood_matcher import augment_query_with_mood


RETRY_QUERY_TIERS: dict[WallpaperCategory, dict[int, List[str]]] = {
    WallpaperCategory.SPACE: {
        1: ["deep field galaxy", "nebula landscape", "james webb deep field", "andromeda galaxy"],
        2: ["cosmos starfield astrophotography", "supernova radiant celestial", "stellar nursery pillars", "milky way night horizon"],
        3: ["epic celestial vista", "hubble space telescope landscape", "saturn rings cassini", "interstellar space panorama"],
        4: ["astronomy widescreen", "galaxy cluster", "high resolution cosmos", "deep space nebula"],
        5: ["space", "universe", "astronomy", "cosmos"],
    },
    WallpaperCategory.NATURE: {
        1: ["scenic mountain landscape", "forest misty morning", "lake reflection sunset", "coastal ocean cliffs"],
        2: ["deep autumn woodland", "alpine mountain peaks dramatic", "tranquil pine forest river", "aurora borealis landscape"],
        3: ["cinematic nature vista", "dramatic sunset clouds horizon", "wilderness mountain valley", "peaceful lake mist"],
        4: ["high resolution landscape", "national park mountains", "scenic nature widescreen", "mountain valley"],
        5: ["nature", "landscape", "mountains", "forest"],
    },
    WallpaperCategory.ART: {
        1: ["classical landscape oil painting", "impressionist garden fine art", "fine art museum masterpiece", "renaissance artwork"],
        2: ["dramatic chiaroscuro oil painting", "hokusai classic wave", "romanticism moody landscape", "turner dramatic sea painting"],
        3: ["cinematic composition painting", "vintage fine art landscape", "monet water lilies impressionism", "classical fine art"],
        4: ["fine art open access", "museum painting high resolution", "classical fine art masterpiece"],
        5: ["painting", "artwork", "fine art", "masterpiece"],
    },
    WallpaperCategory.PORTRAIT: {
        1: ["classic portrait painting", "fine art portrait oil on canvas", "dramatic cinematic portrait", "renaissance portrait fine art"],
        2: ["moody low key portrait", "chiaroscuro Rembrandt portrait", "masterpiece portrait oil painting", "atmospheric character portrait"],
        3: ["cinematic portrait lighting widescreen", "expressive artistic portrait", "historical portrait masterpiece"],
        4: ["high resolution portrait fine art", "classical museum portrait", "fine art character"],
        5: ["portrait", "person portrait", "fine art portrait"],
    },
}


def get_retry_tier_query(
    category: WallpaperCategory,
    attempt: int,
    mood: Optional[WallpaperMood] = None,
    color: Optional[ColorPalette] = None,
) -> str:
    """Retrieve progressive query variation according to attempt tier (1 to 5).
    
    Harmonizes with active mood and palette filters to avoid contradictory searches.
    """
    tier = max(1, min(5, attempt))
    cat_tiers = RETRY_QUERY_TIERS.get(category, {})
    tier_options = cat_tiers.get(tier, [category.value.lower() if hasattr(category, "value") else str(category).lower()])

    # If Dark or Monochrome is selected, avoid contradictory words
    contradictory_words = []
    if mood == WallpaperMood.DARK:
        contradictory_words.extend(["vibrant", "radiant", "sunny", "sunlight", "golden hour", "wildflower"])
    if color == ColorPalette.MONOCHROME:
        contradictory_words.extend(["vibrant", "colorful", "rainbow", "wildflower"])

    filtered_options = [
        opt for opt in tier_options
        if not any(w in opt.lower() for w in contradictory_words)
    ]
    chosen = random.choice(filtered_options) if filtered_options else random.choice(tier_options)

    # Synthesize color keyword if a specific palette is chosen
    if color and color != ColorPalette.ANY:
        pal_kw = "black and white" if color == ColorPalette.MONOCHROME else get_palette_keyword(color)
        if pal_kw and pal_kw.lower() not in chosen.lower():
            chosen = f"{chosen} {pal_kw}"

    return chosen


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

    def get_providers_for_category(
        self,
        category: WallpaperCategory,
        color: Optional[ColorPalette] = None,
        mood: Optional[WallpaperMood] = None,
    ) -> List[BaseImageProvider]:
        """Ordered list of providers (primary followed by secondary and fallbacks)."""
        if category == WallpaperCategory.SPACE:
            providers = [self.nasa, self.wallhaven, self.bing, self.wikimedia]
        elif category == WallpaperCategory.NATURE:
            providers = [self.wallhaven, self.bing, self.wikimedia]
        elif category == WallpaperCategory.ART:
            providers = [self.the_met, self.wallhaven, self.wikimedia, self.artic]
        elif category == WallpaperCategory.PORTRAIT:
            providers = [self.the_met, self.wallhaven, self.wikimedia]
        else:
            providers = []

        # When Dark or Monochrome is active, prioritize search-capable providers
        # and move Bing (which only has bright daylight daily photos) to the end.
        if (mood == WallpaperMood.DARK or color == ColorPalette.MONOCHROME) and self.bing in providers:
            providers = [p for p in providers if p != self.bing] + [self.bing]

        return providers

    def fetch_candidates(
        self,
        category: WallpaperCategory,
        limit: int = 10,
        color: Optional[ColorPalette] = None,
        custom_color_hex: Optional[str] = None,
        mood: Optional[WallpaperMood] = None,
        season: Optional[Season] = None,
        query: Optional[str] = None,
        tried_sources: Optional[Dict[str, Any]] = None,
    ) -> List[WallpaperCandidate]:
        """Fetch candidate images for a category, interleaving results across available providers."""
        try:
            providers = self.get_providers_for_category(category, color=color, mood=mood)
        except TypeError:
            providers = self.get_providers_for_category(category)
        if not providers:
            return []

        active_season = season or (get_current_season() if getattr(self.config, "seasonal_theme_enabled", False) else None)
        effective_query = query
        if not effective_query and active_season:
            effective_query = augment_query_with_season("", active_season, category)

        exclude_ids = self.history.get_recent_ids()
        all_candidates: List[WallpaperCandidate] = []

        # Filter out throttled providers if circuit breaker has tripped
        active_providers = []
        for p in providers:
            if tried_sources is not None:
                p_info = tried_sources.setdefault(p.name, {"failures": 0, "throttled": False, "attempted_queries": set()})
                if p_info.get("throttled"):
                    continue
                if effective_query and effective_query in p_info["attempted_queries"]:
                    continue
                if effective_query:
                    p_info["attempted_queries"].add(effective_query)
            active_providers.append(p)

        if tried_sources is not None:
            search_providers = active_providers
        else:
            search_providers = providers

        if not search_providers:
            return []

        # Interleave candidates from providers to ensure a diverse mix
        provider_candidates: List[List[WallpaperCandidate]] = []
        target_per_provider = max(3, (limit // len(search_providers)) + 2)

        for provider in search_providers:
            try:
                candidates = provider.fetch_candidates(
                    category=category,
                    query=effective_query,
                    limit=target_per_provider,
                    exclude_ids=exclude_ids,
                    color=color,
                    custom_color_hex=custom_color_hex,
                    mood=mood,
                )
                if candidates:
                    provider_candidates.append(list(candidates))
            except Exception as e:
                if tried_sources is not None:
                    p_info = tried_sources.setdefault(provider.name, {"failures": 0, "throttled": False, "attempted_queries": set()})
                    p_info["failures"] += 1
                    err_str = str(e).lower()
                    if "429" in err_str or "rate limit" in err_str or "timed out" in err_str or "connect" in err_str:
                        p_info["throttled"] = True
                continue

        # Interleave candidates round-robin
        while any(provider_candidates) and len(all_candidates) < limit:
            for p_list in provider_candidates:
                if p_list and len(all_candidates) < limit:
                    all_candidates.append(p_list.pop(0))

        # If all candidates were excluded by history and list is empty, retry without history exclusion
        if not all_candidates and exclude_ids:
            for provider in search_providers:
                if tried_sources is not None and tried_sources.get(provider.name, {}).get("throttled"):
                    continue
                try:
                    candidates = provider.fetch_candidates(
                        category=category,
                        limit=limit,
                        exclude_ids=set(),
                        color=color,
                        custom_color_hex=custom_color_hex,
                        mood=mood,
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
        color: Optional[ColorPalette] = None,
        custom_color_hex: Optional[str] = None,
        mood: Optional[WallpaperMood] = None,
        season: Optional[Season] = None,
    ) -> Tuple[Optional[WallpaperMetadata], Optional[str]]:
        """Fetch, download, validate, cache, and record a wallpaper for an online category with retries.
        
        Tries across available repositories with progressive adaptive thresholds.
        If strict validation rejects all candidates across attempts, the best-scoring candidate
        closest to the target criteria is delivered to guarantee zero search failures.

        Returns:
            Tuple of (WallpaperMetadata, error_message)
        """
        total_attempts = max_retries if max_retries is not None else getattr(self.config, "max_fetch_retries", 5)
        accumulated_excludes = set(self.history.get_recent_ids())
        active_season = season or (get_current_season() if getattr(self.config, "seasonal_theme_enabled", False) else None)
        tried_sources: Dict[str, Any] = {}
        best_candidate_info: Optional[Tuple[WallpaperCandidate, Path, float]] = None

        for attempt in range(1, total_attempts + 1):
            tier_query = get_retry_tier_query(category, attempt, mood=mood, color=color)
            if mood and mood != WallpaperMood.ANY and attempt <= 3:
                tier_query = augment_query_with_mood(tier_query, mood, category)
            if active_season and attempt <= 3:
                tier_query = augment_query_with_season(tier_query, active_season, category)

            if status_callback:
                mood_info = f" [{mood.value}]" if mood and mood != WallpaperMood.ANY else ""
                color_info = f" ({color.value})" if color and color != ColorPalette.ANY else ""
                season_info = f" ({get_season_display(active_season)[0]} {active_season.value})" if active_season else ""
                retry_strategy = f" [Tier {min(5, attempt)}: '{tier_query}']" if attempt > 1 else ""
                status_callback(
                    f"Attempt {attempt}/{total_attempts}{retry_strategy}: Finding {category.value}{season_info}{mood_info}{color_info} wallpaper...",
                    attempt,
                    total_attempts,
                )

            try:
                candidates = self.fetch_candidates(
                    category,
                    limit=6,
                    color=color,
                    custom_color_hex=custom_color_hex,
                    mood=mood,
                    season=active_season,
                    query=tier_query,
                    tried_sources=tried_sources,
                )
            except TypeError:
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

                    # ── Post-download adaptive validation ─────────────────
                    img_stats = compute_image_stats_from_file(temp_path)
                    if img_stats is not None:
                        passes, reason = validate_image_matches_selection(
                            img_stats,
                            target_palette=color,
                            target_mood=mood,
                            attempt=attempt,
                            allow_soft=(attempt >= 3),
                        )
                        comp_score = compute_image_compatibility_score(img_stats, color, mood)

                        if not passes:
                            # Keep track of closest matching candidate for guaranteed delivery
                            if best_candidate_info is None or comp_score < best_candidate_info[2]:
                                if best_candidate_info is not None and best_candidate_info[1] != temp_path:
                                    try:
                                        best_candidate_info[1].unlink()
                                    except Exception:
                                        pass
                                best_candidate_info = (candidate, temp_path, comp_score)
                            else:
                                if best_candidate_info is None or best_candidate_info[1] != temp_path:
                                    try:
                                        temp_path.unlink()
                                    except Exception:
                                        pass

                            accumulated_excludes.add(candidate.id)
                            if status_callback:
                                status_callback(
                                    f"Skipped (filter mismatch): {reason}",
                                    attempt,
                                    total_attempts,
                                )
                            continue

                    # If candidate passed validation and we had a previous best_candidate_info temp file, clean it up
                    if best_candidate_info is not None and best_candidate_info[1] != temp_path:
                        try:
                            best_candidate_info[1].unlink()
                        except Exception:
                            pass
                        best_candidate_info = None

                    # Extract dominant color for metadata
                    dom_rgb = extract_dominant_color_from_file(temp_path)
                    candidate.dominant_color_hex = rgb_to_hex(*dom_rgb)

                    metadata = self.cache.atomic_save_download(
                        candidate=candidate,
                        temp_download_path=temp_path,
                        mode=mode,
                    )

                    if metadata:
                        metadata.dominant_color_hex = candidate.dominant_color_hex
                        if mood and mood != WallpaperMood.ANY:
                            metadata.mood = mood.value
                        if active_season:
                            metadata.season = active_season.value
                        self.history.record(
                            item_id=candidate.id,
                            category=category.value,
                            sha256=metadata.sha256,
                            title=metadata.title,
                        )
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

        # ── Guaranteed Delivery Fallback ──────────────────────────────────
        # If all attempts exhausted and strictly rejected, deliver the closest candidate
        if best_candidate_info is not None:
            best_cand, best_temp_path, best_score = best_candidate_info
            if best_temp_path.exists():
                if status_callback:
                    status_callback(
                        f"Guaranteed Delivery: using closest matching wallpaper (distance penalty: {best_score:.2f})...",
                        total_attempts,
                        total_attempts,
                    )
                try:
                    dom_rgb = extract_dominant_color_from_file(best_temp_path)
                    best_cand.dominant_color_hex = rgb_to_hex(*dom_rgb)
                    metadata = self.cache.atomic_save_download(
                        candidate=best_cand,
                        temp_download_path=best_temp_path,
                        mode=mode,
                    )
                    if metadata:
                        metadata.dominant_color_hex = best_cand.dominant_color_hex
                        if mood and mood != WallpaperMood.ANY:
                            metadata.mood = mood.value
                        if active_season:
                            metadata.season = active_season.value
                        self.history.record(
                            item_id=best_cand.id,
                            category=category.value,
                            sha256=metadata.sha256,
                            title=metadata.title,
                        )
                        return metadata, None
                except Exception:
                    pass
                finally:
                    if best_temp_path.exists():
                        try:
                            best_temp_path.unlink()
                        except Exception:
                            pass

        # Local cache fallback if all network downloads failed
        fallback_file = self.cache.get_fallback_wallpaper()
        if fallback_file and fallback_file.exists():
            if status_callback:
                status_callback("Using cached wallpaper as fallback...", total_attempts, total_attempts)
            fb_meta = self.cache.store_local_image(fallback_file, mode=mode)
            if fb_meta:
                return fb_meta, None

        return None, f"Failed to acquire {category.value} wallpaper after {total_attempts} attempts."
