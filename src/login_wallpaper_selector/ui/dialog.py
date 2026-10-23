"""Graphical selection dialog for choosing desktop wallpaper categories."""

from __future__ import annotations
import os
import sys
import threading
from pathlib import Path
from typing import Optional, Callable
from PIL import Image

try:
    import customtkinter as ctk
    HAS_CUSTOMTKINTER = True
except ImportError:
    import tkinter as ctk
    HAS_CUSTOMTKINTER = False

import tkinter as tk
from tkinter import messagebox

from ..core.models import WallpaperCategory, WallpaperPosition, WallpaperMetadata, ColorPalette, WallpaperMood
from ..core.seasonal import Season, get_current_season, get_season_display
from ..core.favorites import FavoritesManager
from ..core.config import AppConfig
from ..core.history import HistoryTracker
from ..core.cache import CacheManager
from ..core.display import generate_desktop_preview_image
from ..core.search_history import SearchHistoryManager
from ..core.updater import check_for_updates, UpdateCheckResult
from ..providers.router import ProviderRouter
from ..adapters.factory import get_wallpaper_adapter
from .file_picker import pick_local_image
from .update_dialog import UpdateModalDialog


class WallpaperSelectorDialog:
    """Desktop dialog displaying the wallpaper options with live preview and controls."""

    def __init__(
        self,
        config: Optional[AppConfig] = None,
        parent_frame: Optional[Any] = None,
        root_window: Optional[Any] = None,
    ):
        self.config = config or AppConfig.load()
        self.config.default_position = WallpaperPosition.FILL.value
        self.parent_frame = parent_frame
        self.root = root_window
        self.history = HistoryTracker(self.config)
        self.cache = CacheManager(self.config)
        self.favorites_mgr = FavoritesManager(self.config)
        self.search_history_mgr = SearchHistoryManager(self.config)
        self.router = ProviderRouter(self.config, self.history, self.cache)
        self.adapter = get_wallpaper_adapter()

        self.current_category: Optional[WallpaperCategory] = None
        self.current_metadata: Optional[WallpaperMetadata] = None
        self.staged_metadata: Optional[WallpaperMetadata] = None
        self.selected_color: ColorPalette = ColorPalette.ANY
        self.selected_mood: WallpaperMood = WallpaperMood.ANY
        self.current_keyword: str = ""
        self._current_search_id: int = 0
        self.suggestion_buttons = []
        self.is_busy = False
        self._rotation_timer_id: Optional[str] = None
        self._is_auto_rotating: bool = False
        self._tray_mgr: Optional[Any] = None

        self._init_window()

        if hasattr(self, "root") and self.root:
            self._schedule_next_rotation_check(delay_ms=3000)

        if not self.parent_frame and getattr(self.config, "check_for_updates_on_startup", True) and hasattr(self, "root") and self.root:
            self.root.after(1500, self._check_for_updates_startup)

    def _init_window(self) -> None:
        if self.parent_frame is not None:
            if not self.root:
                try:
                    self.root = self.parent_frame.winfo_toplevel()
                except Exception:
                    self.root = None
            self._build_widgets()
            return

        if HAS_CUSTOMTKINTER:
            ctk.set_appearance_mode(self.config.theme)
            ctk.set_default_color_theme("blue")
            self.root = ctk.CTk()
        else:
            self.root = tk.Tk()

        self.root.title("Choose Your Wallpaper")
        
        # Responsive window sizing based on screen resolution
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        win_w = min(700, max(580, screen_w - 60))
        win_h = min(820, max(520, screen_h - 100))
        self.root.geometry(f"{win_w}x{win_h}")
        self.root.minsize(560, 480)
        self.root.attributes("-topmost", True)
        self.root.after(100, lambda: self.root.attributes("-topmost", False))

        # Set window icon if available
        icon_path = Path(__file__).resolve().parents[3] / "assets" / "icon.ico"
        if icon_path.exists():
            try:
                self.root.iconbitmap(str(icon_path))
            except Exception:
                pass

        # Center on screen
        self._center_window(win_w, win_h)

        self._build_widgets()

        # Listen for window resize to adjust responsive wrapping
        self.root.bind("<Configure>", self._on_window_configure)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close_window)

    def _center_window(self, width: int, height: int) -> None:
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _on_window_configure(self, event) -> None:
        if hasattr(self, "root") and event.widget == self.root:
            new_w = event.width
            wrap = max(380, new_w - 70)
            if hasattr(self, "attrib_lbl") and self.attrib_lbl:
                try:
                    if HAS_CUSTOMTKINTER:
                        self.attrib_lbl.configure(wraplength=wrap)
                    else:
                        self.attrib_lbl.config(wraplength=wrap)
                except Exception:
                    pass
            if hasattr(self, "status_lbl") and self.status_lbl:
                try:
                    if HAS_CUSTOMTKINTER:
                        self.status_lbl.configure(wraplength=wrap)
                    else:
                        self.status_lbl.config(wraplength=wrap)
                except Exception:
                    pass

    def _build_widgets(self) -> None:
        host_target = self.parent_frame if self.parent_frame is not None else self.root

        # Bottom Action Bar: permanently docked at bottom edge of root so actions are ALWAYS accessible
        bottom_frame = ctk.CTkFrame(host_target, fg_color="transparent") if HAS_CUSTOMTKINTER else tk.Frame(host_target)
        bottom_frame.pack(side="bottom", fill="x", padx=16, pady=(6, 12))

        # Responsive 5-column grid for action buttons - stretches evenly across any width without collision
        bottom_frame.columnconfigure(0, weight=1)
        bottom_frame.columnconfigure(1, weight=1)
        bottom_frame.columnconfigure(2, weight=1)
        bottom_frame.columnconfigure(3, weight=2)
        bottom_frame.columnconfigure(4, weight=1)

        if HAS_CUSTOMTKINTER:
            self.retry_btn = ctk.CTkButton(
                bottom_frame,
                text="🔄 Try Another",
                height=36,
                font=ctk.CTkFont(size=12, weight="bold"),
                state="disabled",
                fg_color="#4b5563",
                hover_color="#374151",
                command=self.on_retry,
            )
            self.retry_btn.grid(row=0, column=0, padx=3, pady=2, sticky="ew")

            self.save_btn = ctk.CTkButton(
                bottom_frame,
                text="💾 Save Image",
                height=36,
                font=ctk.CTkFont(size=12, weight="bold"),
                state="disabled",
                fg_color="#059669",
                hover_color="#047857",
                command=self.on_save_wallpaper,
            )
            self.save_btn.grid(row=0, column=1, padx=3, pady=2, sticky="ew")

            self.open_folder_btn = ctk.CTkButton(
                bottom_frame,
                text="📂 Open Folder",
                height=36,
                font=ctk.CTkFont(size=12, weight="bold"),
                state="disabled",
                fg_color="#374151",
                hover_color="#1f2937",
                command=self.on_open_category_folder,
            )
            self.open_folder_btn.grid(row=0, column=2, padx=3, pady=2, sticky="ew")

            self.apply_btn = ctk.CTkButton(
                bottom_frame,
                text="✓ Apply to Desktop",
                height=36,
                font=ctk.CTkFont(size=12, weight="bold"),
                state="disabled",
                fg_color="#2563eb",
                hover_color="#1d4ed8",
                command=self.on_apply_staged,
            )
            self.apply_btn.grid(row=0, column=3, padx=3, pady=2, sticky="ew")

            self.close_btn = ctk.CTkButton(
                bottom_frame,
                text="Done / Close",
                height=36,
                font=ctk.CTkFont(size=12, weight="bold"),
                command=self.on_close,
            )
            self.close_btn.grid(row=0, column=4, padx=3, pady=2, sticky="ew")
        else:
            self.retry_btn = tk.Button(bottom_frame, text="🔄 Try Another", state="disabled", command=self.on_retry)
            self.retry_btn.grid(row=0, column=0, padx=2, pady=2, sticky="ew")
            self.save_btn = tk.Button(bottom_frame, text="💾 Save Image", state="disabled", command=self.on_save_wallpaper)
            self.save_btn.grid(row=0, column=1, padx=2, pady=2, sticky="ew")
            self.open_folder_btn = tk.Button(bottom_frame, text="📂 Open Folder", state="disabled", command=self.on_open_category_folder)
            self.open_folder_btn.grid(row=0, column=2, padx=2, pady=2, sticky="ew")
            self.apply_btn = tk.Button(bottom_frame, text="✓ Apply to Desktop", state="disabled", command=self.on_apply_staged)
            self.apply_btn.grid(row=0, column=3, padx=2, pady=2, sticky="ew")
            self.close_btn = tk.Button(bottom_frame, text="Done / Close", command=self.on_close)
            self.close_btn.grid(row=0, column=4, padx=2, pady=2, sticky="ew")

        # Scrollable container for the main content area so nothing is EVER clipped or crammed on any screen size
        if HAS_CUSTOMTKINTER:
            self.scroll_container = ctk.CTkScrollableFrame(host_target, fg_color="transparent")
            self.scroll_container.pack(fill="both", expand=True, padx=4, pady=(4, 0))
            main_parent = self.scroll_container
        else:
            canvas = tk.Canvas(host_target, borderwidth=0, highlightthickness=0)
            scrollbar = tk.Scrollbar(host_target, orient="vertical", command=canvas.yview)
            self.scrollable_inner_frame = tk.Frame(canvas)
            self.scrollable_inner_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            canvas_window = canvas.create_window((0, 0), window=self.scrollable_inner_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))

            scrollbar.pack(side="right", fill="y")
            canvas.pack(side="left", fill="both", expand=True)
            self.scroll_container = canvas
            main_parent = self.scrollable_inner_frame

        # Header container
        header_frame = ctk.CTkFrame(main_parent, fg_color="transparent") if HAS_CUSTOMTKINTER else tk.Frame(main_parent)
        header_frame.pack(fill="x", padx=16, pady=(6, 2))

        top_title_row = ctk.CTkFrame(header_frame, fg_color="transparent") if HAS_CUSTOMTKINTER else tk.Frame(header_frame)
        top_title_row.pack(fill="x")

        title_lbl = (
            ctk.CTkLabel(
                top_title_row,
                text="Desktop Wallpaper Selector",
                font=ctk.CTkFont(size=20, weight="bold"),
            )
            if HAS_CUSTOMTKINTER
            else tk.Label(top_title_row, text="Desktop Wallpaper Selector", font=("Helvetica", 15, "bold"))
        )
        title_lbl.pack(side="left")

        if not self.parent_frame:
            self.update_check_btn = (
                ctk.CTkButton(
                    top_title_row,
                    text="🔄 Updates",
                    width=85,
                    height=26,
                    font=ctk.CTkFont(size=11),
                    fg_color="#1f2937",
                    hover_color="#374151",
                    command=self.on_manual_check_update,
                )
                if HAS_CUSTOMTKINTER
                else tk.Button(top_title_row, text="🔄 Updates", font=("Helvetica", 8), command=self.on_manual_check_update)
            )
            self.update_check_btn.pack(side="right")
        else:
            self.update_check_btn = None

        subtitle_lbl = (
            ctk.CTkLabel(
                header_frame,
                text="Select a category for your session background:",
                font=ctk.CTkFont(size=12),
                text_color="gray",
            )
            if HAS_CUSTOMTKINTER
            else tk.Label(header_frame, text="Select a category for your session background:", fg="gray")
        )
        subtitle_lbl.pack(anchor="w", pady=(1, 0))

        # Category buttons container: 2 rows of 3 columns - compact, beautiful & responsive
        btn_grid = ctk.CTkFrame(main_parent, fg_color="transparent") if HAS_CUSTOMTKINTER else tk.Frame(main_parent)
        btn_grid.pack(fill="x", padx=16, pady=(4, 6))

        categories = [
            (WallpaperCategory.SPACE, "🚀 Space", "#1e3a8a"),
            (WallpaperCategory.NATURE, "🌿 Nature", "#065f46"),
            (WallpaperCategory.ART, "🎨 Art", "#78350f"),
            (WallpaperCategory.PORTRAIT, "👤 Portrait", "#581c87"),
            (WallpaperCategory.LOCAL_STORAGE, "📁 Local Storage", "#374151"),
            (WallpaperCategory.FAVORITES, "⭐ Favorites", "#b45309"),
        ]

        self.cat_buttons = {}
        self._cat_colors = {}
        for idx, (cat, label_text, color) in enumerate(categories):
            self._cat_colors[cat] = color
            row = idx // 3
            col = idx % 3

            if HAS_CUSTOMTKINTER:
                btn = ctk.CTkButton(
                    btn_grid,
                    text=label_text,
                    font=ctk.CTkFont(size=13, weight="bold"),
                    height=36,
                    fg_color=color,
                    hover_color=color,
                    command=lambda c=cat: self.on_select_category(c),
                )
                btn.grid(row=row, column=col, padx=4, pady=3, sticky="ew")
            else:
                btn = tk.Button(
                    btn_grid,
                    text=label_text,
                    font=("Helvetica", 10, "bold"),
                    height=1,
                    command=lambda c=cat: self.on_select_category(c),
                )
                btn.grid(row=row, column=col, padx=4, pady=3, sticky="ew")
            self.cat_buttons[cat] = btn

        btn_grid.columnconfigure(0, weight=1)
        btn_grid.columnconfigure(1, weight=1)
        btn_grid.columnconfigure(2, weight=1)

        # Custom Keyword Search Bar & Suggestions Container
        search_container = ctk.CTkFrame(main_parent, fg_color="transparent") if HAS_CUSTOMTKINTER else tk.Frame(main_parent)
        search_container.pack(fill="x", padx=16, pady=(2, 4))

        search_row = ctk.CTkFrame(search_container, fg_color="transparent") if HAS_CUSTOMTKINTER else tk.Frame(search_container)
        search_row.pack(fill="x", pady=(0, 2))

        if HAS_CUSTOMTKINTER:
            self.search_entry = ctk.CTkEntry(
                search_row,
                placeholder_text="🔍 Search wallpapers (e.g., Black Hole, Cyberpunk, Waterfall)...",
                height=32,
                font=ctk.CTkFont(size=12),
            )
            self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
            self.search_entry.bind("<Return>", lambda event: self.on_trigger_search())

            self.search_btn = ctk.CTkButton(
                search_row,
                text="🔍 Search",
                width=80,
                height=32,
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="#3b82f6",
                hover_color="#2563eb",
                command=self.on_trigger_search,
            )
            self.search_btn.pack(side="left", padx=(0, 6))

            self.clear_search_btn = ctk.CTkButton(
                search_row,
                text="✕",
                width=32,
                height=32,
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="#374151",
                hover_color="#4b5563",
                command=self.on_clear_search,
            )
            self.clear_search_btn.pack(side="left")
        else:
            self.search_entry = tk.Entry(search_row, font=("Helvetica", 10))
            self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
            self.search_entry.bind("<Return>", lambda event: self.on_trigger_search())

            self.search_btn = tk.Button(search_row, text="🔍 Search", command=self.on_trigger_search)
            self.search_btn.pack(side="left", padx=(0, 6))

            self.clear_search_btn = tk.Button(search_row, text="✕", command=self.on_clear_search)
            self.clear_search_btn.pack(side="left")

        # Suggestion pills row
        self.suggestions_frame = ctk.CTkFrame(search_container, fg_color="transparent") if HAS_CUSTOMTKINTER else tk.Frame(search_container)
        self.suggestions_frame.pack(fill="x")
        self._populate_suggestion_chips()

        # Color Palette Swatch Bar
        color_frame = ctk.CTkFrame(main_parent, fg_color="transparent") if HAS_CUSTOMTKINTER else tk.Frame(main_parent)
        color_frame.pack(fill="x", padx=16, pady=(2, 4))

        color_lbl = (
            ctk.CTkLabel(color_frame, text="🎨 Color:", font=ctk.CTkFont(size=12, weight="bold"))
            if HAS_CUSTOMTKINTER
            else tk.Label(color_frame, text="🎨 Color:", font=("Helvetica", 9, "bold"))
        )
        color_lbl.pack(side="left", padx=(4, 8))

        palettes = [
            (ColorPalette.ANY, "🔘 Any", "#374151"),
            (ColorPalette.BLUE, "🔵 Blue", "#0284c7"),
            (ColorPalette.PURPLE, "🟣 Purple", "#a855f7"),
            (ColorPalette.GREEN, "🟢 Green", "#10b981"),
            (ColorPalette.WARM, "🟠 Warm", "#ea580c"),
            (ColorPalette.MONOCHROME, "⚫ Dark", "#27272a"),
        ]

        self.color_chips = {}
        for pal, label, bg_color in palettes:
            if HAS_CUSTOMTKINTER:
                chip = ctk.CTkButton(
                    color_frame,
                    text=label,
                    width=72,
                    height=28,
                    font=ctk.CTkFont(size=11, weight="bold"),
                    fg_color=bg_color if pal == self.selected_color else "#1f2937",
                    hover_color=bg_color,
                    border_width=2 if pal == self.selected_color else 0,
                    border_color="#38bdf8",
                    command=lambda p=pal: self.on_select_color(p),
                )
                chip.pack(side="left", padx=3)
            else:
                chip = tk.Button(
                    color_frame,
                    text=label,
                    bg=bg_color if pal == self.selected_color else "#ddd",
                    command=lambda p=pal: self.on_select_color(p),
                )
                chip.pack(side="left", padx=2)
            self.color_chips[pal] = chip

        # Mood Selector Bar ("What's your mood?")
        mood_frame = ctk.CTkFrame(main_parent, fg_color="transparent") if HAS_CUSTOMTKINTER else tk.Frame(main_parent)
        mood_frame.pack(fill="x", padx=16, pady=(2, 4))

        mood_lbl = (
            ctk.CTkLabel(mood_frame, text="🎭 Mood:", font=ctk.CTkFont(size=12, weight="bold"))
            if HAS_CUSTOMTKINTER
            else tk.Label(mood_frame, text="🎭 Mood:", font=("Helvetica", 9, "bold"))
        )
        mood_lbl.pack(side="left", padx=(4, 8))

        moods = [
            (WallpaperMood.ANY, "✨ Any", "#374151"),
            (WallpaperMood.PEACEFUL, "🕊️ Calm", "#0d9488"),
            (WallpaperMood.DARK, "🌑 Dark", "#18181b"),
            (WallpaperMood.CINEMATIC, "🎬 Epic", "#4f46e5"),
            (WallpaperMood.MINIMALIST, "◻️ Minimal", "#52525b"),
            (WallpaperMood.VIBRANT, "🌈 Vivid", "#d97706"),
        ]

        self.mood_chips = {}
        for mood, label, bg_color in moods:
            if HAS_CUSTOMTKINTER:
                chip = ctk.CTkButton(
                    mood_frame,
                    text=label,
                    width=72,
                    height=28,
                    font=ctk.CTkFont(size=11, weight="bold"),
                    fg_color=bg_color if mood == self.selected_mood else "#1f2937",
                    hover_color=bg_color,
                    border_width=2 if mood == self.selected_mood else 0,
                    border_color="#a855f7",
                    command=lambda m=mood: self.on_select_mood(m),
                )
                chip.pack(side="left", padx=3)
            else:
                chip = tk.Button(
                    mood_frame,
                    text=label,
                    bg=bg_color if mood == self.selected_mood else "#ddd",
                    command=lambda m=mood: self.on_select_mood(m),
                )
                chip.pack(side="left", padx=2)
            self.mood_chips[mood] = chip

        # Settings row: Mode selection (Fill / Fit)
        settings_frame = ctk.CTkFrame(main_parent) if HAS_CUSTOMTKINTER else tk.Frame(main_parent)
        settings_frame.pack(fill="x", padx=16, pady=(4, 6))

        mode_lbl = (
            ctk.CTkLabel(settings_frame, text="Display Mode:", font=ctk.CTkFont(size=12, weight="bold"))
            if HAS_CUSTOMTKINTER
            else tk.Label(settings_frame, text="Display Mode:")
        )
        mode_lbl.pack(side="left", padx=10, pady=6)

        default_mode = WallpaperPosition.FILL.value
        self.config.default_position = default_mode

        if HAS_CUSTOMTKINTER:
            self.mode_var = ctk.StringVar(value=default_mode)
            self.mode_selector = ctk.CTkSegmentedButton(
                settings_frame,
                values=[WallpaperPosition.FILL.value, WallpaperPosition.FIT.value],
                variable=self.mode_var,
                command=self.on_mode_change,
            )
            self.mode_selector.set(default_mode)
            self.mode_selector.pack(side="left", padx=8, pady=6)

            self.lockscreen_var = ctk.BooleanVar(value=False)

            self.layout_var = ctk.BooleanVar(value=bool(getattr(self.config, "desktop_layout_awareness", True)))
            self.layout_chk = ctk.CTkCheckBox(
                settings_frame,
                text="Layout Aware",
                variable=self.layout_var,
                font=ctk.CTkFont(size=12),
                command=self.on_layout_toggle,
            )
            self.layout_chk.pack(side="right", padx=6, pady=6)

            season_icon, season_name = get_season_display(get_current_season())
            self.seasonal_var = ctk.BooleanVar(value=bool(getattr(self.config, "seasonal_theme_enabled", False)))
            self.seasonal_chk = ctk.CTkCheckBox(
                settings_frame,
                text=f"{season_icon} {season_name}",
                variable=self.seasonal_var,
                font=ctk.CTkFont(size=12, weight="bold"),
                command=self.on_seasonal_toggle,
            )
            self.seasonal_chk.pack(side="right", padx=6, pady=6)
        else:
            self.mode_var = tk.StringVar(value=default_mode)
            self.mode_var.set(default_mode)
            for m in [WallpaperPosition.FILL.value, WallpaperPosition.FIT.value]:
                rb = tk.Radiobutton(settings_frame, text=m, value=m, variable=self.mode_var, command=self.on_mode_change)
                rb.pack(side="left", padx=4)

            self.lockscreen_var = tk.BooleanVar(value=False)

            self.layout_var = tk.BooleanVar(value=bool(getattr(self.config, "desktop_layout_awareness", True)))
            self.layout_chk = tk.Checkbutton(
                settings_frame,
                text="Layout Aware",
                variable=self.layout_var,
                command=self.on_layout_toggle,
            )
            self.layout_chk.pack(side="right", padx=6, pady=6)

            season_icon, season_name = get_season_display(get_current_season())
            self.seasonal_var = tk.BooleanVar(value=bool(getattr(self.config, "seasonal_theme_enabled", False)))
            self.seasonal_chk = tk.Checkbutton(
                settings_frame,
                text=f"{season_icon} {season_name}",
                variable=self.seasonal_var,
                command=self.on_seasonal_toggle,
            )
            self.seasonal_chk.pack(side="right", padx=6, pady=6)

        # Auto-Rotation Controls Bar
        rotate_frame = ctk.CTkFrame(main_parent) if HAS_CUSTOMTKINTER else tk.Frame(main_parent)
        rotate_frame.pack(fill="x", padx=16, pady=(2, 6))

        self.rotate_var = ctk.BooleanVar(value=bool(getattr(self.config, "rotation_enabled", False)))
        if HAS_CUSTOMTKINTER:
            self.rotate_chk = ctk.CTkCheckBox(
                rotate_frame,
                text="⏱️ Auto-Rotate",
                variable=self.rotate_var,
                font=ctk.CTkFont(size=12, weight="bold"),
                command=self.on_rotate_toggle,
            )
            self.rotate_chk.pack(side="left", padx=10, pady=6)
        else:
            self.rotate_chk = tk.Checkbutton(
                rotate_frame,
                text="⏱️ Auto-Rotate",
                variable=self.rotate_var,
                command=self.on_rotate_toggle,
            )
            self.rotate_chk.pack(side="left", padx=10, pady=6)

        curr_min = getattr(self.config, "rotation_interval_minutes", 180)
        curr_str = "30m" if curr_min == 30 else ("1h" if curr_min == 60 else ("daily" if curr_min >= 1440 else "3h"))

        if HAS_CUSTOMTKINTER:
            self.interval_var = ctk.StringVar(value=curr_str)
            self.interval_seg = ctk.CTkSegmentedButton(
                rotate_frame,
                values=["30m", "1h", "3h", "daily"],
                variable=self.interval_var,
                command=self.on_interval_change,
            )
            self.interval_seg.pack(side="left", padx=8, pady=6)

            self.rotate_now_btn = ctk.CTkButton(
                rotate_frame,
                text="🔄 Rotate Now",
                width=105,
                height=28,
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="#4f46e5",
                hover_color="#4338ca",
                command=self.on_rotate_now,
            )
            self.rotate_now_btn.pack(side="right", padx=10, pady=6)
        else:
            self.interval_var = tk.StringVar(value=curr_str)
            for iv_label in ["30m", "1h", "3h", "daily"]:
                rb = tk.Radiobutton(rotate_frame, text=iv_label, value=iv_label, variable=self.interval_var, command=self.on_interval_change)
                rb.pack(side="left", padx=4)

            self.rotate_now_btn = tk.Button(
                rotate_frame,
                text="🔄 Rotate Now",
                command=self.on_rotate_now,
            )
            self.rotate_now_btn.pack(side="right", padx=10, pady=6)

        # Preview Container
        self.preview_frame = ctk.CTkFrame(main_parent, height=155) if HAS_CUSTOMTKINTER else tk.Frame(main_parent, height=155, bg="black")
        self.preview_frame.pack(fill="x", padx=16, pady=(4, 4))
        self.preview_frame.pack_propagate(False)

        self.preview_label = (
            ctk.CTkLabel(self.preview_frame, text="Preview will appear here after selecting an option", font=ctk.CTkFont(size=12), text_color="gray")
            if HAS_CUSTOMTKINTER
            else tk.Label(self.preview_frame, text="Preview will appear here", fg="gray")
        )
        self.preview_label.pack(expand=True, fill="both")

        # Favorite and Star Rating Toolbar - Positioned directly below preview so it is NEVER cramped or cut off
        fav_rating_frame = ctk.CTkFrame(main_parent, fg_color="transparent") if HAS_CUSTOMTKINTER else tk.Frame(main_parent)
        fav_rating_frame.pack(fill="x", padx=16, pady=(3, 3))

        if HAS_CUSTOMTKINTER:
            self.fav_btn = ctk.CTkButton(
                fav_rating_frame,
                text="🤍 Favorite",
                width=110,
                height=30,
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="#374151",
                hover_color="#be185d",
                state="disabled",
                command=self.on_toggle_favorite,
            )
            self.fav_btn.pack(side="left")

            rating_lbl = ctk.CTkLabel(fav_rating_frame, text="Rating:", font=ctk.CTkFont(size=12, weight="bold"))
            rating_lbl.pack(side="left", padx=(14, 6))

            self.star_buttons = []
            for s in range(1, 6):
                s_btn = ctk.CTkButton(
                    fav_rating_frame,
                    text="★",
                    width=28,
                    height=28,
                    font=ctk.CTkFont(size=14, weight="bold"),
                    fg_color="#1f2937",
                    hover_color="#ca8a04",
                    text_color="#9ca3af",
                    state="disabled",
                    command=lambda star=s: self.on_set_rating(star),
                )
                s_btn.pack(side="left", padx=2)
                self.star_buttons.append(s_btn)

            self.lockscreen_btn = ctk.CTkButton(
                fav_rating_frame,
                text="🔒 Set as Lock Screen",
                height=30,
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="#4f46e5",
                hover_color="#4338ca",
                state="disabled",
                command=self.on_apply_lockscreen,
            )
            self.lockscreen_btn.pack(side="right")
        else:
            self.fav_btn = tk.Button(fav_rating_frame, text="🤍 Favorite", state="disabled", command=self.on_toggle_favorite)
            self.fav_btn.pack(side="left")

            rating_lbl = tk.Label(fav_rating_frame, text="Rating:")
            rating_lbl.pack(side="left", padx=(12, 4))

            self.star_buttons = []
            for s in range(1, 6):
                s_btn = tk.Button(fav_rating_frame, text="★", state="disabled", command=lambda star=s: self.on_set_rating(star))
                s_btn.pack(side="left", padx=1)
                self.star_buttons.append(s_btn)

            self.lockscreen_btn = tk.Button(
                fav_rating_frame,
                text="🔒 Set as Lock Screen",
                state="disabled",
                command=self.on_apply_lockscreen,
            )
            self.lockscreen_btn.pack(side="right")

        # Status & Progress Area
        status_frame = ctk.CTkFrame(main_parent, fg_color="transparent") if HAS_CUSTOMTKINTER else tk.Frame(main_parent)
        status_frame.pack(fill="x", padx=16, pady=(2, 2))

        self.status_lbl = (
            ctk.CTkLabel(status_frame, text="Ready. Click any category above.", font=ctk.CTkFont(size=12), wraplength=580, justify="left")
            if HAS_CUSTOMTKINTER
            else tk.Label(status_frame, text="Ready.", wraplength=580, justify="left")
        )
        self.status_lbl.pack(anchor="w")

        if HAS_CUSTOMTKINTER:
            self.progress_bar = ctk.CTkProgressBar(status_frame)
            self.progress_bar.pack(fill="x", pady=2)
            self.progress_bar.set(0)
        else:
            self.progress_bar = None

        # Attribution display
        self.attrib_lbl = (
            ctk.CTkLabel(
                main_parent,
                text="",
                font=ctk.CTkFont(size=11),
                text_color="gray",
                wraplength=580,
                justify="left",
            )
            if HAS_CUSTOMTKINTER
            else tk.Label(main_parent, text="", fg="gray", wraplength=580, justify="left")
        )
        self.attrib_lbl.pack(anchor="w", padx=16, pady=(2, 8))

    def set_status(self, text: str, progress: Optional[float] = None) -> None:
        """Update status label and optional progress bar from any thread."""
        print(f"[*] {text}", flush=True)
        def _update():
            if HAS_CUSTOMTKINTER:
                self.status_lbl.configure(text=text)
                if progress is not None and self.progress_bar:
                    self.progress_bar.set(progress)
            else:
                self.status_lbl.config(text=text)
        self.root.after(0, _update)

    def _update_category_buttons(self, active_category: Optional[WallpaperCategory] = None) -> None:
        """Highlight active category button and reset others to default unselected appearance."""
        if not hasattr(self, "cat_buttons"):
            return
        for cat, btn in self.cat_buttons.items():
            is_active = (cat == active_category)
            base_col = getattr(self, "_cat_colors", {}).get(cat, "#1f2937")
            if HAS_CUSTOMTKINTER:
                btn.configure(
                    border_width=2 if is_active else 0,
                    border_color="#38bdf8" if is_active else base_col,
                    fg_color="#2563eb" if is_active else base_col,
                )
            else:
                btn.config(
                    relief="sunken" if is_active else "raised",
                    bg="#2563eb" if is_active else "#f0f0f0",
                )

    def set_busy(self, busy: bool) -> None:
        self.is_busy = busy
        state = "disabled" if busy else "normal"
        def _update():
            if hasattr(self, "cat_buttons"):
                for cat, btn in self.cat_buttons.items():
                    if busy and self.current_category == cat:
                        btn.configure(state="normal") if HAS_CUSTOMTKINTER else btn.config(state="normal")
                    else:
                        btn.configure(state=state) if HAS_CUSTOMTKINTER else btn.config(state=state)
            if hasattr(self, "search_btn"):
                self.search_btn.configure(state=state) if HAS_CUSTOMTKINTER else self.search_btn.config(state=state)
            if hasattr(self, "clear_search_btn"):
                self.clear_search_btn.configure(state=state) if HAS_CUSTOMTKINTER else self.clear_search_btn.config(state=state)
            if hasattr(self, "search_entry"):
                self.search_entry.configure(state=state) if HAS_CUSTOMTKINTER else self.search_entry.config(state=state)
            if hasattr(self, "suggestion_buttons"):
                for sb in self.suggestion_buttons:
                    sb.configure(state=state) if HAS_CUSTOMTKINTER else sb.config(state=state)
            if hasattr(self, "retry_btn") and (self.current_keyword or self.current_category or self.selected_color != ColorPalette.ANY or self.selected_mood != WallpaperMood.ANY or getattr(self.config, "seasonal_theme_enabled", False) or self.staged_metadata or self.current_metadata) and self.current_category not in (WallpaperCategory.LOCAL_STORAGE, WallpaperCategory.FAVORITES):
                retry_state = "disabled" if busy else "normal"
                self.retry_btn.configure(state=retry_state) if HAS_CUSTOMTKINTER else self.retry_btn.config(state=retry_state)
            target_meta = self.staged_metadata or self.current_metadata
            if target_meta:
                action_state = "disabled" if busy else "normal"
                if hasattr(self, "save_btn"):
                    self.save_btn.configure(state=action_state) if HAS_CUSTOMTKINTER else self.save_btn.config(state=action_state)
                if hasattr(self, "fav_btn"):
                    self.fav_btn.configure(state=action_state) if HAS_CUSTOMTKINTER else self.fav_btn.config(state=action_state)
                if hasattr(self, "star_buttons"):
                    for sb in self.star_buttons:
                        sb.configure(state=action_state) if HAS_CUSTOMTKINTER else sb.config(state=action_state)
                if hasattr(self, "apply_btn") and self.staged_metadata and self.staged_metadata != self.current_metadata:
                    self.apply_btn.configure(state=action_state) if HAS_CUSTOMTKINTER else self.apply_btn.config(state=action_state)
                if hasattr(self, "lockscreen_btn"):
                    self.lockscreen_btn.configure(state=action_state) if HAS_CUSTOMTKINTER else self.lockscreen_btn.config(state=action_state)
        if hasattr(self, "root") and self.root:
            self.root.after(0, _update)
        else:
            _update()

    def on_mode_change(self, *args) -> None:
        new_mode = self.mode_var.get()
        self.config.default_position = new_mode
        self.config.save()
        target_meta = self.staged_metadata or self.current_metadata
        if target_meta:
            self._render_preview_image(target_meta, mode=new_mode)
            if self.config.preview_before_apply:
                self.set_status(f"Preview updated to {new_mode}. Click 'Apply to Desktop' to confirm.")
                if HAS_CUSTOMTKINTER:
                    self.apply_btn.configure(state="normal", text="✓ Apply to Desktop", fg_color="#2563eb")
                else:
                    self.apply_btn.config(state="normal", text="✓ Apply to Desktop")
            else:
                if Path(target_meta.local_path).exists():
                    self.adapter.set_wallpaper(Path(target_meta.local_path), mode=new_mode)
                    self.set_status(f"Updated display mode to {new_mode}.")

    def on_apply_lockscreen(self) -> None:
        """Apply the currently staged/previewed wallpaper to Windows Lock Screen."""
        target_meta = self.staged_metadata or self.current_metadata
        if not target_meta:
            self.set_status("No wallpaper available to set as Lock Screen.")
            return

        target_path = Path(target_meta.local_path)
        if not target_path.exists():
            self.set_status("Error: Wallpaper file not found on disk.")
            return

        self.set_busy(True)
        self.set_status("Applying wallpaper to Lock Screen...", progress=0.8)

        def _worker():
            success = self.adapter.set_lockscreen(target_path)
            if success:
                self.set_status(f"✓ Applied to Lock Screen: {target_meta.title}", progress=1.0)
                def _ui():
                    if HAS_CUSTOMTKINTER:
                        self.lockscreen_btn.configure(text="✓ Lock Screen Set!", fg_color="#059669", state="disabled")
                    else:
                        self.lockscreen_btn.config(text="✓ Lock Screen Set!", state="disabled")
                self.root.after(0, _ui)
            else:
                self.set_status("Error: Desktop adapter could not apply Lock Screen.")
            self.set_busy(False)

        threading.Thread(target=_worker, daemon=True).start()

    def on_lockscreen_toggle(self) -> None:
        """Compatibility alias for lock screen setting."""
        self.on_apply_lockscreen()

    def on_layout_toggle(self) -> None:
        """Handle toggling of desktop layout awareness."""
        enabled = self.layout_var.get()
        self.config.desktop_layout_awareness = enabled
        self.config.save()
        target_meta = self.staged_metadata or self.current_metadata
        if target_meta:
            self._render_preview_image(target_meta)
        status_text = "Layout Awareness: Enabled (Smart Crop away from desktop icons)" if enabled else "Layout Awareness: Disabled (Center Crop)"
        self.set_status(status_text)

    def on_seasonal_toggle(self) -> None:
        """Handle toggling of seasonal wallpaper themes."""
        enabled = self.seasonal_var.get()
        self.config.seasonal_theme_enabled = enabled
        self.config.save()
        icon, name = get_season_display(get_current_season())
        status_text = f"Seasonal Theme ({icon} {name}): Enabled" if enabled else "Seasonal Theme: Disabled"
        self.set_status(status_text)

        if enabled:
            # Category is NOT considered when seasonal theme is toggled
            self.current_category = None
            self._update_category_buttons(None)
            active_kw = self.search_entry.get().strip() if hasattr(self, "search_entry") else ""
            if active_kw:
                self.on_trigger_search(active_kw)
            else:
                self._fetch_random_wallpaper(color=self.selected_color, mood=self.selected_mood)

    def on_rotate_toggle(self) -> None:
        """Handle toggling of scheduled auto-rotation."""
        enabled = bool(self.rotate_var.get())
        self.config.rotation_enabled = enabled
        self.config.save()
        desc = f"Enabled ({self.config.rotation_interval_minutes}m interval)" if enabled else "Disabled"
        self.set_status(f"Auto-Rotation: {desc}.")
        if enabled:
            self._schedule_next_rotation_check(delay_ms=500)
        else:
            if self._rotation_timer_id and hasattr(self, "root") and self.root:
                try:
                    self.root.after_cancel(self._rotation_timer_id)
                except Exception:
                    pass
                self._rotation_timer_id = None

    def on_interval_change(self, val: str) -> None:
        """Handle change in rotation interval."""
        from ..core.scheduler import parse_interval_minutes, WallpaperRotationDaemon
        self.config.rotation_interval_minutes = parse_interval_minutes(val)
        self.config.save()
        daemon = WallpaperRotationDaemon(self.config, self.history, self.cache, self.router)
        rem = daemon.get_seconds_until_next_rotation()
        if rem <= 0.0 and self.config.rotation_enabled:
            self.set_status(f"Rotation interval: {self.config.rotation_interval_minutes}m. Rotation due now!")
            self._schedule_next_rotation_check(delay_ms=500)
        else:
            mins = int(rem // 60)
            secs = int(rem % 60)
            time_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
            self.set_status(f"Rotation interval: {self.config.rotation_interval_minutes}m (Next in {time_str}).")
            self._schedule_next_rotation_check(delay_ms=1000)

    def _schedule_next_rotation_check(self, delay_ms: int = 15000) -> None:
        """Schedule the next periodic rotation check."""
        if not hasattr(self, "root") or not self.root:
            return
        if self._rotation_timer_id:
            try:
                self.root.after_cancel(self._rotation_timer_id)
            except Exception:
                pass
            self._rotation_timer_id = None
        try:
            self._rotation_timer_id = self.root.after(delay_ms, self._check_rotation_schedule)
        except Exception:
            self._rotation_timer_id = None

    def _check_rotation_schedule(self) -> None:
        """Check if scheduled wallpaper rotation is due and execute if needed."""
        self._rotation_timer_id = None
        if not getattr(self.config, "rotation_enabled", False):
            # Check again periodically in case user enables it
            self._schedule_next_rotation_check(15000)
            return

        if self.is_busy or self._is_auto_rotating:
            # Busy performing manual fetch or rotation; defer check
            self._schedule_next_rotation_check(5000)
            return

        from ..core.scheduler import WallpaperRotationDaemon
        daemon = WallpaperRotationDaemon(self.config, self.history, self.cache, self.router)

        if daemon.is_rotation_due():
            self._perform_scheduled_auto_rotate()
        else:
            rem = daemon.get_seconds_until_next_rotation()
            delay_ms = max(5000, min(30000, int(rem * 1000)))
            self._schedule_next_rotation_check(delay_ms)

    def _perform_scheduled_auto_rotate(self) -> None:
        """Execute scheduled background wallpaper rotation without disturbing active manual previews."""
        if self._is_auto_rotating or self.is_busy:
            self._schedule_next_rotation_check(5000)
            return

        self._is_auto_rotating = True

        def _worker():
            from ..core.scheduler import WallpaperRotationDaemon
            daemon = WallpaperRotationDaemon(self.config, self.history, self.cache, self.router)

            color_filter = self.selected_color if self.selected_color != ColorPalette.ANY else None
            mood_filter = self.selected_mood if self.selected_mood != WallpaperMood.ANY else None

            meta, err = daemon.rotate_now(
                color=color_filter,
                mood=mood_filter,
            )

            def _on_done():
                self._is_auto_rotating = False
                if meta:
                    # Critical Rule: If user is actively previewing an image, do NOT overwrite their preview!
                    if self.staged_metadata is not None:
                        self.set_status(f"✓ Auto-rotated desktop: '{meta.title}' (Active manual preview preserved)")
                    else:
                        self.current_metadata = meta
                        self.set_status(f"✓ Auto-rotated desktop: '{meta.title}' ({meta.category})")
                        self._update_preview_and_attribution(meta, staged=False)
                else:
                    if err:
                        self.set_status(f"Scheduled auto-rotation skipped: {err}")
                self._schedule_next_rotation_check(15000)

            if hasattr(self, "root") and self.root:
                try:
                    self.root.after(0, _on_done)
                except Exception:
                    _on_done()
            else:
                _on_done()

        threading.Thread(target=_worker, daemon=True).start()

    def on_close_window(self) -> None:
        """Handle window close event for standalone dialog."""
        from .tray import SystemTrayManager
        if getattr(self.config, "rotation_enabled", False) and SystemTrayManager.is_available():
            self._minimize_to_tray()
        else:
            self.quit_app()

    def _minimize_to_tray(self) -> None:
        """Minimize standalone dialog to system tray."""
        from .tray import SystemTrayManager
        if not hasattr(self, "_tray_mgr") or self._tray_mgr is None:
            self._tray_mgr = SystemTrayManager(
                on_show=self._restore_from_tray,
                on_rotate_now=self.on_rotate_now,
                on_quit=self.quit_app,
                app_name="Login Wallpaper Selector",
            )
        self.root.withdraw()
        if self._tray_mgr.start():
            self._tray_mgr.notify(
                "Running in background. Desktop wallpaper will continue rotating automatically.",
                "Login Wallpaper Selector",
            )

    def _restore_from_tray(self) -> None:
        """Restore standalone dialog from system tray."""
        def _do_restore():
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
            if hasattr(self, "_tray_mgr") and self._tray_mgr:
                self._tray_mgr.stop()
        if hasattr(self, "root") and self.root:
            self.root.after(0, _do_restore)

    def quit_app(self) -> None:
        """Cleanly exit application and cancel timers."""
        self.cleanup()
        if hasattr(self, "root") and self.root:
            try:
                self.root.destroy()
            except Exception:
                pass

    def cleanup(self) -> None:
        """Cancel pending rotation timers and cleanup system tray icon."""
        if hasattr(self, "root") and self.root and self._rotation_timer_id:
            try:
                self.root.after_cancel(self._rotation_timer_id)
            except Exception:
                pass
            self._rotation_timer_id = None
        if hasattr(self, "_tray_mgr") and self._tray_mgr:
            try:
                self._tray_mgr.stop()
            except Exception:
                pass
            self._tray_mgr = None

    def on_rotate_now(self) -> None:
        """Trigger an instant wallpaper rotation in background worker thread."""
        if self.is_busy:
            return

        self.set_busy(True)
        self.set_status("Rotating wallpaper now...", progress=0.1)

        def _worker():
            from ..core.scheduler import WallpaperRotationDaemon
            daemon = WallpaperRotationDaemon(self.config, self.history, self.cache, self.router)

            def _progress(downloaded: int, total: int):
                frac = min(0.9, 0.2 + (downloaded / total) * 0.7) if total > 0 else 0.5
                kb = downloaded // 1024
                self.set_status(f"Rotating wallpaper ({kb} KB)...", progress=frac)

            def _status(msg: str, attempt: int, total_attempts: int):
                self.set_status(f"[{attempt}/{total_attempts}] {msg}", progress=0.1 * attempt)

            meta, err = daemon.rotate_now(
                color=self.selected_color,
                mood=self.selected_mood,
                progress_callback=_progress,
                status_callback=_status,
            )

            if meta:
                self.current_metadata = meta
                self.set_status(f"✓ Rotated to: {meta.title} ({meta.category})", progress=1.0)
                self._update_preview_and_attribution(meta)
            else:
                self.set_status(f"Rotation failed: {err}")
            self.set_busy(False)

        threading.Thread(target=_worker, daemon=True).start()

    def on_select_color(self, palette: ColorPalette) -> None:
        """Handle user selection of dominant color palette."""
        self.selected_color = palette
        palette_colors = {
            ColorPalette.ANY: "#374151",
            ColorPalette.BLUE: "#0284c7",
            ColorPalette.PURPLE: "#a855f7",
            ColorPalette.GREEN: "#10b981",
            ColorPalette.WARM: "#ea580c",
            ColorPalette.MONOCHROME: "#27272a",
        }
        for pal, chip in self.color_chips.items():
            is_active = (pal == palette)
            if HAS_CUSTOMTKINTER:
                chip.configure(
                    border_width=2 if is_active else 0,
                    fg_color=palette_colors.get(pal, "#374151") if is_active else "#1f2937",
                )
        desc = "No color filter" if palette == ColorPalette.ANY else f"{palette.value} color filter"
        self.set_status(f"Palette updated: {desc}.")

        # Category is NOT considered when color is selected
        self.current_category = None
        self._update_category_buttons(None)

        # Trigger wallpaper acquisition: if search term exists, search with new color; otherwise fetch random image
        active_kw = self.search_entry.get().strip() if hasattr(self, "search_entry") else ""
        if active_kw:
            self.on_trigger_search(active_kw)
        else:
            self._fetch_random_wallpaper(color=palette, mood=self.selected_mood)

    def on_select_mood(self, mood: WallpaperMood) -> None:
        """Handle user selection of mood/aesthetic vibe."""
        self.selected_mood = mood
        mood_colors = {
            WallpaperMood.ANY: "#374151",
            WallpaperMood.PEACEFUL: "#0d9488",
            WallpaperMood.DARK: "#18181b",
            WallpaperMood.CINEMATIC: "#4f46e5",
            WallpaperMood.MINIMALIST: "#52525b",
            WallpaperMood.VIBRANT: "#d97706",
        }
        for m, chip in self.mood_chips.items():
            is_active = (m == mood)
            if HAS_CUSTOMTKINTER:
                chip.configure(
                    border_width=2 if is_active else 0,
                    fg_color=mood_colors.get(m, "#374151") if is_active else "#1f2937",
                )
        desc = "No mood filter" if mood == WallpaperMood.ANY else f"{mood.value} mood"
        self.set_status(f"Mood updated: {desc}.")

        # Category is NOT considered when mood is selected
        self.current_category = None
        self._update_category_buttons(None)

        # Trigger wallpaper acquisition: if search term exists, search with new mood; otherwise fetch random image
        active_kw = self.search_entry.get().strip() if hasattr(self, "search_entry") else ""
        if active_kw:
            self.on_trigger_search(active_kw)
        else:
            self._fetch_random_wallpaper(color=self.selected_color, mood=mood)

    def on_save_wallpaper(self) -> None:
        """Save the active wallpaper permanently to category's Saved folder."""
        target_meta = self.staged_metadata or self.current_metadata
        if not target_meta:
            return

        saved_path, err = self.cache.save_wallpaper_to_category(target_meta)
        if saved_path:
            self.saved_category_folder = saved_path.parent
            if HAS_CUSTOMTKINTER:
                self.save_btn.configure(text="✓ Saved!", state="disabled")
                self.open_folder_btn.configure(state="normal")
            else:
                self.save_btn.config(text="✓ Saved!", state="disabled")
                self.open_folder_btn.config(state="normal")
            self.set_status(f"✓ Saved to {saved_path.parent.name}/{saved_path.name}")
        else:
            self.set_status(f"Could not save wallpaper: {err}")

    def on_open_category_folder(self) -> None:
        """Open the category's Saved directory in Windows File Explorer."""
        folder = getattr(self, "saved_category_folder", None)
        target_meta = self.staged_metadata or self.current_metadata
        if not folder and target_meta:
            folder = self.cache.get_category_dir(target_meta.category) / "Saved"
            if not folder.exists():
                folder = self.cache.get_category_dir(target_meta.category)

        if folder and folder.exists():
            try:
                import os
                os.startfile(folder)
            except Exception:
                import subprocess
                subprocess.Popen(["explorer", str(folder)])

    def on_select_category(self, category: WallpaperCategory) -> None:
        # Toggle button behavior: if clicking the active category, toggle it OFF and cancel any in-flight fetch
        if self.current_category == category:
            self._current_search_id += 1
            self.current_category = None
            self._update_category_buttons(None)
            self._populate_suggestion_chips(None)
            self.set_busy(False)
            self.set_status(f"Category {category.value} toggled off.")
            return

        if self.is_busy:
            return

        # Explicit category selected: clear search entry to focus on category
        if hasattr(self, "search_entry"):
            self.search_entry.delete(0, tk.END)
        self.current_keyword = ""

        # Toggle category ON
        self.current_category = category
        self._update_category_buttons(category)
        self._populate_suggestion_chips(category)
        if category == WallpaperCategory.LOCAL_STORAGE:
            self._handle_local_storage()
        elif category == WallpaperCategory.FAVORITES:
            self._handle_favorites_category()
        else:
            self._handle_online_category(category)

    def _handle_favorites_category(self) -> None:
        """Handle selecting and cycling among favorited wallpapers."""
        fav = self.favorites_mgr.get_random_favorite()
        if not fav:
            self.current_category = None
            self._update_category_buttons(None)
            self.set_status("⭐ No favorites saved yet! Click ❤️ Favorite on wallpapers you like.")
            return

        fav_path = Path(fav.saved_path or fav.local_path)
        if not fav_path.exists():
            self.current_category = None
            self._update_category_buttons(None)
            self.set_status(f"Favorite image not found on disk: {fav.title}")
            return

        self._current_search_id += 1
        fetch_id = self._current_search_id
        self.set_busy(True)
        self.set_status(f"Loading favorite: {fav.title}...")

        def _worker():
            mode = self.mode_var.get()
            meta = self.cache.store_local_image(fav_path, mode=mode)
            if self._current_search_id != fetch_id:
                return

            if not meta:
                meta = WallpaperMetadata(
                    image_id=fav.image_id,
                    category="Favorites",
                    provider=fav.provider or "Favorites",
                    source_url="",
                    download_url="",
                    local_path=str(fav_path),
                    sha256="",
                    title=fav.title,
                    creator="",
                    license="",
                    license_url=None,
                    attribution_required=False,
                    attribution_text=f"Favorite: {fav.title}",
                    width=1920,
                    height=1080,
                    aspect_ratio=1.778,
                    mode=mode,
                    dominant_color_hex=fav.dominant_color_hex,
                    mood=fav.mood,
                    is_favorite=True,
                    rating=fav.rating,
                )
            else:
                meta.title = fav.title
                meta.category = "Favorites"
                meta.is_favorite = True
                meta.rating = fav.rating

            if self.config.preview_before_apply:
                self.staged_metadata = meta
                self.set_status(f"✓ Previewing favorite: {fav.title}. Click 'Apply to Desktop' to set.", progress=1.0)
                self._update_preview_and_attribution(meta, staged=True)
            else:
                success = self.adapter.set_wallpaper(Path(meta.local_path), mode=mode)
                if success:
                    lock_msg = ""
                    if self.lockscreen_var.get():
                        lock_ok = self.adapter.set_lockscreen(Path(meta.local_path))
                        if lock_ok:
                            lock_msg = " & Lock Screen"
                    self.current_metadata = meta
                    self.set_status(f"✓ Applied favorite{lock_msg}: {fav.title}", progress=1.0)
                    self._update_preview_and_attribution(meta, staged=False)
                else:
                    self.set_status("Failed to apply favorite wallpaper via adapter.")

            # Crucial: Category toggle automatically turns OFF after loading
            self.current_category = None
            if hasattr(self, "root") and self.root:
                self.root.after(0, lambda: self._update_category_buttons(None))

            self.set_busy(False)

        threading.Thread(target=_worker, daemon=True).start()

    def on_toggle_favorite(self) -> None:
        """Handle toggling of favorite status for currently active wallpaper."""
        target_meta = self.staged_metadata or self.current_metadata
        if not target_meta:
            return
        is_fav = self.favorites_mgr.toggle_favorite(target_meta)
        target_meta.is_favorite = is_fav
        if HAS_CUSTOMTKINTER:
            self.fav_btn.configure(
                text="❤️ Favorited" if is_fav else "🤍 Favorite",
                fg_color="#9d174d" if is_fav else "#374151",
            )
        else:
            self.fav_btn.config(text="❤️ Favorited" if is_fav else "🤍 Favorite")
        status = "Added to Favorites ❤️" if is_fav else "Removed from Favorites"
        self.set_status(f"{status}: {target_meta.title}")

    def on_set_rating(self, rating: int) -> None:
        """Handle setting or toggling 1-5 star rating for current wallpaper."""
        target_meta = self.staged_metadata or self.current_metadata
        if not target_meta:
            return
        curr = self.favorites_mgr.get_rating(target_meta.image_id)
        new_rating = 0 if curr == rating else rating
        self.favorites_mgr.set_rating(target_meta.image_id, new_rating, target_meta)
        target_meta.rating = new_rating
        for idx, star_btn in enumerate(self.star_buttons):
            is_active = (idx < new_rating)
            if HAS_CUSTOMTKINTER:
                star_btn.configure(
                    fg_color="#ca8a04" if is_active else "#1f2937",
                    text_color="#fef08a" if is_active else "#9ca3af",
                )
            else:
                star_btn.config(bg="#ca8a04" if is_active else "#ddd")
        stars_str = ("★" * new_rating) if new_rating > 0 else "cleared"
        self.set_status(f"Rating {stars_str} recorded for {target_meta.title}")

    def _handle_local_storage(self) -> None:
        self.set_status("Opening native file picker...")
        selected_path = pick_local_image(self.root)

        if not selected_path:
            # User canceled the file picker
            self.current_category = None
            self._update_category_buttons(None)
            self.set_status("Local file selection cancelled.")
            return

        self._current_search_id += 1
        fetch_id = self._current_search_id
        self.set_busy(True)
        self.set_status(f"Validating {selected_path.name}...")

        def _worker():
            mode = self.mode_var.get()
            meta = self.cache.store_local_image(selected_path, mode=mode)
            if self._current_search_id != fetch_id:
                return

            if meta:
                if self.config.preview_before_apply:
                    self.staged_metadata = meta
                    self.set_status(f"✓ Previewing local image: {selected_path.name}. Click 'Apply to Desktop' to set.", progress=1.0)
                    self._update_preview_and_attribution(meta, staged=True)
                else:
                    success = self.adapter.set_wallpaper(Path(meta.local_path), mode=mode)
                    if success:
                        lock_msg = ""
                        if self.lockscreen_var.get():
                            lock_ok = self.adapter.set_lockscreen(Path(meta.local_path))
                            if lock_ok:
                                lock_msg = " & Lock Screen"

                        self.current_metadata = meta
                        self.set_status(f"✓ Applied local wallpaper{lock_msg}: {selected_path.name}", progress=1.0)
                        self._update_preview_and_attribution(meta, staged=False)
                    else:
                        self.set_status("Failed to apply wallpaper through desktop adapter.")
            else:
                self.set_status("Error: Selected file is corrupted or not a valid image.")

            # Crucial: Category toggle automatically turns OFF after loading
            self.current_category = None
            if hasattr(self, "root") and self.root:
                self.root.after(0, lambda: self._update_category_buttons(None))

            self.set_busy(False)

        threading.Thread(target=_worker, daemon=True).start()

    def _handle_online_category(self, category: WallpaperCategory) -> None:
        self._current_search_id += 1
        fetch_id = self._current_search_id
        self.set_busy(True)
        self.set_status(f"Searching for {category.value} wallpaper...", progress=0.05)

        def _worker():
            def _progress(downloaded: int, total: int):
                if self._current_search_id != fetch_id:
                    return
                frac = min(0.9, 0.2 + (downloaded / total) * 0.7) if total > 0 else 0.5
                kb = downloaded // 1024
                self.set_status(f"Downloading {category.value} ({kb} KB)...", progress=frac)

            def _status(msg: str, attempt: int, total_attempts: int):
                if self._current_search_id != fetch_id:
                    return
                self.set_status(f"[{attempt}/{total_attempts}] {msg}", progress=0.1 * attempt)

            mode = self.mode_var.get()
            meta, err = self.router.acquire_wallpaper_for_category(
                category,
                mode=mode,
                progress_callback=_progress,
                status_callback=_status,
                color=self.selected_color,
                mood=self.selected_mood,
            )

            if self._current_search_id != fetch_id:
                return

            if meta:
                self.staged_metadata = meta
                if self.config.preview_before_apply:
                    self.set_status(f"✓ Previewing {category.value}: {meta.title}. Click 'Apply to Desktop' to set.", progress=1.0)
                    self._update_preview_and_attribution(meta, staged=True)
                else:
                    self.set_status("Applying wallpaper to desktop...", progress=0.95)
                    success = self.adapter.set_wallpaper(Path(meta.local_path), mode=mode)
                    if success:
                        lock_msg = ""
                        if self.lockscreen_var.get():
                            lock_ok = self.adapter.set_lockscreen(Path(meta.local_path))
                            if lock_ok:
                                lock_msg = " & Lock Screen"

                        self.current_metadata = meta
                        self.set_status(f"✓ Applied {category.value} wallpaper{lock_msg}: {meta.title}", progress=1.0)
                        self._update_preview_and_attribution(meta, staged=False)
                    else:
                        self.set_status("Download succeeded, but desktop adapter could not set wallpaper.")
            else:
                # Fallback to cached wallpaper if available
                fallback = self.cache.get_fallback_wallpaper()
                if fallback:
                    fallback_meta = self.cache.store_local_image(fallback, mode=mode)
                    if fallback_meta:
                        self.staged_metadata = fallback_meta
                        if self.config.preview_before_apply:
                            self.set_status(f"Online search failed ({err}). Previewing cached wallpaper.", progress=1.0)
                            self._update_preview_and_attribution(fallback_meta, staged=True)
                        else:
                            self.adapter.set_wallpaper(fallback, mode=mode)
                            self.current_metadata = fallback_meta
                            self.set_status(f"Online search failed ({err}). Using previously cached wallpaper.", progress=1.0)
                            self._update_preview_and_attribution(fallback_meta, staged=False)
                    else:
                        self.adapter.set_wallpaper(fallback, mode=mode)
                        self.set_status(f"Online search failed ({err}). Using previously cached wallpaper.", progress=1.0)
                else:
                    self.set_status(f"Error: {err}", progress=0.0)

            # Crucial: Category toggle automatically turns OFF after use so no category remains selected
            self.current_category = None
            if hasattr(self, "root") and self.root:
                self.root.after(0, lambda: self._update_category_buttons(None))

            self.set_busy(False)

        threading.Thread(target=_worker, daemon=True).start()

    def on_apply_staged(self) -> None:
        """Apply the currently staged/previewed wallpaper to desktop & optional lock screen."""
        target_meta = self.staged_metadata or self.current_metadata
        if not target_meta:
            return

        target_path = Path(target_meta.local_path)
        if not target_path.exists():
            self.set_status("Error: Wallpaper file not found on disk.")
            return

        mode = self.mode_var.get()
        self.set_busy(True)
        self.set_status("Applying wallpaper to desktop...", progress=0.8)

        def _worker():
            success = self.adapter.set_wallpaper(target_path, mode=mode)
            if success:
                self.current_metadata = target_meta
                self.staged_metadata = None
                self.set_status(f"✓ Applied wallpaper: {target_meta.title} ({mode})", progress=1.0)

                def _ui_update():
                    if hasattr(self, "apply_btn"):
                        if HAS_CUSTOMTKINTER:
                            self.apply_btn.configure(text="✓ Applied!", fg_color="#059669", state="disabled")
                        else:
                            self.apply_btn.config(text="✓ Applied!", state="disabled")
                if hasattr(self, "root") and self.root:
                    self.root.after(0, _ui_update)
                else:
                    _ui_update()
            else:
                self.set_status("Error: Desktop adapter could not apply wallpaper.")
            self.set_busy(False)

        threading.Thread(target=_worker, daemon=True).start()

    def _render_preview_image(self, meta: WallpaperMetadata, mode: Optional[str] = None) -> None:
        """Render desktop screen-fit and cropping preview mockup for current or staged image."""
        local_path = Path(meta.local_path)
        if not local_path.exists():
            return
        m = mode or self.mode_var.get()
        try:
            target_w = 540
            if hasattr(self, "root") and hasattr(self.root, "winfo_width"):
                try:
                    cur_w = self.root.winfo_width()
                    if cur_w > 200:
                        target_w = min(580, max(400, cur_w - 70))
                except Exception:
                    target_w = 540

            preview_img = generate_desktop_preview_image(
                local_path,
                mode=m,
                max_preview_width=target_w,
                max_preview_height=150,
                layout_aware=bool(self.layout_var.get()),
                draw_mockup_frame=True,
            )
            if not preview_img:
                img = Image.open(local_path)
                img.thumbnail((target_w, 150), Image.Resampling.LANCZOS)
                preview_img = img

            if HAS_CUSTOMTKINTER:
                ctk_img = ctk.CTkImage(light_image=preview_img, dark_image=preview_img, size=preview_img.size)
                self.preview_label.configure(image=ctk_img, text="")
                self.preview_label.image = ctk_img
            else:
                from PIL import ImageTk
                tk_img = ImageTk.PhotoImage(preview_img)
                self.preview_label.config(image=tk_img, text="")
                self.preview_label.image = tk_img
        except Exception:
            pass

    def _update_preview_and_attribution(self, meta: WallpaperMetadata, staged: bool = False) -> None:
        def _update():
            # Enable actions
            is_fav = self.favorites_mgr.is_favorite(meta.image_id)
            rating = self.favorites_mgr.get_rating(meta.image_id)

            if HAS_CUSTOMTKINTER:
                self.retry_btn.configure(state="normal")
                self.save_btn.configure(state="normal", text="💾 Save Image")
                self.open_folder_btn.configure(state="disabled")
                self.fav_btn.configure(
                    state="normal",
                    text="❤️ Favorited" if is_fav else "🤍 Favorite",
                    fg_color="#9d174d" if is_fav else "#374151",
                )
                for idx, star_btn in enumerate(self.star_buttons):
                    is_active = (idx < rating)
                    star_btn.configure(
                        state="normal",
                        fg_color="#ca8a04" if is_active else "#1f2937",
                        text_color="#fef08a" if is_active else "#9ca3af",
                    )
                if hasattr(self, "lockscreen_btn"):
                    self.lockscreen_btn.configure(
                        state="normal",
                        text="🔒 Set as Lock Screen",
                        fg_color="#4f46e5",
                    )
                if staged:
                    self.apply_btn.configure(state="normal", text="✓ Apply to Desktop", fg_color="#2563eb")
                else:
                    self.apply_btn.configure(state="disabled", text="✓ Applied!", fg_color="#059669")
            else:
                self.retry_btn.config(state="normal")
                self.save_btn.config(state="normal", text="💾 Save Image")
                self.open_folder_btn.config(state="disabled")
                self.fav_btn.config(
                    state="normal",
                    text="❤️ Favorited" if is_fav else "🤍 Favorite",
                )
                for idx, star_btn in enumerate(self.star_buttons):
                    is_active = (idx < rating)
                    star_btn.config(state="normal", bg="#ca8a04" if is_active else "#ddd")
                if hasattr(self, "lockscreen_btn"):
                    self.lockscreen_btn.config(
                        state="normal",
                        text="🔒 Set as Lock Screen",
                    )
                if staged:
                    self.apply_btn.config(state="normal", text="✓ Apply to Desktop")
                else:
                    self.apply_btn.config(state="disabled", text="✓ Applied!")

            # Update attribution text
            attr_text = meta.attribution_text or f"{meta.title} ({meta.provider})"
            if getattr(meta, "license", None):
                attr_text += f"\nLicense: {meta.license}"
            if getattr(meta, "width", 0) and getattr(meta, "height", 0):
                attr_text += f" | {meta.width}x{meta.height}"

            if HAS_CUSTOMTKINTER:
                self.attrib_lbl.configure(text=attr_text)
            else:
                self.attrib_lbl.config(text=attr_text)

            # Render preview image mockup
            self._render_preview_image(meta)

        self.root.after(0, _update)

    def _populate_suggestion_chips(self, category: Optional[WallpaperCategory] = None) -> None:
        """Populate clickable keyword suggestion pills beneath the search bar."""
        if not hasattr(self, "suggestions_frame"):
            return
        for child in self.suggestions_frame.winfo_children():
            child.destroy()
        self.suggestion_buttons = []

        hint_lbl = (
            ctk.CTkLabel(self.suggestions_frame, text="💡 Try:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#9ca3af")
            if HAS_CUSTOMTKINTER
            else tk.Label(self.suggestions_frame, text="💡 Try:", font=("Helvetica", 9, "bold"), fg="gray")
        )
        hint_lbl.pack(side="left", padx=(2, 6))

        suggestions = self.search_history_mgr.get_suggestions(category, limit=5)
        for kw in suggestions:
            if HAS_CUSTOMTKINTER:
                btn = ctk.CTkButton(
                    self.suggestions_frame,
                    text=kw,
                    height=22,
                    font=ctk.CTkFont(size=11),
                    fg_color="#1f2937",
                    hover_color="#374151",
                    text_color="#e5e7eb",
                    corner_radius=11,
                )
                btn.configure(command=lambda q=kw, b=btn: self._on_suggestion_click(q, b))
                btn.pack(side="left", padx=2)
            else:
                btn = tk.Button(
                    self.suggestions_frame,
                    text=kw,
                    font=("Helvetica", 8),
                )
                btn.config(command=lambda q=kw, b=btn: self._on_suggestion_click(q, b))
                btn.pack(side="left", padx=2)
            self.suggestion_buttons.append(btn)

    def _on_suggestion_click(self, query: str, chip_btn: Optional[Any] = None) -> None:
        """Handle click on a suggestion chip: clear search bar and search directly without typing into it."""
        if self.is_busy:
            return
        if hasattr(self, "search_entry"):
            self.search_entry.delete(0, tk.END)

        if chip_btn:
            if HAS_CUSTOMTKINTER:
                chip_btn.configure(border_width=2, border_color="#38bdf8", fg_color="#2563eb")
            else:
                chip_btn.config(relief="sunken", bg="#2563eb")

        self.on_trigger_search(query)

    def _fetch_random_wallpaper(
        self,
        color: Optional[ColorPalette] = None,
        mood: Optional[WallpaperMood] = None,
    ) -> None:
        """Fetch a random wallpaper matching selected color, mood, and seasonal filters across all providers without category restriction."""
        if self.is_busy:
            return

        # Ensure all category toggles are OFF
        self.current_category = None
        self._update_category_buttons(None)

        self._current_search_id += 1
        fetch_id = self._current_search_id

        self.set_busy(True)
        color = color if color is not None else self.selected_color
        mood = mood if mood is not None else self.selected_mood
        active_season = get_current_season() if getattr(self.config, "seasonal_theme_enabled", False) else None

        mood_str = f" [{mood.value}]" if mood and mood != WallpaperMood.ANY else ""
        col_str = f" ({color.value})" if color and color != ColorPalette.ANY else ""
        season_str = f" ({get_season_display(active_season)[0]} {active_season.value})" if active_season else ""

        self.set_status(f"Finding random{season_str}{mood_str}{col_str} wallpaper...", progress=0.05)

        def _worker():
            def _progress(downloaded: int, total: int):
                if self._current_search_id != fetch_id:
                    return
                frac = min(0.9, 0.2 + (downloaded / total) * 0.7) if total > 0 else 0.5
                kb = downloaded // 1024
                self.set_status(f"Downloading wallpaper ({kb} KB)...", progress=frac)

            def _status(msg: str, attempt: int, total_attempts: int):
                if self._current_search_id != fetch_id:
                    return
                self.set_status(f"[{attempt}/{total_attempts}] {msg}", progress=0.1 * attempt)

            mode = self.mode_var.get() if hasattr(self, "mode_var") else getattr(self.config, "default_position", "Fill")
            meta, err = self.router.acquire_wallpaper_for_category(
                category=None,
                mode=mode,
                progress_callback=_progress,
                status_callback=_status,
                color=color,
                mood=mood,
                season=active_season,
            )

            if self._current_search_id != fetch_id:
                return

            if meta:
                self.staged_metadata = meta
                if self.config.preview_before_apply:
                    self.set_status(f"✓ Previewing: {meta.title}. Click 'Apply to Desktop' to set.", progress=1.0)
                    self._update_preview_and_attribution(meta, staged=True)
                else:
                    self.set_status("Applying wallpaper to desktop...", progress=0.95)
                    success = self.adapter.set_wallpaper(Path(meta.local_path), mode=mode)
                    if success:
                        lock_msg = ""
                        if self.lockscreen_var.get():
                            lock_ok = self.adapter.set_lockscreen(Path(meta.local_path))
                            if lock_ok:
                                lock_msg = " & Lock Screen"
                        self.current_metadata = meta
                        self.set_status(f"✓ Applied wallpaper{lock_msg}: {meta.title}", progress=1.0)
                        self._update_preview_and_attribution(meta, staged=False)
                    else:
                        self.set_status("Download succeeded, but desktop adapter could not set wallpaper.")
            else:
                self.set_status(f"Could not find wallpaper: {err}", progress=0.0)

            # Ensure all category toggles remain OFF
            self.current_category = None
            if hasattr(self, "root") and self.root:
                self.root.after(0, lambda: self._update_category_buttons(None))

            self.set_busy(False)

        threading.Thread(target=_worker, daemon=True).start()

    def on_trigger_search(self, query: Optional[str] = None) -> None:
        """Initiate custom keyword search across all providers without category restriction."""
        if query is None:
            query = self.search_entry.get().strip() if hasattr(self, "search_entry") else ""

        if not query:
            # Preserve blank search behavior: run standard category workflow if explicitly selected, else random
            if self.current_category and self.current_category not in (WallpaperCategory.LOCAL_STORAGE, WallpaperCategory.FAVORITES):
                self._handle_online_category(self.current_category)
            else:
                self._fetch_random_wallpaper(color=self.selected_color, mood=self.selected_mood)
            return

        if self.is_busy:
            return

        # Crucial: category is NOT considered when search terms are entered
        self.current_category = None
        self._update_category_buttons(None)

        self._current_search_id += 1
        search_id = self._current_search_id
        self.current_keyword = query

        self.set_busy(True)
        self.set_status(f"Searching for '{query}' wallpaper...", progress=0.05)

        def _worker():
            def _progress(downloaded: int, total: int):
                if self._current_search_id != search_id:
                    return
                frac = min(0.9, 0.2 + (downloaded / total) * 0.7) if total > 0 else 0.5
                kb = downloaded // 1024
                self.set_status(f"Downloading '{query}' ({kb} KB)...", progress=frac)

            def _status(msg: str, attempt: int, total_attempts: int):
                if self._current_search_id != search_id:
                    return
                self.set_status(f"[{attempt}/{total_attempts}] {msg}", progress=0.1 * attempt)

            mode = self.mode_var.get() if hasattr(self, "mode_var") else getattr(self.config, "default_position", "Fill")
            meta, err = self.router.acquire_wallpaper_for_category(
                category=None,
                mode=mode,
                progress_callback=_progress,
                status_callback=_status,
                color=self.selected_color,
                mood=self.selected_mood,
                keyword=query,
            )

            if self._current_search_id != search_id:
                # Obsolete search result; discarded
                return

            if meta:
                self.search_history_mgr.record_search(query, "Search", success=True, metadata=meta)
                self.staged_metadata = meta
                if self.config.preview_before_apply:
                    self.set_status(f"✓ Found '{query}': {meta.title}. Click 'Apply to Desktop' to set.", progress=1.0)
                    self._update_preview_and_attribution(meta, staged=True)
                else:
                    self.set_status(f"Applying '{query}' to desktop...", progress=0.95)
                    success = self.adapter.set_wallpaper(Path(meta.local_path), mode=mode)
                    if success:
                        lock_msg = ""
                        if self.lockscreen_var.get():
                            lock_ok = self.adapter.set_lockscreen(Path(meta.local_path))
                            if lock_ok:
                                lock_msg = " & Lock Screen"
                        self.current_metadata = meta
                        self.set_status(f"✓ Applied '{query}' wallpaper{lock_msg}: {meta.title}", progress=1.0)
                        self._update_preview_and_attribution(meta, staged=False)
                    else:
                        self.set_status("Download succeeded, but desktop adapter could not set wallpaper.")
            else:
                self.search_history_mgr.record_search(query, "Search", success=False)
                # Strict keyword search: never silently replace with an unrelated cached category image
                self.set_status(f"Search failed: {err}", progress=0.0)

            self.set_busy(False)
            if hasattr(self, "root") and self.root:
                self.root.after(0, lambda: self._populate_suggestion_chips(None))

        threading.Thread(target=_worker, daemon=True).start()

    def on_clear_search(self) -> None:
        """Clear search entry and restore default suggestions without resetting current preview."""
        if hasattr(self, "search_entry"):
            self.search_entry.delete(0, tk.END)
        self.current_keyword = ""
        self._populate_suggestion_chips(self.current_category)
        self.set_status("Search input cleared.")

    def on_retry(self) -> None:
        active_kw = self.search_entry.get().strip() if hasattr(self, "search_entry") else ""
        if active_kw:
            self.on_trigger_search(active_kw)
        elif self.current_category and self.current_category != WallpaperCategory.LOCAL_STORAGE:
            self._handle_online_category(self.current_category)
        else:
            self._fetch_random_wallpaper(color=self.selected_color, mood=self.selected_mood)

    def _check_for_updates_startup(self) -> None:
        """Asynchronously check for updates in background on app startup."""
        def _worker():
            try:
                res = check_for_updates(self.config, force=False)
                if res.update_available:
                    self.root.after(0, lambda: self._show_update_modal(res))
            except Exception:
                pass
        threading.Thread(target=_worker, daemon=True).start()

    def _show_update_modal(self, update_info: UpdateCheckResult) -> None:
        """Display the in-app update prompt modal."""
        try:
            UpdateModalDialog(self.root, update_info)
        except Exception:
            pass

    def on_manual_check_update(self) -> None:
        """Manually trigger update check from the GUI header."""
        self.set_status("Checking GitHub for updates...")
        def _worker():
            res = check_for_updates(self.config, force=True)
            if res.update_available:
                self.root.after(0, lambda: self._show_update_modal(res))
                self.set_status(f"🚀 New update available: v{res.latest_version}!")
            elif res.error and "No releases found" not in res.error and "Throttled" not in res.error:
                self.set_status(f"Update check: {res.error}")
            else:
                self.set_status(f"✓ You are running the latest version (v{res.current_version}).")
        threading.Thread(target=_worker, daemon=True).start()

    def on_close(self) -> None:
        if self.parent_frame is not None:
            # Embedded in suite shell: close toplevel if present
            if hasattr(self, "root") and self.root:
                try:
                    self.root.destroy()
                except Exception:
                    pass
            return
        if hasattr(self, "root") and self.root:
            self.root.destroy()

    def run(self) -> None:
        """Run the main GUI loop."""
        if hasattr(self, "root") and self.root:
            self.root.mainloop()
