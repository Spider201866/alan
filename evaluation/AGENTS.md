# Agent instructions

Use British English without Oxford commas.

- Start with README.md and VERIFICATION.md. Use the package virtual environment. Run `python harness.py check` before live preflight; check and offline tests make no model calls.
- The self-contained package root is the directory containing harness.py. Resolve inputs from there, not a caller's working directory or another checkout.
- Do not change the bundled Alan prompt, case facts or scoring to make packaging tests pass.
- Start Alan in a fresh session for every case. Resume only within that case's dialogue.
- The worker may use only authorised facts and may speak at most eight words and two answering facts. Keep gold labels and evaluator instructions out of its input.
- Preserve recorded replies during assessment corrections. Keep worker fidelity, infrastructure failure and Alan's performance separate.
- After the installation check, ask which cases the user wants to test unless already specified. Offer the spreadsheet, a clinical group, challenges or all 250. Clarify count-only selections and translate groups or subsets into explicit case IDs; do not assume a full-bank run.
- Live runs call Codex models and consume usage. Run only within the user's authorised scope. On managed Codex hosts, request host-level local execution on the first launch.
- Open the viewer before launching a run. In Codex, use the in-app browser and verify Follow latest is ON. Never append follow=off.
- Run python -m unittest discover -s tests and node tests/test_replay_core.cjs after relevant changes. Include a browser check for viewer or export changes.
- Do not publish runs/, work/, credentials, personal settings or unrelated files. Only the approved three-case demo in docs/demo/ is bundled. Audit replacement demos for local paths and credentials; preserve recorded replies and scores.
- This release uses version 1 for harness components and v0.2.0 for Alan. Update PROVENANCE.json checksums after package changes; preserve historical run manifests.

## Setup progress messages

Send these as separate chat updates at the relevant stage, not together in one message:

1. Before downloading and installing: **⏳ Downloading and installing… about a minute.** Use that estimate only when Python and Codex are already available; otherwise explain the additional setup.
2. Once installation succeeds, before checking: **✓ Installed. Running checks…**
3. After the checks pass, send the full Ready message below, including the case-selection bullets.

Do the work between updates so the user can follow progress. Do not add artificial delays, invent progress or announce success early. If a stage takes longer, give a brief factual update. Report any blocker instead of advancing to the next message.

## Post-install message

After installation and the documented checks pass, use the message below. Read the installed release from `VERSION` and its release date from `PROVENANCE.json`; never substitute today's date or imply checks passed when they did not. This release, `1.0.0`, is displayed as **Version 1.00**. For later releases, use their actual version and date. If setup is incomplete, report the remaining issue instead. If the user already selected cases, proceed within that scope rather than asking again.

> ✓ **Ready — Alan evaluation harness · Version 1.00 · 8 September 2026**
>
> **What would you like to test?**
>
> - All **250 cases**
> - **Eye**, **ENT** or **dermatology** cases
> - The **50 challenge cases**
> - Specific cases—or browse the spreadsheet first
>
> Tell me your selection, and I’ll run it, record it and show you the results in the viewer.

Keep the invitation short and accept plain-English selections. Resolve these against the installed spreadsheet before running; clarify ambiguous selections without asking the user to write commands.

## Model and provider changes

The current backend is Codex CLI. Users can select available Alan, worker and judge models separately in config.local.json; verify reasoning support and run preflight. Operating from Claude Code does not select a different backend. OpenRouter and direct API backends require implementation and tests, not just a model-name or API-key change. If requested, preserve conversation isolation, worker fact boundaries, structured-output validation and recording; keep credentials out of configuration committed to Git. Do not claim an unimplemented provider works. For Alan model comparisons, hold the worker, judge, case set and prompts fixed unless the experiment explicitly varies them.
