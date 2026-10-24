"""Manager for tracking and persisting the 5 most recent successfully fetched wallpapers."""

from __future__ import annotations
import json
import threading
from pathlib import Path
from typing import List, Optional
from .config import AppConfig
from .models import WallpaperMetadata


class RecentWallpaperManager:
    """Tracks up to 5 most recently fetched wallpapers with disk persistence and file validation."""

    DEFAULT_CAPACITY = 5

    def __init__(
        self,
        config: Optional[AppConfig] = None,
        max_items: int = DEFAULT_CAPACITY,
        history_file: Optional[Path] = None,
    ):
        self.config = config or AppConfig()
        self.max_items = max_items
        self._lock = threading.Lock()

        if history_file:
            self.history_file = Path(history_file)
        elif self.config.custom_cache_dir:
            self.history_file = Path(self.config.custom_cache_dir) / "recent_previews.json"
        else:
            self.history_file = AppConfig.get_default_data_dir() / "recent_previews.json"

        self._items: List[WallpaperMetadata] = self._load()

    def add(self, meta: WallpaperMetadata) -> None:
        """Add a successfully fetched wallpaper to recent history.
        
        If the item already exists in history, it is moved to the most recent position.
        Enforces max_items retention (FIFO) and saves to disk.
        """
        if not meta or not meta.local_path:
            return

        target_path = Path(meta.local_path)
        if not target_path.exists():
            return

        with self._lock:
            # Remove duplicate by image_id or local_path to keep order unique
            self._items = [
                item for item in self._items
                if item.image_id != meta.image_id and item.local_path != meta.local_path
            ]
            self._items.append(meta)
            if len(self._items) > self.max_items:
                self._items = self._items[-self.max_items:]
            self._save()

    def get_items(self) -> List[WallpaperMetadata]:
        """Return all valid recent items whose files still exist on disk."""
        with self._lock:
            valid = [item for item in self._items if Path(item.local_path).exists()]
            if len(valid) != len(self._items):
                self._items = valid
                self._save()
            return list(self._items)

    def get_item_at(self, index: int) -> Optional[WallpaperMetadata]:
        """Return the item at the given index, or None if out of bounds."""
        items = self.get_items()
        if 0 <= index < len(items):
            return items[index]
        return None

    def clear(self) -> None:
        """Clear all recent history items and remove persistence file."""
        with self._lock:
            self._items = []
            try:
                if self.history_file.exists():
                    self.history_file.unlink()
            except Exception:
                pass

    def _load(self) -> List[WallpaperMetadata]:
        if not self.history_file.exists():
            return []
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                return []
            records = []
            for item in data:
                if isinstance(item, dict):
                    meta = WallpaperMetadata.from_dict(item)
                    if meta.local_path and Path(meta.local_path).exists():
                        records.append(meta)
            return records[-self.max_items:]
        except Exception:
            return []

    def _save(self) -> None:
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            payload = [item.to_dict() for item in self._items]
            temp_file = self.history_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            temp_file.replace(self.history_file)
        except Exception:
            try:
                # Direct fallback write
                with open(self.history_file, "w", encoding="utf-8") as f:
                    json.dump([item.to_dict() for item in self._items], f, indent=2)
            except Exception:
                pass
