# 🖼️ Login Wallpaper Selector

<div align="center">

[![Version](https://img.shields.io/badge/version-1.0.2-blue.svg?style=for-the-badge)](https://github.com/ashugit1234622/wallpaper-selector/releases)
[![Python](https://img.shields.io/badge/python-3.10+-3776ab.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%2F%2011%20%7C%20Linux%20%7C%20macOS-0078d6.svg?style=for-the-badge&logo=windows&logoColor=white)](https://github.com/ashugit1234622/wallpaper-selector)

**A modern, intelligent desktop wallpaper & lock screen manager that greets you on desktop login with high-resolution curated imagery, custom keyword search, live preview mockup, smart rotation, and color/mood filters.**

[⚡ Quick Install](#-single-command-installation-for-any-windows-machine) • [✨ Key Features](#-features) • [🚀 Usage](#-usage-guide) • [🔄 Updates](#-automated-update-system) • [📜 License](#-license)

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
1. Installs all required dependencies (`customtkinter`, `pillow`, `httpx`, `pywin32`) in editable mode.
2. Creates a desktop shortcut **`Login Wallpaper Selector.lnk`** with a custom high-res icon.
3. Adds a user CLI launcher `login-wallpaper-selector` to your PATH.
4. Registers user login autostart in `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.
5. Runs an automated system health check verifying desktop adapters and provider APIs.

---

## ✨ Features

### 🔍 Custom Keyword Search with Intelligent Fallback
Search for any subject (e.g., *"Black Hole"*, *"Cyberpunk"*, *"Alpine Waterfall"*):
- **5-Tier Query Expansion**: Proactively varies synonyms, moods, and contextual styles without ever stripping the core subject.
- **Stage 1 Relevance Gate**: Disqualifies candidates with zero token overlap. Irrelevant 4K images *never* outrank relevant 1080p images.
- **Stage 2 Quality Ranking**: Ranks candidates dynamically based on native monitor aspect ratio match (30 pts), UHD/QHD resolution fidelity (30 pts), and color/mood harmony (25 pts).
- **Clickable Suggestion Chips**: Dynamic pills populated with recent searches and category favorites for one-click discovery.

### 🚀 Five Curated Online Categories
- **🚀 Space**: NASA Image & Video Library and Wallhaven astronomy.
- **🌿 Nature**: Landscape photography from Wallhaven and Wikimedia Commons.
- **🎨 Art**: Open-access masterworks from The Metropolitan Museum of Art (The Met), Art Institute of Chicago (AIC), and Wikimedia.
- **👤 Portrait**: Classical fine art portraits and featured portraiture.
- **📁 Local Storage**: Native OS file picker to load personal local folders.

### 🎨 Dominant Color & Aesthetic Mood Filters
- **Color Palettes**: 🔘 Any, 🔵 Blue, 🟣 Purple, 🟢 Green, 🟠 Warm, ⚫ Dark/Monochrome.
- **Mood Vibes**: ✨ Any, 🕊️ Calm, 🌑 Dark, 🎬 Epic, ◻️ Minimal, 🌈 Vivid.
- **Adaptive Harmonization**: Automatically eliminates bright or contradictory terms when searching with Dark or Monochrome filters.

### 🖥️ Desktop Preview & Layout Awareness
- **Live Screen-Fit Mockup**: Shows exactly how the wallpaper will be cropped on your desktop before applying it.
- **Display Modes**:
  - **Fill (Default)**: Scales proportionally and covers the entire monitor without distortion.
  - **Fit (Letterbox)**: Shows the complete untouched image with background matte.
- **Desktop Layout Awareness**: Aligns crop focus away from standard desktop icon clutter.

### ⭐ Favorites, Ratings & Categories Storage
- **Favorite & Star Rating**: Rate images (1–5 stars) and click ❤️ Favorite.
- **Favorites Category**: Dedicated category button to shuffle and cycle through your favorite wallpapers.
- **Save Wallpaper**: Save favorite wallpapers permanently to organized category subfolders with a single click.

### 🔄 In-App Automated Update System
- **Startup Check**: Asynchronously checks GitHub Releases upon application startup (throttled to once every 4 hours to respect API limits).
- **GUI Download & Install**: Displays new version release notes in an in-app modal. Clicking **"⬇️ Download & Update"** pulls the update, updates dependencies, refreshes shortcuts, and restarts the app with live progress tracking.
- **Manual Check Button**: Check for updates anytime from the GUI header button or via CLI `--check-update`.

### ⏰ Scheduled Auto-Rotation
- Automatically rotates wallpapers in the background at configurable intervals (`30m`, `1h`, `3h`, `daily`).
- Anti-repetition engine tracks previous 50 images to guarantee fresh visuals.

---

## 🚀 Usage Guide

### 1. Launch GUI Dialog
Simply double-click the **Login Wallpaper Selector** desktop shortcut, or run in terminal:
```bash
python -m login_wallpaper_selector
# Or using the command launcher:
login-wallpaper-selector
```

### 2. Headless CLI Commands

| Command | Description |
| :--- | :--- |
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

## 🛠️ Linux & macOS Installation

```bash
git clone https://github.com/ashugit1234622/wallpaper-selector.git
cd wallpaper-selector
chmod +x install.sh
./install.sh
```

---

## 🧪 Testing & Verification

The project includes an automated test suite covering all providers, retry engines, ranking gates, color analyzers, preview generators, and updater modules:

```bash
python -m pytest
```

```
============================= 114 passed in 9.59s =============================
```

---

## 📜 License

Distributed under the [MIT License](LICENSE). Public domain images and CC0 masterworks are attributed according to their respective open-access provider terms.
