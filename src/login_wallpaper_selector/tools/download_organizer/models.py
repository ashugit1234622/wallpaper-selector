"""Data models and enums for Download Folder Organizer."""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, List


class OrganizationMode(str, Enum):
    """File organization modes."""
    BY_TYPE = "by_type"
    BY_DATE = "by_date"
    BY_TYPE_AND_DATE = "by_type_and_date"
    CUSTOM_RULES = "custom_rules"

    @classmethod
    def display_names(cls) -> list[str]:
        return [
            "By File Type",
            "By Date (Year/Month)",
            "By File Type and Date",
        ]

    @classmethod
    def from_display(cls, display_name: str) -> "OrganizationMode":
        mapping = {
            "By File Type": cls.BY_TYPE,
            "By Date (Year/Month)": cls.BY_DATE,
            "By File Type and Date": cls.BY_TYPE_AND_DATE,
            "Custom Rules": cls.CUSTOM_RULES,
        }
        return mapping.get(display_name, cls.BY_TYPE)

    def to_display(self) -> str:
        mapping = {
            OrganizationMode.BY_TYPE: "By File Type",
            OrganizationMode.BY_DATE: "By Date (Year/Month)",
            OrganizationMode.BY_TYPE_AND_DATE: "By File Type and Date",
            OrganizationMode.CUSTOM_RULES: "Custom Rules",
        }
        return mapping.get(self, "By File Type")


class ConflictPolicy(str, Enum):
    """Strategy when proposed destination file already exists."""
    KEEP_BOTH = "keep_both"
    SKIP = "skip"
    REVIEW = "review"

    @classmethod
    def display_names(cls) -> list[str]:
        return [
            "Keep Both (Auto-Rename)",
            "Skip Conflicting",
        ]

    @classmethod
    def from_display(cls, display_name: str) -> "ConflictPolicy":
        if "Skip" in display_name:
            return cls.SKIP
        return cls.KEEP_BOTH

    def to_display(self) -> str:
        if self == ConflictPolicy.SKIP:
            return "Skip Conflicting"
        return "Keep Both (Auto-Rename)"


class FileCategory(str, Enum):
    """Deterministic high-level file categories."""
    DOCUMENTS = "Documents"
    IMAGES = "Images"
    VIDEOS = "Videos"
    AUDIO = "Audio"
    ARCHIVES = "Archives"
    INSTALLERS = "Installers"
    CODE = "Code and Development"
    SPREADSHEETS = "Spreadsheets and Data"
    PRESENTATIONS = "Presentations"
    OTHER = "Other"


def format_bytes(size_bytes: int) -> str:
    """Format bytes into a human-readable string."""
    if size_bytes < 0:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0 or unit == "TB":
            if unit in ["B"]:
                return f"{int(size_bytes)} {unit}"
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


@dataclass
class FileItem:
    """Represents a discovered file."""
    path: Path
    filename: str
    extension: str
    size_bytes: int
    category: str
    created_time: float
    modified_time: float
    is_already_organized: bool = False

    @property
    def size_formatted(self) -> str:
        return format_bytes(self.size_bytes)


@dataclass
class ScanSummary:
    """Aggregated statistics after scanning a directory."""
    scanned_path: Path
    total_files: int = 0
    total_folders: int = 0
    total_supported_files: int = 0
    organizable_files: int = 0
    already_suitable: int = 0
    needs_review: int = 0
    total_size_bytes: int = 0

    @property
    def total_size_formatted(self) -> str:
        return format_bytes(self.total_size_bytes)


@dataclass
class PlanItem:
    """A single proposed organization move in the plan."""
    id: str
    file_item: FileItem
    source_path: Path
    proposed_destination: Path
    resolved_destination: Optional[Path] = None
    category: str = "Other"
    selected: bool = True
    status: str = "Ready"  # "Ready", "Conflict", "Already Organized", "Excluded", "Needs Review"
    conflict: bool = False
    warning_message: Optional[str] = None


@dataclass
class OperationRecord:
    """Persistent journal entry for a single file operation."""
    transaction_id: str
    batch_id: str
    timestamp: str
    source_path: str
    destination_path: str
    original_size: int
    original_mtime: float
    status: str  # "success", "skipped", "failed", "undone"
    conflict_policy_used: str
    error_message: Optional[str] = None


@dataclass
class BatchRecord:
    """Persistent journal entry for a batch of operations."""
    batch_id: str
    timestamp: str
    source_folder: str
    destination_folder: str
    mode: str
    total_items: int
    successful_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    status: str = "completed"  # "in_progress", "completed", "partial", "interrupted", "undone"
    operations: List[OperationRecord] = field(default_factory=list)


@dataclass
class ExecutionResult:
    """Summary of a completed or cancelled execution run."""
    batch_id: str
    timestamp: str
    total_operations: int
    successful: int
    skipped: int
    failed: int
    cancelled: bool
    details: List[OperationRecord] = field(default_factory=list)


@dataclass
class UndoResult:
    """Summary of an undo operation."""
    batch_id: str
    total: int
    undone: int
    skipped: int
    failed: int
    messages: List[str] = field(default_factory=list)
