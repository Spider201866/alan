# Background

Alan began with a compression problem: how could useful eye, ear and skin knowledge reach a clinic where time is short, tools are basic and specialist help may be absent?

The fullest account of that journey remains WJW's February 2026 essay, *Alan: A Helping Hand for LMIC Eye, Ear and Skin Care*, a deliberately all-in exploration of clinic, code and philosophy. This page offers the shorter repository history and reflects Alan's current position as a teaching tool.

That original question eventually produced a scaffold rather than another reference book. Alan sits atop a language model engine: the model generates language, while the authored layer supplies the teaching role, curated memory, safety logic, stepwise workflow and voice. Every part can be inspected, versioned, compiled, moved between models and forked for local needs.

The design is deliberately not neutral. Brevity, explainable steps and low-cost examination tools take priority. Constraints common in low- and middle-income country (LMIC) settings shape the whole system around one clear next teaching step.

## Clinical Problem

Across many low-resource settings, shortages of staff, equipment, power, specialist support, teaching time and reliable reference material constrain eye, ear and skin care. A health worker may face a queue with little more than a low-cost tool and no experienced colleague immediately available.

Alan addresses that teaching gap, not the whole health system. Case discussions begin with careful questions, observed signs and safety checks before moving through differentials towards a practical next step. Paired with the Arclight ophthalmoscope, otoscope and dermatoscope, the scaffold helps trainers connect basic examination findings with disciplined reasoning.

## Origins

The project predates LLMs. Seven or eight years before the first public release, the starting question was how to distil large ophthalmic textbooks into something compact enough to carry and use. One proposal imagined low-cost miniature books printed on bible-thin paper.

The same compression instinct became the 2021-2022 Atoms project: visual algorithm cards for clinics, fieldwork and rapid student revision. Never intended to replace textbooks or practical training, the cards nevertheless showed how far clinical knowledge could be condensed, even into a single smartphone-friendly image.

Access, however, was only half the problem. Compact information is easier to carry, not automatically easier to understand. Learning remains difficult and expertise takes time to build.

Large language models offered a different answer. By early 2023, structured system messages could create focused agents rather than simply return isolated responses. A March experiment inspired by the Talkie Toaster AI from *Red Dwarf* suggested that memory held inside the context window could sustain a distinctive role and voice.

By May 2023, the habit of jokingly calling any AI "Alan" had settled into the project. The first eye and ear Alan ran on GPT-3.5, combining condensed Atoms material with clinical rules of thumb, a recognisable voice and strict output formatting.

The system message soon gained stepwise differential logic, a reflective review stage, practical dialogue examples, compressed memory and a role and safety wrapper. Informal iterative development through 2023 and 2024 improved consistency and clarified the value of temperature control, compact design and exact clinical wording. This was prompt development, not clinical validation.

## Scaffold

The resulting scaffold has three layers.

The lowest layer defines scope, safety and output format. The middle holds the teaching workflow, compressed memory and eye, ear and skin frames. The top carries persona, tone, context and small behavioural cues that make Alan feel steady rather than generic.

Together, the layers guide the model through a five-step learning rhythm and give every new session the same reference material and behavioural frame. The scaffold can move between models without being rewritten, although performance must be tested afresh on each one.

## Design Choices

One cohesive agent holds role, logic, examples, memory and safety in the same model context. That choice keeps the teaching behaviour joined-up and portable.

Curated examples and memory provide the immediate reference layer, shaping tone, questioning, recall and the handling of less straightforward cases. Broader language and reasoning capability still come from the underlying model.

Brevity carries equal weight. Earlier versions allowed about 70 words; iteration brought the target down through 50 and 40 to the present 20-33. Shorter attempts became coded and lost clinical nuance. The three-question cap and three-differential habit follow the same principle: enough structure to teach without burying the learner.

The result is an authored system around the model rather than a persona alone: Arclight-linked examination prompts, LMIC-aware teaching cues, safety escalation, structured memory and a fixed format for concise case-based learning.

## Character

Alan is a narrow clinical intelligence: formally polite, exacting, unsentimental and faintly eccentric. Terse, steady and dryly confident, he has a taste for order and small oddities.

The intended presence is useful rather than theatrical: manners, memory and purpose held inside a concise clinical frame.

## Timeline

- **6 June 2023:** first real working version of Alan, remembered in the project history as D-Day.
- **6 June 2026:** current Alan Agent manifest date for the open-source prompt line.
- **23 June 2026:** first public GitHub release.

## Principles in Brief

- **Thirty-three words. One clear plan.** Alan aims for replies short enough for time-limited case teaching.
- **Stepwise logic.** Routine cases move through core details, focused questions, differentials, reflection and discussion of a provisional diagnosis and plan.
- **Safety first.** Red flags and urgent markers interrupt the ordinary teaching flow when danger signs are present.
- **Low-cost tool context.** Alan prompts learners to consider findings from basic examination tools rather than assuming advanced imaging.
- **Model portability.** Alan is the scaffold above the engine, so the underlying model can change without rewriting the teaching structure. Behaviour still needs testing on each model.
- **Usable trade-offs.** Alan deliberately favours brevity over depth, speed over breadth and disciplined structure over conversational sprawl.
- **Traceable edits.** The DSL source wraps each rule with stable metadata so changes can be reviewed cleanly.

## Intended Users

Alan serves health workers, students, clinical trainers, prompt researchers and implementers building learning tools around eye, ear and skin care.

Responsible use requires a teacher or health professional to check every output against local context, examination findings and referral rules. Unsupervised patient self-diagnosis falls outside the intended scope.

## Source Structure

The plain source file, [`alan_sm.md`](alan_sm.md), is the gold standard for human editing. [`Alan_DSL`](Alan_DSL) wraps the same content with stable rule IDs and ablation groups. The compiled outputs remove maintainer comments and wrapper metadata so the language model receives only prompt-ready text.

## Safety Position

Alan can support learning and structured thinking, but cannot examine a patient, verify submitted information or provide a validated diagnosis. Every differential, provisional diagnosis and plan is educational and requires local checking. Emergency symptoms, severe pain, sudden loss of vision or hearing, dangerous trauma, airway danger and other local red flags require urgent local care.

The project remains experimental. Prompt-integrity checks and regression tests provide useful engineering controls, not evidence of clinical safety or deployment readiness. Field evaluation, local governance, privacy practice and clinical responsibility remain essential.

## Attribution

Author: WJW.

Affiliation statement: University of St Andrews; no institutional endorsement implied.
