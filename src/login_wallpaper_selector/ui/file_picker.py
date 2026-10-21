"""Native OS file picker integration for Local Storage wallpapers."""

from __future__ import annotations
import tkinter as tk
from tkinter import filedialog
from pathlib import Path
from typing import Optional


def pick_local_image(parent: Optional[tk.Tk] = None) -> Optional[Path]:
    """Open the native file picker dialog for selecting a local wallpaper image.
    
    Returns:
        Path to selected image, or None if user canceled.
    """
    filetypes = [
        ("Image Files", "*.jpg;*.jpeg;*.png;*.webp;*.bmp"),
        ("JPEG Files", "*.jpg;*.jpeg"),
        ("PNG Files", "*.png"),
        ("WebP Files", "*.webp"),
        ("All Files", "*.*"),
    ]

    selected_str = filedialog.askopenfilename(
        parent=parent,
        title="Choose a Wallpaper Image",
        filetypes=filetypes,
    )

    if not selected_str:
        return None

    path = Path(selected_str)
    if path.exists() and path.is_file():
        return path

    return None
