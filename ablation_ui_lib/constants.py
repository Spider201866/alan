from __future__ import annotations

import re
from pathlib import Path

from compile_DSL import (
    EXAMPLE_CHILD_GROUPS as DSL_EXAMPLE_CHILD_GROUPS,
    KNOWN_GROUPS,
    MEMORY_CHILD_GROUPS as DSL_MEMORY_CHILD_GROUPS,
)


GROUP_CODE = {group: f"{idx:02d}" for idx, group in enumerate(KNOWN_GROUPS, start=1)}

GROUP_SHORT = {
    "CORE": "agent identity, mission and top-level priorities",
    "LOGIC": "step framework, order and progression mechanics (parent switch)",
    "LOGIC_S1": "logic step 1 core details and missing-data capture",
    "LOGIC_S2": "logic step 2 focused follow-up questioning behavior",
    "LOGIC_S3": "logic step 3 weighted differentials and validation question",
    "LOGIC_S4": "logic step 4 reflection and contradiction checks",
    "LOGIC_S5": "logic step 5 final diagnosis and management output",
    "OUTPUT": "hard response limits such as word and question caps",
    "STYLE": "language, punctuation and tone behavior rules",
    "RED": "red-flag detection and urgent escalation priority",
    "TOOLS": "tool usage behavior and fallback instructions",
    "SCOPE": "allowed domain boundaries and refusal scope",
    "CHECKS": "validation, contradiction handling and sanity checks",
    "LISTS": "controlled enumerations and reference lists",
    "EXAMPLES": "worked dialogue examples and response patterns",
    "MEMORY": "clinical reference facts, heuristics and reminders",
    "SECURITY": "persona defense and off-topic handling",
    "EX_FULL": "long-form examples for richer demonstrations",
    "EX_SHORT": "compact examples for quick behavior cues",
    "EX_EYE": "reserved eye-tagged example subgroup (currently untagged)",
    "EX_ENT": "reserved ENT-tagged example subgroup (currently untagged)",
    "EX_DERM": "reserved dermatology-tagged example subgroup (currently untagged)",
    "EX_CHILD": "reserved child-tagged example subgroup (currently untagged)",
    "EX_VET": "reserved veterinary-tagged example subgroup (currently untagged)",
    "MEM_EYE": "ophthalmology memory block",
    "MEM_ENT": "ENT memory block",
    "MEM_DERM": "dermatology memory block",
    "MEM_CHILD": "child-focused memory block",
    "MEM_VET": "veterinary memory block",
    "MEM_RED": "red-flag memory block and safety cues",
}

GROUP_BLOCKS: list[tuple[str, list[str]]] = [
    ("AGENT/ROLE Core", ["CORE", "SCOPE", "TOOLS", "OUTPUT", "STYLE", "CHECKS", "LISTS", "RED"]),
    ("LOGIC", ["LOGIC", "LOGIC_S1", "LOGIC_S2", "LOGIC_S3", "LOGIC_S4", "LOGIC_S5"]),
    ("EXAMPLES", ["EXAMPLES", "EX_FULL", "EX_SHORT", "EX_EYE", "EX_ENT", "EX_DERM", "EX_CHILD", "EX_VET"]),
    ("MEMORY", ["MEMORY", "MEM_EYE", "MEM_ENT", "MEM_DERM", "MEM_CHILD", "MEM_VET", "MEM_RED"]),
    ("SECURITY", ["SECURITY"]),
]

PHASE1_SCREENING_ABLATIONS = [
    ("p1_no_RED", {"RED"}),
    ("p1_no_SECURITY", {"SECURITY"}),
    ("p1_no_OUTPUT", {"OUTPUT"}),
    ("p1_no_LOGIC", {"LOGIC"}),
    ("p1_no_LOGIC_S4", {"LOGIC_S4"}),
    ("p1_no_LOGIC_S5", {"LOGIC_S5"}),
    ("p1_no_EXAMPLES", {"EXAMPLES"}),
    ("p1_no_MEMORY", {"MEMORY"}),
    ("p1_no_CHECKS", {"CHECKS"}),
    ("p1_no_SCOPE", {"SCOPE"}),
    ("p1_no_TOOLS", {"TOOLS"}),
    ("p1_no_RED_SECURITY", {"RED", "SECURITY"}),
]

# Phase 2 is intentionally editable: swap these with top 4-6 Phase 1 signals after screening.
PHASE2_CONFIRMATION_ABLATIONS = [
    ("p2_no_RED", {"RED"}),
    ("p2_no_LOGIC", {"LOGIC"}),
    ("p2_no_OUTPUT", {"OUTPUT"}),
    ("p2_no_MEMORY", {"MEMORY"}),
    ("p2_no_EXAMPLES", {"EXAMPLES"}),
    ("p2_no_LOGIC_S5", {"LOGIC_S5"}),
]

