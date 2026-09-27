#!/usr/bin/env python
"""閉ループ driver の変異試験 — driver・gate・記述報告の判定に関わる行を壊すと、意図した test が落ちるか.

次の 3 ファイルの行を 1 つずつ壊し、``tests/test_closed_loop_driver/`` を実行する。
* ``scripts/closed_loop_driver.py`` (閉ループの状態更新・送信前照合 (凍結 scorer の連鎖 replay)・呼び出し順・
  C0 gate・再送と raw=null・送った値の記録・meta の観測・来歴の異常・再開しない・起動の前提)
* ``scripts/closed_loop_run_gate.py`` (終了状態の gate)
* ``scripts/closed_loop_describe.py`` (§9 の抑制・§10 (iii)・決定性の文言・gate 不合格の run を読まない)
* ``scripts/closed_loop_judge.py`` (判定の単一入口: gate 不合格なら run.sh を呼ばない)

枠組みは v3 の ``scripts/skill_experience_driver_mutation_check.py`` と同じ (v3 の certification に結び付くので
変えず、本 harness を別に置く)。違いは 1 点: full run (2,808 呼び出しの mock) は session fixture で走るので、
変異で run が壊れると、依存する test は FAILED でなく ERROR (fixture の setup 失敗) として出る。そこで
``-rfE`` の FAILED 行と ``::`` を含む ERROR 行を「落ちた test」として数える (``::`` を含まない ERROR 行 =
collection error)。fixture の ERROR は理由を問わず出るので、fixture に依存する変異は、失敗行の理由に
``SentBodyMismatchError`` (送信前照合が拒否した) が出ていることも要求する (``Mutant.reason``、DR-7)。
各変異について

* test が落ちること (exit code 非 0) — 落ちなければ SURVIVED、
* 落ちた test に、その行を pin するために書いた test (期待集合) が含まれること — 含まれなければ
  WRONG_REASON、
* collection error で落ちていないこと、
* 置換前の文字列が対象ファイルに 1 回だけ現れ、置換で内容が変わること (no-op 変異を除く)

を確認する。先に無変異で全 test が緑であることを確認する。対象ファイルは必ず原状復帰する。
実行中は対象ファイルを編集しない・読ませない (Windows では中断時に finally が走らず変異が残りうる。
中断したら対象 3 ファイルの sha256 を確かめる)。certification は対象 3 ファイル・本 harness・test の
sha256 に結び付く。

実行 (repo root から)::

    uv run python scripts/closed_loop_driver_mutation_check.py --out <driver_mutation.json>
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
_SCRIPTS = _REPO_ROOT / "scripts"
_DRIVER = _SCRIPTS / "closed_loop_driver.py"
_DESCRIBE = _SCRIPTS / "closed_loop_describe.py"
_GATE = _SCRIPTS / "closed_loop_run_gate.py"
_JUDGE = _SCRIPTS / "closed_loop_judge.py"
_TARGETS = (_DRIVER, _DESCRIBE, _GATE, _JUDGE)
_TESTS = "tests/test_closed_loop_driver"
# commit 済み certification と現在のファイルの一致を見る test は、変異中は必ず落ちて生き残りを覆い隠す
# ので外す (凍結版 harness の test_committed_artifacts_are_consistent と同じ扱い)。
_DESELECT = f"{_TESTS}/test_driver.py::test_committed_driver_certification_is_current"
_TEST_TIMEOUT_S = 1800
_FAILED = re.compile(r"^(?:FAILED|ERROR) (\S+?::\S+?)(?:\[.*?\])?(?: - .*)?$")
_SECTION = re.compile(r"^_{3,} (?:ERROR at setup of )?(test_\w+)(?:\[.*?\])? _{3,}$")


@dataclass(frozen=True)
class Mutant:
    label: str
    old: str
    new: str
    expect: frozenset[str]
    target: pathlib.Path = _DRIVER
    reason: str | None = None  # 期待 test の失敗行に含まれるべき文字列


def _m(label: str, old: str, new: str, *expect: str) -> Mutant:
    return Mutant(label, old, new, frozenset(expect))


_REJECTED = "SentBodyMismatchError"


def _mr(label: str, old: str, new: str, *expect: str) -> Mutant:
    """送信前照合が拒否して run が落ちること (理由 = SentBodyMismatchError) を要求する変異."""
    return Mutant(label, old, new, frozenset(expect), reason=_REJECTED)


def _md(label: str, old: str, new: str, *expect: str) -> Mutant:
    return Mutant(label, old, new, frozenset(expect), _DESCRIBE)


def _mg(label: str, old: str, new: str, *expect: str) -> Mutant:
    return Mutant(label, old, new, frozenset(expect), _GATE)


def _mj(label: str, old: str, new: str, *expect: str) -> Mutant:
    return Mutant(label, old, new, frozenset(expect), _JUDGE)


# full run の fixture に依存する test (run が壊れると ERROR になる)
_RUN = (
    "test_run_follows_the_frozen_plan",
    "test_sent_bodies_follow_the_chain",
    "test_outputs_pass_the_frozen_scorer_checks",
)
_ADVANCE = "test_state_advances_from_the_written_record"
_CHAIN = "test_sent_bodies_follow_the_chain"
_REPLAY = "test_replay_resends_the_original_body_and_seed"
_WRONG_STATE = "test_check_rejects_a_body_from_the_wrong_state"
_VALUE = "test_check_sent_body_rejects_value_and_type"
_UNRESOLVED = "test_unresolved_transport_failure_records_null_and_stops"
_MANIFEST = "test_manifest_problems_require_manifest_ok"
_CERT = "test_driver_certification_detects_stale_or_failing"
_GIT = "test_launch_problems_check_git_tracking_and_head"
_ANOMALY = (
    "test_meta_is_written_from_sent_values_not_constants",
    "test_driver_change_during_the_run_aborts",
    "test_unexpected_response_model_aborts",
)
_FIELDS = "test_each_provenance_field_is_checked"
_ABORTED_RUN = "test_aborted_run_with_complete_records_is_stopped"
_SUPPRESS = "test_effects_are_suppressed_unless_the_verdict_is_valid"

_UPDATE = (
    "        state.states[chain] = bat.update(\n"
    "            state.states.get(chain, bat.EMPTY_STATE),\n"
    "            rec.world,\n"
    "            bat.loop_signature(rec.replicate, rec.step),\n"
    "            rec.parsed,\n"
    "        )\n"
)

MUTANTS: tuple[Mutant, ...] = (
    # ---- 閉ループの状態 (組み立て側)
    _m(
        "s1  状態の更新を削除",
        _UPDATE,
        "        state.states.setdefault(chain, bat.EMPTY_STATE)\n",
        _ADVANCE,
        *_RUN,
    ),
    _m(
        "s2  parsed でなく raw で更新",
        "            rec.parsed,\n        )\n    return rec",
        "            rec.raw,\n        )\n    return rec",
        _ADVANCE,
        _CHAIN,
    ),
    _m(
        "s3  更新の世界を固定",
        "            rec.world,\n            bat.loop_signature",
        "            bat.WORLDS[0],\n            bat.loop_signature",
        _ADVANCE,
        *_RUN,
    ),
    _m(
        "s4  更新の signature を t=0 に固定",
        "bat.loop_signature(rec.replicate, rec.step),",
        "bat.loop_signature(rec.replicate, 0),",
        _ADVANCE,
        *_RUN,
    ),
    _m(
        "s5  記録側で replicate を跨いで持ち越す",
        "        chain = (rec.world, rec.replicate)\n",
        "        chain = (rec.world, 0)\n",
        _ADVANCE,
        *_RUN,
    ),
    _mr(
        "s6  組み立て側で replicate を跨いで持ち越す",
        "    return (key.world, key.replicate)\n",
        "    return (key.world, 0)\n",
        *_RUN,
    ),
    _mr(
        "s7  probe を空状態で描く",
        "        st = state.states.get(_chain_of(key), bat.EMPTY_STATE)\n"
        "        msgs = bat.probe_messages(",
        "        st = bat.EMPTY_STATE\n        msgs = bat.probe_messages(",
        *_RUN,
    ),
    _mr(
        "s8  loop を空状態で描く",
        "        st = state.states.get(_chain_of(key), bat.EMPTY_STATE)\n"
        "        msgs = bat.loop_messages(",
        "        st = bat.EMPTY_STATE\n        msgs = bat.loop_messages(",
        *_RUN,
    ),
    _mr(
        "s9  replay を今の状態で描き直す",
        "        msgs = state.sent_messages[slot(key.of)]\n",
        "        msgs = (\n"
        "            bat.loop_messages(\n"
        "                state.states.get(_chain_of(key), bat.EMPTY_STATE),\n"
        "                key.world, key.replicate, key.step, sc.FROZEN_RENDERER,\n"
        "            )\n"
        "            if key.step is not None\n"
        "            else state.sent_messages[slot(key.of)]\n"
        "        )\n",
        _REPLAY,
        *_RUN,
    ),
    # ---- 送信前照合 (凍結 scorer の連鎖 replay を oracle に)
    _m(
        "o1  連鎖 replay の照合を削除",
        "        if chain:\n",
        "        if False:\n",
        _WRONG_STATE,
        "test_check_rejects_a_probe_before_its_loop",
    ),
    _mr(
        "o2  照合の文脈を捨てる",
        "sc.chain_violations([*expected.context, cand])",
        "sc.chain_violations([cand])",
        _WRONG_STATE,
        *_RUN,
    ),
    _mr(
        "o3  oracle の文脈に loop 行を入れない",
        "    rows = list(state.loops.get(_chain_of(target), []))\n",
        "    rows: list[sc.Record] = []\n",
        *_RUN,
    ),
    _mr(
        "o4  probe の replay に元の行を入れない",
        "        rows.append(state.by_slot[slot(target)])\n",
        "        pass\n",
        _REPLAY,
        *_RUN,
    ),
    _m(
        "o5  seed を照合しない",
        '        "seed": sc.expected_seed(want_key),\n',
        '        "seed": opts["seed"],\n',
        _VALUE,
        "test_mismatch_is_detected_before_the_inner_transport",
    ),
    _m(
        "o6  plan の位置を取り違える",
        "    want_key = _plan()[expected.index]\n",
        "    want_key = _plan()[expected.index % sc.n_c0()]\n",
        "test_check_uses_the_plan_position_not_the_driver_key",
    ),
    _m(
        "o7  照合を送信の後に",
        "            check_sent_body(body, self.expected)\n"
        "            self.sent.append(body)\n"
        "            self.last_content_type = None\n"
        "        response = await self.inner.handle_async_request(request)\n",
        "            self.sent.append(body)\n"
        "            self.last_content_type = None\n"
        "        response = await self.inner.handle_async_request(request)\n"
        "        if is_post:\n"
        "            check_sent_body(body, self.expected)\n",
        "test_mismatch_is_detected_before_the_inner_transport",
        "test_shifted_sampling_aborts_before_sending",
    ),
    _m(
        "o8  送信前照合を削除",
        "            check_sent_body(body, self.expected)\n",
        "            pass\n",
        "test_mismatch_is_detected_before_the_inner_transport",
        "test_shifted_sampling_aborts_before_sending",
    ),
    _m(
        "o9  型の厳密一致を外す",
        "return type(got) is type(want) and got == want",
        "return got == want",
        _VALUE,
    ),
    _m(
        "o10 body の余分な key を許す",
        "set(body) != BODY_KEYS",
        "not BODY_KEYS <= set(body)",
        "test_check_sent_body_rejects_extra_keys",
    ),
    _m(
        "o11 options の余分な key を許す",
        "set(opts) != OPTION_KEYS",
        "not OPTION_KEYS <= set(opts)",
        "test_check_sent_body_rejects_extra_keys",
    ),
    _m(
        "o12 /api/chat 以外の POST を通す",
        '            if request.url.path != "/api/chat":\n',
        "            if False:\n",
        "test_non_chat_post_is_refused_before_sending",
    ),
    _m(
        "o13 期待の無い送信を通す",
        "            if self.expected is None:\n",
        "            if False:\n",
        "test_chat_without_an_expected_call_is_refused",
    ),
    _m(
        "o14 model の照合を削除",
        '    if not _exact(body["model"], v2bat.MODEL):\n',
        "    if False:\n",
        _VALUE,
    ),
    _m(
        "o15 think の照合を削除",
        '    if not _exact(body["think"], v2bat.THINK):\n',
        "    if False:\n",
        _VALUE,
    ),
    _m(
        "o16 stream の照合を削除",
        '    if not _exact(body["stream"], False):\n',
        "    if False:\n",
        _VALUE,
    ),
    # ---- 順序
    _mr(
        "q1  状態側を C0 より先に",
        "stop = await run_calls(state, 0, plan[:n_c0])",
        "stop = await run_calls(state, 0, plan[n_c0:] + plan[:n_c0])",
        *_RUN,
    ),
    _m(
        "q2  replay を省く",
        "stop = await run_calls(state, n_c0, plan[n_c0:])",
        "stop = await run_calls(state, n_c0, plan[n_c0 : sc.n_main()])",
        "test_run_follows_the_frozen_plan",
        "test_every_call_is_sent",
    ),
    _mr(
        "q3  call_index を phase ごとに振り直す",
        "        index = start + offset\n",
        "        index = offset\n",
        *_RUN,
    ),
    _mr(
        "q4  状態側の開始位置を 0 に",
        "stop = await run_calls(state, n_c0, plan[n_c0:])",
        "stop = await run_calls(state, 0, plan[n_c0:])",
        *_RUN,
    ),
    # ---- C0 gate
    _m(
        "c1  C0 gate を >= に",
        "if c0_rate > sc.BOT_MAX:",
        "if c0_rate >= sc.BOT_MAX:",
        "test_c0_gate_at_the_limit_runs_the_state_side",
    ),
    _m(
        "c2  C0 gate を削除",
        "                if c0_rate > sc.BOT_MAX:\n",
        "                if False:\n",
        "test_c0_gate_blocks_the_state_side",
        "test_c0_gate_counts_the_last_replicate",
    ),
    _m(
        "c3  C0 ⊥ 率を r=0 だけで",
        "(bat.ARM_C0,), sc.FROZEN_R)[0]",
        "(bat.ARM_C0,), 1)[0]",
        "test_c0_gate_counts_the_last_replicate",
        "test_c0_gate_at_the_limit_runs_the_state_side",
    ),
    _m(
        "c4  C0 gate の対象を取り違える",
        "(bat.ARM_C0,), sc.FROZEN_R)[0]",
        "(bat.WORLDS[0],), sc.FROZEN_R)[0]",
        "test_c0_gate_blocks_the_state_side",
    ),
    _m(
        "c5  gate の停止の後も状態側を呼ぶ",
        "            if stop is None:\n"
        "                stop = await run_calls(state, n_c0, plan[n_c0:])\n",
        "            if True:\n"
        "                stop = await run_calls(state, n_c0, plan[n_c0:])\n",
        "test_c0_gate_blocks_the_state_side",
        "test_c0_gate_counts_the_last_replicate",
    ),
    # ---- 再送と raw=null
    _m(
        "t1  再送 3 → 2",
        "RESENDS: Final[int] = 3",
        "RESENDS: Final[int] = 2",
        "test_resend_with_the_same_seed_recovers",
        _UNRESOLVED,
    ),
    _m(
        "t2  再送 3 → 4",
        "RESENDS: Final[int] = 3",
        "RESENDS: Final[int] = 4",
        _UNRESOLVED,
    ),
    _m(
        "t3  再送で seed を変える",
        "options=dict(options)",
        'options={**options, "seed": options["seed"] + attempt}',
        "test_resend_with_the_same_seed_recovers",
    ),
    _m(
        "t4  再送が尽きても続行",
        "        if raw is None:\n            return REASON_TRANSPORT\n",
        "        if False:\n            return REASON_TRANSPORT\n",
        _UNRESOLVED,
    ),
    _m(
        "t5  再送が尽きたら null でなく空文字",
        "    return None, state.observer.sent[-1]",
        '    return "", state.observer.sent[-1]',
        _UNRESOLVED,
    ),
    _m(
        "t6  transport 以外の例外も再送",
        "except OllamaUnavailableError as exc:",
        "except Exception as exc:",
        "test_other_exceptions_abort_without_a_null_row",
        "test_shifted_sampling_aborts_before_sending",
    ),
    _m(
        "t7  非文字列 content を成功扱い",
        '            if ctype != "str":\n',
        "            if False:\n",
        "test_null_content_is_a_transport_failure_not_bottom",
    ),
    _m(
        "t8  非 transport 例外を握りつぶす",
        '        error = f"{type(exc).__name__}: {exc}"\n        raise\n',
        '        error = f"{type(exc).__name__}: {exc}"\n',
        "test_other_exceptions_abort_without_a_null_row",
    ),
    # ---- 記録
    _m(
        "r1  raw を strip して記録",
        "            raw=raw,\n",
        "            raw=None if raw is None else raw.strip(),\n",
        "test_raw_is_recorded_verbatim",
    ),
    _m(
        "r2  parsed を parse せずに記録",
        "            parsed=None if raw is None else sc.parse_choice(raw),\n",
        "            parsed=raw,\n",
        "test_raw_is_recorded_verbatim",
        *_RUN,
    ),
    _m(
        "r3  seed を定数から記録",
        '            seed=body["options"]["seed"],\n',
        "            seed=sc.expected_seed(key),\n",
        "test_seed_and_prompt_are_recorded_from_the_sent_body",
    ),
    _m(
        "r4  記録を ensure_ascii=False で書く",
        "    line = json.dumps(obj, ensure_ascii=True, sort_keys=True)",
        "    line = json.dumps(obj, ensure_ascii=False, sort_keys=True)",
        "test_line_separators_in_raw_do_not_split_a_record",
    ),
    # ---- 終了時の preflight
    _m(
        "f1  終了時の preflight を再送しない",
        "    for attempt in range(1 + RESENDS):\n        try:\n            return (await",
        "    for attempt in range(1):\n        try:\n            return (await",
        "test_final_preflight_is_resent",
    ),
    _m(
        "f2  transport 失敗の後の preflight 失敗を aborted に",
        "            if stop != REASON_TRANSPORT:\n",
        "            if True:\n",
        "test_final_preflight_failure_keeps_a_transport_failure",
    ),
    _m(
        "f3  終了時の preflight 失敗を aborted にしない",
        "            if stop != REASON_TRANSPORT:\n",
        "            if False:\n",
        "test_final_preflight_failure_aborts_a_finished_run",
    ),
    # ---- 運用の保護
    _m(
        "p0  main が run dir / endpoint を受け取る",
        "    ap.parse_args(argv)\n    problems = launch_problems()",
        "    ap.parse_known_args(argv)\n    problems = launch_problems()",
        "test_main_takes_no_run_dir_or_endpoint",
    ),
    _m(
        "p1  非空の run dir を拒否しない",
        "    if run_dir.exists() and any(run_dir.iterdir()):\n",
        "    if False:\n",
        "test_run_refuses_a_non_empty_run_dir",
    ),
    _m(
        "p2  preflight を飛ばす",
        "        env = await preflight(http)\n",
        '        env = {"ollama_version": "x", "model_digest": "x"}\n',
        "test_preflight_failure_writes_nothing",
    ),
    _m(
        "p3  meta.json を実走中に書かない",
        "        _ensure_meta(state)\n",
        "",
        "test_meta_is_on_disk_while_the_run_is_going",
    ),
    _m(
        "p4  meta を request_meta() から写す",
        "        meta_of(state.observer.sent[0]),\n",
        "        sc.request_meta(),\n",
        "test_meta_is_written_from_sent_values_not_constants",
    ),
    _m(
        "p5  model digest の変化を見ない",
        '        elif digest_end != env["model_digest"]:\n',
        "        elif False:\n",
        "test_model_digest_change_aborts",
    ),
    # ---- 起動の前提
    _m(
        "l1  manifest 検査を起動条件に入れない",
        "    problems.extend(manifest_problems())\n",
        "",
        "test_launch_problems_include_manifest_and_certification",
    ),
    _m(
        "l2  manifest の exit code だけを見る",
        'if proc.returncode != 0 or not lines or lines[-1] != "MANIFEST OK":',
        "if proc.returncode != 0:",
        _MANIFEST,
    ),
    _m(
        "l3  manifest の末尾行だけを見る",
        'if proc.returncode != 0 or not lines or lines[-1] != "MANIFEST OK":',
        'if not lines or lines[-1] != "MANIFEST OK":',
        _MANIFEST,
    ),
    _m(
        "l4  manifest の OK を末尾以外でも受ける",
        'lines[-1] != "MANIFEST OK"',
        '"MANIFEST OK" not in lines',
        _MANIFEST,
    ),
    _m(
        "l5  起動拒否を外す",
        "    if problems:\n        for p in problems:\n",
        "    if False:\n        for p in problems:\n",
        "test_main_refuses_to_launch_without_touching_the_run_dir",
    ),
    _m(
        "l6  未合格の certification を通す",
        'problems = [] if all_killed else ["driver certification: not all KILLED"]',
        "problems: list[str] = []",
        _CERT,
    ),
    _m(
        "l7  certification の sha256 を照合しない",
        "    if recorded != certified_files():\n",
        "    if False:\n",
        _CERT,
    ),
    _m(
        "l8  PINNED の追跡を見ない",
        '        if _git("ls-files", "--error-unmatch", rel) is None:\n',
        "        if False:\n",
        _GIT,
    ),
    _m(
        "l9  PINNED と HEAD の差分を見ない",
        '    if _git("diff", "--quiet", "HEAD", "--", *PINNED) is None:\n',
        "    if False:\n",
        _GIT,
    ),
    # ---- 来歴の異常は aborted
    _m(
        "a1  要求条件の不一致を aborted にしない",
        "        if observer.sent and meta_ok is not True:\n",
        "        if False:\n",
        _ANOMALY[0],
    ),
    _m(
        "a2  実走中の driver 変更を aborted にしない",
        "        if driver_sha_end != driver_sha_start:\n",
        "        if False:\n",
        _ANOMALY[1],
    ),
    _m(
        "a3  想定外の応答 model を aborted にしない",
        "        if models - {v2bat.MODEL}:\n",
        "        if False:\n",
        _ANOMALY[2],
    ),
    _m(
        "a4  来歴の異常を終了理由に反映しない",
        "        if anomalies and reason in (REASON_COMPLETED, REASON_C0_GATE):\n",
        "        if False:\n",
        *_ANOMALY,
    ),
    # ---- 終了状態の gate
    _mg(
        "g1  exit_reason を見ない",
        'if prov.get("exit_reason") not in ACCEPTED_EXIT:',
        "if False:",
        _ABORTED_RUN,
        _FIELDS,
    ),
    _mg(
        "g2  aborted を受け入れる",
        'frozenset({"completed", "c0_gate"})',
        'frozenset({"completed", "c0_gate", "aborted"})',
        _ABORTED_RUN,
    ),
    _mg(
        "g3  meta 不明 (None) を通す",
        'if prov.get("meta_matches_frozen") is not True:',
        'if prov.get("meta_matches_frozen") is False:',
        _FIELDS,
    ),
    _mg(
        "g4  driver sha の欠落を通す",
        "    if not start or start != end:\n",
        "    if start != end:\n",
        _FIELDS,
    ),
    _mg(
        "g5  model digest を見ない",
        "    if not d_start or d_start != d_end:\n",
        "    if False:\n",
        _FIELDS,
    ),
    _mg(
        "g6  応答 model の空を通す",
        'if prov.get("response_models") != [v2bat.MODEL]:',
        'if not set(prov.get("response_models") or []) <= {v2bat.MODEL}:',
        _FIELDS,
    ),
    _mg(
        "g7  n_records を照合しない",
        '    if prov.get("n_records") != n_lines:\n',
        "    if False:\n",
        _FIELDS,
    ),
    _mg(
        "g8  終了理由ごとの件数を見ない",
        "    if want is not None and n_lines != want:\n",
        "    if False:\n",
        "test_truncated_records_are_stopped",
        "test_c0_gate_needs_exactly_the_c0_rows",
    ),
    _mg(
        "g9  c0_gate の件数を plan 全件に",
        "        return sc.n_c0()\n",
        "        return len(sc.frozen_plan())\n",
        "test_c0_gate_stop_passes_the_gate",
        "test_c0_gate_needs_exactly_the_c0_rows",
    ),
    _mg(
        "g10 raw=null の行を見ない",
        "    if n_null:\n",
        "    if False:\n",
        "test_null_rows_are_stopped",
    ),
    _mg(
        "g11 空行も行数に数える",
        "    lines = [line for line in text.splitlines() if line.strip()]\n",
        "    lines = text.split(chr(10))\n",
        "test_blank_lines_are_not_counted",
        "test_completed_run_passes_the_gate",
    ),
    _mg(
        "g13 endpoint を見ない",
        '    if prov.get("endpoint") != EXPECTED_ENDPOINT:\n',
        "    if False:\n",
        _FIELDS,
    ),
    _mg(
        "g12 不合格でも exit 0",
        "    return 0 if not problems else 1",
        "    return 0",
        _ABORTED_RUN,
    ),
    # ---- 記述報告 (§9 の抑制・§10)
    _md(
        "d1  効果を常に出す",
        "    ok = status == sc.STATUS_COMPUTED and verdict in EFFECT_VERDICTS\n",
        "    ok = True\n",
        _SUPPRESS,
        "test_run_gate_problems_suppress_every_effect",
    ),
    _md(
        "d2  INVALID_TASK_BATTERY でも効果を出す",
        "    {VERDICT_PASS, VERDICT_ABSENT, VERDICT_UNDERPOWERED}\n",
        '    {VERDICT_PASS, VERDICT_ABSENT, VERDICT_UNDERPOWERED, "INVALID_TASK_BATTERY"}\n',
        _SUPPRESS,
    ),
    _md(
        "d3  gate の不合格を無視",
        "    if gate_problems:  # driver",
        "    if False:  # driver",
        "test_run_gate_problems_suppress_every_effect",
    ),
    _md(
        "d5  records と results の結び付けを見ない",
        '    if (results.get("inputs") or {}).get("records_sha256") != records_sha:\n',
        "    if False:\n",
        "test_main_refuses_results_of_other_records",
    ),
    _md(
        "d6  gate 不合格でも claim_branch を残す",
        '"claim_branch": results.get("claim_branch") if not gate_problems else None,',
        '"claim_branch": results.get("claim_branch"),',
        "test_run_gate_problems_suppress_every_effect",
    ),
    _md(
        "d7  INCONCLUSIVE の注記を削除",
        "        if ok and verdict == VERDICT_UNDERPOWERED\n",
        "        if False\n",
        "test_inconclusive_keeps_numbers_with_a_note",
    ),
    _md(
        "d8  決定性の文言を格下げしない",
        'return EXACT if det.get("exact_cancellation") is True else EXPECTED',
        "return EXACT",
        "test_cancellation_wording_is_downgraded_below_one",
    ),
    _md(
        "d9  §10 (iii) の key から seed を落とす",
        "(x.replicate, x.probe_id, x.k, x.seed, x.prompt_sha256): x\n"
        "        for x in records\n"
        "        if x.phase == bat.PHASE_C0 and x.raw is not None\n"
        "    }\n"
        "    pairs = [\n"
        "        (mine[key], s)\n"
        "        for s in previous\n"
        "        if s.arm == bat.ARM_C0 and s.raw is not None\n"
        "        if (key := (s.replicate, s.probe_id, s.k, s.seed, s.prompt_sha256))",
        "(x.replicate, x.probe_id, x.k, x.prompt_sha256): x\n"
        "        for x in records\n"
        "        if x.phase == bat.PHASE_C0 and x.raw is not None\n"
        "    }\n"
        "    pairs = [\n"
        "        (mine[key], s)\n"
        "        for s in previous\n"
        "        if s.arm == bat.ARM_C0 and s.raw is not None\n"
        "        if (key := (s.replicate, s.probe_id, s.k, s.prompt_sha256))",
        "test_c0_agreement_counts_raw_and_parsed_separately",
        "test_c0_agreement_uses_the_same_keys_as_v2_and_v3",
    ),
    _md(
        "d10 位置の ⊥ と Ω 外を混ぜる",
        '            positions["bot"] += 1',
        '            positions["oov"] += 1',
        "test_c0_positions_separate_bottom_and_out_of_omega",
    ),
    _md(
        "d11 gate 不合格の run も記述する",
        "    if gate_problems:  # DR-6",
        "    if False:  # DR-6",
        "test_main_refuses_a_run_that_fails_the_gate",
    ),
    _md(
        "d12 records と run dir の結び付けを見ない",
        '    if args.records.resolve() != (args.run_dir / "records.jsonl").resolve():\n',
        "    if False:\n",
        "test_main_requires_the_records_of_the_run_dir",
    ),
    _md(
        "d13 読めない過去記録を 0 件に畳む",
        "            out[name] = None\n",
        "            out[name] = []\n",
        "test_unreadable_previous_records_are_an_error_not_zero",
    ),
    # ---- 判定の単一入口
    _mj(
        "j1  gate 不合格でも run.sh を呼ぶ",
        "    if problems:\n        for p in problems:\n",
        "    if False:\n        for p in problems:\n",
        "test_gate_failure_does_not_call_run_sh",
    ),
    _mj(
        "j2  run.sh の結果を見ない",
        "    if not run_sh_ok(code, output):\n",
        "    if False:\n",
        "test_run_sh_must_end_byte_identical",
    ),
    _mj(
        "j3  byte 一致を末尾以外でも受ける",
        "RUN_SH_OK in lines[-1]",
        "any(RUN_SH_OK in x for x in lines)",
        "test_run_sh_ok_reads_the_last_line",
    ),
    _mj(
        "j4  run.sh の exit code を見ない",
        "    return code == 0 and bool(lines) and",
        "    return bool(lines) and",
        "test_run_sh_ok_reads_the_last_line",
        "test_run_sh_must_end_byte_identical",
    ),
    _mj(
        "j5  Windows で WSL の bash を使う",
        '    if sys.platform == "win32" and _GIT_BASH.exists():\n',
        "    if False:\n",
        "test_bash_is_not_wsl_on_windows",
    ),
)


def _run_tests(env: dict[str, str]) -> tuple[int, dict[str, str], bool]:
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
        timeout=_TEST_TIMEOUT_S,
    )
    out = proc.stdout or ""
    # traceback 節 (``___ ERROR at setup of test_x ___`` / ``___ test_x ___``) を test 名ごとに集める。
    # fixture の ERROR の要約行には例外名が出ないので、理由はここで照合する。
    sections: dict[str, str] = {}
    current: str | None = None
    for line in out.splitlines():
        if h := _SECTION.match(line):
            current = h.group(1)
            sections[current] = sections.get(current, "")
        elif current is not None:
            sections[current] += line + "\n"
    failed: dict[str, str] = {}  # test 名 → 要約行 + traceback 節 (理由を含む)
    for line in out.splitlines():
        if m := _FAILED.match(line):
            name = m.group(1).split("::")[-1]
            failed[name] = failed.get(name, "") + line + "\n" + sections.get(name, "")
    collect_error = "ERROR collecting" in out or "Interrupted" in out
    return proc.returncode, failed, collect_error


def _raised(reason: str, hits: list[str]) -> bool:
    """理由が traceback の例外行 (``E`` で始まる行) に出ているか (ソース行の偶然の一致を拾わない)."""
    return any(
        line.startswith("E ") and reason in line
        for text in hits
        for line in text.splitlines()
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=pathlib.Path, default=None)
    ap.add_argument("--only", default=None, help="label の接頭辞で絞る (開発用)")
    args = ap.parse_args(argv)

    env = dict(os.environ, PYTHONUTF8="1")
    originals = {t: t.read_bytes() for t in _TARGETS}
    sha_before = {t.name: hashlib.sha256(b).hexdigest() for t, b in originals.items()}
    harness = pathlib.Path(__file__).resolve()
    sha_before[harness.name] = hashlib.sha256(harness.read_bytes()).hexdigest()

    tests_sha = {
        f"tests/{p.name}": hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((_REPO_ROOT / _TESTS).glob("*.py"))
    }
    mutants = [m for m in MUTANTS if args.only is None or m.label.startswith(args.only)]
    if args.only is None:
        code, failed, _ = _run_tests(env)
        if code != 0:
            print(f"ERROR: baseline (無変異) が緑でない: {sorted(failed)}")
            return 2

    rows: list[dict[str, object]] = []
    try:
        for mut in mutants:
            original = originals[mut.target]
            src = original.decode("utf-8")
            n = src.count(mut.old)
            if n != 1 or mut.old == mut.new:
                status = "NO_OP" if mut.old == mut.new else f"ANCHOR x{n}"
                rows.append({"label": mut.label, "status": status})
                print(f"{mut.label:44s} {status}", flush=True)
                continue
            mut.target.write_bytes(src.replace(mut.old, mut.new, 1).encode("utf-8"))
            try:
                code, failed, collect_error = _run_tests(env)
            except subprocess.TimeoutExpired:
                code, failed, collect_error = -1, {}, False
            mut.target.write_bytes(original)
            hits = [failed[t] for t in mut.expect if t in failed]
            if code == -1:
                status = "TIMEOUT"
            elif code == 0:
                status = "SURVIVED"
            elif collect_error or not failed:
                status = "COLLECTION_ERROR"
            elif hits and (mut.reason is None or _raised(mut.reason, hits)):
                status = "KILLED"
            else:
                status = "WRONG_REASON"
            rows.append(
                {
                    "label": mut.label,
                    "status": status,
                    "expected_any_of": sorted(mut.expect),
                    "expected_reason": mut.reason,
                    "failed": sorted(failed),
                }
            )
            print(f"{mut.label:44s} {status}", flush=True)
    finally:
        for t, b in originals.items():
            t.write_bytes(b)

    restored = all(
        hashlib.sha256(t.read_bytes()).hexdigest() == sha_before[t.name]
        for t in _TARGETS
    )
    bad = [r for r in rows if r["status"] != "KILLED"]
    for r in rows:
        mark = "" if r["status"] == "KILLED" else "  <-- !!"
        print(
            f"{r['label']:44s} {r['status']:16s} {len(r.get('failed', []))} failed{mark}"
        )
    print(f"source restored (sha256 match): {restored}")
    print(f"not KILLED: {len(bad)} / {len(rows)}")
    if args.out is not None and args.only is None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(
                {
                    "target_sha256": {**sha_before, **tests_sha},
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
