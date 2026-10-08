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
from scripts import o_time_probe_battery as bat
from scripts import o_time_probe_fixtures as fx
from scripts import o_time_probe_scorer as sc

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

Choose = "Callable[[str, str, bat.Unit], str | None]"


def meta(**observed: str) -> dict[str, object]:
    return {"request": sc.request_meta(), "observed": {**OBSERVED, **observed}}


# ------------------------------------------------------------ 合成の記録


def make_samples(
    choose: Callable[[str, str, bat.Unit], str | None], r_count: int = R
) -> list[sc.Sample]:
    """choose(arm, enc, unit) → label (None は ⊥ になる生テキスト).

    call_index は通し番号。
    """
    out = []
    idx = 0
    for u in bat.units(r_count):
        for arm, enc in bat.unit_calls(u):
            seed, sha = sc.expected_sample(arm, enc, u, 0)
            label = choose(arm, enc, u)
            raw = label if label is not None else "わからない"
            out.append(
                sc.Sample(
                    idx,
                    arm,
                    enc,
                    u.replicate,
                    sc.probe_id(u.room),
                    0,
                    seed,
                    sha,
                    raw,
                    sc.parse_choice(raw),
                )
            )
            idx += 1
    return out


def newer(arm: str, enc: str, u: bat.Unit) -> str | None:
    """新しい日の規則に従う (完全な時期の評価)."""
    del enc
    return bat.pointed(arm, u.room)[0]


def older(arm: str, enc: str, u: bat.Unit) -> str | None:
    del enc
    return bat.pointed(arm, u.room)[1]


def blind(arm: str, enc: str, u: bat.Unit) -> str | None:
    """札を読まない: 条件の合う最初の行 (2 arm で一致して相殺する)."""
    return fx.match_first(fx.context(arm, enc, u))


def third(arm: str, enc: str, u: bat.Unit) -> str | None:
    del enc
    return bat.third_label(bat.ARM_FAMILY[arm], u.room)


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
    if request.node.name != "test_evaluate_fixture_gate_real":
        monkeypatch.setattr(sc.fx, "fixture_violations", lambda _r: [])


# ---------------------------------------------------------------- parse


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ring_bell", "ring_bell"),
        (" 「Ring Bell」。", "ring_bell"),
        ("open-gate", "open_gate"),
        ("ｆｉｌｌ＿ｊａｒ", "fill_jar"),
        ("答え: seal_crate です", "seal_crate"),
        ("", None),
        ("。", None),
        ("sort_cards", None),
        ("spring_bells", None),
    ],
)
def test_parse_basic(raw: str, expected: str | None) -> None:
    assert sc.parse_choice(raw) == expected


def test_parse_two_labels_is_bot() -> None:
    assert sc.parse_choice("ring_bell か open_gate") is None


def test_parse_think_block() -> None:
    assert sc.parse_choice("<think>open_gate?</think>ring_bell") == "ring_bell"
    assert sc.parse_choice("<THINK>open_gate</THINK> ring_bell") == "ring_bell"


def test_parse_unclosed_think() -> None:
    assert sc.parse_choice("<think>ring_bell") is None


# ------------------------------------------------------------- 推定量


def test_category() -> None:
    assert sc.category("open_gate", bat.ARM_AB, 0) == "w"
    assert sc.category("ring_bell", bat.ARM_AB, 0) == "foil"
    assert sc.category("fill_jar", bat.ARM_AB, 0) == "other"
    assert sc.category("trim_wick", bat.ARM_AB, 0) == "oov"
    assert sc.category(None, bat.ARM_AB, 0) == "bot"
    assert sc.category("ring_bell", bat.ARM_BA, 0) == "w"


def _choices(
    samples: list[sc.Sample],
) -> dict[tuple[str, str, int, int], list[str | None]]:
    out: dict[tuple[str, str, int, int], list[str | None]] = {}
    for s in samples:
        out.setdefault(
            (s.arm, s.encoding, sc.room_index(s.probe_id), s.replicate), []
        ).append(s.parsed)
    return out


