from __future__ import annotations

import csv
from datetime import datetime
import difflib
import json
import os
import queue
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import tkinter as tk

from compile_DSL import KNOWN_GROUPS, build_compiled_text, compile_dsl_text, required_groups_for_rule
from ablation_ui_lib.constants import (
    ALLOWED_SECTION_CODES,
    ALLOWED_TAGS,
    BATCH_SCENARIO_SETS,
    EXAMPLE_CHILD_GROUPS,
    LOG_FILE,
    LOG_JSONL_FILE,
    LOGIC_STEP_GROUPS,
    MAX_LOG_LINES,
    MEMORY_CHILD_GROUPS,
    RUNS_DIR,
    WRAPPED_RULE_RE,
)


class RuntimeMixin:
    def _dependency_issues(self, selected: set[str]) -> list[str]:
        issues: list[str] = []
        ex_children_on = sorted(EXAMPLE_CHILD_GROUPS.intersection(selected), key=lambda x: KNOWN_GROUPS.index(x))
        mem_children_on = sorted(MEMORY_CHILD_GROUPS.intersection(selected), key=lambda x: KNOWN_GROUPS.index(x))
        if "EXAMPLES" not in selected and ex_children_on:
            issues.append(f"EXAMPLES is OFF while EX_* are ON: {', '.join(ex_children_on)}")
        if "MEMORY" not in selected and mem_children_on:
            issues.append(f"MEMORY is OFF while MEM_* are ON: {', '.join(mem_children_on)}")
        logic_steps_on = sorted(LOGIC_STEP_GROUPS.intersection(selected), key=lambda x: KNOWN_GROUPS.index(x))
        if "LOGIC" not in selected and logic_steps_on:
            issues.append(f"LOGIC is OFF while LOGIC_S* are ON: {', '.join(logic_steps_on)}")
        return issues

    def _refresh_dependency_status(self) -> None:
        issues = self._dependency_issues(self._selected_groups())
        if issues:
            self.status_var.set(f"Dependency warning: {issues[0]}")
        elif self.status_var.get().startswith("Dependency warning:"):
            self.status_var.set("Ready.")
        self._refresh_warning_badge()
        try:
            if hasattr(self, "_refresh_explorer_visuals"):
                records = getattr(self, "_explorer_last_pie_records", None) or getattr(self, "_explorer_records", [])
                self._refresh_explorer_visuals(records)
        except Exception:
            pass

    def _refresh_warning_badge(self) -> None:
        warn_count = 0
        try:
            selected = self._selected_groups()
            if not Path(self.input_var.get().strip()).exists():
                warn_count += 1
            if not selected:
                warn_count += 1
            dep_issues = self._dependency_issues(selected)
            warn_count += len(dep_issues)
            if self._selection_has_no_effect(selected):
                warn_count += 1
        except Exception:
            warn_count += 1
        self.warning_badge_var.set(f"Warnings: {warn_count}")

    def _refresh_estimate(self) -> None:
        try:
            input_path = Path(self.input_var.get().strip())
            selected = self._selected_groups()
            if not input_path.exists() or not selected:
                self.estimate_var.set("Estimated output: -")
                return
            text = self._build_compiled_text(selected)
            byte_size = len(text.encode("utf-8"))
            line_count = len(text.splitlines())
            suffix = ""
            if self._selection_has_no_effect(selected):
                suffix = " | same as baseline (only inactive groups/example facets excluded)"
            self.estimate_var.set(f"Estimated output: {byte_size} bytes, {line_count} lines{suffix}")
        except Exception:
            self.estimate_var.set("Estimated output: unavailable")

    def _apply_dependency_autofix(self) -> None:
        selected = self._selected_groups()
        changed = []
        if "EXAMPLES" not in selected:
            for group in EXAMPLE_CHILD_GROUPS:
                if group in selected:
                    self.group_vars[group].set(False)
                    changed.append(group)
        if "MEMORY" not in selected:
            for group in MEMORY_CHILD_GROUPS:
                if group in selected:
                    self.group_vars[group].set(False)
                    changed.append(group)
        if "LOGIC" not in selected:
            for group in LOGIC_STEP_GROUPS:
                if group in selected:
                    self.group_vars[group].set(False)
                    changed.append(group)
        self._refresh_all_group_visuals()
        self._refresh_dependency_status()
        if changed:
            changed_sorted = sorted(changed, key=lambda x: KNOWN_GROUPS.index(x))
            self.status_var.set(f"Auto-fix applied: turned off {len(changed_sorted)} dependent groups.")
            self._append_log("Dependency auto-fix applied", extra_lines=changed_sorted)
        else:
            self.status_var.set("Auto-fix: no dependency changes needed.")

    def _run_preflight(self, require_selected: bool = True, strict_dependency: bool = False) -> dict[str, object]:
        input_path = Path(self.input_var.get().strip())
        selected = self._selected_groups()
        errors: list[str] = []
        warnings: list[str] = []
        notes: list[str] = []

        if not input_path.exists():
            errors.append(f"Input file missing: {input_path}")
            return {"ok": False, "errors": errors, "warnings": warnings, "notes": notes}
        if not input_path.is_file():
            errors.append(f"Input path is not a file: {input_path}")
            return {"ok": False, "errors": errors, "warnings": warnings, "notes": notes}

        raw_lines = input_path.read_text(encoding="utf-8").splitlines()
        wrapped_count = 0
        malformed = 0
        unknown_group_count = 0
        unknown_tag_count = 0
        bad_section_count = 0
        ids_seen: set[str] = set()
        duplicate_ids: list[str] = []
        group_rule_counts = {group: 0 for group in KNOWN_GROUPS}

        for idx, line in enumerate(raw_lines, start=1):
            if not line.startswith("{"):
                continue
            wrapped_count += 1
            m = WRAPPED_RULE_RE.match(line)
            if not m:
                malformed += 1
                if malformed <= 5:
                    errors.append(f"Malformed wrapper at line {idx}")
                continue
            rule_id, tag, group = m.group(1), m.group(2), m.group(3)
            sec = rule_id.split("-")[0]
            if sec not in ALLOWED_SECTION_CODES:
                bad_section_count += 1
            if tag not in ALLOWED_TAGS:
                unknown_tag_count += 1
            if group not in KNOWN_GROUPS:
                unknown_group_count += 1
            else:
                for required in required_groups_for_rule(rule_id, group):
                    if required in group_rule_counts:
                        group_rule_counts[required] += 1
            if rule_id in ids_seen:
                duplicate_ids.append(rule_id)
            ids_seen.add(rule_id)

        if malformed:
            errors.append(f"Wrapper format errors: {malformed}")
        if duplicate_ids:
            errors.append(f"Duplicate IDs: {len(duplicate_ids)} (eg {duplicate_ids[0]})")
        if unknown_group_count:
            errors.append(f"Unknown GROUP values: {unknown_group_count}")
        if bad_section_count:
            errors.append(f"Unknown section code in IDs: {bad_section_count}")
        if unknown_tag_count:
            warnings.append(f"Unknown TAG values: {unknown_tag_count}")

        dep_issues = self._dependency_issues(selected)
        if require_selected:
            if strict_dependency:
                errors.extend(dep_issues)
            else:
                warnings.extend(dep_issues)
        if require_selected and not selected:
            errors.append("No groups selected.")
        if require_selected and selected:
            excluded = [group for group in KNOWN_GROUPS if group not in selected]
            empty_off = [group for group in excluded if group_rule_counts.get(group, 0) == 0]
            excluded_facets = self._excluded_example_facets()
            facet_counts = getattr(self, "_example_facet_counts", {})
            empty_facet_off = [facet for facet in excluded_facets if int(facet_counts.get(facet, 0)) == 0]
            groups_have_effect = bool(excluded) and len(empty_off) != len(excluded)
            facets_have_effect = bool(excluded_facets) and len(empty_facet_off) != len(excluded_facets)
            if (excluded or excluded_facets) and not groups_have_effect and not facets_have_effect:
                warnings.append(
                    "Current selection excludes only groups/example facets with no live rules, so compiled output should match baseline."
                )
            elif empty_off:
                preview = ", ".join(empty_off[:6])
                if len(empty_off) > 6:
                    preview += ", ..."
                warnings.append(f"Current selection also excludes groups with no tagged rules: {preview}")
            if empty_facet_off:
                preview = ", ".join(empty_facet_off[:6])
                if len(empty_facet_off) > 6:
                    preview += ", ..."
                warnings.append(f"Current selection also excludes example facets with no live rules: {preview}")

        excluded_facets = self._excluded_example_facets()
        if excluded_facets:
            notes.append(f"Excluded example facets: {', '.join(excluded_facets)}")

        notes.append(f"Wrapped rules: {wrapped_count}")
        notes.append(f"Selected groups: {len(selected)}")
        notes.append(f"Groups with no tagged rules in current source: {sum(1 for count in group_rule_counts.values() if count == 0)}")
        notes.append(f"Strict dependency lint: {'ON' if strict_dependency else 'OFF'}")
        notes.append(f"Input stats: {self._file_stats(input_path)}")

        return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings, "notes": notes}

    def _run_preflight_report(self, require_selected: bool = True) -> bool:
        result = self._run_preflight(
            require_selected=require_selected,
            strict_dependency=self.strict_dep_lint_var.get(),
        )
        lines: list[str] = []
        ok = bool(result["ok"])
        if ok:
            lines.append("PASS: preflight checks passed.")
        else:
            lines.append("FAIL: preflight checks found blocking errors.")
        for err in result["errors"]:
            lines.append(f"ERROR: {err}")
        for warn in result["warnings"]:
            lines.append(f"WARN: {warn}")
        for note in result["notes"]:
            lines.append(f"INFO: {note}")
        self._set_inspector_text("Preflight Report", lines)
        self.status_var.set("Preflight PASS." if ok else "Preflight FAIL. See inspector.")
        self._append_log("Preflight " + ("PASS" if ok else "FAIL"), extra_lines=lines[:12])
        return ok

    def _build_compiled_text(self, enabled_groups: set[str]) -> str:
        input_path = Path(self.input_var.get().strip())
        lines = input_path.read_text(encoding="utf-8").splitlines()
        return build_compiled_text(
            lines,
            enabled_groups=enabled_groups,
            excluded_groups=set(),
            excluded_example_facets=set(self._excluded_example_facets()),
        )

    @staticmethod
    def _count_headings(text: str) -> int:
        return sum(1 for line in text.splitlines() if line.startswith("#"))

    def _get_diff_lines(self, new_text: str, compare_path: Path | None) -> tuple[str, list[str]]:
        if compare_path and compare_path.exists() and compare_path.is_file():
            old_text = compare_path.read_text(encoding="utf-8")
            label = f"vs {compare_path.name}"
        else:
            baseline = self._build_compiled_text(set(KNOWN_GROUPS))
            old_text = baseline
            label = "vs baseline (all groups)"
        diff = list(
            difflib.unified_diff(
                old_text.splitlines(),
                new_text.splitlines(),
                fromfile="old",
                tofile="new",
                n=2,
            )
        )
        return label, diff

    def _preview_diff_report(self) -> None:
        input_path = Path(self.input_var.get().strip())
        if not input_path.exists():
            messagebox.showerror("Input not found", f"Input file does not exist:\n{input_path}")
            return
        selected = self._selected_groups()
        if not selected:
            messagebox.showerror("No groups selected", "Select at least one group before previewing diff.")
            return
        from ablation_ui_lib.constants import MAX_INSPECTOR_LINES

        new_text = self._build_compiled_text(selected)
        target = Path(self.output_var.get().strip())
        label, diff = self._get_diff_lines(new_text, target)
        lines = [
            f"Comparison: {label}",
            f"New output: {len(new_text)} chars, {len(new_text.splitlines())} lines, {self._count_headings(new_text)} headings",
            f"Changed lines in unified diff: {max(0, len(diff) - 2)}",
        ]
        lines.extend(diff[:MAX_INSPECTOR_LINES])
        self._set_inspector_text("Diff Preview", lines)
        self.status_var.set("Diff preview ready (see inspector).")

    def _compare_against_last_run(self) -> None:
        compare_path: Path | None = self._last_compile_output
        if compare_path is None or not compare_path.exists():
            events = self._read_log_events()
            for event in reversed(events):
                if event.get("run_type") != "single_compile":
                    continue
                output_path = event.get("output_path")
                if not output_path:
                    continue
                candidate = Path(output_path)
                if candidate.exists() and candidate.is_file():
                    compare_path = candidate
                    break
        if compare_path is None or not compare_path.exists():
            messagebox.showerror("No previous compile", "No previous compile output found to compare against.")
            return

        selected = self._selected_groups()
        if not selected:
            messagebox.showerror("No groups selected", "Select at least one group before comparing.")
            return
        new_text = self._build_compiled_text(selected)
        label, diff = self._get_diff_lines(new_text, compare_path)
        lines = [
            f"Comparison: {label}",
            f"Target: {compare_path}",
            f"New output: {len(new_text)} chars, {len(new_text.splitlines())} lines, {self._count_headings(new_text)} headings",
            f"Changed lines in unified diff: {max(0, len(diff) - 2)}",
        ]
        lines.extend(diff[:MAX_INSPECTOR_LINES])
        self._set_inspector_text("Compare Against Last Run", lines)
        self.status_var.set("Comparison against last run ready (see inspector).")

    def _build_batch_plan(self, output_dir: Path) -> list[Path]:
        scenarios = self._active_batch_scenarios()
        return [output_dir / "Alan_dsl_baseline_ALL.txt"] + [
            output_dir / f"Alan_dsl_{scenario_id}.txt" for scenario_id, _removed in scenarios
        ]

    def _preview_batch_plan(self) -> None:
        out_dir = self._resolve_batch_output_dir()
        if out_dir is None:
            return
        plan = self._build_batch_plan(out_dir)
        mode = self.batch_mode_var.get().strip() or "Phase 1 (Screening 12)"
        scenarios = self._active_batch_scenarios()
        lines = [f"Batch mode: {mode}", f"Output directory: {out_dir}", f"Planned files: {len(plan)}"]
        lines.append(plan[0].name + " (baseline: all groups ON)")
        for scenario_id, removed in scenarios:
            removed_text = ", ".join(sorted(removed, key=lambda x: KNOWN_GROUPS.index(x)))
            lines.append(f"Alan_dsl_{scenario_id}.txt (drop: {removed_text})")
        self._set_inspector_text("Batch Plan", lines)
        self.status_var.set(f"Batch plan preview ready ({mode}, {len(plan)} files).")

    def _next_run_id(self, kind: str) -> str:
        return f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{kind}"

    def _artifact_dir_for(self, kind: str) -> Path:
        run_dir = RUNS_DIR / self._next_run_id(kind)
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def _resolve_batch_output_dir(self) -> Path | None:
        if self.use_artifacts_var.get():
            return RUNS_DIR / self._next_run_id("batch")
        output_dir = filedialog.askdirectory(title="Choose folder for batch outputs")
        if not output_dir:
            return None
        return Path(output_dir)

    def _active_batch_scenarios(self) -> list[tuple[str, set[str]]]:
        mode = self.batch_mode_var.get().strip()
        return list(BATCH_SCENARIO_SETS.get(mode, BATCH_SCENARIO_SETS["Phase 1 (Screening 12)"]))

    @staticmethod
    def _read_log_lines() -> list[str]:
        if not LOG_FILE.exists() or not LOG_FILE.is_file():
            return []
        try:
            lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
            return lines[-MAX_LOG_LINES:]
        except Exception:
            return []

    @staticmethod
    def _read_log_events() -> list[dict]:
        if not LOG_JSONL_FILE.exists() or not LOG_JSONL_FILE.is_file():
            return []
        events: list[dict] = []
        try:
            for line in LOG_JSONL_FILE.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if isinstance(obj, dict):
                    events.append(obj)
        except Exception:
            return []
        return events[-MAX_LOG_LINES:]

    def _refresh_log_view(self) -> None:
        if self.log_widget is None:
            return
        lines = self._read_log_lines()
        if not lines:
            lines = ["(No log entries yet)"]
        text = "\n".join(lines) + "\n"
        self.log_widget.config(state="normal")
        self.log_widget.delete("1.0", tk.END)
        self.log_widget.insert(tk.END, text)
        self.log_widget.see(tk.END)
        self.log_widget.config(state="disabled")

    def _append_log(self, message: str, extra_lines: list[str] | None = None, metadata: dict | None = None) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [f"[{ts}] {message}"]
        if extra_lines:
            lines.extend([f"  - {line}" for line in extra_lines])
        try:
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            existing = self._read_log_lines()
            existing.extend(lines)
            existing = existing[-MAX_LOG_LINES:]
            LOG_FILE.write_text("\n".join(existing) + "\n", encoding="utf-8")
            payload = {
                "timestamp": ts,
                "message": message,
                "lines": extra_lines or [],
                "preset": self.preset_var.get(),
                "input": self.input_var.get(),
                "output": self.output_var.get(),
                "selected_groups": sorted(self._selected_groups(), key=lambda x: KNOWN_GROUPS.index(x)),
            }
            if metadata:
                payload.update(metadata)
            with LOG_JSONL_FILE.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception:
            pass
        self._refresh_log_view()

    def _export_log_json(self) -> None:
        events = self._read_log_events()
        if not events:
            messagebox.showerror("No log data", "No log events to export.")
            return
        path = filedialog.asksaveasfilename(
            title="Export run log as JSON",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        out = Path(path)
        out.write_text(json.dumps(events, indent=2, ensure_ascii=False), encoding="utf-8")
        self.status_var.set(f"Exported log JSON: {out.name}")
        self._append_log(f"Exported run log JSON -> {out}")

    def _export_log_csv(self) -> None:
        events = self._read_log_events()
        if not events:
            messagebox.showerror("No log data", "No log events to export.")
            return
        path = filedialog.asksaveasfilename(
            title="Export run log as CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        out = Path(path)
        headers = [
            "timestamp",
            "message",
            "preset",
            "input",
            "output",
            "selected_groups",
            "lines",
        ]
        with out.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            for event in events:
                row = {
                    "timestamp": event.get("timestamp", ""),
                    "message": event.get("message", ""),
                    "preset": event.get("preset", ""),
                    "input": event.get("input", ""),
                    "output": event.get("output", ""),
                    "selected_groups": "|".join(event.get("selected_groups", [])),
                    "lines": "|".join(event.get("lines", [])),
                }
                writer.writerow(row)
        self.status_var.set(f"Exported log CSV: {out.name}")
        self._append_log(f"Exported run log CSV -> {out}")

    def _run_in_background(self, label: str, worker_fn, on_success) -> None:
        if self._job_running:
            messagebox.showerror("Busy", "A job is already running. Please wait.")
            return
        self._set_busy(True)
        self.status_var.set(f"{label}...")
        self._job_queue = queue.Queue()

        def _worker() -> None:
            try:
                result = worker_fn()
                self._job_queue.put(("ok", result))
            except Exception as exc:
                self._job_queue.put(("err", str(exc)))

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        self.after(100, lambda: self._poll_job_queue(on_success))

    def _show_run_summary_toast(
        self,
        output_path: Path,
        selected_count: int,
        excluded_count: int,
        excluded_example_facet_count: int,
    ) -> None:
        toast = tk.Toplevel(self)
        toast.title("Compile Summary")
        toast.transient(self)
        toast.resizable(False, False)
        toast.attributes("-topmost", True)
        frm = tk.Frame(toast, padx=12, pady=10)
        frm.pack(fill=tk.BOTH, expand=True)
        facet_line = (
            f"\nExample facets OFF: {excluded_example_facet_count}"
            if excluded_example_facet_count
            else ""
        )
        tk.Label(
            frm,
            text=f"Compiled successfully\n{output_path}\nON: {selected_count}  OFF: {excluded_count}{facet_line}",
            justify="left",
            anchor="w",
        ).grid(row=0, column=0, columnspan=3, sticky="w")
        tk.Button(frm, text="Open Folder", command=lambda: self._open_output_folder(output_path)).grid(
            row=1, column=0, pady=(10, 0), padx=(0, 6)
        )
        tk.Button(frm, text="Copy Path", command=lambda: self._copy_output_path(output_path)).grid(
            row=1, column=1, pady=(10, 0), padx=(0, 6)
        )
        tk.Button(frm, text="Close", command=toast.destroy).grid(row=1, column=2, pady=(10, 0))
        toast.update_idletasks()
        x = self.winfo_rootx() + 80
        y = self.winfo_rooty() + 80
        toast.geometry(f"+{x}+{y}")

    @staticmethod
    def _open_output_folder(path: Path) -> None:
        folder = path.parent
        try:
            os.startfile(str(folder))
        except Exception:
            pass

    def _copy_output_path(self, path: Path) -> None:
        self.clipboard_clear()
        self.clipboard_append(str(path))
        self.status_var.set("Output path copied to clipboard.")

    def _poll_job_queue(self, on_success) -> None:
        if self._job_queue is None:
            self._set_busy(False)
            return
        try:
            status, payload = self._job_queue.get_nowait()
        except queue.Empty:
            self.after(100, lambda: self._poll_job_queue(on_success))
            return
        self._set_busy(False)
        if status == "ok":
            on_success(payload)
        else:
            self.status_var.set("Job failed.")
            messagebox.showerror("Operation failed", str(payload))

    def _compile_selected(self) -> None:
        dep_issues = self._dependency_issues(self._selected_groups())
        if dep_issues and self.auto_fix_on_compile_var.get():
            self._set_inspector_text(
                "Dependency Warning",
                ["Auto-fix was enabled and applied before compile."] + dep_issues,
            )
            self._apply_dependency_autofix()
            self._append_log("Dependency auto-fix applied automatically before compile", dep_issues)
        elif dep_issues and not self.auto_fix_on_compile_var.get():
            self._set_inspector_text(
                "Dependency Warning",
                ["Auto-fix is OFF. Compile will continue unless strict lint blocks it."] + dep_issues,
            )
            self.status_var.set("Dependency warning present. See inspector.")

        if not self._run_preflight_report(require_selected=True):
            return
        selected = self._selected_groups()
        if not selected:
            messagebox.showerror("No groups selected", "Select at least one group before compiling.")
            return

        input_path = Path(self.input_var.get().strip())
        requested_output = Path(self.output_var.get().strip())
        if self.use_artifacts_var.get():
            output_dir = self._artifact_dir_for("compile")
            output_path = output_dir / requested_output.name
        else:
            output_path = requested_output

        if output_path.exists():
            ok = messagebox.askyesno(
                "Overwrite output?",
                f"Output file already exists:\n{output_path}\n\nOverwrite it?",
            )
            if not ok:
                self.status_var.set("Compile cancelled (existing output not overwritten).")
                return

        if self.show_diff_var.get():
            try:
                new_text = self._build_compiled_text(selected)
                label, diff_lines = self._get_diff_lines(new_text, output_path)
                preview = "\n".join(diff_lines[:24]) if diff_lines else "(no changes)"
                go = messagebox.askyesno(
                    "Diff preview",
                    f"{label}\nChanged lines: {max(0, len(diff_lines) - 2)}\n\n{preview}\n\nProceed with compile?",
                )
                if not go:
                    self.status_var.set("Compile cancelled after diff preview.")
                    return
            except Exception as exc:
                cont = messagebox.askyesno(
                    "Diff preview failed",
                    f"Could not build diff preview:\n{exc}\n\nContinue compile anyway?",
                )
                if not cont:
                    return

        def _worker():
            output_path.parent.mkdir(parents=True, exist_ok=True)
            excluded_example_facets = set(self._excluded_example_facets())
            compile_dsl_text(
                input_file=input_path,
                output_file=output_path,
                enabled_groups=selected,
                excluded_groups=set(),
                excluded_example_facets=excluded_example_facets,
            )
            return {
                "output_path": output_path,
                "selected": sorted(selected, key=lambda x: KNOWN_GROUPS.index(x)),
                "excluded_example_facets": sorted(excluded_example_facets),
            }

        def _done(payload):
            out = Path(payload["output_path"])
            selected_sorted = payload["selected"]
            excluded = sorted(set(KNOWN_GROUPS) - set(selected_sorted), key=lambda x: KNOWN_GROUPS.index(x))
            excluded_example_facets = payload.get("excluded_example_facets", [])
            self._last_compile_output = out
            self.status_var.set(
                f"Compiled {out.name} ({len(selected_sorted)} groups on, {len(excluded)} groups off, {len(excluded_example_facets)} example facets off)."
            )
            self._append_log(
                f"Compile -> {out} (on={len(selected_sorted)}, off={len(excluded)})",
                metadata={
                    "run_type": "single_compile",
                    "artifact_mode": self.use_artifacts_var.get(),
                    "output_path": str(out),
                    "excluded_example_facets": excluded_example_facets,
                },
            )
            self._refresh_stats()
            self._refresh_warning_badge()
            self._refresh_estimate()
            self._set_inspector_text(
                "Compile Result",
                [
                    f"Output: {out}",
                    f"Selected groups: {len(selected_sorted)}",
                    f"Excluded groups: {len(excluded)}",
                    f"Excluded example facets: {', '.join(excluded_example_facets) if excluded_example_facets else '(none)'}",
                ],
            )
            self._show_run_summary_toast(
                out,
                len(selected_sorted),
                len(excluded),
                len(excluded_example_facets),
            )

        self._run_in_background("Compiling", _worker, _done)

    def _run_starter_batch(self) -> None:
        if not self._run_preflight_report(require_selected=False):
            return
        mode = self.batch_mode_var.get().strip() or "Phase 1 (Screening 12)"
        scenarios = self._active_batch_scenarios()
        input_path = Path(self.input_var.get().strip())
        if self.use_artifacts_var.get():
            out_dir = self._artifact_dir_for("batch")
        else:
            chosen = filedialog.askdirectory(title="Choose folder for batch outputs")
            if not chosen:
                return
            out_dir = Path(chosen)

        plan = self._build_batch_plan(out_dir)
        existing = [p for p in plan if p.exists()]
        if existing:
            preview = "\n".join(str(p.name) for p in existing[:8])
            if len(existing) > 8:
                preview += "\n..."
            ok = messagebox.askyesno(
                "Overwrite batch files?",
                f"{len(existing)} target file(s) already exist in:\n{out_dir}\n\n{preview}\n\nOverwrite all?",
            )
            if not ok:
                self.status_var.set("Batch cancelled (existing files not overwritten).")
                return

        def _worker():
            out_dir.mkdir(parents=True, exist_ok=True)
            created_files: list[str] = []
            baseline_out = out_dir / "Alan_dsl_baseline_ALL.txt"
            compile_dsl_text(
                input_file=input_path,
                output_file=baseline_out,
                enabled_groups=set(KNOWN_GROUPS),
                excluded_groups=set(),
            )
            created_files.append(baseline_out.name)
            for scenario_id, removed in scenarios:
                selected = set(KNOWN_GROUPS)
                selected -= removed
                out_file = out_dir / f"Alan_dsl_{scenario_id}.txt"
                compile_dsl_text(
                    input_file=input_path,
                    output_file=out_file,
                    enabled_groups=selected,
                    excluded_groups=set(),
                )
                created_files.append(out_file.name)
            return {"out_dir": out_dir, "created": created_files}

        def _done(payload):
            created = payload["created"]
            out = payload["out_dir"]
            self.status_var.set(f"Batch complete ({mode}): {len(created)} files in {out}.")
            self._append_log(
                f"Batch [{mode}] -> {out} ({len(created)} files)",
                extra_lines=created,
                metadata={
                    "run_type": "batch",
                    "batch_mode": mode,
                    "batch_cases": [scenario_id for scenario_id, _removed in scenarios],
                    "artifact_mode": self.use_artifacts_var.get(),
                },
            )
            self._refresh_stats()
            self._set_inspector_text(
                "Batch Result",
                [f"Batch mode: {mode}", f"Output directory: {out}", f"Files created: {len(created)}"] + created,
            )
            messagebox.showinfo(
                "Batch complete",
                f"Created {len(created)} files in:\n{out}\n\n"
                f"{chr(10).join(created[:8])}\n"
                f"{'...' if len(created) > 8 else ''}",
            )

        self._run_in_background(f"Running batch ({mode})", _worker, _done)
