"""Command-line interface and entrypoint for Login Wallpaper Selector."""

from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path

from .core.config import AppConfig
from .core.models import WallpaperCategory, WallpaperPosition, ColorPalette, WallpaperMood
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


def create_desktop_shortcut() -> int:
    """Create or update Windows desktop shortcut and project root shortcut with custom icon."""
    if sys.platform != "win32":
        print("Desktop shortcut creation is currently supported on Windows.")
        return 1

    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        desktop = shell.SpecialFolders("Desktop")

        project_root = Path(__file__).resolve().parents[2]
        pythonw = Path(sys.executable).parent / "pythonw.exe"
        target = str(pythonw) if pythonw.exists() else sys.executable
        icon_path = project_root / "assets" / "icon.ico"
        description = "Login Wallpaper Selector - Smart Desktop & Lock Screen Wallpapers with Rotation, Mood & Color Filters"

        target_paths = [
            Path(desktop) / "Login Wallpaper Selector.lnk",
            project_root / "Login Wallpaper Selector.lnk",
        ]

        for shortcut_path in target_paths:
            shortcut = shell.CreateShortcut(str(shortcut_path))
            shortcut.TargetPath = target
            shortcut.Arguments = "-m login_wallpaper_selector"
            shortcut.WorkingDirectory = str(project_root)
            if icon_path.exists():
                shortcut.IconLocation = str(icon_path)
            shortcut.Description = description
            shortcut.Save()

        print("✓ Updated shortcuts successfully:")
        for sp in target_paths:
            print(f"  Location: {sp}")
        print(f"  Target: {target} -m login_wallpaper_selector")
        if icon_path.exists():
            print(f"  Icon: {icon_path}")
        return 0
    except Exception as e:
        print(f"✗ Failed to create/update shortcut: {e}")
        return 1