def test_bot_in_denominator() -> None:
    def half_bot(arm: str, enc: str, u: bat.Unit) -> str | None:
        return None if u.room < 3 else newer(arm, enc, u)

    s = sc.cell_scores(_choices(make_samples(half_bot)), R)
    d = sc.unit_scores(s, R)
    assert float(d.mean()) == pytest.approx(0.5)


def test_unit_scores_average_of_four() -> None:
    def fwd_only(arm: str, enc: str, u: bat.Unit) -> str | None:
        """fwd は新しい日、bwd は古い日 (= fwd の新しい日の行動と同じ label) を選ぶ."""
        return newer(arm, enc, u) if arm in bat.FWD else older(arm, enc, u)

    s = sc.cell_scores(_choices(make_samples(fwd_only)), R)
    d = sc.unit_scores(s, R)
    assert d.shape == (12 * R,)
    assert np.all(d == 0.0)
    assert sc.components(s).tolist() == [1.0, 1.0, -1.0, -1.0]


def test_components_order() -> None:
    def asc_fwd(arm: str, enc: str, u: bat.Unit) -> str | None:
        """(fwd, asc) は新しい日、(fwd, ago) は古い日、bwd は記録に無い行動."""
        if arm not in bat.FWD:
            return third(arm, enc, u)
        return newer(arm, enc, u) if enc == "asc" else older(arm, enc, u)

    comps = sc.components(sc.cell_scores(_choices(make_samples(asc_fwd)), R))
    assert comps.tolist() == [1.0, -1.0, 0.0, 0.0]
    assert sc.COMPONENTS == (
        ("fwd", "asc"),
        ("fwd", "ago"),
        ("bwd", "asc"),
        ("bwd", "ago"),
    )


def test_bottom_rates_per_arm() -> None:
    def bot_ab(arm: str, enc: str, u: bat.Unit) -> str | None:
        return None if arm == bat.ARM_AB and enc == "asc" else newer(arm, enc, u)

    rates = sc.bottom_rates(_choices(make_samples(bot_ab)), R)
    assert rates.tolist() == [0.5, 0.0, 0.0, 0.0]


def test_describe() -> None:
    samples = make_samples(
        lambda a, e, u: third(a, e, u) if u.room == 0 else newer(a, e, u)
    )
    ch = _choices(samples)
    desc = sc.describe(ch, sc.cell_scores(ch, R), R)
    assert desc["other_rate"] == pytest.approx(1 / 6)
    assert desc["C_asc"] == pytest.approx(5 / 6)
    assert desc["C_ago"] == pytest.approx(5 / 6)


# ------------------------------------------------------------- τ 判定


def _log_e_reference(x: np.ndarray, cap: float) -> float:
    vals = [math.prod(1.0 + (j / 4) * cap * v for v in x) for j in (1, 2, 3, 4)]
    return math.log(sum(vals) / 4)


def test_e_value_exact() -> None:
    d = np.array([0.6] * 10 + [0.1, -0.25, 1.0])
    lp, lm, lz = sc.e_values(d)
    assert float(lp) == pytest.approx(_log_e_reference(d - TAU, 1 / (1 + TAU)))
    assert float(lm) == pytest.approx(_log_e_reference(TAU - d, 1 / (1 - TAU)))
    assert float(lz) == pytest.approx(_log_e_reference(d, 1.0))


def test_e_value_zero_factor() -> None:
    d = np.array([-1.0] + [1.0] * 40)
    lp, _, _ = sc.e_values(d)
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
    for k in range(4):
        comps = np.ones(4)
        comps[k] = 0.0
        assert sc.decide(np.log(1e6), 0.0, comps) == sc.VERDICT_UNDERPOWERED


def test_branches_never_both() -> None:
    rng = np.random.default_rng(0)
    for _ in range(200):
        d = rng.choice([-1.0, -0.5, 0.0, 0.25, 0.5, 1.0], size=rng.integers(4, 64))
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
    assert not bool(sc.bottom_gate_ok(np.array([0.0, 0.0, 0.0, 0.1])))


