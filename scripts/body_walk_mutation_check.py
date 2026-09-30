#!/usr/bin/env python
"""探索を身体側へ (b) 較正 pilot の変異試験 — 判定行を壊すと、意図した test が落ちるか (pilot prereg §7).

``scripts/body_walk_battery.py`` (mb*)・``body_walk_pilot_scorer.py`` (ms*)・``body_walk_sim.py`` (mz*)・
``body_walk_select.py`` (mx*) の判定行を 1 つずつ壊し、``tests/test_body_walk/`` を実行する。枠組みは v5
(``closed_loop_v5_mutation_check.py``) と同じ。

* test が落ちること (exit code 非 0)。落ちなければ SURVIVED。
* 落ちた test に、その判定行を pin するために書いた test (期待集合) が含まれること。無ければ WRONG_REASON。
* collection error で落ちていないこと。
* 置換前の文字列が対象ファイルに 1 回だけ現れ、置換で内容が変わること (no-op 変異を除く)。

等価変異 (意味を変えないので kill できない) は登録しない。判断して外したもの:
* 同一 prompt の記憶の key を成功集合の bitmask から成功数に替える: 連鎖の中で成功集合は単調に増えるので、
  同じ連鎖・同じ signature の 2 回の訪問で「数が等しい ⇔ 集合が等しい」。key は描画状態そのもので、数の近似と一致する
  (bitmask を使うのは、単調性に依らずに厳密であることを構造で示すため)。
* scorer の ŝ_same で、比べる相手を「同一 prompt の直近の応答」から「直近の応答」に替える: 同じく単調性から、
  同一 prompt の以前の訪問があれば、⊥ でない直近の訪問も同一 prompt である。
* base の正規化 ``p / p.sum()`` を外す: base の表は Ω_dev の 4 label 上で和が 1 で、表示の 4 選択肢は Ω_dev と同じ集合。

変異は権威ファイル自体に当てる。先に無変異で全 test が緑であることを確認する。対象ファイルは実行中だけ
書き換わり、必ず原状復帰する (finally + sha256 照合。Windows では強制終了すると finally が走らないので、止めない)。
import する凍結物 (v2〜v5) は変異させない (それぞれの certification が kill を確認済み)。
出力は certification が結び付く 14 ファイル・test (``tests/test_body_walk/*.py``)・本 harness の sha256 と、
変異ごとの明細 (label・status・期待 test・落ちた test) を記録する。写像の入口 (``load_certification``) と manifest が照合する。

実行 (repo root から)::

    uv run python scripts/body_walk_mutation_check.py --out <results.json>
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

from scripts.body_walk_select import (  # noqa: E402
    CERTIFIED,
    harness_sha256,
    tests_sha256,
)

_B = _REPO_ROOT / "scripts" / "body_walk_battery.py"
_S = _REPO_ROOT / "scripts" / "body_walk_pilot_scorer.py"
_Z = _REPO_ROOT / "scripts" / "body_walk_sim.py"
_X = _REPO_ROOT / "scripts" / "body_walk_select.py"
_TESTS = "tests/test_body_walk"
# commit 済み manifest と現在のコードの一致を見る test は、変異中は必ず落ちて生き残りを覆い隠すので外す。
_DESELECT = (
    f"{_TESTS}/test_manifest.py::test_committed_artifacts_are_bound_and_door_close"
)
_FAILED = re.compile(r"^FAILED (\S+?)(?:\[.*?\])?(?: - .*)?$")
_ERROR = re.compile(r"^ERROR (\S+?)(?:\[.*?\])?(?: - .*)?$")


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
_RECOUNT = "test_tallies_match_an_independent_recount"

MUTANTS: tuple[Mutant, ...] = (
    # ================================================================ battery
    _m(
        "mb1  λ を endpoint から外す",
        _B,
        "WALK_LAMBDA: Final[float] = 1.0",
        "WALK_LAMBDA: Final[float] = 0.5",
        "test_frozen_constants",
        "test_walk_sampling_is_the_composed_endpoint",
    ),
    _m(
        "mb2  凍結時の観測値を手書きの 0.95 にする",
        _B,
        "FROZEN_WALK: Final[tuple[float, float, float]] = (1.3, 0.9500000000000001, 0.9)",
        "FROZEN_WALK: Final[tuple[float, float, float]] = (1.3, 0.95, 0.9)",
        "test_walk_sampling_is_the_composed_endpoint",
        "test_battery_checks_pass",
    ),
    _m(
        "mb3  観測値の封印の検査を外す",
        _B,
        "    if (walk.temperature, walk.top_p, walk.repeat_penalty) != FROZEN_WALK:",
        "    if False:",
        "test_sampling_check_catches_a_broken_direction",
    ),
    _m(
        "mb4  peripatetic delta を落とす",
        _B,
        "    return compose_sampling(_sit_base(), mode, loco)",
        "    return compose_sampling(_sit_base(), SamplingDelta(), loco)",
        "test_walk_sampling_is_the_composed_endpoint",
        "test_battery_checks_pass",
    ),
    _m(
        "mb5  meta から Ollama の版を落とす",
        _B,
        "        ollama_version=OLLAMA_VERSION,\n",
        "",
        "test_request_meta_walk",
        "test_battery_checks_pass",
    ),
    _m(
        "mb6  Ollama の版を変える",
        _B,
        'OLLAMA_VERSION: Final[str] = "0.32.12"',
        'OLLAMA_VERSION: Final[str] = "0.32.11"',
        "test_frozen_constants",
    ),
    _m(
        "mb7  model parameters の top_k を変える",
        _B,
        '    "top_k                          20\\n"',
        '    "top_k                          40\\n"',
        "test_frozen_constants",
    ),
    _m(
        "mb8  pilot の r を v5 pilot に重ねる",
        _B,
        "PILOT_R: Final[tuple[int, ...]] = tuple(range(16, 28))",
        "PILOT_R: Final[tuple[int, ...]] = tuple(range(12, 24))",
        "test_frozen_constants",
        "test_battery_checks_pass",
    ),
    _m(
        "mb9  pilot の M を 4 に",
        _B,
        "PILOT_M: Final[int] = 8",
        "PILOT_M: Final[int] = 4",
        "test_frozen_constants",
    ),
    _m(
        "mb10 seed 基点を v4 と同じに",
        _B,
        "PILOT_SEED_BASE: Final[int] = 23_260_930",
        "PILOT_SEED_BASE: Final[int] = 21_260_926",
        "test_frozen_constants",
        "test_battery_checks_pass",
    ),
    _m(
        "mb11 renderer を R1+ にする",
        _B,
        "RENDERER: Final[str] = v4.RENDERER_R1",
        "RENDERER: Final[str] = v4.RENDERER_R1PLUS",
        "test_messages_are_v4_r1",
    ),
    _m(
        "mb12 表示回転を周で変える",
        _B,
        "    return v4.dev_options(r, t)",
        "    return v4.dev_options(r, t + t // N_DEV)",
        "test_rotation",
        "test_battery_checks_pass",
    ),
    _m(
        "mb13 replay の対象 step をずらす",
        _B,
        "REPLAY_ALL_STEPS: Final[tuple[int, ...]] = (N_DEV * 4 - 1, PILOT_T - 1)",
        "REPLAY_ALL_STEPS: Final[tuple[int, ...]] = (N_DEV * 4, PILOT_T - 1)",
        "test_plan_order",
    ),
    _m(
        "mb14 本登録との r の重なりの検査を外す",
        _B,
        "    if any(r < MAIN_R_MAX for r in PILOT_R):",
        "    if False:",
        "test_replicates_check_catches",
    ),
    _m(
        "mb15 v5 pilot との r の重なりの検査を外す",
        _B,
        "    if set(PILOT_R) & set(v5.PILOT_R):",
        "    if False:",
        "test_replicates_check_catches",
    ),
    _m(
        "mb16 r mod 4 の均衡の検査を外す",
        _B,
        '    if len(set(counts)) != 1:\n        problems.append("pilot replicates',
        '    if False:\n        problems.append("pilot replicates',
        "test_replicates_check_catches",
    ),
    _m(
        "mb17 v5 pilot の seed との照合を外す",
        _B,
        '        ("v5 pilot", v5.pilot_seeds()),\n',
        "",
        "test_seed_check_catches_collisions",
    ),
    _m(
        "mb18 v4 のループ段 seed の検査範囲を本登録の r に狭める",
        _B,
        "    v4_loop = {v4.loop_seed(r, t) for r in range(OTHER_R_MAX) for t in range(PILOT_T)}",
        "    v4_loop = {v4.loop_seed(r, t) for r in range(MAIN_R_MAX) for t in range(PILOT_T)}",
        "test_seed_check_catches_collisions",
    ),
    _m(
        "mb19 周で不変の検査を外す",
        _B,
        "            if t + N_DEV < PILOT_T and opts != dev_options(r, t + N_DEV):",
        "            if False:",
        "test_rotation_check_catches_a_lap_rotation",
    ),
    _m(
        "mb20 世界名の token の検査を外す",
        _B,
        '    tokens = ("a_rot", "b_rot", "c0", "arm", "world", "r1plus", "axis")',
        "    tokens = ()",
        "test_non_leakage_catches_world_names",
    ),
    _m(
        "mb21 歩行の向きの検査を外す",
        _B,
        '        problems.append("walk does not move T / top_p up and repeat_penalty down")',
        "        pass",
        "test_sampling_check_catches_a_broken_direction",
    ),
    _m(
        "mb22 replay 部分の検査を外す",
        _B,
        "    if len(replay) != n_replay_calls() or any(",
        "    if False and any(",
        "test_plan_check_catches_a_broken_plan",
    ),
    _m(
        "mb23 ループ部分の順の検査を外す",
        _B,
        "    elif got != [",
        "    elif False and got != [",
        "test_plan_check_catches_a_wrong_world_order",
        "test_plan_check_catches_a_broken_plan",
    ),
    _m(
        "mb24 battery 違反から seed の検査を落とす",
        _B,
        "        *check_seed_disjoint(),\n",
        "",
        "test_battery_violations_aggregates_every_check",
    ),
    # ================================================================ scorer
    _m(
        "ms1  schedule の key の照合を外す",
        _S,
        "        if rec.key() != full[rec.call_index]:",
        "        if False:",
        "test_invalid_records",
    ),
    _m(
        "ms2  schedule の seed の照合を外す",
        _S,
        "        if rec.seed != want:",
        "        if False:",
        "test_invalid_records",
    ),
    _m(
        "ms3  transport 失敗の後に続く記録を許す",
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
        "ms5  連鎖 replay の sha の照合を外す",
        _S,
        "            if rec.prompt_sha256 != messages_sha256(msgs):",
        "            if False:",
        "test_invalid_records",
        "test_chain_replay_catches_forged_choice",
    ),
    _m(
        "ms6  replay の prompt の照合を外す",
        _S,
        "        if orig is None or orig.prompt_sha256 != rec.prompt_sha256:",
        "        if False:",
        "test_invalid_records",
    ),
    _m(
        "ms7  要求条件と実行環境の照合を外す",
        _S,
        "    if meta_violations(meta):",
        "    if False:",
        "test_meta_mismatch_is_invalid",
    ),
    _m(
        "ms8  replay の transport 失敗でも止める",
        _S,
        "    if any(x.raw is None for x in loops):",
        "    if any(x.raw is None for x in records):",
        "test_replay_part_does_not_stop_the_measurement",
    ),
    _m(
        "ms9  replay の欠けでも止める",
        _S,
        "    if len(loops) < bat.n_loop_calls():",
        "    if len(records) < len(bat.pilot_plan()):",
        "test_replay_part_does_not_stop_the_measurement",
    ),
    _m(
        "ms10 重複を畳まない",
        _S,
        "                if cur in opts and first:",
        "                if cur in opts:",
        "test_duplicates_are_collapsed_but_world_rates_are_not",
        _RECOUNT,
    ),
    _m(
        "ms11 世界別の ⊥ も畳む",
        _S,
        "            c.bottom[world].add(rec, cur is None)  # 世界別の ⊥・Ω 外は畳まない",
        "            if first:\n                c.bottom[world].add(rec, cur is None)",
        "test_duplicates_are_collapsed_but_world_rates_are_not",
    ),
    _m(
        "ms12 同一 prompt を判定しない (全て prompt 変化に)",
        _S,
        "                    elif by_sha[sig].get(rec.prompt_sha256) in opts:",
        "                    elif False:",
        "test_same_prompt_is_the_exact_rendered_prompt",
        "test_alternating_policy_never_repeats",
        _RECOUNT,
    ),
    _m(
        "ms13 初訪の h0 / h_sw を weather でなく成功の有無で分ける",
        _S,
        "                        if any(s[0] == sig[0] for s in state.succeeded):",
        "                        if state.succeeded:",
        _RECOUNT,
        "test_denominators_partition_the_counted_visits",
    ),
    _m(
        "ms14 base を h_sw の初訪でも数える",
        _S,
        "                            c.h0.add(rec, hit)\n"
        "                            for a, tally in c.base[sig[0]].items():\n"
        "                                tally.add(rec, cur == a)",
        "                            c.h0.add(rec, hit)\n"
        "                        for a, tally in c.base[sig[0]].items():\n"
        "                            tally.add(rec, cur == a)",
        "test_denominators_partition_the_counted_visits",
    ),
    _m(
        "ms15 base の平滑化を変える",
        _S,
        "BASE_SMOOTH: Final[float] = 0.5",
        "BASE_SMOOTH: Final[float] = 1.0",
        "test_base_probs_smoothing",
    ),
    _m(
        "ms16 低事前 label を最大の label にする",
        _S,
        "        label = min(v4.dev_omega(wt), key=lambda a: probs[wt][a])",
        "        label = max(v4.dev_omega(wt), key=lambda a: probs[wt][a])",
        "test_base_and_low_prior",
        "test_base_probs_smoothing",
        "test_low_prior_ties_take_the_canonical_order",
    ),
    _m(
        "ms17 低事前 label の限界を呼び出し単位だけにする",
        _S,
        "        lo, hi = tally.bounds()",
        "        lo, hi = tally.call_bounds()",
        "test_base_and_low_prior",
    ),
    _m(
        "ms18 保守限界を内側にする",
        _S,
        "        return min(lo_a, lo_b), max(hi_a, hi_b)",
        "        return max(lo_a, lo_b), min(hi_a, hi_b)",
        "test_wilson_and_outer_bounds",
    ),
    _m(
        "ms19 λ̂_dev の 0 の床を外す",
        _S,
        "    return max(0.0, (c.h_sw.k / c.h_sw.n - h0) / (1.0 - h0))",
        "    return (c.h_sw.k / c.h_sw.n - h0) / (1.0 - h0)",
        "test_lam_dev",
    ),
    _m(
        "ms20 ⊥ gate の閾値を外す",
        _S,
        '        "rejected_bottom": max(world_bot.values()) > BOT_MAX,',
        '        "rejected_bottom": max(world_bot.values()) > 1.0,',
        "test_bottom_gate_and_bounds",
    ),
    _m(
        "ms21 ⊥ の上限を cluster 単位にする",
        _S,
        '        "bottom_hi": max(x.call_bounds()[1] for x in c.bottom.values()),',
        '        "bottom_hi": max(x.bounds()[1] for x in c.bottom.values()),',
        "test_bottom_gate_and_bounds",
    ),
    _m(
        "ms22 窓を候補 M でなく全 step にする",
        _S,
        "    c = count_window(records, bat.N_DEV * m)",
        "    c = count_window(records, bat.PILOT_T)",
        "test_bottom_gate_and_bounds",
    ),
    _m(
        "ms23 経験点の入力で ⊥ を数えない",
        _S,
        "                n_bot += rec.parsed is None",
        "                n_bot += 0",
        "test_chains_count_bottoms",
        "test_chains_are_the_end_states",
    ),
    _m(
        "ms24 経験点の入力の窓を 1 step 延ばす",
        _S,
        "                if rec.step >= t_max:\n                    break\n                n_bot",
        "                if rec.step > t_max:\n                    break\n                n_bot",
        "test_chains_are_the_end_states",
        "test_chains_count_bottoms",
    ),
    _m(
        "ms25 replay を常に一致とみなす",
        _S,
        "        by_key[(x.world, x.replicate, x.step)].raw == x.raw",
        "        True",
        "test_determinism_rates",
    ),
    _m(
        "ms26 厳密な相殺の判定を外す",
        _S,
        '        "exact_cancellation": bool(rates) and all(x == 1.0 for x in rates),',
        '        "exact_cancellation": bool(rates),',
        "test_determinism_rates",
    ),
    _m(
        "ms27 meta の型の一致を外す",
        _S,
        "        if type(meta[k]) is not type(v) or meta[k] != v",
        "        if meta[k] != v",
        "test_meta_mismatch_is_invalid",
    ),
    # ================================================================ sim
    _m(
        "mz1  同一 prompt の反復を落とす",
        _Z,
        "        pick = np.where(same_prompt & (u[..., U_REP] < beh.s_same), mem_pos, pick)",
        "",
        _REF,
    ),
    _m(
        "mz2  同一 prompt でも s_changed を使う",
        _Z,
        "            ~same_prompt & has_prev & (u[..., U_REP] < beh.s_changed), prev_pos, pick",
        "            has_prev & (u[..., U_REP] < beh.s_changed), prev_pos, pick",
        _REF,
    ),
    _m(
        "mz3  λ_dev を同 weather の成功なしでも使う",
        _Z,
        "        pick = np.where((n_sw > 0) & (u[..., U_SW] < beh.lam_dev), rp, pick)",
        "        pick = np.where(u[..., U_SW] < beh.lam_dev, rp, pick)",
        _REF,
    ),
    _m(
        "mz4  成功済みにも Ω 外を当てる",
        _Z,
        "        oov = acted & ~done & (u[..., U_OOV] < beh.oov)",
        "        oov = acted & (u[..., U_OOV] < beh.oov)",
        _REF,
    ),
    _m(
        "mz5  結合を常に使う",
        _Z,
        "        if beh.coupled:\n            u = v4sim._coupled",
        "        if True:\n            u = v4sim._coupled",
        _REF,
        "test_coupling_ends",
    ),
    _m(
        "mz6  結合を使わない",
        _Z,
        "        if beh.coupled:\n            u = v4sim._coupled",
        "        if False:\n            u = v4sim._coupled",
        _REF,
        "test_coupling_ends",
    ),
    _m(
        "mz7  記憶を ⊥ でも更新する",
        _Z,
        "        mem_mask[sl] = np.where(acted, mask, mem_mask[sl])",
        "        mem_mask[sl] = mask",
        _REF,
    ),
    _m(
        "mz8  参照の同一 prompt を描画でなく訪問の有無で判定する",
        _Z,
        "                    same = [c for mm, c in hist.get(key, []) if mm == msgs_of[w]]",
        "                    same = [c for mm, c in hist.get(key, [])]",
        _REF,
    ),
    _m(
        "mz9  参照の結合を描画の一致でなく世界番号で決める",
        _Z,
        "                        if beh.coupled\n                        else wi",
        "                        if False\n                        else wi",
        _REF,
    ),
    _m(
        "mz10 参照の Ω 外の label を固定する",
        _Z,
        "        return non[1] if u[U_OOV_WHICH] >= 0.5 else non[0]",
        "        return non[0]",
        _REF,
        "test_reference_branches",
    ),
    _m(
        "mz11 経験点で世界の並びを崩す",
        _Z,
        '        succ=succ[idx], loop_bot=bot[idx], steps=int(chains["steps"])',
        '        succ=succ[idx][..., ::-1, :], loop_bot=bot[idx], steps=int(chains["steps"])',
        "test_empirical_dev_resamples_whole_blocks",
    ),
    _m(
        "mz12 経験点の step 数を窓でなく pilot 全体にする",
        _Z,
        '        succ=succ[idx], loop_bot=bot[idx], steps=int(chains["steps"])',
        "        succ=succ[idx], loop_bot=bot[idx], steps=bat.PILOT_T",
        "test_empirical_dev_resamples_whole_blocks",
        "test_measures_and_chains_are_taken_from_the_candidate_window",
    ),
    _m(
        "mz13 合成 replay の非決定性を植えない",
        _Z,
        "                raw += SYNTH_FLIP_SUFFIX",
        '                raw += ""',
        "test_determinism_rates",
    ),
    _m(
        "mz14 仮想の平らにする指数を逆にする",
        _Z,
        "        p = np.array([probs[wt][a] for a in om], dtype=float) ** exponent",
        "        p = np.array([probs[wt][a] for a in om], dtype=float) ** (1.0 / exponent)",
        "test_tempered_table",
        "test_hypothetical_behaviour",
    ),
    # ================================================================ select
    _m(
        "mx1  s_same を下限にする",
        _X,
        '        "s_same": float(m["s_same"]["hi"]),',
        '        "s_same": float(m["s_same"]["lo"]),',
        "test_conservative_values",
        "test_behaviour_uses_conservative_values",
    ),
    _m(
        "mx2  s_changed を下限にする",
        _X,
        '        "s_changed": float(m["s_changed"]["hi"]),',
        '        "s_changed": float(m["s_changed"]["lo"]),',
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
        "mx4  pilot_low で最小 label を下げない",
        _X,
        "            a: lo if a == label else float(base[a]) * scale",
        "            a: float(base[a]) if a == label else float(base[a]) * scale",
        "test_pilot_low_formula",
        "test_pilot_low_uses_the_scorer_low_prior",
    ),
    _m(
        "mx5  pilot_low で他の label を補わない",
        _X,
        "        scale = (1.0 - lo) / (1.0 - float(base[label]))",
        "        scale = 1.0",
        "test_pilot_low_formula",
    ),
    _m(
        "mx6  結合を coupled だけにする",
        _X,
        "COUPLINGS: Final[tuple[bool, ...]] = (True, False)",
        "COUPLINGS: Final[tuple[bool, ...]] = (True,)",
        "test_grid",
    ),
    _m(
        "mx7  経験点を格子から落とす",
        _X,
        "    return emp + par",
        "    return par",
        "test_grid",
    ),
    _m(
        "mx8  pilot_low を格子から落とす",
        _X,
        'BASE_SOURCES: Final[tuple[str, ...]] = ("pilot", "pilot_low")',
        'BASE_SOURCES: Final[tuple[str, ...]] = ("pilot",)',
        "test_grid",
    ),
    _m(
        "mx9  b_hi を格子から落とす",
        _X,
        '    bots = sorted({0.0, conservative_values(m)["bot_hi"]})',
        "    bots = [0.0]",
        "test_grid",
    ),
    _m(
        "mx10 λ_dev の出所を取り違える",
        _X,
        '        if dp.lam_src == "v4"',
        '        if dp.lam_src == "pilot"',
        "test_behaviour_uses_conservative_values",
    ),
    _m(
        "mx11 結合の点を無視する",
        _X,
        "        coupled=bool(dp.coupled),",
        "        coupled=True,",
        "test_behaviour_uses_conservative_values",
    ),
    _m(
        "mx12 pilot_low の点で pilot の base を使う",
        _X,
        '    probs = m["base"] if dp.base_src == "pilot" else pilot_low(m)',
        '    probs = m["base"]',
        "test_behaviour_uses_conservative_values",
    ),
    _m(
        "mx13 経験点の入力を常に M = 8 の窓から取る",
        _X,
        "                    self.chains[str(m)], len(r_values), n, rng",
        '                    self.chains["8"], len(r_values), n, rng',
        "test_measures_and_chains_are_taken_from_the_candidate_window",
    ),
    _m(
        "mx14 測定量を常に M = 8 の窓から取る",
        _X,
        "                beh = behaviour(self.measures[str(m)], dp)",
        '                beh = behaviour(self.measures["8"], dp)',
        "test_measures_and_chains_are_taken_from_the_candidate_window",
    ),
    _m(
        "mx15 ⊥ gate に落ちた M も審査する",
        _X,
        "        if m in rejected:\n            continue",
        "        if False:\n            continue",
        "test_rejected_m_is_skipped",
    ),
    _m(
        "mx16 合格しても審査を続ける",
        _X,
        '            chosen = {"R": r, "K": k, "M": m, "calls": v4bat.n_main_calls(r, k, m)}\n            break',
        '            chosen = {"R": r, "K": k, "M": m, "calls": v4bat.n_main_calls(r, k, m)}',
        "test_smallest_candidate_wins",
    ),
    _m(
        "mx17 screening に落ちても本確認する",
        _X,
        "        if not ok:\n            continue",
        "        if False:\n            continue",
        "test_door_close",
    ),
    _m(
        "mx18 本確認に落ちても選ぶ",
        _X,
        "        if ok_f:",
        "        if True:",
        "test_final_failure_continues",
    ),
    _m(
        "mx19 違反点で打ち切らない",
        _X,
        '                if not row["ok"]:\n                    return False, rows',
        "                if False:\n                    return False, rows",
        "test_end_to_end_small_grid",
    ),
    _m(
        "mx20 certification の照合を外す",
        _X,
        "    if certification is not None and not load_certification(certification):",
        "    if False:",
        "test_certification_gate_of_the_mapping",
    ),
    _m(
        "mx21 計算できない pilot でも写像する",
        _X,
        '    if report["status"] != ps.STATUS_COMPUTED:',
        "    if False:",
        "test_not_computed_pilot_is_not_mapped",
    ),
    _m(
        "mx22 候補を大きい順に審査する",
        _X,
        "    return v5sel.candidates()",
        "    return v5sel.candidates()[::-1]",
        "test_candidate_order",
        "test_smallest_candidate_wins",
    ),
    _m(
        "mx23 見取り図の平らにする比を逆にする",
        _X,
        "    exponent = bat.sit_sampling().temperature / bat.walk_sampling().temperature",
        "    exponent = bat.walk_sampling().temperature / bat.sit_sampling().temperature",
        "test_hypothetical_behaviour",
    ),
    _m(
        "mx24 見取り図の meta を着座の値にする",
        _X,
        "    meta = json.dumps(bat.request_meta_walk())",
        "    meta = json.dumps({})",
        "test_decision_table_feeds_synthetic_pilots",
    ),
    _m(
        "mx25 見取り図の行を減らす",
        _X,
        "TABLE_ROWS: Final[tuple[float, ...]] = (0.0, 0.5, 0.9)",
        "TABLE_ROWS: Final[tuple[float, ...]] = (0.0, 0.9)",
        "test_hypothetical_behaviour",
        "test_decision_table_feeds_synthetic_pilots",
    ),
    _m(
        "mx26 κ 曲線に dev 点の ⊥ を渡さない",
        _X,
        "            self._curve[ckey] = v5sim.kappa_curve(pp, dp.bot, curve_dev)",
        "            self._curve[ckey] = v5sim.kappa_curve(pp, 0.0, curve_dev)",
        "test_row_passes_the_dev_point_bot_and_the_candidate_r",
    ),
    _m(
        "mx27 候補の R でなく曲線の R で審査する",
        _X,
        "        dev = self.dev(dp, m, tuple(range(r)), n, tag)",
        "        dev = self.dev(dp, m, CURVE_R, n, tag)",
        "test_row_passes_the_dev_point_bot_and_the_candidate_r",
    ),
    _m(
        "mx28 certification の明細の KILLED を見ない",
        _X,
        '        and all(isinstance(x, dict) and x.get("status") == "KILLED" for x in rows)',
        "        and all(isinstance(x, dict) for x in rows)",
        "test_certification_gate_of_the_mapping",
    ),
    _m(
        "mx29 certification の test の sha を見ない",
        _X,
        '        and cert.get("tests_sha256") == tests_sha256(root)\n',
        "",
        "test_certification_gate_of_the_mapping",
    ),
    _m(
        "mx30 certification の harness の sha を見ない",
        _X,
        '        and cert.get("harness_sha256") == harness_sha256(root)\n',
        "",
        "test_certification_gate_of_the_mapping",
    ),
    _m(
        "mx31 certification の空の明細を許す",
        _X,
        "        and len(rows) > 0\n",
        "",
        "test_certification_gate_of_the_mapping",
    ),
    _m(
        "mx32 certification の label の重複を許す",
        _X,
        '        and len({x.get("label") for x in rows}) == len(rows)\n',
        "",
        "test_certification_gate_of_the_mapping",
    ),
)


def _run_tests(env: dict[str, str]) -> tuple[int, list[str], bool]:
    proc = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-rfE",
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
            if (m := _FAILED.match(line) or _ERROR.match(line))
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
    tests = tests_sha256(_REPO_ROOT)
    harness = harness_sha256(_REPO_ROOT)

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
                {
                    "target_sha256": certified,
                    "tests_sha256": tests,
                    "harness_sha256": harness,
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