def set_category_headless(
    category_str: str,
    mode: Optional[str] = None,
    also_lockscreen: bool = False,
    color_str: Optional[str] = None,
    mood_str: Optional[str] = None,
    layout_aware: Optional[bool] = None,
    keyword_str: Optional[str] = None,
) -> int:
    """Directly fetch and apply a category wallpaper headlessly."""
    category = None
    for c in WallpaperCategory:
        if c.value.lower() == category_str.lower():
            category = c
            break

    if not category or category == WallpaperCategory.LOCAL_STORAGE:
        print(f"Invalid online category '{category_str}'. Choose from: Space, Nature, Art, Portrait.")
        return 1

    color_palette = None
    if color_str:
        for p in ColorPalette:
            if p.value.lower() == color_str.lower():
                color_palette = p
                break

    wallpaper_mood = None
    if mood_str:
        for m in WallpaperMood:
            if m.value.lower() == mood_str.lower():
                wallpaper_mood = m
                break

    config = AppConfig.load()
    if layout_aware is not None:
        config.desktop_layout_awareness = layout_aware
    history = HistoryTracker(config)
    cache = CacheManager(config)
    router = ProviderRouter(config, history, cache)
    adapter = get_wallpaper_adapter()

    pos_mode = mode or config.default_position
    mood_desc = f" [{wallpaper_mood.value}]" if wallpaper_mood and wallpaper_mood != WallpaperMood.ANY else ""
    color_desc = f" ({color_palette.value})" if color_palette and color_palette != ColorPalette.ANY else ""
    kw_desc = f" matching '{keyword_str}'" if keyword_str else ""
    print(f"Acquiring {category.value}{kw_desc}{mood_desc}{color_desc} wallpaper (Mode: {pos_mode})...")

    def _cli_status(msg: str, attempt: int, total_attempts: int):
        print(f"  [{attempt}/{total_attempts}] {msg}")

    meta, err = router.acquire_wallpaper_for_category(
        category,
        mode=pos_mode,
        status_callback=_cli_status,
        color=color_palette,
        mood=wallpaper_mood,
        keyword=keyword_str,
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

        color_info = f" | Color: {meta.dominant_color_hex}" if getattr(meta, "dominant_color_hex", None) else ""
        mood_info = f" | Mood: {meta.mood}" if getattr(meta, "mood", None) else ""
        print(f"✓ Successfully applied '{meta.title}' ({meta.creator}){lock_msg}{mood_info}{color_info}")
        print(f"  License: {meta.license}")
        print(f"  Saved to: {meta.local_path}")
        return 0
    else:
        print("Failed to apply wallpaper via desktop adapter.")
        return 1


def run_rotation_daemon(check_interval_sec: int = 30) -> int:
    """Run continuous wallpaper rotation daemon."""
    from .core.scheduler import WallpaperRotationDaemon
    config = AppConfig.load()
    daemon = WallpaperRotationDaemon(config)
    try:
        daemon.run_loop(check_interval_sec=check_interval_sec)
        return 0
    except KeyboardInterrupt:
        daemon.stop()
        print("\nDaemon terminated by user.")
        return 0


def run_rotate_now() -> int:
    """Trigger an immediate wallpaper rotation cycle."""
    from .core.scheduler import WallpaperRotationDaemon
    config = AppConfig.load()
    daemon = WallpaperRotationDaemon(config)
    print(f"Executing immediate wallpaper rotation (Interval: {config.rotation_interval_minutes}m)...")

    def _status(msg, attempt, total):
        print(f"  [{attempt}/{total}] {msg}")

    meta, err = daemon.rotate_now(status_callback=_status)
    if meta:
        print(f"✓ Rotated to '{meta.title}' ({meta.category})")
        print(f"  Saved to: {meta.local_path}")
        return 0
    else:
        print(f"✗ Rotation failed: {err}")
        return 1


def run_check_update() -> int:
    """Check GitHub repository for newer releases."""
    from .core.updater import check_for_updates
    config = AppConfig.load()
    print("Checking GitHub repository for updates...")
    res = check_for_updates(config, force=True)
    print(f"Current Version: v{res.current_version}")
    if res.update_available:
        print(f"🚀 New Update Available: v{res.latest_version}")
        print(f"Release Title : {res.release_title}")
        print(f"Published At  : {res.published_at}")
        print(f"Release Notes :\n{res.release_notes}")
        print("\nRun 'python -m login_wallpaper_selector --update' to download and install.")
        return 0
    elif res.error and "No releases found" not in res.error:
        print(f"Notice: {res.error}")
        return 0
    else:
        print(f"✓ Application is up to date (v{res.current_version}).")
        return 0


def run_update() -> int:
    """Download and install the latest update."""
    from .core.updater import check_for_updates, apply_update
    config = AppConfig.load()
    print("Checking GitHub repository for updates...")
    res = check_for_updates(config, force=True)
    if not res.update_available:
        print(f"✓ Application is already at latest version (v{res.current_version}).")
        return 0

    print(f"⬇️ Downloading and installing update v{res.latest_version}...")
    def _prog(msg, frac):
        pct = int(frac * 100)
        print(f"  [{pct}%] {msg}")

    success, err = apply_update(res, progress_callback=_prog)
    if success:
        print(f"✓ Successfully updated to v{res.latest_version}!")
        return 0
    else:
        print(f"✗ Update failed: {err}")
        return 1


def launch_gui(is_login: bool = False, initial_tool: str = "wallpaper") -> None:
    """Launch the graphical desktop utility suite."""
    print("=== Desktop Utility Suite ===", flush=True)
    config = AppConfig.load()

    if is_login:
        # Wait for desktop session to be ready
        print("[*] Waiting for desktop session stabilization...", flush=True)
        detector = SessionDetector(stabilization_delay_seconds=config.session_delay_seconds)
        detector.wait_until_ready(log_fn=print)

    print("[*] Opening Desktop Utility Suite GUI. Logs will appear below as you interact with the app...", flush=True)
    from .ui.shell import AppShell
    shell = AppShell(config)
    if initial_tool and initial_tool != "wallpaper":
        shell.switch_tool(initial_tool)
    shell.run()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="login-wallpaper-selector",
        description="Desktop utility suite featuring Wallpaper Selector and Download Folder Organizer.",
    )
    parser.add_argument("--on-login", action="store_true", help="Launch triggered by desktop login (waits for session ready)")
    parser.add_argument("--organizer", action="store_true", help="Launch directly into the Download Folder Organizer tool")
    parser.add_argument("--check", action="store_true", help="Run system health check on APIs, adapters, and autostart")
    parser.add_argument("--status", action="store_true", help="Show current application status and metadata")
    parser.add_argument("--install", action="store_true", help="Register current-user login autostart")
    parser.add_argument("--uninstall", action="store_true", help="Deregister login autostart")
    parser.add_argument("--set-category", type=str, help="Headlessly fetch and apply a category (Space, Nature, Art, Portrait)")
    parser.add_argument("--keyword", "-k", type=str, default=None, help="Search for wallpapers matching a custom keyword (e.g. 'Black Hole')")
    parser.add_argument("--mode", type=str, choices=["Fill", "Fit"], help="Display mode (Fill or Fit)")
    parser.add_argument("--set-lockscreen", action="store_true", help="Also apply the fetched wallpaper to system lock screen")
    parser.add_argument("--create-shortcut", action="store_true", help="Create a desktop shortcut with custom icon to run the app")
    parser.add_argument("--color", type=str, choices=["Any", "Blue", "Purple", "Green", "Warm", "Monochrome"], help="Filter by dominant color palette")
    parser.add_argument("--mood", type=str, choices=["Any", "Peaceful", "Dark", "Cinematic", "Minimalist", "Vibrant"], help="Filter by wallpaper mood/aesthetic vibe")
    parser.add_argument("--layout-aware", action="store_true", default=None, help="Align crop away from desktop icon clutter")
    parser.add_argument("--no-layout-aware", action="store_false", dest="layout_aware", help="Disable layout-aware crop alignment")
    parser.add_argument("--rotate-now", action="store_true", help="Instantly trigger one automated wallpaper rotation")
    parser.add_argument("--daemon", action="store_true", help="Run background wallpaper rotation daemon")
    parser.add_argument("--interval", type=str, help="Set rotation interval (e.g. 30m, 1h, 3h, daily)")
    parser.add_argument("--check-update", action="store_true", help="Check GitHub for available software updates")
    parser.add_argument("--update", action="store_true", help="Download and install the latest available software update")

    args = parser.parse_args()

    if args.interval:
        from .core.scheduler import parse_interval_minutes
        cfg = AppConfig.load()
        cfg.rotation_interval_minutes = parse_interval_minutes(args.interval)
        cfg.rotation_enabled = True
        cfg.save()
        print(f"✓ Updated rotation interval to {cfg.rotation_interval_minutes} minutes (Enabled: True).")

    if args.check:
        sys.exit(run_check())
    elif args.status:
        run_status()
        sys.exit(0)
    elif args.install:
        sys.exit(register_autostart())
    elif args.uninstall:
        sys.exit(deregister_autostart())
    elif args.create_shortcut:
        sys.exit(create_desktop_shortcut())
    elif args.rotate_now:
        sys.exit(run_rotate_now())
    elif args.daemon:
        sys.exit(run_rotation_daemon())
    elif args.check_update:
        sys.exit(run_check_update())
    elif args.update:
        sys.exit(run_update())
    elif args.set_category or args.keyword:
        cat_to_use = args.set_category or "Space"
        sys.exit(set_category_headless(cat_to_use, args.mode, args.set_lockscreen, args.color, args.mood, args.layout_aware, keyword_str=args.keyword))
    else:
        # Default action: launch GUI dialog
        initial = "organizer" if args.organizer else "wallpaper"
        launch_gui(is_login=args.on_login, initial_tool=initial)


if __name__ == "__main__":
    main()
