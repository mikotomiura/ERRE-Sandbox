"""Evidence layer — post-hoc metric computation over persisted run data.

M8 baseline-quality-metric (L6 D1 残り半分) の pure-function 集合。
live run 側は sqlite への永続化のみ担当、集計は offline で本 module の
``metrics.aggregate`` を通して実行する (``erre-sandbox baseline-metrics``
CLI が唯一の entry)。

Layer dependency:

* allowed: ``erre_sandbox.memory``, ``erre_sandbox.schemas``
* forbidden: ``world``, ``integration``, ``cognition``, ``ui``
"""

from erre_sandbox.evidence.metrics import (
    aggregate,
    compute_bias_fired_rate,
    compute_cross_persona_echo_rate,
    compute_self_repetition_rate,
)

__all__ = [
    "aggregate",
    "compute_bias_fired_rate",
    "compute_cross_persona_echo_rate",
    "compute_self_repetition_rate",
]
