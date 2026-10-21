# Login Wallpaper Selector

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

A lightweight, reliable desktop application that prompts the logged-in user upon desktop sign-in to select a wallpaper category, downloads verified open-content imagery, and automatically updates the desktop background.

---

## Features

- **Automatic Post-Login Launch:** Launches automatically after user sign-in once the desktop session is confirmed active and stable (using an active Session Readiness Poller).
- **Five Fixed Categories:**
  1. **🚀 Space:** High-resolution public domain astronomy imagery powered by the **NASA Image and Video Library API** (with fallback to Wikimedia Commons).
  2. **🌿 Nature:** Curated landscape photography from **Wikimedia Commons** filtered for landscape aspect ratios and open licensing.
  3. **🎨 Art:** High-resolution public domain CC0 masterworks from the **Art Institute of Chicago Open Access API** (IIIF delivery) and Wikimedia Commons.
  4. **👤 Portrait:** Classical fine art portraits and featured photography from **Wikimedia Commons**.
  5. **📁 Local Storage:** Native operating system file picker allowing selection of JPEG, PNG, or WebP images without moving or modifying the original file. Graceful cancellation closes without altering the wallpaper.
- **Proportional Display Modes:**
  - **Fill (Default):** Crops top/bottom or left/right proportionally to fill the monitor.
  - **Fit (Optional):** Letterboxes/pillarboxes the entire image with the desktop background color without distortion.
  - *Disproportionate stretching is strictly prohibited.*
- **Reliability & Safeguards:**
  - **Atomic Downloads:** Images download to `.part` files, are verified with Pillow, and are committed atomically. Corrupt or partial images are never applied.
  - **Offline Fallback:** If network is unavailable or APIs timeout, falls back to the most recent valid cached image.
  - **LRU Cache Quota:** Automatically prunes oldest cached images when total cache exceeds the quota (default: 500 MB).
  - **Deduplication History:** Remembers the last 50 applied image IDs to prevent immediate repeats on successive logins.
  - **Licensing & Attribution:** Extracts and stores title, creator, source URL, and license in a local `metadata.json` record.
- **Per-User Scope:** Requires zero administrative or `sudo` privileges.

---

## Quick Installation

### Windows 10 & 11 (PowerShell)

Run the single-command installer:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

This will:
1. Install the application in editable mode using `uv` or `pip`.
2. Create a command-line launcher (`login-wallpaper-selector`) in your user PATH.
3. Register current-user login startup in `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.
4. Run a system health check verifying desktop adapters, autostart, and API connectivity.

### Linux & macOS

Run the single-command installer:

```bash
chmod +x install.sh
./install.sh
```

---

## Usage

### Launch Manually
```bash
login-wallpaper-selector
# or
python -m login_wallpaper_selector
```

### System Health Check
Verify network connectivity to NASA, Wikimedia, and Art Institute APIs, autostart registration, and cache health:
```bash
login-wallpaper-selector --check
```

### Check Current Status & Wallpaper Metadata
```bash
login-wallpaper-selector --status
```

### Headless Mode (CLI Wallpaper Switcher)
Directly fetch and apply a wallpaper category without opening the GUI dialog:
```bash
login-wallpaper-selector --set-category Space
login-wallpaper-selector --set-category Nature --mode Fit
login-wallpaper-selector --set-category Art
login-wallpaper-selector --set-category Portrait
```

### Autostart Management
```bash
# Register autostart for the current user
login-wallpaper-selector --install

# Deregister autostart
login-wallpaper-selector --uninstall
```

---

## Uninstallation

To remove the application and startup registration:

### Windows:
```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
```

### Linux & macOS:
```bash
./uninstall.sh
```

---

## Testing

Run the full automated pytest suite:

```bash
python -m pytest tests/
```

All 15 tests cover:
- License validation and attribution generation
- Cache atomicity, Pillow verification, SHA-256 calculation, and quota pruning
- Deduplication history tracking
- Local Storage image validation and non-destructive handling
- API provider candidate parsing (NASA, Wikimedia, Art Institute of Chicago)
- Platform adapter and autostart registration toggles

---

## License

This project is licensed under the [MIT License](LICENSE). All downloaded wallpapers are sourced from legitimate public domain and open-licensed repositories (NASA, Wikimedia Commons, Art Institute of Chicago) with complete attribution recorded locally.
