# Mutation testing log -- Loop I-007a (実走の前段: run.sh 一式 / notes.md 骨格)

Target: `scripts/paper01_scope_condition.py` §「I-007: fidelity pin (b)+(c)
の中身、--scope の Cambridge セル配線」(`cli_fidelity` / `measure_g1_arm_a_
fidelity` / `g1_arm_a_fidelity_matches` / `build_split_cells` /
`_gather_cambridge` / `_score_cambridge_arm_s` / `cli_scope`)、
`experiments/20260908-paper01-scope-condition/run_gate.py`
(`hashes_match`)、`experiments/20260908-paper01-scope-condition/
build_metrics.py` (`build_metrics`)。

Test suites:
- `tests/test_paper01_scope/test_scope_cli_wiring.py` (28 tests, I-007a 新規)
- `tests/test_paper01_scope/test_run_artifacts.py` (20 tests, I-007a 新規)
- 既存の `tests/test_paper01_scope` フルパッケージ (129 passed / 1 skipped
  合計 -- 上記 2 ファイルの計 48 test を含む)

**各 mutant は実際に worktree の対象ファイルへ適用し、実際に pytest を
走らせ、下記の fail した test id は実測の出力そのものである** (「落ちる
はず」という想定ではない)。driver script (`assert old in content` を
mutate 前に / `assert new in content` を write 後・pytest 実行前に /
`Path.read_bytes()`/`Path.write_bytes()` のみ使用、`read_text`/`write_text`
は CRLF 変換の懸念があるため一切使わない / 各 mutant 後に元バイト列へ
restore し SHA-256 で照合、最後の mutant 後も含めすべて照合済み) は
`C:\Users\johnd\AppData\Local\Temp\claude\C--ERRE-Sand-Box\
f33f2702-2785-4497-8a5a-f5a9ee7b5619\scratchpad\mutate_i007a.py` に置き、
この worktree のコピーに対して実行した。

**pristine SHA-256** (driver 起動時に記録、全 mutant 処理後も一致を確認済み):

| ファイル | SHA-256 |
|---|---|
| `scripts/paper01_scope_condition.py` | `36ca5b575e674a7c20d3878a82ecb7a6921655db050494f1e96b136e8275f9e5` |
| `experiments/20260908-paper01-scope-condition/run_gate.py` | `78470f15dc75eb12b56ab1bd28cd52df541ae2e1181cfb8f5a8462024f274aa2` |
| `experiments/20260908-paper01-scope-condition/build_metrics.py` | `5949724d8baada43a3f8bacca569ffb879d2a9a9d234de2018be52aa4439f801` |

Command per mutant: `C:/ERRE-Sand_Box/.venv/Scripts/python.exe -B -m pytest
-p no:cacheprovider -q <該当 test ファイル>` (`-B` = `.pyc` を書かない、
`-p no:cacheprovider` = 直前の I-006/I-004 が踏んだ stale bytecode 型の
false negative を避ける、issue 007 指示どおり)。

## Enumerated mutants (7 -- issue 007 が明記した必須 3 種 (M1-M3) + 本
issue 自身の新規コードに対する追加 4 種 (M4-M7))

| id | 分類 (issue 必須 / 追加) | target |
|---|---|---|
| M1 | **issue 007 必須**: 「SHA-256 一致ゲートを常に真にする」 | `run_gate.hashes_match`: `hash_a == hash_b` を `True` に差し替え |
| M2 | **issue 007 必須**: 「--fidelity の不一致で exit 0 を返す」 | `cli_fidelity`: `if mismatch: return FIDELITY_EXIT_MISMATCH` の戻り値を `FIDELITY_EXIT_OK` に差し替え |
| M3 | **issue 007 必須**: 「build_metrics が抽出でなく再計算する」 | `build_metrics.build_metrics`: `stage1.get("median_drop")` の**そのまま返す**箇所を `drop_p5 + drop_p95` の再計算式に差し替え |
| M4 | 境界述語 (追加) | `g1_arm_a_fidelity_matches`: 6 項連言のうち後半 3 項の `and` を `or` に反転 |
| M5 | データ欠如と不一致の優先順位 (追加、issue 007 の「別々の exit code で区別する」に対応) | `cli_fidelity`: mismatch 優先の判定順序を unavailable 優先に反転 |
| M6 | 境界述語 (追加、DA-SC-3 隣接段判定) | `build_split_cells`: `condition1_at_star` の `and` を `or` に反転 |
| M7 | 境界値 (追加) | `G1_ARM_A_TOLERANCE`: `1e-6` を `1.0` に緩める |

## Results

