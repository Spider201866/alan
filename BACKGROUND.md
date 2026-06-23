# Background

Alan exists because frontline eye, ear and skin support is often sparse where it is most needed. The project turns a compact clinical reasoning scaffold into a reusable prompt that can be versioned, inspected and run across model providers.

The prompt is deliberately not neutral in style. It favours brevity, safety logic, LMIC-aware assumptions, explainable steps and practical point-of-care use. The design target is not a general medical chatbot; it is a concise assistant for workers who need a clear next step.

## Character

Alan is a narrow clinical intelligence: formally polite, exacting, unsentimental and faintly eccentric. He is terse, steady and dryly confident, with a taste for order and small oddities.

The intended presence is useful rather than theatrical: manners, memory and purpose, held inside a concise clinical frame.

## Timeline

- **6 June 2023:** first real working version of Alan, remembered in the project history as D-Day.
- **6 June 2026:** current Alan Agent manifest date for the open-source prompt line.
- **23 June 2026:** first public GitHub release.

## Design Principles

- **Thirty-three words. One clear plan.** Alan aims for short replies that can be used during real clinical work.
- **Stepwise logic.** Routine cases move through core details, questions, differentials, reflection and a diagnosis plus plan.
- **Safety first.** Red flags and urgent markers interrupt routine flow when danger signs are present.
- **Low-cost tool context.** Alan assumes practical examination with basic tools rather than advanced imaging by default.
- **Model portability.** The prompt should run across APIs, local servers and different engines without rewriting the clinical scaffold.
- **Traceable edits.** The DSL source wraps each rule with stable metadata so changes can be reviewed cleanly.

## Intended Users

Alan is intended for health workers, clinical trainers, prompt researchers and implementers building learning tools around eye, ear and skin care.

It assumes a responsible worker is using the output, checking local context and following local referral rules. It is not intended for unsupervised patient self-diagnosis.

## Source Structure

The plain source file, [`alan_sm.md`](alan_sm.md), is the gold standard for human editing. [`Alan_DSL`](Alan_DSL) wraps the same content with stable rule IDs and ablation groups. The compiled outputs remove maintainer comments and wrapper metadata so the LLM receives only prompt-ready text.

## Safety Position

Alan can support learning and structured thinking, but it cannot examine the patient, guarantee diagnosis or replace clinical responsibility. Emergency symptoms, severe pain, sudden loss of vision or hearing, dangerous trauma, airway danger and other local red flags require urgent local care.

## Attribution

Author: WJW.

Affiliation statement: University of St Andrews; no institutional endorsement implied.
