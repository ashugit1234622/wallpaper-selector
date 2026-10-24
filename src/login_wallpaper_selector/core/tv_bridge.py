"""Bridge module connecting Login Wallpaper Selector with CleanMyTV to set wallpapers on Android TV."""

from __future__ import annotations
import json
import logging
import os
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Callable, Optional, Tuple, Union
from PIL import Image

logger = logging.getLogger(__name__)

DEFAULT_CLEANMYTV_DIR = Path(r"C:\Users\Ashirwad\Desktop\projects\clean my tv")
DEFAULT_TV_HOST = "192.168.1.37"
DEFAULT_TV_PORT = 5555


def get_cleanmytv_dir(configured_path: Optional[str] = None) -> Path:
    """Resolve the CleanMyTV directory."""
    if configured_path:
        p = Path(configured_path)
        if p.exists():
            return p
    if DEFAULT_CLEANMYTV_DIR.exists():
        return DEFAULT_CLEANMYTV_DIR
    
    # Try sibling search
    try:
        candidate = Path(__file__).resolve().parents[4] / "clean my tv"
        if candidate.exists():
            return candidate
    except Exception:
        pass

    return DEFAULT_CLEANMYTV_DIR


def ensure_bridge_script(cleanmytv_dir: Path) -> Path:
    """Ensure scripts/apply-wallpaper.ts exists in CleanMyTV, copying from bundled bridge if needed."""
    target_script = cleanmytv_dir / "scripts" / "apply-wallpaper.ts"
    if target_script.exists():
        return target_script

    bundled_source = Path(__file__).resolve().parent.parent / "bridge" / "apply_wallpaper.ts"
    if bundled_source.exists():
        target_script.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bundled_source, target_script)
        logger.info(f"Copied bundled bridge script to {target_script}")

    return target_script


def resolve_tv_host(configured_host: Optional[str] = None) -> str:
    """Resolve the TV host IP from config, CleanMyTV settings, or fallback."""
    if configured_host and configured_host.strip():
        return configured_host.strip()

    appdata = os.environ.get("APPDATA")
    if appdata:
        settings_path = Path(appdata) / "cleanmytv" / "settings.json"
        if settings_path.exists():
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("lastHost"):
                        return data["lastHost"].strip()
            except Exception as e:
                logger.debug(f"Failed to read cleanmytv settings: {e}")

    return DEFAULT_TV_HOST


def prepare_tv_wallpaper(source_image: Path, crop_16_9: bool = False) -> Path:
    """Prepare an optimized JPEG image for the Android TV launcher.
    
    If crop_16_9 is True, center-crops non-16:9 images to 16:9 aspect ratio.
    Always converts to RGB JPEG to ensure compatibility with Android TV adbd/launcher.
    """
    source_image = Path(source_image)
    if not source_image.exists():
        raise FileNotFoundError(f"Source image not found: {source_image}")

    cache_dir = source_image.parent / ".tv_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    out_path = cache_dir / f"tv_{source_image.stem}.jpg"

    with Image.open(source_image) as img:
        img_rgb = img.convert("RGB")
        w, h = img_rgb.size

        if crop_16_9:
            target_ratio = 16.0 / 9.0
            current_ratio = w / float(h)
            if abs(current_ratio - target_ratio) > 0.05:
                if current_ratio > target_ratio:
                    # Wider than 16:9 -> crop width
                    new_w = int(h * target_ratio)
                    offset_x = (w - new_w) // 2
                    img_rgb = img_rgb.crop((offset_x, 0, offset_x + new_w, h))
                else:
                    # Taller than 16:9 -> crop height
                    new_h = int(w / target_ratio)
                    offset_y = (h - new_h) // 2
                    img_rgb = img_rgb.crop((0, offset_y, w, offset_y + new_h))

        # Always ensure exact native 4K UHD (3840x2160) for 4K TV displays
        if img_rgb.size != (3840, 2160):
            img_rgb = img_rgb.resize((3840, 2160), Image.Resampling.LANCZOS)

        # Use 4:4:4 chroma subsampling (subsampling=0) and high quality (96) for crisp 4K TV presentation
        img_rgb.save(out_path, "JPEG", quality=96, optimize=True, subsampling=0)

    return out_path


