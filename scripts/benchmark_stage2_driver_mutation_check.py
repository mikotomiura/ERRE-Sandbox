#!/usr/bin/env python
"""判別性 gate 段 2 の本走前の certification — 対象の行を壊すと、意図した test が意図した理由で落ちるか.

対象 (DD-6・DD-11: 本走が実行・判定に使う code の全体) =
``scripts/benchmark_stage2_{driver,plan,units,records,pilot_gate,stats,fixtures,scorer}.py``。
witness の test = ``tests/test_benchmark_stage2_driver/`` (証明書の読み手 ``test_certificate.py`` を除く) と、凍結の
``tests/test_benchmark_stage2/test_stats.py`` (stats の変異の一部)。``test_fixtures.py`` が原本として import する
凍結の test 2 つと pilot の ``gate.json`` も sha で束ねる。段 3.5 の pilot 前の版 (pre_pilot) は同じ path に
あったものを本走前の版で上書きした (git の履歴に残る)。

枠組みは O_time の driver の harness (``scripts/o_time_probe_driver_mutation_check.py``、Codex review 6 回) を写し、
対象を 8 ファイル (段 3.5 は 6、段 5 で fixtures・scorer を追加) に広げたもの。変わった点だけ書く (他は O_time の docstring のとおり):

* **変異は複製ツリーにだけ当てる** (memory feedback_harness_stop_leaves_mutant)。``--workers`` 個の worker が
  それぞれ複製ツリー (repo の外の一時 dir) を持ち、写しの bytes (8 対象・witness の test・harness の sha256) が repo と
  同じこと・無変異の対照が緑であることを確かめてから、queue の変異を 1 つずつ当てて元の bytes に戻す。凍結の
  ``benchmark_stage2_stats.py`` (manifest の 13 ファイルの 1 つ) を書き換えるのも複製の中だけ。
* 変異は ``(label, 対象, old → new, 期待 test, why, Witness)``。各 run は期待 test を含む test ファイルだけを回す
  (``_files_for``)。KILLED に数えるのは、pytest が test の失敗 (exit 1) で最後まで走り、期待 test の失敗の記録に
  Witness の証拠があるときだけ。既定の証拠は期待 test の本体 (call) の ``assert`` 文。``pytest.raises`` の
  DID NOT RAISE・意図した例外は、item (parametrize の id)・型・文で**同じ 1 つの例外**を照合する。fixture の
  setup の ERROR は、登録で段 = setup と理由の文を名指したものだけを数える (feedback_mutation_fixture_error_reason)。
* anchor は対象ファイルに 1 回だけ現れ、置換で内容が変わり、置換後も構文が通ること (``--anchors``)。
* ``--discover`` は開発用: 各変異の失敗の記録 (関数・id・段・assert 文か・先頭の例外) を出す。証明書は書かない。

登録から外した変異 (等価・この certification の保証の外):

* 記録の seed・prompt の sha を送った body でなく ``CallSpec`` から取る (driver ``_row``): 送信前の照合が
  送った body を plan と型まで一致させるので等価。
* backoff が期限を越えるときに待たずに止める行を外す: 次の ``deadline.check`` が同じ ``DeadlineReachedError`` を
  出す (状態・記録は同じ。待つ実時間だけが変わる)。transport 失敗の後に期限を見る行は等価でない (4 回目の送信が
  期限の後に失敗すると時間切れでなく通信の欠測になる、code-reviewer MEDIUM) ので変異 d53 で pin する。
* 公開名が既にあるときの上書きの拒否 (``publish``): Windows の ``Path.rename`` は既存の宛先で ``FileExistsError``
  を出すので、この harness が走る Windows では等価 (O_time と同じ)。fsync を外す: 耐久性は保証の外。
* (保証の外) ``frozen_decode_problems`` の比較を外す: 負例の無い検査 (凍結の 4 battery の定数は等しく、
  ``test_plan`` は ``== []`` だけを見る)。凍結物は変えないので、定数の一致は凍結の manifest が担う。
* pilot gate の v3 の L arm の本数の検査を外す: 本数と呼び出しの数は引数の arm と r の列だけで決まり、
  データに依らない (登録どおりの arm を渡す限り等価)。本数を 3 本にする変異は検査が捕まえる (登録 g05)。
  G の KNOW の行数 (36 × 3) の検査を外す: 読み手が欠けた区切りを not_computed にし、資格の計算に届かない。
* ``g_samples`` の KNOW の replicate を shift の対象から外す行: 今の呼び手 (pilot gate は KNOW を shift 0 で写す)
  に限って等価。段 5 で scorer が ``g_samples`` を使うなら審査し直す。
* v2 の巡回の block から r の項を外す (plan ``_v2_block_arms``): 1 replicate = 6 probe × 10 k = 60 block で 4 の
  倍数なので、block mod 4 は r に依らない (全 r で等価)。巡回そのもの (block mod 4) は変異 p04 が pin する。
* v3 の得点の腕名を ``POINTS_AS`` で写さない (units ``category``): 判定の arm (= v2 の lever arm) で
  ``POINTS_AS`` は恒等なので等価 (L arm は単位に入らない)。
* O_time の単位の ``Unit`` の部屋だけをずらす (units ``unit_cells``): ``unit_calls`` の (arm, 書き方) の集合は
  部屋に依らず、セルの並びだけが変わる (単位の値は和なので等価)。部屋の取り違えは probe_id の変異 u04 が pin する。

* (段 5、DD-11) scorer の ``segments missing`` の検査を外す: 読み手が区切りを返さないのは区切りの外の違反
  (状態表の order・segments の不一致・読めない) があるときだけで、その違反で battery は既に INVALID。
  scorer の ``half_labels`` に 0 起点の r を渡す: ``half_labels`` は r_list[0] からの相対なので等価
  (半分を潰す変異 c18 は、判定に渡す引数の test の中で stats が空の半分で止める)。fixtures の Δ_min の ``>`` → ``>=``: 許容 10^-12 を
  足した閾値ちょうどの差でだけ違う (閾値の向きは f12 が pin)。fixtures の ``fewest_failures`` の符号を落とす:
  v3 の状態では各セルで全選択肢の失敗の数が等しく (r ∈ [0, 40) ∪ [3000, 3080) の 2,880 セルで確認)、方策は常に
  同点 → 表示順になるので、符号に依らず同じ label (原本も同じ)。
* (段 5b、DD-12) scorer の envelope の負の分子の検査は消した: ⊥ の数を [0, bot_n] に限る検査 (c55) の下では
  復元した envelope は 1/20 以上なので、負の分子は復元との一致 (c46) で拒まれる (負例 20)。⊥ の数が負なら
  envelope も負の分数で整合してしまう (負例 27) ので、負の分子を拒むのは範囲の検査 c55 の役目。

meta-test (計測台 §4.4): 複製ツリーで検査関数を素通りに潰し、依存する test が実際に落ちることを一度見る。

証明書 (``--out``): 全 KILLED・meta-test 成立・原状復帰 (repo の 8 対象が開始時と同じ bytes)・実行中に test と
harness が変わっていないときだけ書く。``target_sha256`` は ``tests/test_architecture/test_closed_chain_selection``
の探索規則が読める形 (dir 名の付かない ``benchmark_stage2_*.py`` key と、新 test dir の全 .py を ``tests/<name>``)。
版 (``version``) = ``pre_main`` (DD-11。pilot 前の版 pre_pilot と区別する)。

実行 (repo root から、長いので detached で)::

    uv run python scripts/benchmark_stage2_driver_mutation_check.py --anchors
    uv run python scripts/benchmark_stage2_driver_mutation_check.py --workers 4 \\
        --out experiments/20261126-benchmark-stage2-driver/results/driver_mutation.json
"""

from __future__ import annotations

import argparse
import concurrent.futures
import getpass
import hashlib
import json
import os
import pathlib
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from dataclasses import dataclass
from typing import Any

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_TARGETS: dict[str, str] = {
    "driver": "scripts/benchmark_stage2_driver.py",
    "plan": "scripts/benchmark_stage2_plan.py",
    "units": "scripts/benchmark_stage2_units.py",
    "records": "scripts/benchmark_stage2_records.py",
    "pilot_gate": "scripts/benchmark_stage2_pilot_gate.py",
    "stats": "scripts/benchmark_stage2_stats.py",
    "fixtures": "scripts/benchmark_stage2_fixtures.py",
    "scorer": "scripts/benchmark_stage2_scorer.py",
}
_TARGET_FILES = frozenset(pathlib.PurePath(p).name for p in _TARGETS.values())
_HARNESS_REL = "scripts/benchmark_stage2_driver_mutation_check.py"
_TEST_DIR = "tests/test_benchmark_stage2_driver"
_STATS_TEST = "tests/test_benchmark_stage2/test_stats.py"
# test_fixtures.py が原本として import する凍結の test (方策の移植の照合の相手)
_ORIGINAL_TESTS = (
    "tests/test_skill_lever/test_scorer.py",
    "tests/test_skill_experience/test_nuisance.py",
)
_WITNESS_EXTRA = (_STATS_TEST, *_ORIGINAL_TESTS)
_PILOT_GATE_REL = (
    "results/pilot/gate.json"  # test_fixtures の実の gate (pilot の記録は他を写さない)
)
_CERT_TEST = "test_certificate.py"  # 証明書の読み手 (変異中は必ず落ちて生き残りを覆うので回さない)
_EXP_REL = "experiments/20261126-benchmark-stage2-discriminability"
_EXP_STAGE1 = "experiments/20261126-benchmark-stage1-reanalysis"
_VERSION = "pre_main"
_TEST_TIMEOUT_S = 1800
_WITNESS_ENV = "BS2_DRIVER_WITNESS"
_PLUGIN = "scripts.benchmark_stage2_driver_mutation_check"
_PHASES = ("setup", "call", "teardown")
_FINISH = "sessionfinish"
_ASSERT_WORD = re.compile(r"assert\b")
_DROPPED_ENV = ("PYTEST_ADDOPTS", "PYTEST_PLUGINS")


def _witness_test_files(root: pathlib.Path = _REPO_ROOT) -> list[str]:
    """回す test ファイル (repo 相対、名前の順)。証明書の読み手は除く."""
    found = sorted(
        p.relative_to(root).as_posix()
        for p in (root / _TEST_DIR).glob("test_*.py")
        if p.name != _CERT_TEST
    )
    return [*found, _STATS_TEST]


_TEST_FILE_NAMES = frozenset(pathlib.PurePath(p).name for p in _witness_test_files())


@dataclass(frozen=True)
class Witness:
    """変異が落とすべき証拠 (O_time の harness と同じ照合。``via`` は対象 8 ファイルのどれかのフレームの関数名)."""

    item: str | None = None
    when: str = "call"
    exc: str | None = None
    text: str | None = None
    via: str | None = None
    assert_stmt: bool = False

    def as_dict(self) -> dict[str, object]:
        return {k: v for k, v in vars(self).items() if v is not None}


_ASSERTED = Witness(assert_stmt=True)
_NOT_RAISED = "DID NOT RAISE"


def _raised(item: str | None = None, text: str = _NOT_RAISED) -> Witness:
    """``pytest.raises`` が上がらなかった (Failed: DID NOT RAISE ...) という証拠."""
    return Witness(item=item, exc="Failed", text=text)


def _assert_in(item: str) -> Witness:
    """parametrize の 1 つの id の本体の assert 文."""
    return Witness(item=item, assert_stmt=True)


# 凍結の集計との一致を ``np.testing.assert_allclose`` で見る test (assert 文でなく AssertionError を上げる)
_ALLCLOSE = Witness(exc="AssertionError", text="Not equal to tolerance")
# r の付け替えを外すと、凍結の集計が [0, R) の配列の外を引く (fixture の setup でも落ちるが call の記録で照合)
_INDEX = Witness(exc="IndexError", text="out of bounds")


@dataclass(frozen=True)
class Mutant:
    label: str
    target: str
    old: str
    new: str
    expect: frozenset[str]
    why: str
    witness: Witness = _ASSERTED


def _m(
    label: str,
    target: str,
    old: str,
    new: str,
    expect: tuple[str, ...],
    why: str,
    witness: Witness = _ASSERTED,
) -> Mutant:
    return Mutant(label, target, old, new, frozenset(expect), why, witness)


# ------------------------------------------------------------ test の名前

