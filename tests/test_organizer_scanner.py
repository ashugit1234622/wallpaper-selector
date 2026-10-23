"""Tests for Download Folder Organizer scanner."""

from pathlib import Path
import pytest
from login_wallpaper_selector.tools.download_organizer.scanner import (
    scan_folder,
    get_default_downloads_folder,
)
from login_wallpaper_selector.tools.download_organizer.models import FileCategory


def test_scan_nonexistent_folder(tmp_path):
    missing = tmp_path / "does_not_exist"
    items, summary = scan_folder(missing)
    assert len(items) == 0
    assert summary.total_files == 0


def test_scan_empty_folder(tmp_path):
    empty = tmp_path / "empty_dir"
    empty.mkdir()
    items, summary = scan_folder(empty)
    assert len(items) == 0
    assert summary.total_files == 0
    assert summary.total_folders == 0


def test_scan_top_level_only_by_default(tmp_path):
    # Root files
    (tmp_path / "photo.jpg").write_text("image-data")
    (tmp_path / "notes.txt").write_text("text-data")
    
    # Subdirectory with files
    sub = tmp_path / "nested"
    sub.mkdir()
    (sub / "nested_file.zip").write_text("zip-data")

    items, summary = scan_folder(tmp_path, recursive=False)
    assert len(items) == 2
    assert summary.total_files == 2
    assert summary.total_folders == 1
    filenames = {i.filename for i in items}
    assert filenames == {"photo.jpg", "notes.txt"}


def test_scan_recursive_mode(tmp_path):
    (tmp_path / "root.png").write_text("png")
    sub = tmp_path / "folder_a"
    sub.mkdir()
    (sub / "child.pdf").write_text("pdf")

    items, summary = scan_folder(tmp_path, recursive=True)
    assert len(items) == 2
    filenames = {i.filename for i in items}
    assert filenames == {"root.png", "child.pdf"}


def test_scan_excludes_destination_folder(tmp_path):
    (tmp_path / "file1.mp3").write_text("audio")
    
    # Destination folder inside source
    dest = tmp_path / "Organized"
    dest.mkdir()
    sub_dest = dest / "Audio"
    sub_dest.mkdir()
    (sub_dest / "already_moved.mp3").write_text("already")

    items, summary = scan_folder(tmp_path, destination_folder=dest, recursive=True)
    # Only file1.mp3 should be found, anything inside Organized/ is excluded
    assert len(items) == 1
    assert items[0].filename == "file1.mp3"


def test_scan_ignores_hidden_files(tmp_path):
    (tmp_path / ".hidden_file").write_text("secret")
    (tmp_path / "desktop.ini").write_text("ini")
    (tmp_path / "regular.docx").write_text("docx")

    items, summary = scan_folder(tmp_path)
    assert len(items) == 1
    assert items[0].filename == "regular.docx"


def test_scan_handles_unicode_and_spaces(tmp_path):
    unicode_file = tmp_path / "résumé 2026 日本語.pdf"
    unicode_file.write_text("unicode content")

    items, summary = scan_folder(tmp_path)
    assert len(items) == 1
    assert items[0].filename == "résumé 2026 日本語.pdf"
    assert items[0].category == FileCategory.DOCUMENTS.value


def test_default_downloads_folder():
    dl = get_default_downloads_folder()
    assert dl is not None
    assert isinstance(dl, Path)
