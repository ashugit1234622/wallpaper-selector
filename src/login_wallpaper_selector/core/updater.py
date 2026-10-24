"""Automated update checking, downloading, installing, and restarting engine."""

from __future__ import annotations
import os
import sys
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple, Callable
import httpx

from .config import AppConfig


@dataclass
class UpdateCheckResult:
    """Detailed result of an update availability check."""
    update_available: bool
    current_version: str
    latest_version: str
    release_title: str = ""
    release_notes: str = ""
    published_at: str = ""
    html_url: str = ""
    zipball_url: Optional[str] = None
    tarball_url: Optional[str] = None
    is_git_clone: bool = False
    error: Optional[str] = None


def parse_version_tuple(ver_str: str) -> Tuple[int, ...]:
    """Parse semver string (e.g. 'v1.0.0', '1.2.3', 'v2.1') into comparable integer tuple."""
    clean = ver_str.strip().lstrip("vV")
    parts = []
    for p in clean.split("."):
        digits = "".join(ch for ch in p if ch.isdigit())
        if digits:
            parts.append(int(digits))
        else:
            break
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def resolve_github_repo(config: Optional[AppConfig] = None) -> str:
    """Resolve owner/repo slug from git remote or config fallback."""
    cfg = config or AppConfig.load()

    # Try detecting from local git remote origin first
    try:
        project_dir = Path(__file__).resolve().parents[3]
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        url = result.stdout.strip()
        if url:
            # Parse GitHub URL e.g. https://github.com/owner/repo.git or git@github.com:owner/repo.git
            if "github.com" in url:
                if url.startswith("git@github.com:"):
                    slug = url.split("git@github.com:")[-1]
                else:
                    slug = url.split("github.com/")[-1]
                if slug.endswith(".git"):
                    slug = slug[:-4]
                slug = slug.strip("/")
                if "/" in slug:
                    return slug
    except Exception:
        pass

    return getattr(cfg, "github_repo", "ashugit1234622/wallpaper-selector") or "ashugit1234622/wallpaper-selector"


