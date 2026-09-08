# Alan evaluation harness

**Version 1.0.0 · 8 September 2026 · Tested on Windows**

Recorded consultations between **Alan** and a simulated **health worker**, assessed by a separate **judge**. Includes a 250-case Excel bank, live viewer and offline replay.

<table>
<tr>
<td width="55%"><img src="docs/runner-map.svg" width="420" alt="Judge above; patient and health worker on the left; Alan on the right."></td>
<td valign="middle">
<a href="https://spider201866.github.io/alan/"><strong>▶ Watch the demo</strong></a><br>
3 cases · Autoplays<br>
<em>No installation needed.</em><br><br>
<a href="https://spider201866.github.io/alan/download.html">Download HTML player</a>
</td>
</tr>
</table>

*The filter selects available worker facts. Alan hears the replies; the runner records them and the judge assesses Alan.*

## Quick start for humans and coding agents

**Coding agents: read [AGENTS.md](AGENTS.md) first.** Codex, Claude Code or another agent can help with setup. New evaluations use the **Codex CLI** as the model backend.

1. Work inside `evaluation/` and read [VERIFICATION.md](VERIFICATION.md). [CLAUDE.md](CLAUDE.md) points to the same agent instructions.
2. Follow [installation](#installation), then run `python harness.py check` and [the offline tests](#tests). These do not call models.
3. With live evaluation authorised, run `python harness.py preflight` to check the model routes.
4. Start `python harness.py view`, open **http://127.0.0.1:8765/** and keep **Follow latest on**.
5. In a second terminal using the same virtual environment, run `python harness.py run --cases EYE-001 --name quick-check`.
6. Inspect the recording, then use [run options](#run-cases), [export](#recording-replay-and-export) or [recovery commands](#stop-recover-and-inspect).

**Need help?** [Setup troubleshooting](#setup-troubleshooting) · [Models](#check-the-model-routes) · [Files](#files) · [Tests](#tests)

## What is included

- **Alan v0.2.0** — the compiled prompt used by the underlying LLM.
- **Health worker and case filter v1** — short replies from authorised patient facts.
- **Runner and recorder v1** — fresh case conversations, recovery and saved events.
- **Judges and scorers v1** — clinical assessment, challenge objectives and a separate worker audit.
- **Viewer v1** — live dialogue, scores, worker facts, repeat groups and replay up to ×1000.
- **Excel case bank v1** — 100 eye, 50 ENT, 50 skin and 50 challenge cases, with all challenge guidance in **Extra 50**.

![Alan viewer showing the score summary, runner map, worker facts, case list and recorded dialogue](docs/viewer.png)

*Complete EYE-001 dialogue from the three-case Windows installation check: intake, differentials, reflection and final answer. This is a UI example, not a 250-case performance claim.*

### Package size

| Included files | Approximate size |
| --- | --- |
| **Complete package** | **1.77 MB** |
| Excel case bank | 98 kB |
| All six prompts | 132 kB |
| Runner, filter and scoring code | 234 kB |
| Viewer, replay scripts and bundled font | 458 kB |
| Runner diagram and viewer screenshot | 242 kB |
| Self-contained three-case demo | 520 kB |

Approximate uncompressed file sizes; kB = 1,000 bytes and MB = 1,000,000 bytes. These cover `evaluation/` only. Python, Codex, the virtual environment, Git history and new recordings are additional. **No model weights are bundled.**

## Installation

**Required:** Git to clone the repository, **Python 3.11+**, a browser and the [Codex CLI](https://learn.chatgpt.com/docs/codex/cli) for new evaluations. Sign in to Codex and ensure your account has access to the models in `config.json`. Model calls consume the account's usage allowance.

**Optional:** Node for the JavaScript player tests or an npm-based Codex installation; **FFmpeg** for MP4 conversion. Neither FFmpeg nor a Node server is needed for HTML replay. Opening an exported HTML file needs only a browser.

### Windows PowerShell — tested

Install Python and Codex first, then:

```powershell
git clone https://github.com/Spider201866/alan.git
cd alan/evaluation
python --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Get-Command codex
codex --version
codex login
python harness.py check
```

### macOS or Linux — not yet tested

```sh
git clone https://github.com/Spider201866/alan.git
cd alan/evaluation
python3 --version
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
command -v codex
codex --version
codex login
python harness.py check
```

Use the virtual environment in **each terminal**. Run the activation command again after opening a new terminal in `evaluation/`. If already signed in, `codex login status` checks the account instead of signing in again.

This release was checked with Codex CLI **0.144.6**. `check` verifies the required isolation flags and sign-in status without calling a model. It reports an incompatible CLI rather than weakening isolation. Use the [official installation guide](https://learn.chatgpt.com/docs/codex/cli) for your operating system.

### Setup troubleshooting

| Problem | What to check |
| --- | --- |
| Python is missing or too old | Install Python 3.11+ and reopen the terminal. On Windows, `py -3 --version` checks an available Python launcher. |
| Linux cannot create `.venv` | Install your distribution's Python virtual-environment/ensurepip support, then repeat the environment command. |
| PowerShell blocks activation | Activation is optional. Use `.\.venv\Scripts\python.exe` in place of `python`, including for pip and harness commands. No execution-policy change is needed. |
| Codex cannot be found | Use `Get-Command codex` on Windows or `command -v codex` on macOS/Linux. Install the CLI or add its installation directory to PATH, then reopen the terminal. The desktop app alone does not prove the command is available. |
| Sign-in or model access fails | Check `codex login status`, sign in if needed and inspect `config.json`. Use an explicitly selected available model; do not silently substitute one. |
| Port 8765 is busy | Use `python harness.py view --port 8767` and open the printed address. |
| Copy report does not work | Check browser clipboard permissions. The native Outlook helper is Windows-only; browser copying has fallbacks. If copying is blocked, use Export HTML. |
| MP4 conversion is unavailable | Install FFmpeg and verify `ffmpeg -version` in the server's terminal. HTML export remains available without it. |

macOS/Linux installation and optional video conversion still need testing on those systems. An agent can diagnose setup issues and run the supplied checks; it should verify the result on the target operating system.

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

If these models are unavailable, copy `config.json` to `config.local.json` and choose available models. Put the option before the command: `python harness.py --config config.local.json preflight`. Use it for subsequent run and view commands too. The harness never silently substitutes a model.

## Open the viewer

In one terminal:

```text
python harness.py view
```

Open **http://127.0.0.1:8765/** in your browser. In Codex, open that address in its in-app browser. **Follow latest starts on**, so a new run appears when it starts. The worker spreadsheet is open by default.

Keep this terminal running.

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
| `docs/` | Runner map, screenshot and self-contained demo |
| `AGENTS.md` / `CLAUDE.md` | Agent instructions and Claude Code entry point |
| `PROVENANCE.json` | Release checksums and development-source mapping |
| `VERIFICATION.md` | Checks performed on this public package |

The screenshot and demo show the three-case installation check, not a full-bank evaluation. No experiment folders, credentials or raw process logs are included. New runs and local settings are ignored by Git.

## Tests

```text
python -m unittest discover -s tests
node tests/test_replay_core.cjs
```

Node is needed only for the player tests and whichever Codex installation method you choose. The viewer itself has no build step or Node server.

## Licence

Code and tests use MIT. Prompts, case data, documentation and visual assets use CC BY-SA 4.0. The Quicksand font keeps its SIL Open Font Licence. See [LICENSE.md](LICENSE.md).