def test_envelope_bottom_max() -> None:
    assert sc.envelope_bottom_max(0.0) == pytest.approx(0.05)
    assert sc.envelope_bottom_max(0.1) == pytest.approx(0.15)
    assert sc.envelope_bottom_max(0.19) == pytest.approx(0.2)


# ------------------------------------------------------------- 判定の枝


def test_evaluate_newer_pass() -> None:
    res = evaluate(make_samples(newer))
    assert res["verdict"] == sc.VERDICT_PASS
    assert res["C"] == pytest.approx(1.0)
    assert res["n_units"] == 72
    assert res["describe"] == {"other_rate": 0.0, "C_asc": 1.0, "C_ago": 1.0}


def test_evaluate_blind_no_go() -> None:
    res = evaluate(make_samples(blind))
    assert res["verdict"] == sc.VERDICT_ABSENT
    assert res["C"] == pytest.approx(0.0)


def test_evaluate_literal_no_go() -> None:
    """数字だけを読む方策 (大きい数) は書き方の対で打ち消し、NO_GO."""

    def digit_max(arm: str, enc: str, u: bat.Unit) -> str | None:
        return fx.digit_rank("max")(fx.context(arm, enc, u))

    res = evaluate(make_samples(digit_max))
    assert res["verdict"] == sc.VERDICT_ABSENT
    assert res["C"] == pytest.approx(0.0)
    assert res["describe"]["C_asc"] == pytest.approx(1.0)


def test_evaluate_older_no_go() -> None:
    res = evaluate(make_samples(older))
    assert res["verdict"] == sc.VERDICT_ABSENT
    assert res["C"] == pytest.approx(-1.0)


def test_evaluate_asc_only_not_pass() -> None:
    """asc だけで新しい日に従う (C = 0.5) は、ago の成分が 0 で PASS しない."""

    def asc_only(arm: str, enc: str, u: bat.Unit) -> str | None:
        return newer(arm, enc, u) if enc == "asc" else third(arm, enc, u)

    res = evaluate(make_samples(asc_only, 12), r_count=12)
    assert res["C"] == pytest.approx(0.5)
    assert float(res["log_e_plus"]) >= sc.LOG_THRESHOLD
    assert res["components"] == {
        "fwd_asc": 1.0,
        "fwd_ago": 0.0,
        "bwd_asc": 1.0,
        "bwd_ago": 0.0,
    }
    assert res["verdict"] == sc.VERDICT_UNDERPOWERED


def test_evaluate_partial_inconclusive() -> None:
    def partial(arm: str, enc: str, u: bat.Unit) -> str | None:
        return newer(arm, enc, u) if u.room < 2 else third(arm, enc, u)

    res = evaluate(make_samples(partial))
    assert res["C"] == pytest.approx(1 / 3)
    assert res["verdict"] == sc.VERDICT_UNDERPOWERED


def test_evaluate_one_direction_not_reading() -> None:
    def one_dir(arm: str, enc: str, u: bat.Unit) -> str | None:
        if arm == bat.ARM_DC:
            return older(arm, enc, u)
        return newer(arm, enc, u)

    res = evaluate(make_samples(one_dir))
    assert res["components"]["bwd_asc"] == pytest.approx(0.0)
    assert res["verdict"] == sc.VERDICT_UNDERPOWERED


def test_evaluate_lever_bottom() -> None:
    def bot_ab(arm: str, enc: str, u: bat.Unit) -> str | None:
        return None if arm == bat.ARM_AB and u.room % 2 == 0 else newer(arm, enc, u)

    assert evaluate(make_samples(bot_ab))["verdict"] == sc.VERDICT_INVALID_BATTERY


def test_evaluate_envelope() -> None:
    """全 arm の ⊥ 率 1/12 (族内差なし).

    pilot の最大 0 なら上限 0.05 で INVALID、0.1 なら通る。
    """

    def bot_all(arm: str, enc: str, u: bat.Unit) -> str | None:
        return None if u.room == 0 and enc == "asc" else newer(arm, enc, u)

    samples = make_samples(bot_all)
    res = evaluate(samples, pilot_max_bottom=0.0)
    assert res["verdict"] == sc.VERDICT_INVALID_BATTERY
    assert res["bottom_max"] == pytest.approx(0.05)
    assert evaluate(samples, pilot_max_bottom=0.1)["verdict"] == sc.VERDICT_PASS


