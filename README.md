# Alan

[![Validate](https://github.com/Spider201866/alan/actions/workflows/validate.yml/badge.svg)](https://github.com/Spider201866/alan/actions/workflows/validate.yml)

Alan is an open-source clinical prompt for eye, ear and skin learning.

Alan is a ready-to-use system prompt. It guides a language model through concise eye, ear and skin reasoning, with safety checks and a practical next step. The design is deliberately narrow: brief outputs, low-cost tool awareness and a steady point-of-care voice for low- and middle-income country (LMIC) settings and wider teaching use.

Alan is not a general medical chatbot. He is a narrow clinical intelligence: formally polite, exacting, unsentimental and faintly eccentric.

![Alan overview](assets/alan-overview.png)

## Safety Status

Alan is a learning and support prompt. It is not a medical device, diagnostic service or emergency service. Its outputs must be checked by a responsible health worker using local protocols.

Read [`SAFETY.md`](SAFETY.md) before using Alan in teaching, research or deployment.

## Quick Start

Clone the repository:

```powershell
git clone https://github.com/Spider201866/alan.git
cd alan
```

Use [`alan_compiled.txt`](alan_compiled.txt) as the system prompt or instruction prompt:

```python
from pathlib import Path

system_prompt = Path("alan_compiled.txt").read_text(encoding="utf-8")
case = "Adult with red painful eye and reduced vision."

# Send system_prompt as the model instruction.
# Send case as the user message.
```

Check the repository state:

```powershell
python validate.py
python -m unittest tests.test_compilers
```

See [`QUICKSTART.md`](QUICKSTART.md) for editing, compiling and export workflows.

## What Alan Does

- Gives eye, ear and skin learning support in a concise clinical style.
- Structures routine cases around details, questions, differentials, reflection and a diagnosis plus plan.
- Prioritises red flags, urgent escalation and unsafe-action stops before ordinary flow.
- Assumes practical examination with basic tools such as the Arclight ophthalmoscope, otoscope and dermatoscope.
- Can be used as a system prompt with hosted APIs, local model servers and provider-specific deployments.

## What Alan Does Not Do

Alan does not examine the patient, guarantee diagnosis, replace clinical judgement or provide emergency care. It should not be deployed as an unsupervised patient-facing diagnosis or treatment service.

No institutional endorsement by the University of St Andrews is implied.

## Repository Map

- [`alan_sm.md`](alan_sm.md): canonical human-editable source prompt.
- [`alan_compiled.txt`](alan_compiled.txt): ready-to-use prompt text.
- [`Alan_DSL`](Alan_DSL): DSL-wrapped source with stable IDs, TAGs and GROUPs.
- [`Alan_dsl_complied.txt`](Alan_dsl_complied.txt): historic DSL compiled output. The spelling is retained intentionally.
- [`Alan_dsl_compiled.txt`](Alan_dsl_compiled.txt): correctly spelt alias of the DSL compiled output.
- [`DSL.md`](DSL.md): DSL v13 specification and workflow notes.
- [`compile.py`](compile.py): legacy compiler from `alan_sm.md`.
- [`compile_DSL.py`](compile_DSL.py): primary DSL compiler for active workflow.
- [`export_prompt.py`](export_prompt.py): optional exporter for paste-ready prompt files.
- [`validate.py`](validate.py): parity, lint and compiled-output validation.
- [`ablation_ui.py`](ablation_ui.py): optional local UI for GROUP-based ablation experiments.
- [`ALAN_EXPRESSIONS.md`](ALAN_EXPRESSIONS.md): expression syntax for ablation GROUP filters.
- [`BACKGROUND.md`](BACKGROUND.md): origins, character, design principles and intended use.
- [`SAFETY.md`](SAFETY.md): safety status, intended use and deployment cautions.
- [`CONTRIBUTING.md`](CONTRIBUTING.md): rules for safe prompt edits.
- [`report.txt`](report.txt): latest local validation report.

## Validation

Run these checks before publishing prompt edits:

```powershell
python validate.py
python -m unittest tests.test_compilers
```

Validation checks that:

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
