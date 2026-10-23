"""Tests for Download Folder Organizer transaction journal and undo engine."""

from pathlib import Path
import pytest

from login_wallpaper_selector.tools.download_organizer.models import (
    FileItem,
    FileCategory,
    OrganizationMode,
)
from login_wallpaper_selector.tools.download_organizer.journal import TransactionJournal
from login_wallpaper_selector.tools.download_organizer.planner import create_organization_plan
from login_wallpaper_selector.tools.download_organizer.executor import execute_plan


def test_journal_persists_across_instances(tmp_path):
    journal_path = tmp_path / "journal.json"
    j1 = TransactionJournal(journal_path)
    b = j1.start_batch(tmp_path / "src", tmp_path / "dest", "by_type", 1)
    j1.finish_batch(b.batch_id, "completed")

    # Open with a fresh instance
    j2 = TransactionJournal(journal_path)
    raw = j2._read_raw()
    assert len(raw["batches"]) == 1
    assert raw["batches"][0]["batch_id"] == b.batch_id


def test_undo_successful_batch(tmp_path):
    journal_path = tmp_path / "journal.json"
    journal = TransactionJournal(journal_path)

    src_dir = tmp_path / "Downloads"
    dest_dir = tmp_path / "Organized"
    src_dir.mkdir()

    f1 = src_dir / "invoice.pdf"
    f2 = src_dir / "logo.png"
    f1.write_text("invoice data")
    f2.write_text("logo data")

    item1 = FileItem(f1, "invoice.pdf", "pdf", len("invoice data"), FileCategory.DOCUMENTS.value, 0, 0)
    item2 = FileItem(f2, "logo.png", "png", len("logo data"), FileCategory.IMAGES.value, 0, 0)

    plan = create_organization_plan([item1, item2], OrganizationMode.BY_TYPE, dest_dir)
    res = execute_plan(plan, journal, src_dir, dest_dir, mode="by_type")
    assert res.successful == 2

    # Verify moved to Organized
    moved_f1 = dest_dir / "Documents" / "invoice.pdf"
    moved_f2 = dest_dir / "Images" / "logo.png"
    assert moved_f1.exists()
    assert moved_f2.exists()
    assert not f1.exists()
    assert not f2.exists()

    # Retrieve undoable batch
    last_batch = journal.get_last_undoable_batch()
    assert last_batch is not None
    assert last_batch.batch_id == res.batch_id

    # Execute undo
    undo_res = journal.undo_batch(last_batch.batch_id)
    assert undo_res.total == 2
    assert undo_res.undone == 2
    assert undo_res.skipped == 0
    assert undo_res.failed == 0

    # Files must be restored to original locations
    assert f1.exists()
    assert f2.exists()
    assert f1.read_text() == "invoice data"
    assert f2.read_text() == "logo data"
    assert not moved_f1.exists()
    assert not moved_f2.exists()


def test_undo_skips_modified_or_missing_dest_file(tmp_path):
    journal_path = tmp_path / "journal.json"
    journal = TransactionJournal(journal_path)

    src_dir = tmp_path / "Downloads"
    dest_dir = tmp_path / "Organized"
    src_dir.mkdir()

    f1 = src_dir / "file1.txt"
    f1.write_text("hello")
    item1 = FileItem(f1, "file1.txt", "txt", 5, FileCategory.DOCUMENTS.value, 0, 0)

    plan = create_organization_plan([item1], OrganizationMode.BY_TYPE, dest_dir)
    res = execute_plan(plan, journal, src_dir, dest_dir, mode="by_type")
    assert res.successful == 1

    moved_file = dest_dir / "Documents" / "file1.txt"
    assert moved_file.exists()

    # Modify the file size in destination
    moved_file.write_text("hello modified with much longer content")

    undo_res = journal.undo_batch(res.batch_id)
    assert undo_res.undone == 0
    assert undo_res.skipped == 1
    # Original file is not touched
    assert not f1.exists()


def test_journal_recovers_from_corrupted_file(tmp_path):
    journal_path = tmp_path / "journal.json"
    journal_path.write_text("NOT VALID JSON {{{", encoding="utf-8")

    # Should not throw exception
    journal = TransactionJournal(journal_path)
    b = journal.start_batch(tmp_path / "src", tmp_path / "dest", "by_type", 1)
    assert b.batch_id is not None
