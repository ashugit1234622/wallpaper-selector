"""Color analysis, dominant hue extraction, and palette classification for wallpapers."""

from __future__ import annotations
import colorsys
from pathlib import Path
from typing import Tuple, List, Optional, NamedTuple
from PIL import Image
import numpy as np

from .models import ColorPalette, WallpaperMood


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


# ── Post-download validation ──────────────────────────────────────────────────

class ImageStats(NamedTuple):
    """Aggregate perceptual stats for a downloaded image."""
    mean_brightness: float   # [0, 1]  V channel in HSV, full-image mean
    mean_saturation: float   # [0, 1]  S channel in HSV, full-image mean
    dark_pixel_ratio: float  # fraction of pixels with V < 0.30
    dominant_palette: ColorPalette


def compute_image_stats(img: Image.Image) -> ImageStats:
    """Compute perceptual brightness and saturation statistics for an image."""
    small = img.resize((128, 72), Image.Resampling.BILINEAR)
    if small.mode != "RGB":
        small = small.convert("RGB")

    try:
        import numpy as np
        pixels = np.array(small, dtype=np.float32) / 255.0
        r, g, b = pixels[..., 0], pixels[..., 1], pixels[..., 2]
        v = np.maximum(np.maximum(r, g), b)
        s_denom = np.where(v == 0, 1.0, v)
        s = (v - np.minimum(np.minimum(r, g), b)) / s_denom
        s = np.where(v == 0, 0.0, s)
        mean_brightness = float(np.mean(v))
        mean_saturation = float(np.mean(s))
        dark_pixel_ratio = float(np.mean(v < 0.30))
    except ImportError:
        # Fallback without numpy: iterate pixels
        pixels_list = list(small.getdata())
        total = len(pixels_list)
        v_sum = s_sum = dark_count = 0.0
        for pr, pg, pb in pixels_list:
            rv, gv, bv = pr / 255.0, pg / 255.0, pb / 255.0
            vv = max(rv, gv, bv)
            sv = (vv - min(rv, gv, bv)) / vv if vv > 0 else 0.0
            v_sum += vv
            s_sum += sv
            if vv < 0.30:
                dark_count += 1
        mean_brightness = v_sum / total if total else 0.5
        mean_saturation = s_sum / total if total else 0.5
        dark_pixel_ratio = dark_count / total if total else 0.0

    dom_rgb = extract_dominant_color(img)
    dominant_palette = classify_rgb_to_palette(dom_rgb)

    return ImageStats(
        mean_brightness=mean_brightness,
        mean_saturation=mean_saturation,
        dark_pixel_ratio=dark_pixel_ratio,
        dominant_palette=dominant_palette,
    )


def compute_image_stats_from_file(image_path: Path) -> Optional["ImageStats"]:
    """Load an image file and return its perceptual stats, or None on error."""
    try:
        with Image.open(image_path) as img:
            return compute_image_stats(img)
    except Exception:
        return None


