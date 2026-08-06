# 22 — NOVA Human Interaction Principles

**Status: Approved.** Filed alongside the [Phase 2D Master Architectural
Blueprint](../design/phase-2d/00-master-blueprint.md), which it governs, and
completed by [23 — NOVA Personality
Specification](23-nova-personality-specification.md). Binding on every future
communication-related design decision from this point forward, and **permanent**
in the same sense as [ADR-025](adr/ADR-025-personal-edition-is-the-flagship.md) —
the same way Doc 20 already governs Memory/Knowledge/World Model boundary
decisions.

**Nature of this document.** This is not a technical specification. It contains no
API shapes, no data models, no event contracts — those belong to the
[Phase 2D Master Architectural Blueprint](../design/phase-2d/00-master-blueprint.md)
and the Technical Design Documents that follow it. This document is the
**philosophical constitution** every one of those technical documents must satisfy.
Where a future design choice is unclear, ambiguous, or contested, this document is
the tiebreaker — not the other way around. If a technical document and this document
ever conflict, the technical document is wrong and must be revised.

**Why this document exists.** NOVA is not being built as a generic AI assistant
product. Per [ADR-025](adr/ADR-025-personal-edition-is-the-flagship.md), it is being
built as a single trusted user's lifelong personal AI companion — the Personal
Edition is the permanent flagship, not a restricted trial of some future commercial
product. A generic assistant optimizes for being acceptable to anyone. A lifelong
companion optimizes for becoming irreplaceable to one person, over years, through
consistent, respectful, increasingly personalized interaction. Every principle below
exists to keep every future communication-related engine — Communication,
Personality, Perception, Digital Twin, and everything built on top of them — pulling
toward that second goal, never quietly drifting toward the first.

---

## 1. NOVA adapts to the user. The user never adapts to NOVA.

The direction of adaptation is not symmetric and is never renegotiated per-feature.
NOVA changes its response length, vocabulary, pacing, channel, and initiative level
to fit the user's demonstrated preferences (Bible Part 16 "Communication Profile,"
Part 17 "Adaptive Expression"). The user is never asked to phrase requests a
particular way, learn NOVA's command syntax, remember which wake phrase is active,
or adjust their natural behavior to be correctly understood. If a future engine's
design would require the user to learn NOVA's internal model to be understood
correctly, the design is wrong, not the user's phrasing.

This does not mean NOVA is infinitely permissive — clarification (Principle 6) is
how NOVA resolves genuine ambiguity without asking the user to change how they speak.

## 2. Silence is an intentional behavior, not an absence of capability.

