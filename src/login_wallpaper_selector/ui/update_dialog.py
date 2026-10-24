"""In-app modal dialog displaying update availability, release notes, and download progress."""

from __future__ import annotations
import time
import threading
import tkinter as tk
from pathlib import Path
from typing import Optional, Callable

try:
    import customtkinter as ctk
    HAS_CUSTOMTKINTER = True
except ImportError:
    import tkinter as ctk
    HAS_CUSTOMTKINTER = False

from ..core.updater import UpdateCheckResult, apply_update, restart_application

_W11 = {
    "font": "Segoe UI",
    "surface_0": "#202020",
    "surface_1": "#2b2b2b",
    "surface_2": "#333333",
    "surface_3": "#3c3c3c",
    "accent": "#0078d4",
    "accent_hov": "#1084d8",
    "text_pri": "#f3f3f3",
    "text_sec": "#9d9d9d",
    "text_ter": "#6b6b6b",
    "border": "#404040",
    "danger": "#c42b1c",
    "success": "#0f7b0f",
}


class UpdateModalDialog:
    """Modal window prompting user to download and install a new application release."""

    def __init__(self, parent: tk.Tk | ctk.CTk, update_info: UpdateCheckResult):
        self.parent = parent
        self.update_info = update_info
        self.is_updating = False

        if HAS_CUSTOMTKINTER:
            self.window = ctk.CTkToplevel(parent)
        else:
            self.window = tk.Toplevel(parent)

        self.window.title("Software Update Available")
        self.window.geometry("540x460")
        self.window.resizable(False, False)
        self.window.attributes("-topmost", True)

        self._center_window(540, 460)
        self._build_widgets()

    def _center_window(self, width: int, height: int) -> None:
        self.window.update_idletasks()
        try:
            x = self.parent.winfo_x() + (self.parent.winfo_width() - width) // 2
            y = self.parent.winfo_y() + (self.parent.winfo_height() - height) // 2
            self.window.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

    def _build_widgets(self) -> None:
        container = (
            ctk.CTkFrame(
                self.window,
                fg_color=_W11["surface_1"],
                corner_radius=8,
                border_width=1,
                border_color=_W11["border"],
            )
            if HAS_CUSTOMTKINTER
            else tk.Frame(self.window)
        )
        container.pack(fill="both", expand=True, padx=16, pady=16)

        # Bottom Button Toolbar - Packed FIRST with side="bottom" so buttons are NEVER overlapped
        btn_frame = ctk.CTkFrame(container, fg_color="transparent") if HAS_CUSTOMTKINTER else tk.Frame(container)
        btn_frame.pack(side="bottom", fill="x", padx=16, pady=(10, 16))

        if HAS_CUSTOMTKINTER:
            self.later_btn = ctk.CTkButton(
                btn_frame,
                text="Remind Me Later",
                width=130,
                height=32,
                font=ctk.CTkFont(family=_W11["font"], size=12),
                corner_radius=6,
                fg_color=_W11["surface_2"],
                hover_color=_W11["surface_3"],
                text_color=_W11["text_sec"],
                command=self.window.destroy,
            )
            self.later_btn.pack(side="left")

            self.update_btn = ctk.CTkButton(
                btn_frame,
                text="⬇️  Download & Update",
                width=170,
                height=32,
                font=ctk.CTkFont(family=_W11["font"], size=12, weight="bold"),
                corner_radius=6,
                fg_color=_W11["accent"],
                hover_color=_W11["accent_hov"],
                text_color=_W11["text_pri"],
                command=self.on_start_update,
            )
            self.update_btn.pack(side="right")
        else:
            self.later_btn = tk.Button(btn_frame, text="Remind Me Later", command=self.window.destroy)
            self.later_btn.pack(side="left")

            self.update_btn = tk.Button(btn_frame, text="⬇️ Download & Update", command=self.on_start_update)
            self.update_btn.pack(side="right")

        # Header Badge
        header_text = f"🚀 New Update: v{self.update_info.latest_version}"
        header_lbl = (
            ctk.CTkLabel(
                container,
                text=header_text,
                font=ctk.CTkFont(family=_W11["font"], size=18, weight="bold"),
                text_color=_W11["text_pri"],
            )
            if HAS_CUSTOMTKINTER
            else tk.Label(container, text=header_text, font=("Segoe UI", 14, "bold"), fg="#0078d4")
        )
        header_lbl.pack(anchor="w", padx=16, pady=(16, 2))

        sub_text = f"Current version: v{self.update_info.current_version}  •  Release: {self.update_info.release_title or self.update_info.latest_version}"
        sub_lbl = (
            ctk.CTkLabel(
                container,
                text=sub_text,
                font=ctk.CTkFont(family=_W11["font"], size=11),
                text_color=_W11["text_sec"],
            )
            if HAS_CUSTOMTKINTER
            else tk.Label(container, text=sub_text, fg="gray", font=("Segoe UI", 9))
        )
        sub_lbl.pack(anchor="w", padx=16, pady=(0, 12))

        # Release Notes Label
        notes_hdr = (
            ctk.CTkLabel(
                container,
                text="Release Notes & Highlights:",
                font=ctk.CTkFont(family=_W11["font"], size=12, weight="bold"),
                text_color=_W11["text_sec"],
            )
            if HAS_CUSTOMTKINTER
            else tk.Label(container, text="Release Notes & Highlights:", font=("Segoe UI", 9, "bold"))
        )
        notes_hdr.pack(anchor="w", padx=16, pady=(0, 4))

        # Scrollable Release Notes Box
        if HAS_CUSTOMTKINTER:
            self.notes_box = ctk.CTkTextbox(
                container,
                height=130,
                font=ctk.CTkFont(family=_W11["font"], size=11),
                corner_radius=6,
                fg_color=_W11["surface_0"],
                border_width=1,
                border_color=_W11["border"],
                wrap="word",
            )
            self.notes_box.pack(fill="both", expand=True, padx=16, pady=(0, 8))
            clean_notes = self.update_info.release_notes or "A new version of Login Wallpaper Selector is available on GitHub."
            self.notes_box.insert("1.0", clean_notes)
            self.notes_box.configure(state="disabled")
        else:
            self.notes_box = tk.Text(container, height=7, wrap="word", font=("Segoe UI", 9))
            self.notes_box.pack(fill="both", expand=True, padx=16, pady=(0, 8))
            self.notes_box.insert("1.0", self.update_info.release_notes or "New version available.")
            self.notes_box.config(state="disabled")

        # Progress Area
        self.status_lbl = (
            ctk.CTkLabel(
                container,
                text="",
                font=ctk.CTkFont(family=_W11["font"], size=11),
                text_color=_W11["text_sec"],
                wraplength=480,
                justify="left",
            )
            if HAS_CUSTOMTKINTER
            else tk.Label(container, text="", wraplength=480, justify="left")
        )
        self.status_lbl.pack(fill="x", padx=16, pady=(2, 4))

        if HAS_CUSTOMTKINTER:
            self.progress_bar = ctk.CTkProgressBar(
                container,
                height=4,
                corner_radius=2,
                progress_color=_W11["accent"],
            )
            self.progress_bar.pack(fill="x", padx=16, pady=(0, 6))
            self.progress_bar.set(0)
        else:
            self.progress_bar = None

    def on_start_update(self) -> None:
        """Trigger update workflow in background with live GUI feedback."""
        if self.is_updating:
            return
        self.is_updating = True

        if HAS_CUSTOMTKINTER:
            self.update_btn.configure(state="disabled", text="Updating...")
            self.later_btn.configure(state="disabled")
        else:
            self.update_btn.config(state="disabled", text="Updating...")
            self.later_btn.config(state="disabled")

        def _progress(msg: str, frac: float):
            def _ui():
                if HAS_CUSTOMTKINTER:
                    self.status_lbl.configure(text=msg)
                    if self.progress_bar:
                        self.progress_bar.set(frac)
                else:
                    self.status_lbl.config(text=msg)
            self.window.after(0, _ui)

        def _worker():
            success, err = apply_update(self.update_info, progress_callback=_progress)
            if success:
                _progress("✓ Update complete! Restarting application in 1.5 seconds...", 1.0)
                time.sleep(1.5)
                self.window.after(0, self._perform_restart)
            else:
                # Clean error message: grab informative last line to keep dialog uncluttered
                clean_err = "Unknown error"
                if err:
                    lines = [ln.strip() for ln in err.splitlines() if ln.strip()]
                    clean_err = lines[-1] if lines else str(err)
                    if len(clean_err) > 90:
                        clean_err = clean_err[:90] + "..."
                _progress(f"✗ Update failed: {clean_err}", 0.0)

                def _re_enable():
                    if HAS_CUSTOMTKINTER:
                        self.update_btn.configure(state="normal", text="Retry Update")
                        self.later_btn.configure(state="normal", text="Close")
                    else:
                        self.update_btn.config(state="normal", text="Retry Update")
                        self.later_btn.config(state="normal", text="Close")
                    self.is_updating = False
                self.window.after(0, _re_enable)

        threading.Thread(target=_worker, daemon=True).start()

    def _perform_restart(self) -> None:
        """Close modal and parent window cleanly, then execute detached restart."""
        try:
            self.window.destroy()
        except Exception:
            pass
        try:
            if hasattr(self, "parent") and self.parent:
                self.parent.destroy()
        except Exception:
            pass
        restart_application()


