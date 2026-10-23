"""System tray integration for background execution when Auto-Rotate is active."""

from __future__ import annotations
import threading
from pathlib import Path
from typing import Optional, Callable
from PIL import Image, ImageDraw

try:
    import pystray
    HAS_PYSTRAY = True
except ImportError:
    pystray = None
    HAS_PYSTRAY = False


def create_fallback_tray_icon_image(size: int = 64) -> Image.Image:
    """Create a sleek fallback icon image if icon.ico is missing or cannot be loaded."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    # Draw blue rounded circle
    draw.ellipse([4, 4, size - 4, size - 4], fill="#2563eb", outline="#1d4ed8", width=2)
    # Draw simple mountain / sun shapes
    draw.polygon([(16, size - 16), (size // 2, 22), (size - 16, size - 16)], fill="#ffffff")
    draw.ellipse([size - 24, 14, size - 14, 24], fill="#f59e0b")
    return image


class SystemTrayManager:
    """Manages the Windows System Tray icon, menu actions, and background state."""

    def __init__(
        self,
        on_show: Callable[[], None],
        on_rotate_now: Optional[Callable[[], None]] = None,
        on_quit: Optional[Callable[[], None]] = None,
        app_name: str = "Desktop Utility Suite",
    ):
        self.on_show = on_show
        self.on_rotate_now = on_rotate_now
        self.on_quit = on_quit
        self.app_name = app_name
        self._icon: Optional[Any] = None
        self._thread: Optional[threading.Thread] = None
        self._is_running = False

    @classmethod
    def is_available(cls) -> bool:
        """Check if system tray capability (pystray) is installed and available."""
        return HAS_PYSTRAY

    def _get_icon_image(self) -> Image.Image:
        """Load icon image from assets or create fallback."""
        icon_path = Path(__file__).resolve().parents[3] / "assets" / "icon.ico"
        if icon_path.exists():
            try:
                img = Image.open(str(icon_path))
                img.load()
                return img
            except Exception:
                pass
        return create_fallback_tray_icon_image()

    def start(self) -> bool:
        """Start system tray icon in background daemon thread."""
        if not HAS_PYSTRAY:
            return False

        if self._is_running and self._icon is not None:
            return True

        try:
            image = self._get_icon_image()
            menu_items = [
                pystray.MenuItem("Open Desktop Utility Suite", self._handle_show, default=True),
            ]

            if self.on_rotate_now is not None:
                menu_items.append(pystray.MenuItem("🔄 Rotate Wallpaper Now", self._handle_rotate_now))

            menu_items.append(pystray.Menu.SEPARATOR)

            if self.on_quit is not None:
                menu_items.append(pystray.MenuItem("❌ Quit Application", self._handle_quit))

            self._icon = pystray.Icon(
                name="DesktopUtilitySuite",
                icon=image,
                title=f"{self.app_name} (Auto-Rotate Active)",
                menu=pystray.Menu(*menu_items),
            )

            self._is_running = True
            self._thread = threading.Thread(target=self._icon.run, daemon=True)
            self._thread.start()
            return True
        except Exception as e:
            self._is_running = False
            self._icon = None
            return False

    def stop(self) -> None:
        """Stop and remove system tray icon."""
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._icon = None
        self._is_running = False

    def notify(self, message: str, title: Optional[str] = None) -> None:
        """Display an OS notification balloon if system tray is active."""
        if self._icon is not None and self._is_running:
            try:
                self._icon.notify(message, title or self.app_name)
            except Exception:
                pass

    def _handle_show(self, icon=None, item=None) -> None:
        if self.on_show:
            self.on_show()

    def _handle_rotate_now(self, icon=None, item=None) -> None:
        if self.on_rotate_now:
            self.on_rotate_now()

    def _handle_quit(self, icon=None, item=None) -> None:
        self.stop()
        if self.on_quit:
            self.on_quit()