BATCH_SCENARIO_SETS: dict[str, list[tuple[str, set[str]]]] = {
    "Phase 1 (Screening 12)": PHASE1_SCREENING_ABLATIONS,
    "Phase 2 (Confirmation 6)": PHASE2_CONFIRMATION_ABLATIONS,
}


def all_groups() -> set[str]:
    return set(KNOWN_GROUPS)


def groups_without(*to_remove: str) -> set[str]:
    base = all_groups()
    for group in to_remove:
        base.discard(group)
    return base


PRESETS = {
    "00 Baseline (include all groups)": all_groups(),
    "01 No CORE (test identity/priority contribution)": groups_without("CORE"),
    "02 No SCOPE (test domain-boundary contribution)": groups_without("SCOPE"),
    "03 No TOOLS (test tool-rule contribution)": groups_without("TOOLS"),
    "04 No OUTPUT (test hard output constraints contribution)": groups_without("OUTPUT"),
    "05 No STYLE (test language/tone contribution)": groups_without("STYLE"),
    "06 No CHECKS (test sanity-check contribution)": groups_without("CHECKS"),
    "07 No LISTS (test controlled-list contribution)": groups_without("LISTS"),
    "08 No RED (test safety escalation contribution)": groups_without("RED"),
    "09 No LOGIC (test step-order contribution)": groups_without("LOGIC"),
    "09a No LOGIC_S1 (step 1 core details)": groups_without("LOGIC_S1"),
    "09b No LOGIC_S2 (step 2 questions)": groups_without("LOGIC_S2"),
    "09c No LOGIC_S3 (step 3 differentials)": groups_without("LOGIC_S3"),
    "09d No LOGIC_S4 (step 4 reflection)": groups_without("LOGIC_S4"),
    "09e No LOGIC_S5 (step 5 diagnosis/plan)": groups_without("LOGIC_S5"),
    "10 No EXAMPLES (test example contribution)": groups_without("EXAMPLES"),
    "11 No MEMORY (test reference-knowledge contribution)": groups_without("MEMORY"),
    "12 No SECURITY (test refusal/persona guard contribution)": groups_without("SECURITY"),
    "13 No EX_FULL (keep EX_SHORT examples)": groups_without("EX_FULL"),
    "14 No EX_EYE (keep other EX_* examples)": groups_without("EX_EYE"),
    "15 No MEM_RED (keep other MEM_* memory)": groups_without("MEM_RED"),
    "20 No SAFETY block (RED+SECURITY+CHECKS+OUTPUT)": groups_without("RED", "SECURITY", "CHECKS", "OUTPUT"),
    "21 No REASONING block (LOGIC+LISTS)": groups_without("LOGIC", "LISTS"),
    "22 No KNOWLEDGE block (MEMORY+MEM_*)": groups_without(
        "MEMORY",
        "MEM_EYE",
        "MEM_ENT",
        "MEM_DERM",
        "MEM_CHILD",
        "MEM_VET",
        "MEM_RED",
    ),
    "23 No EXAMPLES block (EXAMPLES+EX_*)": groups_without(
        "EXAMPLES",
        "EX_FULL",
        "EX_SHORT",
        "EX_EYE",
        "EX_ENT",
        "EX_DERM",
        "EX_CHILD",
        "EX_VET",
    ),
    "24 No SCOPE+TOOLS block": groups_without("SCOPE", "TOOLS"),
    "30 No RED+SECURITY": groups_without("RED", "SECURITY"),
    "31 No LOGIC+OUTPUT": groups_without("LOGIC", "OUTPUT"),
    "32 No LOGIC+CHECKS": groups_without("LOGIC", "CHECKS"),
    "33 No EXAMPLES+MEMORY": groups_without("EXAMPLES", "MEMORY"),
    "34 No SCOPE+TOOLS (interaction)": groups_without("SCOPE", "TOOLS"),
    "40 No EX_EYE (fine-grain)": groups_without("EX_EYE"),
    "41 No EX_ENT": groups_without("EX_ENT"),
    "42 No EX_DERM": groups_without("EX_DERM"),
    "43 No EX_CHILD": groups_without("EX_CHILD"),
    "44 No EX_VET": groups_without("EX_VET"),
    "45 No MEM_EYE": groups_without("MEM_EYE"),
    "46 No MEM_ENT": groups_without("MEM_ENT"),
    "47 No MEM_DERM": groups_without("MEM_DERM"),
    "48 No MEM_CHILD": groups_without("MEM_CHILD"),
    "49 No MEM_RED (fine-grain)": groups_without("MEM_RED"),
}

