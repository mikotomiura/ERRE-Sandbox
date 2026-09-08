# Mutation testing log -- Loop I-005 (判定規則 decide_scope())

Target: `scripts/paper01_scope_condition.py` §「I-005: decision rule --
decide_scope()」(`decide_scope` / `_stage0_t_s_delta` / the `FAIL_PRECEDENCE`
consumption inside `decide_scope`). Test suite:
`tests/test_paper01_scope/test_decision_rule.py` (11 tests), run together
with the full `tests/test_paper01_scope` package (39 tests total: the 28
pre-existing I-001/I-001b/I-002 tests + these 11) so a mutant that happens to
break an earlier issue's contract would also surface.

Per `feedback_witness_needs_mutation_testing` / issue 005 AC 005-MUT: each
mutant below was **actually applied to the worktree's own copy of the file,
actually run through pytest, and the failing test id(s) below are the real
observed output** -- not an assumption about which assertion "should" catch
it. Driver script (`assert old in s` before mutating / `assert new != old` /
`assert new in on_disk` after writing / SHA-256 restore check after every
mutant) ran from
`C:\Users\johnd\AppData\Local\Temp\claude\C--ERRE-Sand-Box\f33f2702-2785-4497-8a5a-f5a9ee7b5619\scratchpad\mutate_i005.py`
against this worktree's copy of the target file; the file was restored to
its pristine, hash-verified byte-identical state after every single mutant,
including after the final one (verified again at driver exit:
`final restore hash match: True`).

**Tooling gotcha hit and fixed (byte-safety)**: the driver's first run used
`Path.read_text()` / `Path.write_text()`, which apply universal-newline
translation. This worktree's copy of the target file is LF-only; the first
`write_text()` call silently turned it into CRLF, and the restore-hash
assertion correctly caught the mismatch (`git diff --stat` afterwards showed
only the intended 195-line insertion in content terms, but `git status`
warned "CRLF will be replaced by LF"). Fixed by switching the driver to
`Path.read_bytes()` / `Path.write_bytes()` with manual UTF-8 decode/encode
(no newline translation at all) before re-running -- this is the same class
of gotcha `mutation-log-I001b.md` recorded for its CRLF checkout, mirrored
here for an LF checkout. The file was manually re-normalised to LF and all
four verify commands re-confirmed green before the mutation run that
produced the results below.

Command per mutant: `pytest -q tests/test_paper01_scope -v` (39 collected),
full stdout+stderr captured, `FAILED <nodeid>` lines parsed for the table
below.

## Enumerated mutants (11, all within this issue's own anchor section)

