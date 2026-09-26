#!/usr/bin/env python
"""Skill lever pilot — 記述報告 (prereg v2 §10、判定に使わない)。

``run.sh`` の判定の **後** に 1 回だけ実行する。項目は prereg §10 の列挙に限り、実走前に commit して固定する
(データを見てから報告項目を選ばない、decisions.md DR-7)。verdict は ``results.json`` だけが持つ。

* C0 の選択分布 (label 別・表示位置別) と ⊥ 率。
* 旧型の対比 (A の状態で g_A − g_B、B の状態で g_B − g_A、その平均)。**label priming と交絡する** (§2.2)。
* 成分 4 つ、C、C > 0 の符号反転 p (p_zero)。lever 4 arm が揃ったときだけ。
* arm 別の w / foil / other (Ω_q 内の残り) / OOΩ / ⊥ の率。C0 は各 lever arm の指す選択肢を選んだ率。
* C0 と lever arm の差 (arm a の w_a 選択率 − C0 の同じ選択肢の選択率)。
* 生テキストが label と厳密一致しなかった率 (前後空白を除いた raw ≠ parsed、冗長な応答の率)。

``results.json`` を必須入力にし、verdict が PASS / NO_GO / INCONCLUSIVE のときだけ効果の数値
(成分・C・p_zero・旧型対比・arm 別の w / foil 率と C0 との差) を出す。INVALID_* と not_computed では
prereg §9 (「効果の有無を書かない」) に従い、それらを null にして理由を書く (⊥・OOΩ 率と C0 は残す)。

実行 (repo root から)::

    uv run python scripts/skill_lever_describe.py --records <samples.jsonl> \
        --results <results.json> --out <describe.json>
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import Counter
from typing import TYPE_CHECKING, Any

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import skill_lever_battery as bat  # noqa: E402
from scripts import skill_lever_scorer as sc  # noqa: E402

if TYPE_CHECKING:
    from collections.abc import Sequence

CATEGORIES = ("w", "foil", "other", "oov", "bot")
EFFECT_VERDICTS = frozenset(
    {sc.VERDICT_PASS, sc.VERDICT_ABSENT, sc.VERDICT_UNDERPOWERED}
)
_EFFECT_ARM_KEYS = ("w_rate", "foil_rate", "other_rate", "w_rate_minus_c0")


def _rate(n: int, d: int) -> float | None:
    return n / d if d else None


def describe(
    samples: Sequence[sc.Sample], results: dict[str, Any]
) -> dict[str, Any]:
    probes = {p.probe_id: p for p in bat.lever_probes()}
    done = [s for s in samples if s.raw is not None]
    by_arm: dict[str, list[sc.Sample]] = {}
    for s in done:
        by_arm.setdefault(s.arm, []).append(s)
    out: dict[str, Any] = {
        "note": "記述報告のみ (prereg v2 §10)。判定は results.json。旧型対比は label priming と交絡する。",
        "n_samples": len(samples),
        "n_transport_failures": len(samples) - len(done),
    }

    # ---- C0 の選択分布
    c0 = by_arm.get(bat.ARM_C0, [])
    labels = Counter(s.parsed if s.parsed is not None else "⊥" for s in c0)
    positions: Counter[str] = Counter()
    for s in c0:
        order = bat.layout(s.replicate).option_order[s.probe_id]
        positions[str(order.index(s.parsed)) if s.parsed in order else "none"] += 1
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
            for arm in bat.LEVER_ARMS
        },
    }

    # ---- arm 別の区分率と C0 との差
    arms: dict[str, Any] = {}
    for arm in bat.LEVER_ARMS:
        rows = by_arm.get(arm, [])
        cats = Counter(sc.category(s.parsed, probes[s.probe_id], arm) for s in rows)
        w_rate = _rate(cats["w"], len(rows))
        c0_rate = out["c0"]["pointed_rates"][arm]
        arms[arm] = {
            "n": len(rows),
            **{f"{c}_rate": _rate(cats[c], len(rows)) for c in CATEGORIES},
            "w_rate_minus_c0": (
                None if w_rate is None or c0_rate is None else w_rate - c0_rate
            ),
        }
    out["lever_arms"] = arms

    # ---- 旧型の対比 (priming と交絡)
    def rate_of(arm: str, target_arm: str) -> float | None:
        rows = by_arm.get(arm, [])
        hit = sum(s.parsed == probes[s.probe_id].pointed[target_arm] for s in rows)
        return _rate(hit, len(rows))

    old: dict[str, float | None] = {}
    parts = (
        (rate_of(bat.ARM_A, bat.ARM_A), rate_of(bat.ARM_A, bat.ARM_B)),
        (rate_of(bat.ARM_B, bat.ARM_B), rate_of(bat.ARM_B, bat.ARM_A)),
    )
    diffs = [None if a is None or b is None else a - b for a, b in parts]
    old["A_state_gA_minus_gB"], old["B_state_gB_minus_gA"] = diffs
    old["mean"] = None if None in diffs else (diffs[0] + diffs[1]) / 2  # type: ignore[operator]
    out["old_contrast_confounded_with_priming"] = old

    # ---- 成分・C・p_zero (lever 4 arm の全 key が揃ったときだけ)
    present = {(s.arm, s.replicate, s.probe_id, s.k) for s in done}
    full = {
        (arm, r, p, k)
        for arm in bat.LEVER_ARMS
        for r in range(sc.FROZEN_R)
        for p in probes
        for k in range(sc.FROZEN_K)
    }
    if full <= present:
        choices: dict[tuple[str, int, str], list[str | None]] = {}
        for s in sorted(done, key=lambda x: x.k):
            choices.setdefault((s.arm, s.replicate, s.probe_id), []).append(s.parsed)
        comp = sc.component_scores(choices, sc.FROZEN_R)
        d = sc.family_units(comp)
        p_zero, _, _ = sc.tests_exact(d)
        out["estimand"] = {
            "components": dict(
                zip(bat.LEVER_ARMS, comp.mean(axis=1).tolist(), strict=True)
            ),
            "C": float(d.mean()),
            "units": d.tolist(),
            "p_zero": p_zero,
        }
    else:
        out["estimand"] = None

    # ---- 冗長な応答の率
    verbose = {
        arm: _rate(
            sum(s.raw.strip() != (s.parsed or "") for s in rows if s.raw is not None),
            len(rows),
        )
        for arm, rows in sorted(by_arm.items())
    }
    out["non_exact_label_rate"] = verbose
    return _suppress_effects_unless_valid(out, results)


def _suppress_effects_unless_valid(
    out: dict[str, Any], results: dict[str, Any]
) -> dict[str, Any]:
    """INVALID_* / not_computed では効果の数値を出さない (prereg §9)."""
    status, verdict = results.get("status"), results.get("verdict")
    out["verdict"] = {"status": status, "verdict": verdict}
    if status == sc.STATUS_COMPUTED and verdict in EFFECT_VERDICTS:
        out["effects_suppressed"] = None
        return out
    out["effects_suppressed"] = f"status={status} verdict={verdict} (prereg §9)"
    out["estimand"] = None
    out["old_contrast_confounded_with_priming"] = None
    for row in out["lever_arms"].values():
        for k in _EFFECT_ARM_KEYS:
            row[k] = None
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--records", type=pathlib.Path, required=True)
    ap.add_argument("--results", type=pathlib.Path, required=True)
    ap.add_argument("--out", type=pathlib.Path, required=True)
    args = ap.parse_args(argv)
    lines = args.records.read_text(encoding="utf-8").splitlines()
    results = json.loads(args.results.read_text(encoding="utf-8"))
    report = describe(sc.load_records(lines), results)
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
