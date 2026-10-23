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

from ..core.config import AppConfig
from ..core.updater import check_for_updates, UpdateCheckResult
from .dialog import WallpaperSelectorDialog
from .update_dialog import UpdateModalDialog
from ..tools.download_organizer.ui import DownloadOrganizerView


class AppShell:
    """Main application window providing persistent navigation across independent tools."""

    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or AppConfig.load()
        self.active_tool = "wallpaper"
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

    def _center_window(self, width: int, height: int) -> None:
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _build_shell(self) -> None:
        # Main layout: Left sidebar + Right content area
        self.main_container = ctk.CTkFrame(self.root, fg_color="transparent") if HAS_CUSTOMTKINTER else tk.Frame(self.root)
        self.main_container.pack(fill="both", expand=True)

        # 1. Left Navigation Sidebar
        self.sidebar = (
            ctk.CTkFrame(self.main_container, width=200, corner_radius=0, fg_color="#0f172a")
            if HAS_CUSTOMTKINTER
            else tk.Frame(self.main_container, width=180, bg="#1e293b")
        )
        self.sidebar.pack(side="left", fill="y", padx=0, pady=0)
        self.sidebar.pack_propagate(False)

        # Sidebar Branding
        brand_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent") if HAS_CUSTOMTKINTER else tk.Frame(self.sidebar)
        brand_frame.pack(fill="x", padx=12, pady=(16, 20))

        app_title = (
            ctk.CTkLabel(
                brand_frame,
                text="⚡ Utility Suite",
                font=ctk.CTkFont(size=18, weight="bold"),
                text_color="#f8fafc",
            )
            if HAS_CUSTOMTKINTER
            else tk.Label(brand_frame, text="Utility Suite", font=("Helvetica", 14, "bold"))
        )
        app_title.pack(anchor="w")

        app_sub = (
            ctk.CTkLabel(
                brand_frame,
                text="Desktop Tools",
                font=ctk.CTkFont(size=11),
                text_color="#64748b",
            )
            if HAS_CUSTOMTKINTER
            else tk.Label(brand_frame, text="Desktop Tools")
        )
        app_sub.pack(anchor="w")

        # Sidebar Navigation Buttons
        nav_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent") if HAS_CUSTOMTKINTER else tk.Frame(self.sidebar)
        nav_frame.pack(fill="x", padx=8, pady=4)

        self.nav_wallpaper_btn = (
            ctk.CTkButton(
                nav_frame,
                text="🖼️  Wallpaper Manager",
                height=38,
                font=ctk.CTkFont(size=12, weight="bold"),
                anchor="w",
                fg_color="#2563eb",
                hover_color="#1d4ed8",
                command=lambda: self.switch_tool("wallpaper"),
            )
            if HAS_CUSTOMTKINTER
            else tk.Button(nav_frame, text="Wallpaper Manager", command=lambda: self.switch_tool("wallpaper"))
        )
        self.nav_wallpaper_btn.pack(fill="x", pady=3)

        self.nav_organizer_btn = (
            ctk.CTkButton(
                nav_frame,
                text="📁  Download Organizer",
                height=38,
                font=ctk.CTkFont(size=12, weight="bold"),
                anchor="w",
                fg_color="transparent",
                text_color="#94a3b8",
                hover_color="#1e293b",
                command=lambda: self.switch_tool("organizer"),
            )
            if HAS_CUSTOMTKINTER
            else tk.Button(nav_frame, text="Download Organizer", command=lambda: self.switch_tool("organizer"))
        )
        self.nav_organizer_btn.pack(fill="x", pady=3)

        # Sidebar Bottom Tools (Theme toggle, Updates, Version)
        bottom_nav = ctk.CTkFrame(self.sidebar, fg_color="transparent") if HAS_CUSTOMTKINTER else tk.Frame(self.sidebar)
        bottom_nav.pack(side="bottom", fill="x", padx=12, pady=16)

        self.update_btn = (
            ctk.CTkButton(
                bottom_nav,
                text="🔄 Check Updates",
                height=30,
                font=ctk.CTkFont(size=11),
                fg_color="#1e293b",
                hover_color="#334155",
                command=self.on_manual_check_update,
            )
            if HAS_CUSTOMTKINTER
            else tk.Button(bottom_nav, text="Updates", command=self.on_manual_check_update)
        )
        self.update_btn.pack(fill="x", pady=(0, 8))

        theme_lbl = (
            ctk.CTkLabel(
                bottom_nav,
                text="Appearance",
                font=ctk.CTkFont(size=10),
                text_color="#64748b",
            )
            if HAS_CUSTOMTKINTER
            else tk.Label(bottom_nav, text="Appearance")
        )
        theme_lbl.pack(anchor="w", pady=(0, 2))

        self.theme_menu = (
            ctk.CTkOptionMenu(
                bottom_nav,
                values=["Dark", "Light", "System"],
                height=26,
                font=ctk.CTkFont(size=10),
                command=self._on_theme_change,
            )
            if HAS_CUSTOMTKINTER
            else tk.OptionMenu(bottom_nav, tk.StringVar(), "Dark", "Light", "System")
        )
        self.theme_menu.pack(fill="x", pady=(0, 8))
        if HAS_CUSTOMTKINTER:
            self.theme_menu.set(self.config.theme)

        version_lbl = (
            ctk.CTkLabel(
                bottom_nav,
                text="v1.5.0 • Desktop Utility Suite",
                font=ctk.CTkFont(size=10),
                text_color="#475569",
            )
            if HAS_CUSTOMTKINTER
            else tk.Label(bottom_nav, text="v1.5.0")
        )
        version_lbl.pack(anchor="center")

        # 2. Right Main Content Area
        self.content_area = (
            ctk.CTkFrame(self.main_container, fg_color="transparent")
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

    def switch_tool(self, tool_id: str) -> None:
        """Switch between tools seamlessly without duplicating windows or losing state."""
        self.active_tool = tool_id

        if not hasattr(self, "wallpaper_frame") or not hasattr(self, "organizer_frame"):
            return

        if tool_id == "wallpaper":
            self.organizer_frame.pack_forget()
            self.wallpaper_frame.pack(fill="both", expand=True)
            if HAS_CUSTOMTKINTER and hasattr(self, "nav_wallpaper_btn") and hasattr(self, "nav_organizer_btn"):
                self.nav_wallpaper_btn.configure(
                    fg_color="#2563eb",
                    text_color="#ffffff",
                    hover_color="#1d4ed8",
                )
                self.nav_organizer_btn.configure(
                    fg_color="transparent",
                    text_color="#94a3b8",
                    hover_color="#1e293b",
                )
        elif tool_id == "organizer":
            self.wallpaper_frame.pack_forget()
            self.organizer_frame.pack(fill="both", expand=True)
            if HAS_CUSTOMTKINTER and hasattr(self, "nav_organizer_btn") and hasattr(self, "nav_wallpaper_btn"):
                self.nav_organizer_btn.configure(
                    fg_color="#2563eb",
                    text_color="#ffffff",
                    hover_color="#1d4ed8",
                )
                self.nav_wallpaper_btn.configure(
                    fg_color="transparent",
                    text_color="#94a3b8",
                    hover_color="#1e293b",
                )

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

    def run(self) -> None:
        """Run the application shell main event loop."""
        self.root.mainloop()
