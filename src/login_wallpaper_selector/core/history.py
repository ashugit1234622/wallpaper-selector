"""History tracking with time-based anti-repetition cooldown system."""

from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Set, Optional
from .config import AppConfig
from .models import HistoryRecord


class HistoryTracker:
    """Tracks applied wallpaper history and enforces configurable anti-repetition cooldowns."""

    def __init__(self, config: AppConfig):
        self.config = config
        if config.custom_cache_dir:
            self.history_file = Path(config.custom_cache_dir) / "history.json"
        else:
            self.history_file = AppConfig.get_default_data_dir() / "history.json"
        self._records: List[HistoryRecord] = self._load()

    @property
    def records(self) -> List[HistoryRecord]:
        return self._records

    @records.setter
    def records(self, new_records: List[HistoryRecord]) -> None:
        self._records = new_records

    def get_latest_record(self) -> Optional[HistoryRecord]:
        return self._records[-1] if self._records else None

    def _load(self) -> List[HistoryRecord]:
        if not self.history_file.exists():
            return []
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    records = []
                    now_str = datetime.now(timezone.utc).isoformat()
                    for item in data:
                        if isinstance(item, dict):
                            records.append(HistoryRecord.from_dict(item))
                        elif isinstance(item, str):
                            # Backwards-compatibility migration for legacy list of string IDs
                            records.append(
                                HistoryRecord(
                                    image_id=item,
                                    applied_at=now_str,
                                )
                            )
                    return records
        except Exception:
            pass
        return []

    def _save(self) -> None:
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump([r.to_dict() for r in self._records], f, indent=2)
        except Exception:
            pass

    def _parse_iso(self, ts_str: str) -> Optional[datetime]:
        try:
            clean_str = ts_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None

    def record(
        self,
        item_id: str,
        category: str = "",
        sha256: Optional[str] = None,
        title: Optional[str] = None,
    ) -> None:
        """Record an applied wallpaper with current UTC timestamp for cooldown tracking."""
        # Remove any existing record with matching ID or SHA256 to update timestamp
        self._records = [
            r for r in self._records
            if r.image_id != item_id and (sha256 is None or r.sha256 != sha256)
        ]

        now_str = datetime.now(timezone.utc).isoformat()
        new_record = HistoryRecord(
            image_id=item_id,
            applied_at=now_str,
            category=category,
            sha256=sha256,
            title=title,
        )
        self._records.append(new_record)

        # Enforce maximum history retention limit
        limit = max(50, getattr(self.config, "history_limit", 50) * 2)
        if len(self._records) > limit:
            self._records = self._records[-limit:]

        self._save()

    def is_in_cooldown(
        self,
        item_id: str,
        cooldown_days: Optional[int] = None,
        sha256: Optional[str] = None,
    ) -> bool:
        """Check if an image ID or sha256 was applied within the active cooldown window."""
        if not getattr(self.config, "anti_repetition_enabled", True):
            return False

        days = cooldown_days if cooldown_days is not None else getattr(self.config, "anti_repetition_days", 14)
        if days <= 0:
            return False

        now = datetime.now(timezone.utc)
        threshold = now - timedelta(days=days)

        for record in reversed(self._records):
            if record.image_id == item_id or (sha256 and record.sha256 and record.sha256 == sha256):
                dt = self._parse_iso(record.applied_at)
                if dt and dt > threshold:
                    return True

        return False

    def get_cooldown_ids(self, cooldown_days: Optional[int] = None) -> Set[str]:
        """Return all candidate IDs and SHA256 hashes currently under anti-repetition cooldown."""
        if not getattr(self.config, "anti_repetition_enabled", True):
            return set()

        days = cooldown_days if cooldown_days is not None else getattr(self.config, "anti_repetition_days", 14)
        if days <= 0:
            return set()

        now = datetime.now(timezone.utc)
        threshold = now - timedelta(days=days)
        cooldown_ids: Set[str] = set()

        for record in self._records:
            dt = self._parse_iso(record.applied_at)
            if dt and dt > threshold:
                cooldown_ids.add(record.image_id)
                if record.sha256:
                    cooldown_ids.add(record.sha256)

        return cooldown_ids

    def get_recent_ids(self) -> Set[str]:
        """Backwards-compatible query returning currently excluded IDs."""
        cooldown = self.get_cooldown_ids()
        if cooldown:
            return cooldown
        return {r.image_id for r in self._records}

    def has_seen(self, item_id: str) -> bool:
        """Check if item is either currently in cooldown or has ever been seen."""
        if self.is_in_cooldown(item_id):
            return True
        return any(r.image_id == item_id for r in self._records)

    def prune_expired(self, retention_days: int = 90) -> int:
        """Remove history records older than retention_days. Returns count pruned."""
        now = datetime.now(timezone.utc)
        threshold = now - timedelta(days=retention_days)
        initial_len = len(self._records)

        kept: List[HistoryRecord] = []
        for r in self._records:
            dt = self._parse_iso(r.applied_at)
            if dt and dt > threshold:
                kept.append(r)

        self._records = kept
        if len(self._records) != initial_len:
            self._save()
        return initial_len - len(self._records)

    def clear(self) -> None:
        """Clear all historical records."""
        self._records = []
        self._save()
