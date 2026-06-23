#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from compile import compile_text_file
from compile_DSL import compile_dsl_text, parse_groups


def parse_facets(raw: str | None) -> set[str] | None:
    if not raw:
        return None
    facets = {part.strip() for part in raw.split(",") if part.strip()}
    return facets or None


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Export a prompt-ready file from alan_sm.md or Alan_DSL."
    )
    parser.add_argument(
        "--dsl",
        action="store_true",
        help="Export from Alan_DSL instead of alan_sm.md.",
    )
    parser.add_argument(
        "-i",
        "--input",
        default=None,
        help="Source path. Defaults to alan_sm.md, or Alan_DSL with --dsl.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output path. Defaults to alan_prompt_ready.txt or Alan_prompt_ready.txt with --dsl.",
    )
    parser.add_argument(
        "-g",
        "--groups",
        default=None,
        help="Comma-separated GROUP whitelist for DSL exports only.",
    )
    parser.add_argument(
        "--exclude-groups",
        default=None,
        help="Comma-separated GROUPs to exclude for DSL exports only.",
    )
    parser.add_argument(
        "--ablate",
        default=None,
        help="Quick ablation helper for DSL exports only.",
    )
    parser.add_argument(
        "--exclude-example-facets",
        default=None,
        help="Comma-separated example facets to exclude for DSL exports only.",
    )
    args = parser.parse_args(argv)

    dsl_only_flags = (
        args.groups,
        args.exclude_groups,
        args.ablate,
        args.exclude_example_facets,
    )
    if not args.dsl and any(value is not None for value in dsl_only_flags):
        parser.error("GROUP and example-facet filters require --dsl.")

    if args.dsl:
        input_path = Path(args.input or "Alan_DSL")
        output_path = Path(args.output or "Alan_prompt_ready.txt")
        enabled_groups = parse_groups(args.groups)
        excluded_groups = (
            parse_groups(args.exclude_groups) or set()
        ) | (parse_groups(args.ablate) or set())
        excluded_example_facets = parse_facets(args.exclude_example_facets)
        compile_dsl_text(
            input_path,
            output_path,
            enabled_groups=enabled_groups,
            excluded_groups=excluded_groups,
            excluded_example_facets=excluded_example_facets,
        )
    else:
        input_path = Path(args.input or "alan_sm.md")
        output_path = Path(args.output or "alan_prompt_ready.txt")
        compile_text_file(input_path, output_path)

    print(f"Prompt-ready export written to {output_path}.")


if __name__ == "__main__":
    main()
