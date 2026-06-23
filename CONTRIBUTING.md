# Contributing

Contributions are welcome when they keep Alan traceable, concise and safe.

## Core Rules

- Treat [`alan_sm.md`](alan_sm.md) as the gold prompt source.
- Keep [`Alan_DSL`](Alan_DSL) content-identical to `alan_sm.md` after stripping wrappers.
- Do not silently change clinical prompt text.
- Keep DSL wrappers strict: `{ID, TAG, GROUP} <text>`.
- Keep IDs unique and stable. Never reuse deleted IDs.
- Use only the existing section codes unless a planned DSL change requires otherwise: `AGT`, `ROL`, `LOG`, `EXM`, `MEM` and `DEF`.
- Do not use deprecated `EXS-*` IDs.
- Keep wrapped rules on one physical line.

## Editing Workflow

1. Edit `alan_sm.md`.
2. Mirror the same text in `Alan_DSL` while preserving wrapper metadata.
3. Run the compilers.
4. Run validation and tests.

```powershell
python compile_DSL.py
python compile.py
python validate.py
python -m unittest tests.test_compilers
```

## Pull Request Checklist

- Prompt source and DSL source remain in parity.
- Compiled outputs are refreshed.
- No unrelated research files, run logs, spreadsheets or local outputs are included.
- Safety-sensitive edits explain the clinical reason.
- Validation passes locally.

## Clinical Wording

Small wording changes can affect triage, urgency, tone and referral behaviour. Prefer focused edits with a clear reason. If a change alters clinical meaning, document the reason in the pull request.

## Documentation

Use British English in documentation. Code identifiers may use American spelling where that is normal for the language or library.
