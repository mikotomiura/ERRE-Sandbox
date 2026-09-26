#!/usr/bin/env python
"""経験由来 Skill driver の変異試験 — driver・gate・記述報告の判定に関わる行を壊すと、意図した test が落ちるか.

次の 3 ファイルの行を 1 つずつ壊し、``tests/test_skill_experience_driver/`` を実行する。
* ``scripts/skill_experience_driver.py`` (C0 gate・呼び出し順・再送と raw=null・送った body の照合・meta の観測・
  来歴の異常・再開しない・raw の verbatim・起動の前提)
* ``scripts/skill_experience_run_gate.py`` (終了状態の gate、DE-R5)
* ``scripts/skill_experience_describe.py`` (§9 の抑制・filler 率・対照の推定量)

枠組みは v2 の ``scripts/skill_lever_driver_mutation_check.py`` と同じ (v2 driver の certification
に結び付くので変えず、v3 driver 用に本 harness を別に置く)。各変異について

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

    uv run python scripts/skill_experience_driver_mutation_check.py --out <driver_mutation.json>
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
_DRIVER = _SCRIPTS / "skill_experience_driver.py"
_DESCRIBE = _SCRIPTS / "skill_experience_describe.py"
_GATE = _SCRIPTS / "skill_experience_run_gate.py"
_TARGETS = (_DRIVER, _DESCRIBE, _GATE)
_TESTS = "tests/test_skill_experience_driver"
# commit 済み certification と現在のファイルの一致を見る test は、変異中は必ず落ちて生き残りを覆い隠す
# ので外す (凍結版 harness の test_committed_artifacts_are_consistent と同じ扱い)。
_DESELECT = f"{_TESTS}/test_driver.py::test_committed_driver_certification_is_current"
_TEST_TIMEOUT_S = 900
_FAILED = re.compile(r"^FAILED (\S+?)(?:\[.*?\])?(?: - .*)?$")


@dataclass(frozen=True)
class Mutant:
    label: str
    old: str
    new: str
    expect: frozenset[str]
    target: pathlib.Path = _DRIVER


def _m(label: str, old: str, new: str, *expect: str) -> Mutant:
    return Mutant(label, old, new, frozenset(expect))


def _md(label: str, old: str, new: str, *expect: str) -> Mutant:
    return Mutant(label, old, new, frozenset(expect), _DESCRIBE)


def _mg(label: str, old: str, new: str, *expect: str) -> Mutant:
    return Mutant(label, old, new, frozenset(expect), _GATE)


_ORDER = "test_run_records_c0_before_state_with_serial_call_index"
_ROT = (
    "test_state_arms_rotate_evenly_over_slots",
    "test_schedule_agrees_with_the_scorer_call_rank",
)
_UNRESOLVED = "test_unresolved_transport_failure_records_null_and_stops"
_WIRED = ("test_c0_gate_at_the_limit_runs_state_arms", "test_uniform_model_is_no_go")
_MANIFEST = "test_manifest_problems_require_manifest_ok"
_CERT = "test_driver_certification_detects_stale_or_failing"
_ANOMALY = (
    "test_meta_is_written_from_sent_values_not_constants",
    "test_driver_change_during_the_run_aborts",
    "test_unexpected_response_model_aborts",
)
_GIT = "test_launch_problems_check_git_tracking_and_head"
_VALUE = "test_check_sent_body_rejects_value_and_type"
_SUPPRESS = "test_effects_are_suppressed_unless_the_verdict_is_valid"
_ABORTED_RUN = "test_aborted_run_with_complete_records_is_stopped"
_FIELDS = "test_each_provenance_field_is_checked"

MUTANTS: tuple[Mutant, ...] = (
    # ---- C0 gate
    _m(
        "md1  C0 gate を >= に",
        "if c0_rate > sc.BOT_MAX:",
        "if c0_rate >= sc.BOT_MAX:",
        "test_c0_gate_at_the_limit_runs_state_arms",
    ),
    _m(
        "md2  C0 gate を削除",
        "                if c0_rate > sc.BOT_MAX:\n",
        "                if False:\n",
        "test_c0_gate_blocks_state_arms",
        "test_c0_gate_counts_the_last_replicate",
    ),
    _m(
        "md3  C0 ⊥ 率を r=0 だけで",
        "(bat.ARM_C0,), sc.FROZEN_R)[0]",
        "(bat.ARM_C0,), 1)[0]",
        "test_c0_gate_counts_the_last_replicate",
    ),
    _m(
        "md4  C0 gate の対象 arm を取り違える",
        "        if s.arm == bat.ARM_C0:\n",
        "        if s.arm == bat.ARM_A:\n",
        "test_c0_gate_blocks_state_arms",
    ),
    # ---- 呼び出し順
    _m(
        "md5  状態 arm を C0 より先に",
        "stop = await run_phase(state, c0_schedule())",
        "stop = await run_phase(state, state_schedule() + c0_schedule())",
        _ORDER,
    ),
    _m(
        "md6  状態 phase で call_index を振り直す",
        "                stop = await run_phase(state, state_schedule())\n",
        "                state.call_index = 0\n"
        "                stop = await run_phase(state, state_schedule())\n",
        _ORDER,
    ),
    _m(
        "md7  block 内の arm 巡回を削除",
        "arms = sc.block_arm_order(sc.call_block(r, qi, k))",
        "arms = bat.STATE_ARMS",
        *_ROT,
    ),
    _m(
        "md8  巡回を mod 4 に",
        "arms = sc.block_arm_order(sc.call_block(r, qi, k))",
        "arms = sc.block_arm_order(sc.call_block(r, qi, k) % 4)",
        *_ROT,
    ),
    _m(
        "md9  巡回の block 番号を k に依らせない",
        "arms = sc.block_arm_order(sc.call_block(r, qi, k))",
        "arms = sc.block_arm_order(sc.call_block(r, qi, 0))",
        *_ROT,
    ),
    _m(
        "md10 対照 arm を呼ばない",
        "                out.extend((arm, r, qi, k) for arm in arms)\n",
        "                out.extend(\n"
        "                    (arm, r, qi, k) for arm in arms if arm in bat.JUDGE_ARMS\n"
        "                )\n",
        "test_schedule_is_the_frozen_grid_with_c0_first",
        "test_state_arms_rotate_evenly_over_slots",
    ),
    _m(
        "md11 C0 の順を probe 優先に",
        "        for r in range(sc.FROZEN_R)\n"
        "        for qi in range(len(v2bat.lever_probes()))\n",
        "        for qi in range(len(v2bat.lever_probes()))\n"
        "        for r in range(sc.FROZEN_R)\n",
        "test_schedule_is_the_frozen_grid_with_c0_first",
        "test_schedule_agrees_with_the_scorer_call_rank",
    ),
    # ---- 再送と raw=null
    _m(
        "md12 再送 3 → 2",
        "RESENDS: Final[int] = 3",
        "RESENDS: Final[int] = 2",
        "test_resend_with_the_same_seed_recovers",
        _UNRESOLVED,
    ),
    _m(
        "md13 再送 3 → 4",
        "RESENDS: Final[int] = 3",
        "RESENDS: Final[int] = 4",
        _UNRESOLVED,
    ),
    _m(
        "md14 再送で seed を変える",
        "options=dict(options)",
        'options={**options, "seed": options["seed"] + attempt}',
        "test_resend_with_the_same_seed_recovers",
    ),
    _m(
        "md15 再送が尽きても続行",
        "        if raw is None:\n            return REASON_TRANSPORT\n",
        "        if False:\n            return REASON_TRANSPORT\n",
        _UNRESOLVED,
    ),
    _m(
        "md16 再送が尽きたら null でなく空文字",
        "    return None, state.observer.sent[-1]",
        '    return "", state.observer.sent[-1]',
        _UNRESOLVED,
    ),
    _m(
        "md17 transport 以外の例外も再送",
        "except OllamaUnavailableError as exc:",
        "except Exception as exc:",
        "test_other_exceptions_abort_without_a_null_row",
        "test_shifted_sampling_aborts_before_sending",
    ),
    _m(
        "md18 非文字列 content を成功扱い",
        '            if ctype != "str":\n',
        "            if False:\n",
        "test_null_content_is_a_transport_failure_not_bottom",
    ),
    # ---- 送った body の照合と meta の観測
    _m(
        "md19 meta を request_meta() から写す",
        "        meta_of(state.observer.sent[0]),\n",
        "        sc.request_meta(),\n",
        "test_meta_is_written_from_sent_values_not_constants",
    ),
    _m(
        "md20 型の厳密一致を外す",
        "return type(got) is type(want) and got == want",
        "return got == want",
        "test_check_sent_body_rejects_value_and_type",
    ),
    _m(
        "md21 送信前照合を削除",
        "            check_sent_body(body, self.expected)\n",
        "            pass\n",
        "test_shifted_sampling_aborts_before_sending",
        "test_mismatch_is_detected_before_the_inner_transport",
    ),
    _m(
        "md22 照合を送信の後に",
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
        "md23 messages の照合を削除",
        '    if messages_sha256(body["messages"]) != sha:\n',
        "    if False:\n",
        "test_check_sent_body_rejects_missing_seed_and_other_prompt",
    ),
    _m(
        "md24 body の余分な key を許す",
        "set(body) != BODY_KEYS",
        "not BODY_KEYS <= set(body)",
        "test_check_sent_body_rejects_extra_keys",
    ),
    _m(
        "md25 options の余分な key を許す",
        "set(opts) != OPTION_KEYS",
        "not OPTION_KEYS <= set(opts)",
        "test_check_sent_body_rejects_extra_keys",
    ),
    _m(
        "md26 /api/chat 以外の POST を通す",
        '            if request.url.path != "/api/chat":\n',
        "            if False:\n",
        "test_non_chat_post_is_refused_before_sending",
    ),
    _m("md27 think=None で送る", "think=v2bat.THINK", "think=None", *_WIRED),
    _m(
        "md28 options から seed を落とす",
        '        "seed": v2bat.sample_seed(r, qi, k),\n',
        "",
        *_WIRED,
    ),
    _m(
        "md29 v2 の renderer で送る",
        "    msgs = bat.render_messages(arm, probe, v2bat.layout(r))\n",
        "    msgs = v2bat.render_messages(\n"
        '        arm if arm == bat.ARM_C0 else "A", probe, v2bat.layout(r)\n'
        "    )\n",
        "test_request_uses_the_v3_renderer_not_v2",
    ),
    # ---- 記録
    _m(
        "md30 raw を strip して記録",
        "            raw=raw,\n",
        "            raw=None if raw is None else raw.strip(),\n",
        "test_raw_is_recorded_verbatim",
    ),
    _m(
        "md31 parsed を parse せずに記録",
        "            parsed=None if raw is None else sc.parse_choice(raw),\n",
        "            parsed=raw,\n",
        "test_raw_is_recorded_verbatim",
    ),
    _m(
        "md32 seed を定数から記録",
        '            seed=body["options"]["seed"],\n',
        "            seed=v2bat.sample_seed(r, qi, k),\n",
        "test_seed_and_prompt_are_recorded_from_the_sent_body",
    ),
    _m(
        "md33 prompt_sha256 を定数から記録",
        '            prompt_sha256=messages_sha256(body["messages"]),\n',
        "            prompt_sha256=sc.expected_sample(arm, r, qi, k)[1],\n",
        "test_seed_and_prompt_are_recorded_from_the_sent_body",
    ),
    _m(
        "md34 probe_id を取り違える",
        "            probe_id=probes[qi].probe_id,\n",
        "            probe_id=probes[(qi + 1) % len(probes)].probe_id,\n",
        "test_records_match_expected_sample_and_parse",
    ),
    # ---- 運用の保護
    _m(
        "md35 非空の run dir を拒否しない",
        "    if run_dir.exists() and any(run_dir.iterdir()):\n",
        "    if False:\n",
        "test_run_refuses_a_non_empty_run_dir",
    ),
    _m(
        "md36 preflight を飛ばす",
        "        env = await preflight(http)\n",
        '        env = {"ollama_version": "x", "model_digest": "x"}\n',
        "test_preflight_failure_writes_nothing",
    ),
    _m(
        "md37 meta.json を実走中に書かない",
        "        _ensure_meta(state)\n",
        "",
        "test_meta_is_on_disk_while_the_run_is_going",
    ),
    _m(
        "md38 model digest の変化を見ない",
        '        if digest_end != env["model_digest"]:\n',
        "        if False:\n",
        "test_model_digest_change_aborts",
    ),
    # ---- 起動の前提
    _m(
        "md39 manifest 検査を起動条件に入れない",
        "    problems.extend(manifest_problems())\n",
        "",
        "test_launch_problems_include_manifest_and_certification",
    ),
    _m(
        "md40 manifest の exit code だけを見る",
        'if proc.returncode != 0 or not lines or lines[-1] != "MANIFEST OK":',
        "if proc.returncode != 0:",
        _MANIFEST,
    ),
    _m(
        "md41 manifest の末尾行だけを見る",
        'if proc.returncode != 0 or not lines or lines[-1] != "MANIFEST OK":',
        'if not lines or lines[-1] != "MANIFEST OK":',
        _MANIFEST,
    ),
    _m(
        "md42 manifest の OK を末尾以外でも受ける",
        'lines[-1] != "MANIFEST OK"',
        '"MANIFEST OK" not in lines',
        _MANIFEST,
    ),
    _m(
        "md43 起動拒否を外す",
        "    if problems:\n        for p in problems:\n",
        "    if False:\n        for p in problems:\n",
        "test_main_refuses_to_launch_without_touching_the_run_dir",
    ),
    _m(
        "md44 未合格の certification を通す",
        'problems = [] if all_killed else ["driver certification: not all KILLED"]',
        "problems: list[str] = []",
        _CERT,
    ),
    _m(
        "md45 certification の sha256 を照合しない",
        "    if recorded != certified_files():\n",
        "    if False:\n",
        _CERT,
    ),
    # ---- 来歴の異常は aborted (review 反映)
    _m(
        "md46 要求条件の不一致を aborted にしない",
        "        if observer.sent and meta_ok is not True:\n",
        "        if False:\n",
        _ANOMALY[0],
    ),
    _m(
        "md47 実走中の driver 変更を aborted にしない",
        "        if driver_sha_end != driver_sha_start:\n",
        "        if False:\n",
        _ANOMALY[1],
    ),
    _m(
        "md48 想定外の応答 model を aborted にしない",
        "        if models - {v2bat.MODEL}:\n",
        "        if False:\n",
        _ANOMALY[2],
    ),
    _m(
        "md49 来歴の異常を終了理由に反映しない",
        "        if anomalies and reason in (REASON_COMPLETED, REASON_C0_GATE):\n",
        "        if False:\n",
        *_ANOMALY,
    ),
    _m(
        "md50 PINNED の追跡を見ない",
        '        if _git("ls-files", "--error-unmatch", rel) is None:\n',
        "        if False:\n",
        _GIT,
    ),
    _m(
        "md51 PINNED と HEAD の差分を見ない",
        '    if _git("diff", "--quiet", "HEAD", "--", *PINNED) is None:\n',
        "    if False:\n",
        _GIT,
    ),
    _m(
        "md52 期待 key の無い送信を通す",
        "            if self.expected is None:\n",
        "            if False:\n",
        "test_chat_without_an_expected_key_is_refused",
    ),
    _m(
        "md53 非 transport 例外を握りつぶす",
        '        error = f"{type(exc).__name__}: {exc}"\n        raise\n',
        '        error = f"{type(exc).__name__}: {exc}"\n',
        "test_other_exceptions_abort_without_a_null_row",
    ),
    _m(
        "md54 model の照合を削除",
        '    if not _exact(body["model"], v2bat.MODEL):\n',
        "    if False:\n",
        _VALUE,
    ),
    _m(
        "md55 think の照合を削除",
        '    if not _exact(body["think"], v2bat.THINK):\n',
        "    if False:\n",
        _VALUE,
    ),
    _m(
        "md56 stream の照合を削除",
        '    if not _exact(body["stream"], False):\n',
        "    if False:\n",
        _VALUE,
    ),
    _m(
        "md57 num_ctx を変えて送る",
        '        "num_ctx": v2bat.NUM_CTX,\n        "num_predict": v2bat.NUM_PREDICT,\n'
        "    }\n    return [ChatMessage",
        '        "num_ctx": 2048,\n        "num_predict": v2bat.NUM_PREDICT,\n'
        "    }\n    return [ChatMessage",
        *_WIRED,
    ),
    # ---- 終了状態の gate (DE-R5)
    _mg(
        "g1   exit_reason を見ない",
        'if prov.get("exit_reason") not in ACCEPTED_EXIT:',
        "if False:",
        _ABORTED_RUN,
        _FIELDS,
    ),
    _mg(
        "g2   aborted を受け入れる",
        'frozenset({"completed", "c0_gate"})',
        'frozenset({"completed", "c0_gate", "aborted"})',
        _ABORTED_RUN,
    ),
    _mg(
        "g3   meta 不明 (None) を通す",
        'if prov.get("meta_matches_frozen") is not True:',
        'if prov.get("meta_matches_frozen") is False:',
        _FIELDS,
    ),
    _mg(
        "g4   driver sha の欠落を通す",
        "    if not start or start != end:\n",
        "    if start != end:\n",
        _FIELDS,
    ),
    _mg(
        "g5   model digest を見ない",
        "    if not d_start or d_start != d_end:\n",
        "    if False:\n",
        _ABORTED_RUN,
        _FIELDS,
    ),
    _mg(
        "g6   応答 model の空を通す",
        'if prov.get("response_models") != [v2bat.MODEL]:',
        'if not set(prov.get("response_models") or []) <= {v2bat.MODEL}:',
        _FIELDS,
    ),
    _mg(
        "g7   行数を照合しない",
        '    if prov.get("n_samples") != n_lines:\n',
        "    if False:\n",
        "test_truncated_samples_are_stopped",
    ),
    _mg(
        "g8   不合格でも exit 0",
        "    return 0 if not problems else 1",
        "    return 0",
        _ABORTED_RUN,
    ),
    _mg(
        "g9   空行も行数に数える",
        "n_lines = sum(bool(line.strip()) for line in text.splitlines())",
        "n_lines = len(text.split(chr(10)))",
        "test_completed_run_passes_the_gate",
    ),
    # ---- 記述報告の抑制と定義 (prereg v3 §9 / §10)
    _md(
        "ds1  判定の効果を常に出す",
        "    judge_ok = status == sc.STATUS_COMPUTED and verdict in EFFECT_VERDICTS\n",
        "    judge_ok = True\n",
        _SUPPRESS,
    ),
    _md(
        "ds2  INVALID でも効果を出す",
        "EFFECT_VERDICTS = frozenset({VERDICT_PASS, VERDICT_ABSENT, VERDICT_UNDERPOWERED})",
        "EFFECT_VERDICTS = frozenset(\n"
        '    {VERDICT_PASS, VERDICT_ABSENT, VERDICT_UNDERPOWERED, "INVALID_TASK_BATTERY"}\n'
        ")",
        _SUPPRESS,
        "test_control_effects_are_suppressed_when_the_control_is_invalid",
    ),
    _md(
        "ds3  対照 verdict を見ない",
        "    control_ok = judge_ok and ctrl_verdict in EFFECT_VERDICTS\n",
        "    control_ok = judge_ok\n",
        "test_control_effects_are_suppressed_when_the_control_is_invalid",
    ),
    _md(
        "ds4  gate の不合格を無視",
        "    if gate_problems:  # driver",
        "    if False:  # driver",
        "test_run_gate_problems_suppress_every_effect",
        "test_main_applies_the_run_gate",
    ),
    _md(
        "ds5  main で gate を渡さない",
        "        gate.run_gate_problems(args.run_dir),\n",
        "        (),\n",
        "test_main_applies_the_run_gate",
    ),
    _md(
        "ds6  records と results の結び付けを見ない",
        '    if (results.get("inputs") or {}).get("records_sha256") != records_sha:\n',
        "    if False:\n",
        "test_main_refuses_results_of_other_records",
    ),
    _md(
        "ds7  filler 率を言及率で",
        '        fillers = sum(answered_filler(s.raw or "") for s in rows)\n',
        '        fillers = sum(bool(fillers_in(s.raw or "")) for s in rows)\n',
        "test_control_minus_judge_and_filler_rate",
    ),
    _md(
        "ds8  filler 回答に ⊥ を要求しない",
        "    return sc.parse_choice(raw) is None and len(fillers_in(raw)) == 1",
        "    return len(fillers_in(raw)) == 1",
        "test_answered_filler_needs_bottom_and_exactly_one_filler",
    ),
    _md(
        "ds9  INCONCLUSIVE の注記を削除",
        "        if judge_ok and verdict == VERDICT_UNDERPOWERED\n",
        "        if False\n",
        "test_inconclusive_keeps_numbers_with_a_note",
    ),
    _md(
        "ds10 対照の推定量を判定 arm で",
        "    control = _estimand(done, bat.CONTROL_ARMS)",
        "    control = _estimand(done, bat.JUDGE_ARMS)",
        "test_extracting_run_description",
    ),
    _md(
        "ds11 対照 arm の指す先を写像しない",
        "        as_arm = bat.POINTS_AS[arm]\n",
        "        as_arm = arm\n",
        "test_extracting_run_description",
    ),
    _md(
        "ds12 位置の ⊥ と OOΩ を混ぜる",
        '            positions["bot"] += 1',
        '            positions["oov"] += 1',
        "test_c0_positions_separate_bottom_and_out_of_omega",
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
        timeout=_TEST_TIMEOUT_S,
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
    originals = {t: t.read_bytes() for t in _TARGETS}
    sha_before = {t.name: hashlib.sha256(b).hexdigest() for t, b in originals.items()}
    harness = pathlib.Path(__file__).resolve()
    sha_before[harness.name] = hashlib.sha256(harness.read_bytes()).hexdigest()

    tests_sha = {
        f"tests/{p.name}": hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((_REPO_ROOT / _TESTS).glob("*.py"))
    }
    code, failed, _ = _run_tests(env)
    if code != 0:
        print(f"ERROR: baseline (無変異) が緑でない: {failed}")
        return 2

    rows: list[dict[str, object]] = []
    try:
        for mut in MUTANTS:
            original = originals[mut.target]
            src = original.decode("utf-8")
            n = src.count(mut.old)
            if n != 1 or mut.old == mut.new:
                status = "NO_OP" if mut.old == mut.new else f"ANCHOR x{n}"
                rows.append({"label": mut.label, "status": status})
                continue
            mut.target.write_bytes(src.replace(mut.old, mut.new, 1).encode("utf-8"))
            try:
                code, failed, collect_error = _run_tests(env)
            except subprocess.TimeoutExpired:
                code, failed, collect_error = -1, [], False
            mut.target.write_bytes(original)
            if code == -1:
                status = "TIMEOUT"
            elif code == 0:
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
    if args.out is not None:
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
