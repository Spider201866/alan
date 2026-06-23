# Alan Expression Guide

Author: WJW  
Date: 17 March 2026

## What this is
This guide explains the custom expression box in the Ablation UI.

It is a fast filter for **GROUP** toggles in `Alan_DSL`.

## Important scope
- Expressions currently target **GROUPS only**.
- **TAG** filtering is not implemented in the expression box.
- TAGs remain metadata for linting and human scan.

## Syntax
Use simple tokens separated by spaces, commas or semicolons.

- `ALL` or `BASELINE`: turn all groups ON
- `NONE`: turn all groups OFF
- `+GROUP`: turn one group ON
- `-GROUP` or `!GROUP`: turn one group OFF
- `GROUP`: same as `+GROUP`

Evaluation order is left to right.

## 60-second usage
1. Start with a known baseline expression:
   `ALL`
2. Add one ablation:
   `ALL -LOGIC_S4`
3. Click `Apply Expression`.
4. Run `Compile Selected`.
5. Read output name and run log.

## Quick examples
- `ALL -LOGIC_S4`
- `BASELINE -EXAMPLES -MEMORY`
- `NONE +CORE +LOGIC +LOGIC_S1 +LOGIC_S2 +LOGIC_S3 +LOGIC_S5 +OUTPUT +STYLE +SECURITY`
- `-RED -SECURITY`
- `+LOGIC_S4`

## Typical recipes
- Remove reflection only:
  `ALL -LOGIC_S4`
- Keep only safety + core flow:
  `NONE +CORE +LOGIC +LOGIC_S1 +LOGIC_S2 +LOGIC_S3 +LOGIC_S4 +LOGIC_S5`  
  `+RED +CHECKS +OUTPUT +SECURITY`
- Remove examples and memory:
  `ALL -EXAMPLES -MEMORY`
- Hard minimal scaffold:
  `NONE +CORE +LOGIC +OUTPUT +STYLE +SECURITY`

## Current group list
- `CORE`
- `SCOPE`
- `TOOLS`
- `OUTPUT`
- `STYLE`
- `CHECKS`
- `LISTS`
- `RED`
- `LOGIC`
- `LOGIC_S1`
- `LOGIC_S2`
- `LOGIC_S3`
- `LOGIC_S4`
- `LOGIC_S5`
- `EXAMPLES`
- `EX_FULL`
- `EX_SHORT`
- `EX_EYE`
- `EX_ENT`
- `EX_DERM`
- `EX_CHILD`
- `EX_VET`
- `MEMORY`
- `MEM_EYE`
- `MEM_ENT`
- `MEM_DERM`
- `MEM_CHILD`
- `MEM_VET`
- `MEM_RED`
- `SECURITY`

## Current repo status
- `EXAMPLES` contains example-wide scaffolding rules.
- `EX_FULL` is populated with the five worked full cases.
- `EX_SHORT` is populated with the shortened/general example material.
- `MEMORY` contains cross-cutting memory rules.
- `MEM_EYE`, `MEM_ENT`, `MEM_DERM` and `MEM_RED` are populated.
- `EX_EYE`, `EX_ENT`, `EX_DERM`, `EX_CHILD`, `EX_VET`, `MEM_CHILD` and `MEM_VET` are available but may be unpopulated in the current `Alan_DSL`.

## Dependency notes
- If `LOGIC` is OFF, `LOGIC_S1..LOGIC_S5` should be OFF.
- If `EXAMPLES` is OFF, `EX_*` should be OFF.
- If `MEMORY` is OFF, `MEM_*` should be OFF.
- The compiler omits child content unless the parent group is also enabled.
- With strict dependency lint OFF: compile proceeds with warnings.
- With strict dependency lint ON: compile is blocked until fixed.

UI auto-fix can enforce these automatically if enabled.

## Error handling
- Unknown tokens show an error and no changes are applied.
- Empty expressions are rejected.

## CLI equivalents (optional)
- One-step ablation:
  `python compile_DSL.py --ablate LOGIC_S4 -o Alan_dsl_no_LOGIC_S4.txt`
- Whitelist compile:
  `python compile_DSL.py --groups CORE,LOGIC,LOGIC_S1,OUTPUT,STYLE,SECURITY -o Alan_dsl_custom.txt`
- Exclusion list:
  `python compile_DSL.py --exclude-groups EXAMPLES,MEMORY -o Alan_dsl_no_examples_memory.txt`
