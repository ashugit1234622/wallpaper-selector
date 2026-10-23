"""User interface component for Download Folder Organizer."""

from __future__ import annotations
import os
import threading
from pathlib import Path
from typing import Optional, List, Dict

try:
    import customtkinter as ctk
    HAS_CUSTOMTKINTER = True
except ImportError:
    import tkinter as ctk
    HAS_CUSTOMTKINTER = False

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ...core.config import AppConfig
from .models import (
    FileItem,
    ScanSummary,
    PlanItem,
    OrganizationMode,
    ConflictPolicy,
    ExecutionResult,
    UndoResult,
    format_bytes,
)
from .scanner import get_default_downloads_folder, scan_folder
from .planner import create_organization_plan
from .executor import execute_plan
from .journal import TransactionJournal


class DownloadOrganizerView(ctk.CTkFrame if HAS_CUSTOMTKINTER else tk.Frame):
    """View container for Download Folder Organizer embedded inside Desktop Utility Suite."""

    def __init__(self, parent, config: Optional[AppConfig] = None, root_window=None, **kwargs):
        if HAS_CUSTOMTKINTER:
            super().__init__(parent, fg_color="transparent", **kwargs)
        else:
            super().__init__(parent, **kwargs)

        self.config = config or AppConfig.load()
        self.root_window = root_window or self.winfo_toplevel()
        self.journal = TransactionJournal()

        # State
        self.current_folder: Path = self._resolve_initial_folder()
        self.custom_destination: Optional[Path] = (
            Path(self.config.organizer_destination)
            if self.config.organizer_destination
            else None
        )
        self.recursive_var = tk.BooleanVar(value=getattr(self.config, "organizer_recursive", False))
        self.conflicts_only_var = tk.BooleanVar(value=False)
        self.search_filter_var = tk.StringVar(value="")
        
        # Mode & Conflict
        self.current_mode: OrganizationMode = OrganizationMode(
            getattr(self.config, "organizer_mode", OrganizationMode.BY_TYPE.value)
        )
        self.conflict_policy: ConflictPolicy = ConflictPolicy(
            getattr(self.config, "organizer_conflict_policy", ConflictPolicy.KEEP_BOTH.value)
        )

        self.discovered_files: List[FileItem] = []
        self.current_summary: ScanSummary = ScanSummary(scanned_path=self.current_folder)
        self.plan_items: List[PlanItem] = []
        self.item_checkbox_vars: Dict[str, tk.BooleanVar] = {}

        self.is_busy = False
        self.cancel_event: Optional[threading.Event] = None

        self._build_widgets()
        # Initial scan on load
        self.after(300, self.on_scan_folder)

    def _resolve_initial_folder(self) -> Path:
        if self.config.organizer_last_folder:
            p = Path(self.config.organizer_last_folder)
            if p.exists() and p.is_dir():
                return p
        return get_default_downloads_folder()

    def get_destination_folder(self) -> Path:
        if self.custom_destination:
            return self.custom_destination
        return self.current_folder / "Organized"

    def _build_widgets(self) -> None:
        # 1. Top Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent") if HAS_CUSTOMTKINTER else tk.Frame(self)
        header_frame.pack(fill="x", padx=16, pady=(8, 4))

        title_lbl = (
            ctk.CTkLabel(
                header_frame,
                text="📁 Download Folder Organizer",
                font=ctk.CTkFont(size=20, weight="bold"),
            )
            if HAS_CUSTOMTKINTER
            else tk.Label(header_frame, text="Download Folder Organizer", font=("Helvetica", 14, "bold"))
        )
        title_lbl.pack(anchor="w")

        subtitle_lbl = (
            ctk.CTkLabel(
                header_frame,
                text="Safely analyze, categorize, and organize cluttered files with pre-execution preview and full undo.",
                font=ctk.CTkFont(size=12),
                text_color="#9ca3af",
            )
            if HAS_CUSTOMTKINTER
            else tk.Label(header_frame, text="Safely categorize and organize cluttered files.", fg="#666666")
        )
        subtitle_lbl.pack(anchor="w", pady=(1, 4))

        # 2. Folder Selection Section
        folder_card = ctk.CTkFrame(self, fg_color="#1e293b", corner_radius=8) if HAS_CUSTOMTKINTER else tk.Frame(self, bg="#eeeeee")
        folder_card.pack(fill="x", padx=16, pady=4)

        f_row = ctk.CTkFrame(folder_card, fg_color="transparent") if HAS_CUSTOMTKINTER else tk.Frame(folder_card)
        f_row.pack(fill="x", padx=12, pady=(10, 6))

        src_lbl = (
            ctk.CTkLabel(f_row, text="Source Folder:", font=ctk.CTkFont(size=12, weight="bold"))
            if HAS_CUSTOMTKINTER
            else tk.Label(f_row, text="Source Folder:")
        )
        src_lbl.pack(side="left", padx=(0, 8))

        self.folder_path_entry = (
            ctk.CTkEntry(f_row, height=32, font=ctk.CTkFont(size=12))
            if HAS_CUSTOMTKINTER
            else tk.Entry(f_row)
        )
        self.folder_path_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.folder_path_entry.insert(0, str(self.current_folder))

        self.browse_btn = (
            ctk.CTkButton(
                f_row,
                text="📁 Browse",
                width=85,
                height=32,
                font=ctk.CTkFont(size=12, weight="bold"),
                command=self.on_browse_folder,
            )
            if HAS_CUSTOMTKINTER
            else tk.Button(f_row, text="Browse", command=self.on_browse_folder)
        )
        self.browse_btn.pack(side="left", padx=(0, 6))

        self.scan_btn = (
            ctk.CTkButton(
                f_row,
                text="🔍 Scan Folder",
                width=110,
                height=32,
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="#2563eb",
                hover_color="#1d4ed8",
                command=self.on_scan_folder,
            )
            if HAS_CUSTOMTKINTER
            else tk.Button(f_row, text="Scan", command=self.on_scan_folder)
        )
        self.scan_btn.pack(side="left")

        # Second row: Subfolders toggle & Target destination
        opt_row = ctk.CTkFrame(folder_card, fg_color="transparent") if HAS_CUSTOMTKINTER else tk.Frame(folder_card)
        opt_row.pack(fill="x", padx=12, pady=(0, 10))

        self.recursive_chk = (
            ctk.CTkCheckBox(
                opt_row,
                text="Include Subfolders (Recursive)",
                variable=self.recursive_var,
                font=ctk.CTkFont(size=11),
                command=self.on_scan_folder,
            )
            if HAS_CUSTOMTKINTER
            else tk.Checkbutton(opt_row, text="Include Subfolders", variable=self.recursive_var, command=self.on_scan_folder)
        )
        self.recursive_chk.pack(side="left", padx=(0, 16))

        dest_desc = f"Target Destination: {self.get_destination_folder()}"
        self.dest_lbl = (
            ctk.CTkLabel(
                opt_row,
                text=dest_desc,
                font=ctk.CTkFont(size=11),
                text_color="#94a3b8",
            )
            if HAS_CUSTOMTKINTER
            else tk.Label(opt_row, text=dest_desc)
        )
        self.dest_lbl.pack(side="left", fill="x", expand=True)

        self.dest_btn = (
            ctk.CTkButton(
                opt_row,
                text="Change Dest...",
                width=90,
                height=26,
                font=ctk.CTkFont(size=11),
                fg_color="#334155",
                hover_color="#475569",
                command=self.on_change_destination,
            )
            if HAS_CUSTOMTKINTER
            else tk.Button(opt_row, text="Change Dest", command=self.on_change_destination)
        )
        self.dest_btn.pack(side="right")

        # 3. Summary Dashboard Cards (4 metrics across)
        self.summary_frame = ctk.CTkFrame(self, fg_color="transparent") if HAS_CUSTOMTKINTER else tk.Frame(self)
        self.summary_frame.pack(fill="x", padx=16, pady=4)

        for col in range(5):
            self.summary_frame.columnconfigure(col, weight=1)

        self.card_files = self._create_metric_card(self.summary_frame, 0, "Discovered Files", "0", "#38bdf8")
        self.card_supported = self._create_metric_card(self.summary_frame, 1, "Categorized Files", "0", "#4ade80")
        self.card_organizable = self._create_metric_card(self.summary_frame, 2, "Proposed Moves", "0", "#facc15")
        self.card_conflicts = self._create_metric_card(self.summary_frame, 3, "Conflicts / Review", "0", "#f87171")
        self.card_size = self._create_metric_card(self.summary_frame, 4, "Total Size", "0 B", "#c084fc")

        # 4. Strategy & Conflict Bar
        strat_card = ctk.CTkFrame(self, fg_color="#1e293b", corner_radius=8) if HAS_CUSTOMTKINTER else tk.Frame(self)
        strat_card.pack(fill="x", padx=16, pady=4)

        s_row = ctk.CTkFrame(strat_card, fg_color="transparent") if HAS_CUSTOMTKINTER else tk.Frame(strat_card)
        s_row.pack(fill="x", padx=12, pady=8)

        mode_lbl = (
            ctk.CTkLabel(s_row, text="Organization Mode:", font=ctk.CTkFont(size=11, weight="bold"))
            if HAS_CUSTOMTKINTER
            else tk.Label(s_row, text="Mode:")
        )
        mode_lbl.pack(side="left", padx=(0, 6))

        self.mode_menu = (
            ctk.CTkOptionMenu(
                s_row,
                values=OrganizationMode.display_names(),
                command=self.on_mode_change,
                width=180,
                height=28,
                font=ctk.CTkFont(size=11),
            )
            if HAS_CUSTOMTKINTER
            else tk.OptionMenu(s_row, tk.StringVar(), *OrganizationMode.display_names())
        )
        self.mode_menu.pack(side="left", padx=(0, 16))
        if HAS_CUSTOMTKINTER:
            self.mode_menu.set(self.current_mode.to_display())

        conflict_lbl = (
            ctk.CTkLabel(s_row, text="Conflict Handling:", font=ctk.CTkFont(size=11, weight="bold"))
            if HAS_CUSTOMTKINTER
            else tk.Label(s_row, text="Conflict Handling:")
        )
        conflict_lbl.pack(side="left", padx=(0, 6))

        self.conflict_menu = (
            ctk.CTkOptionMenu(
                s_row,
                values=ConflictPolicy.display_names(),
                command=self.on_conflict_change,
                width=190,
                height=28,
                font=ctk.CTkFont(size=11),
            )
            if HAS_CUSTOMTKINTER
            else tk.OptionMenu(s_row, tk.StringVar(), *ConflictPolicy.display_names())
        )
        self.conflict_menu.pack(side="left")
        if HAS_CUSTOMTKINTER:
            self.conflict_menu.set(self.conflict_policy.to_display())

        # 5. Interactive Preview Toolbar & Table
        preview_toolbar = ctk.CTkFrame(self, fg_color="transparent") if HAS_CUSTOMTKINTER else tk.Frame(self)
        preview_toolbar.pack(fill="x", padx=16, pady=(6, 2))

        self.select_all_btn = (
            ctk.CTkButton(
                preview_toolbar,
                text="✓ Select All",
                width=85,
                height=26,
                font=ctk.CTkFont(size=11),
                fg_color="#334155",
                hover_color="#475569",
                command=self.on_select_all,
            )
            if HAS_CUSTOMTKINTER
            else tk.Button(preview_toolbar, text="Select All", command=self.on_select_all)
        )
        self.select_all_btn.pack(side="left", padx=(0, 6))

        self.deselect_all_btn = (
            ctk.CTkButton(
                preview_toolbar,
                text="✗ Deselect All",
                width=95,
                height=26,
                font=ctk.CTkFont(size=11),
                fg_color="#334155",
                hover_color="#475569",
                command=self.on_deselect_all,
            )
            if HAS_CUSTOMTKINTER
            else tk.Button(preview_toolbar, text="Deselect All", command=self.on_deselect_all)
        )
        self.deselect_all_btn.pack(side="left", padx=(0, 16))

        self.conflicts_chk = (
            ctk.CTkCheckBox(
                preview_toolbar,
                text="Show Conflicts Only",
                variable=self.conflicts_only_var,
                font=ctk.CTkFont(size=11),
                command=self._refresh_table_display,
            )
            if HAS_CUSTOMTKINTER
            else tk.Checkbutton(preview_toolbar, text="Show Conflicts Only", variable=self.conflicts_only_var, command=self._refresh_table_display)
        )
        self.conflicts_chk.pack(side="left")

        # Search filter entry on right side
        self.search_entry = (
            ctk.CTkEntry(
                preview_toolbar,
                placeholder_text="Filter files...",
                width=160,
                height=26,
                font=ctk.CTkFont(size=11),
            )
            if HAS_CUSTOMTKINTER
            else tk.Entry(preview_toolbar)
        )
        self.search_entry.pack(side="right")
        self.search_entry.bind("<KeyRelease>", lambda e: self._refresh_table_display())

        # Table container
        table_container = ctk.CTkFrame(self, fg_color="#0f172a", corner_radius=6) if HAS_CUSTOMTKINTER else tk.Frame(self)
        table_container.pack(fill="both", expand=True, padx=16, pady=4)

        # Use Treeview with custom dark styling for responsive display
        columns = ("selected", "filename", "category", "proposed_dest", "size", "status")
        self.tree = ttk.Treeview(
            table_container,
            columns=columns,
            show="headings",
            selectmode="browse",
        )
        self.tree.heading("selected", text="[x]", anchor="center")
        self.tree.heading("filename", text="Filename", anchor="w")
        self.tree.heading("category", text="Category", anchor="w")
        self.tree.heading("proposed_dest", text="Proposed Destination", anchor="w")
        self.tree.heading("size", text="Size", anchor="e")
        self.tree.heading("status", text="Status", anchor="w")

        self.tree.column("selected", width=40, stretch=False, anchor="center")
        self.tree.column("filename", width=180, stretch=True, anchor="w")
        self.tree.column("category", width=130, stretch=False, anchor="w")
        self.tree.column("proposed_dest", width=260, stretch=True, anchor="w")
        self.tree.column("size", width=80, stretch=False, anchor="e")
        self.tree.column("status", width=150, stretch=False, anchor="w")

        tree_scroll = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)

        tree_scroll.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)

        self.tree.bind("<ButtonRelease-1>", self._on_tree_click)

        # 6. Bottom Action Bar & Progress
        bottom_frame = ctk.CTkFrame(self, fg_color="#1e293b", corner_radius=8) if HAS_CUSTOMTKINTER else tk.Frame(self)
        bottom_frame.pack(fill="x", padx=16, pady=(4, 12))

        b_top_row = ctk.CTkFrame(bottom_frame, fg_color="transparent") if HAS_CUSTOMTKINTER else tk.Frame(bottom_frame)
        b_top_row.pack(fill="x", padx=12, pady=(8, 4))

        self.plan_summary_lbl = (
            ctk.CTkLabel(
                b_top_row,
                text="Scan a folder to preview and organize files.",
                font=ctk.CTkFont(size=12, weight="bold"),
            )
            if HAS_CUSTOMTKINTER
            else tk.Label(b_top_row, text="Ready.")
        )
        self.plan_summary_lbl.pack(side="left")

        self.undo_btn = (
            ctk.CTkButton(
                b_top_row,
                text="↩️ Undo Last Batch",
                width=140,
                height=30,
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color="#4b5563",
                hover_color="#374151",
                command=self.on_undo_last_batch,
            )
            if HAS_CUSTOMTKINTER
            else tk.Button(b_top_row, text="Undo Last Batch", command=self.on_undo_last_batch)
        )
        self.undo_btn.pack(side="right")

        b_act_row = ctk.CTkFrame(bottom_frame, fg_color="transparent") if HAS_CUSTOMTKINTER else tk.Frame(bottom_frame)
        b_act_row.pack(fill="x", padx=12, pady=(4, 8))

        if HAS_CUSTOMTKINTER:
            self.progress_bar = ctk.CTkProgressBar(b_act_row, height=12)
            self.progress_bar.set(0)
            self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 12))
        else:
            self.progress_bar = ttk.Progressbar(b_act_row, length=200)
            self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 12))

        self.cancel_btn = (
            ctk.CTkButton(
                b_act_row,
                text="⏹ Cancel",
                width=85,
                height=34,
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="#dc2626",
                hover_color="#b91c1c",
                state="disabled",
                command=self.on_cancel_execution,
            )
            if HAS_CUSTOMTKINTER
            else tk.Button(b_act_row, text="Cancel", state="disabled", command=self.on_cancel_execution)
        )
        self.cancel_btn.pack(side="left", padx=(0, 8))

        self.execute_btn = (
            ctk.CTkButton(
                b_act_row,
                text="🚀 Organize Selected Files",
                width=190,
                height=34,
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="#059669",
                hover_color="#047857",
                state="disabled",
                command=self.on_execute_plan,
            )
            if HAS_CUSTOMTKINTER
            else tk.Button(b_act_row, text="Organize", state="disabled", command=self.on_execute_plan)
        )
        self.execute_btn.pack(side="right")

    def _create_metric_card(self, parent, col: int, title: str, value: str, accent_color: str):
        card = (
            ctk.CTkFrame(parent, fg_color="#1e293b", corner_radius=6)
            if HAS_CUSTOMTKINTER
            else tk.Frame(parent, relief="groove", borderwidth=1)
        )
        card.grid(row=0, column=col, padx=3, pady=2, sticky="nsew")

        v_lbl = (
            ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=16, weight="bold"), text_color=accent_color)
            if HAS_CUSTOMTKINTER
            else tk.Label(card, text=value, font=("Helvetica", 12, "bold"))
        )
        v_lbl.pack(pady=(6, 0))

        t_lbl = (
            ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=10), text_color="#94a3b8")
            if HAS_CUSTOMTKINTER
            else tk.Label(card, text=title, font=("Helvetica", 9))
        )
        t_lbl.pack(pady=(0, 6))

        return {"value": v_lbl, "card": card}

    def _set_metric_card_value(self, card_dict, value: str):
        if HAS_CUSTOMTKINTER:
            card_dict["value"].configure(text=value)
        else:
            card_dict["value"].config(text=value)

    def on_browse_folder(self) -> None:
        chosen = filedialog.askdirectory(
            initialdir=str(self.current_folder),
            title="Select Folder to Organize",
        )
        if chosen:
            self.current_folder = Path(chosen).resolve()
            self.folder_path_entry.delete(0, tk.END)
            self.folder_path_entry.insert(0, str(self.current_folder))
            self.config.organizer_last_folder = str(self.current_folder)
            self.config.save()
            self._update_dest_label()
            self.on_scan_folder()

    def on_change_destination(self) -> None:
        chosen = filedialog.askdirectory(
            initialdir=str(self.get_destination_folder()),
            title="Select Destination Folder",
        )
        if chosen:
            self.custom_destination = Path(chosen).resolve()
            self.config.organizer_destination = str(self.custom_destination)
            self.config.save()
            self._update_dest_label()
            self._recalculate_plan()

    def _update_dest_label(self) -> None:
        desc = f"Target Destination: {self.get_destination_folder()}"
        if HAS_CUSTOMTKINTER:
            self.dest_lbl.configure(text=desc)
        else:
            self.dest_lbl.config(text=desc)

    def on_mode_change(self, mode_str: str) -> None:
        self.current_mode = OrganizationMode.from_display(mode_str)
        self.config.organizer_mode = self.current_mode.value
        self.config.save()
        self._recalculate_plan()

    def on_conflict_change(self, conflict_str: str) -> None:
        self.conflict_policy = ConflictPolicy.from_display(conflict_str)
        self.config.organizer_conflict_policy = self.conflict_policy.value
        self.config.save()
        self._recalculate_plan()

    def on_scan_folder(self) -> None:
        if self.is_busy:
            return

        folder_str = self.folder_path_entry.get().strip()
        if not folder_str:
            return

        p = Path(folder_str)
        if not p.exists() or not p.is_dir():
            messagebox.showerror("Invalid Directory", f"The folder '{folder_str}' does not exist or is not a directory.")
            return

        self.current_folder = p.resolve()
        self.is_busy = True
        self.scan_btn.configure(state="disabled") if HAS_CUSTOMTKINTER else self.scan_btn.config(state="disabled")
        self.plan_summary_lbl.configure(text="Scanning folder...") if HAS_CUSTOMTKINTER else self.plan_summary_lbl.config(text="Scanning...")

        def _worker():
            try:
                dest = self.get_destination_folder()
                is_recursive = self.recursive_var.get()
                files, summary = scan_folder(
                    self.current_folder,
                    destination_folder=dest,
                    recursive=is_recursive,
                )
                self.after(0, lambda: self._on_scan_complete(files, summary))
            except Exception as e:
                self.after(0, lambda: self._on_scan_error(str(e)))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_scan_error(self, err: str) -> None:
        self.is_busy = False
        self.scan_btn.configure(state="normal") if HAS_CUSTOMTKINTER else self.scan_btn.config(state="normal")
        messagebox.showerror("Scan Error", f"An error occurred while scanning: {err}")

    def _on_scan_complete(self, files: List[FileItem], summary: ScanSummary) -> None:
        self.is_busy = False
        self.scan_btn.configure(state="normal") if HAS_CUSTOMTKINTER else self.scan_btn.config(state="normal")
        self.discovered_files = files
        self.current_summary = summary

        # Update metrics
        self._set_metric_card_value(self.card_files, str(summary.total_files))
        self._set_metric_card_value(self.card_supported, str(summary.total_supported_files))
        self._set_metric_card_value(self.card_size, summary.total_size_formatted)

        self._recalculate_plan()

    def _recalculate_plan(self) -> None:
        if not self.discovered_files:
            self.plan_items = []
            self._set_metric_card_value(self.card_organizable, "0")
            self._set_metric_card_value(self.card_conflicts, "0")
            self._refresh_table_display()
            self._update_action_summary()
            return

        dest = self.get_destination_folder()
        self.plan_items = create_organization_plan(
            self.discovered_files,
            mode=self.current_mode,
            destination_folder=dest,
            conflict_policy=self.conflict_policy,
        )

        conflicts_count = sum(1 for p in self.plan_items if p.conflict)
        organizable_count = sum(1 for p in self.plan_items if p.selected)

        self._set_metric_card_value(self.card_organizable, str(organizable_count))
        self._set_metric_card_value(self.card_conflicts, str(conflicts_count))

        self._refresh_table_display()
        self._update_action_summary()

    def _refresh_table_display(self) -> None:
        self.tree.delete(*self.tree.get_children())
        filter_text = self.search_entry.get().strip().lower()
        conflicts_only = self.conflicts_only_var.get()

        for item in self.plan_items:
            if conflicts_only and not item.conflict:
                continue

            if filter_text:
                if filter_text not in item.file_item.filename.lower() and filter_text not in item.category.lower():
                    continue

            chk_str = "[✓]" if item.selected else "[ ]"
            dest_display = str(item.resolved_destination.name) if item.resolved_destination else "—"
            # Show relative destination path if inside target
            try:
                dest_display = str(item.resolved_destination.relative_to(self.current_folder))
            except Exception:
                if item.resolved_destination:
                    dest_display = str(item.resolved_destination)

            self.tree.insert(
                "",
                "end",
                iid=item.id,
                values=(
                    chk_str,
                    item.file_item.filename,
                    item.category,
                    dest_display,
                    item.file_item.size_formatted,
                    item.status,
                ),
            )

    def _on_tree_click(self, event) -> None:
        region = self.tree.identify_region(event.x, event.y)
        col = self.tree.identify_column(event.x)
        item_id = self.tree.identify_row(event.y)

        if not item_id:
            return

        # Toggle selection on click
        for p in self.plan_items:
            if p.id == item_id:
                p.selected = not p.selected
                chk_str = "[✓]" if p.selected else "[ ]"
                curr_vals = list(self.tree.item(item_id, "values"))
                curr_vals[0] = chk_str
                self.tree.item(item_id, values=curr_vals)
                break

        self._update_action_summary()

    def on_select_all(self) -> None:
        for p in self.plan_items:
            if p.resolved_destination is not None:
                p.selected = True
        self._refresh_table_display()
        self._update_action_summary()

    def on_deselect_all(self) -> None:
        for p in self.plan_items:
            p.selected = False
        self._refresh_table_display()
        self._update_action_summary()

    def _update_action_summary(self) -> None:
        selected_count = sum(1 for p in self.plan_items if p.selected)
        conflicts = sum(1 for p in self.plan_items if p.selected and p.conflict)
        direct = selected_count - conflicts

        if selected_count == 0:
            summary_msg = f"{len(self.plan_items)} files found. 0 selected for organization."
            btn_state = "disabled"
        else:
            summary_msg = (
                f"{selected_count} files selected. "
                f"{direct} will be organized directly, {conflicts} conflict(s) auto-renamed."
            )
            btn_state = "normal"

        if HAS_CUSTOMTKINTER:
            self.plan_summary_lbl.configure(text=summary_msg)
            self.execute_btn.configure(state=btn_state)
        else:
            self.plan_summary_lbl.config(text=summary_msg)
            self.execute_btn.config(state=btn_state)

    def on_execute_plan(self) -> None:
        selected_items = [p for p in self.plan_items if p.selected and p.resolved_destination is not None]
        if not selected_items:
            return

        confirm = messagebox.askyesno(
            "Confirm Organization",
            f"Are you sure you want to organize {len(selected_items)} selected file(s)?\n\n"
            f"Files will be moved to:\n{self.get_destination_folder()}\n\n"
            "This operation can be safely undone using 'Undo Last Batch'.",
        )
        if not confirm:
            return

        self.is_busy = True
        self.cancel_event = threading.Event()
        if HAS_CUSTOMTKINTER:
            self.execute_btn.configure(state="disabled")
            self.cancel_btn.configure(state="normal")
            self.browse_btn.configure(state="disabled")
            self.scan_btn.configure(state="disabled")
            self.progress_bar.set(0)
        else:
            self.execute_btn.config(state="disabled")
            self.cancel_btn.config(state="normal")

        def _progress_cb(completed, total, filename, succ, skip, fail):
            self.after(0, lambda: self._update_progress(completed, total, filename, succ, skip, fail))

        def _worker():
            res = execute_plan(
                plan=self.plan_items,
                journal=self.journal,
                source_folder=self.current_folder,
                destination_folder=self.get_destination_folder(),
                mode=self.current_mode.value,
                cancel_event=self.cancel_event,
                on_progress=_progress_cb,
            )
            self.after(0, lambda: self._on_execution_complete(res))

        threading.Thread(target=_worker, daemon=True).start()

    def _update_progress(self, completed: int, total: int, filename: str, succ: int, skip: int, fail: int):
        fraction = completed / max(1, total)
        if HAS_CUSTOMTKINTER:
            self.progress_bar.set(fraction)
            self.plan_summary_lbl.configure(
                text=f"Moving ({completed}/{total}): {filename} [✓ {succ} | ✗ {fail}]"
            )
        else:
            self.progress_bar["value"] = fraction * 100
            self.plan_summary_lbl.config(
                text=f"Moving ({completed}/{total}): {filename} [✓ {succ} | ✗ {fail}]"
            )

    def on_cancel_execution(self) -> None:
        if self.cancel_event:
            self.cancel_event.set()
            if HAS_CUSTOMTKINTER:
                self.plan_summary_lbl.configure(text="Cancelling execution safely...")
            else:
                self.plan_summary_lbl.config(text="Cancelling...")

    def _on_execution_complete(self, res: ExecutionResult) -> None:
        self.is_busy = False
        if HAS_CUSTOMTKINTER:
            self.execute_btn.configure(state="normal")
            self.cancel_btn.configure(state="disabled")
            self.browse_btn.configure(state="normal")
            self.scan_btn.configure(state="normal")
            self.progress_bar.set(1.0)
        else:
            self.execute_btn.config(state="normal")
            self.cancel_btn.config(state="disabled")

        if res.cancelled:
            msg = f"Organization cancelled by user.\n\nSuccessfully moved: {res.successful}\nRemaining/Skipped: {res.skipped}\nFailed: {res.failed}"
            messagebox.showwarning("Execution Interrupted", msg)
        elif res.failed > 0:
            msg = f"Batch completed with errors.\n\nSuccessfully moved: {res.successful}\nFailed: {res.failed}\nSkipped: {res.skipped}"
            messagebox.showwarning("Partial Success", msg)
        else:
            msg = f"Successfully organized {res.successful} file(s)!\n\nDestination:\n{self.get_destination_folder()}"
            messagebox.showinfo("Organization Complete", msg)

        # Refresh folder scan
        self.on_scan_folder()

    def on_undo_last_batch(self) -> None:
        last_batch = self.journal.get_last_undoable_batch()
        if not last_batch:
            messagebox.showinfo("No Undo Available", "No recent organizable batch was found to undo.")
            return

        confirm = messagebox.askyesno(
            "Confirm Undo",
            f"Are you sure you want to undo the last batch ({last_batch.successful_count} moves)?\n\n"
            f"Batch ID: {last_batch.batch_id[:8]}\n"
            f"Timestamp: {last_batch.timestamp[:19]}\n\n"
            "Files will be restored to their original source locations.",
        )
        if not confirm:
            return

        self.plan_summary_lbl.configure(text="Undoing last batch...") if HAS_CUSTOMTKINTER else self.plan_summary_lbl.config(text="Undoing...")

        def _worker():
            undo_res = self.journal.undo_batch(last_batch.batch_id)
            self.after(0, lambda: self._on_undo_complete(undo_res))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_undo_complete(self, res: UndoResult) -> None:
        if res.failed > 0 or res.skipped > 0:
            details = "\n".join(res.messages[:5])
            messagebox.showwarning(
                "Undo Results",
                f"Batch Undo finished.\n\nRestored: {res.undone}\nSkipped: {res.skipped}\nFailed: {res.failed}\n\n{details}",
            )
        else:
            messagebox.showinfo(
                "Undo Complete",
                f"Successfully restored all {res.undone} file(s) to their original locations!",
            )

        self.on_scan_folder()
