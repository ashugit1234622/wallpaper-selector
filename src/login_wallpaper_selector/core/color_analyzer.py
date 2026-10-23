"""Color analysis, dominant hue extraction, and palette classification for wallpapers."""

from __future__ import annotations
import colorsys
from pathlib import Path
from typing import Tuple, List, Optional
from PIL import Image

from .models import ColorPalette


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Format RGB tuple as standard #RRGGBB hex string."""
    return f"#{r:02x}{g:02x}{b:02x}"


def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    """Parse #RRGGBB or RRGGBB hex string to RGB tuple."""
    clean = hex_str.strip().lstrip("#")
    if len(clean) == 3:
        clean = "".join(c * 2 for c in clean)
    if len(clean) != 6:
        return 0, 0, 0
    try:
        return int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16)
    except ValueError:
        return 0, 0, 0


def extract_dominant_color(img: Image.Image) -> Tuple[int, int, int]:
    """Extract the primary dominant RGB color of an image using fast adaptive quantization."""
    # Fast resize to speed up processing
    small = img.resize((64, 64), Image.Resampling.BILINEAR)
    if small.mode != "RGB":
        small = small.convert("RGB")

    # Quantize to 5 adaptive palette colors
    quantized = small.convert("P", palette=Image.Palette.ADAPTIVE, colors=5)
    palette = quantized.getpalette() or []
    color_counts = quantized.getcolors(maxcolors=256) or []

    if not color_counts or not palette:
        return 128, 128, 128

    # Sort colors by frequency descending
    color_counts.sort(key=lambda item: item[0], reverse=True)
    top_color_idx = color_counts[0][1]

    idx = top_color_idx * 3
    if idx + 2 < len(palette):
        return palette[idx], palette[idx + 1], palette[idx + 2]

    return 128, 128, 128


def extract_dominant_color_from_file(image_path: Path) -> Tuple[int, int, int]:
    """Open image file and extract dominant RGB color."""
    try:
        with Image.open(image_path) as img:
            return extract_dominant_color(img)
    except Exception:
        return 128, 128, 128


def classify_rgb_to_palette(rgb: Tuple[int, int, int]) -> ColorPalette:
    """Classify an RGB color into a high-level ColorPalette based on HSV properties."""
    r, g, b = rgb
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    h_deg = h * 360.0

    # Low saturation or extreme dark/light levels indicate monochrome / grayscale
    if v < 0.18:
        return ColorPalette.MONOCHROME
    if s < 0.16 and v < 0.88:
        return ColorPalette.MONOCHROME
    if s < 0.08:
        return ColorPalette.MONOCHROME

    # Hue classification
    if 65.0 <= h_deg < 165.0:
        return ColorPalette.GREEN
    elif 165.0 <= h_deg < 260.0:
        return ColorPalette.BLUE
    elif 260.0 <= h_deg < 330.0:
        return ColorPalette.PURPLE
    else:  # h_deg >= 330.0 or h_deg < 65.0 (Reds, Oranges, Ambers, Yellows)
        return ColorPalette.WARM


def compute_color_match_score(
    img_rgb: Tuple[int, int, int],
    target_palette: ColorPalette,
    custom_hex: Optional[str] = None,
) -> float:
    """Calculate matching score between image RGB color and target palette (0.0 to 1.0)."""
    if target_palette == ColorPalette.ANY:
        return 1.0

    if target_palette == ColorPalette.CUSTOM and custom_hex:
        target_rgb = hex_to_rgb(custom_hex)
        # 3D Euclidean distance normalized by max distance (~441.67)
        dist = (
            (img_rgb[0] - target_rgb[0]) ** 2
            + (img_rgb[1] - target_rgb[1]) ** 2
            + (img_rgb[2] - target_rgb[2]) ** 2
        ) ** 0.5
        return max(0.0, 1.0 - (dist / 441.67))

    detected = classify_rgb_to_palette(img_rgb)
    if detected == target_palette:
        return 1.0

    return 0.0


def get_wallhaven_color_code(palette: ColorPalette, custom_hex: Optional[str] = None) -> Optional[str]:
    """Map ColorPalette to Wallhaven API 6-character hex color parameter."""
    if palette == ColorPalette.ANY:
        return None
    elif palette == ColorPalette.BLUE:
        return "0066cc"
    elif palette == ColorPalette.PURPLE:
        return "793db8"
    elif palette == ColorPalette.GREEN:
        return "00cc7a"
    elif palette == ColorPalette.WARM:
        return "e64a19"
    elif palette == ColorPalette.MONOCHROME:
        return "000000"
    elif palette == ColorPalette.CUSTOM and custom_hex:
        clean = custom_hex.strip().lstrip("#")
        return clean if len(clean) == 6 else None
    return None


def get_palette_keyword(palette: ColorPalette) -> Optional[str]:
    """Return search keyword associated with palette for query augmentation."""
    if palette == ColorPalette.BLUE:
        return "blue"
    elif palette == ColorPalette.PURPLE:
        return "purple"
    elif palette == ColorPalette.GREEN:
        return "green"
    elif palette == ColorPalette.WARM:
        return "warm"
    elif palette == ColorPalette.MONOCHROME:
        return "monochrome"
    return None
