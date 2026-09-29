#!/usr/bin/env python
"""閉ループ v5 driver の変異試験 — driver の判定に関わる行を壊すと、意図した test が落ちるか.

``scripts/closed_loop_v5_driver.py`` の行を 1 つずつ壊し、``tests/test_closed_loop_v5_driver/`` を実行する。
壊す行は次の区分に属する。
* 閉ループの状態更新
* 送信前照合 (凍結 scorer の連鎖 replay)
* 呼び出し順
* 再送と raw=null
* 記録
* 公開 (成功したときだけ・二相・凍結 validate・公開時の manifest)
* 終了時の preflight
* 運用の保護
* 起動の前提
* 来歴の異常

枠組みは v4 の ``scripts/closed_loop_driver_mutation_check.py`` と同じ。v4 の certification に結び付くので
変えず、本 harness を別に置く。
- full run (3,072 呼び出しの mock) は session fixture で走る。変異で run が壊れると、依存する test は FAILED で
  なく ERROR (fixture の setup 失敗) として出る。
- そこで ``-rfE`` の FAILED 行と ``::`` を含む ERROR 行を「落ちた test」として数える (``::`` を含まない ERROR 行 =
  collection error)。
- fixture の ERROR は理由を問わず出る。そこで fixture に依存する変異と、公開に関わる変異 (Codex HIGH-1) には、
  失敗の理由の文字列も要求する (``Mutant.reason``、例外行 ``E `` に現れること)。

各変異について、次を確認する。
* test が落ちること (exit code 非 0)。落ちなければ SURVIVED。
* 落ちた test に、その行を pin するために書いた test (期待集合) が含まれること。含まれなければ WRONG_REASON。
* collection error で落ちていないこと。
* 置換前の文字列が対象ファイルに 1 回だけ現れ、置換で内容が変わること (no-op 変異を除く)。

先に、無変異で全 test が緑であることを確認する。対象ファイルは必ず原状復帰する。
実行中は対象ファイルを編集しない・読ませない。Windows では中断時に finally が走らず、変異が残りうる。
中断したら ``--anchors`` で、全変異の置換前文字列が各 1 回ずつ現れることを確かめる。
certification は対象・本 harness・test の sha256 に結び付く。

登録から外した変異 (等価変異、decisions.md に記録):
* absorb の「1 行が 1 記録に読み戻せる」検査を外す。行が割れると、凍結 reader (``load_records``) がこの検査より
  先に ``RecordError`` (not JSON) を出すので等価 (``ensure_ascii`` を外す変異 r5 が、読み戻しの ``RecordError`` で
  止まることを理由照合で要求して pin する)。
* 公開名が既にあるときの上書き拒否を外す。Windows の ``Path.rename`` は既存の宛先で ``FileExistsError`` を出すので、
  この harness が走る Windows では等価。

実行 (repo root から)::

    uv run python scripts/closed_loop_v5_driver_mutation_check.py --out <driver_mutation.json>
    uv run python scripts/closed_loop_v5_driver_mutation_check.py --anchors   # 置換前文字列の検査だけ
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
_DRIVER = _REPO_ROOT / "scripts" / "closed_loop_v5_driver.py"
_TARGETS = (_DRIVER,)
_TESTS = "tests/test_closed_loop_v5_driver"
# commit 済み certification と現在のファイルの一致を見る test は、変異中は必ず落ちて生き残りを覆い隠す
# ので外す (v4 harness と同じ扱い)。
_DESELECT = f"{_TESTS}/test_launch.py::test_committed_driver_certification_is_current"
_TEST_TIMEOUT_S = 1800
_FAILED = re.compile(r"^(?:FAILED|ERROR) (\S+?::\S+?)(?:\[.*?\])?(?: - .*)?$")
# 節の見出しの下線は、名前が長い (parametrize の id が長い) と 1 本まで縮む
_SECTION = re.compile(r"^_+ (?:ERROR at setup of )?(test_\w+)(?:\[.*?\])? _+$")


@dataclass(frozen=True)
class Mutant:
    label: str
    old: str
    new: str
    expect: frozenset[str]
    reason: str | None = None  # 期待 test の失敗行 (例外行 ``E ``) に含まれるべき文字列


def _m(label: str, old: str, new: str, *expect: str) -> Mutant:
    return Mutant(label, old, new, frozenset(expect))


_REJECTED = "SentBodyMismatchError"
_PUBLISHED = "records.jsonl was published"


def _mr(label: str, old: str, new: str, *expect: str) -> Mutant:
    """送信前照合が拒否して run が落ちること (理由 = SentBodyMismatchError) を要求する変異."""
    return Mutant(label, old, new, frozenset(expect), reason=_REJECTED)


def _mp(label: str, old: str, new: str, *expect: str) -> Mutant:
    """公開してはならない run が公開されたこと (理由 = 公開名の存在の assert) で落ちることを要求する変異."""
    return Mutant(label, old, new, frozenset(expect), reason=_PUBLISHED)


# full run の fixture に依存する test (run が壊れると ERROR になる)
_RUN = (
    "test_run_follows_the_frozen_plan",
    "test_sent_bodies_follow_the_chain",
    "test_published_records_are_computed_by_the_frozen_scorer",
)
_ADVANCE = "test_state_advances_from_the_written_record"
_CHAIN = "test_sent_bodies_follow_the_chain"
_WRONG_STATE = "test_check_rejects_a_body_from_the_wrong_state"
_OTHER_AXIS = "test_check_rejects_the_other_axis_body"
_SHARED = "test_check_rejects_state_shared_across_axes"
_VALUE = "test_check_sent_body_rejects_value_and_type"
_BEFORE_SEND = "test_mismatch_is_detected_before_the_inner_transport"
_UNRESOLVED = "test_unresolved_transport_failure_records_null_and_stops"
_RESEND = "test_resend_with_the_same_seed_recovers"
_INCOMPLETE = "test_incomplete_run_is_not_published"
_TWO_PHASE = "test_publication_is_two_phase"
_PUB_FAIL = "test_publication_failure_is_recorded_as_aborted"
_FROZEN_STATUS = "test_frozen_status_reads_the_partial_like_the_judge"
_MANIFEST_PUB = "test_manifest_failure_at_publication_blocks_it"
_META_SENT = "test_meta_is_written_from_sent_values_not_constants"
_META_FILE = "test_meta_file_changed_during_the_run_is_an_anomaly"
_PINNED = "test_pinned_file_change_during_the_run_aborts"
_MODEL = "test_unexpected_response_model_aborts"
_MODEL_FULL = "test_complete_run_with_an_anomaly_is_not_published"
_DIGEST = "test_model_digest_change_aborts"
_FINAL_ABORT = "test_final_preflight_failure_aborts_a_finished_run"
_MANIFEST = "test_manifest_problems_require_manifest_ok"
_CERT = "test_driver_certification_detects_stale_or_failing"
_GIT = "test_launch_problems_check_git_tracking_and_head"

_UPDATE = (
    "    state.states[chain] = v4.update(\n"
    "        state.states.get(chain, v4.EMPTY_STATE),\n"
    "        rec.world,\n"
    "        v4.loop_signature(rec.replicate, rec.step),\n"
    "        rec.parsed,\n"
    "    )\n"
)
_ABSORB_CHAIN = "    chain = (rec.axis, rec.world, rec.replicate)\n"
_RENDER = "bat.loop_messages(st, key.world, key.replicate, key.step, key.axis)"

MUTANTS: tuple[Mutant, ...] = (
    # ---- 閉ループの状態 (組み立て側)
    _mr(
        "s1  状態の更新を削除",
        _UPDATE,
        "    state.states.setdefault(chain, v4.EMPTY_STATE)\n",
        _ADVANCE,
        *_RUN,
    ),
    _m(
        "s2  parsed でなく raw で更新",
        "        rec.parsed,\n    )\n    return rec",
        "        rec.raw,\n    )\n    return rec",
        _ADVANCE,
        _CHAIN,
    ),
    _mr(
        "s3  更新の世界を固定",
        "        rec.world,\n        v4.loop_signature",
        "        v4.WORLDS[0],\n        v4.loop_signature",
        _ADVANCE,
        *_RUN,
    ),
    _mr(
        "s4  更新の signature を t=0 に固定",
        "v4.loop_signature(rec.replicate, rec.step),",
        "v4.loop_signature(rec.replicate, 0),",
        *_RUN,
    ),
    _mr(
        "s5  記録側で軸を跨いで状態を共有",
        _ABSORB_CHAIN,
        "    chain = (bat.AXES[0], rec.world, rec.replicate)\n",
        _ADVANCE,
        *_RUN,
    ),
    _mr(
        "s6  組み立て側で軸を跨いで状態を共有",
        "    return (key.axis, key.world, key.replicate)\n",
        "    return (bat.AXES[0], key.world, key.replicate)\n",
        *_RUN,
    ),
    _mr(
        "s7  記録側で replicate を跨いで持ち越す",
        _ABSORB_CHAIN,
        "    chain = (rec.axis, rec.world, bat.PILOT_R[0])\n",
        _ADVANCE,
        *_RUN,
    ),
    _mr(
        "s8  空状態で描く",
        "    st = state.states.get(_chain_of(key), v4.EMPTY_STATE)\n",
        "    st = v4.EMPTY_STATE\n",
        *_RUN,
    ),
    _mr(
        "s9  別の軸の renderer で描く",
        _RENDER,
        "bat.loop_messages(st, key.world, key.replicate, key.step, bat.AXES[0])",
        *_RUN,
    ),
    _mr(
        "s10 t=0 の状況で描く",
        _RENDER,
        "bat.loop_messages(st, key.world, key.replicate, 0, key.axis)",
        *_RUN,
    ),
    # ---- 送信前照合 (凍結 scorer の連鎖 replay を oracle に)
    _m(
        "o1  連鎖 replay の照合を削除",
        "        if chain:\n",
        "        if False:\n",
        _WRONG_STATE,
        _OTHER_AXIS,
        _SHARED,
    ),
    _mr(
        "o2  照合の文脈を捨てる",
        "ps.chain_violations([*expected.context, cand])",
        "ps.chain_violations([cand])",
        _WRONG_STATE,
        *_RUN,
    ),
    _mr(
        "o3  oracle の文脈を空に",
        "    return tuple(state.chains.get(_chain_of(key), []))\n",
        "    return ()\n",
        *_RUN,
    ),
    _mr(
        "o4  oracle の文脈を別の軸から",
        "    return tuple(state.chains.get(_chain_of(key), []))\n",
        "    return tuple(state.chains.get((bat.AXES[0], key.world, key.replicate), []))\n",
        *_RUN,
    ),
    _m(
        "o5  seed を照合しない",
        '        "seed": bat.pilot_seed(want_key.replicate, want_key.step),\n',
        '        "seed": opts["seed"],\n',
        _VALUE,
        _BEFORE_SEND,
    ),
    _mr(
        "o6  照合の seed を t=0 で",
        "bat.pilot_seed(want_key.replicate, want_key.step)",
        "bat.pilot_seed(want_key.replicate, 0)",
        *_RUN,
    ),
    _m(
        "o7  plan の位置を取り違える",
        "    want_key = _plan()[expected.index]\n",
        "    want_key = _plan()[expected.index % 4]\n",
        "test_check_uses_the_plan_position_not_the_driver_key",
    ),
    _mr(
        "o8  候補の軸を固定",
        "            axis=want_key.axis,\n",
        "            axis=bat.AXES[0],\n",
        _OTHER_AXIS,
        *_RUN,
    ),
    _m(
        "o9  照合を送信の後に",
        "            check_sent_body(body, self.expected)\n"
        "            self.sent.append(body)\n"
        "            self.last_content_type = None\n"
        "        response = await self.inner.handle_async_request(request)\n",
        "            self.sent.append(body)\n"
        "            self.last_content_type = None\n"
        "        response = await self.inner.handle_async_request(request)\n"
        "        if is_post:\n"
        "            check_sent_body(body, self.expected)\n",
        _BEFORE_SEND,
        "test_shifted_sampling_aborts_before_sending",
    ),
    _m(
        "o10 送信前照合を削除",
        "            check_sent_body(body, self.expected)\n",
        "            pass\n",
        _BEFORE_SEND,
        "test_shifted_sampling_aborts_before_sending",
    ),
    _m(
        "o19 messages の schema を照合しない",
        "    if not isinstance(msgs, list) or not all(\n",
        "    if False and not all(\n",
        "test_check_sent_body_rejects_malformed_messages",
    ),
    _m(
        "o11 型の厳密一致を外す",
        "return type(got) is type(want) and got == want",
        "return got == want",
        _VALUE,
    ),
    _m(
        "o12 body の余分な key を許す",
        "set(body) != BODY_KEYS",
        "not BODY_KEYS <= set(body)",
        "test_check_sent_body_rejects_extra_keys",
    ),
    _m(
        "o13 options の余分な key を許す",
        "set(opts) != OPTION_KEYS",
        "not OPTION_KEYS <= set(opts)",
        "test_check_sent_body_rejects_extra_keys",
    ),
    _m(
        "o14 /api/chat 以外の POST を通す",
        '            if request.url.path != "/api/chat":\n',
        "            if False:\n",
        "test_non_chat_post_is_refused_before_sending",
    ),
    _m(
        "o15 期待の無い送信を通す",
        "            if self.expected is None:\n",
        "            if False:\n",
        "test_chat_without_an_expected_call_is_refused",
    ),
    _m(
        "o16 model の照合を削除",
        '    if not _exact(body["model"], v2bat.MODEL):\n',
        "    if False:\n",
        _VALUE,
    ),
    _m(
        "o17 think の照合を削除",
        '    if not _exact(body["think"], v2bat.THINK):\n',
        "    if False:\n",
        _VALUE,
    ),
    _m(
        "o18 stream の照合を削除",
        '    if not _exact(body["stream"], False):\n',
        "    if False:\n",
        _VALUE,
    ),
    # ---- 順序
    _mr(
        "q1  plan を逆順に",
        "stop = await run_calls(state, _plan())",
        "stop = await run_calls(state, _plan()[::-1])",
        *_RUN,
    ),
    _m(
        "q2  plan の末尾を省く",
        "stop = await run_calls(state, _plan())",
        "stop = await run_calls(state, _plan()[:-8])",
        "test_run_follows_the_frozen_plan",
        "test_every_call_is_sent_once",
    ),
    _mr(
        "q3  call_index を 1 から",
        "    for index, key in enumerate(keys):\n",
        "    for index, key in enumerate(keys, start=1):\n",
        *_RUN,
    ),
    # ---- 再送と raw=null
    _m(
        "t1  再送 3 → 2",
        "RESENDS: Final[int] = 3",
        "RESENDS: Final[int] = 2",
        _RESEND,
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
        _RESEND,
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
        "        primary = exc\n        raise\n",
        "        primary = exc\n",
        "test_other_exceptions_abort_without_a_null_row",
    ),
    # ---- 記録
    _m(
        "r1  raw を strip して記録",
        "            raw=raw,\n",
        "            raw=None if raw is None else raw.strip(),\n",
        "test_raw_is_recorded_verbatim",
        "test_line_separators_in_raw_do_not_split_a_record",
    ),
    _m(
        "r2  parsed を parse せずに記録",
        "            parsed=None if raw is None else parse_choice(raw),\n",
        "            parsed=raw,\n",
        "test_raw_is_recorded_verbatim",
        *_RUN,
    ),
    _m(
        "r3  seed を定数から記録",
        '            seed=body["options"]["seed"],\n            prompt_sha256',
        "            seed=bat.pilot_seed(key.replicate, key.step),\n            prompt_sha256",
        "test_seed_and_prompt_are_recorded_from_the_sent_body",
    ),
    _m(
        "r4  prompt を送った body でなく描き直しから記録",
        '            prompt_sha256=messages_sha256(body["messages"]),\n            raw=raw,',
        "            prompt_sha256=messages_sha256(request_for(key, state)[0]),\n"
        "            raw=raw,",
        "test_seed_and_prompt_are_recorded_from_the_sent_body",
    ),
    Mutant(
        "r5  記録を ensure_ascii=False で書く",
        "    line = json.dumps(obj, ensure_ascii=True, sort_keys=True)",
        "    line = json.dumps(obj, ensure_ascii=False, sort_keys=True)",
        frozenset(_RUN),
        reason="not JSON",
    ),
    _m(
        "r6  読み戻した記録を数えない",
        "    state.records.append(rec)\n",
        "",
        "test_published_records_are_computed_by_the_frozen_scorer",
    ),
    # ---- 公開 (成功したときだけ・二相・凍結 validate・公開時の manifest)
    _mp(
        "u1  常に公開",
        "    publishable = reason == REASON_COMPLETED\n",
        "    publishable = True\n",
        _INCOMPLETE,
        _UNRESOLVED,
        _MODEL,
    ),
    _mp(
        "u2  凍結 validate の結果を見ない",
        "        if status != ps.STATUS_COMPUTED:\n",
        "        if False:\n",
        _INCOMPLETE,
    ),
    _mp(
        "u3  凍結 validate を呼ばない",
        "    if reason == REASON_COMPLETED:\n        status, reasons = frozen_status(",
        "    if False:\n        status, reasons = frozen_status(",
        _INCOMPLETE,
    ),
    _m(
        "u4  公開しない",
        "    if publishable:\n        # commit point",
        "    if False:\n        # commit point",
        _TWO_PHASE,
        *_RUN,
    ),
    _m(
        "u5  1 相目の来歴を completed で書く",
        '        "exit_reason": REASON_ABORTED if publishable else reason,\n',
        '        "exit_reason": reason,\n',
        _TWO_PHASE,
    ),
    _m(
        "u6  2 相目の来歴を書かない",
        "            write_json_durable(prov_path, provenance, exclusive=False)\n",
        "            pass\n",
        _TWO_PHASE,
        _PUB_FAIL,
        "test_published_records_are_computed_by_the_frozen_scorer",
    ),
    _m(
        "u7  公開の失敗を来歴に書かない",
        '            provenance["error"] = _join(\n'
        '                error, f"publication failed: {type(exc).__name__}: {exc}"\n'
        "            )\n",
        "            pass\n",
        _PUB_FAIL,
    ),
    _m(
        "u8  公開の失敗を completed のまま返す",
        "        except OSError as exc:\n            reason = REASON_ABORTED\n",
        "        except OSError as exc:\n            reason = REASON_COMPLETED\n",
        _PUB_FAIL,
    ),
    _m(
        "u9  判定と違う reader (改行だけで分割) で読み戻す",
        '        lines = (run_dir / PARTIAL_NAME).read_text(encoding="utf-8").splitlines()\n',
        '        lines = (run_dir / PARTIAL_NAME).read_text(encoding="utf-8").split(chr(10))\n',
        _FROZEN_STATUS,
    ),
    _m(
        "u10 meta を書いたファイルでなく凍結値から",
        '        meta = json.loads((run_dir / META_NAME).read_text(encoding="utf-8"))\n',
        "        meta = request_meta()\n",
        _FROZEN_STATUS,
    ),
    _m(
        "u11 読めない記録を computed に畳む",
        '        return "unreadable", [f"{type(exc).__name__}: {exc}"]\n',
        "        return ps.STATUS_COMPUTED, []\n",
        _FROZEN_STATUS,
    ),
    _m(
        "u12 公開済みで 2 相目の来歴が書けないと失敗にする",
        '            if not provenance["published"]:\n                raise\n',
        "            raise\n",
        "test_final_provenance_failure_keeps_a_published_run",
    ),
    _m(
        "u13 来歴・公開の失敗で元の例外を隠す",
        "            if primary is None:\n                raise\n",
        "            raise\n",
        "test_provenance_failure_keeps_the_original_exception",
    ),
    _mp(
        "m1  公開時の manifest の結果を見ない",
        "        at_publication = manifest_problems()\n        if at_publication:\n",
        "        at_publication = manifest_problems()\n        if False:\n",
        _MANIFEST_PUB,
    ),
    _m(
        "m2  公開時に manifest を照合しない",
        "    if reason == REASON_COMPLETED:\n        at_publication = manifest_problems()\n",
        "    if False:\n        at_publication = manifest_problems()\n",
        _MANIFEST_PUB,
        "test_published_records_are_computed_by_the_frozen_scorer",
    ),
    # ---- 来歴の異常 (公開を止める。短縮 run では validate を computed に固定して見る、Codex HIGH-1)
    _mp(
        "a1  要求条件の不一致を異常にしない",
        "    if observer.sent and meta_ok is not True:\n",
        "    if False:\n",
        _META_SENT,
        _META_FILE,
    ),
    _mp(
        "a2  meta.json と送った値の一致を見ない",
        "meta_ok = meta_matches_frozen(meta) and same",
        "meta_ok = meta_matches_frozen(meta)",
        _META_FILE,
    ),
    _mp(
        "a3  PINNED の変化を異常にしない",
        "    if changed:\n        anomalies",
        "    if False:\n        anomalies",
        _PINNED,
    ),
    _mp(
        "a4  PINNED を終了時どうしで比べる",
        "if pinned_end[p] != pinned_start[p]",
        "if pinned_end[p] != pinned_end[p]",
        _PINNED,
    ),
    _mp(
        "a5  想定外の応答 model を異常にしない",
        "    if models - {v2bat.MODEL}:\n",
        "    if False:\n",
        _MODEL,
        _MODEL_FULL,
    ),
    _mp(
        "a6  来歴の異常を終了理由に反映しない",
        "    if anomalies and reason == REASON_COMPLETED:\n",
        "    if False:\n",
        _META_SENT,
        _PINNED,
        _MODEL,
        _MODEL_FULL,
    ),
    _mp(
        "a7  meta.json と送った値を型を区別せずに比べる",
        "same = _canonical(written) == _canonical(meta)",
        "same = written == meta",
        _META_FILE,
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
    _mp(
        "f3  終了時の preflight 失敗を aborted にしない",
        "            if stop != REASON_TRANSPORT:\n",
        "            if False:\n",
        _FINAL_ABORT,
    ),
    _mp(
        "f4  model digest の変化を見ない",
        '        elif digest_end != env["model_digest"]:\n',
        "        elif False:\n",
        _DIGEST,
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
        "        request_meta(),\n",
        _META_SENT,
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
    _m(
        "l11 certification の変異の集合と status を照合しない",
        "    if rows != registered:\n",
        "    if False:\n",
        _CERT,
    ),
    _m(
        "l10 all_killed を真偽値以外でも受ける",
        'all_killed = obj["all_killed"] is True',
        'all_killed = bool(obj["all_killed"])',
        _CERT,
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


def anchor_problems(src: str) -> list[str]:
    """全変異の置換前文字列が対象に 1 回ずつ現れ、置換で内容が変わること (中断後の原状確認にも使う)."""
    out = []
    for mut in MUTANTS:
        n = src.count(mut.old)
        if n != 1 or mut.old == mut.new:
            out.append(
                f"{mut.label}: {'NO_OP' if mut.old == mut.new else f'ANCHOR x{n}'}"
            )
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=pathlib.Path, default=None)
    ap.add_argument("--only", default=None, help="label の接頭辞で絞る (開発用)")
    ap.add_argument(
        "--anchors", action="store_true", help="置換前文字列の検査だけを行う"
    )
    args = ap.parse_args(argv)

    if args.anchors:
        problems = anchor_problems(_DRIVER.read_text(encoding="utf-8"))
        for p in problems:
            print(p)
        print(f"anchors: {len(MUTANTS) - len(problems)} / {len(MUTANTS)} OK")
        return 1 if problems else 0

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
            original = originals[_DRIVER]
            src = original.decode("utf-8")
            n = src.count(mut.old)
            if n != 1 or mut.old == mut.new:
                status = "NO_OP" if mut.old == mut.new else f"ANCHOR x{n}"
                rows.append({"label": mut.label, "status": status})
                print(f"{mut.label:44s} {status}", flush=True)
                continue
            _DRIVER.write_bytes(src.replace(mut.old, mut.new, 1).encode("utf-8"))
            try:
                code, failed, collect_error = _run_tests(env)
            except subprocess.TimeoutExpired:
                code, failed, collect_error = -1, {}, False
            _DRIVER.write_bytes(original)
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