# driver (test_driver.py)
_D_ORDER = "test_runs_segments_in_order_and_publishes"
_D_ASCII = "test_record_lines_are_ascii_sorted"
_D_NONEMPTY = "test_refuses_non_empty_run_dir"
_D_RESEND = "test_resend_resolves_within_three"
_D_RETRY = "test_unresolved_segment_closes_and_next_runs_then_retry_replaces"
_D_ONCE = "test_retry_only_once"
_D_DL_RETRY = "test_deadline_during_retry"
_D_DL_MID = "test_deadline_mid_segment_then_not_started"
_D_REPLAY_LAST = "test_replay_runs_last_and_only_replay_can_be_left"
_D_REPLAY_ACC = "test_replay_accounted_separately"
_D_DIGEST = "test_digest_mismatch_invalidates_only_that_model"
_D_VER_START = "test_version_mismatch_at_start_invalidates_all"
_D_VER_MID = "test_version_change_mid_run_invalidates_all"
_D_META_FAIL = "test_meta_read_failure_is_transport_and_retried"
_D_GATE_FILE = "test_main_plan_from_gate_file"
_D_OBSERVER = "test_observer_rejects_body_not_in_plan"
_D_SAME = "test_same_distinguishes_types"
_D_FOREIGN = "test_run_stage_rejects_foreign_segments"
_D_GATE_R = "test_main_r_from_gate"
_D_REQ_GATE = "test_main_requires_gate"
# driver (test_driver_contract.py、段 3.5 で足したもの)
_D_TEMPLATE = "test_template_mismatch_invalidates_only_that_model"
_D_RETRY_BEFORE_REPLAY = "test_retry_runs_before_the_replay"
_D_META_LATE = "test_meta_read_failure_after_the_deadline_is_a_timeout"
_D_PUB = "test_publication_problems_check_bytes_rows_and_keys"
_D_PLAN_ENTRANTS = "test_plan_for_refuses_a_model_outside_the_entrants"
_D_EXIT = "test_main_exit_codes"
_D_CONSTANTS = "test_registered_run_constants"
_D_VER_START_DIR = "test_version_mismatch_at_start_touches_no_segment"
_D_MAIN_REPLAY = "test_main_stage_rejects_a_replay_segment"
_D_GATE_NQ_R = "test_read_gate_refuses_an_r_without_three_entrants"
_D_GATE_EXTRA = "test_read_gate_refuses_an_unregistered_battery"
_D_LAST_RESEND = "test_last_resend_failing_after_the_deadline_is_a_timeout"
_D_REQ_TIMEOUT = "test_request_timeout_is_cut_at_the_deadline"
# plan (test_plan.py)
_P_COUNTS = "test_pilot_call_counts_match_registration"
_P_ARMS = "test_pilot_arm_composition"
_P_MAIN_REP = "test_main_calls_per_replicate"
_P_MAIN_REJECT = "test_main_calls_reject_registered_r_violations"
_P_REPLAY = "test_replay_counts_and_seeds_are_the_old_r0"
_P_PILOT_ORDER = "test_pilot_plan_order"
_P_MAIN_ORDER = "test_main_plan_orders_batteries_by_cost_then_models"
_P_V2_ORDER = "test_v2_order_matches_frozen_driver"
_P_V3_ORDER = "test_v3_order_matches_frozen_driver"
_P_V2_PHASE = "test_v2_rotation_phase_is_absolute_in_r"
_P_G_ORDER = "test_g_order_matches_frozen_driver"
_P_O_ORDER = "test_o_time_order_matches_frozen_driver"
_P_PILOT_SEED = "test_pilot_seed_and_prompt_match_frozen_expected"
_P_MAIN_SEED = "test_main_seed_and_prompt_match_frozen_expected"
_P_SHA = "test_messages_sha_formula_matches_every_frozen_scorer"
_P_UNIQUE = "test_calls_unique_within_battery_stage"
_P_BODY = "test_body_has_exact_registered_options"
_P_DIGEST = "test_plan_digest_is_deterministic_and_sensitive"
_P_CHECKS = "test_battery_checks_pass_on_registered_r"
_P_SHIFTED = "test_shifted_evaluates_at_real_r_and_restores"
_P_STAGE2_R = "test_violation_at_a_stage2_r_only_is_caught"
_P_MASKED_R24 = "test_masked_violation_at_r24_only_is_caught"
_P_M0_R312 = "test_m0_violation_at_r312_only_is_caught"
_P_SEEDS = "test_seed_namespaces_catch_overlap_with_used_and_between_stages"
_P_V2V3 = "test_v2_v3_stage2_seeds_disjoint"
_P_BUDGET = "test_prompt_budget_sent_catches_long_prompt"
# units (test_units.py)
_U_V2 = "test_v2_units_match_frozen_per_replicate"
_U_V3 = "test_v3_units_match_frozen_per_replicate"
_U_G = "test_g_units_match_frozen_unit_by_unit"
_U_O = "test_o_time_units_match_frozen_unit_by_unit"
_U_CELL = "test_single_cell_lands_at_its_explicit_position"
_U_SEED = "test_units_share_seed_within_unit_and_differ_across"
_U_HALVES = "test_half_labels_follow_explicit_r"
_U_MISSING = "test_missing_cell_is_not_bottom"
_U_BOT = "test_bot_counts_shapes_and_values"
_U_SIX = "test_six_classes_and_q_r"
# records・pilot gate (test_pilot_gate.py)
_R_KEYS = "test_reader_row_keys_match_the_driver"
_R_ENUM = "test_independent_enumeration_agrees_with_the_plan"
_R_DIGESTS = "test_digests_and_order_agree_with_the_plan"
_R_DRIVER_OUT = "test_reader_accepts_driver_output"
_R_CLEAN = "test_one_model_run_reads_clean"
_R_STRUCT = "test_structure_violations_stop_records"
_R_SHA = "test_sha_mismatch_stops"
_R_META = "test_meta_differing_from_models_json_stops"
_R_MISSING = "test_plain_missing_rows_are_not_computed"
_R_ADOPTED = "test_reader_only_reads_the_adopted_attempt"
_R_NONCOMPLETED = "test_non_completed_segments_are_not_computed"
_R_PARTIAL_VER = "test_partial_invalid_version_stops"
_R_TAMPER = "test_digest_or_order_tamper_stops"
_G_STOP = "test_stop_records_gate_has_no_decisions"
_G_E2E = "test_end_to_end_gate_with_the_frozen_selection"
_G_UNITS = "test_pilot_units_follow_the_registered_order"
_G_REASONS = "test_qualification_reasons_follow_section_a"
_G_M0 = "test_m0_check_is_read_as_its_passed_field"
_G_MASKED = "test_masked_counts_reach_the_frozen_gate"
_G_NQ = "test_not_qualified_and_not_computed_batteries"
_G_STOP_POWER = "test_stop_power_keeps_k_and_records_the_largest_candidate"
_G_READ_GATE = "test_read_gate_rejects_contract_violations"
_G_MAIN_ENTRANTS = "test_main_plan_runs_only_entrants"
_G_ENVELOPE = "test_envelope_is_an_exact_fraction"
# records・pilot gate (test_records_contract.py、段 3.5 で足したもの)
_R_META_SHA = "test_meta_sha_mismatch_stops"
_R_TEMPLATE_SHA = "test_meta_template_sha_must_be_the_sha_of_the_template"
_R_META_FIELDS = "test_meta_fields_must_match_the_registration"
_R_SEG_DIGEST = "test_segment_digest_tamper_stops"
_R_LAST = "test_adopted_attempt_must_be_the_last_attempt"
_R_ADOPTED_NC = "test_adopted_attempt_on_a_non_completed_segment_stops"
_R_N_SENDS = "test_n_sends_out_of_range_stops"
_R_OLLAMA = "test_expected_ollama_version_differs_stops"
_G_INVALID = "test_invalid_meta_makes_the_model_invalid_in_that_battery"
_G_MASKED_G = "test_g_masked_bottom_keeps_the_model_out"
_G_WORST = "test_worst_pair_names_the_stats_pair"
_G_BUDGET = "test_budget_labels_reach_the_gate"
_G_NONFINITE = "test_gate_json_writes_non_finite_floats_as_strings"
# stats (凍結の test_stats.py と test_stats_contract.py)
_S_LAMBDA = "test_lambda_grid_is_frozen_geometric"
_S_K = "test_n_tests_counts_qualified_batteries_only"
_S_PARSE = "test_parse_rule_exact_boundary"
_S_ENVELOPE = "test_envelope_exceeded_exact_boundary"
_S_QUALIFY = "test_qualify_order"
_S_CONTROL = "test_control_arm_bottom_boundary_is_inclusive"
_S_BUDGET = "test_budget_boundary_is_inclusive"
_S_CANDIDATES = "test_r_candidates_respect_caps"
_P_COST_ORDER = "test_main_order_is_by_cost_not_by_name"
_S_LEVEL = "test_decide_level_is_alpha_over_k"
_S_DELTA = "test_decide_threshold_is_delta_min"
_S_EQUIV = "test_equivalence_band_is_point_one"
_S_SPLIT = "test_split_half_blocks_establishment"
_S_FLOOR = "test_floor_concentration_blocks_establishment"
_S_CONC = "test_concentration_level_is_alpha_over_two_sum_m"
_S_WORST = "test_worst_pair_breaks_ties_to_the_first_pair"
_G_WORST_IDX = "test_worst_pair_is_written_from_the_stats_indices"
# scorer (test_scorer.py)
_C_GRADED = "test_graded_run_establishes_and_names_every_pair"
_C_FX_PAIRS = "test_v3_named_pairs_carry_the_fixture_pairs"
_C_QWEN = "test_qwen3_prediction_is_reported"
_C_EQUAL = "test_equal_run_is_calibrated_negative_with_floor_components"
_C_DROPPED = "test_dropped_model_gives_negative_on_subset_and_keeps_k"
_C_NOT_QUAL = "test_too_few_reported_models_is_not_qualified"
_C_NOT_COMP = "test_all_models_missing_is_not_computed"
_C_INV_META = "test_invalid_meta_excludes_the_model"
_C_ALL_INV = "test_all_models_invalid_meta_is_invalid"
_C_ENV_BOUND = "test_envelope_boundary_is_strict"
_C_ENV_GATE = "test_envelope_comes_from_the_gate"
_C_REC_VIOL = "test_record_violation_makes_the_battery_invalid"
_C_RUN_VIOL = "test_run_wide_violation_makes_every_battery_invalid"
_C_FX_MISMATCH = "test_fixture_mismatch_makes_every_battery_invalid"
_C_GATE = "test_gate_contract_violations_are_refused"
_C_GATE_NQ = "test_gate_with_a_not_qualified_battery_is_read"
_C_OUTPUT = "test_output_is_written_once_and_checked"
_C_NONDET = "test_nondeterminism_is_caught"
_C_LEVELS = "test_descriptive_bounds_use_the_registered_levels"
_C_DECIDE_ARGS = "test_decide_battery_gets_the_gate_levels_and_halves"
_C_INV_VERSION = "test_run_wide_invalid_version_is_invalid"
_C_INSENSITIVE = "test_insensitive_named_pair_is_limited_to_the_score_gap"
_C_DR_GATE = "test_driver_refuses_every_gate_the_scorer_refuses"  # DD-12 M1 (driver の読み手に同じ負例)
_C_FX_FILE = "test_named_pairs_carry_every_fixture_pair_of_the_file"  # DD-12 M3
_C_EXCL_META = (
    "test_invalid_meta_excludes_the_model"  # DD-12 M2 (除外後の名指しの完全一致)
)
_C_ENCODING = "test_o_time_six_classes_are_split_by_encoding"  # DD-12 M4
# fixtures (test_fixtures.py)
_F_PORTED = "test_ported_policies_match_the_originals_on_stage2_r"
_F_LABEL_PRIOR = "test_label_prior_prefers_a_fixed_label"
_F_PAIRS = "test_pairs_and_over_delta_min"
_F_REAL = "test_real_gate_diffs"
_F_CLI = "test_cli_writes_once_and_checks"

# ------------------------------------------------------------ 変異の登録

