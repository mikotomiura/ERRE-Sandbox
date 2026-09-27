#!/usr/bin/env python
"""閉ループ分散 pilot — 記述報告 (prereg v4 §10、判定に使わない)。

``run.sh`` の判定の **後** に 1 回だけ実行する。項目は実走前に commit して固定する (データを見てから報告項目を
選ばない)。verdict は ``results.json`` だけが持つ。§10 の大半 (族内 TV と雑音床・λ の層別・coverage・ループ段の
⊥ 率・決定性 (i)(ii)) は凍結 scorer の ``evaluate`` が ``results.json`` に書くので、ここでは計算し直さず参照し、
evaluate に無いものだけを足す:

* §10 (iii): v4 の C0 と、v2 / v3 の C0 の同じ key (seed と prompt sha も一致するもの) での raw・parsed 一致率。
* C0 の選択分布 (label 別・表示位置別、⊥ と Ω 外を分ける) と ⊥ 率。INVALID_TASK_BATTERY でも出す。
* 生テキストが label と厳密一致しなかった率 (phase 別)、finish=length の件数、再送回数 (provenance から)。
* 決定性の文言: (i)(ii) のいずれかが 1.0 未満なら §2.5 の「厳密に 0」を「期待値で 0」に格下げする (§10 の規則)。

§9 の抑制: 判定 verdict が PASS / NO_GO / INCONCLUSIVE でない・run gate が落ちた run では、効果の数値
(C・成分・単位・p・coverage・evaluate の記述) を null にする。INCONCLUSIVE では数値を出すが
``interpretation_note`` に「効果の有無を書かない」を付ける (v3 DE-R4)。``results.json`` の
``inputs.records_sha256`` が ``--records`` と一致しなければ止まる。``--records`` は ``--run-dir`` の
``records.jsonl`` でなければならない。run gate が落ちた run では records を読まずに止まる (DR-6: やり直しの
判断の前に label を見ない)。v2 / v3 の記録が読めなければ、その比較は ``error`` とする (0 件一致に畳まない)。

実行 (repo root から)::

    uv run python scripts/closed_loop_describe.py --records <records.jsonl> \\
        --results <results.json> --run-dir <run dir> --out <describe.json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from collections import Counter
from typing import TYPE_CHECKING, Any, Final

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import closed_loop_battery as bat  # noqa: E402
from scripts import closed_loop_run_gate as gate  # noqa: E402
from scripts import closed_loop_scorer as sc  # noqa: E402
from scripts import skill_lever_battery as v2bat  # noqa: E402
from scripts import skill_lever_scorer as v2sc  # noqa: E402
from scripts.stage_b_scorer import (  # noqa: E402
    VERDICT_ABSENT,
    VERDICT_PASS,
    VERDICT_UNDERPOWERED,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

_EXP = _REPO_ROOT / "experiments"
PREVIOUS_C0: Final[dict[str, pathlib.Path]] = {
    "v2": _EXP / "20260926-skill-lever-pilot" / "results" / "run" / "samples.jsonl",
    "v3": _EXP
    / "20260926-experience-skill-pilot"
    / "results"
    / "run"
    / "samples.jsonl",
}
EFFECT_VERDICTS: Final[frozenset[str]] = frozenset(
    {VERDICT_PASS, VERDICT_ABSENT, VERDICT_UNDERPOWERED}
)
EFFECT_KEYS: Final[tuple[str, ...]] = (
    "C",
    "components",
    "units",
    "p_zero",
    "p_lower",
    "p_upper",
    "coverage",
    "describe",
    "claim_text",
)
EXACT: Final[str] = "厳密に 0"
EXPECTED: Final[str] = "期待値で 0"


def _rate(n: int, d: int) -> float | None:
    return n / d if d else None


def c0_distribution(records: Sequence[sc.Record]) -> dict[str, Any]:
    c0 = [x for x in records if x.phase == bat.PHASE_C0 and x.raw is not None]
    labels = Counter(x.parsed if x.parsed is not None else "⊥" for x in c0)
    positions: Counter[str] = Counter()
    for x in c0:
        assert x.probe_id is not None
        order = v2bat.layout(x.replicate).option_order[x.probe_id]
        if x.parsed is None:
            positions["bot"] += 1
        elif x.parsed in order:
            positions[str(order.index(x.parsed))] += 1
        else:
            positions["oov"] += 1
    return {
        "n": len(c0),
        "label_rates": {k: labels[k] / len(c0) for k in sorted(labels)} if c0 else {},
        "position_rates": (
            {k: positions[k] / len(c0) for k in sorted(positions)} if c0 else {}
        ),
        "bottom_rate": _rate(labels["⊥"], len(c0)),
    }


def c0_agreement(
    records: Sequence[sc.Record], previous: Sequence[v2sc.Sample] | None
) -> dict[str, Any]:
    """§10 (iii): 同じ key・seed・prompt sha の C0 で raw / parsed が一致する率."""
    if previous is None:
        return {"error": "previous C0 records could not be read"}
    mine = {
        (x.replicate, x.probe_id, x.k, x.seed, x.prompt_sha256): x
        for x in records
        if x.phase == bat.PHASE_C0 and x.raw is not None
    }
    pairs = [
        (mine[key], s)
        for s in previous
        if s.arm == bat.ARM_C0 and s.raw is not None
        if (key := (s.replicate, s.probe_id, s.k, s.seed, s.prompt_sha256)) in mine
    ]
    return {
        "n_common": len(pairs),
        "raw_identical_rate": _rate(sum(a.raw == b.raw for a, b in pairs), len(pairs)),
        "parsed_identical_rate": _rate(
            sum(a.parsed == b.parsed for a, b in pairs), len(pairs)
        ),
    }


def cancellation_wording(results: dict[str, Any]) -> str | None:
    """決定性 (i)(ii) の率がどちらも 1.0 なら「厳密に 0」、それ以外は「期待値で 0」(§10 の規則)."""
    det = (results.get("describe") or {}).get("determinism")
    if not isinstance(det, dict):
        return None
    return EXACT if det.get("exact_cancellation") is True else EXPECTED


def describe(
    records: Sequence[sc.Record],
    results: dict[str, Any],
    provenance: dict[str, Any] | None,
    previous: dict[str, Sequence[v2sc.Sample] | None],
    gate_problems: Sequence[str] = (),
) -> dict[str, Any]:
    done = [x for x in records if x.raw is not None]
    by_phase: dict[str, list[sc.Record]] = {}
    for x in done:
        by_phase.setdefault(x.phase, []).append(x)
    prov = provenance or {}
    out: dict[str, Any] = {
        "note": "記述報告のみ (prereg v4 §10)。判定は results.json。",
        "n_records": len(records),
        "n_transport_failures": len(records) - len(done),
        "c0": c0_distribution(records),
        "c0_agreement": {
            name: c0_agreement(records, rows) for name, rows in sorted(previous.items())
        },
        "non_exact_label_rate": {
            phase: _rate(
                sum(
                    x.raw is not None and x.raw.strip() != (x.parsed or "")
                    for x in rows
                ),
                len(rows),
            )
            for phase, rows in sorted(by_phase.items())
        },
        "n_finish_length": prov.get("n_finish_length"),
        "n_resends": prov.get("n_resends"),
        "cancellation_wording": cancellation_wording(results),
        "effects": {k: results.get(k) for k in EFFECT_KEYS},
    }
    return _suppress_effects_unless_valid(out, results, gate_problems)


def _suppress_effects_unless_valid(
    out: dict[str, Any], results: dict[str, Any], gate_problems: Sequence[str]
) -> dict[str, Any]:
    """INVALID_* / not_computed / run gate 不合格では効果の数値を出さない (prereg v4 §9)."""
    status, verdict = results.get("status"), results.get("verdict")
    out["run_gate_problems"] = list(gate_problems)
    if gate_problems:  # driver の終了状態が判定に進めない run は not_computed
        status, verdict = sc.STATUS_NOT_COMPUTED, None
    out["verdict"] = {
        "status": status,
        "verdict": verdict,
        "claim_branch": results.get("claim_branch") if not gate_problems else None,
    }
    ok = status == sc.STATUS_COMPUTED and verdict in EFFECT_VERDICTS
    out["effects_suppressed"] = (
        None if ok else f"status={status} verdict={verdict} (prereg v4 §9)"
    )
    if not ok:
        out["effects"] = None
        out["cancellation_wording"] = None
    out["interpretation_note"] = (
        "INCONCLUSIVE: 効果の有無を書かない (prereg v4 §9)。数値は §10 の記述のみ"
        if ok and verdict == VERDICT_UNDERPOWERED
        else None
    )
    return out


def _read_json(path: pathlib.Path) -> dict[str, Any] | None:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None


def _read_previous(
    paths: dict[str, pathlib.Path],
) -> dict[str, list[v2sc.Sample] | None]:
    out: dict[str, list[v2sc.Sample] | None] = {}
    for name, path in paths.items():
        try:
            out[name] = v2sc.load_records(path.read_text(encoding="utf-8").splitlines())
        except (OSError, ValueError):
            out[name] = None
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--records", type=pathlib.Path, required=True)
    ap.add_argument("--results", type=pathlib.Path, required=True)
    ap.add_argument("--run-dir", type=pathlib.Path, required=True)
    ap.add_argument("--out", type=pathlib.Path, required=True)
    args = ap.parse_args(argv)
    if args.records.resolve() != (args.run_dir / "records.jsonl").resolve():
        print("--records must be <run-dir>/records.jsonl", file=sys.stderr)
        return 2
    gate_problems = gate.run_gate_problems(args.run_dir)
    if gate_problems:  # DR-6: gate が落ちた run の label を見ない
        print(f"run gate failed, not describing: {gate_problems}", file=sys.stderr)
        return 2
    lines = args.records.read_text(encoding="utf-8").splitlines()
    results = json.loads(args.results.read_text(encoding="utf-8"))
    records_sha = hashlib.sha256(args.records.read_bytes()).hexdigest()
    if (results.get("inputs") or {}).get("records_sha256") != records_sha:
        print("results.json was not computed from these records", file=sys.stderr)
        return 2
    report = describe(
        sc.load_records(lines),
        results,
        _read_json(args.run_dir / "provenance.json"),
        _read_previous(PREVIOUS_C0),
        gate_problems,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
