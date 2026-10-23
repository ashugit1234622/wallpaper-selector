"""Deterministic file classifier for Download Folder Organizer."""

from __future__ import annotations
import os
from pathlib import Path
from typing import Optional, Dict

from .models import FileCategory


# Extension to category mapping dictionary
STANDARD_EXTENSION_MAP: Dict[str, FileCategory] = {
    # Images
    "jpg": FileCategory.IMAGES,
    "jpeg": FileCategory.IMAGES,
    "png": FileCategory.IMAGES,
    "webp": FileCategory.IMAGES,
    "gif": FileCategory.IMAGES,
    "bmp": FileCategory.IMAGES,
    "svg": FileCategory.IMAGES,
    "tiff": FileCategory.IMAGES,
    "tif": FileCategory.IMAGES,
    "ico": FileCategory.IMAGES,
    "raw": FileCategory.IMAGES,
    "heic": FileCategory.IMAGES,
    "psd": FileCategory.IMAGES,
    "ai": FileCategory.IMAGES,

    # Documents
    "pdf": FileCategory.DOCUMENTS,
    "docx": FileCategory.DOCUMENTS,
    "doc": FileCategory.DOCUMENTS,
    "txt": FileCategory.DOCUMENTS,
    "rtf": FileCategory.DOCUMENTS,
    "odt": FileCategory.DOCUMENTS,
    "md": FileCategory.DOCUMENTS,
    "epub": FileCategory.DOCUMENTS,
    "mobi": FileCategory.DOCUMENTS,
    "pages": FileCategory.DOCUMENTS,

    # Videos
    "mp4": FileCategory.VIDEOS,
    "mkv": FileCategory.VIDEOS,
    "mov": FileCategory.VIDEOS,
    "avi": FileCategory.VIDEOS,
    "wmv": FileCategory.VIDEOS,
    "webm": FileCategory.VIDEOS,
    "flv": FileCategory.VIDEOS,
    "m4v": FileCategory.VIDEOS,
    "mpg": FileCategory.VIDEOS,
    "mpeg": FileCategory.VIDEOS,
    "3gp": FileCategory.VIDEOS,

    # Audio
    "mp3": FileCategory.AUDIO,
    "wav": FileCategory.AUDIO,
    "flac": FileCategory.AUDIO,
    "aac": FileCategory.AUDIO,
    "ogg": FileCategory.AUDIO,
    "m4a": FileCategory.AUDIO,
    "wma": FileCategory.AUDIO,
    "opus": FileCategory.AUDIO,
    "mid": FileCategory.AUDIO,
    "midi": FileCategory.AUDIO,

    # Archives
    "zip": FileCategory.ARCHIVES,
    "7z": FileCategory.ARCHIVES,
    "rar": FileCategory.ARCHIVES,
    "tar": FileCategory.ARCHIVES,
    "gz": FileCategory.ARCHIVES,
    "bz2": FileCategory.ARCHIVES,
    "xz": FileCategory.ARCHIVES,
    "tar.gz": FileCategory.ARCHIVES,
    "tar.bz2": FileCategory.ARCHIVES,
    "tar.xz": FileCategory.ARCHIVES,
    "tgz": FileCategory.ARCHIVES,
    "tbz2": FileCategory.ARCHIVES,

    # Installers & System Packages
    "exe": FileCategory.INSTALLERS,
    "msi": FileCategory.INSTALLERS,
    "bat": FileCategory.INSTALLERS,
    "cmd": FileCategory.INSTALLERS,
    "dmg": FileCategory.INSTALLERS,
    "pkg": FileCategory.INSTALLERS,
    "deb": FileCategory.INSTALLERS,
    "rpm": FileCategory.INSTALLERS,
    "appimage": FileCategory.INSTALLERS,
    "iso": FileCategory.INSTALLERS,
    "img": FileCategory.INSTALLERS,

    # Code & Development
    "py": FileCategory.CODE,
    "js": FileCategory.CODE,
    "ts": FileCategory.CODE,
    "html": FileCategory.CODE,
    "htm": FileCategory.CODE,
    "css": FileCategory.CODE,
    "scss": FileCategory.CODE,
    "json": FileCategory.CODE,
    "yaml": FileCategory.CODE,
    "yml": FileCategory.CODE,
    "xml": FileCategory.CODE,
    "c": FileCategory.CODE,
    "cpp": FileCategory.CODE,
    "h": FileCategory.CODE,
    "hpp": FileCategory.CODE,
    "cs": FileCategory.CODE,
    "java": FileCategory.CODE,
    "rs": FileCategory.CODE,
    "go": FileCategory.CODE,
    "sh": FileCategory.CODE,
    "bash": FileCategory.CODE,
    "ps1": FileCategory.CODE,
    "sql": FileCategory.CODE,
    "php": FileCategory.CODE,
    "rb": FileCategory.CODE,
    "swift": FileCategory.CODE,
    "kt": FileCategory.CODE,

    # Spreadsheets & Data
    "csv": FileCategory.SPREADSHEETS,
    "xlsx": FileCategory.SPREADSHEETS,
    "xls": FileCategory.SPREADSHEETS,
    "tsv": FileCategory.SPREADSHEETS,
    "ods": FileCategory.SPREADSHEETS,
    "parquet": FileCategory.SPREADSHEETS,
    "feather": FileCategory.SPREADSHEETS,
    "sqlite": FileCategory.SPREADSHEETS,
    "db": FileCategory.SPREADSHEETS,

    # Presentations
    "pptx": FileCategory.PRESENTATIONS,
    "ppt": FileCategory.PRESENTATIONS,
    "key": FileCategory.PRESENTATIONS,
    "odp": FileCategory.PRESENTATIONS,
}

COMPOUND_EXTENSIONS = (
    ".tar.gz",
    ".tar.bz2",
    ".tar.xz",
    ".tar.zst",
)


def extract_extension(filename: str) -> str:
    """Extract lowercased extension, handling compound extensions like .tar.gz."""
    lower_name = filename.lower()
    for compound in COMPOUND_EXTENSIONS:
        if lower_name.endswith(compound):
            return compound.lstrip(".")
    
    ext = Path(filename).suffix.lower()
    return ext.lstrip(".")


def classify_file(filename: str, custom_rules: Optional[Dict[str, str]] = None) -> str:
    """Classify a file into a category based on its extension and optional custom rules."""
    ext = extract_extension(filename)
    if not ext:
        return FileCategory.OTHER.value

    # 1. Check custom user rules first
    if custom_rules and ext in custom_rules:
        return custom_rules[ext]

    # 2. Check standard mapping
    if ext in STANDARD_EXTENSION_MAP:
        return STANDARD_EXTENSION_MAP[ext].value

    return FileCategory.OTHER.value