MUTANTS: tuple[Mutant, ...] = (
    # ---------------------------------------------------------------- driver
    _m(
        "d01 再送の回数 3 → 2",
        "driver",
        "RESENDS: Final[int] = 3",
        "RESENDS: Final[int] = 2",
        (_D_RESEND,),
        "§H: 同じ body の再送は 3 回 (送信は最大 4 回)",
    ),
    _m(
        "d02 backoff の 3 回目 120 → 60",
        "driver",
        "(5.0, 30.0, 120.0)",
        "(5.0, 30.0, 60.0)",
        (_D_CONSTANTS,),
        "§H の backoff の表 (test_driver は定数から期待値を作るので値そのものを pin する)",
    ),
    _m(
        "d03 n_sends を 1 少なく数える",
        "driver",
        "                return reply, send + 1\n",
        "                return reply, send\n",
        (_D_RESEND, _D_ORDER),
        "記録の n_sends = 実送信数",
    ),
    _m(
        "d04 解けない呼び出しの n_sends を 3 にする",
        "driver",
        "            return None, 1 + RESENDS\n",
        "            return None, RESENDS\n",
        (_D_RETRY,),
        "解けない呼び出しの n_sends = 1 + 再送 3",
    ),
    _m(
        "d05 通信の欠測を再実行しない",
        "driver",
        "            retry = [s for s in main_segs if self.states[s.name].status == S_TRANSPORT]\n",
        "            retry = []\n",
        (_D_RETRY, _D_META_FAIL, _D_ONCE),
        "§F-2・H6: 通信の欠測はモデル単位で 1 回再実行する",
    ),
    _m(
        "d06 meta の違反も再実行する",
        "driver",
        "            retry = [s for s in main_segs if self.states[s.name].status == S_TRANSPORT]\n",
        "            retry = [s for s in main_segs if self.states[s.name].status in (S_TRANSPORT, S_INVALID_META)]\n",
        (_D_DIGEST, _D_TEMPLATE),
        "H6: meta の違反は再実行しない",
    ),
    _m(
        "d07 再実行を再生の後に回す",
        "driver",
        "                await self.run_segment(seg, attempt=MAX_ATTEMPTS)\n"
        "                self.save_partial()\n"
        "            await self._run_list(replay_segs, attempt=1)\n",
        "                self.save_partial()\n"
        "            await self._run_list(replay_segs, attempt=1)\n"
        "            for seg in retry:\n"
        "                await self.run_segment(seg, attempt=MAX_ATTEMPTS)\n",
        (_D_RETRY_BEFORE_REPLAY,),
        "H6: pilot の再実行を済ませてから再生",
    ),
    _m(
        "d08 新しい区切りを期限ちょうどで始める",
        "driver",
        '        if self.deadline.remaining() <= 0:\n            return "deadline"\n',
        '        if self.deadline.remaining() < 0:\n            return "deadline"\n',
        (_D_REPLAY_LAST,),
        "§H: 期限に当たった後は新しい区切りを始めない (not_started)",
    ),
    _m(
        "d09 期限の後の meta の読みの失敗を通信の欠測にする",
        "driver",
        "            state.status = S_TIMEOUT if self.deadline.remaining() <= 0 else S_TRANSPORT\n",
        "            state.status = S_TRANSPORT\n",
        (_D_META_LATE,),
        "DD-5: 期限を過ぎた後の meta の読みの失敗は時間切れ",
    ),
    _m(
        "d10 区切りの開始時の版の違いを見ない",
        "driver",
        "        if obs.ollama_version != OLLAMA_VERSION:\n            state.status = S_INVALID_VERSION\n",
        "        if False:\n            state.status = S_INVALID_VERSION\n",
        (_D_VER_MID,),
        "§A.1: 途中で違う版を見た区切りには送らない",
    ),
    _m(
        "d11 終わりに版の違いで全区切りを無効にしない",
        "driver",
        "    def finish(self) -> dict[str, Any]:\n        if any(v != OLLAMA_VERSION for v in self.versions_seen):\n",
        "    def finish(self) -> dict[str, Any]:\n        if False:\n",
        (_D_VER_MID, _D_VER_START),
        "§A.1: 版を混ぜない (run の全区切りを invalid_version)",
    ),
    _m(
        "d12 版の違いを見た後も新しい区切りを始める",
        "driver",
        '        if any(v != OLLAMA_VERSION for v in self.versions_seen):\n            return "Ollama version mismatch seen"\n',
        '        if False:\n            return "Ollama version mismatch seen"\n',
        (_D_VER_MID,),
        "DD-5: 違う版を見たら以後の区切りを始めない (GPU を使わない)",
    ),
    _m(
        "d13 起動時の版の違いでも chat を送る",
        "driver",
        "        if version != OLLAMA_VERSION:\n            # §A.1",
        "        if False:\n            # §A.1",
        (_D_VER_START_DIR,),
        "DD-5: 起動時の版が違えば区切りを 1 つも始めない (meta の読みもしない)",
    ),
    _m(
        "d14 終わりの無効化で adopted_attempt を残す",
        "driver",
        '                state.reason = f"Ollama version {seen} != {OLLAMA_VERSION} (§A.1)"\n'
        "                state.adopted_attempt = None\n",
        '                state.reason = f"Ollama version {seen} != {OLLAMA_VERSION} (§A.1)"\n',
        (_D_VER_MID,),
        "H6: 無効な区切りに採用 attempt を残さない",
    ),
    _m(
        "d15 digest の違いを見ない",
        "driver",
        '    if obs.model_digest != ref.get("model_digest"):\n',
        "    if False:\n",
        (_D_DIGEST,),
        "§A.1・§F-1: digest の違いはそのモデルを INVALID",
    ),
    _m(
        "d16 template の違いを見ない",
        "driver",
        '    if obs.template_sha256 != ref.get("template_sha256"):\n',
        "    if False:\n",
        (_D_TEMPLATE,),
        "§A.1・§F-1: template の違いはそのモデルを INVALID",
    ),
    _m(
        "d17 送信前の照合を外す",
        "driver",
        "                if not same(body, pl.body_for(spec, model)):\n",
        "                if False:\n",
        (_D_OBSERVER,),
        "送信前に wire の body を plan と型まで照合する",
        _raised(),
    ),
    _m(
        "d18 same が型を見ない",
        "driver",
        "    if type(got) is not type(want):\n        return False\n    if isinstance(want, dict):\n        assert isinstance(got, dict)\n        return set(got) == set(want) and all(same(",
        "    if isinstance(want, dict):\n        assert isinstance(got, dict)\n        return set(got) == set(want) and all(same(",
        (_D_SAME,),
        "False と 0、4096.0 と 4096 を区別する",
    ),
    _m(
        "d19 same が dict の余分な key を見ない",
        "driver",
        "        return set(got) == set(want) and all(same(got[k], want[k]) for k in want)\n",
        "        return all(same(got[k], want[k]) for k in want)\n",
        (_D_OBSERVER,),
        "body に余分な・欠けた key があれば違う (欠けた key で same が KeyError)",
        Witness(exc="KeyError", text="top_k", via="same"),
    ),
    _m(
        "d20 /api/show を meta の読みの外でも許す",
        "driver",
        "                if not self.allow_show:\n",
        "                if False:\n",
        (_D_OBSERVER,),
        "POST /api/show は meta の読みの間だけ",
        _raised(),
    ),
    _m(
        "d21 chat・show 以外の POST を許す",
        "driver",
        "            elif path != CHAT_PATH:\n",
        '            elif path not in (CHAT_PATH, "/api/generate"):\n',
        (_D_OBSERVER,),
        "POST は /api/chat と /api/show だけ",
        _raised(),
    ),
    _m(
        "d22 raw を verbatim で残さない",
        "driver",
        '            "raw": None if reply is None else reply.content,\n',
        '            "raw": None if reply is None else reply.content.replace("\\n", " "),\n',
        (_D_ORDER,),
        "記録は parse しない (raw を verbatim)",
    ),
    _m(
        "d23 再送を初回に数える",
        "driver",
        "        return C_INITIAL if send == 0 else C_RESEND\n",
        "        return C_INITIAL\n",
        (_D_RESEND,),
        "M3: 初回・再送を別に数える",
    ),
    _m(
        "d24 再実行を初回に数える",
        "driver",
        "        if attempt > 1:\n            return C_RETRY\n",
        "        if attempt > 2:\n            return C_RETRY\n",
        (_D_RETRY,),
        "M3: 再実行の送信を別に数える",
    ),
    _m(
        "d25 再生を初回に数える",
        "driver",
        "        if seg.stage == pl.STAGE_REPLAY:\n            return C_REPLAY\n",
        "        if False:\n            return C_REPLAY\n",
        (_D_REPLAY_ACC,),
        "M3: 再生は pilot の枠で別に数える",
    ),
    _m(
        "d26 8B 換算の費用を battery によらず v2 の秒で",
        "driver",
        "        self.cost_8b_s[category] += st.SPECS[battery].sec_per_call\n",
        '        self.cost_8b_s[category] += st.SPECS["v2"].sec_per_call\n',
        (_D_REPLAY_ACC,),
        "M3: 8B 換算は battery の秒の表",
    ),
    _m(
        "d27 採用 attempt を常に 1",
        "driver",
        "        state.adopted_attempt = attempt\n        state.records_sha256",
        "        state.adopted_attempt = 1\n        state.records_sha256",
        (_D_RETRY,),
        "H6: 採用 attempt = 公開した attempt",
    ),
    _m(
        "d28 records の sha を meta の bytes から",
        "driver",
        "        state.records_sha256 = sha256_bytes(records_bytes(lines))\n",
        "        state.records_sha256 = sha256_bytes(meta_bytes)\n",
        (_D_ORDER,),
        "H6: 状態表の records の sha = 公開した records の bytes",
    ),
    _m(
        "d29 meta の sha を records の bytes から",
        "driver",
        "        state.meta_sha256 = sha256_bytes(meta_bytes)\n",
        "        state.meta_sha256 = sha256_bytes(records_bytes(lines))\n",
        (_D_ORDER,),
        "H6: 状態表の meta の sha = 書いた meta の bytes",
    ),
    _m(
        "d30 空でない run dir を拒まない",
        "driver",
        "    if stage_root.exists() and any(stage_root.iterdir()):\n",
        "    if False:\n",
        (_D_NONEMPTY,),
        "再開しない (空でない <run>/<stage> を拒否)",
        _raised(),
    ),
    _m(
        "d31 記録の行を escape しない",
        "driver",
        "    return json.dumps(dict(obj), ensure_ascii=True, sort_keys=True)\n",
        "    return json.dumps(dict(obj), ensure_ascii=False, sort_keys=True)\n",
        (_D_ASCII,),
        "1 記録 = 1 行の ASCII (U+2028 等を escape)",
        Witness(exc="UnicodeEncodeError", text="ascii"),
    ),
    _m(
        "d32 記録の key を並べない",
        "driver",
        "    return json.dumps(dict(obj), ensure_ascii=True, sort_keys=True)\n",
        "    return json.dumps(dict(obj), ensure_ascii=True, sort_keys=False)\n",
        (_D_ASCII,),
        "記録は sort_keys",
    ),
    _m(
        "d33 再生を pilot の root の直下に置く",
        "driver",
        "    base = stage_root if seg.stage == run_stage else stage_root / seg.stage\n",
        "    base = stage_root\n",
        (_D_REPLAY_LAST,),
        "DD-5: 再生は <run>/pilot/replay/ (pilot の G・O_time の qwen3:8b と衝突しない)",
    ),
    _m(
        "d34 本走に再生の区切りを許す",
        "driver",
        "            seg.stage == pl.STAGE_REPLAY and run_stage_name != pl.STAGE_PILOT\n",
        '            seg.stage == pl.STAGE_REPLAY and run_stage_name == "never"\n',
        (_D_MAIN_REPLAY,),
        "再生は pilot の枠だけ (§H)",
        _raised(),
    ),
    _m(
        "d35 公開前の検査で行数を見ない",
        "driver",
        '    if len(rows) != len(seg.calls):\n        out.append(f"{len(rows)} rows for {len(seg.calls)} calls")\n        return out\n',
        "    if len(rows) != len(seg.calls):\n        return out\n",
        (_D_PUB,),
        "公開前: 行が区切りの呼び出しと 1 対 1",
    ),
    _m(
        "d36 公開前の検査で key の欄を見ない",
        "driver",
        "        if not all(same(row[k], v) for k, v in want.items()):\n",
        "        if False:\n",
        (_D_PUB,),
        "公開前: 各行の key の欄が plan の順の呼び出しと一致",
    ),
    _m(
        "d37 公開前の検査で書いた bytes との一致を見ない",
        "driver",
        "    if partial != records_bytes(lines):\n",
        "    if False:\n",
        (_D_PUB,),
        "公開前: partial がこの run の書いた bytes と同じ",
    ),
    _m(
        "d38 gate の schema・status を見ない",
        "driver",
        '    if gate.get("schema") != GATE_SCHEMA or gate.get("status") != "OK":\n',
        "    if False:\n",
        (_G_READ_GATE, _D_GATE_R),
        "H5: gate.json の schema と status = OK",
        _raised(item="<lambda>2"),
    ),
    _m(
        "d39 gate の入場を models の status と照合しない",
        "driver",
        '        if ent != entered or not _same_int(entry.get("n_entered"), len(entered)):\n',
        '        if not _same_int(entry.get("n_entered"), len(entered)):\n',
        (_G_READ_GATE,),
        "H5・DD-12 H1: 入場 = models の status が entered のモデル (§A.1 の順)",
        _raised(item="<lambda>3"),
    ),
    _m(
        "d40 gate の n_entered を見ない",
        "driver",
        '        if ent != entered or not _same_int(entry.get("n_entered"), len(entered)):\n',
        "        if ent != entered:\n",
        (_G_READ_GATE,),
        "H5: n_entered = 入場の本数",
        _raised(item="<lambda>4"),
    ),
    _m(
        "d41 gate の R が候補かを見ない",
        "driver",
        "                or r not in st.r_candidates(st.SPECS[name])\n",
        "                or False\n",
        (_G_READ_GATE,),
        "H5: R ∈ r_candidates",
        _raised(item="<lambda>5"),
    ),
    _m(
        "d42 gate の R が int かを見ない",
        "driver",
        "                or type(r) is not int\n",
        "                or False\n",
        (_G_READ_GATE, _D_GATE_R),
        "H5: R は整数 (6.0・True を拒む)",
        _raised(item="<lambda>6"),
    ),
    _m(
        "d43 gate の STOP_POWER・NOT_QUALIFIED の R を見ない",
        "driver",
        "            if qualified or r is not None:\n",
        "            if qualified:\n",
        (_D_GATE_NQ_R,),
        "H5: 入場 < 3 の battery に R は無い",
        _raised(),
    ),
    _m(
        "d44 gate の envelope の型を見ない",
        "driver",
        '                or type(env.get("numerator")) is not int\n',
        "                or False\n",
        (_G_READ_GATE,),
        "H5: envelope は整数の分数 (浮動小数を経由しない)",
        # DD-12 で envelope を Fraction に組んで照合するので、浮動小数の分子は Fraction が拒む
        Witness(item="<lambda>8", exc="TypeError", text="Rational"),
    ),
    _m(
        "d45 gate の K・ΣM を再計算と照合しない",
        "driver",
        '    if not _same_int(gate.get("K"), k_tests) or not _same_int(gate.get("sum_M"), sum_m):\n',
        "    if False:\n",
        (_G_READ_GATE,),
        "H5: K・ΣM は入場数から再計算して照合",
        _raised(item="<lambda>0"),
    ),
    _m(
        "d46 gate の GO / HELD_COST を予算の規則と照合しない",
        "driver",
        "    if st.budget(r_all) != labels:\n",
        "    if False:\n",
        (_G_READ_GATE,),
        "H5・§G-5: GO / HELD_COST = stats.budget",
        _raised(item="<lambda>7"),
    ),
    _m(
        "d47 gate の 4 battery を見ない",
        "driver",
        "    if not isinstance(batteries, dict) or set(batteries) != set(st.BATTERIES):\n",
        "    if not isinstance(batteries, dict):\n",
        (_D_GATE_EXTRA,),
        "H5: 登録の 4 battery (余分な battery を拒む)",
        _raised(),
    ),
    _m(
        "d48 本走の plan に入場集合を渡さない",
        "driver",
        "    segs = pl.main_plan(gate.r_by_battery, gate.entrants)\n",
        "    segs = pl.main_plan(gate.r_by_battery)\n",
        (_D_GATE_FILE,),
        "H5: 本走は pilot の入場モデルだけ",
        Witness(exc="PreflightError", text="outside the pilot entrants"),
    ),
    _m(
        "d49 本走の区切りが入場集合の内かを見ない",
        "driver",
        "    if any(s.model not in gate.entrants[s.battery] for s in segs):\n",
        "    if False:\n",
        (_D_PLAN_ENTRANTS,),
        "H5: 報告集合 ⊆ 入場集合",
        _raised(),
    ),
    _m(
        "d50 終了コードで completed でない区切りを見ない",
        "driver",
        "    return EXIT_OK if all(s == S_COMPLETED for s in statuses) else EXIT_INCOMPLETE\n",
        "    return EXIT_OK\n",
        (_D_EXIT,),
        "DD-5: completed でない区切りがあれば終了コード 3",
    ),
    _m(
        "d51 pilot の期限 12 → 24 時間",
        "driver",
        "    pl.STAGE_PILOT: 12 * 3600.0,",
        "    pl.STAGE_PILOT: 24 * 3600.0,",
        (_D_CONSTANTS,),
        "§H: pilot の実時間の停止は 12 時間",
    ),
    _m(
        "d52 期待する Ollama の版を変える",
        "driver",
        'OLLAMA_VERSION: Final[str] = "0.32.12"',
        'OLLAMA_VERSION: Final[str] = "0.32.13"',
        (_D_CONSTANTS,),
        "§A.1: 版 = results/models.json の版",
    ),
    _m(
        "d53 4 回目の送信の失敗の後に期限を見ない",
        "driver",
        "                    if self.deadline.remaining() <= 0:\n"
        "                        raise DeadlineReachedError from exc\n",
        "",
        (_D_LAST_RESEND,),
        "§H・DD-5: 期限の後の送信の失敗は時間切れ (通信の欠測の行を書かない)",
    ),
    _m(
        "d54 request の timeout を期限で切らない",
        "driver",
        "                    reply = await send_chat(self.http, body, min(self.timeout_s, left))\n",
        "                    reply = await send_chat(self.http, body, self.timeout_s)\n",
        (_D_REQ_TIMEOUT,),
        "driver の契約: 期限は request の timeout にも適用する",
    ),
    _m(
        "d55 gate の models.json の sha を見ない",
        "driver",
        '        or inputs.get("models_json_sha256") != models_json_sha256\n',
        "        or False\n",
        (_C_DR_GATE,),
        "DD-12 M1: 本走が使う models.json から作られた gate だけを読む",
        _raised("<lambda>4"),
    ),
    _m(
        "d56 gate の envelope を ⊥ の数からの復元と照合しない",
        "driver",
        '            if Fraction(env["numerator"], env["denominator"]) != want_env:\n',
        "            if False:\n",
        (_C_DR_GATE,),
        "DD-12 H1: envelope = parse_rule(保存の ⊥ の数) の 2 つ目",
        _raised("<lambda>19"),
    ),
    _m(
        "d57 ⊥ の数の型を見ない",
        "driver",
        "            if not all(type(k) is int for k in counts):\n",
        "            if False:\n",
        (_C_DR_GATE,),
        "DD-12 H1: ⊥ の数は整数 (浮動小数は parse_rule の int() で黙って丸まる)",
        _raised("<lambda>26"),
    ),
    _m(
        "d59 ⊥ の数が list かを見ない",
        "driver",
        "            if not isinstance(counts, list):\n",
        "            if False:\n",
        (_C_DR_GATE,),
        "DD-12 H1: ⊥ の数は arm ごとの list",
        Witness(item="<lambda>25", exc="TypeError", text="has no len"),
    ),
    _m(
        "d60 ⊥ の数の arm の数を見ない",
        "driver",
        "            if len(counts) != st.N_ARMS[name]:\n",
        "            if False:\n",
        (_C_DR_GATE,),
        "DD-12 H1: ⊥ の数は登録の arm の数 (stats.qualify と同じ)",
        _raised("<lambda>24"),
    ),
    _m(
        "d61 bot_n が正の整数かを見ない",
        "driver",
        "            if type(n_bot) is not int or n_bot <= 0:\n",
        "            if False:\n",
        (_C_DR_GATE,),
        "DD-12 H1: bot_n は正の整数",
        Witness(item="<lambda>21", exc="TypeError", text="Rational"),
    ),
    _m(
        "d62 ⊥ の数の範囲 [0, bot_n] を見ない",
        "driver",
        "            if not all(0 <= k <= n_bot for k in counts):\n",
        "            if False:\n",
        (_C_DR_GATE,),
        "DD-12 H1: ⊥ の数は [0, bot_n] (負の数は envelope の負の分数と整合してしまう)",
        _raised("<lambda>27"),
    ),
    _m(
        "d63 入場モデルの parse の規則を見ない",
        "driver",
        "            if not parse_ok:\n",
        "            if False:\n",
        (_C_DR_GATE,),
        "DD-12 H1: entered は parse の規則を通る (stats.qualify)",
        _raised("<lambda>28"),
    ),
    _m(
        "d58 gate の models が object かを見ない",
        "driver",
        '        if not isinstance(models, dict):\n            raise _gate_error(f"{name}: models is not an object")\n',
        '        if False:\n            raise _gate_error(f"{name}: models is not an object")\n',
        (_C_DR_GATE,),
        "DD-12 H1: 入場の照合は models の object を読む",
        Witness(item="<lambda>23", exc="AttributeError", text="has no attribute 'get'"),
    ),
    # ---------------------------------------------------------------- plan
    _m(
        "p01 top_k 20 → 40",
        "plan",
        "TOP_K: Final[int] = 20",
        "TOP_K: Final[int] = 40",
        (_P_BODY,),
        "DM-9: top_k = 20 を全モデル・全 stage で明示",
    ),
    _m(
        "p02 body の stream を真に",
        "plan",
        '        "stream": False,\n        "think": THINK,\n',
        '        "stream": True,\n        "think": THINK,\n',
        (_P_BODY,),
        "§A.1: stream = false",
    ),
    _m(
        "p03 送る seed を 1 ずらす",
        "plan",
        '    return {**DECODE, "seed": seed}\n',
        '    return {**DECODE, "seed": seed + 1}\n',
        (_P_BODY,),
        "送る seed = 凍結の sample_seed",
    ),
    _m(
        "p04 v2 の arm の巡回を外す",
        "plan",
        "    shift = block % len(arms)\n",
        "    shift = 0\n",
        (_P_V2_ORDER,),
        "凍結の v2 の順: block mod 4 の巡回",
    ),
    _m(
        "p06 v2 の C0 を落とす",
        "plan",
        "                out.append(spec(v2bat.ARM_C0, P_C0, r, qi, k))\n",
        "                pass\n",
        (_P_COUNTS, _P_ARMS),
        "§G.1: v2 は C0 を含む 5 arm",
    ),
    _m(
        "p07 v3 の block の順を固定",
        "plan",
        "                for arm in v3sc.block_arm_order(v3sc.call_block(r, qi, k)):\n",
        "                for arm in v3sc.block_arm_order(0):\n",
        (_P_V3_ORDER,),
        "凍結の v3 の順: block_arm_order(call_block)",
    ),
    _m(
        "p08 v3 の L arm を判定の arm に数える",
        "plan",
        "            if arm in v3bat.JUDGE_ARMS\n",
        "            if arm in v3bat.ALL_ARMS\n",
        (_P_ARMS,),
        "v3 の L arm の目的は control (資格の材料、判定に使わない)",
    ),
    _m(
        "p09 G の masked を本走の名前空間の seed で",
        "plan",
        '            ns = f"pilot_fam{fi}" if masked else f"fam{fi}"\n',
        '            ns = f"fam{fi}"\n',
        (_P_PILOT_SEED,),
        "§C: masked は pilot の名前空間の seed",
        _assert_in("G"),
    ),
    _m(
        "p10 G の族内の arm を逆順",
        "plan",
        "                        for arm in family:\n",
        "                        for arm in reversed(family):\n",
        (_P_G_ORDER,),
        "凍結の G の順: 族内の 2 arm",
    ),
    _m(
        "p11 G の KNOW の seed の試行を 0 に",
        "plan",
        '            gbat.sample_seed("know", 0, i, k),\n',
        '            gbat.sample_seed("know", 0, i, 0),\n',
        (_P_PILOT_SEED, _P_UNIQUE),
        "§C: KNOW は旧 pilot と同じ seed (試行ごと)",
        _assert_in("G"),
    ),
    _m(
        "p12 O_time の masked・M0 を本走の名前空間の seed で",
        "plan",
        '    ns = f"fam{unit.family}" if mode == "main" else f"{mode}_fam{unit.family}"\n',
        '    ns = f"fam{unit.family}"\n',
        (_P_PILOT_SEED,),
        "§C: masked・M0 は pilot の名前空間の seed",
        _assert_in("O_time"),
    ),
    _m(
        "p13 O_time の masked と M0 の順を入れ替える",
        "plan",
        '        out += _o_unit_specs(u, "masked")\n        out += _o_unit_specs(u, "m0")\n',
        '        out += _o_unit_specs(u, "m0")\n        out += _o_unit_specs(u, "masked")\n',
        (_P_O_ORDER,),
        "凍結の旧 pilot の順: 単位ごとに masked → M0",
    ),
    _m(
        "p14 pilot の lever の r を本走の始点から",
        "plan",
        "    r0 = st.SPECS[battery].pilot_r0\n",
        "    r0 = st.SPECS[battery].main_r0\n",
        (_P_CHECKS,),
        "§C: pilot の r は SPECS の pilot_r0 から R_PILOT 個",
        Witness(item="v2-8", assert_stmt=True, text="pilot r range differs"),
    ),
    _m(
        "p15 pilot の補助の r の始点を 1 巡ずらす",
        "plan",
        'PILOT_AUX_R0: Final[dict[str, int]] = {"G": 24, "O_time": 312}',
        'PILOT_AUX_R0: Final[dict[str, int]] = {"G": 24, "O_time": 315}',
        (_R_ENUM,),
        "§C: O_time の masked・M0 の r は 312–317",
        _assert_in("pilot-O_time-None"),
    ),
    _m(
        "p16 本走の r を pilot の始点から",
        "plan",
        "    r0 = st.SPECS[battery].main_r0\n",
        "    r0 = st.SPECS[battery].pilot_r0\n",
        (_P_MAIN_SEED,),
        "§C: 本走の r は SPECS の main_r0 から (main_calls の r の範囲の検査が拒む)",
        Witness(
            item="v2",
            exc="ValueError",
            text="main r0 differs from the registered value",
        ),
    ),
    _m(
        "p17 本走の r の範囲の検査を外す",
        "plan",
        '    if problems:\n        raise ValueError("; ".join(problems))\n',
        '    if False:\n        raise ValueError("; ".join(problems))\n',
        (_P_MAIN_REJECT,),
        "§C: 本走の r の範囲は機械検査を通る",
        _raised(),
    ),
    _m(
        "p18 再生の r を 1 に",
        "plan",
        "REPLAY_R: Final[int] = 0",
        "REPLAY_R: Final[int] = 1",
        (_P_REPLAY,),
        "§C: 再生は旧 prompt・seed (r 0)",
    ),
    _m(
        "p19 pilot の順を battery → モデルに",
        "plan",
        "        Segment(STAGE_PILOT, b, m, pilot_calls(b)) for m in MODELS for b in st.BATTERIES\n",
        "        Segment(STAGE_PILOT, b, m, pilot_calls(b)) for b in st.BATTERIES for m in MODELS\n",
        (_P_PILOT_ORDER,),
        "§H: モデルは表の順、各モデルの中は v2 → v3 → G → O_time",
    ),
    _m(
        "p20 本走の battery を名前の順に",
        "plan",
        "    return sorted(cost, key=lambda b: (cost[b], b))\n",
        "    return sorted(cost)\n",
        (_P_COST_ORDER,),
        "§H: GO の battery を費用の安い順 (既存の test は費用の順が名前の順と同じ R だった)",
    ),
    _m(
        "p21 本走で入場外のモデルも回す",
        "plan",
        "        if models_by_battery is None or m in models_by_battery[b]\n",
        "        if True\n",
        (_R_DIGESTS,),
        "H5: 本走は入場モデルだけ",
    ),
    _m(
        "p22 messages の sha を ensure_ascii で",
        "plan",
        "    blob = json.dumps(list(messages), ensure_ascii=False, sort_keys=True)\n",
        "    blob = json.dumps(list(messages), ensure_ascii=True, sort_keys=True)\n",
        (_P_SHA,),
        "4 battery の凍結の messages_sha256 と同じ式",
    ),
    _m(
        "p23 区切りの digest から seed を外す",
        "plan",
        "        [*spec.key(), spec.purpose, spec.seed, messages_sha256(spec.messages_list())]\n",
        "        [*spec.key(), spec.purpose, messages_sha256(spec.messages_list())]\n",
        (_P_DIGEST, _R_DIGESTS),
        "meta の digest は seed を含む",
    ),
    _m(
        "p24 plan digest から区切りの名前を外す",
        "plan",
        "        _canonical([[s.name, segment_digest(s)] for s in segments])\n",
        "        _canonical([segment_digest(s) for s in segments])\n",
        (_R_DIGESTS,),
        "plan digest = (区切りの名前, digest) の列",
    ),
    _m(
        "p25 ずらした検査で r をずらさない",
        "plan",
        "        return orig(*head, r0 + r)\n",
        "        return orig(*head, r)\n",
        (_P_SHIFTED, _P_STAGE2_R),
        "H3: 凍結の検査を実 r で評価する",
    ),
    _m(
        "p26 ずらした関数を元に戻さない",
        "plan",
        "        for mod, name, orig in saved:\n            setattr(mod, name, orig)\n",
        "        for mod, name, orig in saved:\n            pass\n",
        (_P_SHIFTED,),
        "差し替えは一時的 (凍結の関数を残す)",
    ),
    _m(
        "p27 G の masked の状態の検査を本登録の r で回さない",
        "plan",
        '    out["masked_states"] = g_masked_states(masked_r) if masked_r else []\n',
        '    out["masked_states"] = []\n',
        (_P_MASKED_R24,),
        "H3: r 固定の masked の検査は本登録の r の列で書き直す",
    ),
    _m(
        "p28 O_time の M0 の状態の検査を回さない",
        "plan",
        '    out["m0_states"] = o_m0_states(units) if units else []\n',
        '    out["m0_states"] = []\n',
        (_P_M0_R312,),
        "H3: r 固定の M0 の検査は本登録の r の列で書き直す",
    ),
    _m(
        "p29 stage 内の seed の重なりを見ない",
        "plan",
        "            if sets[a] & sets[b]:\n",
        "            if False:\n",
        (_P_SEEDS,),
        "§C: 目的の違う呼び出しの seed は交わらない",
    ),
    _m(
        "p30 使用済みの seed との重なりを見ない",
        "plan",
        "            if useeds & sets[name]:\n",
        "            if False:\n",
        (_P_SEEDS,),
        "§C: 段 2 の seed は旧 chain・段 1 と交わらない",
    ),
    _m(
        "p31 送る prompt の byte 予算を見ない",
        "plan",
        "    if worst > v2bat.MAX_PROMPT_BYTES:\n",
        "    if False:\n",
        (_P_BUDGET,),
        "§C: 送る全 prompt の byte 数 ≤ 凍結の上限",
    ),
    _m(
        "p32 本走の r の範囲を pilot の規則で",
        "plan",
        '        rep[f"{stage}:r_range"] = st.check_r_range(spec, rs, main=stage == "main")\n',
        '        rep[f"{stage}:r_range"] = st.check_r_range(spec, rs, main=False)\n',
        (_P_CHECKS,),
        "§C: 本走の r の範囲の検査",
        _assert_in("v2-8"),
    ),
    # ---------------------------------------------------------------- units
    _m(
        "u01 v2・v3 の単位の順を k 外・probe 内に",
        "units",
        '            for qi in range(len(v2bat.lever_probes()))\n            for k in range(_k_count(battery))\n        ]\n    if battery == "G":',
        '            for k in range(_k_count(battery))\n            for qi in range(len(v2bat.lever_probes()))\n        ]\n    if battery == "G":',
        (_U_CELL,),
        "H2: 単位の順 = strata の順 (probe 外・k 内)",
        _assert_in("v2"),
    ),
    _m(
        "u02 v2 の同じ seed の arm を別単位に割る",
        "units",
        "        return [Cell((arm, r, pid, b), arm) for arm in arms]\n",
        "        return [Cell((arm, r, pid, (b + (arm == arms[0])) % _k_count(battery)), arm) for arm in arms]\n",
        (_U_SEED,),
        "H2: 単位のセルは seed を共有する呼び出し",
    ),
    _m(
        "u03 G の単位の族を取り違える",
        "units",
        "            for arm in gbat.FAMILIES[a]\n",
        "            for arm in gbat.FAMILIES[1 - a]\n",
        (_U_G,),
        "H2: G の単位 = (r, 族, つ組)",
        _ALLCLOSE,
    ),
    _m(
        "u04 O_time の単位の部屋をずらす",
        "units",
        "        pid = osc.probe_id(b)\n",
        "        pid = osc.probe_id((b + 1) % obat.N_ROOMS)\n",
        (_U_O,),
        "H2: O_time の単位 = (r, 族, 部屋)",
        _ALLCLOSE,
    ),
    _m(
        "u05 単位の値の分母を 4 に固定",
        "units",
        "    return (c[:, 0] - c[:, 1]) / c[:, 2]\n",
        "    return (c[:, 0] - c[:, 1]) / 4.0\n",
        (_U_G,),
        "§D: 単位の値 = (t − f) / n (G は n = 6)",
        _ALLCLOSE,
    ),
    _m(
        "u07 欠けたセルを ⊥ に畳む",
        "units",
        "    if key not in choices:\n        raise MissingCellError(key)\n    return choices[key]\n",
        "    return choices.get(key)\n",
        (_U_MISSING,),
        "§F-2: 欠けは not_computed (⊥ に畳まない)",
        _raised(),
    ),
    _m(
        "u08 v2 の ⊥ の arm から C0 を外す",
        "units",
        '    "v2": v2bat.ALL_ARMS,\n',
        '    "v2": v2bat.LEVER_ARMS,\n',
        (_U_BOT,),
        "H4: v2 の parse の規則は C0 を含む 5 本",
    ),
    _m(
        "u09 通信の欠測を ⊥ に数える",
        "units",
        '            row["missing"] += 1\n',
        '            row["bot"] += 1\n',
        (_U_SIX,),
        "§B: 6 分類 (⊥ と通信の欠測を分ける)",
    ),
    _m(
        "u10 q を target の率だけで",
        "units",
        "    q = (t + f) / n\n",
        "    q = t / n\n",
        (_U_SIX,),
        "q = target か foil を選んだ率",
    ),
    _m(
        "u11 v2 の k を 9 に",
        "units",
        "V2_K: Final[int] = 10",
        "V2_K: Final[int] = 9",
        (_U_BOT,),
        "v2 の FROZEN_K = 10",
    ),
    # ---------------------------------------------------------------- records
    _m(
        "r01 重複した key を見ない",
        "records",
        '            out.append(f"{name}: duplicate key {key}")\n',
        "            pass\n",
        (_R_STRUCT,),
        "H1: 重複は STOP (records)",
        _assert_in("_drop_dup-duplicate key"),
    ),
    _m(
        "r02 範囲外の key を見ない",
        "records",
        '            out.append(f"{name}: key outside the registered grid {key}")\n',
        "            pass\n",
        (_R_STRUCT,),
        "H1: 範囲外は STOP (records)",
        _assert_in("_out_of_range-outside the registered grid"),
    ),
    _m(
        "r03 呼び出しの順を見ない",
        "records",
        "    if ranks != sorted(ranks):\n",
        "    if False:\n",
        (_R_STRUCT,),
        "H1: 呼び出し順は凍結の順",
        _assert_in("_swap-call order"),
    ),
    _m(
        "r04 seed を見ない",
        "records",
        '        if obj["seed"] != exp.seed:\n',
        "        if False:\n",
        (_R_STRUCT,),
        "H1: seed は凍結の expected_sample",
        _assert_in("_seed-seed differs"),
    ),
    _m(
        "r05 prompt の sha を見ない",
        "records",
        '        if obj["prompt_sha256"] != exp.prompt_sha256:\n',
        "        if False:\n",
        (_R_STRUCT,),
        "H1: prompt の sha は凍結の renderer",
        _assert_in("_prompt-prompt differs"),
    ),
    _m(
        "r06 応答の model を見ない",
        "records",
        '            "response_model": sr.model,\n',
        "",
        (_R_STRUCT,),
        "H1: 応答の model を採用 attempt に結ぶ",
        _assert_in("_other_model-response_model"),
    ),
    _m(
        "r07 int の欄に bool を許す",
        "records",
        "def _is_int(x: object) -> bool:\n    return type(x) is int\n",
        "def _is_int(x: object) -> bool:\n    return isinstance(x, int)\n",
        (_R_STRUCT,),
        "schema: int の欄は bool を拒む",
        _assert_in("_bool_k-k is not int"),
    ),
    _m(
        "r08 目的を見ない",
        "records",
        '        if obj["purpose"] != exp.purpose:\n',
        "        if False:\n",
        (_R_STRUCT,),
        "H1: 目的は登録の grid の目的",
        _assert_in("_purpose_swap-purpose differs"),
    ),
    _m(
        "r09 records の sha を状態表と照合しない",
        "records",
        '    if _sha(rec_bytes) != entry.get("records_sha256"):\n',
        "    if False:\n",
        (_R_SHA,),
        "H6: records の sha を状態表に結ぶ",
    ),
    _m(
        "r10 meta の sha を状態表と照合しない",
        "records",
        '    if _sha(meta_bytes) != entry.get("meta_sha256"):\n',
        "    if False:\n",
        (_R_META_SHA,),
        "H6: meta の sha を状態表に結ぶ",
    ),
    _m(
        "r11 meta の欄を登録と照合しない",
        "records",
        "        if k not in meta or not _same(meta[k], v):\n",
        "        if False:\n",
        (_R_META_FIELDS,),
        "DD-7: completed の区切りの meta は区切り・attempt・版・digest・request が登録どおり",
    ),
    _m(
        "r12 meta の digest・template を models.json と照合しない",
        "records",
        "        if not isinstance(ref, dict) or meta.get(k) != ref.get(k):\n",
        "        if False:\n",
        (_R_META,),
        "§G.2-1: completed の区切りの meta が models.json と食い違えば STOP",
    ),
    _m(
        "r13 meta の template と sha の一致を見ない",
        "records",
        '    elif _sha(template.encode("utf-8")) != meta.get("template_sha256"):\n',
        "    elif False:\n",
        (_R_TEMPLATE_SHA,),
        "DD-2: template の全文と sha が一致",
    ),
    _m(
        "r14 区切りの digest を照合しない",
        "records",
        '        if entry.get("segment_digest") != dig or entry.get("n_calls") != len(calls):\n',
        "        if False:\n",
        (_R_SEG_DIGEST,),
        "DD-7: 区切りの digest を独立に再計算して照合",
    ),
    _m(
        "r15 plan digest を照合しない",
        "records",
        '    if table.get("plan_digest") != plan_digest(digests):\n',
        "    if False:\n",
        (_R_TAMPER,),
        "DD-7: plan digest を独立に再計算して照合",
    ),
    _m(
        "r16 区切りの順を照合しない",
        "records",
        '    if table.get("order") != names:\n',
        "    if False:\n",
        (_R_TAMPER,),
        "§H: 状態表の区切りの順",
    ),
    _m(
        "r17 正しい行の欠けを ok のままにする",
        "records",
        "    if len(seen) < len(calls):\n",
        "    if False:\n",
        (_R_MISSING,),
        "H1: 正しい行の単なる欠けは not_computed",
    ),
    _m(
        "r18 採用 attempt が最後の attempt かを見ない",
        "records",
        '    if entry.get("attempts_run") != attempt:\n',
        "    if False:\n",
        (_R_LAST,),
        "H6: 読み手は採用 attempt (= 最後の attempt) だけを読む",
    ),
    _m(
        "r19 completed でない区切りの採用 attempt を見ない",
        "records",
        '            if entry.get("adopted_attempt") is not None:\n',
        "            if False:\n",
        (_R_ADOPTED_NC,),
        "H6: completed でない区切りに採用 attempt は無い",
    ),
    _m(
        "r20 一部だけの invalid_version を見ない",
        "records",
        "    if R_INVALID_VERSION in statuses and statuses != {R_INVALID_VERSION}:\n",
        "    if False:\n",
        (_R_PARTIAL_VER,),
        "§A.1: 版の違いは run の全モデル (一部だけなら STOP)",
    ),
    _m(
        "r21 invalid_meta を not_computed に畳む",
        "records",
        "                S_INVALID_META: R_INVALID_META,\n",
        "                S_INVALID_META: R_NOT_COMPUTED,\n",
        (_R_NONCOMPLETED,),
        "§A.1・§F-1: digest・template の違いはそのモデルを INVALID (欠測ではない)",
    ),
    _m(
        "r22 n_sends の範囲を見ない",
        "records",
        '        if not 1 <= obj["n_sends"] <= MAX_SENDS:\n',
        "        if False:\n",
        (_R_N_SENDS,),
        "§H: n_sends ∈ [1, 4]",
    ),
    _m(
        "r23 状態表の Ollama の版を models.json と照合しない",
        "records",
        '    if table.get("expected_ollama_version") != reference.get("ollama_version"):\n',
        "    if False:\n",
        (_R_OLLAMA,),
        "§A.1: 状態表の版 = models.json の版",
    ),
    _m(
        "r24 G の KNOW を lever の parse で読む",
        "records",
        "                    (gpg.ARM_KNOW, None, 0, pid, k), P_KNOW, seed, sha, gpg.parse_class\n",
        "                    (gpg.ARM_KNOW, None, 0, pid, k), P_KNOW, seed, sha, gsc.parse_choice\n",
        (_G_REASONS,),
        "H1: G の KNOW は凍結の parse_class",
    ),
    _m(
        "r25 v2 の C0 を lever の block に混ぜる",
        "records",
        "        return (0, block, 0)\n",
        "        return (1, block, -1)\n",
        (_R_ENUM,),
        "凍結の v2 の順: C0 が先",
        _assert_in("pilot-v2-None"),
    ),
    _m(
        "r26 G の族内の arm の順を逆に",
        "records",
        "    return (r, fi, probe.triple, qi, gbat.FAMILIES[fi].index(lever))\n",
        "    return (r, fi, probe.triple, qi, -gbat.FAMILIES[fi].index(lever))\n",
        (_R_ENUM,),
        "凍結の G の順: 族内の arm",
        _assert_in("pilot-G-None"),
    ),
    _m(
        "r27 O_time の masked と M0 の順を入れ替える",
        "records",
        "        for names, purpose in ((masked_of, P_MASKED), (m0_of, P_M0)):\n",
        "        for names, purpose in ((m0_of, P_M0), (masked_of, P_MASKED)):\n",
        (_R_ENUM,),
        "凍結の旧 pilot の順: 単位ごとに masked → M0",
        _assert_in("pilot-O_time-None"),
    ),
    # ---------------------------------------------------------------- pilot gate
    _m(
        "g01 m0_check を辞書の真偽で読む",
        "pilot_gate",
        '    passed = res["passed"] is True\n',
        "    passed = bool(res)\n",
        (_G_REASONS,),
        'H4: lookup = m0_check(...)["passed"] (辞書を真偽にしない)',
    ),
    _m(
        "g02 M0 の区切りが無いモデルを不合格にする",
        "pilot_gate",
        '        return None, {"status": M_LOOKUP_NOT_COMPUTED, "reason": f"O_time: {sr.status}"}\n',
        '        return False, {"status": M_LOOKUP_NOT_COMPUTED, "reason": f"O_time: {sr.status}"}\n',
        (_G_REASONS,),
        "H4: M0 の欠測 (not_computed) と M0 の不合格 (lookup 不成立) を分ける",
    ),
    _m(
        "g03 lookup が計算できないモデルを資格の判定に回す",
        "pilot_gate",
        "            elif lk_ok is None:\n",
        "            elif False:\n",
        (_G_REASONS,),
        "DD-7: M0 が completed でないモデルは全 battery で lookup_not_computed",
    ),
    _m(
        "g04 M0 の行の写しで r を付け替えない",
        "pilot_gate",
        '    x = opg.cell_scores(rd.o_samples(rows, O_AUX_SHIFT), "m0")[0]\n',
        '    x = opg.cell_scores(rd.o_samples(rows), "m0")[0]\n',
        (_G_E2E,),
        "H3: 凍結の集計は r を [300, 306) に付け替えた写しで",
        _INDEX,
    ),
    _m(
        "g05 v3 の L arm を 3 本",
        "pilot_gate",
        '        control, n_c = un.bot_counts("v3", choices, rs, arms=v3bat.CONTROL_ARMS)\n',
        '        control, n_c = un.bot_counts("v3", choices, rs, arms=v3bat.CONTROL_ARMS[:3])\n',
        (_G_E2E, _G_REASONS),
        "H4: v3 の L arm は 4 本 (本数を検査する)",
        Witness(exc="ValueError", text="v3 control arms differ from the registered 4"),
    ),
    _m(
        "g06 G の KNOW の失敗を見ない",
        "pilot_gate",
        "        know_ok = len(know) == N_KNOW and not failures\n",
        "        know_ok = len(know) == N_KNOW\n",
        (_G_REASONS,),
        "H4: KNOW = 36 × 3 完全 + knowledge_failures が空",
    ),
    _m(
        "g07 G の masked の写しで r を付け替えない",
        "pilot_gate",
        "        _, nb = gpg.cell_scores(rd.g_samples(masked, G_MASKED_SHIFT))\n",
        "        _, nb = gpg.cell_scores(rd.g_samples(masked))\n",
        (_G_E2E,),
        "H3: 凍結の集計は r を付け替えた写しで",
        _INDEX,
    ),
    _m(
        "g08 G の masked の envelope を見ない",
        "pilot_gate",
        "        envelope_ok = bool(gsc.bottom_gate_ok(rates))\n",
        "        envelope_ok = True\n",
        (_G_MASKED_G,),
        "H4: masked = 凍結の bottom_gate_ok",
    ),
    _m(
        "g09 O_time の masked の envelope を見ない",
        "pilot_gate",
        "        envelope_ok = bool(osc.bottom_gate_ok(rates))\n",
        "        envelope_ok = True\n",
        (_G_MASKED, _G_REASONS),
        "H4: masked = 凍結の bottom_gate_ok",
    ),
    _m(
        "g10 O_time の masked の写しで r を付け替えない",
        "pilot_gate",
        '        _, nb, _ = opg.cell_scores(rd.o_samples(masked, O_AUX_SHIFT), "masked")\n',
        '        _, nb, _ = opg.cell_scores(rd.o_samples(masked), "masked")\n',
        (_G_E2E,),
        "H3: 凍結の集計は r を付け替えた写しで",
        _INDEX,
    ),
    _m(
        "g11 envelope を浮動小数を経由して",
        "pilot_gate",
        "                    env = st.parse_rule(mp.bot_counts, mp.bot_n)[1]\n",
        "                    env = st.Fraction(float(st.parse_rule(mp.bot_counts, mp.bot_n)[1]))\n",
        (_G_ENVELOPE,),
        "H5: envelope は Fraction の分子と分母 (浮動小数を経由しない)",
    ),
    _m(
        "g12 ΣM に入場 < 3 の battery を数える",
        "pilot_gate",
        "    sum_m = sum(n for n in n_entered.values() if n >= st.MIN_ENTRANTS)\n",
        "    sum_m = sum(n_entered.values())\n",
        (_G_NQ,),
        "§E: ΣM = 入場 ≥ 3 の battery の入場数の和",
    ),
    _m(
        "g13 NOT_QUALIFIED と not_computed を入れ替える",
        "pilot_gate",
        "            else G_NOT_QUALIFIED\n            if computed\n            else G_NOT_COMPUTED,\n",
        "            else G_NOT_COMPUTED\n            if computed\n            else G_NOT_QUALIFIED,\n",
        (_G_NQ,),
        "§G.2: 計算できた battery の入場 < 3 は NOT_QUALIFIED、計算できないのは not_computed",
    ),
    _m(
        "g14 INVALID を計算できたに数える",
        "pilot_gate",
        '            models[m]["status"] not in (M_NOT_COMPUTED, M_INVALID) for m in rd.MODELS\n',
        '            models[m]["status"] not in (M_NOT_COMPUTED,) for m in rd.MODELS\n',
        (_G_INVALID,),
        "INVALID のモデルは資格を計算していない",
    ),
    _m(
        "g15 invalid_meta を not_computed に",
        "pilot_gate",
        "            if sr.status in (rd.R_INVALID_META, rd.R_INVALID_VERSION):\n",
        "            if sr.status in (rd.R_INVALID_VERSION,):\n",
        (_G_INVALID,),
        "§A.1・§F-1: digest・template の違いはそのモデルを INVALID",
    ),
    _m(
        "g16 STOP_POWER の記述の R を候補の最小に",
        "pilot_gate",
        "        r_desc = r_main if r_main is not None else st.r_candidates(spec)[-1]\n",
        "        r_desc = r_main if r_main is not None else st.r_candidates(spec)[0]\n",
        (_G_STOP_POWER,),
        "§G-4: STOP (power) の spike_negative_all は候補の最大で",
    ),
    _m(
        "g17 予算の規則を gate に写さない",
        "pilot_gate",
        '        batteries[b]["gate"] = label\n',
        '        batteries[b]["gate"] = st.GATE_GO\n',
        (_G_BUDGET,),
        "§G-5: GO / HELD_COST = stats.budget",
    ),
    _m(
        "g18 STOP (records) でも判定を続ける",
        "pilot_gate",
        "    if run.stop:\n        return stop_records(run, inputs)\n",
        "    if False:\n        return stop_records(run, inputs)\n",
        (_G_STOP,),
        "§G.2-1: STOP (records) は以後を計算しない",
        Witness(exc="KeyError", via="compute_gate"),
    ),
    _m(
        "g19 gate.json を上書きする",
        "pilot_gate",
        "    if out.exists():\n",
        "    if False:\n",
        (_G_E2E,),
        "DD-7: gate.json を上書きしない",
        _raised(),
    ),
    _m(
        "g20 非有限の float を文字列にしない",
        "pilot_gate",
        "    if isinstance(x, float) and not math.isfinite(x):\n        return str(x)\n",
        "",
        (_G_NONFINITE,),
        "DD-7: 非有限の float は文字列 (allow_nan=False の JSON)",
    ),
    _m(
        "g21 入場を表の順でなく名前の順に",
        "pilot_gate",
        '        entrants = [m for m in rd.MODELS if models[m]["status"] == M_ENTERED]\n',
        '        entrants = sorted(m for m in rd.MODELS if models[m]["status"] == M_ENTERED)\n',
        (_G_E2E,),
        "H5: 入場は §A.1 の表の順",
    ),
    _m(
        "g22 worst_pair の名前を逆に",
        "pilot_gate",
        '                "worst_pair": [entry["entrants"][a], entry["entrants"][c]],\n',
        '                "worst_pair": [entry["entrants"][c], entry["entrants"][a]],\n',
        (_G_WORST,),
        "記述: worst_pair は stats.worst_pair の対",
    ),
    _m(
        "g23 v3 の L arm の ⊥ を記録しない",
        "pilot_gate",
        '        detail["control_counts"] = list(control)\n',
        '        detail["control_counts"] = []\n',
        (_G_REASONS,),
        "H5: arm 別の整数の ⊥ 数を保存",
    ),
    # ---------------------------------------------------------------- stats (複製の中だけ)
    _m(
        "s01 λ の最上段 0.98 → 0.97",
        "stats",
        "LAMBDA_TOP: Final[float] = 0.98",
        "LAMBDA_TOP: Final[float] = 0.97",
        (_S_LAMBDA,),
        "H7: 固定 λ の格子 (§D)",
    ),
    _m(
        "s02 λ の比 0.7 → 0.75",
        "stats",
        "LAMBDA_RATIO: Final[float] = 0.7",
        "LAMBDA_RATIO: Final[float] = 0.75",
        (_S_LAMBDA,),
        "H7: 固定 λ の格子 (§D)",
    ),
    _m(
        "s03 λ の数 12 → 11",
        "stats",
        "N_LAMBDA: Final[int] = 12",
        "N_LAMBDA: Final[int] = 11",
        (_S_LAMBDA,),
        "H7: 固定 λ の格子 (§D)",
    ),
    _m(
        "s04 K を順序なしの対で数える",
        "stats",
        "    return sum(m * (m - 1) for m in entrants.values() if m >= MIN_ENTRANTS)\n",
        "    return sum(m * (m - 1) // 2 for m in entrants.values() if m >= MIN_ENTRANTS)\n",
        (_S_K,),
        "H7: K = 資格を通った battery × 順序対",
    ),
    _m(
        "s05 K に入場 < 3 の battery を数える",
        "stats",
        "    return sum(m * (m - 1) for m in entrants.values() if m >= MIN_ENTRANTS)\n",
        "    return sum(m * (m - 1) for m in entrants.values())\n",
        (_S_K,),
        "H7: K は資格を通った battery だけ",
    ),
    _m(
        "s06 parse の族内差を ≤ で",
        "stats",
        "    ok = top <= BOT_MAX_FR and gap < BOT_FAMILY_GAP_FR\n",
        "    ok = top <= BOT_MAX_FR and gap <= BOT_FAMILY_GAP_FR\n",
        (_S_PARSE,),
        "H7: §A.3 の族内差は厳密な < τ/4",
    ),
    _m(
        "s07 parse の ⊥ の上限を < で",
        "stats",
        "    ok = top <= BOT_MAX_FR and gap < BOT_FAMILY_GAP_FR\n",
        "    ok = top < BOT_MAX_FR and gap < BOT_FAMILY_GAP_FR\n",
        (_S_PARSE,),
        "H7: §A.3 の ⊥ の上限は ≤ 1/5",
    ),
    _m(
        "s08 envelope の上限 1/5 を外す",
        "stats",
        "    return ok, min(BOT_MAX_FR, top + ENVELOPE_MARGIN_FR)\n",
        "    return ok, top + ENVELOPE_MARGIN_FR\n",
        (_S_PARSE,),
        "H7: §F-3 の envelope = min(1/5, pilot の最大 + 1/20)",
    ),
    _m(
        "s09 envelope を超えるの判定を ≥ で",
        "stats",
        "    return any(Fraction(int(k), main_n) > env for k in main_counts)\n",
        "    return any(Fraction(int(k), main_n) >= env for k in main_counts)\n",
        (_S_ENVELOPE,),
        "H7: §F-3 の「超える」は厳密な >",
    ),
    _m(
        "s10 v3 の L arm の上限を < で",
        "stats",
        "        and max(Fraction(int(k), mp.bot_n) for k in mp.control_counts) <= BOT_MAX_FR\n",
        "        and max(Fraction(int(k), mp.bot_n) for k in mp.control_counts) < BOT_MAX_FR\n",
        (_S_CONTROL,),
        "H7: §A の L arm の ⊥ ≤ 1/5",
    ),
    _m(
        "s11 資格で lookup を見ない",
        "stats",
        "    if not mp.lookup_ok:\n        return REASON_LOOKUP\n",
        "",
        (_G_REASONS,),
        "H7: §A の順の最初は lookup",
    ),
    _m(
        "s12 予算の境界を < で",
        "stats",
        "        if cum + cost[n] <= BUDGET_SECONDS:\n",
        "        if cum + cost[n] < BUDGET_SECONDS:\n",
        (_S_BUDGET,),
        "H7: §G-5 の累計は予算ちょうどまで GO",
    ),
    _m(
        "s13 R の候補で上限を外す",
        "stats",
        "    return list(range(spec.r_step, cap + 1, spec.r_step))\n",
        "    return list(range(spec.r_step, cap, spec.r_step))\n",
        (_S_CANDIDATES,),
        "H7: R の候補は上限まで (上限を含む)",
    ),
    _m(
        "s14 判定の水準を α / K から α に",
        "stats",
        "    level = ALPHA / k_tests\n    pairs = ordered_pairs(n_models)\n",
        "    level = ALPHA\n    pairs = ordered_pairs(n_models)\n",
        (_S_LEVEL,),
        "H7: §D の Bonferroni (α / K)",
    ),
    _m(
        "s15 確立の閾値を Δ_min から 0 に",
        "stats",
        "        est.append(rejects_lower(d, DELTA_MIN, -2.0, level))\n",
        "        est.append(rejects_lower(d, 0.0, -2.0, level))\n",
        (_S_DELTA,),
        "H7: §F の確立 = 下限 ≥ Δ_min",
    ),
    _m(
        "s16 同等域を ±0.2 に",
        "stats",
        "        equiv.append(rejects_lower(d, -EQUIV, -2.0, level))\n",
        "        equiv.append(rejects_lower(d, -2 * EQUIV, -2.0, level))\n",
        (_S_EQUIV,),
        "H7: §F の同等域 ±0.10",
    ),
    _m(
        "s17 半分の再現を片方の半分だけで",
        "stats",
        "        rep.append(all(d[halves == h].mean() > DELTA_MIN for h in (0, 1)))\n",
        "        rep.append(all(d[halves == h].mean() > DELTA_MIN for h in (0,)))\n",
        (_S_SPLIT,),
        "H7: §E の split-half は両方の半分",
    ),
    _m(
        "s18 集中の水準を α / ΣM に",
        "stats",
        "    level = ALPHA / (2 * sum_m)\n",
        "    level = ALPHA / sum_m\n",
        (_S_CONC,),
        "H7: §E の集中の同時区間は各側 α / (2 ΣM)",
    ),
    _m(
        "s19 集中で確立を外さない",
        "stats",
        "    ok1 = np.any(est & np.asarray(rep, dtype=bool), axis=-1) & ~np.asarray(\n        concentrated, dtype=bool\n    )\n",
        "    ok1 = np.any(est & np.asarray(rep, dtype=bool), axis=-1)\n",
        (_S_FLOOR,),
        "H7: §F の (1) は集中でないとき",
    ),
    _m(
        "s20 worst_pair の同点を後の対に",
        "stats",
        "            if v > best + 1e-15:\n",
        "            if v >= best - 1e-15:\n",
        (_S_WORST,),
        "H7: 同点は番号の若い対",
    ),
    _m(
        "s21 最小の入場数 3 → 2",
        "stats",
        "MIN_ENTRANTS: Final[int] = 3",
        "MIN_ENTRANTS: Final[int] = 2",
        (_S_K,),
        "H7: 入場 ≥ 3 の battery だけを判定する",
    ),
    _m(
        "g24 worst_pair を stats の対でなく先頭 2 モデルに",
        "pilot_gate",
        '                "worst_pair": [entry["entrants"][a], entry["entrants"][c]],\n',
        '                "worst_pair": [entry["entrants"][0], entry["entrants"][1]],\n',
        (_G_WORST_IDX,),
        "記述: worst_pair は stats.worst_pair の対 (B-2: 非対称な対で pin)",
    ),
    # ---------------------------------------------------------------- scorer
    _m(
        "c01 gate の schema を見ない",
        "scorer",
        '    if gate.get("schema") != GATE_SCHEMA or gate.get("status") != "OK":\n',
        '    if gate.get("status") != "OK":\n',
        (_C_GATE,),
        "H5: OK の pilot gate だけを読む",
        _raised("<lambda>2"),
    ),
    _m(
        "c02 gate の models.json の sha を見ない",
        "scorer",
        '        or inputs.get("models_json_sha256") != models_json_sha256\n',
        "        or False\n",
        (_C_GATE,),
        "DD-10: gate の models.json と使う models.json の一致",
        _raised("<lambda>4"),
    ),
    _m(
        "c03 gate の battery の集合を見ない",
        "scorer",
        "    if not isinstance(batteries, dict) or set(batteries) != set(st.BATTERIES):\n",
        "    if not isinstance(batteries, dict):\n",
        (_C_GATE,),
        "H5: 登録の 4 battery",
        Witness(item="<lambda>13", exc="KeyError"),
    ),
    _m(
        "c04 入場を models の status と照合しない",
        "scorer",
        '        if ent != entered or not _int_eq(entry.get("n_entered"), len(entered)):\n',
        '        if not _int_eq(entry.get("n_entered"), len(entered)):\n',
        (_C_GATE,),
        "H5・DD-12 H1: 入場 = models の status が entered のモデル (§A.1 の順)",
        _raised("<lambda>5"),
    ),
    _m(
        "c05 n_entered を見ない",
        "scorer",
        '        if ent != entered or not _int_eq(entry.get("n_entered"), len(entered)):\n',
        "        if ent != entered:\n",
        (_C_GATE,),
        "H5: n_entered = 入場の数",
        _raised("<lambda>6"),
    ),
    _m(
        "c06 R が候補かを見ない",
        "scorer",
        "                or r not in st.r_candidates(st.SPECS[b])\n",
        "                or False\n",
        (_C_GATE,),
        "H5: R ∈ r_candidates",
        _raised("<lambda>9"),
    ),
    _m(
        "c07 R の型を見ない",
        "scorer",
        "                or type(r) is not int\n",
        "                or False\n",
        (_C_GATE,),
        "H5: R は整数 (8.0 を通さない)",
        _raised("<lambda>8"),
    ),
    _m(
        "c08 STOP_POWER に R があっても通す",
        "scorer",
        '            if not qualified or r is not None:\n                raise GateError(f"{b}: STOP_POWER',
        '            if not qualified:\n                raise GateError(f"{b}: STOP_POWER',
        (_C_GATE,),
        "H5: STOP_POWER は R を持たない",
        _raised("<lambda>7"),
    ),
    _m(
        "c09 envelope の分子の型を見ない",
        "scorer",
        '                or type(env.get("numerator")) is not int\n',
        "                or False\n",
        (_C_GATE,),
        "H5: envelope は整数の分数",
        Witness(item="<lambda>11", exc="TypeError"),
    ),
    _m(
        "c10 envelope の分母 0 を通す",
        "scorer",
        '                or env["denominator"] <= 0\n',
        '                or env["denominator"] < 0\n',
        (_C_GATE,),
        "H5: envelope の分母は正",
        Witness(item="<lambda>12", exc="ZeroDivisionError"),
    ),
    _m(
        "c11 gate の ΣM を見ない",
        "scorer",
        '    if not _int_eq(gate.get("K"), k_tests) or not _int_eq(gate.get("sum_M"), sum_m):\n',
        '    if not _int_eq(gate.get("K"), k_tests):\n',
        (_C_GATE,),
        "H5: ΣM を入場数から再計算して照合",
        _raised("<lambda>1"),
    ),
    _m(
        "c12 gate の K を見ない",
        "scorer",
        '    if not _int_eq(gate.get("K"), k_tests) or ',
        "    if ",
        (_C_GATE,),
        "H5: K を入場数から再計算して照合",
        _raised("<lambda>0"),
    ),
    _m(
        "c13 ΣM に資格不足の battery も数える",
        "scorer",
        "    sum_m = sum(n for n in n_entered.values() if n >= st.MIN_ENTRANTS)\n",
        "    sum_m = sum(n_entered.values())\n",
        (_C_GATE_NQ,),
        "§D: ΣM は入場 ≥ 3 の battery の和",
        Witness(exc="GateError"),
    ),
    _m(
        "c14 予算の規則を照合しない",
        "scorer",
        "    if st.budget(r_sel) != {b: labels[b] for b in r_sel}:\n",
        "    if False:\n",
        (_C_GATE,),
        "H5: GO / HELD_COST は予算の規則の再計算",
        _raised("<lambda>10"),
    ),
    _m(
        "c15 GO の無い gate を通す",
        "scorer",
        '    if not r_go:\n        raise GateError("no GO battery")\n',
        '    if False:\n        raise GateError("no GO battery")\n',
        (_C_GATE,),
        "本走は GO の battery を回す",
        _raised("<lambda>15"),
    ),
    _m(
        "c16 判定の K・ΣM を報告集合から計算し直す",
        "scorer",
        "        gate.k_tests,\n        gate.sum_m,\n        halves,\n        cell_counts=c_arr,\n",
        "        st.n_tests({battery: len(report)}),\n        len(report),\n        halves,\n        cell_counts=c_arr,\n",
        (_C_DECIDE_ARGS,),
        "§D・§F: K・ΣM は gate の値 (本走で外したモデルの分を減らさない)",
        # stats.decide_battery が K・ΣM と入場数の整合を検査して止める
        Witness(exc="ValueError", text="K・ΣM が入場集合の本数と整合しない"),
    ),
    _m(
        "c17 判定の n_entered を報告集合の数に",
        "scorer",
        "        not_computed=no_records and not all_invalid,\n        n_entered=len(entrants),\n",
        "        not_computed=no_records and not all_invalid,\n        n_entered=len(report),\n",
        (_C_DROPPED,),
        "§F: 入場の一部を外した否定は NEGATIVE_SUBSET",
    ),
    _m(
        "c18 半分のラベルを全部 0 に",
        "scorer",
        "    halves = st.half_labels(spec, r_list)\n",
        "    halves = np.zeros(n_units, dtype=int)\n",
        (_C_DECIDE_ARGS,),
        "§F: 半分は位置の 1 巡の block の偶奇 (stats.half_labels)",
        # 片方の半分が空になり、半分の点推定が空の平均の警告 (pytest の設定で error) で止まる
        Witness(exc="RuntimeWarning", text="Mean of empty slice"),
    ),
    _m(
        "c19 envelope を gate でなく固定の 1/20 に",
        "scorer",
        "        env = gate.envelopes[(battery, m)]\n",
        "        env = Fraction(1, 20)\n",
        (_C_ENV_GATE,),
        "§F-3: envelope は gate の整数の分数",
    ),
    _m(
        "c20 envelope の超過で外さない",
        "scorer",
        "        if st.envelope_exceeded(bots, n_arm, env):\n",
        "        if False:\n",
        (_C_ENV_BOUND,),
        "§F-3: ⊥ が envelope を超えたモデルを外す",
        _assert_in("25-True"),
    ),
    _m(
        "c21 meta の違反を INVALID でなく not_computed に",
        "scorer",
        "        if sr.status in (rd.R_INVALID_META, rd.R_INVALID_VERSION):\n            excluded.append(",
        "        if False:\n            excluded.append(",
        (_C_INV_META,),
        "§F: 外す理由は INVALID → not_computed → envelope の順",
    ),
    _m(
        "c22 全モデルの meta の違反を INVALID にしない",
        "scorer",
        "    all_invalid = all(s in (rd.R_INVALID_META, rd.R_INVALID_VERSION) for s in statuses)\n",
        "    all_invalid = False\n",
        (_C_ALL_INV,),
        "§F-1: 全モデル INVALID = battery INVALID",
    ),
    _m(
        "c23 記録の無い battery を not_computed にしない",
        "scorer",
        "        not_computed=no_records and not all_invalid,\n",
        "        not_computed=False,\n",
        (_C_NOT_COMP,),
        "§F: 記録のあるモデルが無い = not_computed",
    ),
    _m(
        "c24 区切りの外の違反を battery に割り当てない",
        "scorer",
        "        if not own or any(n in names for n in own):\n",
        "        if any(n in names for n in own):\n",
        (_C_RUN_VIOL,),
        "DD-10: 区切りの外 (状態表・plan digest) の違反は全 battery",
    ),
    _m(
        "c25 他の battery の区切りの違反も拾う",
        "scorer",
        "        if not own or any(n in names for n in own):\n",
        "        if True:\n",
        (_C_REC_VIOL,),
        "DD-10: 区切りの違反はその battery だけを INVALID にする",
    ),
    _m(
        "c26 fixture を名指しに条件付きで併記する",
        "scorer",
        '                "fixture_pairs": fx_pairs,\n',
        '                "fixture_pairs": [] if (a, b) in sens else fx_pairs,\n',
        (_C_FX_PAIRS,),
        "§J: 名指した対に常に併記する",
    ),
    _m(
        "c27 fixture の再計算と比べない",
        "scorer",
        '        if fxm.compute_text(gate_path).encode("utf-8") != fx_bytes:\n',
        "        if False:\n",
        (_C_FX_MISMATCH,),
        "§J・§F-1: fixture の byte が違えば全 battery INVALID",
    ),
    _m(
        "c28 fixture の file が無くても通す",
        "scorer",
        '        global_invalid.append("fixture_diffs_main.json is missing")\n',
        "        pass\n",
        (_C_FX_MISMATCH,),
        "§J: fixture が無ければ全 battery INVALID",
    ),
    _m(
        "c29 全体の違反を battery に渡さない",
        "scorer",
        "            batteries[b] = score_battery(b, run, gate, fixture.get(b), global_invalid)\n",
        "            batteries[b] = score_battery(b, run, gate, fixture.get(b), [])\n",
        (_C_FX_MISMATCH,),
        "§F-1: fixture の照合の違反は全 battery",
    ),
    _m(
        "c30 記述の対の水準を α/(2K) に",
        "scorer",
        "    level = st.ALPHA / gate.k_tests  #",
        "    level = st.ALPHA / (2 * gate.k_tests)  #",
        (_C_LEVELS,),
        "DD-10: 記述の対の下限は判定と同じ水準 α/K",
    ),
    _m(
        "c31 モデルの C の区間の水準を α/ΣM に",
        "scorer",
        "    level_c = st.ALPHA / (2 * gate.sum_m)\n",
        "    level_c = st.ALPHA / gate.sum_m\n",
        (_C_LEVELS,),
        "§M: モデルの C の両側区間は α/(2ΣM)",
    ),
    _m(
        "c32 2 回計算の比較を外す",
        "scorer",
        "    if texts[0] != texts[1]:\n",
        "    if False:\n",
        (_C_NONDET,),
        "DD-10: 2 回計算して byte が違えば書かない",
        _raised(),
    ),
    _m(
        "c33 verdict.json を上書きする",
        "scorer",
        '        with out.open("xb") as fh:\n',
        '        with out.open("wb") as fh:\n',
        (_C_OUTPUT,),
        "DD-10: 出力は上書きしない",
        _raised(),
    ),
    _m(
        "c34 --check が byte を比べない",
        "scorer",
        '            same = args.out.read_bytes() == body.encode("utf-8")\n',
        "            same = True\n",
        (_C_OUTPUT,),
        "DD-10: --check は byte 比較",
    ),
    _m(
        "c35 判定が出ても終わりの文を書く",
        "scorer",
        '            "line_end": None if established else LINE_END_TEXT,\n',
        '            "line_end": None,\n',
        (_C_EQUAL,),
        "§M: 確立した battery が無ければ終わりの文",
    ),
    _m(
        "c36 qwen3 の大きさの予測の向きを逆に",
        "scorer",
        "            agree = rank[a] > rank[b]\n",
        "            agree = rank[a] < rank[b]\n",
        (_C_QWEN,),
        "§M: qwen3 は大きいほど C が高いという予測",
    ),
    _m(
        "c37 gate の status を見ない",
        "scorer",
        '    if gate.get("schema") != GATE_SCHEMA or gate.get("status") != "OK":\n',
        '    if gate.get("schema") != GATE_SCHEMA:\n',
        (_C_GATE,),
        "H5: OK の pilot gate だけを読む (STOP_RECORDS を通さない)",
        _raised("<lambda>3"),
    ),
    _m(
        "c38 入場 3 未満の battery の GO を通す",
        "scorer",
        "                not qualified\n                or type(r) is not int\n",
        "                type(r) is not int\n",
        (_C_GATE,),
        "H7: GO・HELD_COST は入場 ≥ 3 の battery だけ (code-reviewer MEDIUM)",
        _raised("<lambda>16"),
    ),
    _m(
        "c39 入場 3 以上の battery の NOT_QUALIFIED を通す",
        "scorer",
        "            if qualified or r is not None:\n",
        "            if r is not None:\n",
        (_C_GATE,),
        "H7: 入場 ≥ 3 の battery を資格不足と書かせない (code-reviewer MEDIUM)",
        _raised("<lambda>17"),
    ),
    _m(
        "c40 run 全体の invalid_version を battery INVALID にしない",
        "scorer",
        "    all_invalid = all(s in (rd.R_INVALID_META, rd.R_INVALID_VERSION) for s in statuses)\n",
        "    all_invalid = all(s in (rd.R_INVALID_META,) for s in statuses)\n",
        (_C_INV_VERSION,),
        "§A.1・§F-1: 版を混ぜた run は INVALID (not_computed でない、code-reviewer MEDIUM)",
    ),
    _m(
        "c41 invalid_version のモデルを not_computed で外す",
        "scorer",
        "        if sr.status in (rd.R_INVALID_META, rd.R_INVALID_VERSION):\n",
        "        if sr.status in (rd.R_INVALID_META,):\n",
        (_C_INV_VERSION,),
        "§F: invalid_version で外すモデルの理由は INVALID",
    ),
    _m(
        "c42 名指しの対の感度を常に満たすと書く",
        "scorer",
        '                "sensitivity_ok": (a, b) in sens,\n',
        '                "sensitivity_ok": True,\n',
        (_C_INSENSITIVE,),
        "§M: 感度は decide_battery の sensitivity_ok (code-reviewer MEDIUM)",
    ),
    _m(
        "c43 感度の無い対を「得点差まで」と書かない",
        "scorer",
        '            if not p["sensitivity_ok"] or battery == "v3":\n',
        '            if battery == "v3":\n',
        (_C_INSENSITIVE,),
        "§M: 感度を満たさない対は得点差までに固定する",
    ),
    _m(
        "c44 名指しの対の向きを逆に",
        "scorer",
        '                "pair": [report[a], report[b]],\n                "lower_bound": _f(\n',
        '                "pair": [report[b], report[a]],\n                "lower_bound": _f(\n',
        (_C_GRADED,),
        "§M: 名指しは高い方 > 低い方",
    ),
    _m(
        "c45 qwen3 の大きさの順の判定を逆に",
        "scorer",
        '        order = "一致" if cs == sorted(cs) else "不一致"\n',
        '        order = "一致" if cs == sorted(cs, reverse=True) else "不一致"\n',
        (_C_QWEN,),
        "§M: 大きさの順に C が増えれば一致",
    ),
    _m(
        "c46 envelope を ⊥ の数からの復元と照合しない",
        "scorer",
        "            if envelopes[(b, m)] != want_env:\n",
        "            if False:\n",
        (_C_GATE,),
        "DD-12 H1: envelope = parse_rule(保存の ⊥ の数) の 2 つ目",
        _raised("<lambda>19"),
    ),
    _m(
        "c47 ⊥ の数の型を見ない",
        "scorer",
        "            if not all(type(k) is int for k in counts):\n",
        "            if False:\n",
        (_C_GATE,),
        "DD-12 H1: ⊥ の数は整数 (浮動小数は parse_rule の int() で黙って丸まる)",
        _raised("<lambda>26"),
    ),
    _m(
        "c52 ⊥ の数が list かを見ない",
        "scorer",
        "            if not isinstance(counts, list):\n",
        "            if False:\n",
        (_C_GATE,),
        "DD-12 H1: ⊥ の数は arm ごとの list",
        Witness(item="<lambda>25", exc="TypeError", text="has no len"),
    ),
    _m(
        "c53 ⊥ の数の arm の数を見ない",
        "scorer",
        "            if len(counts) != st.N_ARMS[b]:\n",
        "            if False:\n",
        (_C_GATE,),
        "DD-12 H1: ⊥ の数は登録の arm の数 (stats.qualify と同じ)",
        _raised("<lambda>24"),
    ),
    _m(
        "c54 bot_n が正の整数かを見ない",
        "scorer",
        "            if type(n_bot) is not int or n_bot <= 0:\n",
        "            if False:\n",
        (_C_GATE,),
        "DD-12 H1: bot_n は正の整数",
        Witness(item="<lambda>21", exc="TypeError", text="Rational"),
    ),
    _m(
        "c55 ⊥ の数の範囲 [0, bot_n] を見ない",
        "scorer",
        "            if not all(0 <= k <= n_bot for k in counts):\n",
        "            if False:\n",
        (_C_GATE,),
        "DD-12 H1: ⊥ の数は [0, bot_n] (負の数は envelope の負の分数と整合してしまう)",
        _raised("<lambda>27"),
    ),
    _m(
        "c56 入場モデルの parse の規則を見ない",
        "scorer",
        "            if not parse_ok:\n",
        "            if False:\n",
        (_C_GATE,),
        "DD-12 H1: entered は parse の規則を通る (stats.qualify)",
        _raised("<lambda>28"),
    ),
    _m(
        "c48 models が object かを見ない",
        "scorer",
        '        if not isinstance(models, dict):\n            raise GateError(f"{b}: models is not an object")\n',
        '        if False:\n            raise GateError(f"{b}: models is not an object")\n',
        (_C_GATE,),
        "DD-12 H1: 入場の照合は models の object を読む",
        Witness(item="<lambda>23", exc="AttributeError", text="has no attribute 'get'"),
    ),
    _m(
        "c49 名指しの対を報告集合でなく入場の添字で書く",
        "scorer",
        '            {\n                "pair": [report[a], report[b]],\n                "lower_bound"',
        '            {\n                "pair": [gate.entrants[battery][a], gate.entrants[battery][b]],\n                "lower_bound"',
        (_C_EXCL_META,),
        "DD-12 M2: 名指しは報告集合 (除外の後) の添字",
    ),
    _m(
        "c50 併記を近傍の方策との対だけにする",
        "scorer",
        '                "fixture_pairs": fx_pairs,\n',
        '                "fixture_pairs": [q for q in fx_pairs if "nearest" in q["low"]],\n',
        (_C_FX_FILE,),
        "§J・DD-12 M3: fixture の対の全部を併記する",
    ),
    _m(
        "c51 O_time の 6 分類を書き方で分けない",
        "scorer",
        "        arm, enc = cell.key[0], cell.key[1]\n",
        '        arm, enc = cell.key[0], "asc"\n',
        (_C_ENCODING,),
        "§B・DD-12 M4: O_time の 6 分類は (arm, 書き方) ごと",
    ),
    # ---------------------------------------------------------------- fixtures
    _m(
        "f01 v3 の by_score の同点を後ろの選択肢に",
        "fixtures",
        "        best = max(range(len(opts)), key=lambda i: (score(rows, p, opts[i]), -i))\n",
        "        best = max(range(len(opts)), key=lambda i: (score(rows, p, opts[i]), i))\n",
        (_F_PORTED,),
        "DD-10: 原本 by_score の同点は表示順",
        _assert_in("v3"),
    ),
    _m(
        "f02 近傍の signature の切り方を変える",
        "fixtures",
        "    labels = [x.action for x in _succ(rows) if x.signature[1:] == p.signature[1:]]\n",
        "    labels = [x.action for x in _succ(rows) if x.signature[:2] == p.signature[:2]]\n",
        (_F_PORTED,),
        "DD-10: 近傍は weather を無視し時刻・同伴が一致",
        _assert_in("v3"),
    ),
    _m(
        "f03 陽性対照の weather の欄を取り違える",
        "fixtures",
        "    labels = [x.action for x in _succ(rows) if x.signature[0] == p.signature[0]]\n",
        "    labels = [x.action for x in _succ(rows) if x.signature[1] == p.signature[1]]\n",
        (_F_PORTED,),
        "DD-10: 陽性対照は weather の一致",
        _assert_in("v3"),
    ),
    _m(
        "f04 v3 の priming の同点を後ろに",
        "fixtures",
        "    return max(opts, key=lambda o: (labels.count(o), -opts.index(o)))\n",
        "    return max(opts, key=lambda o: (labels.count(o), opts.index(o)))\n",
        (_F_PORTED,),
        "DD-10: 原本 priming の同点は表示順",
        _assert_in("v3"),
    ),
    _m(
        "f06 隣の行の範囲の端を落とす",
        "fixtures",
        "            if x.success and 0 <= i + offset < len(rows)\n",
        "            if x.success and 0 < i + offset < len(rows)\n",
        (_F_PORTED,),
        "DD-10: 原本 _adjacent の範囲",
        _assert_in("v3"),
    ),
    _m(
        "f07 hash 方策の byte を取り違える",
        "fixtures",
        "        return opts[h[0] % len(opts)]\n",
        "        return opts[h[1] % len(opts)]\n",
        (_F_PORTED,),
        "DD-10: 原本 _hash_policy",
        _assert_in("v3"),
    ),
    _m(
        "f08 v2 の uniform_null から r を外す",
        "fixtures",
        "    return _opts(r, p)[(k + r) % 4]\n",
        "    return _opts(r, p)[k % 4]\n",
        (_F_PORTED,),
        "DD-10: 原本 uniform_null",
        _assert_in("v2"),
    ),
    _m(
        "f09 v2 の recency を最初のエントリに",
        "fixtures",
        "    return v2bat.state_entries(arm, v2bat.layout(r))[-1][1]\n",
        "    return v2bat.state_entries(arm, v2bat.layout(r))[0][1]\n",
        (_F_PORTED,),
        "DD-10: 原本 recency (最後のエントリ)",
        _assert_in("v2"),
    ),
    _m(
        "f10 label_prior の昇順・降順を入れ替える",
        "fixtures",
        '    rank = sorted(V2_ACTIONS, reverse=order == "desc")\n',
        '    rank = sorted(V2_ACTIONS, reverse=order == "asc")\n',
        (_F_LABEL_PRIOR,),
        "DD-10: label_prior[asc] は語彙の昇順で最上位",
    ),
    _m(
        "f11 陽性対照も nuisance の対に入れる",
        "fixtures",
        "        if not p.positive_control:\n            nuisance[p.name] = c\n",
        "        if True:\n            nuisance[p.name] = c\n",
        (_F_REAL,),
        "§J: 陽性対照を除く方策の対",
    ),
    _m(
        "f12 Δ_min ちょうどを超えたと数える",
        "fixtures",
        '        if abs(q["diff"]) > st.DELTA_MIN + 10.0**-ROUND:\n',
        '        if abs(q["diff"]) > st.DELTA_MIN - 10.0**-ROUND:\n',
        (_F_PAIRS,),
        "§J: |ΔC| > Δ_min (ちょうどは超えない)",
    ),
    _m(
        "f13 対の差の符号を逆に",
        "fixtures",
        '    return [\n        {"a": a, "b": b, "diff": round(cs[a] - cs[b], ROUND)}\n',
        '    return [\n        {"a": a, "b": b, "diff": round(cs[b] - cs[a], ROUND)}\n',
        (_F_PAIRS,),
        "diff = C_a − C_b",
    ),
    _m(
        "f14 R の無い battery も計算する",
        "fixtures",
        '        if r is None:\n            batteries[b] = {\n                "status": NOT_SELECTED,\n',
        '        if False:\n            batteries[b] = {\n                "status": NOT_SELECTED,\n',
        (_F_REAL,),
        "DD-10: gate が R を選んでいない battery は not_selected",
        # DD-12 H3: R = None が main_r_list に届いた TypeError だけを数える (別の setup の TypeError でない)
        Witness(when="setup", exc="TypeError", text="NoneType", via="main_r_list"),
    ),
    _m(
        "f15 本走の r を 0 起点に",
        "fixtures",
        "    r0 = st.SPECS[battery].main_r0\n",
        "    r0 = 0\n",
        (_F_REAL,),
        "§J: 段 2 の本走の r の上で計算する",
    ),
    _m(
        "f16 fixture_diffs_main.json を上書きする",
        "fixtures",
        '        with args.out.open("xb") as fh:\n',
        '        with args.out.open("wb") as fh:\n',
        (_F_CLI,),
        "DD-10: 出力は上書きしない",
    ),
    _m(
        "f17 --check が byte を比べない",
        "fixtures",
        '        same = args.out.read_bytes() == body.encode("utf-8")\n',
        "        same = True\n",
        (_F_CLI,),
        "DD-10: --check は byte 比較",
    ),
)

