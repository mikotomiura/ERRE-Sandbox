#!/usr/bin/env python
"""経験由来 Skill pilot の変異試験 — 判定行を壊すと、意図した test が落ちるか (prereg v3 §7).

``scripts/skill_experience_scorer.py`` (ms*) と ``scripts/skill_experience_battery.py`` (mb*) の判定行を
1 つずつ壊し、``tests/test_skill_experience/`` を実行する。枠組みは v2 (``skill_lever_mutation_check.py``) と
同じ。各変異について次を確認する。

* test が落ちること (exit code 非 0)。落ちなければ SURVIVED。
* 落ちた test に、その判定行を pin するために書いた test (期待集合) が含まれること。
  含まれなければ WRONG_REASON。
* collection error で落ちていないこと。
* 置換前の文字列が対象ファイルに 1 回だけ現れ、置換で内容が変わること (no-op 変異を除く)。

先に無変異で全 test が緑であることを確認する。対象ファイルは実行中だけ書き換わり、必ず原状復帰する
(finally + sha256 照合)。import する凍結 v2 の純粋関数 (parse・category・族単位・⊥ gate・3 分岐・符号反転) は
変異させない。v2 の certification が既に kill を確認しており、本 harness の出力は v2 のファイルを含む
6 ファイルの sha256 を記録して、その同一性に結び付ける。

実行 (repo root から)::

    uv run python scripts/skill_experience_mutation_check.py --out <results.json>
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
_SCORER = _REPO_ROOT / "scripts" / "skill_experience_scorer.py"
_BATTERY = _REPO_ROOT / "scripts" / "skill_experience_battery.py"
_CERTIFIED = (
    _SCORER,
    _BATTERY,
    _REPO_ROOT / "scripts" / "skill_lever_scorer.py",
    _REPO_ROOT / "scripts" / "skill_lever_battery.py",
    _REPO_ROOT / "scripts" / "stage_b_scorer.py",
    _REPO_ROOT / "scripts" / "stage_b_battery.py",
)
_TESTS = "tests/test_skill_experience"
# commit 済み manifest と現在のコードの一致を見る test は、変異中は必ず落ちて生き残りを覆い隠すので外す。
_DESELECT = f"{_TESTS}/test_manifest.py::test_committed_artifacts_are_consistent"
_FAILED = re.compile(r"^FAILED (\S+?)(?:\[.*?\])?(?: - .*)?$")


@dataclass(frozen=True)
class Mutant:
    label: str
    target: pathlib.Path
    old: str
    new: str
    expect: frozenset[str]


def _m(label: str, target: pathlib.Path, old: str, new: str, *expect: str) -> Mutant:
    return Mutant(label, target, old, new, frozenset(expect))


_S = _SCORER
_B = _BATTERY
_OFF = "    if False:\n"
_OFF8 = "        if False:\n"

MUTANTS: tuple[Mutant, ...] = (
    # ---- 推定量
    _m(
        "ms1  対照 arm を判定 arm の指す選択肢に写像しない",
        _S,
        "        as_arm = bat.POINTS_AS[arm]\n",
        "        as_arm = arm\n",
        "test_control_component_uses_judge_pointing",
    ),
    _m(
        "ms2  ⊥ を分母から落とす",
        _S,
        "                    n += 1\n",
        '                    n += cat != "bot"\n',
        "test_bottom_counts_in_denominator",
    ),
    # ---- 判定 (3 分岐への入力)
    _m(
        "ms3  PASS の下限を τ でなく 0 に (p_zero で判定)",
        _S,
        "        verdict=str(decide(np.float64(p_lower), np.float64(p_upper), comps)),\n",
        "        verdict=str(decide(np.float64(p_zero), np.float64(p_upper), comps)),\n",
        "test_small_effect_is_no_go",
    ),
    _m(
        "ms4  PASS でなければ全て NO_GO",
        _S,
        "        verdict=str(decide(np.float64(p_lower), np.float64(p_upper), comps)),\n",
        "        verdict=str(decide(np.float64(p_lower), np.float64(0.0), comps)),\n",
        "test_effect_at_threshold_is_inconclusive",
        "test_noisy_effect_straddling_threshold_is_inconclusive",
        "test_one_arm_failure_is_not_pass",
    ),
    _m(
        "ms5  4 成分の符号条件を外す",
        _S,
        "    comps = s.mean(axis=1)\n    p_zero, p_lower, p_upper = tests_exact(d)\n",
        "    comps = np.ones(len(arms))\n    p_zero, p_lower, p_upper = tests_exact(d)\n",
        "test_one_arm_failure_is_not_pass",
    ),
    # ---- 対照と claim 分岐
    _m(
        "ms6  判定を対照 arm で計算する",
        _S,
        "    main = judge_arms(choices, bat.JUDGE_ARMS)\n",
        "    main = judge_arms(choices, bat.CONTROL_ARMS)\n",
        "test_control_does_not_change_the_verdict",
        "test_no_go_with_control_pass_is_attributed",
    ),
    _m(
        "ms7  対照 verdict を判定 arm で計算する",
        _S,
        "        control = judge_arms(choices, bat.CONTROL_ARMS)\n",
        "        control = judge_arms(choices, bat.JUDGE_ARMS)\n",
        "test_no_go_with_control_pass_is_attributed",
        "test_control_does_not_change_the_verdict",
    ),
    _m(
        "ms8  対照 PASS の条件を外す (NO_GO を常に対照 PASS 側へ)",
        _S,
        "        if control_verdict == VERDICT_PASS:\n",
        "        if True:\n",
        "test_no_go_with_control_no_go_stays_narrow",
        "test_claim_branch_table",
    ),
    _m(
        "ms9  claim 分岐に対照 verdict を渡さない",
        _S,
        '    report["claim_branch"] = claim_branch(verdict, control["verdict"])\n',
        '    report["claim_branch"] = claim_branch(verdict, None)\n',
        "test_no_go_with_control_pass_is_attributed",
    ),
    _m(
        "ms10 対照の ⊥ gate を判定 verdict に効かせる",
        _S,
        '    if main["verdict"] == VERDICT_INVALID_BATTERY:\n',
        '    if VERDICT_INVALID_BATTERY in (main["verdict"], control["verdict"]):\n',
        "test_control_bottom_gate_only_affects_control",
    ),
    _m(
        "ms11 対照行の欠けを検査しない",
        _S,
        "    if grid(bat.CONTROL_ARMS) <= present:\n",
        _OFF.replace("False", "True"),
        "test_missing_control_rows_leave_the_verdict",
    ),
    # ---- ⊥ gate
    _m(
        "ms12 判定 arm / 対照の ⊥ gate を削除",
        _S,
        "    if not bool(bottom_gate_ok(bot)):\n",
        _OFF,
        "test_lever_bottom_rate_is_invalid_battery",
        "test_family_bottom_gap_is_invalid_battery",
        "test_control_bottom_gate_only_affects_control",
    ),
    _m(
        "ms13 C0 ⊥ gate を削除",
        _S,
        "    if c0_bot > BOT_MAX:\n",
        _OFF,
        "test_c0_bottom_rate_is_invalid_battery",
        "test_c0_gate_precedes_missing_state_rows",
    ),
    # ---- 計算できない / INVALID_SCORER
    _m(
        "ms14 transport 失敗を ⊥ に畳む",
        _S,
        "    if any(s.raw is None for s in samples):\n",
        _OFF,
        "test_transport_failure_is_not_computed",
    ),
    _m(
        "ms15 certification 照合を削除",
        _S,
        "    if not load_certification(certification):\n",
        _OFF,
        "test_missing_certification_is_invalid_scorer",
        "test_stale_certification_is_invalid_scorer",
        "test_uncertified_harness_is_invalid_scorer",
    ),
    _m(
        "ms16 certification から v2 scorer を外す",
        _S,
        '        "skill_lever_scorer.py",\n',
        "",
        "test_certification_must_cover_all_six_files",
    ),
    _m(
        "ms37 certification から旧 Stage B battery を外す",
        _S,
        '        "stage_b_battery.py",\n',
        "",
        "test_certification_must_cover_all_six_files",
    ),
    _m(
        "ms38 C0 行の欠けを検査しない",
        _S,
        "    if not grid((bat.ARM_C0,)) <= present:\n",
        _OFF,
        "test_missing_c0_rows_is_not_computed",
    ),
    _m(
        "ms39 判定 arm 行の欠けを検査しない",
        _S,
        "    if not grid(bat.JUDGE_ARMS) <= present:\n",
        _OFF,
        "test_missing_judge_rows_is_not_computed",
    ),
    _m(
        "ms17 battery 検査を削除",
        _S,
        "    if battery:\n",
        _OFF,
        "test_battery_violation_is_invalid_scorer",
    ),
    _m(
        "ms18 要求条件の照合を削除",
        _S,
        "    if dict(meta) != request_meta():\n",
        _OFF,
        "test_request_meta_mismatch_is_invalid_scorer",
    ),
    _m(
        "ms19 seed 照合を削除",
        _S,
        "        if s.seed != seed:\n",
        _OFF8,
        "test_wrong_seed_is_invalid_scorer",
    ),
    _m(
        "ms20 凍結 renderer との照合を削除",
        _S,
        "        if s.prompt_sha256 != sha:\n",
        _OFF8,
        "test_v2_prompt_is_invalid_scorer",
    ),
    _m(
        "ms21 期待 prompt を v2 の lever renderer で描く",
        _S,
        "    msgs = bat.render_messages(arm, probe, v2bat.layout(r))\n",
        "    msgs = v2bat.render_messages(bat.POINTS_AS.get(arm, arm), probe, v2bat.layout(r))\n",
        "test_v2_prompt_is_invalid_scorer",
    ),
    _m(
        "ms22 再 parse 照合を削除",
        _S,
        "        if s.raw is not None and s.parsed != parse_choice(s.raw):\n",
        _OFF8,
        "test_recorded_parse_mismatch_is_invalid_scorer",
    ),
    _m(
        "ms23 重複 sample の検出を削除",
        _S,
        "        if key in seen:\n",
        _OFF8,
        "test_duplicate_sample_is_invalid_scorer",
    ),
    _m(
        "ms24 想定外 key の検出を削除",
        _S,
        "        if key not in full:\n",
        _OFF8,
        "test_unexpected_replicate_is_invalid_scorer",
    ),
    _m(
        "ms25 C0 先行の監査を削除",
        _S,
        "    if c0_calls and state_calls and max(c0_calls) > min(state_calls):\n",
        _OFF,
        "test_state_call_before_c0_is_invalid_scorer",
    ),
    _m(
        "ms26 call_index の一意性検査を削除",
        _S,
        "    if len(set(calls)) != len(calls) or any(c < 0 for c in calls):\n",
        _OFF,
        "test_duplicate_call_index_is_invalid_scorer",
    ),
    _m(
        "ms27 凍結した呼び出し順の検査を削除",
        _S,
        "        if ranks != sorted(ranks):\n",
        _OFF8,
        "test_out_of_order_state_calls_are_invalid_scorer",
    ),
    _m(
        "ms36 block 内の arm 巡回を外す",
        _S,
        "    shift = block % len(CALL_ARM_ORDER)\n",
        "    shift = 0\n",
        "test_arms_rotate_within_each_block",
        "test_block_arm_order_is_a_rotation",
    ),
    _m(
        "ms28 schema 違反を verdict 体系の外 (例外) に落とす",
        _S,
        "    except ValueError as exc:  # RecordError を含む\n",
        "    except KeyError as exc:\n",
        "test_malformed_record_is_invalid_scorer",
        "test_malformed_meta_is_invalid_scorer",
    ),
    # ---- OC 模擬
    _m(
        "ms29 clip 補正を外す (名目値 = 真の C)",
        _S,
        "    mu = nominal_effect(true_c, nu.sd, nu.bot)\n",
        "    mu = true_c\n",
        "test_simulation_plants_the_clipped_expectation",
    ),
    _m(
        "ms30 clipped normal の期待値から sd 項を落とす",
        _S,
        " + s * (_phi(a) - _phi(b))\n",
        "\n",
        "test_clipped_effect_matches_monte_carlo",
        "test_nominal_effect_inverts_clipping",
    ),
    _m(
        "ms31 模擬から ⊥ gate を外す",
        _S,
        "    verdict = np.where(bottom_gate_ok(bot), verdict, VERDICT_INVALID_BATTERY)\n",
        "    verdict = np.where(True, verdict, VERDICT_INVALID_BATTERY)\n",
        "test_simulation_applies_bottom_gate",
    ),
    _m(
        "ms32 模擬の下限検定を τ でなく 0 に",
        _S,
        "        _flip_p(d - TAU, flips, exact),\n",
        "        _flip_p(d, flips, exact),\n",
        "test_plant_is_distinct_from_threshold",
    ),
    _m(
        "ms33 sd の広い点の size 上限を緩める",
        _S,
        "SIZE_CAP_WIDE: Final[float] = 1.5 * ALPHA",
        "SIZE_CAP_WIDE: Final[float] = 1.0",
        "test_frozen_values",
        "test_size_cap_depends_on_spread",
    ),
    _m(
        "ms34 sd によらず緩い上限を使う",
        _S,
        "    if sd <= SD_EXACT_MAX:\n",
        _OFF,
        "test_size_cap_depends_on_spread",
    ),
    _m(
        "ms35 選定条件から NO_GO 側の size を外す",
        _S,
        "            and self.no_go_at_tau <= self.size_cap\n",
        "",
        "test_criteria_ok_requires_all_four",
    ),
    # ---- battery
    _m(
        "mb1  block 内巡回を削除",
        _B,
        "    return (r + j) % N_BLOCK\n",
        "    return 0\n",
        "test_success_positions_balanced_within_each_r",
        "test_block_rotation_uses_render_order_index",
    ),
    _m(
        "mb2  巡回の block 番号を描画順でなく正準 signature 順に",
        _B,
        "        shift = block_shift(lay.replicate, j)\n",
        "        shift = block_shift(lay.replicate, dev_signatures().index(sig))\n",
        "test_block_rotation_uses_render_order_index",
    ),
    _m(
        "mb3  成否を label 固定にする (weather を見ない)",
        _B,
        "            ok = act == table[sig[0]]\n",
        "            ok = act in table.values()\n",
        "test_state_has_36_rows_with_12_successes",
        "test_success_follows_the_arm_rule",
    ),
    _m(
        "mb4  失敗行を落とす (v2 lever への退化)",
        _B,
        '    return "\\n".join([STATE_HEADER, *(render_row(x) for x in state_rows(arm, lay))])\n',
        '    return "\\n".join([STATE_HEADER, *(render_row(x) for x in state_rows(arm, lay) if x.success)])\n',
        "test_max_prompt_bytes_is_pinned",
        "test_family_states_identical_outside_outcomes",
    ),
    _m(
        "mb5  族内で試行列をずらす",
        _B,
        '    if family_of(arm) == "A":\n        return canon\n',
        '    if family_of(arm) == "A":\n        return canon if arm != ARM_A_ROT else canon[1:] + canon[:1]\n',
        "test_family_states_identical_outside_outcomes",
        "test_trial_sequences_shared_within_family",
    ),
    _m(
        "mb6  族内一致検査を削除",
        _B,
        "            if mask_outcomes(render_state(a, lay)) != mask_outcomes(\n",
        "            if False and mask_outcomes(render_state(a, lay)) != mask_outcomes(\n",
        "test_family_identity_detects_shifted_trials",
    ),
    _m(
        "mb7  成功行の位置均衡検査を削除",
        _B,
        "            if len(set(counts)) != 1:\n",
        "            if False:\n",
        "test_outcome_balance_detects_unrotated_blocks",
    ),
    _m(
        "mb8  対照 filler を語彙 label にする",
        _B,
        'FILLERS: Final[tuple[str, str]] = ("wash_cups", "fold_mats")',
        'FILLERS: Final[tuple[str, str]] = ("sit_quiet", "fold_mats")',
        "test_fillers_are_out_of_vocabulary_and_parse_to_bottom",
    ),
    _m(
        "mb9  対照の失敗行 label を置き換えない",
        _B,
        "            label = act if ok or not control else FILLERS[failed.index(act)]\n",
        "            label = act\n",
        "test_control_is_filler_swap_of_judge_state",
    ),
    _m(
        "mb10 対照構成検査を削除",
        _B,
        "                if want_filler != (xc.action in FILLERS) or (\n",
        "                if False and want_filler != (xc.action in FILLERS) or (\n",
        "test_control_check_detects_unswapped_labels",
    ),
    _m(
        "mb11 byte 予算の検査を削除",
        _B,
        "    if n > v2.MAX_PROMPT_BYTES:\n",
        "    if False:\n",
        "test_prompt_budget_detects_overflow",
    ),
    _m(
        "mb12 成功行の文面を v2 lever 行から変える",
        _B,
        'OUTCOME_SUCCESS: Final[str] = f"成功 {ATTEMPTS} / 失敗 0"',
        'OUTCOME_SUCCESS: Final[str] = f"成功 {ATTEMPTS} / 失敗 00"',
        "test_success_row_text_equals_v2_lever_line",
    ),
    _m(
        "mb13 C0 にも状態を入れる",
        _B,
        "    user = probe_text if arm == ARM_C0 else",
        '    user = probe_text if arm == "none" else',
        "test_c0_has_no_state_and_shares_probe_part",
    ),
)


def _run_tests(env: dict[str, str]) -> tuple[int, list[str], bool]:
    proc = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-rf",
            "-p",
            "no:cacheprovider",
            "--deselect",
            _DESELECT,
            _TESTS,
        ],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )
    out = proc.stdout or ""
    failed = sorted(
        {
            m.group(1).split("::")[-1]
            for line in out.splitlines()
            if (m := _FAILED.match(line))
        }
    )
    collect_error = "ERROR collecting" in out or "Interrupted" in out
    return proc.returncode, failed, collect_error


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=pathlib.Path, default=None)
    args = ap.parse_args(argv)

    env = dict(os.environ, PYTHONUTF8="1")
    originals = {t: t.read_bytes() for t in (_SCORER, _BATTERY)}
    sha_before = {t: hashlib.sha256(b).hexdigest() for t, b in originals.items()}
    certified = {t.name: hashlib.sha256(t.read_bytes()).hexdigest() for t in _CERTIFIED}

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
            print(f"{mut.label:44s} {status}", flush=True)
    finally:
        for t, b in originals.items():
            t.write_bytes(b)

    restored = all(
        hashlib.sha256(t.read_bytes()).hexdigest() == sha_before[t] for t in originals
    )
    bad = [r for r in rows if r["status"] != "KILLED"]
    for r in rows:
        mark = "" if r["status"] == "KILLED" else "  <-- !!"
        print(
            f"{r['label']:44s} {r['status']:16s} {len(r.get('failed', []))} failed{mark}"
        )
    print(f"source restored (sha256 match): {restored}")
    print(f"not KILLED: {len(bad)} / {len(rows)}")
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(
                {"target_sha256": certified, "mutants": rows, "all_killed": not bad},
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
