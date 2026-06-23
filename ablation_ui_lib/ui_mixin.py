from __future__ import annotations

from collections import Counter, defaultdict
import math
from pathlib import Path
import tkinter as tk
import re
from tkinter import filedialog, ttk, messagebox
from tkinter import font as tkfont

try:
    import tiktoken  # type: ignore
except Exception:
    tiktoken = None

from compile_DSL import KNOWN_GROUPS, required_groups_for_rule
from ablation_ui_lib.constants import (
    BASELINE_LOCK_GROUPS,
    BATCH_SCENARIO_SETS,
    BUTTON_PADX,
    BUTTON_PADY,
    DEPENDENCY_CLUSTERS,
    FAVORITE_EXPRESSIONS,
    GROUP_BLOCKS,
    GROUP_CODE,
    GROUP_SHORT,
    MAX_RECENT_EXPRESSIONS,
    MAX_INSPECTOR_LINES,
    PHASE_EXPLANATIONS,
    PRESETS,
    PRESET_OPTIONS_BY_BATCH_MODE,
    TTK_BUTTON_STYLE,
)
from ablation_ui_lib.dsl_analysis import (
    facet_for_record_values,
    ordered_semantic_example_facets,
    parse_dsl_records,
    semantic_example_facet_name,
)
from ablation_ui_lib.widgets import RoundedButton


_ENCODER = None
_TOKENIZER_LABEL = "fallback-whitespace"

SURFACE_BG = "#f3f7fb"
CARD_BG = "#ffffff"
CARD_ALT_BG = "#f8fbff"
CARD_BORDER = "#d7e3ef"
TEXT_PRIMARY = "#102033"
TEXT_SECONDARY = "#526173"
TEXT_MUTED = "#6b7b8d"
ACCENT = "#0f766e"
ACCENT_SOFT = "#dff6f3"
ACCENT_BLUE = "#2563eb"
ACCENT_BLUE_SOFT = "#e7f0ff"
DANGER = "#dc2626"
SUCCESS = "#198754"
CODE_BG = "#0f172a"
CODE_PANEL_BG = "#111c34"
CODE_FG = "#dbeafe"
CODE_ACCENT = "#7dd3fc"

SECTION_COLOR_MAP = {
    "AGENT": "#64748b",
    "ROLE": "#7c3aed",
    "LOGIC": "#0f766e",
    "EXAMPLES": "#2563eb",
    "MEMORY": "#d97706",
    "SECURITY": "#dc2626",
}

SUBPART_COLOR_MAP = {
    "Parent": "#99f6e4",
    "Step S1": "#99f6e4",
    "Step S2": "#5eead4",
    "Step S3": "#2dd4bf",
    "Step S4": "#14b8a6",
    "Step S5": "#0f766e",
    "Parent / Scaffold": "#bfdbfe",
    "Short Scaffold": "#93c5fd",
    "Full Examples": "#2563eb",
    "Eye": "#60a5fa",
    "ENT": "#38bdf8",
    "Dermatology": "#1d4ed8",
    "General": "#818cf8",
    "Post Ops": "#0ea5e9",
    "Ophthalmology": "#fbbf24",
    "ENT Memory": "#fb923c",
    "Derm": "#f59e0b",
    "Dermatology Memory": "#d97706",
    "Red Flags": "#ef4444",
    "Persona / Scope": "#fda4af",
    "Step Reminders": "#fb7185",
}


def _token_count(text: str) -> int:
    global _ENCODER, _TOKENIZER_LABEL
    if tiktoken is not None:
        try:
            if _ENCODER is None:
                _ENCODER = tiktoken.get_encoding("cl100k_base")
                _TOKENIZER_LABEL = "openai-cl100k_base"
            return len(_ENCODER.encode(text))
        except Exception:
            pass
    return len(re.findall(r"\S+", text))


