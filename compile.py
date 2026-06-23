#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from prompt_compile_core import compile_markdown_lines

DEFAULT_INPUT = Path("alan_sm.md")
DEFAULT_OUTPUT = Path("alan_compiled.txt")


def build_compiled_text(lines: list[str]) -> str:
    return compile_markdown_lines(lines)


def compile_text_file(input_file: str | Path, output_file: str | Path) -> None:
    input_path = Path(input_file)
    output_path = Path(output_file)
    compiled_text = build_compiled_text(input_path.read_text(encoding="utf-8").splitlines())
    output_path.write_text(compiled_text, encoding="utf-8")
    print(f"Compiled text has been written to {output_path}.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Compile alan_sm.md into prompt-ready text while preserving Markdown structure."
    )
    parser.add_argument(
        "-i",
        "--input",
        default=str(DEFAULT_INPUT),
        help="Path to markdown source file (default: alan_sm.md).",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Path to compiled output file (default: alan_compiled.txt).",
    )
    args = parser.parse_args(argv)
    compile_text_file(args.input, args.output)


if __name__ == "__main__":
    main()
