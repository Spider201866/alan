# Background

Alan began as a compression problem: how do you carry useful eye, ear and skin knowledge into a clinic where time is short, tools are basic and specialist help may be absent?

Alan is a scaffold that sits above a language model engine. The engine generates language; Alan supplies the teaching role, curated memory, safety logic, stepwise workflow and voice. The scaffold can be inspected, versioned, compiled, moved between models and forked for local teaching needs.

The design is deliberately not neutral. Alan favours brevity, explainable steps and low-cost examination tools. It is shaped by constraints common in low- and middle-income country (LMIC) settings and built around one clear next teaching step.

## Clinical Problem

In many low-resource settings, eye, ear and skin care is constrained by shortages of staff, equipment, power, specialist support, teaching time and reliable reference material. A health worker may have a queue, a low-cost tool and no experienced colleague immediately available.

Alan starts with those realities. It structures case-based teaching around careful questions, observed signs, safety checks, differentials and a practical next step. It is intended to strengthen the teaching of basic examination and reasoning, especially when paired with tools such as the Arclight ophthalmoscope, otoscope and dermatoscope.

## Origins

The idea predates LLMs. Around seven to eight years before the first public release, the starting question was how to distil large ophthalmic textbooks into something compact enough to carry and use. One suggestion was a set of low-cost, credit-card-sized books printed on bible-thin paper.

That compression instinct became the 2021-2022 Atoms project: condensed visual algorithm cards for clinical settings, fieldwork or quick student revision. They were not textbook replacements and were never meant to stand in for practical training. They did show that clinical knowledge could be compressed surprisingly far, especially into a single smartphone-friendly image.

The hard part remained. Compression can make information easier to carry, but not automatically easier to understand. Learning is difficult and expertise takes time to build.

By late 2022, the large language model wave had arrived. In early 2023 it became clear that structured system messages could create focused agents. A March 2023 experiment inspired by the Talkie Toaster AI from Red Dwarf suggested that memory held inside the model's context window could help an agent maintain a distinctive role and voice.

The habit of jokingly calling any AI "Alan" settled into the project in May 2023 with the first eye and ear Alan. From there the agent developed quickly: condensed Atoms material, clinical rules of thumb, a recognisable voice and strict output formatting.

Alan then gained stepwise differential logic, a reflective review stage, practical dialogue examples, compressed memory and a role and safety wrapper to keep the agent on topic. Informal iterative development through 2023 and 2024 improved the consistency of the prompt and clarified the value of temperature control, compact design and close attention to clinical wording. This was prompt development, not clinical validation.

## Scaffold

Alan is layered.

The lowest layer defines scope, safety and output format. The middle layer holds the teaching workflow, compressed memory and eye, ear and skin frames. The top layer carries persona, tone, context and small behavioural cues that make the agent feel steady rather than generic.

This structure gives Alan its useful constraint. It guides the model through a five-step learning rhythm and gives each new session the same reference material and behavioural frame. The scaffold can move between models without being rewritten, although its performance must be tested on each one.

## Design Choices

Alan keeps role, logic, examples, memory and safety together in one scaffold. Keeping these elements in the same model context helps the teaching behaviour remain cohesive and portable.

Within each session, Alan's curated examples and memory provide an immediate reference layer. They are intended to shape tone, questioning, recall and handling of less straightforward cases while the underlying model supplies broader language and reasoning capability.

The short output style is also a design choice, not a gimmick. Earlier versions were longer. Testing pushed replies down from about 70 words towards the present 20-33 word target. Below that, answers became too coded and lost clinical nuance. The same logic sits behind the three-question cap and the three-differential habit: enough structure to teach, not so much that the worker is buried.

Alan is therefore an authored system around the model: Arclight-linked examination prompts, LMIC-aware teaching cues, safety escalation, structured memory and a fixed output format for concise case-based learning.

## Character

Alan is a narrow clinical intelligence: formally polite, exacting, unsentimental and faintly eccentric. He is terse, steady and dryly confident, with a taste for order and small oddities.

The intended presence is useful rather than theatrical. Alan should feel like manners, memory and purpose held inside a concise clinical frame.

## Timeline

- **6 June 2023:** first real working version of Alan, remembered in the project history as D-Day.
- **6 June 2026:** current Alan Agent manifest date for the open-source prompt line.
- **23 June 2026:** first public GitHub release.

## Design Principles

- **Thirty-three words. One clear plan.** Alan aims for replies short enough for time-limited case teaching.
- **Stepwise logic.** Routine cases move through core details, focused questions, differentials, reflection and a provisional diagnosis-and-plan discussion.
- **Safety first.** Red flags and urgent markers interrupt the ordinary teaching flow when danger signs are present.
- **Low-cost tool context.** Alan prompts learners to consider findings from basic examination tools rather than assuming advanced imaging.
- **Model portability.** Alan is the scaffold above the engine, so the underlying model can change without rewriting the teaching structure. Behaviour still needs testing on each model.
- **Usable trade-offs.** Alan deliberately favours brevity over depth, speed over breadth and disciplined structure over conversational sprawl.
- **Traceable edits.** The DSL source wraps each rule with stable metadata so changes can be reviewed cleanly.

## Intended Users

Alan is intended for health workers, students, clinical trainers, prompt researchers and implementers building learning tools around eye, ear and skin care.

It assumes that a responsible teacher or health professional is checking the output against local context, examination findings and referral rules. It is not intended for unsupervised patient self-diagnosis.

## Source Structure

The plain source file, [`alan_sm.md`](alan_sm.md), is the gold standard for human editing. [`Alan_DSL`](Alan_DSL) wraps the same content with stable rule IDs and ablation groups. The compiled outputs remove maintainer comments and wrapper metadata so the language model receives only prompt-ready text.

## Safety Position

Alan can support learning and structured thinking, but it cannot examine a patient, verify the information it receives or provide a validated diagnosis. Any differential, provisional diagnosis or plan it generates is educational and must be checked locally. Emergency symptoms, severe pain, sudden loss of vision or hearing, dangerous trauma, airway danger and other local red flags require urgent local care.

Alan remains an experimental teaching scaffold. Prompt-integrity checks and regression tests are useful engineering controls, but they do not establish clinical safety or deployment readiness. Field evaluation, local governance, privacy practice and clinical responsibility remain essential.

## Attribution

Author: WJW.

Affiliation statement: University of St Andrews; no institutional endorsement implied.