class UIMixin:
    def _configure_ttk_styles(self) -> None:
        self.configure(bg=SURFACE_BG)
        style = ttk.Style(self)
        themes = style.theme_names()
        if "clam" in themes:
            style.theme_use("clam")
        elif "vista" in themes:
            style.theme_use("vista")
        base_font = tkfont.nametofont("TkDefaultFont")
        style.configure(".", background=SURFACE_BG, foreground=TEXT_PRIMARY, font=base_font)
        style.configure("TFrame", background=SURFACE_BG)
        style.configure("TLabel", background=SURFACE_BG, foreground=TEXT_PRIMARY)
        style.configure("TCheckbutton", background=SURFACE_BG, foreground=TEXT_PRIMARY)
        style.map(
            "TCheckbutton",
            background=[("active", SURFACE_BG)],
            foreground=[("disabled", TEXT_MUTED), ("active", TEXT_PRIMARY)],
        )
        style.configure(
            TTK_BUTTON_STYLE,
            padding=(BUTTON_PADX, BUTTON_PADY),
            background=CARD_BG,
            foreground=TEXT_PRIMARY,
            borderwidth=0,
            focusthickness=0,
            focuscolor="none",
            relief="flat",
        )
        style.map(
            TTK_BUTTON_STYLE,
            background=[("active", ACCENT_BLUE_SOFT), ("pressed", "#dbeafe")],
            foreground=[("disabled", TEXT_MUTED)],
        )
        header_font = self.font_main_header.copy()
        style.configure("TLabelframe.Label", font=header_font, background=SURFACE_BG, foreground=TEXT_PRIMARY)
        style.configure("MainPanel.TLabelframe.Label", font=header_font, background=SURFACE_BG, foreground=TEXT_PRIMARY)
        group_header_font = tkfont.nametofont("TkDefaultFont").copy()
        try:
            base_size = int(group_header_font.cget("size"))
        except Exception:
            base_size = 10
        group_header_font.configure(size=max(base_size - 3, 7), weight="normal")
        style.configure("GroupBlock.TLabelframe.Label", font=group_header_font, background=CARD_BG, foreground=TEXT_SECONDARY)
        tab_font = tkfont.nametofont("TkDefaultFont").copy()
        tab_font.configure(size=9, weight="normal")
        style.configure("TNotebook", background=SURFACE_BG, borderwidth=0, tabmargins=(10, 10, 10, 0))
        style.configure("Blue.TNotebook", background=SURFACE_BG, borderwidth=0, tabmargins=(10, 10, 10, 0))
        style.configure(
            "Blue.TNotebook.Tab",
            font=tab_font,
            padding=(12, 6),
            background=CARD_BG,
            foreground=TEXT_SECONDARY,
            borderwidth=0,
        )
        style.map(
            "Blue.TNotebook.Tab",
            background=[("selected", ACCENT_BLUE_SOFT), ("active", CARD_ALT_BG), ("!selected", CARD_BG)],
            foreground=[("selected", ACCENT_BLUE), ("active", TEXT_PRIMARY), ("!selected", TEXT_SECONDARY)],
        )
        style.configure(
            "Treeview",
            background=CARD_BG,
            fieldbackground=CARD_BG,
            foreground=TEXT_PRIMARY,
            borderwidth=0,
            relief="flat",
            rowheight=25,
        )
        style.map(
            "Treeview",
            background=[("selected", ACCENT_BLUE_SOFT)],
            foreground=[("selected", TEXT_PRIMARY)],
        )
        style.configure(
            "Treeview.Heading",
            background=CARD_ALT_BG,
            foreground=TEXT_PRIMARY,
            relief="flat",
            borderwidth=0,
            padding=(8, 7),
            font=header_font,
        )
        style.map(
            "Treeview.Heading",
            background=[("active", "#eef6ff")],
            foreground=[("active", TEXT_PRIMARY)],
        )
        style.configure(
            "TCombobox",
            fieldbackground=CARD_BG,
            background=CARD_BG,
            foreground=TEXT_PRIMARY,
            bordercolor=CARD_BORDER,
            lightcolor=CARD_BORDER,
            darkcolor=CARD_BORDER,
            arrowsize=14,
            padding=5,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", CARD_BG)],
            background=[("readonly", CARD_BG)],
            foreground=[("readonly", TEXT_PRIMARY)],
        )
        style.configure(
            "Horizontal.TProgressbar",
            troughcolor=CARD_ALT_BG,
            background=ACCENT,
            bordercolor=CARD_BORDER,
            lightcolor=ACCENT,
            darkcolor=ACCENT,
        )

    def _force_visible(self) -> None:
        self.update_idletasks()
        req_w = self.winfo_reqwidth()
        req_h = self.winfo_reqheight()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()

        width = min(max(req_w + 20, 1100), screen_w - 80)
        height = min(max(req_h + 20, 740), screen_h - 100)
        x = max((screen_w - width) // 2, 0)
        y = max((screen_h - height) // 2, 0)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.deiconify()
        self.lift()
        self.focus_force()
        self.attributes("-topmost", True)
        self.after(300, lambda: self.attributes("-topmost", False))

    def _main_panel(self, parent: tk.Widget, title: str, padx: int, pady: int) -> tk.LabelFrame:
        caption = tk.Label(
            parent,
            text=title,
            font=self.font_main_header,
            bg=CARD_BG,
            fg=TEXT_PRIMARY,
        )
        return tk.LabelFrame(
            parent,
            labelwidget=caption,
            padx=padx,
            pady=pady,
            bd=0,
            relief=tk.FLAT,
            bg=CARD_BG,
            highlightthickness=1,
            highlightbackground=CARD_BORDER,
            highlightcolor=CARD_BORDER,
        )

    def _dashboard_canvas(self, parent: tk.Widget, width: int, height: int) -> tk.Canvas:
        return tk.Canvas(
            parent,
            width=width,
            height=height,
            bg=CARD_BG,
            highlightthickness=1,
            highlightbackground=CARD_BORDER,
            bd=0,
            relief=tk.FLAT,
        )

    def _code_text_widget(self, parent: tk.Widget, height: int, wrap: str = "word") -> tk.Text:
        return tk.Text(
            parent,
            height=height,
            wrap=wrap,
            state="normal",
            bg=CODE_PANEL_BG,
            fg=CODE_FG,
            insertbackground=CODE_ACCENT,
            selectbackground="#164e63",
            selectforeground="#e0f2fe",
            relief=tk.FLAT,
            bd=0,
            highlightthickness=1,
            highlightbackground="#1f3b63",
            highlightcolor="#2563eb",
            font=("Consolas", 9),
        )

    @staticmethod
    def _mix_hex(base: str, target: str, ratio: float) -> str:
        base = base.lstrip("#")
        target = target.lstrip("#")
        br, bg, bb = tuple(int(base[i : i + 2], 16) for i in (0, 2, 4))
        tr, tg, tb = tuple(int(target[i : i + 2], 16) for i in (0, 2, 4))
        r = int(br + (tr - br) * ratio)
        g = int(bg + (tg - bg) * ratio)
        b = int(bb + (tb - bb) * ratio)
        return f"#{r:02x}{g:02x}{b:02x}"

    @staticmethod
    def _section_color(section: str) -> str:
        return SECTION_COLOR_MAP.get(section.upper(), "#475569")

    def _subpart_color(self, section: str, subpart: str, idx: int = 0) -> str:
        explicit = SUBPART_COLOR_MAP.get(subpart)
        if explicit:
            return explicit
        base = self._section_color(section)
        tint = 0.18 + ((idx % 4) * 0.13)
        return self._mix_hex(base, "#ffffff", min(tint, 0.62))

    def _visual_metric_name(self) -> str:
        metric = self.explorer_metric_var.get().strip()
        return metric if metric in {"Tokens", "Rules", "Chars"} else "Tokens"

    def _metric_value(self, rec: dict[str, object], metric: str | None = None) -> int:
        metric = metric or self._visual_metric_name()
        if metric == "Rules":
            return 1
        if metric == "Chars":
            return int(rec.get("chars", 0))
        return int(rec.get("tokens", 0))

    def _metric_total(self, records: list[dict[str, object]], metric: str | None = None) -> int:
        metric = metric or self._visual_metric_name()
        return sum(self._metric_value(rec, metric) for rec in records)

    def _build_ui(self) -> None:
        notebook = ttk.Notebook(self, style="Blue.TNotebook")
        notebook.pack(fill=tk.BOTH, expand=True)
        ablation_tab = ttk.Frame(notebook)
        explorer_tab = ttk.Frame(notebook)
        notebook.add(ablation_tab, text="Ablation")
        notebook.add(explorer_tab, text="Prompt Explorer")

        root = ttk.Frame(ablation_tab, padding=12)
        root.pack(fill=tk.BOTH, expand=True)
        root.columnconfigure(0, weight=2)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(2, weight=1)

        io_frame = self._main_panel(root, "Files", padx=10, pady=8)
        io_frame.grid(row=0, column=0, columnspan=2, sticky="ew")
        io_frame.columnconfigure(1, weight=1)
        io_frame.columnconfigure(4, weight=1)

        ttk.Label(io_frame, text="Input DSL").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(io_frame, textvariable=self.input_var, width=48).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Button(io_frame, text="Browse", command=self._browse_input, style=TTK_BUTTON_STYLE).grid(
            row=0, column=2, padx=(8, 0), pady=4
        )

        ttk.Label(io_frame, text="Output file").grid(row=0, column=3, sticky="w", padx=(14, 8), pady=4)
        ttk.Entry(io_frame, textvariable=self.output_var, width=48).grid(row=0, column=4, sticky="ew", pady=4)
        ttk.Button(io_frame, text="Browse", command=self._browse_output, style=TTK_BUTTON_STYLE).grid(
            row=0, column=5, padx=(8, 0), pady=4
        )

        preset_frame = self._main_panel(root, "Ablations", padx=10, pady=8)
        preset_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        preset_frame.columnconfigure(4, weight=1)

        ttk.Label(preset_frame, text="Preset").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.preset_combo = ttk.Combobox(
            preset_frame,
            textvariable=self.preset_var,
            values=list(PRESETS.keys()),
            state="readonly",
            height=min(len(PRESETS), 20),
            width=70,
        )
        self.preset_combo.grid(row=0, column=1, sticky="w")
        ttk.Label(preset_frame, textvariable=self.preset_count_var).grid(row=0, column=2, sticky="w", padx=(8, 0))

        self.btn_apply_preset = ttk.Button(
            preset_frame, text="Apply Preset", command=self._on_apply_preset, style=TTK_BUTTON_STYLE
        )
        self.btn_apply_preset.grid(row=0, column=3, padx=(8, 0), sticky="w")
        phase_buttons = ttk.Frame(preset_frame)
        phase_buttons.grid(row=0, column=4, sticky="w", padx=(10, 0))
        ttk.Label(phase_buttons, text="Batch phase quick set").grid(row=0, column=0, padx=(0, 6))
        phase_button_specs = [
            ("Phase 1", "Phase 1 (Screening 12)"),
            ("Phase 2", "Phase 2 (Confirmation 6)"),
        ]
        for idx, (label, mode) in enumerate(phase_button_specs, start=1):
            btn = RoundedButton(
                phase_buttons,
                text=label,
                command=lambda m=mode, p=label: self._set_batch_mode_from_button(m, p),
                width=98,
                height=32,
                radius=12,
                normal_bg="#f3f4f6",
                normal_fg="#2b2b2b",
                hover_bg="#e5e7eb",
                press_bg="#dbe0e7",
                border_color="#b7b7b7",
            )
            btn.grid(row=0, column=idx, padx=(0, 4))
            self.phase_buttons[mode] = btn
            self.phase_button_labels[mode] = label
        ttk.Label(
            preset_frame,
            text="Tip: choose a preset, review groups, then click Compile Selected (bottom).",
        ).grid(row=1, column=0, columnspan=5, sticky="w", pady=(8, 0))
        ttk.Label(
            preset_frame,
            textvariable=self.preset_help_var,
            foreground="#333333",
            wraplength=980,
            justify="left",
        ).grid(row=2, column=0, columnspan=5, sticky="w", pady=(6, 0))
        ttk.Label(
            preset_frame,
            textvariable=self.phase_help_var,
            foreground="#333333",
            wraplength=980,
            justify="left",
        ).grid(row=3, column=0, columnspan=5, sticky="w", pady=(4, 0))

        expr_row = ttk.Frame(preset_frame)
        expr_row.grid(row=4, column=0, columnspan=5, sticky="w", pady=(8, 0))
        ttk.Label(expr_row, text="Custom expression").grid(row=0, column=0, sticky="w", padx=(0, 8))
        tk.Entry(
            expr_row,
            textvariable=self.custom_expr_var,
            width=74,
            bg=CODE_BG,
            fg=CODE_FG,
            insertbackground=CODE_ACCENT,
            selectbackground="#164e63",
            selectforeground="#e0f2fe",
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground="#1f3b63",
            highlightcolor="#2563eb",
            font=("Consolas", 9),
        ).grid(row=0, column=1, sticky="w")
        self.btn_apply_expr = ttk.Button(
            expr_row, text="Apply Expression", command=self._on_apply_custom_expression, style=TTK_BUTTON_STYLE
        )
        self.btn_apply_expr.grid(row=0, column=2, padx=(8, 0))
        self.btn_copy_expr = ttk.Button(
            expr_row,
            text="Copy From Ticks",
            command=self._copy_expression_from_selection,
            style=TTK_BUTTON_STYLE,
        )
        self.btn_copy_expr.grid(row=0, column=3, padx=(8, 0))
        self.btn_undo_expr = ttk.Button(
            expr_row,
            text="Undo Expr",
            command=self._undo_last_expression_apply,
            style=TTK_BUTTON_STYLE,
        )
        self.btn_undo_expr.grid(row=0, column=4, padx=(6, 0))
        self.btn_expr_help = tk.Button(
            expr_row,
            text="\u24d8",
            command=self._show_custom_expression_help,
            width=2,
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            bg=self.cget("bg"),
            fg=TEXT_MUTED,
            activeforeground=TEXT_PRIMARY,
            activebackground=self.cget("bg"),
            font=("Segoe UI Symbol", 10),
        )
        self.btn_expr_help.grid(row=0, column=5, padx=(8, 0))

        expr_tools_row = ttk.Frame(preset_frame)
        expr_tools_row.grid(row=5, column=0, columnspan=5, sticky="w", pady=(6, 0))
        ttk.Label(expr_tools_row, text="Favorites").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.favorite_combo = ttk.Combobox(
            expr_tools_row,
            textvariable=self.favorite_expr_var,
            values=list(FAVORITE_EXPRESSIONS.keys()),
            state="readonly",
            width=38,
        )
        self.favorite_combo.grid(row=0, column=1, sticky="w")
        self.btn_apply_favorite = ttk.Button(
            expr_tools_row,
            text="Apply Favorite",
            command=self._apply_favorite_expression,
            style=TTK_BUTTON_STYLE,
        )
        self.btn_apply_favorite.grid(row=0, column=2, padx=(8, 0))

        ttk.Label(expr_tools_row, text="Recent").grid(row=0, column=3, sticky="w", padx=(14, 8))
        self.recent_combo = ttk.Combobox(
            expr_tools_row,
            textvariable=self.recent_expr_var,
            values=[],
            state="readonly",
            width=46,
        )
        self.recent_combo.grid(row=0, column=4, sticky="w")
        self.btn_use_recent = ttk.Button(
            expr_tools_row,
            text="Use Recent",
            command=self._use_recent_expression,
            style=TTK_BUTTON_STYLE,
        )
        self.btn_use_recent.grid(row=0, column=5, padx=(8, 0))

        left = self._main_panel(root, "Groups", padx=10, pady=8)
        left.grid(row=2, column=0, sticky="nsew", pady=(10, 0), padx=(0, 8))
        left.columnconfigure(0, weight=1)
        left.columnconfigure(1, weight=0)
        left.rowconfigure(1, weight=1)

        ttk.Label(
            left,
            text="Toggle compile switches here. LOGIC and EXAMPLES can be expanded; EXAMPLES also contains single-compile example filters.",
        ).grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )
        group_tools = ttk.Frame(left)
        group_tools.grid(row=0, column=1, sticky="e", pady=(0, 8), padx=(8, 0))
        self.btn_select_all = ttk.Button(group_tools, text="Select All", command=self._select_all, style=TTK_BUTTON_STYLE)
        self.btn_select_all.grid(row=0, column=0, padx=(0, 6))
        self.btn_select_none = ttk.Button(
            group_tools, text="Deselect All", command=self._select_none, style=TTK_BUTTON_STYLE
        )
        self.btn_select_none.grid(row=0, column=1)

        group_container = ttk.Frame(left)
        group_container.grid(row=1, column=0, columnspan=2, sticky="nw")
        group_container.columnconfigure(0, weight=1)

        def _add_group_row(parent: ttk.Widget, row: int, group: str) -> None:
            row_frame = tk.Frame(parent, bg=CARD_BG)
            row_frame.grid(row=row, column=0, sticky="w", pady=0)

            symbol = tk.Label(row_frame, text="\u2713", fg=SUCCESS, width=2, anchor="w", bg=CARD_BG)
            symbol.grid(row=0, column=0, sticky="w", padx=(0, 4))
            symbol.bind("<Button-1>", lambda _e, g=group: self._toggle_group_from_icon(g))
            symbol.config(cursor="hand2")

            chk = tk.Checkbutton(
                row_frame,
                text=self._group_checkbox_text(group),
                variable=self.group_vars[group],
                command=lambda g=group: self._on_group_toggle(g),
                indicatoron=False,
                relief=tk.FLAT,
                overrelief=tk.FLAT,
                bd=0,
                highlightthickness=0,
                anchor="w",
                justify="left",
                padx=0,
                pady=0,
                font=self.font_normal,
                fg=TEXT_PRIMARY,
                activeforeground=TEXT_PRIMARY,
                bg=CARD_BG,
                activebackground=CARD_BG,
                selectcolor=CARD_BG,
            )
            chk.grid(row=0, column=1, sticky="w")

            self.group_symbol_labels[group] = symbol
            self.group_text_checks[group] = chk

        assigned_groups: set[str] = set()
        block_row = 0
        for block_name, block_groups in GROUP_BLOCKS:
            visible = [g for g in block_groups if g in self.group_vars]
            if not visible:
                continue
            assigned_groups.update(visible)
            block_frame = tk.Frame(
                group_container,
                bd=0,
                relief=tk.FLAT,
                padx=6,
                pady=4,
                bg=CARD_BG,
                highlightthickness=1,
                highlightbackground=CARD_BORDER,
            )
            block_frame.grid(row=block_row, column=0, sticky="ew", pady=(0, 3))
            block_frame.columnconfigure(0, weight=1)
            if block_name in self.group_block_open:
                header = tk.Button(
                    block_frame,
                    text=self._group_block_header_text(block_name, len(visible)),
                    command=lambda name=block_name: self._toggle_group_block(name),
                    relief=tk.FLAT,
                    bd=0,
                    highlightthickness=0,
                    anchor="w",
                    justify="left",
                    padx=0,
                    pady=0,
                    cursor="hand2",
                    font=self.font_group_header,
                    bg=CARD_BG,
                    fg=TEXT_SECONDARY,
                    activebackground=CARD_BG,
                    activeforeground=TEXT_PRIMARY,
                )
                header.grid(row=0, column=0, sticky="w", pady=(0, 2))
                self.group_block_headers[block_name] = header
            else:
                tk.Label(
                    block_frame,
                    text=f"{block_name} ({len(visible)})",
                    font=self.font_group_header,
                    anchor="w",
                    justify="left",
                    bg=CARD_BG,
                    fg=TEXT_SECONDARY,
                ).grid(row=0, column=0, sticky="w", pady=(0, 2))
            block_body = ttk.Frame(block_frame)
            block_body.grid(row=1, column=0, sticky="ew")
            block_body.columnconfigure(0, weight=1)
            for row, group in enumerate(visible):
                _add_group_row(block_body, row, group)
            if block_name == "EXAMPLES":
                facet_header_row = len(visible)
                facet_header = ttk.Frame(block_body)
                facet_header.grid(row=facet_header_row, column=0, sticky="ew", pady=(8, 0))
                facet_header.columnconfigure(0, weight=1)
                ttk.Label(
                    facet_header,
                    text="Example filters (single compile only)",
                    foreground=TEXT_SECONDARY,
                    justify="left",
                ).grid(row=0, column=0, sticky="w")
                facet_tools = ttk.Frame(facet_header)
                facet_tools.grid(row=0, column=1, sticky="e", padx=(8, 0))
                self.btn_example_facets_all = ttk.Button(
                    facet_tools,
                    text="All",
                    command=self._select_all_example_facets,
                    style=TTK_BUTTON_STYLE,
                )
                self.btn_example_facets_all.grid(row=0, column=0, padx=(0, 6))
                self.btn_example_facets_none = ttk.Button(
                    facet_tools,
                    text="None",
                    command=self._select_none_example_facets,
                    style=TTK_BUTTON_STYLE,
                )
                self.btn_example_facets_none.grid(row=0, column=1)
                ttk.Label(
                    block_body,
                    textvariable=self.example_facet_info_var,
                    foreground=TEXT_SECONDARY,
                    justify="left",
                ).grid(row=facet_header_row + 1, column=0, sticky="w", pady=(4, 4))
                self.example_facet_container = ttk.Frame(block_body)
                self.example_facet_container.grid(row=facet_header_row + 2, column=0, sticky="w")
            self.group_block_bodies[block_name] = block_body
            if not self.group_block_open.get(block_name, True):
                block_body.grid_remove()
            block_row += 1

        remaining = [group for group in KNOWN_GROUPS if group not in assigned_groups]
        if remaining:
            block_frame = tk.Frame(
                group_container,
                bd=0,
                relief=tk.FLAT,
                padx=6,
                pady=4,
                bg=CARD_BG,
                highlightthickness=1,
                highlightbackground=CARD_BORDER,
            )
            block_frame.grid(row=block_row, column=0, sticky="ew", pady=(0, 3))
            block_frame.columnconfigure(0, weight=1)
            tk.Label(
                block_frame,
                text=f"Other ({len(remaining)})",
                font=self.font_group_header,
                anchor="w",
                justify="left",
                bg=CARD_BG,
                fg=TEXT_SECONDARY,
            ).grid(row=0, column=0, sticky="w", pady=(0, 2))
            block_body = ttk.Frame(block_frame)
            block_body.grid(row=1, column=0, sticky="ew")
            block_body.columnconfigure(0, weight=1)
            for row, group in enumerate(remaining):
                _add_group_row(block_body, row, group)

        right = ttk.Frame(root)
        right.grid(row=2, column=1, sticky="nsew", pady=(10, 0))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        glossary_frame = self._main_panel(right, "DSL Glossary", padx=8, pady=6)
        glossary_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        glossary_frame.columnconfigure(0, weight=1)
        glossary_text = tk.Text(
            glossary_frame,
            height=24,
            wrap="word",
            state="normal",
            font=self.font_small,
            bg=CARD_ALT_BG,
            fg=TEXT_PRIMARY,
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            padx=4,
            pady=4,
        )
        glossary_text.grid(row=0, column=0, sticky="nsew")
        glossary_text.insert("1.0", self._build_glossary_text())
        glossary_text.config(state="disabled")

        action_frame = self._main_panel(right, "Actions", padx=10, pady=8)
        action_frame.grid(row=1, column=0, sticky="nsew")

        self.btn_compile = RoundedButton(
            action_frame,
            text="Compile Selected (write one file)",
            command=self._compile_selected,
            width=245,
            height=36,
            radius=14,
            normal_bg="#2e7d32",
            normal_fg="white",
            hover_bg="#12695d",
            press_bg="#0f5a50",
            border_color="#0f5a50",
        )
        self.btn_compile.grid(row=0, column=0, padx=(0, 8), pady=2, sticky="w")
        self.btn_batch = RoundedButton(
            action_frame,
            text="Run Phase Batch",
            command=self._run_starter_batch,
            width=230,
            height=36,
            radius=14,
            normal_bg=CARD_BG,
            normal_fg=TEXT_PRIMARY,
            hover_bg=ACCENT_BLUE_SOFT,
            press_bg="#dbeafe",
            border_color=CARD_BORDER,
        )
        self.btn_batch.grid(row=0, column=1, padx=(0, 8), pady=2, sticky="w")
        self.btn_preview_batch = ttk.Button(
            action_frame, text="Preview Batch Plan", command=self._preview_batch_plan, style=TTK_BUTTON_STYLE
        )
        self.btn_preview_batch.grid(row=0, column=2, padx=(0, 8), pady=2, sticky="w")
        tk.Label(
            action_frame,
            textvariable=self.warning_badge_var,
            fg=DANGER,
            font=self.font_small,
            anchor="w",
            justify="left",
        ).grid(row=0, column=3, sticky="w")
        ttk.Label(action_frame, textvariable=self.estimate_var).grid(row=0, column=4, sticky="w", padx=(10, 0))
        ttk.Label(
            action_frame,
            text="Single compile uses current ticks/preset/expression plus example facet filters. Batch ignores current ticks and facet filters, then writes baseline + selected phase scenarios.",
            foreground=TEXT_SECONDARY,
            wraplength=620,
            justify="left",
        ).grid(row=1, column=0, columnspan=5, sticky="w", pady=(4, 0))
        simple_row = ttk.Frame(action_frame)
        simple_row.grid(row=2, column=0, columnspan=5, sticky="w", pady=(4, 0))
        ttk.Checkbutton(simple_row, text="Auto artifact folders", variable=self.use_artifacts_var).grid(
            row=0, column=0, padx=(0, 8)
        )
        ttk.Checkbutton(
            simple_row,
            text="Auto-fix dependencies on compile",
            variable=self.auto_fix_on_compile_var,
        ).grid(row=0, column=1, padx=(0, 8))
        ttk.Checkbutton(
            simple_row,
            text="Strict dependency lint (block compile)",
            variable=self.strict_dep_lint_var,
        ).grid(row=0, column=2, padx=(0, 8))
        ttk.Checkbutton(
            simple_row,
            text="Show advanced controls",
            variable=self.show_advanced_var,
            command=self._toggle_advanced_controls,
        ).grid(row=0, column=3, padx=(0, 8))
        ttk.Checkbutton(
            simple_row,
            text="Lock baseline groups",
            variable=self.lock_baseline_var,
            command=self._on_lock_baseline_toggle,
        ).grid(row=0, column=4, padx=(0, 8))

        ttk.Label(
            action_frame,
            text="Compile runs preflight automatically. Dependency mismatches can be auto-fixed with warnings.",
        ).grid(row=3, column=0, columnspan=5, sticky="w", pady=(4, 0))

        self.advanced_tools_row = ttk.Frame(action_frame)
        self.advanced_tools_row.grid(row=4, column=0, columnspan=5, sticky="w", pady=(6, 0))
        self.btn_preflight = ttk.Button(
            self.advanced_tools_row, text="Run Preflight", command=self._run_preflight_report, style=TTK_BUTTON_STYLE
        )
        self.btn_preflight.grid(row=0, column=0, padx=(0, 6))
        self.btn_preview_diff = ttk.Button(
            self.advanced_tools_row, text="Preview Diff", command=self._preview_diff_report, style=TTK_BUTTON_STYLE
        )
        self.btn_preview_diff.grid(row=0, column=1, padx=(0, 6))
        self.btn_compare_last = ttk.Button(
            self.advanced_tools_row,
            text="Compare Last Run",
            command=self._compare_against_last_run,
            style=TTK_BUTTON_STYLE,
        )
        self.btn_compare_last.grid(row=0, column=2, padx=(0, 6))
        self.btn_autofix = ttk.Button(
            self.advanced_tools_row,
            text="Auto-fix Dependencies",
            command=self._apply_dependency_autofix,
            style=TTK_BUTTON_STYLE,
        )
        self.btn_autofix.grid(row=0, column=3, padx=(0, 6))
        ttk.Checkbutton(self.advanced_tools_row, text="Show diff before write", variable=self.show_diff_var).grid(
            row=0, column=4, padx=(0, 6)
        )

        self.progress_bar = ttk.Progressbar(action_frame, mode="indeterminate", length=220)
        self.progress_bar.grid(row=5, column=0, columnspan=3, sticky="w", pady=(6, 0))
        self.progress_bar.grid_remove()
        ttk.Label(action_frame, textvariable=self.status_var).grid(row=6, column=0, columnspan=5, sticky="w", pady=(8, 0))

        stats_frame = self._main_panel(action_frame, "File Stats", padx=8, pady=6)
        stats_frame.grid(row=7, column=0, columnspan=5, sticky="ew", pady=(8, 0))
        stats_frame.columnconfigure(0, weight=1)
        ttk.Label(stats_frame, textvariable=self.stats_var, justify="left").grid(row=0, column=0, sticky="w")
        ttk.Button(stats_frame, text="Refresh", command=self._refresh_stats, style=TTK_BUTTON_STYLE).grid(
            row=0, column=1, padx=(8, 0), sticky="e"
        )

        inspect_frame = self._main_panel(action_frame, "Inspector", padx=8, pady=6)
        inspect_frame.grid(row=8, column=0, columnspan=5, sticky="nsew", pady=(8, 0))
        inspect_frame.columnconfigure(0, weight=1)
        inspect_frame.rowconfigure(0, weight=1)
        action_frame.rowconfigure(8, weight=1)
        inspect_scroll = ttk.Scrollbar(inspect_frame, orient="vertical")
        inspect_scroll.grid(row=0, column=1, sticky="ns")
        self.inspector_widget = self._code_text_widget(inspect_frame, height=8)
        self.inspector_widget.configure(yscrollcommand=inspect_scroll.set)
        self.inspector_widget.grid(row=0, column=0, sticky="nsew")
        inspect_scroll.config(command=self.inspector_widget.yview)

        log_frame = self._main_panel(action_frame, "Run Log (persistent)", padx=8, pady=6)
        log_frame.grid(row=9, column=0, columnspan=5, sticky="nsew", pady=(8, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        action_frame.rowconfigure(9, weight=1)

        log_scroll = ttk.Scrollbar(log_frame, orient="vertical")
        log_scroll.grid(row=0, column=1, sticky="ns")
        self.log_widget = self._code_text_widget(log_frame, height=8)
        self.log_widget.configure(yscrollcommand=log_scroll.set)
        self.log_widget.grid(row=0, column=0, sticky="nsew")
        log_scroll.config(command=self.log_widget.yview)

        log_btns = ttk.Frame(log_frame)
        log_btns.grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Button(log_btns, text="Refresh Log", command=self._refresh_log_view, style=TTK_BUTTON_STYLE).grid(
            row=0, column=0, padx=(0, 6)
        )
        ttk.Button(log_btns, text="Export CSV", command=self._export_log_csv, style=TTK_BUTTON_STYLE).grid(
            row=0, column=1, padx=(0, 6)
        )
        ttk.Button(log_btns, text="Export JSON", command=self._export_log_json, style=TTK_BUTTON_STYLE).grid(
            row=0, column=2
        )
        self._build_explorer_tab(explorer_tab)
        self._toggle_advanced_controls()
        self._refresh_all_group_visuals()

    @staticmethod
    def _group_label(group: str) -> str:
        return f"{GROUP_CODE.get(group, '??')} {group} ({GROUP_SHORT.get(group, 'no short note')})"

    def _group_block_header_text(self, block_name: str, item_count: int) -> str:
        arrow = "v" if self.group_block_open.get(block_name, True) else ">"
        return f"{arrow} {block_name} ({item_count})"

    @staticmethod
    def _group_rule_counts_from_records(records: list[dict[str, object]]) -> dict[str, int]:
        counts = {group: 0 for group in KNOWN_GROUPS}
        for rec in records:
            rule_id = str(rec.get("id", ""))
            group = str(rec.get("group", ""))
            for required in required_groups_for_rule(rule_id, group):
                if required in counts:
                    counts[required] += 1
        return counts

    def _group_checkbox_text(self, group: str) -> str:
        count = int(getattr(self, "_group_rule_counts", {}).get(group, 0))
        suffix = "[0 tagged rules]" if count == 0 else f"[{count} rule{'s' if count != 1 else ''}]"
        return f"{self._group_label(group)} {suffix}"

    def _toggle_group_block(self, block_name: str) -> None:
        if block_name not in self.group_block_open:
            return
        self.group_block_open[block_name] = not self.group_block_open[block_name]
        body = self.group_block_bodies.get(block_name)
        if body is not None:
            if self.group_block_open[block_name]:
                body.grid()
            else:
                body.grid_remove()
        header = self.group_block_headers.get(block_name)
        if header is not None:
            item_count = 0
            for group_name, groups in GROUP_BLOCKS:
                if group_name == block_name:
                    item_count = len([g for g in groups if g in self.group_vars])
                    break
            header.config(text=self._group_block_header_text(block_name, item_count))

    def _example_facet_checkbox_text(self, facet: str, is_on: bool | None = None) -> str:
        count = int(getattr(self, "_example_facet_counts", {}).get(facet, 0))
        suffix = "[0 rules]" if count == 0 else f"[{count} rule{'s' if count != 1 else ''}]"
        if is_on is None:
            is_on = bool(self.example_facet_vars.get(facet).get()) if facet in self.example_facet_vars else True
        state = "[ON]" if is_on else "[OFF]"
        return f"{facet} {suffix} {state}"

    def _excluded_groups(self, selected: set[str] | None = None) -> list[str]:
        current = self._selected_groups() if selected is None else selected
        return [group for group in KNOWN_GROUPS if group not in current]

    def _excluded_example_facets(self) -> list[str]:
        current = {facet for facet, var in self.example_facet_vars.items() if var.get()}
        return [facet for facet in self._example_facet_order if facet not in current]

    def _selection_has_only_empty_exclusions(self, selected: set[str] | None = None) -> bool:
        counts = getattr(self, "_group_rule_counts", {})
        if not counts or sum(int(v) for v in counts.values()) == 0:
            return False
        excluded = self._excluded_groups(selected)
        return bool(excluded) and all(int(counts.get(group, 0)) == 0 for group in excluded)

    def _selection_has_only_empty_example_facet_exclusions(self) -> bool:
        counts = getattr(self, "_example_facet_counts", {})
        excluded = self._excluded_example_facets()
        return bool(excluded) and all(int(counts.get(facet, 0)) == 0 for facet in excluded)

    def _selection_has_no_effect(self, selected: set[str] | None = None) -> bool:
        excluded_groups = self._excluded_groups(selected)
        excluded_facets = self._excluded_example_facets()
        if not excluded_groups and not excluded_facets:
            return False
        groups_have_effect = bool(excluded_groups) and not self._selection_has_only_empty_exclusions(selected)
        facets_have_effect = bool(excluded_facets) and not self._selection_has_only_empty_example_facet_exclusions()
        return not groups_have_effect and not facets_have_effect

    def _refresh_example_facet_info(self) -> None:
        selected_count = len(self._example_facet_order) - len(self._excluded_example_facets())
        self.example_facet_info_var.set(
            f"Semantic example facets: {len(self._example_facet_order)} available, {selected_count} ON, {len(self._excluded_example_facets())} OFF."
        )

    def _refresh_example_facet_visual(self, facet: str) -> None:
        chk = self.example_facet_checks.get(facet)
        symbol = self.example_facet_symbol_labels.get(facet)
        var = self.example_facet_vars.get(facet)
        if chk is None or symbol is None or var is None:
            return
        is_on = bool(var.get())
        chk.config(text=self._example_facet_checkbox_text(facet, is_on))
        if is_on:
            symbol.config(text="\u2713", fg=SUCCESS)
            chk.config(font=self.font_normal, fg=TEXT_PRIMARY, activeforeground=TEXT_PRIMARY)
        else:
            symbol.config(text="\u2717", fg=DANGER)
            chk.config(font=self.font_italic, fg=TEXT_MUTED, activeforeground=TEXT_MUTED)

    def _refresh_all_example_facet_visuals(self) -> None:
        for facet in self._example_facet_order:
            self._refresh_example_facet_visual(facet)
        self._refresh_example_facet_info()

    def _refresh_example_facet_controls(self) -> None:
        if self.example_facet_container is None:
            return

        ordered_facets, counts = ordered_semantic_example_facets(self._explorer_records)
        previous_selection = {facet for facet, var in self.example_facet_vars.items() if var.get()}
        old_facets = set(self.example_facet_vars)
        self._example_facet_order = ordered_facets
        self._example_facet_counts = counts

        for child in self.example_facet_container.winfo_children():
            child.destroy()
        self.example_facet_checks = {}
        self.example_facet_symbol_labels = {}

        if not ordered_facets:
            self.example_facet_vars = {}
            ttk.Label(
                self.example_facet_container,
                text="No semantic example facets found in the current source.",
                foreground=TEXT_MUTED,
            ).grid(row=0, column=0, sticky="w")
            self.example_facet_info_var.set("Example facets: none detected in current source.")
            return

        new_vars: dict[str, tk.BooleanVar] = {}
        keep_on = previous_selection | (set(ordered_facets) - old_facets) if old_facets else set(ordered_facets)
        for row, facet in enumerate(ordered_facets):
            var = tk.BooleanVar(value=facet in keep_on)
            row_frame = tk.Frame(self.example_facet_container, bg=CARD_BG)
            row_frame.grid(row=row, column=0, sticky="w", pady=0)
            symbol = tk.Label(row_frame, text="\u2713", fg=SUCCESS, width=2, anchor="w", bg=CARD_BG)
            symbol.grid(row=0, column=0, sticky="w", padx=(0, 4))
            symbol.bind("<Button-1>", lambda _e, f=facet: self._toggle_example_facet_from_icon(f))
            symbol.config(cursor="hand2")
            chk = tk.Checkbutton(
                row_frame,
                text=self._example_facet_checkbox_text(facet, bool(var.get())),
                variable=var,
                command=lambda f=facet: self._on_example_facet_toggle(f),
                indicatoron=False,
                relief=tk.FLAT,
                overrelief=tk.FLAT,
                bd=0,
                highlightthickness=0,
                anchor="w",
                justify="left",
                padx=0,
                pady=0,
                font=self.font_normal,
                fg=TEXT_PRIMARY,
                activeforeground=TEXT_PRIMARY,
                bg=CARD_BG,
                activebackground=CARD_BG,
                selectcolor=CARD_BG,
            )
            chk.grid(row=0, column=1, sticky="w", pady=0)
            new_vars[facet] = var
            self.example_facet_checks[facet] = chk
            self.example_facet_symbol_labels[facet] = symbol
        self.example_facet_vars = new_vars

        self._refresh_all_example_facet_visuals()
        self._update_group_interactivity()

    @staticmethod
    def _logic_step_idx_from_record(rec: dict[str, object]) -> int:
        sub = str(rec.get("subsection", "")).lower()
        for idx in (1, 2, 3, 4, 5):
            if f"step {idx}" in sub:
                return idx
        grp = str(rec.get("group", ""))
        for idx in (1, 2, 3, 4, 5):
            if grp == f"LOGIC_S{idx}":
                return idx
        try:
            rule_id = str(rec.get("id", ""))
            if rule_id.startswith("LOG-"):
                number = int(rule_id.split("-", 1)[1])
                if 200 <= number <= 299:
                    return 1
                if 300 <= number <= 399:
                    return 2
                if 400 <= number <= 599:
                    return 3
                if 600 <= number <= 799:
                    return 4
                if 800 <= number <= 899:
                    return 5
        except Exception:
            pass
        return 0

    @staticmethod
    def _facet_for_record(rec: dict[str, object]) -> str:
        return facet_for_record_values(
            section=str(rec.get("section", "")),
            group=str(rec.get("group", "")),
            subsection=str(rec.get("subsection", "")),
            rule_id=str(rec.get("id", "")),
        )

    @staticmethod
    def _build_glossary_text() -> str:
        structure = (
            "AGENT -> ROLE (Medical Approach, Emotional Intelligence) -> LOGIC (parent + Steps S1-S5) -> "
            "EXAMPLES (parent + Full/Short + optional child groups) -> MEMORY (parent + Eye/ENT/Derm/Red child groups) -> "
            "SECURITY (Persona + Step Reminders)"
        )
        tag_rows = [
            "META=metadata  SCOPE=domain  STEP=sequence  LIMIT=constraints  STYLE=language/tone",
            "TOOL=tool use  DATA=required inputs  CHECK=validation  TERM=definitions  RED=safety urgency",
            "LIST=enumerations  DO=must do  DONT=must not do  EX=examples  NOTE=implementation note",
        ]
        group_sections = [
            ("Core", ["CORE", "SCOPE", "TOOLS", "OUTPUT", "STYLE", "CHECKS", "LISTS", "RED"]),
            ("Logic", ["LOGIC", "LOGIC_S1", "LOGIC_S2", "LOGIC_S3", "LOGIC_S4", "LOGIC_S5"]),
            ("Examples", ["EXAMPLES", "EX_FULL", "EX_SHORT", "EX_EYE", "EX_ENT", "EX_DERM", "EX_CHILD", "EX_VET"]),
            ("Memory", ["MEMORY", "MEM_EYE", "MEM_ENT", "MEM_DERM", "MEM_CHILD", "MEM_VET", "MEM_RED"]),
            ("Security", ["SECURITY"]),
        ]
        group_lines: list[str] = []
        for section_name, section_groups in group_sections:
            visible = [group for group in section_groups if group in KNOWN_GROUPS]
            if not visible:
                continue
            inline_items = [f"{GROUP_CODE.get(group, '??')} {group}" for group in visible]
            group_lines.append(f"{section_name}: " + ", ".join(inline_items))
        groups = "\n".join(group_lines)
        return (
            "Prompt Structure (v13)\n"
            f"{structure}\n\n"
            "TAG quick glossary\n"
            + "\n".join(tag_rows)
            + f"\n\nGROUP order (01..{len(KNOWN_GROUPS):02d}) by section\n"
            + groups
            + "\n\nGROUPs are compile switches. Content facets (Eye, ENT, Dermatology, General, Post Ops, etc.) are derived from headings."
            + "\n\nUse group ticks to include/exclude DSL blocks. Example semantic filters live inside the EXAMPLES block and affect single compile only. Batch uses phase scenarios only."
        )

    def _build_explorer_tab(self, parent: ttk.Frame) -> None:
        container = ttk.Frame(parent, padding=12)
        container.pack(fill=tk.BOTH, expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(2, weight=1)

        top = self._main_panel(container, "Explorer Controls", padx=8, pady=8)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)
        ttk.Label(top, text="Source file").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Label(top, textvariable=self.input_var).grid(row=0, column=1, sticky="w")
        self.btn_explorer_refresh = ttk.Button(
            top,
            text="Refresh Explorer",
            command=self._refresh_explorer_data,
            style=TTK_BUTTON_STYLE,
        )
        self.btn_explorer_refresh.grid(row=0, column=2, padx=(8, 0), sticky="e")
        ttk.Label(top, text="Visual metric").grid(row=0, column=3, sticky="e", padx=(18, 6))
        self.explorer_metric_combo = ttk.Combobox(
            top,
            textvariable=self.explorer_metric_var,
            values=["Tokens", "Rules", "Chars"],
            state="readonly",
            width=10,
        )
        self.explorer_metric_combo.grid(row=0, column=4, sticky="e")
        self.explorer_metric_combo.bind("<<ComboboxSelected>>", lambda _e: self._schedule_apply_explorer_filters(0))
        ttk.Label(top, textvariable=self.explorer_stats_var).grid(row=1, column=0, columnspan=5, sticky="w", pady=(6, 0))
        ttk.Label(top, textvariable=self.explorer_section_totals_var).grid(row=2, column=0, columnspan=5, sticky="w", pady=(2, 0))
        ttk.Label(
            top,
            textvariable=self.explorer_visual_summary_var,
            foreground=TEXT_SECONDARY,
            wraplength=1120,
            justify="left",
        ).grid(row=3, column=0, columnspan=5, sticky="w", pady=(4, 0))

        filters = self._main_panel(container, "Filters", padx=8, pady=8)
        filters.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(filters, text="Section").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.explorer_section_combo = ttk.Combobox(
            filters,
            textvariable=self.explorer_filter_section_var,
            values=["All sections"],
            state="readonly",
            width=20,
        )
        self.explorer_section_combo.grid(row=0, column=1, sticky="w")
        self.explorer_section_combo.bind("<<ComboboxSelected>>", lambda _e: self._schedule_apply_explorer_filters(0))
        ttk.Label(filters, text="TAG").grid(row=0, column=2, sticky="w", padx=(12, 6))
        self.explorer_tag_combo = ttk.Combobox(
            filters,
            textvariable=self.explorer_filter_tag_var,
            values=["All tags"],
            state="readonly",
            width=16,
        )
        self.explorer_tag_combo.grid(row=0, column=3, sticky="w")
        self.explorer_tag_combo.bind("<<ComboboxSelected>>", lambda _e: self._schedule_apply_explorer_filters(0))
        ttk.Label(filters, text="GROUP").grid(row=0, column=4, sticky="w", padx=(12, 6))
        self.explorer_group_combo = ttk.Combobox(
            filters,
            textvariable=self.explorer_filter_group_var,
            values=["All groups"],
            state="readonly",
            width=18,
        )
        self.explorer_group_combo.grid(row=0, column=5, sticky="w")
        self.explorer_group_combo.bind("<<ComboboxSelected>>", lambda _e: self._schedule_apply_explorer_filters(0))
        ttk.Label(filters, text="Facet").grid(row=0, column=6, sticky="w", padx=(12, 6))
        self.explorer_facet_combo = ttk.Combobox(
            filters,
            textvariable=self.explorer_filter_facet_var,
            values=["All facets"],
            state="readonly",
            width=22,
        )
        self.explorer_facet_combo.grid(row=0, column=7, sticky="w")
        self.explorer_facet_combo.bind("<<ComboboxSelected>>", lambda _e: self._schedule_apply_explorer_filters(0))
        ttk.Label(filters, text="Search").grid(row=0, column=8, sticky="w", padx=(12, 6))
        search_entry = ttk.Entry(filters, textvariable=self.explorer_search_var, width=30)
        search_entry.grid(row=0, column=9, sticky="w")
        search_entry.bind("<KeyRelease>", lambda _e: self._schedule_apply_explorer_filters())
        self.btn_explorer_apply = ttk.Button(
            filters,
            text="Apply",
            command=self._apply_explorer_filters,
            style=TTK_BUTTON_STYLE,
        )
        self.btn_explorer_apply.grid(row=0, column=10, sticky="w", padx=(8, 0))
        self.btn_explorer_clear = ttk.Button(
            filters,
            text="Clear",
            command=self._clear_explorer_filters,
            style=TTK_BUTTON_STYLE,
        )
        self.btn_explorer_clear.grid(row=0, column=11, sticky="w", padx=(6, 0))
        ttk.Checkbutton(
            filters,
            text="Mirror filters in Structure Tree",
            variable=self.explorer_tree_mirror_var,
            command=lambda: self._schedule_apply_explorer_filters(0),
        ).grid(row=1, column=10, columnspan=2, sticky="e", pady=(6, 0))
        ttk.Label(filters, textvariable=self.explorer_filter_info_var).grid(row=1, column=0, columnspan=10, sticky="w", pady=(6, 0))

        split = tk.PanedWindow(
            container,
            orient=tk.VERTICAL,
            sashwidth=8,
            sashrelief=tk.FLAT,
            showhandle=True,
            opaqueresize=True,
            bg=SURFACE_BG,
            bd=0,
        )
        split.grid(row=2, column=0, sticky="nsew", pady=(8, 0))

        visuals = self._main_panel(split, "Visuals", padx=8, pady=8)
        visuals.columnconfigure(0, weight=1)
        visuals.rowconfigure(0, weight=1)
        visuals_nb = ttk.Notebook(visuals, style="Blue.TNotebook")
        visuals_nb.grid(row=0, column=0, sticky="nsew")

        pies_tab = ttk.Frame(visuals_nb, padding=4)
        pies_tab.columnconfigure(0, weight=1)
        pies_tab.columnconfigure(1, weight=1)
        pies_tab.rowconfigure(0, weight=1)
        left_pie = ttk.Frame(pies_tab)
        left_pie.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left_pie.columnconfigure(0, weight=1)
        left_pie.rowconfigure(1, weight=1)
        right_pie = ttk.Frame(pies_tab)
        right_pie.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        right_pie.columnconfigure(0, weight=1)
        right_pie.rowconfigure(1, weight=1)
        ttk.Label(left_pie, text="Section share").grid(row=0, column=0, sticky="w")
        self.explorer_section_pie_canvas = self._dashboard_canvas(left_pie, 320, 190)
        self.explorer_section_pie_canvas.grid(row=1, column=0, sticky="nsew")
        self.explorer_section_pie_canvas.bind("<Configure>", self._on_explorer_pie_canvas_resize)
        ttk.Label(right_pie, textvariable=self.explorer_subpart_title_var).grid(row=0, column=0, sticky="w")
        self.explorer_subpart_pie_canvas = self._dashboard_canvas(right_pie, 320, 190)
        self.explorer_subpart_pie_canvas.grid(row=1, column=0, sticky="nsew")
        self.explorer_subpart_pie_canvas.bind("<Configure>", self._on_explorer_pie_canvas_resize)

        heatmap_tab = ttk.Frame(visuals_nb, padding=4)
        heatmap_tab.columnconfigure(0, weight=1)
        heatmap_tab.rowconfigure(1, weight=1)
        ttk.Label(heatmap_tab, text="TAG x GROUP heatmap (top rows/cols + Other, current metric)").grid(row=0, column=0, sticky="w")
        self.explorer_heatmap_canvas = self._dashboard_canvas(heatmap_tab, 640, 190)
        self.explorer_heatmap_canvas.grid(row=1, column=0, sticky="nsew")
        self.explorer_heatmap_canvas.bind("<Configure>", self._on_explorer_pie_canvas_resize)

        treemap_tab = ttk.Frame(visuals_nb, padding=4)
        treemap_tab.columnconfigure(0, weight=1)
        treemap_tab.rowconfigure(1, weight=1)
        ttk.Label(treemap_tab, text="Section -> Subpart breakdown (stacked bars, current metric)").grid(row=0, column=0, sticky="w")
        self.explorer_treemap_canvas = self._dashboard_canvas(treemap_tab, 640, 190)
        self.explorer_treemap_canvas.grid(row=1, column=0, sticky="nsew")
        self.explorer_treemap_canvas.bind("<Configure>", self._on_explorer_pie_canvas_resize)

        cov_delta_tab = ttk.Frame(visuals_nb, padding=4)
        cov_delta_tab.columnconfigure(0, weight=1)
        cov_delta_tab.columnconfigure(1, weight=1)
        cov_delta_tab.rowconfigure(1, weight=1)
        ttk.Label(
            cov_delta_tab,
            text="Section coverage (included vs excluded, current metric)",
        ).grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Label(
            cov_delta_tab,
            text="Baseline vs active totals (rules/chars/tokens)",
        ).grid(row=0, column=1, sticky="w")
        self.explorer_coverage_canvas = self._dashboard_canvas(cov_delta_tab, 320, 190)
        self.explorer_coverage_canvas.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        self.explorer_coverage_canvas.bind("<Configure>", self._on_explorer_pie_canvas_resize)
        self.explorer_delta_canvas = self._dashboard_canvas(cov_delta_tab, 320, 190)
        self.explorer_delta_canvas.grid(row=1, column=1, sticky="nsew")
        self.explorer_delta_canvas.bind("<Configure>", self._on_explorer_pie_canvas_resize)

        trends_deps_tab = ttk.Frame(visuals_nb, padding=4)
        trends_deps_tab.columnconfigure(0, weight=1)
        trends_deps_tab.columnconfigure(1, weight=1)
        trends_deps_tab.rowconfigure(1, weight=1)
        ttk.Label(trends_deps_tab, text="Run trends (small multiples, recent single compiles)").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Label(trends_deps_tab, text="Dependency graph (parent/child switch state)").grid(row=0, column=1, sticky="w")
        self.explorer_trend_canvas = self._dashboard_canvas(trends_deps_tab, 320, 190)
        self.explorer_trend_canvas.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        self.explorer_trend_canvas.bind("<Configure>", self._on_explorer_pie_canvas_resize)
        self.explorer_dep_canvas = self._dashboard_canvas(trends_deps_tab, 320, 190)
        self.explorer_dep_canvas.grid(row=1, column=1, sticky="nsew")
        self.explorer_dep_canvas.bind("<Configure>", self._on_explorer_pie_canvas_resize)

        visuals_nb.add(pies_tab, text="Share")
        visuals_nb.add(heatmap_tab, text="Heatmap")
        visuals_nb.add(treemap_tab, text="Breakdown")
        visuals_nb.add(cov_delta_tab, text="Coverage + Totals")
        visuals_nb.add(trends_deps_tab, text="Trends + Dependencies")

        body = ttk.Panedwindow(split, orient=tk.HORIZONTAL)

        left = self._main_panel(body, "Structure Tree", padx=6, pady=6)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)
        self.explorer_tree = ttk.Treeview(left, columns=("rules", "chars", "tokens"), show="tree headings", height=24)
        self.explorer_tree.heading("#0", text="Node")
        self.explorer_tree.heading("rules", text="Rules")
        self.explorer_tree.heading("chars", text="Chars")
        self.explorer_tree.heading("tokens", text="Tokens")
        self.explorer_tree.column("#0", width=260, stretch=True)
        self.explorer_tree.column("rules", width=60, anchor="center", stretch=False)
        self.explorer_tree.column("chars", width=80, anchor="center", stretch=False)
        self.explorer_tree.column("tokens", width=90, anchor="center", stretch=False)
        self.font_tree_total = tkfont.nametofont("TkDefaultFont").copy()
        self.font_tree_total.configure(weight="bold")
        self.explorer_tree.tag_configure("total_row", font=self.font_tree_total)
        tree_scroll = ttk.Scrollbar(left, orient="vertical", command=self.explorer_tree.yview)
        self.explorer_tree.configure(yscrollcommand=tree_scroll.set)
        self.explorer_tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll.grid(row=0, column=1, sticky="ns")
        body.add(left, weight=1)

        right = ttk.Frame(body)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        right.rowconfigure(1, weight=0)

        table_wrap = self._main_panel(right, "Rule Table", padx=6, pady=6)
        table_wrap.grid(row=0, column=0, sticky="nsew")
        table_wrap.columnconfigure(0, weight=1)
        table_wrap.rowconfigure(0, weight=1)
        table_wrap.rowconfigure(1, weight=0)
        columns = ("line", "id", "tag", "group", "facet", "section", "text")
        self.explorer_table = ttk.Treeview(table_wrap, columns=columns, show="headings", height=22)
        self.explorer_table.heading("line", text="Line")
        self.explorer_table.heading("id", text="ID")
        self.explorer_table.heading("tag", text="TAG")
        self.explorer_table.heading("group", text="GROUP")
        self.explorer_table.heading("facet", text="Facet")
        self.explorer_table.heading("section", text="Section")
        self.explorer_table.heading("text", text="Text")
        self.explorer_table.column("line", width=54, anchor="center", stretch=False)
        self.explorer_table.column("id", width=88, anchor="w", stretch=False)
        self.explorer_table.column("tag", width=70, anchor="w", stretch=False)
        self.explorer_table.column("group", width=96, anchor="w", stretch=False)
        self.explorer_table.column("facet", width=140, anchor="w", stretch=False)
        self.explorer_table.column("section", width=130, anchor="w", stretch=False)
        self.explorer_table.column("text", width=1800, anchor="w", stretch=False)
        table_scroll = ttk.Scrollbar(table_wrap, orient="vertical", command=self.explorer_table.yview)
        table_hscroll = ttk.Scrollbar(table_wrap, orient="horizontal", command=self.explorer_table.xview)
        self.explorer_table.configure(yscrollcommand=table_scroll.set, xscrollcommand=table_hscroll.set)
        self.explorer_table.grid(row=0, column=0, sticky="nsew")
        table_scroll.grid(row=0, column=1, sticky="ns")
        table_hscroll.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.explorer_table.bind("<<TreeviewSelect>>", self._on_explorer_table_select)

        detail_wrap = self._main_panel(right, "Selected Rule Detail", padx=6, pady=6)
        detail_wrap.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        detail_wrap.columnconfigure(0, weight=1)
        detail_wrap.rowconfigure(0, weight=1)
        self.explorer_detail_widget = self._code_text_widget(detail_wrap, height=8)
        detail_scroll = ttk.Scrollbar(detail_wrap, orient="vertical", command=self.explorer_detail_widget.yview)
        self.explorer_detail_widget.configure(yscrollcommand=detail_scroll.set)
        self.explorer_detail_widget.grid(row=0, column=0, sticky="nsew")
        detail_scroll.grid(row=0, column=1, sticky="ns")
        body.add(right, weight=3)

        split.add(visuals, minsize=220)
        split.add(body, minsize=260)

        def _place_split_sash() -> None:
            try:
                total_h = split.winfo_height()
                y = max(240, int(total_h * 0.42))
                split.sash_place(0, 2, y)
            except Exception:
                pass

        self.after(120, _place_split_sash)

    @staticmethod
    def _parse_explorer_records(input_path: Path) -> list[dict[str, object]]:
        records = parse_dsl_records(input_path)
        for rec in records:
            rec["tokens"] = _token_count(str(rec["text"]))
        return records

    def _refresh_explorer_data(self) -> None:
        if self.explorer_tree is None or self.explorer_table is None:
            return
        input_path = Path(self.input_var.get().strip())
        if not input_path.exists() or not input_path.is_file():
            self._explorer_records = []
            self._group_rule_counts = {group: 0 for group in KNOWN_GROUPS}
            self._example_facet_counts = {}
            self._example_facet_order = []
            self.explorer_stats_var.set("Rules: 0  Sections: 0  TAGs: 0  GROUPs: 0  Facets: 0  Tokens: 0  Tokenizer: -")
            self.explorer_section_totals_var.set("Section totals: -")
            self.explorer_visual_summary_var.set("Visual summary: -")
            self.explorer_subpart_title_var.set("Subparts: -")
            self.explorer_filter_facet_var.set("All facets")
            self.explorer_filter_info_var.set("0 matching rules")
            self._populate_explorer_tree([])
            self._populate_explorer_table([])
            self._refresh_explorer_visuals([])
            self._refresh_example_facet_controls()
            self._refresh_all_group_visuals()
            self._refresh_preset_help()
            self._set_explorer_detail_text("Input file not found.")
            return
        try:
            records = self._parse_explorer_records(input_path)
        except Exception as exc:
            self._explorer_records = []
            self._group_rule_counts = {group: 0 for group in KNOWN_GROUPS}
            self._example_facet_counts = {}
            self._example_facet_order = []
            self.explorer_stats_var.set("Rules: 0  Sections: 0  TAGs: 0  GROUPs: 0  Facets: 0  Tokens: 0  Tokenizer: -")
            self.explorer_section_totals_var.set("Section totals: -")
            self.explorer_visual_summary_var.set("Visual summary: -")
            self.explorer_subpart_title_var.set("Subparts: -")
            self.explorer_filter_facet_var.set("All facets")
            self.explorer_filter_info_var.set("0 matching rules")
            self._populate_explorer_tree([])
            self._populate_explorer_table([])
            self._refresh_explorer_visuals([])
            self._refresh_example_facet_controls()
            self._refresh_all_group_visuals()
            self._refresh_preset_help()
            self._set_explorer_detail_text(f"Could not parse source: {exc}")
            return

        self._explorer_records = records
        self._group_rule_counts = self._group_rule_counts_from_records(records)
        self._refresh_example_facet_controls()
        section_values = ["All sections"] + self._ordered_section_names(records)
        tag_values = ["All tags"] + sorted({str(r["tag"]) for r in records})
        group_values = ["All groups"] + sorted(
            {str(r["group"]) for r in records},
            key=lambda g: KNOWN_GROUPS.index(g) if g in KNOWN_GROUPS else 999,
        )
        facet_values = ["All facets"] + sorted({str(r.get("facet", "")) for r in records if str(r.get("facet", ""))})
        if self.explorer_section_combo is not None:
            self.explorer_section_combo.configure(values=section_values)
        if self.explorer_tag_combo is not None:
            self.explorer_tag_combo.configure(values=tag_values)
        if self.explorer_group_combo is not None:
            self.explorer_group_combo.configure(values=group_values)
        if self.explorer_facet_combo is not None:
            self.explorer_facet_combo.configure(values=facet_values)
        if self.explorer_filter_section_var.get() not in section_values:
            self.explorer_filter_section_var.set("All sections")
        if self.explorer_filter_tag_var.get() not in tag_values:
            self.explorer_filter_tag_var.set("All tags")
        if self.explorer_filter_group_var.get() not in group_values:
            self.explorer_filter_group_var.set("All groups")
        if self.explorer_filter_facet_var.get() not in facet_values:
            self.explorer_filter_facet_var.set("All facets")

        total_chars = sum(int(r["chars"]) for r in records)
        total_tokens = sum(int(r["tokens"]) for r in records)
        self.explorer_stats_var.set(
            f"Rules: {len(records)}  Sections: {len(section_values) - 1}  TAGs: {len(tag_values) - 1}  GROUPs: {len(group_values) - 1}  Facets: {len(facet_values) - 1}  "
            f"Text chars: {total_chars}  Tokens: {total_tokens}  Tokenizer: {_TOKENIZER_LABEL}"
        )
        self._refresh_all_group_visuals()
        self._refresh_preset_help()
        self._apply_explorer_filters()

    def _apply_explorer_filters(self) -> None:
        records = self._explorer_records
        section_filter = self.explorer_filter_section_var.get().strip()
        tag_filter = self.explorer_filter_tag_var.get().strip()
        group_filter = self.explorer_filter_group_var.get().strip()
        facet_filter = self.explorer_filter_facet_var.get().strip()
        search = self.explorer_search_var.get().strip().lower()
        filtered: list[dict[str, object]] = []
        for rec in records:
            if section_filter and section_filter != "All sections" and str(rec["section"]) != section_filter:
                continue
            if tag_filter and tag_filter != "All tags" and str(rec["tag"]) != tag_filter:
                continue
            if group_filter and group_filter != "All groups" and str(rec["group"]) != group_filter:
                continue
            if facet_filter and facet_filter != "All facets" and str(rec.get("facet", "")) != facet_filter:
                continue
            if search:
                hay = " ".join(
                    [
                        str(rec["id"]),
                        str(rec["tag"]),
                        str(rec["group"]),
                        str(rec.get("facet", "")),
                        str(rec["section"]),
                        str(rec["subsection"]),
                        str(rec["text"]),
                    ]
                ).lower()
                if search not in hay:
                    continue
            filtered.append(rec)
        tree_records = filtered if self.explorer_tree_mirror_var.get() else records
        self._populate_explorer_tree(tree_records)
        self._populate_explorer_table(filtered)
        self.explorer_filter_info_var.set(f"{len(filtered)} matching rules (of {len(records)})")
        self._set_explorer_section_totals(filtered)
        self._refresh_explorer_visuals(filtered)

    def _schedule_apply_explorer_filters(self, delay_ms: int = 120) -> None:
        if self._explorer_filter_after_id:
            try:
                self.after_cancel(self._explorer_filter_after_id)
            except Exception:
                pass
            self._explorer_filter_after_id = None
        if delay_ms <= 0:
            self._apply_explorer_filters()
            return
        self._explorer_filter_after_id = self.after(delay_ms, self._apply_explorer_filters)

    def _clear_explorer_filters(self) -> None:
        self.explorer_filter_section_var.set("All sections")
        self.explorer_filter_tag_var.set("All tags")
        self.explorer_filter_group_var.set("All groups")
        self.explorer_filter_facet_var.set("All facets")
        self.explorer_search_var.set("")
        self._apply_explorer_filters()

    @staticmethod
    def _canonical_section_order() -> list[str]:
        return ["AGENT", "ROLE", "LOGIC", "EXAMPLES", "MEMORY", "SECURITY"]

    def _ordered_section_names(self, records: list[dict[str, object]]) -> list[str]:
        present = {str(r["section"]) for r in records}
        ordered = [s for s in self._canonical_section_order() if s in present]
        extras = sorted(s for s in present if s not in set(self._canonical_section_order()))
        return ordered + extras

    @staticmethod
    def _subparts_for_section(section: str, recs: list[dict[str, object]]) -> list[tuple[str, list[dict[str, object]]]]:
        sec = section.upper()
        buckets: list[tuple[str, list[dict[str, object]]]]
        if sec == "ROLE":
            med = [r for r in recs if "medical approach" in str(r["subsection"]).lower()]
            emo = [r for r in recs if "emotional intelligence" in str(r["subsection"]).lower()]
            buckets = [("Medical Approach", med), ("Emotional Intelligence", emo)]
            return buckets
        if sec == "LOGIC":
            parent = [r for r in recs if UIMixin._logic_step_idx_from_record(r) == 0]
            s1 = [r for r in recs if UIMixin._logic_step_idx_from_record(r) == 1]
            s2 = [r for r in recs if UIMixin._logic_step_idx_from_record(r) == 2]
            s3 = [r for r in recs if UIMixin._logic_step_idx_from_record(r) == 3]
            s4 = [r for r in recs if UIMixin._logic_step_idx_from_record(r) == 4]
            s5 = [r for r in recs if UIMixin._logic_step_idx_from_record(r) == 5]
            buckets = [("Parent", parent), ("Step S1", s1), ("Step S2", s2), ("Step S3", s3), ("Step S4", s4), ("Step S5", s5)]
            return buckets
        if sec == "EXAMPLES":
            buckets = [
                ("Parent / Scaffold", [r for r in recs if str(r.get("facet", "")) == "Parent / Scaffold"]),
                ("Short Scaffold", [r for r in recs if str(r.get("facet", "")) == "Short Scaffold"]),
                ("Full Examples", [r for r in recs if str(r.get("facet", "")) == "Full Examples"]),
                ("Eye", [r for r in recs if str(r.get("facet", "")) == "Eye"]),
                ("ENT", [r for r in recs if str(r.get("facet", "")) == "ENT"]),
                ("Dermatology", [r for r in recs if str(r.get("facet", "")) == "Dermatology"]),
                ("General", [r for r in recs if str(r.get("facet", "")) == "General"]),
                ("Post Ops", [r for r in recs if str(r.get("facet", "")) == "Post Ops"]),
                ("Child", [r for r in recs if str(r.get("facet", "")) == "Child"]),
                ("Vet", [r for r in recs if str(r.get("facet", "")) == "Vet"]),
            ]
            return buckets
        if sec == "MEMORY":
            buckets = [
                ("Parent / Shared", [r for r in recs if str(r.get("group", "")) == "MEMORY"]),
                ("Ophthalmology", [r for r in recs if str(r.get("group", "")) == "MEM_EYE"]),
                ("ENT", [r for r in recs if str(r.get("group", "")) == "MEM_ENT"]),
                ("Derm", [r for r in recs if str(r.get("group", "")) == "MEM_DERM"]),
                ("Child", [r for r in recs if str(r.get("group", "")) == "MEM_CHILD"]),
                ("Vet", [r for r in recs if str(r.get("group", "")) == "MEM_VET"]),
                ("Red Flags", [r for r in recs if str(r.get("group", "")) == "MEM_RED"]),
            ]
            return buckets
        if sec == "SECURITY":
            reminders = [r for r in recs if "step reminders" in str(r.get("subsection", "")).lower()]
            persona = [r for r in recs if r not in reminders]
            buckets = [("Persona / Scope", persona), ("Step Reminders", reminders)]
            return buckets
        return []

    def _set_explorer_section_totals(self, records: list[dict[str, object]]) -> None:
        by_section: dict[str, list[dict[str, object]]] = defaultdict(list)
        for rec in records:
            by_section[str(rec["section"])].append(rec)
        parts: list[str] = []
        for section in self._ordered_section_names(records):
            recs = by_section.get(section, [])
            if not recs:
                continue
            rules = len(recs)
            tokens = sum(int(r["tokens"]) for r in recs)
            parts.append(f"{section}: {rules}r/{tokens}t")
        self.explorer_section_totals_var.set("Section totals: " + (" | ".join(parts) if parts else "-"))

    def _refresh_explorer_pies(self, records: list[dict[str, object]]) -> None:
        if self.explorer_section_pie_canvas is None or self.explorer_subpart_pie_canvas is None:
            return
        self._explorer_last_pie_records = list(records)
        metric = self._visual_metric_name()
        by_section: dict[str, list[dict[str, object]]] = defaultdict(list)
        for rec in records:
            by_section[str(rec["section"])].append(rec)
        section_data: list[tuple[str, int]] = []
        for section in self._ordered_section_names(records):
            recs = by_section.get(section, [])
            amount = self._metric_total(recs, metric)
            if amount > 0:
                section_data.append((section, amount))
        self._draw_ranked_share_chart(
            self.explorer_section_pie_canvas,
            section_data,
            metric_label=metric,
            section_name="",
        )

        selected = self.explorer_filter_section_var.get().strip()
        if not selected or selected == "All sections" or selected not in by_section or self._metric_total(by_section.get(selected, []), metric) <= 0:
            if section_data:
                selected = max(section_data, key=lambda x: x[1])[0]
            else:
                selected = "-"
        self.explorer_subpart_title_var.set(f"Subpart share: {selected}")
        recs = by_section.get(selected, [])
        subpart_data = [(name, self._metric_total(bucket, metric)) for name, bucket in self._subparts_for_section(selected, recs) if bucket]
        self._draw_ranked_share_chart(
            self.explorer_subpart_pie_canvas,
            subpart_data,
            metric_label=metric,
            section_name=selected,
        )

    @staticmethod
    def _fmt_short_num(value: int) -> str:
        if value >= 1_000_000:
            txt = f"{value / 1_000_000:.1f}".rstrip("0").rstrip(".")
            return f"{txt}M"
        if value >= 1_000:
            txt = f"{value / 1_000:.1f}".rstrip("0").rstrip(".")
            return f"{txt}k"
        return str(value)

    def _draw_ranked_share_chart(
        self,
        canvas: tk.Canvas,
        data: list[tuple[str, int]],
        metric_label: str,
        section_name: str,
    ) -> None:
        canvas.delete("all")
        width = max(int(canvas.winfo_width()), 1)
        height = max(int(canvas.winfo_height()), 1)
        if not data:
            canvas.create_text(width // 2, height // 2, text="No data", fill=TEXT_MUTED, font=("Segoe UI", 10))
            return
        filtered = [(label, value) for label, value in data if value > 0]
        if not filtered:
            canvas.create_text(width // 2, height // 2, text="No metric data", fill=TEXT_MUTED, font=("Segoe UI", 10))
            return
        total = sum(value for _label, value in filtered)
        top_items = sorted(filtered, key=lambda item: item[1], reverse=True)[:8]
        left = 12
        top = 12
        right = 12
        bottom = 18
        label_w = 118
        value_w = 86
        bar_left = left + label_w
        bar_right = width - right - value_w
        usable_h = max(height - top - bottom, 40)
        row_h = max(usable_h / max(len(top_items), 1), 16)
        max_value = max(value for _label, value in top_items) or 1
        for idx, (label, value) in enumerate(top_items):
            y = top + idx * row_h
            yc = y + (row_h / 2)
            bar_h = max(row_h - 6, 8)
            section_for_color = section_name or label
            base_color = self._section_color(section_for_color)
            fill = self._subpart_color(section_for_color, label, idx)
            pct = (100.0 * value / total) if total else 0.0
            bar_w = max(2, (bar_right - bar_left) * (value / max_value))
            canvas.create_text(left, yc, text=label, anchor="w", fill=TEXT_PRIMARY, font=("Segoe UI", 8, "bold"))
            canvas.create_rectangle(
                bar_left,
                yc - (bar_h / 2),
                bar_right,
                yc + (bar_h / 2),
                fill=self._mix_hex(base_color, "#ffffff", 0.84),
                outline=CARD_BORDER,
            )
            canvas.create_rectangle(
                bar_left,
                yc - (bar_h / 2),
                bar_left + bar_w,
                yc + (bar_h / 2),
                fill=fill,
                outline=fill,
            )
            canvas.create_text(
                width - right,
                yc,
                text=f"{self._fmt_short_num(value)} {pct:.0f}%",
                anchor="e",
                fill=TEXT_SECONDARY,
                font=("Segoe UI", 8),
            )
        canvas.create_text(
            left,
            height - 6,
            text=f"Ranked by {metric_label.lower()} share",
            anchor="sw",
            fill=TEXT_MUTED,
            font=("Segoe UI", 7),
        )

    def _cached_output_tokens(self, path: Path) -> int:
        """
        Tokenize output files with mtime/size caching to keep trend redraws cheap.
        """
        try:
            stat = path.stat()
            key = str(path.resolve())
            sig = (int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000))), int(stat.st_size))
            cache = getattr(self, "_output_token_cache", None)
            if cache is None:
                cache = {}
                setattr(self, "_output_token_cache", cache)
            cached = cache.get(key)
            if cached is not None and (cached[0], cached[1]) == sig:
                return int(cached[2])
            tokens = _token_count(path.read_text(encoding="utf-8"))
            cache[key] = (sig[0], sig[1], tokens)
            return tokens
        except Exception:
            return 0

    @staticmethod
    def _record_enabled_for_groups(rec: dict[str, object], selected_groups: set[str]) -> bool:
        """
        Mirror compiler selection logic for wrapped rules.
        This is important for LOGIC step ablations, where wrapped GROUP may be LOGIC
        but effective requirements include LOGIC_S* via ID mapping.
        """
        rule_id = str(rec.get("id", ""))
        group = str(rec.get("group", ""))
        required = required_groups_for_rule(rule_id, group)
        return all(req in selected_groups for req in required)

    @staticmethod
    def _record_enabled_for_visual_state(
        rec: dict[str, object],
        selected_groups: set[str],
        excluded_example_facets: set[str],
    ) -> bool:
        if not UIMixin._record_enabled_for_groups(rec, selected_groups):
            return False
        facet = semantic_example_facet_name(rec)
        return facet not in excluded_example_facets

    def _refresh_visual_summary(self, baseline_records: list[dict[str, object]], active_records: list[dict[str, object]]) -> None:
        metric = self._visual_metric_name()
        baseline_metric = self._metric_total(baseline_records, metric)
        active_metric = self._metric_total(active_records, metric)
        groups_off = len(self._excluded_groups())
        facets_off = len(self._excluded_example_facets())
        delta_pct = ((active_metric - baseline_metric) / baseline_metric * 100.0) if baseline_metric else 0.0
        self.explorer_visual_summary_var.set(
            "Visual summary: "
            f"baseline {len(baseline_records)} rules / {self._fmt_short_num(baseline_metric)} {metric.lower()} | "
            f"active {len(active_records)} rules / {self._fmt_short_num(active_metric)} {metric.lower()} | "
            f"delta {delta_pct:+.1f}% | groups off {groups_off} | example filters off {facets_off}"
        )

    def _refresh_explorer_visuals(self, records: list[dict[str, object]]) -> None:
        self._explorer_last_pie_records = list(records)
        self._refresh_explorer_pies(records)
        self._draw_tag_group_heatmap(records)
        self._draw_section_treemap(records)
        active_groups = self._selected_groups() if hasattr(self, "_selected_groups") else set(KNOWN_GROUPS)
        excluded_example_facets = set(self._excluded_example_facets())
        active_records = [
            r for r in records if self._record_enabled_for_visual_state(r, active_groups, excluded_example_facets)
        ]
        self._refresh_visual_summary(records, active_records)
        self._draw_coverage_bars(records, active_records)
        self._draw_delta_chart(records, active_records)
        self._draw_run_trend_chart()
        self._draw_dependency_graph(active_groups)

    def _draw_tag_group_heatmap(self, records: list[dict[str, object]]) -> None:
        canvas = self.explorer_heatmap_canvas
        if canvas is None:
            return
        canvas.delete("all")
        w = max(int(canvas.winfo_width()), 1)
        h = max(int(canvas.winfo_height()), 1)
        metric = self._visual_metric_name()
        if not records:
            canvas.create_text(w // 2, h // 2, text="No data", fill=TEXT_MUTED, font=("Segoe UI", 10))
            return
        tag_totals: dict[str, int] = defaultdict(int)
        group_totals: dict[str, int] = defaultdict(int)
        matrix: dict[tuple[str, str], int] = defaultdict(int)
        for rec in records:
            tag = str(rec["tag"])
            group = str(rec["group"])
            amount = self._metric_value(rec, metric)
            tag_totals[tag] += amount
            group_totals[group] += amount
            matrix[(tag, group)] += amount
        top_tags = sorted(tag_totals.keys(), key=lambda t: tag_totals[t], reverse=True)[:8]
        top_groups = sorted(group_totals.keys(), key=lambda g: group_totals[g], reverse=True)[:10]
        tags = list(top_tags)
        groups = list(top_groups)
        if len(tag_totals) > len(top_tags):
            tags.append("Other")
        if len(group_totals) > len(top_groups):
            groups.append("Other")
        if not tags or not groups:
            canvas.create_text(w // 2, h // 2, text="No heatmap data", fill=TEXT_MUTED, font=("Segoe UI", 10))
            return
        agg: dict[tuple[str, str], int] = defaultdict(int)
        for (tag, group), value in matrix.items():
            tag_key = tag if tag in top_tags else ("Other" if "Other" in tags else None)
            group_key = group if group in top_groups else ("Other" if "Other" in groups else None)
            if tag_key is None or group_key is None:
                continue
            agg[(tag_key, group_key)] += value
        left = 88
        top = 30
        right = 8
        bottom = 30
        grid_w = max(w - left - right, 40)
        grid_h = max(h - top - bottom, 40)
        cw = max(grid_w / max(len(tags), 1), 8)
        ch = max(grid_h / max(len(groups), 1), 8)
        max_val = max(agg.values()) if agg else 1
        def _heat(v: int) -> str:
            if max_val <= 0 or v <= 0:
                return CARD_ALT_BG
            t = min(max(v / max_val, 0.0), 1.0)
            r = int(239 - (172 * t))
            g = int(246 - (105 * t))
            b = int(255 - (32 * t))
            return f"#{r:02x}{g:02x}{b:02x}"
        for r_i, group in enumerate(groups):
            y1 = top + (r_i * ch)
            y2 = y1 + ch
            grp_lbl = GROUP_CODE.get(group, group)
            canvas.create_text(left - 6, (y1 + y2) / 2, text=grp_lbl, anchor="e", fill=TEXT_PRIMARY, font=("Segoe UI", 7))
            for c_i, tag in enumerate(tags):
                x1 = left + (c_i * cw)
                x2 = x1 + cw
                v = agg.get((tag, group), 0)
                canvas.create_rectangle(x1, y1, x2, y2, fill=_heat(v), outline=CARD_BORDER)
                if cw >= 36 and ch >= 16 and v > 0:
                    canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=self._fmt_short_num(v), fill=TEXT_PRIMARY, font=("Segoe UI", 6, "bold"))
        if cw < 14:
            tag_step = 3
        elif cw < 22:
            tag_step = 2
        else:
            tag_step = 1

        def _tag_label(tag_name: str) -> str:
            if cw >= 28:
                return tag_name
            if len(tag_name) <= 4:
                return tag_name
            return tag_name[:4]

        rendered = 0
        for c_i, tag in enumerate(tags):
            if c_i % tag_step != 0:
                continue
            x = left + (c_i * cw) + (cw / 2)
            canvas.create_text(x, top - 8, text=_tag_label(tag), anchor="s", fill=TEXT_SECONDARY, font=("Segoe UI", 7))
            rendered += 1
        legend_text = f"Rows: top groups + Other, columns: top TAGs + Other, colour = {metric.lower()} weight"
        if rendered < len(tags):
            legend_text += f" (showing {rendered}/{len(tags)} TAG labels)"
        canvas.create_text(left, h - 6, text=legend_text, anchor="sw", fill=TEXT_MUTED, font=("Segoe UI", 7))

    def _draw_section_treemap(self, records: list[dict[str, object]]) -> None:
        canvas = self.explorer_treemap_canvas
        if canvas is None:
            return
        canvas.delete("all")
        w = max(int(canvas.winfo_width()), 1)
        h = max(int(canvas.winfo_height()), 1)
        metric = self._visual_metric_name()
        if not records:
            canvas.create_text(w // 2, h // 2, text="No data", fill=TEXT_MUTED, font=("Segoe UI", 10))
            return
        by_section: dict[str, list[dict[str, object]]] = defaultdict(list)
        for rec in records:
            by_section[str(rec["section"])].append(rec)
        sections = [(sec, by_section[sec]) for sec in self._ordered_section_names(records) if by_section.get(sec)]
        totals = [(sec, self._metric_total(recs, metric), recs) for sec, recs in sections]
        totals = [item for item in totals if item[1] > 0]
        if not totals:
            canvas.create_text(w // 2, h // 2, text="No metric data", fill=TEXT_MUTED, font=("Segoe UI", 10))
            return
        left = 10
        top = 12
        right = 10
        bottom = 24
        label_w = 94
        value_w = 70
        bar_left = left + label_w
        bar_right = w - right - value_w
        usable_h = max(h - top - bottom, 40)
        row_h = max(usable_h / max(len(totals), 1), 18)
        for sec_idx, (section, sec_total, recs) in enumerate(totals):
            y = top + sec_idx * row_h
            yc = y + (row_h / 2)
            bar_h = max(row_h - 7, 10)
            canvas.create_text(left, yc, text=section, anchor="w", fill=TEXT_PRIMARY, font=("Segoe UI", 8, "bold"))
            canvas.create_rectangle(
                bar_left,
                yc - (bar_h / 2),
                bar_right,
                yc + (bar_h / 2),
                fill=self._mix_hex(self._section_color(section), "#ffffff", 0.88),
                outline=CARD_BORDER,
            )
            x = bar_left
            span = max(bar_right - bar_left, 20)
            subparts = [(name, bucket) for name, bucket in self._subparts_for_section(section, recs) if bucket]
            if not subparts:
                continue
            sub_total = self._metric_total(recs, metric)
            for sub_idx, (name, bucket) in enumerate(subparts):
                amount = self._metric_total(bucket, metric)
                if amount <= 0 or sub_total <= 0:
                    continue
                seg_w = span * (amount / sub_total)
                x2 = min(bar_right, x + seg_w)
                fill = self._subpart_color(section, name, sub_idx)
                canvas.create_rectangle(x, yc - (bar_h / 2), x2, yc + (bar_h / 2), fill=fill, outline=fill)
                if (x2 - x) >= 56:
                    canvas.create_text(
                        x + 4,
                        yc,
                        text=name,
                        anchor="w",
                        fill="#ffffff" if sub_idx > 1 else TEXT_PRIMARY,
                        font=("Segoe UI", 7, "bold"),
                    )
                x = x2
            canvas.create_text(
                w - right,
                yc,
                text=self._fmt_short_num(sec_total),
                anchor="e",
                fill=TEXT_SECONDARY,
                font=("Segoe UI", 8),
            )
        canvas.create_text(
            left,
            h - 6,
            text=f"Each row is a section; segments are subparts, sized by {metric.lower()}",
            anchor="sw",
            fill=TEXT_MUTED,
            font=("Segoe UI", 7),
        )

    def _draw_coverage_bars(self, baseline_records: list[dict[str, object]], active_records: list[dict[str, object]]) -> None:
        canvas = self.explorer_coverage_canvas
        if canvas is None:
            return
        canvas.delete("all")
        w = max(int(canvas.winfo_width()), 1)
        h = max(int(canvas.winfo_height()), 1)
        metric = self._visual_metric_name()
        if not baseline_records:
            canvas.create_text(w // 2, h // 2, text="No data", fill=TEXT_MUTED, font=("Segoe UI", 10))
            return
        b_by_sec: dict[str, list[dict[str, object]]] = defaultdict(list)
        a_by_sec: dict[str, list[dict[str, object]]] = defaultdict(list)
        for rec in baseline_records:
            b_by_sec[str(rec["section"])].append(rec)
        for rec in active_records:
            a_by_sec[str(rec["section"])].append(rec)
        sections = [s for s in self._ordered_section_names(baseline_records) if b_by_sec.get(s)]
        if not sections:
            canvas.create_text(w // 2, h // 2, text="No section data", fill=TEXT_MUTED, font=("Segoe UI", 10))
            return
        left = 8
        right = 8
        top = 8
        bottom = 8
        row_h = max((h - top - bottom) / max(len(sections), 1), 12)
        bar_x1 = left + 82
        bar_x2 = w - right - 72
        bar_w = max(bar_x2 - bar_x1, 20)
        for idx, sec in enumerate(sections):
            y = top + idx * row_h
            yc = y + (row_h / 2)
            base = self._metric_total(b_by_sec[sec], metric)
            active = self._metric_total(a_by_sec.get(sec, []), metric)
            pct = (active / base) if base > 0 else 0.0
            inc_w = bar_w * pct
            color = self._section_color(sec)
            canvas.create_text(left, yc, text=sec, anchor="w", fill=TEXT_PRIMARY, font=("Segoe UI", 8, "bold"))
            canvas.create_rectangle(
                bar_x1,
                y + 2,
                bar_x2,
                y + row_h - 2,
                fill=self._mix_hex(color, "#ffffff", 0.9),
                outline=CARD_BORDER,
            )
            canvas.create_rectangle(
                bar_x1,
                y + 2,
                bar_x1 + inc_w,
                y + row_h - 2,
                fill=color,
                outline=color,
            )
            canvas.create_text(
                bar_x2 + 4,
                yc,
                text=f"{self._fmt_short_num(active)}/{self._fmt_short_num(base)}",
                anchor="w",
                fill=TEXT_SECONDARY,
                font=("Segoe UI", 7),
            )
        canvas.create_text(
            left,
            h - 6,
            text=f"Filled bar = included {metric.lower()}, pale bar = excluded share within current filtered scope",
            anchor="sw",
            fill=TEXT_MUTED,
            font=("Segoe UI", 7),
        )

    def _draw_delta_chart(self, baseline_records: list[dict[str, object]], active_records: list[dict[str, object]]) -> None:
        canvas = self.explorer_delta_canvas
        if canvas is None:
            return
        canvas.delete("all")
        w = max(int(canvas.winfo_width()), 1)
        h = max(int(canvas.winfo_height()), 1)
        if not baseline_records:
            canvas.create_text(w // 2, h // 2, text="No data", fill=TEXT_MUTED, font=("Segoe UI", 10))
            return
        b_rules = len(baseline_records)
        a_rules = len(active_records)
        b_chars = sum(int(r["chars"]) for r in baseline_records)
        a_chars = sum(int(r["chars"]) for r in active_records)
        b_tokens = sum(int(r["tokens"]) for r in baseline_records)
        a_tokens = sum(int(r["tokens"]) for r in active_records)
        metrics = [("Rules", b_rules, a_rules), ("Chars", b_chars, a_chars), ("Tokens", b_tokens, a_tokens)]
        max_v = max(v for _n, b, a in metrics for v in (b, a))
        if max_v <= 0:
            max_v = 1
        left = 12
        right = 8
        top = 18
        bottom = 18
        area_w = max(w - left - right, 20)
        area_h = max(h - top - bottom, 20)
        group_w = area_w / max(len(metrics), 1)
        for idx, (name, b_v, a_v) in enumerate(metrics):
            x0 = left + idx * group_w
            bw = max(group_w * 0.28, 10)
            gap = max(group_w * 0.08, 4)
            ax = x0 + (group_w - (2 * bw + gap)) / 2
            b_h = area_h * (b_v / max_v)
            a_h = area_h * (a_v / max_v)
            base_y = top + area_h
            color = {"Rules": "#94a3b8", "Chars": "#8b5cf6", "Tokens": ACCENT_BLUE}.get(name, ACCENT_BLUE)
            canvas.create_rectangle(ax, base_y - b_h, ax + bw, base_y, fill="#dbe5ef", outline=CARD_BORDER)
            canvas.create_rectangle(ax + bw + gap, base_y - a_h, ax + (2 * bw) + gap, base_y, fill=color, outline=color)
            canvas.create_text(x0 + group_w / 2, base_y + 10, text=name, anchor="n", fill=TEXT_PRIMARY, font=("Segoe UI", 8, "bold"))
            delta_pct = ((a_v - b_v) / b_v * 100.0) if b_v else 0.0
            canvas.create_text(
                x0 + group_w / 2,
                2,
                text=f"{delta_pct:+.1f}%",
                anchor="n",
                fill=ACCENT_BLUE if delta_pct >= 0 else DANGER,
                font=("Segoe UI", 8),
            )
        canvas.create_text(
            left,
            2,
            text="Baseline = grey, active compile state = coloured",
            anchor="nw",
            fill=TEXT_MUTED,
            font=("Segoe UI", 7),
        )

    def _draw_run_trend_chart(self) -> None:
        canvas = self.explorer_trend_canvas
        if canvas is None:
            return
        canvas.delete("all")
        w = max(int(canvas.winfo_width()), 1)
        h = max(int(canvas.winfo_height()), 1)
        if not hasattr(self, "_read_log_events"):
            canvas.create_text(w // 2, h // 2, text="Run log unavailable", fill=TEXT_MUTED, font=("Segoe UI", 10))
            return
        events = [e for e in self._read_log_events() if str(e.get("run_type", "")) == "single_compile"][-24:]
        if not events:
            canvas.create_text(w // 2, h // 2, text="No single compile runs yet", fill=TEXT_MUTED, font=("Segoe UI", 10))
            return
        tokens: list[int] = []
        groups_on: list[int] = []
        scores: list[float | None] = []
        costs: list[float | None] = []
        for e in events:
            out_path = str(e.get("output_path", "")).strip()
            tok = 0
            if out_path:
                p = Path(out_path)
                if p.exists() and p.is_file():
                    tok = self._cached_output_tokens(p)
            tokens.append(tok)
            groups_on.append(len(e.get("selected_groups", []) or []))
            score_val = e.get("score", e.get("judge_score", None))
            cost_val = e.get("cost", e.get("run_cost", None))
            try:
                scores.append(float(score_val) if score_val is not None else None)
            except Exception:
                scores.append(None)
            try:
                costs.append(float(cost_val) if cost_val is not None else None)
            except Exception:
                costs.append(None)
        score_vals = [v for v in scores if v is not None]
        cost_vals = [v for v in costs if v is not None]
        series: list[tuple[str, list[float | None], str]] = [
            ("Output tokens", [float(v) for v in tokens], ACCENT_BLUE),
            ("Groups ON", [float(v) for v in groups_on], SUCCESS),
        ]
        if score_vals:
            series.append(("Score", [float(v) if v is not None else None for v in scores], "#8b5cf6"))
        if cost_vals:
            series.append(("Cost", [float(v) if v is not None else None for v in costs], "#ea580c"))
        left, right, top, bottom = 10, 8, 10, 16
        panel_gap = 8
        usable_h = max(h - top - bottom - (panel_gap * (len(series) - 1)), 40)
        panel_h = max(30, usable_h / max(len(series), 1))
        plot_left = left + 54
        plot_right = w - right - 8
        plot_w = max(plot_right - plot_left, 24)
        n = len(events)

        def _panel_xy(idx: int, value: float, min_v: float, max_v: float, y0: float) -> tuple[float, float]:
            x = plot_left + (plot_w * (idx / max(n - 1, 1)))
            if max_v <= min_v:
                y = y0 + (panel_h / 2)
            else:
                norm = (value - min_v) / (max_v - min_v)
                y = y0 + panel_h - 12 - ((panel_h - 22) * norm)
            return x, y

        for s_idx, (label, values, color) in enumerate(series):
            y0 = top + s_idx * (panel_h + panel_gap)
            y1 = y0 + panel_h
            canvas.create_rectangle(left, y0, w - right, y1, outline=CARD_BORDER, fill="")
            present = [float(v) for v in values if v is not None]
            if not present:
                continue
            min_v = min(present)
            max_v = max(present)
            if label in {"Output tokens", "Groups ON", "Cost"}:
                min_v = 0.0
            canvas.create_text(left + 6, y0 + 4, text=label, anchor="nw", fill=TEXT_PRIMARY, font=("Segoe UI", 8, "bold"))
            canvas.create_text(w - right - 4, y0 + 4, text=self._fmt_short_num(int(max_v)) if label != "Score" else f"{max_v:.2f}", anchor="ne", fill=TEXT_MUTED, font=("Segoe UI", 7))
            base_y = y1 - 12
            canvas.create_line(plot_left, base_y, plot_right, base_y, fill=CARD_BORDER, width=1)
            points: list[tuple[float, float]] = []
            for idx, value in enumerate(values):
                if value is None:
                    continue
                points.append(_panel_xy(idx, float(value), min_v, max_v, y0))
            for i in range(1, len(points)):
                canvas.create_line(*points[i - 1], *points[i], fill=color, width=2)
            for x, y in points:
                canvas.create_oval(x - 2, y - 2, x + 2, y + 2, fill=color, outline=color)
        canvas.create_text(left, h - 4, text="Recent single compiles, each panel scaled independently", anchor="sw", fill=TEXT_MUTED, font=("Segoe UI", 7))

    def _draw_dependency_graph(self, selected_groups: set[str]) -> None:
        canvas = self.explorer_dep_canvas
        if canvas is None:
            return
        canvas.delete("all")
        w = max(int(canvas.winfo_width()), 1)
        h = max(int(canvas.winfo_height()), 1)
        groups = DEPENDENCY_CLUSTERS
        cluster_names = ["EXAMPLES", "MEMORY", "LOGIC"]
        margin_x = 12
        margin_y = 12
        usable_w = max(w - (2 * margin_x), 60)
        col_x = [
            int(margin_x + (usable_w * ((idx + 0.5) / len(cluster_names))))
            for idx in range(len(cluster_names))
        ]
        node_w = max(44, min(84, int((usable_w / len(cluster_names)) * 0.78)))
        node_h = 14 if h >= 170 else 12
        cluster_nodes: dict[str, tuple[float, float]] = {}
        child_nodes: dict[str, tuple[float, float]] = {}
        parent_y = margin_y + 4
        child_top = parent_y + node_h + 12
        child_bottom = max(child_top + 4, h - 18)

        def _short_dep_label(label: str, compact: bool) -> str:
            if not compact:
                return label
            if label == "EXAMPLES":
                return "EX"
            if label == "MEMORY":
                return "MEM"
            if label == "LOGIC":
                return "LOG"
            if label.startswith("LOGIC_S"):
                return "S" + label.rsplit("S", 1)[-1]
            if label.startswith("EX_"):
                return label[3:7]
            if label.startswith("MEM_"):
                return label[4:8]
            return label[:6]

        for idx, parent in enumerate(cluster_names):
            px = col_x[idx]
            py = parent_y
            cluster_nodes[parent] = (px, py)
            children = groups[parent]
            if len(children) <= 1:
                step = 0.0
            else:
                step = (child_bottom - child_top) / max(len(children) - 1, 1)
            compact = node_w < 58 or step < 14
            for c_idx, child in enumerate(children):
                y = child_top + (c_idx * step)
                child_nodes[child] = (px, y)

        def _node(x: float, y: float, label: str, on: bool, parent_off_child_on: bool = False, compact: bool = False) -> None:
            fill = "#bbf7d0" if on else "#fee2e2"
            outline = "#15803d" if on else "#b91c1c"
            if parent_off_child_on:
                fill = "#fecaca"
                outline = "#b91c1c"
            canvas.create_rectangle(x - node_w / 2, y - node_h / 2, x + node_w / 2, y + node_h / 2, fill=fill, outline=outline)
            text_label = _short_dep_label(label, compact)
            fsize = 7 if node_w >= 58 else 6
            canvas.create_text(
                x,
                y,
                text=text_label,
                fill="#111827",
                font=("Segoe UI", fsize, "bold" if len(text_label) <= 8 else "normal"),
            )

        warnings = 0
        for parent, children in groups.items():
            px, py = cluster_nodes[parent]
            p_on = parent in selected_groups
            compact = node_w < 58
            _node(px, py, parent, p_on, compact=compact)
            for child in children:
                cx, cy = child_nodes[child]
                c_on = child in selected_groups
                bad = (not p_on) and c_on
                if bad:
                    warnings += 1
                line_col = "#ef4444" if bad else "#94a3b8"
                canvas.create_line(px, py + (node_h / 2), cx, cy - (node_h / 2), fill=line_col, width=2 if bad else 1)
                _node(cx, cy, child, c_on, parent_off_child_on=bad, compact=compact)
        note = f"Dependency alerts: {warnings}" if warnings else "Dependencies clean"
        note_col = "#b91c1c" if warnings else "#166534"
        canvas.create_text(8, h - 6, text=note, anchor="sw", fill=note_col, font=("Segoe UI", 8, "bold"))

    @staticmethod
    def _draw_pie_chart(canvas: tk.Canvas, data: list[tuple[str, int]]) -> None:
        palette = [
            "#2563eb",
            "#0ea5e9",
            "#22c55e",
            "#f59e0b",
            "#ef4444",
            "#a855f7",
            "#14b8a6",
            "#f97316",
        ]
        canvas.delete("all")
        width = max(int(canvas.winfo_width()), 1)
        height = max(int(canvas.winfo_height()), 1)
        if not data:
            canvas.create_text(width // 2, height // 2, text="No data", fill="#475569", font=("Segoe UI", 10))
            return
        total = sum(v for _k, v in data if v > 0)
        if total <= 0:
            canvas.create_text(width // 2, height // 2, text="No token data", fill="#475569", font=("Segoe UI", 10))
            return
        left_pad = 8
        top_pad = 8
        bottom_pad = 8
        right_pad = 8
        legend_gap = 12
        side_legend = width >= 360
        if side_legend:
            legend_w = min(max(130, int(width * 0.24)), 190)
            pie_region_w = width - left_pad - right_pad - legend_gap - legend_w
            pie_region_h = height - top_pad - bottom_pad
            pie_size = max(min(pie_region_w, pie_region_h), 60)
            pie_x1 = left_pad + max((pie_region_w - pie_size) // 2, 0)
            pie_y1 = top_pad + max((pie_region_h - pie_size) // 2, 0)
            legend_x = width - right_pad - legend_w
            legend_y_start = top_pad + 4
            max_rows = max(1, len(data))
            available_h = max(height - (top_pad + bottom_pad + 8), 24)
            step_y = max(10, min(16, int(available_h / max_rows)))
            legend_items = data
        else:
            legend_h = min(max(92, 14 + len(data) * 12), max(height - 24, 92))
            pie_region_w = width - left_pad - right_pad
            pie_region_h = height - top_pad - bottom_pad - legend_h - 6
            pie_size = max(min(pie_region_w, pie_region_h), 60)
            pie_x1 = left_pad + max((pie_region_w - pie_size) // 2, 0)
            pie_y1 = top_pad + max((pie_region_h - pie_size) // 2, 0)
            legend_x = left_pad + 2
            legend_y_start = pie_y1 + pie_size + 6
            max_rows = max(1, len(data))
            available_h = max(bottom_pad + legend_h - 14, 24)
            step_y = max(9, min(12, int(available_h / max_rows)))
            legend_items = data
        pie_x2, pie_y2 = pie_x1 + pie_size, pie_y1 + pie_size
        start = 90.0

        def _fmt_token(v: int) -> str:
            if v >= 1_000_000:
                txt = f"{v / 1_000_000:.1f}".rstrip("0").rstrip(".")
                return f"{txt}M"
            if v >= 1_000:
                txt = f"{v / 1_000:.1f}".rstrip("0").rstrip(".")
                return f"{txt}k"
            return str(v)

        cx = pie_x1 + (pie_size / 2.0)
        cy = pie_y1 + (pie_size / 2.0)
        label_r = pie_size * 0.34
        small_labels: list[tuple[float, float, str]] = []
        for idx, (label, value) in enumerate(data):
            if value <= 0:
                continue
            extent = -360.0 * (value / total)
            color = palette[idx % len(palette)]
            canvas.create_arc(pie_x1, pie_y1, pie_x2, pie_y2, start=start, extent=extent, fill=color, outline="#ffffff")
            pct = (100.0 * value / total) if total else 0.0
            mid_angle = start + (extent / 2.0)
            rad = math.radians(mid_angle)
            tx = cx + (label_r * math.cos(rad))
            ty = cy - (label_r * math.sin(rad))
            val_txt = _fmt_token(value)
            if pct >= 6.0:
                canvas.create_text(tx + 1, ty + 1, text=val_txt, fill="#0f172a", font=("Segoe UI", 7, "bold"))
                canvas.create_text(tx, ty, text=val_txt, fill="#ffffff", font=("Segoe UI", 7, "bold"))
            else:
                small_labels.append((mid_angle, pct, val_txt))
            start += extent
        if small_labels:
            outer_r = pie_size * 0.53
            for mid_angle, _pct, val_txt in small_labels:
                rad = math.radians(mid_angle)
                edge_x = cx + ((pie_size * 0.48) * math.cos(rad))
                edge_y = cy - ((pie_size * 0.48) * math.sin(rad))
                text_x = cx + (outer_r * math.cos(rad))
                text_y = cy - (outer_r * math.sin(rad))
                anchor = "w" if math.cos(rad) >= 0 else "e"
                text_x += 4 if anchor == "w" else -4
                canvas.create_line(edge_x, edge_y, text_x, text_y, fill="#475569", width=1)
                canvas.create_text(text_x, text_y, text=val_txt, anchor=anchor, fill="#334155", font=("Segoe UI", 7, "bold"))
        for idx, (label, value) in enumerate(legend_items):
            color = palette[idx % len(palette)]
            y = legend_y_start + idx * step_y
            pct = (100.0 * value / total) if total else 0.0
            canvas.create_rectangle(legend_x, y, legend_x + 10, y + 10, fill=color, outline=color)
            canvas.create_text(
                legend_x + 16,
                y + 5,
                anchor="w",
                text=f"{label} {_fmt_token(value)} ({pct:.1f}%)",
                fill="#1f2937",
                font=("Segoe UI", 8 if side_legend else 7),
            )
        # Legend renders all slices so values are always visible at a glance.

    def _populate_explorer_tree(self, records: list[dict[str, object]]) -> None:
        if self.explorer_tree is None:
            return
        self.explorer_tree.delete(*self.explorer_tree.get_children())
        total_rules = len(records)
        total_chars = sum(int(r["chars"]) for r in records)
        total_tokens = sum(int(r["tokens"]) for r in records)

        root_id = self.explorer_tree.insert(
            "",
            "end",
            text="TOTAL",
            values=(total_rules, total_chars, total_tokens),
            tags=("total_row",),
        )

        by_section: dict[str, list[dict[str, object]]] = defaultdict(list)
        for rec in records:
            by_section[str(rec["section"])].append(rec)
        max_section_tokens = 0
        for recs in by_section.values():
            max_section_tokens = max(max_section_tokens, sum(int(r["tokens"]) for r in recs))
        heavy_threshold = int(max_section_tokens * 0.6) if max_section_tokens > 0 else 0

        def _token_text(tokens: int) -> str:
            return f"{tokens} ^" if heavy_threshold > 0 and tokens >= heavy_threshold else str(tokens)

        ordered_sections = self._ordered_section_names(records)
        for section in ordered_sections:
            recs = by_section[section]
            sec_chars = sum(int(r["chars"]) for r in recs)
            sec_tokens = sum(int(r["tokens"]) for r in recs)
            sec_id = self.explorer_tree.insert(
                root_id,
                "end",
                text=section,
                values=(len(recs), sec_chars, _token_text(sec_tokens)),
            )
            for sub_name, bucket in self._subparts_for_section(section, recs):
                sub_chars = sum(int(r["chars"]) for r in bucket)
                sub_tokens = sum(int(r["tokens"]) for r in bucket)
                self.explorer_tree.insert(
                    sec_id,
                    "end",
                    text=sub_name,
                    values=(len(bucket), sub_chars, _token_text(sub_tokens)),
                )
            self.explorer_tree.item(sec_id, open=True)
        self.explorer_tree.item(root_id, open=True)

    def _on_explorer_pie_canvas_resize(self, _event=None) -> None:
        if self._explorer_visual_after_id:
            try:
                self.after_cancel(self._explorer_visual_after_id)
            except Exception:
                pass
            self._explorer_visual_after_id = None
        self._explorer_visual_after_id = self.after(
            90, lambda: self._refresh_explorer_visuals(self._explorer_last_pie_records or self._explorer_records)
        )

    def _populate_explorer_table(self, records: list[dict[str, object]]) -> None:
        if self.explorer_table is None:
            return
        self.explorer_table.delete(*self.explorer_table.get_children())
        self._explorer_item_map = {}
        for rec in records:
            text = str(rec["text"])
            item_id = self.explorer_table.insert(
                "",
                "end",
                values=(
                    str(rec["line_no"]),
                    str(rec["id"]),
                    str(rec["tag"]),
                    str(rec["group"]),
                    str(rec.get("facet", "")),
                    str(rec["section"]),
                    text,
                ),
            )
            self._explorer_item_map[item_id] = rec
        if records:
            first = self.explorer_table.get_children()[0]
            self.explorer_table.selection_set(first)
            self.explorer_table.focus(first)
            self._on_explorer_table_select()
        else:
            self._set_explorer_detail_text("No matching rules for current filters.")

    def _set_explorer_detail_text(self, text: str) -> None:
        if self.explorer_detail_widget is None:
            return
        self.explorer_detail_widget.config(state="normal")
        self.explorer_detail_widget.delete("1.0", tk.END)
        self.explorer_detail_widget.insert("1.0", text)
        self.explorer_detail_widget.config(state="disabled")

    def _on_explorer_table_select(self, _event=None) -> None:
        if self.explorer_table is None:
            return
        selection = self.explorer_table.selection()
        if not selection:
            self._set_explorer_detail_text("Select a rule row to see full content.")
            return
        rec = self._explorer_item_map.get(selection[0])
        if rec is None:
            self._set_explorer_detail_text("Rule detail unavailable.")
            return
        detail = (
            f"Line: {rec['line_no']}\n"
            f"ID: {rec['id']}\n"
            f"TAG: {rec['tag']}\n"
            f"GROUP: {rec['group']}\n"
            f"Facet: {rec.get('facet', '')}\n"
            f"Section: {rec['section']}\n"
            f"Subsection: {rec['subsection']}\n\n"
            f"Chars: {rec['chars']}  Tokens: {rec['tokens']} ({_TOKENIZER_LABEL})\n\n"
            f"{rec['text']}\n"
        )
        self._set_explorer_detail_text(detail)

    def _refresh_preset_help(self) -> None:
        preset_name = self.preset_var.get().strip()
        selected = PRESETS.get(preset_name)
        if selected is None:
            self.preset_help_var.set("Preset meaning: not recognised in current list.")
            return
        off_groups = sorted(set(KNOWN_GROUPS) - set(selected), key=lambda x: KNOWN_GROUPS.index(x))
        if not off_groups:
            self.preset_help_var.set(
                f"Preset meaning: baseline, all {len(KNOWN_GROUPS)} groups ON (no ablation)."
            )
            return
        counts = getattr(self, "_group_rule_counts", {})
        empty_off = [group for group in off_groups if int(counts.get(group, 0)) == 0]
        live_off = [group for group in off_groups if group not in empty_off]
        if live_off and empty_off:
            self.preset_help_var.set(
                "Preset meaning: single compile with these groups OFF: "
                + ", ".join(live_off)
                + ". Groups with no tagged rules also OFF: "
                + ", ".join(empty_off)
                + "."
            )
            return
        if empty_off and not live_off:
            self.preset_help_var.set(
                "Preset meaning: selected OFF groups have no tagged rules in the current source, so this preset currently has no effect: "
                + ", ".join(empty_off)
                + "."
            )
            return
        self.preset_help_var.set(f"Preset meaning: single compile with these groups OFF: {', '.join(off_groups)}.")

    def _refresh_phase_help(self) -> None:
        mode = self.batch_mode_var.get().strip()
        self.phase_help_var.set(PHASE_EXPLANATIONS.get(mode, "Phase explanation not available."))

    def _on_batch_mode_changed(self) -> None:
        self._refresh_phase_help()
        self._refresh_preset_options_for_batch_mode()
        self._refresh_phase_button_styles()

    def _refresh_preset_options_for_batch_mode(self) -> None:
        if self.preset_combo is None:
            return
        mode = self.batch_mode_var.get().strip()
        options = PRESET_OPTIONS_BY_BATCH_MODE.get(mode, list(PRESETS.keys()))
        options = [name for name in options if name in PRESETS]
        if not options:
            options = list(PRESETS.keys())
        self.preset_combo.configure(values=options, height=min(len(options), 20))
        has_baseline = "00 Baseline (include all groups)" in options
        ablation_count = len(options) - 1 if has_baseline else len(options)
        if has_baseline:
            self.preset_count_var.set(f"Count: {len(options)} options ({ablation_count} ablations + baseline)")
        else:
            self.preset_count_var.set(f"Count: {len(options)} options ({ablation_count} ablations)")
        current = self.preset_var.get().strip()
        if current not in options:
            self.preset_var.set(options[0])

    def _browse_input(self) -> None:
        path = filedialog.askopenfilename(title="Choose DSL source file", filetypes=[("All files", "*.*")])
        if path:
            self.input_var.set(path)
            self._refresh_stats()

    def _browse_output(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Choose output file",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            self.output_var.set(path)
            self._refresh_stats()

    @staticmethod
    def _file_stats(path: Path) -> str:
        if not path.exists():
            return "missing"
        if not path.is_file():
            return "not a file"
        try:
            byte_size = path.stat().st_size
            text = path.read_text(encoding="utf-8")
            line_count = len(text.splitlines())
            char_count = len(text)
            heading_count = sum(1 for line in text.splitlines() if line.startswith("#"))
            return f"{byte_size} bytes, {line_count} lines, {char_count} chars, {heading_count} headings"
        except Exception:
            return "unreadable"

    def _refresh_stats(self) -> None:
        in_path = Path(self.input_var.get().strip())
        out_path = Path(self.output_var.get().strip())
        in_stats = self._file_stats(in_path)
        out_stats = self._file_stats(out_path)
        self.stats_var.set(f"Input: {in_path.name} ({in_stats})\n" f"Output: {out_path.name} ({out_stats})")

    def _set_inspector_text(self, title: str, lines: list[str]) -> None:
        if self.inspector_widget is None:
            return
        body = [title, "-" * len(title)] + lines[:MAX_INSPECTOR_LINES]
        if len(lines) > MAX_INSPECTOR_LINES:
            body.append(f"... ({len(lines) - MAX_INSPECTOR_LINES} more lines)")
        text = "\n".join(body) + "\n"
        self.inspector_widget.config(state="normal")
        self.inspector_widget.delete("1.0", tk.END)
        self.inspector_widget.insert(tk.END, text)
        self.inspector_widget.see("1.0")
        self.inspector_widget.config(state="disabled")

    def _toggle_advanced_controls(self) -> None:
        if not hasattr(self, "advanced_tools_row"):
            return
        if self.show_advanced_var.get():
            self.advanced_tools_row.grid()
        else:
            self.advanced_tools_row.grid_remove()

    def _select_all(self) -> None:
        if self._job_running:
            return
        for var in self.group_vars.values():
            var.set(True)
        self._enforce_baseline_lock()
        self._refresh_all_group_visuals()
        self._refresh_dependency_status()
        self._refresh_warning_badge()
        self._refresh_estimate()

    def _select_none(self) -> None:
        if self._job_running:
            return
        for var in self.group_vars.values():
            var.set(False)
        self._enforce_baseline_lock()
        self._refresh_all_group_visuals()
        self._refresh_dependency_status()
        self._refresh_warning_badge()
        self._refresh_estimate()

    def _select_all_example_facets(self) -> None:
        if self._job_running:
            return
        for var in self.example_facet_vars.values():
            var.set(True)
        self._refresh_all_example_facet_visuals()
        self._update_group_interactivity()
        self._refresh_warning_badge()
        self._refresh_estimate()
        self.status_var.set("All example facets ON for single compile.")

    def _select_none_example_facets(self) -> None:
        if self._job_running:
            return
        for var in self.example_facet_vars.values():
            var.set(False)
        self._refresh_all_example_facet_visuals()
        self._update_group_interactivity()
        self._refresh_warning_badge()
        self._refresh_estimate()
        self.status_var.set("All semantic example facets OFF for single compile.")

    def _on_apply_preset(self) -> None:
        if self._job_running:
            return
        self._apply_preset(self.preset_var.get())

    def _on_apply_custom_expression(self) -> None:
        if self._job_running:
            return
        expr = self.custom_expr_var.get().strip()
        if not expr:
            messagebox.showerror("Empty expression", "Enter a custom expression first.")
            return

        self._expr_undo_stack.append(set(self._selected_groups()))
        selected, unknown, actions = self._parse_custom_expression(expr)
        if unknown:
            if self._expr_undo_stack:
                self._expr_undo_stack.pop()
            bad = ", ".join(unknown)
            messagebox.showerror(
                "Unknown token(s)",
                f"Unknown token(s) in expression:\n{bad}\n\nUse the i button for syntax examples.",
            )
            return

        for group, var in self.group_vars.items():
            var.set(group in selected)
        self._enforce_baseline_lock()
        self._refresh_all_group_visuals()
        self._refresh_dependency_status()
        self._refresh_warning_badge()
        self._refresh_estimate()
        self._add_recent_expression(expr)

        selected_sorted = sorted(selected, key=lambda x: KNOWN_GROUPS.index(x))
        excluded = sorted(set(KNOWN_GROUPS) - set(selected_sorted), key=lambda x: KNOWN_GROUPS.index(x))
        self.status_var.set(f"Custom expression applied ({len(selected_sorted)} ON, {len(excluded)} OFF).")
        self._set_inspector_text(
            "Custom Expression Applied",
            [
                f"Expression: {expr}",
                f"Groups ON: {len(selected_sorted)}",
                f"Groups OFF: {len(excluded)}",
                "Actions parsed:",
            ] + [f"- {item}" for item in actions[:30]],
        )
        self._append_log(
            "Custom expression applied",
            extra_lines=[f"expr={expr}", f"on={len(selected_sorted)}", f"off={len(excluded)}"],
        )

    def _copy_expression_from_selection(self) -> None:
        selected = sorted(self._selected_groups(), key=lambda x: KNOWN_GROUPS.index(x))
        excluded = [group for group in KNOWN_GROUPS if group not in selected]
        if not selected:
            expr = "NONE"
        elif not excluded:
            expr = "ALL"
        elif len(excluded) <= len(selected):
            expr = "ALL " + " ".join(f"-{group}" for group in excluded)
        else:
            expr = "NONE " + " ".join(f"+{group}" for group in selected)
        self.custom_expr_var.set(expr)
        self.clipboard_clear()
        self.clipboard_append(expr)
        self.status_var.set("Expression copied from current ticks and copied to clipboard.")
        self._append_log("Copied expression from current selection", extra_lines=[expr])

    def _undo_last_expression_apply(self) -> None:
        if not self._expr_undo_stack:
            self.status_var.set("Undo expression: no previous expression state.")
            return
        previous = self._expr_undo_stack.pop()
        for group, var in self.group_vars.items():
            var.set(group in previous)
        self._enforce_baseline_lock()
        self._refresh_all_group_visuals()
        self._refresh_dependency_status()
        self._refresh_warning_badge()
        self._refresh_estimate()
        self.status_var.set("Reverted last expression apply.")
        self._append_log("Undo expression applied")

    def _apply_favorite_expression(self) -> None:
        key = self.favorite_expr_var.get().strip()
        expr = FAVORITE_EXPRESSIONS.get(key)
        if not expr:
            self.status_var.set("Favorite expression not found.")
            return
        self.custom_expr_var.set(expr)
        self._on_apply_custom_expression()

    def _use_recent_expression(self) -> None:
        expr = self.recent_expr_var.get().strip()
        if not expr:
            self.status_var.set("No recent expression selected.")
            return
        self.custom_expr_var.set(expr)
        self._on_apply_custom_expression()

    def _add_recent_expression(self, expr: str) -> None:
        value = expr.strip()
        if not value:
            return
        self._recent_expressions = [item for item in self._recent_expressions if item != value]
        self._recent_expressions.insert(0, value)
        self._recent_expressions = self._recent_expressions[:MAX_RECENT_EXPRESSIONS]
        self._update_recent_expression_combo()

    def _update_recent_expression_combo(self) -> None:
        if self.recent_combo is None:
            return
        self.recent_combo.configure(values=self._recent_expressions)
        if self._recent_expressions:
            self.recent_expr_var.set(self._recent_expressions[0])

    def _on_lock_baseline_toggle(self) -> None:
        self._enforce_baseline_lock()
        self._refresh_all_group_visuals()
        self._refresh_warning_badge()
        self._refresh_estimate()
        if self.lock_baseline_var.get():
            self.status_var.set("Baseline lock ON: critical groups cannot be turned off.")
        else:
            self.status_var.set("Baseline lock OFF.")

    def _is_group_locked(self, group: str) -> bool:
        return self.lock_baseline_var.get() and group in BASELINE_LOCK_GROUPS

    def _enforce_baseline_lock(self) -> None:
        if not self.lock_baseline_var.get():
            return
        for group in BASELINE_LOCK_GROUPS:
            if group in self.group_vars:
                self.group_vars[group].set(True)

    def _parse_custom_expression(self, expr: str) -> tuple[set[str], list[str], list[str]]:
        tokens = [t for t in re.split(r"[,\s;]+", expr.strip()) if t]
        known_upper = {group.upper(): group for group in KNOWN_GROUPS}
        selected = self._selected_groups()
        unknown: list[str] = []
        actions: list[str] = []

        for token in tokens:
            upper = token.upper()
            if upper in ("ALL", "BASELINE"):
                selected = set(KNOWN_GROUPS)
                actions.append("ALL -> set all groups ON")
                continue
            if upper == "NONE":
                selected = set()
                actions.append("NONE -> set all groups OFF")
                continue

            sign = "+"
            name = token
            if token[0] in "+-!":
                sign = token[0]
                name = token[1:]
            if not name:
                unknown.append(token)
                continue

            mapped = known_upper.get(name.upper())
            if mapped is None:
                unknown.append(token)
                continue

            if sign in ("-", "!"):
                selected.discard(mapped)
                actions.append(f"OFF {mapped}")
            else:
                selected.add(mapped)
                actions.append(f"ON {mapped}")

        return selected, unknown, actions

    @staticmethod
    def _show_custom_expression_help() -> None:
        examples = (
            "Custom expression quick help\n\n"
            "Scope:\n"
            "  - Expressions filter GROUPS only (not TAGs).\n\n"
            "Syntax:\n"
            "  - Tokens are applied left-to-right.\n"
            "  - Separators: space, comma or semicolon.\n"
            "  - ALL or BASELINE: all groups ON\n"
            "  - NONE: all groups OFF\n"
            "  - +GROUP: turn group ON\n"
            "  - -GROUP or !GROUP: turn group OFF\n"
            "  - GROUP: shorthand for +GROUP\n\n"
            "60-second flow:\n"
            "  1) Type: ALL -LOGIC_S4\n"
            "  2) Click Apply Expression\n"
            "  3) Click Compile Selected\n\n"
            "Typical examples:\n"
            "  ALL -LOGIC_S4\n"
            "  BASELINE -EXAMPLES -MEMORY\n"
            "  NONE +CORE +LOGIC +LOGIC_S1 +LOGIC_S2 +LOGIC_S3 +LOGIC_S5 +OUTPUT +STYLE +SECURITY\n"
            "  -RED -SECURITY\n"
            "  +LOGIC_S4\n\n"
            "Dependency behavior:\n"
            "  - Strict dependency lint OFF: compile continues with warnings.\n"
            "  - Strict dependency lint ON: compile is blocked until fixed.\n\n"
            "Full reference: ALAN_EXPRESSIONS.md"
        )
        messagebox.showinfo("Custom Expression Help", examples)

    def _set_batch_mode_from_button(self, mode: str, phase_label: str) -> None:
        if self._job_running:
            return
        self.batch_mode_var.set(mode)
        scenarios = self._active_batch_scenarios()
        self.status_var.set(f"{phase_label} selected ({len(scenarios)} scenarios + baseline).")

    def _refresh_phase_button_styles(self) -> None:
        selected_mode = self.batch_mode_var.get().strip()
        for mode, btn in self.phase_buttons.items():
            base_label = self.phase_button_labels.get(mode, "Phase")
            if mode == selected_mode:
                btn.set_text(f"\u2713 {base_label}")
                btn.set_palette(
                    normal_bg="#1f7a3f",
                    normal_fg="white",
                    hover_bg="#166534",
                    press_bg="#14532d",
                    border_color="#14532d",
                )
            else:
                btn.set_text(base_label)
                btn.set_palette(
                    normal_bg="#f3f4f6",
                    normal_fg="#2b2b2b",
                    hover_bg="#e5e7eb",
                    press_bg="#dbe0e7",
                    border_color="#b7b7b7",
                )

    def _apply_preset(self, preset_name: str) -> None:
        selected = PRESETS.get(preset_name, set(KNOWN_GROUPS))
        for group, var in self.group_vars.items():
            var.set(group in selected)
        self._enforce_baseline_lock()
        self._refresh_all_group_visuals()
        self._refresh_dependency_status()
        self._refresh_warning_badge()
        self._refresh_estimate()

    def _selected_groups(self) -> set[str]:
        return {group for group, var in self.group_vars.items() if var.get()}

    def _on_group_toggle(self, group: str) -> None:
        if self._is_group_locked(group):
            self.group_vars[group].set(True)
            self.status_var.set(f"{group} is baseline-locked.")
        self._refresh_group_visual(group)
        self._refresh_dependency_status()
        self._refresh_warning_badge()
        self._refresh_estimate()

    def _on_example_facet_toggle(self, facet: str) -> None:
        self._refresh_example_facet_visual(facet)
        self._refresh_example_facet_info()
        self._refresh_warning_badge()
        self._refresh_estimate()

    def _toggle_example_facet_from_icon(self, facet: str) -> None:
        if self._job_running:
            return
        var = self.example_facet_vars.get(facet)
        if var is None:
            return
        var.set(not var.get())
        self._on_example_facet_toggle(facet)

    def _toggle_group_from_icon(self, group: str) -> None:
        if self._job_running:
            return
        if self._is_group_locked(group):
            self.status_var.set(f"{group} is baseline-locked.")
            return
        self.group_vars[group].set(not self.group_vars[group].get())
        self._refresh_group_visual(group)
        self._refresh_dependency_status()
        self._refresh_warning_badge()
        self._refresh_estimate()

    def _refresh_all_group_visuals(self) -> None:
        for group in KNOWN_GROUPS:
            self._refresh_group_visual(group)
        self._update_group_interactivity()

    def _refresh_group_visual(self, group: str) -> None:
        is_on = self.group_vars[group].get()
        symbol = self.group_symbol_labels.get(group)
        text_chk = self.group_text_checks.get(group)
        if symbol is None or text_chk is None:
            return

        text_chk.config(text=self._group_checkbox_text(group))
        if is_on:
            symbol.config(text="\u2713", fg=SUCCESS)
            text_chk.config(font=self.font_normal, fg=TEXT_PRIMARY, activeforeground=TEXT_PRIMARY)
        else:
            symbol.config(text="\u2717", fg=DANGER)
            text_chk.config(font=self.font_italic, fg=TEXT_MUTED, activeforeground=TEXT_MUTED)

    def _set_busy(self, busy: bool) -> None:
        self._job_running = busy
        state = "disabled" if busy else "normal"
        for btn in [
            self.btn_compile,
            self.btn_batch,
            self.btn_preflight,
            self.btn_preview_diff,
            self.btn_preview_batch,
            self.btn_autofix,
            self.btn_apply_preset,
            self.btn_apply_expr,
            self.btn_expr_help,
            self.btn_copy_expr,
            self.btn_undo_expr,
            self.btn_apply_favorite,
            self.btn_use_recent,
            self.btn_compare_last,
            self.btn_select_all,
            self.btn_select_none,
            self.btn_explorer_refresh,
            self.btn_explorer_apply,
            self.btn_explorer_clear,
        ]:
            if btn is not None:
                if isinstance(btn, RoundedButton):
                    btn.set_enabled(not busy)
                else:
                    btn.config(state=state)
        if self.preset_combo is not None:
            self.preset_combo.config(state="disabled" if busy else "readonly")
        if self.favorite_combo is not None:
            self.favorite_combo.config(state="disabled" if busy else "readonly")
        if self.recent_combo is not None:
            self.recent_combo.config(state="disabled" if busy else "readonly")
        if self.explorer_metric_combo is not None:
            self.explorer_metric_combo.config(state="disabled" if busy else "readonly")
        for phase_btn in self.phase_buttons.values():
            phase_btn.set_enabled(not busy)
        for header in self.group_block_headers.values():
            header.config(state="disabled" if busy else "normal", cursor="arrow" if busy else "hand2")
        self._update_group_interactivity()
        if self.progress_bar is not None:
            if busy:
                self.progress_bar.grid()
                self.progress_bar.start(12)
            else:
                self.progress_bar.stop()
                self.progress_bar.grid_remove()

    def _update_group_interactivity(self) -> None:
        for group, text_chk in self.group_text_checks.items():
            if self._job_running or self._is_group_locked(group):
                text_chk.config(state="disabled")
            else:
                text_chk.config(state="normal")
        facet_state = "disabled" if self._job_running else "normal"
        for chk in self.example_facet_checks.values():
            chk.config(state=facet_state)
        for symbol in self.example_facet_symbol_labels.values():
            symbol.config(cursor="arrow" if self._job_running else "hand2")
        for btn in [self.btn_example_facets_all, self.btn_example_facets_none]:
            if btn is not None:
                btn.config(state=facet_state)