| id | category (issue text / design-final.md §7) | target |
|---|---|---|
| M1 | Stage 1 override (**this issue's named core mutant, AC 005-MUT**) | `write_eligible` re-derived from `not stage1.deflation_supported` instead of `stage1_outcome == "DEFLATION_REJECTED"` |
| M2 | 境界述語 `<` vs `>` | F4: `no_material_delta` direction |
| M3 | 境界述語 `>` vs `<` | T-confound: `t_driven` direction |
| M4 | 境界述語 `<` vs `>` | F2: `object_loss` direction |
| M5 | 述語の比較対象 | F3: `audit_inactive` target string |
| M6 | 述語の否定 `==` vs `!=` | F5: `cambridge_contradiction` |
| M7 | 境界述語 `>` vs `<` | F1: `rho_unreachable` direction |
| M8 | `FAIL_PRECEDENCE` の順序 | `fail_reason` の走査順を `reversed(FAIL_PRECEDENCE)` に |
| M9 | 連言の各項 (§3 condition 3) | `condition_c_supported` から `both_splits_robust` 項を削除 |
| M10 | 連言の各項 (§3 condition 1&2) | `condition_c_supported` から `both_splits_supported` 項を削除 |
| M11 | 連言の各項 (§3 condition 4) | `condition_c_supported` の F1-F6 ゲート項を `True` 定数に置換 |

## Results

### M1: Stage 1 override -- `not stage1.deflation_supported` へ差し戻し

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed: `test_decision_rule.py::test_inconclusive_never_derives_write_right`
- note: **this is the issue-mandated core mutant.** `INCONCLUSIVE` と
  `DEFLATION_REJECTED` はどちらも `deflation_supported == False` を共有する
  ため、`not deflation_supported` から書く権利を導出すると
  `stage1_outcome == "INCONCLUSIVE"` の入力でも `verdict == "WRITE"` に
  なってしまう。実際に当てて確認したところ、
  `test_inconclusive_never_derives_write_right` の
  `assert inconclusive.verdict == "DO_NOT_WRITE"` が直接落ちた
  (mutant 下では `inconclusive.verdict == "WRITE"` になっていた) --
  「INCONCLUSIVE から WRITE を出す mutant が kill される」ことを実地で確認。
  他の 9 テストは無関係 (`deflation_supported` が絡む分岐を通らない) ため
  巻き込まれず、この 1 本だけが単独で落ちた -- 過大申告を避けるため、
  この mutant を kill するのは他ではなくこの assertion だけであることを
  明記する。

### M2: F4 `no_material_delta` 方向反転 (`<` -> `>`)

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed (10): `test_both_outcomes_are_reachable`,
  `test_each_fail_branch_is_reachable`,
  `test_fail_precedence_resolves_simultaneous_branches`,
  `test_deflation_overrides_stage2`,
  `test_inconclusive_never_derives_write_right`,
  `test_split_disagreement_is_not_support`,
  `test_single_point_dependence_is_not_support`,
  `test_cambridge_contradiction_only_on_pass`,
  `test_t_attribution_requires_note_but_does_not_fail`,
  `test_no_material_delta_is_f4`
- note: この方向反転は「材料差あり」の baseline fixture (diff=0.39) を
  誤って F4 発火させ、あわせて「材料差なし」の fixture (diff=0.005) の
  F4 発火を止める -- 影響範囲が広く、`_supportive_cells()` を使う
  ほぼ全 test が連鎖的に落ちた。直接の専用 witness は
  `test_no_material_delta_is_f4` (F4 が消える方) と
  `test_both_outcomes_are_reachable` (baseline に誤って F4 が付く方)。

### M3: T-confound `t_driven` 方向反転 (`>` -> `<`)

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed: `test_t_attribution_requires_note_but_does_not_fail`
- note: 他の 10 test には影響しない -- `t_driven` は
  `t_confound_note_required` のみに効き、`condition_c_supported` /
  `verdict` / `fail_reason` を一切動かさない設計 (design-final.md HIGH-3:
  T 側は探索的、verdict には使わない) の通り、単独 witness になった。

### M4: F2 `object_loss` 方向反転 (`<` -> `>`)

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed (8): `test_both_outcomes_are_reachable`,
  `test_each_fail_branch_is_reachable`, `test_deflation_overrides_stage2`,
  `test_inconclusive_never_derives_write_right`,
  `test_split_disagreement_is_not_support`,
  `test_single_point_dependence_is_not_support`,
  `test_cambridge_contradiction_only_on_pass`,
  `test_t_attribution_requires_note_but_does_not_fail`
- note: `_supportive_cells()` の baseline は ARM-A/ARM-S が同数の
  active_objects (4件=4件) を持つため、`len(s) < len(a)*0.5` は元々
  False (4 < 2 は False)。反転後は `len(s) > len(a)*0.5` (4 > 2 は
  True) となり baseline 全体が誤って F2 発火 -- 連鎖的に多数の supportive
  系 test が落ちた。専用 witness は `test_each_fail_branch_is_reachable`
  の F2 ケース (`fail_reason == "F2"` が別の値になる)。

### M5: F3 `audit_inactive` 比較対象を `INVALID_TASK_BATTERY` -> `NO_VALID_SCORER`

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed (8): M4 と同一集合
- note: mutant 下では f3_cells (`arm_s.verdict == "INVALID_TASK_BATTERY"`)
  の `audit_inactive` が False になり `fail_reason` が `None` に落ちる
  (`test_each_fail_branch_is_reachable` の F3 ケースが直接 witness)。
  同時に `_supportive_cells()` の baseline (`arm_s.verdict ==
  "NO_VALID_SCORER"`) が誤って `audit_inactive=True` になり、baseline を
  使う他の test も連鎖的に落ちた。

### M6: F5 `cambridge_contradiction` 否定 (`==` -> `!=`)

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed (9): M2 と同一集合 + `test_fail_precedence_resolves_simultaneous_branches`
- note: PASS/非PASS が完全に反転するため、AC 005-9 の両方向
  (`test_cambridge_contradiction_only_on_pass`) と、F4/F5 同時到達を扱う
  `test_fail_precedence_resolves_simultaneous_branches` も直接巻き込まれた
  (mutant 下では baseline の `INCONCLUSIVE_UNDERPOWERED` が誤って F5 を
  発火させる)。

### M7: F1 `rho_unreachable` 方向反転 (`>` -> `<`)

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed (8): M4 と同一集合
- note: baseline (`rho_int_primary=0.5`, `rho_by_tau[-1]=0.40`) は本来
  `0.40 > 0.5` = False (F1 不発火) だが、反転後は `0.40 < 0.5` = True と
  なり baseline 全体が誤って F1 発火。専用 witness は
  `test_each_fail_branch_is_reachable` の F1 ケース。

### M8: `FAIL_PRECEDENCE` 走査順を `reversed(...)` に

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed: `test_fail_precedence_resolves_simultaneous_branches`
- note: F4/F5 同時到達 fixture で `fail_reason` が `"F4"` から `"F5"` に
  変わり、AC 005-4 の中心アサーションが直接落ちた -- 他の test は
  F1-F7 が単独でしか到達しない fixture のため影響を受けなかった
  (優先順位の入れ替えは「複数同時到達」以外では観測不能)。この test
  内部の `monkeypatch.setattr(mod, "FAIL_PRECEDENCE", ...)` による
  非恒真性チェックと合わせて、`FAIL_PRECEDENCE` の消費順序が
  実際に load-bearing であることを二重に確認した。

### M9: `condition_c_supported` から `both_splits_robust` 項を削除

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed: `test_each_fail_branch_is_reachable` (F7 ケース),
  `test_single_point_dependence_is_not_support`
- note: F7 (単点依存) fixture は `both_splits_supported=True` かつ
  `both_splits_robust=False` だが F1-F6 はどれも該当しない --
  robust 項を落とすと `condition_c_supported` が誤って `True` になる。
  §3 condition 3 (τ* 隣接段) が単独で load-bearing であることの直接証拠。

### M10: `condition_c_supported` から `both_splits_supported` 項を削除

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed: `test_both_outcomes_are_reachable`,
  `test_one_sided_evidence_is_not_support`
- note: AC 005-6 の fixture (両分割とも ARM-A が `PASS` でない = cond1
  両方 False、分割は一致) は F6 (分割不一致) を誘発しない -- そのため
  `both_splits_supported` 項を落とすと、他に条件 C を否定する項が無く
  `condition_c_supported` が誤って `True` になった。
  §3 condition 1&2 が F6 とは独立に load-bearing であることの直接証拠
  (F6 は「不一致」だけを見るため「両方とも不支持で一致」なケースを
  捕まえられない -- この mutant が生きていたら見逃していた穴)。

### M11: `condition_c_supported` の F1-F6 ゲート項を `True` 定数に置換

- verdict: **KILLED**
- exit code: 1
- failing test(s) observed: `test_each_fail_branch_is_reachable` (F4 ケース),
  `test_cambridge_contradiction_only_on_pass`, `test_no_material_delta_is_f4`
- note: F4 (材料差なし) fixture は `both_splits_supported=True` かつ
  `both_splits_robust=True` -- F1-F6 ゲートだけが `condition_c_supported`
  を `False` にしている。ゲートを定数 `True` に置換すると誤って `True`
  になり、AC 005-11 の中心アサーションが直接落ちた。

## Summary

- **11/11 mutants KILLED, 0 survivors.**
- 事前登録された 4 分類 (issue 本文 / design-final.md §7) を全てカバー:
  連言の各項 (M9/M10/M11)、境界述語の向き (M2/M3/M4/M7)、
  `FAIL_PRECEDENCE` の順序 (M8)、Stage 1 上書き (M1)。
- **M1 (この issue の核: 「INCONCLUSIVE から WRITE を出す mutant」)は
  実地で kill を確認した** -- `test_inconclusive_never_derives_write_right`
  の `verdict == "DO_NOT_WRITE"` アサーションが直接落ち、他のどの test も
  この mutant では巻き込まれなかった (過大申告なし)。
- witness の効き方は **すべて実際に mutant を当てて観測**した
  (docstring から「効くはず」と書く前に driver の実行結果を先に見た) --
  M9/M10 はどちらも「§3 の 4 条件のうち特定の 1 項だけが独立に
  load-bearing である」ことを、他の項では代替不可能な fixture で
  直接証明している (とくに M10 は F6 だけでは捕まえられない
  「両分割一致で不支持」というケースの穴を塞いでいることを確認した)。
- ファイル復元は毎回 SHA-256 で pristine と完全一致することを確認
  (`final restore hash match: True`)。最終 sanity run
  (`pytest -q tests/test_paper01_scope`) も exit 0 (39 passed)。

## Post-mutation semantic cross-check (design-final.md §7 item 4)

`decide_scope()` はこの issue の scope では JSON を emit しない
(`results/scope.json` は I-007 の責務)。適用可能な代替として、
各 mutant 適用後に手計算した期待値 (baseline `delta_int=0.20` /
`delta_ext=0.59` -> diff=0.39 > EPS=0.01、T 由来 fixture
`t_int-t_ext=0.40` > `s_int-s_ext=0.01`、F2 の `4 < 4*0.5=2` は False
だが `2 < 10*0.5=5` は True 等) を、実装を読み返す前に本ログの各節へ
先に書き下し、driver の実測結果と突き合わせた。数値の意味が
「もっともらしいが誤った値」にすり替わっていないかを、実装から
読み取った値でなく紙の上で導いた値で確認する discipline
(`mutation-log-I002.md` と同じ手順) を踏襲している。

## 復元確認

全 11 mutant 適用後、`scripts/paper01_scope_condition.py` を SHA-256 で
mutation 前の on-disk バイト列と比較し、**完全一致**を確認
(`final restore hash match: True`)。`git diff --stat` は本 issue の意図した
195 行追加のみを示し、CRLF 警告は出ていない (driver 初回実行時に
`Path.write_text()` の universal-newline 変換で一度 CRLF 化する事故が
あったが、`Path.read_bytes()`/`write_bytes()` へ切り替えて再実行し、
手動で LF に正規化した上で最終確認済み)。
