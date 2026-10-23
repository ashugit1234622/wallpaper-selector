# ⚡ Desktop Utility Suite

<div align="center">

[![Version](https://img.shields.io/badge/version-1.5.0-blue.svg?style=for-the-badge)](https://github.com/ashugit1234622/wallpaper-selector/releases)
[![Python](https://img.shields.io/badge/python-3.10+-3776ab.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%2F%2011%20%7C%20Linux%20%7C%20macOS-0078d6.svg?style=for-the-badge&logo=windows&logoColor=white)](https://github.com/ashugit1234622/wallpaper-selector)

**A modular desktop utility suite featuring intelligent Wallpaper Management and an offline, safe Download Folder Organizer with live preview, collision protection, and durable undo.**

[⚡ Quick Install](#-single-command-installation-for-any-windows-machine) • [✨ Suite Tools](#-suite-tools) • [🚀 Usage](#-usage-guide) • [🔄 Updates](#-automated-update-system) • [📜 License](#-license)

---

</div>

## ⚡ Single-Command Installation for Any Windows Machine

Open **PowerShell** (no Administrator privileges required) and run:

```powershell
git clone https://github.com/ashugit1234622/wallpaper-selector.git
cd wallpaper-selector
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

### What the Installer Does Automatically:
1. Installs all required dependencies (`customtkinter`, `pillow`, `httpx`, `platformdirs`, `pywin32`) in editable mode.
2. Creates a desktop shortcut **`Desktop Utility Suite.lnk`** with custom high-res icon.
3. Adds a user CLI launcher `login-wallpaper-selector` to your PATH.
4. Registers user login autostart in `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.
5. Runs an automated system health check verifying desktop adapters and provider APIs.

---

## ✨ Suite Tools

The suite provides a persistent left navigation sidebar allowing seamless switching between independent desktop utilities without window duplication or application restart.

### 1. 🖼️ Wallpaper Manager
- **🔍 Custom Keyword Search**: 5-tier query expansion with intelligent multi-source fallback (NASA, Wallhaven, The Met, Art Institute of Chicago, Wikimedia).
- **🎨 Color & Mood Harmonization**: Filter by dominant palette (Blue, Purple, Green, Warm, Monochrome) and aesthetic vibes (Calm, Dark, Epic, Minimal, Vivid).
- **🖥️ Screen-Fit Live Preview**: Mockup rendering with Fill (proportional cover) and Fit (pillarbox/letterbox) display modes, plus layout-aware crop alignment away from desktop icon clutter.
- **⭐ Favorites & Local Storage**: 1–5 star rating system, favorites shuffling, and single-click image saving to organized category folders.
- **⏰ Scheduled Rotation**: Background wallpaper rotation daemon with anti-repetition tracking.

### 2. 📁 Download Folder Organizer (New in v1.5.0!)
- **Deterministic Offline Classifier**: Extensible rules mapping extensions across 9 categories (*Documents, Images, Videos, Audio, Archives, Installers, Code & Dev, Spreadsheets & Data, Presentations, Other*). Supports compound extensions like `.tar.gz` and custom user mappings.
- **Folder Analysis Dashboard**: 5 KPI summary cards displaying Discovered Files, Categorized Files, Proposed Moves, Conflicts / Review, and Total Size.
- **Selectable Organization Modes**:
  - **By File Type**: Categorized into clean subfolders (`Images/`, `Documents/`, etc.).
  - **By Date**: Organized into chronological `YYYY/MM/` subfolders.
  - **By File Type and Date**: Category folders with nested `YYYY/MM/` dates.
- **Safe Pre-Execution Preview**: Interactive table with per-file checkboxes, destination paths, size, search filters, and "Select All" / "Deselect All". Files are **never** moved without user approval.
- **Collision Protection**: Never silently overwrites files. "Keep Both" automatically adds unique numbering (`file (1).ext`) for both existing on-disk files and in-batch duplicate names.
- **Durable Undo Engine**: Persistent JSON transaction journal in `%LOCALAPPDATA%`. "Undo Last Batch" verifies file integrity and restores moved files back to their exact original locations.

---

## 🚀 Usage Guide

### 1. Launch GUI Suite
Double-click the desktop shortcut, or run in terminal:
```bash
python -m login_wallpaper_selector
# Or using the command launcher:
login-wallpaper-selector
```

To launch directly into the **Download Organizer**:
```bash
python -m login_wallpaper_selector --organizer
```

### 2. Headless CLI Commands

| Command | Description |
| :--- | :--- |
| `python -m login_wallpaper_selector --organizer` | Launch GUI directly into the Download Folder Organizer |
| `python -m login_wallpaper_selector --keyword "Black Hole"` | Search and apply wallpaper matching keyword |
| `python -m login_wallpaper_selector --set-category Space` | Headlessly fetch and apply Space wallpaper |
| `python -m login_wallpaper_selector --set-category Nature --mood Peaceful` | Apply Nature wallpaper with Calm mood |
| `python -m login_wallpaper_selector --color Blue --mode Fill` | Apply with dominant Blue color in Fill mode |
| `python -m login_wallpaper_selector --set-lockscreen` | Also synchronize wallpaper with Windows Lock Screen |
| `python -m login_wallpaper_selector --rotate-now` | Instantly trigger one automated wallpaper rotation |
| `python -m login_wallpaper_selector --daemon` | Run background rotation scheduler daemon |
| `python -m login_wallpaper_selector --check-update` | Check GitHub for software updates |
| `python -m login_wallpaper_selector --update` | Download and install latest update from GitHub |
| `python -m login_wallpaper_selector --status` | Display cache consumption and metadata of last wallpaper |
| `python -m login_wallpaper_selector --create-shortcut` | Recreate or update Windows desktop shortcut |

---

## 🔄 Automated Update System
- **Startup Check**: Asynchronously checks GitHub Releases upon application startup (throttled to once every 4 hours).
- **In-App Modal**: Displays release notes and version diffs. Clicking **"⬇️ Download & Update"** downloads the release, updates dependencies, refreshes shortcuts, and restarts with live progress.
- **Manual Check**: Check for updates anytime from the sidebar button or via `--check-update`.

---

## 🧪 Testing & Verification

The suite includes an automated test suite covering all providers, retry engines, preview generators, classifiers, scanners, planners, executors, and journal undo engines:

```bash
python -m pytest
```

```text
============================= 146 passed in 9.68s =============================
```

---

## 📜 License

Distributed under the [MIT License](LICENSE). Public domain images and CC0 masterworks are attributed according to their respective open-access provider terms.
