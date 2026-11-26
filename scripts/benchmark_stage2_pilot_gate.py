"""判別性 gate 段 2 — pilot gate (prereg §G.2、Codex r1 H4・H5).

規則の SSOT は ``experiments/20261126-benchmark-stage2-discriminability/prereg.md`` (第 1 段 PILOT-FROZEN)。
判定は ``benchmark_stage2_stats`` の関数だけで行う。記録は ``benchmark_stage2_records`` (plan に頼らない読み手) で読む。

§G.2 の順:

1. **STOP (records)**: 読み手の違反 (状態表・meta・schema・構造)。gate.json は ``status = STOP_RECORDS`` で、以後を計算しない。
2. **not_computed**: completed でない区切り (通信・時間切れ・未着手)・欠け。M0 の区切りが無いモデルは
   lookup が計算できない (``lookup_not_computed``) ので、全 battery で not_computed (M0 の**不合格**とは別、H4)。
   digest・template の違い (``invalid_meta``) はそのモデルを INVALID、版の違いは run の全モデルを INVALID (§A.1)。
3. **資格** (§A、``stats.qualify``): lookup = O_time の M0 の ``m0_check(...)["passed"]`` をモデルごとに 1 回。
   parse = lever arm の ⊥ の数 (v2 は C0 を含む 5 本)。G の KNOW = 36 × 3 が揃い ``knowledge_failures`` が空。
   v3 の L arm = 4 本。masked = G ``masked_bottom_rates`` / O_time ``bottom_rates`` を凍結の ``bottom_gate_ok`` へ。
   入場 < 3 の battery は NOT_QUALIFIED。K = ``stats.n_tests``、ΣM = 入場 ≥ 3 の battery の入場数の和。
4. **R の選定** (``stats.select_r``): 入場モデルの pilot の lever arm の単位の値 (``benchmark_stage2_units``、§D の単位の順)。
   記述に ``worst_pair``・``SpikeRow.p_pair_equiv_at_zero``・``spike_negative_all`` (選んだ R、STOP (power) なら候補の最大)。
5. **予算** (``stats.budget``): GO / HELD_COST。

出力 ``results/pilot/gate.json`` (H5): battery 別の入場モデル ID・K・ΣM・R・gate・arm 別の整数の ⊥ 数・
envelope の分子と分母・入力の sha。本走の driver と scorer はこの file に照合する。
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import pathlib
import sys
from typing import TYPE_CHECKING, Any, Final

import numpy as np
from scripts import benchmark_stage2_records as rd
from scripts import benchmark_stage2_stats as st
from scripts import benchmark_stage2_units as un
from scripts import generalization_probe_battery as gbat
from scripts import generalization_probe_pilot_gate as gpg
from scripts import generalization_probe_scorer as gsc
from scripts import o_time_probe_battery as obat
from scripts import o_time_probe_pilot_gate as opg
from scripts import o_time_probe_scorer as osc
from scripts import skill_experience_battery as v3bat

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

_REPO_ROOT: Final[pathlib.Path] = pathlib.Path(__file__).resolve().parent.parent
EXP: Final[pathlib.Path] = (
    _REPO_ROOT / "experiments" / "20261126-benchmark-stage2-discriminability"
)
MODELS_JSON: Final[pathlib.Path] = EXP / "results" / "models.json"
GATE_JSON: Final[pathlib.Path] = EXP / "results" / "pilot" / "gate.json"

SCHEMA: Final[str] = "benchmark_stage2_pilot_gate/1"
STATUS_OK: Final[str] = "OK"
STATUS_STOP_RECORDS: Final[str] = "STOP_RECORDS"

# モデル × battery の結果 (qualify の理由に加えて)
M_ENTERED: Final[str] = st.ENTERED
M_NOT_COMPUTED: Final[str] = "not_computed"
M_LOOKUP_NOT_COMPUTED: Final[str] = "lookup_not_computed"  # M0 の欠測 (不合格ではない)
M_INVALID: Final[str] = "INVALID"
# battery の gate (stats の 3 つに加えて)
G_NOT_QUALIFIED: Final[str] = st.VERDICT_NOT_QUALIFIED
G_NOT_COMPUTED: Final[str] = st.VERDICT_NOT_COMPUTED
GATES: Final[frozenset[str]] = frozenset(
    {st.GATE_GO, st.GATE_STOP_POWER, st.GATE_HELD_COST, G_NOT_QUALIFIED, G_NOT_COMPUTED}
)

# 凍結の集計の添字 (r − PILOT_R0) に合わせる付け替え (集計用の写しの添字だけ、H3)
G_MASKED_SHIFT: Final[int] = gbat.PILOT_R0 - rd.PILOT_AUX_R["G"].start
O_AUX_SHIFT: Final[int] = obat.PILOT_R0 - rd.PILOT_AUX_R["O_time"].start
N_KNOW: Final[int] = len(gbat.all_keys()) * gbat.KNOW_K  # 36 × 3


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _purpose(rows: Sequence[rd.Row], purpose: str) -> list[rd.Row]:
    return [r for r in rows if r.purpose == purpose]


# ------------------------------------------------------------ 資格の材料 (凍結の関数への写し、H4)


def lookup(run: rd.RunRead, model: str) -> tuple[bool | None, dict[str, Any]]:
    """O_time の M0 の PASS の規則。区切りが無ければ (None, 理由)。passed は真偽の値そのもの (辞書を真偽にしない)."""
    sr = run.segments[rd.seg_name(rd.STAGE_PILOT, "O_time", model)]
    if sr.status != rd.R_OK:
        return None, {"status": M_LOOKUP_NOT_COMPUTED, "reason": f"O_time: {sr.status}"}
    rows = _purpose(sr.rows, rd.P_M0)
    want = 2 * len(obat.LEVER_ARMS) * obat.N_ROOMS * len(rd.PILOT_AUX_R["O_time"])
    if len(rows) != want:
        return None, {"status": M_LOOKUP_NOT_COMPUTED, "reason": "M0 rows incomplete"}
    x = opg.cell_scores(rd.o_samples(rows, O_AUX_SHIFT), "m0")[0]
    res = opg.m0_check(x)
    passed = res["passed"] is True
    return passed, {"status": "passed" if passed else "failed", **res}


def model_pilot(
    battery: str, sr: rd.SegmentRead, lookup_ok: bool
) -> tuple[st.ModelPilot, dict[str, Any]]:
    rows = sr.rows
    rs = list(rd.PILOT_LEVER_R[battery])
    choices = rd.unit_choices(battery, rows)
    counts, n = un.bot_counts(battery, choices, rs)
    detail: dict[str, Any] = {"bot_counts": list(counts), "bot_n": n}
    know_ok = control = envelope_ok = None
    if battery == "v3":
        control, n_c = un.bot_counts("v3", choices, rs, arms=v3bat.CONTROL_ARMS)
        if len(control) != len(v3bat.CONTROL_ARMS) or n_c != n:
            msg = "v3 control arms differ from the registered 4"
            raise ValueError(msg)
        detail["control_counts"] = list(control)
    if battery == "G":
        know = _purpose(rows, rd.P_KNOW)
        failures = gpg.knowledge_failures(rd.g_samples(know))
        know_ok = len(know) == N_KNOW and not failures
        detail["know_failures"] = failures
        masked = _purpose(rows, rd.P_MASKED)
        _, nb = gpg.cell_scores(rd.g_samples(masked, G_MASKED_SHIFT))
        rates = gpg.masked_bottom_rates(nb)
        envelope_ok = bool(gsc.bottom_gate_ok(rates))
        detail["masked_bottom_rates"] = [float(x) for x in rates]
        detail["masked_n"] = len(masked)
    if battery == "O_time":
        masked = _purpose(rows, rd.P_MASKED)
        _, nb, _ = opg.cell_scores(rd.o_samples(masked, O_AUX_SHIFT), "masked")
        rates = opg.bottom_rates(nb)
        envelope_ok = bool(osc.bottom_gate_ok(rates))
        detail["masked_bottom_rates"] = [float(x) for x in rates]
        detail["masked_n"] = len(masked)
    mp = st.ModelPilot(
        lookup_ok=lookup_ok,
        bot_counts=tuple(counts),
        bot_n=n,
        know_ok=know_ok,
        control_counts=None if control is None else tuple(control),
        envelope_ok=envelope_ok,
    )
    return mp, detail


def pilot_units(battery: str, sr: rd.SegmentRead) -> np.ndarray:
    """Pilot の lever arm の単位の値 (§D の単位、``stats.strata`` の順)."""
    choices = rd.unit_choices(battery, sr.rows)
    counts = un.unit_counts(battery, choices, list(rd.PILOT_LEVER_R[battery]))
    return un.unit_values(counts)


# ------------------------------------------------------------ gate


def _jsonable(x: object) -> object:
    if isinstance(x, float) and not math.isfinite(x):
        return str(x)
    if isinstance(x, dict):
        return {k: _jsonable(v) for k, v in x.items()}
    if isinstance(x, list | tuple):
        return [_jsonable(v) for v in x]
    return x


def spike_row_json(row: st.SpikeRow) -> dict[str, Any]:
    return _jsonable(dataclasses.asdict(row))  # type: ignore[return-value]


def stop_records(run: rd.RunRead, inputs: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "status": STATUS_STOP_RECORDS,
        "violations": list(run.violations),
        "inputs": dict(inputs),
    }


def compute_gate(
    run: rd.RunRead,
    *,
    models_json_sha256: str,
    select_r: Callable[
        [st.BatterySpec, np.ndarray, int], tuple[int | None, list[st.SpikeRow]]
    ] = st.select_r,
    negative_all: Callable[..., float] = st.spike_negative_all,
) -> dict[str, Any]:
    """§G.2 を順に当てた gate.json の中身."""
    inputs = {"models_json_sha256": models_json_sha256, **run.inputs}
    if run.stop:
        return stop_records(run, inputs)
    observed = {}
    for sr in run.segments.values():
        if sr.status == rd.R_OK and sr.meta is not None and sr.stage == rd.STAGE_PILOT:
            observed.setdefault(
                sr.model,
                {
                    k: sr.meta.get(k)
                    for k in ("ollama_version", "model_digest", "template_sha256")
                },
            )
    looks = {m: lookup(run, m) for m in rd.MODELS}
    batteries: dict[str, Any] = {}
    n_entered: dict[str, int] = {}
    for b in st.BATTERIES:
        models: dict[str, Any] = {}
        for m in rd.MODELS:
            sr = run.segments[rd.seg_name(rd.STAGE_PILOT, b, m)]
            lk_ok, lk = looks[m]
            if sr.status in (rd.R_INVALID_META, rd.R_INVALID_VERSION):
                models[m] = {"status": M_INVALID, "reason": f"{sr.status}: {sr.reason}"}
            elif sr.status != rd.R_OK:
                models[m] = {"status": M_NOT_COMPUTED, "reason": sr.reason or sr.status}
            elif lk_ok is None:
                models[m] = {"status": M_LOOKUP_NOT_COMPUTED, "reason": lk["reason"]}
            else:
                mp, detail = model_pilot(b, sr, lk_ok)
                status = st.qualify(b, mp)
                models[m] = {"status": status, **detail}
                if status == M_ENTERED:
                    env = st.parse_rule(mp.bot_counts, mp.bot_n)[1]
                    models[m]["envelope"] = {
                        "numerator": env.numerator,
                        "denominator": env.denominator,
                    }
        entrants = [m for m in rd.MODELS if models[m]["status"] == M_ENTERED]
        n_entered[b] = len(entrants)
        computed = any(
            models[m]["status"] not in (M_NOT_COMPUTED, M_INVALID) for m in rd.MODELS
        )
        batteries[b] = {
            "models": models,
            "entrants": entrants,
            "n_entered": len(entrants),
            "gate": None
            if len(entrants) >= st.MIN_ENTRANTS
            else G_NOT_QUALIFIED
            if computed
            else G_NOT_COMPUTED,
            "R": None,
        }
    k_tests = st.n_tests(n_entered)
    sum_m = sum(n for n in n_entered.values() if n >= st.MIN_ENTRANTS)
    r_sel: dict[str, int] = {}
    for b in st.BATTERIES:
        entry = batteries[b]
        if entry["gate"] is not None:
            continue
        spec = st.SPECS[b]
        units = np.stack(
            [
                pilot_units(b, run.segments[rd.seg_name(rd.STAGE_PILOT, b, m)])
                for m in entry["entrants"]
            ]
        )
        a, c = st.worst_pair(units)
        r_main, rows = select_r(spec, units, k_tests)
        r_desc = r_main if r_main is not None else st.r_candidates(spec)[-1]
        entry.update(
            {
                "pilot_C": {
                    m: float(u.mean())
                    for m, u in zip(entry["entrants"], units, strict=True)
                },
                "worst_pair": [entry["entrants"][a], entry["entrants"][c]],
                "spike_rows": [spike_row_json(row) for row in rows],
                "spike_negative_all": {
                    "R": r_desc,
                    "p": negative_all(
                        spec,
                        units,
                        k_tests,
                        r_desc,
                        np.random.default_rng(st.SPIKE_SEED),
                    ),
                },
            }
        )
        if r_main is None:
            entry["gate"] = st.GATE_STOP_POWER
        else:
            entry["R"] = r_main
            r_sel[b] = r_main
    for b, label in st.budget(r_sel).items():
        batteries[b]["gate"] = label
        batteries[b]["cost_8b_s"] = str(r_sel[b] * st.SPECS[b].sec_per_rep())
    replay = {
        n: {"status": sr.status, "reason": sr.reason, "n_rows": len(sr.rows)}
        for n, sr in run.segments.items()
        if sr.stage == rd.STAGE_REPLAY
    }
    # 非有限の float は gate 全体で文字列にする (DD-7。pilot_C・spike_negative_all の p も含む)
    return _jsonable(  # type: ignore[return-value]
        {
            "schema": SCHEMA,
            "status": STATUS_OK,
            "violations": [],
            "K": k_tests,
            "sum_M": sum_m,
            "lookup": {m: looks[m][1] for m in rd.MODELS},
            "batteries": batteries,
            "observed": observed,
            "replay": replay,
            "inputs": inputs,
        }
    )


def gate_text(gate: Mapping[str, Any]) -> str:
    return (
        json.dumps(gate, indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False)
        + "\n"
    )


def run_gate(
    run_dir: pathlib.Path,
    out: pathlib.Path,
    models_json: pathlib.Path = MODELS_JSON,
    **kwargs: Any,
) -> dict[str, Any]:
    reference, ref_sha = rd.load_reference(models_json)
    run = rd.read_run(run_dir, rd.STAGE_PILOT, reference)
    acc = run_dir / rd.STAGE_PILOT / "accounting.json"
    if acc.exists():
        run.inputs["accounting_json_sha256"] = _sha(acc.read_bytes())
    gate = compute_gate(run, models_json_sha256=ref_sha, **kwargs)
    if out.exists():
        msg = f"refusing to overwrite {out}"
        raise FileExistsError(msg)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(gate_text(gate).encode("utf-8"))
    return gate


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-dir", type=pathlib.Path, required=True)
    ap.add_argument("--out", type=pathlib.Path, default=GATE_JSON)
    ap.add_argument("--models-json", type=pathlib.Path, default=MODELS_JSON)
    args = ap.parse_args(argv)
    gate = run_gate(args.run_dir, args.out, args.models_json)
    if gate["status"] != STATUS_OK:
        print(
            f"[pilot-gate] {gate['status']}: {len(gate['violations'])} violations",
            file=sys.stderr,
        )  # noqa: T201
        return 3
    print(  # noqa: T201
        "[pilot-gate] K={} ΣM={} ".format(gate["K"], gate["sum_M"])
        + ", ".join(
            f"{b}={e['gate']}(R={e['R']})" for b, e in gate["batteries"].items()
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
