# Changelog

## Reviewed prompt revision — 2026-10-14

- Published the tested gold source, matching DSL and all three compiled outputs with the 14 October source date. No clinical wording was changed during publication.
- Five compact replacements clarify question priority, lens-versus-retina evidence, ocular albinism cues and progression after urgent care. Alan is 12 words shorter; compiled token count is unchanged.
- A local 12-case development trial covered seven previously flagged cases and five passing controls. All 12 received diagnosis credit under the recorded judge policy, with no serious unsafe advice flagged. These familiar cases do not provide independent validation or isolate prompt changes from assessment changes.
- Preserved the case bank, authored health-worker examples, eight-word/two-finding limits and all original results. The historical replay and frozen September harness release are unchanged.
- A fresh 250-case run of this revision has not started.

## Reviewed prompt revision — 2026-10-13

- Published the approved gold source, matching DSL and all three compiled outputs with the 13 October source date. No additional clinical wording changes were made during publication.
- Incorporated the reviewed cue-priority, final-diagnosis, ranking and concise referral changes, including the approved short retinoblastoma teaching example.
- Targeted trials and nearby controls informed development. Revised cases and scoring policies remain separate from claims of prompt performance. Original results are preserved.
- Corrected stale README synchronisation wording and the background timeline. The September replay and frozen harness release remain unchanged.
- The next fresh 250-case run has not started.

## Reviewed prompt revision — 2026-10-12

- Published the reviewed gold prompt, matching DSL and all three compiled outputs. Stable DSL IDs are preserved.
- Clarified clinical cue priority, differential ranking, reflection and the final single-diagnosis form. Retained occasional acknowledgement examples and concise challenge handling.
- These are replacements within v0.2.0, not a longer prompt or a new full-bank performance claim.
- Targeted development trials and nearby controls are recorded separately. The revised ROP case is a case-bank correction, not evidence of an Alan performance gain.
- The historical September replay and frozen evaluation release are unchanged. The next full-bank run has not started.

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
