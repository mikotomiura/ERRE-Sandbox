"""判別性 gate 段 2 — 記録の読み手と pilot gate の test (合成記録、GPU なし).

合成記録は driver と同じ形 (``dr.record_line``・``dr.meta_for``・
``dr.json_text``) で直接書く (全 6 モデルの pilot は 58,968 呼び出しなので
FakeOllama を通さない)。driver の出力を読み手が
そのまま読めることは、本走の小さい plan を FakeOllama で回す test で結ぶ。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
from functools import cache
from typing import TYPE_CHECKING, Any

import numpy as np
import pytest
from scripts import benchmark_stage2_driver as dr
from scripts import benchmark_stage2_pilot_gate as pg
from scripts import benchmark_stage2_plan as pl
from scripts import benchmark_stage2_records as rd
from scripts import benchmark_stage2_stats as st
from scripts import benchmark_stage2_units as un
from scripts import generalization_probe_battery as gbat
from scripts import generalization_probe_pilot_gate as gpg
from scripts import o_time_probe_battery as obat
from scripts import o_time_probe_pilot_gate as opg
from scripts import o_time_probe_scorer as osc
from scripts import skill_experience_battery as v3bat
from scripts import skill_lever_battery as v2bat

from tests.test_benchmark_stage2_driver.main_tree import build_tree

if TYPE_CHECKING:
    import pathlib
    from collections.abc import Callable, Mapping, Sequence

BOT = "?"  # どの battery の parse でも ⊥


def _template(model: str) -> str:
    return f"{{{{ .Prompt }}}} template of {model}"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _reference() -> dict[str, Any]:
    return {
        "ollama_version": dr.OLLAMA_VERSION,
        "models": {
            m: {
                "model_digest": f"digest-{m}",
                "template_sha256": _sha(_template(m).encode()),
            }
            for m in pl.MODELS
        },
    }


# ------------------------------------------------------------ 応答の方策


_ACTIONS = {
    "v2": v2bat.ACTIONS,
    "v3": v2bat.ACTIONS,
    "G": gbat.ACTIONS,
    "O_time": obat.ACTIONS,
}
_LEVER = {
    "v2": v2bat.LEVER_ARMS,
    "v3": v3bat.JUDGE_ARMS,
    "G": gbat.LEVER_ARMS,
    "O_time": obat.LEVER_ARMS,
}


def _cell_key(spec: pl.CallSpec) -> tuple[Any, ...]:
    if spec.battery == "O_time":
        return (spec.arm, spec.encoding, spec.replicate, spec.probe_id, spec.k)
    return (spec.arm, spec.replicate, spec.probe_id, spec.k)


@cache
def _lever_label(battery: str, key: tuple[Any, ...], want: str) -> str:
    for label in _ACTIONS[battery]:
        if un.category(battery, key, label) == want:
            return label
    raise AssertionError((battery, key, want))


@cache
def _m0_label(arm: str, pid: str, want: str) -> str:
    for label in obat.ACTIONS:
        if osc.category(label, opg.M0_ARMS[arm], osc.room_index(pid)) == want:
            return label
    raise AssertionError((arm, pid, want))


# モデルごとの target を選ぶ lever arm の本数 (残りは foil)。
# 単位の値は項目の中で r に依らない (残差 0)
N_TARGET = {
    "qwen3:1.7b": 4,
    "qwen3:4b-q4_K_M": 3,
    "qwen3:8b": 2,
    "qwen3:14b": 1,
    "llama3.1:8b": 0,
    "gemma2:9b": 2,
}


def base_policy(model: str, spec: pl.CallSpec) -> str:
    b = spec.battery
    if spec.purpose == pl.P_LEVER:
        want = "w" if _LEVER[b].index(spec.arm) < N_TARGET[model] else "foil"
        return _lever_label(b, _cell_key(spec), want)
    if spec.purpose == pl.P_M0:
        return _m0_label(spec.arm, spec.probe_id, "w")
    if spec.purpose == pl.P_KNOW:
        return gbat.key_class(gbat.all_keys()[int(spec.probe_id[1:])])
    return _ACTIONS[b][0]


# ---------------------------------------- 合成の run (driver と同じ形)


def _row(seg: pl.Segment, index: int, spec: pl.CallSpec, raw: str) -> dict[str, Any]:
    return {
        "stage": seg.stage,
        "battery": seg.battery,
        "model": seg.model,
        "attempt": 1,
        "call_index": index,
        "purpose": spec.purpose,
        "arm": spec.arm,
        "encoding": spec.encoding,
        "replicate": spec.replicate,
        "probe_id": spec.probe_id,
        "k": spec.k,
        "seed": spec.seed,
        "prompt_sha256": pl.messages_sha256(spec.messages_list()),
        "raw": raw,
        "response_model": seg.model,
        "prompt_eval_count": 17,
        "eval_count": 2,
        "done_reason": "stop",
        "n_sends": 1,
    }


def write_pilot(
    run_dir: pathlib.Path,
    policy: Callable[[str, pl.CallSpec], str] = base_policy,
    *,
    models: Sequence[str] = pl.MODELS,
    status: Mapping[str, str] | None = None,
) -> None:
    segs = [
        s
        for s in pl.pilot_plan()
        if s.model in models
        and (s.stage == pl.STAGE_PILOT or pl.REPLAY_MODEL in models)
    ]
    root = run_dir / pl.STAGE_PILOT
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
            adir = dr.attempt_dir(dr.segment_dir(root, pl.STAGE_PILOT, seg), 1)
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
        "run_stage": pl.STAGE_PILOT,
        "plan_digest": pdig,
        "expected_ollama_version": dr.OLLAMA_VERSION,
        "segments": entries,
        "order": [s.name for s in segs],
    }
    (root / dr.SEGMENTS_NAME).write_bytes(dr.json_text(table).encode("utf-8"))


def _records_path(run_dir: pathlib.Path, name: str) -> pathlib.Path:
    stage, battery, model = name.split("/")
    base = run_dir / pl.STAGE_PILOT
    if stage != pl.STAGE_PILOT:
        base = base / stage
    return base / battery / dr.model_dirname(model) / "attempt-1" / dr.RECORDS_NAME


def rewrite(
    run_dir: pathlib.Path,
    name: str,
    mutate: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
    *,
    fix_sha: bool = True,
) -> None:
    """記録を書き換え、状態表の sha を合わせる.

    sha の照合でなく構造の検査で落ちることを見る。
    """
    path = _records_path(run_dir, name)
    rows = [json.loads(x) for x in path.read_text(encoding="ascii").split("\n")[:-1]]
    data = dr.records_bytes([dr.record_line(r) for r in mutate(rows)])
    path.write_bytes(data)
    if fix_sha:
        tpath = run_dir / pl.STAGE_PILOT / dr.SEGMENTS_NAME
        table = json.loads(tpath.read_text(encoding="utf-8"))
        table["segments"][name]["records_sha256"] = _sha(data)
        tpath.write_bytes(dr.json_text(table).encode("utf-8"))


def _read(run_dir: pathlib.Path, models: Sequence[str] = pl.MODELS) -> rd.RunRead:
    return rd.read_run(run_dir, rd.STAGE_PILOT, _reference(), models=models)


def fake_select_r(
    spec: st.BatterySpec, units: np.ndarray, k_tests: int
) -> tuple[int | None, list[st.SpikeRow]]:
    del units, k_tests
    return spec.r_step, []


def _gate(run_dir: pathlib.Path, **kw: Any) -> dict[str, Any]:
    kw.setdefault("select_r", fake_select_r)
    kw.setdefault("negative_all", lambda *_a, **_k: 0.0)
    return pg.compute_gate(_read(run_dir), models_json_sha256="ref", **kw)


ONE = ("qwen3:8b",)  # 区切りの構造の test は 1 モデル (+ 再生) で


@pytest.fixture(scope="module")
def one_model_run(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    run = tmp_path_factory.mktemp("one") / "run"
    write_pilot(run, models=ONE)
    return run


@pytest.fixture
def one_run(one_model_run: pathlib.Path, tmp_path: pathlib.Path) -> pathlib.Path:
    dst = tmp_path / "run"
    shutil.copytree(one_model_run, dst)
    return dst


# ---------------------------------------- 読み手: 独立な列挙と driver の形


def test_reader_row_keys_match_the_driver() -> None:
    assert rd.ROW_KEYS == dr.RECORD_KEYS


@pytest.mark.parametrize(
    ("stage", "battery", "r_count"),
    [
        *((rd.STAGE_PILOT, b, None) for b in st.BATTERIES),
        (rd.STAGE_REPLAY, "G", None),
        (rd.STAGE_REPLAY, "O_time", None),
        (rd.STAGE_MAIN, "v2", 8),
        (rd.STAGE_MAIN, "v3", 16),
        (rd.STAGE_MAIN, "G", 12),
        (rd.STAGE_MAIN, "O_time", 6),
    ],
)
def test_independent_enumeration_agrees_with_the_plan(
    stage: str, battery: str, r_count: int | None
) -> None:
    """読み手は plan を使わずに列挙する.

    両者の (key・目的・seed・prompt の sha・順) が一致する。
    """
    if stage == rd.STAGE_PILOT:
        calls = pl.pilot_calls(battery)
    elif stage == rd.STAGE_REPLAY:
        calls = pl.replay_calls(battery)
    else:
        assert r_count is not None
        calls = pl.main_calls(battery, r_count)
    got = [
        (*e.key, e.purpose, e.seed, e.prompt_sha256)
        for e in rd.expected_calls(stage, battery, r_count)
    ]
    want = [
        (
            c.arm,
            c.encoding,
            c.replicate,
            c.probe_id,
            c.k,
            c.purpose,
            c.seed,
            pl.messages_sha256(c.messages_list()),
        )
        for c in calls
    ]
    assert got == want


def test_digests_and_order_agree_with_the_plan() -> None:
    segs = pl.pilot_plan()
    assert [rd.seg_name(*x) for x in rd.expected_order(rd.STAGE_PILOT)] == [
        s.name for s in segs
    ]
    digs = [
        (
            s.name,
            rd.segment_digest(
                s.stage, s.battery, s.model, rd.expected_calls(s.stage, s.battery)
            ),
        )
        for s in segs
    ]
    assert digs == [(s.name, pl.segment_digest(s)) for s in segs]
    assert rd.plan_digest(digs) == pl.plan_digest(segs)
    r = {"O_time": 6, "G": 6, "v3": 8}
    ents = {"O_time": pl.MODELS[:3], "G": pl.MODELS[2:], "v3": pl.MODELS}
    want = [s.name for s in pl.main_plan(r, ents)]
    assert [
        rd.seg_name(*x)
        for x in rd.expected_order(
            rd.STAGE_MAIN, r_by_battery=r, models_by_battery=ents
        )
    ] == want


def test_reader_accepts_driver_output(tmp_path: pathlib.Path) -> None:
    """FakeOllama で driver を回した本走の記録を、読み手がそのまま読める (形の一致)."""
    from tests.test_benchmark_stage2_driver import test_driver as td

    r = {"O_time": 6}
    ents = {"O_time": ("qwen3:8b", "qwen3:14b")}
    segs = pl.main_plan(r, ents)
    clock = td.FakeClock()
    fake = td.FakeOllama(clock, content="the answer is " + obat.ACTIONS[0])
    table = asyncio.run(
        dr.run_stage(
            pl.STAGE_MAIN,
            tmp_path / "run",
            segs,
            transport=fake.transport(),
            endpoint="http://fake",
            reference=td._reference(),
            clock=clock.clock(),
        )
    )
    assert {v["status"] for v in table["segments"].values()} == {dr.S_COMPLETED}
    run = rd.read_run(
        tmp_path / "run",
        rd.STAGE_MAIN,
        td._reference(),
        r_by_battery=r,
        models_by_battery=ents,
    )
    assert run.violations == []
    for sr in run.segments.values():
        assert sr.status == rd.R_OK
        assert len(sr.rows) == 288
        assert {row.parsed for row in sr.rows} == {obat.ACTIONS[0]}


def test_one_model_run_reads_clean(one_run: pathlib.Path) -> None:
    run = _read(one_run, ONE)
    assert run.violations == []
    assert {sr.status for sr in run.segments.values()} == {rd.R_OK}
    know = [r for r in run.segments["pilot/G/qwen3:8b"].rows if r.purpose == rd.P_KNOW]
    assert len(know) == pg.N_KNOW
    # KNOW は parse_class で読む (lever の parse では分類名は ⊥)
    assert all(r.parsed in gbat.CLASSES for r in know)


# ---------------------------------------- 読み手: STOP (records) と not_computed


def _drop_dup(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """最後の行を落とし、最初の行を複製して末尾に (行数は同じ。重複と欠けが同時)."""
    dup = dict(rows[0])
    dup["call_index"] = len(rows) - 1
    return [*rows[:-1], dup]


def _out_of_range(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows[-1]["replicate"] = 99
    return rows


def _swap(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows[0], rows[1] = rows[1], rows[0]
    rows[0]["call_index"], rows[1]["call_index"] = 0, 1
    return rows


def _seed(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows[3]["seed"] += 1
    return rows


def _prompt(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows[3]["prompt_sha256"] = "0" * 64
    return rows


def _other_model(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows[3]["response_model"] = "qwen3:14b"
    return rows


def _bool_k(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows[3]["k"] = False
    return rows


def _purpose_swap(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows[3]["purpose"] = pl.P_LEVER  # v2 の先頭は C0
    return rows


@pytest.mark.parametrize(
    ("mutate", "pattern"),
    [
        (_drop_dup, "duplicate key"),
        (_out_of_range, "outside the registered grid"),
        (_swap, "call order"),
        (_seed, "seed differs"),
        (_prompt, "prompt differs"),
        (_other_model, "response_model"),
        (_bool_k, "k is not int"),
        (_purpose_swap, "purpose differs"),
    ],
)
def test_structure_violations_stop_records(
    one_run: pathlib.Path,
    mutate: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
    pattern: str,
) -> None:
    rewrite(one_run, "pilot/v2/qwen3:8b", mutate)
    run = _read(one_run, ONE)
    assert run.stop
    assert any(pattern in v for v in run.violations), run.violations


def test_sha_mismatch_stops(one_run: pathlib.Path) -> None:
    rewrite(one_run, "pilot/G/qwen3:8b", lambda rows: rows[::-1][::-1], fix_sha=False)
    assert not _read(one_run, ONE).stop  # 同じ bytes
    path = _records_path(one_run, "pilot/G/qwen3:8b")
    path.write_bytes(path.read_bytes().replace(b'"raw": "', b'"raw": "x', 1))
    run = _read(one_run, ONE)
    assert any("records sha differs" in v for v in run.violations)


def test_meta_differing_from_models_json_stops(one_run: pathlib.Path) -> None:
    ref = _reference()
    ref["models"]["qwen3:8b"]["model_digest"] = "other"
    run = rd.read_run(one_run, rd.STAGE_PILOT, ref, models=ONE)
    assert any("model_digest differs from models.json" in v for v in run.violations)


def test_plain_missing_rows_are_not_computed(one_run: pathlib.Path) -> None:
    rewrite(one_run, "pilot/v3/qwen3:8b", lambda rows: rows[:-5])
    run = _read(one_run, ONE)
    assert run.violations == []
    sr = run.segments["pilot/v3/qwen3:8b"]
    assert sr.status == rd.R_NOT_COMPUTED
    assert sr.reason == "5 rows missing"
    assert sr.rows == []


def test_reader_only_reads_the_adopted_attempt(one_run: pathlib.Path) -> None:
    """状態表が attempt-2 を採用と言えば attempt-2 だけを読む.

    attempt-1 に戻らない・補完しない。
    """
    tpath = one_run / pl.STAGE_PILOT / dr.SEGMENTS_NAME
    table = json.loads(tpath.read_text(encoding="utf-8"))
    table["segments"]["pilot/v2/qwen3:8b"].update(adopted_attempt=2, attempts_run=2)
    tpath.write_bytes(dr.json_text(table).encode("utf-8"))
    run = _read(one_run, ONE)
    assert any("cannot read adopted attempt" in v for v in run.violations)


def test_non_completed_segments_are_not_computed(tmp_path: pathlib.Path) -> None:
    write_pilot(
        tmp_path / "run",
        models=ONE,
        status={
            "pilot/v2/qwen3:8b": dr.S_TRANSPORT,
            "pilot/v3/qwen3:8b": dr.S_TIMEOUT,
            "pilot/G/qwen3:8b": dr.S_INVALID_META,
            "replay/O_time/qwen3:8b": dr.S_NOT_STARTED,
        },
    )
    run = _read(tmp_path / "run", ONE)
    assert run.violations == []
    got = {n: sr.status for n, sr in run.segments.items()}
    assert got["pilot/v2/qwen3:8b"] == rd.R_NOT_COMPUTED
    assert got["pilot/v3/qwen3:8b"] == rd.R_NOT_COMPUTED
    assert got["pilot/G/qwen3:8b"] == rd.R_INVALID_META
    assert got["replay/O_time/qwen3:8b"] == rd.R_NOT_COMPUTED
    assert got["pilot/O_time/qwen3:8b"] == rd.R_OK


def test_partial_invalid_version_stops(tmp_path: pathlib.Path) -> None:
    write_pilot(
        tmp_path / "run", models=ONE, status={"pilot/v2/qwen3:8b": dr.S_INVALID_VERSION}
    )
    assert any(
        "invalid_version on some" in v for v in _read(tmp_path / "run", ONE).violations
    )


def test_digest_or_order_tamper_stops(one_run: pathlib.Path) -> None:
    tpath = one_run / pl.STAGE_PILOT / dr.SEGMENTS_NAME
    table = json.loads(tpath.read_text(encoding="utf-8"))
    table["plan_digest"] = "0" * 64
    tpath.write_bytes(dr.json_text(table).encode("utf-8"))
    assert any("plan_digest" in v for v in _read(one_run, ONE).violations)
    table["order"] = table["order"][::-1]
    tpath.write_bytes(dr.json_text(table).encode("utf-8"))
    assert any("order differs" in v for v in _read(one_run, ONE).violations)


def test_stop_records_gate_has_no_decisions(one_run: pathlib.Path) -> None:
    rewrite(one_run, "pilot/v2/qwen3:8b", _seed)
    gate = pg.compute_gate(_read(one_run, ONE), models_json_sha256="ref")
    assert gate["status"] == pg.STATUS_STOP_RECORDS
    assert "batteries" not in gate
    with pytest.raises(dr.PreflightError):
        dr.read_gate(gate, "ref")


# ------------------------------------------------------------ pilot gate: 全 6 モデル


@pytest.fixture(scope="module")
def six_model_run(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    run = tmp_path_factory.mktemp("six") / "run"
    write_pilot(run)
    return run


def test_end_to_end_gate_with_the_frozen_selection(
    six_model_run: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """凍結の select_r・spike_negative_all・budget で gate.json を書く.

    driver がその gate.json から本走の plan を作れる。
    """
    out = tmp_path / "gate.json"
    ref = tmp_path / "models.json"
    ref.write_text(json.dumps(_reference()), encoding="utf-8")
    gate = pg.run_gate(six_model_run, out, ref)
    assert json.loads(out.read_text(encoding="utf-8")) == gate
    assert gate["status"] == pg.STATUS_OK
    assert gate["K"] == 4 * 6 * 5
    assert gate["sum_M"] == 24
    assert gate["inputs"]["models_json_sha256"] == _sha(ref.read_bytes())
    for b, entry in gate["batteries"].items():
        assert entry["entrants"] == list(pl.MODELS)
        # 候補を小さい順に当て、最初に OC を満たす R
        # (残差 0 の合成記録では size・較正は常に通る)
        rows = entry["spike_rows"]
        assert [r["r"] for r in rows] == st.r_candidates(st.SPECS[b])[: len(rows)]
        assert entry["R"] == rows[-1]["r"]
        assert rows[-1]["ok"] is True
        assert not any(r["ok"] for r in rows[:-1])
        assert all(r["size_rejects"] == 0 for r in rows)
        for m in pl.MODELS:
            assert entry["models"][m]["envelope"] == {"numerator": 1, "denominator": 20}
            assert entry["models"][m]["bot_counts"] == [0] * st.N_ARMS[b]
    labels = st.budget({b: e["R"] for b, e in gate["batteries"].items()})
    assert {b: e["gate"] for b, e in gate["batteries"].items()} == labels
    mg = dr.read_gate(gate, _sha(ref.read_bytes()))
    assert mg.k_tests == gate["K"]
    assert set(mg.r_by_battery) == {b for b, v in labels.items() if v == st.GATE_GO}
    with pytest.raises(FileExistsError):
        pg.run_gate(six_model_run, out, ref)


def test_pilot_units_follow_the_registered_order(six_model_run: pathlib.Path) -> None:
    """非対称な合成記録: 単位の値が §D の単位の順 (r 外側・項目) に並ぶ."""
    run = _read(six_model_run)
    for b in st.BATTERIES:
        sr = run.segments[f"pilot/{b}/gemma2:9b"]  # 2 本が target、2 本が foil
        u = pg.pilot_units(b, sr)
        spec = st.SPECS[b]
        assert u.size == spec.units_per_rep * st.R_PILOT
        if b in ("v2", "v3"):
            assert np.all(u == 0.0)  # 4 arm で (2 − 2) / 4
        else:
            # 族 0 (target の 2 arm) が +1、族 1 が −1。
            # 単位は r が外側、1 replicate の中は族が外側
            per = u.reshape(st.R_PILOT, 2, -1)
            assert np.all(per[:, 0] == 1.0)
            assert np.all(per[:, 1] == -1.0)


def _asymmetric(model: str, spec: pl.CallSpec) -> str:
    b, arm = spec.battery, spec.arm
    if model == "qwen3:14b" and b == "v2" and arm == v2bat.ARM_C0:
        return BOT  # C0 だけ ⊥ (v2 の parse は C0 を含む 5 本)
    if model == "llama3.1:8b" and b == "v3" and arm == v3bat.CONTROL_ARMS[3]:
        # 第 4 の L arm だけ 73/360 (> 1/5)。先頭 3 本だけを見れば通る (H4)
        return BOT if _bot_index(spec) < 73 else base_policy(model, spec)
    if model == "gemma2:9b" and spec.purpose == pl.P_KNOW:
        i = int(spec.probe_id[1:])
        truth = gbat.key_class(gbat.all_keys()[i])
        return next(c for c in gbat.CLASSES if c != truth) if i == 5 else truth
    if model == "qwen3:4b-q4_K_M" and spec.purpose == pl.P_M0:
        return _m0_label(
            arm, spec.probe_id, "foil"
        )  # M0 が採点で落ちる (lookup 不成立)
    if model == "qwen3:14b" and b == "O_time" and arm == "M_" + obat.LEVER_ARMS[0]:
        return BOT  # masked の 1 arm だけ ⊥
    return base_policy(model, spec)


_L4_ORDER: dict[tuple[int, str, int], int] = {}


def _bot_index(spec: pl.CallSpec) -> int:
    if not _L4_ORDER:
        keys = [
            (c.replicate, c.probe_id, c.k)
            for c in pl.pilot_calls("v3")
            if c.arm == v3bat.CONTROL_ARMS[3]
        ]
        _L4_ORDER.update({k: i for i, k in enumerate(keys)})
    return _L4_ORDER[(spec.replicate, spec.probe_id, spec.k)]


@pytest.fixture(scope="module")
def asym_gate(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    run = tmp_path_factory.mktemp("asym") / "run"
    write_pilot(run, _asymmetric, status={"pilot/O_time/qwen3:1.7b": dr.S_TRANSPORT})
    return _gate(run)


def test_qualification_reasons_follow_section_a(asym_gate: dict[str, Any]) -> None:
    b = asym_gate["batteries"]
    status = {k: {m: v["models"][m]["status"] for m in pl.MODELS} for k, v in b.items()}
    # M0 の欠測 (O_time の区切りが通信の欠測) と M0 の不合格を区別する (H4)
    for k in st.BATTERIES:
        want = rd.R_NOT_COMPUTED if k == "O_time" else pg.M_LOOKUP_NOT_COMPUTED
        assert status[k]["qwen3:1.7b"] == want
        assert status[k]["qwen3:4b-q4_K_M"] == st.REASON_LOOKUP
    assert asym_gate["lookup"]["qwen3:1.7b"]["status"] == pg.M_LOOKUP_NOT_COMPUTED
    assert asym_gate["lookup"]["qwen3:4b-q4_K_M"]["status"] == "failed"
    assert asym_gate["lookup"]["qwen3:4b-q4_K_M"]["passed"] is False
    assert asym_gate["lookup"]["qwen3:8b"]["passed"] is True
    assert status["v2"]["qwen3:14b"] == st.REASON_PARSE
    assert b["v2"]["models"]["qwen3:14b"]["bot_counts"] == [0, 0, 0, 0, 720]
    assert status["v3"]["llama3.1:8b"] == st.REASON_CONTROL
    assert b["v3"]["models"]["llama3.1:8b"]["control_counts"] == [0, 0, 0, 73]
    assert status["G"]["gemma2:9b"] == st.REASON_KNOW
    assert b["G"]["models"]["gemma2:9b"]["know_failures"] == [gbat.all_keys()[5]]
    assert status["O_time"]["qwen3:14b"] == st.REASON_ENVELOPE
    assert b["v2"]["entrants"] == ["qwen3:8b", "llama3.1:8b", "gemma2:9b"]
    assert b["v3"]["entrants"] == ["qwen3:8b", "qwen3:14b", "gemma2:9b"]
    assert b["G"]["entrants"] == ["qwen3:8b", "qwen3:14b", "llama3.1:8b"]
    assert b["O_time"]["entrants"] == ["qwen3:8b", "llama3.1:8b", "gemma2:9b"]
    assert asym_gate["K"] == 4 * 3 * 2
    assert asym_gate["sum_M"] == 12


def test_m0_check_is_read_as_its_passed_field() -> None:
    """凍結の m0_check は不合格でも空でない辞書を返す.

    辞書を真偽にすると lookup 不成立が入場する (H4)。
    """
    x = -np.ones((2, obat.N_ROOMS, obat.PILOT_R, 2, 2))
    res = opg.m0_check(x)
    assert res
    assert res["passed"] is False


def test_masked_counts_reach_the_frozen_gate(asym_gate: dict[str, Any]) -> None:
    m = asym_gate["batteries"]["O_time"]["models"]["qwen3:14b"]
    assert m["masked_n"] == 288
    assert m["masked_bottom_rates"] == [1.0, 0.0, 0.0, 0.0]
    g = asym_gate["batteries"]["G"]["models"]["qwen3:8b"]
    assert g["masked_n"] == 576
    assert g["masked_bottom_rates"] == [0.0] * 4


def test_not_qualified_and_not_computed_batteries(tmp_path: pathlib.Path) -> None:
    status = {f"pilot/v2/{m}": dr.S_TIMEOUT for m in pl.MODELS}
    status.update({f"pilot/v3/{m}": dr.S_TRANSPORT for m in pl.MODELS[2:]})
    write_pilot(tmp_path / "run", status=status)
    gate = _gate(tmp_path / "run")
    assert gate["batteries"]["v2"]["gate"] == pg.G_NOT_COMPUTED
    assert gate["batteries"]["v3"]["gate"] == pg.G_NOT_QUALIFIED
    assert gate["batteries"]["v3"]["n_entered"] == 2
    # K と ΣM は入場 ≥ 3 の battery だけ (STOP_POWER・HELD_COST は含む)
    assert gate["K"] == 2 * 6 * 5
    assert gate["sum_M"] == 12
    dr.read_gate(gate, "ref")


def test_stop_power_keeps_k_and_records_the_largest_candidate(
    six_model_run: pathlib.Path,
) -> None:
    seen: dict[str, Any] = {}

    def stop_g(
        spec: st.BatterySpec, units: np.ndarray, k: int
    ) -> tuple[int | None, list[st.SpikeRow]]:
        del units, k
        return (None, []) if spec.name == "G" else (spec.r_step, [])

    def neg(
        spec: st.BatterySpec, units: np.ndarray, k: int, r: int, rng: object
    ) -> float:
        del rng
        seen[spec.name] = (r, k, units.shape)
        return 0.25

    gate = _gate(six_model_run, select_r=stop_g, negative_all=neg)
    g = gate["batteries"]["G"]
    assert g["gate"] == st.GATE_STOP_POWER
    assert g["R"] is None
    # STOP_POWER の battery も K に入る
    assert gate["K"] == 120
    assert gate["sum_M"] == 24
    assert seen["G"] == (st.r_candidates(st.SPECS["G"])[-1], 120, (6, 16 * 12))
    assert g["spike_negative_all"] == {"R": 36, "p": 0.25}
    mg = dr.read_gate(gate, "ref")
    assert "G" not in mg.r_by_battery
    assert mg.entrants["G"] == tuple(pl.MODELS)


# ---------------------------------------- driver: gate.json の契約 (H5)


@pytest.fixture(scope="module")
def good_gate(six_model_run: pathlib.Path) -> dict[str, Any]:
    return _gate(six_model_run)


def _bad(gate: dict[str, Any], f: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    g = json.loads(json.dumps(gate))
    f(g)
    return g


@pytest.mark.parametrize(
    "mutate",
    [
        lambda g: g.__setitem__("K", g["K"] - 2),
        lambda g: g.__setitem__("sum_M", 4),
        lambda g: g.__setitem__("schema", "x"),
        lambda g: g["batteries"]["v2"].__setitem__(
            "entrants", g["batteries"]["v2"]["entrants"][::-1]
        ),
        lambda g: g["batteries"]["v2"].__setitem__("n_entered", 5),
        lambda g: g["batteries"]["G"].__setitem__("R", 7),
        lambda g: g["batteries"]["G"].__setitem__("R", 6.0),
        lambda g: g["batteries"]["O_time"].__setitem__("gate", st.GATE_HELD_COST),
        lambda g: g["batteries"]["v3"]["models"]["qwen3:8b"]["envelope"].__setitem__(
            "numerator", 0.05
        ),
        lambda g: g["batteries"].pop("v3"),
        lambda g: g["batteries"]["v2"].__setitem__(
            "entrants", ["qwen3:8b", "llama3.1:8b"]
        ),
    ],
)
def test_read_gate_rejects_contract_violations(
    good_gate: dict[str, Any], mutate: Callable[[dict[str, Any]], None]
) -> None:
    dr.read_gate(good_gate, "ref")
    with pytest.raises(dr.PreflightError):
        dr.read_gate(_bad(good_gate, mutate), "ref")


def test_main_plan_runs_only_entrants(
    good_gate: dict[str, Any], tmp_path: pathlib.Path
) -> None:
    g = _bad(good_gate, lambda _g: None)
    # O_time の入場から 2 本を外しても (4 本、入場 ≥ 3)、
    # K・ΣM は入場数から再計算して照合する
    o = g["batteries"]["O_time"]
    o["entrants"] = list(pl.MODELS[:4])
    o["n_entered"] = 4
    for m in pl.MODELS[4:]:  # 入場は models の status と照合される (DD-12 H1)
        o["models"][m]["status"] = pg.M_NOT_COMPUTED
    g["K"] = 3 * 30 + 12
    g["sum_M"] = 22
    path = tmp_path / "gate.json"
    path.write_text(json.dumps(g), encoding="utf-8")
    models = tmp_path / "models.json"
    models.write_bytes(b"{}")
    with pytest.raises(dr.PreflightError, match="models_json_sha256"):
        dr.plan_for(pl.STAGE_MAIN, path, models)  # gate の sha "ref" と違う models.json
    g["inputs"]["models_json_sha256"] = dr.sha256_bytes(models.read_bytes())
    path.write_text(json.dumps(g), encoding="utf-8")
    root = build_tree(
        tmp_path / "root",
        gate_bytes=path.read_bytes(),
        models_bytes=models.read_bytes(),
    )
    segs = dr.plan_for(pl.STAGE_MAIN, path, models, root=root)
    g["inputs"]["models_json_sha256"] = "ref"
    go = dr.read_gate(g, "ref").r_by_battery
    assert {s.battery for s in segs} == set(go)
    if "O_time" in go:
        assert [s.model for s in segs if s.battery == "O_time"] == list(pl.MODELS[:4])
    for s in segs:
        assert s.model in g["batteries"][s.battery]["entrants"]


def test_envelope_is_an_exact_fraction(asym_gate: dict[str, Any]) -> None:
    """Envelope は浮動小数を経由せず分子・分母で残る.

    境界ちょうどの比較を誤らない (H5)。
    """
    from fractions import Fraction

    for entry in asym_gate["batteries"].values():
        for m in entry["entrants"]:
            mm = entry["models"][m]
            env = Fraction(mm["envelope"]["numerator"], mm["envelope"]["denominator"])
            assert env == st.parse_rule(mm["bot_counts"], mm["bot_n"])[1]
    # v2 の pilot 各腕 90/720 → envelope 7/40、本走 84/480 はちょうど境界で残る
    _, env = st.parse_rule([90] * 5, 720)
    assert env == Fraction(7, 40)
    assert not st.envelope_exceeded([84], 480, env)
    assert st.envelope_exceeded([85], 480, env)


# ---------------------------------------- 段 3.5 の certification で足したもの
# (変異 harness の witness。既存の test が捕まえなかった読み手・pilot gate の行)


def _table(run_dir: pathlib.Path) -> tuple[pathlib.Path, dict[str, Any]]:
    tpath = run_dir / pl.STAGE_PILOT / dr.SEGMENTS_NAME
    return tpath, json.loads(tpath.read_text(encoding="utf-8"))


def _meta_path(run_dir: pathlib.Path, name: str) -> pathlib.Path:
    return _records_path(run_dir, name).with_name(dr.META_NAME)


def _rewrite_meta(
    run_dir: pathlib.Path, name: str, mutate: Callable[[dict[str, Any]], None]
) -> None:
    """meta.json を書き換え、状態表の meta の sha を合わせる."""
    path = _meta_path(run_dir, name)
    meta = json.loads(path.read_text(encoding="utf-8"))
    mutate(meta)
    data = dr.json_text(meta).encode("utf-8")
    path.write_bytes(data)
    tpath, table = _table(run_dir)
    table["segments"][name]["meta_sha256"] = _sha(data)
    tpath.write_bytes(dr.json_text(table).encode("utf-8"))


def test_meta_sha_mismatch_stops(one_run: pathlib.Path) -> None:
    name = "pilot/v3/qwen3:8b"
    path = _meta_path(one_run, name)
    # 中身は同じで bytes だけが違う (meta の欄の照合は通り、sha の照合だけが落ちる)
    path.write_bytes(
        json.dumps(json.loads(path.read_text(encoding="utf-8"))).encode("utf-8")
    )
    run = _read(one_run, ONE)
    assert run.violations == [f"{name}: meta sha differs from segments.json"]


def test_meta_fields_must_match_the_registration(one_run: pathlib.Path) -> None:
    name = "pilot/O_time/qwen3:8b"
    _rewrite_meta(one_run, name, lambda m: m.__setitem__("attempt", 2))
    assert f"{name}: meta attempt differs" in _read(one_run, ONE).violations


def test_meta_template_sha_must_be_the_sha_of_the_template(
    one_run: pathlib.Path,
) -> None:
    name = "pilot/G/qwen3:8b"
    _rewrite_meta(one_run, name, lambda m: m.__setitem__("template", "edited"))
    assert _read(one_run, ONE).violations == [
        f"{name}: meta template_sha256 is not the sha of the template"
    ]


def test_adopted_attempt_on_a_non_completed_segment_stops(
    tmp_path: pathlib.Path,
) -> None:
    write_pilot(
        tmp_path / "run", models=ONE, status={"pilot/v2/qwen3:8b": dr.S_TRANSPORT}
    )
    tpath, table = _table(tmp_path / "run")
    table["segments"]["pilot/v2/qwen3:8b"]["adopted_attempt"] = 1
    tpath.write_bytes(dr.json_text(table).encode("utf-8"))
    assert _read(tmp_path / "run", ONE).violations == [
        "pilot/v2/qwen3:8b: adopted_attempt on a non-completed segment"
    ]


def test_n_sends_out_of_range_stops(one_run: pathlib.Path) -> None:
    def five(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows[7]["n_sends"] = 1 + dr.RESENDS + 1
        return rows

    rewrite(one_run, "pilot/v2/qwen3:8b", five)
    assert any("n_sends out of range" in v for v in _read(one_run, ONE).violations)


def test_expected_ollama_version_differs_stops(one_run: pathlib.Path) -> None:
    tpath, table = _table(one_run)
    table["expected_ollama_version"] = "0.33.0"
    tpath.write_bytes(dr.json_text(table).encode("utf-8"))
    assert _read(one_run, ONE).violations == [
        "segments.json expected_ollama_version differs from models.json"
    ]


def test_invalid_meta_makes_the_model_invalid_in_that_battery(
    six_model_run: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    run = tmp_path / "run"
    shutil.copytree(six_model_run, run)
    tpath, table = _table(run)
    for m in pl.MODELS:  # G の全モデルの区切りが digest の違いで閉じた
        table["segments"][f"pilot/G/{m}"].update(
            status=dr.S_INVALID_META,
            reason=f"{m}: model_digest differs",
            adopted_attempt=None,
            records_sha256=None,
            meta_sha256=None,
        )
    tpath.write_bytes(dr.json_text(table).encode("utf-8"))
    gate = _gate(run)
    g = gate["batteries"]["G"]
    assert {g["models"][m]["status"] for m in pl.MODELS} == {pg.M_INVALID}
    assert g["entrants"] == []
    # 資格を計算したモデルが無い battery は NOT_QUALIFIED でなく not_computed
    assert g["gate"] == pg.G_NOT_COMPUTED
    # 他の battery では同じモデルが入場する (そのモデルをその battery で INVALID)
    assert "qwen3:8b" in gate["batteries"]["O_time"]["entrants"]


def test_g_masked_bottom_keeps_the_model_out(
    six_model_run: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    run = tmp_path / "run"
    shutil.copytree(six_model_run, run)
    arm = next(m for m, lv in gpg.MASKED_ARMS.items() if lv == gbat.LEVER_ARMS[0])

    def bottom(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for row in rows:
            if row["purpose"] == pl.P_MASKED and row["arm"] == arm:
                row["raw"] = BOT  # masked の 1 arm だけ ⊥
        return rows

    rewrite(run, "pilot/G/qwen3:8b", bottom)
    g = _gate(run)["batteries"]["G"]
    assert g["models"]["qwen3:8b"]["status"] == st.REASON_ENVELOPE
    assert g["models"]["qwen3:8b"]["masked_bottom_rates"][0] == 1.0


def test_worst_pair_names_the_stats_pair(six_model_run: pathlib.Path) -> None:
    run = _read(six_model_run)
    gate = _gate(six_model_run)
    for b, entry in gate["batteries"].items():
        ents = entry["entrants"]
        units = np.stack(
            [pg.pilot_units(b, run.segments[f"pilot/{b}/{m}"]) for m in ents]
        )
        a, c = st.worst_pair(units)
        assert a < c
        assert entry["worst_pair"] == [ents[a], ents[c]]


def test_worst_pair_is_written_from_the_stats_indices(
    six_model_run: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B-2: 同点の合成記録では (0, 1) と区別できない.

    stats の対を非対称な (2, 4) に差し替えて見る。
    """
    monkeypatch.setattr(st, "worst_pair", lambda _units: (2, 4))
    gate = _gate(six_model_run)
    for entry in gate["batteries"].values():
        ents = entry["entrants"]
        assert entry["worst_pair"] == [ents[2], ents[4]]


