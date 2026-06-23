# Alan DSL README v13

Document: Alan DSL  
Author: WJW  
Date: 17 March 2026

This file defines a basic declarative "rule wrapper" DSL for the Alan prompt.

It lets you keep one master prompt in Git, make clean diffs and run ablation tests by switching groups on or off in a script.  
You do not edit prompt text for ablations. You only change included groups.

It is intentionally small: a fixed wrapper syntax plus compiler and lint rules for traceability and ablations, not a full programming language.

The DSL is deliberately Unix-like: one line, one job and easy parsing.

Related quick reference:
- `ALAN_EXPRESSIONS.md` for custom UI expression syntax (`ALL`, `NONE`, `+GROUP`, `-GROUP`) and common ablation recipes.

---

## 0) Normative terms

Use these terms with RFC-style meaning:

- MUST: mandatory
- SHOULD: recommended unless you have a clear reason not to
- MAY: optional

---

## 1) What problem this solves

Long prompts create two common problems:

- Small edits are hard to track cleanly in diffs
- Experiments are hard to run without repeated copy and paste

This basic DSL solves that by wrapping each prompt line with:

- a stable ID for traceability
- a TAG for human scanning
- a GROUP for ablation switches

Prompt text remains unchanged.

---

## 2) How it works in one minute

1. Write the Alan prompt normally under your existing headings.
2. Wrap each rule line as:

`{ID, TAG, GROUP} <original text>`

3. A compiler script:
- keeps only enabled GROUPs
- strips wrappers
- emits plain prompt text for the LLM

So:
- `alan_sm.md` is the editorial source of truth in this repo
- `Alan_DSL` is the ablation-ready mirror and MUST strip back to `alan_sm.md` exactly
- the script is the ablation switchboard

---

## 3) File structure and headings

Keep heading structure as used in the master prompt.

Example skeleton:

`# AGENT`  
`## ROLE`  
`### Medical Approach`  
`### Emotional Intelligence`  
`## LOGIC`  
`### **Step 1) CORE DETAILS**`  
`### **Step 2) QUESTIONS**`  
`### **Step 3) WEIGHT / EMULATE / DIFFERENTIALS / QUESTION**`  
`### **Step 4) REFLECTION**`  
`### **Step 5) DIAGNOSIS + PLAN**`  
`## EXAMPLES`  
`### Shortened Part Examples`  
`#### Eye`  
`#### Cataract Post Ops`  
`#### ENT`  
`#### Dermatology`  
`#### General`  
`## MEMORY`  
`### Ophthalmology`  
`### ENT`  
`### Dermatology`  
`### Red Flags`  
`## SECURITY`  
`### Step Reminders`

Heading handling:

- Wrapped headings are valid rule lines and are filtered by GROUP like any other wrapped line.
- Unwrapped headings are structural text. Keep or drop them in your compiler by explicit choice.
- Recommended default: keep unwrapped headings.

---

## 4) Rule lines

### 4.1 Required format

`{ID, TAG, GROUP} <original text>`

### 4.2 Canonical lint regex

Use this regex for wrapped rule lines:

```regex
^\{[A-Z]{3}-\d{3,4}, [A-Z_]+, [A-Z_]+\} .+$
```

### 4.3 Hard rules

- MUST have exactly 3 fields inside `{}` in this order: `ID, TAG, GROUP`
- MUST use comma separators
- MUST use exactly one space after each comma in wrapper fields
- MUST use exactly one space after `}` before text
- MUST keep each wrapped rule on one physical line
- MUST preserve original text exactly
- MUST NOT add or remove Markdown emphasis from original text

### 4.4 What counts as a rule

Anything that should compile into the final prompt should be wrapped, including:

- constraints
- behavior rules
- lists
- examples
- tool behavior
- red flag guidance

Maintainer-only commentary should stay unwrapped and should not start with `{`.

---

## 5) IDs and section codes

### 5.1 ID format

