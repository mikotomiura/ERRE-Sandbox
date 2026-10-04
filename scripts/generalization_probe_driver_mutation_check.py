#!/usr/bin/env python
"""候補 G (汎化 probe) の driver の変異試験 — driver の判定に関わる行を壊すと、意図した test が落ちるか.

``scripts/generalization_probe_driver.py`` の行を 1 つずつ壊し、``tests/test_generalization_probe/test_driver.py``
を実行する。壊す行の区分: plan (呼び出し順)・body の組み立て・予定表の事前検査・送る直前の照合・observed・
再送と raw = null・記録・公開 (成功したときだけ・二相・読み戻し・公開時の manifest)・来歴の異常・運用の保護・
起動の前提。枠組みは v5 の driver の harness (``closed_loop_v5_driver_mutation_check.py``) と同じ。

変異は 5 つ組 (名前・変異 (old → new)・期待診断 = 落ちるべき test の集合・理由 ``why``・証拠 ``Witness``) で登録する。
証拠は、pytest の出力の文字列でなく、harness 自身を pytest の plugin として読み込ませ (``-p``)、hook
``pytest_exception_interact`` が失敗ごとに書く記録 (関数名・parametrize の id・段・先頭が assert 文か・例外の chain の
型と文とフレーム) で照合する (Codex 3 回目 MEDIUM-1・LOW-1。出力を正規表現で切る方式は、assert 行の 2 形・
見出しの下線・id の中の ``] - `` で 3 回崩れた)。hook ``pytest_runtest_logfinish`` が走りきった item を数え、
``pytest_sessionfinish`` が session の終わり (exitstatus・選ばれた item の数・走りきった数・打ち切りの印) を 1 行書く。
各 run には空の bytecode の置き場所 (``PYTHONPYCACHEPREFIX``) を渡し、書き込みも止める (前の変異の pyc で走らない。
Codex 4 回目 MEDIUM-1)。判定は 3 通りに分けて報告する:

* 対照が落ちた: 無変異で test が緑でない → harness を止める (変異の判定をしない)。
* 変異が捕まらなかった: SURVIVED (test が緑のまま)。
* 変異は落ちたが理由が違う: WRONG_REASON (期待診断の記録に証拠が無い) / COLLECTION_ERROR / TIMEOUT /
  ABNORMAL_EXIT (pytest が通常の失敗 = exit 1 で終わっていない・session の終わりの記録が無い・``-x``/``--maxfail`` で
  打ち切った・選ばれた item の全てが走りきっていない。計測が途中で壊れた run の記録を証拠に数えない、Codex 4 回目
  MEDIUM-2・5 回目 MEDIUM-1) / NO_FAILURE_RECORD (exit 1 で終わったが失敗の記録が無い)。
  KILLED に数えるのは、期待診断の記録に証拠があるものだけ (``status_of``・``witnessed``)。既定の証拠は、期待診断の
  test の本体 (call) が test の ``assert`` 文で落ちたこと。fixture の setup の ERROR・teardown・assert 以外の例外
  (NameError・TypeError・autouse の封鎖の ``raise AssertionError``) は数えない (Codex MEDIUM-4・code-reviewer MEDIUM-4・
  Codex 再 review MEDIUM-1・BL-3)。意図どおりに assert 以外で落ちる変異 (``pytest.raises`` の DID NOT RAISE・
  fixture の full run を止める例外等) には、item (parametrize の id)・段・例外の型・文・経由した driver の関数を
  登録し、**同じ 1 つの例外**で照合する (別の parameter・段・例外を流用しない、Codex 3 回目 MEDIUM-1。fixture に
  依存する登録だけ段 = setup、memory feedback_mutation_fixture_error_reason)。certification の行には、照合した証拠の
  要約 (``witnessed_by``) を残す。判定器自体の負例は ``test_harness_*`` が pin する。

anchor (置換前の文字列) は対象に 1 回だけ現れ、置換で内容が変わり、置換後も構文が通ること (``--anchors`` で検査)。
登録から外した変異 (decisions.md DN-2 にも記録)。等価 (意味を変えないので kill できない):

* ``absorb`` の読み戻しを外す: ``ensure_ascii=True`` で書いた行は必ず 1 記録に読み戻せる
  (``ensure_ascii`` を外す変異 r4 が、読み戻しの ``record is not JSON`` で止まることを理由照合で要求して pin する)。
* 記録の seed・prompt を予定表の body から取る: 送る直前の照合が、送った body の seed と prompt を plan の位置の
  凍結値に一致させる。
* meta の request を ``sc.request_meta()`` から写す: 予定表の事前検査が、型まで含めて凍結値と一致させる。

(初稿では「来歴の records・meta の sha256 を rename の後のファイルから取る」も等価に数えていた。照合と hash の間に
窓があるので等価ではない (code-reviewer の再レビュー MEDIUM)。変異 u31・u32 として登録し直した。)

等価ではないが、この certification の保証の外に置いたもの:

* 公開名が既にあるときの上書き拒否を外す: Windows の ``Path.rename`` は既存の宛先で ``FileExistsError`` を出すので、
  この harness が走る Windows では観測できない (Windows 限定の等価。POSIX では上書きを拒否する行が効く)。
* fsync を外す: 電源断・書き込みの永続化の失敗に対する耐性だけに効き、test から観測できない
  (耐久性は本 certification の保証外。Codex LOW-6)。

meta-test (計測台 §4.4): 対象を複製ツリー (repo の外の一時 dir) に写し、検査関数を no-op に潰して、依存する test が
実際に落ちることを一度見る。無変異の複製で期待する test が緑であることを先に確かめる。登録 (``META_CASES``) は
本登録の harness と同じ形 (先頭 = label、末尾 = 落ちるべき test の集合)。

certification は manifest の契約 (``driver_certification_violations``、第 1 段で封印) どおりに書く。全 KILLED・
meta-test 成立・原状復帰のときだけ書く (書かないときは理由を出して非 0 で終わる)。対象ファイルは実行中だけ
書き換わり、必ず原状復帰する。実行中は対象・test を編集しない・読ませない。Windows では中断時に finally が走らず、
変異が残りうる。中断したら ``--anchors`` で、全変異の置換前文字列が各 1 回ずつ現れることを確かめる。

実行 (repo root から、長いので detached で)::

    uv run python scripts/generalization_probe_driver_mutation_check.py --out <driver_certification.json>
    uv run python scripts/generalization_probe_driver_mutation_check.py --anchors
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from dataclasses import dataclass
from typing import Any

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_DRIVER_REL = "scripts/generalization_probe_driver.py"
_TEST_REL = "tests/test_generalization_probe/test_driver.py"
_HARNESS_REL = "scripts/generalization_probe_driver_mutation_check.py"
_EXP_REL = "experiments/20261001-generalization-probe-pilot"
_DRIVER = _REPO_ROOT / _DRIVER_REL
# commit 済み certification と現在のファイルの一致を見る test は、変異中は必ず落ちて生き残りを覆い隠すので外す
_DESELECT = f"{_TEST_REL}::test_committed_driver_certification_is_current"
_TEST_TIMEOUT_S = 1800
# 証拠の記録 (pytest の hook が書く JSONL) の置き場所を渡す env。harness 自身を plugin として読み込ませる
_WITNESS_ENV = "GP_DRIVER_WITNESS"
_PLUGIN = "scripts.generalization_probe_driver_mutation_check"
_TEST_FILE = pathlib.PurePath(_TEST_REL).name
_DRIVER_FILE = pathlib.PurePath(_DRIVER_REL).name
_PHASES = ("setup", "call", "teardown")
_FINISH = "sessionfinish"  # session の終わりの記録の段 (``pytest_sessionfinish``)
_ASSERT_WORD = re.compile(
    r"assert\b"
)  # assert 文の行の頭 (``assertion`` 等の名前は除く)
# test の run に継がせない env (計測を変える: -x 等の追加の option・追加の plugin。Codex 4 回目 MEDIUM-2)
_DROPPED_ENV = ("PYTEST_ADDOPTS", "PYTEST_PLUGINS")


@dataclass(frozen=True)
class Witness:
    """変異が落とすべき証拠 (Codex 3 回目 MEDIUM-1).

    期待 test の失敗の記録のうち、``item`` (parametrize の id)・``when`` (段) が一致するもので照合する。``item`` が None なら、
    assert 文の証拠はどの item でも、それ以外の証拠は parametrize でない test の記録だけに一致する。
    ``assert_stmt`` なら、先頭の例外が test の ``assert`` 文 (pytest が書き換えたもの) であること。そうでなければ、
    例外の chain の **同じ 1 つの例外**で、型 (``exc``、完全名の末尾)・文 (``text``、``str(e)`` の部分文字列)・
    経由 (``via``、その例外のフレームにある driver の関数) が全て一致すること。
    """

    item: str | None = None
    when: str = "call"
    exc: str | None = None
    text: str | None = None
    via: str | None = None
    assert_stmt: bool = False

    def as_dict(self) -> dict[str, object]:
        return {k: v for k, v in vars(self).items() if v is not None}


_ASSERTED = Witness(assert_stmt=True)


@dataclass(frozen=True)
class Mutant:
    label: str
    old: str
    new: str
    expect: frozenset[str]
    why: str
    witness: Witness = (
        _ASSERTED  # 理由の文の無い変異は、期待 test の本体の assert 文で落ちること
    )


def _m(
    label: str,
    old: str,
    new: str,
    expect: tuple[str, ...],
    why: str,
    witness: Witness = _ASSERTED,
) -> Mutant:
    return Mutant(label, old, new, frozenset(expect), why, witness)


# full run の fixture に依存する test (run が壊れると ERROR になる)
_PILOT = (
    "test_complete_pilot_run_is_published_and_computed",
    "test_records_follow_the_schema_and_the_plan",
    "test_raw_is_recorded_verbatim",
    "test_parse_follows_the_arm",
    "test_line_separators_in_raw_do_not_split_a_record",
    "test_written_files_use_lf",
    "test_pilot_gate_cli_and_provenance_contract",
)
_MAIN = ("test_main_run_is_computed_by_the_frozen_scorer",)
_PLAN_P = "test_pilot_plan_is_the_frozen_grid_in_order"
_PLAN_M = "test_main_plan_is_the_frozen_grid_in_order"
_EVERY = "test_every_planned_body_passes_the_frozen_checks"
_BAD = "test_bad_schedule_makes_no_call"
_META = "test_schedule_checks_meta_against_the_frozen_values"
_FIXED = "test_schedule_rejects_a_wrong_fixed_option"
_VALUE = "test_check_sent_body_rejects_value_and_type"
_POSITION = "test_check_uses_the_plan_position"
_OBSERVER = "test_observer_refuses_before_the_inner_transport"
_SHOW = "test_show_is_allowed_only_while_reading_observed"
_SHIFTED = "test_shifted_body_is_refused_before_sending"
_RESEND = "test_resend_with_the_same_seed_recovers"
_UNRESOLVED = "test_unresolved_transport_failure_records_null_and_stops"
_NULL = "test_null_content_is_a_transport_failure_not_bottom"
_FAILED_RESP = "test_failed_responses_are_resent"
_OTHER_EXC = "test_other_exceptions_abort_without_a_null_row"
_COMPLETE = "test_complete_pilot_run_is_published_and_computed"
_RAW = "test_raw_is_recorded_verbatim"
_PARSE = "test_parse_follows_the_arm"
_GATE = "test_pilot_gate_cli_and_provenance_contract"
_MAIN_RUN = "test_main_run_is_computed_by_the_frozen_scorer"
_MAIN_OBS = "test_main_refuses_an_observed_environment_different_from_the_pilot"
_PUB_CHECK = "test_publication_problems_check_completeness_and_structure"
_PUB_READER = "test_publication_problems_read_like_the_judge"
_PUB_META = "test_publication_problems_read_the_written_meta"
_TWO_PHASE = "test_publication_is_two_phase"
_PUB_FAIL = "test_publication_failure_is_recorded_as_aborted"
_FINAL_PROV = "test_final_provenance_failure_keeps_records_but_aborts"
_SWAPPED = "test_swapped_files_are_not_published"
_AFTER_RENAME = "test_files_changed_after_the_rename_are_not_bound"
_PINNED_ORDER = "test_pinned_change_during_the_manifest_check_blocks_publication"
_PINNED_LAUNCH = "test_run_compares_with_the_pinned_values_taken_at_launch"
_DRIVER_SWAP = "test_driver_swap_is_detected"
_RUNNING = "test_provenance_binds_the_running_driver"
_LENGTH = "test_finish_length_is_counted"
_RUN_MANIFEST = "test_run_manifest_calls_the_frozen_check_like_run_sh"
_GIT_REAL = "test_git_reports_a_failure_as_none"
_HASHES = "test_provenance_hashes_are_the_written_bytes"
_PINNED_READBACK = "test_pinned_change_during_the_read_back_blocks_publication"
_SHA_UNREADABLE = "test_sha256_reports_an_unreadable_file_as_none"
_ORIGINAL = "test_provenance_failure_keeps_the_original_exception"
_MANIFEST_PUB = "test_manifest_failure_at_publication_blocks_it"
_READ_BACK = "test_read_back_failure_blocks_publication"
_MODEL = "test_unexpected_response_model_blocks_publication"
_OBS_CHANGE = "test_observed_change_during_the_run_blocks_publication"
_PINNED_CHANGE = "test_pinned_file_change_during_the_run_blocks_publication"
_FINAL_ABORT = "test_final_observed_failure_aborts_a_finished_run"
_FINAL_KEEP = "test_final_observed_failure_keeps_a_transport_failure"
_FINAL_RESENT = "test_final_observed_is_resent"
_NON_EMPTY = "test_run_refuses_a_non_empty_run_dir"
_PREFLIGHT = "test_preflight_failure_writes_nothing"
_IDENTITY = "test_preflight_requires_the_environment_identity"
_META_DISK = "test_meta_is_on_disk_before_the_first_call"
_ARGS = "test_main_takes_only_the_stage"
_REFUSE = "test_main_refuses_to_launch_without_touching_the_run_dir"
_MAIN_STAGE = "test_main_runs_the_stage_and_returns_the_exit_code"
_OK_LINE = "test_manifest_problems_require_the_exact_ok_line"
_NO_RUN = "test_manifest_problems_report_a_failure_to_run"
_COMBINE = "test_launch_problems_combine_certification_git_manifest_and_gate"
_GIT = "test_launch_problems_check_git_tracking_and_head"
_CERT = "test_certification_problems_use_the_manifest_contract"
_GATE_PROBLEMS = "test_gate_problems_require_go_r_and_observed"
_PINNED = "test_pinned_covers_the_frozen_files_and_the_driver_evidence"
# Codex 再 review の反映 (decisions DX-1・DX-4)
_INTERRUPTED = "test_interrupted_transport_failure_keeps_not_computed"
_COMPILES = "test_compiles_to_compares_the_program"
_SELF_BYTES = "test_imported_driver_runs_its_bytes"
_FINDER = "test_pinned_finder_runs_the_bytes_it_read"
_EXECUTED = "test_executed_problems_check_driver_modules_and_pins"
_MAIN_EXECUTED = "test_main_checks_the_executed_code_after_the_launch_checks"
_LAUNCH_CLI = "test_command_line_launch_runs_repo_code_from_hashed_bytes"
_LAUNCH_SWAP = "test_command_line_launch_refuses_code_that_is_not_its_bytes"
# 環境と固定ファイルの外のコード (Codex 3 回目 MEDIUM-2)
_ROOTS = "test_environment_roots_are_the_prefixes_that_do_not_hold_the_repo"
_IN_ENV = "test_in_environment_compares_whole_path_components"
_GATE_PASS = "test_launch_gate_passes_the_environment"
_GATE_REFUSE = "test_launch_gate_refuses_code_outside_the_environment"
_OUTSIDE = "test_outside_problems_require_the_environment_and_the_scripts_namespace"
_NAMESPACE = "test_pinned_finder_makes_the_package_a_namespace"
_LAUNCH_INIT = "test_command_line_launch_does_not_run_a_scripts_initializer"
_LAUNCH_SHADOW = "test_command_line_launch_refuses_to_import_a_shadow"
_LAUNCH_EARLY = "test_command_line_launch_refuses_code_imported_before_the_gate"
# Codex 4 回目 (HIGH-1・HIGH-2・LOW-2)
_FOLD = "test_run_manifest_folds_an_exception_into_a_failure"
_INTERPRETER = "test_interpreter_problems_require_the_run_sh_settings"
_STARTUP = "test_startup_problems_find_customization_outside_the_environment"
_LAUNCH_FAILED_SITE = (
    "test_command_line_launch_refuses_a_startup_customization_that_failed"
)
_FOUR_PREFIXES = "test_environment_roots_count_all_four_prefixes"
_LINKS = "test_in_environment_resolves_links"
# code-reviewer (/review-changes) の HIGH-2・LOW-7
_LAUNCH_PTH_SHADOW = "test_command_line_launch_refuses_a_pythonpath_shadow"
_USER_SITE = "test_user_site_reads_the_site_module"
_REGISTRY = "test_registry_paths_follow_getpath"
# Codex 6 回目 (HIGH-1)
_ORDINARY = "test_ordinary_drops_only_the_drive_and_unc_extended_prefix"
_EXTENDED = "test_extended_paths_are_compared_as_ordinary"
_NO_IMPORT_ERROR = "DID NOT RAISE <class 'ImportError'>"
_NOT_RAISED_SCHEDULE = (
    "DID NOT RAISE <class 'scripts.generalization_probe_driver.ScheduleError'>"
)
_NOT_RAISED_SENT = (
    "DID NOT RAISE <class 'scripts.generalization_probe_driver.SentBodyMismatchError'>"
)
_NOT_RAISED_PREFLIGHT = (
    "DID NOT RAISE <class 'scripts.generalization_probe_driver.PreflightError'>"
)

_NOT_PUBLISHED = "the complete run was not published"
_RESENT = "resent more or fewer than 3 times"

_UNIT_INNER = "out.extend((arm_name(arm), r, p.probe_id, k) for arm in family)"
_PILOT_RS = "    rs = range(bat.PILOT_R0, bat.PILOT_R0 + bat.PILOT_R)\n"
_SHAPE_ROWS = (
    "        for name, want in (\n"
    '            ("model", bat.MODEL),\n'
    '            ("think", bat.THINK),\n'
    '            ("stream", False),\n'
    "        )\n"
)
_WIRE = (
    "                check_sent_body(self.stage, self.expected, body)\n"
    "                self.sent.setdefault(self.expected, []).append(body)\n"
    "        return await self.inner.handle_async_request(request)\n"
)
_RECORD_RAW = (
    "            raw=raw,\n"
    "            parsed=None if raw is None else state.stage.parse(arm, raw),\n"
)
_PUB_COMPLETE = "    if len(samples) != len(stage.grid) or keys != stage.grid:\n"
_RESENDS_BLOCK = (
    "RESENDS: Final[int] = 3  # 同じ seed での再送回数 (送信は初回と合わせて最大 4 回)\n"
    "# 再送の待ち (秒)。attempt ごとに延ばす (Ollama の再起動・復帰を待つ。登録外・label と独立)\n"
    "BACKOFF_SCHEDULE_S: Final[tuple[float, ...]] = (5.0, 30.0, 120.0)\n"
)
# 公開の条件の並び: 実走中の異常 → 公開時の manifest → 読み戻し → 固定ファイル (Codex HIGH-2)
_FINISH_FIRST = "    anomalies = _run_anomalies(out)\n"
_FINISH_LAST = "    late, changed = _file_anomalies(stage, out)\n"
_FINISH_BLOCK = (
    _FINISH_FIRST + "    if anomalies and reason == REASON_COMPLETED:\n"
    "        reason = REASON_ABORTED\n"
    '        error = _join(error, "; ".join(anomalies))\n'
    "    # 公開の条件 (続き): 判定 (run.sh) が照合するその段の manifest が今も OK\n"
    "    at_publication: list[str] | None = None\n"
    "    if reason == REASON_COMPLETED:\n"
    "        at_publication = manifest_problems(stage.name)\n"
    "        if at_publication:\n"
    "            reason = REASON_ABORTED\n"
    '            error = _join(error, f"manifest at publication: {at_publication}")\n'
    "    # 公開の最後の条件: 判定と同じ reader・凍結済みの検査で読み戻せ、bytes がこの run の書いたものと同じ\n"
    "    written = records_bytes([] if state is None else state.lines)\n"
    "    read_back: list[str] | None = None\n"
    "    if reason == REASON_COMPLETED:\n"
    "        read_back = publication_problems(stage) + binding_problems(\n"
    "            stage.run_dir, PARTIAL_NAME, written, out.meta_bytes\n"
    "        )\n"
    "        if read_back:\n"
    "            reason = REASON_ABORTED\n"
    '            error = _join(error, f"read-back: {read_back}")\n' + _FINISH_LAST
)
_FINISH_EARLY = _FINISH_BLOCK.replace(
    _FINISH_FIRST, _FINISH_FIRST + "    early = _file_anomalies(stage, out)\n"
).replace(_FINISH_LAST, "    late, changed = early\n")
# 固定ファイルを、公開時の manifest の照合の後・読み戻しの前に比べる (読み戻しの間の差し替えを見逃す)
_READ_BACK_BLOCK = _FINISH_BLOCK[
    _FINISH_BLOCK.index("    # 公開の最後の条件") : -len(_FINISH_LAST)
]
_BEFORE_READ_BACK = (_READ_BACK_BLOCK + _FINISH_LAST, _FINISH_LAST + _READ_BACK_BLOCK)
_MAIN_PINNED = (
    "    pinned_start = pinned_sha256(args.stage)\n"
    "    problems = launch_problems(args.stage)\n"
)

MUTANTS: tuple[Mutant, ...] = (
    # ================================================================ plan (呼び出し順)
    _m(
        "p1  族の順を逆に",
        "        for family in bat.FAMILIES:\n",
        "        for family in bat.FAMILIES[::-1]:\n",
        (_PLAN_P, _PLAN_M),
        "単位の順 (r, 族, つ組) が prereg §4 と違う (判定は順序を見ないので plan の test だけが捕まえる)",
    ),
    _m(
        "p2  族内の 2 arm の順を逆に",
        _UNIT_INNER,
        "out.extend((arm_name(arm), r, p.probe_id, k) for arm in family[::-1])",
        (_PLAN_P, _PLAN_M),
        "族内の 2 arm の交互が族の正準順と逆",
    ),
    _m(
        "p3  つ組の順を逆に",
        "            for j in range(bat.N_TRIPLES):\n",
        "            for j in reversed(range(bat.N_TRIPLES)):\n",
        (_PLAN_P, _PLAN_M),
        "単位の順が bat.units と違う",
    ),
    _m(
        "p4  KNOW を後ろに",
        "    return (*know, *unit_keys(rs, pg.PILOT_K, _MASKED_OF.__getitem__))\n",
        "    return (*unit_keys(rs, pg.PILOT_K, _MASKED_OF.__getitem__), *know)\n",
        (_PLAN_P,),
        "KNOW を先に置く決定 (DD-4) と違う",
    ),
    _m(
        "p5  pilot の r を 0 から",
        _PILOT_RS,
        "    rs = range(bat.PILOT_R)\n",
        (_PLAN_P, _EVERY),
        "pilot の r が本走の r と交わる (grid の外。予定表の検査で止まる)",
    ),
    _m(
        "p6  KNOW の試行を 1 回減らす",
        "        for k in range(bat.KNOW_K)\n",
        "        for k in range(bat.KNOW_K - 1)\n",
        (_PLAN_P, _EVERY),
        "知識確認の 3 試行 (正答の位置の一巡) が欠ける",
    ),
    _m(
        "p7  本走の r を 1 つ減らす",
        "    return tuple(unit_keys(range(r_count), sc.FROZEN_K, str))\n",
        "    return tuple(unit_keys(range(r_count - 1), sc.FROZEN_K, str))\n",
        (_PLAN_M, _EVERY),
        "本走の grid (R = 18) が欠ける",
    ),
    # ================================================================ body の組み立て
    _m(
        "b1  pilot の状態を masked でなく描く",
        "        bat.render_messages(lever, probe, r, masked=True),\n",
        "        bat.render_messages(lever, probe, r, masked=False),\n",
        (_EVERY,),
        "null pilot の状態が key を含む (prompt が凍結 renderer と違う)",
    ),
    _m(
        "b2  pilot の seed を本走の名前空間で",
        '    ns = f"pilot_fam{bat.ARM_FAMILY[lever]}"\n',
        '    ns = f"fam{bat.ARM_FAMILY[lever]}"\n',
        (_EVERY,),
        "pilot と本走の seed が交わる",
    ),
    _m(
        "b3  pilot の seed の slot を probe 番号に",
        "        bat.sample_seed(ns, r, probe.triple, k),\n",
        "        bat.sample_seed(ns, r, probe.index, k),\n",
        (_EVERY,),
        "seed が分類を運ぶ (つ組で共有しない、Codex 2 回目 HIGH-1)",
    ),
    _m(
        "b4  KNOW の seed の key と試行を取り違える",
        'bat.sample_seed("know", 0, i, k)',
        'bat.sample_seed("know", 0, k, i)',
        (_EVERY,),
        "知識確認の seed が凍結 schedule と違う",
    ),
    _m(
        "b5  KNOW の試行 k を描かない",
        "        return bat.render_know_messages(i, k), bat.sample_seed(",
        "        return bat.render_know_messages(i, 0), bat.sample_seed(",
        (_EVERY,),
        "正答の位置が 3 試行で一巡しない",
    ),
    _m(
        "b6  本走の seed を pilot の名前空間で",
        '    ns = f"fam{bat.ARM_FAMILY[arm]}"\n',
        '    ns = f"pilot_fam{bat.ARM_FAMILY[arm]}"\n',
        (_EVERY,),
        "本走の seed が凍結 schedule と違う",
    ),
    _m(
        "b7  本走の状態を masked で描く",
        "    return bat.render_messages(arm, probe, r), bat.sample_seed(",
        "    return bat.render_messages(arm, probe, r, masked=True), bat.sample_seed(",
        (_EVERY,),
        "本走の状態から key が消える",
    ),
    _m(
        "b8  model を変える",
        '        "model": bat.MODEL,\n        "messages": messages,\n',
        '        "model": "qwen3:14b",\n        "messages": messages,\n',
        (_EVERY,),
        "凍結 model と違う model を呼ぶ",
    ),
    _m(
        "b9  think を逆に",
        '        "think": bat.THINK,\n',
        '        "think": not bat.THINK,\n',
        (_EVERY,),
        "thinking が有効になる (着座が v2 と違う)",
    ),
    _m(
        "b10 stream を True に",
        '        "stream": False,\n        "think"',
        '        "stream": True,\n        "think"',
        (_EVERY,),
        "stream の応答は 1 つの JSON にならない",
    ),
    _m(
        "b11 num_predict の定数を誤る",
        '    "num_predict": bat.NUM_PREDICT,\n',
        '    "num_predict": bat.NUM_CTX,\n',
        (_EVERY,),
        "driver の定数の誤りは形の検査 (同じ定数と比べる) を通る。凍結 scorer の request で捕まえる",
    ),
    _m(
        "b12 num_ctx の定数を float に",
        '    "num_ctx": bat.NUM_CTX,\n',
        '    "num_ctx": float(bat.NUM_CTX),\n',
        (_EVERY,),
        "4096.0 は凍結 scorer の meta_violations (辞書の等値) を通る。型まで比べる照合で捕まえる",
    ),
    # ================================================================ 予定表の事前検査
    _m(
        "c1  plan と grid の照合を外す",
        "    if len(set(stage.plan)) != len(stage.plan) or set(stage.plan) != stage.grid:\n",
        "    if False:\n",
        (_BAD,),
        "欠けた plan (重複・grid 外は凍結の構造の検査が捕まえるが、欠けは捕まえない) で走り始める",
        Witness(item="missing", exc="Failed", text=_NOT_RAISED_SCHEDULE),
    ),
    _m(
        "c2  body の数と plan の照合を外す",
        "    if not schedule or len(schedule) != len(stage.plan):\n",
        "    if not schedule:\n",
        (_META,),
        "plan と数の違う予定表を、照合の表を作らずに受け入れる",
        Witness(
            exc="ValueError",
            text="zip() argument 2 is shorter than argument 1",
            via="schedule_violations",
        ),
    ),
    _m(
        "c3  予定表で形の検査をしない",
        '        out.extend(f"schedule: call {i}: {p}" for p in shape_problems(body))\n',
        "        pass\n",
        (_BAD,),
        "stream などの形の誤りに、送る直前まで気づかない (GPU を使ってから止まる)",
        Witness(
            item="stream",
            exc="SentBodyMismatchError",
            text="call 500 ",
            via="check_sent_body",
        ),
    ),
    _m(
        "c4  形の問題があっても続ける",
        "    if out:\n        return out\n    cands = [",
        "    if False:\n        return out\n    cands = [",
        (_BAD,),
        "形の崩れた body で候補記録を作り、ScheduleError でなく KeyError で落ちる",
        Witness(item="no_options", exc="KeyError", text="'options'", via="skeleton"),
    ),
    _m(
        "c5  予定表で凍結の構造の検査をしない",
        '    out.extend(f"schedule: {p}" for p in stage.structure(cands))\n',
        "    pass\n",
        (_BAD,),
        "seed・prompt の誤りに、送る直前まで気づかない",
        Witness(
            item="seed",
            exc="SentBodyMismatchError",
            text="call 400 ",
            via="check_sent_body",
        ),
    ),
    _m(
        "c6  request の型の照合を外す",
        '    if _canonical(meta["request"]) != _canonical(sc.request_meta()):\n',
        "    if False:\n",
        (_BAD, _FIXED, _EVERY),
        "4096.0 のような型の誤りを、凍結 scorer の meta_violations は通す",
    ),
    _m(
        "c7  meta の照合で pilot の observed を見ない",
        '        f"schedule: {p}" for p in sc.meta_violations(meta, stage.reference_observed)\n',
        '        f"schedule: {p}" for p in sc.meta_violations(meta, None)\n',
        (_META,),
        "本走の observed が pilot と違っても予定表を通す",
    ),
    _m(
        "c8  meta の observed を空に",
        '    return {"request": request_of(schedule[0]), "observed": dict(observed)}\n',
        '    return {"request": request_of(schedule[0]), "observed": {}}\n',
        (_EVERY, _META),
        "meta.json が実行環境の同定を持たない (判定で INVALID_SCORER)",
    ),
    # ================================================================ 送る直前の照合
    _m(
        "w1  送る直前の照合を削除",
        "                check_sent_body(self.stage, self.expected, body)\n",
        "                pass\n",
        (_OBSERVER, _SHIFTED),
        "送る経路でずれた body をそのまま送る",
        Witness(item="mismatch", exc="Failed", text=_NOT_RAISED_SENT),
    ),
    _m(
        "w2  照合を送信の後に",
        _WIRE,
        "                self.sent.setdefault(self.expected, []).append(body)\n"
        "        response = await self.inner.handle_async_request(request)\n"
        '        if request.method == "POST" and request.url.path == CHAT_PATH:\n'
        "            check_sent_body(self.stage, self.expected, body)\n"
        "        return response\n",
        (_OBSERVER, _SHIFTED),
        "ずれた body をモデルに送ってから止まる",
    ),
    _m(
        "w3  照合のキーを plan の位置から取らない",
        "    key = stage.plan[index]\n    where",
        "    key = stage.plan[index % 4]\n    where",
        (_POSITION, _VALUE),
        "別の位置のキーで照合する",
        Witness(exc="SentBodyMismatchError", text="call 200 ", via="check_sent_body"),
    ),
    _m(
        "w4  送る直前に形を検査しない",
        "    problems = shape_problems(body)\n    if not problems:\n",
        "    problems = []\n    if not problems:\n",
        (_VALUE,),
        "think・stream・型の誤りを送る",
        Witness(item="pilot-missing_option", exc="Failed", text=_NOT_RAISED_SENT),
    ),
    _m(
        "w5  送る直前に凍結の構造の検査をしない",
        "        problems = stage.structure([skeleton(index, key, body)])\n",
        "        problems = []\n",
        (_VALUE, _POSITION, _SHIFTED),
        "seed・prompt のずれを送る",
        Witness(item="pilot-prompt", exc="Failed", text=_NOT_RAISED_SENT),
    ),
    _m(
        "w6  seed の型を検査しない",
        '    if type(opts["seed"]) is not int:\n',
        "    if False:\n",
        (_VALUE,),
        "float の seed (20261001.0) は凍結の構造の検査 (!=) を通る",
        Witness(item="pilot-seed_float", exc="Failed", text=_NOT_RAISED_SENT),
    ),
    _m(
        "w7  型の厳密一致を外す",
        "return type(got) is type(want) and got == want",
        "return got == want",
        (_VALUE,),
        "False と 0、4096.0 と 4096 を同じとみなす",
        Witness(item="pilot-num_ctx_float", exc="Failed", text=_NOT_RAISED_SENT),
    ),
    _m(
        "w8  body の余分な key を許す",
        "    if not isinstance(body, dict) or set(body) != BODY_KEYS:\n",
        "    if not isinstance(body, dict) or not BODY_KEYS <= set(body):\n",
        (_VALUE,),
        "keep_alive などの登録外の要求を送る",
        Witness(item="pilot-extra_key", exc="Failed", text=_NOT_RAISED_SENT),
    ),
    _m(
        "w9  options の余分な key を許す",
        "    if not isinstance(opts, dict) or set(opts) != OPTION_KEYS:\n",
        "    if not isinstance(opts, dict) or not OPTION_KEYS <= set(opts):\n",
        (_VALUE,),
        "top_k などの登録外の decoding 条件を送る",
        Witness(item="pilot-extra_option", exc="Failed", text=_NOT_RAISED_SENT),
    ),
    _m(
        "w10 messages の形を検査しない",
        "    if not isinstance(msgs, list) or not all(\n",
        "    if False and not all(\n",
        (_VALUE,),
        "list でない messages で SentBodyMismatchError でなく TypeError になる",
        Witness(
            item="pilot-messages_not_list",
            exc="TypeError",
            text="'int' object is not iterable",
            via="skeleton",
        ),
    ),
    _m(
        "w11 model を照合しない",
        '            ("model", bat.MODEL),\n',
        "",
        (_VALUE,),
        "別の model への送信を通す",
        Witness(item="pilot-model", exc="Failed", text=_NOT_RAISED_SENT),
    ),
    _m(
        "w12 think を照合しない",
        '            ("think", bat.THINK),\n',
        "",
        (_VALUE,),
        "think の誤りを通す",
        Witness(item="pilot-think", exc="Failed", text=_NOT_RAISED_SENT),
    ),
    _m(
        "w13 stream を照合しない",
        '            ("stream", False),\n',
        "",
        (_VALUE,),
        "stream の誤りを通す",
        Witness(item="pilot-stream", exc="Failed", text=_NOT_RAISED_SENT),
    ),
    _m(
        "w14 固定の options を照合しない",
        "        if not _exact(opts[name], want)\n    )\n",
        "        if False\n    )\n",
        (_VALUE,),
        "temperature・num_ctx の誤りを通す",
        Witness(item="pilot-temperature", exc="Failed", text=_NOT_RAISED_SENT),
    ),
    _m(
        "w15 /api/chat 以外の POST を通す",
        "            elif path != CHAT_PATH:\n",
        "            elif False:\n",
        (_OBSERVER,),
        "照合をすり抜ける経路を開ける",
        Witness(item="generate_path", exc="Failed", text=_NOT_RAISED_SENT),
    ),
    _m(
        "w16 /api/show を常に通す",
        "            if path == SHOW_PATH and self.allow_show:\n",
        "            if path == SHOW_PATH:\n",
        (_OBSERVER, _SHOW),
        "observed を読む間以外にも /api/show を通す",
        Witness(item="show_path", exc="Failed", text=_NOT_RAISED_SENT),
    ),
    _m(
        "w17 期待の無い送信を通す",
        "                if self.expected is None:\n",
        "                if False:\n",
        (_OBSERVER,),
        "位置の無い送信を照合せずに通す (TypeError になる)",
        Witness(
            item="no_expected",
            exc="TypeError",
            text="tuple indices must be integers or slices, not NoneType",
            via="check_sent_body",
        ),
    ),
    _m(
        "w18 observed を読む間に /api/show を許さない",
        "    observer.allow_show = True\n    try:\n",
        "    observer.allow_show = False\n    try:\n",
        (_SHOW, _META_DISK, *_PILOT),
        "chat template を読めず、どの run も始まらない",
        Witness(
            exc="SentBodyMismatchError",
            text="unexpected POST path '/api/show'",
            via="read_observed",
        ),
    ),
    _m(
        "w19 /api/show の許可を閉じない",
        "    finally:\n        observer.allow_show = False\n",
        "    finally:\n        pass\n",
        (_SHOW,),
        "observed を読んだ後も /api/show が開いたまま",
    ),
    # ================================================================ observed
    _m(
        "o1  template の sha を版から",
        'hashlib.sha256(template.encode("utf-8")).hexdigest()',
        'hashlib.sha256(version.encode("utf-8")).hexdigest()',
        (_META_DISK, _COMPLETE),
        "chat template を同定しない",
    ),
    _m(
        "o2  digest の model 名を照合しない",
        '        if isinstance(m, dict) and bat.MODEL in (m.get("name"), m.get("model")):\n',
        "        if isinstance(m, dict):\n",
        (_IDENTITY,),
        "別の model の digest を記録する",
        Witness(item="other_model", exc="Failed", text=_NOT_RAISED_PREFLIGHT),
    ),
    _m(
        "o3  空の版を許す",
        "    if not isinstance(version, str) or not version:\n",
        "    if not isinstance(version, str):\n",
        (_IDENTITY,),
        "版の無い環境で走る",
        Witness(
            item="no_version",
            exc="ScheduleError",
            text="observed environment is missing or malformed",
            via="run",
        ),
    ),
    _m(
        "o4  digest が無くても続ける",
        '    if digest is None:\n        msg = f"model',
        '    if False:\n        msg = f"model',
        (_IDENTITY,),
        "model の無い環境で PreflightError でなく予定表の検査まで進む",
        Witness(
            item="no_model",
            exc="ScheduleError",
            text="observed environment is missing or malformed",
            via="run",
        ),
    ),
    _m(
        "o5  template が無くても続ける",
        "    if not isinstance(template, str):\n",
        "    if False:\n",
        (_IDENTITY,),
        "chat template の無い応答で PreflightError でなく AttributeError になる",
        Witness(
            item="null_template",
            exc="AttributeError",
            text="'NoneType' object has no attribute 'encode'",
            via="read_observed",
        ),
    ),
    _m(
        "o6  preflight で HTTP の状態を見ない",
        '    if response.status_code != httpx.codes.OK:\n        msg = f"{response.request.url.path}',
        '    if False:\n        msg = f"{response.request.url.path}',
        (_IDENTITY,),
        "404 の応答の値を observed として使う",
        Witness(item="show_404", exc="Failed", text=_NOT_RAISED_PREFLIGHT),
    ),
    _m(
        "o8  /api/show に model を渡さない",
        'json={"model": bat.MODEL}',
        'json={"name": bat.MODEL}',
        (_SHOW, _META_DISK),
        "凍結 model の chat template を読まない (偽の Ollama は 404 を返す)",
        Witness(
            exc="PreflightError",
            text="/api/show returned HTTP 404",
            via="read_observed",
        ),
    ),
    _m(
        "o7  本走の observed を pilot と照合しない",
        "        if ref is not None and observed != ref:\n",
        "        if False:\n",
        (_MAIN_OBS,),
        "pilot と違う環境で本走を始めかける (予定表の検査が ScheduleError で止めるが、理由が違う)",
        Witness(
            exc="ScheduleError",
            text="observed environment differs from the pilot",
            via="run",
        ),
    ),
    # ================================================================ 再送と raw = null
    _m(
        "t1  再送 3 → 2",
        "RESENDS: Final[int] = 3",
        "RESENDS: Final[int] = 2",
        (_RESEND, _UNRESOLVED),
        "prereg §4 の再送 3 回より少ない",
        Witness(assert_stmt=True, text=_RESENT),
    ),
    _m(
        "t2  再送 3 → 4 (待ちの表も延ばす)",
        _RESENDS_BLOCK,
        _RESENDS_BLOCK.replace("= 3", "= 4").replace("120.0)", "120.0, 120.0)"),
        (_UNRESOLVED, _FINAL_ABORT),
        "prereg §4 の再送 3 回より多い (待ちの表を延ばさないと IndexError で落ち、回数の検査に届かない。Codex MEDIUM-4)",
        Witness(assert_stmt=True, text=_RESENT),
    ),
    _m(
        "t3  再送で seed を変える",
        "            reply = await send_chat(state.http, body)\n",
        "            reply = await send_chat(\n"
        "                state.http,\n"
        '                {**body, "options": {**body["options"], "seed": body["options"]["seed"] + attempt}},\n'
        "            )\n",
        (_RESEND, _FAILED_RESP),
        "再送が同じ seed でない (送る直前の照合が止める)",
        Witness(
            exc="SentBodyMismatchError",
            text="seed differs from the pilot schedule",
            via="check_sent_body",
        ),
    ),
    _m(
        "t4  再送が尽きても続行",
        "        if raw is None:\n            return REASON_TRANSPORT\n",
        "        if False:\n            return REASON_TRANSPORT\n",
        (_UNRESOLVED, _NULL),
        "transport 失敗の後も呼び続ける",
    ),
    _m(
        "t5  解けない transport 失敗を空文字 (⊥) に",
        "    return None\n\n\ndef absorb",
        '    return ""\n\n\ndef absorb',
        (_UNRESOLVED, _NULL),
        "transport 失敗を ⊥ に畳む (prereg §4 違反)",
    ),
    _m(
        "t6  transport 以外の例外も再送",
        '    except httpx.HTTPError as exc:\n        msg = f"{type(exc).__name__}: {exc}"\n',
        '    except Exception as exc:\n        msg = f"{type(exc).__name__}: {exc}"\n',
        (_OTHER_EXC, _SHIFTED),
        "照合の不一致や想定外の例外を transport 失敗に畳む",
        Witness(exc="Failed", text="DID NOT RAISE <class 'ValueError'>"),
    ),
    _m(
        "t7  HTTP の状態を見ない",
        '    if response.status_code != httpx.codes.OK:\n        msg = f"HTTP',
        '    if False:\n        msg = f"HTTP',
        (_FAILED_RESP,),
        "500 の応答の本文を答えとして使う",
    ),
    _m(
        "t8  JSON でない応答を例外のまま上げる",
        '    except ValueError as exc:\n        msg = "non-JSON response"\n',
        '    except KeyError as exc:\n        msg = "non-JSON response"\n',
        (_FAILED_RESP,),
        "JSON でない応答で再送せずに止まる",
        Witness(item="non_json", exc="JSONDecodeError", via="send_chat"),
    ),
    _m(
        "t9  文字列でない content を受ける",
        '    if not isinstance(content, str):\n        msg = f"message.content',
        '    if False:\n        msg = f"message.content',
        (_NULL, _FAILED_RESP),
        "null の content を再送せずに受ける",
    ),
    _m(
        "t10 object でない応答を前提にする",
        '    message = payload.get("message") if isinstance(payload, dict) else None\n',
        '    message = payload.get("message")\n',
        (_FAILED_RESP,),
        "配列の応答で AttributeError になる",
        Witness(
            item="non_object",
            exc="AttributeError",
            text="'list' object has no attribute 'get'",
            via="send_chat",
        ),
    ),
    _m(
        "t11 応答の model を数えない",
        "            state.response_models.add(str(reply.model))\n",
        "",
        (_MODEL,),
        "別の model の応答に気づかない",
    ),
    _m(
        "t14 num_predict で切れた応答を数えない",
        '            state.n_length += reply.done_reason == "length"\n',
        "",
        (_LENGTH,),
        "来歴の n_finish_length が 0 のまま",
    ),
    _m(
        "t12 試行の記録を書かない",
        "        _write_line(state.attempts_fh, row)\n",
        "",
        (_RESEND, _FAILED_RESP),
        "再送の経過が残らない",
    ),
    _m(
        "t13 再送の回数を数えない",
        "            state.resends += 1\n",
        "",
        (_RESEND,),
        "来歴の再送の回数が 0 のまま",
    ),
    # ================================================================ 記録
    _m(
        "r1  raw を strip して記録",
        _RECORD_RAW,
        "            raw=None if raw is None else raw.strip(),\n"
        "            parsed=None if raw is None else state.stage.parse(arm, raw),\n",
        (_RAW,),
        "応答をそのまま残さない",
        Witness(assert_stmt=True, text="raw is not recorded verbatim"),
    ),
    _m(
        "r2  KNOW も行動 label として parse",
        "    return pg.parse_class(raw) if arm == pg.ARM_KNOW else sc.parse_choice(raw)\n",
        "    return sc.parse_choice(raw)\n",
        (_PARSE, _COMPLETE),
        "知識確認の答えが全て ⊥ になる (凍結 pilot 判定の re-parse と違い、公開されない)",
        Witness(assert_stmt=True, text=_NOT_PUBLISHED),
    ),
    _m(
        "r3  parsed を parse せずに raw で",
        _RECORD_RAW,
        "            raw=raw,\n            parsed=raw,\n",
        (_PARSE, _COMPLETE),
        "記録の parse が凍結の re-parse と違う",
        Witness(assert_stmt=True, text=_NOT_PUBLISHED),
    ),
    _m(
        "r4  記録を ensure_ascii=False で書く",
        "    line = json.dumps(obj, ensure_ascii=True, sort_keys=True)\n",
        "    line = json.dumps(obj, ensure_ascii=False, sort_keys=True)\n",
        _PILOT,
        "U+2028 などで 1 記録が 2 行に割れる (読み戻しが止める)",
        Witness(
            when="setup", exc="RecordError", text="record is not JSON", via="absorb"
        ),
    ),
    _m(
        "r5  call_index を 1 から",
        "    for index, key in enumerate(state.stage.plan):\n",
        "    for index, key in enumerate(state.stage.plan, start=1):\n",
        _PILOT,
        "call_index と予定表の位置がずれる",
        Witness(
            when="setup",
            exc="IndexError",
            text="tuple index out of range",
            via="run_calls",
        ),
    ),
    _m(
        "r6  記録のキーを plan の先頭に固定",
        "        arm, r, probe_id, k = key\n        rec = sc.Sample(",
        "        arm, r, probe_id, k = state.stage.plan[0]\n        rec = sc.Sample(",
        (_COMPLETE, _RAW),
        "記録のキーが送った呼び出しと違う (重複、公開されない)",
        Witness(assert_stmt=True, text=_NOT_PUBLISHED),
    ),
    _m(
        "r7  読み戻した記録を数えない",
        "    state.records.append(rows[0])\n",
        "",
        (_COMPLETE,),
        "来歴の記録数が 0",
        Witness(assert_stmt=True, text="n_records differs from the plan"),
    ),
    # ================================================================ 公開
    _m(
        "u1  常に公開",
        "    publishable = reason == REASON_COMPLETED\n",
        "    publishable = True\n",
        (_UNRESOLVED, _MODEL, _MANIFEST_PUB),
        "transport 失敗・異常のある run を公開する",
        Witness(assert_stmt=True, text="records.jsonl was published"),
    ),
    _m(
        "u2  公開前の読み戻しの結果を見ない",
        "        if read_back:\n",
        "        if False:\n",
        (_READ_BACK,),
        "凍結の検査を通らない記録を公開する",
    ),
    _m(
        "u3  公開前に読み戻さない",
        "    if reason == REASON_COMPLETED:\n"
        "        read_back = publication_problems(stage) + binding_problems(\n",
        "    if False:\n        read_back = publication_problems(stage) + binding_problems(\n",
        (_READ_BACK,),
        "読み戻さずに公開する",
    ),
    _m(
        "u4  公開しない",
        "    if publishable:\n        # commit point",
        "    if False:\n        # commit point",
        (_TWO_PHASE, _COMPLETE, _MAIN_RUN),
        "完了した run を公開しない",
    ),
    _m(
        "u5  1 相目の来歴を completed で書く",
        '        "exit_reason": REASON_ABORTED if publishable else reason,\n',
        '        "exit_reason": reason,\n',
        (_TWO_PHASE,),
        "rename の前に kill されると、未公開の run が completed に見える",
    ),
    _m(
        "u6  1 相目に pending の注記を書かない",
        '        "error": _join(error, PENDING_NOTE) if publishable else error,\n',
        '        "error": error,\n',
        (_TWO_PHASE,),
        "公開の前に中断した run を見分けられない",
    ),
    _m(
        "u7  3 項目を 1 相目にも書く",
        '        "published": False,\n        "n_records"',
        '        "published": False,\n'
        '        "driver_sha256": _sha256(pathlib.Path(__file__).resolve()),\n'
        '        "n_records"',
        (_TWO_PHASE, _UNRESOLVED),
        "公開していない run の来歴が第 2 段の照合を通りうる (DD-5)",
    ),
    _m(
        "u8  2 相目の来歴を書かない",
        "            write_json_durable(prov_path, provenance, exclusive=False)\n",
        "            pass\n",
        (_TWO_PHASE, _COMPLETE, _GATE),
        "公開済みの run の来歴が未公開のまま",
    ),
    _m(
        "u9  公開の失敗を来歴に書かない",
        '            provenance["error"] = _join(\n'
        '                error, f"publication failed: {type(exc).__name__}: {exc}"\n'
        "            )\n",
        "            pass\n",
        (_PUB_FAIL,),
        "公開の失敗の理由が残らない",
    ),
    _m(
        "u10 公開の失敗を completed のまま返す",
        "        except OSError as exc:\n            reason = REASON_ABORTED\n",
        "        except OSError as exc:\n            reason = REASON_COMPLETED\n",
        (_PUB_FAIL,),
        "公開されていない run が completed で終わる",
    ),
    _m(
        "u11 判定と違う reader (改行だけで分割) で読み戻す",
        '        lines = (stage.run_dir / PARTIAL_NAME).read_text(encoding="utf-8").splitlines()\n',
        '        lines = (stage.run_dir / PARTIAL_NAME).read_text(encoding="utf-8").split(chr(10))\n',
        (_PUB_READER,),
        "判定 (splitlines) では割れる記録を読めたことにする",
    ),
    _m(
        "u12 書いた meta を読まない",
        '        meta = json.loads((stage.run_dir / META_NAME).read_text(encoding="utf-8"))\n',
        "        meta = sc.request_meta()\n",
        (_PUB_CHECK, _PUB_META),
        "書いた meta.json でなく別の値を検査する",
    ),
    _m(
        "u13 読めない記録を問題なしに畳む",
        '        return [f"unreadable: {type(exc).__name__}: {exc}"]\n',
        "        return []\n",
        (_PUB_READER,),
        "読めない partial を公開する",
    ),
    _m(
        "u14 公開前に完全性を見ない",
        _PUB_COMPLETE,
        "    if False:\n",
        (_PUB_CHECK,),
        "欠けた記録を公開する",
    ),
    _m(
        "u15 公開前に transport 失敗を見ない",
        "    if any(s.raw is None for s in samples):\n",
        "    if False:\n",
        (_PUB_CHECK,),
        "raw = null の記録を公開する",
    ),
    _m(
        "u16 公開前に凍結の構造の検査をしない",
        "    out = list(stage.structure(samples))\n",
        "    out = []\n",
        (_PUB_CHECK,),
        "seed の違う記録を公開する",
    ),
    _m(
        "u17 公開前の meta の照合で pilot の observed を見ない",
        "    out.extend(sc.meta_violations(meta, stage.reference_observed))\n",
        "    out.extend(sc.meta_violations(meta, None))\n",
        (_PUB_META,),
        "本走の meta が pilot の observed と違っても公開する",
    ),
    _m(
        "u18 公開済みで 2 相目の来歴が書けないと失敗にする",
        '            if not provenance["published"]:\n                raise\n',
        "            raise\n",
        (_FINAL_PROV,),
        "公開済みの run を例外で終える",
        Witness(exc="OSError", text="readonly (second phase)", via="_finish"),
    ),
    _m(
        "u19 来歴・公開の失敗で元の例外を隠す",
        "            if primary is None:\n                raise\n",
        "            raise\n",
        (_ORIGINAL,),
        "元の例外が来歴の書き込みの失敗に隠れる",
        Witness(exc="OSError", text="readonly", via="_finish"),
    ),
    _m(
        "u20 driver の sha256 を公開の後にディスクから",
        "                    driver_sha256=_DRIVER_SHA,\n",
        "                    driver_sha256=_sha256(_DRIVER_PATH),\n",
        (_RUNNING,),
        "照合の後に差し替わった driver の sha256 を来歴に書く (Codex HIGH-2)",
    ),
    _m(
        "u21 records の sha256 を meta の bytes から",
        "                    records_sha256=hashlib.sha256(written).hexdigest(),\n",
        "                    records_sha256=hashlib.sha256(out.meta_bytes).hexdigest(),\n",
        (_TWO_PHASE, _GATE),
        "provenance が公開した記録に結び付かない",
    ),
    _m(
        "u22 meta の sha256 を記録の bytes から",
        "                    meta_sha256=hashlib.sha256(out.meta_bytes).hexdigest(),\n",
        "                    meta_sha256=hashlib.sha256(written).hexdigest(),\n",
        (_TWO_PHASE, _GATE),
        "provenance が meta に結び付かない",
    ),
    _m(
        "u25 書いた bytes と照合しない",
        "        read_back = publication_problems(stage) + binding_problems(\n"
        "            stage.run_dir, PARTIAL_NAME, written, out.meta_bytes\n"
        "        )\n",
        "        read_back = publication_problems(stage)\n",
        (_SWAPPED,),
        "同じ grid の別の run の記録・別の observed の meta を公開する (Codex HIGH-1)",
    ),
    _m(
        "u26 照合で meta を見ない",
        "    for rel, want in ((records_name, records), (META_NAME, meta)):\n",
        "    for rel, want in ((records_name, records),):\n",
        (_SWAPPED,),
        "別の observed の meta を公開する",
    ),
    _m(
        "u27 rename の後に照合しない",
        "            after = binding_problems(\n"
        "                stage.run_dir, RECORDS_NAME, written, out.meta_bytes\n"
        "            )\n",
        "            after: list[str] = []\n",
        (_AFTER_RENAME,),
        "rename の後に差し替わった記録に 3 項目を結び付ける",
    ),
    _m(
        "u28 2 相目の来歴の失敗を completed で終える",
        "            reason = REASON_ABORTED\n            _progress(\n",
        "            _progress(\n",
        (_FINAL_PROV,),
        "第 2 段に使えない run (来歴に 3 項目なし) が completed で終わる",
    ),
    _m(
        "u29 transport 失敗の来歴に status を書かない",
        '        "status": sc.STATUS_NOT_COMPUTED if wrote_null else None,\n',
        '        "status": None,\n',
        (_UNRESOLVED, _INTERRUPTED),
        "prereg §4 の status=not_computed が残らない (Codex MEDIUM-3)",
    ),
    _m(
        "u30 どの run の来歴にも status を not_computed で書く",
        '        "status": sc.STATUS_NOT_COMPUTED if wrote_null else None,\n',
        '        "status": sc.STATUS_NOT_COMPUTED,\n',
        (_COMPLETE,),
        "公開した run まで not_computed と書く",
        Witness(assert_stmt=True, text="'not_computed' is None"),
    ),
    _m(
        "u34 status を終了理由から決める",
        "    wrote_null = state is not None and any(s.raw is None for s in state.records)\n",
        "    wrote_null = reason == REASON_TRANSPORT\n",
        (_INTERRUPTED,),
        "終了時の observed の取得中に中断すると not_computed が消える (Codex 再 review MEDIUM-2)",
    ),
    _m(
        "u31 records の sha256 を rename の後のファイルから",
        "                    records_sha256=hashlib.sha256(written).hexdigest(),\n",
        "                    records_sha256=_sha256(stage.run_dir / RECORDS_NAME),\n",
        (_HASHES,),
        "照合と hash の間に差し替わった記録を来歴に結び付ける (code-reviewer の再レビュー MEDIUM)",
    ),
    _m(
        "u32 meta の sha256 を rename の後のファイルから",
        "                    meta_sha256=hashlib.sha256(out.meta_bytes).hexdigest(),\n",
        "                    meta_sha256=_sha256(stage.run_dir / META_NAME),\n",
        (_HASHES,),
        "照合と hash の間に差し替わった meta を来歴に結び付ける",
    ),
    _m(
        "u33 rename の後の照合に落ちた記録を公開名に残す",
        "                    (stage.run_dir / RECORDS_NAME).rename(stage.run_dir / REJECTED_NAME)\n",
        "                    pass\n",
        (_AFTER_RENAME,),
        "書き換えられた記録が公開名に残り、凍結 run.sh が gate を計算する",
        Witness(assert_stmt=True, text="records.jsonl was published"),
    ),
    _m(
        "u23 公開時の manifest の結果を見ない",
        "        at_publication = manifest_problems(stage.name)\n        if at_publication:\n",
        "        at_publication = manifest_problems(stage.name)\n        if False:\n",
        (_MANIFEST_PUB,),
        "公開の時点で manifest が崩れていても公開する",
    ),
    _m(
        "u24 公開時に manifest を照合しない",
        "    if reason == REASON_COMPLETED:\n        at_publication = manifest_problems(stage.name)\n",
        "    if False:\n        at_publication = manifest_problems(stage.name)\n",
        (_MANIFEST_PUB,),
        "公開の時点の manifest を見ない",
    ),
    # ================================================================ 来歴の異常
    _m(
        "a1  固定ファイルの変化を異常にしない",
        "    if changed:\n        anomalies.append",
        "    if False:\n        anomalies.append",
        (_PINNED_CHANGE,),
        "実走中に判定コードが変わっても公開する",
    ),
    _m(
        "a2  固定ファイルを終了時どうしで比べる",
        "if pinned_end[p] != out.pinned_start.get(p)",
        "if pinned_end[p] != pinned_end.get(p)",
        (_PINNED_CHANGE,),
        "変化を検出できない",
    ),
    _m(
        "a3  想定外の応答 model を異常にしない",
        "    if models - {bat.MODEL}:\n",
        "    if False:\n",
        (_MODEL,),
        "別の model の応答を公開する",
    ),
    _m(
        "a4  observed の変化を異常にしない",
        "    if out.observed_end is not None and out.observed_end != out.observed_start:\n",
        "    if False:\n",
        (_OBS_CHANGE,),
        "実走中に重み・template が変わっても公開する",
    ),
    _m(
        "a5  異常を終了理由に反映しない",
        "    if anomalies and reason == REASON_COMPLETED:\n",
        "    if False:\n",
        (_MODEL, _OBS_CHANGE, _PINNED_CHANGE),
        "異常のある run を公開する",
    ),
    _m(
        "a6  終了時の observed を読まない",
        "        observed_end, final_error = await final_observed(http, observer, backoff_s)\n",
        # 開始時の値を流用する (Codex 再 review MEDIUM-1: 前の置換は未定義の名前で NameError になっていた)
        "        observed_end, final_error = out.observed_start, None\n",
        (_OBS_CHANGE, _FINAL_ABORT),
        "実走中の環境の変化を見ない",
    ),
    _m(
        "a7  終了時の observed を再送しない",
        "    for attempt in range(1 + RESENDS):\n        try:\n            return await read_observed",
        "    for attempt in range(1):\n        try:\n            return await read_observed",
        (_FINAL_RESENT,),
        "一時的な不調で完了した run を捨てる",
    ),
    _m(
        "a8  transport 失敗の後の終了時の失敗を aborted に",
        "            if stop != REASON_TRANSPORT:\n",
        "            if True:\n",
        (_FINAL_KEEP,),
        "transport 失敗の分類が変わる",
    ),
    _m(
        "a9  終了時の observed の失敗を aborted にしない",
        "            if stop != REASON_TRANSPORT:\n",
        "            if False:\n",
        (_FINAL_ABORT,),
        "終了時に環境を同定できない run を公開する",
    ),
    _m(
        "a10 固定ファイルを公開時の manifest の照合の前に比べる",
        _FINISH_BLOCK,
        _FINISH_EARLY,
        (_PINNED_ORDER,),
        "manifest の照合 (約 16 秒) の間の差し替えを見逃す (Codex HIGH-2)",
    ),
    _m(
        "a11 起動時に取った固定ファイルの sha256 を使わない",
        "                pinned_sha256(stage.name) if pinned_start is None else pinned_start\n",
        "                pinned_sha256(stage.name)\n",
        (_PINNED_LAUNCH,),
        "起動の検査から実走の開始までの差し替えを見逃す (Codex HIGH-2)",
    ),
    _m(
        "a12 終了時にディスクの driver を実行中の driver と比べない",
        "    if _sha256(_DRIVER_PATH) != _DRIVER_SHA:\n        anomalies.append(",
        "    if False:\n        anomalies.append(",
        (_DRIVER_SWAP,),
        "実行中に差し替わった driver の run を公開する",
    ),
    _m(
        "a13 固定ファイルを読み戻しの前に比べる",
        _BEFORE_READ_BACK[0],
        _BEFORE_READ_BACK[1],
        (_PINNED_READBACK,),
        "読み戻しの間の差し替えを見逃す (code-reviewer の再レビュー LOW)",
    ),
    _m(
        "a14 読めない固定ファイルで例外にする",
        "    except OSError:\n        return None\n",
        "    except FileNotFoundError:\n        return None\n",
        (_SHA_UNREADABLE,),
        "読めないファイルで来歴を書けなくなる (code-reviewer の再レビュー LOW)",
        Witness(exc="PermissionError", text="locked", via="_sha256"),
    ),
    _m(
        "a15 main が起動の検査の後に固定ファイルの sha256 を取る",
        _MAIN_PINNED,
        "    problems = launch_problems(args.stage)\n"
        "    pinned_start = pinned_sha256(args.stage)\n",
        (_MAIN_STAGE,),
        "起動の検査 (manifest の照合 約 16 秒) の間の差し替えを見逃す (code-reviewer の再レビュー LOW)",
    ),
    # ================================================================ 運用の保護
    _m(
        "q1  中身のある run dir を拒否しない",
        "    if run_dir.exists() and any(run_dir.iterdir()):\n",
        "    if False:\n",
        (_NON_EMPTY,),
        "前の run に重ねて書く (再開しない規律)",
        Witness(exc="Failed", text="DID NOT RAISE <class 'FileExistsError'>"),
    ),
    _m(
        "q2  preflight を飛ばす",
        "        observed = await read_observed(http, observer)\n        ref",
        '        observed = {"model_digest": "x", "ollama_version": "x", "template_sha256": "x"}\n        ref',
        (_PREFLIGHT, _META_DISK),
        "実行環境を同定せずに走る",
    ),
    _m(
        "q3  meta.json を書かない",
        "        write_json_durable(stage.run_dir / META_NAME, meta, exclusive=True)\n",
        "        pass\n",
        (_META_DISK, _COMPLETE),
        "meta.json の無い run (公開されない)",
    ),
    _m(
        "q4  main が段以外の引数を受け取る",
        "    args = ap.parse_args(argv)\n",
        "    args, _ = ap.parse_known_args(argv)\n",
        (_ARGS,),
        "run dir・endpoint を差し替える登録外の実走経路を開ける",
        Witness(item="argv0", exc="Failed", text="DID NOT RAISE <class 'SystemExit'>"),
    ),
    _m(
        "q5  起動拒否を外す",
        "    if problems:\n        for p in problems:\n",
        "    if False:\n        for p in problems:\n",
        (_REFUSE,),
        "起動の前提が崩れていても走る",
    ),
    _m(
        "q6  本走でも pilot の段を走らせる",
        "            if args.stage == STAGE_PILOT\n",
        "            if True\n",
        (_MAIN_STAGE,),
        "段を取り違える",
    ),
    _m(
        "q7  本走の observed を gate から読まない",
        '    return main_stage(run_dir, gate["R"], gate["observed"])\n',
        '    return main_stage(run_dir, gate["R"], {})\n',
        (_MAIN_STAGE,),
        "本走の observed を pilot と照合しない",
    ),
    _m(
        "q8  exit code を終了理由から返さない",
        "    return EXIT_CODES[reason]\n",
        "    return 0\n",
        (_MAIN_STAGE,),
        "transport 失敗でも 0 で終わる",
    ),
    # ================================================================ 起動の前提
    _m(
        "l1  manifest の exit code を見ない",
        "    if code != 0 or last != want:\n",
        "    if last != want:\n",
        (_OK_LINE,),
        "exit 1 の照合を OK とみなす",
    ),
    _m(
        "l2  manifest の末尾行を見ない",
        "    if code != 0 or last != want:\n",
        "    if code != 0:\n",
        (_OK_LINE,),
        "NOT FROZEN (exit 0 の場合) を OK とみなす",
    ),
    _m(
        "l3  OK を末尾以外でも受ける",
        "last != want",
        'want not in out.split("\\n")',
        (_OK_LINE,),
        "OK の後に続く行を見ない",
    ),
    _m(
        "l4  段の名前を照合しない",
        '    want = f"MANIFEST OK (stage {stage_name})"\n',
        '    want = "MANIFEST OK (stage pilot)"\n',
        (_OK_LINE,),
        "本走の前提に pilot の段の OK を使う",
    ),
    _m(
        "l5  manifest が走らないことを問題にしない",
        '        return [f"manifest --verify --stage {stage_name} could not run: {exc}"]\n',
        "        return []\n",
        (_NO_RUN,),
        "照合できないことを OK に畳む",
    ),
    _m(
        "l6  certification を起動の前提に入れない",
        "    problems = certification_problems(DRIVER_CERT)\n",
        "    problems: list[str] = []\n",
        (_COMBINE,),
        "certify されていない driver で走る",
    ),
    _m(
        "l7  manifest を起動の前提に入れない",
        "    problems.extend(manifest_problems(stage_name))\n",
        "",
        (_COMBINE,),
        "封印の崩れた状態で走る",
    ),
    _m(
        "l8  本走で gate を見ない",
        "    if stage_name == STAGE_MAIN:\n        problems.extend(gate_problems(GATE_PATH))\n",
        "    if False:\n        problems.extend(gate_problems(GATE_PATH))\n",
        (_COMBINE,),
        "pilot が GO でないのに本走を走らせる",
    ),
    _m(
        "l9  git の追跡を見ない",
        '        if _git("ls-files", "--error-unmatch", rel) is None:\n',
        "        if False:\n",
        (_GIT,),
        "commit していないファイルで走る",
    ),
    _m(
        "l10 HEAD との差分を見ない",
        '    if _git("diff", "--quiet", "HEAD", "--", *files) is None:\n',
        "    if False:\n",
        (_GIT,),
        "HEAD と違うファイルで走る",
    ),
    _m(
        "l11 certification の契約を使わない",
        "    return man.driver_certification_violations(obj, _REPO_ROOT)\n",
        "    return []\n",
        (_CERT,),
        "壊れた certification を通す",
    ),
    _m(
        "l12 読めない certification を問題にしない",
        '        return [f"driver certification unreadable: {cert}"]\n',
        "        return []\n",
        (_CERT,),
        "certification の無い driver で走る",
    ),
    _m(
        "l13 gate の GO を見ない",
        '    if not isinstance(gate, dict) or gate.get("decision") != pg.DECISION_GO:\n',
        "    if not isinstance(gate, dict):\n",
        (_GATE_PROBLEMS,),
        "STOP の pilot の後に本走を走らせる",
    ),
    _m(
        "l14 gate の R の型を見ない",
        'type(gate.get("R")) is not int',
        'gate.get("R") is None',
        (_GATE_PROBLEMS,),
        "R が整数でない gate を通す",
    ),
    _m(
        "l15 gate の observed を見ない",
        '    if type(gate.get("R")) is not int or not isinstance(gate.get("observed"), dict):\n',
        '    if type(gate.get("R")) is not int:\n',
        (_GATE_PROBLEMS,),
        "observed の無い gate を通す",
    ),
    _m(
        "l16 読めない gate を問題にしない",
        '        return [f"pilot gate unreadable: {gate_path}"]\n',
        "        return []\n",
        (_GATE_PROBLEMS,),
        "gate の無い本走を走らせる",
    ),
    _m(
        "l17 固定ファイルに driver の証拠を入れない",
        "        man.DRIVER_HARNESS,\n        man.DRIVER_TEST,\n        man.DRIVER_CERT,\n",
        "",
        (_PINNED,),
        "harness・test・certification の変更に気づかない",
    ),
    _m(
        "l18 本走で第 2 段の証拠を固定しない",
        "        files = (*files, *man.MAIN_EVIDENCE, man.MANIFEST_MAIN)\n",
        "        files = (*files,)\n",
        (_PINNED,),
        "pilot の記録・gate・第 2 段の manifest の変更に気づかない",
    ),
    _m(
        "l19 起動時にディスクの driver を実行中の driver と比べない",
        "    if _sha256(_DRIVER_PATH) != _DRIVER_SHA:\n        problems.append(",
        "    if False:\n        problems.append(",
        (_DRIVER_SWAP,),
        "import の後に差し替わった driver で起動する (Codex HIGH-2)",
    ),
    _m(
        "l20 main が起動時の固定ファイルの sha256 を渡さない",
        "run(stage, httpx.AsyncHTTPTransport(), pinned_start=pinned_start)",
        "run(stage, httpx.AsyncHTTPTransport())",
        (_MAIN_STAGE,),
        "起動の検査から実走の開始までの差し替えを見逃す",
    ),
    _m(
        "l21 manifest の出力を strip してから末尾行を見る",
        '    last = out.removesuffix("\\n").rsplit("\\n", 1)[-1]\n',
        '    last = out.strip().rsplit("\\n", 1)[-1]\n',
        (_OK_LINE,),
        "末尾の空白・空行の付いた出力を OK とみなす",
    ),
    _m(
        "l25 manifest の末尾行を splitlines で切る",
        '    last = out.removesuffix("\\n").rsplit("\\n", 1)[-1]\n',
        '    last = (out.splitlines() or [""])[-1]\n',
        (_OK_LINE,),
        "LF 以外の区切り文字 (U+001C・U+0085・U+2028) の後ろを捨てて OK とみなす (Codex 再 review LOW-1)",
    ),
    _m(
        "l22 起動の前提で PYTHONHASHSEED を SEED と比べない",
        '        if env.get("PYTHONHASHSEED") != seed:\n',
        "        if False:\n",
        (_INTERPRETER,),
        "run.sh と違う hash seed で、process の中の manifest の照合をする (decisions DF-5)",
    ),
    _m(
        "l23 manifest を固定の段で照合する",
        '            code = man.main(["--verify", "--stage", stage_name])\n',
        '            code = man.main(["--verify", "--stage", "pilot"])\n',
        (_RUN_MANIFEST,),
        "本走の前提に pilot の段の照合を使う",
    ),
    # ============================ manifest の照合を process の中で (Codex 4 回目 HIGH-1、decisions DF-5)
    _m(
        "h1  manifest の照合を子プロセスで起動する",
        "        with contextlib.redirect_stdout(out):\n"
        '            code = man.main(["--verify", "--stage", stage_name])\n',
        "        proc = subprocess.run(  # noqa: S603\n"
        '            [sys.executable, man.SELF, "--verify", "--stage", stage_name],\n'
        '            capture_output=True, encoding="utf-8", errors="replace", check=False,\n'
        "        )\n"
        "        code = proc.returncode\n"
        '        out.write(proc.stdout or "")\n',
        (_RUN_MANIFEST,),
        "門も _PinnedFinder も無い子が、未追跡の scripts/__init__.py 等を実行しても、照合の最後の行は変わらない",
    ),
    _m(
        "h2  照合の例外を畳まない",
        "    except (Exception, SystemExit) as exc:  # noqa: BLE001 — 照合が走りきらなければ不合格\n",
        "    except ZeroDivisionError as exc:  # noqa: BLE001 — 照合が走りきらなければ不合格\n",
        (_FOLD,),
        "照合の例外が起動・公開の判断の外へ抜ける (公開の時点では来歴の異常にならない)",
        Witness(
            exc="RuntimeError", text="the frozen check exploded", via="_run_manifest"
        ),
    ),
    _m(
        "h3  照合の出力を返さない",
        "    return code, out.getvalue()\n",
        '    return code, ""\n',
        (_RUN_MANIFEST,),
        "最後の行の照合が、照合の出力でなく空の文字列を見る",
    ),
    _m(
        "h5  起動の前提で UTF-8 mode を見ない",
        "    if mode != 1:\n",
        "    if False:\n",
        (_INTERPRETER,),
        "run.sh と違う UTF-8 mode で、process の中の manifest の照合をする",
    ),
    _m(
        "h6  起動の前提に interpreter の設定を入れない",
        "    problems.extend(interpreter_problems())\n",
        "    problems.extend([])\n",
        (_COMBINE,),
        "run.sh と違う設定で起動しても拒否しない",
    ),
    _m(
        "h7  起動の前提で -E/-I の起動を見ない",
        '    if getattr(fl, "ignore_environment", 0):\n',
        "    if False:\n",
        (_INTERPRETER,),
        "-E/-I で起動すると PYTHONHASHSEED が効かないのに、os.environ に残る値で通す (code-reviewer MEDIUM-3)",
    ),
    _m(
        "h8  照合の SystemExit を畳まない",
        "    except (Exception, SystemExit) as exc:  # noqa: BLE001 — 照合が走りきらなければ不合格\n",
        "    except Exception as exc:  # noqa: BLE001 — 照合が走りきらなければ不合格\n",
        (_FOLD,),
        "照合の SystemExit が公開の判断の外へ抜け、来歴が書かれない (code-reviewer LOW-5)",
        Witness(exc="SystemExit", via="_run_manifest"),
    ),
    _m(
        "l24 git の失敗を None にしない",
        "            check=True,\n",
        "            check=False,\n",
        (_GIT_REAL,),
        "git が失敗しても「追跡済み」「HEAD と一致」に畳む (code-reviewer MEDIUM-5)",
    ),
    # ================================================ 実行したコードの同定 (Codex 再 review HIGH-1)
    _m(
        "x1  コンパイル結果の比較を常に真にする",
        '        return code == compile(data, str(path), "exec", dont_inherit=True)\n',
        "        return True\n",
        (_COMPILES, _LAUNCH_SWAP),
        "別のプログラムを、来歴の hash の bytes のコンパイル結果とみなす",
    ),
    _m(
        "x2  コンパイルできない bytes を同じプログラムとみなす",
        "    except (SyntaxError, ValueError):\n        return False\n",
        "    except (SyntaxError, ValueError):\n        return True\n",
        (_COMPILES,),
        "構文の通らない bytes を、実行中のプログラムと同じとみなす",
    ),
    _m(
        "x3  driver の検証を常に真にする",
        "_DRIVER_RUNS_ITS_BYTES: bool = _compiles_to(\n",
        "_DRIVER_RUNS_ITS_BYTES: bool = True or _compiles_to(\n",
        (_LAUNCH_SWAP,),
        "起動の窓で差し替わった driver (実行したのは別版) を見逃す",
    ),
    _m(
        "x4  driver の検証に別の code object を使う",
        "    sys._getframe(0).f_code,",
        "    _compiles_to.__code__,",
        (_SELF_BYTES, _LAUNCH_CLI),
        "実行中のモジュールでない code object と比べる (正しい driver を拒否する)",
    ),
    _m(
        "x5  loader がディスクを読み直して実行する",
        '        code = compile(self.data, str(self.path), "exec", dont_inherit=True)\n',
        '        code = compile(self.path.read_bytes(), str(self.path), "exec", dont_inherit=True)\n',
        (_FINDER,),
        "hash した bytes と、実行した bytes が別になりうる",
    ),
    _m(
        "x6  loader の sha256 をディスクから取る",
        "        self.pinned_sha256 = hashlib.sha256(data).hexdigest()\n",
        "        self.pinned_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()\n",
        (_FINDER,),
        "実行する bytes でなく、その時点のディスクを hash する",
    ),
    _m(
        "x7  finder が他の package の名前も読む",
        '        if head != self.package or not name or "." in name:\n',
        '        if not name or "." in name:\n',
        (_FINDER,),
        "対象外の import を、root のファイルで置き換える",
    ),
    _m(
        "x8  起動のときに finder を入れない",
        "    sys.meta_path.insert(0, _PinnedFinder(_REPO_ROOT))\n",
        "    pass\n",
        (_LAUNCH_CLI,),
        "repo のモジュールを通常の import (pyc を含む) で読み、実行した bytes を同定しない",
    ),
    _m(
        "x9  driver の検証の結果を見ない",
        "    if not _DRIVER_RUNS_ITS_BYTES:\n",
        "    if False:\n",
        (_EXECUTED, _LAUNCH_SWAP),
        "実行中の driver が来歴の hash の bytes でなくても起動する",
    ),
    _m(
        "x10 driver の bytes を起動の検査の前の値と比べない",
        "    if pinned_start.get(man.DRIVER) != _DRIVER_SHA:\n",
        "    if False:\n",
        (_EXECUTED,),
        "起動から起動の検査までの driver の差し替えを見逃す",
    ),
    _m(
        "x11 finder を通らないモジュールを問題にしない",
        "        if sha is None:\n",
        "        if False:\n",
        (_EXECUTED, _LAUNCH_SWAP),
        "通常の import で読んだモジュール (実行した bytes が分からない) で起動する",
    ),
    _m(
        "x12 固定ファイルでないモジュールを問題にしない",
        "        elif rel not in files:\n",
        "        elif False:\n",
        (_EXECUTED,),
        "封印・certification の外のコードを実行して起動する",
    ),
    _m(
        "x13 実行した bytes を起動の検査の前の値と比べない",
        "        elif sha != pinned_start.get(rel):\n",
        "        elif False:\n",
        (_EXECUTED,),
        "import から起動の検査までのモジュールの差し替えを見逃す",
    ),
    _m(
        "x14 実行中のモジュールを見ない",
        "    mods = sys.modules if modules is None else modules\n",
        "    mods = {} if modules is None else modules\n",
        (_LAUNCH_SWAP,),
        "起動で実際に読まれたモジュールを照合しない",
    ),
    _m(
        "x15 main が実行中のコードを照合しない",
        "    problems += executed_problems(args.stage, pinned_start)\n",
        "    problems += []\n",
        (_MAIN_EXECUTED,),
        "実行したコードが来歴の hash を指さなくても起動する",
    ),
    _m(
        "x16 main が実行中のコードを起動の検査の前に照合する",
        "    problems = launch_problems(args.stage)\n"
        "    # 実行中のコードの照合は起動の検査の **後** (certification の検査が import する driver の harness も含める)\n"
        "    problems += executed_problems(args.stage, pinned_start)\n",
        "    problems = executed_problems(args.stage, pinned_start)\n"
        "    problems += launch_problems(args.stage)\n",
        (_MAIN_EXECUTED,),
        "certification の検査が import する driver の harness を照合しない",
    ),
    # ============================ 環境と固定ファイルの外のコード: 門 (g)・名前空間 (n)・走査 (s)
    _m(
        "g1  起動のときに門を入れない",
        "    sys.meta_path.insert(0, _LaunchGate(_environment_roots()))\n",
        "    pass\n",
        (_LAUNCH_SHADOW,),
        "scripts/ に置いた numpy.py が sys.path[0] から import されて実行される",
    ),
    _m(
        "g2  門が環境の外も通す",
        "            if outside:\n                msg = (\n",
        "            if False:\n                msg = (\n",
        (_GATE_REFUSE, _LAUNCH_SHADOW),
        "環境の外に所在がある module を import させる",
        Witness(item="numpy", exc="Failed", text=_NO_IMPORT_ERROR),
    ),
    _m(
        "g3  環境の判定が常に真",
        "    return any(_under(loc, r) for r in roots)\n",
        "    return True\n",
        (_IN_ENV, _ROOTS, _GATE_REFUSE, _OUTSIDE, _LAUNCH_SHADOW, _LAUNCH_EARLY),
        "どこにあるコードも環境として通す",
    ),
    _m(
        "g4  repo を含む prefix も環境に数える",
        "    return tuple(sorted(r for r in roots if not _under(repo_n, r)))\n",
        "    return tuple(sorted(roots))\n",
        (_ROOTS,),
        "venv を repo root そのものに作ると、repo の全てのコードが環境になる",
    ),
    _m(
        "g5  門が自分自身に尋ねる",
        "            if finder is self or find is None:\n",
        "            if find is None:\n",
        (_GATE_PASS, _LAUNCH_CLI),
        "門が自分を呼んで再帰し、起動のたびに RecursionError で落ちる",
    ),
    _m(
        "g6  下にあるかを文字列の前方一致で見る",
        "        return os.path.commonpath([path, root]) == root\n",
        "        return path.startswith(root)\n",
        (_IN_ENV,),
        "prefix と同じ文字列で始まる隣の dir (env2) を環境に数える",
    ),
    _m(
        "g7  比べられない組で例外を出す",
        "    try:\n        return os.path.commonpath([path, root]) == root\n"
        "    except ValueError:\n        return False\n",
        "    return os.path.commonpath([path, root]) == root\n",
        (_IN_ENV,),
        "別ドライブ・相対と絶対の組で ValueError になり、門が import を止める理由が変わる",
        Witness(exc="ValueError", via="_under"),
    ),
    _m(
        "g8  spec の所在に package の探索場所を含めない",
        '    out.extend(str(p) for p in getattr(spec, "submodule_search_locations", None) or ())\n',
        "    out.extend([])\n",
        (_GATE_REFUSE,),
        "環境の外の package (名前空間) を import させる",
        Witness(item="ns", exc="Failed", text=_NO_IMPORT_ERROR),
    ),
    _m(
        "g9  spec の所在に origin を含めない",
        "        out.append(origin)\n",
        "        pass\n",
        (_GATE_REFUSE, _OUTSIDE, _LAUNCH_SHADOW),
        "環境の外の file の module を import させる・走査が見逃す",
    ),
    _m(
        "n1  scripts を名前空間として持たない",
        "        if fullname == self.package:\n",
        "        if False:\n",
        (_NAMESPACE, _LAUNCH_CLI, _LAUNCH_INIT),
        "scripts の __init__.py が実行されうる (門が repo の scripts を止めて起動できない)",
    ),
    _m(
        "s1  起動の検査で走査をしない",
        "    problems += outside_problems(mods, _environment_roots() if roots is None else roots)\n",
        "    problems += []\n",
        (_EXECUTED, _LAUNCH_EARLY),
        "門より前に取り込まれた環境の外のコードで起動する",
    ),
    _m(
        "s2  走査が scripts の __init__.py を許す",
        '            if getattr(module, "__file__", None) is not None or where != namespace:\n',
        "            if where != namespace:\n",
        (_OUTSIDE,),
        "初期化のコードを実行した scripts で起動する",
    ),
    _m(
        "s3  走査が scripts の探索場所を見ない",
        '            if getattr(module, "__file__", None) is not None or where != namespace:\n',
        '            if getattr(module, "__file__", None) is not None:\n',
        (_OUTSIDE,),
        "root/scripts 以外も探す scripts で起動する",
    ),
    _m(
        "s4  走査が __file__ を見ない",
        "    if isinstance(file, str):\n        out.append(file)\n",
        "    if False:\n        out.append(file)\n",
        (_OUTSIDE, _EXECUTED),
        "spec の無い module の file を見逃す",
    ),
    _m(
        "s5  走査が spec の所在を見ない",
        '    out = _spec_locations(getattr(module, "__spec__", None))\n',
        "    out: list[str] = []\n",
        (_OUTSIDE,),
        "spec だけが所在を持つ module を見逃す",
    ),
    _m(
        "s6  走査が __path__ を見ない",
        '    out.extend(p for p in getattr(module, "__path__", None) or () if isinstance(p, str))\n',
        "    out.extend([])\n",
        (_OUTSIDE,),
        "探索場所だけを持つ package を見逃す",
    ),
    _m(
        "s7  走査が環境の外を許す",
        "        if outside:\n            problems.append(\n",
        "        if False:\n            problems.append(\n",
        (_OUTSIDE, _EXECUTED, _LAUNCH_EARLY),
        "環境の外のコードを実行したまま起動する",
    ),
    # ============================ 起動前に走りうるコード (Codex 4 回目 HIGH-2)・境界条件 (Codex 4 回目 LOW-2)
    _m(
        "s8  起動の検査で起動前の customization を見ない",
        "    problems += startup_problems(\n",
        "    _ = startup_problems(\n",
        (_EXECUTED, _LAUNCH_FAILED_SITE),
        "import に失敗して sys.modules に残らない sitecustomize を実行したまま起動する",
    ),
    _m(
        "s9  sitecustomize を見ない",
        '_STARTUP_MODULES: Final[tuple[str, ...]] = ("sitecustomize", "usercustomize")\n',
        '_STARTUP_MODULES: Final[tuple[str, ...]] = ("usercustomize",)\n',
        (_STARTUP, _EXECUTED, _LAUNCH_FAILED_SITE),
        "site が起動時に実行する sitecustomize を見逃す",
    ),
    _m(
        "s13 usercustomize を見ない",
        '_STARTUP_MODULES: Final[tuple[str, ...]] = ("sitecustomize", "usercustomize")\n',
        '_STARTUP_MODULES: Final[tuple[str, ...]] = ("sitecustomize",)\n',
        (_STARTUP,),
        "site が起動時に実行する usercustomize を見逃す",
    ),
    _m(
        "s10 最初に見つかった entry だけを見る",
        "        specs = [importlib.machinery.PathFinder.find_spec(name, [e]) for e in entries]\n",
        "        specs = [importlib.machinery.PathFinder.find_spec(name, entries)]\n",
        (_STARTUP,),
        "環境の中の customization の後ろにある外のもの (実行されたかを sys.modules では確かめられない) を見逃す",
    ),
    _m(
        "s11 user site の .pth を見ない",
        "    if user_site is not None and not _in_environment(user_site, roots):\n",
        "    if False:\n",
        (_STARTUP,),
        "site が起動時に実行する user site の .pth を見逃す",
    ),
    _m(
        "s12 走査が所在の先頭 1 件だけを見る",
        "            loc for loc in _module_locations(module) if not _in_environment(loc, roots)\n",
        "            loc\n"
        "            for loc in _module_locations(module)[:1]\n"
        "            if not _in_environment(loc, roots)\n",
        (_OUTSIDE,),
        "探索場所が環境の中と外にある package を、先頭が中なら通す",
    ),
    _m(
        "g10 所在の link を解決しない",
        "    resolved = os.path.normcase(os.path.realpath(path))\n",
        "    resolved = os.path.normcase(os.path.abspath(path))\n",
        (_LINKS,),
        "環境の中の link の先にある外のコードを、環境の中として通す",
    ),
    _m(
        "g11 門が所在の先頭 1 件だけを見る",
        "                for loc in _spec_locations(spec)\n"
        "                if not _in_environment(loc, self.roots)\n",
        "                for loc in _spec_locations(spec)[:1]\n"
        "                if not _in_environment(loc, self.roots)\n",
        (_GATE_REFUSE,),
        "portion が環境の中と外にある名前空間を、先頭が中なら import させる",
        Witness(item="ns_mixed", exc="Failed", text=_NO_IMPORT_ERROR),
    ),
    _m(
        "g12 環境に exec_prefix を数えない",
        "    prefixes = (sys.prefix, sys.exec_prefix, sys.base_prefix, sys.base_exec_prefix)\n",
        "    prefixes = (sys.prefix, sys.base_prefix, sys.base_exec_prefix)\n",
        (_FOUR_PREFIXES,),
        "exec_prefix が prefix と違う環境で、正当な拡張 module の import を止める",
    ),
    _m(
        "g13 環境に base_exec_prefix を数えない",
        "    prefixes = (sys.prefix, sys.exec_prefix, sys.base_prefix, sys.base_exec_prefix)\n",
        "    prefixes = (sys.prefix, sys.exec_prefix, sys.base_prefix)\n",
        (_FOUR_PREFIXES,),
        "base_exec_prefix が base_prefix と違う環境で、正当な拡張 module の import を止める",
    ),
    _m(
        "s14 PYTHONPATH を見ない",
        "    for entry in pythonpath.split(os.pathsep) if pythonpath else ():\n",
        "    for entry in ():\n",
        (_STARTUP, _LAUNCH_PTH_SHADOW),
        "site の .pth の import 行が PYTHONPATH の影 (_virtualenv.py 等) を実行し、失敗して消えても起動する (code-reviewer HIGH-2)",
    ),
    _m(
        "s15 起動の検査が PYTHONPATH を渡さない",
        '    pythonpath = None if sys.flags.ignore_environment else env.get("PYTHONPATH")\n',
        "    pythonpath = None\n",
        (_EXECUTED, _LAUNCH_PTH_SHADOW),
        "PYTHONPATH の影を見ずに起動する",
    ),
    _m(
        "s16 user site が無効でも見る",
        '    if not getattr(found_site, "ENABLE_USER_SITE", False):\n',
        "    if False:\n",
        (_USER_SITE,),
        "site が無効にした user site の .pth を、起動前に走りうるものとして数える (起動を誤って止める)",
    ),
    _m(
        "s17 起動の検査が user site を渡さない",
        "        _user_site(),\n",
        "        None,\n",
        (_EXECUTED,),
        "site が有効にした環境の外の user site の .pth を見ずに起動する (Codex 5 回目 LOW-2)",
    ),
    # ============================ レジストリの検索パス (Codex 5 回目 HIGH-1、decisions DG-4)
    _m(
        "k1  startup_problems がレジストリの entry を見ない",
        "    for path in registry:\n",
        "    for path in ():\n",
        (_STARTUP,),
        "getpath がレジストリから足した環境の外の dir の _virtualenv.py 等を、site の .pth が実行して失敗しても起動する",
    ),
    _m(
        "k2  起動の検査がレジストリの entry を渡さない",
        "        registry = [] if sys.flags.ignore_environment else _registry_paths(search)\n",
        "        registry = []\n",
        (_EXECUTED,),
        "レジストリの検索パスを見ずに起動する",
    ),
    _m(
        "k3  子キーの既定値を読まない",
        '                    found += str(r.QueryValue(key, sub)).split(";")\n',
        "                    found += []\n",
        (_REGISTRY,),
        "getpath が venv でも常に足す子キーの path を見逃す",
    ),
    _m(
        "k4  キー自身の既定値を sys.path に無くても数える",
        "            found += [e for e in own if e and _norm(e) in on_path]\n",
        "            found += own\n",
        (_REGISTRY,),
        "stdlib が見つかって使われていない既定値 (python.org 版を入れた機械) で、正当な起動を止める",
    ),
    _m(
        "k5  キー自身の既定値を見ない",
        "            found += [e for e in own if e and _norm(e) in on_path]\n",
        "            found += []\n",
        (_REGISTRY,),
        "stdlib が見つからず getpath がキー自身の既定値を足した起動で、その path を見逃す",
    ),
    _m(
        "k6  HKLM を見ない",
        "    for hive in (r.HKEY_CURRENT_USER, r.HKEY_LOCAL_MACHINE):\n",
        "    for hive in (r.HKEY_CURRENT_USER,):\n",
        (_REGISTRY,),
        "getpath が HKLM から足す path を見逃す",
    ),
    _m(
        "k7  読めない子キーで止まる",
        "                except OSError:  # 読めない子キーは飛ばして次へ (上位集合)\n"
        "                    continue\n",
        "                except OSError:  # 読めない子キーは飛ばして次へ (上位集合)\n"
        "                    break\n",
        (_REGISTRY,),
        "読めない子キーの後ろにある子キーの path を見逃す",
    ),
    _m(
        "k8  key の名前に winver を入れない",
        '    key_name = _REGISTRY_KEY.format(getattr(sys, "winver", ""))\n',
        '    key_name = _REGISTRY_KEY.format("")\n',
        (_REGISTRY,),
        "getpath が読む key (この interpreter の版) と違う key を読み、足された path を見逃す",
    ),
    _m(
        "k9  既定で実のレジストリを読まない",
        '    if reg is None and sys.platform != "win32":\n',
        "    if reg is None:\n",
        (_REGISTRY,),
        "Windows の起動で winreg を読まず、レジストリの検索パスを見逃す",
    ),
    _m(
        "k10 getpath と違う key を読む",
        '_REGISTRY_KEY: Final[str] = r"SOFTWARE\\Python\\PythonCore\\{}\\PythonPath"\n',
        '_REGISTRY_KEY: Final[str] = r"SOFTWARE\\Python\\PythonCore\\{}\\PythonPaths"\n',
        (_REGISTRY,),
        "getpath が読む key と違う key を読み、足された path を黙って見逃す (code-reviewer MEDIUM)",
    ),
    _m(
        "k11 起動の検査が渡されたレジストリの entry を使わない",
        "    if registry is None:\n",
        "    if True:\n",
        (_EXECUTED,),
        "注入した entry を捨てて実のレジストリを読む (検査の入力を test が決められない)",
    ),
    _m(
        "k12 -E/-I の起動でもレジストリを読む",
        "        registry = [] if sys.flags.ignore_environment else _registry_paths(search)\n",
        "        registry = _registry_paths(search)\n",
        (_EXECUTED,),
        "getpath がレジストリを読まない起動で、使われていない entry を数えて起動を誤って止める",
    ),
    # ============================ 拡張表記の比べ方・レジストリの値の扱い (Codex 6 回目 HIGH-1・LOW-3、decisions DH-2・DH-3)
    # 証拠は test の専用の assert の文に結ぶ (同じ test の別の assert に一致させない)
    _m(
        "e1  UNC の拡張表記を通常の表記に戻さない",
        r'    if resolved.startswith("\\\\?\\unc\\"):' "\n",
        "    if False:\n",
        (_ORDINARY,),
        "環境の中の UNC の dir を拡張表記で指す entry を、環境の外として起動を誤って止める",
        Witness(assert_stmt=True, text="extended-unc"),
    ),
    _m(
        "e2  ドライブの拡張表記を通常の表記に戻さない",
        r'    if resolved.startswith("\\\\?\\") and resolved[5:7] == ":\\":' "\n",
        "    if False:\n",
        (_ORDINARY,),
        "環境の中の dir を拡張表記で指す entry を、環境の外として起動を誤って止める",
        Witness(assert_stmt=True, text="extended-drive"),
    ),
    _m(
        "e3  ドライブでない名前空間の接頭辞も外す",
        r'    if resolved.startswith("\\\\?\\") and resolved[5:7] == ":\\":' "\n",
        r'    if resolved.startswith("\\\\?\\"):' "\n",
        (_ORDINARY,),
        "volume 等の名前空間の path を、別の path (相対) として比べる",
        Witness(assert_stmt=True, text="other-namespace-kept"),
    ),
    _m(
        "e4  所在を比べる前に拡張表記を揃えない",
        '    return _ordinary(resolved) if os.name == "nt" else resolved\n',
        "    return resolved\n",
        (_EXTENDED,),
        "realpath が接頭辞を保った環境の中の所在を、環境の外として起動を誤って止める",
        Witness(assert_stmt=True, text="extended-in-environment"),
    ),
    _m(
        "e5  子キーの値の空の entry を捨てる",
        '                    found += str(r.QueryValue(key, sub)).split(";")\n',
        '                    found += [e for e in str(r.QueryValue(key, sub)).split(";") if e]\n',
        (_REGISTRY,),
        "getpath が足し site が cwd にする空の entry (repo root) を見逃す",
        Witness(assert_stmt=True, text="subkey-entries-verbatim"),
    ),
    _m(
        "e6  子キーの値の entry の空白を削る",
        '                    found += str(r.QueryValue(key, sub)).split(";")\n',
        '                    found += [e.strip() for e in str(r.QueryValue(key, sub)).split(";")]\n',
        (_REGISTRY,),
        "getpath が削らない空白を削り、検索パスに入った entry と違う path を見る",
        Witness(assert_stmt=True, text="subkey-entries-verbatim"),
    ),
    _m(
        "e7  キー自身の既定値を正規化せずに sys.path と比べる",
        "            found += [e for e in own if e and _norm(e) in on_path]\n",
        "            found += [e for e in own if e and e in paths]\n",
        (_REGISTRY,),
        "site が絶対 path にした既定値の entry を、表記の違いで見逃す",
        Witness(assert_stmt=True, text="own-default-compared-normalized"),
    ),
)

# ---------------------------------------------------------------- meta-test

_TARGET = "generalization_probe_driver.py"
META_CASES: tuple[tuple[str, str, str, str, tuple[str, ...]], ...] = (
    (
        "予定表の事前検査 schedule_violations を [] に潰す",
        _TARGET,
        '    """予定表全体と meta を、呼び出しの前に凍結済みの検査に通す (DD-1)."""\n',
        '    """予定表全体と meta を、呼び出しの前に凍結済みの検査に通す (DD-1)."""\n'
        "    return []\n",
        (_BAD, _META, _FIXED),
    ),
    (
        "送る直前の照合 check_sent_body を素通りに潰す",
        _TARGET,
        '    """送信前の wire body を、plan の位置 index のキーで凍結値と凍結済みの構造の検査に照合する."""\n',
        '    """送信前の wire body を、plan の位置 index のキーで凍結値と凍結済みの構造の検査に照合する."""\n'
        "    return\n",
        (_VALUE, _POSITION, _OBSERVER, _SHIFTED),
    ),
    (
        "公開前の読み戻し publication_problems を [] に潰す",
        _TARGET,
        '    構造・meta・完全性だけを見る (label から計算する量は見ない)。\n    """\n',
        "    構造・meta・完全性だけを見る (label から計算する量は見ない)。\n"
        '    """\n'
        "    return []\n",
        (_PUB_CHECK, _PUB_READER, _PUB_META),
    ),
)