PHASE1_PRESET_NAMES = [
    "00 Baseline (include all groups)",
    "08 No RED (test safety escalation contribution)",
    "12 No SECURITY (test refusal/persona guard contribution)",
    "04 No OUTPUT (test hard output constraints contribution)",
    "09 No LOGIC (test step-order contribution)",
    "09d No LOGIC_S4 (step 4 reflection)",
    "09e No LOGIC_S5 (step 5 diagnosis/plan)",
    "10 No EXAMPLES (test example contribution)",
    "11 No MEMORY (test reference-knowledge contribution)",
    "06 No CHECKS (test sanity-check contribution)",
    "02 No SCOPE (test domain-boundary contribution)",
    "03 No TOOLS (test tool-rule contribution)",
    "30 No RED+SECURITY",
]

PHASE2_PRESET_NAMES = [
    "00 Baseline (include all groups)",
    "08 No RED (test safety escalation contribution)",
    "09 No LOGIC (test step-order contribution)",
    "04 No OUTPUT (test hard output constraints contribution)",
    "11 No MEMORY (test reference-knowledge contribution)",
    "10 No EXAMPLES (test example contribution)",
    "09e No LOGIC_S5 (step 5 diagnosis/plan)",
]

PRESET_OPTIONS_BY_BATCH_MODE: dict[str, list[str]] = {
    "Phase 1 (Screening 12)": PHASE1_PRESET_NAMES,
    "Phase 2 (Confirmation 6)": PHASE2_PRESET_NAMES,
}

PHASE_EXPLANATIONS: dict[str, str] = {
    "Phase 1 (Screening 12)": (
        "Phase 1 screening: baseline + 12 targeted ablations on a disjoint case set "
        "(core safety, logic, examples, memory and scope/tool factors). "
        "Current manual ticks/preset affect single compile only, not batch outputs."
    ),
    "Phase 2 (Confirmation 6)": (
        "Phase 2 confirmation: baseline + 6 shortlisted ablations on a new disjoint case set. "
        "Update this shortlist after Phase 1 using measured effect sizes. "
        "Current manual ticks/preset affect single compile only, not batch outputs."
    ),
}

LOG_FILE = Path("logs") / "ablation_ui_runlog.txt"
LOG_JSONL_FILE = Path("logs") / "ablation_ui_runlog.jsonl"
RUNS_DIR = Path("runs")
MAX_LOG_LINES = 500
MAX_INSPECTOR_LINES = 200

ALLOWED_SECTION_CODES = {"AGT", "ROL", "LOG", "EXM", "MEM", "DEF"}
ALLOWED_TAGS = {
    "META",
    "SCOPE",
    "STEP",
    "LIMIT",
    "STYLE",
    "TOOL",
    "DATA",
    "CHECK",
    "TERM",
    "RED",
    "LIST",
    "DO",
    "DONT",
    "EX",
    "NOTE",
}
WRAPPED_RULE_RE = re.compile(r"^\{([A-Z]{3}-\d{3,4}[A-Z]?), ([A-Z_]+), ([A-Z_]+)\} .+$")

EXAMPLE_CHILD_GROUPS = frozenset(DSL_EXAMPLE_CHILD_GROUPS)
MEMORY_CHILD_GROUPS = frozenset(DSL_MEMORY_CHILD_GROUPS)
LOGIC_STEP_GROUPS = frozenset(group for group in KNOWN_GROUPS if group.startswith("LOGIC_S"))
DEPENDENCY_CLUSTERS: dict[str, tuple[str, ...]] = {
    "EXAMPLES": tuple(group for group in KNOWN_GROUPS if group in EXAMPLE_CHILD_GROUPS),
    "MEMORY": tuple(group for group in KNOWN_GROUPS if group in MEMORY_CHILD_GROUPS),
    "LOGIC": tuple(group for group in KNOWN_GROUPS if group in LOGIC_STEP_GROUPS),
}

BASELINE_LOCK_GROUPS = {
    "CORE",
    "LOGIC",
    "OUTPUT",
    "STYLE",
    "CHECKS",
    "RED",
    "SECURITY",
}

FAVORITE_EXPRESSIONS: dict[str, str] = {
    "Baseline (all on)": "ALL",
    "Reflection off (S4)": "ALL -LOGIC_S4",
    "No examples + memory": "BASELINE -EXAMPLES -MEMORY",
    "No safety guardrails": "ALL -RED -SECURITY -CHECKS -OUTPUT",
    "Minimal scaffold": "NONE +CORE +LOGIC +OUTPUT +STYLE +SECURITY",
    "Logic steps only": "NONE +CORE +LOGIC +LOGIC_S1 +LOGIC_S2 +LOGIC_S3 +LOGIC_S4 +LOGIC_S5 +OUTPUT +STYLE +SECURITY",
}

MAX_RECENT_EXPRESSIONS = 10

TTK_BUTTON_STYLE = "Ui.TButton"
BUTTON_PADX = 10
BUTTON_PADY = 4
