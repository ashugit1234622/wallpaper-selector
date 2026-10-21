"""History tracking for recently applied wallpapers to prevent immediate repetition."""

from __future__ import annotations
import json
from pathlib import Path
from typing import List, Set
from .config import AppConfig


class HistoryTracker:
    def __init__(self, config: AppConfig):
        self.config = config
        self.history_file = AppConfig.get_default_data_dir() / "history.json"
        self._history: List[str] = self._load()

    def _load(self) -> List[str]:
        if not self.history_file.exists():
            return []
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return [str(item) for item in data]
        except Exception:
            pass
        return []

    def _save(self) -> None:
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self._history, f, indent=2)
        except Exception:
            pass

    def has_seen(self, item_id: str) -> bool:
        """Check if this item ID was used recently."""
        return item_id in self._history

    def record(self, item_id: str) -> None:
        """Record an item ID as recently used, moving it to the end and trimming."""
        if item_id in self._history:
            self._history.remove(item_id)
        self._history.append(item_id)
        
        # Enforce max limit
        limit = max(10, self.config.history_limit)
        if len(self._history) > limit:
            self._history = self._history[-limit:]
            
        self._save()

    def get_recent_ids(self) -> Set[str]:
        return set(self._history)

    def clear(self) -> None:
        self._history = []
        self._save()
