# Quick Start

This guide is for people who want to try Alan, edit the prompt or export a prompt-ready file.

## 1) Get The Repository

```powershell
git clone https://github.com/Spider201866/alan.git
cd alan
```

Alan currently uses only the Python standard library for its compiler and validation checks.

## 2) Use Alan In A Model

Use [`alan_compiled.txt`](alan_compiled.txt) as the system prompt or instruction prompt in your chosen model provider.

Minimal provider-agnostic shape:

```python
from pathlib import Path

system_prompt = Path("alan_compiled.txt").read_text(encoding="utf-8")
user_message = "Child with itchy ear, discharge and reduced hearing."

# Pass system_prompt as the model instruction.
# Pass user_message as the user case.
```

The exact API call depends on your provider. Alan itself is model-agnostic.

## 3) Edit The Prompt

For ordinary prompt edits:

1. Edit [`alan_sm.md`](alan_sm.md).
2. Reflect the same prompt text in [`Alan_DSL`](Alan_DSL) with wrappers preserved.
3. Run validation.

```powershell
python validate.py
```

Do not make silent clinical wording changes in only one source file.

## 4) Rebuild Compiled Outputs

From the plain markdown source:

```powershell
python compile.py
```

From the DSL source:

```powershell
python compile_DSL.py
```

The DSL compiler writes the historic output name [`Alan_dsl_complied.txt`](Alan_dsl_complied.txt) and the correctly spelt alias [`Alan_dsl_compiled.txt`](Alan_dsl_compiled.txt) when run with its default output path.

## 5) Export A Paste-Ready Prompt

From `alan_sm.md`:

```powershell
python export_prompt.py
```

From `Alan_DSL`:

```powershell
python export_prompt.py --dsl
```

For a group-filtered DSL export:

```powershell
python export_prompt.py --dsl --exclude-groups EXAMPLES,MEMORY -o Alan_no_examples_memory.txt
```

## 6) Validate Before Sharing

Run:

```powershell
python validate.py
python -m unittest tests.test_compilers
```

Validation checks source parity, DSL wrapper lint, deprecated IDs, compiled output freshness and cross-compiler equality.
