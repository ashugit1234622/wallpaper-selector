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

    with patch("httpx.Client.get", return_value=mock_resp), \
         patch("login_wallpaper_selector.core.updater.check_git_remote_update", return_value=None):
        res = check_for_updates(cfg, force=True)
        # v1.0.0 is older than current version, so no update available
        assert res.update_available is False


def test_check_for_updates_handles_404_gracefully():
    cfg = AppConfig.load()
    mock_resp = MagicMock()
    mock_resp.status_code = 404

    with patch("httpx.Client.get", return_value=mock_resp), \
         patch("login_wallpaper_selector.core.updater.check_git_remote_update", return_value=None):
        res = check_for_updates(cfg, force=True)
        assert res.update_available is False


def test_check_for_updates_hybrid_git_commits():
    cfg = AppConfig.load()
    mock_resp = MagicMock()
    mock_resp.status_code = 404

    with patch("httpx.Client.get", return_value=mock_resp), \
         patch("login_wallpaper_selector.core.updater.check_git_remote_update", return_value=(True, "1111111", "2222222")):
        res = check_for_updates(cfg, force=True)
        assert res.update_available is True
        assert "2222222" in res.latest_version
        assert "2222222" in res.release_notes
        assert res.is_git_clone is True


def test_check_git_remote_update_detection(tmp_path):
    from login_wallpaper_selector.core.updater import check_git_remote_update

    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    def _mock_run(cmd, **kwargs):
        mock = MagicMock()
        mock.returncode = 0
        if "rev-parse" in cmd:
            mock.stdout = "aaa111122223333444455556666777788889999\n"
        elif "ls-remote" in cmd:
            mock.stdout = "bbb111122223333444455556666777788889999\trefs/heads/master\n"
        return mock

    with patch("subprocess.run", side_effect=_mock_run):
        res = check_git_remote_update(tmp_path)
        assert res is not None
        has_diff, local_h, remote_h = res
        assert has_diff is True
        assert local_h == "aaa1111"
        assert remote_h == "bbb1111"


def test_check_for_updates_throttles_automated_checks():
    from datetime import datetime, timezone
    cfg = AppConfig.load()
    cfg.last_update_check_timestamp = datetime.now(timezone.utc).isoformat()
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

