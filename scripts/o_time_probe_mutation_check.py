#!/usr/bin/env python
"""候補 O_time (時期の評価) の変異試験 — 判定行を壊すと、意図した test が落ちるか (prereg §10、計測台 ADR §4.4).

``scripts/o_time_probe_battery.py`` (mb*)・``o_time_probe_fixtures.py`` (mx*)・``o_time_probe_scorer.py`` (ms*)・
``o_time_probe_sim.py`` (mz*)・``o_time_probe_pilot_gate.py`` (mp*)・``o_time_probe_manifest.py`` (mm*) の判定行を
1 つずつ壊し、``tests/test_o_time_probe/`` を実行する。枠組みは候補 G (``generalization_probe_mutation_check.py``)。

変異は 4 つ組 (名前・変異 (old → new)・期待診断 (落ちるべき test の集合)・理由) で登録する。判定は 3 通りに分けて報告する:

* 対照が落ちた: 無変異で test が緑でない → harness を止める (変異の判定をしない)。
* 変異が捕まらなかった: SURVIVED (test が緑のまま)。
* 変異は落ちたが理由が違う: WRONG_REASON (落ちた test に期待診断が無い) / COLLECTION_ERROR。KILLED に数えない。

anchor (置換前の文字列) は対象ファイルに 1 回だけ現れ、置換で内容が変わること (no-op を除く)。
等価変異 (意味を変えないので kill できない) は登録しない。判断して外したもの:

* ``log_capital`` の ``np.maximum(f, 0.0)``: λ ≤ cap と D ∈ [−1, 1] で因子は非負なので、浮動小数の誤差以外では等価。
* 見取り図の成分の並べ方 (向き × 書き方の順): ``decide`` は 4 成分がすべて正かだけを見るので、順に依らない。
* fixture の ``third_option`` が記録に無い行動の代わりに選択肢の先頭を選ぶ変異: どちらも札を読まないので C = 0 のまま。

meta-test (計測台 §4.4): 対象を複製ツリー (repo の外の一時 dir) に写し、検査関数を no-op に潰して、依存する
test が実際に落ちることを一度見る (``decide`` を常に INCONCLUSIVE に・``structure_violations`` を空に)。

変異は権威ファイル自体に当てる。対象ファイルは実行中だけ書き換わり、必ず原状復帰する (finally + sha256 照合。
Windows では強制終了すると finally が走らないので、止めない)。import する凍結物 (旧 Stage B scorer) は変異させない。
出力は certification が結び付く 6 ファイル・test・本 harness・manifest 検査の sha256、meta-test の結果、変異ごとの明細を記録する。

実行 (repo root から)::

    uv run python scripts/o_time_probe_mutation_check.py --out <certification.json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"
_B = _SCRIPTS / "o_time_probe_battery.py"
_X = _SCRIPTS / "o_time_probe_fixtures.py"
_S = _SCRIPTS / "o_time_probe_scorer.py"
_Z = _SCRIPTS / "o_time_probe_sim.py"
_P = _SCRIPTS / "o_time_probe_pilot_gate.py"
_M = _SCRIPTS / "o_time_probe_manifest.py"
_TESTS = "tests/test_o_time_probe"
_CERTIFIED = (
    "o_time_probe_battery.py",
    "o_time_probe_fixtures.py",
    "o_time_probe_scorer.py",
    "o_time_probe_sim.py",
    "o_time_probe_pilot_gate.py",
    "stage_b_scorer.py",
)
_TEST_FILES = (
    "__init__.py",
    "conftest.py",
    "test_battery.py",
    "test_fixtures.py",
    "test_scorer.py",
    "test_sim.py",
    "test_pilot_gate.py",
    "test_manifest.py",
)
# commit 済みの成果物と現在のコードの一致を見る test だけは、変異中は必ず落ちて生き残りを覆い隠すので外す
# (manifest の判定行は変異の対象にする)。
_DESELECT = f"{_TESTS}/test_manifest.py::test_committed_artifacts_are_bound"
_FAILED = re.compile(r"^FAILED (\S+?)(?:\[.*?\])?(?: - .*)?$")
_ERROR = re.compile(r"^ERROR (\S+?)(?:\[.*?\])?(?: - .*)?$")


@dataclass(frozen=True)
class Mutant:
    label: str
    target: pathlib.Path
    old: str
    new: str
    expect: frozenset[str]
    reason: str


def _m(
    label: str,
    target: pathlib.Path,
    old: str,
    new: str,
    expect: tuple[str, ...],
    reason: str,
) -> Mutant:
    return Mutant(label, target, old, new, frozenset(expect), reason)


_BCP = "test_battery_checks_pass"

MUTANTS: tuple[Mutant, ...] = (
    # ================================================================ battery
    _m(
        "mb01 第 2 の規則 = 第 1 の規則",
        _B,
        "return LABELS[fi][(i + 1) % 3]",
        "return LABELS[fi][i % 3]",
        ("test_rules_pinned", _BCP),
        "全部屋で 2 つの規則が同じ行動を指し、w と foil が一致する",
    ),
    _m(
        "mb02 記録に無い label = 第 1 の規則",
        _B,
        "return LABELS[fi][(i + 2) % 3]",
        "return LABELS[fi][i % 3]",
        ("test_rules_pinned", _BCP),
        "Ω の残り 1 つが foil と一致する",
    ),
    _m(
        "mb03 規則の列が日に依らない",
        _B,
        "first = (day == 1) == (arm in FWD)",
        "first = arm in FWD",
        ("test_rules_pinned", "test_state_rows_follow_daily_rule"),
        "2 日とも同じ規則になり、時期の違いが消える",
    ),
    _m(
        "mb04 規則の列が arm の向きに依らない (AB = BA)",
        _B,
        "first = (day == 1) == (arm in FWD)",
        "first = day == 1",
        ("test_rules_pinned", "test_pointed_is_newer_day"),
        "族の 2 arm が同じ列になり、差の源が消える",
    ),
    _m(
        "mb05 w と foil を入れ替える",
        _B,
        "return rule_on_day(arm, 2)[room], rule_on_day(arm, 1)[room]",
        "return rule_on_day(arm, 1)[room], rule_on_day(arm, 2)[room]",
        ("test_pointed_is_newer_day", "test_evaluate_newer_pass"),
        "推定量の向きが古い日になる",
    ),
    _m(
        "mb06 試行を 1 回に",
        _B,
        "for _ in range(TRIALS_PER_ACTION)",
        "for _ in range(1)",
        ("test_state_rows_follow_daily_rule", "test_exposure_is_shared_within_family"),
        "行の成功数が固定の文言 (成功 3) と合わない",
    ),
    _m(
        "mb07 aggregator が日をまたいで数える",
        _B,
        "(succ if ob.success else fail)[(ob.day, ob.room, ob.action)] += 1",
        "(succ if ob.success else fail)[(1, ob.room, ob.action)] += 1",
        ("test_aggregator_is_daily", "test_state_rows_follow_daily_rule"),
        "日をまたぐと成功と失敗が混じり、行が残らない",
    ),
    _m(
        "mb08 aggregator が失敗のある行も残す",
        _B,
        "if fail[(day, room, act)] == 0:",
        "if True:",
        ("test_aggregator_is_daily",),
        "失敗のある行動も成功行になる (日をまたぐ数え方で 2 行になる)",
    ),
    _m(
        "mb09 aggregator の 2 行の検査を外す",
        _B,
        "if room in rows:",
        "if False:",
        ("test_aggregator_rejects_two_rows",),
        "同じ日・部屋の 2 つの成功行を黙って上書きする",
    ),
    _m(
        "mb10 row_day の一意性の検査を緩める",
        _B,
        "if len(days) != 1:",
        "if not days:",
        ("test_row_day_requires_one_day",),
        "同じ label が 2 日に記録された状態を通す",
    ),
    _m(
        "mb11 並びが部屋に依らない",
        _B,
        "np.random.default_rng([LAYOUT_SEED, fi, i, r])",
        "np.random.default_rng([LAYOUT_SEED, fi, r])",
        ("test_entry_order_pinned_and_shared",),
        "単位の並びが部屋の間で共有され、凍結した並びと違う",
    ),
    _m(
        "mb12 表示順の回転が部屋に依らない",
        _B,
        "shift = (r + i) % N_POSITIONS",
        "shift = r % N_POSITIONS",
        ("test_option_order", "test_render_probe_text"),
        "凍結した表示順と違う",
    ),
    _m(
        "mb13 seed が部屋に依らない",
        _B,
        "10_000 * r + 100 * i + k",
        "10_000 * r + k",
        ("test_seed", _BCP),
        "部屋の間で seed を共有し、単位の独立の理想化が崩れる",
    ),
    _m(
        "mb14 seed の r の範囲の検査を外す",
        _B,
        "or not 0 <= r < 1000:",
        ":",
        ("test_seed",),
        "r ≥ 1000 で他の名前空間と交わる",
    ),
    _m(
        "mb15 masked が札の数字を伏せない",
        _B,
        "return MASK_DIGIT + text[1:]",
        "return text",
        ("test_masked_states", _BCP),
        "null pilot の masked が時期を見せる",
    ),
    _m(
        "mb16 行の文面から失敗数を外す",
        _B,
        "(成功 {n} / 失敗 0)",
        "(成功 {n})",
        ("test_render_row_text",),
        "凍結した行の文面と違う",
    ),
    _m(
        "mb17 M0 が古い日の行を描く",
        _B,
        "act, n = table[2][room]",
        "act, n = table[1][room]",
        ("test_m0_states", "test_pilot_clean_go"),
        "陽性対照の lookup が古い規則を指す",
    ),
    _m(
        "mb18 M0 の札が古い日",
        _B,
        "lines.append(render_row(tag(enc, 2), room, act, n))",
        "lines.append(render_row(tag(enc, 1), room, act, n))",
        ("test_m0_states",),
        "陽性対照の札が新しい日でない",
    ),
    _m(
        "mb19 masked の mode を無視する",
        _B,
        'masked=mode == "masked"',
        "masked=False",
        ("test_masked_states", _BCP),
        "masked の状態が本走と同じになる",
    ),
    _m(
        "mb20 probe の「今の状況」を変える",
        _B,
        'f"今の状況: {room} の部屋。',
        'f"状況: {room} の部屋。',
        ("test_render_probe_text",),
        "凍結した probe の文面と違う",
    ),
    _m(
        "mb21 族の検査を外す",
        _B,
        "if fi != unit.family:",
        "if False:",
        ("test_render_rejects_wrong_family",),
        "別の族の単位で描画できてしまう",
    ),
    _m(
        "mb22 単位の 4 呼び出しの順を変える",
        _B,
        "return tuple((arm, enc) for arm in FAMILIES[unit.family] for enc in ENCODINGS)",
        "return tuple((arm, enc) for enc in ENCODINGS for arm in FAMILIES[unit.family])",
        ("test_units_order",),
        "呼び出しの順の凍結と違う",
    ),
    _m(
        "mb23 mask_digits を no-op に",
        _B,
        'f"[{DIGIT_PLACEHOLDER}{TAGS[enc][day][1:]}]"',
        'f"[{TAGS[enc][day]}]"',
        ("test_layer1_holds", "test_mask_helpers", _BCP),
        "定理 1 の前提の検査が数字の違いで常に落ちる",
    ),
    _m(
        "mb24 mask_suffix を no-op に",
        _B,
        'f"[{t[:-1]}{SUFFIX_PLACEHOLDER}]"',
        'f"[{t}]"',
        ("test_layer2_holds", "test_mask_helpers", _BCP),
        "定理 2 の前提の検査が後ろの語の違いで常に落ちる",
    ),
    _m(
        "mb24b 定理の前提の検査を user の文面だけにする",
        _B,
        '[{**dict(m), "content": fn(m["content"])} for m in messages]',
        '[{"content": fn(m["content"])} for m in messages if m["role"] == "user"]',
        ("test_layer_checks_compare_the_whole_prompt",),
        "system・role・追加の message の差を見逃す (Codex HIGH-1)",
    ),
    _m(
        "mb25 既存の語の 4-gram の検査を外す",
        _B,
        "if char_ngrams(w) & prior:",
        "if False:",
        ("test_vocabulary_detects",),
        "既存の battery の語と字面を共有する語を通す",
    ),
    _m(
        "mb26 語の数字の検査を外す",
        _B,
        "if any(ch.isdigit() for ch in w):",
        "if False:",
        ("test_vocabulary_detects",),
        "数字を含む語 (札の数字と紛れる) を通す",
    ),
    _m(
        "mb27 規則の一致の検査を外す",
        _B,
        "if any(a == b for a, b in zip(firsts, seconds, strict=True)):",
        "if False:",
        ("test_rules_detect",),
        "2 つの規則が同じ行動を指す部屋を通す",
    ),
    _m(
        "mb28 aggregator と規則の照合を外す",
        _B,
        "if act != rule_on_day(arm, day)[room] or n != TRIALS_PER_ACTION:",
        "if n != TRIALS_PER_ACTION:",
        ("test_state_table_check_detects",),
        "規則と違う行を通す",
    ),
    _m(
        "mb29 多重集合の照合を外す",
        _B,
        "if ms[0] != ms[1]:",
        "if False:",
        ("test_multiset_detects",),
        "族の 2 状態の記録の集合が違っても通す (時期だけの違いが崩れる)",
    ),
    _m(
        "mb30 札の書き方の中の照合を外す",
        _B,
        "if t1[1:] != t2[1:] or t1[0] == t2[0] or t1[-1] != SUFFIX[enc]:",
        "if False:",
        ("test_tags_detect",),
        "2 日の札が数字以外でも違う書き方を通す",
    ),
    _m(
        "mb31 数字の向きの照合を反転",
        _B,
        'TAGS["ago"][2][0] < TAGS["ago"][1][0]',
        'TAGS["ago"][2][0] > TAGS["ago"][1][0]',
        ("test_tags_pinned", _BCP),
        "凍結した札 (ago は新しい日が小さい数) を拒否する",
    ),
    _m(
        "mb32 定理 1 の前提の検査を外す",
        _B,
        "if ma != mb:",
        "if False:",
        ("test_layer1_detects",),
        "2 arm の prompt が札の数字以外で違っても通す",
    ),
    _m(
        "mb33 定理 2 の前提の検査を外す",
        _B,
        "if mx != my:",
        "if False:",
        ("test_layer2_detects",),
        "書き方の対が後ろの語以外で違っても通す",
    ),
    _m(
        "mb34 定理 2 の対の組を取り違える",
        _B,
        "for x, y in ((fwd, bwd), (bwd, fwd)):",
        "for x, y in ((fwd, fwd), (bwd, bwd)):",
        ("test_layer2_holds", _BCP),
        "対の組を誤り、正しい設計を拒否する",
    ),
    _m(
        "mb35 非漏洩で arm 名を許す",
        _B,
        'allowed = {*ROOMS, *ACTIONS, "1", "2", "3", "0"}',
        'allowed = {*ROOMS, *ACTIONS, "1", "2", "3", "0", *LEVER_ARMS}',
        ("test_non_leakage_detects",),
        "arm 名が prompt に漏れても通す",
    ),
    _m(
        "mb36 R が 3 の倍数かの検査を外す",
        _B,
        "if r_count % N_POSITIONS:",
        "if False:",
        ("test_position_balance",),
        "表示位置の均衡が取れない R を通す",
    ),
    _m(
        "mb37 表示位置の均衡の検査を外す",
        _B,
        "                set(seen.values()) != {r_count // N_POSITIONS}\n"
        "                or len(seen) != N_POSITIONS**2\n",
        "                False\n",
        ("test_position_balance_detects",),
        "表示順が偏っても通す",
    ),
    _m(
        "mb38 byte 予算の検査を外す",
        _B,
        "if worst > MAX_PROMPT_BYTES:",
        "if False:",
        ("test_prompt_budget_detects",),
        "切り詰めが起こりうる prompt を通す",
    ),
    _m(
        "mb39 masked の 2 arm の同一性の検査を外す",
        _B,
        "if len(texts) != 1:",
        "if False:",
        ("test_masked_states_detect",),
        "masked の 2 arm の prompt が違っても通す",
    ),
    _m(
        "mb40 M0 の行の照合を外す",
        _B,
        "if set(lines) != want:",
        "if False:",
        ("test_m0_states_detect",),
        "M0 の行が新しい日の行でなくても通す",
    ),
    _m(
        "mb41 seed の名前空間の分離の検査を外す",
        _B,
        "if main & masked or main & m0 or masked & m0:",
        "if False:",
        ("test_seed_namespaces_detect",),
        "本走と pilot の seed が交わっても通す",
    ),
    # ================================================================ fixtures
    _m(
        "mx01 単位の d を fwd arm だけにする",
        _X,
        "row.append((s[0] + s[1]) / 2.0)",
        "row.append(float(s[0]))",
        (
            "test_fixture_gate_passes",
            "test_theorem1_digit_blind_policies_are_zero_per_unit",
        ),
        "族内の打ち消しが消え、札を見ない方策の C が 0 でなくなる",
    ),
    _m(
        "mx02 C を asc だけで計算する",
        _X,
        '"C": float(np.mean(d.mean(axis=1))),',
        '"C": float(np.mean(d[:, 0])),',
        ("test_fixture_gate_passes", "test_fixture_table_pinned"),
        "書き方の対の打ち消しが消え、字面の方策が gate を越える",
    ),
    _m(
        "mx03 foil を 0 に数える",
        _X,
        "    if choice == foil:\n        return -1",
        "    if choice == foil:\n        return 0",
        ("test_cell_score", "test_positive_controls"),
        "古い日に従う方策が C = 0 になる",
    ),
    _m(
        "mx04 文脈の札を取り違える",
        _X,
        "rows.append(Row(bat.tag(enc, day), room, table[day][room][0]))",
        "rows.append(Row(bat.tag(enc, 3 - day), room, table[day][room][0]))",
        ("test_context_matches_renderer", "test_positive_controls"),
        "fixture の文脈が renderer と違う",
    ),
    _m(
        "mx05 ago の新しさの読みを反転",
        _X,
        "return _digit(row) < _digit(other)",
        "return _digit(row) > _digit(other)",
        ("test_positive_controls",),
        "陽性対照が ago で古い日に従う",
    ),
    _m(
        "mx06 3 族の厳密な 0 の検査を外す",
        _X,
        'if v["family"] in GATED_FAMILIES and abs(v["C"]) > EXACT_ZERO',
        "if False",
        (
            "test_fixture_violations_detect_small_nonzero",
            "test_fixture_violations_detect",
        ),
        "定理で 0 のはずの方策が 0 でなくても通す",
    ),
    _m(
        "mx07 gate の閾値を外す",
        _X,
        'if abs(v["C"]) >= FIXTURE_GATE',
        'if abs(v["C"]) > 1.0',
        ("test_fixture_violations_detect",),
        "τ/4 を越える方策を通す",
    ),
    _m(
        "mx08 gate を τ/2 に",
        _X,
        "FIXTURE_GATE: Final[float] = TAU / 4.0",
        "FIXTURE_GATE: Final[float] = TAU / 2.0",
        ("test_fixture_gate_passes",),
        "凍結した gate (τ/4) と違う",
    ),
    _m(
        "mx09 登録方策を 1 つ外す",
        _X,
        '"digit_max": ("tag_literal", digit_rank("max")),',
        "",
        ("test_fixture_table_pinned",),
        "凍結した登録表と違う",
    ),
    _m(
        "mx10 大きい数の方策を反転",
        _X,
        'rows = sorted(_matching(ctx), key=_digit, reverse=order == "max")',
        'rows = sorted(_matching(ctx), key=_digit, reverse=order == "min")',
        ("test_fixture_table_pinned",),
        "方策の定義が名前と違う",
    ),
    _m(
        "mx11 辞書順の方策を反転",
        _X,
        'rows = sorted(_matching(ctx), key=lambda r: r.tag, reverse=order == "max")',
        'rows = sorted(_matching(ctx), key=lambda r: r.tag, reverse=order == "min")',
        ("test_fixture_table_pinned",),
        "方策の定義が名前と違う",
    ),
    _m(
        "mx12 passed を常に真に",
        _X,
        '"passed": worst < FIXTURE_GATE,',
        '"passed": True,',
        ("test_fixture_table_passed_flag",),
        "gate を越えた表を合格と記録する",
    ),
    _m(
        "mx13 厳密な 0 の対象から字面の方策を外す",
        _X,
        'GATED_FAMILIES: Final[tuple[str, ...]] = ("tag_blind", "tag_relative", "tag_literal")',
        'GATED_FAMILIES: Final[tuple[str, ...]] = ("tag_blind", "tag_relative")',
        ("test_fixture_violations_detect",),
        "定理 2 の対象の方策が 0 でなくても通す",
    ),
    _m(
        "mx14 大きい数が後の行だけの方策の位置を取り違える",
        _X,
        "if rows.index(big) == len(rows) - 1:",
        "if rows.index(big) == 0:",
        ("test_fixture_table_pinned",),
        "方策の定義が名前と違う",
    ),
    # ================================================================ scorer
    _m(
        "ms01 think ブロックを除かない",
        _S,
        'text = _THINK_BLOCK.sub(" ", text)',
        "text = text",
        ("test_parse_think_block",),
        "think の中の label を拾う",
    ),
    _m(
        "ms02 閉じない think を ⊥ にしない",
        _S,
        'if "<think" in text or "</think" in text:',
        "if False:",
        ("test_parse_unclosed_think",),
        "閉じない think の中の label を拾う",
    ),
    _m(
        "ms03 2 label を ⊥ にしない",
        _S,
        "if len(found) != 1:",
        "if not found:",
        ("test_parse_two_labels_is_bot",),
        "2 つの label を含む応答を最初の label にする",
    ),
    _m(
        "ms04 parse の前の単語境界を外す",
        _S,
        'r"(?<![a-z0-9])"',
        'r""',
        ("test_parse_word_boundary",),
        "語の一部の label を拾う",
    ),
    _m(
        "ms05 NFKC を外す",
        _S,
        'text = unicodedata.normalize("NFKC", raw).lower()',
        "text = raw.lower()",
        ("test_parse_basic",),
        "全角の label を ⊥ にする",
    ),
    _m(
        "ms06 category の w を foil に",
        _S,
        '        return "w"',
        '        return "foil"',
        ("test_category", "test_evaluate_newer_pass"),
        "新しい日の選択を foil に数える",
    ),
    _m(
        "ms07 category の other を oov に",
        _S,
        '        return "other"',
        '        return "oov"',
        ("test_category", "test_describe"),
        "記録に無い行動を語彙外に数える",
    ),
    _m(
        "ms08 セル得点の符号を足し算に",
        _S,
        '(category(c, arm, u.room) == "w") - (category(c, arm, u.room) == "foil")',
        '(category(c, arm, u.room) == "w") + (category(c, arm, u.room) == "foil")',
        ("test_evaluate_older_no_go", "test_evaluate_blind_no_go"),
        "foil を w と同じ向きに数える",
    ),
    _m(
        "ms09 D を asc だけに",
        _S,
        "out.append((d[0] + d[1]) / 2.0)",
        "out.append(d[0])",
        ("test_evaluate_literal_no_go",),
        "書き方の対の打ち消しが消え、字面の方策で C > 0",
    ),
    _m(
        "ms10 成分の並びを入れ替える",
        _S,
        "(dr, enc) for dr in bat.DIRECTIONS for enc in bat.ENCODINGS",
        "(dr, enc) for enc in bat.ENCODINGS for dr in bat.DIRECTIONS",
        ("test_components_order",),
        "成分の名前と値が対応しない",
    ),
    _m(
        "ms11 成分が向きを見ない",
        _S,
        "if bat.direction(arm) == dr and enc == e",
        "if enc == e",
        ("test_unit_scores_average_of_four", "test_evaluate_asc_only_not_pass"),
        "一方向だけの効果で 4 成分が正になる",
    ),
    _m(
        "ms12 ⊥ 率の分母を倍に",
        _S,
        "out.append(sum(c is None for c in cs) / len(cs))",
        "out.append(sum(c is None for c in cs) / (2 * len(cs)))",
        ("test_bottom_rates_per_arm",),
        "⊥ 率を半分に数える",
    ),
    _m(
        "ms13 CAP_PLUS を 1/(1−τ) に",
        _S,
        "CAP_PLUS: Final[float] = 1.0 / (1.0 + TAU)",
        "CAP_PLUS: Final[float] = 1.0 / (1.0 - TAU)",
        ("test_frozen_constants", "test_e_value_exact"),
        "因子が負になりうる λ を許す (有効性の証明が壊れる)",
    ),
    _m(
        "ms14 λ の混合を 1 点に",
        _S,
        "LAMBDA_FRACTIONS: Final[tuple[float, ...]] = (0.25, 0.5, 0.75, 1.0)",
        "LAMBDA_FRACTIONS: Final[tuple[float, ...]] = (1.0,)",
        ("test_frozen_constants", "test_e_value_exact"),
        "凍結した混合と違う",
    ),
    _m(
        "ms15 混合を最大にする",
        _S,
        "mixed = np.log(np.mean(np.exp(logs - safe), axis=-1)) + safe[..., 0]",
        "mixed = np.log(np.max(np.exp(logs - safe), axis=-1)) + safe[..., 0]",
        ("test_e_value_exact",),
        "λ の後選びで e-value が膨らむ (有効でない)",
    ),
    _m(
        "ms16 NO_GO 枝の符号を反転",
        _S,
        "log_e_value(TAU - d, CAP_MINUS),",
        "log_e_value(d - TAU, CAP_MINUS),",
        ("test_e_value_exact", "test_no_go_reachable"),
        "NO_GO 枝が C ≥ τ の帰無を棄却しない",
    ),
    _m(
        "ms17 PASS の閾値を厳しく (>)",
        _S,
        "passed = (np.asarray(log_e_plus) >= LOG_THRESHOLD) & comps_positive",
        "passed = (np.asarray(log_e_plus) > LOG_THRESHOLD) & comps_positive",
        ("test_decide_threshold",),
        "E⁺ = 1/α ちょうどを PASS にしない",
    ),
    _m(
        "ms18 成分の条件を ≥ 0 に",
        _S,
        "comps_positive = np.all(np.asarray(comps) > 0, axis=-1)",
        "comps_positive = np.all(np.asarray(comps) >= 0, axis=-1)",
        ("test_decide_requires_positive_components",),
        "動かない成分があっても PASS する",
    ),
    _m(
        "ms19 NO_GO の閾値を厳しく (>)",
        _S,
        "no_go = np.asarray(log_e_minus) >= LOG_THRESHOLD",
        "no_go = np.asarray(log_e_minus) > LOG_THRESHOLD",
        ("test_decide_threshold",),
        "E⁻ = 1/α ちょうどを NO_GO にしない",
    ),
    _m(
        "ms20 arm ごとの ⊥ の上限を外す",
        _S,
        "per_arm = np.all(bot <= bot_max, axis=-1)",
        "per_arm = np.all(bot <= 1.0, axis=-1)",
        ("test_bottom_gate", "test_evaluate_lever_bottom"),
        "⊥ の多い arm を通す",
    ),
    _m(
        "ms21 族内の ⊥ 差の上限を外す",
        _S,
        "family = np.all(np.stack(gaps, axis=-1) < BOT_FAMILY_GAP, axis=-1)",
        "family = np.all(np.stack(gaps, axis=-1) <= 1.0, axis=-1)",
        ("test_bottom_gate_family_gap",),
        "族内で ⊥ が偏っても通す",
    ),
    _m(
        "ms22 envelope を外す",
        _S,
        "return min(BOT_MAX, pilot_max_bottom + ENVELOPE_MARGIN)",
        "return BOT_MAX",
        ("test_envelope_bottom_max", "test_evaluate_envelope"),
        "pilot の雑音から外れた ⊥ 率を通す",
    ),
    _m(
        "ms23 certification の確認を外す",
        _S,
        "    if not certified:",
        "    if False:",
        ("test_evaluate_requires_certification",),
        "certify されていない判定コードで verdict を出す",
    ),
    _m(
        "ms24 battery の検査を外す",
        _S,
        "if bat.battery_violations(r_count):",
        "if False:",
        ("test_evaluate_battery_gate",),
        "前提の崩れた battery で verdict を出す",
    ),
    _m(
        "ms25 fixture gate を外す",
        _S,
        "if fx.fixture_violations(r_count):",
        "if False:",
        ("test_evaluate_fixture_gate",),
        "fixture gate を越えた設計で verdict を出す",
    ),
    _m(
        "ms26 meta の検査を外す",
        _S,
        "invalid += meta_violations(meta, reference_observed)",
        "invalid += []",
        ("test_evaluate_meta", "test_meta_observed"),
        "凍結と違う実行条件の記録で verdict を出す",
    ),
    _m(
        "ms27 記録の構造の検査を外す",
        _S,
        "invalid += structure_violations(samples, r_count, k_count)",
        "invalid += []",
        ("test_evaluate_structure",),
        "seed や prompt の違う記録で verdict を出す",
    ),
    _m(
        "ms28 transport 失敗を not_computed にしない",
        _S,
        "if any(s.raw is None for s in samples) or len(samples) != len(",
        "if len(samples) != len(",
        ("test_evaluate_transport_failure",),
        "欠けた応答を ⊥ として verdict を出す",
    ),
    _m(
        "ms29 ⊥ gate を外す",
        _S,
        "if not bool(bottom_gate_ok(lever_bot, bot_max)):",
        "if False:",
        ("test_evaluate_lever_bottom", "test_evaluate_envelope"),
        "⊥ の多い記録で verdict を出す",
    ),
    _m(
        "ms30 envelope を本走に使わない",
        _S,
        "bot_max = envelope_bottom_max(pilot_max_bottom)",
        "bot_max = BOT_MAX",
        ("test_evaluate_envelope",),
        "pilot の雑音の外の ⊥ 率を通す",
    ),
    _m(
        "ms31 meta の request の照合を外す",
        _S,
        'if meta["request"] != request_meta():',
        "if False:",
        ("test_evaluate_meta",),
        "凍結と違う decode 条件の記録を通す",
    ),
    _m(
        "ms32 観測環境の pilot との照合を外す",
        _S,
        "elif reference_observed is not None and dict(observed) != dict(reference_observed):",
        "elif False:",
        ("test_meta_observed",),
        "pilot と違うモデルの記録を通す",
    ),
    _m(
        "ms33 seed の照合を外す",
        _S,
        "        if s.seed != seed:",
        "        if False:",
        ("test_structure_seed", "test_evaluate_structure"),
        "凍結と違う seed の記録を通す",
    ),
    _m(
        "ms34 prompt の照合を外す",
        _S,
        "        if s.prompt_sha256 != sha:",
        "        if False:",
        ("test_structure_prompt", "test_structure_encoding_swapped"),
        "凍結と違う prompt の記録を通す",
    ),
    _m(
        "ms35 parse の照合を外す",
        _S,
        "if s.raw is not None and parse_choice(s.raw) != s.parsed:",
        "if False:",
        ("test_structure_parse",),
        "記録した parse と再 parse が違っても通す",
    ),
    _m(
        "ms36 重複の検査を外す",
        _S,
        "if len(set(keys)) != len(keys):",
        "if False:",
        ("test_structure_duplicate",),
        "同じセルの重複を通す",
    ),
    _m(
        "ms37 grid 外の検査を外す",
        _S,
        "if not set(keys) <= the_grid:",
        "if False:",
        ("test_structure_grid",),
        "凍結した grid の外の記録を通す",
    ),
    _m(
        "ms38 call_index の検査を外す",
        _S,
        "if len(set(idx)) != len(idx) or any(i < 0 for i in idx):",
        "if False:",
        ("test_structure_call_index",),
        "call_index の重複を通す",
    ),
    _m(
        "ms39 seed の名前空間を族に依らせない",
        _S,
        'ns = f"fam{unit.family}"',
        'ns = "fam0"',
        ("test_seed_shared_within_unit",),
        "族 1 の seed が凍結と違う",
    ),
    _m(
        "ms40 schema が bool を int に数える",
        _S,
        "if type(obj[f]) is not int:",
        "if not isinstance(obj[f], int):",
        ("test_schema_bool_is_rejected",),
        "true / false を 1 / 0 として通す",
    ),
    _m(
        "ms41 schema の欄の照合を外す",
        _S,
        "if not isinstance(obj, dict) or set(obj) != _FIELDS:",
        "if not isinstance(obj, dict):",
        ("test_schema_missing_field_and_bad_json",),
        "欄の欠けた記録を RecordError にしない",
    ),
    _m(
        "ms42 certification の全 KILLED を見ない",
        _S,
        'if not all(m.get("status") == "KILLED" for m in mutants):',
        "if False:",
        ("test_load_certification_requires_all_killed",),
        "生き残りのある certification を通す",
    ),
    _m(
        "ms43 certification の label の一意性を見ない",
        _S,
        "if len(set(labels)) != len(labels):",
        "if False:",
        ("test_load_certification_requires_all_killed",),
        "label の重複した certification を通す",
    ),
    _m(
        "ms44 certification の sha256 を見ない",
        _S,
        "return recorded == current",
        "return True",
        ("test_load_certification_detects_stale",),
        "古いコードの certification を通す",
    ),
    _m(
        "ms45 certification の空の明細を通す",
        _S,
        "if not isinstance(mutants, list) or not mutants:",
        "if not isinstance(mutants, list):",
        ("test_load_certification",),
        "変異 0 件の certification を通す",
    ),
    _m(
        "ms46 CLI が pilot の GO を確かめない",
        _S,
        'and gate.get("decision") == "GO"',
        'and gate.get("decision") in ("GO", "STOP")',
        ("test_cli_end_to_end",),
        "pilot が STOP でも本走の判定を出す",
    ),
    _m(
        "ms47 CLI が splitlines で行を割る",
        _S,
        'args.records.read_text(encoding="utf-8").split("\\n")',
        'args.records.read_text(encoding="utf-8").splitlines()',
        ("test_cli_end_to_end",),
        "U+2028 を含む応答で記録の行が割れる",
    ),
    _m(
        "ms48 結果の JSON を LF で書かない",
        _S,
        'with path.open("w", encoding="utf-8", newline="\\n") as fh:',
        'with path.open("w", encoding="utf-8") as fh:',
        ("test_cli_end_to_end",),
        "Windows で CRLF の結果を書く (G prereg BL-3)",
    ),
    _m(
        "ms49 τ を変える",
        _S,
        "TAU: Final[float] = 0.30",
        "TAU: Final[float] = 0.25",
        ("test_frozen_constants",),
        "凍結した τ と違う",
    ),
    _m(
        "ms50 記述の other_rate を oov に",
        _S,
        '"other_rate": cats.count("other") / len(cats)',
        '"other_rate": cats.count("oov") / len(cats)',
        ("test_describe",),
        "記録に無い行動の率を数え違える",
    ),
    # ================================================================ sim
    _m(
        "mz01 w と foil の index を入れ替える",
        _Z,
        "w_idx = np.stack([b_side, a_side], axis=-1)",
        "w_idx = np.stack([a_side, b_side], axis=-1)",
        ("test_design_indices", "test_sim_power_and_null"),
        "模擬の向きが凍結した推定量と逆",
    ),
    _m(
        "mz02 表示先頭の index が部屋に依らない",
        _Z,
        "pos0 = np.array([(u.replicate + u.room) % bat.N_POSITIONS for u in us])",
        "pos0 = np.array([u.replicate % bat.N_POSITIONS for u in us])",
        ("test_design_indices",),
        "position_skew の base が凍結した表示順と違う",
    ),
    _m(
        "mz03 時系列の表示の判定を反転",
        _Z,
        "a_first.append(pa < pb)",
        "a_first.append(pa > pb)",
        ("test_a_first_matches_layout",),
        "時系列の表示でだけ評価する形が逆の arm に掛かる",
    ),
    _m(
        "mz04 label_skew の対象を B 側に",
        _Z,
        'target = dz.a_side if base == "label_skew" else dz.position0',
        'target = dz.b_side if base == "label_skew" else dz.position0',
        ("test_base_probs",),
        "事前偏りの base が登録と違う",
    ),
    _m(
        "mz05 asc だけの形を ago に",
        _Z,
        "lam[0, 0, 0, 0] = min(1.0, 2.0 * t)",
        "lam[0, 0, 1, 0] = min(1.0, 2.0 * t)",
        ("test_asc_only_and_chrono_only",),
        "書き方の集中の形が登録と違う",
    ),
    _m(
        "mz06 時系列の arm を入れ替える",
        _Z,
        "return np.stack([dz.a_first, ~dz.a_first], axis=-1).astype(float)",
        "return np.stack([~dz.a_first, dz.a_first], axis=-1).astype(float)",
        ("test_asc_only_and_chrono_only",),
        "時系列の表示でだけ評価する形が逆の arm に掛かる",
    ),
    _m(
        "mz06b 時系列の形を較正しない (注入量 2t に戻す)",
        _Z,
        "lam = min(1.0, t / chrono_factor(dz, nu.base))",
        "lam = min(1.0, 2.0 * t)",
        ("test_chrono_only_is_calibrated_under_skewed_base",),
        "偏った base の下で E[C] が目標からずれる (Codex HIGH-3)",
    ),
    _m(
        "mz06c 較正係数で g を無視する",
        _Z,
        "return float(np.mean(chrono_mask(dz) * (1.0 - base_gap(dz, base))))",
        "return float(np.mean(chrono_mask(dz)))",
        (
            "test_chrono_only_is_calibrated_under_skewed_base",
            "test_registered_reach_matches_the_sim",
        ),
        "偏った base の残りの得点を較正に入れない",
    ),
    _m(
        "mz06d 較正の許容を外す",
        _Z,
        'abs(p["realized_C"] - row["target_C"]) <= CALIBRATION_TOL',
        'abs(p["realized_C"] - row["target_C"]) <= 1.0',
        ("test_judge_r_calibration",),
        "目標からずれた模擬を健全と記録する",
    ),
    _m(
        "mz06e 診断の帯を条件 4 に数える",
        _Z,
        'if row["kind"] == "band_diag":',
        'if row["kind"] == "unused":',
        ("test_judge_r_flags", "test_band_diag_points"),
        "条件 4 から外した点で選定が決まる (DU-3 と違う)",
    ),
    _m(
        "mz07 部屋の集中の境界を変える",
        _Z,
        "on = (dz.unit_room < k).astype(float)",
        "on = (dz.unit_room <= k).astype(float)",
        ("test_sparse_reach",),
        "集中の形の部屋の数が登録と違う",
    ),
    _m(
        "mz08 arm × 単位の全か無かを書き方ごとに",
        _Z,
        "return _cells((rng.random((n, n_u, 1, 2)) < t).astype(float), n, n_u)",
        "return _cells((rng.random((n, n_u, 2, 2)) < t).astype(float), n, n_u)",
        ("test_aon_arm_unit_shape",),
        "形が登録 (書き方を通じて共通) と違う",
    ),
    _m(
        "mz09 項目の値の端数を切り上げる",
        _Z,
        "k = int(math.floor(total + 1e-12))",
        "k = int(math.ceil(total))",
        ("test_item_values_stay_in_range",),
        "項目の λ が [0, 1] の外に出る",
    ),
    _m(
        "mz10 逆向きの項目を 1 つに",
        _Z,
        "n_rev = round(N_ITEMS * REVERSE_FRACTION)",
        "n_rev = 1",
        ("test_item_pattern_exact_mean",),
        "逆向きの形の割合が登録 (1/6) と違う",
    ),
    _m(
        "mz11 crn を単位の中で共有しない",
        _Z,
        "u = np.broadcast_to(rng.random((*shape[:2], 1, 1)), shape)",
        "u = rng.random(shape)",
        ("test_crn_shares_randomness_within_the_unit", "test_crn_null_exact_zero"),
        "seed の共有の写しになっていない",
    ),
    _m(
        "mz12 anti を crn に",
        _Z,
        "u = np.concatenate([u0, 1.0 - u0], axis=-1)",
        "u = np.concatenate([u0, u0], axis=-1)",
        ("test_crn_shares_randomness_within_the_unit",),
        "逆向きの結合が登録と違う",
    ),
    _m(
        "mz13 ⊥ のセルの得点を 0 にしない",
        _Z,
        "score = np.where(bot, 0.0, score)",
        "score = score + 0.0 * bot",
        ("test_sim_calibration",),
        "⊥ のセルを w / foil に数え、較正がずれる",
    ),
    _m(
        "mz14 D を asc だけに",
        _Z,
        "d = score.mean(axis=(2, 3))",
        "d = score[:, :, 0, :].mean(axis=2)",
        ("test_asc_only_and_chrono_only",),
        "書き方の対の平均が登録と違う",
    ),
    _m(
        "mz15 模擬で ⊥ gate を外す",
        _Z,
        "verdict = np.where(sc.bottom_gate_ok(botr), verdict, sc.VERDICT_INVALID_BATTERY)",
        "verdict = verdict",
        ("test_sim_bottom_gate",),
        "凍結した判定 (⊥ gate) と違う",
    ),
    _m(
        "mz16 選定を最小の R に",
        _Z,
        'return {"selected_R": max(ok), "door_close": False}',
        'return {"selected_R": min(ok), "door_close": False}',
        ("test_select_is_the_largest_passing_candidate",),
        "選定規則 (4 条件を満たす最大) と違う",
    ),
    _m(
        "mz17 選定が帯の条件を見ない",
        _Z,
        '        and res["band_ok"]\n',
        "",
        ("test_select_is_the_largest_passing_candidate",),
        "決着しない確率の条件 (読み 5) を無視する",
    ),
    _m(
        "mz17b 選定が較正を見ない",
        _Z,
        '        and res["calibrated"]\n',
        "",
        ("test_select_is_the_largest_passing_candidate",),
        "較正の崩れた模擬で R を選ぶ",
    ),
    _m(
        "mz18 帯の条件を外す",
        _Z,
        'band_ok &= row["value"] <= UNDECIDED_MAX',
        'band_ok &= row["value"] <= 1.0',
        ("test_judge_r_flags",),
        "決着しない確率が大きくても帯を合格にする",
    ),
    _m(
        "mz19 帯の値から NO_GO を引かない",
        _Z,
        "                np.mean([1.0 - p[sc.VERDICT_PASS] - p[sc.VERDICT_ABSENT] for p in ps])\n"
        "            )\n"
        "            band_ok &=",
        "                np.mean([1.0 - p[sc.VERDICT_PASS] for p in ps])\n"
        "            )\n"
        "            band_ok &=",
        ("test_judge_r_flags",),
        "NO_GO も決着しないに数える",
    ),
    _m(
        "mz20 power の条件を外す",
        _Z,
        'power_ok &= row["value"] >= POWER_TARGET',
        'power_ok &= row["value"] >= 0.0',
        ("test_judge_r_flags",),
        "2τ で power 0.8 に届かない R を選ぶ",
    ),
    _m(
        "mz21 NO_GO の power の条件を外す",
        _Z,
        'no_go_ok &= row["value"] >= POWER_TARGET',
        'no_go_ok &= row["value"] >= 0.0',
        ("test_judge_r_flags",),
        "効果 0 で NO_GO に届かない R を選ぶ",
    ),
    _m(
        "mz22 size の閾値を 1 つ緩める",
        _Z,
        'size_ok = all(round(r["value"] * N_SIM_SIZE) <= x for r in size_rows)',
        'size_ok = all(round(r["value"] * N_SIM_SIZE) <= x + 1 for r in size_rows)',
        ("test_judge_r_flags",),
        "size の閾値を越える R を選ぶ",
    ),
    _m(
        "mz23 二項の閾値に多重性を入れない",
        _Z,
        "level = MC_FWER / n_checks",
        "level = MC_FWER",
        ("test_size_threshold_is_exact_binomial",),
        "点の数に応じた誤棄却の制御をしない",
    ),
    _m(
        "mz24 境目の補間を外す",
        _Z,
        "return c0 + (POWER_TARGET - p0) * (c1 - c0) / (p1 - p0)",
        "return c1",
        ("test_boundary",),
        "境目を格子の点で読む (memory feedback_boundary_from_sweep_not_grid)",
    ),
    _m(
        "mz25 下がる境目の補間を外す",
        _Z,
        "return c0 + (p0 - POWER_TARGET) * (c1 - c0) / (p0 - p1)",
        "return c0",
        ("test_boundary",),
        "NO_GO の境目を格子の点で読む",
    ),
    _m(
        "mz26 最有利行が 2τ の点を見ない",
        _Z,
        'and abs(r["target_C"] - sc.DELTA_PLANT) < 1e-9',
        "and True",
        ("test_most_favorable_requires_the_2tau_point",),
        "2τ 以外の点の power で door-close を外す",
    ),
    _m(
        "mz27 最有利行の結合を取り違える",
        _Z,
        "== (FAVORABLE.base, FAVORABLE.bot, FAVORABLE.coupling)",
        '== (FAVORABLE.base, FAVORABLE.bot, "indep")',
        ("test_most_favorable_requires_the_2tau_point",),
        "最も有利な行でない行で判定する",
    ),
    _m(
        "mz28 帯の幅を変える",
        _Z,
        "BAND_DELTA: Final[float] = 0.05",
        "BAND_DELTA: Final[float] = 0.1",
        ("test_band_points",),
        "帯の点が登録 (τ ± 0.05) と違う",
    ),
    _m(
        "mz29 帯を crn 以外にも",
        _Z,
        'if nu.coupling == "crn" and nu.base in BAND_BASES',
        'if nu.coupling != "anti" and nu.base in BAND_BASES',
        ("test_band_points",),
        "帯の攪乱点が登録と違う",
    ),
    _m(
        "mz29b 帯に label_skew を戻す",
        _Z,
        'BAND_BASES: Final[tuple[str, ...]] = ("uniform", "position_skew")',
        'BAND_BASES: Final[tuple[str, ...]] = ("uniform", "position_skew", "label_skew")',
        ("test_band_points",),
        "条件 4 の攪乱点が登録 (DU-3) と違う",
    ),
    _m(
        "mz30弱い null を size の点から外す",
        _Z,
        'pts.append(("weak_null", 0.0, "pass"))',
        "pass",
        ("test_size_points_cover_forms",),
        "帰無の領域の点が欠ける",
    ),
    _m(
        "mz31 R の候補を変える",
        _Z,
        "R_CANDIDATES: Final[tuple[int, ...]] = (96, 192, 288)",
        "R_CANDIDATES: Final[tuple[int, ...]] = (96, 192)",
        ("test_select_is_the_largest_passing_candidate",),
        "凍結した候補と違う",
    ),
    _m(
        "mz32 呼び出しの数を 2 倍で数える",
        _Z,
        '"calls": len(bat.units(r_count)) * 4 * sc.FROZEN_K,',
        '"calls": len(bat.units(r_count)) * 2 * sc.FROZEN_K,',
        ("test_judge_r_flags",),
        "単位あたり 4 呼び出しの設計と違う",
    ),
    _m(
        "mz33 対数オッズを foil に足す",
        _Z,
        "np.put_along_axis(boost, dz.w_idx[..., None], beta, axis=-1)",
        "np.put_along_axis(boost, dz.foil_idx[..., None], beta, axis=-1)",
        ("test_logodds_calibration",),
        "対数オッズの形の向きが逆",
    ),
    # ================================================================ pilot gate
    _m(
        "mp01 pilot の seed の名前空間を masked に固定",
        _P,
        'ns = f"{mode}_fam{unit.family}"',
        'ns = f"masked_fam{unit.family}"',
        ("test_expected_uses_the_pilot_namespaces",),
        "M0 の seed が凍結と違う",
    ),
    _m(
        "mp02 pilot の prompt を本走の mode で描く",
        _P,
        "msgs = bat.render_messages(lever, enc, unit, mode)",
        'msgs = bat.render_messages(lever, enc, unit, "main")',
        ("test_expected_uses_the_pilot_namespaces",),
        "masked と M0 の prompt が凍結と違う",
    ),
    _m(
        "mp03 pilot の grid から M0 を外す",
        _P,
        "for arms in (MASKED_ARMS, M0_ARMS):",
        "for arms in (MASKED_ARMS,):",
        ("test_pilot_grid_size",),
        "陽性対照の腕が計画から抜ける",
    ),
    _m(
        "mp04 pilot の seed の照合を外す",
        _P,
        "        if s.seed != seed:",
        "        if False:",
        ("test_pilot_records_stop",),
        "凍結と違う seed の pilot の記録を通す",
    ),
    _m(
        "mp05 pilot の prompt の照合を外す",
        _P,
        "        if s.prompt_sha256 != sha:",
        "        if False:",
        ("test_structure_checks",),
        "凍結と違う prompt の pilot の記録を通す",
    ),
    _m(
        "mp06 pilot の重複の検査を外す",
        _P,
        "if len(set(keys)) != len(keys):",
        "if False:",
        ("test_structure_checks",),
        "重複した pilot の記録を通す",
    ),
    _m(
        "mp07 pilot の grid 外の検査を外す",
        _P,
        "if not set(keys) <= grid:",
        "if False:",
        ("test_structure_checks",),
        "grid の外の pilot の記録を通す",
    ),
    _m(
        "mp08 cell_scores が mode を分けない",
        _P,
        "        if m != mode:\n            continue",
        "        if False:\n            continue",
        ("test_cell_scores_shapes",),
        "masked と M0 の記録が混じる",
    ),
    _m(
        "mp09 ⊥ 率を反転",
        _P,
        "1.0 - nb[fi, ..., ai].mean()",
        "nb[fi, ..., ai].mean()",
        ("test_pilot_clean_go",),
        "⊥ でない率を ⊥ 率として扱う",
    ),
    _m(
        "mp10 M0 を常に合格に",
        _P,
        '"passed": verdict == sc.VERDICT_PASS,',
        '"passed": True,',
        ("test_pilot_m0_stop",),
        "lookup が動かなくても本走を起こす",
    ),
    _m(
        "mp11 M0 の成分の条件を外す",
        _P,
        "comps = components(x)",
        "comps = np.ones(4)",
        ("test_pilot_m0_requires_components",),
        "凍結した PASS の規則 (4 成分) と違う",
    ),
    _m(
        "mp12 M0 の STOP を外す",
        _P,
        'if not m0["passed"]:',
        "if False:",
        ("test_pilot_m0_stop", "test_pilot_m0_requires_components"),
        "M0 の陽性対照が失敗しても本走を起こす",
    ),
    _m(
        "mp13 envelope の STOP を外す",
        _P,
        "if not bool(sc.bottom_gate_ok(bot)):",
        "if False:",
        ("test_pilot_envelope",),
        "⊥ の多い null で本走を起こす",
    ),
    _m(
        "mp14 不一致率を 0 に",
        _P,
        "return sum(a != b for a, b in pairs) / len(pairs)",
        "return 0.0",
        ("test_discordance",),
        "決定性の理想化の監査が恒真になる",
    ),
    _m(
        "mp15 foil の注入の向きを w に",
        _P,
        "return min(1.0, max(0.0, lam)), -1",
        "return min(1.0, max(0.0, lam)), 1",
        ("test_injection_calibrates",),
        "目標が null より小さいときに逆向きに注入する",
    ),
    _m(
        "mp16 層別の再標本化で回転を見ない",
        _P,
        "if (bat.PILOT_R0 + rp + i) % bat.N_POSITIONS == shift",
        "if True",
        ("test_strata_keep_the_rotation",),
        "本走の表示位置の割付を保たない",
    ),
    _m(
        "mp17 ⊥ のセルにも注入する",
        _P,
        "hit = (rng.random(xs.shape) < lam) & (nbs > 0)",
        "hit = rng.random(xs.shape) < lam",
        ("test_injection_skips_bot",),
        "較正 (⊥ でないセルの割合で λ を決める) とずれる",
    ),
    _m(
        "mp18 較正の許容を外す",
        _P,
        'abs(o["realized_C"] - t) < CALIBRATION_TOL',
        'abs(o["realized_C"] - t) < 1.0',
        ("test_oc_conditions_each_matter",),
        "目標から外れた注入を合格にする",
    ),
    _m(
        "mp19 OC の PASS の power を外す",
        _P,
        '"power_pass": at_plant["pass"] >= POWER_TARGET,',
        '"power_pass": at_plant["pass"] >= 0.0,',
        ("test_oc_conditions_each_matter",),
        "2τ で power が足りなくても GO",
    ),
    _m(
        "mp20 OC の NO_GO の power を外す",
        _P,
        '"power_no_go": at_zero["no_go"] >= POWER_TARGET,',
        '"power_no_go": at_zero["no_go"] >= 0.0,',
        ("test_oc_conditions_each_matter",),
        "効果 0 で NO_GO に届かなくても GO",
    ),
    _m(
        "mp21 OC の PASS の size を外す",
        _P,
        '"size_pass": at_tau["pass"] <= cap,',
        '"size_pass": at_tau["pass"] <= 1.0,',
        ("test_oc_conditions_each_matter",),
        "τ で PASS の率が大きくても GO",
    ),
    _m(
        "mp22 OC の NO_GO の size を外す",
        _P,
        '"size_no_go": at_tau["no_go"] <= cap,',
        '"size_no_go": at_tau["no_go"] <= 1.0,',
        ("test_oc_conditions_each_matter",),
        "τ で NO_GO の率が大きくても GO",
    ),
    _m(
        "mp23 OC の合否を常に合格に",
        _P,
        '"ok": all(checks.values()),',
        '"ok": True,',
        ("test_oc_for_r_uses_the_checks",),
        "条件を満たさなくても GO",
    ),
    _m(
        "mp24 OC の size の閾値の点の数を 1 に",
        _P,
        "cap = size_rate_cap(N_OC_SIZE_CHECKS)",
        "cap = size_rate_cap(1)",
        ("test_oc_for_r_uses_the_checks",),
        "登録した点の数 (2) の多重性と違う",
    ),
    _m(
        "mp25 GO の R を記録しない",
        _P,
        "decision=DECISION_GO, R=selected_r,",
        "decision=DECISION_GO, R=None,",
        ("test_pilot_clean_go",),
        "本走が読む R が欠ける",
    ),
    _m(
        "mp26 power の STOP を GO に",
        _P,
        'out.update(decision=DECISION_STOP, reasons=["power"], oc=oc)',
        'out.update(decision=DECISION_GO, reasons=["power"], oc=oc)',
        ("test_pilot_stop_on_power",),
        "検出力の無い設計で本走を起こす",
    ),
    _m(
        "mp27 pilot の transport 失敗を見ない",
        _P,
        "if any(s.raw is None for s in samples) or len(samples) != len(pilot_grid()):",
        "if len(samples) != len(pilot_grid()):",
        ("test_pilot_not_computed",),
        "欠けた応答を ⊥ として判定する",
    ),
    _m(
        "mp28 pilot の certification の確認を外す",
        _P,
        "    if not certified:",
        "    if False:",
        ("test_pilot_records_stop", "test_cli_end_to_end"),
        "certify されていない判定コードで GO を出す",
    ),
    _m(
        "mp29 見取り図の選定の確認を外す",
        _P,
        "    if selected_r is None:",
        "    if False:",
        ("test_pilot_records_stop",),
        "見取り図が door-close でも pilot を判定する",
    ),
    _m(
        "mp30 CLI が bool の R を受け入れる",
        _P,
        "selected_r=selected if type(selected) is int else None,",
        "selected_r=selected,",
        ("test_cli_end_to_end",),
        "JSON の true を R として扱う",
    ),
    _m(
        "mp31 pilot の meta の検査を外す",
        _P,
        "invalid += sc.meta_violations(meta)",
        "invalid += []",
        ("test_pilot_meta_stop",),
        "凍結と違う実行条件の pilot を通す",
    ),
    # ================================================================ manifest
    _m(
        "mm01 改変の検出を外す",
        _M,
        "elif sha256(p) != want:",
        "elif False:",
        ("test_manifest_detects_changed_and_missing_files",),
        "改変されたファイルを通す",
    ),
    _m(
        "mm02 欠けの検出を外す",
        _M,
        '        if not p.is_file():\n            out.append(f"{f}: missing")',
        '        if False:\n            out.append(f"{f}: missing")',
        ("test_manifest_detects_changed_and_missing_files",),
        "欠けたファイルで落ちる (例外) か通す",
    ),
    _m(
        "mm03 第 1 段の prereg の照合を外す",
        _M,
        'if sealed.get("prereg_body_sha256") != body:',
        "if False:",
        ("test_stage1_seal_allows_only_the_status_line",),
        "第 1 段の後に prereg の本文が変わっても通す",
    ),
    _m(
        "mm04 status 行を正規化しない",
        _M,
        'lines[i] = STATUS_PREFIX + "<SEALED>"',
        "lines[i] = line",
        (
            "test_prereg_body_sha256_ignores_only_the_status_line",
            "test_stage1_seal_allows_only_the_status_line",
        ),
        "status 行の変更も本文の変更として拒否する",
    ),
    _m(
        "mm05 第 1 段の封印の対象の集合を見ない",
        _M,
        "if not isinstance(files, dict) or set(files) != set(FROZEN_FILES):",
        "if not isinstance(files, dict):",
        ("test_stage1_seal_file_set",),
        "対象の欠けた封印を通す",
    ),
    _m(
        "mm06 期待した test で落ちたかを見ない",
        _M,
        "return _strs(failed) and _strs(expect) and bool(set(failed) & set(expect))",
        "return _strs(failed) and _strs(expect)",
        ("test_certification_requires_the_expected_failure",),
        "違う理由の失敗を KILLED に数える",
    ),
    _m(
        "mm07 登録の label の重複を通す",
        _M,
        "if not _name(label) or label in want:",
        "if not _name(label):",
        ("test_registries_must_be_well_formed",),
        "後の登録が前を消し、一対一にならない",
    ),
    _m(
        "mm07b 空白だけの名前を通す",
        _M,
        "return isinstance(x, str) and bool(x.strip())",
        "return isinstance(x, str)",
        ("test_registry_rejects_empty_names",),
        "空の label・test 名を登録として受け入れる (Codex LOW-6)",
    ),
    _m(
        "mm08 空の期待集合を通す",
        _M,
        "if not isinstance(expect, (list, tuple, set, frozenset)) or not expect:",
        "if not isinstance(expect, (list, tuple, set, frozenset)):",
        ("test_registries_must_be_well_formed",),
        "失敗 0 でも成り立つ登録を通す",
    ),
    _m(
        "mm09 meta-test の状態と期待集合を見ない",
        _M,
        'm.get("status") != "FAILED_AS_EXPECTED"',
        "False",
        ("test_meta_test_must_match_the_registered_cases",),
        "期待どおりに落ちていない meta-test を通す",
    ),
    _m(
        "mm10 meta-test の期待集合の部分集合を見ない",
        _M,
        "if not _strs(failed) or not set(expect) <= set(failed):",
        "if not _strs(failed):",
        ("test_meta_test_must_match_the_registered_cases",),
        "期待集合の一部しか落ちていない meta-test を通す",
    ),
    _m(
        "mm11 meta-test の label の重複を通す",
        _M,
        "if len(set(labels)) != len(labels) or set(labels) != set(want):",
        "if set(labels) != set(want):",
        ("test_meta_test_must_match_the_registered_cases",),
        "同じケースの重複を通す",
    ),
    _m(
        "mm12 certification の all_killed を見ない",
        _M,
        '    if cert.get("all_killed") is not True:\n        out.append("certification: not all',
        '    if False:\n        out.append("certification: not all',
        ("test_certification_binding",),
        "全 KILLED でない certification を通す",
    ),
    _m(
        "mm13 certification のコードの sha256 を見ない",
        _M,
        'if cert.get("target_sha256") != certified_sha256(root):',
        "if False:",
        ("test_certification_binding",),
        "古いコードの certification を通す",
    ),
    _m(
        "mm14 certification の test の sha256 を見ない",
        _M,
        'if cert.get("tests_sha256") != tests_sha256(root):',
        "if False:",
        ("test_certification_binding",),
        "古い test の certification を通す",
    ),
    _m(
        "mm15 certification の harness の sha256 を見ない",
        _M,
        'if cert.get("harness_sha256") != harness_sha256(root):',
        "if False:",
        ("test_certification_binding",),
        "古い harness の certification を通す",
    ),
    _m(
        "mm16 certification の manifest 検査の sha256 を見ない",
        _M,
        'if cert.get("manifest_sha256") != sha256(root / SELF):',
        "if False:",
        ("test_certification_binding",),
        "古い manifest 検査の certification を通す",
    ),
    _m(
        "mm17 登録変異との一致を見ない",
        _M,
        "if want is None or len(rows) != len(want) or got != want:",
        "if want is None:",
        ("test_certification_binding",),
        "変異の欠けた certification を通す",
    ),
    _m(
        "mm18 変異の行の KILLED を見ない",
        _M,
        'if any(not isinstance(x, dict) or x.get("status") != "KILLED" for x in rows):',
        "if False:",
        ("test_certification_binding",),
        "生き残りの行を通す",
    ),
    _m(
        "mm19 帯の点を片側に",
        _M,
        "for target in (0.25, 0.35):",
        "for target in (0.25,):",
        ("test_expected_points_match_the_sim_plan",),
        "条件 4 の点の一部を要求しない",
    ),
    _m(
        "mm20 行の値の照合を外す",
        _M,
        'if not _close(v, _num(x["value"])):',
        "if False:",
        ("test_sketch_recheck_recomputes_flags_and_values",),
        "per_seed と合わない値を通す",
    ),
    _m(
        "mm21 帯の条件の再計算を外す",
        _M,
        '"band_ok": all(v <= 0.2 + 1e-12 for v in values.get("band", [])),',
        '"band_ok": True,',
        ("test_sketch_recheck_band",),
        "帯の不合格を合格と記録しても通す",
    ),
    _m(
        "mm22 size の閾値を 1 つ緩める",
        _M,
        '"size_ok": all(round(v * REGISTERED_N_SIM_SIZE) <= x_max for v in sizes),',
        '"size_ok": all(round(v * REGISTERED_N_SIM_SIZE) <= x_max + 1 for v in sizes),',
        ("test_sketch_recheck_size_threshold_boundary",),
        "size の閾値を越える R を合格とする",
    ),
    _m(
        "mm23 power の条件の再計算を外す",
        _M,
        '"power_ok": all(v >= POWER_TARGET for v in values.get("power_pass", [])),',
        '"power_ok": True,',
        ("test_sketch_recheck_power_flags",),
        "power の不足を合格と記録しても通す",
    ),
    _m(
        "mm24 NO_GO の power の条件の再計算を外す",
        _M,
        '"no_go_ok": all(v >= POWER_TARGET for v in values.get("power_no_go", [])),',
        '"no_go_ok": True,',
        ("test_sketch_recheck_power_flags",),
        "NO_GO の power の不足を合格と記録しても通す",
    ),
    _m(
        "mm25 帯の値から NO_GO を引かない",
        _M,
        "sum(1.0 - p[sc.VERDICT_PASS] - p[sc.VERDICT_ABSENT] for p in per_seed) / n",
        "sum(1.0 - p[sc.VERDICT_PASS] for p in per_seed) / n",
        ("test_sketch_recheck_accepts_a_consistent_sketch",),
        "決着しない確率を誤って再計算する",
    ),
    _m(
        "mm26 率の合計の検査を外す",
        _M,
        "if abs(sum(vals) - 1.0) > 1e-9:",
        "if False:",
        ("test_sketch_recheck_rejects_invalid_rates_and_row_r",),
        "合計が 1 でない率を通す",
    ),
    _m(
        "mm27 率の格子の検査を外す",
        _M,
        "if not all(abs(v * n_sims - round(v * n_sims)) < 1e-6 for v in vals):",
        "if False:",
        ("test_sketch_recheck_rejects_invalid_rates_and_row_r",),
        "MC の回数で作れない率を通す",
    ),
    _m(
        "mm28 率の範囲の検査を外す",
        _M,
        "if not all(math.isfinite(v) and 0.0 <= v <= 1.0 for v in vals):",
        "if False:",
        ("test_sketch_recheck_rejects_invalid_rates_and_row_r",),
        "[0, 1] の外の率を通す",
    ),
    _m(
        "mm29 bool を数値に数える",
        _M,
        "if isinstance(x, (int, float)) and not isinstance(x, bool):",
        "if isinstance(x, (int, float)):",
        ("test_sketch_recheck_rejects_booleans",),
        "JSON の true / false を 1 / 0 として通す",
    ),
    _m(
        "mm30 設定の照合で型を見ない",
        _M,
        "return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)",
        "return a == b",
        ("test_sketch_recheck_rejects_booleans",),
        "1.0 を true にした設定を通す",
    ),
    _m(
        "mm31 凍結した設定の値を変える",
        _M,
        '"undecided_max": 0.2,',
        '"undecided_max": 0.3,',
        (
            "test_sketch_recheck_accepts_a_consistent_sketch",
            "test_expected_params_match_the_sim",
        ),
        "凍結した帯の上限と違う",
    ),
    _m(
        "mm32 選定の再計算を最小の R に",
        _M,
        '{"selected_R": max(ok), "door_close": False}',
        '{"selected_R": min(ok), "door_close": False}',
        ("test_recompute_selection",),
        "選定規則と違う再計算",
    ),
    _m(
        "mm33 選定の再計算で真偽値を緩める",
        _M,
        'ok = [x["R"] for x in per_r if all(x.get(f) is True for f in flags)]',
        'ok = [x["R"] for x in per_r if all(x.get(f) for f in flags)]',
        ("test_recompute_selection",),
        "1 を真として扱う",
    ),
    _m(
        "mm33b 選定の再計算が較正を見ない",
        _M,
        'flags = ("power_ok", "no_go_ok", "size_ok", "band_ok", "calibrated")',
        'flags = ("power_ok", "no_go_ok", "size_ok", "band_ok")',
        ("test_recompute_selection",),
        "較正の崩れた見取り図の選定を通す",
    ),
    _m(
        "mm33c 行の較正の再計算を緩める",
        _M,
        'and abs(_num(p.get("realized_C")) - _num(x["target_C"])) <= CALIBRATION_TOL',
        'and abs(_num(p.get("realized_C")) - _num(x["target_C"])) <= 1.0',
        ("test_sketch_recheck_calibration",),
        "目標からずれた模擬を健全と照合する",
    ),
    _m(
        "mm33d sweep の較正の照合を外す",
        _M,
        'abs(_num(p["realized_C"]) - _num(x["target_C"])) > CALIBRATION_TOL',
        'abs(_num(p["realized_C"]) - _num(x["target_C"])) > 1.0',
        ("test_sketch_recheck_calibration",),
        "目標からずれた sweep を通す",
    ),
    _m(
        "mm33e 登録の形を sim から導く",
        _M,
        '    "asc_only",\n    "chrono_only",\n',
        '    "chrono_only",\n',
        (
            "test_registered_reach_matches_the_sim",
            "test_sketch_recheck_accepts_a_consistent_sketch",
        ),
        "登録から形が欠ける",
    ),
    _m(
        "mm33f 時系列の形の到達上限の符号を誤る",
        _M,
        "total += (1.0 - g_fwd) if a_first else (1.0 + g_fwd)",
        "total += (1.0 + g_fwd) if a_first else (1.0 - g_fwd)",
        ("test_registered_reach_matches_the_sim",),
        "到達上限の独立な再計算が誤る",
    ),
    _m(
        "mm34 sweep の no_go の照合を外す",
        _M,
        '            _num(x["no_go"]), sum(p[sc.VERDICT_ABSENT] for p in x["per_seed"]) / n\n        ):',
        '            _num(x["no_go"]), _num(x["no_go"])\n        ):',
        ("test_sketch_recheck_checks_the_sweeps",),
        "per_seed と合わない no_go を通す",
    ),
    _m(
        "mm35 sweep の点の完全性を見ない",
        _M,
        "if set(keys) != expected_sweep_points() or len(keys) != len(set(keys)):",
        "if False:",
        ("test_sketch_recheck_checks_the_sweeps",),
        "点の欠けた sweep を通す",
    ),
    _m(
        "mm36 境目の照合を外す",
        _M,
        'if sketch.get("boundaries") != fresh:',
        "if False:",
        ("test_sketch_recheck_checks_the_sweeps",),
        "sweep と合わない境目を通す",
    ),
    _m(
        "mm37 最有利行の到達の照合を外す",
        _M,
        'if sketch.get("most_favorable_reaches") is not favorable_reaches(sweeps):',
        "if False:",
        ("test_sketch_recheck_recomputes_selection_and_reach",),
        "最有利行の到達を偽っても通す",
    ),
    _m(
        "mm38 実行した R の照合を外す",
        _M,
        'if sketch.get("R_run") != list(REGISTERED_R):',
        "if False:",
        ("test_sketch_recheck_checks_r_run",),
        "一部の R だけを回した見取り図を通す",
    ),
    _m(
        "mm39 選定の照合を外す",
        _M,
        'if sketch.get("selection") != recompute_selection(per_r):',
        "if False:",
        ("test_sketch_recheck_recomputes_selection_and_reach",),
        "規則と違う選定を通す",
    ),
    _m(
        "mm40 設定の照合を外す",
        _M,
        'if not _same_json(sketch.get("params"), expected_params()):',
        "if False:",
        ("test_sketch_recheck_checks_the_params",),
        "凍結と違う設定の見取り図を通す",
    ),
    _m(
        "mm41 凍結の R の候補の照合を外す",
        _M,
        "        or selected not in REGISTERED_R\n",
        "\n",
        ("test_freeze_violations_stage_pilot",),
        "候補の外の R の選定で凍結する",
    ),
    _m(
        "mm42 最有利行の到達の凍結条件を外す",
        _M,
        '    if sketch.get("most_favorable_reaches") is not True:\n        out.append(NOT_REACHED)',
        "    if False:\n        out.append(NOT_REACHED)",
        ("test_freeze_violations_stage_pilot",),
        "設計容量の door-close で凍結する",
    ),
    _m(
        "mm43 draft の凍結条件を外す",
        _M,
        "    if status is None:\n        out.append(DRAFT)",
        "    if False:\n        out.append(DRAFT)",
        ("test_freeze_violations_stage_pilot",),
        "status が draft のまま凍結する",
    ),
    _m(
        "mm44 FROZEN の status を読まない",
        _M,
        "if any(STATUS_FROZEN_LINE in line for line in head):",
        "if False:",
        ("test_freeze_violations_stage_pilot",),
        "FROZEN の prereg を draft と読む",
    ),
    _m(
        "mm45 第 2 段で第 1 段の封印を見ない",
        _M,
        "out += stage1_seal_violations(root)",
        "out += []",
        ("test_freeze_violations_stage_main_checks_the_seal",),
        "第 1 段の封印が無くても第 2 段を凍結する",
    ),
    _m(
        "mm46 pilot の判定の再計算を照合しない",
        _M,
        "if fresh.get(key) != gate.get(key):",
        "if False:",
        ("test_pilot_gate_is_recomputed_from_its_inputs",),
        "入力と合わない pilot の判定を通す",
    ),
    _m(
        "mm47 pilot の R と選定の照合を外す",
        _M,
        'if gate.get("R") != selected_r:',
        "if False:",
        ("test_pilot_gate_is_recomputed_from_its_inputs",),
        "見取り図と違う R の pilot を通す",
    ),
    _m(
        "mm48 provenance の sha256 を見ない",
        _M,
        "            or provenance.get(key) != sha256(p)\n",
        "\n",
        ("test_pilot_provenance_binds_driver_records_and_meta",),
        "別の実行の provenance を混ぜた記録を通す",
    ),
    _m(
        "mm49 pilot の入力の sha256 を見ない",
        _M,
        "if not p.is_file() or inputs.get(name) != sha256(p):",
        "if not p.is_file():",
        ("test_pilot_gate_is_recomputed_from_its_inputs",),
        "入力と結び付かない pilot の判定を通す",
    ),
    _m(
        "mm50 driver の all_killed を見ない",
        _M,
        '    if cert.get("all_killed") is not True:\n        out.append("driver:',
        '    if False:\n        out.append("driver:',
        ("test_driver_certification_contract",),
        "全 KILLED でない driver を通す",
    ),
    _m(
        "mm51 driver の行の KILLED を見ない",
        _M,
        'if any(x.get("status") != "KILLED" for x in rows):',
        "if False:",
        ("test_driver_certification_contract",),
        "生き残りの driver の変異を通す",
    ),
    _m(
        "mm52 driver の登録変異との一致を見ない",
        _M,
        "if want is None or got != want:",
        "if want is None:",
        ("test_driver_certification_contract", "test_registries_must_be_well_formed"),
        "登録と違う driver の certification を通す",
    ),
    _m(
        "mm53 driver の sha256 を見ない",
        _M,
        "if not p.is_file() or cert.get(key) != {rel: sha256(p)}:",
        "if not p.is_file():",
        ("test_driver_certification_contract",),
        "古い driver の certification を通す",
    ),
    _m(
        "mm54 fixture 表の再計算を照合しない",
        _M,
        'if table.get("tables") != json.loads(json.dumps(fresh)):',
        "if False:",
        ("test_fixture_table_binding",),
        "コードと合わない fixture 表を通す",
    ),
    _m(
        "mm55 単位と呼び出しの数を照合しない",
        _M,
        'if res.get("n_units") != n_units or res.get("calls") != 4 * n_units:',
        "if False:",
        ("test_sketch_recheck_recomputes_flags_and_values",),
        "設計と違う単位の数を通す",
    ),
    _m(
        "mm56 size の閾値の記録を照合しない",
        _M,
        '        or res.get("size_count_threshold") != x_max\n',
        "\n",
        ("test_sketch_recheck_recomputes_flags_and_values",),
        "閾値を偽った見取り図を通す",
    ),
    _m(
        "mm57 size の閾値の独立な計算で P(X > x) を P(X ≥ x) にする",
        _M,
        "    while FWER_DEN * n_checks * tail[x + 1] > total:",
        "    while FWER_DEN * n_checks * tail[x] > total:",
        ("test_registered_size_threshold_matches_its_definition",),
        "manifest の閾値の再計算が定義からずれる (Codex 2 周目 MEDIUM-1)",
    ),
    _m(
        "mm58 二項の項の漸化式を誤る",
        _M,
        "terms[k + 1] = terms[k] * (n_sims - k) // ((k + 1) * (ALPHA_DEN - 1))",
        "terms[k + 1] = terms[k] * (n_sims - k + 1) // ((k + 1) * (ALPHA_DEN - 1))",
        ("test_registered_size_threshold_matches_its_definition",),
        "manifest の閾値の再計算が二項分布でなくなる",
    ),
    _m(
        "mm59 境目の補間で下降の向きを無視する",
        _M,
        "crosses = (p0 < POWER_TARGET <= p1) if rising else (p1 < POWER_TARGET <= p0)",
        "crosses = p0 < POWER_TARGET <= p1",
        ("test_registered_boundary_matches_its_definition",),
        "NO_GO の境目の再計算が誤る (Codex 2 周目 MEDIUM-1 の反例)",
    ),
    _m(
        "mm60 境目の補間を区間の右端にする",
        _M,
        "            return c0 + (c1 - c0) * (POWER_TARGET - p0) / (p1 - p0)",
        "            return c1",
        ("test_registered_boundary_matches_its_definition",),
        "境目の再計算が補間しない",
    ),
    _m(
        "mm61 manifest が sim の size の閾値を使う",
        _M,
        "x_max = registered_size_threshold(n_checks) if n_checks else -1",
        "x_max = sim.size_count_threshold(n_checks) if n_checks else -1",
        ("test_size_threshold_is_independent_of_the_sim",),
        "生成側の閾値の誤りを照合が共有する (Codex 2 周目 MEDIUM-1)",
    ),
    _m(
        "mm62 manifest が sim の境目 (上昇) を使う",
        _M,
        '"pass_08": registered_boundary(',
        '"pass_08": sim.boundary(',
        ("test_boundaries_are_independent_of_the_sim",),
        "生成側の境目の誤りを照合が共有する (Codex 2 周目 MEDIUM-1)",
    ),
    _m(
        "mm63 manifest が sim の境目 (下降) を使う",
        _M,
        '"no_go_08": registered_boundary(',
        '"no_go_08": sim.boundary(',
        ("test_boundaries_are_independent_of_the_sim",),
        "生成側の境目の誤りを照合が共有する (Codex 2 周目 MEDIUM-1)",
    ),
)


def _run_tests(
    env: dict[str, str], root: pathlib.Path = _REPO_ROOT, tests: str = _TESTS
) -> tuple[int, list[str], bool]:
    args = [sys.executable, "-m", "pytest", "-q", "-rfE", "-p", "no:cacheprovider"]
    if root == _REPO_ROOT:
        args += ["--deselect", _DESELECT]
    proc = subprocess.run(  # noqa: S603
        [*args, tests],
        cwd=str(root),
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


META_CASES: tuple[tuple[str, str, str, str, tuple[str, ...]], ...] = (
    (
        "decide を常に INCONCLUSIVE に潰す",
        "o_time_probe_scorer.py",
        "    comps_positive = np.all(np.asarray(comps) > 0, axis=-1)\n",
        "    return np.full(np.shape(log_e_plus), VERDICT_UNDERPOWERED)\n"
        "    comps_positive = np.all(np.asarray(comps) > 0, axis=-1)\n",
        (
            "test_decide_threshold",
            "test_evaluate_newer_pass",
            "test_evaluate_blind_no_go",
        ),
    ),
    (
        "structure_violations を空に潰す",
        "o_time_probe_scorer.py",
        "    out: list[str] = []\n    keys = [(s.arm, s.encoding, s.replicate, s.probe_id, s.k) for s in samples]\n",
        "    return []\n"
        "    out: list[str] = []\n    keys = [(s.arm, s.encoding, s.replicate, s.probe_id, s.k) for s in samples]\n",
        ("test_structure_seed", "test_structure_prompt", "test_structure_grid"),
    ),
)


def run_meta(env: dict[str, str]) -> list[dict[str, object]]:
    """複製ツリー (repo の外の一時 dir) で検査関数を no-op に潰し、依存する test が落ちることを見る."""
    rows: list[dict[str, object]] = []
    for label, target, old, new, expect in META_CASES:
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="ot_meta_"))
        try:
            (tmp / "scripts").mkdir()
            for name in (
                *_CERTIFIED,
                "o_time_probe_manifest.py",
                "o_time_probe_mutation_check.py",
            ):
                shutil.copy2(_SCRIPTS / name, tmp / "scripts" / name)
            dst_tests = tmp / _TESTS
            dst_tests.mkdir(parents=True)
            for name in _TEST_FILES:
                shutil.copy2(_REPO_ROOT / _TESTS / name, dst_tests / name)
            path = tmp / "scripts" / target
            src = path.read_text(encoding="utf-8")
            if src.count(old) != 1:
                msg = f"meta anchor not unique: {label}"
                raise RuntimeError(msg)
            path.write_text(src.replace(old, new, 1), encoding="utf-8", newline="\n")
            code, failed, collect_error = _run_tests(
                env, tmp, f"{_TESTS}/test_scorer.py"
            )
            status = (
                "FAILED_AS_EXPECTED"
                if code != 0 and not collect_error and set(expect) <= set(failed)
                else "NOT_AS_EXPECTED"
            )
            rows.append(
                {
                    "label": label,
                    "status": status,
                    "expected_all_of": sorted(expect),
                    "failed": failed,
                }
            )
            print(f"meta: {label:40s} {status}", flush=True)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return rows


def _sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def anchor_problems() -> list[str]:
    """全変異の anchor が対象ファイルに 1 回だけ現れ、置換で内容が変わるか (実行の前の確認)."""
    out = []
    labels = [m.label for m in MUTANTS]
    if len(set(labels)) != len(labels):
        out.append("mutant labels are not unique")
    for mut in MUTANTS:
        src = mut.target.read_text(encoding="utf-8")
        n = src.count(mut.old)
        if n != 1:
            out.append(f"{mut.label}: anchor x{n}")
        if mut.old == mut.new:
            out.append(f"{mut.label}: no-op")
        if not mut.expect:
            out.append(f"{mut.label}: no expected diagnosis")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=pathlib.Path, default=None)
    ap.add_argument("--only", default=None, help="label の接頭辞で絞る (開発用)")
    ap.add_argument("--anchors", action="store_true", help="anchor の確認だけをする")
    args = ap.parse_args(argv)

    if args.anchors:
        problems = anchor_problems()
        print("\n".join(problems) or f"anchors ok ({len(MUTANTS)} mutants)")
        return 1 if problems else 0

    env = dict(os.environ, PYTHONUTF8="1")
    targets = (_B, _X, _S, _Z, _P, _M)
    originals = {t: t.read_bytes() for t in targets}
    sha_before = {t: hashlib.sha256(b).hexdigest() for t, b in originals.items()}
    certified = {f"scripts/{name}": _sha(_SCRIPTS / name) for name in _CERTIFIED}
    tests = {
        f"{_TESTS}/{name}": _sha(_REPO_ROOT / _TESTS / name) for name in _TEST_FILES
    }
    harness = _sha(pathlib.Path(__file__).resolve())
    manifest_sha = _sha(_M)

    code, failed, _ = _run_tests(env)
    if code != 0:
        print(f"ERROR: 対照 (無変異) が緑でない: {failed}")
        return 2
    meta = run_meta(env) if args.only is None else []

    mutants = [m for m in MUTANTS if args.only is None or m.label.startswith(args.only)]
    rows: list[dict[str, object]] = []
    try:
        for mut in mutants:
            src = originals[mut.target].decode("utf-8")
            n = src.count(mut.old)
            if n != 1 or mut.old == mut.new:
                status = "NO_OP" if mut.old == mut.new else f"ANCHOR x{n}"
                rows.append(
                    {
                        "label": mut.label,
                        "status": status,
                        "expected_any_of": sorted(mut.expect),
                    }
                )
                print(f"{mut.label:52s} {status}", flush=True)
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
                    "reason": mut.reason,
                    "failed": failed,
                }
            )
            print(f"{mut.label:52s} {status}", flush=True)
    finally:
        for t, b in originals.items():
            t.write_bytes(b)

    restored = all(
        hashlib.sha256(t.read_bytes()).hexdigest() == sha_before[t] for t in originals
    )
    bad = [r for r in rows if r["status"] != "KILLED"]
    meta_ok = bool(meta) and all(m["status"] == "FAILED_AS_EXPECTED" for m in meta)
    print(f"source restored (sha256 match): {restored}")
    print(f"meta-test: {'ok' if meta_ok else 'NOT ok'}")
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
                    "manifest_sha256": manifest_sha,
                    "meta_test": meta,
                    "mutants": rows,
                    "all_killed": not bad and meta_ok,
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
    return 1 if bad or (args.only is None and not meta_ok) else 0


if __name__ == "__main__":
    sys.exit(main())
