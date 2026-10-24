"""Desktop Utility Suite application shell and navigation framework."""

from __future__ import annotations
import sys
import threading
from pathlib import Path
from typing import Optional, Dict

try:
    import customtkinter as ctk
    HAS_CUSTOMTKINTER = True
except ImportError:
    import tkinter as ctk
    HAS_CUSTOMTKINTER = False

import tkinter as tk
from tkinter import messagebox

from .. import __version__
from ..core.config import AppConfig
from ..core.updater import check_for_updates, UpdateCheckResult
from .dialog import WallpaperSelectorDialog
from .update_dialog import UpdateModalDialog
from ..tools.download_organizer.ui import DownloadOrganizerView

# ── Windows 11 Fluent Design tokens ──────────────────────────────────────────
_W11 = {
    "surface_0":  "#202020",   # App background (Mica-like)
    "surface_1":  "#2b2b2b",   # Card / panel fill
    "surface_2":  "#333333",   # Elevated rows
    "surface_3":  "#3c3c3c",   # Hover
    "sidebar_bg": "#1c1c1c",   # Navigation rail
    "accent":     "#0078d4",   # Windows accent blue
    "accent_hov": "#1084d8",
    "text_pri":   "#f3f3f3",
    "text_sec":   "#9d9d9d",
    "text_ter":   "#6b6b6b",
    "border":     "#404040",
    "font":       "Segoe UI",
}


