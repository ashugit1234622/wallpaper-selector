"""Favorites, star ratings, and taste profile learning for wallpapers."""

from __future__ import annotations
import json
import random
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

from .config import AppConfig
from .models import WallpaperMetadata, WallpaperCategory, ColorPalette, WallpaperMood


@dataclass
class FavoriteRecord:
    """Persistent record of a favorited or rated wallpaper."""
    image_id: str
    title: str
    category: str
    local_path: str
    saved_path: Optional[str] = None
    provider: str = ""
    is_favorite: bool = True
    rating: int = 0  # 0 to 5 stars
    dominant_color_hex: Optional[str] = None
    mood: Optional[str] = None
    season: Optional[str] = None
    favorited_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FavoriteRecord":
        return cls(
            image_id=str(data.get("image_id", "")),
            title=str(data.get("title", "Wallpaper")),
            category=str(data.get("category", "")),
            local_path=str(data.get("local_path", "")),
            saved_path=data.get("saved_path"),
            provider=str(data.get("provider", "")),
            is_favorite=bool(data.get("is_favorite", True)),
            rating=int(data.get("rating", 0)),
            dominant_color_hex=data.get("dominant_color_hex"),
            mood=data.get("mood"),
            season=data.get("season"),
            favorited_at=str(data.get("favorited_at", "")),
        )


class FavoritesManager:
    """Manages storage, retrieval, and taste profile learning for favorited wallpapers."""

    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or AppConfig.load()
        if self.config.custom_cache_dir:
            self.file_path = Path(self.config.custom_cache_dir) / "favorites.json"
        else:
            self.file_path = AppConfig.get_default_data_dir() / "favorites.json"

        self._records: Dict[str, FavoriteRecord] = self._load()

    def _load(self) -> Dict[str, FavoriteRecord]:
        if not self.file_path.exists():
            return {}
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return {k: FavoriteRecord.from_dict(v) for k, v in data.items()}
                elif isinstance(data, list):
                    return {item.get("image_id"): FavoriteRecord.from_dict(item) for item in data if "image_id" in item}
        except Exception:
            pass
        return {}

    def _save(self) -> None:
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump({k: r.to_dict() for k, r in self._records.items()}, f, indent=2)
        except Exception:
            pass

    def is_favorite(self, image_id: str) -> bool:
        """Check if an image ID is currently marked as favorite."""
        rec = self._records.get(image_id)
        return bool(rec and rec.is_favorite)

    def get_rating(self, image_id: str) -> int:
        """Get star rating (0-5) for an image ID."""
        rec = self._records.get(image_id)
        return rec.rating if rec else 0

    def toggle_favorite(self, metadata: WallpaperMetadata) -> bool:
        """Toggle favorite status. Returns True if now favorited, False if unfavorited."""
        rec = self._records.get(metadata.image_id)
        if rec:
            rec.is_favorite = not rec.is_favorite
            # Update paths if metadata has fresh ones
            if metadata.local_path:
                rec.local_path = metadata.local_path
            new_status = rec.is_favorite
        else:
            rec = FavoriteRecord(
                image_id=metadata.image_id,
                title=metadata.title,
                category=metadata.category,
                local_path=metadata.local_path,
                provider=metadata.provider,
                is_favorite=True,
                rating=metadata.rating or 0,
                dominant_color_hex=metadata.dominant_color_hex,
                mood=metadata.mood,
                season=getattr(metadata, "season", None),
            )
            self._records[metadata.image_id] = rec
            new_status = True

        self._save()
        return new_status

    def set_rating(self, image_id: str, rating: int, metadata: Optional[WallpaperMetadata] = None) -> int:
        """Assign 1-5 star rating to an image (0 to clear rating). Returns new rating."""
        rating = max(0, min(5, int(rating)))
        rec = self._records.get(image_id)
        if rec:
            rec.rating = rating
        elif metadata:
            rec = FavoriteRecord(
                image_id=metadata.image_id,
                title=metadata.title,
                category=metadata.category,
                local_path=metadata.local_path,
                provider=metadata.provider,
                is_favorite=False,
                rating=rating,
                dominant_color_hex=metadata.dominant_color_hex,
                mood=metadata.mood,
                season=getattr(metadata, "season", None),
            )
            self._records[image_id] = rec

        self._save()
        return rating

    def get_favorites(
        self,
        min_rating: int = 0,
        category: Optional[str] = None,
        only_existing_files: bool = True,
    ) -> List[FavoriteRecord]:
        """Return list of favorited or rated records matching criteria."""
        results = []
        for r in self._records.values():
            if not r.is_favorite and r.rating < max(1, min_rating):
                continue
            if min_rating > 0 and r.rating < min_rating:
                continue
            if category and r.category.lower() != category.lower():
                continue
            if only_existing_files:
                p = Path(r.saved_path or r.local_path)
                if not p.exists():
                    continue
            results.append(r)
        return results

    def get_random_favorite(self) -> Optional[FavoriteRecord]:
        """Return a random favorited image whose file exists on disk."""
        candidates = self.get_favorites(only_existing_files=True)
        if not candidates:
            return None
        # Weight by rating: 5-star gets weight 5, 4-star gets weight 4, unrated favorite gets weight 2
        weights = [max(2, r.rating) for r in candidates]
        return random.choices(candidates, weights=weights, k=1)[0]

    def compute_taste_profile(self) -> Dict[str, Any]:
        """Extract user taste preferences from favorites and 4-5 star ratings."""
        category_counts: Dict[str, int] = {}
        mood_counts: Dict[str, int] = {}
        color_counts: Dict[str, int] = {}

        for rec in self._records.values():
            if not rec.is_favorite and rec.rating < 4:
                continue

            multiplier = 2 if rec.rating == 5 else 1
            if rec.category:
                category_counts[rec.category] = category_counts.get(rec.category, 0) + multiplier
            if rec.mood and rec.mood != "Any":
                mood_counts[rec.mood] = mood_counts.get(rec.mood, 0) + multiplier
            if rec.dominant_color_hex:
                color_counts[rec.dominant_color_hex] = color_counts.get(rec.dominant_color_hex, 0) + multiplier

        top_category = max(category_counts, key=category_counts.get) if category_counts else None
        top_mood = max(mood_counts, key=mood_counts.get) if mood_counts else None

        return {
            "category_counts": category_counts,
            "top_category": top_category,
            "top_mood": top_mood,
            "total_favorites": sum(1 for r in self._records.values() if r.is_favorite),
        }
