"""Tests for Download Folder Organizer planner."""

from datetime import datetime
from pathlib import Path
import pytest

from login_wallpaper_selector.tools.download_organizer.models import (
    FileItem,
    OrganizationMode,
    ConflictPolicy,
    FileCategory,
)
from login_wallpaper_selector.tools.download_organizer.planner import create_organization_plan


def make_file_item(path: Path, filename: str, category: str, mtime: float = 0.0) -> FileItem:
    return FileItem(
        path=path,
        filename=filename,
        extension=path.suffix.lstrip("."),
        size_bytes=100,
        category=category,
        created_time=mtime,
        modified_time=mtime,
    )


def test_plan_by_file_type(tmp_path):
    dest = tmp_path / "Organized"
    f1 = tmp_path / "img.png"
    f2 = tmp_path / "doc.pdf"
    f1.write_text("1")
    f2.write_text("2")

    items = [
        make_file_item(f1, "img.png", FileCategory.IMAGES.value),
        make_file_item(f2, "doc.pdf", FileCategory.DOCUMENTS.value),
    ]

    plan = create_organization_plan(items, OrganizationMode.BY_TYPE, dest)
    assert len(plan) == 2
    assert plan[0].resolved_destination == dest / "Images" / "img.png"
    assert plan[1].resolved_destination == dest / "Documents" / "doc.pdf"
    assert all(p.selected for p in plan)
    assert all(p.status == "Ready" for p in plan)
    # Check read-only guarantee: nothing created yet
    assert not dest.exists()


def test_plan_by_date(tmp_path):
    dest = tmp_path / "Organized"
    f = tmp_path / "notes.txt"
    f.write_text("data")
    # Set a fixed timestamp: 2026-05-15
    fixed_ts = datetime(2026, 5, 15, 12, 0, 0).timestamp()

    items = [make_file_item(f, "notes.txt", FileCategory.DOCUMENTS.value, mtime=fixed_ts)]
    plan = create_organization_plan(items, OrganizationMode.BY_DATE, dest)
    assert len(plan) == 1
    assert plan[0].resolved_destination == dest / "2026" / "05" / "notes.txt"


def test_plan_by_type_and_date(tmp_path):
    dest = tmp_path / "Organized"
    f = tmp_path / "clip.mp4"
    f.write_text("video")
    fixed_ts = datetime(2025, 11, 20, 10, 0, 0).timestamp()

    items = [make_file_item(f, "clip.mp4", FileCategory.VIDEOS.value, mtime=fixed_ts)]
    plan = create_organization_plan(items, OrganizationMode.BY_TYPE_AND_DATE, dest)
    assert len(plan) == 1
    assert plan[0].resolved_destination == dest / "Videos" / "2025" / "11" / "clip.mp4"


def test_plan_conflict_keep_both_with_existing_disk_file(tmp_path):
    dest = tmp_path / "Organized"
    target_dir = dest / "Images"
    target_dir.mkdir(parents=True)
    (target_dir / "photo.jpg").write_text("existing")

    source_file = tmp_path / "photo.jpg"
    source_file.write_text("new")

    items = [make_file_item(source_file, "photo.jpg", FileCategory.IMAGES.value)]
    plan = create_organization_plan(
        items,
        OrganizationMode.BY_TYPE,
        dest,
        conflict_policy=ConflictPolicy.KEEP_BOTH,
    )
    assert len(plan) == 1
    assert plan[0].conflict is True
    assert plan[0].resolved_destination == target_dir / "photo (1).jpg"
    assert plan[0].selected is True
    assert "Conflict" in plan[0].status


def test_plan_in_batch_duplicate_collision(tmp_path):
    dest = tmp_path / "Organized"
    sub1 = tmp_path / "folder1"
    sub2 = tmp_path / "folder2"
    sub1.mkdir()
    sub2.mkdir()
    f1 = sub1 / "data.csv"
    f2 = sub2 / "data.csv"
    f1.write_text("one")
    f2.write_text("two")

    items = [
        make_file_item(f1, "data.csv", FileCategory.SPREADSHEETS.value),
        make_file_item(f2, "data.csv", FileCategory.SPREADSHEETS.value),
    ]

    plan = create_organization_plan(
        items,
        OrganizationMode.BY_TYPE,
        dest,
        conflict_policy=ConflictPolicy.KEEP_BOTH,
    )
    assert len(plan) == 2
    dest1 = plan[0].resolved_destination
    dest2 = plan[1].resolved_destination
    # Both destinations must be distinct!
    assert dest1 != dest2
    assert dest1 == dest / "Spreadsheets and Data" / "data.csv"
    assert dest2 == dest / "Spreadsheets and Data" / "data (1).csv"


def test_plan_conflict_skip_policy(tmp_path):
    dest = tmp_path / "Organized"
    target_dir = dest / "Documents"
    target_dir.mkdir(parents=True)
    (target_dir / "doc.pdf").write_text("existing")

    source_file = tmp_path / "doc.pdf"
    source_file.write_text("new")

    items = [make_file_item(source_file, "doc.pdf", FileCategory.DOCUMENTS.value)]
    plan = create_organization_plan(
        items,
        OrganizationMode.BY_TYPE,
        dest,
        conflict_policy=ConflictPolicy.SKIP,
    )
    assert len(plan) == 1
    assert plan[0].conflict is True
    assert plan[0].selected is False
    assert plan[0].status == "Conflict: Skipped"
