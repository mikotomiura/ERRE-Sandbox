#!/usr/bin/env python
"""経験由来 Skill pilot — 記述報告 (prereg v3 §10、判定に使わない)。

``run.sh`` の判定の **後** に 1 回だけ実行する。項目は prereg v3 §10 の列挙に限り、実走前に commit して固定する
(データを見てから報告項目を選ばない。v2 DR-7 と同じ)。verdict は ``results.json`` だけが持つ。

* C0 の選択分布 (label 別・表示位置別) と ⊥ 率 (位置の偏り)。
* 判定 4 成分と対照 4 成分、それぞれの C と C > 0 の符号反転 p (p_zero)。
* arm 別の w / foil / other (Ω_q 内の残り) / OOΩ / ⊥ の率と、filler を答えた率 (対照)。filler 率は
  「parse が ⊥ で、filler 語がちょうど 1 種だけ出た」応答の率。filler に言及しただけの率は別欄
  (``filler_mention_rate``)。
* C_v3 / C_v2 と成分別の差。v2 は別 run (``experiments/20260926-skill-lever-pilot/results/run/results.json``)
  で、記述上の上限 anchor であって判定には使わない。
* 対照 C − 判定 C (失敗行の label が選択肢と競合することの効果の記述)。
* 生テキストが label と厳密一致しなかった率 (前後空白を除いた raw ≠ parsed)。

``results.json`` と run dir の ``provenance.json`` を必須入力にする。``results.json`` の ``inputs.records_sha256`` が
``--records`` と一致しなければ止まる。``scripts/skill_experience_run_gate.py`` の gate が落ちた run は not_computed
と同じ扱いにする (DE-R5)。prereg v3 §9 (「INVALID / 測れなかった: 効果の有無を書かない」) に従う。
* 判定 verdict が PASS / NO_GO / INCONCLUSIVE でなければ、判定 arm の効果の数値 (成分・C・p・w/foil 率・
  v2 との比・対照との差) を null にして理由を書く。
* 対照の効果の数値は、判定側が出せ、かつ対照 verdict も PASS / NO_GO / INCONCLUSIVE のときだけ出す。
* ⊥・OOΩ・filler 率と C0 の分布は INVALID の説明に要るので残す。
* INCONCLUSIVE では §10 の数値 (C・p_zero を含む) を出すが、``interpretation_note`` に「効果の有無を書かない」
  (§9) を付ける (DE-R4)。

実行 (repo root から)::

    uv run python scripts/skill_experience_describe.py --records <samples.jsonl> \
        --results <results.json> --run-dir <run dir> --out <describe.json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
import unicodedata
from collections import Counter
from typing import TYPE_CHECKING, Any

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import skill_experience_battery as bat  # noqa: E402
from scripts import skill_experience_scorer as sc  # noqa: E402
from scripts import skill_experience_run_gate as gate  # noqa: E402
from scripts import skill_lever_battery as v2bat  # noqa: E402
from scripts.skill_lever_scorer import (  # noqa: E402
    category,
    family_units,
    load_records,
    tests_exact,
)
from scripts.stage_b_scorer import (  # noqa: E402
    VERDICT_ABSENT,
    VERDICT_PASS,
    VERDICT_UNDERPOWERED,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

V2_RESULTS: pathlib.Path = (
    _REPO_ROOT
    / "experiments"
    / "20260926-skill-lever-pilot"
    / "results"
    / "run"
    / "results.json"
)
CATEGORIES = ("w", "foil", "other", "oov", "bot")
EFFECT_VERDICTS = frozenset({VERDICT_PASS, VERDICT_ABSENT, VERDICT_UNDERPOWERED})
_EFFECT_ARM_KEYS = ("w_rate", "foil_rate", "other_rate", "w_rate_minus_c0")
_FILLER_PATTERNS = {
    f: re.compile(rf"(?<![0-9a-z]){re.escape(f)}(?![0-9a-z])") for f in bat.FILLERS
}
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


def fillers_in(raw: str) -> set[str]:
    """NFKC・小文字化・think 除去の後に出る filler 語 (parse_choice と同じ前処理)."""
    text = _THINK.sub("", unicodedata.normalize("NFKC", raw).lower())
    return {f for f, pat in _FILLER_PATTERNS.items() if pat.search(text)}


def answered_filler(raw: str) -> bool:
    """Filler を答えた = parse が ⊥ (語彙の label がちょうど 1 種ではない) で filler 語がちょうど 1 種."""
    return sc.parse_choice(raw) is None and len(fillers_in(raw)) == 1


def _rate(n: int, d: int) -> float | None:
    return n / d if d else None


def _estimand(
    done: Sequence[sc.Sample], arms: Sequence[str]
) -> dict[str, Any] | None:
    """4 arm の全 key が揃ったときだけ、成分・C・単位・p_zero."""
    present = {(s.arm, s.replicate, s.probe_id, s.k) for s in done}
    if not sc.grid(arms) <= present:
        return None
    choices: dict[tuple[str, int, str], list[str | None]] = {}
    for s in sorted(done, key=lambda x: x.k):
        choices.setdefault((s.arm, s.replicate, s.probe_id), []).append(s.parsed)
    comp = sc.component_scores(choices, arms, sc.FROZEN_R)
    d = family_units(comp)
    p_zero, _, _ = tests_exact(d)
    return {
        "components": dict(zip(arms, comp.mean(axis=1).tolist(), strict=True)),
        "C": float(d.mean()),
        "units": d.tolist(),
        "p_zero": p_zero,
    }


def _v2_anchor(v2_results: dict[str, Any] | None, est: dict[str, Any] | None) -> Any:
    """C_v3 / C_v2 と成分別の差 (v3 − v2)。v2 の記録が読めなければ None."""
    if est is None or v2_results is None:
        return None
    try:
        c_v2 = float(v2_results["C"])
        comp_v2 = {a: float(v2_results["components"][a]) for a in bat.JUDGE_ARMS}
    except (KeyError, TypeError, ValueError):
        return None
    return {
        "C_v2": c_v2,
        "C_v3_over_C_v2": est["C"] / c_v2 if c_v2 else None,
        "component_minus_v2": {
            a: est["components"][a] - comp_v2[a] for a in bat.JUDGE_ARMS
        },
    }


def describe(
    samples: Sequence[sc.Sample],
    results: dict[str, Any],
    v2_results: dict[str, Any] | None = None,
    gate_problems: Sequence[str] = (),
) -> dict[str, Any]:
    probes = {p.probe_id: p for p in v2bat.lever_probes()}
    done = [s for s in samples if s.raw is not None]
    by_arm: dict[str, list[sc.Sample]] = {}
    for s in done:
        by_arm.setdefault(s.arm, []).append(s)
    out: dict[str, Any] = {
        "note": "記述報告のみ (prereg v3 §10)。判定は results.json。v2 は別 run の記述上の anchor。",
        "n_samples": len(samples),
        "n_transport_failures": len(samples) - len(done),
    }

    # ---- C0 の選択分布
    c0 = by_arm.get(bat.ARM_C0, [])
    labels = Counter(s.parsed if s.parsed is not None else "⊥" for s in c0)
    positions: Counter[str] = Counter()
    for s in c0:
        order = v2bat.layout(s.replicate).option_order[s.probe_id]
        if s.parsed is None:
            positions["bot"] += 1
        elif s.parsed in order:
            positions[str(order.index(s.parsed))] += 1
        else:
            positions["oov"] += 1
    out["c0"] = {
        "n": len(c0),
        "label_rates": {k: labels[k] / len(c0) for k in sorted(labels)} if c0 else {},
        "position_rates": (
            {k: positions[k] / len(c0) for k in sorted(positions)} if c0 else {}
        ),
        "bottom_rate": _rate(labels["⊥"], len(c0)),
        "pointed_rates": {
            arm: _rate(
                sum(s.parsed == probes[s.probe_id].pointed[arm] for s in c0), len(c0)
            )
            for arm in bat.JUDGE_ARMS
        },
    }

    # ---- arm 別の区分率・C0 との差・filler 率
    arms: dict[str, Any] = {}
    for arm in bat.STATE_ARMS:
        rows = by_arm.get(arm, [])
        as_arm = bat.POINTS_AS[arm]
        cats = Counter(category(s.parsed, probes[s.probe_id], as_arm) for s in rows)
        w_rate = _rate(cats["w"], len(rows))
        c0_rate = out["c0"]["pointed_rates"][as_arm]
        fillers = sum(answered_filler(s.raw or "") for s in rows)
        mentions = sum(bool(fillers_in(s.raw or "")) for s in rows)
        arms[arm] = {
            "n": len(rows),
            **{f"{c}_rate": _rate(cats[c], len(rows)) for c in CATEGORIES},
            "filler_rate": _rate(fillers, len(rows)),
            "filler_mention_rate": _rate(mentions, len(rows)),
            "w_rate_minus_c0": (
                None if w_rate is None or c0_rate is None else w_rate - c0_rate
            ),
        }
    out["state_arms"] = arms

    # ---- 推定量 (判定・対照) と v2 anchor・対照 − 判定
    judge = _estimand(done, bat.JUDGE_ARMS)
    control = _estimand(done, bat.CONTROL_ARMS)
    out["judge_estimand"] = judge
    out["control_estimand"] = control
    out["v2_anchor"] = _v2_anchor(v2_results, judge)
    out["control_C_minus_judge_C"] = (
        None if judge is None or control is None else control["C"] - judge["C"]
    )

    # ---- 冗長な応答の率
    out["non_exact_label_rate"] = {
        arm: _rate(
            sum(s.raw.strip() != (s.parsed or "") for s in rows if s.raw is not None),
            len(rows),
        )
        for arm, rows in sorted(by_arm.items())
    }
    return _suppress_effects_unless_valid(out, results, gate_problems)


def _suppress_effects_unless_valid(
    out: dict[str, Any], results: dict[str, Any], gate_problems: Sequence[str]
) -> dict[str, Any]:
    """INVALID_* / not_computed / run gate 不合格では効果の数値を出さない (prereg v3 §9)."""
    status, verdict = results.get("status"), results.get("verdict")
    out["run_gate_problems"] = list(gate_problems)
    if gate_problems:  # driver の終了状態が判定に進めない run は not_computed (DE-R5)
        status, verdict = sc.STATUS_NOT_COMPUTED, None
    ctrl = results.get("control") or {}
    ctrl_verdict = ctrl.get("verdict") if isinstance(ctrl, dict) else None
    out["verdict"] = {
        "status": status,
        "verdict": verdict,
        "control_verdict": ctrl_verdict,
        "claim_branch": results.get("claim_branch"),
    }
    judge_ok = status == sc.STATUS_COMPUTED and verdict in EFFECT_VERDICTS
    control_ok = judge_ok and ctrl_verdict in EFFECT_VERDICTS
    out["effects_suppressed"] = (
        None if judge_ok else f"status={status} verdict={verdict} (prereg v3 §9)"
    )
    out["control_effects_suppressed"] = (
        None
        if control_ok
        else f"verdict={verdict} control_verdict={ctrl_verdict} (prereg v3 §9)"
    )
    if not judge_ok:
        out["judge_estimand"] = None
        out["v2_anchor"] = None
    if not control_ok:
        out["control_estimand"] = None
        out["control_C_minus_judge_C"] = None
    out["interpretation_note"] = (
        "INCONCLUSIVE: 効果の有無を書かない (prereg v3 §9)。数値は §10 の記述のみ"
        if judge_ok and verdict == VERDICT_UNDERPOWERED
        else None
    )
    for arm, row in out["state_arms"].items():
        ok = control_ok if arm in bat.CONTROL_ARMS else judge_ok
        if not ok:
            for k in _EFFECT_ARM_KEYS:
                row[k] = None
    return out


def _read_v2(path: pathlib.Path) -> dict[str, Any] | None:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--records", type=pathlib.Path, required=True)
    ap.add_argument("--results", type=pathlib.Path, required=True)
    ap.add_argument("--run-dir", type=pathlib.Path, required=True)
    ap.add_argument("--out", type=pathlib.Path, required=True)
    ap.add_argument("--v2-results", type=pathlib.Path, default=V2_RESULTS)
    args = ap.parse_args(argv)
    lines = args.records.read_text(encoding="utf-8").splitlines()
    results = json.loads(args.results.read_text(encoding="utf-8"))
    records_sha = hashlib.sha256(args.records.read_bytes()).hexdigest()
    if (results.get("inputs") or {}).get("records_sha256") != records_sha:
        print("results.json was not computed from these records", file=sys.stderr)
        return 2
    report = describe(
        load_records(lines),
        results,
        _read_v2(args.v2_results),
        gate.run_gate_problems(args.run_dir),
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