def test_evaluate_requires_certification() -> None:
    res = evaluate(make_samples(newer), certified=False)
    assert res["verdict"] == sc.VERDICT_INVALID_SCORER


def test_evaluate_meta() -> None:
    bad = meta()
    bad["request"] = {**sc.request_meta(), "model": "other"}
    assert (
        evaluate(make_samples(newer), meta=bad)["verdict"] == sc.VERDICT_INVALID_SCORER
    )


def test_meta_observed() -> None:
    assert sc.meta_violations(meta(), OBSERVED) == []
    assert sc.meta_violations({"request": sc.request_meta()}) != []
    missing = {"request": sc.request_meta(), "observed": {"model_digest": "x"}}
    assert sc.meta_violations(missing) == [
        "meta: observed environment is missing or malformed"
    ]
    assert sc.meta_violations(meta(model_digest="e" * 64), OBSERVED) == [
        "meta: observed environment differs from the pilot"
    ]
    res = evaluate(make_samples(newer), meta=meta(ollama_version="0.33.0"))
    assert res["verdict"] == sc.VERDICT_INVALID_SCORER


def test_evaluate_fixture_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sc.fx, "fixture_violations", lambda _r: ["planted"])
    res = evaluate(make_samples(newer))
    assert res["verdict"] == sc.VERDICT_INVALID_SCORER
    assert "fixture gate failed" in res["reasons"]


def test_evaluate_fixture_gate_real() -> None:
    """fixture gate を差し替えない経路 (凍結した fixture の計算を通る)."""
    res = evaluate(make_samples(newer))
    assert res["verdict"] == sc.VERDICT_PASS


def test_evaluate_battery_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sc.bat, "battery_violations", lambda _r: ["planted"])
    res = evaluate(make_samples(newer))
    assert res["verdict"] == sc.VERDICT_INVALID_SCORER
    assert "battery check failed" in res["reasons"]


def test_evaluate_transport_failure() -> None:
    samples = make_samples(newer)
    s0 = samples[100]
    samples[100] = sc.Sample(**{**vars(s0), "raw": None, "parsed": None})
    res = evaluate(samples)
    assert res["status"] == sc.STATUS_NOT_COMPUTED
    assert res["verdict"] is None


def test_evaluate_missing_rows() -> None:
    res = evaluate(make_samples(newer)[:-1])
    assert res["status"] == sc.STATUS_NOT_COMPUTED


# ------------------------------------------------------------- 記録の検査


def _edit(samples: list[sc.Sample], i: int, **kw: object) -> list[sc.Sample]:
    out = list(samples)
    out[i] = sc.Sample(**{**vars(samples[i]), **kw})
    return out


def test_structure_clean() -> None:
    assert sc.structure_violations(make_samples(newer), R, 1) == []


def test_structure_seed() -> None:
    out = sc.structure_violations(_edit(make_samples(newer), 200, seed=1), R, 1)
    assert out == ["seed differs from the frozen schedule"]


def test_structure_prompt() -> None:
    out = sc.structure_violations(
        _edit(make_samples(newer), 200, prompt_sha256="0" * 64), R, 1
    )
    assert out == ["prompt differs from the frozen renderer"]


def test_structure_encoding_swapped() -> None:
    """書き方を入れ替えた記録は、prompt の照合で落ちる."""
    samples = make_samples(newer)
    enc = "ago" if samples[201].encoding == "asc" else "asc"
    out = sc.structure_violations(
        _edit(samples, 201, encoding=enc, call_index=99_999), R, 1
    )
    assert "prompt differs from the frozen renderer" in out


def test_structure_parse() -> None:
    out = sc.structure_violations(
        _edit(make_samples(newer), 200, parsed="hang_rope"), R, 1
    )
    assert "recorded parse differs from re-parse" in out


