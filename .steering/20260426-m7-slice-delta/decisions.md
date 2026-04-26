# M7 Slice δ — Decision Log

## Plan-mode hybrid (post /reimagine)

Recorded in ``design-final.md``. Adopted picks (from v1 + v2 cross-comparison):

| Axis | Adopted | Note |
|---|---|---|
| 1a decay | v1 (neuroticism 0.02-0.08) | Observability priority over v2's agreeableness |
| 1b impact | v2 (structural features) | JP lex dropped — brittle without MeCab |
| 1c weight | v1 (extraversion 0.5-1.5) | Wider range = more contrast |
| 2 negative | v1 antagonism table | Trait-distance fails empirically at N=3 (computed) |
| 3 belief | v2 (typed enum + simulation-derived threshold) | Cleaner for m8 Critics |
| 4 SQL | v2 (extend only, no wrapper) | YAGNI |
| 5 zone | v2 (no DB migration; AgentState-resident) | v1 over-engineered |
| C3 #3 | defer to ε | Cost undersized; bundle stays in 15h envelope |

## C5 calibration retune

The first-pass C3 tunables (impact 0.6/0.4, antagonism -0.30) saturated
the recurrence in 1-2 turns, defeating the belief-promotion threshold.
The C5 simulation regression test
(``tests/test_cognition/test_relational_simulation.py``) caught this and
drove the retune to:

* ``_IMPACT_ADDRESSEE_WEIGHT``: 0.6 → 0.08
* ``_IMPACT_LENGTH_WEIGHT``: 0.4 → 0.04
* antagonism magnitude: -0.30 → -0.10

Result: saturating dyads cross |affinity|>0.45 between turns 6-12, inside
the live G-GEAR window. See ``observation.md`` for per-pair simulation
values.

## C7 — Godot GUT scope

The design-final mentioned "Godot GUT — `ReasoningPanel` 'last in <zone>'
rendering fixture" but the project has no GUT runner configured. C7
shipped the GDScript change without a GUT-side test. The wire-level
guarantee is provided by C1's ``test_relationship_bond_round_trip_with_zone``
in pytest plus the regenerated agent_state JSON schema golden file. If
GUT is later set up (m9-lora candidate), a focused
``ReasoningPanelTest.gd`` should pin the format.

## C3 #3 — Persona-distinct silhouette deferral

User-confirmed via AskUserQuestion in Plan mode. Deferred to ε (M9-lora
will revisit visual differentiation alongside persona voice work). γ's
C3 trinity remains at 2/3 closed (Relationships UI + visual capsule).

## Bundle scope drift

None. All 8 commits landed within the design-final scope. No mid-flight
addition or deletion. Bundle total trended ~12.9h actual against the
14.4h estimate (slight under-shoot, mostly from C5's simulation test
revealing the calibration issue early so retune was cheap).

## Pre-existing flake annotation

``tests/test_memory/test_store.py::test_concurrent_add_does_not_raise_systemerror``
intermittently shows in the full suite as failing or as the recipient of
an ``unraisableexception`` warning attribution. This is a pre-existing
socket-leak issue (introduced before δ; reproducible on
``main`` HEAD) and has no relation to any δ commit. Standalone the test
passes; in the full suite it occasionally claims a warning that pytest's
``unraisableexception`` plugin attributes to the next-running test.
Cleanup is L6 backlog scope.