# ------------------------------------------------- 証拠の記録 (pytest の plugin、Codex 3 回目 MEDIUM-1・LOW-1)


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


def _assert_stmt(exc: BaseException) -> bool:
    """先頭の例外が、test_driver.py の ``assert`` 文 (pytest が書き換えたもの) から出た AssertionError か.

    autouse の封鎖の ``raise AssertionError(...)`` は偽 (Codex 再 review MEDIUM-1)。
    """
    if not isinstance(exc, AssertionError):
        return False
    frames = traceback.extract_tb(exc.__traceback__)
    if not frames:
        return False
    last = frames[-1]
    line = (last.line or "").lstrip()
    # assert の後は空白 (タブを含む)・括弧・行末のどれでもよい (Codex 4 回目 BL-2)
    return pathlib.PurePath(last.filename).name == _TEST_FILE and bool(
        _ASSERT_WORD.match(line)
    )


def pytest_exception_interact(node: object, call: object) -> None:
    """pytest の hook (``-p`` で harness を読み込ませたときだけ働く): 失敗ごとに証拠の記録を 1 行書く.

    記録 = 関数名・parametrize の id・段 (setup / call / teardown / collect)・先頭が assert 文か・例外の chain。
    出力の文字列を切らずに item と段を持つ (parametrize の id の中の ``] - `` でも崩れない、Codex 3 回目 LOW-1)。
    """
    out = os.environ.get(_WITNESS_ENV)
    excinfo = getattr(call, "excinfo", None)
    if not out or excinfo is None:
        return
    exc = excinfo.value
    _append(
        out,
        {
            "function": getattr(node, "originalname", None)
            or getattr(node, "name", ""),
            "param": getattr(getattr(node, "callspec", None), "id", None),
            "when": getattr(call, "when", None),
            "assert_stmt": _assert_stmt(exc),
            "chain": _chain(exc),
        },
    )


