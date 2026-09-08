# Agent instructions

Use British English without Oxford commas.

- Start with README.md and VERIFICATION.md. Use the package virtual environment. Run `python harness.py check` before live preflight; check and offline tests make no model calls.
- The self-contained package root is the directory containing harness.py. Resolve inputs from there, not a caller's working directory or another checkout.
- Do not change the bundled Alan prompt, case facts or scoring to make packaging tests pass.
- Start Alan in a fresh session for every case. Resume only within that case's dialogue.
- The worker may use only authorised facts and may speak at most eight words and two answering facts. Keep gold labels and evaluator instructions out of its input.
- Preserve recorded replies during assessment corrections. Keep worker fidelity, infrastructure failure and Alan's performance separate.
- Live runs call Codex models and consume usage. Run only within the user's authorised scope. On managed Codex hosts, request host-level local execution on the first launch.
- Open the viewer before launching a run. In Codex, use the in-app browser and verify Follow latest is ON. Never append follow=off.
- Run python -m unittest discover -s tests and node tests/test_replay_core.cjs after relevant changes. Include a browser check for viewer or export changes.
- Do not publish runs/, work/, credentials, personal settings or unrelated files. Only the approved three-case demo in docs/demo/ is bundled. Audit replacement demos for local paths and credentials; preserve recorded replies and scores.
- This release uses version 1 for harness components and v0.2.0 for Alan. Update PROVENANCE.json checksums after package changes; preserve historical run manifests.
