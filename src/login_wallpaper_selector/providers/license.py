"""Licensing validator and attribution formatter."""

from __future__ import annotations
import re
from typing import Tuple, Optional


class LicenseValidator:
    """Validates open content licenses and generates standardized attribution strings."""

    ALLOWED_LICENSE_PATTERNS = [
        r"public domain",
        r"cc0",
        r"cc-0",
        r"cc[\s_-]?by",
        r"cc[\s_-]?by[\s_-]?sa",
        r"us government work",
        r"nasa public domain",
        r"gnu free documentation license",
        r"gfdl",
    ]

    DISALLOWED_LICENSE_PATTERNS = [
        r"all rights reserved",
        r"fair use",
        r"non-commercial",
        r"noncommercial",
        r"-nc",
        r"copyrighted",
        r"unknown",
    ]

    @classmethod
    def clean_text(cls, text: Optional[str]) -> str:
        """Strip HTML tags, unwanted entities, and whitespace."""
        if not text:
            return ""
        # Remove HTML tags
        clean = re.sub(r"<[^>]+>", "", text)
        clean = re.sub(r"&nbsp;", " ", clean)
        clean = re.sub(r"&amp;", "&", clean)
        clean = re.sub(r"&quot;", '"', clean)
        clean = re.sub(r"&#39;", "'", clean)
        return clean.strip()

    @classmethod
    def is_valid_license(cls, license_name: str) -> bool:
        """Determine whether the license name represents a recognized, open-use license."""
        if not license_name or not license_name.strip():
            return False

        lower = license_name.lower().strip()

        # Reject explicitly disallowed terms
        for pattern in cls.DISALLOWED_LICENSE_PATTERNS:
            if re.search(pattern, lower):
                return False

        # Match allowed patterns
        for pattern in cls.ALLOWED_LICENSE_PATTERNS:
            if re.search(pattern, lower):
                return True

        return False

    @classmethod
    def format_attribution(
        cls,
        title: str,
        creator: str,
        license_name: str,
        source_url: str,
        license_url: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Generate attribution requirement flag and standardized attribution string."""
        creator_clean = cls.clean_text(creator) or "Unknown Creator"
        title_clean = cls.clean_text(title) or "Wallpaper"
        lic_clean = cls.clean_text(license_name) or "Open License"

        lower_lic = lic_clean.lower()
        requires_attribution = not (
            "public domain" in lower_lic or "cc0" in lower_lic or "us government" in lower_lic
        )

        parts = [f'"{title_clean}" by {creator_clean}']
        parts.append(f"Licensed under {lic_clean}")
        if license_url:
            parts.append(f"({license_url})")
        parts.append(f"Source: {source_url}")

        attribution_string = " | ".join(parts)
        return requires_attribution, attribution_string
