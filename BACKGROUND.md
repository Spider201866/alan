# Background

Alan began with a practical problem: eye, ear and skin knowledge is large, training time is short and expert help is unevenly distributed. The project asks how far useful clinical structure can be compressed without losing safety, nuance or the worker's next action.

The result is a scaffold, not a product. Alan sits above the chosen language model engine: the engine generates language; Alan supplies the clinical role, memory, safety logic, stepwise workflow and voice. The scaffold can be inspected, versioned, compiled and run across model providers.

The design is deliberately not neutral. Alan favours brevity, safety logic, LMIC-aware assumptions, explainable steps and practical point-of-care use. The target is not a general medical chatbot. The target is a concise assistant for workers who need one clear next move.

## Clinical Problem

Alan is shaped around missing basics: staff, kit, power, specialist support, teaching time and reliable point-of-care reference. Eye, ear and skin problems are common, but practical expertise is often thinly spread. A worker may have a queue, a low-cost tool and no immediate specialist to ask.

The aim is therefore not a high-tech image-first system. Alan starts with ordinary clinical work: careful questions, visible signs, safety checks, differentials and a practical next step. It is meant to lift basic examination and reasoning, especially when paired with low-cost tools such as the Arclight ophthalmoscope, otoscope and dermatoscope.

## Origins

The idea predates LLMs. Around seven to eight years before the first public release, the starting question was how to distil large ophthalmic textbooks into something compact enough to carry and use. One suggestion was a set of low-cost, credit-card-sized books printed on bible-thin paper.

That compression instinct became the 2021-2022 Atoms project: condensed visual algorithm cards for clinical settings, fieldwork or quick student revision. They were not textbook replacements and were never meant to stand in for practical training. They did show that clinical knowledge could be compressed surprisingly far, especially into a single smartphone-friendly image.

The hard part remained. Concentrated information is still information. It still has to be absorbed. Learning is hard and experts are few for a reason.

By late 2022, the large language model (LLM) wave had arrived. In early 2023 it became clear that careful user queries could steer output strongly and that structured system messages could produce distinctive focused agents. A March 2023 experiment inspired by the Talkie Toaster AI from Red Dwarf showed that custom memory held inside the model context window could work unexpectedly well.

The habit of jokingly calling any AI "Alan" settled into the project in May 2023 with the first eye and ear Alan. From there the agent developed quickly: condensed Atoms material, clinical rules of thumb, a recognisable voice and strict output formatting.

Alan then gained stepwise differential logic, a reflective review stage, practical dialogue examples, compressed memory and a role/security wrapper to keep the agent on topic. Iterative testing through 2023 and 2024 made the steering more reliable and clarified the value of temperature control, compact prompt design and close attention to clinical wording.

## Scaffold

Alan is layered. The underlying language model is the engine. Alan sits above it as a scaffold of role, memory, examples, safety rules, clinical logic and output constraints.

At the lowest level the scaffold handles scope, formatting and security. The middle holds the clinical workflow, compressed memory and eye, ear and skin frames. The top carries the persona, tone, context and small behavioural cues that make the agent feel steady rather than generic.

This design gives Alan its useful constraint. It slows the model down into a five-step clinical rhythm, pulls curated knowledge into the conversation and reduces cold-start amnesia. The same scaffold can be moved across engines without starting again.

## Design Choices

Alan keeps the agent together in one scaffold rather than splitting it into a committee of separate agents. The role, logic, examples, memory and safety wrapper sit in the model context so the behaviour stays cohesive and portable.

The curated examples and memory are not decorative. They are Alan's primary reference layer: they shape tone, questioning, clinical recall and edge-case handling before the base model's wider knowledge is used as fallback. This is different from simply asking a raw model for medical advice.

The short output style was also a design choice, not a gimmick. Earlier versions were longer. Testing pushed replies down from about 70 words towards the present 20-33 word target. Below that, the answers became too coded and lost clinical nuance. The same logic sits behind the three-question cap and the three-differential habit: enough structure to teach, not so much that the worker is buried.

Alan is therefore more than a prompt trick or a thin wrapper. The useful part is the system around the model: Arclight-linked examination cues, LMIC-specific heuristics, constrained triage, structured memory and a fixed output format designed for point-of-care use.

## Character

Alan is a narrow clinical intelligence: formally polite, exacting, unsentimental and faintly eccentric. He is terse, steady and dryly confident, with a taste for order and small oddities.

The intended presence is useful rather than theatrical. Alan should feel like manners, memory and purpose held inside a concise clinical frame.

## Timeline

- **6 June 2023:** first real working version of Alan, remembered in the project history as D-Day.
- **6 June 2026:** current Alan Agent manifest date for the open-source prompt line.
- **23 June 2026:** first public GitHub release.

## Design Principles

- **Thirty-three words. One clear plan.** Alan aims for short replies that can be used during real clinical work.
- **Stepwise logic.** Routine cases move through core details, focused questions, differentials, reflection and a diagnosis plus plan.
- **Safety first.** Red flags and urgent markers interrupt routine flow when danger signs are present.
- **Low-cost tool context.** Alan assumes practical examination with basic tools rather than advanced imaging by default.
- **Model portability.** Alan is the scaffold above the engine, so the underlying model can change without rewriting the clinical structure.
- **Usable trade-offs.** Alan deliberately favours brevity over depth, speed over breadth and disciplined structure over conversational sprawl.
- **Traceable edits.** The DSL source wraps each rule with stable metadata so changes can be reviewed cleanly.

## Intended Users

Alan is intended for health workers, clinical trainers, prompt researchers and implementers building learning tools around eye, ear and skin care.

It assumes a responsible worker is using the output, checking local context and following local referral rules. It is not intended for unsupervised patient self-diagnosis.

## Source Structure

The plain source file, [`alan_sm.md`](alan_sm.md), is the gold standard for human editing. [`Alan_DSL`](Alan_DSL) wraps the same content with stable rule IDs and ablation groups. The compiled outputs remove maintainer comments and wrapper metadata so the LLM receives only prompt-ready text.

## Safety Position

Alan can support learning and structured thinking, but it cannot examine the patient, guarantee diagnosis or replace clinical responsibility. Emergency symptoms, severe pain, sudden loss of vision or hearing, dangerous trauma, airway danger and other local red flags require urgent local care.

Alan remains experimental. Prompt integrity checks and regression tests are useful engineering controls, but field evaluation, local governance, privacy practice and clinical responsibility remain essential.

## Attribution

Author: WJW.

Affiliation statement: University of St Andrews; no institutional endorsement implied.
