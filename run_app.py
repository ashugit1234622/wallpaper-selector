"""Application entry point for compiled executable packaging."""

import sys
from pathlib import Path

# Ensure src directory is on sys.path
root_dir = Path(__file__).resolve().parent
src_dir = root_dir / "src"
if src_dir.exists() and str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from login_wallpaper_selector.__main__ import main

if __name__ == "__main__":
    main()
