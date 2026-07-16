# Alan

[![Validate](https://github.com/Spider201866/alan/actions/workflows/validate.yml/badge.svg)](https://github.com/Spider201866/alan/actions/workflows/validate.yml)

*Thirty-three words. One clear plan.*

Alan is an open-source prompt scaffold that creates a concise eye, ear and skin teaching agent on top of a language model. The model is the engine; Alan is the authored layer above it, supplying persona, curated memory, safety rules, a five-step learning workflow and strict output discipline.

Alan is for teaching and supervised case-based learning. It is not a diagnostic product, medical device or emergency service. It may discuss differentials, provisional diagnoses and plans as part of a learning exercise, but it is not validated or intended to diagnose patients independently or direct treatment.

Alan was designed around constraints common in low- and middle-income country (LMIC) settings: limited specialist access, affordable examination tools, short consultations and the need for one clear next teaching step. It can also be used wherever brief, structured clinical teaching is useful.

Alan is not a general medical chatbot. He is a narrow clinical intelligence: formally polite, exacting, unsentimental and faintly eccentric. Terse, steady and dryly confident, he has a taste for order and small oddities: a useful presence with manners, memory and purpose.

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

In a chat interface, place the compiled scaffold in the system or instruction field, then enter a fictional or properly de-identified teaching case. With an API or local model server, send the scaffold as the system message and the case as the user message.

Alan can run through hosted APIs, on local hardware or on private servers. Because it is authored as text, it is portable, editable and forkable for local teaching, research or implementation needs. See [`QUICKSTART.md`](QUICKSTART.md) for editing, compiling and export workflows.

Alan can move between models, but it will not behave identically on each one. It inherits the capabilities and limitations of its underlying model. Stronger models may improve fluency and clinical reasoning, but performance varies with the model, quantisation and settings and must be tested locally.

## What Alan Does as a Learning Tool

These behaviours describe a learning process, not an automated diagnosis system.

- Creates a consistent teaching agent on top of a chosen language model engine.
- Organises eye, ear and skin case discussion into five stages: core details, focused questions, differentials, reflection and a provisional diagnosis and plan.
- Interrupts the ordinary teaching flow when red flags require urgent escalation or an unsafe action must be stopped.
- Uses curated examples and compact in-context memory to demonstrate reasoning, retain relevant details and maintain Alan's character.
- Prompts learners to interpret examination findings from accessible tools such as the Arclight ophthalmoscope, otoscope and dermatoscope.
- Produces brief, plain and structured responses for teaching in time-limited settings.

## Limits and Safety

Alan cannot examine a patient, verify the information it receives, authorise treatment or provide emergency care. Any differential, provisional diagnosis or plan it generates is part of a teaching sequence and must be checked against examination, local guidance and senior clinical judgement.

Use fictional or properly de-identified cases unless the deployment has explicit approval for handling patient-identifiable information. Do not send identifiable clinical information to a hosted model without appropriate information-governance approval.

Read [`SAFETY.md`](SAFETY.md) before using Alan in teaching, research or deployment.

No institutional endorsement by the University of St Andrews is implied.

## Start Here

- [`alan_compiled.txt`](alan_compiled.txt): ready-to-use Alan scaffold.
- [`alan_sm.md`](alan_sm.md): canonical human-editable source prompt.
- [`QUICKSTART.md`](QUICKSTART.md): use, editing, compiling and export instructions.
- [`BACKGROUND.md`](BACKGROUND.md): origins, architecture, character and design principles.
- [`SAFETY.md`](SAFETY.md): intended use, safety status and deployment cautions.

## For Maintainers

[`Alan_DSL`](Alan_DSL) wraps the canonical prompt with stable IDs, TAGs and GROUPs for traceable editing and ablation. [`compile_DSL.py`](compile_DSL.py) is the primary compiler. [`compile.py`](compile.py) is retained as the legacy compiler. See [`DSL.md`](DSL.md) and [`CONTRIBUTING.md`](CONTRIBUTING.md) before changing prompt content.

Run these checks before publishing prompt edits:

```powershell
python validate.py
python -m unittest tests.test_compilers
```

Validation checks source parity, DSL wrapper integrity, stable IDs, deprecated IDs and matching compiled outputs. GitHub Actions runs the same validation on pushes and pull requests.

## Licence and Citation

Alan uses a split licence:

- Prompt, DSL source, documentation and visual assets: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
- Python code and tests: MIT.

See [`LICENSE.md`](LICENSE.md) and [`CITATION.cff`](CITATION.cff).