# ---------------------------------------------------------------- meta-test

META_CASES: tuple[tuple[str, str, str, str, tuple[str, ...]], ...] = (
    (
        "送信前の照合 ObservingTransport を素通りに潰す",
        "driver",
        "    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:\n",
        "    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:\n"
        "        return await self.inner.handle_async_request(request)\n",
        (_D_OBSERVER,),
    ),
    (
        "記録の読み手の completed の検査 _read_completed を素通りに潰す",
        "records",
        '    """completed の区切りを読み、STOP (records) の違反を返す (欠けだけなら sr を not_computed にする)."""\n',
        '    """completed の区切りを読み、STOP (records) の違反を返す (欠けだけなら sr を not_computed にする)."""\n'
        "    return []\n",
        (_R_STRUCT, _R_SHA, _R_MISSING),
    ),
    (
        "gate.json の契約 read_gate の検査を素通りに潰す",
        "driver",
        "def read_gate(gate: Mapping[str, Any], models_json_sha256: str) -> MainGate:\n",
        "def read_gate(gate: Mapping[str, Any], models_json_sha256: str) -> MainGate:\n"
        "    return MainGate({}, {}, 0, 0)\n",
        (_G_READ_GATE, _D_GATE_R),
    ),
    (
        "scorer の gate.json の照合 read_gate を素通りに潰す",
        "scorer",
        "def read_gate(gate: Mapping[str, Any], models_json_sha256: str) -> GateRead:\n",
        "def read_gate(gate: Mapping[str, Any], models_json_sha256: str) -> GateRead:\n"
        "    return GateRead({}, {}, {}, {}, 0, 0)\n",
        (_C_GATE,),
    ),
)


