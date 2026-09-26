#!/usr/bin/env python
"""Skill lever pilot の変異試験 — 判定行を壊すと、意図した test が落ちるか (prereg v2 §7).

``scripts/skill_lever_scorer.py`` (ms*) と ``scripts/skill_lever_battery.py`` (mb*) の判定行を 1 つずつ壊し、
``tests/test_skill_lever/`` を実行する。枠組みは ``scripts/stage_b_mutation_check.py`` と同じ。各変異について

* test が落ちること (exit code 非 0) — 落ちなければ SURVIVED、
* 落ちた test に、その判定行を pin するために書いた test (期待集合) が含まれること —
  含まれなければ WRONG_REASON (別の理由で落ちただけ)、
* collection error で落ちていないこと (import が壊れただけの no-op kill を除く)、
* 置換前の文字列が対象ファイルに 1 回だけ現れ、置換で内容が変わること (no-op 変異を除く)

を確認する。先に無変異で全 test が緑であることを確認する (恒真の検出)。
対象ファイルは実行中だけ書き換わり、必ず原状復帰する (finally + sha256 照合)。
出力の ``target_sha256`` は ``skill_lever_scorer.load_certification`` が照合する 4 ファイルの値。

実行 (repo root から)::

    uv run python scripts/skill_lever_mutation_check.py --out <results.json>
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
_SCORER = _REPO_ROOT / "scripts" / "skill_lever_scorer.py"
_BATTERY = _REPO_ROOT / "scripts" / "skill_lever_battery.py"
# certification が照合する 4 ファイル。変異対象は前 2 つ (後 2 つは旧 prereg に結び付くので触らない)。
_CERTIFIED = (
    _SCORER,
    _BATTERY,
    _REPO_ROOT / "scripts" / "stage_b_scorer.py",
    _REPO_ROOT / "scripts" / "stage_b_battery.py",
)
_TESTS = "tests/test_skill_lever"
# commit 済み manifest / certification / power 表と現在のコードの一致を見る test は、変異中は必ず落ちて
# 生き残りを覆い隠すので外す (この test 自体は凍結後の改変検出用)。
_DESELECT = f"{_TESTS}/test_manifest.py::test_committed_artifacts_are_consistent"
_FAILED = re.compile(r"^FAILED (\S+?)(?:\[.*?\])?(?: - .*)?$")


@dataclass(frozen=True)
class Mutant:
    label: str
    target: pathlib.Path
    old: str
    new: str
    expect: frozenset[str]  # 判定行を pin する test 関数名 (どれか 1 つ以上が落ちる)


def _m(label: str, target: pathlib.Path, old: str, new: str, *expect: str) -> Mutant:
    return Mutant(label, target, old, new, frozenset(expect))


_S = _SCORER
_B = _BATTERY
_OFF = "    if False:\n"
_OFF8 = "        if False:\n"

MUTANTS: tuple[Mutant, ...] = (
    # ---- 推定量
    _m(
        "ms1  foil を反対族 (旧 A vs B 対比) に",
        _S,
        "    if choice == probe.pointed[bat.FOIL[arm]]:\n",
        '    if choice == probe.pointed[{"A": "B", "A_rot": "B_rot", "B": "A", "B_rot": "A_rot"}[arm]]:\n',
        "test_priming_only_is_not_pass",
    ),
    _m(
        "ms2  ⊥ を分母から落とす",
        _S,
        "                    n += 1\n",
        '                    n += cat != "bot"\n',
        "test_bottom_counts_in_denominator",
    ),
    # ---- 判定 (3 分岐)
    _m(
        "ms3  4 成分の符号条件を削除",
        _S,
        "    passed = (np.asarray(p_lower) < ALPHA) & comps_positive\n",
        "    passed = np.asarray(p_lower) < ALPHA\n",
        "test_one_arm_failure_is_not_pass",
    ),
    _m(
        "ms4  PASS の下限を τ でなく 0 に",
        _S,
        "signflip_p(d), signflip_p(d - TAU), signflip_p(TAU - d)",
        "signflip_p(d), signflip_p(d), signflip_p(TAU - d)",
        "test_small_effect_is_no_go",
    ),
    _m(
        "ms5  PASS でなければ全て NO_GO",
        _S,
        "    no_go = np.asarray(p_upper) < ALPHA\n",
        "    no_go = np.asarray(p_upper) <= 1.0\n",
        "test_effect_at_threshold_is_inconclusive",
        "test_noisy_effect_straddling_threshold_is_inconclusive",
        "test_one_arm_failure_is_not_pass",
    ),
    _m(
        "ms6  NO_GO の上限検定を τ でなく 0 に",
        _S,
        "signflip_p(TAU - d)",
        "signflip_p(-d)",
        "test_small_effect_is_no_go",
        "test_uniform_null_is_no_go",
    ),
    _m(
        "ms7  植える効果 = 閾値 (DB-1 の再現)",
        _S,
        "DELTA_PLANT: Final[float] = 2.0 * TAU",
        "DELTA_PLANT: Final[float] = TAU",
        "test_plant_is_distinct_from_threshold",
        "test_frozen_values",
    ),
    # ---- ⊥ gate
    _m(
        "ms8  lever ⊥ gate を削除",
        _S,
        "    return per_arm & family\n",
        "    return per_arm | True\n",
        "test_lever_bottom_rate_is_invalid_battery",
        "test_family_bottom_gap_is_invalid_battery",
    ),
    _m(
        "ms9  族内 ⊥ 率差の条項を削除",
        _S,
        "< BOT_FAMILY_GAP, axis=-1)",
        "< 1.0, axis=-1)",
        "test_family_bottom_gap_is_invalid_battery",
    ),
    _m(
        "ms10 arm ごと ⊥ 率上限を削除",
        _S,
        "    per_arm = np.all(bot <= BOT_MAX, axis=-1)\n",
        "    per_arm = np.all(bot <= 1.0, axis=-1)\n",
        "test_lever_bottom_rate_is_invalid_battery",
    ),
    _m(
        "ms11 C0 ⊥ gate を削除",
        _S,
        "    if c0_bot > BOT_MAX:\n",
        _OFF,
        "test_c0_bottom_rate_is_invalid_battery",
        "test_c0_gate_precedes_missing_lever_rows",
    ),
    # ---- 計算できない / INVALID_SCORER
    _m(
        "ms12 transport 失敗を ⊥ に畳む",
        _S,
        "    if any(s.raw is None for s in samples):\n",
        _OFF,
        "test_transport_failure_is_not_computed",
    ),
    _m(
        "ms13 certification 照合を削除",
        _S,
        "    if not load_certification(certification):\n",
        _OFF,
        "test_missing_certification_is_invalid_scorer",
        "test_stale_certification_is_invalid_scorer",
        "test_uncertified_harness_is_invalid_scorer",
    ),
    _m(
        "ms14 seed 照合を削除",
        _S,
        "        if s.seed != seed:\n",
        _OFF8,
        "test_wrong_seed_is_invalid_scorer",
    ),
    _m(
        "ms15 凍結 renderer との照合を削除",
        _S,
        "        if s.prompt_sha256 != sha:\n",
        _OFF8,
        "test_unfrozen_prompt_is_invalid_scorer",
    ),
    _m(
        "ms16 再 parse 照合を削除",
        _S,
        "        if s.raw is not None and s.parsed != parse_choice(s.raw):\n",
        _OFF8,
        "test_recorded_parse_mismatch_is_invalid_scorer",
    ),
    _m(
        "ms17 重複 sample の検出を削除",
        _S,
        "        if key in seen:\n",
        _OFF8,
        "test_duplicate_sample_is_invalid_scorer",
    ),
    _m(
        "ms18 想定外 key の検出を削除",
        _S,
        "        if key not in grid:\n",
        _OFF8,
        "test_unexpected_replicate_is_invalid_scorer",
    ),
    _m(
        "ms19 要求条件 (model / sampling) の照合を削除",
        _S,
        "    if dict(meta) != request_meta():\n",
        _OFF,
        "test_request_meta_mismatch_is_invalid_scorer",
    ),
    # ---- parse
    _m(
        "ms20 2 種以上の label で先頭を採る",
        _S,
        "    return found[0] if len(found) == 1 else None\n",
        "    return found[0] if found else None\n",
        "test_parse_two_labels_is_bottom",
    ),
    _m(
        "ms21 閉じていない think を許す",
        _S,
        '    if "<think" in text or "</think" in text:\n',
        _OFF,
        "test_unclosed_think_is_bottom",
    ),
    # ---- OC 模擬
    _m(
        "ms22 模擬から ⊥ gate を外す",
        _S,
        "    verdict = np.where(bottom_gate_ok(bot), verdict, VERDICT_INVALID_BATTERY)\n",
        "    verdict = np.where(True, verdict, VERDICT_INVALID_BATTERY)\n",
        "test_simulation_applies_bottom_gate",
    ),
    _m(
        "ms23 模擬の下限検定を τ でなく 0 に",
        _S,
        "        _flip_p(d - TAU, flips, exact),\n",
        "        _flip_p(d, flips, exact),\n",
        "test_plant_is_distinct_from_threshold",
    ),
    # ---- Codex review 反映分
    _m(
        "ms24 C0 先行の監査を削除",
        _S,
        "    if c0_calls and lever_calls and max(c0_calls) > min(lever_calls):\n",
        _OFF,
        "test_lever_before_c0_is_invalid_scorer",
    ),
    _m(
        "ms25 call_index の一意性検査を削除",
        _S,
        "    if len(set(calls)) != len(calls) or any(c < 0 for c in calls):\n",
        _OFF,
        "test_duplicate_call_index_is_invalid_scorer",
    ),
    _m(
        "ms26 int 欄の型検査を緩める (bool / float を通す)",
        _S,
        "        if type(obj[f]) is not int:\n",
        "        if not isinstance(obj[f], (int, float)):\n",
        "test_malformed_record_is_invalid_scorer",
    ),
    _m(
        "ms27 schema 違反を verdict 体系の外 (例外) に落とす",
        _S,
        "    except ValueError as exc:  # RecordError を含む\n",
        "    except KeyError as exc:\n",
        "test_malformed_record_is_invalid_scorer",
        "test_malformed_meta_is_invalid_scorer",
    ),
    _m(
        "ms28 think 除去を正規化の前に戻す",
        _S,
        '    text = unicodedata.normalize("NFKC", raw).lower()\n'
        '    text = _THINK_BLOCK.sub("", text)\n',
        '    text = _THINK_BLOCK.sub("", raw)\n'
        '    text = unicodedata.normalize("NFKC", text).lower()\n',
        "test_accepted",
    ),
    _m(
        "mb6  族内 signature 順の検査を削除",
        _B,
        "        if sa != sb:\n",
        _OFF8,
        "test_label_balance_detects_signature_order",
    ),
    # ---- battery
    _m(
        "mb1  Ω_q 位置の巡回を削除",
        _B,
        "        shift = (r + qi) % N_POSITIONS\n",
        "        shift = 0\n",
        "test_position_balance_requires_multiple_of_four",
        "test_battery_report_clean_at_frozen_r",
    ),
    _m(
        "mb2  A_rot の規則を A と同じに",
        _B,
        "        return {w: RULE_A[_next_weather(w)] for w in WEATHER}\n",
        "        return dict(RULE_A)\n",
        "test_four_arms_point_to_distinct_options",
        "test_rotation_rule_differs_only_in_mapping",
    ),
    _m(
        "mb3  Skill エントリ順を arm ごとに変える",
        _B,
        "    return [(sig, table[sig[0]]) for sig in lay.entry_order]\n",
        "    return [(sig, table[sig[0]]) for sig in sorted(lay.entry_order, key=lambda s: table[s[0]])]\n",
        "test_family_states_share_label_multiset",
    ),
    _m(
        "mb4  num_ctx が byte 予算を収めない",
        _B,
        "NUM_CTX: Final[int] = 4096",
        "NUM_CTX: Final[int] = 2048",
        "test_prompt_budget_is_static",
    ),
    _m(
        "mb5  C0 にも状態を入れる",
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