class TvBridge:
    """Client for executing wallpaper pushes and connection checks to Android TV via CleanMyTV."""

    def __init__(self, cleanmytv_dir: Optional[Union[str, Path]] = None, host: Optional[str] = None):
        self.cleanmytv_dir = get_cleanmytv_dir(str(cleanmytv_dir) if cleanmytv_dir else None)
        self.host = resolve_tv_host(host)

    def test_connection(self, host: Optional[str] = None) -> Tuple[bool, str]:
        """Test ADB connection to the Android TV."""
        target_host = host.strip() if host and host.strip() else self.host
        ensure_bridge_script(self.cleanmytv_dir)

        cmd = [
            "npx",
            "tsx",
            "scripts/apply-wallpaper.ts",
            "--test",
            "--host",
            target_host,
        ]

        try:
            res = subprocess.run(
                cmd,
                cwd=str(self.cleanmytv_dir),
                capture_output=True,
                text=True,
                shell=True,
                timeout=20,
            )

            last_json = None
            for line in res.stdout.splitlines():
                line = line.strip()
                if line.startswith("{") and line.endswith("}"):
                    try:
                        last_json = json.loads(line)
                    except Exception:
                        pass

            if last_json and last_json.get("status") == "ok":
                model = last_json.get("model", "Android TV")
                device = last_json.get("device", "")
                return True, f"Connected to {model} ({device})" if device else f"Connected to {model}"

            error_msg = (
                last_json.get("message")
                if last_json and last_json.get("message")
                else res.stderr.strip() or res.stdout.strip() or "Connection failed"
            )
            return False, error_msg

        except subprocess.TimeoutExpired:
            return False, f"Connection to {target_host} timed out (15s)."
        except Exception as e:
            return False, f"Failed to run connection test: {e}"

    def apply_wallpaper(
        self,
        image_path: Union[str, Path],
        host: Optional[str] = None,
        crop_16_9: bool = False,
        on_progress: Optional[Callable[[float, str], None]] = None,
    ) -> Tuple[bool, str]:
        """Apply a wallpaper image to the Android TV launcher."""
        target_host = host.strip() if host and host.strip() else self.host
        image_path = Path(image_path)

        if not image_path.exists():
            return False, f"Wallpaper file not found: {image_path}"

        if on_progress:
            on_progress(0.05, "Optimizing image for TV display...")

        try:
            tv_image = prepare_tv_wallpaper(image_path, crop_16_9=crop_16_9)
        except Exception as e:
            logger.warning(f"Could not preprocess image ({e}), sending original")
            tv_image = image_path

        ensure_bridge_script(self.cleanmytv_dir)

        cmd = [
            "npx",
            "tsx",
            "scripts/apply-wallpaper.ts",
            "--image",
            str(tv_image.resolve()),
            "--host",
            target_host,
        ]

        if on_progress:
            on_progress(0.1, f"Connecting to TV at {target_host}...")

        try:
            process = subprocess.Popen(
                cmd,
                cwd=str(self.cleanmytv_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=True,
                bufsize=1,
            )

            last_json = None
            if process.stdout:
                for line in iter(process.stdout.readline, ""):
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("{") and line.endswith("}"):
                        try:
                            data = json.loads(line)
                            last_json = data
                            status = data.get("status")
                            msg = data.get("message", "")
                            pct = data.get("progress", 0.0)

                            if on_progress:
                                on_progress(float(pct), msg)
                        except Exception:
                            pass

            process.wait(timeout=60)
            stderr = process.stderr.read() if process.stderr else ""

            if process.returncode == 0 and last_json and last_json.get("status") == "ok":
                return True, last_json.get("message", "TV Wallpaper updated successfully!")

            err_msg = (
                last_json.get("message")
                if last_json and last_json.get("message")
                else stderr.strip() or "Failed to apply wallpaper to TV"
            )
            return False, err_msg

        except subprocess.TimeoutExpired:
            return False, f"Transfer to TV at {target_host} timed out."
        except Exception as e:
            return False, f"Bridge execution error: {e}"
