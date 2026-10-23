"""Durable transaction journal and undo engine for Download Folder Organizer."""

from __future__ import annotations
import json
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable

from ...core.config import AppConfig
from .models import (
    OperationRecord,
    BatchRecord,
    UndoResult,
)


class TransactionJournal:
    """Manages durable transaction logs and batch reversal."""

    def __init__(self, journal_path: Optional[Path] = None):
        if journal_path:
            self.journal_path = Path(journal_path)
        else:
            self.journal_path = AppConfig.get_default_data_dir() / "organizer_journal.json"
        
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_journal_exists()

    def _ensure_journal_exists(self) -> None:
        if not self.journal_path.exists():
            self._write_raw({"version": "1.0", "batches": []})

    def _read_raw(self) -> Dict[str, Any]:
        if not self.journal_path.exists():
            return {"version": "1.0", "batches": []}
        try:
            with open(self.journal_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict) or "batches" not in data:
                    return {"version": "1.0", "batches": []}
                return data
        except Exception:
            # If journal is corrupted, back it up and start fresh
            try:
                backup = self.journal_path.with_suffix(f".corrupt_{int(datetime.now().timestamp())}.bak")
                shutil.copy2(self.journal_path, backup)
            except Exception:
                pass
            fallback = {"version": "1.0", "batches": []}
            self._write_raw(fallback)
            return fallback

    def _write_raw(self, data: Dict[str, Any]) -> None:
        temp_file = self.journal_path.with_suffix(".tmp")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            temp_file.replace(self.journal_path)
        except Exception:
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass

    def start_batch(
        self,
        source_folder: Path,
        destination_folder: Path,
        mode: str,
        total_items: int,
    ) -> BatchRecord:
        """Start a new batch and register it as in_progress."""
        batch_id = str(uuid.uuid4())
        now_str = datetime.now().isoformat()

        batch = BatchRecord(
            batch_id=batch_id,
            timestamp=now_str,
            source_folder=str(source_folder.resolve()),
            destination_folder=str(destination_folder.resolve()),
            mode=mode,
            total_items=total_items,
            status="in_progress",
        )

        data = self._read_raw()
        data["batches"].append(
            {
                "batch_id": batch.batch_id,
                "timestamp": batch.timestamp,
                "source_folder": batch.source_folder,
                "destination_folder": batch.destination_folder,
                "mode": batch.mode,
                "total_items": batch.total_items,
                "successful_count": 0,
                "skipped_count": 0,
                "failed_count": 0,
                "status": batch.status,
                "operations": [],
            }
        )
        self._write_raw(data)
        return batch

    def record_operation(self, op: OperationRecord) -> None:
        """Append a single operation's outcome to its batch in the journal."""
        data = self._read_raw()
        for b in data.get("batches", []):
            if b.get("batch_id") == op.batch_id:
                b.setdefault("operations", []).append(
                    {
                        "transaction_id": op.transaction_id,
                        "batch_id": op.batch_id,
                        "timestamp": op.timestamp,
                        "source_path": op.source_path,
                        "destination_path": op.destination_path,
                        "original_size": op.original_size,
                        "original_mtime": op.original_mtime,
                        "status": op.status,
                        "conflict_policy_used": op.conflict_policy_used,
                        "error_message": op.error_message,
                    }
                )
                if op.status == "success":
                    b["successful_count"] = b.get("successful_count", 0) + 1
                elif op.status == "skipped":
                    b["skipped_count"] = b.get("skipped_count", 0) + 1
                elif op.status == "failed":
                    b["failed_count"] = b.get("failed_count", 0) + 1
                break
        self._write_raw(data)

    def finish_batch(self, batch_id: str, status: str = "completed") -> None:
        """Mark a batch as completed, partial, or interrupted."""
        data = self._read_raw()
        for b in data.get("batches", []):
            if b.get("batch_id") == batch_id:
                b["status"] = status
                break
        self._write_raw(data)

    def get_last_undoable_batch(self) -> Optional[BatchRecord]:
        """Find the most recent batch that has successful operations and is not undone."""
        data = self._read_raw()
        for b in reversed(data.get("batches", [])):
            if b.get("status") in ("completed", "partial", "interrupted"):
                # Check if it has any successful operations that are not undone
                has_undoable_ops = any(
                    op.get("status") == "success" for op in b.get("operations", [])
                )
                if has_undoable_ops:
                    ops = [
                        OperationRecord(
                            transaction_id=op["transaction_id"],
                            batch_id=op["batch_id"],
                            timestamp=op["timestamp"],
                            source_path=op["source_path"],
                            destination_path=op["destination_path"],
                            original_size=op["original_size"],
                            original_mtime=op["original_mtime"],
                            status=op["status"],
                            conflict_policy_used=op["conflict_policy_used"],
                            error_message=op.get("error_message"),
                        )
                        for op in b.get("operations", [])
                    ]
                    return BatchRecord(
                        batch_id=b["batch_id"],
                        timestamp=b["timestamp"],
                        source_folder=b["source_folder"],
                        destination_folder=b["destination_folder"],
                        mode=b["mode"],
                        total_items=b["total_items"],
                        successful_count=b.get("successful_count", 0),
                        skipped_count=b.get("skipped_count", 0),
                        failed_count=b.get("failed_count", 0),
                        status=b["status"],
                        operations=ops,
                    )
        return None

    def get_interrupted_batches(self) -> List[BatchRecord]:
        """Find any batches that were left in 'in_progress' status."""
        data = self._read_raw()
        results: List[BatchRecord] = []
        for b in data.get("batches", []):
            if b.get("status") == "in_progress":
                ops = [
                    OperationRecord(
                        transaction_id=op["transaction_id"],
                        batch_id=op["batch_id"],
                        timestamp=op["timestamp"],
                        source_path=op["source_path"],
                        destination_path=op["destination_path"],
                        original_size=op["original_size"],
                        original_mtime=op["original_mtime"],
                        status=op["status"],
                        conflict_policy_used=op["conflict_policy_used"],
                        error_message=op.get("error_message"),
                    )
                    for op in b.get("operations", [])
                ]
                results.append(
                    BatchRecord(
                        batch_id=b["batch_id"],
                        timestamp=b["timestamp"],
                        source_folder=b["source_folder"],
                        destination_folder=b["destination_folder"],
                        mode=b["mode"],
                        total_items=b["total_items"],
                        successful_count=b.get("successful_count", 0),
                        skipped_count=b.get("skipped_count", 0),
                        failed_count=b.get("failed_count", 0),
                        status=b["status"],
                        operations=ops,
                    )
                )
        return results

    def undo_batch(
        self,
        batch_id: str,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
    ) -> UndoResult:
        """Safely reverse all successful operations in a batch."""
        data = self._read_raw()
        target_batch = None
        for b in data.get("batches", []):
            if b.get("batch_id") == batch_id:
                target_batch = b
                break

        if not target_batch:
            return UndoResult(
                batch_id=batch_id,
                total=0,
                undone=0,
                skipped=0,
                failed=1,
                messages=[f"Batch ID '{batch_id}' not found in journal."],
            )

        eligible_ops = [
            op for op in target_batch.get("operations", []) if op.get("status") == "success"
        ]
        total_eligible = len(eligible_ops)
        undone_count = 0
        skipped_count = 0
        failed_count = 0
        messages: List[str] = []

        for idx, op in enumerate(eligible_ops):
            dest_p = Path(op["destination_path"])
            orig_p = Path(op["source_path"])
            filename = dest_p.name

            if on_progress:
                on_progress(idx + 1, total_eligible, filename)

            # Verification: Destination file must still exist
            if not dest_p.exists() or not dest_p.is_file():
                skipped_count += 1
                messages.append(f"Skipped '{filename}': File not found at '{dest_p}'.")
                continue

            # Verification: File size should match original size
            try:
                curr_size = dest_p.stat().st_size
                if curr_size != op["original_size"]:
                    skipped_count += 1
                    messages.append(
                        f"Skipped '{filename}': File size changed since move ({curr_size} != {op['original_size']} B)."
                    )
                    continue
            except Exception as e:
                failed_count += 1
                messages.append(f"Failed verifying '{filename}': {e}")
                continue

            # Verification: Original location must be available or safely resolvable
            if orig_p.exists():
                skipped_count += 1
                messages.append(
                    f"Skipped '{filename}': Original path '{orig_p}' is already occupied."
                )
                continue

            # Execute reverse move
            try:
                orig_p.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(dest_p), str(orig_p))
                op["status"] = "undone"
                undone_count += 1
            except Exception as e:
                failed_count += 1
                messages.append(f"Failed reversing '{filename}': {e}")

        # Update batch status in journal
        all_undone = all(
            op.get("status") in ("undone", "skipped", "failed")
            for op in target_batch.get("operations", [])
        )
        if all_undone:
            target_batch["status"] = "undone"
        self._write_raw(data)

        return UndoResult(
            batch_id=batch_id,
            total=total_eligible,
            undone=undone_count,
            skipped=skipped_count,
            failed=failed_count,
            messages=messages,
        )
