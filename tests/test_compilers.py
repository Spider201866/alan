from __future__ import annotations

import re
import tempfile
import textwrap
import unittest
from pathlib import Path

import compile as legacy
from compile_DSL import build_compiled_text, compile_dsl_text
from export_prompt import main as export_main
from prompt_compile_core import compile_markdown_lines, strip_inline_comment


class CompilerTests(unittest.TestCase):
    def test_dsl_stripped_source_matches_gold_prompt(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        gold_text = (repo_root / "alan_sm.md").read_text(encoding="utf-8")
        dsl_text = (repo_root / "Alan_DSL").read_text(encoding="utf-8")
        wrapper_re = re.compile(r"^\{[^}]+\} (.*)$")
        stripped_lines = [
            (match.group(1) if (match := wrapper_re.match(line)) else line)
            for line in dsl_text.splitlines()
        ]
        stripped_text = "\n".join(stripped_lines)
        if dsl_text.endswith("\n"):
            stripped_text += "\n"
        self.assertEqual(stripped_text, gold_text)

    def test_strip_inline_comment_drops_comments_and_preserves_urls(self) -> None:
        self.assertIsNone(strip_inline_comment("// full line comment"))
        self.assertIsNone(strip_inline_comment("\ufeff// full line comment"))
        self.assertEqual(strip_inline_comment("hello // note"), "hello")
        self.assertEqual(strip_inline_comment("https://x/y // note"), "https://x/y")
        self.assertEqual(strip_inline_comment("https://x/y"), "https://x/y")

    def test_compile_markdown_lines_preserves_structure(self) -> None:
        lines = [
            "// comment",
            "# H1",
            "Line one",
            "- Bullet",
            "",
            "## H2",
            "Line two // note",
            "https://x/y // trailing",
        ]
        compiled = compile_markdown_lines(lines)
        self.assertEqual(
            compiled,
            "# H1\nLine one\n- Bullet\n\n## H2\nLine two\nhttps://x/y\n",
        )

    def test_compile_text_file_preserves_markdown_layout(self) -> None:
        sample = textwrap.dedent(
            """
            // comment
            ## H
            Line one
            - Bullet // note

            ### H2
            text
            """
        ).lstrip()
        with tempfile.TemporaryDirectory() as td:
            input_path = Path(td) / "in.md"
            output_path = Path(td) / "out.txt"
            input_path.write_text(sample, encoding="utf-8")
            legacy.compile_text_file(input_path, output_path)
            self.assertEqual(
                output_path.read_text(encoding="utf-8"),
                "## H\nLine one\n- Bullet\n\n### H2\ntext\n",
            )

    def test_dsl_build_compiled_text_strips_wrappers_and_preserves_structure(self) -> None:
        lines = textwrap.dedent(
            """
            # AGENT
            {AGT-001, META, CORE} // comment
            {AGT-002, SCOPE, CORE} Line one
            {AGT-003, DONT, CORE} - Bullet // note

            ## LOGIC
            {LOG-200, STEP, LOGIC} Step one
            """
        ).strip().splitlines()
        compiled = build_compiled_text(lines, enabled_groups=None, excluded_groups=set())
        self.assertEqual(compiled, "# AGENT\nLine one\n- Bullet\n\n## LOGIC\nStep one\n")

    def test_compile_dsl_text_filters_groups(self) -> None:
        sample = textwrap.dedent(
            """
            # AGENT
            {AGT-001, SCOPE, CORE} Agent line
            ## LOGIC
            {LOG-200, STEP, LOGIC} Logic step one
            """
        ).strip()
        with tempfile.TemporaryDirectory() as td:
            input_path = Path(td) / "in.dsl"
            output_path = Path(td) / "out.txt"
            input_path.write_text(sample, encoding="utf-8")
            compile_dsl_text(
                input_path,
                output_path,
                enabled_groups={"CORE"},
                excluded_groups=set(),
            )
            self.assertEqual(
                output_path.read_text(encoding="utf-8"),
                "# AGENT\nAgent line\n## LOGIC\n",
            )

    def test_export_prompt_from_markdown(self) -> None:
        sample = textwrap.dedent(
            """
            // comment
            # A
            Line
            """
        ).lstrip()
        with tempfile.TemporaryDirectory() as td:
            input_path = Path(td) / "in.md"
            output_path = Path(td) / "out.txt"
            input_path.write_text(sample, encoding="utf-8")
            export_main(["-i", str(input_path), "-o", str(output_path)])
            self.assertEqual(output_path.read_text(encoding="utf-8"), "# A\nLine\n")

    def test_export_prompt_from_dsl_supports_filters(self) -> None:
        sample = textwrap.dedent(
            """
            # AGENT
            {AGT-001, SCOPE, CORE} Agent line
            ## EXAMPLES
            {EXM-001, META, EXAMPLES} ### Shortened Part Examples
            {EXM-002, META, EX_SHORT} #### Eye
            {EXM-003, CHECK, EX_SHORT} Eye rule text
            {EXM-004, META, EX_SHORT} #### ENT
            {EXM-005, CHECK, EX_SHORT} ENT rule text
            """
        ).strip()
        with tempfile.TemporaryDirectory() as td:
            input_path = Path(td) / "in.dsl"
            output_path = Path(td) / "out.txt"
            input_path.write_text(sample, encoding="utf-8")
            export_main(
                [
                    "--dsl",
                    "-i",
                    str(input_path),
                    "-o",
                    str(output_path),
                    "--exclude-example-facets",
                    "Eye",
                ]
            )
            compiled = output_path.read_text(encoding="utf-8")
            self.assertIn("Agent line", compiled)
            self.assertNotIn("Eye rule text", compiled)
            self.assertNotIn("#### Eye", compiled)
            self.assertIn("ENT rule text", compiled)


if __name__ == "__main__":
    unittest.main()
