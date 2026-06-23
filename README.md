# Alan

[![Validate](https://github.com/Spider201866/alan/actions/workflows/validate.yml/badge.svg)](https://github.com/Spider201866/alan/actions/workflows/validate.yml)

Alan is an open-source eye, ear and skin learning prompt for concise point-of-care guidance.

It is designed for health workers, trainers and researchers who need a portable prompt that can run across different LLM providers, APIs or local model servers. Alan is especially shaped around LMIC practice: scarce specialist support, low-cost tools, brief outputs and clear referral safety.

![Alan overview](assets/alan-overview.png)

## Safety Status

Alan is a learning and support prompt, not a medical device, diagnostic service or emergency service. Its outputs must be checked by a responsible health worker using local protocols.

Read [`SAFETY.md`](SAFETY.md) before using Alan in clinical teaching, research or deployment.

## Quick Start

Clone the repository:

```powershell
git clone https://github.com/Spider201866/alan.git
cd alan
```

Use [`alan_compiled.txt`](alan_compiled.txt) as the ready-to-run system prompt:

```python
from pathlib import Path

system_prompt = Path("alan_compiled.txt").read_text(encoding="utf-8")
case = "Adult with red painful eye and reduced vision."

# Send system_prompt as the system or instruction prompt in your chosen model provider.
# Send case as the user message.
```

Check the repository state:

```powershell
python validate.py
python -m unittest tests.test_compilers
```

See [`QUICKSTART.md`](QUICKSTART.md) for the editing and export workflow.

## What Alan Is

- A concise learning prompt for eye, ear and skin cases.
- A structured scaffold for triage, focused questions, differentials, reflection and a diagnosis plus plan.
- A model-agnostic prompt intended to work with hosted APIs, local engines or provider-specific deployments.
- A practical companion for low-cost tools such as the Arclight ophthalmoscope, otoscope and dermatoscope.
- A narrow clinical intelligence with a formally polite, exacting, terse and dryly confident voice.

## What Alan Is Not

Alan is not a replacement for local clinical judgement. It does not examine the patient, guarantee diagnosis or provide emergency care. It should not be deployed as an unsupervised patient-facing diagnosis or treatment service.

No institutional endorsement by the University of St Andrews is implied.

## Repository Guide

- [`alan_sm.md`](alan_sm.md): canonical human-editable source prompt.
- [`alan_compiled.txt`](alan_compiled.txt): ready-to-use prompt text.
- [`Alan_DSL`](Alan_DSL): DSL-wrapped source with stable IDs, TAGs and GROUPs.
- [`Alan_dsl_complied.txt`](Alan_dsl_complied.txt): historic compiled output from the DSL source. The spelling is retained intentionally.
- [`Alan_dsl_compiled.txt`](Alan_dsl_compiled.txt): correctly spelt alias of the DSL compiled output.
- [`DSL.md`](DSL.md): DSL v13 specification and workflow notes.
- [`compile.py`](compile.py): legacy compiler from `alan_sm.md`.
- [`compile_DSL.py`](compile_DSL.py): primary DSL compiler for active workflow.
- [`export_prompt.py`](export_prompt.py): optional exporter for paste-ready prompt files.
- [`validate.py`](validate.py): public validation script for parity, lint and compiled output checks.
- [`ablation_ui.py`](ablation_ui.py): optional local UI for GROUP-based ablation experiments.
- [`ALAN_EXPRESSIONS.md`](ALAN_EXPRESSIONS.md): expression syntax for ablation GROUP filters.
- [`BACKGROUND.md`](BACKGROUND.md): project background, design choices and intended use.
- [`CONTRIBUTING.md`](CONTRIBUTING.md): rules for safe prompt edits.
- [`report.txt`](report.txt): latest local validation report.

## Validate

Run these checks before publishing prompt edits:

```powershell
python validate.py
python -m unittest tests.test_compilers
```

Expected invariants:

- `Alan_DSL` stripped of wrappers matches `alan_sm.md`.
- DSL wrappers have unique stable IDs.
- No deprecated `EXS-*` IDs are present.
- `compile_DSL.py` and `compile.py` produce matching prompt text when no group filter is used.
- Committed compiled outputs match the current source.

GitHub Actions runs the same validation on pushes and pull requests.

## Licence And Citation

Alan uses a split licence:

- Prompt, DSL source, documentation and visual assets: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
- Python code and tests: MIT.

See [`LICENSE.md`](LICENSE.md) and [`CITATION.cff`](CITATION.cff).