### M1: `hashes_match` を常に `True` にする

```diff
-    return hash_a == hash_b
+    return True
```

- exit code: 1 (**KILLED**)
- `3 failed, 17 passed`
- `FAILED test_hashes_match_detects_mismatch`
- `FAILED test_sha256_of_file_reflects_content`
- `FAILED test_run_gate_check_hashes_cli_exit_code`
  -- `run_gate.main(["check-hashes", a, c])` が異なる内容のファイルに
  対しても `0` を返すようになり、`== 1` の assertion が fail。
  **issue 007 の必須 mutant を実測で kill 済み。**

### M2: `--fidelity` の mismatch 分岐を exit 0 に差し替える

```diff
     if mismatch:
-        return FIDELITY_EXIT_MISMATCH
+        return FIDELITY_EXIT_OK
     if unavailable:
         return FIDELITY_EXIT_SOURCE_UNAVAILABLE
     return FIDELITY_EXIT_OK
```

- exit code: 1 (**KILLED**)
- `3 failed, 21 passed`
- `FAILED test_cli_fidelity_pin_c_mismatch_never_reports_exit_ok`
- `FAILED test_cli_fidelity_pin_b_mismatch_never_reports_exit_ok`
- `FAILED test_cli_fidelity_mismatch_takes_priority_over_unavailable`
  -- 不一致が発生しても `cli_fidelity()` が `0` を返すようになり、
  「不一致は必ず非ゼロ」を確認する 3 test が fail。
  **issue 007 の必須 mutant を実測で kill 済み。**

### M3: `build_metrics` が `median_drop` を再計算するよう差し替える

```diff
-            "median_drop": stage1.get("median_drop"),
+            "median_drop": (stage1.get("drop_p5") or 0) + (stage1.get("drop_p95") or 0),
```

- exit code: 1 (**KILLED**)
- `2 failed, 18 passed`
- `FAILED test_build_metrics_extracts_verbatim_values_never_recomputed`
  -- 入力に設定した sentinel `0.20`(`median_drop`) がそのまま出てくる
  はずが、`drop_p5(0.10) + drop_p95(0.30) = 0.40` という**別の値**に
  変わり fail。
- `FAILED test_build_metrics_changing_the_sentinel_changes_the_output`
  -- 入力の `median_drop` を `0.987654` に変えても出力が `drop_p5+drop_p95`
  の再計算値のままになり `assert metrics[...]["median_drop"] == 0.987654`
  が `assert 0 == 0.987654` — 抽出でなく再計算していることが実測で判明。
  **issue 007 の必須 mutant を実測で kill 済み。**

### M4: `g1_arm_a_fidelity_matches` の連言を選言に緩める

```diff
-        and result.cell_verdict == G1_ARM_A_EXPECTED_CELL_VERDICT
+        or result.cell_verdict == G1_ARM_A_EXPECTED_CELL_VERDICT
         and result.overall_verdict == G1_ARM_A_EXPECTED_OVERALL_VERDICT
         and result.survivors == G1_ARM_A_EXPECTED_SURVIVORS
```

- exit code: 1 (**KILLED**)
- `8 failed, 16 passed`
- `test_g1_arm_a_fidelity_matches_rejects_any_single_disagreement` の
  6 パラメータ全ケース + `test_g1_arm_a_fidelity_matches_tolerance_boundary`
  + `test_cli_fidelity_pin_b_mismatch_never_reports_exit_ok` が fail --
  6 項連言のどれか 1 つだけ食い違う perturbed result が誤って match と
  判定されるようになったことを、パラメータ化 test の全ケースが捕まえた。

### M5: `cli_fidelity` の判定順序を反転 (unavailable を先に return)

```diff
-    if mismatch:
-        return FIDELITY_EXIT_MISMATCH
     if unavailable:
         return FIDELITY_EXIT_SOURCE_UNAVAILABLE
+    if mismatch:
+        return FIDELITY_EXIT_MISMATCH
     return FIDELITY_EXIT_OK
```

- exit code: 1 (**KILLED**)
- `2 failed, 22 passed`
- `FAILED test_cli_fidelity_pin_c_mismatch_never_reports_exit_ok`
  (pin (b) が同時に unavailable なシナリオで、mismatch でなく
  unavailable (`2`) が返るようになり `== 1` が fail)
- `FAILED test_cli_fidelity_mismatch_takes_priority_over_unavailable`
  (この mutant がまさに壊す性質そのものを確認する test)

### M6: `build_split_cells` の `condition1_at_star` を選言に緩める

