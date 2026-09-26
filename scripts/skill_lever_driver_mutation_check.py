#!/usr/bin/env python
"""Skill lever driver の変異試験 — driver の判定に関わる行を壊すと、意図した test が落ちるか.

``scripts/skill_lever_driver.py`` の行 (C0 gate・呼び出し順・再送と raw=null・送った body の照合・meta の
観測・再開しない・raw の verbatim) を 1 つずつ壊し、``tests/test_skill_lever_driver/`` を実行する。
枠組みは凍結済みの ``scripts/skill_lever_mutation_check.py`` と同じ (同ファイルは凍結 manifest に入って
いるので変えず、driver 用に本 harness を別に置く)。各変異について

* test が落ちること (exit code 非 0) — 落ちなければ SURVIVED、
* 落ちた test に、その行を pin するために書いた test (期待集合) が含まれること — 含まれなければ
  WRONG_REASON、
* collection error で落ちていないこと、
* 置換前の文字列が対象ファイルに 1 回だけ現れ、置換で内容が変わること (no-op 変異を除く)

を確認する。先に無変異で全 test が緑であることを確認する。対象ファイルは必ず原状復帰する。

実行 (repo root から)::

    uv run python scripts/skill_lever_driver_mutation_check.py --out <driver_mutation.json>
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
_DRIVER = _REPO_ROOT / "scripts" / "skill_lever_driver.py"
_TESTS = "tests/test_skill_lever_driver"
# commit 済み certification と現在のファイルの一致を見る test は、変異中は必ず落ちて生き残りを覆い隠す
# ので外す (凍結版 harness の test_committed_artifacts_are_consistent と同じ扱い)。
_DESELECT = f"{_TESTS}/test_driver.py::test_committed_driver_certification_is_current"
_TEST_TIMEOUT_S = 600
_FAILED = re.compile(r"^FAILED (\S+?)(?:\[.*?\])?(?: - .*)?$")


@dataclass(frozen=True)
class Mutant:
    label: str
    old: str
    new: str
    expect: frozenset[str]


def _m(label: str, old: str, new: str, *expect: str) -> Mutant:
    return Mutant(label, old, new, frozenset(expect))


_ORDER = "test_run_records_c0_before_lever_with_serial_call_index"
_UNRESOLVED = "test_unresolved_transport_failure_records_null_and_stops"
_WIRED = ("test_c0_gate_at_the_limit_runs_lever", "test_uniform_model_is_no_go")

MUTANTS: tuple[Mutant, ...] = (
    # ---- C0 gate
    _m(
        "md1  C0 gate を >= に",
        "if c0_rate > sc.BOT_MAX:",
        "if c0_rate >= sc.BOT_MAX:",
        "test_c0_gate_at_the_limit_runs_lever",
    ),
    _m(
        "md2  C0 gate を削除",
        "                if c0_rate > sc.BOT_MAX:\n",
        "                if False:\n",
        "test_c0_gate_blocks_lever",
    ),
    _m(
        "md3  C0 ⊥ 率を r=0 だけで",
        "(bat.ARM_C0,), sc.FROZEN_R)[0]",
        "(bat.ARM_C0,), 1)[0]",
        "test_c0_gate_at_the_limit_runs_lever",
    ),
    # ---- 呼び出し順
    _m(
        "md4  lever を C0 より先に",
        "stop = await run_phase(state, c0_schedule())",
        "stop = await run_phase(state, lever_schedule() + c0_schedule())",
        _ORDER,
    ),
    _m(
        "md5  lever phase で call_index を振り直す",
        "                stop = await run_phase(state, lever_schedule())\n",
        "                state.call_index = 0\n"
        "                stop = await run_phase(state, lever_schedule())\n",
        _ORDER,
    ),
    _m(
        "md6  block 内の arm 巡回を削除",
        "shift = block % len(bat.LEVER_ARMS)",
        "shift = 0",
        "test_lever_arms_rotate_evenly_over_slots",
    ),
    # ---- 再送と raw=null
    _m(
        "md7  再送 3 → 2",
        "RESENDS: Final[int] = 3",
        "RESENDS: Final[int] = 2",
        "test_resend_with_the_same_seed_recovers",
        _UNRESOLVED,
    ),
    _m(
        "md8  再送 3 → 4",
        "RESENDS: Final[int] = 3",
        "RESENDS: Final[int] = 4",
        _UNRESOLVED,
    ),
    _m(
        "md9  再送で seed を変える",
        "options=dict(options)",
        'options={**options, "seed": options["seed"] + attempt}',
        "test_resend_with_the_same_seed_recovers",
    ),
    _m(
        "md10 再送が尽きても続行",
        "        if raw is None:\n            return REASON_TRANSPORT\n",
        "        if False:\n            return REASON_TRANSPORT\n",
        _UNRESOLVED,
    ),
    _m(
        "md11 再送が尽きたら null でなく空文字",
        "    return None, state.observer.sent[-1]",
        '    return "", state.observer.sent[-1]',
        _UNRESOLVED,
    ),
    _m(
        "md12 transport 以外の例外も再送",
        "except OllamaUnavailableError as exc:",
        "except Exception as exc:",
        "test_other_exceptions_abort_without_a_null_row",
        "test_shifted_sampling_aborts_before_sending",
    ),
    # ---- 送った body の照合と meta の観測
    _m(
        "md13 meta を request_meta() から写す",
        "        meta_of(state.observer.sent[0]),\n",
        "        sc.request_meta(),\n",
        "test_meta_is_written_from_sent_values_not_constants",
    ),
    _m(
        "md14 型の厳密一致を外す",
        "return type(got) is type(want) and got == want",
        "return got == want",
        "test_check_sent_body_rejects_value_and_type",
    ),
    _m(
        "md15 送信前照合を削除",
        "            check_sent_body(body, self.expected)\n",
        "            pass\n",
        "test_shifted_sampling_aborts_before_sending",
        "test_mismatch_is_detected_before_the_inner_transport",
    ),
    _m(
        "md16 照合を送信の後に",
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
        "md17 messages の照合を削除",
        '    if sc.messages_sha256(body["messages"]) != sha:\n',
        "    if False:\n",
        "test_check_sent_body_rejects_missing_seed_and_other_prompt",
    ),
    _m("md18 think=None で送る", "think=bat.THINK", "think=None", *_WIRED),
    _m(
        "md19 options から seed を落とす",
        '        "seed": bat.sample_seed(r, qi, k),\n',
        "",
        *_WIRED,
    ),
    # ---- 記録
    _m(
        "md20 raw を strip して記録",
        "            raw=raw,\n",
        "            raw=None if raw is None else raw.strip(),\n",
        "test_raw_is_recorded_verbatim",
    ),
    _m(
        "md21 parsed を parse せずに記録",
        "            parsed=None if raw is None else sc.parse_choice(raw),\n",
        "            parsed=raw,\n",
        "test_raw_is_recorded_verbatim",
    ),
    _m(
        "md22 非空の run dir を拒否しない",
        "    if run_dir.exists() and any(run_dir.iterdir()):\n",
        "    if False:\n",
        "test_run_refuses_a_non_empty_run_dir",
    ),
    # ---- review 反映 (code-reviewer / Codex)
    _m(
        "md23 seed を定数から記録",
        '            seed=body["options"]["seed"],\n',
        "            seed=bat.sample_seed(r, qi, k),\n",
        "test_seed_and_prompt_are_recorded_from_the_sent_body",
    ),
    _m(
        "md24 prompt_sha256 を定数から記録",
        '            prompt_sha256=sc.messages_sha256(body["messages"]),\n',
        "            prompt_sha256=sc.expected_sample(arm, r, qi, k)[1],\n",
        "test_seed_and_prompt_are_recorded_from_the_sent_body",
    ),
    _m(
        "md25 非文字列 content を成功扱い",
        '            if ctype != "str":\n',
        "            if False:\n",
        "test_null_content_is_a_transport_failure_not_bottom",
    ),
    _m(
        "md26 preflight を飛ばす",
        "        env = await preflight(http)\n",
        '        env = {"ollama_version": "x", "model_digest": "x"}\n',
        "test_preflight_failure_writes_nothing",
    ),
    _m(
        "md27 meta.json を実走中に書かない",
        "        _ensure_meta(state)\n",
        "",
        "test_meta_is_on_disk_while_the_run_is_going",
    ),
    _m(
        "md28 model digest の変化を見ない",
        '        if digest_end != env["model_digest"]:\n',
        "        if False:\n",
        "test_model_digest_change_aborts",
    ),
    _m(
        "md29 body の余分な key を許す",
        "set(body) != BODY_KEYS",
        "not BODY_KEYS <= set(body)",
        "test_check_sent_body_rejects_extra_keys",
    ),
    _m(
        "md30 options の余分な key を許す",
        "set(opts) != OPTION_KEYS",
        "not OPTION_KEYS <= set(opts)",
        "test_check_sent_body_rejects_extra_keys",
    ),
    _m(
        "md31 /api/chat 以外の POST を通す",
        '            if request.url.path != "/api/chat":\n',
        "            if False:\n",
        "test_non_chat_post_is_refused_before_sending",
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
    original = _DRIVER.read_bytes()
    sha_before = hashlib.sha256(original).hexdigest()

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
            src = original.decode("utf-8")
            n = src.count(mut.old)
            if n != 1 or mut.old == mut.new:
                status = "NO_OP" if mut.old == mut.new else f"ANCHOR x{n}"
                rows.append({"label": mut.label, "status": status})
                continue
            _DRIVER.write_bytes(src.replace(mut.old, mut.new, 1).encode("utf-8"))
            try:
                code, failed, collect_error = _run_tests(env)
            except subprocess.TimeoutExpired:
                code, failed, collect_error = -1, [], False
            _DRIVER.write_bytes(original)
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
    finally:
        _DRIVER.write_bytes(original)

    restored = hashlib.sha256(_DRIVER.read_bytes()).hexdigest() == sha_before
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
                    "target_sha256": {_DRIVER.name: sha_before, **tests_sha},
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
