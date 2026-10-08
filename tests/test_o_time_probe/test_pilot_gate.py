"""null pilot の機械判定: M0 の陽性対照・⊥ の envelope・spike-in の OC (prereg §8)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import numpy as np
import pytest
from scripts import o_time_probe_battery as bat
from scripts import o_time_probe_pilot_gate as pg
from scripts import o_time_probe_scorer as sc

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

OBSERVED = {
    "model_digest": "d" * 64,
    "ollama_version": "0.32.12",
    "template_sha256": "t" * 64,
}
META = {"request": sc.request_meta(), "observed": OBSERVED}
R_SEL = 24

Choose = "Callable[[str, str, bat.Unit], str | None]"


def _first_match_label(lever: str, enc: str, u: bat.Unit, mode: str) -> str:
    """状態の中で probe の部屋の最初の行の label (札を読まない写し)."""
    text = bat.render_state(lever, enc, u, mode)
    room = bat.ROOMS[u.room]
    for line in text.splitlines()[1:]:
        if f" {room} の部屋" in line:
            return line.split("行動: ")[1].split(" ")[0]
    raise AssertionError


def blind_masked(lever: str, enc: str, u: bat.Unit) -> str | None:
    return _first_match_label(lever, enc, u, "masked")


def lookup_m0(lever: str, enc: str, u: bat.Unit) -> str | None:
    return _first_match_label(lever, enc, u, "m0")


def make_pilot(
    masked: Callable[[str, str, bat.Unit], str | None] = blind_masked,
    m0: Callable[[str, str, bat.Unit], str | None] = lookup_m0,
) -> list[sc.Sample]:
    """pilot の全 grid の合成記録.

    masked(lever, enc, unit)・m0(lever, enc, unit) → label (None は ⊥)。
    """
    out = []
    idx = 0
    for arms, choose in ((pg.MASKED_ARMS, masked), (pg.M0_ARMS, m0)):
        for name, lever in arms.items():
            fi = bat.ARM_FAMILY[lever]
            for u in bat.pilot_units():
                if u.family != fi:
                    continue
                for enc in bat.ENCODINGS:
                    pid = sc.probe_id(u.room)
                    seed, sha = pg.expected(name, enc, u.replicate, pid, 0)
                    label = choose(lever, enc, u)
                    raw = label if label is not None else "わからない"
                    out.append(
                        sc.Sample(
                            idx,
                            name,
                            enc,
                            u.replicate,
                            pid,
                            0,
                            seed,
                            sha,
                            raw,
                            sc.parse_choice(raw),
                        )
                    )
                    idx += 1
    return out


def decide(samples: list[sc.Sample], **kw: object) -> dict[str, object]:
    kwargs: dict[str, object] = {"certified": True, "selected_r": R_SEL}
    kwargs.update(kw)
    meta = kwargs.pop("meta", META)
    return pg.decide_pilot(samples, meta, **kwargs)  # type: ignore[arg-type]


def test_pilot_grid_size() -> None:
    assert len(pg.pilot_grid()) == 2 * 4 * 6 * 6 * 2
    assert pg.structure_violations(make_pilot()) == []


def test_expected_uses_the_pilot_namespaces() -> None:
    u = bat.pilot_units()[0]
    s_masked, sha_masked = pg.expected(
        "M_AB", "asc", u.replicate, sc.probe_id(u.room), 0
    )
    s_m0, sha_m0 = pg.expected("P_AB", "asc", u.replicate, sc.probe_id(u.room), 0)
    assert s_masked == bat.sample_seed("masked_fam0", u.replicate, u.room, 0)
    assert s_m0 == bat.sample_seed("m0_fam0", u.replicate, u.room, 0)
    assert sha_masked == sc.messages_sha256(
        bat.render_messages("AB", "asc", u, "masked")
    )
    assert sha_m0 == sc.messages_sha256(bat.render_messages("AB", "asc", u, "m0"))
    assert (
        pg.expected("M_BA", "asc", u.replicate, sc.probe_id(u.room), 0)[1] == sha_masked
    )


def test_pilot_clean_go() -> None:
    res = decide(make_pilot())
    assert res["decision"] == pg.DECISION_GO
    assert res["R"] == R_SEL
    assert res["masked_max_bottom"] == 0.0
    assert res["observed"] == OBSERVED
    assert res["null_C"] == 0.0
    assert res["m0"]["passed"] is True
    assert res["m0"]["C"] == pytest.approx(1.0)
    assert res["describe"]["masked_discordance"] == 0.0


def test_pilot_m0_stop() -> None:
    """M0 の陽性対照が凍結した PASS の規則を通らなければ STOP (lookup すら動かない)."""

    def third_m0(lever: str, enc: str, u: bat.Unit) -> str | None:
        del enc
        return bat.third_label(bat.ARM_FAMILY[lever], u.room)

    res = decide(make_pilot(m0=third_m0))
    assert res["decision"] == pg.DECISION_STOP
    assert res["reasons"] == ["m0"]
    assert res["m0"]["passed"] is False


def test_pilot_m0_requires_components() -> None:
    """lookup の C が大きくても、成分の 1 つが 0 なら M0 を通らない.

    凍結した PASS の規則のまま。
    """

    def m0_no_dc(lever: str, enc: str, u: bat.Unit) -> str | None:
        if lever == bat.ARM_DC or (lever == bat.ARM_BA and enc == "ago"):
            return bat.third_label(bat.ARM_FAMILY[lever], u.room)
        return lookup_m0(lever, enc, u)

    res = decide(make_pilot(m0=m0_no_dc))
    assert res["m0"]["components"][3] == 0.0
    assert res["m0"]["C"] > sc.TAU
    assert res["decision"] == pg.DECISION_STOP
    assert res["reasons"] == ["m0"]


def test_pilot_envelope() -> None:
    def bot_ab(lever: str, enc: str, u: bat.Unit) -> str | None:
        return (
            None if lever == "AB" and u.room % 2 == 0 else blind_masked(lever, enc, u)
        )

    res = decide(make_pilot(bot_ab))
    assert res["decision"] == pg.DECISION_STOP
    assert res["reasons"] == ["envelope"]


def test_pilot_stop_on_power(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pg, "oc_for_r", lambda _x, _nb, r: {"R": r, "ok": False})
    res = decide(make_pilot())
    assert res["decision"] == pg.DECISION_STOP
    assert res["reasons"] == ["power"]
    assert res["oc"]["R"] == R_SEL


def test_pilot_records_stop() -> None:
    res = decide(make_pilot(), certified=False)
    assert res["decision"] == pg.DECISION_STOP
    assert res["reasons"][0] == "records"
    res2 = decide(make_pilot(), selected_r=None)
    assert res2["decision"] == pg.DECISION_STOP
    assert "the sketch selected no R (door-close before the pilot)" in res2["reasons"]
    bad = make_pilot()
    bad[3] = sc.Sample(**{**vars(bad[3]), "seed": 1})
    res3 = decide(bad)
    assert res3["decision"] == pg.DECISION_STOP
    assert "seed differs from the pilot schedule" in res3["reasons"]


def test_pilot_meta_stop() -> None:
    bad = {"request": {**sc.request_meta(), "think": True}, "observed": OBSERVED}
    res = decide(make_pilot(), meta=bad)
    assert res["decision"] == pg.DECISION_STOP
    assert "meta: request differs from the frozen values" in res["reasons"]


def test_pilot_not_computed() -> None:
    samples = make_pilot()
    samples[5] = sc.Sample(**{**vars(samples[5]), "raw": None, "parsed": None})
    res = decide(samples)
    assert res["status"] == pg.STATUS_NOT_COMPUTED
    assert res["decision"] is None
    assert decide(make_pilot()[:-1])["status"] == pg.STATUS_NOT_COMPUTED


def test_structure_checks() -> None:
    samples = make_pilot()
    dup = sc.Sample(**{**vars(samples[10]), "call_index": 99_999})
    assert "duplicate (arm, encoding, replicate, probe, k)" in pg.structure_violations(
        [*samples, dup]
    )
    off = sc.Sample(**{**vars(samples[10]), "replicate": 0})
    assert "record outside the pilot grid" in pg.structure_violations(
        [*samples[:10], off]
    )
    sha = sc.Sample(**{**vars(samples[10]), "prompt_sha256": "0" * 64})
    assert pg.structure_violations([*samples[:10], sha, *samples[11:]]) == [
        "prompt differs from the pilot renderer"
    ]


def test_discordance() -> None:
    """masked の同じ書き方の 2 arm が違う label を選んだ率 (記述)."""

    def disagree(lever: str, enc: str, u: bat.Unit) -> str | None:
        if lever in bat.FWD and u.room == 0:
            return bat.third_label(bat.ARM_FAMILY[lever], u.room)
        return blind_masked(lever, enc, u)

    res = decide(make_pilot(disagree))
    assert res["describe"]["masked_discordance"] == pytest.approx(1 / 6)


def test_cell_scores_shapes() -> None:
    x, nb, other = pg.cell_scores(make_pilot(), "m0")
    assert x.shape == (2, 6, 6, 2, 2)
    assert np.all(x == 1.0)
    assert np.all(nb == 1.0)
    assert np.all(other == 0.0)
    xm, _, _ = pg.cell_scores(make_pilot(), "masked")
    assert np.all(xm.sum(axis=-1) == 0.0)  # 2 arm で同じ label → 得点が逆符号


def test_components_order() -> None:
    x = np.zeros((2, 6, 6, 2, 2))
    x[..., 0, 0] = 1.0  # fwd asc
    x[..., 1, 1] = -1.0  # bwd ago
    assert pg.components(x).tolist() == [1.0, 0.0, 0.0, -1.0]


def _oc(pass_: float, no_go: float, c: float) -> dict[str, float]:
    return {"pass": pass_, "no_go": no_go, "realized_C": c}


def test_oc_conditions_each_matter() -> None:
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
    oc = pg.oc_for_r(np.zeros(1), np.zeros(1), 24)
    assert oc["ok"] is True
    assert oc["size_cap"] == pytest.approx(pg.size_rate_cap(2))

    def weak(x, nb, r_count, target, n_resample, seed):
        out = fake(x, nb, r_count, target, n_resample, seed)
        if target > 0.5:
            out["pass"] = 0.5
        return out

    monkeypatch.setattr(pg, "spike_in_oc", weak)
    oc_weak = pg.oc_for_r(np.zeros(1), np.zeros(1), 24)
    assert oc_weak["ok"] is False
    assert oc_weak["checks"]["power_pass"] is False


def test_size_rate_cap() -> None:
    cap = pg.size_rate_cap(2)
    x = round(cap * 2000)
    assert pg._binom_upper_tail(x + 1, 2000, 0.05) * 2 <= 0.01
    assert pg._binom_upper_tail(x, 2000, 0.05) * 2 > 0.01


def test_injection_calibrates() -> None:
    x, nb, _ = pg.cell_scores(make_pilot(), "masked")
    for target in (0.0, sc.TAU, sc.DELTA_PLANT):
        oc = pg.spike_in_oc(x, nb, 24, target, 200, 1)
        assert oc["realized_C"] == pytest.approx(target, abs=0.02)
    lam, sign = pg.injection(np.full(4, 0.2), np.ones(4), 0.0)
    assert sign == -1
    assert lam == pytest.approx(0.2 / 1.2)


def test_strata_keep_the_rotation() -> None:
    picks = pg.strata_picks(24, 50, np.random.default_rng(0))
    for i in range(6):
        for r in range(24):
            rot = (r + i) % 3
            assert set(
                ((bat.PILOT_R0 + picks[:, :, i, r] + i) % 3).ravel().tolist()
            ) == {rot}


def test_spike_in_power_on_blind_null() -> None:
    x, nb, _ = pg.cell_scores(make_pilot(), "masked")
    oc = pg.oc_for_r(x, nb, 24)
    assert oc["checks"]["calibrated"] is True
    assert oc["ok"] is True


def test_cli_end_to_end(tmp_path: Path) -> None:
    samples = make_pilot()
    rec = tmp_path / "records.jsonl"
    rec.write_text(
        "\n".join(json.dumps(vars(s), ensure_ascii=False) for s in samples) + "\n",
        encoding="utf-8",
    )
    met = tmp_path / "meta.json"
    met.write_text(json.dumps(META), encoding="utf-8")
    cert = tmp_path / "cert.json"
    cert.write_text("{}", encoding="utf-8")
    sketch = tmp_path / "sketch.json"
    sketch.write_text(
        json.dumps({"selection": {"selected_R": R_SEL}}), encoding="utf-8"
    )
    out = tmp_path / "gate.json"
    pg.main(
        [
            *("--records", str(rec)),
            *("--meta", str(met)),
            *("--cert", str(cert)),
            *("--sketch", str(sketch)),
            *("--out", str(out)),
        ]
    )
    res = json.loads(out.read_text(encoding="utf-8"))
    assert res["decision"] == pg.DECISION_STOP
    assert "certification missing, stale, or not all KILLED" in res["reasons"]
    assert set(res["inputs_sha256"]) == {"records", "meta", "cert", "sketch"}
    sketch.write_text(json.dumps({"selection": {"selected_R": True}}), encoding="utf-8")
    pg.main(
        [
            *("--records", str(rec)),
            *("--meta", str(met)),
            *("--cert", str(cert)),
            *("--sketch", str(sketch)),
            *("--out", str(out)),
        ]
    )
    res2 = json.loads(out.read_text(encoding="utf-8"))
    assert "the sketch selected no R (door-close before the pilot)" in res2["reasons"]


def test_injection_skips_bot() -> None:
    """⊥ のセルには注入しない (λ は ⊥ でないセルの割合で較正している)."""

    def some_bot(lever: str, enc: str, u: bat.Unit) -> str | None:
        return None if u.room == 0 else blind_masked(lever, enc, u)

    x, nb, _ = pg.cell_scores(make_pilot(some_bot), "masked")
    assert float(nb.mean()) == pytest.approx(5 / 6)
    oc = pg.spike_in_oc(x, nb, 24, sc.DELTA_PLANT, 200, 1)
    assert oc["realized_C"] == pytest.approx(sc.DELTA_PLANT, abs=0.02)
