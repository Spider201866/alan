# Quick Start

This guide is for people who want to try Alan with a teaching case, edit the prompt or export a prompt-ready file.

## 1. Get the Repository

```powershell
git clone https://github.com/Spider201866/alan.git
cd alan
```

Alan currently uses only the Python standard library for its compiler and validation checks.

## 2. Use Alan for a Teaching Case

Alan is the scaffold and the language model is the engine. Use [`alan_compiled.txt`](alan_compiled.txt) as the system or instruction prompt in your chosen model interface.

Minimal provider-agnostic shape:

```python
from pathlib import Path

alan_scaffold = Path("alan_compiled.txt").read_text(encoding="utf-8")
teaching_case = "Child with itchy ear, discharge and reduced hearing."

# Pass alan_scaffold as the model instruction.
# Pass teaching_case as the user message.
```

The exact API call depends on your provider. Alan can move between hosted APIs, local hardware and private servers, but behaviour will vary with the model, quantisation and settings. Test each deployment locally.

Use fictional or properly de-identified teaching cases. Read [`SAFETY.md`](SAFETY.md) before using Alan with real case material or in teaching connected to clinical care.

## 3. Edit the Prompt

For ordinary prompt edits:

1. Edit [`alan_sm.md`](alan_sm.md).
2. Reflect the same prompt text in [`Alan_DSL`](Alan_DSL) with wrappers preserved.
3. Run validation.

```powershell
python validate.py
```

Do not make silent clinical wording changes in only one source file.

## 4. Rebuild Compiled Outputs

From the plain markdown source:

```powershell
python compile.py
```

From the DSL source:

```powershell
python compile_DSL.py
```

The DSL compiler writes the historic output name [`Alan_dsl_complied.txt`](Alan_dsl_complied.txt) and the correctly spelt alias [`Alan_dsl_compiled.txt`](Alan_dsl_compiled.txt) when run with its default output path.

## 5. Export a Paste-Ready Prompt

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

## 6. Validate Before Sharing

Run:

```powershell
python validate.py
python -m unittest tests.test_compilers
```

Validation checks source parity, DSL wrapper lint, deprecated IDs, compiled output freshness and cross-compiler equality.