def test_budget_labels_reach_the_gate(six_model_run: pathlib.Path) -> None:
    def largest(
        spec: st.BatterySpec, units: np.ndarray, k: int
    ) -> tuple[int | None, list[st.SpikeRow]]:
        del units, k
        return st.r_candidates(spec)[-1], []

    gate = _gate(six_model_run, select_r=largest)
    labels = {b: e["gate"] for b, e in gate["batteries"].items()}
    assert labels == st.budget({b: e["R"] for b, e in gate["batteries"].items()})
    assert st.GATE_HELD_COST in labels.values()
    assert st.GATE_GO in labels.values()


def test_gate_json_writes_non_finite_floats_as_strings(
    six_model_run: pathlib.Path,
) -> None:
    gate = _gate(six_model_run, negative_all=lambda *_a, **_k: float("nan"))
    assert gate["batteries"]["v2"]["spike_negative_all"]["p"] == "nan"
    assert '"p": "nan"' in pg.gate_text(gate)


def test_segment_digest_tamper_stops(one_run: pathlib.Path) -> None:
    tpath, table = _table(one_run)
    table["segments"]["pilot/v3/qwen3:8b"]["segment_digest"] = "0" * 64
    tpath.write_bytes(dr.json_text(table).encode("utf-8"))
    assert _read(one_run, ONE).violations == [
        "pilot/v3/qwen3:8b: segment digest differs from the frozen schedule"
    ]


def test_adopted_attempt_must_be_the_last_attempt(one_run: pathlib.Path) -> None:
    tpath, table = _table(one_run)
    table["segments"]["pilot/v2/qwen3:8b"]["attempts_run"] = 2  # 採用は attempt-1
    tpath.write_bytes(dr.json_text(table).encode("utf-8"))
    assert _read(one_run, ONE).violations == [
        "pilot/v2/qwen3:8b: adopted_attempt is not the last attempt"
    ]
