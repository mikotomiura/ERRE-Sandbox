#!/usr/bin/env python
"""候補 G (汎化 probe) の変異試験 — 判定行を壊すと、意図した test が落ちるか (prereg §10、計測台 ADR §4.4).

``scripts/generalization_probe_battery.py`` (mb*)・``generalization_probe_fixtures.py`` (mx*)・
``generalization_probe_scorer.py`` (ms*)・``generalization_probe_sim.py`` (mz*)・
``generalization_probe_pilot_gate.py`` (mp*)・``generalization_probe_manifest.py`` (mm*) の判定行を 1 つずつ壊し、``tests/test_generalization_probe/`` を
実行する。枠組みは (b) (``body_walk_mutation_check.py``)。

変異は 4 つ組 (名前・変異 (old → new)・期待診断 (落ちるべき test の集合)・理由) で登録する。判定は 3 通りに
分けて報告する:

* 対照が落ちた: 無変異で test が緑でない → harness を止める (変異の判定をしない)。
* 変異が捕まらなかった: SURVIVED (test が緑のまま)。
* 変異は落ちたが理由が違う: WRONG_REASON (落ちた test に期待診断が無い) / COLLECTION_ERROR。KILLED に数えない。

anchor (置換前の文字列) は対象ファイルに 1 回だけ現れ、置換で内容が変わること (no-op を除く)。
等価変異 (意味を変えないので kill できない) は登録しない。判断して外したもの:

* aggregator の「失敗の無い成功だけ」(``fail[(sit, act)] == 0``) を外す: 決定的な世界では成功した行動は
  失敗しないので等価。
* ``log_capital`` の ``np.maximum(f, 0.0)``: λ ≤ cap と d ∈ [−1, 1] で因子は非負なので、浮動小数の誤差以外では等価。
* 表示順の回転を (r + j) から r だけにする: 各 (族, つ組) での位置の均衡・分類からの独立はどちらでも成り立つ
  (表示順の pin で別に捕まえる: mb06b)。

meta-test (計測台 §4.4): 対象を複製ツリー (repo の外の一時 dir) に写し、検査関数を no-op に潰して、依存する
test が実際に落ちることを一度見る (``decide`` を常に INCONCLUSIVE に・``structure_violations`` を空に)。

変異は権威ファイル自体に当てる。対象ファイルは実行中だけ書き換わり、必ず原状復帰する (finally + sha256 照合。
Windows では強制終了すると finally が走らないので、止めない)。import する凍結物 (旧 Stage B scorer) は変異させない。
出力は certification が結び付く 6 ファイル・test・本 harness の sha256、meta-test の結果、変異ごとの明細を記録する。

実行 (repo root から)::

    uv run python scripts/generalization_probe_mutation_check.py --out <certification.json>
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
_B = _SCRIPTS / "generalization_probe_battery.py"
_X = _SCRIPTS / "generalization_probe_fixtures.py"
_S = _SCRIPTS / "generalization_probe_scorer.py"
_Z = _SCRIPTS / "generalization_probe_sim.py"
_P = _SCRIPTS / "generalization_probe_pilot_gate.py"
_M = _SCRIPTS / "generalization_probe_manifest.py"
_TESTS = "tests/test_generalization_probe"
_CERTIFIED = (
    "generalization_probe_battery.py",
    "generalization_probe_fixtures.py",
    "generalization_probe_scorer.py",
    "generalization_probe_sim.py",
    "generalization_probe_pilot_gate.py",
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
# (manifest の判定行は変異の対象にする。Codex 2 回目 MEDIUM-5)。
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
        "mb01 回転を外す (A_rot = A)",
        _B,
        "return {c: base[next_class(c)] for c in CLASSES}",
        "return {c: base[c] for c in CLASSES}",
        ("test_rotation_and_sigma", "test_pointed"),
        "族内の foil が w と一致し、推定量が定義されない",
    ),
    _m(
        "mb02 σ を外す (B = A)",
        _B,
        "return {c: SIGMA[a] for c, a in rule(ARM_A).items()}",
        "return {c: a for c, a in rule(ARM_A).items()}",
        ("test_rotation_and_sigma", "test_pointed"),
        "族 B が族 A と同じ label を使う",
    ),
    _m(
        "mb03 aggregator が失敗も成功として記録する",
        _B,
        "(succ if ob.success else fail)[(ob.situation, ob.action)] += 1",
        "(succ if True else fail)[(ob.situation, ob.action)] += 1",
        ("test_state_rows_follow_world_rule", _BCP),
        "状態が世界の規則でなく試行の全体を写す",
    ),
    _m(
        "mb04 曝露の試行回数を変える",
        _B,
        "TRIALS_PER_ACTION: Final[int] = 3",
        "TRIALS_PER_ACTION: Final[int] = 2",
        ("test_render_row_text",),
        "行の文面 (成功 3 / 失敗 0) が v2 の lever 行と変わる",
    ),
    _m(
        "mb05 状態の行順を arm ごとにする (族内で共有しない)",
        _B,
        "    order = entry_order(fi, probe.triple, r)\n",
        "    order = entry_order(LEVER_ARMS.index(arm), probe.triple, r)\n",
        ("test_shared_within_family", _BCP),
        "族内の 2 arm の状態が label 以外でも違い、相殺が崩れる",
    ),
    _m(
        "mb06 表示順を probe ごとにずらす (Ω の順が分類を明かす)",
        _B,
        "probe_text = render_probe(probe.situation, option_order(fi, probe.triple, r))",
        "probe_text = render_probe(probe.situation, option_order(fi, probe.triple, r + probe.index))",
        ("test_triple_prompts_differ_only_in_key", _BCP),
        "つ組の 3 probe の prompt が key 以外でも違い、key を見ない方策の C = 0 の定理が外れる (Codex HIGH-1)",
    ),
    _m(
        "mb06b 表示順の回転からつ組を外す",
        _B,
        "shift = (r + j) % N_POSITIONS",
        "shift = r % N_POSITIONS",
        ("test_options_are_family_labels_independent_of_class",),
        "凍結した表示順から外れる",
    ),
    _m(
        "mb07 dev key に probe key を入れる",
        _B,
        '"bird": ("sparrow", "heron", "pigeon", "magpie"),',
        '"bird": ("eagle", "heron", "pigeon", "magpie"),',
        ("test_probe_keys_absent", _BCP),
        "probe の key が状態に現れ、汎化でなく lookup になる",
    ),
    _m(
        "mb08 字面の重なりの検査を止める",
        _B,
        "        if shared:\n",
        "        if False:\n",
        ("test_surface_overlap_detects",),
        "probe key と dev key の 4-gram の共有を見逃す",
    ),
    _m(
        "mb09 頻度ベクトルの不変性を恒真にする",
        _B,
        "return Counter(labels_a) == Counter(labels_b)",
        "return True",
        ("test_frequency_vector_counterexample",),
        "(x, x, y) の反例を通す",
    ),
    _m(
        "mb10 非漏洩の検査から分類名を外す",
        _B,
        'tokens = {t.lower() for t in (*CLASSES, *LEVER_ARMS, "rot")}',
        'tokens = {t.lower() for t in (*LEVER_ARMS, "rot")}',
        ("test_non_leakage_detects_class_name",),
        "潜在の分類名が prompt に漏れても検出しない",
    ),
    _m(
        "mb11 つ組の distractor を分類ごとにずらす",
        _B,
        "        place, company = COMBOS[j % len(COMBOS)]\n        for ci, c in enumerate(CLASSES):\n",
        "        for ci, c in enumerate(CLASSES):\n            place, company = COMBOS[(j + ci) % len(COMBOS)]\n",
        ("test_triples_share_distractors", _BCP),
        "つ組の 3 probe が近傍を共有しない",
    ),
    _m(
        "mb12 dev の状況を 1 つの組に寄せる",
        _B,
        "Situation(DEV_KEYS[c][i], *COMBOS[i])",
        "Situation(DEV_KEYS[c][i], *COMBOS[0])",
        ("test_dev_design_one_per_combo_and_class", _BCP),
        "一致の型ごとに各分類 1 行の均衡が崩れる",
    ),
    _m(
        "mb13 masked の状態に key を残す",
        _B,
        "key = MASK if masked else sit.key",
        "key = sit.key",
        ("test_masked_states", _BCP),
        "null pilot が潜在を読めてしまい、null でなくなる",
    ),
    _m(
        "mb14 pilot と本走の seed の名前空間を重ねる",
        _B,
        '"pilot_fam0": 3,',
        '"pilot_fam0": 0,',
        ("test_seed_namespaces", _BCP),
        "資格に使った null 記録と確認の実走が分離されない",
    ),
    _m(
        "mb15 prompt の byte 予算を下げる",
        _B,
        "MAX_PROMPT_BYTES: Final[int] = 3000",
        "MAX_PROMPT_BYTES: Final[int] = 1000",
        ("test_prompt_budget", _BCP),
        "切り詰めが起こりえないことの静的保証が外れる",
    ),
    _m(
        "mb16 知識確認の正答を常に先頭にする",
        _B,
        "pos = (key_index + k) % len(CLASSES)",
        "pos = 0",
        ("test_know_options_balance_the_answer_position", _BCP),
        "先頭を答える方策が知識確認を通る (Codex HIGH-2)",
    ),
    _m(
        "mb17 選定用の行順を本走と同じにする",
        _B,
        "    20261002  # probe key の選定だけに使う行順 (本走と別、Codex HIGH-4)\n",
        "    20261001  # probe key の選定だけに使う行順 (本走と別、Codex HIGH-4)\n",
        ("test_selection_layout_separate", _BCP),
        "key の選定が本走の layout に条件付く (Codex HIGH-4)",
    ),
    _m(
        "mb18 つ組の prompt の検査を止める",
        _B,
        "                if len(texts) != 1:\n",
        "                if False:\n",
        ("test_triple_prompts_check_detects",),
        "定理の前提の崩れを見逃す",
    ),
    # ================================================================ fixtures
    _m(
        "mx01 fixture の w / foil の符号を入れ替える",
        _X,
        "        return 1\n    if choice == probe.pointed[bat.FOIL[arm]]:\n        return -1\n",
        "        return -1\n    if choice == probe.pointed[bat.FOIL[arm]]:\n        return 1\n",
        ("test_positive_controls", "test_fixture_table_pinned"),
        "陽性対照の向きが逆になる",
    ),
    _m(
        "mx02 fixture gate の閾値を 1 にする",
        _X,
        'if abs(v["C"]) >= FIXTURE_GATE',
        'if abs(v["C"]) >= 1.0',
        ("test_fixture_violations_detects",),
        "|C| が τ/4 を超える写し方を見逃す",
    ),
    _m(
        "mx03 fixture の単位を族内の平均でなく片方の arm にする",
        _X,
        "            (s[(a, u.triple, u.replicate)] + s[(b, u.triple, u.replicate)]) / 2.0\n",
        "            s[(a, u.triple, u.replicate)]\n",
        ("test_fixture_table_pinned", "test_positive_controls"),
        "族内の相殺を経ずに C を計算する",
    ),
    _m(
        "mx04 字面の方策の登録を落とす",
        _X,
        'metrics = (*SURFACE_SCORES, "alphabetical")',
        'metrics = ("alphabetical",)',
        ("test_fixture_table_pinned",),
        "登録した写し方の集合が欠ける",
    ),
    _m(
        "mx05 編集距離の置換の費用を 0 にする",
        _X,
        "prev[j - 1] + (ca != cb)",
        "prev[j - 1]",
        ("test_levenshtein_and_similarity", "test_fixture_table_pinned"),
        "字面の近さの計算が誤る",
    ),
    _m(
        "mx06 Jaccard を共通部分の数にする",
        _X,
        "return len(ga & gb) / len(ga | gb)",
        "return float(len(ga & gb))",
        ("test_levenshtein_and_similarity", "test_fixture_table_pinned"),
        "字面の近さの計算が誤る",
    ),
    _m(
        "mx07 同点処理 'last' を 'first' と同じにする",
        _X,
        'idx = range(len(ctx.rows)) if tie == "first" else range(len(ctx.rows) - 1, -1, -1)',
        "idx = range(len(ctx.rows))",
        ("test_fixture_table_pinned",),
        "同点処理の変種が登録されていても計算されない",
    ),
    _m(
        "mx08 fixture 表の合否を恒真にする",
        _X,
        '"passed": worst < FIXTURE_GATE,',
        '"passed": True,',
        ("test_fixture_violations_detects",),
        "gate を通らない表を合格と記録する",
    ),
    _m(
        "mx09 key を見ない方策の 0 の確認を止める",
        _X,
        'if v["family"] == "key_blind" and abs(v["C"]) > 1e-9',
        "if False",
        ("test_fixture_violations_detects_a_nonzero_key_blind",),
        "定理の破れを見逃す",
    ),
    _m(
        "mx10 最長共通部分列を誤る",
        _X,
        "cur.append(prev[j - 1] + 1 if ca == cb else max(prev[j], cur[j - 1]))",
        "cur.append(prev[j - 1] + 1 if ca == cb else 0)",
        ("test_levenshtein_and_similarity", "test_fixture_table_pinned"),
        "部分列の方策の計算が誤る (Codex LOW-12)",
    ),
    _m(
        "mx11 選定用の行順を使わない",
        _X,
        "order_fn = bat.selection_entry_order if selection else bat.entry_order",
        "order_fn = bat.entry_order",
        ("test_selection_contexts_use_selection_layouts",),
        "key の選定が本走の layout に条件付く (Codex HIGH-4)",
    ),
    # ================================================================ scorer
    _m(
        "ms01 parse: 2 種以上の label で先頭を採る",
        _S,
        "    if len(found) != 1:\n        return None\n    return found[0]",
        "    if not found:\n        return None\n    return found[0]",
        ("test_parse_two_labels_is_bot",),
        "曖昧な応答を数える",
    ),
    _m(
        "ms02 parse: think ブロックを除かない",
        _S,
        'text = _THINK_BLOCK.sub(" ", text)',
        "text = text",
        ("test_parse_think_block",),
        "think の中の label を数える",
    ),
    _m(
        "ms03 parse: 閉じない think を ⊥ にしない",
        _S,
        '    if "<think" in text or "</think" in text:\n        return None\n    found',
        "    found",
        ("test_parse_unclosed_think",),
        "途中で切れた応答を数える",
    ),
    _m(
        "ms04 parse: NFKC を外す",
        _S,
        'text = unicodedata.normalize("NFKC", raw).lower()',
        "text = raw.lower()",
        ("test_parse_basic",),
        "全角の応答を ⊥ にする",
    ),
    _m(
        "ms05 ⊥ を分母から落とす",
        _S,
        "                        n += 1\n",
        '                        n += cat != "bot"\n',
        ("test_bot_in_denominator",),
        "⊥ の偏りが C を動かす",
    ),
    _m(
        "ms06 単位を族内の平均でなく片方の arm にする",
        _S,
        "            (s[(a, u.triple, u.replicate)] + s[(b, u.triple, u.replicate)]) / 2.0\n",
        "            s[(a, u.triple, u.replicate)]\n",
        ("test_unit_scores_family_average", "test_evaluate_blind_no_go"),
        "label priming と事前傾向の族内の相殺が外れる",
    ),
    _m(
        "ms07 成分の条件を外す",
        _S,
        "passed = (np.asarray(log_e_plus) >= LOG_THRESHOLD) & comps_positive",
        "passed = np.asarray(log_e_plus) >= LOG_THRESHOLD",
        ("test_decide_requires_positive_components",),
        "1 arm が読まなくても PASS する",
    ),
    _m(
        "ms08 PASS の閾値を e ≥ 1 に下げる",
        _S,
        "passed = (np.asarray(log_e_plus) >= LOG_THRESHOLD) & comps_positive",
        "passed = (np.asarray(log_e_plus) >= 0.0) & comps_positive",
        ("test_decide_threshold",),
        "size が α を超える",
    ),
    _m(
        "ms09 PASS 以外を全て NO_GO にする",
        _S,
        "no_go = np.asarray(log_e_minus) >= LOG_THRESHOLD",
        "no_go = np.asarray(log_e_plus) < LOG_THRESHOLD",
        ("test_decide_threshold", "test_evaluate_partial_inconclusive"),
        "INCONCLUSIVE に到達しない",
    ),
    _m(
        "ms10 λ の上限を 1/(1−τ) に上げる",
        _S,
        "CAP_PLUS: Final[float] = 1.0 / (1.0 + TAU)",
        "CAP_PLUS: Final[float] = 1.0 / (1.0 - TAU)",
        ("test_e_value_respects_necessary_bound", "test_frozen_constants"),
        "因子が負になりうる賭けで、帰無の領域の size が破れる",
    ),
    _m(
        "ms11 λ の混合を平均でなく最大にする",
        _S,
        "mixed = np.log(np.mean(np.exp(logs - safe), axis=-1)) + safe[..., 0]",
        "mixed = np.log(np.max(np.exp(logs - safe), axis=-1)) + safe[..., 0]",
        ("test_e_value_exact",),
        "e-value でなくなる (λ を見てから選ぶ)",
    ),
    _m(
        "ms12 NO_GO の e-value の符号を逆にする",
        _S,
        "log_e_value(TAU - d, CAP_MINUS),",
        "log_e_value(d - TAU, CAP_MINUS),",
        ("test_no_go_reachable", "test_e_value_exact"),
        "NO_GO が τ より大の側で立つ",
    ),
    _m(
        "ms13 arm の ⊥ の上限を外す",
        _S,
        "per_arm = np.all(bot <= bot_max, axis=-1)",
        "per_arm = np.all(bot <= 1.0, axis=-1)",
        ("test_bottom_gate", "test_evaluate_lever_bottom"),
        "⊥ の多い battery で判定する",
    ),
    _m(
        "ms14 族内の ⊥ 率差の検査を外す",
        _S,
        "family = np.all(np.stack(gaps, axis=-1) < BOT_FAMILY_GAP, axis=-1)",
        "family = np.all(np.stack(gaps, axis=-1) < 1.0, axis=-1)",
        ("test_bottom_gate_family_gap", "test_evaluate_lever_bottom"),
        "族内の ⊥ の偏りで C が動く",
    ),
    _m(
        "ms15 envelope の余裕を外す (gate 全域にする)",
        _S,
        "return min(BOT_MAX, pilot_max_bottom + ENVELOPE_MARGIN)",
        "return BOT_MAX",
        ("test_envelope_bottom_max", "test_evaluate_envelope"),
        "pilot の雑音の外で判定する (Codex MEDIUM-6)",
    ),
    _m(
        "ms16 certification の確認を外す",
        _S,
        "    if not certified:\n        invalid.append(",
        "    if False:\n        invalid.append(",
        ("test_evaluate_requires_certification",),
        "変異試験を通っていない判定コードで判定する",
    ),
    _m(
        "ms17 meta の要求条件の照合を外す",
        _S,
        'if meta["request"] != request_meta():',
        "if False:",
        ("test_evaluate_meta",),
        "凍結と違う decode の記録で判定する",
    ),
    _m(
        "ms18 seed の照合を外す",
        _S,
        "        if s.seed != seed:\n",
        "        if False:\n",
        ("test_structure_seed",),
        "共通乱数の結び付きを確かめない",
    ),
    _m(
        "ms19 prompt の照合を外す",
        _S,
        "        if s.prompt_sha256 != sha:\n",
        "        if False:\n",
        ("test_structure_prompt",),
        "凍結 renderer と違う prompt の記録で判定する",
    ),
    _m(
        "ms20 parse の照合を外す",
        _S,
        "if s.raw is not None and parse_choice(s.raw) != s.parsed:",
        "if False:",
        ("test_structure_parse",),
        "記録の parse を信じる",
    ),
    _m(
        "ms21 重複の検査を外す",
        _S,
        '    if len(set(keys)) != len(keys):\n        out.append("duplicate',
        '    if False:\n        out.append("duplicate',
        ("test_structure_duplicate",),
        "同じセルを 2 回数える",
    ),
    _m(
        "ms22 grid の検査を外す",
        _S,
        "if not set(keys) <= the_grid:",
        "if False:",
        ("test_structure_grid",),
        "凍結 grid の外の記録を受け入れる",
    ),
    _m(
        "ms23 観測環境と pilot の照合を外す",
        _S,
        "elif reference_observed is not None and dict(observed) != dict(reference_observed):",
        "elif False:",
        ("test_meta_observed",),
        "pilot と違うモデル実体で判定する (Codex MEDIUM-11)",
    ),
    _m(
        "ms24 call_index の一意性の検査を外す",
        _S,
        "if len(set(idx)) != len(idx) or any(i < 0 for i in idx):",
        "if False:",
        ("test_structure_call_index",),
        "呼び出し順の記録の欠陥を見逃す",
    ),
    _m(
        "ms25 transport 失敗を ⊥ として計算する",
        _S,
        "if any(s.raw is None for s in samples) or len(samples) != len(",
        "if False or len(samples) != len(",
        ("test_evaluate_transport_failure",),
        "送れなかった呼び出しを ⊥ に数える",
    ),
    _m(
        "ms26 int 欄の型検査を緩める (bool を通す)",
        _S,
        "if type(obj[f]) is not int:",
        "if not isinstance(obj[f], int):",
        ("test_schema_bool_is_rejected",),
        "bool を int に読み替える",
    ),
    _m(
        "ms27 certification の KILLED の確認を外す",
        _S,
        'if not all(m.get("status") == "KILLED" for m in mutants):',
        "if False:",
        ("test_load_certification_requires_all_killed",),
        "生き残りのある certification を受け入れる",
    ),
    _m(
        "ms28 certification の sha256 照合を外す",
        _S,
        "return recorded == current",
        "return True",
        ("test_load_certification_detects_stale",),
        "古いコードの certification を受け入れる",
    ),
    _m(
        "ms29 fixture gate を判定から外す",
        _S,
        "if fx.fixture_violations(r_count):",
        "if False:",
        ("test_evaluate_fixture_gate",),
        "登録した写し方で説明できる設計で判定する",
    ),
    _m(
        "ms30 battery の機械検査を判定から外す",
        _S,
        "if bat.battery_violations(r_count):",
        "if False:",
        ("test_evaluate_battery_gate",),
        "相殺条件の崩れた battery で判定する",
    ),
    _m(
        "ms31 族内で seed を共有しない",
        _S,
        'ns = f"fam{bat.ARM_FAMILY[arm]}"',
        'ns = f"fam{bat.LEVER_ARMS.index(arm) % 2}"',
        ("test_seed_shared_within_family",),
        "共通乱数で state-blind の選択を相殺できない",
    ),
    _m(
        "ms32 τ を変える",
        _S,
        "TAU: Final[float] = 0.30",
        "TAU: Final[float] = 0.25",
        ("test_frozen_constants",),
        "凍結値 (v2 の τ) から外れる",
    ),
    _m(
        "ms33 K を変える",
        _S,
        "FROZEN_K: Final[int] = 1",
        "FROZEN_K: Final[int] = 2",
        ("test_frozen_constants",),
        "凍結値から外れる",
    ),
    _m(
        "ms34 成分を arm でなく全体の平均にする",
        _S,
        "np.mean([v for (arm, _, _), v in s.items() if arm == a])",
        "np.mean(list(s.values()))",
        ("test_unit_scores_family_average", "test_components_order"),
        "成分の条件が意味を失う",
    ),
    _m(
        "ms35 観測環境の欠けを通す",
        _S,
        '        out.append("meta: observed environment is missing or malformed")\n',
        "        pass\n",
        ("test_meta_observed",),
        "モデル実体を同定しない記録を受け入れる (Codex MEDIUM-11)",
    ),
    _m(
        "ms36 CLI が pilot の GO を確かめない",
        _S,
        '        and gate.get("decision") == "GO"\n',
        "        and True\n",
        ("test_cli_end_to_end",),
        "pilot が STOP でも本走を判定する",
    ),
    _m(
        "ms37 envelope を gate に渡さない",
        _S,
        "if not bool(bottom_gate_ok(lever_bot, bot_max)):",
        "if not bool(bottom_gate_ok(lever_bot)):",
        ("test_evaluate_envelope",),
        "pilot の雑音の外で判定する (Codex MEDIUM-6)",
    ),
    _m(
        "ms38 other を族の Ω でなく全語彙にする",
        _S,
        "if choice in bat.family_actions(bat.ARM_FAMILY[arm]):",
        "if choice in bat.ACTIONS:",
        ("test_category",),
        "Ω 外の label を other に数える",
    ),
    # ================================================================ sim
    _m(
        "mz01 効果の較正で ⊥ を割り戻さない",
        _Z,
        "t = target / (1.0 - nu.bot)",
        "t = target",
        ("test_sim_calibration",),
        "植えた E[C] が目標より小さくなる",
    ),
    _m(
        "mz02 crn の結合を独立にする",
        _Z,
        "u = np.broadcast_to(rng.random((*shape[:-2], 1, 1)), shape)",
        "u = rng.random(shape)",
        ("test_crn_null_exact_zero",),
        "共通乱数の結合を模擬しない",
    ),
    _m(
        "mz03 項目の 1 の数を厳密にしない",
        _Z,
        "    vals[:, :k] = high\n",
        "",
        ("test_item_pattern_exact_mean",),
        "項目に条件付けた帰無の平均が目標から外れる",
    ),
    _m(
        "mz04 逆向きの項目を正にする",
        _Z,
        "vals[:, :n_rev] = -1.0",
        "vals[:, :n_rev] = 1.0",
        ("test_item_pattern_exact_mean",),
        "逆向きの汎化の形を模擬しない",
    ),
    _m(
        "mz05 選定で size の条件を外す",
        _Z,
        'ok = bool(res["power_ok"] and res["no_go_ok"] and res["size_ok"])',
        'ok = bool(res["power_ok"] and res["no_go_ok"])',
        ("test_select_is_r_main_when_it_passes",),
        "size の悪い R を選ぶ",
    ),
    _m(
        "mz06 二項の閾値を探さない",
        _Z,
        "    while binom_upper_tail(x + 1, n_sims, sc.ALPHA) > level:\n",
        "    while False:\n",
        ("test_size_threshold_is_exact_binomial", "test_evaluate_r_flags"),
        "MC の揺らぎで真の size が α の候補を落とす",
    ),
    _m(
        "mz06b MC の閾値を点の数で割らない",
        _Z,
        "    level = MC_FWER / n_checks\n",
        "    level = MC_FWER\n",
        ("test_size_threshold_is_exact_binomial", "test_evaluate_r_flags"),
        "格子の全点合格で誤棄却の率が膨らむ",
    ),
    _m(
        "mz07 境目の補間を誤る",
        _Z,
        "return c0 + (POWER_TARGET - p0) * (c1 - c0) / (p1 - p0)",
        "return c1",
        ("test_boundary",),
        "power 0.8 の境目を格子の点に丸める",
    ),
    _m(
        "mz08 最も有利な行の 2τ の点を要求しない",
        _Z,
        'abs(r["target_C"] - sc.DELTA_PLANT) < 1e-9 and r["pass"] >= POWER_TARGET',
        'r["target_C"] <= sc.DELTA_PLANT + 1e-9 and r["pass"] >= POWER_TARGET',
        ("test_most_favorable_requires_the_2tau_point",),
        "2τ に届かない行で door-close を外す (Codex MEDIUM-8)",
    ),
    _m(
        "mz09 模擬で ⊥ gate を外す",
        _Z,
        "verdict = np.where(sc.bottom_gate_ok(botr), verdict, sc.VERDICT_INVALID_BATTERY)",
        "verdict = verdict",
        ("test_sim_bottom_gate",),
        "判定と同じ gate を模擬しない",
    ),
    _m(
        "mz10 集中の形の分類を 1 つ多くする",
        _Z,
        "on = (dz.probe_class < k).astype(float)",
        "on = (dz.probe_class <= k).astype(float)",
        ("test_sparse_reach",),
        "集中の形の到達上限が変わる",
    ),
    _m(
        "mz11 二点の極値の確率を誤る",
        _Z,
        "p = (t - other) / (m - other)",
        "p = 0.5",
        ("test_extremal_mean",),
        "帰無の境界でない分布で size を測る",
    ),
    _m(
        "mz12 対数オッズの較正の向きを逆にする",
        _Z,
        "if _expected_c_logodds(dz, mid, bot) < target:",
        "if _expected_c_logodds(dz, mid, bot) > target:",
        ("test_logodds_calibration",),
        "対数オッズの形の E[C] が目標に合わない",
    ),
    _m(
        "mz13 power の条件を外す",
        _Z,
        "power_ok &= val >= POWER_TARGET",
        "power_ok &= True",
        ("test_evaluate_r_flags",),
        "power の足りない R を選ぶ",
    ),
    _m(
        "mz14 size の上限を外す",
        _Z,
        'size_ok = all(r["value"] <= cap + 1e-12 for r in size_rows)',
        "size_ok = True",
        ("test_evaluate_r_flags",),
        "size の破れた R を選ぶ",
    ),
    _m(
        "mz15 選定を R_MAIN でなく最初の合格 R にする",
        _Z,
        '        if res["R"] == R_MAIN:\n',
        "        if True:\n",
        ("test_select_is_r_main_when_it_passes",),
        "user 裁定 DU-1 の R を外れる",
    ),
    _m(
        "mz16 逆向きの結合を共通にする",
        _Z,
        "u = np.concatenate([u0, 1.0 - u0], axis=-1)",
        "u = np.concatenate([u0, u0], axis=-1)",
        ("test_anti_coupling_is_more_variable",),
        "逆向きの結合を模擬しない (Codex MEDIUM-10)",
    ),
    _m(
        "mz17 arm × 単位の全か無かを arm で共通にする",
        _Z,
        "on = (rng.random((n, n_u, 1, 2)) < t).astype(float)",
        "on = (rng.random((n, n_u, 1, 1)) < t).astype(float)",
        ("test_aon_arm_unit_shape",),
        "ADR の形 3 を模擬しない",
    ),
    _m(
        "mz18 回転の arm の w を誤る",
        _Z,
        "w1 = (cls + 1) % 3",
        "w1 = (cls + 2) % 3",
        ("test_design_indices",),
        "模擬の推定量が判定と違う",
    ),
    _m(
        "mz19 模擬の表示の先頭を probe ごとにする",
        _Z,
        "pos0[ui, qi] = (u.replicate + u.triple) % bat.N_POSITIONS",
        "pos0[ui, qi] = (u.replicate + p.index) % bat.N_POSITIONS",
        ("test_design_indices",),
        "模擬の位置の偏りが設計と違う",
    ),
    # ================================================================ pilot gate
    _m(
        "mp01 知識確認の閾値を 1 に下げる",
        _P,
        "KNOW_MIN_CORRECT: Final[int] = 2",
        "KNOW_MIN_CORRECT: Final[int] = 1",
        ("test_knowledge_gate", "test_knowledge_position_policies_fail"),
        "分類を知らない key で本走する",
    ),
    _m(
        "mp02 分類の parse で先頭を採る",
        _P,
        "return found[0] if len(found) == 1 else None",
        "return found[0] if found else None",
        ("test_parse_class",),
        "曖昧な答えを正答に数える",
    ),
    _m(
        "mp03 envelope の gate を外す",
        _P,
        "    if not bool(sc.bottom_gate_ok(bot)):\n",
        "    if False:\n",
        ("test_pilot_envelope",),
        "⊥ の多い battery で本走する",
    ),
    _m(
        "mp04 注入の較正式を誤る",
        _P,
        "lam = (target - c_null) / (live - c_null) if live > c_null else 1.0",
        "lam = (target - c_null) / live if live > c_null else 1.0",
        ("test_injection_calibrates",),
        "既知量への較正が外れる",
    ),
    _m(
        "mp05 再標本化の層を外す",
        _P,
        "                if (bat.PILOT_R0 + rp + j) % bat.N_POSITIONS == shift\n",
        "                if True\n",
        ("test_strata_picks_preserve_the_rotation",),
        "本走の表示の割付を保たない (Codex MEDIUM-7)",
    ),
    _m(
        "mp06 spike-in の OC を見ずに GO にする",
        _P,
        '        if oc["ok"]:\n',
        "        if True:\n",
        ("test_pilot_stop_on_power",),
        "power の足りない設計で本走する",
    ),
    _m(
        "mp07 見取り図が選んだ R より小さい R を許す",
        _P,
        "for r_count in (r for r in R_CANDIDATES if r >= selected_r):",
        "for r_count in R_CANDIDATES:",
        ("test_pilot_respects_selected_r",),
        "見取り図の選定を pilot で緩める",
    ),
    _m(
        "mp08 pilot の seed の照合を外す",
        _P,
        "        if s.seed != seed:\n",
        "        if False:\n",
        ("test_pilot_structure_seed",),
        "pilot の記録の結び付きを確かめない",
    ),
    _m(
        "mp09 pilot の certification の確認を外す",
        _P,
        "    if not certified:\n        invalid.append(",
        "    if False:\n        invalid.append(",
        ("test_pilot_requires_cert",),
        "変異試験を通っていない判定コードで pilot を判定する",
    ),
    _m(
        "mp10 見取り図の door-close を見ずに pilot を判定する",
        _P,
        "    if selected_r is None:\n        invalid.append(",
        "    if False:\n        invalid.append(",
        ("test_pilot_requires_selected_r",),
        "凍結前に door-close した設計の pilot を通す",
    ),
    _m(
        "mp11 masked の腕の向きを foil にする",
        _P,
        "        lever = MASKED_ARMS[s.arm]\n",
        "        lever = bat.FOIL[MASKED_ARMS[s.arm]]\n",
        ("test_cell_scores",),
        "null の記録の得点の向きが逆になる",
    ),
    _m(
        "mp12 pilot の meta の照合を外す",
        _P,
        "    invalid += sc.meta_violations(meta)\n",
        "",
        ("test_pilot_meta",),
        "凍結と違う decode・環境の pilot を受け入れる",
    ),
    _m(
        "mp13 OC の較正の確認を外す",
        _P,
        'abs(o["realized_C"] - t) < CALIBRATION_TOL',
        'abs(o["realized_C"] - t) < 1.0',
        ("test_oc_conditions_each_matter",),
        "既知量への較正が外れても通す (Codex MEDIUM-8)",
    ),
    _m(
        "mp14 OC の PASS の power の条件を外す",
        _P,
        '"power_pass": at_plant["pass"] >= POWER_TARGET,',
        '"power_pass": True,',
        ("test_oc_conditions_each_matter", "test_oc_for_r_uses_the_checks"),
        "power の足りない設計で本走する (Codex MEDIUM-8)",
    ),
    _m(
        "mp15 OC の NO_GO の power の条件を外す",
        _P,
        '"power_no_go": at_zero["no_go"] >= POWER_TARGET,',
        '"power_no_go": True,',
        ("test_oc_conditions_each_matter",),
        "NO_GO に届かない設計で本走する (Codex MEDIUM-8)",
    ),
    _m(
        "mp16 OC の PASS 側の size の条件を外す",
        _P,
        '"size_pass": at_tau["pass"] <= cap,',
        '"size_pass": True,',
        ("test_oc_conditions_each_matter",),
        "size の破れを見逃す (Codex MEDIUM-8)",
    ),
    _m(
        "mp17 OC の NO_GO 側の size の条件を外す",
        _P,
        '"size_no_go": at_tau["no_go"] <= cap,',
        '"size_no_go": True,',
        ("test_oc_conditions_each_matter",),
        "size の破れを見逃す (Codex MEDIUM-8)",
    ),
    _m(
        "mp18 OC の合否を恒真にする",
        _P,
        '"ok": all(checks.values()),',
        '"ok": True,',
        ("test_oc_for_r_uses_the_checks",),
        "どの条件が偽でも GO にする",
    ),
    _m(
        "mp19 pilot の MC の閾値を点の数で割らない",
        _P,
        "    level = MC_FWER / n_checks\n",
        "    level = MC_FWER\n",
        ("test_size_rate_cap",),
        "誤棄却の率が膨らむ",
    ),
    _m(
        "mp20 入力の sha256 を記録しない",
        _P,
        'result["inputs_sha256"] = inputs',
        'result["inputs_sha256"] = {}',
        ("test_cli_end_to_end",),
        "pilot の判定と記録の結び付きを残さない (DC-3)",
    ),
    _m(
        "mp21 知識確認の正答を数えない",
        _P,
        "correct[i] += s.parsed == bat.key_class(keys[i])",
        "correct[i] += 1",
        ("test_knowledge_gate", "test_knowledge_position_policies_fail"),
        "分類を知らない key で本走する",
    ),
    # ================================================================ Codex 2 回目の反映
    _m(
        "ms39 seed のスロットを probe 番号に戻す (seed が分類を運ぶ)",
        _S,
        "return bat.sample_seed(ns, r, probe.triple, k), messages_sha256(",
        "return bat.sample_seed(ns, r, probe.index, k), messages_sha256(",
        ("test_seed_shared_within_triple",),
        "seed を読む key を見ない方策が C = 1 を出せる (Codex 2 回目 HIGH-1)",
    ),
    _m(
        "mp22 pilot の seed のスロットを probe 番号に戻す",
        _P,
        "return bat.sample_seed(ns, r, probe.triple, k), sc.messages_sha256(msgs)",
        "return bat.sample_seed(ns, r, probe.index, k), sc.messages_sha256(msgs)",
        ("test_pilot_seed_shared_within_triple",),
        "pilot の seed が分類を運ぶ (Codex 2 回目 HIGH-1)",
    ),
    _m(
        "mp23 OC の ⊥ gate に本走の envelope を渡さない",
        _P,
        "sc.bottom_gate_ok(botr, bot_max), verdict, sc.VERDICT_INVALID_BATTERY",
        "sc.bottom_gate_ok(botr), verdict, sc.VERDICT_INVALID_BATTERY",
        ("test_oc_uses_the_main_run_envelope",),
        "OC と本走で判定器が違う (Codex 2 回目 MEDIUM-4)",
    ),
    _m(
        "mz20 crn の乱数をつ組で共有しない",
        _Z,
        "u = np.broadcast_to(rng.random((*shape[:-2], 1, 1)), shape)",
        "u = np.broadcast_to(rng.random((*shape[:-1], 1)), shape)",
        ("test_crn_shares_randomness_within_the_triple",),
        "seed の共有を模擬しない (Codex 2 回目 HIGH-1)",
    ),
    _m(
        "mm01 第 1 段の prereg の本文の照合を外す",
        _M,
        'if sealed.get("prereg_body_sha256") != body:',
        "if False:",
        ("test_stage1_seal_allows_only_the_status_line",),
        "pilot の後に prereg の規則を差し替えられる (Codex 2 回目 HIGH-2)",
    ),
    _m(
        "mm02 第 1 段の他の対象の照合を外す",
        _M,
        "out = manifest_violations({f: h for f, h in files.items() if f != PREREG}, root)",
        "out: list[str] = []",
        ("test_stage1_seal_allows_only_the_status_line",),
        "pilot の後に封印した成果物を差し替えられる (Codex 2 回目 HIGH-2)",
    ),
    _m(
        "mm03 certification の manifest 検査の sha256 照合を外す",
        _M,
        'if cert.get("manifest_sha256") != sha256(root / SELF):',
        "if False:",
        ("test_certification_binding",),
        "変異試験を通っていない manifest 検査を受け入れる",
    ),
    _m(
        "mm04 見取り図の点の完全性の確認を外す",
        _M,
        "if keys != expected_points(r_count) or len(rows) != len(keys):",
        "if False:",
        ("test_sketch_recheck_detects_missing_points",),
        "点の欠けた見取り図を受け入れる (Codex 2 回目 MEDIUM-5)",
    ),
    _m(
        "mm05 見取り図の行の値の再計算を外す",
        _M,
        'if not _close(v, _num(x["value"])):',
        "if False:",
        ("test_sketch_recheck_recomputes_flags_and_values",),
        "per_seed と食い違う値を受け入れる (Codex 2 回目 MEDIUM-5)",
    ),
    _m(
        "mm06 見取り図の 3 条件の再計算を外す",
        _M,
        "if res.get(flag) is not want:",
        "if False:",
        ("test_sketch_recheck_recomputes_flags_and_values",),
        "報告のフラグを信じる (Codex 2 回目 MEDIUM-5)",
    ),
    _m(
        "mm07 選定の再計算を外す",
        _M,
        'if sketch.get("selection") != sim.select(per_r):',
        "if False:",
        ("test_sketch_recheck_recomputes_selection_and_reach",),
        "規則と違う選定を受け入れる",
    ),
    _m(
        "mm08 最有利行の到達の再計算を外す",
        _M,
        ") is not sim.most_favorable_reaches(sweeps):",
        ') is not sketch.get("most_favorable_reaches"):',
        ("test_sketch_recheck_recomputes_selection_and_reach",),
        "報告の到達フラグを信じる (Codex 2 回目 MEDIUM-5)",
    ),
    _m(
        "mm09 driver の各行の KILLED の確認を外す",
        _M,
        'if any(x.get("status") != "KILLED" for x in rows):',
        "if False:",
        ("test_driver_certification_contract",),
        "SURVIVED を含む driver の証明書を受け入れる (Codex 2 回目 HIGH-3)",
    ),
    _m(
        "mm10 driver の登録変異の照合を外す",
        _M,
        "if want is None or got != want:",
        "if False:",
        (
            "test_driver_certification_contract",
            "test_driver_certification_requires_the_harness_module",
        ),
        "登録外の変異の証明書を受け入れる (Codex 2 回目 HIGH-3)",
    ),
    _m(
        "mm11 driver の sha256 の照合を外す",
        _M,
        "if not p.is_file() or cert.get(key) != {rel: sha256(p)}:",
        "if False:",
        ("test_driver_certification_contract",),
        "旧 driver の証明書で新 driver を封印できる (Codex 2 回目 HIGH-3)",
    ),
    _m(
        "mm12 pilot の判定の再計算を外す",
        _M,
        'for key in ("decision", "R", "masked_max_bottom", "observed"):',
        "for key in ():",
        ("test_pilot_gate_is_recomputed_from_its_inputs",),
        "入力から導かれない GO を受け入れる (Codex 2 回目 MEDIUM-5)",
    ),
    _m(
        "mm13 pilot の provenance の照合を外す",
        _M,
        "or provenance.get(key) != sha256(p)",
        "or False",
        ("test_pilot_provenance_binds_driver_records_and_meta",),
        "別の driver・別の実行の pilot を受け入れる (Codex 2 回目 HIGH-3、3 回目 HIGH-2)",
    ),
    _m(
        "mm14 第 2 段で第 1 段の封印を照合しない",
        _M,
        "        out += stage1_seal_violations(root)\n",
        "",
        ("test_freeze_violations_stage_main_checks_the_seal",),
        "第 2 段が第 1 段の manifest を読まない (Codex 2 回目 HIGH-2)",
    ),
    _m(
        "mm15 certification の期待診断での失敗の照合を外す",
        _M,
        "if any(not isinstance(x, dict) or not failed_for_expected(x) for x in rows):",
        "if False:",
        ("test_certification_requires_the_expected_failure",),
        "違う理由で落ちた変異を KILLED に数える (Codex 3 回目 HIGH-1)",
    ),
    _m(
        "mm16 期待診断と失敗の共通部分を見ない",
        _M,
        "return _strs(failed) and _strs(expect) and bool(set(failed) & set(expect))",
        "return _strs(failed) and _strs(expect)",
        (
            "test_certification_requires_the_expected_failure",
            "test_driver_certification_requires_the_expected_failures",
        ),
        "無関係な test の失敗を期待どおりと数える (Codex 3 回目 HIGH-1)",
    ),
    _m(
        "mm17 meta-test の期待集合が実際に落ちたかを見ない",
        _M,
        "if not _strs(failed) or not set(expect) <= set(failed):",
        "if False:",
        (
            "test_meta_test_must_match_the_registered_cases",
            "test_driver_certification_requires_the_expected_failures",
        ),
        "依存する test が落ちていない meta-test を受け入れる (Codex 3 回目 HIGH-1)",
    ),
    _m(
        "mm18 meta-test の重複を許す",
        _M,
        "    if len(set(labels)) != len(labels):\n        return False\n",
        "",
        (
            "test_meta_test_must_match_the_registered_cases",
            "test_driver_certification_requires_the_expected_failures",
        ),
        "同じケースの行を重ねた meta-test を受け入れる (Codex 3 回目 HIGH-1)",
    ),
    _m(
        "mm19 meta-test の登録ケースとの一致を見ない",
        _M,
        "    if set(labels) != set(want):\n        return False\n",
        "",
        (
            "test_meta_test_must_match_the_registered_cases",
            "test_driver_certification_contract",
            "test_driver_certification_requires_the_expected_failures",
        ),
        "ケースの欠けた meta-test を受け入れる (Codex 3 回目 HIGH-1)",
    ),
    _m(
        "mm20 meta-test の status と期待集合の照合を外す",
        _M,
        'm.get("status") != "FAILED_AS_EXPECTED"\n            or m.get("expected_all_of") != expect',
        "False",
        (
            "test_meta_test_must_match_the_registered_cases",
            "test_driver_certification_requires_the_expected_failures",
        ),
        "登録と違う期待集合の meta-test を受け入れる (Codex 3 回目 HIGH-1)",
    ),
    _m(
        "mm21 driver の期待診断での失敗の照合を外す",
        _M,
        "if any(not failed_for_expected(x) for x in rows):",
        "if False:",
        ("test_driver_certification_requires_the_expected_failures",),
        "Codex 3 回目の反例 (無関係な test だけが落ちた KILLED) を受け入れる",
    ),
    _m(
        "mm22 driver の meta-test の照合を外す",
        _M,
        'if want_meta is None or not meta_contract_ok(cert.get("meta_test"), want_meta):',
        "if False:",
        (
            "test_driver_certification_contract",
            "test_driver_certification_requires_the_expected_failures",
            "test_driver_certification_requires_the_harness_module",
        ),
        "どの no-op 検査をしたか分からない meta-test を受け入れる (Codex 3 回目 HIGH-1)",
    ),
    _m(
        "mm23 driver の meta の登録を証明書自身から読む",
        _M,
        'want_meta = meta_want(getattr(harness, "META_CASES", None))',
        'want_meta = {m.get("label"): m.get("expected_all_of") for m in cert.get("meta_test") or []}',
        ("test_driver_certification_requires_the_expected_failures",),
        "登録外のケース名の meta-test を受け入れる (Codex 3 回目 HIGH-1)",
    ),
    _m(
        "mm24 provenance の records の照合を外す",
        _M,
        '        ("records_sha256", PILOT_RECORDS),\n',
        "",
        ("test_pilot_provenance_binds_driver_records_and_meta",),
        "別の実行の provenance を混ぜた pilot を受け入れる (Codex 3 回目 HIGH-2)",
    ),
    _m(
        "mm25 provenance の meta の照合を外す",
        _M,
        '        ("meta_sha256", PILOT_META),\n',
        "",
        ("test_pilot_provenance_binds_driver_records_and_meta",),
        "別の meta の provenance を受け入れる (Codex 3 回目 HIGH-2)",
    ),
    _m(
        "mm26 provenance の driver の照合を外す",
        _M,
        '        ("driver_sha256", DRIVER),\n',
        "",
        ("test_pilot_provenance_binds_driver_records_and_meta",),
        "未認証の driver の pilot を受け入れる (Codex 2 回目 HIGH-3)",
    ),
    _m(
        "mm27 見取り図の行の R の照合を外す",
        _M,
        'if any(x["R"] != r_count for x in rows):',
        "if False:",
        ("test_sketch_recheck_rejects_invalid_rates_and_row_r",),
        "別の R の行を混ぜた見取り図を受け入れる (Codex 3 回目 MEDIUM-3)",
    ),
    _m(
        "mm28 率の範囲の確認を外す",
        _M,
        "if not all(math.isfinite(v) and 0.0 <= v <= 1.0 for v in vals):",
        "if not all(math.isfinite(v) for v in vals):",
        ("test_sketch_recheck_rejects_invalid_rates_and_row_r",),
        "率 1.5 を受け入れる (Codex 3 回目 MEDIUM-3)",
    ),
    _m(
        "mm29 率の合計の確認を外す",
        _M,
        "if abs(sum(vals) - 1.0) > 1e-9:",
        "if False:",
        ("test_sketch_recheck_rejects_invalid_rates_and_row_r",),
        "合計が 1 でない率の組を受け入れる (Codex 3 回目 MEDIUM-3)",
    ),
    _m(
        "mm30 率の格子の確認を外す",
        _M,
        "if not all(abs(v * n_sims - round(v * n_sims)) < 1e-6 for v in vals):",
        "if False:",
        ("test_sketch_recheck_rejects_invalid_rates_and_row_r",),
        "凍結した MC の回数では出ない率を受け入れる (Codex 3 回目 MEDIUM-3)",
    ),
    _m(
        "mm31 実現 C の有限の確認を外す",
        _M,
        'return math.isfinite(_num(p["realized_C"]))',
        "return True",
        ("test_sketch_recheck_rejects_invalid_rates_and_row_r",),
        "NaN の実現 C を受け入れる (Codex 3 回目 MEDIUM-3)",
    ),
    _m(
        "mm32 seed の数の確認を緩める",
        _M,
        "and len(per_seed) == len(sim.SEEDS)",
        "and len(per_seed) >= 1",
        ("test_sketch_recheck_rejects_invalid_rates_and_row_r",),
        "1 seed だけの行を受け入れる (Codex 3 回目 MEDIUM-3)",
    ),
    _m(
        "mm33 worst_size の再計算を外す",
        _M,
        'if sizes and not _close(_num(res.get("worst_size")), max(sizes)):',
        "if False:",
        ("test_sketch_recheck_recomputes_flags_and_values",),
        "prereg に引く size の最悪値を検査しない",
    ),
    _m(
        "mm34 見取り図の設定の照合を外す",
        _M,
        'if not _same_json(sketch.get("params"), expected_params()):',
        "if False:",
        ("test_sketch_recheck_checks_the_params",),
        "n_sim_power = 1・grid = [] の見取り図を受け入れる (Codex 3 回目 MEDIUM-3)",
    ),
    _m(
        "mm35 sweep の完全性の確認を外す",
        _M,
        "if set(keys) != expected_sweep_points() or len(keys) != len(set(keys)):",
        "if False:",
        ("test_sketch_recheck_checks_the_sweeps",),
        "Codex 3 回目の反例 (sweep を最有利の 1 行だけにする) を受け入れる",
    ),
    _m(
        "mm36 sweep の重複を許す",
        _M,
        " or len(keys) != len(set(keys)):",
        ":",
        ("test_sketch_recheck_checks_the_sweeps",),
        "同じ点の行を重ねた sweep を受け入れる",
    ),
    _m(
        "mm37 sweep の pass の再計算を外す",
        _M,
        'if not _close(_num(x["pass"]), mean):',
        "if False:",
        ("test_sketch_recheck_checks_the_sweeps",),
        "per_seed と食い違う集計の pass を信じる (Codex 3 回目 MEDIUM-3)",
    ),
    _m(
        "mm38 sweep の到達上限の再計算を外す",
        _M,
        'if not _close(_num(x["reachable"]), sim.reachable(x["form"], nu)):',
        "if False:",
        ("test_sketch_recheck_checks_the_sweeps",),
        "記録した到達上限を信じる (Codex 3 回目 MEDIUM-3)",
    ),
    _m(
        "mm39 sweep の率の確認を外す",
        _M,
        'if not per_seed_ok(x["per_seed"], sim.N_SIM_POWER):',
        "if False:",
        ("test_sketch_recheck_checks_the_sweeps",),
        "率として成り立たない sweep の行を受け入れる (Codex 3 回目 MEDIUM-3)",
    ),
    _m(
        "mm40 境目の再計算を外す",
        _M,
        'if sketch.get("boundaries") != fresh:',
        "if False:",
        ("test_sketch_recheck_checks_the_sweeps",),
        "prereg に引く境目を検査しない (Codex 3 回目 MEDIUM-3)",
    ),
    _m(
        "mm41 sweep の点を到達上限で切らない",
        _M,
        "if t <= reach + 1e-9",
        "if True",
        ("test_sketch_recheck_accepts_a_consistent_sketch",),
        "検査器の点集合が本番の sweep と食い違う",
    ),
    _m(
        "mm42 対数オッズの sweep を label_skew に固定しない",
        _M,
        'base = "label_skew" if form == "logodds" else nu.base',
        "base = nu.base",
        ("test_sketch_recheck_accepts_a_consistent_sketch",),
        "検査器の攪乱点が本番の sweep と食い違う",
    ),
    _m(
        "mm43 登録の期待集合が空でも表を作る",
        _M,
        "if not isinstance(expect, (list, tuple, set, frozenset)) or not expect:",
        "if not isinstance(expect, (list, tuple, set, frozenset)):",
        ("test_registries_must_be_well_formed",),
        "Codex 4 回目の反例 (期待集合が空の META_CASES で失敗 0 の meta-test) を受け入れる",
    ),
    _m(
        "mm44 登録の label の重複を許す",
        _M,
        "if not isinstance(label, str) or label in want:",
        "if not isinstance(label, str):",
        ("test_registries_must_be_well_formed",),
        "Codex 4 回目の反例 (label の重複で前の登録が消える) を受け入れる",
    ),
    _m(
        "mm45 登録の test 名の型を見ない",
        _M,
        "        if not all(isinstance(t, str) for t in expect):\n            return None\n",
        "",
        ("test_registries_must_be_well_formed",),
        "test 名でない期待集合の登録を受け入れる",
    ),
    _m(
        "mm46 driver の登録変異を検証せずに表にする",
        _M,
        'want = mutant_want(getattr(harness, "MUTANTS", None))',
        'want = {m.label: sorted(m.expect) for m in getattr(harness, "MUTANTS", [])}',
        ("test_registries_must_be_well_formed",),
        "label の重複した driver の登録変異を受け入れる (Codex 4 回目 HIGH-1)",
    ),
    _m(
        "mm47 数値に JSON の真偽値を数える",
        _M,
        "    if isinstance(x, (int, float)) and not isinstance(x, bool):\n",
        "    if isinstance(x, (int, float)):\n",
        ("test_sketch_recheck_rejects_booleans",),
        "率の 0.0 を false にした見取り図を受け入れる (Codex 4 回目 LOW-2)",
    ),
    _m(
        "mm48 点の欄に JSON の真偽値を許す",
        _M,
        "isinstance(x[k], (str, int, float)) and not isinstance(x[k], bool) for k in keys",
        "isinstance(x[k], (str, int, float)) for k in keys",
        ("test_sketch_recheck_rejects_booleans",),
        "攪乱点の ⊥ 0.0 を false にした行を受け入れる (Codex 4 回目 LOW-2)",
    ),
    _m(
        "mm49 設定の照合で型を見ない",
        _M,
        "return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)",
        "return a == b",
        ("test_sketch_recheck_rejects_booleans",),
        "lambda_fractions の 1.0 を true にした設定を受け入れる (Codex 4 回目 LOW-2)",
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
        "generalization_probe_scorer.py",
        "    comps_positive = np.all(np.asarray(comps) > 0, axis=-1)\n",
        "    return np.full(np.shape(log_e_plus), VERDICT_UNDERPOWERED)\n"
        "    comps_positive = np.all(np.asarray(comps) > 0, axis=-1)\n",
        (
            "test_decide_threshold",
            "test_evaluate_lookup_pass",
            "test_evaluate_blind_no_go",
        ),
    ),
    (
        "structure_violations を空に潰す",
        "generalization_probe_scorer.py",
        "    out: list[str] = []\n    keys = [(s.arm, s.replicate, s.probe_id, s.k) for s in samples]\n",
        "    return []\n"
        "    out: list[str] = []\n    keys = [(s.arm, s.replicate, s.probe_id, s.k) for s in samples]\n",
        ("test_structure_seed", "test_structure_prompt", "test_structure_grid"),
    ),
)


def run_meta(env: dict[str, str]) -> list[dict[str, object]]:
    """複製ツリー (repo の外の一時 dir) で検査関数を no-op に潰し、依存する test が落ちることを見る."""
    rows: list[dict[str, object]] = []
    for label, target, old, new, expect in META_CASES:
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="gp_meta_"))
        try:
            (tmp / "scripts").mkdir()
            for name in (*_CERTIFIED, "generalization_probe_key_selection.py"):
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=pathlib.Path, default=None)
    ap.add_argument("--only", default=None, help="label の接頭辞で絞る (開発用)")
    args = ap.parse_args(argv)

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
