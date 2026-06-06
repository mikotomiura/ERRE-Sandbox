"""SWM hint-engagement instrument — trace persistence + post-hoc scoring.

The instrument decomposes the *engagement floor* (the disposition ADR's binding
constraint) into three mutually-exclusive, exhaustive states — (a) emission rarity,
(b) adoption rejection, (c) direction inconsistency — so a real run can route to the
right downstream probe (engagement instrument ADR §2 / §6).

Layering (DA-EII-9): this package is the **evidence** half — trace DDL / row builder
(:mod:`.trace_ddl`), frozen thresholds (:mod:`.constants`), and the loader + decision
table (:mod:`.loader`). It imports only ``contracts`` / stdlib / duckdb, never
``cognition``. The cognition-time classifier and carrier builder live in
``cognition.hint_engagement`` (the runtime cannot import ``evidence``); the loader
aggregates the **stored** disposition labels and never re-runs classification.
"""

from __future__ import annotations
