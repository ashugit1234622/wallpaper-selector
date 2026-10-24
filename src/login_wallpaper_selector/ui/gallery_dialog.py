"""Wallpaper Archive and Favorites Gallery Dialog with Lightbox Viewer.

Provides a Windows 11 Fluent styled modal grid gallery displaying recent wallpaper
history and saved favorites with instant keyword search, lightbox zoom, and 1-click apply.
"""

from __future__ import annotations
import os
import subprocess
from pathlib import Path
from typing import Optional, Callable, List, Any, Dict
from PIL import Image

try:
    import customtkinter as ctk
    HAS_CUSTOMTKINTER = True
except ImportError:
    import tkinter as ctk
    HAS_CUSTOMTKINTER = False

import tkinter as tk
from tkinter import messagebox

from ..core.config import AppConfig
from ..core.favorites import FavoritesManager, FavoriteRecord
from ..core.recent_history import RecentWallpaperManager
from ..core.history import HistoryTracker
from ..core.models import WallpaperMetadata

# Windows 11 Fluent dark tokens
_W11 = {
    "surface_0":  "#202020",
    "surface_1":  "#2b2b2b",
    "surface_2":  "#333333",
    "surface_3":  "#3c3c3c",
    "accent":     "#0078d4",
    "accent_hov": "#1084d8",
    "accent_pre": "#006cbd",
    "text_pri":   "#f3f3f3",
    "text_sec":   "#9d9d9d",
    "text_ter":   "#6b6b6b",
    "border":     "#404040",
    "danger":     "#c42b1c",
    "success":    "#0f7b0f",
    "font":       "Segoe UI",
}


