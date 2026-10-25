#!/usr/bin/env bash
# ==============================================================================
# Desktop Utility Suite - Linux AppImage Build Script
#
# Builds a standalone, source-code-protected AppImage for Linux.
# Produces: dist_installer/Desktop-Utility-Suite-v2.0.0-x86_64.AppImage
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${HOME}/build_appimage"
APP_DIR="${BUILD_DIR}/AppDir"
DIST_DIR="${SCRIPT_DIR}/dist_installer"
APPIMAGE_NAME="Desktop-Utility-Suite-v2.0.0-x86_64.AppImage"

echo "=========================================================="
echo " Building Desktop Utility Suite AppImage (Linux Standalone)"
echo "=========================================================="

mkdir -p "${BUILD_DIR}"
mkdir -p "${DIST_DIR}"

# 1. Prepare Python Build Environment
if [ ! -d "${BUILD_DIR}/venv" ]; then
    echo "[*] Creating build virtualenv..."
    python3 -m venv "${BUILD_DIR}/venv"
    "${BUILD_DIR}/venv/bin/pip" install --upgrade pip
fi

echo "[*] Installing build requirements..."
"${BUILD_DIR}/venv/bin/pip" install --upgrade pyinstaller httpx pillow platformdirs customtkinter pystray
"${BUILD_DIR}/venv/bin/pip" install -e "${SCRIPT_DIR}"

# 2. Compile to Standalone Binary via PyInstaller
echo "[*] Compiling binary with PyInstaller..."
cd "${BUILD_DIR}"
rm -rf dist build "${APP_DIR}"

"${BUILD_DIR}/venv/bin/pyinstaller" \
    --onedir \
    --windowed \
    --name desktop-utility-suite \
    --add-data "${SCRIPT_DIR}/src/login_wallpaper_selector/providers/uhd_4k_catalog.py:login_wallpaper_selector/providers" \
    --collect-all customtkinter \
    --collect-all PIL \
    --collect-all pystray \
    --hidden-import login_wallpaper_selector \
    --hidden-import httpx \
    --hidden-import platformdirs \
    "${SCRIPT_DIR}/run_app.py"

# 3. Assemble AppDir Layout
echo "[*] Assembling AppDir structure..."
mkdir -p "${APP_DIR}/usr/bin"
mkdir -p "${APP_DIR}/usr/share/applications"
mkdir -p "${APP_DIR}/usr/share/icons/hicolor/256x256/apps"

# Copy compiled binaries (no .py source files included)
cp -r "${BUILD_DIR}/dist/desktop-utility-suite/"* "${APP_DIR}/usr/bin/"

# Copy Desktop Entry, Icon, and AppRun
cp "${SCRIPT_DIR}/desktop-utility-suite.desktop" "${APP_DIR}/desktop-utility-suite.desktop"
cp "${SCRIPT_DIR}/desktop-utility-suite.desktop" "${APP_DIR}/usr/share/applications/desktop-utility-suite.desktop"
cp "${SCRIPT_DIR}/assets/icon.png" "${APP_DIR}/desktop-utility-suite.png"
cp "${SCRIPT_DIR}/assets/icon.png" "${APP_DIR}/usr/share/icons/hicolor/256x256/apps/desktop-utility-suite.png"

# Copy AppRun and ensure executable
cp "${SCRIPT_DIR}/AppRun" "${APP_DIR}/AppRun"
chmod +x "${APP_DIR}/AppRun"
chmod +x "${APP_DIR}/usr/bin/desktop-utility-suite"

# 4. Acquire appimagetool if not present
APPIMAGETOOL="${BUILD_DIR}/appimagetool"
if [ ! -f "${APPIMAGETOOL}" ]; then
    echo "[*] Downloading appimagetool..."
    wget -q https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage -O "${APPIMAGETOOL}"
    chmod +x "${APPIMAGETOOL}"
fi

# 5. Generate Standalone AppImage
echo "[*] Packaging AppImage..."
export ARCH="x86_64"

# In containers or WSL without FUSE, appimagetool needs --appimage-extract-and-run
if ! "${APPIMAGETOOL}" "${APP_DIR}" "${DIST_DIR}/${APPIMAGE_NAME}" 2>/dev/null; then
    echo "[*] Falling back to --appimage-extract-and-run for environments without FUSE..."
    "${APPIMAGETOOL}" --appimage-extract-and-run "${APP_DIR}" "${DIST_DIR}/${APPIMAGE_NAME}"
fi

chmod +x "${DIST_DIR}/${APPIMAGE_NAME}"

echo ""
echo "=========================================================="
echo " [✓] Build Successful!"
echo " Output AppImage: ${DIST_DIR}/${APPIMAGE_NAME}"
echo " File Size: $(du -h "${DIST_DIR}/${APPIMAGE_NAME}" | cut -f1)"
echo "=========================================================="
