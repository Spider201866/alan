#!/usr/bin/env python3
from __future__ import annotations

from collections.abc import Iterable


def strip_inline_comment(text: str) -> str | None:
    """
    Remove maintainer comments while preserving URL text.

    Rules:
    - Ignore a UTF-8 BOM if present at line start.
    - If the trimmed line starts with `//`, drop the whole line.
    - Else remove inline comments only when written as ` //...`
      (space before the slashes), which preserves `https://...` and similar.
    """
    raw = text.lstrip("\ufeff").rstrip("\n")
    trimmed = raw.strip()
    if trimmed.startswith("//"):
        return None
    marker = " //"
    idx = raw.find(marker)
    if idx != -1:
        raw = raw[:idx]
    return raw.rstrip()


def compile_markdown_lines(lines: Iterable[str]) -> str:
    """
    Preserve Markdown structure while stripping maintainer comments.
    """
    compiled_lines: list[str] = []
    for raw_line in lines:
        line = strip_inline_comment(raw_line)
        if line is None:
            continue
        compiled_lines.append(line)
    return "\n".join(compiled_lines).rstrip() + "\n"
