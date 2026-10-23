"""Tests for Download Folder Organizer executor."""

import threading
from pathlib import Path
import pytest

from login_wallpaper_selector.tools.download_organizer.models import (
    FileItem,
    PlanItem,
    FileCategory,
    OrganizationMode,
)
from login_wallpaper_selector.tools.download_organizer.journal import TransactionJournal
from login_wallpaper_selector.tools.download_organizer.planner import create_organization_plan
from login_wallpaper_selector.tools.download_organizer.executor import execute_plan


def test_execute_plan_success(tmp_path):
    journal_path = tmp_path / "journal.json"
    journal = TransactionJournal(journal_path)

    src_dir = tmp_path / "Downloads"
    src_dir.mkdir()
    dest_dir = tmp_path / "Organized"

    f1 = src_dir / "pic.png"
    f2 = src_dir / "paper.pdf"
    f1.write_text("image content")
    f2.write_text("pdf content")

    item1 = FileItem(f1, "pic.png", "png", len("image content"), FileCategory.IMAGES.value, 0, 0)
    item2 = FileItem(f2, "paper.pdf", "pdf", len("pdf content"), FileCategory.DOCUMENTS.value, 0, 0)

    plan = create_organization_plan([item1, item2], OrganizationMode.BY_TYPE, dest_dir)
    res = execute_plan(plan, journal, src_dir, dest_dir, mode="by_type")

    assert res.total_operations == 2
    assert res.successful == 2
    assert res.failed == 0
    assert not res.cancelled

    # Files must now be in destination and removed from source
    assert not f1.exists()
    assert not f2.exists()
    assert (dest_dir / "Images" / "pic.png").read_text() == "image content"
    assert (dest_dir / "Documents" / "paper.pdf").read_text() == "pdf content"


def test_execute_missing_source_fails_gracefully(tmp_path):
    journal_path = tmp_path / "journal.json"
    journal = TransactionJournal(journal_path)

    src_dir = tmp_path / "Downloads"
    src_dir.mkdir()
    dest_dir = tmp_path / "Organized"

    f_existing = src_dir / "present.txt"
    f_existing.write_text("here")
    f_ghost = src_dir / "ghost.txt"  # Doesn't exist on disk

    item1 = FileItem(f_existing, "present.txt", "txt", 4, FileCategory.DOCUMENTS.value, 0, 0)
    item2 = FileItem(f_ghost, "ghost.txt", "txt", 0, FileCategory.DOCUMENTS.value, 0, 0)

    plan = create_organization_plan([item1, item2], OrganizationMode.BY_TYPE, dest_dir)
    res = execute_plan(plan, journal, src_dir, dest_dir, mode="by_type")

    assert res.successful == 1
    assert res.failed == 1
    assert (dest_dir / "Documents" / "present.txt").exists()


def test_execute_cancellation(tmp_path):
    journal_path = tmp_path / "journal.json"
    journal = TransactionJournal(journal_path)

    src_dir = tmp_path / "Downloads"
    src_dir.mkdir()
    dest_dir = tmp_path / "Organized"

    for i in range(5):
        (src_dir / f"file_{i}.txt").write_text(f"text {i}")

    items = [
        FileItem(src_dir / f"file_{i}.txt", f"file_{i}.txt", "txt", 6, FileCategory.DOCUMENTS.value, 0, 0)
        for i in range(5)
    ]
    plan = create_organization_plan(items, OrganizationMode.BY_TYPE, dest_dir)

    cancel_evt = threading.Event()
    cancel_evt.set()  # Cancel immediately

    res = execute_plan(plan, journal, src_dir, dest_dir, mode="by_type", cancel_event=cancel_evt)
    assert res.cancelled is True
    assert res.successful == 0
