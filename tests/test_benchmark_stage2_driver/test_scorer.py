"""判別性 gate 段 2 — 本走の判別性 scorer の test (合成の本走の記録、GPU なし).

合成記録は driver と同じ形 (``dr.record_line``・``dr.meta_for``・
``dr.json_text``) で直接書く。
gate は契約どおりの合成 (v2 R 8・v3 R 8・O_time R 6 が GO、
G は STOP_POWER、6 モデル入場)。
"""

from __future__ import annotations

import ast
import json
import pathlib
import shutil
from fractions import Fraction
from typing import TYPE_CHECKING, Any

import numpy as np
import pytest
from scripts import benchmark_stage2_driver as dr
from scripts import benchmark_stage2_fixtures as fxm
from scripts import benchmark_stage2_pilot_gate as pg
from scripts import benchmark_stage2_plan as pl
from scripts import benchmark_stage2_records as rd
from scripts import benchmark_stage2_scorer as sc
from scripts import benchmark_stage2_stats as st
from scripts import skill_lever_battery as v2bat

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
    envelopes: Mapping[tuple[str, str], tuple[int, int]] | None = None,
) -> dict[str, Any]:
    batteries: dict[str, Any] = {}
    for b in st.BATTERIES:
        models = {}
        for m in pl.MODELS:
            num, den = (envelopes or {}).get((b, m), (1, 20))
            models[m] = {
                "status": st.ENTERED,
                "envelope": {"numerator": num, "denominator": den},
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
    return paths


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
        sc.compute_twice(run_dir, paths["gate"], paths["models"], paths["fixtures"])
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
    assert all(p["fixture_pairs"] == fx_pairs for p in v3["named"])
    assert any("でも説明しうる" in line for line in v3["report_text"])
    assert any("得点差までに固定" in line for line in v3["report_text"])
    assert graded_verdict["batteries"]["v2"]["named"][0]["fixture_pairs"] == []


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


def test_all_models_invalid_meta_is_invalid(tmp_path: pathlib.Path) -> None:
    run = tmp_path / "run"
    bad = {rd.seg_name(rd.STAGE_MAIN, "v2", m): dr.S_INVALID_META for m in pl.MODELS}
    write_main(run, graded, status=bad)
    assert score(tmp_path, run)["batteries"]["v2"]["verdict"] == st.VERDICT_INVALID


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
    """Gate の envelope (整数の分数) を使う: 24/480 = 1/20 を 1/21 にすると外れる."""
    run = tmp_path / "run"
    write_main(run, with_bots("qwen3:14b", 24, graded))
    gate = make_gate({("v2", "qwen3:14b"): (1, 21)})
    v2 = score(tmp_path, run, gate)["batteries"]["v2"]
    assert "qwen3:14b" not in v2["report_set"]


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
    out = json.loads(
        sc.compute_twice(graded_run, paths["gate"], paths["models"], paths["fixtures"])
    )
    for b in R_MAIN:
        assert out["batteries"][b]["verdict"] == st.VERDICT_INVALID
    paths["fixtures"].unlink()
    out = json.loads(
        sc.compute_twice(graded_run, paths["gate"], paths["models"], paths["fixtures"])
    )
    assert all(out["batteries"][b]["verdict"] == st.VERDICT_INVALID for b in R_MAIN)


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
]


@pytest.mark.parametrize("mutate", GATE_MUTATIONS)
def test_gate_contract_violations_are_refused(
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    good = make_gate()
    sc.read_gate(good, _ref_sha())
    dr.read_gate(good)  # driver の読み手も同じ gate を受ける
    with pytest.raises(sc.GateError):
        sc.read_gate(_bad(good, mutate), _ref_sha())


def test_gate_envelope_is_an_exact_fraction() -> None:
    g = sc.read_gate(make_gate({("v2", "qwen3:8b"): (37, 720)}), _ref_sha())
    assert g.envelopes[("v2", "qwen3:8b")] == Fraction(37, 720)
    assert g.r_go == R_MAIN
    assert g.k_tests == 120
    assert g.sum_m == 24


def test_gate_schema_matches_the_pilot_gate() -> None:
    assert sc.GATE_SCHEMA == pg.SCHEMA


# ------------------------------------------------------------ 出力


def test_output_is_written_once_and_checked(
    graded_run: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    paths = write_inputs(tmp_path, make_gate())
    out = tmp_path / "main" / "verdict.json"
    body = sc.run_scorer(
        graded_run,
        out,
        gate_path=paths["gate"],
        models_json=paths["models"],
        fixture_path=paths["fixtures"],
    )
    assert out.read_bytes() == body.encode("utf-8")
    with pytest.raises(FileExistsError):
        sc.run_scorer(
            graded_run,
            out,
            gate_path=paths["gate"],
            models_json=paths["models"],
            fixture_path=paths["fixtures"],
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
    assert sc.main([*args, "--check"]) == 0
    out.write_bytes(body.encode("utf-8").replace(b"ESTABLISHED", b"INCONCLUSIVE", 1))
    assert sc.main([*args, "--check"]) == 3


def test_refused_gate_exits_2(graded_run: pathlib.Path, tmp_path: pathlib.Path) -> None:
    paths = write_inputs(tmp_path, _bad(make_gate(), GATE_MUTATIONS[0]))
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

    def flaky(*a: Any) -> dict[str, Any]:
        out = real(*a)
        out["K"] = next(calls)
        return out

    monkeypatch.setattr(sc, "compute_verdict", flaky)
    with pytest.raises(sc.NotDeterministicError):
        sc.compute_twice(graded_run, paths["gate"], paths["models"], paths["fixtures"])


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


def _imports(mod: Any) -> set[str]:
    tree = ast.parse(pathlib.Path(mod.__file__).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names.update(f"{node.module}.{a.name}" for a in node.names)
        elif isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
    return names


@pytest.mark.parametrize("mod", [sc, fxm, rd], ids=["scorer", "fixtures", "records"])
def test_scorer_does_not_import_plan_or_driver(mod: Any) -> None:
    """DD-1: scorer とそれが import する段 2 の module は plan・driver を import しない.

    docstring の言及は数えず、import 文だけを見る。
    """
    names = _imports(mod)
    assert names
    assert not any(
        "benchmark_stage2_plan" in n or "benchmark_stage2_driver" in n for n in names
    )
