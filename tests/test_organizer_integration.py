"""End-to-end integration tests for Download Folder Organizer."""

from pathlib import Path
from datetime import datetime
import pytest

from login_wallpaper_selector.tools.download_organizer.scanner import scan_folder
from login_wallpaper_selector.tools.download_organizer.planner import create_organization_plan
from login_wallpaper_selector.tools.download_organizer.executor import execute_plan
from login_wallpaper_selector.tools.download_organizer.journal import TransactionJournal
from login_wallpaper_selector.tools.download_organizer.models import (
    OrganizationMode,
    ConflictPolicy,
)


def test_full_organizer_workflow_with_undo(tmp_path):
    downloads_dir = tmp_path / "Downloads"
    downloads_dir.mkdir()
    dest_dir = downloads_dir / "Organized"
    journal_path = tmp_path / "journal.json"
    journal = TransactionJournal(journal_path)

    # 1. Create a messy collection of sample download files
    sample_files = {
        "landscape.jpg": "image content",
        "financial_report.pdf": "pdf content",
        "archive.zip": "zip content",
        "video.mp4": "video content",
        "installer.exe": "exe content",
        "script.py": "python code",
        "sheet.csv": "csv data",
        "unsupported.bin": "binary blob",
    }
    for name, content in sample_files.items():
        (downloads_dir / name).write_text(content)

    # 2. Scan directory
    files, summary = scan_folder(downloads_dir, destination_folder=dest_dir)
    assert len(files) == len(sample_files)
    assert summary.total_files == len(sample_files)
    assert summary.total_supported_files == 7  # 7 supported categories, 1 Other
    assert summary.needs_review == 1

    # 3. Plan organization: By File Type
    plan = create_organization_plan(
        files,
        mode=OrganizationMode.BY_TYPE,
        destination_folder=dest_dir,
        conflict_policy=ConflictPolicy.KEEP_BOTH,
    )
    assert len(plan) == len(sample_files)
    assert all(p.selected for p in plan)

    # 4. Execute organization
    exec_res = execute_plan(
        plan=plan,
        journal=journal,
        source_folder=downloads_dir,
        destination_folder=dest_dir,
        mode=OrganizationMode.BY_TYPE.value,
    )
    assert exec_res.successful == len(sample_files)
    assert exec_res.failed == 0
    assert not exec_res.cancelled

    # 5. Verify organized directory structure
    assert (dest_dir / "Images" / "landscape.jpg").exists()
    assert (dest_dir / "Documents" / "financial_report.pdf").exists()
    assert (dest_dir / "Archives" / "archive.zip").exists()
    assert (dest_dir / "Videos" / "video.mp4").exists()
    assert (dest_dir / "Installers" / "installer.exe").exists()
    assert (dest_dir / "Code and Development" / "script.py").exists()
    assert (dest_dir / "Spreadsheets and Data" / "sheet.csv").exists()
    assert (dest_dir / "Other" / "unsupported.bin").exists()

    # Original files should no longer be in root
    for name in sample_files:
        assert not (downloads_dir / name).exists()

    # 6. Verify and Execute Undo
    undoable = journal.get_last_undoable_batch()
    assert undoable is not None
    assert undoable.batch_id == exec_res.batch_id

    undo_res = journal.undo_batch(undoable.batch_id)
    assert undo_res.total == len(sample_files)
    assert undo_res.undone == len(sample_files)
    assert undo_res.failed == 0
    assert undo_res.skipped == 0

    # 7. Verify all files restored to original locations with matching content
    for name, content in sample_files.items():
        orig_file = downloads_dir / name
        assert orig_file.exists()
        assert orig_file.read_text() == content