# ------------------------------------------------- 証拠の記録 (pytest の plugin)


def _exception_text(exc: BaseException) -> str:
    try:
        return str(exc)
    except Exception:  # noqa: BLE001 — 文を作れない例外も記録する
        return f"<unprintable {type(exc).__name__}>"


def _chain(exc: BaseException) -> list[dict[str, object]]:
    """例外の chain (先頭 → ``__cause__`` / ``__context__``)。各例外の型の完全名・文・フレーム (ファイル名, 関数名)."""
    out: list[dict[str, object]] = []
    seen: set[int] = set()
    cur: BaseException | None = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        frames = [
            [pathlib.PurePath(f.filename).name, f.name]
            for f in traceback.extract_tb(cur.__traceback__)
        ]
        kind = type(cur)
        out.append(
            {
                "type": f"{kind.__module__}.{kind.__qualname__}",
                "text": _exception_text(cur),
                "frames": frames,
            }
        )
        if cur.__cause__ is not None:
            cur = cur.__cause__
        else:
            cur = None if cur.__suppress_context__ else cur.__context__
    return out


def _assert_stmt(exc: BaseException, function: str) -> bool:
    """先頭の例外が witness の test ファイルの ``assert`` 文 (pytest が書き換えたもの) から出た AssertionError か.

    最後のフレームの関数名が test の関数 (``function``) と一致することも求める (B-2: test の helper の assert は数えない)。
    """
    if not isinstance(exc, AssertionError):
        return False
    frames = traceback.extract_tb(exc.__traceback__)
    if not frames:
        return False
    last = frames[-1]
    line = (last.line or "").lstrip()
    return (
        pathlib.PurePath(last.filename).name in _TEST_FILE_NAMES
        and last.name == function
        and bool(_ASSERT_WORD.match(line))
    )


