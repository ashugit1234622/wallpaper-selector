"""Monitor resolution detection and display-optimized wallpaper rendering."""

from __future__ import annotations
import sys
from pathlib import Path
from typing import Tuple
from PIL import Image

from .models import WallpaperPosition


def get_native_screen_resolution() -> Tuple[int, int]:
    """Detect the primary monitor's true physical native resolution in pixels.
    
    Ensures process DPI awareness is active on Windows to avoid virtualized scaling.
    """
    if sys.platform == "win32":
        try:
            import ctypes
            # Enable per-monitor DPI awareness (PROCESS_PER_MONITOR_DPI_AWARE = 2)
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception:
                try:
                    ctypes.windll.user32.SetProcessDPIAware()
                except Exception:
                    pass

            user32 = ctypes.windll.user32
            width = user32.GetSystemMetrics(0)   # SM_CXSCREEN
            height = user32.GetSystemMetrics(1)  # SM_CYSCREEN
            if width > 0 and height > 0:
                return width, height
        except Exception:
            pass

    # Cross-platform fallback using Tkinter
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        w = root.winfo_screenwidth()
        h = root.winfo_screenheight()
        root.destroy()
        if w > 0 and h > 0:
            return w, h
    except Exception:
        pass

    # Standard 1080p fallback
    return 1920, 1080


def get_screen_aspect_ratio() -> float:
    w, h = get_native_screen_resolution()
    return round(w / h, 3) if h > 0 else 1.778


def render_wallpaper_for_screen(
    source_path: Path,
    output_path: Path,
    target_width: int,
    target_height: int,
    mode: str = WallpaperPosition.FILL.value,
    layout_aware: bool = True,
) -> bool:
    """Render an image to match the monitor's exact native resolution 1:1.
    
    Fill: Proportional resize and layout-aware crop to exact target_width x target_height.
    Fit: Proportional resize to fit inside target_width x target_height, centered on a clean background canvas.
    """
    try:
        with Image.open(source_path) as img:
            # Convert palette/grayscale/RGBA to RGB
            if img.mode != "RGB":
                img = img.convert("RGB")

            src_w, src_h = img.size
            if src_w <= 0 or src_h <= 0:
                return False

            target_ratio = target_width / target_height
            src_ratio = src_w / src_h

            if mode.lower() == WallpaperPosition.FILL.value.lower():
                # Scale proportionally so it covers the entire target resolution, then crop excess
                if src_ratio > target_ratio:
                    # Source is wider than target: fit height, crop width
                    new_h = target_height
                    new_w = max(target_width, int(src_w * (target_height / src_h)))
                else:
                    # Source is taller than target: fit width, crop height
                    new_w = target_width
                    new_h = max(target_height, int(src_h * (target_width / src_w)))

                resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

                if layout_aware and (new_w > target_width or new_h > target_height):
                    try:
                        from .layout_awareness import (
                            analyze_desktop_layout,
                            compute_image_saliency_focal_point,
                            calculate_smart_crop_offset,
                        )
                        focal_point = compute_image_saliency_focal_point(img)
                        profile = analyze_desktop_layout()
                        left, top = calculate_smart_crop_offset(
                            new_w, new_h, target_width, target_height, focal_point, profile
                        )
                    except Exception:
                        left = (new_w - target_width) // 2
                        top = (new_h - target_height) // 2
                else:
                    left = (new_w - target_width) // 2
                    top = (new_h - target_height) // 2

                final_img = resized.crop((left, top, left + target_width, top + target_height))

            else:
                # FIT mode: Scale proportionally to fit inside target, letterbox with solid black/background
                if src_ratio > target_ratio:
                    # Source is wider: fit width, letterbox top/bottom
                    new_w = target_width
                    new_h = int(src_h * (target_width / src_w))
                else:
                    # Source is taller: fit height, pillarbox left/right
                    new_h = target_height
                    new_w = int(src_w * (target_height / src_h))

                resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                final_img = Image.new("RGB", (target_width, target_height), color=(15, 15, 20))
                paste_x = (target_width - new_w) // 2
                paste_y = (target_height - new_h) // 2
                final_img.paste(resized, (paste_x, paste_y))

            # Save in high-quality JPEG
            output_path.parent.mkdir(parents=True, exist_ok=True)
            final_img.save(output_path, format="JPEG", quality=95, optimize=True)
            return True

    except Exception:
        return False
