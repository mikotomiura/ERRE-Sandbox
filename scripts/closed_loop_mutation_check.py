#!/usr/bin/env python
"""閉ループ分散 pilot の変異試験 — 判定行を壊すと、意図した test が落ちるか (prereg v4 §7).

``scripts/closed_loop_scorer.py`` (ms*)・``scripts/closed_loop_battery.py`` (mb*)・
``scripts/closed_loop_sim.py`` (mz*) の判定行を 1 つずつ壊し、``tests/test_closed_loop/`` を実行する。
枠組みは v2 / v3 (``skill_experience_mutation_check.py``) と同じ。各変異について次を確認する。

* test が落ちること (exit code 非 0)。落ちなければ SURVIVED。
* 落ちた test に、その判定行を pin するために書いた test (期待集合) が含まれること。
  含まれなければ WRONG_REASON。
* collection error で落ちていないこと。
* 置換前の文字列が対象ファイルに 1 回だけ現れ、置換で内容が変わること (no-op 変異を除く)。

変異は権威ファイル自体 (判定・renderer・模擬の本体) に当てる。先に無変異で全 test が緑であることを確認する。
対象ファイルは実行中だけ書き換わり、必ず原状復帰する (finally + sha256 照合)。import する凍結 v2 の
純粋関数は変異させない (v2 の certification が既に kill を確認している)。本 harness の出力は、v2 / 旧
Stage B のファイルを含む 7 ファイルの sha256 を記録して、その同一性に結び付ける。

実行 (repo root から)::

    uv run python scripts/closed_loop_mutation_check.py --out <results.json>
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
_SCORER = _REPO_ROOT / "scripts" / "closed_loop_scorer.py"
_BATTERY = _REPO_ROOT / "scripts" / "closed_loop_battery.py"
_SIM = _REPO_ROOT / "scripts" / "closed_loop_sim.py"
_CERTIFIED = (
    _SCORER,
    _BATTERY,
    _SIM,
    _REPO_ROOT / "scripts" / "skill_lever_scorer.py",
    _REPO_ROOT / "scripts" / "skill_lever_battery.py",
    _REPO_ROOT / "scripts" / "stage_b_scorer.py",
    _REPO_ROOT / "scripts" / "stage_b_battery.py",
)
_TESTS = "tests/test_closed_loop"
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
_Z = _SIM

MUTANTS: tuple[Mutant, ...] = (
    # ================================================================ scorer
    # ---- 連鎖 replay
    _m(
        "ms1  連鎖 replay の loop 段 sha 照合を削除",
        _S,
        "            if rec.prompt_sha256 != messages_sha256(msgs):\n"
        '                out.append(f"{world} r={r} t={n}',
        '            if False:\n                out.append(f"{world} r={r} t={n}',
        "test_chain_detects_tampered_prompt",
        "test_chain_detects_forged_outcome",
    ),
    _m(
        "ms2  連鎖 replay で状態を更新しない (記録の行動を使わない)",
        _S,
        "            state = bat.update(state, world, bat.loop_signature(r, n), rec.parsed)\n",
        "            state = state\n",
        "test_full_lookup_is_pass_with_claim",
        "test_chain_replay_reconstructs_final_states",
    ),
    _m(
        "ms3  probe の sha 照合 (終状態から) を削除",
        _S,
        "            if rec.prompt_sha256 != messages_sha256(msgs):\n"
        "                out.append(\n"
        '                    f"call {rec.call_index}: probe prompt',
        "            if False:\n"
        "                out.append(\n"
        '                    f"call {rec.call_index}: probe prompt',
        "test_chain_detects_probe_from_wrong_state",
    ),
    _m(
        "ms4  C0 の sha 照合を削除",
        _S,
        "            if rec.prompt_sha256 != want:\n",
        "            if False:\n",
        "test_chain_detects_tampered_c0",
    ),
    _m(
        "ms5  replay の sha 照合を削除",
        _S,
        "            if target is None or target.prompt_sha256 != rec.prompt_sha256:\n",
        "            if False:\n",
        "test_chain_detects_replay_prompt_mismatch",
    ),
    # ---- schedule 監査
    _m(
        "ms6  plan の key 照合を削除",
        _S,
        "        if (got.phase, got.world, got.replicate, got.step, got.probe_id, got.k) != (\n",
        "        if False and (got.phase, got.world, got.replicate, got.step, got.probe_id, got.k) != (\n",
        "test_schedule_swapped_worlds_is_invalid_scorer",
        "test_state_before_c0_is_invalid_scorer",
    ),
    _m(
        "ms7  接頭辞 (call_index = 0..n-1) の検査を削除",
        _S,
        "    if [x.call_index for x in records] != list(range(len(records))):\n",
        "    if False:\n",
        "test_schedule_gap_is_invalid_scorer",
        "test_physical_line_swap_is_invalid_scorer",
    ),
    _m(
        "ms8  seed の照合を削除",
        _S,
        "        if rec.seed != expected_seed(want):\n",
        "        if False:\n",
        "test_wrong_seed_is_invalid_scorer",
        "test_probe_seed_is_checked",
    ),
    _m(
        "ms9  transport 失敗の後に続く記録を検査しない",
        _S,
        "    if failed and failed[0] != ordered[-1].call_index:\n",
        "    if False:\n",
        "test_records_after_transport_failure_are_invalid",
    ),
    _m(
        "ms10 再 parse の照合を削除",
        _S,
        "        if rec.parsed != want:\n",
        "        if False:\n",
        "test_parse_mismatch_is_invalid_scorer",
    ),
    # ---- ⊥ gate
    _m(
        "ms11 ループ段の ⊥ gate を削除",
        _S,
        "    if max(loop_bot.values()) > LOOP_BOT_MAX:\n",
        "    if False:\n",
        "test_loop_bottom_rate_is_invalid_battery",
    ),
    _m(
        "ms12 ループ段の ⊥ の上限を緩める",
        _S,
        "LOOP_BOT_MAX: Final[float] = BOT_MAX",
        "LOOP_BOT_MAX: Final[float] = 0.5",
        "test_loop_bottom_rate_is_invalid_battery",
    ),
    _m(
        "ms13 C0 ⊥ gate を削除",
        _S,
        "    if c0_bot > BOT_MAX:\n",
        "    if False:\n",
        "test_c0_bottom_rate_is_invalid_battery",
        "test_c0_gate_precedes_missing_state_rows",
    ),
    _m(
        "ms14 C0 gate を状態側の完了の後にする",
        _S,
        "    if len(records) < n_c0():\n",
        "    if len(records) < n_main():\n",
        "test_c0_gate_precedes_missing_state_rows",
    ),
    _m(
        "ms15 probe の ⊥ gate を削除",
        _S,
        "    if not bool(bottom_gate_ok(bot)):\n",
        "    if False:\n",
        "test_probe_bottom_rate_is_invalid_battery",
        "test_family_bottom_gap_is_invalid_battery",
    ),
    # ---- 計算しない
    _m(
        "ms16 transport 失敗を ⊥ に畳む",
        _S,
        "    if any(x.raw is None for x in records):\n",
        "    if False:\n",
        "test_transport_failure_is_not_computed",
    ),
    _m(
        "ms17 本体の欠けを検査しない",
        _S,
        "    if len(records) < n_main():\n",
        "    if False:\n",
        "test_main_incomplete_is_not_computed",
    ),
    # ---- 判定
    _m(
        "ms18 PASS の下限を τ でなく 0 に (p_zero で判定)",
        _S,
        "    verdict = str(decide(np.float64(p_lower), np.float64(p_upper), comps))\n",
        "    verdict = str(decide(np.float64(p_zero), np.float64(p_upper), comps))\n",
        "test_small_effect_is_no_go",
    ),
    _m(
        "ms19 NO_GO を出さない",
        _S,
        "    verdict = str(decide(np.float64(p_lower), np.float64(p_upper), comps))\n",
        "    verdict = str(decide(np.float64(p_lower), np.float64(1.0), comps))\n",
        "test_small_effect_is_no_go",
        "test_state_blind_policy_is_no_go_with_zero_units",
    ),
    _m(
        "ms20 4 成分の符号条件を外す",
        _S,
        "    comps = s.mean(axis=1)\n",
        "    comps = np.ones(len(bat.WORLDS))\n",
        "test_one_world_failure_is_not_pass",
    ),
    # ---- coverage と claim
    _m(
        "ms21 coverage を gate にする",
        _S,
        '    report["claim_branch"] = claim_branch(verdict, cov)\n',
        '    verdict = verdict if cov["weather_coverage"] >= COVERAGE_BRANCH else '
        "VERDICT_INVALID_BATTERY\n"
        '    report["claim_branch"] = claim_branch(verdict, cov)\n',
        "test_no_go_with_low_coverage_is_exploration_limited",
    ),
    _m(
        "ms22 claim 分岐の境界を変える",
        _S,
        '        if cov["weather_coverage"] < COVERAGE_BRANCH:\n',
        '        if cov["weather_coverage"] <= COVERAGE_BRANCH:\n',
        "test_claim_branch_table",
    ),
    _m(
        "ms23 PASS の文から coverage を落とす",
        _S,
        "        f\"終点の weather coverage = {cov['weather_coverage']:.3f} \"\n",
        '        f""\n',
        "test_full_lookup_is_pass_with_claim",
    ),
    _m(
        "ms24 PASS の文を出さない",
        _S,
        '        report["claim_text"] = pass_claim_text(c, cov)\n',
        '        report["claim_text"] = None\n',
        "test_full_lookup_is_pass_with_claim",
    ),
    # ---- INVALID_SCORER の照合
    _m(
        "ms25 certification から sim を外す",
        _S,
        '        "closed_loop_sim.py",\n',
        "",
        "test_certification_covers_all_seven_files",
        "test_stale_certification_is_invalid_scorer",
    ),
    _m(
        "ms26 certification 照合を削除",
        _S,
        "    if not load_certification(certification):\n",
        "    if False:\n",
        "test_missing_certification_is_invalid_scorer",
        "test_stale_certification_is_invalid_scorer",
        "test_uncertified_harness_is_invalid_scorer",
    ),
    _m(
        "ms27 battery 検査を削除",
        _S,
        "    if battery:\n",
        "    if False:\n",
        "test_battery_violation_is_invalid_scorer",
    ),
    _m(
        "ms28 要求条件の照合を削除",
        _S,
        "    if dict(meta) != request_meta():\n",
        "    if False:\n",
        "test_meta_mismatch_is_invalid_scorer",
    ),
    _m(
        "ms29 凍結 renderer を変える",
        _S,
        "FROZEN_RENDERER: Final[str] = bat.RENDERER_R1PLUS",
        "FROZEN_RENDERER: Final[str] = bat.RENDERER_R1",
        "test_frozen_design_values",
    ),
    _m(
        "ms30 決定性の格下げ規則を外す",
        _S,
        '        "exact_cancellation": bool(rates) and all(x == 1.0 for x in rates),\n',
        '        "exact_cancellation": True,\n',
        "test_determinism_rates",
    ),
    _m(
        "ms31 phase と欄の組み合わせを検査しない",
        _S,
        "    if not ok:\n",
        "    if False:\n",
        "test_record_schema_violations",
    ),
    _m(
        "ms32 int 欄の型を検査しない",
        _S,
        "        if not _is_int(obj[f]):\n",
        "        if False:\n",
        "test_record_schema_violations",
    ),
    # ================================================================ battery
    _m(
        "mb1  Ω_dev の巡回を削除",
        _B,
        "    shift = (r + t) % N_POSITIONS\n",
        "    shift = 0\n",
        "test_dev_options_are_world_rules_rotated",
    ),
    _m(
        "mb2  Ω_dev の巡回を r だけにする",
        _B,
        "    shift = (r + t) % N_POSITIONS\n",
        "    shift = r % N_POSITIONS\n",
        "test_dev_options_are_world_rules_rotated",
    ),
    _m(
        "mb3  ループの seed を probe の値域に重ねる",
        _B,
        "    return LOOP_SEED_BASE + LOOP_SEED_STRIDE * r + t\n",
        "    return v2.SEED_BASE + LOOP_SEED_STRIDE * r + t\n",
        "test_loop_seed_shared_and_disjoint_from_probe_seeds",
    ),
    _m(
        "mb4  世界の順を回転しない",
        _B,
        "    shift = r % len(WORLDS)\n",
        "    shift = 0\n",
        "test_world_order_rotates_per_replicate",
    ),
    _m(
        "mb5  ⊥ を成功にする",
        _B,
        "    return choice is not None and choice == rule(world)[sig[0]]\n",
        "    return choice is None or choice == rule(world)[sig[0]]\n",
        "test_update_success_bottom_and_oov",
    ),
    _m(
        "mb6  Ω 外の label を試行に数えない",
        _B,
        "    if choice is not None and choice in ACTIONS:\n",
        "    if choice is not None and choice in dev_omega(sig[0]):\n",
        "test_update_success_bottom_and_oov",
    ),
    _m(
        "mb7  失敗も成功行として描く",
        _B,
        "        if sig in state.succeeded\n",
        "        if any(s == sig for s, _ in state.tried)\n",
        "test_rows_follow_pi_r_and_only_presence_changes",
    ),
    _m(
        "mb8  試行 label を語彙順でなく逆順に",
        _B,
        "        acts = [a for a in ACTIONS if (sig, a) in state.tried]\n",
        "        acts = [a for a in reversed(ACTIONS) if (sig, a) in state.tried]\n",
        "test_tried_labels_in_action_order_not_trial_order",
    ),
    _m(
        "mb9  行の文言に回数を入れる",
        _B,
        'SUCCESS_MARK: Final[str] = "(成功あり)"',
        'SUCCESS_MARK: Final[str] = "(成功 1 回)"',
        "test_row_wording_is_pinned",
    ),
    _m(
        "mb10 空状態の文字列を世界ごとに変える",
        _B,
        '        return "\\n".join([STATE_HEADER, *(succ or [EMPTY_R1])])\n',
        '        return "\\n".join([STATE_HEADER, *(succ or [f"{EMPTY_R1}{len(world)}"])])\n',
        "test_empty_state_strings",
    ),
    _m(
        "mb11 byte 予算の検査を削除",
        _B,
        "    if n > v2.MAX_PROMPT_BYTES:\n",
        "    if False:\n",
        "test_prompt_budget_detects_overflow",
    ),
    _m(
        "mb12 seed の衝突検査を削除",
        _B,
        "    if loop & probe:\n",
        "    if False:\n",
        "test_seed_check_detects_collision",
    ),
    _m(
        "mb13 Ω_dev の巡回の均衡検査を削除",
        _B,
        "            if len(set(counts)) != 1:\n",
        "            if False:\n",
        "test_dev_rotation_check_detects_fixed_order",
    ),
    _m(
        "mb14 世界名の漏洩検査を削除",
        _B,
        '        problems.extend(f"prompt contains {tok!r}" for tok in tokens if tok in low)\n',
        "        problems.extend([])\n",
        "test_non_leakage_clean_and_detects_arm_name",
    ),
    _m(
        "mb15 C0 に状態を入れる",
        _B,
        "    return v2.render_messages(ARM_C0, v2.lever_probes()[qi], v2.layout(r))\n",
        '    return v2.render_messages("A", v2.lever_probes()[qi], v2.layout(r))\n',
        "test_c0_is_v2_c0_and_situation_matches_v2_probe",
    ),
    _m(
        "mb16 ループ段の block 内の世界順を逆にする",
        _B,
        "            PlanKey(PHASE_LOOP, w, r, step=t) for t in range(n_steps(m)) for w in order\n",
        "            PlanKey(PHASE_LOOP, w, r, step=t) for t in range(n_steps(m)) for w in order[::-1]\n",
        "test_plan_layout_and_counts",
    ),
    _m(
        "mb17 replay の登録部分集合を変える",
        _B,
        "    out += [PlanKey(PHASE_LOOP, w, r, step=last) for w in order]\n",
        "    out += [PlanKey(PHASE_LOOP, w, r, step=last - 1) for w in order]\n",
        "test_replay_targets",
    ),
    _m(
        "mb18 世界順の均衡検査を削除",
        _B,
        '    return [] if len(set(counts.values())) == 1 else ["world order is unbalanced"]\n',
        "    return []\n",
        "test_world_order_check_detects_unrotated",
    ),
    # ================================================================ sim
    _m(
        "mz1  同一状態の世界で一様乱数を共有しない",
        _Z,
        "            src[:, :, i] = np.where(same, j, src[:, :, i])\n",
        "            src[:, :, i] = src[:, :, i]\n",
        "test_identical_states_share_uniforms",
        "test_vectorized_dev_matches_reference",
    ),
    _m(
        "mz2  R1+ の状態 key から試行を落とす",
        _Z,
        "    if tried is not None:\n        parts.append(",
        "    if False:\n        parts.append(",
        "test_state_keys_follow_prompt_identity",
        "test_vectorized_dev_matches_reference",
    ),
    _m(
        "mz27 状態 key から世界の印を落とす (Codex HIGH の再発)",
        _Z,
        "    flag = np.where(succ.any(-1), world, -1)[..., None]\n",
        "    flag = np.full(succ.shape[:3], -1)[..., None]\n",
        "test_state_keys_follow_prompt_identity",
        "test_vectorized_dev_matches_reference",
    ),
    _m(
        "mz3  γ を κ から切り離す",
        _Z,
        "    gamma = cfg.gamma_factor * kappa\n",
        "    gamma = cfg.gamma_factor\n",
        "test_vectorized_dev_matches_reference",
    ),
    _m(
        "mz4  graded を flat にする",
        _Z,
        "GRADED: Final[dict[int, float]] = {0: 0.0, 1: 0.5, 2: 0.75, 3: 0.75, 4: 1.0}",
        "GRADED: Final[dict[int, float]] = {0: 0.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0}",
        "test_lambda_versions_and_graded_is_lower",
    ),
    _m(
        "mz5  同じ signature の行を特別扱いしない",
        _Z,
        "        p_follow = np.where(same, kappa, lam_vec[np.minimum(n_same_w, 4)])\n",
        "        p_follow = lam_vec[np.minimum(n_same_w, 4)]\n",
        "test_vectorized_dev_matches_reference",
    ),
    _m(
        "mz6  R1+ の回避を削除",
        _Z,
        "            weights = pb * np.where(tr, 1.0 - gamma, 1.0)\n",
        "            weights = pb\n",
        "test_vectorized_dev_matches_reference",
        "test_r1plus_avoidance_raises_coverage_and_gamma_factor",
    ),
    _m(
        "mz7  模擬の ⊥ gate を削除",
        _Z,
        "    verdict = np.where(\n        pipeline_gates(c0_bot, loop_bot, probe_bot), verdict, VERDICT_INVALID_BATTERY\n    )\n",
        "    verdict = verdict\n",
        "test_bottom_gates_act_in_simulation",
    ),
    _m(
        "mz8  模擬のループ段 ⊥ gate を削除",
        _Z,
        "    loop_ok = np.all(loop_bot <= BOT_MAX, axis=-1)\n",
        "    loop_ok = True\n",
        "test_pipeline_gates_each_stage",
    ),
    _m(
        "mz9  閉形式の負側を 0 に",
        _Z,
        "    return pos(mean), pos(-mean)\n",
        "    return pos(mean), 0.0\n",
        "test_clipped_parts_match_monte_carlo",
        "test_expected_c_at_kappa_zero_is_zero",
    ),
    _m(
        "mz10 抽選で e < 0 の foil 質量を落とす",
        _Z,
        "    p_f = base_live * pf + np.where(e < 0, live * mix, 0.0)\n",
        "    p_f = base_live * pf\n",
        "test_expected_c_matches_sampled_mean",
    ),
    _m(
        "mz11 植えられない点を検出しない",
        _Z,
        "        if ec[-1] < target:\n",
        "        if False:\n",
        "test_curve_solve_interpolates_and_detects_unreachable",
        "test_unreachable_plant_fails_design",
    ),
    _m(
        "mz12 到達可能を合格条件から外す",
        _Z,
        "            self.reachable\n",
        "            True\n",
        "test_criteria_requires_reachability_planting_and_all_four",
    ),
    _m(
        "mz24 植えた C の再確認を合格条件から外す",
        _Z,
        "            and self.planted\n",
        "",
        "test_criteria_requires_reachability_planting_and_all_four",
    ),
    _m(
        "mz25 fixture の硬い gate を緩める",
        _Z,
        "FIXTURE_HARD: Final[float] = TAU / 2.0",
        "FIXTURE_HARD: Final[float] = TAU",
        "test_fixture_gate_is_positive_side_only",
    ),
    _m(
        "mz26 τ/4 を超えた fixture を列挙しない",
        _Z,
        '    flagged = sorted({x["fixture"] for x in registered if _upper(x) >= FIXTURE_GATE})\n',
        "    flagged = []\n",
        "test_fixture_gate_is_positive_side_only",
    ),
    _m(
        "ms33 PASS の文に列挙 fixture の注記を入れない",
        _S,
        "        f\"{FLAGGED_NOTE if FLAGGED_FIXTURES else ''}\"",
        '        f""',
        "test_full_lookup_is_pass_with_claim",
    ),
    _m(
        "mz28 Ω 外を試行に数えない (模擬)",
        _Z,
        "        acted = ~is_bot\n",
        "        acted = ~is_bot & ~oov\n",
        "test_out_of_omega_is_tried_but_never_success",
        "test_vectorized_dev_matches_reference",
    ),
    _m(
        "mz13 sd 広域の size 上限を狭い方にする",
        _Z,
        "    return SIZE_CAP_WIDE\n",
        "    return ALPHA + mc_margin(n_sims)\n",
        "test_size_cap_rule",
    ),
    _m(
        "mz14 size 上限の sd 境界",
        _Z,
        "    if sd <= SD_EXACT_MAX:\n",
        "    if sd < SD_EXACT_MAX:\n",
        "test_size_cap_rule",
    ),
    _m(
        "mz15 null の power 条件を削除",
        _Z,
        "            and self.no_go_at_zero >= POWER_TARGET\n",
        "",
        "test_criteria_requires_reachability_planting_and_all_four",
    ),
    _m(
        "mz16 τ での PASS の size 条件を削除",
        _Z,
        "            and self.pass_at_tau <= self.size_cap\n",
        "",
        "test_criteria_requires_reachability_planting_and_all_four",
    ),
    _m(
        "mz17 fixture gate を両側にする",
        _Z,
        "    worst = max(registered, key=_upper)\n",
        '    worst = max(registered, key=lambda x: abs(x["mean"]) + 3.0 * x["se"])\n',
        "test_fixture_gate_is_positive_side_only",
    ),
    _m(
        "mz18 fixture gate に陽性対照を含める",
        _Z,
        '    registered = [x for x in rows if x["fixture"] != POSITIVE_CONTROL[0]]\n',
        "    registered = list(rows)\n",
        "test_fixture_gate_is_positive_side_only",
    ),
    _m(
        "mz19 実測 base の定数を変える",
        _Z,
        "MEASURED_BETA: Final[tuple[float, ...]] = (-1.515986,",
        "MEASURED_BETA: Final[tuple[float, ...]] = (-1.415986,",
        "test_refit_equals_sealed_constants",
    ),
    _m(
        "mz20 Ω 外の割合を変える",
        _Z,
        "OOV: Final[float] = 0.05",
        "OOV: Final[float] = 0.0",
        "test_constants_are_pinned",
    ),
    _m(
        "mz21 参照実装の追従を壊す",
        _Z,
        "    if u.follow < p_follow:\n",
        "    if u.follow <= 0.0:\n",
        "test_vectorized_dev_matches_reference",
    ),
    _m(
        "mz22 植える目標を 2τ でなく τ に",
        _Z,
        "    k_plant = curve.solve(DELTA_PLANT, r_count)\n",
        "    k_plant = curve.solve(TAU, r_count)\n",
        "test_unreachable_plant_fails_design",
    ),
    _m(
        "mz23 近傍 fixture を登録から外す",
        _Z,
        '    "F8_neighbor": f_neighbor,\n',
        "",
        "test_fixture_registry",
        "test_neighbor_fixture_points_to_the_foil",
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
    ap.add_argument("--only", default=None, help="label の接頭辞で絞る (開発用)")
    args = ap.parse_args(argv)

    env = dict(os.environ, PYTHONUTF8="1")
    targets = (_SCORER, _BATTERY, _SIM)
    originals = {t: t.read_bytes() for t in targets}
    sha_before = {t: hashlib.sha256(b).hexdigest() for t, b in originals.items()}
    certified = {t.name: hashlib.sha256(t.read_bytes()).hexdigest() for t in _CERTIFIED}

    code, failed, _ = _run_tests(env)
    if code != 0:
        print(f"ERROR: baseline (無変異) が緑でない: {failed}")
        return 2

    mutants = [m for m in MUTANTS if args.only is None or m.label.startswith(args.only)]
    rows: list[dict[str, object]] = []
    try:
        for mut in mutants:
            src = originals[mut.target].decode("utf-8")
            n = src.count(mut.old)
            if n != 1 or mut.old == mut.new:
                status = "NO_OP" if mut.old == mut.new else f"ANCHOR x{n}"
                rows.append({"label": mut.label, "status": status})
                print(f"{mut.label:44s} {status}", flush=True)
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
        if args.only is not None:
            print("ERROR: --only の結果は certification にしない")
            return 2
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