class WallpaperGalleryDialog:
    """Modal grid gallery allowing users to browse, search, and re-apply past wallpapers and favorites."""

    def __init__(
        self,
        parent: Any,
        config: Optional[AppConfig] = None,
        favorites_mgr: Optional[FavoritesManager] = None,
        recent_mgr: Optional[RecentWallpaperManager] = None,
        history_tracker: Optional[HistoryTracker] = None,
        on_apply: Optional[Callable[[WallpaperMetadata], None]] = None,
        on_favorite_toggled: Optional[Callable[[WallpaperMetadata], None]] = None,
    ):
        self.parent = parent
        self.config = config or AppConfig.load()
        self.favorites_mgr = favorites_mgr or FavoritesManager(self.config)
        self.recent_mgr = recent_mgr or RecentWallpaperManager(self.config)
        self.history_tracker = history_tracker or HistoryTracker(self.config)
        self.on_apply = on_apply
        self.on_favorite_toggled = on_favorite_toggled

        self._current_tab: str = "history"  # "history" or "favorites"
        self._search_query: str = ""
        self._thumbnail_cache: Dict[str, Any] = {}
        self.cards_data: List[Dict[str, Any]] = []

        if HAS_CUSTOMTKINTER:
            self.window = ctk.CTkToplevel(parent)
            self.window.configure(fg_color=_W11["surface_0"])
        else:
            self.window = tk.Toplevel(parent)
            self.window.configure(bg=_W11["surface_0"])

        self.window.title("Wallpaper Gallery & Archive")
        self.window.geometry("780x620")
        self.window.minsize(620, 480)

        # Center on parent or screen
        try:
            self.window.transient(parent)
            self.window.grab_set()
        except Exception:
            pass

        self._build_widgets()
        self._refresh_gallery()

    def _build_widgets(self) -> None:
        header_frame = ctk.CTkFrame(self.window, fg_color="transparent") if HAS_CUSTOMTKINTER else tk.Frame(self.window, bg=_W11["surface_0"])
        header_frame.pack(fill="x", padx=20, pady=(16, 8))

        # Title and Tab Controls
        top_row = ctk.CTkFrame(header_frame, fg_color="transparent") if HAS_CUSTOMTKINTER else tk.Frame(header_frame, bg=_W11["surface_0"])
        top_row.pack(fill="x", pady=(0, 8))

        title_lbl = (
            ctk.CTkLabel(
                top_row,
                text="🖼️ Wallpaper Gallery & Archive",
                font=ctk.CTkFont(family=_W11["font"], size=18, weight="bold"),
                text_color=_W11["text_pri"],
            )
            if HAS_CUSTOMTKINTER
            else tk.Label(top_row, text="🖼️ Wallpaper Gallery & Archive", font=("Segoe UI", 16, "bold"), fg=_W11["text_pri"], bg=_W11["surface_0"])
        )
        title_lbl.pack(side="left")

        # Tab Segmented Button
        if HAS_CUSTOMTKINTER:
            self.tab_var = ctk.StringVar(value="🕒 Recent History")
            self.tab_seg = ctk.CTkSegmentedButton(
                top_row,
                values=["🕒 Recent History", "⭐ Saved Favorites"],
                variable=self.tab_var,
                command=self._on_tab_change,
            )
            self.tab_seg.pack(side="right")
        else:
            self.tab_var = tk.StringVar(value="🕒 Recent History")
            btn_h = tk.Button(top_row, text="🕒 Recent History", command=lambda: self._on_tab_change("🕒 Recent History"))
            btn_h.pack(side="right", padx=2)
            btn_f = tk.Button(top_row, text="⭐ Saved Favorites", command=lambda: self._on_tab_change("⭐ Saved Favorites"))
            btn_f.pack(side="right", padx=2)

        # Search Bar Row
        search_row = ctk.CTkFrame(header_frame, fg_color="transparent") if HAS_CUSTOMTKINTER else tk.Frame(header_frame, bg=_W11["surface_0"])
        search_row.pack(fill="x")

        if HAS_CUSTOMTKINTER:
            self.search_entry = ctk.CTkEntry(
                search_row,
                placeholder_text="Filter wallpapers by title, category, or provider...",
                height=32,
                font=ctk.CTkFont(family=_W11["font"], size=12),
                corner_radius=6,
                border_width=1,
                border_color=_W11["border"],
                fg_color=_W11["surface_1"],
            )
            self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
            self.search_entry.bind("<KeyRelease>", lambda e: self._on_search_change())

            self.clear_btn = ctk.CTkButton(
                search_row,
                text="Clear",
                width=65,
                height=32,
                corner_radius=6,
                fg_color=_W11["surface_2"],
                hover_color=_W11["surface_3"],
                command=self._clear_search,
            )
            self.clear_btn.pack(side="left")
        else:
            self.search_entry = tk.Entry(search_row, font=("Segoe UI", 10))
            self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
            self.search_entry.bind("<KeyRelease>", lambda e: self._on_search_change())
            self.clear_btn = tk.Button(search_row, text="Clear", command=self._clear_search)
            self.clear_btn.pack(side="left")

        # Scrollable Grid Area
        if HAS_CUSTOMTKINTER:
            self.scroll_frame = ctk.CTkScrollableFrame(
                self.window,
                fg_color=_W11["surface_0"],
                corner_radius=8,
                border_width=1,
                border_color=_W11["border"],
            )
            self.scroll_frame.pack(fill="both", expand=True, padx=20, pady=(4, 16))
        else:
            self.scroll_frame = tk.Frame(self.window, bg=_W11["surface_0"])
            self.scroll_frame.pack(fill="both", expand=True, padx=20, pady=(4, 16))

        # Bottom Bar: Stats and Close
        bottom_bar = ctk.CTkFrame(self.window, fg_color="transparent") if HAS_CUSTOMTKINTER else tk.Frame(self.window, bg=_W11["surface_0"])
        bottom_bar.pack(fill="x", padx=20, pady=(0, 14))

        self.status_lbl = (
            ctk.CTkLabel(bottom_bar, text="", font=ctk.CTkFont(family=_W11["font"], size=11), text_color=_W11["text_sec"])
            if HAS_CUSTOMTKINTER
            else tk.Label(bottom_bar, text="", fg="gray", bg=_W11["surface_0"])
        )
        self.status_lbl.pack(side="left")

        if HAS_CUSTOMTKINTER:
            close_btn = ctk.CTkButton(
                bottom_bar,
                text="Close",
                width=90,
                height=30,
                corner_radius=6,
                fg_color=_W11["surface_2"],
                hover_color=_W11["surface_3"],
                command=self.window.destroy,
            )
            close_btn.pack(side="right")
        else:
            close_btn = tk.Button(bottom_bar, text="Close", command=self.window.destroy)
            close_btn.pack(side="right")

    def _on_tab_change(self, value: str) -> None:
        self._current_tab = "favorites" if "Favorites" in value else "history"
        self._refresh_gallery()

    def _on_search_change(self) -> None:
        self._search_query = self.search_entry.get().strip().lower()
        self._render_cards()

    def _clear_search(self) -> None:
        self.search_entry.delete(0, tk.END)
        self._search_query = ""
        self._render_cards()

    def _collect_items(self) -> List[Dict[str, Any]]:
        """Gather items from history or favorites based on active tab."""
        items: List[Dict[str, Any]] = []

        if self._current_tab == "favorites":
            favs = self.favorites_mgr.get_favorites(only_existing_files=True)
            for f in favs:
                items.append({
                    "id": f.image_id,
                    "title": f.title or "Wallpaper",
                    "category": f.category or "Favorites",
                    "provider": f.provider or "Curated",
                    "path": f.saved_path or f.local_path,
                    "is_fav": True,
                    "raw": f,
                })
        else:
            # History: recent items + history tracker records up to 20
            seen_paths = set()
            recents = self.recent_mgr.get_items()
            for r in reversed(recents):
                p = Path(r.local_path)
                if p.exists() and str(p) not in seen_paths:
                    seen_paths.add(str(p))
                    items.append({
                        "id": r.image_id,
                        "title": r.title or p.stem,
                        "category": r.category or "Wallpaper",
                        "provider": r.provider or "History",
                        "path": str(p),
                        "is_fav": self.favorites_mgr.is_favorite(r.image_id),
                        "raw": r,
                    })
                    if len(items) >= 20:
                        break

            # Also check history records for any downloaded files still in cache
            if len(items) < 20:
                hist_records = self.history_tracker.reload()
                for h in reversed(hist_records):
                    if hasattr(h, "local_path") and h.local_path:
                        p = Path(h.local_path)
                        if p.exists() and str(p) not in seen_paths:
                            seen_paths.add(str(p))
                            items.append({
                                "id": h.image_id,
                                "title": getattr(h, "title", None) or p.stem,
                                "category": getattr(h, "category", "History"),
                                "provider": getattr(h, "provider", "Local"),
                                "path": str(p),
                                "is_fav": self.favorites_mgr.is_favorite(h.image_id),
                                "raw": h,
                            })
                            if len(items) >= 20:
                                break

        return items

    def _refresh_gallery(self) -> None:
        self.cards_data = self._collect_items()
        self._render_cards()

    def _render_cards(self) -> None:
        """Render wallpaper card grid inside the scrollable container."""
        if not hasattr(self, "scroll_frame") or self.scroll_frame is None:
            return

        # Clear existing card widgets
        if hasattr(self.scroll_frame, "winfo_children"):
            for widget in self.scroll_frame.winfo_children():
                try:
                    widget.destroy()
                except Exception:
                    pass

        query = self._search_query
        filtered = [
            item for item in self.cards_data
            if not query or (query in item["title"].lower() or query in item["category"].lower() or query in item["provider"].lower())
        ]

        count = len(filtered)
        tab_name = "Favorites" if self._current_tab == "favorites" else "Recent History"
        if hasattr(self, "status_lbl") and self.status_lbl:
            if hasattr(self.status_lbl, "configure"):
                self.status_lbl.configure(text=f"Showing {count} {tab_name} item(s)")
            elif hasattr(self.status_lbl, "config"):
                self.status_lbl.config(text=f"Showing {count} {tab_name} item(s)")

        if not filtered:
            msg = "No wallpapers found matching your search." if query else f"No {tab_name.lower()} available yet."
            empty_lbl = (
                ctk.CTkLabel(self.scroll_frame, text=msg, font=ctk.CTkFont(family=_W11["font"], size=13), text_color=_W11["text_sec"])
                if HAS_CUSTOMTKINTER
                else tk.Label(self.scroll_frame, text=msg, fg="gray", bg=_W11["surface_0"])
            )
            empty_lbl.pack(pady=40)
            return

        columns = 3
        for idx, item in enumerate(filtered):
            row = idx // columns
            col = idx % columns

            card = self._create_card(self.scroll_frame, item)
            card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")

        for c in range(columns):
            self.scroll_frame.columnconfigure(c, weight=1)

    def _get_thumbnail_image(self, path_str: str, size: tuple[int, int] = (210, 125)) -> Optional[Any]:
        """Generate and cache thumbnail PhotoImage for a wallpaper."""
        if path_str in self._thumbnail_cache:
            return self._thumbnail_cache[path_str]

        p = Path(path_str)
        if not p.exists() or not p.is_file():
            return None

        try:
            with Image.open(p) as img:
                try:
                    img.draft("RGB", (size[0] * 2, size[1] * 2))
                except Exception:
                    pass
                img_copy = img.copy()
                img_copy.thumbnail(size, Image.Resampling.BILINEAR)
                if HAS_CUSTOMTKINTER:
                    ctk_img = ctk.CTkImage(light_image=img_copy, dark_image=img_copy, size=img_copy.size)
                    self._thumbnail_cache[path_str] = ctk_img
                    return ctk_img
                else:
                    from PIL import ImageTk
                    tk_img = ImageTk.PhotoImage(img_copy)
                    self._thumbnail_cache[path_str] = tk_img
                    return tk_img
        except Exception:
            return None

    def _create_card(self, parent: Any, item: Dict[str, Any]) -> Any:
        card = (
            ctk.CTkFrame(
                parent,
                fg_color=_W11["surface_1"],
                corner_radius=8,
                border_width=1,
                border_color=_W11["border"],
            )
            if HAS_CUSTOMTKINTER
            else tk.Frame(parent, bg=_W11["surface_1"], bd=1, relief="ridge")
        )

        thumb = self._get_thumbnail_image(item["path"])
        if thumb and HAS_CUSTOMTKINTER:
            img_btn = ctk.CTkButton(
                card,
                image=thumb,
                text="",
                fg_color="transparent",
                hover_color=_W11["surface_2"],
                corner_radius=6,
                height=125,
                command=lambda it=item: self._open_lightbox(it),
            )
            img_btn.pack(fill="x", padx=6, pady=(6, 4))
        else:
            placeholder = (
                ctk.CTkLabel(card, text="[Image Preview]", height=110, font=ctk.CTkFont(size=11), text_color=_W11["text_ter"])
                if HAS_CUSTOMTKINTER
                else tk.Label(card, text="[Preview]", bg=_W11["surface_1"], fg="gray")
            )
            placeholder.pack(fill="x", padx=6, pady=(6, 4))

        # Title (Shortened to 26 characters if needed)
        title_text = item["title"]
        if len(title_text) > 26:
            title_text = title_text[:24] + "…"

        title_lbl = (
            ctk.CTkLabel(
                card,
                text=title_text,
                font=ctk.CTkFont(family=_W11["font"], size=11, weight="bold"),
                text_color=_W11["text_pri"],
                anchor="w",
            )
            if HAS_CUSTOMTKINTER
            else tk.Label(card, text=title_text, font=("Segoe UI", 9, "bold"), fg=_W11["text_pri"], bg=_W11["surface_1"], anchor="w")
        )
        title_lbl.pack(fill="x", padx=8, pady=(2, 0))

        # Category & Provider Badge
        cat_badge = f"{item['category']}  •  {item['provider']}"
        meta_lbl = (
            ctk.CTkLabel(
                card,
                text=cat_badge,
                font=ctk.CTkFont(family=_W11["font"], size=10),
                text_color=_W11["text_sec"],
                anchor="w",
            )
            if HAS_CUSTOMTKINTER
            else tk.Label(card, text=cat_badge, font=("Segoe UI", 8), fg=_W11["text_sec"], bg=_W11["surface_1"], anchor="w")
        )
        meta_lbl.pack(fill="x", padx=8, pady=(0, 6))

        # Action Buttons Toolbar
        action_row = ctk.CTkFrame(card, fg_color="transparent") if HAS_CUSTOMTKINTER else tk.Frame(card, bg=_W11["surface_1"])
        action_row.pack(fill="x", padx=6, pady=(0, 6))

        if HAS_CUSTOMTKINTER:
            apply_btn = ctk.CTkButton(
                action_row,
                text="🖥️ Apply",
                height=26,
                font=ctk.CTkFont(family=_W11["font"], size=11, weight="bold"),
                fg_color=_W11["accent"],
                hover_color=_W11["accent_hov"],
                corner_radius=4,
                command=lambda it=item: self._apply_item(it),
            )
            apply_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))

            fav_icon = "⭐" if item["is_fav"] else "☆"
            fav_btn = ctk.CTkButton(
                action_row,
                text=fav_icon,
                width=32,
                height=26,
                font=ctk.CTkFont(size=12),
                fg_color=_W11["surface_2"],
                hover_color=_W11["surface_3"],
                corner_radius=4,
                command=lambda it=item: self._toggle_favorite(it),
            )
            fav_btn.pack(side="left", padx=(0, 4))

            exp_btn = ctk.CTkButton(
                action_row,
                text="📂",
                width=32,
                height=26,
                font=ctk.CTkFont(size=11),
                fg_color=_W11["surface_2"],
                hover_color=_W11["surface_3"],
                corner_radius=4,
                command=lambda it=item: self._reveal_in_explorer(it["path"]),
            )
            exp_btn.pack(side="left")
        else:
            apply_btn = tk.Button(action_row, text="Apply", command=lambda it=item: self._apply_item(it))
            apply_btn.pack(side="left", fill="x", expand=True, padx=2)
            exp_btn = tk.Button(action_row, text="📂", command=lambda it=item: self._reveal_in_explorer(it["path"]))
            exp_btn.pack(side="right", padx=2)

        return card

    def _open_lightbox(self, item: Dict[str, Any]) -> None:
        """Display enlarged high-resolution image preview lightbox modal."""
        p = Path(item["path"])
        if not p.exists():
            return

        lb = ctk.CTkToplevel(self.window) if HAS_CUSTOMTKINTER else tk.Toplevel(self.window)
        lb.title(f"Preview: {item['title']}")
        lb.geometry("740x560")
        lb.configure(fg_color=_W11["surface_0"] if HAS_CUSTOMTKINTER else "#1e1e1e")

        try:
            lb.transient(self.window)
        except Exception:
            pass

        # Load larger preview image
        try:
            with Image.open(p) as img:
                try:
                    img.draft("RGB", (1400, 840))
                except Exception:
                    pass
                img_copy = img.copy()
                orig_w, orig_h = img.size
                img_copy.thumbnail((700, 420), Image.Resampling.BILINEAR)
                if HAS_CUSTOMTKINTER:
                    ctk_large = ctk.CTkImage(light_image=img_copy, dark_image=img_copy, size=img_copy.size)
                    img_lbl = ctk.CTkLabel(lb, image=ctk_large, text="")
                else:
                    from PIL import ImageTk
                    tk_large = ImageTk.PhotoImage(img_copy)
                    img_lbl = tk.Label(lb, image=tk_large)
                    img_lbl.image = tk_large
                img_lbl.pack(pady=12, padx=12, fill="both", expand=True)
        except Exception:
            err_lbl = ctk.CTkLabel(lb, text="[Could not load full preview]") if HAS_CUSTOMTKINTER else tk.Label(lb, text="[Error]")
            err_lbl.pack(pady=40)
            orig_w, orig_h = (0, 0)

        # Meta & Actions Footer
        info_row = ctk.CTkFrame(lb, fg_color="transparent") if HAS_CUSTOMTKINTER else tk.Frame(lb)
        info_row.pack(fill="x", padx=16, pady=(0, 14))

        meta_info = f"{item['title']}  •  {orig_w}x{orig_h}  •  {item['category']}  •  {item['provider']}"
        detail_lbl = (
            ctk.CTkLabel(info_row, text=meta_info, font=ctk.CTkFont(family=_W11["font"], size=11), text_color=_W11["text_sec"])
            if HAS_CUSTOMTKINTER
            else tk.Label(info_row, text=meta_info, fg="gray")
        )
        detail_lbl.pack(side="left")

        if HAS_CUSTOMTKINTER:
            apply_lb_btn = ctk.CTkButton(
                info_row,
                text="🖥️ Apply Wallpaper",
                font=ctk.CTkFont(family=_W11["font"], size=12, weight="bold"),
                fg_color=_W11["accent"],
                hover_color=_W11["accent_hov"],
                command=lambda: [self._apply_item(item), lb.destroy()],
            )
            apply_lb_btn.pack(side="right", padx=(8, 0))

            close_lb_btn = ctk.CTkButton(
                info_row,
                text="Close",
                fg_color=_W11["surface_2"],
                hover_color=_W11["surface_3"],
                command=lb.destroy,
            )
            close_lb_btn.pack(side="right")
        else:
            apply_lb_btn = tk.Button(info_row, text="Apply", command=lambda: [self._apply_item(item), lb.destroy()])
            apply_lb_btn.pack(side="right")

    def _apply_item(self, item: Dict[str, Any]) -> None:
        """Trigger application of selected gallery item to the desktop."""
        raw = item.get("raw")
        meta = None

        if isinstance(raw, WallpaperMetadata):
            meta = raw
        else:
            # Construct WallpaperMetadata wrapper from item
            meta = WallpaperMetadata(
                image_id=item["id"],
                category=item["category"],
                provider=item["provider"],
                source_url="",
                download_url="",
                local_path=item["path"],
                sha256="",
                title=item["title"],
                creator="Curated",
                license="Free",
                license_url=None,
                attribution_required=False,
                attribution_text="",
                width=1920,
                height=1080,
                aspect_ratio=1.778,
                mode=getattr(self.config, "default_position", "Fill"),
            )

        if self.on_apply:
            self.on_apply(meta)
            self.status_lbl.configure(text=f"✓ Applied '{item['title']}' to desktop.")

    def _toggle_favorite(self, item: Dict[str, Any]) -> None:
        """Toggle favorite state of wallpaper card."""
        raw = item.get("raw")
        meta = raw if isinstance(raw, WallpaperMetadata) else WallpaperMetadata(
            image_id=item["id"],
            category=item["category"],
            provider=item["provider"],
            source_url="",
            download_url="",
            local_path=item["path"],
            sha256="",
            title=item["title"],
            creator="Curated",
            license="Free",
            license_url=None,
            attribution_required=False,
            attribution_text="",
            width=1920,
            height=1080,
            aspect_ratio=1.778,
            mode="Fill",
        )

        new_fav = self.favorites_mgr.toggle_favorite(meta)
        item["is_fav"] = new_fav

        if self.on_favorite_toggled:
            self.on_favorite_toggled(meta)

        self._refresh_gallery()

    def _reveal_in_explorer(self, path_str: str) -> None:
        """Open Windows Explorer with the specific wallpaper file highlighted."""
        p = Path(path_str)
        if not p.exists():
            messagebox.showwarning("File Not Found", f"Wallpaper file no longer exists at:\n{path_str}")
            return

        if os.name == "nt":
            try:
                subprocess.run(["explorer.exe", f"/select,{str(p.resolve())}"])
            except Exception as e:
                messagebox.showerror("Explorer Error", f"Could not launch Windows Explorer: {e}")
        else:
            messagebox.showinfo("File Path", str(p.resolve()))
