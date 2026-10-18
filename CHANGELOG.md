# Changelog

## Reviewed prompt revision — 2026-10-18

- Final 18 October review: updated the approved teaching examples, practical how-to guidance, safety wording and memory across eye, ENT and skin care. Retained the authored voice, darker-skin teaching emphasis, sleep-well cue and approximate teaching percentages.
- Consolidated duplicated rules and clarified occasional acknowledgements and the zero-score style branch. Retained the prohibition on word counting to avoid wasteful small-model reasoning loops. Retired AGT-120 and MEM-680 after consolidation; retained identifiers and groups are unchanged.
- Source and DSL match; all three compiled outputs are identical. Compiled prompt: 15,591 whitespace words and 104,887 UTF-8 bytes. Local technical checks: 138 source tests and 279 offline harness tests pass. These checks do not establish a new clinical-performance result.
- The original health-worker examples and eight-word/two-finding limits are unchanged. The fresh 250-case regression is being prepared with technical recovery, contextual length scoring and two separate follow-up attempts for eligible results; it has not started.

- Later on 18 October, updated only the AOM example final answer (EXM-060) and swollen-cheek memory (MEM-760): immediate pain relief, practical follow-up and antibiotics conditional on spreading or systemic dental infection. Matching DSL and compiled outputs are synchronised. The prompt is now 15,637 words and 104,771 bytes, two words and four cl100k tokens shorter than the preceding revision.
- Four familiar development consultations showed pain relief in both targets, with both close controls retaining correct diagnoses. A separate saved-dialogue reassessment corrected an urgency/marker judgement; this is a judging correction, not improved Alan performance. Original scores and dialogues remain preserved.

- Published the gold source and matching DSL with the 18 October date, plus three byte-identical compiled outputs.
- Replaced only the short retinoblastoma example (EXM-180), prioritising reflex/lens examination and clarification of an uncertain view. Retained the enlarged-eye presentation, full cataract example, staged workflow and conditional working diagnosis.
- Compiled length is unchanged at 15,639 words and 104,777 bytes; cl100k token count falls from 27,913 to 27,911.
- Three development consultations credited the retinoblastoma, cataract and photographic-artefact diagnoses. The photographic control retained a minor over-referral deduction. Disclosure and reference clarifications were tested alongside the prompt edit, so this does not isolate its effect or establish broad improvement. Original results are retained.
- Author-edited worker examples and eight-word/two-finding limits are unchanged. No new run was started for publication. The frozen harness release and historical replay remain unchanged.

## Reviewed prompt revision — 2026-10-16

- Published the dated gold source, matching DSL and three byte-identical compiled outputs. Stable rule IDs and safety-controller ownership are preserved.
- Incorporated the approved corneal-localisation, supplied-fact, concise-output and care-priority refinements. The latest replacement gives medication schedules, timed review/referral and deterioration advice priority over explanation. It adds no words or tokens.
- Retained age-pairing and question rules. The latest one-line replacement leaves all Alan examples, authored worker examples and eight-word/two-finding limits unchanged.
- Focused development trials and passing controls check familiar cases. Results are mixed: improved length compliance does not establish better care in every case. These are regression checks, not independent clinical validation or a new 250-case performance claim.
- A separate saved hearing dialogue was reassessed by the unchanged clinical judge after a conditional reference clarification. Its original judgement and dialogue are retained; this is an assessment correction, not improved Alan performance.
- The fresh 250-case package is prepared with technical recovery and two separate follow-up attempts for eligible results. It has not started. The September replay and frozen release remain unchanged.

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
