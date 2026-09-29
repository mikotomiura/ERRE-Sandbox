#!/usr/bin/env python
"""閉ループ v5 較正 pilot の変異試験 — 判定行を壊すと、意図した test が落ちるか (pilot prereg §7).

``scripts/closed_loop_v5_battery.py`` (mb*)・``closed_loop_v5_pilot_scorer.py`` (ms*)・
``closed_loop_v5_sim.py`` (mz*)・``closed_loop_v5_select.py`` (mx*) の判定行を 1 つずつ壊し、
``tests/test_closed_loop_v5/`` を実行する。枠組みは v4 (``closed_loop_mutation_check.py``) と同じ。

* test が落ちること (exit code 非 0)。落ちなければ SURVIVED。
* 落ちた test に、その判定行を pin するために書いた test (期待集合) が含まれること。無ければ WRONG_REASON。
* collection error で落ちていないこと。
* 置換前の文字列が対象ファイルに 1 回だけ現れ、置換で内容が変わること (no-op 変異を除く)。

等価変異 (意味を変えないので kill できない) は登録しない。試走で生存した次の 2 つは等価と判断して外した:
* ε̂ の分母条件 ``len(tried) < len(opts)`` を外す: 未成功の signature では規則 (表示中) を試していない
  (試せば成功する) ので、「表示中の全てが試行済み」は起こらない。
* C の結合 key から試行行を外す: 結合の下では、成功が出るまで族内の世界は同じ行動列をとり試行集合も一致する。
  成功が出れば成功行 (世界ごとに label が違う) で key が分かれる。

変異は権威ファイル自体に当てる。先に無変異で全 test が緑であることを確認する。対象ファイルは実行中だけ
書き換わり、必ず原状復帰する (finally + sha256 照合)。import する凍結物 (v4 battery / sim、v2 / 旧 Stage B)
は変異させない (それぞれの certification が kill を確認済み)。出力は 10 ファイルの sha256 を記録する。

実行 (repo root から)::

    uv run python scripts/closed_loop_v5_mutation_check.py --out <results.json>
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
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.closed_loop_v5_select import CERTIFIED  # noqa: E402

_B = _REPO_ROOT / "scripts" / "closed_loop_v5_battery.py"
_S = _REPO_ROOT / "scripts" / "closed_loop_v5_pilot_scorer.py"
_Z = _REPO_ROOT / "scripts" / "closed_loop_v5_sim.py"
_X = _REPO_ROOT / "scripts" / "closed_loop_v5_select.py"
_TESTS = "tests/test_closed_loop_v5"
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


_REF = "test_vectorized_matches_reference"

MUTANTS: tuple[Mutant, ...] = (
    # ================================================================ battery
    _m(
        "mb1  B の回転から周の項を落とす",
        _B,
        "        return (r + t + t // N_DEV) % N_POSITIONS",
        "        return (r + t) % N_POSITIONS",
        "test_rotation",
        "test_battery_checks_pass",
    ),
    _m(
        "mb2  C の回転を v4 からずらす",
        _B,
        "    if axis == AXIS_C:\n        return (r + t) % N_POSITIONS",
        "    if axis == AXIS_C:\n        return (r + t + 1) % N_POSITIONS",
        "test_rotation",
        "test_battery_checks_pass",
    ),
    _m(
        "mb3  指示文の文言を変える",
        _B,
        "まだ試していない行動も試して、成功する行動を探すこと。",
        "まだ試していない行動を試すこと。",
        "test_frozen_constants",
    ),
    _m(
        "mb4  指示文を状況部の後ろに置く",
        _B,
        'return f"{block}\\n\\n{EXPLORE_SENTENCE}\\n\\n{situation}"',
        'return f"{block}\\n\\n{situation}\\n\\n{EXPLORE_SENTENCE}"',
        "test_messages_layout",
        "test_battery_checks_pass",
    ),
    _m(
        "mb5  B にも指示文を置く",
        _B,
        "    if axis == AXIS_C:\n        return f",
        "    if axis in AXES:\n        return f",
        "test_battery_checks_pass",
    ),
    _m(
        "mb6  pilot の r を ADR の {8..11} に戻す",
        _B,
        "PILOT_R: Final[tuple[int, ...]] = (12, 13, 14, 15)",
        "PILOT_R: Final[tuple[int, ...]] = (8, 9, 10, 11)",
        "test_frozen_constants",
        "test_battery_checks_pass",
    ),
    _m(
        "mb7  pilot の M を 4 に",
        _B,
        "PILOT_M: Final[int] = 8",
        "PILOT_M: Final[int] = 4",
        "test_frozen_constants",
    ),
    _m(
        "mb8  seed 基点を v4 と同じに",
        _B,
        "PILOT_SEED_BASE: Final[int] = 22_260_928",
        "PILOT_SEED_BASE: Final[int] = 21_260_926",
        "test_frozen_constants",
        "test_battery_checks_pass",
    ),
    _m(
        "mb9  軸の順を r によらず固定",
        _B,
        "    return AXES if r % 2 == 0 else AXES[::-1]",
        "    return AXES",
        "test_plan_order",
        "test_battery_checks_pass",
    ),
    _m(
        "mb10 B の renderer を R1+ に",
        _B,
        "    AXIS_B: v4.RENDERER_R1,",
        "    AXIS_B: v4.RENDERER_R1PLUS,",
        "test_messages_layout",
        "test_battery_checks_pass",
    ),
    _m(
        "mb11 r の重なり検査を外す",
        _B,
        "    if any(r < V5_R_MAX for r in PILOT_R):",
        "    if False:",
        "test_replicate_check_catches_overlap",
    ),
    _m(
        "mb12 v4 ループ段 seed との衝突検査を外す",
        _B,
        "    if seeds & v4_loop:",
        "    if False:",
        "test_seed_check_catches_collision",
    ),
    _m(
        "mb13 v2 probe seed との衝突検査を外す",
        _B,
        "    if seeds & v2_probe:",
        "    if False:",
        "test_seed_check_catches_collision",
    ),
    _m(
        "mb14 B の周ごとの回転変化の検査を外す",
        _B,
        "            if dev_options(AXIS_B, r, t) == dev_options(AXIS_B, r, t + N_DEV):",
        "            if False:",
        "test_rotation_check_catches_lap_invariant_b",
    ),
    _m(
        "mb15 system prompt への漏洩検査を外す",
        _B,
        "    if EXPLORE_SENTENCE in v2.SYSTEM_PROMPT:",
        "    if False:",
        "test_renderer_check_catches_leaks",
    ),
    _m(
        "mb16 指示文が答えを含む検査を外す",
        _B,
        "        if tok in EXPLORE_SENTENCE:",
        "        if False:",
        "test_renderer_check_catches_answer_in_sentence",
    ),
    _m(
        "mb17 B への指示文混入の検査を外す",
        _B,
        '                    if EXPLORE_SENTENCE in b[1]["content"]:',
        "                    if False:",
        "test_renderer_check_catches_sentence_in_b",
    ),
    _m(
        "mb18 plan の網羅検査を外す",
        _B,
        "    if len(got) != n_pilot_calls() or set(got) != want or len(set(got)) != len(got):",
        "    if False:",
        "test_plan_check_catches_missing_key",
    ),
    _m(
        "mb19 軸の順の均衡検査を外す",
        _B,
        "    if len({firsts.count(a) for a in AXES}) != 1:",
        "    if False:",
        "test_plan_check_catches_missing_key",
    ),
    _m(
        "mb20 byte 予算の検査を外す",
        _B,
        "    if n > v2.MAX_PROMPT_BYTES:",
        "    if False:",
        "test_budget_check_catches_overflow",
    ),
    _m(
        "mb21 世界名 token の検査を外す",
        _B,
        '    tokens = ("a_rot", "b_rot", "c0", "arm", "world", "r1plus", "axis")',
        "    tokens = ()",
        "test_non_leakage_catches_world_name",
    ),
    # ================================================================ scorer
    _m(
        "ms1  schedule の key 照合を外す",
        _S,
        "        if rec.key() != full[rec.call_index]:",
        "        if False:",
        "test_invalid_records",
    ),
    _m(
        "ms2  seed 照合を外す",
        _S,
        "        if rec.seed != want:",
        "        if False:",
        "test_invalid_records",
    ),
    _m(
        "ms3  transport 失敗後の継続の検査を外す",
        _S,
        "    if failed and failed[0] != records[-1].call_index:",
        "    if False:",
        "test_records_after_transport_failure_are_invalid",
    ),
    _m(
        "ms4  再 parse の照合を外す",
        _S,
        "        if rec.parsed != want:",
        "        if False:",
        "test_invalid_records",
    ),
    _m(
        "ms5  連鎖 replay の sha 照合を外す",
        _S,
        "            if rec.prompt_sha256 != messages_sha256(msgs):",
        "            if False:",
        "test_invalid_records",
        "test_chain_replay_catches_forged_choice",
    ),
    _m(
        "ms6  欠けを computed にする",
        _S,
        "    if len(records) < bat.n_pilot_calls():",
        "    if False:",
        "test_incomplete_and_transport_failure_are_not_computed",
    ),
    _m(
        "ms7  要求条件の照合を外す",
        _S,
        "    if dict(meta) != request_meta():",
        "    if False:",
        "test_record_schema_and_meta",
    ),
    _m(
        "ms8  (prompt, seed) の重複を畳まない",
        _S,
        "        if key in self.seen:\n            return",
        "        if False:\n            return",
        "test_tally_collapses_duplicates_and_takes_outer_bound",
        "test_base_counts_first_visits_without_same_weather_rows_once_per_prompt",
    ),
    _m(
        "ms9  cluster 単位の区間を捨てる",
        _S,
        "        return min(lo_a, lo_b), max(hi_a, hi_b)",
        "        return lo_a, hi_a",
        "test_tally_collapses_duplicates_and_takes_outer_bound",
    ),
    _m(
        "ms10 ŝ_changed の一致を反転",
        _S,
        "                        c.s_changed.add(rec, cur == last[sig])",
        "                        c.s_changed.add(rec, cur != last[sig])",
        "test_first_option_policy",
        "test_repeat_previous_policy",
    ),
    _m(
        "ms11 同一 prompt の再訪を prompt 変化に数える",
        _S,
        "                    elif by_sha[sig].get(rec.prompt_sha256) in opts:",
        "                    elif False:",
        "test_b_phase_return_is_same_prompt",
        "test_first_option_policy",
    ),
    _m(
        "ms23 同一 prompt の以前の応答が Ω 外でも同一 prompt に数える",
        _S,
        "                    elif by_sha[sig].get(rec.prompt_sha256) in opts:",
        "                    elif rec.prompt_sha256 in by_sha[sig]:",
        "test_same_prompt_with_oov_response_falls_to_changed",
    ),
    _m(
        "ms12 ε̂ の未試行判定を反転",
        _S,
        "                        untried = cur not in tried",
        "                        untried = cur in tried",
        "test_explore_policy_sets_eps_one",
        "test_repeat_previous_policy",
    ),
    _m(
        "ms14 λ̂ の正規化を外す",
        _S,
        "    return max(0.0, (c.h_sw.k / c.h_sw.n - h0) / (1.0 - h0))",
        "    return max(0.0, c.h_sw.k / c.h_sw.n - h0)",
        "test_lambda_and_base",
    ),
    _m(
        "ms15 h0 と h_sw を入れ替え",
        _S,
        "                        if n_sw:",
        "                        if not n_sw:",
        "test_lambda_and_base",
        "test_base_counts_first_visits_without_same_weather_rows_once_per_prompt",
    ),
    _m(
        "ms16 base の平滑化を外す",
        _S,
        "BASE_SMOOTH: Final[float] = 0.5",
        "BASE_SMOOTH: Final[float] = 0.0",
        "test_base_smoothing",
    ),
    _m(
        "ms17 ⊥ gate を ≥ 0.25 に緩める",
        _S,
        '            "rejected_bottom": max(world_bot.values()) > BOT_MAX,',
        '            "rejected_bottom": max(world_bot.values()) >= 0.25,',
        "test_bottom_gate_boundary",
    ),
    _m(
        "ms18 ⊥ 上限を世界の最小にする",
        _S,
        '            "bottom_hi": max(wilson(x.k, x.n)[1] for x in c.bottom.values()),',
        '            "bottom_hi": min(wilson(x.k, x.n)[1] for x in c.bottom.values()),',
        "test_bottom_gate_boundary",
    ),
    _m(
        "ms19 Ω 外の判定を反転",
        _S,
        "                c.oov[world].add(rec, cur not in opts)",
        "                c.oov[world].add(rec, cur in opts)",
        "test_oov_rate",
    ),
    _m(
        "ms20 窓の境界をずらす",
        _S,
        "            if t >= t_max:",
        "            if t > t_max:",
        "test_windows_restrict_steps",
    ),
    _m(
        "ms21 Wilson の z を片側にする",
        _S,
        "Z95: Final[float] = 1.959964",
        "Z95: Final[float] = 1.644854",
        "test_wilson_known_values",
    ),
    _m(
        "ms22 重複の代表を call_index 順にしない",
        _S,
        "            first = rep[(rec.prompt_sha256, rec.seed)] == rec.call_index",
        "            first = True",
        "test_duplicate_representative_is_first_call",
    ),
    # ================================================================ sim
    _m(
        "mz1  世界間の乱数結合を外す",
        _Z,
        "        u = v4sim._coupled(rng.random((n, rr, n_w, N_U)), keys)",
        "        u = rng.random((n, rr, n_w, N_U))",
        _REF,
    ),
    _m(
        "mz3  同一 prompt の記憶を使わない",
        _Z,
        "        same_prompt = np.all(mk == now, axis=-1) & (mem_pos >= 0)",
        "        same_prompt = np.all(mk == now, axis=-1) & (mem_pos >= 99)",
        _REF,
        "test_same_prompt_memory_is_used_in_b",
    ),
    _m(
        "mz4  同 weather の分岐で λ を無視",
        _Z,
        "(u[..., U_SW] < beh.lam_dev)",
        "(u[..., U_SW] < 1.0)",
        _REF,
    ),
    _m(
        "mz5  写しの分岐を外す",
        _Z,
        "            pick = np.where(has_prev & (u[..., U_COPY] < beh.rho), prev_pos, pick)",
        "            pick = pick",
        _REF,
    ),
    _m(
        "mz6  探索の率を半分に",
        _Z,
        "            explore = untried_any & (u[..., U_EPS] < beh.eps)",
        "            explore = untried_any & (u[..., U_EPS] < beh.eps / 2)",
        _REF,
        "test_explore_eps_raises_untried_rate",
    ),
    _m(
        "mz7  base 制限の未試行選択を一様にする",
        _Z,
        "                w_un = pb * ~tr",
        "                w_un = (~tr).astype(float)",
        _REF,
        "test_untried_modes_differ",
    ),
    _m(
        "mz8  成功済みでも Ω 外に落とす",
        _Z,
        "        oov = acted & ~done & (u[..., U_OOV] < beh.oov)",
        "        oov = acted & (u[..., U_OOV] < beh.oov)",
        _REF,
    ),
    _m(
        "mz9  成功済みの規則を外す",
        _Z,
        "        pick = np.where(done, rp, pick)",
        "        pick = pick",
        _REF,
    ),
    _m(
        "mz10 ループ段の ⊥ を gate に数えない",
        _Z,
        "        loop_bot += is_bot",
        "        loop_bot += 0",
        "test_bottom_gate_in_verdicts",
    ),
    _m(
        "mz11 k_rep を無視",
        _Z,
        "    reps = rng.binomial(k - 1, k_rep, size=shape)",
        "    reps = rng.binomial(k - 1, 0.0, size=shape)",
        "test_k_rep_repeats_first_draw",
    ),
    _m(
        "mz12 probe の植え付けを半分に",
        _Z,
        "        lvec[nq] + pp.sd * rng.standard_normal((n_sims, r_count, n_w, 1)), -1.0, 1.0",
        "        lvec[nq] / 2 + pp.sd * rng.standard_normal((n_sims, r_count, n_w, 1)), -1.0, 1.0",
        "test_closed_form_matches_draws",
        "test_verdict_directions_and_planting",
    ),
    _m(
        "mz13 閉形式から Ω 外を落とす",
        _Z,
        "    diff = live * (ep - em + (1.0 - ep - em) * (1.0 - cfg.oov) * (pw - pf))",
        "    diff = live * (ep - em + (1.0 - ep - em) * (pw - pf))",
        "test_expected_units_equals_v4",
    ),
    _m(
        "mz14 検定の向きを入れ替え",
        _Z,
        "        _flip_p(d - TAU, flips, exact), _flip_p(TAU - d, flips, exact), comps",
        "        _flip_p(TAU - d, flips, exact), _flip_p(d - TAU, flips, exact), comps",
        "test_verdict_directions_and_planting",
    ),
    _m(
        "mz15 植える効果を τ にする",
        _Z,
        "    k_plant = curve.solve(v4sim.DELTA_PLANT, r_count)",
        "    k_plant = curve.solve(TAU, r_count)",
        "test_verdict_directions_and_planting",
    ),
    _m(
        "mz16 seed の JSON を正準化しない",
        _Z,
        "        [SIM_SEED, *parts], sort_keys=True,",
        "        [SIM_SEED, *parts], sort_keys=False,",
        "test_point_seed_is_canonical",
    ),
    _m(
        "mz17 同一 prompt の反復で s_same を無視",
        _Z,
        "        pick = np.where(same_prompt & (u[..., U_REP] < beh.s_same), mem_pos, pick)",
        "        pick = np.where(same_prompt & (u[..., U_REP] < beh.s_changed), mem_pos, pick)",
        _REF,
    ),
    # ================================================================ select
    _m(
        "mx1  B の保守値を下限にする",
        _X,
        '        out["s_changed"] = float(m["s_changed"]["hi"])',
        '        out["s_changed"] = float(m["s_changed"]["lo"])',
        "test_conservative_values",
    ),
    _m(
        "mx2  C の保守値を上限にする",
        _X,
        '        out["eps"] = float(m["eps"]["lo"])',
        '        out["eps"] = float(m["eps"]["hi"])',
        "test_conservative_values",
    ),
    _m(
        "mx3  Ω 外の床を外す",
        _X,
        '        "oov": max(OOV_FLOOR, float(m["oov_hi"])),',
        '        "oov": float(m["oov_hi"]),',
        "test_conservative_values",
    ),
    _m(
        "mx4  b = 0 の格子点を外す",
        _X,
        '            sorted({0.0, cv["bot_hi"]}),',
        '            sorted({cv["bot_hi"]}),',
        "test_grid",
    ),
    _m(
        "mx5  k_rep の格子を 0 だけに",
        _X,
        "K_REPS: Final[tuple[float, ...]] = (0.0, K_REP_V4)",
        "K_REPS: Final[tuple[float, ...]] = (0.0,)",
        "test_grid",
    ),
    _m(
        "mx6  候補を呼び出し数の逆順に",
        _X,
        "        key=lambda x: (v4bat.n_main_calls(*x), x[2], x[0]),",
        "        key=lambda x: (-v4bat.n_main_calls(*x), x[2], x[0]),",
        "test_candidate_order",
    ),
    _m(
        "mx7  軸を C → B の順に",
        _X,
        "        for axis in (a for a in bat.AXES if a not in rejected[str(m)]):",
        "        for axis in (a for a in bat.AXES[::-1] if a not in rejected[str(m)]):",
        "test_smallest_candidate_wins_and_tie_goes_to_b",
    ),
    _m(
        "mx8  screening 不合格でも本確認へ",
        _X,
        "            if not ok:\n                continue\n",
        "            if False:\n                continue\n",
        "test_door_close",
    ),
    _m(
        "mx9  採用後も探索を続ける",
        _X,
        "        if chosen is not None:\n            break\n",
        "        if False:\n            break\n",
        "test_smallest_candidate_wins_and_tie_goes_to_b",
    ),
    _m(
        "mx10 不採用の軸も審査する",
        _X,
        "        for axis in (a for a in bat.AXES if a not in rejected[str(m)]):",
        "        for axis in (a for a in bat.AXES if a not in ()):",
        "test_rejected_axis_is_skipped_per_m",
    ),
    _m(
        "mx11 dev 段の測定量を M = 4 の窓で固定",
        _X,
        "            beh = behaviour(axis, self.measures[str(m)][axis], dp)",
        '            beh = behaviour(axis, self.measures["4"][axis], dp)',
        "test_measures_are_taken_from_the_candidate_window",
    ),
    _m(
        "mx12 λ̂ が無いとき v4 の値を使う",
        _X,
        "        else (0.0 if lam_pilot is None else float(lam_pilot))",
        "        else (V4_LAM_DEV if lam_pilot is None else float(lam_pilot))",
        "test_behaviour_uses_conservative_values",
    ),
    _m(
        "mx13 v4 の較正値を書き換える",
        _X,
        "V4_LAM_DEV: Final[float] = 0.43387853429694445",
        "V4_LAM_DEV: Final[float] = 0.45",
        "test_v4_calibration_constants_are_observed",
    ),
    _m(
        "mx14 最初の違反で不合格にしない",
        _X,
        '                if not row["ok"]:\n                    return False, rows',
        "                if False:\n                    return False, rows",
        "test_end_to_end_small_grid",
    ),
    _m(
        "mx15 certification の照合を外す",
        _X,
        "    if certification is not None and not load_certification(certification):",
        "    if False:",
        "test_certification_gate_of_the_mapping",
    ),
    _m(
        "mx16 計算できない pilot でも写像する",
        _X,
        '    if report["status"] != ps.STATUS_COMPUTED:',
        "    if False:",
        "test_not_computed_pilot_is_not_mapped",
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
    targets = (_B, _S, _Z, _X)
    originals = {t: t.read_bytes() for t in targets}
    sha_before = {t: hashlib.sha256(b).hexdigest() for t, b in originals.items()}
    certified = {
        name: hashlib.sha256((_REPO_ROOT / "scripts" / name).read_bytes()).hexdigest()
        for name in CERTIFIED
    }

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