def pytest_exception_interact(node: object, call: object) -> None:
    """pytest の hook (``-p`` で harness を読み込ませたときだけ働く): 失敗ごとに証拠の記録を 1 行書く."""
    out = os.environ.get(_WITNESS_ENV)
    excinfo = getattr(call, "excinfo", None)
    if not out or excinfo is None:
        return
    exc = excinfo.value
    function = getattr(node, "originalname", None) or getattr(node, "name", "")
    _append(
        out,
        {
            "function": function,
            "param": getattr(getattr(node, "callspec", None), "id", None),
            "when": getattr(call, "when", None),
            "assert_stmt": _assert_stmt(exc, str(function)),
            "chain": _chain(exc),
        },
    )


_FINISHED_ITEMS: list[str] = []


def pytest_runtest_logfinish(nodeid: str) -> None:
    """item の setup・call・teardown が走りきるたびに呼ばれる pytest の hook."""
    _FINISHED_ITEMS.append(nodeid)


def pytest_sessionfinish(session: object, exitstatus: object) -> None:
    """session の終わりを 1 行書く pytest の hook (exitstatus・選ばれた item の数・走りきった数・打ち切りの印)."""
    out = os.environ.get(_WITNESS_ENV)
    if not out:
        return
    items = getattr(session, "items", None)
    _append(
        out,
        {
            "when": _FINISH,
            "exitstatus": int(exitstatus) if isinstance(exitstatus, int) else None,
            "collected": getattr(session, "testscollected", None),
            "failed": getattr(session, "testsfailed", None),
            "items": len(items) if isinstance(items, list) else None,
            "ran": len(_FINISHED_ITEMS),
            "stopped": bool(getattr(session, "shouldstop", False))
            or bool(getattr(session, "shouldfail", False)),
        },
    )


