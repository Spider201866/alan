# Changelog

## Source synchronisation - 2026-09-20

- Mirrored the current gold source into the DSL, preserving all 503 rule IDs, TAGs and GROUPs.
- Rebuilt all three compiled outputs and updated the source header date.
- Incorporated existing source refinements, including waiting for the reply before Step 5 and asking the worker for examination observations.
- Exact parity, lint and compiler checks pass; all 138 local tests pass.
- No new clinical model evaluation was run. Earlier evaluation results apply to their recorded frozen prompt versions.

## v0.2.0 - 2026-09-08

- Updated the source date and synchronised the full source, DSL and compiled prompts.
- Incorporated tested emergency routing, mandatory openers, unanswered-check handling and concise final diagnosis/plan wording.
- Updated the practical reference link to arclightproject.app.
- Health-worker experiments and evaluation recordings are separate from this Alan prompt release.

- Completed the August section-by-section Alan prompt refinement while preserving the five-stage scaffold, authored examples, LMIC memory and established persona.
- Promoted the frozen Alan prompt used in the September evaluation runs; all compiled outputs reproduce that tested text exactly.
- Tightened scope routing, evidence retention, question selection, safety transitions, stage separation, challenge recovery and post-Step-5 continuation.
- Reassigned 11 central safety-controller rules to the DSL `RED` group so the safety ablation is meaningful.
- Normalised prompt, DSL, compiler, test and generated-output files to UTF-8 LF and made both compilers write LF explicitly.
- Refreshed the validation report, evaluation baseline and living handover; 503 DSL rules and all 112 local tests pass.
- Added quick-start, safety, contribution and citation documentation together with GitHub Actions validation.
- Expanded the background with Alan's pre-LLM origins, the Atoms project, early development, architecture and design choices.
- Clarified throughout the public documentation that Alan is a portable teaching and learning scaffold above the language model engine, not a diagnostic product.
- Added cautions covering model dependence, local testing, privacy and information governance.
- Simplified the public repository guide and added the correctly spelt `Alan_dsl_compiled.txt` alias while retaining the historic output name.

## v0.1.0 - 2026-06-23

- Prepared Alan for first public GitHub release.
- Published the canonical prompt source, DSL source and compiled prompt outputs.
- Added public README, background notes, licence summary and overview image.
- Retained the established compiler workflow and validation report.
