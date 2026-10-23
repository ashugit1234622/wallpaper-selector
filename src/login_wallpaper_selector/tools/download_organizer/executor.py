"""Safe execution engine for Download Folder Organizer."""

from __future__ import annotations
import os
import shutil
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Callable

from .models import (
    PlanItem,
    ExecutionResult,
    OperationRecord,
    ConflictPolicy,
)
from .journal import TransactionJournal


def safe_move_file(source: Path, destination: Path) -> None:
    """Move a file safely, with copy-verify-delete fallback for cross-device filesystems."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    
    # Try atomic/direct move first
    try:
        shutil.move(str(source), str(destination))
        return
    except (OSError, shutil.Error) as err:
        # Cross-device link or filesystem error: attempt safe copy, verify, then remove original
        if not source.exists():
            raise err

        src_size = source.stat().st_size
        shutil.copy2(str(source), str(destination))

        # Verify copied file integrity
        if not destination.exists():
            raise RuntimeError(f"Copy verification failed: destination '{destination}' does not exist.")

        dest_size = destination.stat().st_size
        if dest_size != src_size:
            # Clean up corrupted target and preserve original
            try:
                destination.unlink()
            except Exception:
                pass
            raise RuntimeError(
                f"Copy verification failed: size mismatch (src: {src_size} B, dest: {dest_size} B)."
            )

        # Verified safe: remove original source
        source.unlink()


def execute_plan(
    plan: List[PlanItem],
    journal: TransactionJournal,
    source_folder: Path,
    destination_folder: Path,
    mode: str,
    cancel_event: Optional[threading.Event] = None,
    on_progress: Optional[Callable[[int, int, str, int, int, int], None]] = None,
) -> ExecutionResult:
    """Execute approved plan items safely with progress reporting and cancellation support."""
    selected_items = [p for p in plan if p.selected and p.resolved_destination is not None]
    total_ops = len(selected_items)
    now_str = datetime.now().isoformat()

    if total_ops == 0:
        return ExecutionResult(
            batch_id="none",
            timestamp=now_str,
            total_operations=0,
            successful=0,
            skipped=0,
            failed=0,
            cancelled=False,
            details=[],
        )

    batch = journal.start_batch(
        source_folder=source_folder,
        destination_folder=destination_folder,
        mode=mode,
        total_items=total_ops,
    )

    successful = 0
    skipped = 0
    failed = 0
    cancelled = False
    details: List[OperationRecord] = []

    for idx, item in enumerate(selected_items):
        if cancel_event and cancel_event.is_set():
            cancelled = True
            break

        src = item.source_path
        dest = item.resolved_destination
        filename = src.name

        if on_progress:
            on_progress(idx + 1, total_ops, filename, successful, skipped, failed)

        # 1. Validation: source must still exist
        if not src.exists() or not src.is_file():
            op = OperationRecord(
                transaction_id=str(uuid.uuid4()),
                batch_id=batch.batch_id,
                timestamp=datetime.now().isoformat(),
                source_path=str(src),
                destination_path=str(dest) if dest else "",
                original_size=0,
                original_mtime=0.0,
                status="failed",
                conflict_policy_used="none",
                error_message=f"Source file '{src}' was deleted or missing before move.",
            )
            journal.record_operation(op)
            details.append(op)
            failed += 1
            continue

        # 2. Validation: source != destination
        if dest is None or src.resolve() == dest.resolve():
            op = OperationRecord(
                transaction_id=str(uuid.uuid4()),
                batch_id=batch.batch_id,
                timestamp=datetime.now().isoformat(),
                source_path=str(src),
                destination_path=str(dest) if dest else "",
                original_size=src.stat().st_size,
                original_mtime=src.stat().st_mtime,
                status="skipped",
                conflict_policy_used="none",
                error_message="Source and destination are identical.",
            )
            journal.record_operation(op)
            details.append(op)
            skipped += 1
            continue

        # 3. Capture pre-move stats for undo journal
        stat_info = src.stat()
        src_size = stat_info.st_size
        src_mtime = stat_info.st_mtime

        # 4. Safe move execution
        try:
            safe_move_file(src, dest)
            op = OperationRecord(
                transaction_id=str(uuid.uuid4()),
                batch_id=batch.batch_id,
                timestamp=datetime.now().isoformat(),
                source_path=str(src),
                destination_path=str(dest),
                original_size=src_size,
                original_mtime=src_mtime,
                status="success",
                conflict_policy_used="keep_both" if item.conflict else "none",
                error_message=None,
            )
            journal.record_operation(op)
            details.append(op)
            successful += 1
        except Exception as e:
            op = OperationRecord(
                transaction_id=str(uuid.uuid4()),
                batch_id=batch.batch_id,
                timestamp=datetime.now().isoformat(),
                source_path=str(src),
                destination_path=str(dest),
                original_size=src_size,
                original_mtime=src_mtime,
                status="failed",
                conflict_policy_used="none",
                error_message=str(e),
            )
            journal.record_operation(op)
            details.append(op)
            failed += 1

    # Finalize batch status in journal
    if cancelled:
        status_to_record = "interrupted"
    elif failed > 0:
        status_to_record = "partial" if successful > 0 else "failed"
    else:
        status_to_record = "completed"

    journal.finish_batch(batch.batch_id, status=status_to_record)

    if on_progress:
        on_progress(total_ops, total_ops, "Complete", successful, skipped, failed)

    return ExecutionResult(
        batch_id=batch.batch_id,
        timestamp=now_str,
        total_operations=total_ops,
        successful=successful,
        skipped=skipped,
        failed=failed,
        cancelled=cancelled,
        details=details,
    )
