"""Download Folder Organizer package."""

from .models import (
    OrganizationMode,
    ConflictPolicy,
    FileCategory,
    FileItem,
    ScanSummary,
    PlanItem,
    ExecutionResult,
    UndoResult,
    OperationRecord,
    BatchRecord,
)
from .classifier import classify_file, extract_extension
from .scanner import get_default_downloads_folder, scan_folder
from .planner import create_organization_plan
from .executor import safe_move_file, execute_plan
from .journal import TransactionJournal

__all__ = [
    "OrganizationMode",
    "ConflictPolicy",
    "FileCategory",
    "FileItem",
    "ScanSummary",
    "PlanItem",
    "ExecutionResult",
    "UndoResult",
    "OperationRecord",
    "BatchRecord",
    "classify_file",
    "extract_extension",
    "get_default_downloads_folder",
    "scan_folder",
    "create_organization_plan",
    "safe_move_file",
    "execute_plan",
    "TransactionJournal",
]
