"""判別性 gate 段 2 — 本走の判別性 scorer の test (合成の本走の記録、GPU なし).

合成記録は driver と同じ形 (``dr.record_line``・``dr.meta_for``・
``dr.json_text``) で直接書く。
gate は契約どおりの合成 (v2 R 8・v3 R 8・O_time R 6 が GO、
G は STOP_POWER、6 モデル入場)。
"""

from __future__ import annotations

import ast
import dataclasses
import json
import pathlib
import shutil
from fractions import Fraction
from typing import TYPE_CHECKING, Any

import numpy as np
import pytest
from scripts import benchmark_stage2_driver as dr
from scripts import benchmark_stage2_fixtures as fxm
from scripts import benchmark_stage2_manifest_main as mm
from scripts import benchmark_stage2_pilot_gate as pg
from scripts import benchmark_stage2_plan as pl
from scripts import benchmark_stage2_records as rd
from scripts import benchmark_stage2_scorer as sc
from scripts import benchmark_stage2_stats as st
from scripts import skill_lever_battery as v2bat

from tests.test_benchmark_stage2_driver.main_tree import build_tree
from tests.test_benchmark_stage2_driver.test_pilot_gate import (
    _ACTIONS,
    _LEVER,
    _cell_key,
    _lever_label,
    _reference,
    _row,
    _sha,
    _template,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

R_MAIN = {"v2": 8, "v3": 8, "O_time": 6}
BOT = "?"
Policy = "Callable[[str, pl.CallSpec], str]"


# ------------------------------------------------------------ 合成の gate と run


def make_gate(
    bots: Mapping[tuple[str, str], tuple[list[int], int]] | None = None,
) -> dict[str, Any]:
    """契約どおりの gate.

    envelope は pilot の ⊥ の数 (既定は全 arm 0/720) から pilot gate と同じ規則で作る。
    """
    batteries: dict[str, Any] = {}
    for b in st.BATTERIES:
        models = {}
        for m in pl.MODELS:
            counts, n = (bots or {}).get((b, m), ([0] * st.N_ARMS[b], 720))
            env = st.parse_rule(counts, n)[1]
            models[m] = {
                "status": st.ENTERED,
                "bot_counts": list(counts),
                "bot_n": n,
                "envelope": {
                    "numerator": env.numerator,
                    "denominator": env.denominator,
                },
            }
        batteries[b] = {
            "models": models,
            "entrants": list(pl.MODELS),
            "n_entered": len(pl.MODELS),
            "gate": st.GATE_GO if b in R_MAIN else st.GATE_STOP_POWER,
            "R": R_MAIN.get(b),
        }
    return {
        "schema": pg.SCHEMA,
        "status": pg.STATUS_OK,
        "violations": [],
        "K": 4 * 6 * 5,
        "sum_M": 24,
        "batteries": batteries,
        "inputs": {"models_json_sha256": _ref_sha()},
    }


def _ref_bytes() -> bytes:
    return json.dumps(_reference(), sort_keys=True).encode("utf-8")


def _ref_sha() -> str:
    return _sha(_ref_bytes())


def write_inputs(tmp: pathlib.Path, gate: Mapping[str, Any]) -> dict[str, pathlib.Path]:
    paths = {
        "gate": tmp / "gate.json",
        "models": tmp / "models.json",
        "fixtures": tmp / "fixture_diffs_main.json",
    }
    paths["gate"].write_text(pg.gate_text(gate), encoding="utf-8")
    paths["models"].write_bytes(_ref_bytes())
    paths["fixtures"].write_bytes(fxm.compute_text(paths["gate"]).encode("utf-8"))
    # 第 2 段の封印 (manifest_main.json) がこの gate・models・fixture で通る root
    paths["root"] = tree_for(tmp / "root", paths)
    return paths


def tree_for(root: pathlib.Path, paths: Mapping[str, pathlib.Path]) -> pathlib.Path:
    return build_tree(
        root,
        gate_bytes=paths["gate"].read_bytes(),
        models_bytes=paths["models"].read_bytes(),
        fixture_bytes=paths["fixtures"].read_bytes(),
    )


def write_main(
    run_dir: pathlib.Path,
    policy: Callable[[str, pl.CallSpec], str],
    *,
    status: Mapping[str, str] | None = None,
) -> None:
    segs = pl.main_plan(R_MAIN, dict.fromkeys(R_MAIN, pl.MODELS))
    root = run_dir / pl.STAGE_MAIN
    root.mkdir(parents=True)
    pdig = pl.plan_digest(segs)
    entries = {}
    for seg in segs:
        sdig = pl.segment_digest(seg)
        state = (status or {}).get(seg.name, dr.S_COMPLETED)
        entry: dict[str, Any] = {
            "status": state,
            "reason": None if state == dr.S_COMPLETED else "synthetic",
            "adopted_attempt": None,
            "records_sha256": None,
            "meta_sha256": None,
            "n_calls": len(seg.calls),
            "segment_digest": sdig,
            "attempts_run": 0 if state == dr.S_NOT_STARTED else 1,
        }
        if state == dr.S_COMPLETED:
            adir = dr.attempt_dir(dr.segment_dir(root, pl.STAGE_MAIN, seg), 1)
            adir.mkdir(parents=True)
            obs = dr.Observed(
                dr.OLLAMA_VERSION, f"digest-{seg.model}", _template(seg.model)
            )
            mb = dr.json_text(dr.meta_for(seg, 1, obs, sdig, pdig)).encode("utf-8")
            (adir / dr.META_NAME).write_bytes(mb)
            lines = [
                dr.record_line(_row(seg, i, c, policy(seg.model, c)))
                for i, c in enumerate(seg.calls)
            ]
            rb = dr.records_bytes(lines)
            (adir / dr.RECORDS_NAME).write_bytes(rb)
            entry.update(
                adopted_attempt=1, records_sha256=_sha(rb), meta_sha256=_sha(mb)
            )
        entries[seg.name] = entry
    table = {
        "run_stage": pl.STAGE_MAIN,
        "plan_digest": pdig,
        "expected_ollama_version": dr.OLLAMA_VERSION,
        "segments": entries,
        "order": [s.name for s in segs],
    }
    (root / dr.SEGMENTS_NAME).write_bytes(dr.json_text(table).encode("utf-8"))


def score(
    tmp: pathlib.Path, run_dir: pathlib.Path, gate: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    paths = write_inputs(tmp, gate or make_gate())
    return json.loads(
        sc.compute_twice(
            run_dir,
            paths["gate"],
            paths["models"],
            paths["fixtures"],
            root=paths["root"],
        )
    )


# ------------------------------------------------------------ 応答の方策

# モデルごとの target を選ぶ lever arm の本数 (残りは foil)。単位の値 = (2N − 4)/4
N_TARGET = {
    "qwen3:1.7b": 4,
    "qwen3:4b-q4_K_M": 3,
    "qwen3:8b": 2,
    "qwen3:14b": 1,
    "llama3.1:8b": 0,
    "gemma2:9b": 2,
}


def _lever(spec: pl.CallSpec, want: str) -> str:
    return _lever_label(spec.battery, _cell_key(spec), want)


def graded(model: str, spec: pl.CallSpec) -> str:
    if spec.purpose != pl.P_LEVER:
        return _ACTIONS[spec.battery][0]
    i = _LEVER[spec.battery].index(spec.arm)
    return _lever(spec, "w" if i < N_TARGET[model] else "foil")


def equal_zero(_model: str, spec: pl.CallSpec) -> str:
    """全モデル同じ: 族ごとに target と foil が 1 本ずつ.

    単位の値 0、成分の符号が混ざる。
    """
    if spec.purpose != pl.P_LEVER:
        return _ACTIONS[spec.battery][0]
    i = _LEVER[spec.battery].index(spec.arm)
    return _lever(spec, "w" if i in (0, 1) else "foil")


def _unit_hash(spec: pl.CallSpec) -> int:
    return (spec.replicate * 7 + int(spec.probe_id[-1], 36) * 3 + spec.k) % 10


def noisy(model: str, spec: pl.CallSpec) -> str:
    """1 モデルだけ 10 単位に 1 つ全 target (平均 0.1)、他は other (0) → (3)."""
    if spec.purpose != pl.P_LEVER:
        return _ACTIONS[spec.battery][0]
    if model == "qwen3:1.7b" and _unit_hash(spec) == 0:
        return _lever(spec, "w")
    return _lever(spec, "other")


def with_bots(
    model: str, n_bot: int, base: Callable[[str, pl.CallSpec], str]
) -> Callable[[str, pl.CallSpec], str]:
    """``model`` の v2 の第 1 lever arm の先頭 n_bot 呼び出しを ⊥ にする."""

    def policy(m: str, spec: pl.CallSpec) -> str:
        if (
            m == model
            and spec.battery == "v2"
            and spec.purpose == pl.P_LEVER
            and spec.arm == v2bat.LEVER_ARMS[0]
        ):
            r0 = rd.MAIN_R0["v2"]
            qi = [p.probe_id for p in v2bat.lever_probes()].index(spec.probe_id)
            if ((spec.replicate - r0) * 6 + qi) * 10 + spec.k < n_bot:
                return BOT
        return base(m, spec)

    return policy


@pytest.fixture(scope="module")
def graded_run(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    d = tmp_path_factory.mktemp("graded")
    write_main(d, graded)
    return d


@pytest.fixture(scope="module")
def graded_verdict(
    graded_run: pathlib.Path, tmp_path_factory: pytest.TempPathFactory
) -> dict[str, Any]:
    return score(tmp_path_factory.mktemp("in"), graded_run)


# ------------------------------------------------------------ end-to-end


def test_graded_run_establishes_and_names_every_pair(
    graded_verdict: dict[str, Any],
) -> None:
    v2 = graded_verdict["batteries"]["v2"]
    assert v2["verdict"] == st.VERDICT_ESTABLISHED
    assert v2["report_set"] == list(pl.MODELS)
    c = {m: v2["models"][m]["C"] for m in pl.MODELS}
    assert c == {m: (2 * N_TARGET[m] - 4) / 4 for m in pl.MODELS}
    want = {(a, b) for a in pl.MODELS for b in pl.MODELS if c[a] - c[b] > st.DELTA_MIN}
    assert {tuple(p["pair"]) for p in v2["named"]} == want
    assert all(p["sensitivity_ok"] for p in v2["named"])
    assert graded_verdict["line_end"] is None
    assert graded_verdict["K"] == 120
    assert graded_verdict["sum_M"] == 24
    assert "replicate_lower_bounds" in v2
    assert len(v2["pairs"]) == 15


def test_graded_run_covers_the_other_go_batteries(
    graded_verdict: dict[str, Any],
) -> None:
    for b in ("v3", "O_time"):
        assert graded_verdict["batteries"][b]["verdict"] == st.VERDICT_ESTABLISHED
    g = graded_verdict["batteries"]["G"]
    assert g["verdict"] is None
    assert g["pilot_gate"] == st.GATE_STOP_POWER
    assert "設計容量" in g["report_text"][0]


def test_v3_named_pairs_carry_the_fixture_pairs(graded_verdict: dict[str, Any]) -> None:
    """§J: v3 の名指しには、Δ_min を超える登録方策の対を常に併記する.

    v2・O_time には無い。
    """
    v3 = graded_verdict["batteries"]["v3"]
    fx_pairs = v3["named"][0]["fixture_pairs"]
    assert any(q["low"] == "nearest_neighbor_ignoring_weather" for q in fx_pairs)
    assert any("でも説明しうる" in line for line in v3["report_text"])
    assert any("得点差までに固定" in line for line in v3["report_text"])
    assert graded_verdict["batteries"]["v2"]["named"][0]["fixture_pairs"] == []


def test_named_pairs_carry_every_fixture_pair_of_the_file(
    graded_verdict: dict[str, Any], tmp_path: pathlib.Path
) -> None:
    """§J: 各名指しの併記 = 同じ gate の fixture ファイルの対の全部.

    名指しどうしの比較でなく file と直接照合する (DD-12 M3)。
    """
    paths = write_inputs(tmp_path, make_gate())
    want = json.loads(paths["fixtures"].read_text(encoding="utf-8"))["batteries"]
    v3_want = want["v3"]["nuisance_pairs_over_delta_min"]
    # 近傍の方策との対の他の対 (直前 − 直後 など) もある:
    # 一部の対だけを残す転記を区別できる
    assert any("nearest" not in q["low"] for q in v3_want)
    for b in R_MAIN:
        named = graded_verdict["batteries"][b]["named"]
        assert named
        for p in named:
            assert p["fixture_pairs"] == want[b]["nuisance_pairs_over_delta_min"]


def _o_time_by_encoding(model: str, spec: pl.CallSpec) -> str:
    """O_time の同じ arm で、asc はすべて target、ago はすべて foil (書き方の非対称)."""
    if spec.battery == "O_time" and spec.purpose == pl.P_LEVER:
        return _lever(spec, "w" if spec.encoding == "asc" else "foil")
    return graded(model, spec)


def test_o_time_six_classes_are_split_by_encoding(tmp_path: pathlib.Path) -> None:
    """§B: O_time の 6 分類は (arm, 書き方) ごと (DD-12 M4).

    arm だけの集計は 2 つを足した 1 行になる。
    """
    run = tmp_path / "run"
    write_main(run, _o_time_by_encoding)
    o = score(tmp_path, run)["batteries"]["O_time"]["models"]["qwen3:8b"]
    by_enc = o["six_classes_by_encoding"]
    arms = list(o["six_classes"])
    assert set(by_enc) == {f"{a}|{e}" for a in arms for e in ("asc", "ago")}
    for a in arms:
        asc, ago = by_enc[f"{a}|asc"], by_enc[f"{a}|ago"]
        n = o["six_classes"][a]["target"] + o["six_classes"][a]["foil"]
        assert asc == {**dict.fromkeys(asc, 0), "target": n // 2}
        assert ago == {**dict.fromkeys(ago, 0), "foil": n // 2}
        assert {k: asc[k] + ago[k] for k in asc} == o["six_classes"][a]


def test_qwen3_prediction_is_reported(graded_verdict: dict[str, Any]) -> None:
    pred = graded_verdict["batteries"]["v2"]["qwen3_prediction"]
    # graded: 1.7b が最も高い → 大きさの順と逆
    assert pred["size_order"] == "不一致"
    by_pair = {tuple(p["pair"]): p["prediction"] for p in pred["named_pairs"]}
    assert by_pair[("qwen3:1.7b", "qwen3:14b")] == "逆転"
    assert all(p[0].startswith("qwen3") and p[1].startswith("qwen3") for p in by_pair)


def test_equal_run_is_calibrated_negative_with_floor_components(
    tmp_path: pathlib.Path,
) -> None:
    run = tmp_path / "run"
    write_main(run, equal_zero)
    out = score(tmp_path, run)
    v2 = out["batteries"]["v2"]
    assert v2["verdict"] == st.VERDICT_NEGATIVE
    assert v2["concentration"] == "floor"
    assert v2["named"] == []
    comp = v2["floor_components"]["qwen3:8b"]
    assert comp["sign"] == "mixed_signs"
    assert set(comp["components"]) == set(v2bat.LEVER_ARMS)
    assert out["line_end"] == sc.LINE_END_TEXT
    assert any("5 ポイント" in line for line in v2["report_text"])


def test_dropped_model_gives_negative_on_subset_and_keeps_k(
    tmp_path: pathlib.Path,
) -> None:
    run = tmp_path / "run"
    name = rd.seg_name(rd.STAGE_MAIN, "v2", "gemma2:9b")
    write_main(run, equal_zero, status={name: dr.S_TIMEOUT})
    out = score(tmp_path, run)
    v2 = out["batteries"]["v2"]
    assert v2["verdict"] == st.VERDICT_NEGATIVE_SUBSET
    assert v2["n_excluded"] == 1
    assert v2["excluded"][0]["model"] == "gemma2:9b"
    assert v2["excluded"][0]["reason"] == sc.EXCL_NOT_COMPUTED
    assert v2["K"] == 120  # 外しても減らさない
    assert out["batteries"]["v3"]["verdict"] == st.VERDICT_NEGATIVE


def test_noisy_run_is_inconclusive(tmp_path: pathlib.Path) -> None:
    run = tmp_path / "run"
    write_main(run, noisy)
    v2 = score(tmp_path, run)["batteries"]["v2"]
    assert v2["verdict"] == st.VERDICT_INCONCLUSIVE
    assert any("決着しない" in line for line in v2["report_text"])


def test_too_few_reported_models_is_not_qualified(tmp_path: pathlib.Path) -> None:
    run = tmp_path / "run"
    drop = {rd.seg_name(rd.STAGE_MAIN, "v2", m): dr.S_TRANSPORT for m in pl.MODELS[:4]}
    write_main(run, graded, status=drop)
    v2 = score(tmp_path, run)["batteries"]["v2"]
    assert v2["verdict"] == st.VERDICT_NOT_QUALIFIED
    assert v2["n_excluded"] == 4


def test_all_models_missing_is_not_computed(tmp_path: pathlib.Path) -> None:
    run = tmp_path / "run"
    drop = {rd.seg_name(rd.STAGE_MAIN, "v2", m): dr.S_NOT_STARTED for m in pl.MODELS}
    write_main(run, graded, status=drop)
    assert score(tmp_path, run)["batteries"]["v2"]["verdict"] == st.VERDICT_NOT_COMPUTED


def test_invalid_meta_excludes_the_model(tmp_path: pathlib.Path) -> None:
    run = tmp_path / "run"
    name = rd.seg_name(rd.STAGE_MAIN, "v2", "qwen3:8b")
    write_main(run, graded, status={name: dr.S_INVALID_META})
    v2 = score(tmp_path, run)["batteries"]["v2"]
    assert v2["verdict"] == st.VERDICT_ESTABLISHED
    assert v2["excluded"] == [
        {
            "model": "qwen3:8b",
            "reason": sc.EXCL_INVALID,
            "detail": "invalid_meta: synthetic",
        }
    ]
    # 名指しの全対と向きを、残りのモデルから独立に作って完全一致
    # (DD-12 M2: 添字の取り違えを区別する)
    rest = [m for m in pl.MODELS if m != "qwen3:8b"]
    assert v2["report_set"] == rest
    c = {m: (2 * N_TARGET[m] - 4) / 4 for m in rest}
    want = {(a, b) for a in rest for b in rest if c[a] - c[b] > st.DELTA_MIN}
    assert want
    named = [tuple(p["pair"]) for p in v2["named"]]
    assert len(named) == len(set(named))
    assert set(named) == want


def test_all_models_invalid_meta_is_invalid(tmp_path: pathlib.Path) -> None:
    run = tmp_path / "run"
    bad = {rd.seg_name(rd.STAGE_MAIN, "v2", m): dr.S_INVALID_META for m in pl.MODELS}
    write_main(run, graded, status=bad)
    assert score(tmp_path, run)["batteries"]["v2"]["verdict"] == st.VERDICT_INVALID


def test_run_wide_invalid_version_is_invalid(tmp_path: pathlib.Path) -> None:
    """§A.1: run の全区切りが invalid_version なら全 battery INVALID.

    not_computed ではない。
    """
    run = tmp_path / "run"
    segs = pl.main_plan(R_MAIN, dict.fromkeys(R_MAIN, pl.MODELS))
    write_main(run, graded, status={s.name: dr.S_INVALID_VERSION for s in segs})
    out = score(tmp_path, run)
    assert out["record_violations"] == []
    for b in R_MAIN:
        v = out["batteries"][b]
        assert v["verdict"] == st.VERDICT_INVALID
        assert {e["reason"] for e in v["excluded"]} == {sc.EXCL_INVALID}
        assert len(v["excluded"]) == len(pl.MODELS)


def test_insensitive_named_pair_is_limited_to_the_score_gap(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§M: 感度の条件を満たさない名指しの対は「得点差まで」と書く (v2・O_time でも)."""
    real = st.decide_battery

    def no_sensitivity(*a: Any, **kw: Any) -> st.BatteryDecision:
        return dataclasses.replace(real(*a, **kw), sensitivity_ok=())

    monkeypatch.setattr(st, "decide_battery", no_sensitivity)
    run = tmp_path / "run"
    write_main(run, graded)
    v2 = score(tmp_path, run)["batteries"]["v2"]
    assert v2["verdict"] == st.VERDICT_ESTABLISHED
    assert v2["named"]
    assert not any(p["sensitivity_ok"] for p in v2["named"])
    limited = [line for line in v2["report_text"] if "得点差まで" in line]
    assert len(limited) == len(v2["named"])


@pytest.mark.parametrize(("n_bot", "excluded"), [(24, False), (25, True)])
def test_envelope_boundary_is_strict(
    tmp_path: pathlib.Path,
    n_bot: int,
    excluded: bool,  # noqa: FBT001
) -> None:
    """Envelope 1/20、arm あたり 480 呼び出し (§F-3).

    24/480 ちょうどは残し、25/480 で外す。
    """
    run = tmp_path / "run"
    write_main(run, with_bots("qwen3:14b", n_bot, graded))
    v2 = score(tmp_path, run)["batteries"]["v2"]
    assert v2["models"]["qwen3:14b"]["bot_counts"][0] == n_bot
    assert v2["models"]["qwen3:14b"]["bot_n"] == 480
    assert ("qwen3:14b" not in v2["report_set"]) is excluded
    if excluded:
        assert v2["excluded"][0]["reason"] == sc.EXCL_ENVELOPE


def test_envelope_comes_from_the_gate(tmp_path: pathlib.Path) -> None:
    """Gate の envelope (整数の分数) を使う.

    pilot の ⊥ 2/720 → envelope 2/720 + 1/20 = 19/360。本走 25/480 (< 19/360) は残る
    (固定の 1/20 なら外れる)。
    """
    run = tmp_path / "run"
    write_main(run, with_bots("qwen3:14b", 25, graded))
    gate = make_gate({("v2", "qwen3:14b"): ([2, 0, 0, 0, 0], 720)})
    env = gate["batteries"]["v2"]["models"]["qwen3:14b"]["envelope"]
    assert Fraction(env["numerator"], env["denominator"]) == Fraction(19, 360)
    v2 = score(tmp_path, run, gate)["batteries"]["v2"]
    assert "qwen3:14b" in v2["report_set"]


def test_record_violation_makes_the_battery_invalid(
    graded_run: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    run = tmp_path / "run"
    shutil.copytree(graded_run, run)
    name = rd.seg_name(rd.STAGE_MAIN, "v3", "qwen3:8b")
    path = (
        run
        / rd.STAGE_MAIN
        / "v3"
        / rd.model_dirname("qwen3:8b")
        / "attempt-1"
        / dr.RECORDS_NAME
    )
    rows = path.read_text(encoding="ascii").split("\n")[:-1]
    data = dr.records_bytes([rows[0], *rows[:-1]])  # 重複 + 欠け
    path.write_bytes(data)
    tpath = run / rd.STAGE_MAIN / dr.SEGMENTS_NAME
    table = json.loads(tpath.read_text(encoding="utf-8"))
    table["segments"][name]["records_sha256"] = _sha(data)
    tpath.write_bytes(dr.json_text(table).encode("utf-8"))
    out = score(tmp_path, run)
    assert out["batteries"]["v3"]["verdict"] == st.VERDICT_INVALID
    assert any("duplicate" in v for v in out["batteries"]["v3"]["violations"])
    assert out["batteries"]["v2"]["verdict"] == st.VERDICT_ESTABLISHED


def test_fixture_mismatch_makes_every_battery_invalid(
    graded_run: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    paths = write_inputs(tmp_path, make_gate())
    paths["fixtures"].write_bytes(paths["fixtures"].read_bytes() + b" ")
    # 封印が記録した fixture でも、再計算と違えば判定は INVALID (封印の照合とは別の検査)
    root = tree_for(tmp_path / "root2", paths)
    out = json.loads(
        sc.compute_twice(
            graded_run, paths["gate"], paths["models"], paths["fixtures"], root=root
        )
    )
    for b in R_MAIN:
        assert out["batteries"][b]["verdict"] == st.VERDICT_INVALID
    # 読めない fixture は判定しない (DF-6 の改め: 封印の照合で拒む)
    paths["fixtures"].unlink()
    with pytest.raises(mm.ManifestError, match="cannot read"):
        sc.compute_twice(
            graded_run, paths["gate"], paths["models"], paths["fixtures"], root=root
        )


# ------------------------------------------------------------ gate の契約


def _bad(gate: dict[str, Any], f: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    g = json.loads(json.dumps(gate))
    f(g)
    return g


GATE_MUTATIONS = [
    lambda g: g.__setitem__("K", g["K"] - 2),
    lambda g: g.__setitem__("sum_M", 4),
    lambda g: g.__setitem__("schema", "x"),
    lambda g: g.__setitem__("status", pg.STATUS_STOP_RECORDS),
    lambda g: g["inputs"].__setitem__("models_json_sha256", "other"),
    lambda g: g["batteries"]["v2"].__setitem__(
        "entrants", g["batteries"]["v2"]["entrants"][::-1]
    ),
    lambda g: g["batteries"]["v2"].__setitem__("n_entered", 5),
    lambda g: g["batteries"]["G"].__setitem__("R", 6),
    lambda g: g["batteries"]["v2"].__setitem__("R", 8.0),
    lambda g: g["batteries"]["v2"].__setitem__("R", 7),
    lambda g: g["batteries"]["O_time"].__setitem__("gate", st.GATE_HELD_COST),
    lambda g: g["batteries"]["v3"]["models"]["qwen3:8b"]["envelope"].__setitem__(
        "numerator", 0.05
    ),
    lambda g: g["batteries"]["v3"]["models"]["qwen3:8b"]["envelope"].__setitem__(
        "denominator", 0
    ),
    lambda g: g["batteries"].pop("v3"),
    lambda g: g["batteries"]["v2"].__setitem__("entrants", ["qwen3:8b", "llama3.1:8b"]),
    lambda g: [
        g["batteries"][b].__setitem__("gate", st.GATE_STOP_POWER)
        or g["batteries"][b].__setitem__("R", None)
        for b in R_MAIN
    ],
    # 16: 入場 2 の battery を GO と書く (n_entered・K・ΣM は正直な値)
    lambda g: _set_entrants(g, "v2", list(pl.MODELS[:2])),
    # 17: 入場 6 の battery を NOT_QUALIFIED と書く (R なし、K・ΣM は正直な値)
    lambda g: g["batteries"]["v2"].update(gate=st.VERDICT_NOT_QUALIFIED, R=None),
    # 18: models の status は 6 本とも entered のまま、entrants を先頭 3 本に
    # (K・ΣM は正直な値、H1)
    lambda g: _set_entrants(g, "G", list(pl.MODELS[:3]), statuses=False),
    # 19: pilot の ⊥ は 0 のまま envelope を 1/5 と書く (H1)
    lambda g: g["batteries"]["v3"]["models"]["qwen3:8b"].__setitem__(
        "envelope", {"numerator": 1, "denominator": 5}
    ),
    # 20: envelope の負の分子 (M1)
    lambda g: g["batteries"]["v3"]["models"]["qwen3:8b"]["envelope"].__setitem__(
        "numerator", -1
    ),
    # 21: ⊥ の数が整数でない (bot_n を浮動小数に)
    lambda g: g["batteries"]["v3"]["models"]["qwen3:8b"].__setitem__("bot_n", 720.0),
    # 22: ⊥ の数が parse の規則の外 (bot_n = 0)
    lambda g: g["batteries"]["v3"]["models"]["qwen3:8b"].__setitem__("bot_n", 0),
    # 23: models が object でない
    lambda g: g["batteries"]["O_time"].__setitem__("models", []),
    # 24〜28 (code-reviewer MEDIUM): ⊥ の数そのものの妥当性。envelope は数と整合させる
    # 24: arm の数が登録と違う (v2 の 5 arm を 4 本に)
    lambda g: _set_bots(g, "v2", "qwen3:8b", [0, 0, 0, 0]),
    # 25: bot_counts が list でない
    lambda g: g["batteries"]["v3"]["models"]["qwen3:8b"].__setitem__(
        "bot_counts", None
    ),
    # 26: bot_counts が浮動小数 (parse_rule の int() で黙って 0 になる)
    lambda g: _set_bots(g, "v3", "qwen3:8b", [0.0, 0.0, 0.0, 0.0]),
    # 27: 負の数 (parse_rule は通し、envelope は負の分数で復元と一致する)
    lambda g: _set_bots(g, "v3", "qwen3:8b", [-200, -200, -200, -200]),
    # 28: parse の規則を通らない数のまま status が entered (145/720 > 1/5、envelope 1/5)
    lambda g: _set_bots(g, "v3", "qwen3:8b", [145, 0, 0, 0]),
]


def _set_bots(
    g: dict[str, Any], battery: str, model: str, counts: list[Any], n: int = 720
) -> None:
    """⊥ の数を書き換え、envelope を同じ規則の復元に合わせる.

    envelope の照合では拒めない形。
    """
    env = st.parse_rule(counts, n)[1]
    g["batteries"][battery]["models"][model].update(
        bot_counts=counts,
        bot_n=n,
        envelope={"numerator": env.numerator, "denominator": env.denominator},
    )


def _set_entrants(
    g: dict[str, Any], battery: str, ents: list[str], *, statuses: bool = True
) -> None:
    g["batteries"][battery].update(entrants=ents, n_entered=len(ents))
    if statuses:  # 入場の外のモデルの status を entered から外す (gate の内部で整合)
        for m, mm in g["batteries"][battery]["models"].items():
            mm["status"] = st.ENTERED if m in ents else pg.M_NOT_COMPUTED
    n_entered = {b: len(e["entrants"]) for b, e in g["batteries"].items()}
    g["K"] = st.n_tests(n_entered)
    g["sum_M"] = sum(n for n in n_entered.values() if n >= st.MIN_ENTRANTS)


@pytest.mark.parametrize("mutate", GATE_MUTATIONS)
def test_gate_contract_violations_are_refused(
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    good = make_gate()
    sc.read_gate(good, _ref_sha())
    dr.read_gate(good, _ref_sha())  # driver の読み手も同じ gate を受ける
    with pytest.raises(sc.GateError):
        sc.read_gate(_bad(good, mutate), _ref_sha())


@pytest.mark.parametrize("mutate", GATE_MUTATIONS)
def test_driver_refuses_every_gate_the_scorer_refuses(
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    """2 つの独立な読み手は同じ負例をすべて拒否する.

    DD-12 M1: driver が受け scorer が拒む gate を残さない。
    """
    with pytest.raises(dr.PreflightError):
        dr.read_gate(_bad(make_gate(), mutate), _ref_sha())


def test_gate_envelope_is_an_exact_fraction() -> None:
    g = sc.read_gate(
        make_gate({("v2", "qwen3:8b"): ([1, 0, 0, 0, 0], 720)}), _ref_sha()
    )
    assert g.envelopes[("v2", "qwen3:8b")] == Fraction(37, 720)
    assert g.r_go == R_MAIN
    assert g.k_tests == 120
    assert g.sum_m == 24


def test_gate_schema_matches_the_pilot_gate() -> None:
    assert sc.GATE_SCHEMA == pg.SCHEMA


# ------------------------------------------------------------ 出力


def test_output_is_written_once_and_checked(
    graded_run: pathlib.Path, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = write_inputs(tmp_path, make_gate())
    out = tmp_path / "main" / "verdict.json"
    body = sc.run_scorer(
        graded_run,
        out,
        gate_path=paths["gate"],
        models_json=paths["models"],
        fixture_path=paths["fixtures"],
        root=paths["root"],
    )
    assert out.read_bytes() == body.encode("utf-8")
    with pytest.raises(FileExistsError):
        sc.run_scorer(
            graded_run,
            out,
            gate_path=paths["gate"],
            models_json=paths["models"],
            fixture_path=paths["fixtures"],
            root=paths["root"],
        )
    args = [
        "--run-dir",
        str(graded_run),
        "--out",
        str(out),
        "--gate",
        str(paths["gate"]),
        "--models-json",
        str(paths["models"]),
        "--fixtures",
        str(paths["fixtures"]),
    ]
    # CLI の照合の root は module の repo に固定 (test は差し替える)
    monkeypatch.setattr(sc, "_REPO_ROOT", paths["root"])
    assert sc.main([*args, "--check"]) == 0
    out.write_bytes(body.encode("utf-8").replace(b"ESTABLISHED", b"INCONCLUSIVE", 1))
    assert sc.main([*args, "--check"]) == 3


def test_refused_gate_exits_2(
    graded_run: pathlib.Path, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = write_inputs(tmp_path, _bad(make_gate(), GATE_MUTATIONS[0]))
    monkeypatch.setattr(sc, "_REPO_ROOT", paths["root"])
    rc = sc.main(
        [
            "--run-dir",
            str(graded_run),
            "--out",
            str(tmp_path / "v.json"),
            "--gate",
            str(paths["gate"]),
            "--models-json",
            str(paths["models"]),
            "--fixtures",
            str(paths["fixtures"]),
        ]
    )
    assert rc == 2
    assert not (tmp_path / "v.json").exists()


def test_nondeterminism_is_caught(
    graded_run: pathlib.Path, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = write_inputs(tmp_path, make_gate())
    calls = iter(range(10))
    real = sc.compute_verdict

    def flaky(*a: Any, **k: Any) -> dict[str, Any]:
        out = real(*a, **k)
        out["K"] = next(calls)
        return out

    monkeypatch.setattr(sc, "compute_verdict", flaky)
    with pytest.raises(sc.NotDeterministicError):
        sc.compute_twice(
            graded_run,
            paths["gate"],
            paths["models"],
            paths["fixtures"],
            root=paths["root"],
        )


def test_model_interval_and_q_r(graded_verdict: dict[str, Any]) -> None:
    m = graded_verdict["batteries"]["v2"]["models"]["qwen3:4b-q4_K_M"]
    lo, hi = m["C_interval"]
    assert lo <= m["C"] <= hi
    assert m["q"] == 1.0
    assert m["r"] == pytest.approx(0.75)
    assert m["six_classes"][v2bat.LEVER_ARMS[3]]["foil"] == 480


def test_correlation_is_null_without_variance(graded_verdict: dict[str, Any]) -> None:
    assert all(
        p["correlation"] is None for p in graded_verdict["batteries"]["v2"]["pairs"]
    )
    assert sc.correlation(np.array([0.0, 1.0, 0.0]), np.array([1.0, 0.0, 1.0])) == -1.0


def test_component_sign_labels() -> None:
    assert sc.component_sign({"a": -0.1, "b": -0.2}) == "all_negative"
    assert sc.component_sign({"a": -0.1, "b": 0.2}) == "mixed_signs"
    assert sc.component_sign({"a": 0.0, "b": 0.2}) == "neither"


def test_descriptive_bounds_use_the_registered_levels(
    graded_verdict: dict[str, Any],
) -> None:
    """記述の対は判定と同じ α/K、モデルの C は両側 α/(2ΣM) (DD-10・§M).

    graded の単位の値はモデルごとに定数なので、期待値を定数の配列から直接作る。
    """
    v2 = graded_verdict["batteries"]["v2"]
    n = R_MAIN["v2"] * st.SPECS["v2"].units_per_rep
    c = {m: v2["models"][m]["C"] for m in pl.MODELS}
    level = st.ALPHA / 120
    for p in v2["pairs"]:
        a, b = p["pair"]
        d = np.full(n, c[a] - c[b])
        assert p["n_units"] == n
        assert p["lower_bound_a_minus_b"] == sc._f(st.lower_bound(d, -2.0, 2.0, level))
        assert p["lower_bound_b_minus_a"] == sc._f(st.lower_bound(-d, -2.0, 2.0, level))
    for p in v2["named"]:
        d = np.full(n, c[p["pair"][0]] - c[p["pair"][1]])
        assert p["lower_bound"] == sc._f(st.lower_bound(d, -2.0, 2.0, level))
    level_c = st.ALPHA / (2 * 24)
    for m in pl.MODELS:
        u = np.full(n, c[m])
        assert v2["models"][m]["C_interval"] == [
            sc._f(st.lower_bound(u, -1.0, 1.0, level_c)),
            sc._f(st.upper_bound(u, -1.0, 1.0, level_c)),
        ]


def test_decide_battery_gets_the_gate_levels_and_halves(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§D・§F: 判定には gate の K・ΣM・入場数と、本走の r の半分を渡す.

    1 モデルを外した run でも K・ΣM・n_entered は gate の値のまま。
    """
    run = tmp_path / "run"
    name = rd.seg_name(rd.STAGE_MAIN, "v2", "gemma2:9b")
    write_main(run, equal_zero, status={name: dr.S_TIMEOUT})
    seen: list[tuple[int, int, np.ndarray, int, int]] = []
    real = st.decide_battery

    def spy(units: np.ndarray, k: int, m: int, halves: np.ndarray, **kw: Any) -> Any:
        seen.append((k, m, halves, kw["n_entered"], units.shape[1]))
        return real(units, k, m, halves, **kw)

    monkeypatch.setattr(st, "decide_battery", spy)
    score(tmp_path, run)  # 2 回計算する
    order = [b for b in st.BATTERIES if b in R_MAIN] * 2
    assert len(seen) == len(order)
    for (k, m, halves, n_entered, n_units), b in zip(seen, order, strict=True):
        assert (k, m, n_entered) == (120, 24, 6)
        r_list = sc.main_r_list(b, R_MAIN[b])
        np.testing.assert_array_equal(halves, st.half_labels(st.SPECS[b], r_list))
        assert halves.size == n_units
        assert 0 < halves.sum() < halves.size


def test_run_wide_violation_makes_every_battery_invalid(
    graded_run: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """区切りの外 (状態表) の違反は全 battery を INVALID にする (DD-10)."""
    run = tmp_path / "run"
    shutil.copytree(graded_run, run)
    tpath = run / rd.STAGE_MAIN / dr.SEGMENTS_NAME
    table = json.loads(tpath.read_text(encoding="utf-8"))
    table["expected_ollama_version"] = "0.0.0"
    tpath.write_bytes(dr.json_text(table).encode("utf-8"))
    out = score(tmp_path, run)
    assert out["record_violations"]
    for b in R_MAIN:
        assert out["batteries"][b]["verdict"] == st.VERDICT_INVALID
        assert any(
            "expected_ollama_version" in v for v in out["batteries"][b]["violations"]
        )


def test_gate_with_a_not_qualified_battery_is_read() -> None:
    """入場 2 の battery は K・ΣM に数えない (§D)。その gate を受ける."""
    gate = make_gate()
    _set_entrants(gate, "G", list(pl.MODELS[:2]))
    gate["batteries"]["G"].update(gate=st.VERDICT_NOT_QUALIFIED, R=None)
    assert gate["sum_M"] == 18
    read = sc.read_gate(gate, _ref_sha())
    dr.read_gate(gate, _ref_sha())
    assert read.sum_m == 18
    assert read.k_tests == gate["K"]
    assert read.labels["G"] == st.VERDICT_NOT_QUALIFIED


def _imports(mod: Any) -> set[str]:
    tree = ast.parse(pathlib.Path(mod.__file__).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names.update(f"{node.module}.{a.name}" for a in node.names)
        elif isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
    return names


def test_scorer_import_closure_excludes_plan_driver_and_writers() -> None:
    """DD-1: scorer から import で届く module の全体に plan・driver・書き手が無い.

    直接の import だけでなく閉包を見る (Codex r1 M2: 書き手を経由する回帰)。
    """
    root = pathlib.Path(sc.__file__).resolve().parents[1]
    closure = mm.import_closure(root, ("scripts/benchmark_stage2_scorer.py",))
    assert "scripts/benchmark_stage2_manifest_main.py" in closure
    banned = {
        "scripts/benchmark_stage2_plan.py",
        "scripts/benchmark_stage2_driver.py",
        "scripts/benchmark_stage2_freeze.py",
        "scripts/benchmark_stage2_driver_mutation_check.py",
    }
    assert not closure & banned
    # 書き手を経由する import は閉包が拾う (負例)
    via_writer = mm.import_closure(root, ("scripts/benchmark_stage2_freeze.py",))
    assert {
        "scripts/benchmark_stage2_plan.py",
        "scripts/benchmark_stage2_driver.py",
    } <= (via_writer)


@pytest.mark.parametrize(
    "mod", [sc, fxm, rd, mm], ids=["scorer", "fixtures", "records", "manifest_main"]
)
def test_scorer_does_not_import_plan_or_driver(mod: Any) -> None:
    """DD-1: scorer とそれが import する段 2 の module は plan・driver を import しない.

    docstring の言及は数えず、import 文だけを見る。
    """
    names = _imports(mod)
    assert names
    assert not any(
        "benchmark_stage2_plan" in n or "benchmark_stage2_driver" in n for n in names
    )
