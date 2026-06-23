from __future__ import annotations

import queue
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont

from compile_DSL import KNOWN_GROUPS
from ablation_ui_lib.constants import FAVORITE_EXPRESSIONS
from ablation_ui_lib.runtime_mixin import RuntimeMixin
from ablation_ui_lib.ui_mixin import UIMixin
from ablation_ui_lib.widgets import RoundedButton


class AblationUI(UIMixin, RuntimeMixin, tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Alan DSL Ablation UI")
        self.geometry("1320x900")
        self.minsize(1180, 800)

        self.input_var = tk.StringVar(value="Alan_DSL")
        self.output_var = tk.StringVar(value="Alan_dsl_complied.txt")
        self.preset_var = tk.StringVar(value="00 Baseline (include all groups)")
        self.batch_mode_var = tk.StringVar(value="Phase 1 (Screening 12)")
        self.preset_help_var = tk.StringVar(value="")
        self.phase_help_var = tk.StringVar(value="")
        self.preset_count_var = tk.StringVar(value="")
        self.custom_expr_var = tk.StringVar(value="")
        self.recent_expr_var = tk.StringVar(value="")
        self.favorite_expr_var = tk.StringVar(value=next(iter(FAVORITE_EXPRESSIONS.keys())))
        self.use_artifacts_var = tk.BooleanVar(value=True)
        self.show_diff_var = tk.BooleanVar(value=True)
        self.strict_dep_lint_var = tk.BooleanVar(value=False)
        self.auto_fix_on_compile_var = tk.BooleanVar(value=True)
        self.lock_baseline_var = tk.BooleanVar(value=False)
        self.show_advanced_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Ready.")
        self.stats_var = tk.StringVar(value="Input: -\nOutput: -")
        self.estimate_var = tk.StringVar(value="Estimated output: -")
        self.warning_badge_var = tk.StringVar(value="Warnings: 0")
        self.example_facet_info_var = tk.StringVar(value="Example facets: -")
        self.explorer_stats_var = tk.StringVar(value="Rules: -  Sections: -  TAGs: -  GROUPs: -  Facets: -  Tokens: -  Tokenizer: -")
        self.explorer_section_totals_var = tk.StringVar(value="Section totals: -")
        self.explorer_visual_summary_var = tk.StringVar(value="Visual summary: -")
        self.explorer_subpart_title_var = tk.StringVar(value="Subparts: -")
        self.explorer_metric_var = tk.StringVar(value="Tokens")
        self.explorer_filter_section_var = tk.StringVar(value="All sections")
        self.explorer_filter_tag_var = tk.StringVar(value="All tags")
        self.explorer_filter_group_var = tk.StringVar(value="All groups")
        self.explorer_filter_facet_var = tk.StringVar(value="All facets")
        self.explorer_search_var = tk.StringVar(value="")
        self.explorer_tree_mirror_var = tk.BooleanVar(value=False)
        self.explorer_filter_info_var = tk.StringVar(value="0 matching rules")
        self.log_widget: tk.Text | None = None
        self.inspector_widget: tk.Text | None = None
        self.explorer_tree: ttk.Treeview | None = None
        self.explorer_table: ttk.Treeview | None = None
        self.explorer_detail_widget: tk.Text | None = None
        self.explorer_section_pie_canvas: tk.Canvas | None = None
        self.explorer_subpart_pie_canvas: tk.Canvas | None = None
        self.explorer_heatmap_canvas: tk.Canvas | None = None
        self.explorer_treemap_canvas: tk.Canvas | None = None
        self.explorer_coverage_canvas: tk.Canvas | None = None
        self.explorer_delta_canvas: tk.Canvas | None = None
        self.explorer_trend_canvas: tk.Canvas | None = None
        self.explorer_dep_canvas: tk.Canvas | None = None
        self.explorer_section_combo: ttk.Combobox | None = None
        self.explorer_tag_combo: ttk.Combobox | None = None
        self.explorer_group_combo: ttk.Combobox | None = None
        self.explorer_facet_combo: ttk.Combobox | None = None
        self.explorer_metric_combo: ttk.Combobox | None = None
        self.btn_explorer_refresh: ttk.Button | None = None
        self.btn_explorer_apply: ttk.Button | None = None
        self.btn_explorer_clear: ttk.Button | None = None
        self.progress_bar: ttk.Progressbar | None = None
        self.btn_compile: RoundedButton | None = None
        self.btn_batch: RoundedButton | None = None
        self.btn_preflight: ttk.Button | None = None
        self.btn_preview_diff: ttk.Button | None = None
        self.btn_preview_batch: ttk.Button | None = None
        self.btn_autofix: ttk.Button | None = None
        self.btn_apply_preset: ttk.Button | None = None
        self.btn_apply_expr: ttk.Button | None = None
        self.btn_expr_help: ttk.Button | None = None
        self.btn_copy_expr: ttk.Button | None = None
        self.btn_undo_expr: ttk.Button | None = None
        self.btn_apply_favorite: ttk.Button | None = None
        self.btn_use_recent: ttk.Button | None = None
        self.btn_compare_last: ttk.Button | None = None
        self.btn_select_all: ttk.Button | None = None
        self.btn_select_none: ttk.Button | None = None
        self.preset_combo: ttk.Combobox | None = None
        self.favorite_combo: ttk.Combobox | None = None
        self.recent_combo: ttk.Combobox | None = None
        self.btn_example_facets_all: ttk.Button | None = None
        self.btn_example_facets_none: ttk.Button | None = None
        self.example_facet_container: ttk.Frame | None = None
        self.group_block_bodies: dict[str, ttk.Frame] = {}
        self.group_block_headers: dict[str, tk.Button] = {}
        self.group_block_open: dict[str, bool] = {"LOGIC": True, "EXAMPLES": True}
        self.phase_buttons: dict[str, RoundedButton] = {}
        self.phase_button_labels: dict[str, str] = {}
        self._job_running = False
        self._job_queue: queue.Queue | None = None
        self._expr_undo_stack: list[set[str]] = []
        self._recent_expressions: list[str] = []
        self._last_compile_output: Path | None = None
        self._explorer_records: list[dict[str, object]] = []
        self._explorer_item_map: dict[str, dict[str, object]] = {}
        self._explorer_last_pie_records: list[dict[str, object]] = []
        self._explorer_filter_after_id: str | None = None
        self._explorer_visual_after_id: str | None = None
        self._output_token_cache: dict[str, tuple[int, int, int]] = {}

        self.group_vars: dict[str, tk.BooleanVar] = {
            group: tk.BooleanVar(value=True) for group in KNOWN_GROUPS
        }
        self._group_rule_counts: dict[str, int] = {group: 0 for group in KNOWN_GROUPS}
        self.example_facet_vars: dict[str, tk.BooleanVar] = {}
        self.example_facet_checks: dict[str, tk.Checkbutton] = {}
        self.example_facet_symbol_labels: dict[str, tk.Label] = {}
        self._example_facet_counts: dict[str, int] = {}
        self._example_facet_order: list[str] = []
        self.group_symbol_labels: dict[str, tk.Label] = {}
        self.group_text_checks: dict[str, tk.Checkbutton] = {}
        self.font_normal = tkfont.nametofont("TkDefaultFont").copy()
        self.font_italic = tkfont.nametofont("TkDefaultFont").copy()
        group_font_size = 9
        self.font_normal.configure(size=group_font_size)
        self.font_italic.configure(size=group_font_size, slant="italic")
        self.font_group_header = tkfont.nametofont("TkDefaultFont").copy()
        self.font_group_header.configure(size=group_font_size, weight="bold")
        self.font_main_header = tkfont.nametofont("TkDefaultFont").copy()
        self.font_main_header.configure(weight="bold", size=11)
        self.font_small = tkfont.nametofont("TkDefaultFont").copy()
        try:
            base_size = int(self.font_small.cget("size"))
        except Exception:
            base_size = 10
        self.font_small.configure(size=max(base_size, 9))

        self._configure_ttk_styles()
        self._build_ui()
        self.input_var.trace_add("write", lambda *_: self._refresh_stats())
        self.input_var.trace_add("write", lambda *_: self._refresh_warning_badge())
        self.input_var.trace_add("write", lambda *_: self._refresh_estimate())
        self.input_var.trace_add("write", lambda *_: self._refresh_explorer_data())
        self.output_var.trace_add("write", lambda *_: self._refresh_stats())
        self.preset_var.trace_add("write", lambda *_: self._refresh_preset_help())
        self.batch_mode_var.trace_add("write", lambda *_: self._on_batch_mode_changed())
        self._apply_preset("00 Baseline (include all groups)")
        self._refresh_preset_options_for_batch_mode()
        self._update_recent_expression_combo()
        self._refresh_stats()
        self._refresh_preset_help()
        self._refresh_phase_help()
        self._refresh_dependency_status()
        self._refresh_warning_badge()
        self._refresh_estimate()
        self._refresh_log_view()
        self._refresh_phase_button_styles()
        self._refresh_explorer_data()
        self.bind("<Control-Return>", lambda _e: self._on_apply_custom_expression())
        self.bind("<Control-KP_Enter>", lambda _e: self._on_apply_custom_expression())
        self.bind("<Control-Shift-Return>", lambda _e: self._compile_selected())
        self.bind("<Control-Shift-KP_Enter>", lambda _e: self._compile_selected())
        self._force_visible()


def main() -> None:
    app = AblationUI()
    app.mainloop()
