#!/usr/bin/env python
"""Stage B B1 の変異試験 — 判定行を壊すと、意図した test が落ちるか (prereg §6).

``scripts/stage_b_scorer.py`` (m1〜m15、Codex review で足した判定行 mc1〜mc4) と ``scripts/stage_b_pre.py`` (mb1〜mb6、§7 rule) の
判定行を 1 つずつ壊し、``tests/test_stage_b/`` を実行する。各変異について

* test が落ちること (exit code 非 0) — 落ちなければ SURVIVED、
* 落ちた test に、その判定行を pin するために書いた test (期待集合) が含まれること —
  含まれなければ WRONG_REASON (別の理由で落ちただけ)、
* collection error で落ちていないこと (import が壊れただけの no-op kill を除く)、
* 置換前の文字列が対象ファイルに 1 回だけ現れ、置換で内容が変わること (no-op 変異を除く)

を確認する。先に無変異で全 test が緑であることを確認する (恒真の検出)。
対象ファイルは実行中だけ書き換わり、必ず原状復帰する (finally + sha256 照合)。

実行 (repo root から)::

    uv run python scripts/stage_b_mutation_check.py --out <results.json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
from dataclasses import dataclass

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_SCORER = _REPO_ROOT / "scripts" / "stage_b_scorer.py"
_B_PRE = _REPO_ROOT / "scripts" / "stage_b_pre.py"
_TESTS = "tests/test_stage_b"
_FAILED = re.compile(r"^FAILED (\S+?)(?:\[.*?\])?(?: - .*)?$")


@dataclass(frozen=True)
class Mutant:
    label: str
    target: pathlib.Path
    old: str
    new: str
    expect: frozenset[str]  # 判定行を pin する test 関数名 (どれか 1 つ以上が落ちる)


def _m(label: str, target: pathlib.Path, old: str, new: str, *expect: str) -> Mutant:
    return Mutant(label, target, old, new, frozenset(expect))


_SAMPLE_UNITS = '''    counts = [category_counts(i, probes) for i in inds]
    units = [
        np.concatenate(
            [
                np.ones(int(c[:, GA].sum())),
                -np.ones(int(c[:, GB].sum())),
                np.zeros(int(c[:, OTHER].sum() + c[:, BOT].sum())),
            ]
        )
        for c in counts
    ]
    return np.concatenate(units), np.repeat(is_a, [u.size for u in units])
'''

MUTANTS: tuple[Mutant, ...] = (
    _m(
        "m1   置換単位を個体から sample に",
        _SCORER,
        "    d, _ = unit_scores(inds, probes)\n    return d, is_a\n",
        _SAMPLE_UNITS,
        "test_n2_individual_displacement_unrelated_to_stream",
        "test_n2_random_direction_is_not_pass",
    ),
    _m(
        "m2   整合対応 g_A / g_B を反転",
        _SCORER,
        "            elif c == probe.g_a:\n                out[qi, GA] += 1\n"
        "            elif c == probe.g_b:\n                out[qi, GB] += 1\n",
        "            elif c == probe.g_b:\n                out[qi, GA] += 1\n"
        "            elif c == probe.g_a:\n                out[qi, GB] += 1\n",
        "test_alignment_direction_positive_control",
        "test_positive_control_passes",
    ),
    _m(
        "m3   ablation 条項を削除",
        _SCORER,
        '        ("ablation_point", abl["C_abl"] <= c / 2.0),\n'
        '        ("ablation_paired", abl["paired_p"] < ALPHA),\n',
        "",
        "test_ablation_retaining_effect_is_not_pass",
    ),
    _m(
        "m4   C の代わりに |C|",
        _SCORER,
        "    return (c_a + c_b) / 2.0, c_a, c_b\n",
        "    return abs((c_a + c_b) / 2.0), c_a, c_b\n",
        "test_anti_aligned_is_one_sided_not_significant",
        "test_contrast_matches_definition",
    ),
    _m(
        "m5a  両成分の符号条件を削除",
        _SCORER,
        '        ("both_components", c_a > 0 and c_b > 0),\n',
        '        ("both_components", True),\n',
        "test_n3_one_sided_effect_is_not_pass",
    ),
    _m(
        "m5b  C_A だけで判定",
        _SCORER,
        '        ("delta_min", c >= delta_min),\n'
        '        ("both_components", c_a > 0 and c_b > 0),\n',
        '        ("delta_min", c_a >= delta_min),\n'
        '        ("both_components", c_a > 0),\n',
        "test_n3_one_sided_effect_is_not_pass",
    ),
    _m(
        "m6a  ⊥ を整合選択に数える",
        _SCORER,
        "                out[qi, BOT] += 1\n            elif c == probe.g_a:\n",
        "                out[qi, GA] += 1\n            elif c == probe.g_a:\n",
        "test_rates_count_bottom_in_denominator_only",
    ),
    _m(
        "m6b  ⊥ を分母から落とす",
        _SCORER,
        "    total = counts.sum(axis=(-2, -1), keepdims=False)\n",
        "    total = counts[..., :BOT].sum(axis=(-2, -1))\n",
        "test_rates_count_bottom_in_denominator_only",
    ),
    _m(
        "m7   δ_min を lever 記録から読まずリテラル",
        _SCORER,
        '        "delta_min": recorded / 2.0,\n',
        '        "delta_min": 0.3375,\n',
        "test_delta_min_is_read_from_lever_record",
    ),
    _m(
        "m8   CI 陰性対照の行を削除",
        _SCORER,
        "    if ci_p < ALPHA:\n"
        '        return done(VERDICT_INVALID_SCORER, "ci_negative_control_separates")\n',
        "",
        "test_ci_separation_is_invalid_scorer",
    ),
    _m(
        "m9   δ_min 条項を削除",
        _SCORER,
        '        ("delta_min", c >= delta_min),\n',
        '        ("delta_min", True),\n',
        "test_c_below_delta_min_is_not_pass",
        "test_delta_min_is_read_from_lever_record",
    ),
    _m(
        "m10  ⊥ 上界条項を削除",
        _SCORER,
        '    if lever["b_lever"] >= delta_min / 2.0 or b_di >= delta_min / 2.0:\n'
        '        return done(VERDICT_INVALID_BATTERY, "bottom_bound")\n',
        "",
        "test_bottom_gap_in_di_is_invalid_battery",
        "test_bottom_gap_in_lever_is_invalid_battery",
    ),
    _m(
        "m11a power 分岐を削除 (常に NO_GO)",
        _SCORER,
        "    if realized < POWER_TARGET:\n"
        '        return done(VERDICT_UNDERPOWERED, "realized_power_below_target")\n',
        "",
        "test_low_realized_power_is_inconclusive",
    ),
    _m(
        "m11b power 分岐を削除 (常に INCONCLUSIVE)",
        _SCORER,
        '    return done(VERDICT_ABSENT, "pass_condition_failed_with_power")\n',
        '    return done(VERDICT_UNDERPOWERED, "pass_condition_failed_with_power")\n',
        "test_high_realized_power_is_absent",
        "test_n1_no_effect_is_not_pass",
    ),
    _m(
        "m12  観測割当を p の分子・分母から落とす",
        _SCORER,
        "        return count / total\n    gen =",
        "        return (count - 1) / (total - 1)\n    gen =",
        "test_perm_p_exact_includes_observed",
    ),
    _m(
        "m13a ablation を unpaired (別 seed) に",
        _SCORER,
        "        if twin.seed != ind.seed:\n",
        "        if False:\n",
        "test_ablation_with_other_seed_is_invalid",
    ),
    _m(
        "m13b ablation の点推定条件を削除",
        _SCORER,
        '        ("ablation_point", abl["C_abl"] <= c / 2.0),\n',
        '        ("ablation_point", True),\n',
        "test_ablation_point_estimate_required",
    ),
    _m(
        "m13c ablation の paired 検定を削除",
        _SCORER,
        '        ("ablation_paired", abl["paired_p"] < ALPHA),\n',
        '        ("ablation_paired", True),\n',
        "test_ablation_paired_test_required",
    ),
    _m(
        "m14  非漏洩 integrity 検査を削除",
        _SCORER,
        "    if violations:\n"
        '        return done(VERDICT_INVALID_SCORER, "non_leakage_integrity")\n',
        "",
        "test_n4_leaked_snapshot_is_invalid_scorer",
    ),
    _m(
        "m15  power 模擬の効果注入を s への直接加算に",
        _SCORER,
        "    p = inject(symmetrize(pool[idx]), is_a, delta_min)\n"
        "    counts = rng.multinomial(k, p)\n"
        "    return rates(counts), is_a\n",
        "    p = symmetrize(pool[idx])\n"
        "    counts = rng.multinomial(k, p)\n"
        "    r = rates(counts)\n"
        "    r[is_a, GA] += delta_min / 2.0\n"
        "    r[~is_a, GB] += delta_min / 2.0\n"
        "    return r, is_a\n",
        "test_simulated_individuals_stay_in_simplex",
    ),
    _m(
        "mc1  B1 certification の確認を削除",
        _SCORER,
        "    if not load_b1_certification(records.b1_certification):\n",
        "    if False:\n",
        "test_b1_certification_is_required",
    ),
    _m(
        "mc2  certification の scorer sha256 照合を削除",
        _SCORER,
        '    return obj.get("all_killed") is True and certified == _scorer_sha256()\n',
        '    return obj.get("all_killed") is True\n',
        "test_b1_certification_is_required",
    ),
    _m(
        "mc3  K / R 整合 guard を削除",
        _SCORER,
        "    if sizes:\n",
        "    if False:\n",
        "test_k_mismatch_is_invalid_scorer",
        "test_unbalanced_di_is_invalid_scorer",
    ),
    _m(
        "mc4  lever 十分性の plan_r 条件を削除",
        _SCORER,
        "        and lever_r is not None\n",
        "",
        "test_weak_lever_is_invalid_battery",
        "test_literal_prereg_power_blocks_lever",
    ),
    _m(
        "mb1  B-pre: 成立を >= に (strict でない)",
        _B_PRE,
        '        "established": median > floor,\n',
        '        "established": median >= floor,\n',
        "test_equal_median_and_floor_is_not_established",
    ),
    _m(
        "mb2  B-pre: 床を within の平均に",
        _B_PRE,
        "    floor = max(within.values())\n",
        "    floor = float(np.mean(list(within.values())))\n",
        "test_floor_is_max_within",
    ),
    _m(
        "mb3  B-pre: between を半分 1 × 半分 2 に",
        _B_PRE,
        "tv(h1[a], h1[b])",
        "tv(h1[a], h2[b])",
        "test_between_uses_half1_only",
    ),
    _m(
        "mb4  B-pre: 両条件 AND を OR に",
        _B_PRE,
        '    established = all(v["established"] for v in per_cond.values())\n',
        '    established = any(v["established"] for v in per_cond.values())\n',
        "test_both_conditions_required",
    ),
    _m(
        "mb5  B-pre: 分割を mc_index 偶奇に",
        _B_PRE,
        "    half1, _ = split_halves()\n    per_cond",
        "    half1 = frozenset(range(0, N_MC, 2))\n    per_cond",
        "test_context_free_choice_is_not_established",
        "test_floor_is_max_within",
    ),
    _m(
        "mb7  B-pre: None の zone を落とす",
        _B_PRE,
        "        zone = r[ZONE_KEY]\n",
        "        zone = r[ZONE_KEY]\n        if zone is None:\n            continue\n",
        "test_none_zone_is_counted_as_bottom_category",
    ),
    _m(
        "mb6  B-pre: 入力 sha256 照合を削除",
        _B_PRE,
        '    if out["inputs"]["bank"]["sha256"] != BANK_SHA256_PREREG:\n',
        "    if False:\n",
        "test_hash_mismatch_is_not_computed",
    ),
)


def _run_tests(env: dict[str, str]) -> tuple[int, list[str], bool]:
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pytest", "-q", "-rf", "-p", "no:cacheprovider", _TESTS],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )
    out = proc.stdout or ""
    failed = sorted(
        {m.group(1).split("::")[-1] for line in out.splitlines() if (m := _FAILED.match(line))}
    )
    collect_error = "ERROR collecting" in out or "Interrupted" in out
    return proc.returncode, failed, collect_error


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=pathlib.Path, default=None)
    args = ap.parse_args(argv)

    env = dict(os.environ, PYTHONUTF8="1")
    originals = {t: t.read_bytes() for t in (_SCORER, _B_PRE)}
    sha_before = {t: hashlib.sha256(b).hexdigest() for t, b in originals.items()}

    code, failed, _ = _run_tests(env)
    if code != 0:
        print(f"ERROR: baseline (無変異) が緑でない: {failed}")
        return 2

    rows: list[dict[str, object]] = []
    try:
        for mut in MUTANTS:
            src = originals[mut.target].decode("utf-8")
            n = src.count(mut.old)
            if n != 1 or mut.old == mut.new:
                status = "NO_OP" if mut.old == mut.new else f"ANCHOR x{n}"
                rows.append({"label": mut.label, "status": status})
                continue
            mut.target.write_bytes(src.replace(mut.old, mut.new, 1).encode("utf-8"))
            code, failed, collect_error = _run_tests(env)
            mut.target.write_bytes(originals[mut.target])
            if code == 0:
                status = "SURVIVED"
            elif collect_error or not failed:
                status = "COLLECTION_ERROR"
            elif mut.expect & set(failed):
                status = "KILLED"
            else:
                status = "WRONG_REASON"
            rows.append(
                {
                    "label": mut.label,
                    "target": mut.target.name,
                    "status": status,
                    "expected_any_of": sorted(mut.expect),
                    "failed": failed,
                }
            )
    finally:
        for t, b in originals.items():
            t.write_bytes(b)

    restored = all(
        hashlib.sha256(t.read_bytes()).hexdigest() == sha_before[t] for t in originals
    )
    bad = [r for r in rows if r["status"] != "KILLED"]
    for r in rows:
        mark = "" if r["status"] == "KILLED" else "  <-- !!"
        print(f"{r['label']:44s} {r['status']:16s} {len(r.get('failed', []))} failed{mark}")
    print(f"source restored (sha256 match): {restored}")
    print(f"not KILLED: {len(bad)} / {len(rows)}")
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(
                {
                    "target_sha256": {t.name: s for t, s in sha_before.items()},
                    "mutants": rows,
                    "all_killed": not bad,
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
    if not restored:
        print("ERROR: 対象ファイルが原状復帰していない")
        return 2
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