# 走りきった item の nodeid (``pytest_runtest_logfinish``。打ち切りを session の終わりの記録で数える、Codex 5 回目 MEDIUM-1)
_FINISHED_ITEMS: list[str] = []


def pytest_runtest_logfinish(nodeid: str) -> None:
    """item の setup・call・teardown が走りきるたびに呼ばれる pytest の hook (``-p`` のときだけ働く)."""
    _FINISHED_ITEMS.append(nodeid)


def pytest_sessionfinish(session: object, exitstatus: object) -> None:
    """session の終わりを 1 行書く pytest の hook (Codex 4 回目 MEDIUM-2・5 回目 MEDIUM-1).

    計測が最後まで走ったことと pytest の終了の種類を、証拠と同じ記録に残す: exitstatus・選ばれた item の数 (``items``)・
    走りきった item の数 (``ran``)・打ち切りの印 (``stopped`` = ``shouldstop`` か ``shouldfail``。``-x``・``--maxfail`` は
    exit 1 のまま途中で止める)。``status_of`` は、この記録がちょうど 1 つで、exitstatus 1・打ち切りなし・全 item が
    走りきった run だけで証拠を照合する (``finished_with_failures``)。
    """
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
    """各 run の env: 証拠の置き場所・空の bytecode の置き場所・書き込みの停止 (計測を変える env は外す).

    pyc は source の mtime (秒) と大きさで照合されるので、同じ長さの置換を同じ秒に書くと前の変異の pyc で走る
    (前タスクの decisions DI-3)。``PYTHONPYCACHEPREFIX`` は pyc の読み取り先も変える (``__pycache__`` を読まない)。
    run ごとに空の dir を渡し、書き込みも止めるので、読める pyc が無い (継いだ prefix も上書きする、Codex 4 回目 MEDIUM-1)。
    """
    out = {k: v for k, v in env.items() if k not in _DROPPED_ENV}
    out.update(
        {
            _WITNESS_ENV: str(witness),
            "PYTHONPYCACHEPREFIX": str(cache),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    return out


def _run_tests(
    env: dict[str, str], root: pathlib.Path = _REPO_ROOT
) -> tuple[int, set[str], bool, list[dict[str, Any]]]:
    """test_driver.py を、harness を plugin として読み込ませて実行する.

    返り値 = (exit code, 落ちた test (関数名), collection error, 証拠の記録)。
    """
    fd, name = tempfile.mkstemp(prefix="gp_driver_witness_", suffix=".jsonl")
    os.close(fd)
    witness = pathlib.Path(name)
    cache = pathlib.Path(tempfile.mkdtemp(prefix="gp_driver_pycache_"))
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
                "--deselect",
                _DESELECT,
                _TEST_REL,
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
        shutil.rmtree(cache, ignore_errors=True)  # 空のまま (書き込みを止めている)
    out = proc.stdout or ""
    failed = {str(r.get("function")) for r in records if r.get("when") in _PHASES}
    collect_error = (
        "ERROR collecting" in out
        or "Interrupted" in out
        or any(r.get("when") == "collect" for r in records)
    )
    return proc.returncode, failed, collect_error, records


# 公開の certification に、手元の path (OS のユーザー名を含む) とメモリの address を残さない (security-checker MEDIUM)。
# 照合は元の文で行い、要約に書くときだけ置き換える。先に実の tmp・home・ユーザー名を置き換え (空白入りの名前・
# 任意の置き場所も消える)、次に他の手元の形を汎用の規則で消す (Codex 4 回目 LOW-1)
_LOCAL_TEXT = (
    (
        # 名前は空白を含みうる (区切り文字が続くときだけ空白をまたいで延ばす。行の残りを消さない、code-reviewer LOW-8)
        re.compile(
            r"(?:[A-Za-z]:)?[\\/]+(?:Users|home)[\\/]+"
            r"(?:[^\\/'\"\n]*?[^\\/'\"\s](?=[\\/])|[^\\/'\"\s]+)",
            re.IGNORECASE,
        ),
        "<home>",
    ),
    (re.compile(r"/root(?=[\\/'\"\s]|$)"), "<home>"),
    (re.compile(r"pytest-of-[^\\/'\"\s]+"), "pytest-of-<user>"),
    # address = repr の `` at 0x`` の後の 8 桁以上 (64-bit の %p。function・code・frame・weakref の repr、pytest が
    # 後ろを省いたもの)。比較の数値 (0xdead・``at 0xdead,`` 等の短いもの) は残す (Codex 5 回目 LOW-1・code-reviewer HIGH)
    (re.compile(r"(?<= at )0x[0-9A-Fa-f]{8,}"), "0x?"),
    # pytest が途中を省いて `` at 0x`` が切れた address の残り (``...00195CF8963E0>``)
    (re.compile(r"(?<=\.\.\.)[0-9A-Fa-f]{6,}(?=>)"), "?"),
)
# 実の tmp・home の置き換えの終わり = path の要素が続かない (英数字・``_``・``.``・``-`` 以外、Codex 5 回目 LOW-1)
_PATH_END = r"(?![\w.-])"


def _tmp_dir() -> str:
    return tempfile.gettempdir()


def _home_dir() -> str:
    return str(pathlib.Path.home())


def _local_names() -> list[tuple[str, str]]:
    """実の tmp・home (区切りが slash・backslash・repr の二重の backslash の形) と、その置き換え先.

    長いものから並べる (tmp は home の下にある)。取れないもの (home を決められない等) は飛ばす (code-reviewer LOW-9)。
    """
    bs = chr(92)
    found: list[tuple[str, str]] = []
    for get, placeholder in ((_tmp_dir, "<tmp>"), (_home_dir, "<home>")):
        try:
            found.append((get(), placeholder))
        except (OSError, RuntimeError, KeyError):
            continue
    pairs: dict[str, str] = {}
    for path, placeholder in found:
        for form in (path, path.replace(bs, "/"), path.replace(bs, bs + bs)):
            if len(form) > 3:  # noqa: PLR2004 — ドライブだけ (``C:\``) の path は消さない
                pairs.setdefault(form, placeholder)
    return sorted(pairs.items(), key=lambda kv: len(kv[0]), reverse=True)


def _local_user() -> str:
    """OS のユーザー名 (3 文字未満・取れないときは空。短すぎる名前は普通の語と区別できない)."""
    try:
        user = getpass.getuser()
    except (OSError, KeyError, ImportError):
        return ""
    return user if len(user) >= 3 else ""  # noqa: PLR2004


def redact(text: str) -> str:
    """要約に書く文から、手元の tmp・home の path・ユーザー名・メモリの address を消す.

    ユーザー名は英数字の境界の内側だけ (``AppData`` の ``data`` を消さない、code-reviewer LOW-8)。実の tmp・home は、
    path の要素の終わり (区切り・引用符・空白・行末) で終わるときだけ (``/home/ann`` で ``/home/annette`` を割らない、
    Codex 5 回目 LOW-1。割らなかった home は汎用の規則が消す)。
    """
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
    return {
        "function": record.get("function"),
        "param": record.get("param"),
        "when": record.get("when"),
        "type": link.get("type"),
        "text": redact(str(link.get("text", "")))[:300],
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
        # 理由の文のある証拠で item を名指さないものは、parametrize でない test の記録だけに一致させる
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
                and (w.via is None or [_DRIVER_FILE, w.via] in frames)
            ):
                return _summary(record, link)
    return None


def finished_with_failures(code: int, records: list[dict[str, Any]]) -> bool:
    """Test の失敗 (exit 1) で pytest が最後まで走ったか.

    session の終わりの記録がちょうど 1 つで、exitstatus 1・打ち切りなし (``stopped`` が False)・選ばれた全 item が
    走りきった (``ran == items``)。INTERNALERROR (exit 3)・中断 (exit 2)・記録の書き込みの失敗の後に残った途中の記録
    (Codex 4 回目 MEDIUM-2) と、``-x``・``--maxfail`` で exit 1 のまま打ち切った run (Codex 5 回目 MEDIUM-1) を証拠に数えない。
    """
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
    """変異の判定 (3 通り): SURVIVED / 理由が違う (WRONG_REASON・COLLECTION_ERROR・TIMEOUT・ABNORMAL_EXIT・NO_FAILURE_RECORD) / KILLED.

    KILLED は、pytest が test の失敗 (exit 1) で最後まで走り (``finished_with_failures``)、期待 test の失敗の記録に、
    変異の証拠 (``Witness``) があるときだけ。理由の文の無い変異の証拠は、test の本体の assert 文 (fixture の setup の
    ERROR・assert 以外の例外・autouse の封鎖は数えない、code-reviewer MEDIUM-4・Codex MEDIUM-4・Codex 再 review
    MEDIUM-1)。理由の文のある変異は、その item・段の、同じ 1 つの例外で型・文・経由を照合する (別の parameter・段・
    例外を流用しない、Codex 3 回目 MEDIUM-1)。
    """
    if code == -1:
        return "TIMEOUT"
    if code == 0:
        return "SURVIVED"
    if collect:
        return "COLLECTION_ERROR"
    if not finished_with_failures(code, records):
        return "ABNORMAL_EXIT"
    if not failed:
        return "NO_FAILURE_RECORD"  # exit 1 で終わったが、失敗の記録が無い
    return (
        "KILLED"
        if witnessed(mut.witness, mut.expect, records) is not None
        else "WRONG_REASON"
    )


def anchor_problems(src: str) -> list[str]:
    """全変異と meta-test の置換前文字列が 1 回ずつ現れ、置換で内容が変わり、置換後も構文が通ること."""
    out = []
    cases = [(m.label, m.old, m.new) for m in MUTANTS]
    cases += [(f"meta: {c[0]}", c[2], c[3]) for c in META_CASES]
    for label, old, new in cases:
        n = src.count(old)
        if n != 1 or old == new:
            out.append(f"{label}: {'NO_OP' if old == new else f'ANCHOR x{n}'}")
            continue
        try:
            compile(src.replace(old, new, 1), _DRIVER_REL, "exec")
        except SyntaxError as exc:
            out.append(f"{label}: SYNTAX {exc}")
    labels = [m.label for m in MUTANTS] + [c[0] for c in META_CASES]
    if len(set(labels)) != len(labels):
        out.append("labels are not unique")
    return out


def _copy_tree() -> pathlib.Path:
    """複製ツリー (repo の外の一時 dir): scripts・test・実験 dir・pytest の設定."""
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="gp_driver_meta_"))
    skip = shutil.ignore_patterns("__pycache__")
    shutil.copytree(_REPO_ROOT / "scripts", tmp / "scripts", ignore=skip)
    (tmp / "tests").mkdir()
    for name in ("__init__.py", "conftest.py"):
        shutil.copy2(_REPO_ROOT / "tests" / name, tmp / "tests" / name)
    tests = "tests/test_generalization_probe"
    shutil.copytree(_REPO_ROOT / tests, tmp / tests, ignore=skip)
    shutil.copytree(
        _REPO_ROOT / _EXP_REL,
        tmp / _EXP_REL,
        ignore=shutil.ignore_patterns("sketch_logs", "sketch_run*", "pilot", "run"),
    )
    shutil.copy2(_REPO_ROOT / "pyproject.toml", tmp / "pyproject.toml")
    return tmp


