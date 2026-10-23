"""Plan generator and conflict resolver for Download Folder Organizer."""

from __future__ import annotations
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Set, Optional, Dict, Tuple

from .models import (
    FileItem,
    PlanItem,
    OrganizationMode,
    ConflictPolicy,
    FileCategory,
)
from .classifier import classify_file


def get_date_subfolder(timestamp: float) -> Tuple[str, str]:
    """Return (YYYY, MM) folder names for a given timestamp."""
    try:
        dt = datetime.fromtimestamp(timestamp)
        return f"{dt.year:04d}", f"{dt.month:02d}"
    except Exception:
        now = datetime.now()
        return f"{now.year:04d}", f"{now.month:02d}"


def generate_unique_path(target_path: Path, claimed_paths: Set[Path]) -> Path:
    """Generate a unique path with a (1), (2) suffix that does not collide with disk or batch."""
    stem = target_path.stem
    suffix = target_path.suffix
    parent = target_path.parent

    counter = 1
    while True:
        candidate = parent / f"{stem} ({counter}){suffix}"
        if not candidate.exists() and candidate not in claimed_paths:
            return candidate
        counter += 1


def create_organization_plan(
    files: List[FileItem],
    mode: OrganizationMode,
    destination_folder: Path,
    conflict_policy: ConflictPolicy = ConflictPolicy.KEEP_BOTH,
    custom_rules: Optional[Dict[str, str]] = None,
) -> List[PlanItem]:
    """Generate a pre-execution plan mapping discovered files to validated destinations.
    
    This function is strictly read-only and will never create, modify, or move files.
    """
    dest_dir = destination_folder.resolve()
    plan_items: List[PlanItem] = []
    claimed_paths: Set[Path] = set()

    for item in files:
        source_p = item.path.resolve()

        # 1. Determine destination subfolder based on organization mode
        if mode == OrganizationMode.BY_TYPE:
            category = classify_file(item.filename, custom_rules)
            target_subfolder = dest_dir / category
        elif mode == OrganizationMode.BY_DATE:
            category = classify_file(item.filename, custom_rules)
            year_str, month_str = get_date_subfolder(item.modified_time)
            target_subfolder = dest_dir / year_str / month_str
        elif mode == OrganizationMode.BY_TYPE_AND_DATE:
            category = classify_file(item.filename, custom_rules)
            year_str, month_str = get_date_subfolder(item.modified_time)
            target_subfolder = dest_dir / category / year_str / month_str
        elif mode == OrganizationMode.CUSTOM_RULES:
            category = classify_file(item.filename, custom_rules)
            target_subfolder = dest_dir / category
        else:
            category = classify_file(item.filename, custom_rules)
            target_subfolder = dest_dir / category

        initial_target = target_subfolder / item.filename

        # 2. Check if file is already organized at this location
        if source_p == initial_target:
            plan_items.append(
                PlanItem(
                    id=str(uuid.uuid4())[:8],
                    file_item=item,
                    source_path=source_p,
                    proposed_destination=initial_target,
                    resolved_destination=initial_target,
                    category=category,
                    selected=False,
                    status="Already Organized",
                    conflict=False,
                    warning_message="File is already in its suitable organized location.",
                )
            )
            continue

        # 3. Conflict detection (disk existence or already claimed in this batch)
        is_conflict = initial_target.exists() or (initial_target in claimed_paths)

        if not is_conflict:
            claimed_paths.add(initial_target)
            plan_items.append(
                PlanItem(
                    id=str(uuid.uuid4())[:8],
                    file_item=item,
                    source_path=source_p,
                    proposed_destination=initial_target,
                    resolved_destination=initial_target,
                    category=category,
                    selected=True,
                    status="Ready",
                    conflict=False,
                    warning_message=None,
                )
            )
        else:
            # Conflict handling
            if conflict_policy == ConflictPolicy.KEEP_BOTH:
                unique_dest = generate_unique_path(initial_target, claimed_paths)
                claimed_paths.add(unique_dest)
                plan_items.append(
                    PlanItem(
                        id=str(uuid.uuid4())[:8],
                        file_item=item,
                        source_path=source_p,
                        proposed_destination=initial_target,
                        resolved_destination=unique_dest,
                        category=category,
                        selected=True,
                        status="Conflict: Auto-Renamed",
                        conflict=True,
                        warning_message=f"Conflict detected. Will rename to '{unique_dest.name}'",
                    )
                )
            elif conflict_policy == ConflictPolicy.SKIP:
                plan_items.append(
                    PlanItem(
                        id=str(uuid.uuid4())[:8],
                        file_item=item,
                        source_path=source_p,
                        proposed_destination=initial_target,
                        resolved_destination=None,
                        category=category,
                        selected=False,
                        status="Conflict: Skipped",
                        conflict=True,
                        warning_message="Destination already exists; skipped per policy.",
                    )
                )
            else:  # REVIEW
                plan_items.append(
                    PlanItem(
                        id=str(uuid.uuid4())[:8],
                        file_item=item,
                        source_path=source_p,
                        proposed_destination=initial_target,
                        resolved_destination=None,
                        category=category,
                        selected=False,
                        status="Conflict: Needs Review",
                        conflict=True,
                        warning_message="Destination filename already exists.",
                    )
                )

    return plan_items
