"""記述報告 (prereg v2 §10) — 合成記録で既知の値を返すこと (判定には使わない)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from scripts import skill_lever_battery as bat
from scripts import skill_lever_describe as ds
from scripts import skill_lever_driver as drv
from scripts import skill_lever_scorer as sc

if TYPE_CHECKING:
    from collections.abc import Callable


VALID = {"status": sc.STATUS_COMPUTED, "verdict": sc.VERDICT_PASS}
GATED = {"status": sc.STATUS_COMPUTED, "verdict": sc.VERDICT_INVALID_BATTERY}


def synth(policy: Callable[[drv.Key], str], keys: list[drv.Key]) -> list[sc.Sample]:
    probes = bat.lever_probes()
    out = []
    for i, key in enumerate(keys):
        arm, r, qi, k = key
        seed, sha = sc.expected_sample(*key)
        raw = policy(key)
        out.append(
            sc.Sample(
                i, arm, r, probes[qi].probe_id, k, seed, sha, raw, sc.parse_choice(raw)
            )
        )
    return out


def lookup(key: drv.Key) -> str:
    arm, r, qi, _ = key
    probe = bat.lever_probes()[qi]
    if arm == bat.ARM_C0:
        return bat.layout(r).option_order[probe.probe_id][0]
    return probe.pointed[arm]


def test_lookup_run_description() -> None:
    rep = ds.describe(synth(lookup, drv.schedule()), VALID)
    assert rep["n_transport_failures"] == 0
    assert rep["c0"]["position_rates"] == {"0": 1.0}
    assert rep["c0"]["bottom_rate"] == 0.0
    assert sum(rep["c0"]["pointed_rates"].values()) == pytest.approx(1.0)
    for arm in bat.LEVER_ARMS:
        row = rep["lever_arms"][arm]
        assert row["w_rate"] == 1.0
        assert row["foil_rate"] == 0.0
        assert row["w_rate_minus_c0"] == pytest.approx(
            1.0 - rep["c0"]["pointed_rates"][arm]
        )
    assert rep["old_contrast_confounded_with_priming"]["mean"] == 1.0
    assert rep["estimand"]["C"] == 1.0
    assert set(rep["estimand"]["components"].values()) == {1.0}
    assert rep["estimand"]["p_zero"] == pytest.approx(1 / 2 ** (2 * sc.FROZEN_R))
    assert set(rep["non_exact_label_rate"].values()) == {0.0}


def test_priming_only_is_large_on_the_old_contrast_but_zero_on_c() -> None:
    """状態に出た label を選ぶだけ (A 族 → g_A、B 族 → g_B): 旧型対比は大、C は 0."""

    def priming(key: drv.Key) -> str:
        arm, _, qi, _ = key
        probe = bat.lever_probes()[qi]
        if arm in (bat.ARM_A, bat.ARM_A_ROT):
            return probe.pointed[bat.ARM_A]
        if arm in (bat.ARM_B, bat.ARM_B_ROT):
            return probe.pointed[bat.ARM_B]
        return lookup(key)

    rep = ds.describe(synth(priming, drv.schedule()), VALID)
    assert rep["old_contrast_confounded_with_priming"]["mean"] == 1.0
    assert rep["estimand"]["C"] == 0.0


def test_c0_only_and_verbose_answers() -> None:
    rows = synth(lambda key: f" {lookup(key)} です。", drv.c0_schedule())
    rep = ds.describe(rows, GATED)
    assert rep["estimand"] is None
    assert rep["lever_arms"][bat.ARM_A]["w_rate"] is None
    assert rep["non_exact_label_rate"] == {bat.ARM_C0: 1.0}


@pytest.mark.parametrize(
    "results",
    [
        {"status": sc.STATUS_COMPUTED, "verdict": sc.VERDICT_INVALID_SCORER},
        {"status": sc.STATUS_COMPUTED, "verdict": sc.VERDICT_INVALID_BATTERY},
        {"status": sc.STATUS_NOT_COMPUTED, "verdict": None},
    ],
)
def test_effects_are_suppressed_unless_the_verdict_is_valid(results: dict) -> None:
    rep = ds.describe(synth(lookup, drv.schedule()), results)
    assert rep["effects_suppressed"]
    assert rep["estimand"] is None
    assert rep["old_contrast_confounded_with_priming"] is None
    for row in rep["lever_arms"].values():
        assert row["w_rate"] is None
        assert row["w_rate_minus_c0"] is None
        assert row["bot_rate"] == 0.0  # ⊥ 率は INVALID の説明に要るので残す
    assert rep["c0"]["position_rates"] == {"0": 1.0}
