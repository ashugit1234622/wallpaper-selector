"""Unit tests for the updater engine, semantic version comparison, and GitHub release checking."""

from unittest.mock import MagicMock, patch
import pytest

from login_wallpaper_selector.core.config import AppConfig
from login_wallpaper_selector.core.updater import (
    parse_version_tuple,
    resolve_github_repo,
    check_for_updates,
    UpdateCheckResult,
)


def test_parse_version_tuple():
    assert parse_version_tuple("v1.0.0") == (1, 0, 0)
    assert parse_version_tuple("1.2.3") == (1, 2, 3)
    assert parse_version_tuple("v2.1") == (2, 1, 0)
    assert parse_version_tuple("v0.10.2") == (0, 10, 2)
    assert parse_version_tuple("1") == (1, 0, 0)

    # Comparisons
    assert parse_version_tuple("1.0.0") > parse_version_tuple("0.1.0")
    assert parse_version_tuple("v2.0.0") > parse_version_tuple("v1.9.9")
    assert parse_version_tuple("v1.0.1") > parse_version_tuple("1.0.0")
    assert parse_version_tuple("1.0.0") == parse_version_tuple("v1.0.0")


def test_resolve_github_repo():
    cfg = AppConfig.load()
    cfg.github_repo = "ashugit1234622/wallpaper-selector"
    slug = resolve_github_repo(cfg)
    assert slug == "ashugit1234622/wallpaper-selector"


def test_check_for_updates_detects_newer_release():
    cfg = AppConfig.load()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "tag_name": "v2.0.0",
        "name": "Version 2.0.0 - Major Features",
        "body": "Added advanced multi-monitor support and live previews.",
        "published_at": "2026-10-23T12:00:00Z",
        "html_url": "https://github.com/ashugit1234622/wallpaper-selector/releases/tag/v2.0.0",
        "zipball_url": "https://api.github.com/repos/ashugit1234622/wallpaper-selector/zipball/v2.0.0",
    }

    with patch("httpx.Client.get", return_value=mock_resp):
        res = check_for_updates(cfg, force=True)
        assert res.update_available is True
        assert res.latest_version == "2.0.0"
        assert "multi-monitor" in res.release_notes
        assert res.html_url.endswith("/v2.0.0")


def test_check_for_updates_ignores_current_or_older_release():
    cfg = AppConfig.load()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "tag_name": "v1.0.0",
        "name": "v1.0.0",
        "body": "Initial release",
        "published_at": "2026-10-23T10:00:00Z",
        "html_url": "https://github.com/ashugit1234622/wallpaper-selector/releases/tag/v1.0.0",
    }

    with patch("httpx.Client.get", return_value=mock_resp):
        res = check_for_updates(cfg, force=True)
        # v1.0.0 is equal to current version, so no update available
        assert res.update_available is False


def test_check_for_updates_handles_404_gracefully():
    cfg = AppConfig.load()
    mock_resp = MagicMock()
    mock_resp.status_code = 404

    with patch("httpx.Client.get", return_value=mock_resp):
        res = check_for_updates(cfg, force=True)
        assert res.update_available is False
        assert "No releases found" in (res.error or "")


def test_check_for_updates_throttles_automated_checks():
    cfg = AppConfig.load()
    cfg.last_update_check_timestamp = "2026-10-23T15:00:00Z"
    cfg.update_check_interval_hours = 4

    # Non-forced check should be throttled
    res = check_for_updates(cfg, force=False)
    assert res.update_available is False
    assert "Throttled" in (res.error or "")


def test_restart_application_spawns_process_and_exits(monkeypatch):
    from login_wallpaper_selector.core.updater import restart_application

    mock_popen = MagicMock()
    mock_exit = MagicMock()
    monkeypatch.setattr("subprocess.Popen", mock_popen)
    monkeypatch.setattr("os._exit", mock_exit)

    restart_application()
    assert mock_popen.called
    assert mock_exit.called
    mock_exit.assert_called_with(0)

