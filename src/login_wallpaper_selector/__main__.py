"""Command-line interface and entrypoint for Login Wallpaper Selector."""

from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path

from .core.config import AppConfig
from .core.models import WallpaperCategory, WallpaperPosition
from .core.session import SessionDetector
from .core.cache import CacheManager
from .core.history import HistoryTracker
from .providers.router import ProviderRouter
from .adapters.factory import get_wallpaper_adapter
from .autostart.factory import get_autostart_adapter


def run_check() -> int:
    """Perform comprehensive health check on APIs, adapters, cache, and autostart."""
    print("=== Login Wallpaper Selector Health Check ===")
    config = AppConfig.load()
    all_ok = True

    # 1. Check Platform & Desktop Adapter
    adapter = get_wallpaper_adapter()
    print(f"[*] Detected Wallpaper Adapter: {adapter.platform_name}")
    current_wp = adapter.get_current_wallpaper()
    print(f"[*] Current Desktop Wallpaper: {current_wp or 'Unknown'}")

    # 2. Check Autostart Adapter
    autostart = get_autostart_adapter()
    is_auto = autostart.is_enabled()
    print(f"[*] Autostart Adapter: {autostart.platform_name} (Enabled: {is_auto})")
    if is_auto:
        print(f"    Registered Command: {autostart.get_registered_command()}")

    # 3. Check Cache & Data Directory
    cache = CacheManager(config)
    cache_size_mb = round(cache.get_total_cache_size_bytes() / (1024 * 1024), 2)
    print(f"[*] Cache Directory: {cache.cache_dir} (Usage: {cache_size_mb} MB / Quota: {config.cache_quota_mb} MB)")

    # 4. Check Provider API Connectivity
    history = HistoryTracker(config)
    router = ProviderRouter(config, history, cache)

    print("[*] Testing API connectivity...")
    providers = [
        (router.nasa, WallpaperCategory.SPACE),
        (router.wallhaven, WallpaperCategory.NATURE),
        (router.the_met, WallpaperCategory.ART),
        (router.bing, WallpaperCategory.NATURE),
        (router.wikimedia, WallpaperCategory.NATURE),
        (router.artic, WallpaperCategory.ART),
    ]
    for prov, cat in providers:
        try:
            items = prov.fetch_candidates(cat, limit=1)
            if items:
                print(f"    ✓ {prov.name}: Reachable ({len(items)} candidate found: '{items[0].title[:35]}...')")
            else:
                print(f"    ⚠ {prov.name}: Query succeeded but returned 0 candidates.")
        except Exception as e:
            print(f"    ✗ {prov.name}: Failed to connect ({e})")
            if prov != router.artic:  # Artic is an optional fallback
                all_ok = False

    print("\nHealth check complete.")
    return 0 if all_ok else 1


def run_status() -> None:
    """Print current application status and metadata."""
    config = AppConfig.load()
    cache = CacheManager(config)
    history = HistoryTracker(config)
    autostart = get_autostart_adapter()

    print("=== Login Wallpaper Selector Status ===")
    print(f"Default Display Mode : {config.default_position}")
    print(f"Cache Directory      : {cache.cache_dir}")
    print(f"Cache Consumption    : {round(cache.get_total_cache_size_bytes() / (1024 * 1024), 2)} MB / {config.cache_quota_mb} MB")
    print(f"Recent History Count : {len(history.get_recent_ids())} items")
    print(f"Login Autostart      : {'Enabled' if autostart.is_enabled() else 'Disabled'}")

    latest = cache.get_latest_metadata()
    if latest:
        print("\nLast Applied Wallpaper:")
        print(f"  Title      : {latest.get('title')}")
        print(f"  Category   : {latest.get('category')}")
        print(f"  Provider   : {latest.get('provider')}")
        print(f"  Creator    : {latest.get('creator')}")
        print(f"  License    : {latest.get('license')}")
        print(f"  Local Path : {latest.get('local_path')}")
        print(f"  Applied At : {latest.get('applied_at')}")
    else:
        print("\nNo wallpaper applied through this application yet.")


