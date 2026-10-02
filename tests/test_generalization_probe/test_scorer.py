"""parse・推定量・τ 判定 (betting e-value)・判定 rule・記録の検査 (prereg §3〜§5)."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pytest
from scripts import generalization_probe_battery as bat
from scripts import generalization_probe_scorer as sc

if TYPE_CHECKING:
    from collections.abc import Callable

R = 6
TAU = sc.TAU
_ROOT = Path(__file__).resolve().parents[2]
OBSERVED = {
    "model_digest": "d" * 64,
    "ollama_version": "0.32.12",
    "template_sha256": "t" * 64,
}


def meta(**observed: str) -> dict[str, object]:
    return {"request": sc.request_meta(), "observed": {**OBSERVED, **observed}}


# ------------------------------------------------------------ 合成の記録


def make_samples(
    choose: Callable[[str, int, bat.Probe], str | None], r_count: int = R
) -> list[sc.Sample]:
    """choose(arm, r, probe) → label (None は ⊥ になる生テキスト).

    call_index は通し番号。
    """
    out = []
    idx = 0
    for arm in bat.LEVER_ARMS:
        for r in range(r_count):
            for p in bat.probes():
                seed, sha = sc.expected_sample(arm, r, p, 0)
                label = choose(arm, r, p)
                raw = label if label is not None else "わからない"
                out.append(
                    sc.Sample(
                        idx, arm, r, p.probe_id, 0, seed, sha, raw, sc.parse_choice(raw)
                    )
                )
                idx += 1
    return out


def lookup(arm: str, r: int, p: bat.Probe) -> str | None:
    """自分の規則の向き (完全な汎化)."""
    del r
    return p.pointed[arm]


def blind(arm: str, r: int, p: bat.Probe) -> str | None:
    """状態も key も読まない: 表示の先頭 (族内・つ組で一致して相殺する)."""
    return bat.option_order(bat.ARM_FAMILY[arm], p.triple, r)[0]


def other(arm: str, p: bat.Probe) -> str:
    """Ω の残り 1 つ (w でも foil でもない族の label)."""
    rest = set(bat.family_actions(bat.ARM_FAMILY[arm])) - {
        p.pointed[arm],
        p.pointed[bat.FOIL[arm]],
    }
    return rest.pop()


def evaluate(samples: list[sc.Sample], **kw: object) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "certified": True,
        "r_count": R,
        "pilot_max_bottom": 0.15,
        "reference_observed": OBSERVED,
    }
    kwargs.update(kw)
    the_meta = kwargs.pop("meta", meta())
    return sc.evaluate(samples, the_meta, **kwargs)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def _fast_fixture_gate(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """fixture gate を空に置き換えて速くする.

    全計算は test_fixtures と下の専用 test で見る。
    """
    if request.node.name != "test_evaluate_fixture_gate":
        monkeypatch.setattr(sc.fx, "fixture_violations", lambda _r: [])


# ---------------------------------------------------------------- parse


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("sort_cards", "sort_cards"),
        (" 「Sort Cards」。", "sort_cards"),
        ("sort-cards", "sort_cards"),
        ("ｓｏｒｔ＿ｃａｒｄｓ", "sort_cards"),
        ("答え: wind_clock です", "wind_clock"),
        ("", None),
        ("。", None),
        ("read_book", None),
        ("unsorted_cards_x", None),
    ],
)
def test_parse_basic(raw: str, expected: str | None) -> None:
    assert sc.parse_choice(raw) == expected


def test_parse_two_labels_is_bot() -> None:
    assert sc.parse_choice("sort_cards か fold_linen") is None


def test_parse_think_block() -> None:
    assert sc.parse_choice("<think>fold_linen?</think>sort_cards") == "sort_cards"
    assert sc.parse_choice("<THINK>fold_linen</THINK> sort_cards") == "sort_cards"


def test_parse_unclosed_think() -> None:
    assert sc.parse_choice("<think>sort_cards") is None


# ------------------------------------------------------------- 推定量


def test_category() -> None:
    p = bat.probes()[0]
    assert sc.category(p.pointed[bat.ARM_A], p, bat.ARM_A) == "w"
    assert sc.category(p.pointed[bat.ARM_A_ROT], p, bat.ARM_A) == "foil"
    assert sc.category(other(bat.ARM_A, p), p, bat.ARM_A) == "other"
    assert sc.category(p.pointed[bat.ARM_B], p, bat.ARM_A) == "oov"
    assert sc.category(None, p, bat.ARM_A) == "bot"


def _choices(samples: list[sc.Sample]) -> dict[tuple[str, int, str], list[str | None]]:
    out: dict[tuple[str, int, str], list[str | None]] = {}
    for s in samples:
        out.setdefault((s.arm, s.replicate, s.probe_id), []).append(s.parsed)
    return out


def test_bot_in_denominator() -> None:
    def half_bot(arm: str, r: int, p: bat.Probe) -> str | None:
        del r
        return None if p.situation.latent == "bird" else p.pointed[arm]

    s = sc.arm_unit_scores(_choices(make_samples(half_bot)), R)
    assert all(v == pytest.approx(2 / 3) for v in s.values())


def test_unit_scores_family_average() -> None:
    def a_and_b(arm: str, r: int, p: bat.Probe) -> str | None:
        """A・B は自分の w、A_rot・B_rot は相手の w (= 自分の foil)."""
        del r
        if arm in (bat.ARM_A, bat.ARM_B):
            return p.pointed[arm]
        return p.pointed[bat.FOIL[arm]]

    s = sc.arm_unit_scores(_choices(make_samples(a_and_b)), R)
    d = sc.unit_scores(s, R)
    assert d.shape == (2 * bat.N_TRIPLES * R,)
    assert np.all(d == 0.0)
    assert sc.components(s).tolist() == [1.0, -1.0, 1.0, -1.0]


def test_components_order() -> None:
    def a_only(arm: str, r: int, p: bat.Probe) -> str | None:
        """A は w、A_rot は Ω の残り (other)、B は foil、B_rot は w."""
        del r
        if arm == bat.ARM_A:
            return p.pointed[arm]
        if arm == bat.ARM_A_ROT:
            return other(arm, p)
        if arm == bat.ARM_B:
            return p.pointed[bat.ARM_B_ROT]
        return p.pointed[bat.ARM_B_ROT]

    comps = sc.components(sc.arm_unit_scores(_choices(make_samples(a_only)), R))
    assert comps.tolist() == [1.0, 0.0, -1.0, 1.0]


# ------------------------------------------------------------- τ 判定


def _log_e_reference(x: np.ndarray, cap: float) -> float:
    vals = [math.prod(1.0 + (j / 4) * cap * v for v in x) for j in (1, 2, 3, 4)]
    return math.log(sum(vals) / 4)


def test_e_value_exact() -> None:
    d = np.array([0.6] * 10 + [0.1, -0.2, 1.0])
    lp, lm, lz = sc.e_values(d)
    assert float(lp) == pytest.approx(_log_e_reference(d - TAU, 1 / (1 + TAU)))
    assert float(lm) == pytest.approx(_log_e_reference(TAU - d, 1 / (1 - TAU)))
    assert float(lz) == pytest.approx(_log_e_reference(d, 1.0))


def test_e_value_zero_factor() -> None:
    d = np.array([-1.0] + [1.0] * 40)
    lp, _, _ = sc.e_values(d)
    # λ = 1/(1+τ) の成分は d = −1 で 0 になるが、他の λ の成分が残る
    assert np.isfinite(lp)
    assert float(lp) == pytest.approx(_log_e_reference(d - TAU, 1 / (1 + TAU)))


def test_e_value_respects_necessary_bound() -> None:
    """雑音ゼロでも m < (1+τ)α^(−1/n) − 1 なら棄却しない (n = 16 で 0.568)."""
    lp, _, _ = sc.e_values(np.full(16, 0.55))
    assert float(lp) < sc.LOG_THRESHOLD
    lp32, _, _ = sc.e_values(np.full(32, 0.6))
    assert float(lp32) >= sc.LOG_THRESHOLD


def test_decide_threshold() -> None:
    comps = np.ones(4)
    assert sc.decide(np.log(20.0), 0.0, comps) == sc.VERDICT_PASS
    assert sc.decide(np.log(19.9), 0.0, comps) == sc.VERDICT_UNDERPOWERED
    assert sc.decide(0.0, np.log(20.0), comps) == sc.VERDICT_ABSENT
    assert sc.decide(0.0, np.log(19.9), comps) == sc.VERDICT_UNDERPOWERED


def test_decide_requires_positive_components() -> None:
    assert (
        sc.decide(np.log(1e6), 0.0, np.array([1.0, 1.0, 1.0, 0.0]))
        == sc.VERDICT_UNDERPOWERED
    )


def test_branches_never_both() -> None:
    rng = np.random.default_rng(0)
    for _ in range(200):
        d = rng.choice([-1.0, -0.5, 0.0, 0.5, 1.0], size=rng.integers(4, 64))
        lp, lm, _ = sc.e_values(d)
        assert not (lp >= sc.LOG_THRESHOLD and lm >= sc.LOG_THRESHOLD)


def test_no_go_reachable() -> None:
    _, lm, _ = sc.e_values(np.zeros(32))
    assert float(lm) >= sc.LOG_THRESHOLD
    _, lm_tau, _ = sc.e_values(np.full(32, TAU))
    assert float(lm_tau) == pytest.approx(0.0)


def test_bottom_gate() -> None:
    assert bool(sc.bottom_gate_ok(np.array([0.1, 0.1, 0.0, 0.0])))
    assert not bool(sc.bottom_gate_ok(np.array([0.25, 0.25, 0.0, 0.0])))
    assert not bool(sc.bottom_gate_ok(np.array([0.1, 0.1, 0.0, 0.0]), bot_max=0.05))


def test_bottom_gate_family_gap() -> None:
    assert not bool(sc.bottom_gate_ok(np.array([0.1, 0.0, 0.0, 0.0])))
    assert bool(sc.bottom_gate_ok(np.array([0.07, 0.0, 0.0, 0.0])))


def test_envelope_bottom_max() -> None:
    assert sc.envelope_bottom_max(0.0) == pytest.approx(0.05)
    assert sc.envelope_bottom_max(0.1) == pytest.approx(0.15)
    assert sc.envelope_bottom_max(0.19) == pytest.approx(0.2)


# ------------------------------------------------------------- 判定の枝


def test_evaluate_lookup_pass() -> None:
    res = evaluate(make_samples(lookup))
    assert res["verdict"] == sc.VERDICT_PASS
    assert res["C"] == pytest.approx(1.0)
    assert res["n_units"] == 96


def test_evaluate_blind_no_go() -> None:
    res = evaluate(make_samples(blind))
    assert res["verdict"] == sc.VERDICT_ABSENT
    assert res["C"] == pytest.approx(0.0)


def test_evaluate_partial_inconclusive() -> None:
    def partial(arm: str, r: int, p: bat.Probe) -> str | None:
        del r
        return p.pointed[arm] if p.situation.latent == "bird" else other(arm, p)

    res = evaluate(make_samples(partial))
    assert res["C"] == pytest.approx(1 / 3)
    assert res["verdict"] == sc.VERDICT_UNDERPOWERED


def test_evaluate_one_arm_not_reading() -> None:
    def one_arm(arm: str, r: int, p: bat.Probe) -> str | None:
        if arm == bat.ARM_B_ROT:
            return p.pointed[bat.FOIL[arm]]
        return lookup(arm, r, p)

    res = evaluate(make_samples(one_arm))
    assert res["components"]["B_rot"] == pytest.approx(-1.0)
    assert res["verdict"] == sc.VERDICT_UNDERPOWERED


def test_evaluate_lever_bottom() -> None:
    def bot_a(arm: str, r: int, p: bat.Probe) -> str | None:
        return None if arm == bat.ARM_A and p.index % 2 == 0 else lookup(arm, r, p)

    assert evaluate(make_samples(bot_a))["verdict"] == sc.VERDICT_INVALID_BATTERY


def test_evaluate_envelope() -> None:
    """全 arm の ⊥ 率 1/12 (族内差なし) の envelope.

    pilot の最大 0 なら上限 0.05 で INVALID_TASK_BATTERY、0.1 なら通る。
    """

    def bot_all(arm: str, r: int, p: bat.Probe) -> str | None:
        return None if p.index % 12 == 0 else lookup(arm, r, p)

    samples = make_samples(bot_all)
    res = evaluate(samples, pilot_max_bottom=0.0)
    assert res["verdict"] == sc.VERDICT_INVALID_BATTERY
    assert res["bottom_max"] == pytest.approx(0.05)
    assert evaluate(samples, pilot_max_bottom=0.1)["verdict"] == sc.VERDICT_PASS


def test_evaluate_requires_certification() -> None:
    res = evaluate(make_samples(lookup), certified=False)
    assert res["verdict"] == sc.VERDICT_INVALID_SCORER


def test_evaluate_meta() -> None:
    bad = meta()
    bad["request"] = {**sc.request_meta(), "model": "other"}
    assert (
        evaluate(make_samples(lookup), meta=bad)["verdict"] == sc.VERDICT_INVALID_SCORER
    )


def test_meta_observed() -> None:
    """観測環境 (モデルの同定) が欠ける / pilot と違うなら INVALID_SCORER.

    Codex MEDIUM-11。
    """
    assert sc.meta_violations(meta(), OBSERVED) == []
    assert sc.meta_violations({"request": sc.request_meta()}) != []
    missing = {"request": sc.request_meta(), "observed": {"model_digest": "x"}}
    assert sc.meta_violations(missing) == [
        "meta: observed environment is missing or malformed"
    ]
    assert sc.meta_violations(meta(model_digest="e" * 64), OBSERVED) == [
        "meta: observed environment differs from the pilot"
    ]
    res = evaluate(make_samples(lookup), meta=meta(ollama_version="0.33.0"))
    assert res["verdict"] == sc.VERDICT_INVALID_SCORER


def test_evaluate_fixture_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sc.fx, "fixture_violations", lambda _r: ["planted"])
    res = evaluate(make_samples(lookup))
    assert res["verdict"] == sc.VERDICT_INVALID_SCORER
    assert "fixture gate failed" in res["reasons"]


def test_evaluate_battery_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sc.bat, "battery_violations", lambda _r: ["planted"])
    res = evaluate(make_samples(lookup))
    assert res["verdict"] == sc.VERDICT_INVALID_SCORER
    assert "battery check failed" in res["reasons"]


def test_evaluate_transport_failure() -> None:
    samples = make_samples(lookup)
    s0 = samples[100]
    samples[100] = sc.Sample(**{**vars(s0), "raw": None, "parsed": None})
    res = evaluate(samples)
    assert res["status"] == sc.STATUS_NOT_COMPUTED
    assert res["verdict"] is None


def test_evaluate_missing_rows() -> None:
    res = evaluate(make_samples(lookup)[:-1])
    assert res["status"] == sc.STATUS_NOT_COMPUTED


# ------------------------------------------------------------- 記録の検査


def _edit(samples: list[sc.Sample], i: int, **kw: object) -> list[sc.Sample]:
    out = list(samples)
    out[i] = sc.Sample(**{**vars(samples[i]), **kw})
    return out


def test_structure_clean() -> None:
    assert sc.structure_violations(make_samples(lookup), R, 1) == []


def test_structure_seed() -> None:
    out = sc.structure_violations(_edit(make_samples(lookup), 200, seed=1), R, 1)
    assert out == ["seed differs from the frozen schedule"]


def test_structure_prompt() -> None:
    out = sc.structure_violations(
        _edit(make_samples(lookup), 200, prompt_sha256="0" * 64), R, 1
    )
    assert out == ["prompt differs from the frozen renderer"]


def test_structure_parse() -> None:
    out = sc.structure_violations(
        _edit(make_samples(lookup), 200, parsed="tidy_shelf"), R, 1
    )
    assert "recorded parse differs from re-parse" in out


def test_structure_duplicate() -> None:
    samples = make_samples(lookup)
    dup = sc.Sample(**{**vars(samples[150]), "call_index": 10_000})
    assert "duplicate (arm, replicate, probe, k)" in sc.structure_violations(
        [*samples, dup], R, 1
    )


def test_structure_grid() -> None:
    out = sc.structure_violations(_edit(make_samples(lookup), 200, replicate=R), R, 1)
    assert "record outside the frozen grid" in out


def test_structure_call_index() -> None:
    out = sc.structure_violations(_edit(make_samples(lookup), 200, call_index=0), R, 1)
    assert "call_index is not unique and non-negative" in out


def test_seed_shared_within_family() -> None:
    p = bat.probes()[3]
    a = sc.expected_sample(bat.ARM_A, 1, p, 0)[0]
    assert a == sc.expected_sample(bat.ARM_A_ROT, 1, p, 0)[0]
    assert a != sc.expected_sample(bat.ARM_B, 1, p, 0)[0]


def test_schema_bool_is_rejected() -> None:
    obj = vars(make_samples(lookup)[0]).copy()
    obj["k"] = False
    with pytest.raises(sc.RecordError):
        sc.sample_from_json(obj)


def test_schema_missing_field_and_bad_json() -> None:
    obj = vars(make_samples(lookup)[0]).copy()
    del obj["raw"]
    with pytest.raises(sc.RecordError):
        sc.sample_from_json(obj)
    with pytest.raises(sc.RecordError):
        sc.load_records(["{not json"])


# ------------------------------------------------------------- certification


def _cert(tmp_path: Path, **kw: object) -> Path:
    cert = {
        "mutants": [
            {"label": "m1", "status": "KILLED"},
            {"label": "m2", "status": "KILLED"},
        ],
        "target_sha256": {
            k: hashlib.sha256(v.read_bytes()).hexdigest()
            for k, v in sc.certified_targets().items()
        },
    }
    cert.update(kw)
    path = tmp_path / "cert.json"
    path.write_text(json.dumps(cert), encoding="utf-8")
    return path


def test_load_certification(tmp_path: Path) -> None:
    assert sc.load_certification(_cert(tmp_path))
    assert not sc.load_certification(tmp_path / "missing.json")
    assert not sc.load_certification(_cert(tmp_path, mutants=[]))


def test_load_certification_requires_all_killed(tmp_path: Path) -> None:
    bad = [{"label": "m1", "status": "KILLED"}, {"label": "m2", "status": "SURVIVED"}]
    assert not sc.load_certification(_cert(tmp_path, mutants=bad))
    dup = [{"label": "m1", "status": "KILLED"}, {"label": "m1", "status": "KILLED"}]
    assert not sc.load_certification(_cert(tmp_path, mutants=dup))


def test_load_certification_detects_stale(tmp_path: Path) -> None:
    stale = dict.fromkeys(sc.certified_targets(), "0" * 64)
    assert not sc.load_certification(_cert(tmp_path, target_sha256=stale))


# ------------------------------------------------------------- CLI (Codex HIGH-5)


def test_cli_runs_as_a_script() -> None:
    proc = subprocess.run(  # noqa: S603
        [
            sys.executable,
            str(_ROOT / "scripts/generalization_probe_scorer.py"),
            "--help",
        ],
        capture_output=True,
        check=False,
        cwd=str(_ROOT),
    )
    assert proc.returncode == 0


def test_cli_end_to_end(tmp_path: Path) -> None:
    samples = make_samples(lookup)
    rec = tmp_path / "records.jsonl"
    rec.write_text(
        "\n".join(json.dumps(vars(s)) for s in samples) + "\n", encoding="utf-8"
    )
    met = tmp_path / "meta.json"
    met.write_text(json.dumps(meta()), encoding="utf-8")
    gate = tmp_path / "gate.json"
    out = tmp_path / "results.json"
    args = [
        *("--records", str(rec)),
        *("--meta", str(met)),
        *("--cert", str(_cert(tmp_path))),
        *("--gate", str(gate)),
        *("--out", str(out)),
    ]
    # decision だけが STOP で、他の欄は GO と同じ形
    # (decision の確認を外す変異を捕まえる)
    no_go = {"decision": "STOP", "R": R, "masked_max_bottom": 0.0, "observed": OBSERVED}
    gate.write_text(json.dumps(no_go), encoding="utf-8")
    sc.main(args)
    assert (
        json.loads(out.read_text(encoding="utf-8"))["status"] == sc.STATUS_NOT_COMPUTED
    )
    go = {"decision": "GO", "R": R, "masked_max_bottom": 0.0, "observed": OBSERVED}
    gate.write_text(json.dumps(go), encoding="utf-8")
    sc.main(args)
    res = json.loads(out.read_text(encoding="utf-8"))
    assert res["verdict"] == sc.VERDICT_PASS


def test_frozen_constants() -> None:
    assert sc.TAU == 0.30
    assert sc.ALPHA == 0.05
    assert sc.FROZEN_K == 1
    assert sc.LAMBDA_FRACTIONS == (0.25, 0.5, 0.75, 1.0)
    assert pytest.approx(1 / 1.3) == sc.CAP_PLUS
    assert pytest.approx(1 / 0.7) == sc.CAP_MINUS
    assert pytest.approx(math.log(20.0)) == sc.LOG_THRESHOLD
    assert sc.BOT_MAX == 0.2
    assert sc.ENVELOPE_MARGIN == 0.05


def test_seed_shared_within_triple() -> None:
    """つ組の 3 probe は seed を共有し、seed は分類を運ばない (Codex 2 回目 HIGH-1)."""
    for j in range(bat.N_TRIPLES):
        seeds = {
            sc.expected_sample(bat.ARM_A, 2, p, 0)[0] for p in bat.triple_probes(j)
        }
        assert len(seeds) == 1
    all_seeds = {
        sc.expected_sample(bat.ARM_A, 2, bat.triple_probes(j)[0], 0)[0]
        for j in range(bat.N_TRIPLES)
    }
    assert len(all_seeds) == bat.N_TRIPLES


def test_seed_reading_key_blind_policy_is_zero() -> None:
    """Codex 2 回目の反例方策は、どの単位でも d = 0.

    seed から分類番号を読み、その分類の dev 行を写す方策。
    """

    def seed_reader(arm: str, r: int, p: bat.Probe) -> str | None:
        seed = sc.expected_sample(arm, r, p, 0)[0]
        c = ((seed - 20261001) % 10000 // 100) % 3
        key = ("sparrow", "trout", "beetle")[c]
        table = bat.state_table(arm)
        return next(act for sit, (act, _) in table.items() if sit.key == key)

    s = sc.arm_unit_scores(_choices(make_samples(seed_reader)), R)
    assert np.all(sc.unit_scores(s, R) == 0.0)
