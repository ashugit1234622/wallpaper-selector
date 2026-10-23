"""Tests for Download Folder Organizer classifier."""

import pytest
from login_wallpaper_selector.tools.download_organizer.classifier import (
    classify_file,
    extract_extension,
    STANDARD_EXTENSION_MAP,
)
from login_wallpaper_selector.tools.download_organizer.models import FileCategory


def test_extract_extension():
    assert extract_extension("photo.jpg") == "jpg"
    assert extract_extension("DOCUMENT.PDF") == "pdf"
    assert extract_extension("archive.tar.gz") == "tar.gz"
    assert extract_extension("backup.tar.bz2") == "tar.bz2"
    assert extract_extension("no_extension") == ""
    assert extract_extension(".gitignore") == ""


def test_classify_standard_categories():
    assert classify_file("wallpaper.png") == FileCategory.IMAGES.value
    assert classify_file("REPORT.DOCX") == FileCategory.DOCUMENTS.value
    assert classify_file("movie.mkv") == FileCategory.VIDEOS.value
    assert classify_file("song.flac") == FileCategory.AUDIO.value
    assert classify_file("bundle.zip") == FileCategory.ARCHIVES.value
    assert classify_file("setup.exe") == FileCategory.INSTALLERS.value
    assert classify_file("app.py") == FileCategory.CODE.value
    assert classify_file("data.xlsx") == FileCategory.SPREADSHEETS.value
    assert classify_file("slides.pptx") == FileCategory.PRESENTATIONS.value


def test_classify_compound_archive():
    assert classify_file("source.tar.gz") == FileCategory.ARCHIVES.value
    assert classify_file("package.tar.xz") == FileCategory.ARCHIVES.value


def test_classify_unknown_and_extensionless():
    assert classify_file("random_blob.xyz123") == FileCategory.OTHER.value
    assert classify_file("LICENSE") == FileCategory.OTHER.value
    assert classify_file("notes.") == FileCategory.OTHER.value


def test_classify_custom_rules():
    custom = {"xyz": "Custom Group", "log": "Logs"}
    assert classify_file("server.log", custom_rules=custom) == "Logs"
    assert classify_file("model.xyz", custom_rules=custom) == "Custom Group"
    # Fallback to standard for non-custom
    assert classify_file("doc.pdf", custom_rules=custom) == FileCategory.DOCUMENTS.value
