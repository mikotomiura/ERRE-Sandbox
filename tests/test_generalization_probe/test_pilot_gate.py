"""null pilot の機械判定: 知識確認・⊥ の envelope・spike-in の OC (prereg §8)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import numpy as np
import pytest
from scripts import generalization_probe_battery as bat
from scripts import generalization_probe_pilot_gate as pg
from scripts import generalization_probe_scorer as sc

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

OBSERVED = {
    "model_digest": "d" * 64,
    "ollama_version": "0.32.12",
    "template_sha256": "t" * 64,
}
META = {"request": sc.request_meta(), "observed": OBSERVED}


def blind_masked(arm: str, r: int, p: bat.Probe) -> str | None:
    lever = pg.MASKED_ARMS[arm]
    return bat.option_order(bat.ARM_FAMILY[lever], p.triple, r)[0]


def make_pilot(
    masked: Callable[[str, int, bat.Probe], str | None] = blind_masked,
    know: Callable[[int, int], str] | None = None,
) -> list[sc.Sample]:
    """pilot の全 grid の合成記録。know(i, k) = key i の試行 k の答え (既定は正答)."""
    out = []
    idx = 0
    rs = range(bat.PILOT_R0, bat.PILOT_R0 + bat.PILOT_R)
    for arm in pg.MASKED_ARMS:
        for r in rs:
            for p in bat.probes():
                seed, sha = pg.expected(arm, r, p.probe_id, 0)
                label = masked(arm, r, p)
                raw = label if label is not None else "わからない"
                out.append(
                    sc.Sample(
                        idx, arm, r, p.probe_id, 0, seed, sha, raw, sc.parse_choice(raw)
                    )
                )
                idx += 1
    keys = bat.all_keys()
    for i, key in enumerate(keys):
        for k in range(bat.KNOW_K):
            pid = pg.know_probe_id(i)
            seed, sha = pg.expected(pg.ARM_KNOW, 0, pid, k)
            raw = know(i, k) if know else bat.key_class(key)
            out.append(
                sc.Sample(
                    idx, pg.ARM_KNOW, 0, pid, k, seed, sha, raw, pg.parse_class(raw)
                )
            )
            idx += 1
    return out


def decide(samples: list[sc.Sample], **kw: object) -> dict[str, object]:
    kwargs: dict[str, object] = {"certified": True, "selected_r": 6}
    kwargs.update(kw)
    meta = kwargs.pop("meta", META)
    return pg.decide_pilot(samples, meta, **kwargs)  # type: ignore[arg-type]


def test_parse_class() -> None:
    assert pg.parse_class("Bird") == "bird"
    assert pg.parse_class("「魚」= fish") == "fish"
    assert pg.parse_class("bird or fish") is None
    assert pg.parse_class("<think>insect</think>bird") == "bird"
    assert pg.parse_class("birds") is None


def test_pilot_grid_size() -> None:
    assert len(pg.pilot_grid()) == 4 * 6 * 24 + 36 * 3
    assert pg.structure_violations(make_pilot()) == []


def test_pilot_clean_go() -> None:
    res = decide(make_pilot())
    assert res["decision"] == pg.DECISION_GO
    assert res["R"] == 6
    assert res["masked_max_bottom"] == 0.0
    assert res["observed"] == OBSERVED


def test_pilot_respects_selected_r() -> None:
    res = decide(make_pilot(), selected_r=12)
    assert res["decision"] == pg.DECISION_GO
    assert res["R"] == 12


def test_knowledge_gate() -> None:
    def wrong_twice(i: int, k: int) -> str:
        truth = bat.key_class(bat.all_keys()[i])
        wrong = next(c for c in bat.CLASSES if c != truth)
        return wrong if i == 30 and k < 2 else truth

    res = decide(make_pilot(know=wrong_twice))
    assert res["decision"] == pg.DECISION_STOP
    assert res["reasons"][0] == "knowledge"
    assert res["knowledge_failures"] == [bat.all_keys()[30]]

    def wrong_once(i: int, k: int) -> str:
        truth = bat.key_class(bat.all_keys()[i])
        wrong = next(c for c in bat.CLASSES if c != truth)
        return wrong if i == 30 and k == 0 else truth

    assert decide(make_pilot(know=wrong_once))["decision"] == pg.DECISION_GO


def test_knowledge_position_policies_fail() -> None:
    """常に先頭 / 末尾を答える方策は knowledge で止まる.

    全 key で 1/3 しか当たらない (Codex HIGH-2)。
    """
    for pos in (0, -1):
        res = decide(make_pilot(know=lambda i, k, pos=pos: bat.know_options(i, k)[pos]))
        assert res["decision"] == pg.DECISION_STOP
        assert len(res["knowledge_failures"]) == 36


def test_pilot_envelope() -> None:
    def bot_a(arm: str, r: int, p: bat.Probe) -> str | None:
        return None if arm == "M_A" and p.index % 3 == 0 else blind_masked(arm, r, p)

    res = decide(make_pilot(bot_a))
    assert res["decision"] == pg.DECISION_STOP
    assert res["reasons"] == ["envelope"]


def test_pilot_stop_on_power(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pg, "oc_for_r", lambda _x, _nb, r: {"R": r, "ok": False})
    res = decide(make_pilot())
    assert res["decision"] == pg.DECISION_STOP
    assert res["reasons"] == ["power"]
    assert [o["R"] for o in res["oc"]] == [6, 12, 18]


def _oc(pass_: float, no_go: float, c: float) -> dict[str, float]:
    return {"pass": pass_, "no_go": no_go, "realized_C": c}


def test_oc_conditions_each_matter() -> None:
    """OC の 5 条件を 1 つずつ破ると不合格になる (Codex MEDIUM-8)."""
    cap = 0.065
    good = (_oc(0.9, 0.0, 0.6), _oc(0.0, 0.9, 0.0), _oc(0.04, 0.04, 0.3))
    assert all(pg.oc_ok(*good, cap).values())
    cases = {
        "calibrated": (_oc(0.9, 0.0, 0.62), good[1], good[2]),
        "power_pass": (_oc(0.79, 0.0, 0.6), good[1], good[2]),
        "power_no_go": (good[0], _oc(0.0, 0.79, 0.0), good[2]),
        "size_pass": (good[0], good[1], _oc(0.066, 0.04, 0.3)),
        "size_no_go": (good[0], good[1], _oc(0.04, 0.066, 0.3)),
    }
    for flag, args in cases.items():
        checks = pg.oc_ok(*args, cap)
        assert checks[flag] is False, flag
        assert sum(not v for v in checks.values()) == 1, flag


def test_oc_for_r_uses_the_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake(x, nb, r_count, target, n_resample, seed):
        del x, nb, r_count, n_resample, seed
        return {
            "pass": 0.9 if target > 0.5 else 0.0,
            "no_go": 0.9 if target == 0.0 else 0.0,
            "realized_C": target,
            "lambda": 0.5,
            "direction": 1,
        }

    monkeypatch.setattr(pg, "spike_in_oc", fake)
    oc = pg.oc_for_r(np.zeros(1), np.zeros(1), 6)
    assert oc["ok"] is True
    assert oc["size_cap"] == pytest.approx(pg.size_rate_cap(6))

    def weak(x, nb, r_count, target, n_resample, seed):
        out = fake(x, nb, r_count, target, n_resample, seed)
        if target > 0.5:
            out["pass"] = 0.5
        return out

    monkeypatch.setattr(pg, "spike_in_oc", weak)
    oc_weak = pg.oc_for_r(np.zeros(1), np.zeros(1), 6)
    assert oc_weak["ok"] is False
    assert oc_weak["checks"]["power_pass"] is False


def test_size_rate_cap() -> None:
    assert pg.size_rate_cap(6) == pytest.approx(0.065)
    assert pg._binom_upper_tail(int(0.065 * 2000) + 1, 2000, 0.05) * 6 <= 0.01


def test_pilot_requires_cert() -> None:
    res = decide(make_pilot(), certified=False)
    assert res["decision"] == pg.DECISION_STOP
    assert res["reasons"][0] == "records"


def test_pilot_requires_selected_r() -> None:
    res = decide(make_pilot(), selected_r=None)
    assert res["decision"] == pg.DECISION_STOP
    assert "the sketch selected no R (door-close before the pilot)" in res["reasons"]


def test_pilot_meta() -> None:
    bad = {"request": {**sc.request_meta(), "model": "other"}, "observed": OBSERVED}
    assert decide(make_pilot(), meta=bad)["decision"] == pg.DECISION_STOP
    no_obs = {"request": sc.request_meta(), "observed": {}}
    assert decide(make_pilot(), meta=no_obs)["decision"] == pg.DECISION_STOP


def test_pilot_structure_seed() -> None:
    samples = make_pilot()
    samples[10] = sc.Sample(**{**vars(samples[10]), "seed": 7})
    assert pg.structure_violations(samples) == ["seed differs from the pilot schedule"]


def test_pilot_structure_prompt_and_parse() -> None:
    samples = make_pilot()
    samples[10] = sc.Sample(**{**vars(samples[10]), "prompt_sha256": "0" * 64})
    samples[-1] = sc.Sample(**{**vars(samples[-1]), "parsed": "bird"})
    assert pg.structure_violations(samples) == [
        "prompt differs from the pilot renderer",
        "recorded parse differs from re-parse",
    ]


def test_pilot_not_computed() -> None:
    samples = make_pilot()
    samples[5] = sc.Sample(**{**vars(samples[5]), "raw": None, "parsed": None})
    assert decide(samples)["status"] == pg.STATUS_NOT_COMPUTED
    assert decide(make_pilot()[:-1])["status"] == pg.STATUS_NOT_COMPUTED


def test_cell_scores() -> None:
    def own_w(arm: str, r: int, p: bat.Probe) -> str | None:
        del r
        return p.pointed[pg.MASKED_ARMS[arm]]

    x, nb = pg.cell_scores(make_pilot(own_w))
    assert np.all(x == 1.0)
    assert np.all(nb == 1.0)
    x0, _ = pg.cell_scores(make_pilot())
    assert float(x0.mean()) == pytest.approx(0.0)


def test_injection_calibrates() -> None:
    rng = np.random.default_rng(0)
    x = rng.choice([-1.0, 0.0, 1.0], size=(2, 8, 6, 3, 2), p=[0.2, 0.5, 0.3])
    nb = (rng.random(x.shape) > 0.1).astype(float)
    x = x * nb
    c, live = float(x.mean()), float(nb.mean())
    for target in (0.0, sc.TAU, sc.DELTA_PLANT):
        lam, sign = pg.injection(x, nb, target)
        expected = c + sign * lam * (live - sign * c)
        assert expected == pytest.approx(target)
    assert pg.injection(x, nb, -0.2)[1] == -1
    assert pg.injection(x, nb, 0.6)[1] == 1


def test_strata_picks_preserve_the_rotation() -> None:
    """再標本化した pilot の単位は、本走の単位と表示の回転が同じ (Codex MEDIUM-7)."""
    pick = pg.strata_picks(18, 50, np.random.default_rng(0))
    assert pick.shape == (50, 2, 8, 18)
    for j in range(bat.N_TRIPLES):
        for r in range(18):
            rot = (bat.PILOT_R0 + pick[:, :, j, r] + j) % 3
            assert np.all(rot == (r + j) % 3)


def test_resampling_uses_all_replicates() -> None:
    x = np.zeros((2, 8, 6, 3, 2))
    x[:, :, 0] = 1.0
    nb = np.ones_like(x)
    oc = pg.spike_in_oc(x, nb, 18, sc.DELTA_PLANT, 2000, 1)
    assert oc["realized_C"] == pytest.approx(sc.DELTA_PLANT, abs=0.01)


def test_oc_size_at_tau_small() -> None:
    x0, nb0 = pg.cell_scores(make_pilot())
    oc = pg.spike_in_oc(x0, nb0, 6, sc.TAU, 2000, 3)
    assert oc["pass"] <= 0.05
    assert oc["no_go"] <= 0.05


def test_cli_end_to_end(tmp_path: Path) -> None:
    rec = tmp_path / "records.jsonl"
    rec.write_text(
        "\n".join(json.dumps(vars(s)) for s in make_pilot()) + "\n", encoding="utf-8"
    )
    met = tmp_path / "meta.json"
    met.write_text(json.dumps(META), encoding="utf-8")
    sketch = tmp_path / "sketch.json"
    sketch.write_text(json.dumps({"selection": {"selected_R": 6}}), encoding="utf-8")
    out = tmp_path / "gate.json"
    args = [
        "--records",
        str(rec),
        "--meta",
        str(met),
        "--cert",
        str(tmp_path / "none.json"),
        "--sketch",
        str(sketch),
        "--out",
        str(out),
    ]
    pg.main(args)
    res = json.loads(out.read_text(encoding="utf-8"))
    assert res["decision"] == pg.DECISION_STOP  # certification が無い
    assert set(res["inputs_sha256"]) == {"records", "meta", "cert", "sketch"}
    assert res["inputs_sha256"]["cert"] is None


def test_oc_uses_the_main_run_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    """OC の ⊥ gate は本走と同じ上限を使う (Codex 2 回目 MEDIUM-4)."""

    def bot_some(arm: str, r: int, p: bat.Probe) -> str | None:
        return None if p.index == 0 else blind_masked(arm, r, p)

    x, nb = pg.cell_scores(make_pilot(bot_some))
    oc = pg.spike_in_oc(x, nb, 6, sc.DELTA_PLANT, 400, 1)
    assert oc["pass"] > 0.5
    monkeypatch.setattr(sc, "envelope_bottom_max", lambda _m: 0.0)
    strict = pg.spike_in_oc(x, nb, 6, sc.DELTA_PLANT, 400, 1)
    assert strict["pass"] == 0.0


def test_pilot_seed_shared_within_triple() -> None:
    for arm in pg.MASKED_ARMS:
        for j in range(bat.N_TRIPLES):
            seeds = {
                pg.expected(arm, 50, p.probe_id, 0)[0] for p in bat.triple_probes(j)
            }
            assert len(seeds) == 1
