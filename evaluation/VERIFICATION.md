# Package verification

**Alan evaluation harness v1.0.0 · 8 September 2026**

This checks the portable release package. It is not a new 250-case clinical evaluation.

## Case bank

The updated source workbook already contained all 50 challenges in its **Extra 50** tab. The old loader still opened archived source files before applying the current spreadsheet definitions. Those lookups were redundant for the current challenge pipeline.

The public loader reads `data/cases.xlsx` directly. A comparison against the selected development configuration confirmed:

| Check | Result |
| --- | --- |
| Clinical case inputs | All 200 identical |
| Current challenge judge inputs | All 50 identical |
| Authorised worker views | All 250 identical |
| Challenge driver messages and policies | All 50 identical |
| Unique case IDs | 250 |

The workbook includes 100 eye cases, 50 ENT cases, 50 skin cases and 50 challenges. Stretch definitions and analysis tags remain in their own tabs. The retired holdout bank, earlier results and unused legacy source columns are excluded. The current case facts, screening metadata and challenge guidance are retained. Workbook totals and rendered previews were checked.

## Installation and offline checks

- Copied only the package into a separate directory and created a fresh Python environment.
- Installed the two pinned dependencies from `requirements.txt`.
- Verified setup from the separate copy and verified case loading from an unrelated working directory.
- Passed **36 Python tests**, including capacity recovery, worker disclosure boundaries, scripted challenge receipts, scoring validation and input isolation.
- Passed the JavaScript replay tests for event ordering, seeking, text reveal and keeping future scores hidden.
- Checked that no archived run, experiment folder or Git checkout is needed at runtime.

## Live route and recording check

The live preflight passed with Codex CLI **0.144.6**, Alan on GPT-5.6 Sol with medium reasoning, the worker on GPT-5.6 Terra with medium reasoning and the judges on GPT-5.6 Sol with high reasoning.

A separate three-case recording completed **EYE-001, ENT-001 and EXT-E01** in order. Each case used a different Alan conversation and only continued that conversation within its own dialogue. The frozen prompts matched the release inputs. All three result files and recordings were present and the saved-run validator passed with no errors or warnings.

This small check confirms installation, model routes, recording and assessment integration. It does not measure broad clinical reliability. The generated answers, model traces and run folders are kept outside the publication files.

## Viewer and export

- Checked desktop, tablet and phone widths: 1467, 900 and 390 pixels, with no horizontal page overflow.
- Confirmed Follow latest starts on, the worker view opens by default and the configuration shows Alan v0.2.0 with harness components v1.
- Exported the three-case recording through the viewer and played the HTML with networking disabled.
- Checked the sidebar, minimap and replay at speeds of ×500 and ×1000.
- Checked three groups of four repeated cases and a 250-case minimap using clearly labelled synthetic layout fixtures. These were display checks, not additional clinical runs.

## Packaging corrections

The saved-run validator now uses the challenge schema and Challenge Index for challenge cases, recognises the separate worker-fidelity field and distinguishes scripted driver messages from the worker's eight-word replies. It verifies the saved scores without changing them. Repeat labels are retained in the replay sidebar.

The model prompts and clinical scoring rules were not changed for packaging. Public component names start at version 1; `PROVENANCE.json` retains the development-source mapping and release checksums.

## Remaining scope

The fresh installation was exercised on Windows. The documented macOS and Linux commands have not been tested on those operating systems. Optional video capture and FFmpeg conversion were not retested; the verified export path is self-contained HTML. A full new 250-case model run has not been performed for this release package.
