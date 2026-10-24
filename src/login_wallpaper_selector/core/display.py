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


def generate_desktop_preview_image(
    source_path: Path,
    mode: str = WallpaperPosition.FILL.value,
    max_preview_width: int = 540,
    max_preview_height: int = 160,
    layout_aware: bool = True,
    draw_mockup_frame: bool = True,
) -> Optional[Image.Image]:
    """Render a scaled desktop screen-fit and cropping preview for an image.
    
    Matches the primary monitor's true aspect ratio, accurately rendering
    Fill (smart-cropped) vs Fit (letterbox/pillarbox with dark canvas).
    Includes a subtle Windows desktop bezel and translucent mini taskbar mockup.
    """
    if not source_path.exists():
        return None

    try:
        screen_w, screen_h = get_native_screen_resolution()
        screen_ratio = screen_w / screen_h if screen_h > 0 else 1.778

        # Calculate preview canvas dimensions matching true screen aspect ratio
        if screen_ratio >= (max_preview_width / max_preview_height):
            canvas_w = max_preview_width
            canvas_h = max(60, int(max_preview_width / screen_ratio))
        else:
            canvas_h = max_preview_height
            canvas_w = max(100, int(max_preview_height * screen_ratio))

        with Image.open(source_path) as img:
            try:
                img.draft("RGB", (canvas_w * 2, canvas_h * 2))
            except Exception:
                pass
            if img.mode != "RGB":
                img = img.convert("RGB")

            src_w, src_h = img.size
            if src_w <= 0 or src_h <= 0:
                return None

            src_ratio = src_w / src_h

            if mode.lower() == WallpaperPosition.FILL.value.lower():
                # Proportional scale to fill preview screen canvas
                if src_ratio > screen_ratio:
                    new_h = canvas_h
                    new_w = max(canvas_w, int(src_w * (canvas_h / src_h)))
                else:
                    new_w = canvas_w
                    new_h = max(canvas_h, int(src_h * (canvas_w / src_w)))

                resized = img.resize((new_w, new_h), Image.Resampling.BILINEAR)

                # Layout aware or center crop to canvas_w x canvas_h
                if layout_aware and (new_w > canvas_w or new_h > canvas_h):
                    try:
                        from .layout_awareness import (
                            analyze_desktop_layout,
                            compute_image_saliency_focal_point,
                            calculate_smart_crop_offset,
                        )
                        focal = compute_image_saliency_focal_point(img)
                        profile = analyze_desktop_layout()
                        left, top = calculate_smart_crop_offset(
                            new_w, new_h, canvas_w, canvas_h, focal, profile
                        )
                    except Exception:
                        left = (new_w - canvas_w) // 2
                        top = (new_h - canvas_h) // 2
                else:
                    left = (new_w - canvas_w) // 2
                    top = (new_h - canvas_h) // 2

                preview_img = resized.crop((left, top, left + canvas_w, top + canvas_h))

            else:
                # FIT mode: Proportional fit inside canvas with dark letterbox/pillarbox
                if src_ratio > screen_ratio:
                    new_w = canvas_w
                    new_h = max(1, int(src_h * (canvas_w / src_w)))
                else:
                    new_h = canvas_h
                    new_w = max(1, int(src_w * (canvas_h / src_h)))

                resized = img.resize((new_w, new_h), Image.Resampling.BILINEAR)
                preview_img = Image.new("RGB", (canvas_w, canvas_h), color=(15, 15, 20))
                paste_x = (canvas_w - new_w) // 2
                paste_y = (canvas_h - new_h) // 2
                preview_img.paste(resized, (paste_x, paste_y))

            # Overlay desktop mockup frame & taskbar if requested
            if draw_mockup_frame:
                from PIL import ImageDraw
                draw = ImageDraw.Draw(preview_img, "RGBA")

                # 1. Subtle desktop frame bezel (outer edge)
                draw.rectangle([(0, 0), (canvas_w - 1, canvas_h - 1)], outline=(60, 70, 90, 180), width=1)

                # 2. Translucent Windows taskbar mockup at bottom
                tb_height = max(10, int(canvas_h * 0.08))
                tb_y0 = canvas_h - tb_height
                draw.rectangle([(0, tb_y0), (canvas_w, canvas_h)], fill=(15, 20, 30, 200))
                draw.line([(0, tb_y0), (canvas_w, tb_y0)], fill=(80, 100, 130, 160), width=1)

                # Mini Start accent icon in taskbar
                icon_size = max(4, tb_height - 4)
                icon_y = tb_y0 + (tb_height - icon_size) // 2
                draw.rectangle([(8, icon_y), (8 + icon_size, icon_y + icon_size)], fill=(56, 189, 248, 220))

                # Mode tag watermark in top-right
                mode_tag = f"Desktop Preview ({mode})"
                draw.rectangle([(canvas_w - 135, 4), (canvas_w - 4, 18)], fill=(0, 0, 0, 140))
                draw.text((canvas_w - 130, 5), mode_tag, fill=(220, 220, 230, 220))

            return preview_img

    except Exception:
        return None