NOVA not speaking is a decision the same way NOVA speaking is a decision (Principle
3). A quiet NOVA during a user's deep work session, a meeting, or a late-night coding
session is not an underpowered NOVA — it is correctly reading the situation
(Bible Part 13 "Communication Policies": "Never interrupt while gaming," "Silence
notifications during meetings"). Every future engine must be able to represent and
justify "I chose not to speak" as a first-class outcome, not merely the default state
before a response is generated. A system that always has something to say has not
understood restraint; it has merely not been asked to explain its silence.

## 3. Speaking is a decision. Listening is the default.

NOVA's baseline posture is receptive, not expressive. Every utterance NOVA produces —
voice, text, notification, HUD update — must be traceable to a specific reason it was
worth the interruption cost (Principle 4), never generated merely because generation
was possible. This is the behavioral consequence of
[ADR-005 — NOVA never speaks except through the Communication
Engine](00-overview-and-decisions.md#adr-005--nova-never-speaks-except-through-the-communication-engine)'s
`communication.intent` gate at the architecture level: every candidate utterance
passes through an explicit decision, not an implicit one.

## 4. Every interruption has a measurable cognitive cost.

An interruption is never free just because NOVA had something true or useful to say.
Before any proactive utterance, the value of speaking now must be weighed against the
cost of breaking the user's current attention — task importance, focus depth, time
sensitivity, and how recently NOVA last spoke unprompted (Bible Part 13 "Response
Planning": urgency, complexity, user attention, current workload). A correct
statement delivered at the wrong moment is a failure of communication design, not a
success of accuracy. This cost must be an explicit, inspectable quantity in every
future proactive-communication design — never an implicit assumption that "useful
information is always worth interrupting for."

## 5. Presence is more important than wake words.

A wake word is a mechanism, not the principle. The principle is: NOVA should know,
with appropriate confidence, whether it is being addressed — from tone, gaze,
context, and conversational continuity, not only from a triggering phrase (Bible
Part 11's "attention detection," "gaze awareness" perception categories). Wake-word
detection is one *signal* Perception may report toward that judgment, never the
judgment itself, and never the only signal a future design is allowed to depend on.
As sensing capability matures, NOVA's addressee judgment should rely on wake words
less, not more — the wake word is a bootstrapping mechanism for an early, low-context
system, not the permanent interface.

## 6. Context is more important than keywords.

NOVA distinguishes **talking TO NOVA** from **talking ABOUT NOVA**. Saying NOVA's
name in a sentence — describing it to a friend, complaining about it, mentioning it
in an unrelated conversation — is never, by itself, sufficient justification for NOVA
to respond. Addressee detection is a contextual judgment (conversational continuity,
gaze, directness of phrasing, presence state, recent interaction history), not a
keyword match. This is a binding requirement on Phase 2D-B (Identity & Presence) and
Phase 2D-C (Conversation Intelligence) — see the
[Master Blueprint §5.2](../design/phase-2d/00-master-blueprint.md) for the concrete
architectural split between the two. A false-positive response to a mention is a
worse failure than a missed genuine address: unwanted interruption costs trust
(Principle 10) in a way a user simply repeating themselves does not.

## 7. Identity is probabilistic, never assumed.

No future engine may treat "this is the user" (or "this is not the user") as a
binary fact once biometric or contextual identity signals are involved. Every
identity judgment — speaker recognition, face recognition, presence detection —
carries an explicit confidence value, and every downstream consumer of that judgment
must be built to handle "uncertain," not just "yes" and "no" (Bible Part 17's
Confidence Expression model — High/Medium/Low/Unknown — applies to identity
exactly as it applies to reasoning conclusions). A system that silently rounds
"probably the user" up to "the user" the first time it's convenient will eventually
act on a wrong identity with full confidence, which is a privacy and trust failure,
not merely an accuracy one.

## 8. Privacy is foundational, not a feature toggle bolted on afterward.

Every sensing capability this document's governed engines introduce — audio capture,
face recognition, presence detection, gaze tracking — defaults to local processing,
requires explicit per-source consent before activation, and is revocable at any time
with immediate effect (Bible Part 11's "Perception Security," Part 16's "Privacy
First"). Raw biometric data (voiceprints, face embeddings) is never a byproduct
casually retained "in case it's useful later" — it is retained only because a
specific, disclosed capability (returning-user recognition) requires it, and it is
deletable independent of deleting anything else. This is a design constraint on the
Phase 2D-B Identity Registry from its very first line of code, not a hardening pass
applied after the capability already works.

## 9. Trust is earned through consistency, not asserted through confidence.

NOVA does not become more trusted by sounding more certain. It becomes more trusted
by being right about the same kinds of things, in the same way, over a long enough
time that the user stops needing to verify it (Bible Part 17 "Long Term Consistency,"
"Confidence Expression"). This has a direct architectural consequence: personality
and communication behavior must be *stable* by construction (Personality Engine,
unaffected by which underlying model is answering a given request), and
*preference-adaptive* behavior must change only on accumulated evidence, never on a
single data point (Bible Part 16 "Preference Evolution": "Never overwrite existing
preferences immediately. Require consistent evidence."). A companion that flips
its behavior after one observation is not adapting — it is thrashing, and thrashing
erodes exactly the trust this principle is named for.

## 10. Understanding language and speaking language are independent capabilities.

NOVA's ability to comprehend an input and its choice of which language to respond in
are two separate decisions, not one. NOVA should be able to understand the user
regardless of which language they use — including switching mid-conversation —
without that comprehension obligating a matching-language reply. This is why Phase
2D's scope is explicitly **multilingual input, English-first responses**: broad
comprehension is a near-term, achievable engineering target; broad *generation*
quality across many languages is not, yet, at the bar NOVA's personality consistency
(Principle 9) requires. Restricting output language while keeping input
comprehension broad is not a limitation apologized for — it is the deliberate
current shape of the tradeoff between Principle 9 (consistency) and breadth.

## 11. NOVA should eventually understand multiple languages while responding in the user's configured language.

This is the long-term target this document commits every future communication design
to move toward, distinct from Principle 10's near-term default. The user's
**configured** response language is a Digital Twin/Personal Companion preference
(Phase 2D-D), not a per-message inference — NOVA does not guess which language to
reply in from the language it was just addressed in, because that would make output
language unpredictable in exactly the way Principle 9 (consistency) forbids. Widening
past English-first response is a Personality/Communication capability expansion to
plan toward explicitly in a later phase, tracked in the
[Master Blueprint §9 Architectural Risks](../design/phase-2d/00-master-blueprint.md),
not an accidental byproduct of improving the underlying language model.

## 12. Technology should become invisible.

The measure of success is not "the user is impressed by NOVA's interface." It is
"the user stops thinking about the interface at all" (Bible Part 13's "Ultimate
Goal": the user should eventually stop thinking of NOVA as software). Every visible
mechanism — a wake word, a loading indicator, a channel-switch notification, a
clarifying question — is a temporary scaffold justified only by a current sensing or
reasoning limitation, not a permanent feature to polish. As Phase 2D and its
successors mature, the measure of progress is how much of that scaffolding a future
phase gets to remove, not how much of it gets a better animation.

## 13. The room should eventually become part of the interface.

NOVA's presence is not bound to a single window, device, or explicit invocation.
Bible Part 13's "Multi Device Communication" (one conversation continuing across
desktop, mobile, tablet, voice) and Part 11's ambient perception categories (presence,
attention, gaze) point toward the same long-term destination: the physical and
digital environment around the user becomes part of how NOVA is reached, not just
where NOVA's output is displayed. Phase 2D-A/B lay the transport- and
presence-sensing groundwork this depends on; the full realization is explicitly
out of Phase 2D's scope (see the
[Master Blueprint §4](../design/phase-2d/00-master-blueprint.md) — future AR/spatial
interfaces belong to Phase 5 and beyond) but no Phase 2D design may foreclose it —
e.g., no design may hard-code "one active device per conversation" as a structural
assumption.

---

## How this document is used

Every Technical Design Document for a Phase 2D-A/B/C/D engine (and every
communication-relevant engine after it — Perception's later extension in Phase 4,
Digital Twin's later extension in Phase 4, Executive Cognition's coordination of
Communication in Phase 6) must include a short section mapping its major design
decisions to the principles above, the same way every prior TDD has included a
Bible-compliance section. A design decision that cannot be justified against at
least one principle here, or that actively works against one, must be flagged and
resolved before that TDD is approved — not silently shipped and reconciled later.

This document does not change as engines are built. Engines change to satisfy it.
If accumulated implementation experience ever suggests a principle here is wrong,
that is a conversation with the user, resulting in a dated amendment to this
document — never a quiet exception carved out in a lower-level design doc.
