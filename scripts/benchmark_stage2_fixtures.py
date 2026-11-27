"""判別性 gate 段 2 — 登録した方策 (fixture) の C を、段 2 の割付・pilot の gate が選んだ R の上で再計算する.

規則の SSOT は ``experiments/20261126-benchmark-stage2-discriminability/prereg.md`` §I.3・§J (第 1 段 PILOT-FROZEN)。

* 方策がすべての呼び出しで決定的に選ぶ label を、本走の scorer と同じ単位・採点
  (``benchmark_stage2_units`` の ``lever_cells``・``unit_counts``・``unit_values``) で C にする。
* 方策の出典 (decisions DD-10 に対応表):
  - v2: ``tests/test_skill_lever/test_scorer.py`` の方策を移植し、v2 prereg §2 の「label の事前傾向」を
    ``label_prior[asc|desc]`` として足した (test に原本が無い)。``uniform_null`` は nuisance class ではないが、
    test の fixture なので入れる (併記が増える側)。
  - v3: ``tests/test_skill_experience/test_nuisance.py`` の方策を移植した。
  - G・O_time: 凍結の ``generalization_probe_fixtures`` / ``o_time_probe_fixtures`` の登録方策と陽性対照をそのまま使う。
* 陽性対照を除く方策の対で |ΔC| > Δ_min となるものを列挙する。scorer はそれを (1) で名指した対に常に併記する (§J)。
* gate が R を選んでいない battery (STOP_POWER など) は ``not_selected`` で、計算しない。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from collections import Counter
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING, Any, Final

import numpy as np
from scripts import benchmark_stage2_stats as st
from scripts import benchmark_stage2_units as un
from scripts import generalization_probe_battery as gbat
from scripts import generalization_probe_fixtures as gfx
from scripts import o_time_probe_battery as obat
from scripts import o_time_probe_fixtures as ofx
from scripts import o_time_probe_scorer as osc
from scripts import skill_experience_battery as v3bat
from scripts import skill_lever_battery as v2bat
from scripts.stage_b_battery import (
    ACTIONS as V2_ACTIONS,
)  # v2 の語彙 (skill_lever_battery が写す)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

_REPO_ROOT: Final[pathlib.Path] = pathlib.Path(__file__).resolve().parent.parent
EXP: Final[pathlib.Path] = (
    _REPO_ROOT / "experiments" / "20261126-benchmark-stage2-discriminability"
)
GATE_JSON: Final[pathlib.Path] = EXP / "results" / "pilot" / "gate.json"
OUT_JSON: Final[pathlib.Path] = EXP / "results" / "fixture_diffs_main.json"
SCHEMA: Final[str] = "benchmark_stage2_fixture_diffs_main/1"
ROUND: Final[int] = 12
FROZEN_SOURCES: Final[dict[str, pathlib.Path]] = {
    "G": _REPO_ROOT / "scripts" / "generalization_probe_fixtures.py",
    "O_time": _REPO_ROOT / "scripts" / "o_time_probe_fixtures.py",
}
NOT_SELECTED: Final[str] = "not_selected"

# 方策: 単位の 1 セルの key (benchmark_stage2_units の形) → 選んだ label (None = ⊥)
CellPolicy = "Callable[[tuple[Any, ...]], str | None]"


@dataclass(frozen=True)
class Policy:
    name: str  # 細かい方策の名
    registered: str  # prereg §I.3 の登録名 (G・O_time は凍結の族)
    positive_control: bool
    choose: Callable[[tuple[Any, ...]], str | None]


# ------------------------------------------------------------ v2 (tests/test_skill_lever/test_scorer.py の移植)

V2Fn = "Callable[[str, int, v2bat.LeverProbe, int], str]"
_V2_PROBES: Final[dict[str, v2bat.LeverProbe]] = {
    p.probe_id: p for p in v2bat.lever_probes()
}


def _opts(r: int, p: v2bat.LeverProbe) -> tuple[str, ...]:
    return tuple(v2bat.layout(r).option_order[p.probe_id])


def v2_lookup(arm: str, r: int, p: v2bat.LeverProbe, _k: int) -> str:
    """規則どおり (原本 ``lookup``。C0 は Ω_q 先頭)."""
    if arm == v2bat.ARM_C0:
        return _opts(r, p)[0]
    return p.pointed[arm]


def v2_priming(arm: str, r: int, p: v2bat.LeverProbe, k: int) -> str:
    """状態に出た label を一様に選ぶだけ (原本 ``priming_only``)."""
    if arm == v2bat.ARM_C0:
        return p.omega[k % 4]
    labels = sorted({x for _, x in v2bat.state_entries(arm, v2bat.layout(r))})
    return labels[k % len(labels)]


def v2_uniform_null(_arm: str, r: int, p: v2bat.LeverProbe, k: int) -> str:
    """原本 ``uniform_null``."""
    return _opts(r, p)[(k + r) % 4]


def v2_recency(arm: str, r: int, p: v2bat.LeverProbe, k: int) -> str:
    """状態の最後のエントリの label (原本 ``test_recency_only_is_not_pass`` の方策)."""
    if arm == v2bat.ARM_C0:
        return p.omega[k % 4]
    return v2bat.state_entries(arm, v2bat.layout(r))[-1][1]


def v2_position(_arm: str, r: int, p: v2bat.LeverProbe, _k: int) -> str:
    """常に表示の先頭 (原本 ``test_position_only_is_not_pass`` の方策)."""
    return _opts(r, p)[0]


def v2_label_prior(order: str) -> Callable[[str, int, v2bat.LeverProbe, int], str]:
    """Label そのものへの固定の事前傾向: 語彙の固定の順 (昇順 / 降順) で Ω_q の最上位 (v2 prereg §2、DD-10)."""
    rank = sorted(V2_ACTIONS, reverse=order == "desc")

    def policy(_arm: str, r: int, p: v2bat.LeverProbe, _k: int) -> str:
        opts = _opts(r, p)
        return next(a for a in rank if a in opts)

    return policy


V2_POLICIES: Final[dict[str, tuple[str, bool, Callable[..., str]]]] = {
    "priming": ("priming", False, v2_priming),
    "label_prior[asc]": ("label_prior", False, v2_label_prior("asc")),
    "label_prior[desc]": ("label_prior", False, v2_label_prior("desc")),
    "position": ("position", False, v2_position),
    "recency_last_entry": ("recency_last_entry", False, v2_recency),
    "uniform_null": ("uniform_null", False, v2_uniform_null),
    "positive_control_rule_lookup": (
        "positive_control_rule_lookup",
        True,
        v2_lookup,
    ),
}


# ------------------------------------------------------------ v3 (tests/test_skill_experience/test_nuisance.py の移植)


@cache
def _v3_rows(arm: str, r: int) -> tuple[v3bat.Row, ...]:
    return tuple(v3bat.state_rows(arm, v2bat.layout(r)))


Score = "Callable[[Sequence[v3bat.Row], v2bat.LeverProbe, str], float]"


def v3_by_score(
    score: Callable[[Sequence[v3bat.Row], v2bat.LeverProbe, str], float],
) -> Callable[[str, int, v2bat.LeverProbe, int], str]:
    """選択肢ごとの score の最大 (同点は表示順)。C0 は表示先頭 (原本 ``by_score``)."""

    def policy(arm: str, r: int, p: v2bat.LeverProbe, _k: int) -> str:
        opts = _opts(r, p)
        if arm == v3bat.ARM_C0:
            return opts[0]
        rows = list(_v3_rows(arm, r))
        best = max(range(len(opts)), key=lambda i: (score(rows, p, opts[i]), -i))
        return opts[best]

    return policy


def _succ(rows: Sequence[v3bat.Row]) -> list[v3bat.Row]:
    return [x for x in rows if x.success]


def _count(labels: Sequence[str], opt: str) -> float:
    return float(Counter(labels)[opt])


def _rate(rows: Sequence[v3bat.Row], _p: v2bat.LeverProbe, o: str) -> float:
    ts = [x for x in rows if x.action == o]
    return sum(x.success for x in ts) / len(ts) if ts else -1.0


def _first(rows: Sequence[v3bat.Row], _p: v2bat.LeverProbe, o: str) -> float:
    s = [x.action for x in _succ(rows)]
    return -s.index(o) if o in s else -1e9


def _last(rows: Sequence[v3bat.Row], _p: v2bat.LeverProbe, o: str) -> float:
    s = [x.action for x in _succ(rows)]
    return max(i for i, a in enumerate(s) if a == o) if o in s else -1e9


def _adjacent(
    offset: int,
) -> Callable[[Sequence[v3bat.Row], v2bat.LeverProbe, str], float]:
    def score(rows: Sequence[v3bat.Row], _p: v2bat.LeverProbe, o: str) -> float:
        labels = [
            rows[i + offset].action
            for i, x in enumerate(rows)
            if x.success and 0 <= i + offset < len(rows)
        ]
        return _count(labels, o)

    return score


def _neighbour(rows: Sequence[v3bat.Row], p: v2bat.LeverProbe, o: str) -> float:
    """Weather を無視し、時刻・同伴が probe と一致する signature の成功行."""
    labels = [x.action for x in _succ(rows) if x.signature[1:] == p.signature[1:]]
    return _count(labels, o)


def _weather_match(rows: Sequence[v3bat.Row], p: v2bat.LeverProbe, o: str) -> float:
    """陽性対照: weather が probe と一致する成功行."""
    labels = [x.action for x in _succ(rows) if x.signature[0] == p.signature[0]]
    return _count(labels, o)


def _success_count(rows: Sequence[v3bat.Row], _p: v2bat.LeverProbe, o: str) -> float:
    return _count([x.action for x in _succ(rows)], o)


def _fewest_failures(rows: Sequence[v3bat.Row], _p: v2bat.LeverProbe, o: str) -> float:
    return -_count([x.action for x in rows if not x.success], o)


@cache
def _masked_prompt(arm: str, r: int, probe_id: str) -> str:
    p = _V2_PROBES[probe_id]
    return v3bat.mask_outcomes(
        v3bat.render_messages(arm, p, v2bat.layout(r))[1]["content"]
    )


def v3_hash(salt: str) -> Callable[[str, int, v2bat.LeverProbe, int], str]:
    """成否欄を消した prompt と seed だけの任意関数 (原本 ``_hash_policy``)."""

    def policy(arm: str, r: int, p: v2bat.LeverProbe, k: int) -> str:
        opts = _opts(r, p)
        if arm == v3bat.ARM_C0:
            return opts[0]
        text = f"{salt}|{k}|{_masked_prompt(arm, r, p.probe_id)}"
        h = hashlib.sha256(text.encode()).digest()
        return opts[h[0] % len(opts)]

    return policy


def v3_priming(arm: str, r: int, p: v2bat.LeverProbe, _k: int) -> str:
    opts = _opts(r, p)
    if arm == v3bat.ARM_C0:
        return opts[0]
    labels = [x.action for x in _v3_rows(arm, r)]
    return max(opts, key=lambda o: (labels.count(o), -opts.index(o)))


def v3_recency(arm: str, r: int, p: v2bat.LeverProbe, _k: int) -> str:
    opts = _opts(r, p)
    if arm == v3bat.ARM_C0:
        return opts[0]
    labels = [x.action for x in _v3_rows(arm, r) if x.action in opts]
    return labels[-1] if labels else opts[0]


def v3_first_row(arm: str, r: int, p: v2bat.LeverProbe, _k: int) -> str:
    opts = _opts(r, p)
    if arm == v3bat.ARM_C0:
        return opts[0]
    labels = [x.action for x in _v3_rows(arm, r) if x.action in opts]
    return labels[0] if labels else opts[0]


def v3_position(_arm: str, r: int, p: v2bat.LeverProbe, _k: int) -> str:
    return _opts(r, p)[0]


V3_POLICIES: Final[dict[str, tuple[str, bool, Callable[..., str]]]] = {
    "outcome_blind/priming": ("outcome_blind", False, v3_priming),
    "outcome_blind/recency": ("outcome_blind", False, v3_recency),
    "outcome_blind/first_row": ("outcome_blind", False, v3_first_row),
    "outcome_blind/position": ("outcome_blind", False, v3_position),
    "outcome_blind/hash_a": ("outcome_blind", False, v3_hash("a")),
    "outcome_blind/hash_b": ("outcome_blind", False, v3_hash("b")),
    "outcome_blind/hash_c": ("outcome_blind", False, v3_hash("c")),
    "success_count": ("most_success_label", False, v3_by_score(_success_count)),
    "fewest_failures": ("most_success_label", False, v3_by_score(_fewest_failures)),
    "success_rate": ("most_success_label", False, v3_by_score(_rate)),
    "first_success": ("first_or_last_success_row", False, v3_by_score(_first)),
    "last_success": ("first_or_last_success_row", False, v3_by_score(_last)),
    "after_success": ("row_after_success", False, v3_by_score(_adjacent(1))),
    "before_success": ("row_before_success", False, v3_by_score(_adjacent(-1))),
    "nearest_neighbor_ignoring_weather": (
        "nearest_neighbor_ignoring_weather",
        False,
        v3_by_score(_neighbour),
    ),
    "positive_control_weather_match": (
        "positive_control_weather_match",
        True,
        v3_by_score(_weather_match),
    ),
}


def _lever_cell_policy(
    fn: Callable[[str, int, v2bat.LeverProbe, int], str],
) -> Callable[[tuple[Any, ...]], str | None]:
    """v2・v3 の key = (arm, r, probe_id, k)."""

    def choose(key: tuple[Any, ...]) -> str | None:
        arm, r, pid, k = key
        return fn(arm, r, _V2_PROBES[pid], k)

    return choose


# ------------------------------------------------------------ G・O_time (凍結の fixture)

_G_PROBES: Final[dict[str, gbat.Probe]] = {p.probe_id: p for p in gbat.probes()}


@cache
def _g_contexts(arm: str, r: int) -> dict[str, gfx.Context]:
    return {p.probe_id: ctx for p, ctx in gfx.contexts(arm, r)}


def _g_cell_policy(
    fn: Callable[[gfx.Context], str | None],
) -> Callable[[tuple[Any, ...]], str | None]:
    def choose(key: tuple[Any, ...]) -> str | None:
        arm, r, pid, _ = key
        return fn(_g_contexts(arm, r)[pid])

    return choose


def _o_cell_policy(
    fn: Callable[[ofx.Context], str | None],
) -> Callable[[tuple[Any, ...]], str | None]:
    def choose(key: tuple[Any, ...]) -> str | None:
        arm, enc, r, pid, _ = key
        unit = obat.Unit(obat.ARM_FAMILY[arm], osc.room_index(pid), r)
        return fn(ofx.context(arm, enc, unit))

    return choose


def policies(battery: str) -> list[Policy]:
    """Battery の登録方策 (陽性対照を含む)。名前の順に並べる."""
    out: list[Policy] = []
    if battery in ("v2", "v3"):
        table = V2_POLICIES if battery == "v2" else V3_POLICIES
        out = [
            Policy(n, reg, pc, _lever_cell_policy(fn))
            for n, (reg, pc, fn) in table.items()
        ]
    elif battery == "G":
        out = [
            Policy(n, fam, False, _g_cell_policy(fn))  # type: ignore[arg-type]
            for n, (fam, fn) in gfx.registered_policies().items()
        ] + [
            Policy(n, "positive_control", True, _g_cell_policy(fn))  # type: ignore[arg-type]
            for n, fn in gfx.positive_controls().items()
        ]
    elif battery == "O_time":
        out = [
            Policy(n, fam, False, _o_cell_policy(fn))
            for n, (fam, fn) in ofx.registered_policies().items()
        ] + [
            Policy(n, "positive_control", True, _o_cell_policy(fn))
            for n, fn in ofx.positive_controls().items()
        ]
    else:
        msg = f"unknown battery {battery!r}"
        raise ValueError(msg)
    return sorted(out, key=lambda p: p.name)


# ------------------------------------------------------------ C と対


def policy_units(
    battery: str,
    choose: Callable[[tuple[Any, ...]], str | None],
    r_list: Sequence[int],
) -> np.ndarray:
    """方策に完全に従ったときの単位の値 (本走の scorer と同じ単位・採点)."""
    choices = {c.key: choose(c.key) for c in un.lever_cells(battery, r_list)}
    return un.unit_values(un.unit_counts(battery, choices, r_list))


def policy_c(
    battery: str,
    choose: Callable[[tuple[Any, ...]], str | None],
    r_list: Sequence[int],
) -> float:
    return float(np.mean(policy_units(battery, choose, r_list)))


def pairs(cs: Mapping[str, float]) -> list[dict[str, Any]]:
    """全ての順序のない対 (名前の昇順の a < b)。diff = C_a − C_b."""
    names = sorted(cs)
    return [
        {"a": a, "b": b, "diff": round(cs[a] - cs[b], ROUND)}
        for i, a in enumerate(names)
        for b in names[i + 1 :]
    ]


def over_delta_min(cs: Mapping[str, float]) -> list[dict[str, Any]]:
    """|ΔC| > Δ_min の対 (高い方 → 低い方)。浮動小数の誤差は 12 桁で潰す."""
    out = []
    for q in pairs(cs):
        if abs(q["diff"]) > st.DELTA_MIN + 10.0**-ROUND:
            hi, lo = (q["a"], q["b"]) if q["diff"] > 0 else (q["b"], q["a"])
            out.append({"high": hi, "low": lo, "diff": abs(q["diff"])})
    return sorted(out, key=lambda q: (-q["diff"], q["high"], q["low"]))


def main_r_list(battery: str, r_count: int) -> list[int]:
    r0 = st.SPECS[battery].main_r0
    return list(range(r0, r0 + r_count))


def battery_table(battery: str, r_list: Sequence[int]) -> dict[str, Any]:
    rows: dict[str, Any] = {}
    nuisance: dict[str, float] = {}
    for p in policies(battery):
        c = round(policy_c(battery, p.choose, r_list), ROUND)
        rows[p.name] = {
            "registered": p.registered,
            "positive_control": p.positive_control,
            "C": c,
        }
        if not p.positive_control:
            nuisance[p.name] = c
    return {
        "status": "computed",
        "r_list": [r_list[0], r_list[-1] + 1] if r_list else [],
        "R": len(r_list),
        "n_policies": len(rows),
        "policies": rows,
        "max_abs_C_nuisance": max(abs(v) for v in nuisance.values()),
        "nuisance_pairs": pairs(nuisance),
        "nuisance_pairs_over_delta_min": over_delta_min(nuisance),
    }


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def selected_r(gate: Mapping[str, Any]) -> dict[str, int | None]:
    """Gate の R (GO・HELD_COST の battery だけ int。契約の照合は scorer・driver がする)."""
    out: dict[str, int | None] = {}
    for b in st.BATTERIES:
        r = gate["batteries"][b].get("R")
        out[b] = r if type(r) is int else None
    return out


def fixture_diffs_main(gate: Mapping[str, Any], gate_sha256: str) -> dict[str, Any]:
    batteries: dict[str, Any] = {}
    for b, r in selected_r(gate).items():
        if r is None:
            batteries[b] = {
                "status": NOT_SELECTED,
                "gate": gate["batteries"][b].get("gate"),
            }
            continue
        batteries[b] = {
            "gate": gate["batteries"][b].get("gate"),
            **battery_table(b, main_r_list(b, r)),
        }
    return {
        "schema": SCHEMA,
        "delta_min": st.DELTA_MIN,
        "inputs": {
            "gate_json_sha256": gate_sha256,
            "frozen_fixture_sha256": {
                b: _sha(p.read_bytes()) for b, p in FROZEN_SOURCES.items()
            },
        },
        "batteries": batteries,
    }


def text(obj: object) -> str:
    return (
        json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False)
        + "\n"
    )


def compute_text(gate_path: pathlib.Path) -> str:
    raw = gate_path.read_bytes()
    gate = json.loads(raw.decode("utf-8"))
    return text(fixture_diffs_main(gate, _sha(raw)))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gate", type=pathlib.Path, default=GATE_JSON)
    ap.add_argument("--out", type=pathlib.Path, default=OUT_JSON)
    ap.add_argument(
        "--check", action="store_true", help="計算し直して --out と byte 比較"
    )
    args = ap.parse_args(argv)
    body = compute_text(args.gate)
    if args.check:
        same = args.out.read_bytes() == body.encode("utf-8")
        print("[fixtures] " + ("MATCH" if same else "DIFFERS"))  # noqa: T201
        return 0 if same else 3
    if args.out.exists():
        print(f"[fixtures] refusing to overwrite {args.out}", file=sys.stderr)  # noqa: T201
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(body.encode("utf-8"))
    print(f"[fixtures] wrote {args.out}")  # noqa: T201
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