def run_meta(env: dict[str, str]) -> list[dict[str, object]]:
    """複製ツリーで検査関数を no-op に潰し、依存する test が実際に落ちることを見る."""
    rows: list[dict[str, object]] = []
    tmp = _copy_tree()
    try:
        code, failed, collect_error, _ = _run_tests(env, tmp)
        if code != 0 or collect_error:
            msg = f"meta-test の対照 (無変異の複製) が緑でない: {sorted(failed)}"
            raise RuntimeError(msg)
        for label, target, old, new, expect in META_CASES:
            path = tmp / "scripts" / target
            original = path.read_bytes()
            src = original.decode("utf-8")
            if src.count(old) != 1:
                msg = f"meta anchor not unique: {label}"
                raise RuntimeError(msg)
            path.write_bytes(src.replace(old, new, 1).encode("utf-8"))
            try:
                code, failed, collect_error, records = _run_tests(env, tmp)
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
                    "status": "FAILED_AS_EXPECTED" if ok else "NOT_AS_EXPECTED",
                    "expected_all_of": sorted(expect),
                    "failed": sorted(failed),
                }
            )
            print(f"meta: {label:48s} {rows[-1]['status']}", flush=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return rows


def _sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:  # noqa: C901, PLR0912, PLR0915
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=pathlib.Path, default=None)
    ap.add_argument("--only", default=None, help="label の接頭辞で絞る (開発用)")
    ap.add_argument(
        "--anchors", action="store_true", help="置換前文字列の検査だけを行う"
    )
    args = ap.parse_args(argv)

    problems = anchor_problems(_DRIVER.read_text(encoding="utf-8"))
    if args.anchors or problems:
        for p in problems:
            print(p)
        n = len(MUTANTS) + len(META_CASES)
        print(f"anchors: {n - len(problems)} / {n} OK")
        return 1 if problems else 0

    env = dict(os.environ, PYTHONUTF8="1")
    original = _DRIVER.read_bytes()
    sha_driver = hashlib.sha256(original).hexdigest()
    sha_test = _sha(_REPO_ROOT / _TEST_REL)
    sha_harness = _sha(_REPO_ROOT / _HARNESS_REL)

    code, failed, _, _ = _run_tests(env)
    if code != 0:
        print(f"ERROR: 対照 (無変異) が緑でない: {sorted(failed)}")
        return 2
    meta = run_meta(env) if args.only is None else []

    mutants = [m for m in MUTANTS if args.only is None or m.label.startswith(args.only)]
    rows: list[dict[str, object]] = []
    try:
        for mut in mutants:
            _DRIVER.write_bytes(
                original.decode("utf-8").replace(mut.old, mut.new, 1).encode("utf-8")
            )
            try:
                code, failed, collect, records = _run_tests(env)
            except subprocess.TimeoutExpired:
                code, failed, collect, records = -1, set(), False, []
            finally:
                _DRIVER.write_bytes(original)
            status = status_of(mut, code, failed, records, collect=collect)
            evidence = witnessed(mut.witness, mut.expect, records)
            rows.append(
                {
                    "label": mut.label,
                    "status": status,
                    "expected_any_of": sorted(mut.expect),
                    "expected_witness": mut.witness.as_dict(),
                    "why": mut.why,
                    "failed": sorted(failed),
                    "witnessed_by": evidence,
                }
            )
            print(f"{mut.label:52s} {status}", flush=True)
    finally:
        _DRIVER.write_bytes(original)

    restored = _sha(_DRIVER) == sha_driver
    unchanged = (
        _sha(_REPO_ROOT / _TEST_REL) == sha_test
        and _sha(_REPO_ROOT / _HARNESS_REL) == sha_harness
    )
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
        if args.only is not None:
            print("ERROR: --only の結果は certification にしない")
            return 2
        if not (all_killed and restored and unchanged):
            print(
                "certification を書かない (全 KILLED・meta-test 成立・原状復帰のときだけ書く)"
            )
        else:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(
                json.dumps(
                    {
                        "target_sha256": {_DRIVER_REL: sha_driver},
                        "tests_sha256": {_TEST_REL: sha_test},
                        "harness_sha256": {_HARNESS_REL: sha_harness},
                        "meta_test": meta,
                        "mutants": rows,
                        "all_killed": all_killed,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            print(f"wrote {args.out}")
    if not restored:
        print("ERROR: 対象ファイルが原状復帰していない")
        return 2
    return (
        0 if all_killed or args.only is not None and not survived and not wrong else 1
    )


if __name__ == "__main__":
    sys.exit(main())
