#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import re
import sys
from collections import Counter
from pathlib import Path

from compile import build_compiled_text as build_markdown_compiled_text
from compile_DSL import KNOWN_GROUPS, build_compiled_text as build_dsl_compiled_text

ROOT = Path(__file__).resolve().parent

WRAPPED_RULE_RE = re.compile(
    r"^\{([A-Z]{3}-\d{3,4}[A-Z]?), ([A-Z_]+), ([A-Z_]+)\} (.*)$"
)

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


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def format_list(values: list[str], limit: int = 8) -> str:
    if not values:
        return "-"
    shown = values[:limit]
    suffix = "" if len(values) <= limit else f" ... +{len(values) - limit} more"
    return ", ".join(shown) + suffix


def strip_dsl_wrappers(dsl_text: str) -> tuple[str, list[dict[str, str | int]], list[str]]:
    stripped_lines: list[str] = []
    records: list[dict[str, str | int]] = []
    errors: list[str] = []

    for line_no, line in enumerate(dsl_text.splitlines(), start=1):
        if line.startswith("{"):
            match = WRAPPED_RULE_RE.match(line)
            if not match:
                errors.append(f"Line {line_no}: invalid wrapper format")
                stripped_lines.append(line)
                continue

            rule_id, tag, group, text = match.groups()
            records.append(
                {
                    "line_no": line_no,
                    "id": rule_id,
                    "tag": tag,
                    "group": group,
                    "section": rule_id.split("-", 1)[0],
                }
            )
            stripped_lines.append(text)
        else:
            stripped_lines.append(line)

    stripped_text = "\n".join(stripped_lines)
    if dsl_text.endswith("\n"):
        stripped_text += "\n"
    return stripped_text, records, errors


def main() -> int:
    failures: list[str] = []

    alan_sm = read_text("alan_sm.md")
    alan_dsl = read_text("Alan_DSL")
    stripped_dsl, records, wrapper_errors = strip_dsl_wrappers(alan_dsl)

    if stripped_dsl != alan_sm:
        failures.append("Alan_DSL stripped of wrappers does not match alan_sm.md")

    if wrapper_errors:
        failures.extend(wrapper_errors)

    ids = [str(record["id"]) for record in records]
    tags = [str(record["tag"]) for record in records]
    groups = [str(record["group"]) for record in records]
    sections = [str(record["section"]) for record in records]

    duplicate_ids = sorted(rule_id for rule_id, count in Counter(ids).items() if count > 1)
    unknown_sections = sorted(set(sections) - ALLOWED_SECTION_CODES)
    unknown_tags = sorted(set(tags) - ALLOWED_TAGS)
    unknown_groups = sorted(set(groups) - set(KNOWN_GROUPS))
    deprecated_ids = sorted(rule_id for rule_id in ids if rule_id.startswith("EXS-"))

    if duplicate_ids:
        failures.append(f"Duplicate DSL IDs: {format_list(duplicate_ids)}")
    if unknown_sections:
        failures.append(f"Unknown section codes: {format_list(unknown_sections)}")
    if unknown_tags:
        failures.append(f"Unknown TAG values: {format_list(unknown_tags)}")
    if unknown_groups:
        failures.append(f"Unknown GROUP values: {format_list(unknown_groups)}")
    if deprecated_ids:
        failures.append(f"Deprecated EXS-* IDs present: {format_list(deprecated_ids)}")

    compiled_from_markdown = build_markdown_compiled_text(alan_sm.splitlines())
    compiled_from_dsl = build_dsl_compiled_text(
        alan_dsl.splitlines(),
        enabled_groups=None,
        excluded_groups=set(),
    )

    if not compiled_from_markdown.strip():
        failures.append("Compiled markdown output is empty")
    if not compiled_from_dsl.strip():
        failures.append("Compiled DSL output is empty")
    if compiled_from_markdown != compiled_from_dsl:
        failures.append("compile.py and compile_DSL.py outputs differ")

    committed_markdown = read_text("alan_compiled.txt")
    committed_dsl = read_text("Alan_dsl_complied.txt")
    committed_dsl_alias = read_text("Alan_dsl_compiled.txt")

    if committed_markdown != compiled_from_markdown:
        failures.append("alan_compiled.txt is stale; run python compile.py")
    if committed_dsl != compiled_from_dsl:
        failures.append("Alan_dsl_complied.txt is stale; run python compile_DSL.py")
    if committed_dsl_alias != compiled_from_dsl:
        failures.append("Alan_dsl_compiled.txt is stale; run python compile_DSL.py")

    print("Alan validation")
    print(f"- stripped parity: {stripped_dsl == alan_sm}")
    print(f"- wrapped rules: {len(records)}")
    print(f"- unique IDs: {len(set(ids))}")
    print(f"- deprecated EXS IDs: {len(deprecated_ids)}")
    print(f"- compiled SHA-256: {sha256_text(compiled_from_markdown)}")

    if failures:
        print("\nFailures:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