def register_autostart() -> int:
    """Register this application to launch on user login."""
    autostart = get_autostart_adapter()
    
    # Construct python executable path
    python_exe = sys.executable
    if sys.platform == "win32":
        # Prefer pythonw.exe to prevent terminal popup
        pythonw = Path(python_exe).parent / "pythonw.exe"
        if pythonw.exists():
            python_exe = str(pythonw)

    cmd = f'"{python_exe}" -m login_wallpaper_selector --on-login'
    success = autostart.enable(cmd)
    if success:
        print(f"✓ Registered login autostart for current user via {autostart.platform_name}:")
        print(f"  Command: {cmd}")
        return 0
    else:
        print(f"✗ Failed to register login autostart via {autostart.platform_name}.")
        return 1


def deregister_autostart() -> int:
    """Deregister login autostart."""
    autostart = get_autostart_adapter()
    success = autostart.disable()
    if success:
        print(f"✓ Removed login autostart via {autostart.platform_name}.")
        return 0
    else:
        print(f"✗ Failed to remove login autostart via {autostart.platform_name}.")
        return 1


def set_category_headless(category_str: str, mode: Optional[str] = None, also_lockscreen: bool = False) -> int:
    """Directly fetch and apply a category wallpaper headlessly."""
    category = None
    for c in WallpaperCategory:
        if c.value.lower() == category_str.lower():
            category = c
            break

    if not category or category == WallpaperCategory.LOCAL_STORAGE:
        print(f"Invalid online category '{category_str}'. Choose from: Space, Nature, Art, Portrait.")
        return 1

    config = AppConfig.load()
    history = HistoryTracker(config)
    cache = CacheManager(config)
    router = ProviderRouter(config, history, cache)
    adapter = get_wallpaper_adapter()

    pos_mode = mode or config.default_position
    print(f"Acquiring {category.value} wallpaper (Mode: {pos_mode})...")

    def _cli_status(msg: str, attempt: int, total_attempts: int):
        print(f"  [{attempt}/{total_attempts}] {msg}")

    meta, err = router.acquire_wallpaper_for_category(
        category,
        mode=pos_mode,
        status_callback=_cli_status,
    )
    if not meta:
        print(f"Failed to acquire wallpaper: {err}")
        return 1

    success = adapter.set_wallpaper(Path(meta.local_path), mode=pos_mode)
    if success:
        lock_msg = ""
        if also_lockscreen or config.also_set_lockscreen:
            lock_ok = adapter.set_lockscreen(Path(meta.local_path))
            if lock_ok:
                lock_msg = " & Lock Screen"

        print(f"✓ Successfully applied '{meta.title}' ({meta.creator}){lock_msg}")
        print(f"  License: {meta.license}")
        print(f"  Saved to: {meta.local_path}")
        return 0
    else:
        print("Failed to apply wallpaper via desktop adapter.")
        return 1


def launch_gui(is_login: bool = False) -> None:
    """Launch the graphical selection dialog."""
    config = AppConfig.load()

    if is_login:
        # Wait for desktop session to be ready
        detector = SessionDetector(stabilization_delay_seconds=config.session_delay_seconds)
        detector.wait_until_ready(log_fn=print)

    from .ui.dialog import WallpaperSelectorDialog
    dialog = WallpaperSelectorDialog(config)
    dialog.run()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="login-wallpaper-selector",
        description="Desktop application that prompts user to select a wallpaper category upon login.",
    )
    parser.add_argument("--on-login", action="store_true", help="Launch triggered by desktop login (waits for session ready)")
    parser.add_argument("--check", action="store_true", help="Run system health check on APIs, adapters, and autostart")
    parser.add_argument("--status", action="store_true", help="Show current application status and metadata")
    parser.add_argument("--install", action="store_true", help="Register current-user login autostart")
    parser.add_argument("--uninstall", action="store_true", help="Deregister login autostart")
    parser.add_argument("--set-category", type=str, help="Headlessly fetch and apply a category (Space, Nature, Art, Portrait)")
    parser.add_argument("--mode", type=str, choices=["Fill", "Fit"], help="Display mode (Fill or Fit)")
    parser.add_argument("--set-lockscreen", action="store_true", help="Also apply the fetched wallpaper to system lock screen")

    args = parser.parse_args()

    if args.check:
        sys.exit(run_check())
    elif args.status:
        run_status()
        sys.exit(0)
    elif args.install:
        sys.exit(register_autostart())
    elif args.uninstall:
        sys.exit(deregister_autostart())
    elif args.set_category:
        sys.exit(set_category_headless(args.set_category, args.mode, args.set_lockscreen))
    else:
        # Default action: launch GUI dialog
        launch_gui(is_login=args.on_login)


if __name__ == "__main__":
    main()