def _append(out: str, row: dict[str, object]) -> None:
    with pathlib.Path(out).open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row, ensure_ascii=True) + "\n")


def read_records(path: pathlib.Path) -> list[dict[str, Any]]:
    """証拠の記録を読む (ensure_ascii で書いたので、行は LF だけで切れる)."""
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    return [json.loads(line) for line in text.split("\n") if line]


# ---------------------------------------------------------------- 実行


def run_env(
    env: dict[str, str], witness: pathlib.Path, cache: pathlib.Path
) -> dict[str, str]:
    """各 run の env: 証拠の置き場所・空の bytecode の置き場所・書き込みの停止 (計測を変える env は外す)."""
    out = {k: v for k, v in env.items() if k not in _DROPPED_ENV}
    out.update(
        {
            _WITNESS_ENV: str(witness),
            "PYTHONPYCACHEPREFIX": str(cache),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    return out


_DEF = re.compile(r"^(?:async )?def (test_\w+)\(", re.MULTILINE)


def index_tests(root: pathlib.Path = _REPO_ROOT) -> dict[str, str]:
    """witness の test の関数名 → test ファイル (repo 相対)。同じ名前が 2 つのファイルにあれば誤り."""
    out: dict[str, str] = {}
    for rel in _witness_test_files(root):
        for name in _DEF.findall((root / rel).read_text(encoding="utf-8")):
            if name in out:
                msg = f"test name {name} defined twice ({out[name]}, {rel})"
                raise ValueError(msg)
            out[name] = rel
    return out


def _files_for(expect: frozenset[str], index: dict[str, str]) -> list[str]:
    missing = sorted(n for n in expect if n not in index)
    if missing:
        msg = f"expected tests not found: {missing}"
        raise KeyError(msg)
    return sorted({index[n] for n in expect})


def _run_tests(
    env: dict[str, str], files: list[str], root: pathlib.Path = _REPO_ROOT
) -> tuple[int, set[str], bool, list[dict[str, Any]]]:
    """test ファイルを、harness を plugin として読み込ませて実行する.

    返り値 = (exit code, 落ちた test (関数名), collection error, 証拠の記録)。
    """
    fd, name = tempfile.mkstemp(prefix="bs2_witness_", suffix=".jsonl")
    os.close(fd)
    witness = pathlib.Path(name)
    cache = pathlib.Path(tempfile.mkdtemp(prefix="bs2_pycache_"))
    try:
        proc = subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-rfE",
                "-p",
                "no:cacheprovider",
                "-p",
                _PLUGIN,
                *files,
            ],
            cwd=str(root),
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            env=run_env(env, witness, cache),
            check=False,
            timeout=_TEST_TIMEOUT_S,
        )
        records = read_records(witness)
    finally:
        witness.unlink(missing_ok=True)
        shutil.rmtree(cache, ignore_errors=True)
    out = proc.stdout or ""
    failed = {str(r.get("function")) for r in records if r.get("when") in _PHASES}
    collect_error = (
        "ERROR collecting" in out
        or "Interrupted" in out
        or any(r.get("when") == "collect" for r in records)
    )
    return proc.returncode, failed, collect_error, records


# 公開の certification に、手元の path (OS のユーザー名を含む) とメモリの address を残さない (O_time と同じ)
_LOCAL_TEXT = (
    (
        re.compile(
            r"(?:[A-Za-z]:)?[\\/]+(?:Users|home)[\\/]+"
            r"(?:[^\\/'\"\n]*?[^\\/'\"\s](?=[\\/])|[^\\/'\"\s]+)",
            re.IGNORECASE,
        ),
        "<home>",
    ),
    (re.compile(r"/root(?=[\\/'\"\s]|$)"), "<home>"),
    (re.compile(r"pytest-of-[^\\/'\"\s]+"), "pytest-of-<user>"),
    (re.compile(r"(?<= at )0x[0-9A-Fa-f]{8,}"), "0x?"),
    (re.compile(r"(?<=\.\.\.)[0-9A-Fa-f]{6,}(?=>)"), "?"),
)
_PATH_END = r"(?![\w.-])"


def _local_names() -> list[tuple[str, str]]:
    bs = chr(92)
    found: list[tuple[str, str]] = []
    for get, placeholder in (
        (tempfile.gettempdir, "<tmp>"),
        (lambda: str(pathlib.Path.home()), "<home>"),
    ):
        try:
            found.append((get(), placeholder))
        except (OSError, RuntimeError, KeyError):
            continue
    pairs: dict[str, str] = {}
    for path, placeholder in found:
        for form in (path, path.replace(bs, "/"), path.replace(bs, bs + bs)):
            if len(form) > 3:  # noqa: PLR2004 — ドライブだけの path は消さない
                pairs.setdefault(form, placeholder)
    return sorted(pairs.items(), key=lambda kv: len(kv[0]), reverse=True)


def _local_user() -> str:
    try:
        user = getpass.getuser()
    except (OSError, KeyError, ImportError):
        return ""
    return user if len(user) >= 3 else ""  # noqa: PLR2004


def redact(text: str) -> str:
    """要約に書く文から、手元の tmp・home の path・ユーザー名・メモリの address を消す."""
    for name, placeholder in _local_names():
        text = re.sub(
            re.escape(name) + _PATH_END, placeholder, text, flags=re.IGNORECASE
        )
    user = _local_user()
    if user:
        text = re.sub(
            rf"(?<![A-Za-z0-9]){re.escape(user)}(?![A-Za-z0-9])",
            "<user>",
            text,
            flags=re.IGNORECASE,
        )
    for pattern, placeholder in _LOCAL_TEXT:
        text = pattern.sub(placeholder, text)
    return text


def _summary(record: dict[str, Any], link: dict[str, Any]) -> dict[str, object]:
    """照合に使った証拠 (DD-12 H4: 証明書の読み手が登録の条件と ``failed`` への所属を検査し直せる形).

    ``assert_stmt`` は記録の判定、``frames`` は照合した例外の (ファイル名, 関数名) の列 (``via`` の照合に使う)。
    要約の文は先頭 300 字 (登録の ``text`` はどれも先頭にある)。
    """
    return {
        "function": record.get("function"),
        "param": record.get("param"),
        "when": record.get("when"),
        "assert_stmt": record.get("assert_stmt") is True,
        "type": link.get("type"),
        "text": redact(str(link.get("text", "")))[:300],
        "frames": [list(f) for f in link.get("frames") or ()],
    }


def witnessed(
    w: Witness, expect: frozenset[str], records: list[dict[str, Any]]
) -> dict[str, object] | None:
    """期待 test の記録に ``w`` の証拠があれば、その要約を返す (無ければ None)."""
    for record in records:
        if record.get("function") not in expect or record.get("when") != w.when:
            continue
        if w.item is not None and record.get("param") != w.item:
            continue
        if w.item is None and not w.assert_stmt and record.get("param") is not None:
            continue
        chain = record.get("chain") or []
        if w.assert_stmt:
            head = chain[0] if chain else {}
            if record.get("assert_stmt") is True and (
                w.text is None or w.text in str(head.get("text", ""))
            ):
                return _summary(record, head)
            continue
        for link in chain:
            kind = str(link.get("type", ""))
            frames = [list(f) for f in link.get("frames") or ()]
            if (
                (w.exc is None or kind == w.exc or kind.endswith("." + w.exc))
                and (w.text is None or w.text in str(link.get("text", "")))
                and (
                    w.via is None
                    or any(f[0] in _TARGET_FILES and f[1] == w.via for f in frames)
                )
            ):
                return _summary(record, link)
    return None


