# Alan

[![Validate](https://github.com/Spider201866/alan/actions/workflows/validate.yml/badge.svg)](https://github.com/Spider201866/alan/actions/workflows/validate.yml)

Alan is an open-source scaffold for creating a concise eye, ear and skin clinical learning agent on top of a language model.

The language model is the engine. Alan is the authored layer above it: persona, memory, safety rules, clinical workflow and output discipline. It gives the engine a narrow job, a steady voice and a practical way to handle routine and urgent cases.

Alan is built for LMIC point-of-care reality: limited specialist access, low-cost tools, short consultations and workers who need the next useful step. It is also useful anywhere that clear, brief and practical clinical teaching matters.

Alan is not a general medical chatbot. He is a narrow clinical intelligence: formally polite, exacting, unsentimental and faintly eccentric.

![Alan overview](assets/alan-overview.png)

## Use Alan

Use [`alan_compiled.txt`](alan_compiled.txt) as the Alan scaffold in your system prompt or instruction prompt.

```powershell
git clone https://github.com/Spider201866/alan.git
cd alan
```

```python
from pathlib import Path

alan_scaffold = Path("alan_compiled.txt").read_text(encoding="utf-8")
case = "Adult with red painful eye and reduced vision."

# Send alan_scaffold as the system or instruction prompt.
# Send case as the user message.
```

Alan can be used with hosted APIs, local model servers or provider-specific deployments. See [`QUICKSTART.md`](QUICKSTART.md) for editing, compiling and export workflows.

## What Alan Does

- Creates a consistent clinical agent on top of a chosen language model engine.
- Guides eye, ear and skin cases through a short five-step clinical rhythm.
- Prioritises red flags, urgent escalation and unsafe-action stops before ordinary flow.
- Uses curated examples and compressed memory to steer tone, recall and clinical judgement.
- Assumes practical examination with tools such as the Arclight ophthalmoscope, otoscope and dermatoscope.
- Keeps output brief, plain and structured enough for point-of-care use.

## What Alan Does Not Do

Alan does not examine the patient, guarantee diagnosis, replace clinical judgement or provide emergency care. It should not be deployed as an unsupervised patient-facing diagnosis or treatment service.

Read [`SAFETY.md`](SAFETY.md) before using Alan in teaching, research or deployment.

No institutional endorsement by the University of St Andrews is implied.

## Repository Map

- [`alan_sm.md`](alan_sm.md): canonical human-editable source prompt.
- [`alan_compiled.txt`](alan_compiled.txt): ready-to-use Alan scaffold.
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
- [`BACKGROUND.md`](BACKGROUND.md): origins, architecture, character and design principles.
- [`CONTRIBUTING.md`](CONTRIBUTING.md): rules for safe prompt edits.
- [`SAFETY.md`](SAFETY.md): intended use, safety status and deployment cautions.
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