```diff
-    condition1_at_star = arm_s.verdict == "NO_VALID_SCORER" and arm_a.verdict == "PASS"
+    condition1_at_star = arm_s.verdict == "NO_VALID_SCORER" or arm_a.verdict == "PASS"
```

- exit code: 1 (**KILLED**)
- `1 failed, 23 passed`
- `FAILED test_build_split_cells_no_neighbour_check_when_condition1_absent`
  -- このシナリオは ARM-A が `NO_VALID_SCORER`(≠PASS) なので本来
  condition 1 は成立せず隣接段チェックを一切呼ばないはずが、`or` に
  緩めたことで ARM-S 側の `NO_VALID_SCORER` だけで condition 1 が
  成立してしまい、隣接段 (`tau=0.55`) への余分な `score_cell` 呼び出しが
  発生 -- `calls` リストへの記録件数が `[0.5, 0.9]` の想定 2 件から
  `[0.5, 0.55, 0.9]` の 3 件に増えて fail。

### M7: `G1_ARM_A_TOLERANCE` を `1e-6` から `1.0` へ緩める

```diff
-G1_ARM_A_TOLERANCE: Final[float] = 1e-6
+G1_ARM_A_TOLERANCE: Final[float] = 1.0
```

- exit code: 1 (**KILLED**)
- `4 failed, 20 passed`
- `test_g1_arm_a_fidelity_matches_rejects_any_single_disagreement` の
  数値 3 ケース (`auc_full_at_median_draw` / `auc_lao_at_median_draw` /
  `potency_at_median_draw` をそれぞれ `0.5` にずらしたケース) +
  `test_cli_fidelity_pin_b_mismatch_never_reports_exit_ok` が fail --
  許容誤差が `1.0` まで緩むと `0.5` ずれた perturbed result も
  「一致」と判定されてしまうことを実測で確認。
  (`cell_verdict`/`overall_verdict`/`survivors` の文字列一致ケースは
  この mutant では影響を受けないため引き続き fail しない -- 期待どおり。)

## 生存 mutant

**0 件。** 上記 7 件すべてが実測で KILLED。

## mutation 後の意味突き合わせ工程 (issue 007 の binding 指示)

`--scope` / `--fidelity` は本セッション (I-007a) では実データで一度も
走っていない (Ocsai 到達不能・実走禁止の boundary、`notes.md` 参照) ため、
「出力 JSON の数字を読んで意味を突き合わせる」対象の実データ JSON は
存在しない。代わりに、本 issue が新規に書いたコードが読む・書く実在の
アーティファクトに対して同種の突き合わせを行った:

- `results/mutation-log-I007a.md` (本ファイル) 自体 --
  各 mutant の fail 出力 (上記の pytest 実測ログ) を**要約せず転記**した。
- M3 の突き合わせで、`build_metrics` の出力する `metrics.json`
  相当の dict (`_FAKE_SCOPE` fixture 由来) の `stage1.median_drop`
  フィールドが、mutation 前は入力の `0.20`/`0.987654` (sentinel) と
  **完全一致**し、mutation 後は `drop_p5+drop_p95` の再計算値
  (`0.40`) に変わることを、pytest の assertion diff (`assert 0 ==
  0.987654` 等) で実測確認した -- これは「全 test 緑・全 mutant kill
  でも意味が壊れている」型の欠陥 (G1 ADR §7 の反省) を、build_metrics
  の**出力値そのもの**を突き合わせることで捕まえる設計になっている。
- M6 の突き合わせで、`build_split_cells` が実際に `score_cell` へ渡す
  `tau` 引数列 (`calls` リスト) を直接記録・比較し、隣接段チェックが
  「呼ばれるべきでない場面で呼ばれていないか」を生の呼び出し引数で
  確認した (集約統計でなく配線そのものを見る、design-final.md §7 の
  「spy で生の呼び出し引数を見て kill」規律)。

## 逸脱・気づき

- 必須 3 mutant (M1-M3) はすべて 1 回で KILLED (再試行不要)。
- M6 は当初「4-cell 交差を union に緩める」(I-006 の M5 と同型) も
  候補にしていたが、`common_active_objects` 自体は I-006 の anchor
  節にあり本 issue の Allowed Files 外 (既存 issue の anchor 節を
  書き換えない、という binding 制約) のため対象から外し、代わりに
  本 issue 自身が新規に書いた `condition1_at_star` の連言を対象にした。
- driver 実行中の pytest 出力が Windows のデフォルトコンソール
  エンコーディング (cp932) の都合で日本語コメント部分が文字化けして
  見えたが、assertion の実測内容 (fail した test id / exit code /
  診断メッセージ) は文字化けせず正しく読めており、判定には影響していない。