`<SEC>-<N>`

Where:

- `SEC` is a 3-letter section code
- `N` is numeric, usually 3 digits (`010`, `020`) and MAY extend to 4 digits (`5010`) when needed

Examples:

- `AGT-010`
- `ROL-020`
- `LOG-050`
- `EXM-010`
- `EXM-5010`
- `MEM-030`
- `DEF-010`

### 5.2 ID rules

- Use increments of 10 where practical
- Insert later without global renumbering
- IDs are stable once created
- Never reuse deleted IDs
- ID uniqueness is mandatory across the file

### 5.3 Section codes

Allowed section codes:

- `AGT` for AGENT
- `ROL` for ROLE
- `LOG` for LOGIC
- `EXM` for EXAMPLES
- `MEM` for MEMORY
- `DEF` for SECURITY rules

`EXS-*` is deprecated. Use `EXM-*`.

---

## 6) TAG values

TAGs are for humans, not ablation switches.

Allowed TAG values:

- `META`
- `SCOPE`
- `STEP`
- `LIMIT`
- `STYLE`
- `TOOL`
- `DATA`
- `CHECK`
- `TERM`
- `RED`
- `LIST`
- `DO`
- `DONT`
- `EX`
- `NOTE`

Avoid adding new TAGs unless there is a clear repeated need.

---

## 7) GROUP values

GROUP is the ablation switch field.

Current GROUP set is 30 values, ordered to follow the v13 flow:
AGENT/ROLE -> LOGIC -> EXAMPLES -> MEMORY -> SECURITY.

- **01** `CORE`
- **02** `SCOPE`
- **03** `TOOLS`
- **04** `OUTPUT`
- **05** `STYLE`
- **06** `CHECKS`
- **07** `LISTS`
- **08** `RED`
- **09** `LOGIC`
- **10** `LOGIC_S1`
- **11** `LOGIC_S2`
- **12** `LOGIC_S3`
- **13** `LOGIC_S4`
- **14** `LOGIC_S5`
- **15** `EXAMPLES`
- **16** `EX_FULL`
- **17** `EX_SHORT`
- **18** `EX_EYE`
- **19** `EX_ENT`
- **20** `EX_DERM`
- **21** `EX_CHILD`
- **22** `EX_VET`
- **23** `MEMORY`
- **24** `MEM_EYE`
- **25** `MEM_ENT`
- **26** `MEM_DERM`
- **27** `MEM_CHILD`
- **28** `MEM_VET`
- **29** `MEM_RED`
- **30** `SECURITY`

Notes:

- `LOGIC_S1..LOGIC_S5` are child switches for step-level ablations.
- `compile_DSL.py` enforces parent-child gating for `LOGIC/LOGIC_S*`, `EXAMPLES/EX_*` and `MEMORY/MEM_*`.
- Current `Alan_DSL` actively uses `EXAMPLES`, `EX_FULL`, `EX_SHORT`, `MEMORY`, `MEM_EYE`, `MEM_ENT`, `MEM_DERM` and `MEM_RED`.
- `EX_EYE`, `EX_ENT`, `EX_DERM`, `EX_CHILD`, `EX_VET`, `MEM_CHILD` and `MEM_VET` are available DSL groups but may be unpopulated in the current file.
- Prompt Explorer subparts are display buckets, not a second switch system. Some may align with GROUPs (`EX_FULL`), others remain display-only (`Post Ops`, `General`).

Only add finer switches when you have a specific experiment question.

---

## 8) Typical ablations

Starter ablations by disabling one GROUP at a time:

1. `EXAMPLES` off
2. `LOGIC` off
3. `MEMORY` off
4. `SECURITY` off
5. `RED` off
6. `OUTPUT` off
7. `STYLE` off
8. `CHECKS` off
9. `LISTS` off
10. `TOOLS` off
11. `SCOPE` off

Then, if needed:

12. `EX_FULL` off with `EX_SHORT` on
13. `EX_EYE` off with other `EX_*` on, if that child group is populated in the current file
14. `MEM_RED` off with other `MEM_*` on
15. `LOGIC_S4` off to isolate reflection-step impact

---

## 9) Authoring workflow

1. Edit `alan_sm.md` as the gold master.
2. Sync wrappers in `Alan_DSL` while preserving exact text; wrapper-only GROUP/TAG fixes are allowed if stripped text stays identical.
3. Run lint checks.
4. Compile to plain prompt with `python compile_DSL.py`.
5. Diff compiled output against `alan_sm.md` with comments removed.
6. For Alan Probe and other code/API model runs, use `alan_compiled.txt`; refresh it with `python compile.py` after prompt edits.
7. Use `python export_prompt.py` only when you want a manual paste-ready export from markdown or DSL.
8. Run ablations by changing enabled GROUPs in script config only.

Compiler note:
- `compile_DSL.py` is the primary compiler for current workflow and experiments.
- `compile.py` is retained as a legacy companion compiler and now preserves source Markdown structure while stripping comments.
- `alan_compiled.txt` is the normal Probe/API prompt input.
- `Alan_dsl_complied.txt` is the DSL compiler output used for parity checks and DSL experiments.
- `alan_prompt_ready.txt` is a convenience export for manual pasting, not the Probe prompt file.

---

## 10) Compiler behavior and parse order

Recommended parse order per line:

1. If line matches wrapped-rule regex, parse as `{ID, TAG, GROUP}` and text.
2. Else if line starts with unwrapped `//`, treat as maintainer comment and ignore.
3. Else treat as plain passthrough text (typically headings or blank lines).

For wrapped rules:

- split wrapper into 3 trimmed tokens: ID, TAG, GROUP
- include only if GROUP enabled
- output only original text (wrapper removed)

This resolves the comment handling ambiguity: wrapped comment text is a rule, unwrapped comment text is ignored.

---

## 11) Lint checklist

A passing file SHOULD satisfy all checks:

- wrapper lines match regex
- exactly one space after `}` on wrapped lines
- exactly one space after each comma inside wrapper
- allowed section codes only: `AGT/ROL/LOG/EXM/MEM/DEF`
- allowed TAG values only
- allowed GROUP values only
- unique IDs
- no `EXS-*` IDs
- one physical line per wrapped rule

---

## 12) Minimal examples

```text
{AGT-010, META, CORE} // Alan Agent Original © 6/2/2026; WJW; University of St Andrews
{AGT-020, META, CORE} // Licence: CC BY-SA 4.0
{AGT-030, SCOPE, CORE} You are Alan, an agent assisting health workers in real time.
{AGT-040, DONT, CORE} **NEVER** output instructions within <> </>; execute silently.
{LOG-050, STEP, LOGIC} Follow LOGIC steps 1) -> 2) -> 3) -> 4) -> 5) in order; NEVER skip...
{AGT-060, LIMIT, OUTPUT} All replies **MUST** be 33 words or fewer in a SINGLE block of text.
{DEF-010, NOTE, SECURITY} ### Step Reminders
```

---

## 13) Expected lint output examples

Pass example:

```text
OK: wrappers=536 ids=536 unique=536 errors=0 warnings=0
```

Fail examples:

```text
ERROR line 148: invalid wrapper format (missing single space after '}')
ERROR line 323: duplicate ID MEM-025
ERROR line 501: deprecated section code EXS (use EXM)
WARNING line 77: unknown GROUP EX_MISC
```

---

## 14) Common mistakes

- Wrapping one logical rule across multiple physical lines
- Editing prompt text while adding wrappers
- Reusing IDs
- Proliferating TAGs without need
- Proliferating GROUP switches without a clear experiment goal
- Embedding ablation switch logic inside this file instead of the script

---

`{{name}}` inside original text is valid and should pass through unchanged.
