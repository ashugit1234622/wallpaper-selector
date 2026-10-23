"""Search history tracking and dynamic category suggestion manager."""

from __future__ import annotations
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any
from .config import AppConfig
from .models import WallpaperCategory
from .keyword_expander import normalize_keyword


@dataclass
class SearchRecord:
    keyword: str
    normalized_keyword: str
    category: str
    timestamp: str
    successful: bool
    palette: Optional[str] = None
    mood: Optional[str] = None
    final_query: Optional[str] = None
    provider: Optional[str] = None
    image_id: Optional[str] = None
    title: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SearchRecord":
        return cls(
            keyword=data.get("keyword", ""),
            normalized_keyword=data.get("normalized_keyword", normalize_keyword(data.get("keyword", ""))),
            category=data.get("category", "General"),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            successful=bool(data.get("successful", False)),
            palette=data.get("palette"),
            mood=data.get("mood"),
            final_query=data.get("final_query"),
            provider=data.get("provider"),
            image_id=data.get("image_id"),
            title=data.get("title"),
        )


CATEGORY_DEFAULT_SUGGESTIONS: Dict[WallpaperCategory, List[str]] = {
    WallpaperCategory.SPACE: ["Black Hole", "James Webb", "Andromeda Galaxy", "Carina Nebula", "Saturn Rings"],
    WallpaperCategory.NATURE: ["Waterfalls", "Misty Forest", "Aurora Borealis", "Alpine Mountains", "Ocean Waves"],
    WallpaperCategory.ART: ["Cyberpunk City", "Oil Painting", "Impressionism", "Fantasy Landscape", "Ukiyo-e Wave"],
    WallpaperCategory.PORTRAIT: ["Renaissance Portrait", "Cyberpunk Character", "Atmospheric Portrait", "Cinematic Lighting"],
}


class SearchHistoryManager:
    """Manages search history persistence and dynamic keyword suggestions."""

    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or AppConfig.load()
        if self.config.custom_cache_dir:
            self.history_file = Path(self.config.custom_cache_dir) / "search_history.json"
        else:
            self.history_file = AppConfig.get_default_data_dir() / "search_history.json"

        self.retention_limit = 50
        self._records: List[SearchRecord] = self._load()

    def _load(self) -> List[SearchRecord]:
        if not self.history_file.exists():
            return []
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return [SearchRecord.from_dict(item) for item in data if isinstance(item, dict)]
        except Exception:
            # Auto-heal corrupted or empty JSON
            pass
        return []

    def _save(self) -> None:
        """Atomically persist records via temporary file replacement."""
        try:
            temp_path = self.history_file.with_suffix(".tmp")
            data = [asdict(r) for r in self._records[-self.retention_limit:]]
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            temp_path.replace(self.history_file)
        except Exception:
            pass

    @property
    def records(self) -> List[SearchRecord]:
        return list(self._records)

    def clear_history(self) -> None:
        """Clear all search history records."""
        self._records.clear()
        self._save()

    def get_record(self, keyword: str) -> Optional[SearchRecord]:
        """Find record by keyword."""
        clean_kw = normalize_keyword(keyword).lower()
        for r in reversed(self._records):
            if r.normalized_keyword == clean_kw:
                return r
        return None

    def record_search(
        self,
        keyword: str,
        category: str,
        successful: Optional[bool] = None,
        success: Optional[bool] = None,
        metadata: Optional[Any] = None,
        palette: Optional[str] = None,
        mood: Optional[str] = None,
        final_query: Optional[str] = None,
        provider: Optional[str] = None,
        image_id: Optional[str] = None,
        title: Optional[str] = None,
    ) -> SearchRecord:
        """Record a search attempt or successful wallpaper discovery."""
        clean_kw = normalize_keyword(keyword)
        if not clean_kw:
            return SearchRecord(keyword="", normalized_keyword="", category=category, timestamp="", successful=False)

        is_success = True
        if successful is not None:
            is_success = bool(successful)
        elif success is not None:
            is_success = bool(success)

        if metadata:
            image_id = image_id or getattr(metadata, "image_id", None) or getattr(metadata, "id", None)
            title = title or getattr(metadata, "title", None)
            provider = provider or getattr(metadata, "provider", None) or getattr(metadata, "provider_name", None)
            palette = palette or getattr(metadata, "dominant_color_hex", None)
            mood = mood or (metadata.mood.value if hasattr(getattr(metadata, "mood", None), "value") else str(getattr(metadata, "mood", None) or ""))

        record = SearchRecord(
            keyword=keyword.strip(),
            normalized_keyword=clean_kw.lower(),
            category=category,
            timestamp=datetime.now(timezone.utc).isoformat(),
            successful=is_success,
            palette=palette,
            mood=mood,
            final_query=final_query,
            provider=provider,
            image_id=image_id,
            title=title,
        )

        # Deduplicate recent entries matching the exact same keyword and category
        self._records = [
            r for r in self._records
            if not (r.normalized_keyword == record.normalized_keyword and r.category == record.category)
        ]
        self._records.append(record)
        self._save()
        return record

    def get_recent_keywords(self, limit: int = 5, category: Optional[WallpaperCategory] = None) -> List[str]:
        """Return list of recent successful search keywords."""
        cat_filter = category.value if hasattr(category, "value") else (str(category) if category else None)
        seen = set()
        results = []

        # Iterate from newest to oldest
        for r in reversed(self._records):
            if not r.successful:
                continue
            if cat_filter and r.category != cat_filter:
                continue
            norm = r.normalized_keyword
            if norm not in seen:
                seen.add(norm)
                results.append(r.keyword)
                if len(results) >= limit:
                    break

        return results

    def get_recent_searches(self, limit: int = 5, category: Optional[WallpaperCategory] = None) -> List[str]:
        return self.get_recent_keywords(limit=limit, category=category)

    def get_suggestions(self, category: Optional[WallpaperCategory] = None, limit: int = 5) -> List[str]:
        return self.get_suggestions_for_category(category=category, limit=limit)

    def get_suggestions_for_category(self, category: Optional[WallpaperCategory] = None, limit: int = 5) -> List[str]:
        """Return curated + recent suggestions for a category."""
        defaults = CATEGORY_DEFAULT_SUGGESTIONS.get(category, ["Black Hole", "Waterfalls", "Cyberpunk", "Impressionism"])
        recent = self.get_recent_keywords(limit=2, category=category)
        
        # Combine recent user searches with defaults without duplicates
        combined = []
        seen = set()
        for kw in recent + defaults:
            norm = kw.lower().strip()
            if norm not in seen:
                seen.add(norm)
                combined.append(kw)
        return combined[:limit]
