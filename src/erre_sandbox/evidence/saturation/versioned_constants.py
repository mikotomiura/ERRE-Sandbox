"""Frozen §3.0' thresholds for the **versioned** saturation shadow scorer.

This module is the single source of truth for the new thresholds the versioned
measurement ADR (`.steering/20260613-versioned-measurement-adr/`) pre-registered
in §3.0' — the values that the versioned ``retained-across-fingerprint-change``
gate adds on top of the frozen saturation §3.0 table. Like the frozen
:mod:`.constants`, every value here was fixed **before** any result was seen
(ADR §3.0' / decisions F-2 forking-paths guard): a value can only change by a
deliberate edit here, which itself requires a superseding ADR. No value is read
off a result and then tuned.

The unchanged §3.0 thresholds the versioned gate inherits verbatim
(``ENGAGEMENT_MIN`` / ``MIN_ACTIVE_CHANNELS`` / ``TRANSIENT_HIGH`` / ``THETA_HIGH``
/ ``THETA_LOW`` / ``N_SEEDS`` / ``EPSILON_MOD`` / ``T_WARMUP`` /
``MAX_TOTAL_MODULATION``) are **imported** from :mod:`.constants`, never
re-spelled here — the versioned scorer differs from the frozen scorer only in
the ``drop_rate`` branch (ADR §3), so it must not introduce a second copy of an
already-frozen value.
"""

from __future__ import annotations

from typing import Final

# --- §3.0' new frozen thresholds (versioned retention gate) -------------------

RHO_RETAIN_MIN: Final[float] = 0.50
"""``retained_across_fp_change_rate >= this`` is required (ADR §3.0').

A normative *half-or-more* requirement: a passing ON arm retains the modulation
across **at least half** of its clean cross-fp trials. Separated from the OFF
baseline, which is structurally 0 (the frozen reconcile drops every cross-fp
modulation). The old "DROP_HIGH mirror" rationale was withdrawn (Codex MED-1):
drop_rate and retention have different denominators and events, so ``>= 0.50``
is "half or more", not a mirror image."""

MIN_D_FP: Final[int] = 30
"""Minimum cross-fp trial count ``D_fp`` per partition for the rate to mean
anything (ADR §3.0', Codex HIGH-1). Closes the ``D_fp=1, R=1 -> 1.0``
trivial-pass. Set a priori from the disposition forensic's ~38 eligible channels
times several cross-fp trials each."""

CROSSFP_CHANNEL_MIN: Final[int] = 5
"""Minimum number of **distinct** channels that experienced >= 1 cross-fp trial
(``n_crossfp_channels``), at the same level as ``MIN_ACTIVE_CHANNELS`` (ADR
§3.0'). Prevents a single channel's many transitions from dominating the
denominator."""

RETAINED_CHANNEL_MIN: Final[int] = 3
"""Minimum number of **distinct** channels that retained at least once
(``n_retained_channels``, ADR §3.0', Codex HIGH-1). Makes "few-channel
retention" miss the gate — the distinct-channel breadth floor that keeps the
reachability argument from being a trivial-pass."""

DISAPPEAR_MARGIN: Final[float] = 0.05
"""Non-inferiority slack for ``channel_disappearance_rate[ON] <=
channel_disappearance_rate[OFF] + this`` (ADR §3.0'). Bounds how much worse the
ON arm's disappearance may be before we suspect it inflated retention by
dropping hard-to-keep channels (Codex HIGH-1)."""

H_SAFETY: Final[int] = 20
"""External TTL safety ceiling in ticks for a retained modulation (ADR §3.0',
Codex HIGH-3). A retained modulation that persists more than this many ticks past
its **first cross-fp retention** is stale -> V2 guard FAIL. The III-a STM horizon
**must be <= H_SAFETY** (the measurement must not self-conform to the
intervention spec). The run must also include an expiry-observation window past
H_SAFETY; an episode still active at run end within the window is right-censored
(V2 INCONCLUSIVE), never a silent PASS (Codex HIGH-3)."""

CANCEL_HIGH: Final[float] = 0.30
"""``cancel_rate >= this`` -> V3 guard FAIL (ADR §3.0' / §4). The share of
joinable retention ticks where a fresh adopted nudge's ``direction`` opposes the
retained modulation's realised direction (a stale modulation fighting new intent)
that we treat as dangerous."""

__all__ = [
    "CANCEL_HIGH",
    "CROSSFP_CHANNEL_MIN",
    "DISAPPEAR_MARGIN",
    "H_SAFETY",
    "MIN_D_FP",
    "RETAINED_CHANNEL_MIN",
    "RHO_RETAIN_MIN",
]
