"""候補 O_time (時期の評価) — null pilot の機械判定 (判定に使わない pilot、prereg §8、計測台 ADR §4.1 の spike-in の契約).

pilot (GPU、別の user 裁定) の記録から、本走を起こすか (GO と R) / 起こさないか (STOP と理由) を機械的に決める。
pilot は効果を測らない。verdict を書かない。

pilot の腕 (prereg §8.1)。どれも単位 (族, 部屋, r) に 4 呼び出し (2 arm × 2 書き方) を置き、r ∈ [PILOT_R0, PILOT_R0 + 6)、K = 1:

* ``M_AB`` / ``M_BA`` / ``M_CD`` / ``M_DC`` (masked): 本走と同じ状態の札の数字を「?」に伏せたもの。同じ書き方の 2 arm の prompt が
  同一になるので、決定的な decode なら d ≡ 0。⊥ の envelope・spike-in の基底・2 arm の出力の不一致率 (記述) に使う。
* ``P_AB`` / ``P_BA`` / ``P_CD`` / ``P_DC`` (M0 の陽性対照): 新しい日の行だけの状態 (lookup)。

判定の順 (凍結):

1. STOP (records): certification・meta・schema・構造の違反、または見取り図が R を選ばなかった。
2. not_computed: transport 失敗・欠け。
3. STOP (M0): M0 の腕が、凍結した PASS の規則 (pilot の 72 単位で E⁺ ≥ 1/α かつ 4 成分 > 0) を通らない。
   保守的な運用規則で、構成概念の確認ではない (scoping ADR §6 gate 3・DC-5)。
4. STOP (envelope): masked の arm の ⊥ 率 > 0.2、または族内の ⊥ 率差 ≥ τ/4。
5. spike-in の OC (混合の形、見取り図が選んだ R で): masked の記録を (族, 部屋, 表示の回転) の層ごとに単位で再標本化して
   本走の割付 (各層 R/3 単位) に揃え、⊥ でないセルを確率 λ で w (目標が null の C より小さければ foil) に置き換える。
   λ は記録の上で E[C] が目標に一致するよう解析的に較正し、注入の後に実現した平均で確かめる。
   P(PASS | 2τ) ≥ 0.8・P(NO_GO | 0) ≥ 0.8・P(PASS | τ) と P(NO_GO | τ) ≤ 二項の閾値・較正 をすべて満たせば GO、
   満たさなければ STOP (power、door-close)。OC の ⊥ gate は本走と同じ上限 (masked の最大 + 0.05)。
   OC は「この null 記録に条件付けた値」で、母集団への保証ではない。size は定理 (scorer) で守られ、pilot に依らない。

出力は、本走の判定が読む値 (GO と R・masked の最大 ⊥ 率・観測環境) と、入力の sha256 を記録する。

実行::

    uv run python scripts/o_time_probe_pilot_gate.py --records <records.jsonl> --meta <meta.json> \\
        --cert <cert.json> --sketch <sketch.json> --out <gate.json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import o_time_probe_battery as bat  # noqa: E402
from scripts import o_time_probe_scorer as sc  # noqa: E402

if TYPE_CHECKING:
    from collections.abc import Sequence

MASKED_ARMS: Final[dict[str, str]] = {f"M_{a}": a for a in bat.LEVER_ARMS}
M0_ARMS: Final[dict[str, str]] = {f"P_{a}": a for a in bat.LEVER_ARMS}
PILOT_K: Final[int] = 1
N_RESAMPLE: Final[int] = 2_000
OC_SEED: Final[int] = 20261008
CALIBRATION_TOL: Final[float] = 0.01
MC_FWER: Final[float] = 0.01
POWER_TARGET: Final[float] = 0.8
N_OC_SIZE_CHECKS: Final[int] = 2  # P(PASS | τ) と P(NO_GO | τ)

DECISION_GO: Final[str] = "GO"
DECISION_STOP: Final[str] = "STOP"
STATUS_NOT_COMPUTED: Final[str] = "not_computed"


# ---------------------------------------------------------------- 計画


def kind_of(arm: str) -> tuple[str, str]:
    """pilot の腕名 → (mode, lever arm)。mode = masked / m0."""
    if arm in MASKED_ARMS:
        return "masked", MASKED_ARMS[arm]
    return "m0", M0_ARMS[arm]


def expected(arm: str, enc: str, r: int, probe_id: str, k: int) -> tuple[int, str]:
    """(seed, prompt sha256) の凍結値."""
    mode, lever = kind_of(arm)
    unit = bat.Unit(bat.ARM_FAMILY[lever], sc.room_index(probe_id), r)
    msgs = bat.render_messages(lever, enc, unit, mode)
    ns = f"{mode}_fam{unit.family}"
    return bat.sample_seed(ns, r, unit.room, k), sc.messages_sha256(msgs)


def pilot_grid() -> set[tuple[str, str, int, str, int]]:
    out = set()
    for arms in (MASKED_ARMS, M0_ARMS):
        for name, lever in arms.items():
            fi = bat.ARM_FAMILY[lever]
            out |= {
                (name, enc, u.replicate, sc.probe_id(u.room), k)
                for u in bat.pilot_units()
                if u.family == fi
                for enc in bat.ENCODINGS
                for k in range(PILOT_K)
            }
    return out


def structure_violations(samples: Sequence[sc.Sample]) -> list[str]:
    out: list[str] = []
    keys = [(s.arm, s.encoding, s.replicate, s.probe_id, s.k) for s in samples]
    if len(set(keys)) != len(keys):
        out.append("duplicate (arm, encoding, replicate, probe, k)")
    grid = pilot_grid()
    if not set(keys) <= grid:
        out.append("record outside the pilot grid")
    idx = [s.call_index for s in samples]
    if len(set(idx)) != len(idx) or any(i < 0 for i in idx):
        out.append("call_index is not unique and non-negative")
    for s, key in zip(samples, keys, strict=True):
        if key not in grid:
            continue
        seed, sha = expected(s.arm, s.encoding, s.replicate, s.probe_id, s.k)
        if s.seed != seed:
            out.append("seed differs from the pilot schedule")
        if s.prompt_sha256 != sha:
            out.append("prompt differs from the pilot renderer")
        if s.raw is not None and sc.parse_choice(s.raw) != s.parsed:
            out.append("recorded parse differs from re-parse")
    return sorted(set(out))


# ---------------------------------------------------------------- gate


def cell_scores(
    samples: Sequence[sc.Sample], mode: str
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """mode の腕の記録 → (x, nb, other)。形は (2 族, 6 部屋, PILOT_R, 2 書き方, 2 arm).

    x = セル得点 (+1/−1/0)、nb = ⊥ でない指標、other = 記録に無い行動を選んだ指標。
    """
    shape = (len(bat.FAMILIES), bat.N_ROOMS, bat.PILOT_R, 2, 2)
    x = np.zeros(shape)
    nb = np.zeros(shape)
    other = np.zeros(shape)
    for s in samples:
        if s.arm not in MASKED_ARMS and s.arm not in M0_ARMS:
            continue
        m, lever = kind_of(s.arm)
        if m != mode:
            continue
        fi = bat.ARM_FAMILY[lever]
        ai = bat.FAMILIES[fi].index(lever)
        ei = bat.ENCODINGS.index(s.encoding)
        i = sc.room_index(s.probe_id)
        cat = sc.category(s.parsed, lever, i)
        idx = (fi, i, s.replicate - bat.PILOT_R0, ei, ai)
        x[idx] = (cat == "w") - (cat == "foil")
        nb[idx] = cat != "bot"
        other[idx] = cat == "other"
    return x, nb, other


def bottom_rates(nb: np.ndarray) -> np.ndarray:
    """(4,) LEVER_ARMS の順の ⊥ 率 (書き方と単位をまとめる)."""
    return np.array(
        [
            1.0 - nb[fi, ..., ai].mean()
            for fi in range(len(bat.FAMILIES))
            for ai in range(2)
        ]
    )


def components(x: np.ndarray) -> np.ndarray:
    """(…, 4) 向き × 書き方の s の平均 (scorer の COMPONENTS の順)。x は (…, F, 部屋, R, 2 書き方, 2 arm)."""
    return np.stack(
        [x[..., e, a].mean(axis=(-3, -2, -1)) for a in range(2) for e in range(2)],
        axis=-1,
    )


def m0_check(x: np.ndarray) -> dict[str, Any]:
    """M0 の陽性対照: 凍結した PASS の規則 (E⁺ ≥ 1/α かつ 4 成分 > 0) を pilot の単位で通るか."""
    d = x.mean(axis=(-2, -1)).reshape(-1)
    comps = components(x)
    le_plus, le_minus, _ = sc.e_values(d)
    verdict = str(sc.decide(le_plus, le_minus, comps))
    return {
        "C": float(d.mean()),
        "n_units": int(d.size),
        "log_e_plus": float(le_plus),
        "components": [float(c) for c in comps],
        "verdict": verdict,
        "passed": verdict == sc.VERDICT_PASS,
    }


def discordance(samples: Sequence[sc.Sample]) -> float:
    """masked の同じ書き方の 2 arm (同じ prompt・seed) の parse 結果が違う率 (記述。決定性の理想化の監査)."""
    by: dict[tuple[int, int, int, str], list[str | None]] = {}
    for s in samples:
        if s.arm not in MASKED_ARMS:
            continue
        lever = MASKED_ARMS[s.arm]
        key = (
            bat.ARM_FAMILY[lever],
            sc.room_index(s.probe_id),
            s.replicate,
            s.encoding,
        )
        by.setdefault(key, []).append(s.parsed)
    pairs = [v for v in by.values() if len(v) == 2]
    if not pairs:
        return 0.0
    return sum(a != b for a, b in pairs) / len(pairs)


def injection(x: np.ndarray, nb: np.ndarray, target: float) -> tuple[float, int]:
    """(λ, 向き)。向き +1 = w を注入、−1 = foil を注入。記録の上で E[C] = target になる λ."""
    c_null = float(x.mean())
    live = float(nb.mean())
    if target >= c_null:
        lam = (target - c_null) / (live - c_null) if live > c_null else 1.0
        return min(1.0, max(0.0, lam)), 1
    lam = (c_null - target) / (live + c_null)
    return min(1.0, max(0.0, lam)), -1


def strata_picks(r_count: int, n_resample: int, rng: np.random.Generator) -> np.ndarray:
    """(B, F, 部屋, R) の pilot の replicate 番号 (0..PILOT_R-1)。本走の割付を保つ層別の復元抽出.

    本走の単位 (f, i, r) の表示の回転は (r + i) mod 3。その単位には、同じ (f, i) で回転が等しい pilot の単位
    ((r' + i) mod 3 が等しい r') だけを引く。
    """
    n_f, n_i = len(bat.FAMILIES), bat.N_ROOMS
    pick = np.zeros((n_resample, n_f, n_i, r_count), dtype=int)
    for i in range(n_i):
        for r in range(r_count):
            shift = (r + i) % bat.N_POSITIONS
            pool = [
                rp
                for rp in range(bat.PILOT_R)
                if (bat.PILOT_R0 + rp + i) % bat.N_POSITIONS == shift
            ]
            pick[:, :, i, r] = rng.choice(pool, size=(n_resample, n_f))
    return pick


def spike_in_oc(
    x: np.ndarray,
    nb: np.ndarray,
    r_count: int,
    target: float,
    n_resample: int,
    seed: int,
) -> dict[str, float]:
    """層別に単位を R 個再標本化し、注入して判定式を通す。verdict の率と実現した平均."""
    rng = np.random.default_rng([seed, r_count, int(round((target + 2) * 10_000))])
    lam, sign = injection(x, nb, target)
    # 本走と同じ ⊥ の上限 (masked の最大 + 0.05)
    bot_max = sc.envelope_bottom_max(float(bottom_rates(nb).max()))
    n_f, n_i = x.shape[:2]
    pick = strata_picks(r_count, n_resample, rng)
    fi = np.arange(n_f)[None, :, None, None]
    ii = np.arange(n_i)[None, None, :, None]
    xs = x[fi, ii, pick]  # (B, F, 部屋, R, 2 書き方, 2 arm)
    nbs = nb[fi, ii, pick]
    hit = (rng.random(xs.shape) < lam) & (nbs > 0)
    xs = np.where(hit, float(sign), xs)
    d = xs.mean(axis=(-2, -1)).reshape(n_resample, -1)
    comps = components(xs)
    botr = np.stack(
        [
            1.0 - nbs[:, f, ..., a].reshape(n_resample, -1).mean(axis=1)
            for f in range(n_f)
            for a in range(2)
        ],
        axis=1,
    )
    le_plus, le_minus, _ = sc.e_values(d)
    verdict = sc.decide(le_plus, le_minus, comps)
    verdict = np.where(
        sc.bottom_gate_ok(botr, bot_max), verdict, sc.VERDICT_INVALID_BATTERY
    )
    return {
        "lambda": lam,
        "direction": sign,
        "pass": float(np.mean(verdict == sc.VERDICT_PASS)),
        "no_go": float(np.mean(verdict == sc.VERDICT_ABSENT)),
        "realized_C": float(d.mean()),
    }


def _binom_upper_tail(x: int, n: int, p: float) -> float:
    if x <= 0:
        return 1.0
    logs = [
        math.lgamma(n + 1)
        - math.lgamma(k + 1)
        - math.lgamma(n - k + 1)
        + k * math.log(p)
        + (n - k) * math.log1p(-p)
        for k in range(x, n + 1)
    ]
    top = max(logs)
    return math.exp(top) * sum(math.exp(v - top) for v in logs)


def size_rate_cap(n_checks: int, n_sims: int = N_RESAMPLE) -> float:
    """size の採否の上限 (率) = x / N。合格は X ≤ x、棄却は X ≥ x + 1 (X = 棄却の数).

    x は P(X > x) ≤ MC_FWER / n_checks を満たす最小の整数 (X ~ Binomial(N, α))。
    """
    level = MC_FWER / n_checks
    x = int(sc.ALPHA * n_sims)
    while _binom_upper_tail(x + 1, n_sims, sc.ALPHA) > level:
        x += 1
    return x / n_sims


def oc_ok(
    at_plant: dict[str, float],
    at_zero: dict[str, float],
    at_tau: dict[str, float],
    cap: float,
) -> dict[str, bool]:
    """OC の 4 条件と較正。どれか 1 つでも偽なら不合格."""
    calibrated = all(
        abs(o["realized_C"] - t) < CALIBRATION_TOL
        for o, t in ((at_plant, sc.DELTA_PLANT), (at_zero, 0.0), (at_tau, sc.TAU))
    )
    return {
        "calibrated": calibrated,
        "power_pass": at_plant["pass"] >= POWER_TARGET,
        "power_no_go": at_zero["no_go"] >= POWER_TARGET,
        "size_pass": at_tau["pass"] <= cap,
        "size_no_go": at_tau["no_go"] <= cap,
    }


def oc_for_r(x: np.ndarray, nb: np.ndarray, r_count: int) -> dict[str, Any]:
    at_plant = spike_in_oc(x, nb, r_count, sc.DELTA_PLANT, N_RESAMPLE, OC_SEED)
    at_zero = spike_in_oc(x, nb, r_count, 0.0, N_RESAMPLE, OC_SEED + 1)
    at_tau = spike_in_oc(x, nb, r_count, sc.TAU, N_RESAMPLE, OC_SEED + 2)
    cap = size_rate_cap(N_OC_SIZE_CHECKS)
    checks = oc_ok(at_plant, at_zero, at_tau, cap)
    return {
        "R": r_count,
        "at_plant": at_plant,
        "at_zero": at_zero,
        "at_tau": at_tau,
        "size_cap": cap,
        "checks": checks,
        "ok": all(checks.values()),
    }


def decide_pilot(
    samples: Sequence[sc.Sample],
    meta: object,
    *,
    certified: bool,
    selected_r: int | None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "status": "computed",
        "decision": None,
        "R": None,
        "reasons": [],
    }
    invalid: list[str] = []
    if not certified:
        invalid.append("certification missing, stale, or not all KILLED")
    invalid += sc.meta_violations(meta)
    if selected_r is None:
        invalid.append("the sketch selected no R (door-close before the pilot)")
    invalid += structure_violations(samples)
    if invalid:
        out.update(decision=DECISION_STOP, reasons=["records", *invalid])
        return out
    out["observed"] = dict(meta["observed"])  # type: ignore[index]
    if any(s.raw is None for s in samples) or len(samples) != len(pilot_grid()):
        out.update(
            status=STATUS_NOT_COMPUTED, reasons=["transport failure or missing rows"]
        )
        return out
    xm, nbm, otherm = cell_scores(samples, "masked")
    x0, _, other0 = cell_scores(samples, "m0")
    out["describe"] = {
        "masked_discordance": discordance(samples),
        "masked_null_C": float(xm.mean()),
        "masked_other_rate": float(otherm.mean()),
        "m0_other_rate": float(other0.mean()),
    }
    m0 = m0_check(x0)
    out["m0"] = m0
    if not m0["passed"]:
        out.update(decision=DECISION_STOP, reasons=["m0"])
        return out
    bot = bottom_rates(nbm)
    out["masked_bottom_rates"] = dict(zip(bat.LEVER_ARMS, map(float, bot), strict=True))
    out["masked_max_bottom"] = float(bot.max())
    out["null_C"] = float(xm.mean())
    if not bool(sc.bottom_gate_ok(bot)):
        out.update(decision=DECISION_STOP, reasons=["envelope"])
        return out
    assert selected_r is not None
    oc = oc_for_r(xm, nbm, selected_r)
    if oc["ok"]:
        out.update(
            decision=DECISION_GO, R=selected_r, reasons=["spike-in OC passed"], oc=oc
        )
        return out
    out.update(decision=DECISION_STOP, reasons=["power"], oc=oc)
    return out


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", type=Path, required=True)
    ap.add_argument("--meta", type=Path, required=True)
    ap.add_argument("--cert", type=Path, required=True)
    ap.add_argument("--sketch", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    inputs = {
        name: _sha256(path) if path.is_file() else None
        for name, path in (
            ("records", args.records),
            ("meta", args.meta),
            ("cert", args.cert),
            ("sketch", args.sketch),
        )
    }
    result: dict[str, Any]
    try:
        samples = sc.load_records(args.records.read_text(encoding="utf-8").split("\n"))
        meta = json.loads(args.meta.read_text(encoding="utf-8"))
        sketch = json.loads(args.sketch.read_text(encoding="utf-8"))
    except (sc.RecordError, json.JSONDecodeError, OSError) as exc:
        result = {
            "status": "computed",
            "decision": DECISION_STOP,
            "reasons": ["records", f"record_schema: {exc}"],
        }
    else:
        selection = sketch.get("selection", {}) if isinstance(sketch, dict) else {}
        selected = selection.get("selected_R") if isinstance(selection, dict) else None
        result = decide_pilot(
            samples,
            meta,
            certified=sc.load_certification(args.cert),
            selected_r=selected if type(selected) is int else None,
        )
    result["inputs_sha256"] = inputs
    sc.write_json(args.out, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