def check_git_remote_update(project_dir: Path, timeout_sec: float = 6.0) -> Optional[Tuple[bool, str, str]]:
    """Check if remote git origin has newer commits than local HEAD.
    
    Returns (has_update, local_commit_short, remote_commit_short) or None on failure.
    """
    if not (project_dir / ".git").is_dir():
        return None

    try:
        local_res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        if local_res.returncode != 0:
            return None
        local_hash = local_res.stdout.strip()

        # Query remote refs for origin/master, fallback to origin/main
        remote_res = subprocess.run(
            ["git", "ls-remote", "origin", "refs/heads/master"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        if remote_res.returncode != 0 or not remote_res.stdout.strip():
            remote_res = subprocess.run(
                ["git", "ls-remote", "origin", "refs/heads/main"],
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )

        if remote_res.returncode == 0 and remote_res.stdout.strip():
            remote_hash = remote_res.stdout.strip().split()[0]
            if remote_hash:
                has_diff = (remote_hash != local_hash)
                return (has_diff, local_hash[:7], remote_hash[:7])
    except Exception:
        pass
    return None


def check_for_updates(
    config: Optional[AppConfig] = None,
    force: bool = False,
    timeout_sec: float = 5.0,
) -> UpdateCheckResult:
    """Check repository for newer releases, tags, or git commits.
    
    Uses hybrid detection:
    1. GitHub Releases API (latest published release)
    2. GitHub Tags API (latest semver tag if no release drafted)
    3. Git remote commits (if running from a git clone)
    """
    from .. import __version__ as current_ver_str
    cfg = config or AppConfig.load()
    repo_slug = resolve_github_repo(cfg)

    # 1. Throttling check (only check once per update_check_interval_hours on startup)
    if not force and getattr(cfg, "last_update_check_timestamp", None):
        try:
            last_ts = datetime.fromisoformat(cfg.last_update_check_timestamp.replace("Z", "+00:00"))
            now_ts = datetime.now(timezone.utc)
            hours_passed = (now_ts - last_ts).total_seconds() / 3600.0
            interval_hours = getattr(cfg, "update_check_interval_hours", 4)
            if hours_passed < interval_hours:
                return UpdateCheckResult(
                    update_available=False,
                    current_version=current_ver_str,
                    latest_version=current_ver_str,
                    error="Throttled: checked recently.",
                )
        except Exception:
            pass

    project_dir = Path(__file__).resolve().parents[3]
    is_git_clone = (project_dir / ".git").is_dir()
    curr_tuple = parse_version_tuple(current_ver_str)

    # 2. Check GitHub Releases & Tags API
    api_url = f"https://api.github.com/repos/{repo_slug}/releases/latest"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": f"LoginWallpaperSelector/{current_ver_str}",
    }

    try:
        with httpx.Client(timeout=timeout_sec, follow_redirects=True) as client:
            resp = client.get(api_url, headers=headers)

            # Record timestamp of check
            cfg.last_update_check_timestamp = datetime.now(timezone.utc).isoformat()
            try:
                cfg.save()
            except Exception:
                pass

            if resp.status_code == 200:
                data = resp.json()
                tag_name = data.get("tag_name", "").strip()
                title = data.get("name") or tag_name
                notes = data.get("body") or "New update released on GitHub."
                published_at = data.get("published_at", "")
                html_url = data.get("html_url", f"https://github.com/{repo_slug}/releases")
                zipball_url = data.get("zipball_url")
                tarball_url = data.get("tarball_url")

                latest_tuple = parse_version_tuple(tag_name)
                if latest_tuple > curr_tuple:
                    return UpdateCheckResult(
                        update_available=True,
                        current_version=current_ver_str,
                        latest_version=tag_name.lstrip("vV"),
                        release_title=title,
                        release_notes=notes,
                        published_at=published_at,
                        html_url=html_url,
                        zipball_url=zipball_url,
                        tarball_url=tarball_url,
                        is_git_clone=is_git_clone,
                    )

            # Check GitHub Tags API if release wasn't newer
            try:
                tags_resp = client.get(f"https://api.github.com/repos/{repo_slug}/tags", headers=headers)
                if tags_resp.status_code == 200:
                    tags_data = tags_resp.json()
                    if isinstance(tags_data, list) and tags_data:
                        highest_tag = None
                        highest_tuple = curr_tuple
                        for t in tags_data:
                            t_name = t.get("name", "").strip()
                            t_tuple = parse_version_tuple(t_name)
                            if t_tuple > highest_tuple:
                                highest_tuple = t_tuple
                                highest_tag = t_name
                        if highest_tag:
                            return UpdateCheckResult(
                                update_available=True,
                                current_version=current_ver_str,
                                latest_version=highest_tag.lstrip("vV"),
                                release_title=f"Release {highest_tag}",
                                release_notes=f"New version {highest_tag} is available on GitHub.",
                                html_url=f"https://github.com/{repo_slug}/releases/tag/{highest_tag}",
                                zipball_url=f"https://api.github.com/repos/{repo_slug}/zipball/{highest_tag}",
                                tarball_url=f"https://api.github.com/repos/{repo_slug}/tarball/{highest_tag}",
                                is_git_clone=is_git_clone,
                            )
            except Exception:
                pass

    except Exception:
        pass

    # 3. Check Git Remote Commits (if running from git clone)
    if is_git_clone:
        git_check = check_git_remote_update(project_dir, timeout_sec=timeout_sec)
        if git_check and git_check[0]:
            _, local_hash, remote_hash = git_check
            return UpdateCheckResult(
                update_available=True,
                current_version=current_ver_str,
                latest_version=f"{current_ver_str} (rev {remote_hash})",
                release_title=f"New commits on origin/master ({remote_hash})",
                release_notes=(
                    f"New commits are available on remote repository.\n\n"
                    f"• Remote commit: {remote_hash}\n"
                    f"• Local commit:  {local_hash}\n\n"
                    f"Click 'Update Now' to pull the latest changes, update dependencies, and restart."
                ),
                html_url=f"https://github.com/{repo_slug}/commits/master",
                is_git_clone=True,
            )

    return UpdateCheckResult(
        update_available=False,
        current_version=current_ver_str,
        latest_version=current_ver_str,
        is_git_clone=is_git_clone,
    )


def apply_update(
    update_info: UpdateCheckResult,
    progress_callback: Optional[Callable[[str, float], None]] = None,
) -> Tuple[bool, Optional[str]]:
    """Download, update repository, install updated dependencies, and refresh shortcuts.
    
    Args:
        update_info: The UpdateCheckResult from check_for_updates.
        progress_callback: Optional callback receiving (status_message, fractional_progress 0.0-1.0).

    Returns:
        Tuple of (success_bool, optional_error_message).
    """
    def _notify(msg: str, frac: float):
        print(f"[*] [Update] {msg}", flush=True)
        if progress_callback:
            progress_callback(msg, frac)

    project_dir = Path(__file__).resolve().parents[3]
    _notify("Preparing update environment...", 0.1)

    try:
        # Case A: Git Clone Update Workflow
        if (project_dir / ".git").is_dir():
            _notify("Connecting to GitHub remote...", 0.25)
            # Fetch latest
            fetch_res = subprocess.run(
                ["git", "fetch", "--tags", "origin"],
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=30.0,
            )

            _notify("Pulling latest code...", 0.45)
            # Pull active branch or master
            pull_res = subprocess.run(
                ["git", "pull", "origin", "master"],
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=30.0,
            )
            if pull_res.returncode != 0:
                # Try pulling current branch
                subprocess.run(
                    ["git", "pull"],
                    cwd=project_dir,
                    capture_output=True,
                    text=True,
                    timeout=30.0,
                )

            _notify("Installing updated packages and dependencies...", 0.70)
            pip_cmd = [sys.executable, "-m", "pip", "install", "-e", "."]
            pip_res = subprocess.run(
                pip_cmd,
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=90.0,
            )
            if pip_res.returncode != 0:
                # Fallback without build isolation if environment already has setuptools/wheel
                pip_fallback = [sys.executable, "-m", "pip", "install", "-e", ".", "--no-build-isolation"]
                pip_res = subprocess.run(
                    pip_fallback,
                    cwd=project_dir,
                    capture_output=True,
                    text=True,
                    timeout=90.0,
                )

            if pip_res.returncode != 0:
                raw_err = pip_res.stderr or pip_res.stdout or "pip install failed"
                lines = [ln.strip() for ln in raw_err.splitlines() if ln.strip()]
                clean_err = lines[-1] if lines else raw_err
                return False, f"pip install failed: {clean_err}"

            _notify("Refreshing desktop shortcuts...", 0.90)
            shortcut_cmd = [sys.executable, "-m", "login_wallpaper_selector", "--create-shortcut"]
            subprocess.run(shortcut_cmd, cwd=project_dir, capture_output=True, text=True, timeout=10.0)

            _notify(f"✓ Successfully updated to v{update_info.latest_version}!", 1.0)
            return True, None

        # Case B: Standalone / Archive Download Workflow
        elif update_info.zipball_url:
            _notify("Downloading update archive from GitHub...", 0.3)
            temp_zip = project_dir / "update_download.zip"
            with httpx.Client(timeout=60.0, follow_redirects=True) as client:
                with client.stream("GET", update_info.zipball_url) as resp:
                    if resp.status_code != 200:
                        return False, f"Failed to download update archive (HTTP {resp.status_code})"
                    with open(temp_zip, "wb") as f:
                        for chunk in resp.iter_bytes():
                            if chunk:
                                f.write(chunk)

            _notify("Extracting and applying update...", 0.65)
            import zipfile
            extract_dir = project_dir / "update_extract"
            with zipfile.ZipFile(temp_zip, "r") as zf:
                zf.extractall(extract_dir)

            _notify("Installing package...", 0.85)
            subprocess.run([sys.executable, "-m", "pip", "install", "-e", str(project_dir)], capture_output=True, text=True)
            if temp_zip.exists():
                temp_zip.unlink()

            _notify(f"✓ Updated to v{update_info.latest_version}!", 1.0)
            return True, None

        else:
            return False, "Neither a git repository nor a downloadable zipball URL was found."

    except Exception as e:
        return False, str(e)


def restart_application() -> None:
    """Safely restart the application in a clean detached process and exit current process."""
    try:
        project_root = Path(__file__).resolve().parents[3]
        cwd_dir = str(project_root) if project_root.exists() else None

        # Prefer pythonw.exe on Windows to prevent terminal window flash
        python_exe = sys.executable
        if sys.platform == "win32":
            pythonw = Path(python_exe).parent / "pythonw.exe"
            if pythonw.exists():
                python_exe = str(pythonw)

            # Use cmd.exe /c start "" "<python_exe>" -m login_wallpaper_selector
            # completely detaches from console, immune to handle inheritance hangs
            cmd = f'cmd.exe /c start "" "{python_exe}" -m login_wallpaper_selector'
            subprocess.Popen(
                cmd,
                shell=True,
                cwd=cwd_dir,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            cmd = [python_exe, "-m", "login_wallpaper_selector"]
            subprocess.Popen(cmd, cwd=cwd_dir, start_new_session=True)
    except Exception as e:
        try:
            subprocess.Popen([sys.executable, "-m", "login_wallpaper_selector"])
        except Exception:
            pass
    finally:
        # CRITICAL: sys.exit(0) only raises SystemExit in the calling thread if called from
        # a background worker thread, leaving the main Tkinter event loop running!
        # os._exit(0) guarantees immediate, clean termination of the entire old process.
        os._exit(0)