def test_structure_duplicate() -> None:
    samples = make_samples(newer)
    dup = sc.Sample(**{**vars(samples[150]), "call_index": 10_000})
    assert "duplicate (arm, encoding, replicate, probe, k)" in sc.structure_violations(
        [*samples, dup], R, 1
    )


def test_structure_grid() -> None:
    out = sc.structure_violations(_edit(make_samples(newer), 200, replicate=R), R, 1)
    assert "record outside the frozen grid" in out


def test_structure_call_index() -> None:
    out = sc.structure_violations(_edit(make_samples(newer), 200, call_index=0), R, 1)
    assert "call_index is not unique and non-negative" in out


def test_seed_shared_within_unit() -> None:
    u = bat.Unit(0, 3, 1)
    seeds = {sc.expected_sample(arm, enc, u, 0)[0] for arm, enc in bat.unit_calls(u)}
    assert len(seeds) == 1
    assert sc.expected_sample(bat.ARM_CD, "asc", bat.Unit(1, 3, 1), 0)[0] not in seeds
    assert sc.expected_sample(bat.ARM_AB, "asc", bat.Unit(0, 4, 1), 0)[0] not in seeds


def test_schema_bool_is_rejected() -> None:
    obj = vars(make_samples(newer)[0]).copy()
    obj["k"] = False
    with pytest.raises(sc.RecordError):
        sc.sample_from_json(obj)


def test_schema_missing_field_and_bad_json() -> None:
    obj = vars(make_samples(newer)[0]).copy()
    del obj["encoding"]
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


def test_certified_targets() -> None:
    assert sorted(sc.certified_targets()) == [
        "scripts/o_time_probe_battery.py",
        "scripts/o_time_probe_fixtures.py",
        "scripts/o_time_probe_pilot_gate.py",
        "scripts/o_time_probe_scorer.py",
        "scripts/o_time_probe_sim.py",
        "scripts/stage_b_scorer.py",
    ]


# ------------------------------------------------------------- CLI


def test_cli_runs_as_a_script() -> None:
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(_ROOT / "scripts/o_time_probe_scorer.py"), "--help"],
        capture_output=True,
        check=False,
        cwd=str(_ROOT),
    )
    assert proc.returncode == 0


def test_cli_end_to_end(tmp_path: Path) -> None:
    samples = make_samples(newer)
    rec = tmp_path / "records.jsonl"
    # U+2028 を含む生テキストでも行が割れない (改行だけで割る)
    first = sc.Sample(**{**vars(samples[0]), "raw": samples[0].raw + chr(0x2028)})
    rows = [first, *samples[1:]]
    rec.write_text(
        "\n".join(json.dumps(vars(s), ensure_ascii=False) for s in rows) + "\n",
        encoding="utf-8",
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
    assert b"\r\n" not in out.read_bytes()


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
    assert pytest.approx(0.075) == sc.BOT_FAMILY_GAP


def test_seed_reading_policy_is_zero() -> None:
    """seed を読む方策も札を見ないなら、どの単位でも D = 0.

    4 呼び出しで seed を共有するので。
    """

    def seed_reader(arm: str, enc: str, u: bat.Unit) -> str | None:
        seed = sc.expected_sample(arm, enc, u, 0)[0]
        ctx = fx.context(arm, enc, u)
        rows = [r for r in ctx.rows if r.room == ctx.room]
        return rows[seed % 2].label

    s = sc.cell_scores(_choices(make_samples(seed_reader)), R)
    assert np.all(sc.unit_scores(s, R) == 0.0)


def test_parse_word_boundary() -> None:
    assert sc.parse_choice("bring_bell") is None
    assert sc.parse_choice("ring_bells") is None


def test_evaluate_structure() -> None:
    samples = _edit(make_samples(newer), 200, seed=1)
    res = evaluate(samples)
    assert res["verdict"] == sc.VERDICT_INVALID_SCORER
    assert "seed differs from the frozen schedule" in res["reasons"]