def finished_with_failures(code: int, records: list[dict[str, Any]]) -> bool:
    """Test の失敗 (exit 1) で pytest が最後まで走ったか (session の終わりの記録がちょうど 1 つ・打ち切りなし)."""
    finish = [r for r in records if r.get("when") == _FINISH]
    if code != 1 or len(finish) != 1:
        return False
    done = finish[0]
    items, ran = done.get("items"), done.get("ran")
    return (
        done.get("exitstatus") == 1
        and done.get("stopped") is False
        and type(items) is int
        and items == ran
    )


def status_of(
    mut: Mutant,
    code: int,
    failed: set[str],
    records: list[dict[str, Any]],
    *,
    collect: bool,
) -> str:
    """変異の判定 (3 通り): SURVIVED / 理由が違う (WRONG_REASON ほか) / KILLED."""
    if code == -1:
        return "TIMEOUT"
    if code == 0:
        return "SURVIVED"
    if collect:
        return "COLLECTION_ERROR"
    if not finished_with_failures(code, records):
        return "ABNORMAL_EXIT"
    if not failed:
        return "NO_FAILURE_RECORD"
    return (
        "KILLED"
        if witnessed(mut.witness, mut.expect, records) is not None
        else "WRONG_REASON"
    )


def anchor_problems(sources: dict[str, str]) -> list[str]:
    """全変異と meta-test の置換前文字列が対象に 1 回ずつ現れ、置換で内容が変わり、置換後も構文が通ること."""
    out = []
    cases = [(m.label, m.target, m.old, m.new) for m in MUTANTS]
    cases += [(f"meta: {c[0]}", c[1], c[2], c[3]) for c in META_CASES]
    for label, target, old, new in cases:
        if target not in sources:
            out.append(f"{label}: unknown target {target!r}")
            continue
        src = sources[target]
        n = src.count(old)
        if n != 1 or old == new:
            out.append(f"{label}: {'NO_OP' if old == new else f'ANCHOR x{n}'}")
            continue
        try:
            compile(src.replace(old, new, 1), _TARGETS[target], "exec")
        except SyntaxError as exc:
            out.append(f"{label}: SYNTAX {exc}")
    labels = [m.label for m in MUTANTS] + [c[0] for c in META_CASES]
    if len(set(labels)) != len(labels):
        out.append("labels are not unique")
    try:
        index = index_tests()
        for m in MUTANTS:
            _files_for(m.expect, index)
        for c in META_CASES:
            _files_for(frozenset(c[4]), index)
    except (KeyError, ValueError) as exc:
        out.append(f"tests: {exc}")
    return out


def _sources(root: pathlib.Path = _REPO_ROOT) -> dict[str, str]:
    """対象の文 (bytes をそのまま decode。``read_text`` は CRLF を LF に変えて worker の置換と食い違う)."""
    return {k: (root / rel).read_bytes().decode("utf-8") for k, rel in _TARGETS.items()}


def crlf_files(root: pathlib.Path = _REPO_ROOT) -> list[str]:
    """CRLF を含む固定対象 (証明書の sha は LF の checkout と一致しなければならない)."""
    return [rel for rel in pinned_files() if b"\r\n" in (root / rel).read_bytes()]


def _copy_tree() -> pathlib.Path:
    """複製ツリー (repo の外の一時 dir): scripts・test・実験 dir・pytest の設定."""
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="bs2_tree_"))
    skip = shutil.ignore_patterns("__pycache__")
    shutil.copytree(_REPO_ROOT / "scripts", tmp / "scripts", ignore=skip)
    (tmp / "tests").mkdir()
    for name in ("__init__.py", "conftest.py"):
        shutil.copy2(_REPO_ROOT / "tests" / name, tmp / "tests" / name)
    dirs = {_TEST_DIR} | {pathlib.PurePath(t).parent.as_posix() for t in _WITNESS_EXTRA}
    for rel in sorted(dirs):
        shutil.copytree(_REPO_ROOT / rel, tmp / rel, ignore=skip)
    for rel in (_EXP_REL, _EXP_STAGE1):
        shutil.copytree(
            _REPO_ROOT / rel, tmp / rel, ignore=shutil.ignore_patterns("pilot", "main")
        )
    gate = pathlib.PurePath(_EXP_REL, _PILOT_GATE_REL).as_posix()
    (tmp / gate).parent.mkdir(parents=True)
    shutil.copy2(_REPO_ROOT / gate, tmp / gate)
    shutil.copy2(_REPO_ROOT / "pyproject.toml", tmp / "pyproject.toml")
    return tmp


def _sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pinned_files() -> list[str]:
    """写しの一致を見るファイル: 8 対象・witness の test (と dir の全 .py)・原本の test・pilot の gate.json・harness."""
    tests = sorted(
        p.relative_to(_REPO_ROOT).as_posix()
        for p in (_REPO_ROOT / _TEST_DIR).glob("*.py")
    )
    gate = pathlib.PurePath(_EXP_REL, _PILOT_GATE_REL).as_posix()
    return [*_TARGETS.values(), *tests, *_WITNESS_EXTRA, gate, _HARNESS_REL]


class WorkerError(RuntimeError):
    """worker の複製が使えない (写しが repo と違う・対照が緑でない)。変異の判定をしない."""


def run_meta(env: dict[str, str]) -> list[dict[str, object]]:
    """複製ツリーで検査関数を素通りに潰し、依存する test が実際に落ちることを見る."""
    rows: list[dict[str, object]] = []
    tmp = _copy_tree()
    try:
        files = _witness_test_files(tmp)
        code, failed, collect_error, _ = _run_tests(env, files, tmp)
        if code != 0 or collect_error:
            msg = f"meta-test の対照 (無変異の複製) が緑でない: {sorted(failed)}"
            raise RuntimeError(msg)
        for label, target, old, new, expect in META_CASES:
            path = tmp / _TARGETS[target]
            original = path.read_bytes()
            src = original.decode("utf-8")
            if src.count(old) != 1:
                msg = f"meta anchor not unique: {label}"
                raise RuntimeError(msg)
            path.write_bytes(src.replace(old, new, 1).encode("utf-8"))
            try:
                code, failed, collect_error, records = _run_tests(env, files, tmp)
            finally:
                path.write_bytes(original)
            ok = (
                finished_with_failures(code, records)
                and not collect_error
                and set(expect) <= set(failed)
            )
            rows.append(
                {
                    "label": label,
                    "target": _TARGETS[target],
                    "status": "FAILED_AS_EXPECTED" if ok else "NOT_AS_EXPECTED",
                    "expected_all_of": sorted(expect),
                    "failed": sorted(failed),
                }
            )
            print(f"meta: {label:56s} {rows[-1]['status']}", flush=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return rows


def run_controls(env: dict[str, str], mutants: list[Mutant]) -> list[list[str]]:
    """変異の run が回す test ファイルの組それぞれを、無変異の複製で単独に回して緑を確かめる.

    対照の全ファイルの run が緑でも、部分集合を単独で回すと順序依存で落ちる test は、無変異でも落ちて
    偽の KILLED になる (code-reviewer MEDIUM)。返り値は確かめた組の一覧 (証明書に残す)。
    """
    tmp = _copy_tree()
    try:
        index = index_tests(tmp)
        sets = sorted({tuple(_files_for(m.expect, index)) for m in mutants})
        for files in sets:
            code, failed, collect, _ = _run_tests(env, list(files), tmp)
            if code != 0 or collect:
                msg = f"対照 (無変異) の組 {list(files)} が単独で緑でない: {sorted(failed)}"
                raise WorkerError(msg)
            print(f"control: {' '.join(files)} green", flush=True)
        return [list(f) for f in sets]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _mutant_row(
    mut: Mutant,
    code: int,
    failed: set[str],
    records: list[dict[str, Any]],
    *,
    collect: bool,
) -> dict[str, object]:
    return {
        "label": mut.label,
        "target": _TARGETS[mut.target],
        "status": status_of(mut, code, failed, records, collect=collect),
        "expected_any_of": sorted(mut.expect),
        "expected_witness": mut.witness.as_dict(),
        "why": mut.why,
        "failed": sorted(failed),
        "witnessed_by": witnessed(mut.witness, mut.expect, records),
    }


def _discovery(records: list[dict[str, Any]]) -> list[str]:
    out = []
    for r in records:
        if r.get("when") not in _PHASES:
            continue
        head = (r.get("chain") or [{}])[0]
        out.append(
            f"    {r.get('function')}[{r.get('param')}] {r.get('when')} "
            f"assert={r.get('assert_stmt')} {head.get('type')}: "
            f"{redact(str(head.get('text', '')))[:140]!r}"
        )
    return out


def _worker(
    env: dict[str, str],
    todo: queue.Queue[Mutant],
    originals: dict[str, bytes],
    want: dict[str, str],
    rows: dict[str, dict[str, object]],
    *,
    discover: bool,
) -> None:
    """1 つの複製ツリーで、対照 (無変異) → queue の変異を 1 つずつ.

    変異は複製の対象にだけ書き、各 run の後に元の bytes に戻す。repo のファイルは書き換えない。
    """
    tmp = _copy_tree()
    try:
        copied = {rel: _sha(tmp / rel) for rel in want}
        if copied != want:
            msg = (
                f"複製が repo と違う: {sorted(k for k in want if copied[k] != want[k])}"
            )
            raise WorkerError(msg)
        code, failed, collect, _ = _run_tests(env, _witness_test_files(tmp), tmp)
        if code != 0 or collect:
            msg = f"対照 (無変異の複製) が緑でない: {sorted(failed)}"
            raise WorkerError(msg)
        index = index_tests(tmp)
        while True:
            try:
                mut = todo.get_nowait()
            except queue.Empty:
                return
            target = tmp / _TARGETS[mut.target]
            original = originals[mut.target]
            src = original.decode("utf-8")
            if src.count(mut.old) != 1:
                # 置換が起きないまま走らせると無変異の run を SURVIVED と数える (CRLF の作業ツリーで起きた)
                msg = f"{mut.label}: anchor x{src.count(mut.old)} in the bytes"
                raise WorkerError(msg)
            target.write_bytes(src.replace(mut.old, mut.new, 1).encode("utf-8"))
            try:
                try:
                    files = _files_for(mut.expect, index)
                except KeyError:
                    if not discover:
                        raise
                    files = _witness_test_files(
                        tmp
                    )  # 開発用: まだ無い test は全ファイルで探す
                code, failed, collect, records = _run_tests(env, files, tmp)
            except subprocess.TimeoutExpired:
                code, failed, collect, records = -1, set(), False, []
            finally:
                target.write_bytes(original)
            row = _mutant_row(mut, code, failed, records, collect=collect)
            rows[mut.label] = row
            lines = [f"{mut.label:60s} {row['status']}"]
            if discover:
                lines += _discovery(records)
            print("\n".join(lines), flush=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_mutants(
    env: dict[str, str],
    mutants: list[Mutant],
    originals: dict[str, bytes],
    want: dict[str, str],
    workers: int,
    *,
    discover: bool = False,
) -> list[dict[str, object]]:
    """変異を ``workers`` 個の複製ツリーで並列に判定する。返り値は登録の順."""
    todo: queue.Queue[Mutant] = queue.Queue()
    for mut in mutants:
        todo.put(mut)
    rows: dict[str, dict[str, object]] = {}
    n = max(1, min(workers, len(mutants)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=n) as pool:
        futures = [
            pool.submit(_worker, env, todo, originals, want, rows, discover=discover)
            for _ in range(n)
        ]
        errors = [f.exception() for f in futures]
    problems = [e for e in errors if e is not None]
    if problems:
        raise problems[0]
    missing = [m.label for m in mutants if m.label not in rows]
    if missing:
        msg = f"判定されなかった変異がある: {missing}"
        raise WorkerError(msg)
    return [rows[m.label] for m in mutants]


def certificate(
    want: dict[str, str],
    meta: list[dict[str, object]],
    rows: list[dict[str, object]],
    controls: list[list[str]],
) -> dict[str, object]:
    """証明書の中身 (closed-chain の探索規則が読める ``target_sha256``)."""
    target: dict[str, str] = {}
    for rel in [*_TARGETS.values(), _HARNESS_REL]:
        target[pathlib.PurePath(rel).name] = want[rel]
    for rel, sha in want.items():
        if rel.startswith(_TEST_DIR + "/"):
            target["tests/" + pathlib.PurePath(rel).name] = sha
    return {
        "version": _VERSION,
        "scope": "本走が実行・判定に使う code の全体 (DD-6・DD-11)。pilot 前の版 (pre_pilot) は git の履歴",
        "target_sha256": target,
        "witness_tests_sha256": {rel: want[rel] for rel in _WITNESS_EXTRA},
        "inputs_sha256": {
            (g := pathlib.PurePath(_EXP_REL, _PILOT_GATE_REL).as_posix()): want[g]
        },
        "targets": dict(_TARGETS),
        "meta_test": meta,
        "control_file_sets": controls,
        "mutants": rows,
        "all_killed": all(r["status"] == "KILLED" for r in rows),
    }


def main(argv: list[str] | None = None) -> int:  # noqa: C901, PLR0912, PLR0915
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=pathlib.Path, default=None)
    ap.add_argument(
        "--only", default=None, help="label の接頭辞 (カンマ区切り、開発用)"
    )
    ap.add_argument("--anchors", action="store_true", help="置換前文字列の検査だけ")
    ap.add_argument(
        "--discover",
        action="store_true",
        help="失敗の記録を出す (開発用、証明書は書かない)",
    )
    ap.add_argument("--workers", type=int, default=4, help="複製ツリーの数")
    args = ap.parse_args(argv)
    # Windows の端末 (cp932) で ≥ 等を出して落ちない (log は UTF-8 で残す)
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")

    problems = anchor_problems(_sources())
    problems += [f"{rel}: CRLF (LF にしてから回す)" for rel in crlf_files()]
    if args.discover and not args.anchors:
        problems = [p for p in problems if not p.startswith("tests: ")]
    if args.anchors or problems:
        for p in problems:
            print(p)
        n = len(MUTANTS) + len(META_CASES)
        print(f"anchors: {n - len(problems)} / {n} OK")
        return 1 if problems else 0

    env = dict(os.environ, PYTHONUTF8="1")
    originals = {k: (_REPO_ROOT / rel).read_bytes() for k, rel in _TARGETS.items()}
    want = {rel: _sha(_REPO_ROOT / rel) for rel in pinned_files()}

    prefixes = () if args.only is None else tuple(args.only.split(","))
    mutants = [m for m in MUTANTS if args.only is None or m.label.startswith(prefixes)]
    try:
        meta = run_meta(env) if args.only is None and not args.discover else []
        controls = run_controls(env, mutants)
        rows = run_mutants(
            env, mutants, originals, want, args.workers, discover=args.discover
        )
    except (WorkerError, RuntimeError) as exc:
        print(f"ERROR: {exc}")
        return 2

    restored = all(_sha(_REPO_ROOT / rel) == want[rel] for rel in _TARGETS.values())
    unchanged = all(_sha(_REPO_ROOT / rel) == sha for rel, sha in want.items())
    survived = [r for r in rows if r["status"] == "SURVIVED"]
    wrong = [r for r in rows if r["status"] not in ("KILLED", "SURVIVED")]
    meta_ok = bool(meta) and all(m["status"] == "FAILED_AS_EXPECTED" for m in meta)
    print("---- 判定 (3 通り)")
    print("対照 (無変異): 緑")
    print(f"変異が捕まらなかった (SURVIVED): {len(survived)}")
    for r in survived:
        print(f"  {r['label']}")
    print(
        "落ちたが理由が違う (WRONG_REASON / COLLECTION_ERROR / TIMEOUT / "
        f"ABNORMAL_EXIT / NO_FAILURE_RECORD): {len(wrong)}"
    )
    for r in wrong:
        print(f"  {r['label']} {r['status']} failed={r['failed']}")
    print(f"KILLED: {len(rows) - len(survived) - len(wrong)} / {len(rows)}")
    print(f"meta-test: {'ok' if meta_ok else 'NOT ok'}")
    print(f"source restored (sha256 match): {restored}")
    print(f"test / harness unchanged during the run: {unchanged}")
    all_killed = not survived and not wrong and meta_ok
    if args.out is not None:
        if args.only is not None or args.discover:
            print("ERROR: --only / --discover の結果は certification にしない")
            return 2
        if not (all_killed and restored and unchanged):
            print(
                "certification を書かない (全 KILLED・meta-test 成立・原状復帰のときだけ書く)"
            )
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            text = json.dumps(
                certificate(want, meta, rows, controls), indent=2, ensure_ascii=False
            )
            args.out.write_bytes((text + "\n").encode("utf-8"))
            print(f"wrote {args.out}")
    print("MUTATION CHECK DONE", flush=True)  # completion marker (log の先頭に探す)
    if not restored:
        print("ERROR: 対象ファイルが原状復帰していない")
        return 2
    if not unchanged:
        print("ERROR: 実行中に test または harness が変わった")
        return 2
    if args.only is not None or args.discover:
        return 0 if not survived and not wrong else 1
    return 0 if all_killed else 1


if __name__ == "__main__":
    sys.exit(main())
