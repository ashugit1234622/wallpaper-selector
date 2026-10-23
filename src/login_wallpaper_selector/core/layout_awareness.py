"""Desktop Layout Awareness and Saliency-Guided Smart Cropping.

Analyzes in-memory desktop screenshots to detect icon and taskbar clutter,
calculates image saliency focal points, and aligns wallpaper crops so important
subjects are not occluded by interface elements.

PRIVACY GUARANTEE: Desktop screenshots remain strictly in-memory (RAM only)
and are never saved to disk, logged, or transmitted.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple, Optional
from PIL import Image, ImageFilter


@dataclass
class DesktopLayoutProfile:
    """Clutter density metrics and preferred visual zones on the desktop."""
    left_clutter: float       # 0.0 to 1.0 (icon columns density)
    right_clutter: float      # 0.0 to 1.0
    top_clutter: float        # 0.0 to 1.0
    bottom_clutter: float     # 0.0 to 1.0 (taskbar density)
    preferred_horizontal: str # "right", "left", or "center"
    preferred_vertical: str   # "top", "bottom", or "center"

    @classmethod
    def standard_windows_default(cls) -> "DesktopLayoutProfile":
        """Default heuristic for Windows: icons on left, taskbar at bottom."""
        return cls(
            left_clutter=0.65,
            right_clutter=0.10,
            top_clutter=0.15,
            bottom_clutter=0.75,
            preferred_horizontal="right",
            preferred_vertical="top",
        )


def analyze_desktop_layout(
    screenshot: Optional[Image.Image] = None,
) -> DesktopLayoutProfile:
    """Capture desktop in-memory and compute clutter distribution.
    
    If screenshot is not provided, captures current desktop via ImageGrab.
    Falls back safely to standard desktop defaults on errors.
    """
    img = screenshot
    if img is None:
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab()
        except Exception:
            return DesktopLayoutProfile.standard_windows_default()

    if img is None:
        return DesktopLayoutProfile.standard_windows_default()

    try:
        # Downscale to low-resolution thumbnail in RAM for high-speed analysis
        thumb = img.resize((128, 72), Image.Resampling.BILINEAR)
        gray = thumb.convert("L")
        w, h = gray.size

        # Detect high-frequency edges (icons and interface boundaries)
        edges = gray.filter(ImageFilter.FIND_EDGES)
        pixels = list(edges.get_flattened_data()) if hasattr(edges, "get_flattened_data") else list(edges.getdata())

        left_edges = []
        right_edges = []
        top_edges = []
        bottom_edges = []

        for y in range(h):
            for x in range(w):
                val = pixels[y * w + x]
                # Left 30% vs Right 30%
                if x < int(w * 0.30):
                    left_edges.append(val)
                elif x > int(w * 0.70):
                    right_edges.append(val)

                # Top 30% vs Bottom 25% (taskbar region)
                if y < int(h * 0.30):
                    top_edges.append(val)
                elif y > int(h * 0.75):
                    bottom_edges.append(val)

        def _mean_density(edge_vals: list[int]) -> float:
            if not edge_vals:
                return 0.0
            return min(1.0, (sum(edge_vals) / len(edge_vals)) / 64.0)

        left_clutter = _mean_density(left_edges)
        right_clutter = _mean_density(right_edges)
        top_clutter = _mean_density(top_edges)
        bottom_clutter = _mean_density(bottom_edges)

        # Determine optimal focal zone (opposite the heaviest clutter)
        if left_clutter > right_clutter + 0.10:
            pref_h = "right"
        elif right_clutter > left_clutter + 0.10:
            pref_h = "left"
        else:
            pref_h = "center"

        if bottom_clutter > top_clutter + 0.10:
            pref_v = "top"
        elif top_clutter > bottom_clutter + 0.10:
            pref_v = "center"
        else:
            pref_v = "center"

        return DesktopLayoutProfile(
            left_clutter=round(left_clutter, 3),
            right_clutter=round(right_clutter, 3),
            top_clutter=round(top_clutter, 3),
            bottom_clutter=round(bottom_clutter, 3),
            preferred_horizontal=pref_h,
            preferred_vertical=pref_v,
        )

    except Exception:
        return DesktopLayoutProfile.standard_windows_default()


def compute_image_saliency_focal_point(img: Image.Image) -> Tuple[float, float]:
    """Calculate the normalized (fx, fy) center of visual interest in an image (0.0 to 1.0)."""
    try:
        small = img.resize((128, 72), Image.Resampling.BILINEAR)
        gray = small.convert("L")
        w, h = gray.size

        # High-pass edge filter to find detail centers
        edges = gray.filter(ImageFilter.FIND_EDGES)
        edge_data = list(edges.get_flattened_data()) if hasattr(edges, "get_flattened_data") else list(edges.getdata())

        total_weight = 0.0
        weighted_x = 0.0
        weighted_y = 0.0

        for y in range(h):
            for x in range(w):
                weight = float(edge_data[y * w + x])
                if weight > 20:  # Noise threshold
                    weighted_x += x * weight
                    weighted_y += y * weight
                    total_weight += weight

        if total_weight > 0:
            fx = (weighted_x / total_weight) / w
            fy = (weighted_y / total_weight) / h
            return max(0.0, min(1.0, fx)), max(0.0, min(1.0, fy))

        return 0.5, 0.5
    except Exception:
        return 0.5, 0.5


def calculate_smart_crop_offset(
    scaled_w: int,
    scaled_h: int,
    target_w: int,
    target_h: int,
    focal_point: Tuple[float, float],
    layout_profile: DesktopLayoutProfile,
) -> Tuple[int, int]:
    """Calculate left and top crop offsets to align focal points with clear screen zones."""
    excess_w = max(0, scaled_w - target_w)
    excess_h = max(0, scaled_h - target_h)

    # Standard center crop fallback
    default_left = excess_w // 2
    default_top = excess_h // 2

    fx, fy = focal_point

    # Horizontal alignment
    if excess_w > 0:
        focal_x_px = fx * scaled_w
        if layout_profile.preferred_horizontal == "right":
            # Target focal point at 65% of screen width (away from left icons)
            desired_screen_x = 0.65 * target_w
            smart_left = int(focal_x_px - desired_screen_x)
        elif layout_profile.preferred_horizontal == "left":
            # Target focal point at 35% of screen width (away from right icons/widgets)
            desired_screen_x = 0.35 * target_w
            smart_left = int(focal_x_px - desired_screen_x)
        else:
            desired_screen_x = 0.50 * target_w
            smart_left = int(focal_x_px - desired_screen_x)

        left = max(0, min(excess_w, smart_left))
    else:
        left = 0

    # Vertical alignment
    if excess_h > 0:
        focal_y_px = fy * scaled_h
        if layout_profile.preferred_vertical == "top":
            # Target focal point at 40% of screen height (away from bottom taskbar)
            desired_screen_y = 0.40 * target_h
            smart_top = int(focal_y_px - desired_screen_y)
        else:
            desired_screen_y = 0.50 * target_h
            smart_top = int(focal_y_px - desired_screen_y)

        top = max(0, min(excess_h, smart_top))
    else:
        top = 0

    return left, top
