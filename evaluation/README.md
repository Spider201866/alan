# Alan evaluation harness

**Version 1.0.0 · 8 September 2026 · Tested on Windows**

Run recorded consultations between Alan and a simulated health worker, then assess Alan with a separate judge. The viewer shows the dialogue, worker facts, scores and replay controls.

The package includes **200 clinical cases and 50 challenges** in [Excel](data/cases.xlsx), Alan **v0.2.0** and the selected worker and judge prompts. Each harness component starts at **version 1**. Earlier development numbers remain only in the technical provenance record.

## Start here

You need Python **3.11 or later**. New evaluations also need the [Codex CLI](https://learn.chatgpt.com/docs/codex/cli), a signed-in account and access to the models in `config.json`. Model calls consume the account's usage allowance. A web browser is enough to open an exported HTML replay.

```text
git clone https://github.com/Spider201866/alan.git
cd alan/evaluation
python -m venv .venv
```

On **Windows PowerShell**:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe harness.py check
```

On **macOS or Linux** (not yet tested): use `python3 -m venv .venv` to create the environment if `python` is unavailable, then:

```sh
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python harness.py check
```

The examples below use `python`. Use the Python inside this virtual environment, or activate it first.

Install Codex using the official instructions and run `codex login` if needed. This release was checked with Codex CLI **0.144.6**. `check` verifies the required isolation flags and sign-in status without calling a model. It reports an incompatible CLI rather than weakening the isolation settings.

## Platform notes

Windows installation and the HTML viewer have been tested. macOS and Linux still need a native installation check: Python and its virtual-environment support, the Codex executable on PATH, account sign-in and browser clipboard permissions. An agent can investigate setup failures and run the included tests, but compatibility should be confirmed on the target operating system.

The optional native Outlook clipboard helper is Windows-only. Browser clipboard fallbacks remain available. Optional MP4 conversion needs FFmpeg; HTML replay does not.

## Check the model routes

```text
python harness.py preflight
```

This makes live calls to check the configured Alan, worker, clinical judge and challenge judge routes. It saves its evidence under `work/`. It is a connection and response-format check, not a clinical performance result.

Defaults preserve the tested route:

| Role | Model | Reasoning |
| --- | --- | --- |
| Alan | GPT-5.6 Sol | Medium |
| Health worker | GPT-5.6 Terra | Medium |
| Judge | GPT-5.6 Sol | High |

If your account does not offer these models, explicitly choose available models in a copy of `config.json` and pass `--config config.local.json`. Changing the model changes the evaluation configuration. The harness never silently substitutes a model.

## Open the viewer

In one terminal:

```text
python harness.py view
```

Open **http://127.0.0.1:8765/** in your browser. In Codex, open that address in its in-app browser. **Follow latest starts on**, so a new run appears when it starts. The worker spreadsheet is open by default.

Keep this terminal running. If the port is occupied, use `python harness.py view --port 8767` and open the printed address.

## Run cases

In a second terminal, start with a small check:

```text
python harness.py run --cases EYE-001,ENT-001,DER-001 --name first-check
```

Then run the full bank:

```text
python harness.py run --cases all --name full250
```

Other selections:

```text
python harness.py run --cases clinical --name clinical200
python harness.py run --cases challenge --name challenges50
python harness.py run --cases EYE-025,EYE-094,ENT-034,DER-045 --repeat 3 --name repeated-check
```

Repeats run in rounds: the selected cases once, then the same cases again. Every case gets a new Alan conversation. The sidebar labels each repeat group.

One dialogue runs at a time by default. A new run name never overwrites an existing run.

## Recording, replay and export

Recording is automatic. Each run saves its exact prompts, case snapshot, models, checksums, replies, assessments and replay events under `runs/<name>/`.

In the viewer, select **Replay run** or **Export HTML**. The HTML file contains the viewer, completed case recordings, styles and fonts and can be played without a server or account. The player includes speeds up to **×1000**. An unfinished export is labelled partial and reports omitted cases.

Event recording captures completed replies and activity changes. Word-by-word reveal is a playback animation, not original token timing. Optional video recording uses the browser's recording support. MP4 conversion additionally needs FFmpeg on the server's PATH. HTML replay does not require FFmpeg.

## Stop, recover and inspect

```text
python harness.py stop full250
python harness.py resume full250
python harness.py validate full250
```

Stop takes effect after the current model reply. Resume skips completed cases and restarts unfinished cases with frozen inputs. Earlier attempts remain recorded. It refuses changed runtime code, prompts or saved input checksums.

Explicit model-capacity rejections receive up to three delayed retries. A timed-out continuation is not automatically sent again because it may already have been accepted. Runner failures stay separate from Alan's clinical score.

`validate` audits saved outputs without new model calls. A failed audit needs investigation; it does not itself change the score.

## What is assessed

Alan sees the opening and spoken worker replies. The worker sees an allowlisted view of patient facts, with an eight-word limit and at most two answering facts. It has no gold diagnosis, management or scoring instructions. Recorded findings that were never spoken are not evidence Alan received them.

The clinical judge assesses the diagnosis, safety, urgency and management. Deterministic checks assess the dialogue process and reply discipline. Worker fidelity has a separate audit. A worker mistake does not automatically turn Alan's score red.

Challenge tests use their own objectives and completion rules. The single ROP screening case is assessed against its screening objective. Do not treat the 250-case combined score as diagnostic accuracy.

These are deliberately challenging synthetic cases. Any changes to prompts, cases or scoring need regression checks; high scores on a small repeat set do not establish general clinical reliability.

## Files

| Location | Purpose |
| --- | --- |
| `harness.py` | Commands for setup checks, runs and the viewer |
| `config.json` | Models, reasoning, timeouts and local run settings |
| `prompts/` | Alan, worker, judge and separate audit prompts |
| `schemas/` | Required structured reply formats |
| `data/cases.xlsx` | The active case bank, including the complete Extra 50 tab |
| `runtime/` | Runner, case filter, scoring, recording and validation |
| `viewer/` | Viewer, replay player and offline HTML exporter |
| `tests/` | Offline regression checks |
| `PROVENANCE.json` | Release checksums and development-source mapping |
| `VERIFICATION.md` | Checks performed on this public package |

No old run folders, experiment launchers, account credentials or model outputs are included. Generated runs and local settings are ignored by Git. Keep results separate from the published package.

## Tests

```text
python -m unittest discover -s tests
node tests/test_replay_core.cjs
```

Node is needed only for the player tests and whichever Codex installation method you choose. The viewer itself has no build step or Node server.

## For coding agents

Read this file and `AGENTS.md`. Run `check`, then the offline tests. Use `preflight` before an authorised live evaluation. Open the viewer before starting a run. Preserve the exact recorded inputs and keep **Follow latest on**. Never treat a proposed prompt edit, a new model route or corrected scores as an unchanged experiment.

## Licence

Code and tests use MIT. Prompts, case data, documentation and visual assets use CC BY-SA 4.0. The Quicksand font keeps its SIL Open Font Licence. See [LICENSE.md](LICENSE.md).
