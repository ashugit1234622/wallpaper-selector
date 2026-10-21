#!/usr/bin/env bash
# Single-command per-user installer for Linux and macOS
set -e

echo "=========================================="
echo " Installing Login Wallpaper Selector       "
echo "=========================================="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 1. Check Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not found."
    exit 1
fi

echo "[1/4] Installing package in user environment..."
python3 -m pip install --user -e "$SCRIPT_DIR"

# 2. Setup CLI launcher in ~/.local/bin
echo "[2/4] Setting up CLI launcher..."
mkdir -p "$HOME/.local/bin"
cat << 'EOF' > "$HOME/.local/bin/login-wallpaper-selector"
#!/usr/bin/env bash
exec python3 -m login_wallpaper_selector "$@"
EOF
chmod +x "$HOME/.local/bin/login-wallpaper-selector"

# 3. Register autostart
echo "[3/4] Registering login startup entry..."
python3 -m login_wallpaper_selector --install

# 4. Verification check
echo "[4/4] Verifying installation..."
python3 -m login_wallpaper_selector --check

echo "============================================================"
echo " Installation Complete!"
echo " The selector will run automatically on desktop login."
echo "============================================================"
