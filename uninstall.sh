#!/usr/bin/env bash
# Uninstaller for Linux and macOS
echo "=========================================="
echo " Uninstalling Login Wallpaper Selector     "
echo "=========================================="

# 1. Deregister login autostart
python3 -m login_wallpaper_selector --uninstall

# 2. Remove CLI launcher
rm -f "$HOME/.local/bin/login-wallpaper-selector"

echo "Application uninstalled successfully."
