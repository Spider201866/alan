#!/usr/bin/env python3
"""
Compile Alan DSL source into plain LLM-ready text while preserving Markdown layout.

Default behavior:
- Input:  Alan_DSL
- Output: Alan_dsl_complied.txt
- Include all wrapped rule lines

Optional:
- Filter wrapped rules by GROUP via --groups
- Exclude groups via --exclude-groups
- Quick single-group ablation via --ablate

Ablation quick reminder (DSL.md v13):
- Baseline compile:
  python compile_DSL.py
- Disable one group (recommended pattern):
  python compile_DSL.py --ablate EXAMPLES -o Alan_dsl_no_EXAMPLES.txt
- Disable with explicit exclude list:
  python compile_DSL.py --exclude-groups LOGIC -o Alan_dsl_no_LOGIC.txt
- Keep only a small whitelist:
  python compile_DSL.py --groups CORE,LOGIC,OUTPUT -o Alan_core_logic_output.txt
- Show supported groups:
  python compile_DSL.py --list-groups

Parent-child gating:
- LOGIC gates LOGIC_S*
- EXAMPLES gates EX_*
- MEMORY gates MEM_*
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from ablation_ui_lib.dsl_analysis import parse_dsl_lines, semantic_example_facet_name
from prompt_compile_core import compile_markdown_lines

WRAPPER_RE = re.compile(r"^\{([^}]*)\}\s(.*)$")

# DSL.md v13-aligned display/order flow:
# AGENT + ROLE -> LOGIC -> EXAMPLES -> MEMORY -> SECURITY
# (with optional LOGIC_S*, EX_* and MEM_* finer switches under parent blocks)
KNOWN_GROUPS = (
    "CORE",
    "SCOPE",
    "TOOLS",
    "OUTPUT",
    "STYLE",
    "CHECKS",
    "LISTS",
    "RED",
    "LOGIC",
    "LOGIC_S1",
    "LOGIC_S2",
    "LOGIC_S3",
    "LOGIC_S4",
    "LOGIC_S5",
    "EXAMPLES",
    "EX_FULL",
    "EX_SHORT",
    "EX_EYE",
    "EX_ENT",
    "EX_DERM",
    "EX_CHILD",
    "EX_VET",
    "MEMORY",
    "MEM_EYE",
    "MEM_ENT",
    "MEM_DERM",
    "MEM_CHILD",
    "MEM_VET",
    "MEM_RED",
    "SECURITY",
)

EXAMPLE_CHILD_GROUPS = frozenset(
    {"EX_FULL", "EX_SHORT", "EX_EYE", "EX_ENT", "EX_DERM", "EX_CHILD", "EX_VET"}
)

MEMORY_CHILD_GROUPS = frozenset(
    {"MEM_EYE", "MEM_ENT", "MEM_DERM", "MEM_CHILD", "MEM_VET", "MEM_RED"}
)


def logic_step_group_for_rule(rule_id: str) -> str | None:
    """
    Map LOGIC step rule IDs to fine-grained ablation groups.

    Step ranges in Alan_DSL:
    - Step 1: LOG-200..299
    - Step 2: LOG-300..399
    - Step 3: LOG-400..599
    - Step 4: LOG-600..799
    - Step 5: LOG-800..899
    """
    if not rule_id.startswith("LOG-"):
        return None
    match = re.fullmatch(r"LOG-(\d{3,4})[A-Z]?", rule_id)
    if not match:
        return None
    number = int(match.group(1))
    if 200 <= number <= 299:
        return "LOGIC_S1"
    if 300 <= number <= 399:
        return "LOGIC_S2"
    if 400 <= number <= 599:
        return "LOGIC_S3"
    if 600 <= number <= 799:
        return "LOGIC_S4"
    if 800 <= number <= 899:
        return "LOGIC_S5"
    return None


def required_groups_for_rule(rule_id: str, group: str) -> tuple[str, ...]:
    """
    Return group requirements for a wrapped rule line.

    Default: rule requires its own GROUP only.
    LOGIC step rules also require LOGIC parent + the corresponding LOGIC_S* child.
    EX_* rules also require EXAMPLES.
    MEM_* rules also require MEMORY.
    """
    requirements = [group]
    if group in EXAMPLE_CHILD_GROUPS and "EXAMPLES" not in requirements:
        requirements.append("EXAMPLES")
    if group in MEMORY_CHILD_GROUPS and "MEMORY" not in requirements:
        requirements.append("MEMORY")
    step_group = logic_step_group_for_rule(rule_id)
    if step_group is not None:
        if "LOGIC" not in requirements:
            requirements.append("LOGIC")
        requirements.append(step_group)
    return tuple(requirements)


def parse_groups(raw: str | None) -> set[str] | None:
    if not raw:
        return None
    groups = {part.strip() for part in raw.split(",") if part.strip()}
    return groups or None


def unwrap_dsl_line(
    line: str,
    enabled_groups: set[str] | None,
    excluded_groups: set[str],
) -> str | None:
    """
    Return:
    - string: line content to continue compiling
    - None: line should be omitted (eg filtered by GROUP)
    """
    m = WRAPPER_RE.match(line)
    if not m:
        return line

    meta = [p.strip() for p in m.group(1).split(",")]
    if len(meta) != 3:
        # Invalid wrapper, keep the raw line so issues are visible.
        return line

    rule_id, _tag, group = meta
    text = m.group(2)

    required_groups = required_groups_for_rule(rule_id, group)

    if any(req_group in excluded_groups for req_group in required_groups):
        return None
    if enabled_groups is not None and any(req_group not in enabled_groups for req_group in required_groups):
        return None
    return text


def build_compiled_text(
    lines: list[str],
    enabled_groups: set[str] | None,
    excluded_groups: set[str],
    excluded_example_facets: set[str] | None = None,
) -> str:
    excluded_example_facets = {
        facet.strip() for facet in (excluded_example_facets or set()) if facet.strip()
    }
    facet_by_line: dict[int, str] = {}
    if excluded_example_facets:
        for record in parse_dsl_lines(lines):
            facet = semantic_example_facet_name(record)
            if facet:
                facet_by_line[int(record["line_no"])] = facet

    visible_lines: list[str] = []

    for line_no, raw_line in enumerate(lines, start=1):
        if facet_by_line.get(line_no) in excluded_example_facets:
            continue

        unwrapped = unwrap_dsl_line(raw_line, enabled_groups, excluded_groups)
        if unwrapped is None:
            continue

        visible_lines.append(unwrapped)
    return compile_markdown_lines(visible_lines)


def compile_dsl_text(
    input_file: Path,
    output_file: Path,
    enabled_groups: set[str] | None,
    excluded_groups: set[str],
    excluded_example_facets: set[str] | None = None,
) -> None:
    lines = input_file.read_text(encoding="utf-8").splitlines()
    compiled_text = build_compiled_text(
        lines,
        enabled_groups=enabled_groups,
        excluded_groups=excluded_groups,
        excluded_example_facets=excluded_example_facets,
    )
    output_file.write_text(compiled_text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compile Alan DSL source into plain prompt text."
    )
    parser.add_argument(
        "-i",
        "--input",
        default="Alan_DSL",
        help="Path to DSL source file (default: Alan_DSL).",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="Alan_dsl_complied.txt",
        help="Path to compiled output file (default: Alan_dsl_complied.txt).",
    )
    parser.add_argument(
        "-g",
        "--groups",
        default=None,
        help="Comma-separated GROUP whitelist (eg CORE,LOGIC,OUTPUT). Default includes all groups.",
    )
    parser.add_argument(
        "--exclude-groups",
        default=None,
        help="Comma-separated GROUPs to exclude (eg EXAMPLES,LOGIC).",
    )
    parser.add_argument(
        "--ablate",
        default=None,
        help="Quick ablation helper: group name(s) to disable (same format as --exclude-groups).",
    )
    parser.add_argument(
        "--list-groups",
        action="store_true",
        help="Print known GROUP values from DSL.md v13 and exit.",
    )
    args = parser.parse_args()

    if args.list_groups:
        print("Known GROUP values:")
        for group in KNOWN_GROUPS:
            print(f"- {group}")
        return

    input_path = Path(args.input)
    output_path = Path(args.output)
    enabled_groups = parse_groups(args.groups)
    excluded_groups = (parse_groups(args.exclude_groups) or set()) | (parse_groups(args.ablate) or set())

    # Warn on unknown group names so ablation typos do not silently pass.
    unknown_selected = set()
    if enabled_groups is not None:
        unknown_selected |= {group for group in enabled_groups if group not in KNOWN_GROUPS}
    unknown_selected |= {group for group in excluded_groups if group not in KNOWN_GROUPS}
    for group in sorted(unknown_selected):
        print(f"Warning: group '{group}' is not in KNOWN_GROUPS.")

    # If whitelist and exclude overlap, exclusion wins.
    if enabled_groups is not None and excluded_groups:
        enabled_groups = {group for group in enabled_groups if group not in excluded_groups}

    compile_dsl_text(input_path, output_path, enabled_groups, excluded_groups)
    print(f"Compiled text has been written to {output_path}.")


if __name__ == "__main__":
    main()
