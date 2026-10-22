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

from ..core.models import WallpaperCategory, WallpaperPosition, WallpaperMetadata
from ..core.config import AppConfig
from ..core.history import HistoryTracker
from ..core.cache import CacheManager
from ..providers.router import ProviderRouter
from ..adapters.factory import get_wallpaper_adapter
from .file_picker import pick_local_image


class WallpaperSelectorDialog:
    """Desktop dialog displaying the 5 wallpaper options with live preview and controls."""

    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or AppConfig.load()
        self.history = HistoryTracker(self.config)
        self.cache = CacheManager(self.config)
        self.router = ProviderRouter(self.config, self.history, self.cache)
        self.adapter = get_wallpaper_adapter()

        self.current_category: Optional[WallpaperCategory] = None
        self.current_metadata: Optional[WallpaperMetadata] = None
        self.is_busy = False

        self._init_window()

    def _init_window(self) -> None:
        if HAS_CUSTOMTKINTER:
            ctk.set_appearance_mode(self.config.theme)
            ctk.set_default_color_theme("blue")
            self.root = ctk.CTk()
        else:
            self.root = tk.Tk()

        self.root.title("Choose Your Wallpaper")
        self.root.geometry("640x740")
        self.root.minsize(600, 700)
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
        self._center_window(640, 740)

        self._build_widgets()

    def _center_window(self, width: int, height: int) -> None:
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _build_widgets(self) -> None:
        # Bottom Action Buttons ("Try Another", "Done / Close")
        # Pack bottom frame FIRST so it is firmly anchored to the bottom edge and never clipped
        bottom_frame = ctk.CTkFrame(self.root, fg_color="transparent") if HAS_CUSTOMTKINTER else tk.Frame(self.root)
        bottom_frame.pack(side="bottom", fill="x", padx=24, pady=(10, 20))

        if HAS_CUSTOMTKINTER:
            self.retry_btn = ctk.CTkButton(
                bottom_frame,
                text="🔄 Try Another",
                width=120,
                height=38,
                font=ctk.CTkFont(size=13, weight="bold"),
                state="disabled",
                fg_color="#4b5563",
                hover_color="#374151",
                command=self.on_retry,
            )
            self.retry_btn.pack(side="left", padx=(0, 6))

            self.save_btn = ctk.CTkButton(
                bottom_frame,
                text="💾 Save Image",
                width=125,
                height=38,
                font=ctk.CTkFont(size=13, weight="bold"),
                state="disabled",
                fg_color="#059669",
                hover_color="#047857",
                command=self.on_save_wallpaper,
            )
            self.save_btn.pack(side="left", padx=6)

            self.open_folder_btn = ctk.CTkButton(
                bottom_frame,
                text="📂 Open Folder",
                width=120,
                height=38,
                font=ctk.CTkFont(size=13, weight="bold"),
                state="disabled",
                fg_color="#374151",
                hover_color="#1f2937",
                command=self.on_open_category_folder,
            )
            self.open_folder_btn.pack(side="left", padx=6)

            self.close_btn = ctk.CTkButton(
                bottom_frame,
                text="Done / Close",
                width=110,
                height=38,
                font=ctk.CTkFont(size=13, weight="bold"),
                command=self.on_close,
            )
            self.close_btn.pack(side="right")
        else:
            self.retry_btn = tk.Button(bottom_frame, text="🔄 Try Another", state="disabled", command=self.on_retry)
            self.retry_btn.pack(side="left", padx=4)
            self.save_btn = tk.Button(bottom_frame, text="💾 Save Image", state="disabled", command=self.on_save_wallpaper)
            self.save_btn.pack(side="left", padx=4)
            self.open_folder_btn = tk.Button(bottom_frame, text="📂 Open Folder", state="disabled", command=self.on_open_category_folder)
            self.open_folder_btn.pack(side="left", padx=4)
            self.close_btn = tk.Button(bottom_frame, text="Done / Close", command=self.on_close)
            self.close_btn.pack(side="right")

        # Header container
        header_frame = ctk.CTkFrame(self.root, fg_color="transparent") if HAS_CUSTOMTKINTER else tk.Frame(self.root)
        header_frame.pack(fill="x", padx=24, pady=(16, 8))

        title_lbl = (
            ctk.CTkLabel(
                header_frame,
                text="Desktop Wallpaper Selector",
                font=ctk.CTkFont(size=22, weight="bold"),
            )
            if HAS_CUSTOMTKINTER
            else tk.Label(header_frame, text="Desktop Wallpaper Selector", font=("Helvetica", 16, "bold"))
        )
        title_lbl.pack(anchor="w")

        subtitle_lbl = (
            ctk.CTkLabel(
                header_frame,
                text="Select a category for your session background:",
                font=ctk.CTkFont(size=13),
                text_color="gray",
            )
            if HAS_CUSTOMTKINTER
            else tk.Label(header_frame, text="Select a category for your session background:", fg="gray")
        )
        subtitle_lbl.pack(anchor="w", pady=(2, 0))

        # Category buttons container (Grid of 5 options)
        btn_grid = ctk.CTkFrame(self.root, fg_color="transparent") if HAS_CUSTOMTKINTER else tk.Frame(self.root)
        btn_grid.pack(fill="x", padx=24, pady=(6, 8))

        categories = [
            (WallpaperCategory.SPACE, "🚀 Space", "#1e3a8a"),
            (WallpaperCategory.NATURE, "🌿 Nature", "#065f46"),
            (WallpaperCategory.ART, "🎨 Art", "#78350f"),
            (WallpaperCategory.PORTRAIT, "👤 Portrait", "#581c87"),
            (WallpaperCategory.LOCAL_STORAGE, "📁 Local Storage", "#374151"),
        ]

        self.cat_buttons = {}
        for idx, (cat, label_text, color) in enumerate(categories):
            row = idx // 2
            col = idx % 2
            colspan = 2 if idx == 4 else 1

            if HAS_CUSTOMTKINTER:
                btn = ctk.CTkButton(
                    btn_grid,
                    text=label_text,
                    font=ctk.CTkFont(size=14, weight="bold"),
                    height=42,
                    command=lambda c=cat: self.on_select_category(c),
                )
                btn.grid(row=row, column=col, columnspan=colspan, padx=6, pady=4, sticky="ew")
            else:
                btn = tk.Button(
                    btn_grid,
                    text=label_text,
                    font=("Helvetica", 11, "bold"),
                    height=2,
                    command=lambda c=cat: self.on_select_category(c),
                )
                btn.grid(row=row, column=col, columnspan=colspan, padx=6, pady=4, sticky="ew")
            self.cat_buttons[cat] = btn

        btn_grid.columnconfigure(0, weight=1)
        btn_grid.columnconfigure(1, weight=1)

        # Settings row: Mode selection (Fill / Fit)
        settings_frame = ctk.CTkFrame(self.root) if HAS_CUSTOMTKINTER else tk.Frame(self.root)
        settings_frame.pack(fill="x", padx=24, pady=(5, 10))

        mode_lbl = (
            ctk.CTkLabel(settings_frame, text="Display Mode:", font=ctk.CTkFont(size=12, weight="bold"))
            if HAS_CUSTOMTKINTER
            else tk.Label(settings_frame, text="Display Mode:")
        )
        mode_lbl.pack(side="left", padx=12, pady=8)

        if HAS_CUSTOMTKINTER:
            self.mode_var = ctk.StringVar(value=self.config.default_position)
            self.mode_selector = ctk.CTkSegmentedButton(
                settings_frame,
                values=[WallpaperPosition.FILL.value, WallpaperPosition.FIT.value],
                variable=self.mode_var,
                command=self.on_mode_change,
            )
            self.mode_selector.pack(side="left", padx=10, pady=8)

            self.lockscreen_var = ctk.BooleanVar(value=bool(getattr(self.config, "also_set_lockscreen", False)))
            self.lockscreen_chk = ctk.CTkCheckBox(
                settings_frame,
                text="Also set Lock Screen",
                variable=self.lockscreen_var,
                font=ctk.CTkFont(size=12),
                command=self.on_lockscreen_toggle,
            )
            self.lockscreen_chk.pack(side="right", padx=12, pady=8)
        else:
            self.mode_var = tk.StringVar(value=self.config.default_position)
            for m in [WallpaperPosition.FILL.value, WallpaperPosition.FIT.value]:
                rb = tk.Radiobutton(settings_frame, text=m, value=m, variable=self.mode_var, command=self.on_mode_change)
                rb.pack(side="left", padx=5)

            self.lockscreen_var = tk.BooleanVar(value=bool(getattr(self.config, "also_set_lockscreen", False)))
            self.lockscreen_chk = tk.Checkbutton(
                settings_frame,
                text="Also set Lock Screen",
                variable=self.lockscreen_var,
                command=self.on_lockscreen_toggle,
            )
            self.lockscreen_chk.pack(side="right", padx=12, pady=8)

        # Preview Container
        self.preview_frame = ctk.CTkFrame(self.root, height=165) if HAS_CUSTOMTKINTER else tk.Frame(self.root, height=165, bg="black")
        self.preview_frame.pack(fill="x", padx=24, pady=8)
        self.preview_frame.pack_propagate(False)

        self.preview_label = (
            ctk.CTkLabel(self.preview_frame, text="Preview will appear here after selecting an option", font=ctk.CTkFont(size=12), text_color="gray")
            if HAS_CUSTOMTKINTER
            else tk.Label(self.preview_frame, text="Preview will appear here", fg="gray")
        )
        self.preview_label.pack(expand=True, fill="both")

        # Status & Progress Area
        status_frame = ctk.CTkFrame(self.root, fg_color="transparent") if HAS_CUSTOMTKINTER else tk.Frame(self.root)
        status_frame.pack(fill="x", padx=24, pady=4)

        self.status_lbl = (
            ctk.CTkLabel(status_frame, text="Ready. Click any category above.", font=ctk.CTkFont(size=12))
            if HAS_CUSTOMTKINTER
            else tk.Label(status_frame, text="Ready.")
        )
        self.status_lbl.pack(anchor="w")

        if HAS_CUSTOMTKINTER:
            self.progress_bar = ctk.CTkProgressBar(status_frame)
            self.progress_bar.pack(fill="x", pady=4)
            self.progress_bar.set(0)
        else:
            self.progress_bar = None

        # Attribution display
        self.attrib_lbl = (
            ctk.CTkLabel(
                self.root,
                text="",
                font=ctk.CTkFont(size=11),
                text_color="gray",
                wraplength=560,
                justify="left",
            )
            if HAS_CUSTOMTKINTER
            else tk.Label(self.root, text="", fg="gray", wraplength=560, justify="left")
        )
        self.attrib_lbl.pack(anchor="w", padx=24, pady=(2, 6))

    def set_status(self, text: str, progress: Optional[float] = None) -> None:
        """Update status label and optional progress bar from any thread."""
        def _update():
            if HAS_CUSTOMTKINTER:
                self.status_lbl.configure(text=text)
                if progress is not None and self.progress_bar:
                    self.progress_bar.set(progress)
            else:
                self.status_lbl.config(text=text)
        self.root.after(0, _update)

    def set_busy(self, busy: bool) -> None:
        self.is_busy = busy
        state = "disabled" if busy else "normal"
        def _update():
            for btn in self.cat_buttons.values():
                btn.configure(state=state) if HAS_CUSTOMTKINTER else btn.config(state=state)
            if self.current_category and self.current_category != WallpaperCategory.LOCAL_STORAGE:
                retry_state = "disabled" if busy else "normal"
                self.retry_btn.configure(state=retry_state) if HAS_CUSTOMTKINTER else self.retry_btn.config(state=retry_state)
            if self.current_metadata:
                save_state = "disabled" if busy else "normal"
                self.save_btn.configure(state=save_state) if HAS_CUSTOMTKINTER else self.save_btn.config(state=save_state)
        self.root.after(0, _update)

    def on_mode_change(self, *args) -> None:
        new_mode = self.mode_var.get()
        self.config.default_position = new_mode
        self.config.save()
        # If a wallpaper is currently active in this session, reapply with new mode
        if self.current_metadata and Path(self.current_metadata.local_path).exists():
            self.adapter.set_wallpaper(Path(self.current_metadata.local_path), mode=new_mode)
            self.set_status(f"Updated display mode to {new_mode}.")

    def on_lockscreen_toggle(self) -> None:
        enabled = self.lockscreen_var.get()
        self.config.also_set_lockscreen = enabled
        self.config.save()
        # If active wallpaper exists and user checked box, apply to lock screen immediately
        if enabled and self.current_metadata and Path(self.current_metadata.local_path).exists():
            ok = self.adapter.set_lockscreen(Path(self.current_metadata.local_path))
            if ok:
                self.set_status("✓ Applied current wallpaper to Lock Screen.")

    def on_save_wallpaper(self) -> None:
        """Save the active wallpaper permanently to category's Saved folder."""
        if not self.current_metadata:
            return

        saved_path, err = self.cache.save_wallpaper_to_category(self.current_metadata)
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
        if not folder and self.current_metadata:
            folder = self.cache.get_category_dir(self.current_metadata.category) / "Saved"
            if not folder.exists():
                folder = self.cache.get_category_dir(self.current_metadata.category)

        if folder and folder.exists():
            try:
                import os
                os.startfile(folder)
            except Exception:
                import subprocess
                subprocess.Popen(["explorer", str(folder)])

    def on_select_category(self, category: WallpaperCategory) -> None:
        if self.is_busy:
            return

        self.current_category = category
        if category == WallpaperCategory.LOCAL_STORAGE:
            self._handle_local_storage()
        else:
            self._handle_online_category(category)

    def _handle_local_storage(self) -> None:
        self.set_status("Opening native file picker...")
        selected_path = pick_local_image(self.root)

        if not selected_path:
            # User canceled the file picker
            self.root.destroy()
            return

        self.set_busy(True)
        self.set_status(f"Validating {selected_path.name}...")

        def _worker():
            mode = self.mode_var.get()
            meta = self.cache.store_local_image(selected_path, mode=mode)
            if meta:
                success = self.adapter.set_wallpaper(Path(meta.local_path), mode=mode)
                if success:
                    lock_msg = ""
                    if self.lockscreen_var.get():
                        lock_ok = self.adapter.set_lockscreen(Path(meta.local_path))
                        if lock_ok:
                            lock_msg = " & Lock Screen"

                    self.current_metadata = meta
                    self.set_status(f"✓ Applied local wallpaper{lock_msg}: {selected_path.name}", progress=1.0)
                    self._update_preview_and_attribution(meta)
                else:
                    self.set_status("Failed to apply wallpaper through desktop adapter.")
            else:
                self.set_status("Error: Selected file is corrupted or not a valid image.")
            self.set_busy(False)

        threading.Thread(target=_worker, daemon=True).start()

    def _handle_online_category(self, category: WallpaperCategory) -> None:
        self.set_busy(True)
        self.set_status(f"Searching for {category.value} wallpaper...", progress=0.05)

        def _worker():
            def _progress(downloaded: int, total: int):
                frac = min(0.9, 0.2 + (downloaded / total) * 0.7) if total > 0 else 0.5
                kb = downloaded // 1024
                self.set_status(f"Downloading {category.value} ({kb} KB)...", progress=frac)

            def _status(msg: str, attempt: int, total_attempts: int):
                self.set_status(f"[{attempt}/{total_attempts}] {msg}", progress=0.1 * attempt)

            mode = self.mode_var.get()
            meta, err = self.router.acquire_wallpaper_for_category(
                category,
                mode=mode,
                progress_callback=_progress,
                status_callback=_status,
            )

            if meta:
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
                    self._update_preview_and_attribution(meta)
                else:
                    self.set_status("Download succeeded, but desktop adapter could not set wallpaper.")
            else:
                # Fallback to cached wallpaper if available
                fallback = self.cache.get_fallback_wallpaper()
                if fallback:
                    self.adapter.set_wallpaper(fallback, mode=mode)
                    self.set_status(f"Online search failed ({err}). Using previously cached wallpaper.", progress=1.0)
                else:
                    self.set_status(f"Error: {err}", progress=0.0)

            self.set_busy(False)

        threading.Thread(target=_worker, daemon=True).start()

    def _update_preview_and_attribution(self, meta: WallpaperMetadata) -> None:
        def _update():
            # Enable actions
            if HAS_CUSTOMTKINTER:
                self.retry_btn.configure(state="normal")
                self.save_btn.configure(state="normal", text="💾 Save Image")
                self.open_folder_btn.configure(state="disabled")
            else:
                self.retry_btn.config(state="normal")
                self.save_btn.config(state="normal", text="💾 Save Image")
                self.open_folder_btn.config(state="disabled")

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

            # Render preview image
            local_path = Path(meta.local_path)
            if local_path.exists():
                try:
                    img = Image.open(local_path)
                    # Scale to fit preview box (approx 540x155) maintaining aspect ratio
                    img.thumbnail((540, 155), Image.Resampling.LANCZOS)
                    if HAS_CUSTOMTKINTER:
                        ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                        self.preview_label.configure(image=ctk_img, text="")
                        self.preview_label.image = ctk_img
                    else:
                        from PIL import ImageTk
                        tk_img = ImageTk.PhotoImage(img)
                        self.preview_label.config(image=tk_img, text="")
                        self.preview_label.image = tk_img
                except Exception:
                    pass

        self.root.after(0, _update)

    def on_retry(self) -> None:
        if self.current_category and self.current_category != WallpaperCategory.LOCAL_STORAGE:
            self._handle_online_category(self.current_category)

    def on_close(self) -> None:
        self.root.destroy()

    def run(self) -> None:
        """Run the main GUI loop."""
        self.root.mainloop()
