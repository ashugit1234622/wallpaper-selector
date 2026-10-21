"""Cache manager for downloaded wallpapers and companion metadata."""

from __future__ import annotations
import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from PIL import Image

from .config import AppConfig
from .models import WallpaperCandidate, WallpaperMetadata, WallpaperPosition


class CacheManager:
    """Manages the download, validation, atomic caching, and retention of wallpapers."""

    def __init__(self, config: AppConfig):
        self.config = config
        if config.custom_cache_dir:
            self.cache_dir = Path(config.custom_cache_dir)
        else:
            self.cache_dir = AppConfig.get_default_cache_dir()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_file = self.cache_dir / "metadata.json"
        self._metadata_store: Dict[str, Dict[str, Any]] = self._load_metadata()

    def _load_metadata(self) -> Dict[str, Dict[str, Any]]:
        if not self.metadata_file.exists():
            return {}
        try:
            with open(self.metadata_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
        return {}

    def _save_metadata(self) -> None:
        try:
            temp_path = self.metadata_file.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self._metadata_store, f, indent=2)
            temp_path.replace(self.metadata_file)
        except Exception:
            pass

    def compute_sha256(self, file_path: Path) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def validate_image_file(self, file_path: Path) -> Tuple[bool, int, int, str]:
        """Verify image integrity with Pillow.
        
        Returns:
            Tuple of (is_valid, width, height, format_name)
        """
        try:
            with Image.open(file_path) as img:
                img.verify()  # Check for corruption
            
            # Reopen to read dimensions and format (verify() closes or resets parser)
            with Image.open(file_path) as img:
                width, height = img.size
                fmt = img.format or "UNKNOWN"
                return True, width, height, fmt
        except Exception:
            return False, 0, 0, "CORRUPT"

    def store_local_image(self, source_path: Path, mode: str = WallpaperPosition.FILL.value) -> Optional[WallpaperMetadata]:
        """Validate and prepare a local storage image without modifying or deleting the original."""
        if not source_path.exists() or not source_path.is_file():
            return None

        is_valid, width, height, fmt = self.validate_image_file(source_path)
        if not is_valid or width <= 0 or height <= 0:
            return None

        # For Windows wallpaper compatibility, if WebP, convert a copy to PNG in cache
        dest_filename = f"local_{source_path.stem}_{int(time.time())}"
        if fmt.upper() in ("WEBP", "TIFF"):
            target_file = self.cache_dir / f"{dest_filename}.png"
            with Image.open(source_path) as img:
                img.save(target_file, format="PNG")
        else:
            target_file = self.cache_dir / f"{dest_filename}{source_path.suffix.lower()}"
            shutil.copy2(source_path, target_file)

        sha256_hash = self.compute_sha256(target_file)
        metadata = WallpaperMetadata(
            image_id=f"local_{sha256_hash[:12]}",
            category="Local Storage",
            provider="Local File System",
            source_url=str(source_path.resolve()),
            download_url="file://" + str(source_path.resolve()),
            local_path=str(target_file.resolve()),
            sha256=sha256_hash,
            title=source_path.name,
            creator="User Local File",
            license="Local File",
            license_url=None,
            attribution_required=False,
            attribution_text="",
            width=width,
            height=height,
            aspect_ratio=width / height,
            mode=mode,
        )

        self._record_metadata(metadata)
        self.enforce_quota()
        return metadata

    def atomic_save_download(
        self,
        candidate: WallpaperCandidate,
        temp_download_path: Path,
        mode: str = WallpaperPosition.FILL.value,
    ) -> Optional[WallpaperMetadata]:
        """Validate a downloaded temp file and atomically commit it to cache."""
        try:
            is_valid, width, height, fmt = self.validate_image_file(temp_download_path)
            if not is_valid:
                if temp_download_path.exists():
                    temp_download_path.unlink()
                return None

            # Calculate hash
            sha256_hash = self.compute_sha256(temp_download_path)
            clean_id = "".join(c for c in candidate.id if c.isalnum() or c in ("-", "_"))[:32]
            
            # Extension resolution
            ext = ".jpg"
            if fmt.upper() == "PNG":
                ext = ".png"
            elif fmt.upper() == "WEBP":
                # Convert WebP to PNG for wallpaper API compatibility
                converted_temp = temp_download_path.with_suffix(".png.tmp")
                with Image.open(temp_download_path) as img:
                    img.save(converted_temp, format="PNG")
                temp_download_path.unlink()
                temp_download_path = converted_temp
                ext = ".png"

            final_path = self.cache_dir / f"{candidate.category.value.lower()}_{clean_id}_{sha256_hash[:8]}{ext}"

            # Atomically rename
            temp_download_path.replace(final_path)

            metadata = WallpaperMetadata(
                image_id=candidate.id,
                category=candidate.category.value,
                provider=candidate.provider_name,
                source_url=candidate.source_url,
                download_url=candidate.download_url,
                local_path=str(final_path.resolve()),
                sha256=sha256_hash,
                title=candidate.title,
                creator=candidate.creator,
                license=candidate.license_name,
                license_url=candidate.license_url,
                attribution_required=candidate.attribution_required,
                attribution_text=candidate.attribution_text,
                width=width,
                height=height,
                aspect_ratio=width / height,
                mode=mode,
            )

            self._record_metadata(metadata)
            self.enforce_quota()
            return metadata
        except Exception:
            if temp_download_path.exists():
                try:
                    temp_download_path.unlink()
                except Exception:
                    pass
            return None

    def _record_metadata(self, metadata: WallpaperMetadata) -> None:
        self._metadata_store[metadata.image_id] = metadata.to_dict()
        self._save_metadata()

    def get_latest_metadata(self) -> Optional[Dict[str, Any]]:
        """Return the most recently applied wallpaper metadata."""
        if not self._metadata_store:
            return None
        # Sort by applied_at
        sorted_items = sorted(
            self._metadata_store.values(),
            key=lambda x: x.get("applied_at", ""),
            reverse=True,
        )
        return sorted_items[0] if sorted_items else None

    def get_fallback_wallpaper(self) -> Optional[Path]:
        """Retrieve the most recent existing, valid wallpaper from the cache for offline fallback."""
        sorted_items = sorted(
            self._metadata_store.values(),
            key=lambda x: x.get("applied_at", ""),
            reverse=True,
        )
        for item in sorted_items:
            path_str = item.get("local_path")
            if path_str:
                p = Path(path_str)
                if p.exists() and p.is_file():
                    valid, _, _, _ = self.validate_image_file(p)
                    if valid:
                        return p
        return None

    def get_total_cache_size_bytes(self) -> int:
        total = 0
        for entry in self.cache_dir.iterdir():
            if entry.is_file():
                try:
                    total += entry.stat().st_size
                except OSError:
                    pass
        return total

    def enforce_quota(self) -> None:
        """Prune oldest cached files if cache size exceeds quota."""
        max_bytes = max(50, self.config.cache_quota_mb) * 1024 * 1024
        current_size = self.get_total_cache_size_bytes()
        if current_size <= max_bytes:
            return

        # Find all cache image files
        files = []
        for p in self.cache_dir.iterdir():
            if p.is_file() and p.name not in ("metadata.json", "config.json"):
                try:
                    files.append((p, p.stat().st_mtime, p.stat().st_size))
                except OSError:
                    pass

        # Sort by oldest modification time
        files.sort(key=lambda x: x[1])

        for file_path, _, size in files:
            if current_size <= max_bytes:
                break
            try:
                file_path.unlink()
                current_size -= size
                # Remove from metadata store
                for k, v in list(self._metadata_store.items()):
                    if v.get("local_path") == str(file_path.resolve()):
                        del self._metadata_store[k]
            except Exception:
                pass

        self._save_metadata()