def validate_image_matches_selection(
    stats: "ImageStats",
    target_palette: Optional[ColorPalette],
    target_mood: Optional[WallpaperMood],
    attempt: int = 1,
    allow_soft: bool = False,
) -> Tuple[bool, str]:
    """Return (passes, reason) — False means the image should be rejected.

    Adaptive thresholds applied after download:
    - Attempts 1–2 (Strict):
        * Dark mood:       mean_brightness ≤ 0.46  AND dark_pixel_ratio ≥ 0.32
        * Vibrant mood:    mean_saturation ≥ 0.28  AND mean_brightness ≥ 0.28
        * Peaceful mood:   mean_brightness ≥ 0.20
        * Monochrome:      mean_saturation ≤ 0.28  OR mean_brightness ≤ 0.22
    - Attempts 3–5 or allow_soft (Soft Adaptive):
        * Dark mood:       mean_brightness ≤ 0.58  AND dark_pixel_ratio ≥ 0.20
        * Vibrant mood:    mean_saturation ≥ 0.22  AND mean_brightness ≥ 0.22
        * Peaceful mood:   mean_brightness ≥ 0.15
        * Monochrome:      mean_saturation ≤ 0.38
    - Other palettes: dominant_palette matches target_palette or monochrome.
    """
    is_soft = allow_soft or attempt >= 3

    # ── Mood gate ──────────────────────────────────────────────────────────
    if target_mood and target_mood != WallpaperMood.ANY:
        if target_mood == WallpaperMood.DARK:
            max_b = 0.58 if is_soft else 0.46
            min_dp = 0.20 if is_soft else 0.32
            if stats.mean_brightness > max_b:
                return False, f"Dark mood: brightness {stats.mean_brightness:.2f} > {max_b:.2f}"
            if stats.dark_pixel_ratio < min_dp:
                return False, f"Dark mood: dark_pixel_ratio {stats.dark_pixel_ratio:.2f} < {min_dp:.2f}"

        elif target_mood == WallpaperMood.VIBRANT:
            min_s = 0.22 if is_soft else 0.28
            min_b = 0.22 if is_soft else 0.28
            if stats.mean_saturation < min_s:
                return False, f"Vibrant mood: saturation {stats.mean_saturation:.2f} < {min_s:.2f}"
            if stats.mean_brightness < min_b:
                return False, f"Vibrant mood: brightness {stats.mean_brightness:.2f} < {min_b:.2f}"

        elif target_mood == WallpaperMood.PEACEFUL:
            min_b = 0.15 if is_soft else 0.20
            if stats.mean_brightness < min_b:
                return False, f"Peaceful mood: brightness {stats.mean_brightness:.2f} < {min_b:.2f}"

    # ── Palette gate ───────────────────────────────────────────────────────
    if target_palette and target_palette not in (ColorPalette.ANY, ColorPalette.CUSTOM):
        if target_palette == ColorPalette.MONOCHROME:
            max_s = 0.38 if is_soft else 0.28
            if stats.mean_saturation > max_s and stats.mean_brightness > 0.24:
                return False, f"Monochrome: sat={stats.mean_saturation:.2f}>{max_s:.2f} AND brightness={stats.mean_brightness:.2f}>0.24"
        else:
            if stats.dominant_palette != target_palette:
                if not (is_soft and stats.dominant_palette == ColorPalette.MONOCHROME):
                    return False, f"Palette mismatch: image={stats.dominant_palette.value}, expected={target_palette.value}"

    return True, "ok"


def compute_image_compatibility_score(
    stats: "ImageStats",
    target_palette: Optional[ColorPalette],
    target_mood: Optional[WallpaperMood],
) -> float:
    """Calculate distance penalty score [0.0..infinity) between candidate stats and target criteria.

    Lower score is better; 0.0 is an ideal match.
    Used on final fallback tier to guarantee the best candidate is chosen rather than failing.
    """
    penalty = 0.0

    if target_mood and target_mood != WallpaperMood.ANY:
        if target_mood == WallpaperMood.DARK:
            penalty += max(0.0, stats.mean_brightness - 0.35) * 2.5
            penalty += max(0.0, 0.40 - stats.dark_pixel_ratio) * 1.5
        elif target_mood == WallpaperMood.VIBRANT:
            penalty += max(0.0, 0.45 - stats.mean_saturation) * 2.0
            penalty += max(0.0, 0.40 - stats.mean_brightness) * 1.0
        elif target_mood == WallpaperMood.PEACEFUL:
            penalty += max(0.0, 0.25 - stats.mean_brightness) * 1.5

    if target_palette and target_palette not in (ColorPalette.ANY, ColorPalette.CUSTOM):
        if target_palette == ColorPalette.MONOCHROME:
            penalty += stats.mean_saturation * 3.0
        else:
            if stats.dominant_palette != target_palette:
                penalty += 1.5

    return penalty
