from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
from typing import Iterable, Mapping


WRAPPED_RULE_RE = re.compile(r"^\{([A-Z]{3}-\d{3,4}[A-Z]?), ([A-Z_]+), ([A-Z_]+)\} (.*)$")

SECTION_CODE_MAP = {
    "AGT": "AGENT",
    "ROL": "ROLE",
    "LOG": "LOGIC",
    "EXM": "EXAMPLES",
    "MEM": "MEMORY",
    "DEF": "SECURITY",
}

STRUCTURAL_EXAMPLE_FACETS = frozenset(
    {
        "Parent / Scaffold",
        "Short Scaffold",
        "Short / Other",
        "Full Examples",
    }
)

PREFERRED_EXAMPLE_FACET_ORDER = (
    "Eye",
    "ENT",
    "Dermatology",
    "General",
    "Post Ops",
    "Child",
    "Vet",
)


def logic_step_idx_from_values(subsection: str, group: str, rule_id: str) -> int:
    sub_l = subsection.lower()
    for idx in (1, 2, 3, 4, 5):
        if f"step {idx}" in sub_l:
            return idx
    for idx in (1, 2, 3, 4, 5):
        if group == f"LOGIC_S{idx}":
            return idx
    try:
        if rule_id.startswith("LOG-"):
            match = re.fullmatch(r"LOG-(\d{3,4})[A-Z]?", rule_id)
            if not match:
                return 0
            number = int(match.group(1))
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


def facet_for_record_values(section: str, group: str, subsection: str, rule_id: str) -> str:
    sec = section.upper()
    sub = subsection.strip()
    sub_l = sub.lower()

    if sec == "LOGIC":
        idx = logic_step_idx_from_values(sub, group, rule_id)
        return "Parent" if idx == 0 else f"Step S{idx}"
    if sec == "ROLE":
        if "medical approach" in sub_l:
            return "Medical Approach"
        if "emotional intelligence" in sub_l:
            return "Emotional Intelligence"
        return sub or "Role / Other"
    if sec == "EXAMPLES":
        child_map = {
            "EX_EYE": "Eye",
            "EX_ENT": "ENT",
            "EX_DERM": "Dermatology",
            "EX_CHILD": "Child",
            "EX_VET": "Vet",
        }
        if group == "EX_FULL":
            return "Full Examples"
        if group in child_map:
            return child_map[group]
        if "cataract post ops" in sub_l or "post op" in sub_l:
            return "Post Ops"
        if sub in {"Eye", "ENT", "Dermatology", "General"}:
            return sub
        if "shortened part examples" in sub_l:
            return "Short Scaffold"
        if group == "EX_SHORT":
            return sub or "Short / Other"
        return sub or "Parent / Scaffold"
    if sec == "MEMORY":
        mem_map = {
            "MEM_EYE": "Ophthalmology",
            "MEM_ENT": "ENT",
            "MEM_DERM": "Dermatology",
            "MEM_CHILD": "Child",
            "MEM_VET": "Vet",
            "MEM_RED": "Red Flags",
        }
        if group in mem_map:
            return mem_map[group]
        return sub or "Parent / Shared"
    if sec == "SECURITY":
        if "step reminders" in sub_l:
            return "Step Reminders"
        return "Persona / Scope"
    if sec == "AGENT":
        return sub or "Agent / Global"
    return sub or group or sec or "Other"


def _update_headings(headings: dict[int, str], md_line: str) -> None:
    stripped = md_line.lstrip()
    if not stripped.startswith("#"):
        return
    level = len(stripped) - len(stripped.lstrip("#"))
    if 1 <= level <= 4:
        headings[level] = stripped[level:].strip()
        for deeper in range(level + 1, 5):
            headings[deeper] = ""


def parse_dsl_lines(lines: Iterable[str]) -> list[dict[str, object]]:
    headings: dict[int, str] = {1: "", 2: "", 3: "", 4: ""}
    records: list[dict[str, object]] = []

    for line_no, line in enumerate(lines, start=1):
        if line.lstrip().startswith("#"):
            _update_headings(headings, line)
            continue
        match = WRAPPED_RULE_RE.match(line)
        if not match:
            continue
        rule_id, tag, group, text = match.groups()
        _update_headings(headings, text)
        section_code = rule_id.split("-", 1)[0]
        section = headings[2] or headings[1] or SECTION_CODE_MAP.get(section_code, section_code)
        subsection = headings[4] or headings[3] or ""
        records.append(
            {
                "line_no": line_no,
                "id": rule_id,
                "tag": tag,
                "group": group,
                "text": text,
                "section": section,
                "subsection": subsection,
                "chars": len(text),
                "facet": facet_for_record_values(section, group, subsection, rule_id),
            }
        )
    return records


def parse_dsl_records(path: Path) -> list[dict[str, object]]:
    return parse_dsl_lines(path.read_text(encoding="utf-8").splitlines())


def semantic_example_facet_name(record: Mapping[str, object]) -> str | None:
    if str(record.get("section", "")).upper() != "EXAMPLES":
        return None
    facet = str(record.get("facet", "")).strip()
    if not facet or facet in STRUCTURAL_EXAMPLE_FACETS:
        return None
    return facet


def ordered_semantic_example_facets(records: list[Mapping[str, object]]) -> tuple[list[str], dict[str, int]]:
    counts = Counter()
    for record in records:
        facet = semantic_example_facet_name(record)
        if facet:
            counts[facet] += 1
    preferred = [facet for facet in PREFERRED_EXAMPLE_FACET_ORDER if facet in counts]
    extras = sorted(facet for facet in counts if facet not in set(PREFERRED_EXAMPLE_FACET_ORDER))
    ordered = preferred + extras
    return ordered, {facet: counts[facet] for facet in ordered}
