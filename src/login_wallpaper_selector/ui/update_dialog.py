"""In-app modal dialog displaying update availability, release notes, and download progress."""

from __future__ import annotations
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
        self.window.geometry("520x420")
        self.window.resizable(False, False)
        self.window.attributes("-topmost", True)

        self._center_window(520, 420)
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
        container = ctk.CTkFrame(self.window) if HAS_CUSTOMTKINTER else tk.Frame(self.window)
        container.pack(fill="both", expand=True, padx=20, pady=20)

        # Header Badge
        header_text = f"🚀 New Major Update: v{self.update_info.latest_version}"
        header_lbl = (
            ctk.CTkLabel(container, text=header_text, font=ctk.CTkFont(size=18, weight="bold"), text_color="#38bdf8")
            if HAS_CUSTOMTKINTER
            else tk.Label(container, text=header_text, font=("Helvetica", 14, "bold"), fg="#0284c7")
        )
        header_lbl.pack(anchor="w", pady=(0, 4))

        sub_text = f"Current version: v{self.update_info.current_version}  •  Release: {self.update_info.release_title or self.update_info.latest_version}"
        sub_lbl = (
            ctk.CTkLabel(container, text=sub_text, font=ctk.CTkFont(size=12), text_color="gray")
            if HAS_CUSTOMTKINTER
            else tk.Label(container, text=sub_text, fg="gray", font=("Helvetica", 9))
        )
        sub_lbl.pack(anchor="w", pady=(0, 12))

        # Release Notes Label
        notes_hdr = (
            ctk.CTkLabel(container, text="Release Notes & Highlights:", font=ctk.CTkFont(size=12, weight="bold"))
            if HAS_CUSTOMTKINTER
            else tk.Label(container, text="Release Notes & Highlights:", font=("Helvetica", 9, "bold"))
        )
        notes_hdr.pack(anchor="w", pady=(0, 4))

        # Scrollable Release Notes Box
        if HAS_CUSTOMTKINTER:
            self.notes_box = ctk.CTkTextbox(container, height=140, font=ctk.CTkFont(size=11), wrap="word")
            self.notes_box.pack(fill="x", pady=(0, 12))
            clean_notes = self.update_info.release_notes or "A new version of Login Wallpaper Selector is available on GitHub."
            self.notes_box.insert("1.0", clean_notes)
            self.notes_box.configure(state="disabled")
        else:
            self.notes_box = tk.Text(container, height=8, wrap="word", font=("Helvetica", 9))
            self.notes_box.pack(fill="x", pady=(0, 12))
            self.notes_box.insert("1.0", self.update_info.release_notes or "New version available.")
            self.notes_box.config(state="disabled")

        # Progress Area (Initially hidden / ready)
        self.status_lbl = (
            ctk.CTkLabel(container, text="", font=ctk.CTkFont(size=12))
            if HAS_CUSTOMTKINTER
            else tk.Label(container, text="")
        )
        self.status_lbl.pack(fill="x", pady=(2, 4))

        if HAS_CUSTOMTKINTER:
            self.progress_bar = ctk.CTkProgressBar(container)
            self.progress_bar.pack(fill="x", pady=(0, 14))
            self.progress_bar.set(0)
        else:
            self.progress_bar = None

        # Button Toolbar
        btn_frame = ctk.CTkFrame(container, fg_color="transparent") if HAS_CUSTOMTKINTER else tk.Frame(container)
        btn_frame.pack(fill="x", side="bottom")

        if HAS_CUSTOMTKINTER:
            self.later_btn = ctk.CTkButton(
                btn_frame,
                text="Remind Me Later",
                width=130,
                height=34,
                fg_color="#374151",
                hover_color="#4b5563",
                command=self.window.destroy,
            )
            self.later_btn.pack(side="left")

            self.update_btn = ctk.CTkButton(
                btn_frame,
                text="⬇️ Download & Update",
                width=170,
                height=34,
                font=ctk.CTkFont(size=13, weight="bold"),
                fg_color="#2563eb",
                hover_color="#1d4ed8",
                command=self.on_start_update,
            )
            self.update_btn.pack(side="right")
        else:
            self.later_btn = tk.Button(btn_frame, text="Remind Me Later", command=self.window.destroy)
            self.later_btn.pack(side="left")

            self.update_btn = tk.Button(btn_frame, text="⬇️ Download & Update", command=self.on_start_update)
            self.update_btn.pack(side="right")

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
                _progress("✓ Update complete! Restarting application in 2 seconds...", 1.0)
                time.sleep(2.0)
                restart_application()
            else:
                _progress(f"✗ Update failed: {err}", 0.0)
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