class AppShell:
    """Main application window providing persistent navigation across independent tools."""

    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or AppConfig.load()
        self.active_tool = "wallpaper"
        self._tray_mgr: Optional[Any] = None
        self._init_window()
        self._build_shell()
        self.switch_tool("wallpaper")

        if getattr(self.config, "check_for_updates_on_startup", True) and hasattr(self, "root") and self.root:
            self.root.after(2000, self._check_for_updates_startup)

    def _init_window(self) -> None:
        if HAS_CUSTOMTKINTER:
            ctk.set_appearance_mode(self.config.theme)
            ctk.set_default_color_theme("blue")
            self.root = ctk.CTk()
        else:
            self.root = tk.Tk()

        self.root.title("Desktop Utility Suite")

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        win_w = min(1040, max(780, screen_w - 60))
        win_h = min(820, max(560, screen_h - 100))
        self.root.geometry(f"{win_w}x{win_h}")
        self.root.minsize(740, 520)

        # Set window icon if available
        icon_path = Path(__file__).resolve().parents[3] / "assets" / "icon.ico"
        if icon_path.exists():
            try:
                self.root.iconbitmap(str(icon_path))
            except Exception:
                pass

        self._center_window(win_w, win_h)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close_window)

    def _center_window(self, width: int, height: int) -> None:
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _build_shell(self) -> None:
        # Main layout: Left sidebar + Right content area
        self.main_container = (
            ctk.CTkFrame(self.root, fg_color=_W11["surface_0"])
            if HAS_CUSTOMTKINTER
            else tk.Frame(self.root)
        )
        self.main_container.pack(fill="both", expand=True)

        # ── 1. Left Navigation Sidebar ────────────────────────────────────────
        self.sidebar = (
            ctk.CTkFrame(self.main_container, width=220, corner_radius=0, fg_color=_W11["sidebar_bg"])
            if HAS_CUSTOMTKINTER
            else tk.Frame(self.main_container, width=200, bg="#1c1c1c")
        )
        self.sidebar.pack(side="left", fill="y", padx=0, pady=0)
        self.sidebar.pack_propagate(False)

        # ── Brand / logo section ──────────────────────────────────────────────
        brand_frame = (
            ctk.CTkFrame(self.sidebar, fg_color="transparent")
            if HAS_CUSTOMTKINTER
            else tk.Frame(self.sidebar, bg="#1c1c1c")
        )
        brand_frame.pack(fill="x", padx=16, pady=(20, 8))

        if HAS_CUSTOMTKINTER:
            ctk.CTkLabel(
                brand_frame,
                text="🖼  Desktop Suite",
                font=ctk.CTkFont(family=_W11["font"], size=15, weight="bold"),
                text_color=_W11["text_pri"],
            ).pack(anchor="w")
            ctk.CTkLabel(
                brand_frame,
                text=f"v{__version__}",
                font=ctk.CTkFont(family=_W11["font"], size=11),
                text_color=_W11["text_ter"],
            ).pack(anchor="w", pady=(1, 0))
        else:
            tk.Label(brand_frame, text=f"Desktop Suite v{__version__}", font=("Segoe UI", 12, "bold"), bg="#1c1c1c", fg="#f3f3f3").pack(anchor="w")

        # Separator line
        if HAS_CUSTOMTKINTER:
            ctk.CTkFrame(self.sidebar, height=1, fg_color=_W11["border"]).pack(fill="x", padx=16, pady=(8, 10))
        else:
            tk.Frame(self.sidebar, height=1, bg="#404040").pack(fill="x", padx=12, pady=(6, 8))

        # ── Navigation buttons ────────────────────────────────────────────────
        nav_frame = (
            ctk.CTkFrame(self.sidebar, fg_color="transparent")
            if HAS_CUSTOMTKINTER
            else tk.Frame(self.sidebar, bg="#1c1c1c")
        )
        nav_frame.pack(fill="x", padx=8, pady=4)

        self._nav_font_bold = ctk.CTkFont(family=_W11["font"], size=12, weight="bold") if HAS_CUSTOMTKINTER else None
        self._nav_font_normal = ctk.CTkFont(family=_W11["font"], size=12) if HAS_CUSTOMTKINTER else None

        self.nav_wallpaper_btn = (
            ctk.CTkButton(
                nav_frame,
                text="🖼️   Wallpaper Manager",
                height=36,
                font=self._nav_font_bold,
                anchor="w",
                corner_radius=6,
                fg_color=_W11["accent"],
                hover_color=_W11["accent_hov"],
                text_color=_W11["text_pri"],
                command=lambda: self.switch_tool("wallpaper"),
            )
            if HAS_CUSTOMTKINTER
            else tk.Button(nav_frame, text="Wallpaper Manager", command=lambda: self.switch_tool("wallpaper"))
        )
        self.nav_wallpaper_btn.pack(fill="x", pady=(0, 2))

        self.nav_organizer_btn = (
            ctk.CTkButton(
                nav_frame,
                text="📁   Download Organizer",
                height=36,
                font=ctk.CTkFont(family=_W11["font"], size=12),
                anchor="w",
                corner_radius=6,
                fg_color="transparent",
                text_color=_W11["text_sec"],
                hover_color=_W11["surface_2"],
                command=lambda: self.switch_tool("organizer"),
            )
            if HAS_CUSTOMTKINTER
            else tk.Button(nav_frame, text="Download Organizer", command=lambda: self.switch_tool("organizer"))
        )
        self.nav_organizer_btn.pack(fill="x", pady=(0, 2))

        # ── Bottom tools (pushed to bottom of sidebar) ────────────────────────
        bottom_nav = (
            ctk.CTkFrame(self.sidebar, fg_color="transparent")
            if HAS_CUSTOMTKINTER
            else tk.Frame(self.sidebar, bg="#1c1c1c")
        )
        bottom_nav.pack(side="bottom", fill="x", padx=12, pady=16)

        # Separator above bottom section
        if HAS_CUSTOMTKINTER:
            ctk.CTkFrame(self.sidebar, height=1, fg_color=_W11["border"]).pack(side="bottom", fill="x", padx=16, pady=(0, 4))

        if HAS_CUSTOMTKINTER:
            ctk.CTkLabel(
                bottom_nav,
                text="Appearance",
                font=ctk.CTkFont(family=_W11["font"], size=10),
                text_color=_W11["text_ter"],
            ).pack(anchor="w", pady=(0, 3))

            self.theme_menu = ctk.CTkOptionMenu(
                bottom_nav,
                values=["Dark", "Light", "System"],
                height=28,
                font=ctk.CTkFont(family=_W11["font"], size=11),
                corner_radius=6,
                fg_color=_W11["surface_2"],
                button_color=_W11["surface_3"],
                button_hover_color=_W11["border"],
                command=self._on_theme_change,
            )
            self.theme_menu.pack(fill="x", pady=(0, 10))
            self.theme_menu.set(self.config.theme)

            self.update_btn = ctk.CTkButton(
                bottom_nav,
                text="↻  Check for Updates",
                height=28,
                font=ctk.CTkFont(family=_W11["font"], size=11),
                corner_radius=6,
                fg_color=_W11["surface_2"],
                hover_color=_W11["surface_3"],
                text_color=_W11["text_sec"],
                command=self.on_manual_check_update,
            )
            self.update_btn.pack(fill="x", pady=(0, 10))

            ctk.CTkLabel(
                bottom_nav,
                text="Desktop Utility Suite",
                font=ctk.CTkFont(family=_W11["font"], size=10),
                text_color=_W11["text_ter"],
            ).pack(anchor="center")
        else:
            self.theme_menu = tk.OptionMenu(bottom_nav, tk.StringVar(), "Dark", "Light", "System")
            self.theme_menu.pack(fill="x", pady=(0, 6))
            self.update_btn = tk.Button(bottom_nav, text="Check Updates", command=self.on_manual_check_update)
            self.update_btn.pack(fill="x", pady=(0, 4))
            tk.Label(bottom_nav, text="Desktop Utility Suite").pack(anchor="center")

        # ── Thin separator between sidebar and content ────────────────────────
        if HAS_CUSTOMTKINTER:
            ctk.CTkFrame(self.main_container, width=1, fg_color=_W11["border"]).pack(side="left", fill="y")

        # ── 2. Right Main Content Area ────────────────────────────────────────
        self.content_area = (
            ctk.CTkFrame(self.main_container, fg_color=_W11["surface_0"])
            if HAS_CUSTOMTKINTER
            else tk.Frame(self.main_container)
        )
        self.content_area.pack(side="right", fill="both", expand=True)

        # Tool 1 Container: Wallpaper Manager
        self.wallpaper_frame = (
            ctk.CTkFrame(self.content_area, fg_color="transparent")
            if HAS_CUSTOMTKINTER
            else tk.Frame(self.content_area)
        )
        self.wallpaper_tool = WallpaperSelectorDialog(
            config=self.config,
            parent_frame=self.wallpaper_frame,
            root_window=self.root,
        )

        # Tool 2 Container: Download Organizer
        self.organizer_frame = (
            ctk.CTkFrame(self.content_area, fg_color="transparent")
            if HAS_CUSTOMTKINTER
            else tk.Frame(self.content_area)
        )
        self.organizer_tool = DownloadOrganizerView(
            parent=self.organizer_frame,
            config=self.config,
            root_window=self.root,
        )
        self.organizer_tool.pack(fill="both", expand=True)

    def switch_tool(self, tool_id: str) -> None:
        """Switch between tools seamlessly without duplicating windows or losing state."""
        self.active_tool = tool_id

        if not hasattr(self, "wallpaper_frame") or not hasattr(self, "organizer_frame"):
            return

        if tool_id == "wallpaper":
            self.organizer_frame.pack_forget()
            self.wallpaper_frame.pack(fill="both", expand=True)
            if HAS_CUSTOMTKINTER and hasattr(self, "nav_wallpaper_btn") and hasattr(self, "nav_organizer_btn"):
                config_wp = {
                    "fg_color": _W11["accent"],
                    "text_color": _W11["text_pri"],
                    "hover_color": _W11["accent_hov"],
                }
                config_org = {
                    "fg_color": "transparent",
                    "text_color": _W11["text_sec"],
                    "hover_color": _W11["surface_2"],
                }
                if getattr(self, "_nav_font_bold", None):
                    config_wp["font"] = self._nav_font_bold
                if getattr(self, "_nav_font_normal", None):
                    config_org["font"] = self._nav_font_normal
                self.nav_wallpaper_btn.configure(**config_wp)
                self.nav_organizer_btn.configure(**config_org)
        elif tool_id == "organizer":
            self.wallpaper_frame.pack_forget()
            self.organizer_frame.pack(fill="both", expand=True)
            if HAS_CUSTOMTKINTER and hasattr(self, "nav_organizer_btn") and hasattr(self, "nav_wallpaper_btn"):
                config_org = {
                    "fg_color": _W11["accent"],
                    "text_color": _W11["text_pri"],
                    "hover_color": _W11["accent_hov"],
                }
                config_wp = {
                    "fg_color": "transparent",
                    "text_color": _W11["text_sec"],
                    "hover_color": _W11["surface_2"],
                }
                if getattr(self, "_nav_font_bold", None):
                    config_org["font"] = self._nav_font_bold
                if getattr(self, "_nav_font_normal", None):
                    config_wp["font"] = self._nav_font_normal
                self.nav_organizer_btn.configure(**config_org)
                self.nav_wallpaper_btn.configure(**config_wp)

    def _on_theme_change(self, new_theme: str) -> None:
        self.config.theme = new_theme
        self.config.save()
        if HAS_CUSTOMTKINTER:
            ctk.set_appearance_mode(new_theme)

    def _check_for_updates_startup(self) -> None:
        def _worker():
            try:
                res = check_for_updates(self.config, force=False)
                if res.update_available:
                    self.root.after(0, lambda: self._show_update_modal(res))
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True).start()

    def _show_update_modal(self, update_info: UpdateCheckResult) -> None:
        try:
            UpdateModalDialog(self.root, update_info)
        except Exception:
            pass

    def on_manual_check_update(self) -> None:
        def _worker():
            res = check_for_updates(self.config, force=True)
            if res.update_available:
                self.root.after(0, lambda: self._show_update_modal(res))
            elif res.error and "No releases found" not in res.error and "Throttled" not in res.error:
                self.root.after(0, lambda: messagebox.showwarning("Update Check", res.error))
            else:
                self.root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "Latest Version",
                        f"You are running the latest version (v{res.current_version}).",
                    ),
                )
        threading.Thread(target=_worker, daemon=True).start()

    def on_close_window(self) -> None:
        """Handle window close event: minimize to tray if auto-rotation is enabled, else exit."""
        from .tray import SystemTrayManager
        rotation_active = bool(getattr(self.config, "rotation_enabled", False))
        if rotation_active and SystemTrayManager.is_available():
            self._minimize_to_tray()
        else:
            self.quit_app()

    def _minimize_to_tray(self) -> None:
        """Minimize shell window to system tray to keep background rotation active."""
        from .tray import SystemTrayManager
        if not hasattr(self, "_tray_mgr") or self._tray_mgr is None:
            self._tray_mgr = SystemTrayManager(
                on_show=self._restore_from_tray,
                on_rotate_now=self._tray_rotate_now,
                on_quit=self.quit_app,
                app_name="Desktop Utility Suite",
            )
        self.root.withdraw()
        if self._tray_mgr.start():
            self._tray_mgr.notify(
                "Running in background. Desktop wallpaper will continue rotating automatically.",
                "Desktop Utility Suite",
            )

    def _restore_from_tray(self) -> None:
        """Restore GUI window from system tray."""
        def _do_restore():
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
            if hasattr(self, "_tray_mgr") and self._tray_mgr:
                self._tray_mgr.stop()
        if hasattr(self, "root") and self.root:
            self.root.after(0, _do_restore)

    def _tray_rotate_now(self) -> None:
        """Trigger instant rotation from tray icon menu."""
        if hasattr(self, "wallpaper_tool") and hasattr(self.wallpaper_tool, "on_rotate_now"):
            if hasattr(self, "root") and self.root:
                self.root.after(0, self.wallpaper_tool.on_rotate_now)

    def quit_app(self) -> None:
        """Cleanly terminate application and background services."""
        if hasattr(self, "_tray_mgr") and self._tray_mgr:
            try:
                self._tray_mgr.stop()
            except Exception:
                pass
            self._tray_mgr = None
        if hasattr(self, "wallpaper_tool") and hasattr(self.wallpaper_tool, "cleanup"):
            try:
                self.wallpaper_tool.cleanup()
            except Exception:
                pass
        if hasattr(self, "root") and self.root:
            try:
                self.root.destroy()
            except Exception:
                pass

    def run(self) -> None:
        """Run the application shell main event loop."""
        self.root.mainloop()
