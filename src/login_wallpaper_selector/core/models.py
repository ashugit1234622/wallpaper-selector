"""Data models and enums for Login Wallpaper Selector."""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime


class WallpaperCategory(str, Enum):
    SPACE = "Space"
    NATURE = "Nature"
    ART = "Art"
    PORTRAIT = "Portrait"
    LOCAL_STORAGE = "Local Storage"


class WallpaperPosition(str, Enum):
    FILL = "Fill"  # Scale proportionally, crop excess to cover screen (no distortion)
    FIT = "Fit"    # Scale proportionally, letterbox/pillarbox to fit whole image (no distortion)


class ColorPalette(str, Enum):
    ANY = "Any"
    BLUE = "Blue"              # Deep blues, cyans, teals, sky blues
    PURPLE = "Purple"          # Violets, indigos, lavenders, magentas
    GREEN = "Green"            # Emeralds, forest greens, sage, mint
    WARM = "Warm"              # Sunset orange, red, amber, gold
    MONOCHROME = "Monochrome"  # Dark moody blacks, charcoals, slates, grays
    CUSTOM = "Custom"          # User-specified hex color


class WallpaperMood(str, Enum):
    ANY = "Any"
    PEACEFUL = "Peaceful"      # Calm, serene, tranquil landscapes and soft ambient views
    DARK = "Dark"              # Deep night, shadowy tones, moody astrophotography, low-key
    CINEMATIC = "Cinematic"    # Epic vistas, dramatic atmospheric lighting, widescreen scale
    MINIMALIST = "Minimalist"  # Clean compositions, high negative space, uncluttered subjects
    VIBRANT = "Vibrant"        # Vivid colors, radiant golden hour, bold saturation


@dataclass
class HistoryRecord:
    """Historical entry for a displayed wallpaper with timestamp for anti-repetition cooldown."""
    image_id: str
    applied_at: str  # ISO 8601 UTC string (e.g. 2026-10-23T04:00:00Z)
    category: str = ""
    sha256: Optional[str] = None
    title: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "image_id": self.image_id,
            "applied_at": self.applied_at,
            "category": self.category,
            "sha256": self.sha256,
            "title": self.title,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HistoryRecord":
        return cls(
            image_id=str(data.get("image_id", "")),
            applied_at=str(data.get("applied_at", "")),
            category=str(data.get("category", "")),
            sha256=data.get("sha256"),
            title=data.get("title"),
        )


@dataclass
class ImageDimensions:
    width: int
    height: int

    @property
    def aspect_ratio(self) -> float:
        if self.height <= 0:
            return 0.0
        return self.width / self.height

    @property
    def is_landscape(self) -> bool:
        return self.aspect_ratio >= 1.25


@dataclass
class WallpaperCandidate:
    """Represents a potential wallpaper discovered from a provider before download."""
    id: str
    category: WallpaperCategory
    provider_name: str
    title: str
    download_url: str
    source_url: str
    creator: str = "Unknown"
    license_name: str = "Unknown"
    license_url: Optional[str] = None
    attribution_required: bool = False
    attribution_text: str = ""
    preview_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    mime_type: Optional[str] = None
    dominant_color_hex: Optional[str] = None
    mood: Optional[WallpaperMood] = None
    raw_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WallpaperMetadata:
    """Metadata recorded when a wallpaper is successfully applied."""
    image_id: str
    category: str
    provider: str
    source_url: str
    download_url: str
    local_path: str
    sha256: str
    title: str
    creator: str
    license: str
    license_url: Optional[str]
    attribution_required: bool
    attribution_text: str
    width: int
    height: int
    aspect_ratio: float
    mode: str  # "Fill" or "Fit"
    dominant_color_hex: Optional[str] = None
    mood: Optional[str] = None
    applied_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    @property
    def dimensions(self) -> Dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "aspect_ratio": round(self.aspect_ratio, 3),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "image_id": self.image_id,
            "category": self.category,
            "provider": self.provider,
            "source_url": self.source_url,
            "download_url": self.download_url,
            "local_path": self.local_path,
            "sha256": self.sha256,
            "title": self.title,
            "creator": self.creator,
            "license": self.license,
            "license_url": self.license_url,
            "attribution_required": self.attribution_required,
            "attribution_text": self.attribution_text,
            "dimensions": {
                "width": self.width,
                "height": self.height,
                "aspect_ratio": round(self.aspect_ratio, 3),
            },
            "applied_at": self.applied_at,
            "mode": self.mode,
            "dominant_color_hex": self.dominant_color_hex,
            "mood": self.mood,
        }
