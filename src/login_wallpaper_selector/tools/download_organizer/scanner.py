"""Folder scanner for Download Folder Organizer."""

from __future__ import annotations
import os
import sys
from pathlib import Path
from typing import Optional, List, Tuple, Dict
from platformdirs import user_downloads_dir

from .models import FileItem, ScanSummary, FileCategory
from .classifier import classify_file, extract_extension


IGNORE_FILENAMES = {
    "desktop.ini",
    "thumbs.db",
    ".ds_store",
    ".git",
    ".gitignore",
    ".svn",
}


def get_default_downloads_folder() -> Path:
    """Resolve the operating system's default Downloads folder."""
    try:
        downloads_str = user_downloads_dir()
        if downloads_str:
            p = Path(downloads_str)
            if p.exists() and p.is_dir():
                return p
    except Exception:
        pass

    fallback = Path.home() / "Downloads"
    if fallback.exists() and fallback.is_dir():
        return fallback
    return Path.home()


def is_hidden_or_system(name: str) -> bool:
    """Check if file/folder is hidden or a known OS system artifact."""
    lower = name.lower()
    if lower in IGNORE_FILENAMES or lower.startswith("."):
        return True
    return False


def scan_folder(
    folder_path: Path,
    destination_folder: Optional[Path] = None,
    recursive: bool = False,
    custom_rules: Optional[Dict[str, str]] = None,
) -> Tuple[List[FileItem], ScanSummary]:
    """Scan a target directory and gather file statistics.
    
    Args:
        folder_path: Directory to analyze.
        destination_folder: Proposed target directory for organized files (excluded from scan).
        recursive: If True, recursively scans subdirectories. If False, only top-level files.
        custom_rules: User custom extension-to-category mapping.
        
    Returns:
        Tuple of (discovered FileItem list, ScanSummary)
    """
    resolved_source = folder_path.resolve()
    summary = ScanSummary(scanned_path=resolved_source)

    if not resolved_source.exists() or not resolved_source.is_dir():
        return [], summary

    target_dest = (destination_folder or (resolved_source / "Organized")).resolve()
    items: List[FileItem] = []
    folder_count = 0

    try:
        if not recursive:
            with os.scandir(resolved_source) as it:
                for entry in it:
                    try:
                        # Skip symlinks
                        if entry.is_symlink():
                            continue

                        if entry.is_dir(follow_symlinks=False):
                            entry_path = Path(entry.path).resolve()
                            # Never scan inside the designated destination folder
                            if entry_path == target_dest or target_dest in entry_path.parents:
                                continue
                            if not is_hidden_or_system(entry.name):
                                folder_count += 1
                            continue

                        if entry.is_file(follow_symlinks=False):
                            if is_hidden_or_system(entry.name):
                                continue

                            stat_res = entry.stat(follow_symlinks=False)
                            file_path = Path(entry.path)
                            ext = extract_extension(entry.name)
                            category = classify_file(entry.name, custom_rules)
                            
                            # Check creation / modification times
                            mtime = stat_res.st_mtime
                            # On Windows st_ctime is creation time; on Unix it's metadata change
                            ctime = getattr(stat_res, "st_birthtime", stat_res.st_ctime)

                            item = FileItem(
                                path=file_path,
                                filename=entry.name,
                                extension=ext,
                                size_bytes=stat_res.st_size,
                                category=category,
                                created_time=ctime,
                                modified_time=mtime,
                                is_already_organized=False,
                            )
                            items.append(item)
                    except (PermissionError, FileNotFoundError, OSError):
                        continue
        else:
            # Recursive scanning
            for root, dirs, files in os.walk(resolved_source, followlinks=False):
                root_path = Path(root).resolve()
                # Skip target destination directory and its subtrees
                if root_path == target_dest or target_dest in root_path.parents:
                    dirs.clear()
                    continue

                # Filter out hidden directories in-place so os.walk does not traverse them
                dirs[:] = [d for d in dirs if not is_hidden_or_system(d)]
                folder_count += len(dirs)

                for f in files:
                    if is_hidden_or_system(f):
                        continue
                    full_p = root_path / f
                    try:
                        if full_p.is_symlink():
                            continue
                        stat_res = full_p.stat(follow_symlinks=False)
                        ext = extract_extension(f)
                        category = classify_file(f, custom_rules)
                        mtime = stat_res.st_mtime
                        ctime = getattr(stat_res, "st_birthtime", stat_res.st_ctime)

                        item = FileItem(
                            path=full_p,
                            filename=f,
                            extension=ext,
                            size_bytes=stat_res.st_size,
                            category=category,
                            created_time=ctime,
                            modified_time=mtime,
                            is_already_organized=False,
                        )
                        items.append(item)
                    except (PermissionError, FileNotFoundError, OSError):
                        continue

    except (PermissionError, OSError):
        pass

    # Calculate summary metrics
    summary.total_files = len(items)
    summary.total_folders = folder_count
    summary.total_size_bytes = sum(i.size_bytes for i in items)
    summary.total_supported_files = sum(1 for i in items if i.category != FileCategory.OTHER.value)
    summary.organizable_files = len(items)
    summary.already_suitable = 0
    summary.needs_review = sum(1 for i in items if i.category == FileCategory.OTHER.value)

    return items, summary
