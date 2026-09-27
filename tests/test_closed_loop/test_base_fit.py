"""実測 base の封印 (prereg v4 §6): 凍結入力の sha・再推定 = 定数・固着の事実."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scripts import closed_loop_sim as sim

_ROOT = Path(__file__).resolve().parents[2]


def test_inputs_are_the_sealed_files() -> None:
    assert sim.input_sha256(_ROOT) == sim.MEASURED_INPUT_SHA256


def test_refit_equals_sealed_constants() -> None:
    data = sim.c0_fit_data(_ROOT)
    assert len(data) == 360
    alpha, beta = sim.fit_measured_base(data)
    np.testing.assert_allclose(alpha, np.array(sim.MEASURED_ALPHA), atol=1e-6)
    np.testing.assert_allclose(beta, np.array(sim.MEASURED_BETA), atol=1e-6)


def test_v2_v3_c0_overlap_is_byte_identical() -> None:
    """重なる 120 key で v2 と v3 の C0 raw は一致する (統合して 360 件にする根拠)."""

    def c0(rel: str) -> dict[tuple[int, str, int], str]:
        rows = [
            json.loads(x)
            for x in (_ROOT / rel).read_text(encoding="utf-8").splitlines()
            if x.strip()
        ]
        return {
            (r["replicate"], r["probe_id"], r["k"]): r["raw"]
            for r in rows
            if r["arm"] == "C0"
        }

    a, b = c0(sim.V2_SAMPLES), c0(sim.V3_SAMPLES)
    common = set(a) & set(b)
    assert len(common) == 120
    assert all(a[k] == b[k] for k in common)


def test_measured_base_rarely_picks_two_rules() -> None:
    """rain → read_book と clear → tend_moss は全巡回の平均で 0.02 未満 (固着の源)."""
    from scripts import closed_loop_battery as bat

    for weather, label in (("rain", "read_book"), ("clear", "tend_moss")):
        om = bat.dev_omega(weather)
        probs = []
        for s in range(4):
            opts = om[s:] + om[:s]
            probs.append(
                sim.base_option_probs("measured", weather, opts)[opts.index(label)]
            )
        assert np.mean(probs) < 0.02


def test_base_probs_are_distributions() -> None:
    from scripts import closed_loop_battery as bat

    opts = bat.dev_omega("wind")
    for base in sim.BASES:
        p = sim.base_option_probs(base, "wind", opts)
        assert p.shape == (4,)
        assert abs(p.sum() - 1.0) < 1e-12
    assert sim.base_option_probs("label_skew", "wind", opts)[0] == 0.7
    assert sim.base_option_probs("position_skew", "wind", opts[::-1])[0] == 0.7
