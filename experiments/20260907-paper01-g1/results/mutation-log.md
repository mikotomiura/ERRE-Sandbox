# Mutation testing log — I-003 `decide_external()` 判定 5 行

- **対象ファイル**: `scripts/paper01_external_audit.py`
- **手順**: `experiments/20260907-paper01-g1/results` 配下の一時 mutate スクリプト
  (`C:\Users\johnd\AppData\Local\Temp\claude\...\scratchpad\mutate.py`) で
  対象 1 行を文字列置換 → `assert new != old` (置換が実際に適用されたことの確認、
  no-op mutation の落とし穴回避) → `.venv/Scripts/python.exe -m pytest -q tests/test_paper01_g1`
  を実行 → exit code と落ちた test を記録 → バックアップから復元 →
  `diff` でバックアップと完全一致 (= 復元後 diff 空) を確認。1 つずつ直列に実施。
- **バックアップ**: `decide_external()` 実装完了・全 test/ruff/mypy 緑を確認した直後の
  `scripts/paper01_external_audit.py` を一時ディレクトリへ `cp` して保持。
  各 mutation 後はこのバックアップへ `cp` で復元し、`diff` で 0 差分を確認した
  (`git diff scripts/paper01_external_audit.py` は I-003 の正規実装分の差分が
  常に残るため、mutation 由来の残留が無いことは「復元後ファイル ==
  実装完了直後バックアップ」の byte-diff で検証した)。

## 対象 5 行 (mutation 前の該当行番号)

| # | 判定 | 行 | 元のコード |
|---|---|---|---|
| ① | eligible 判定 | L810 | `eligible = [r for r in family if aggregate_draws(r.eligible_flags)]` |
| ② | engaged 判定 | L812 | `engaged = [r for r in eligible if aggregate_draws(r.engaged_flags)]` |
| ③ | collapsed 判定 | L816 | `collapsed = [r for r in engaged if r.auc_lao_ci_upper < floor]` |
| ④ | `EMBEDDING_FAMILY_EXT` への限定 | L807 | `family = [by_key[key] for key in EMBEDDING_FAMILY_EXT if key in by_key]` |
| ⑤ | CI 跨ぎ判定 (survivor 側) | L814 | `survivors = [r for r in engaged if r.auc_lao_ci_lower >= floor]` |

**設計メモ (④ について)**: 当初 `by_key` の辞書内包表記にも
`if r.key in EMBEDDING_FAMILY_EXT` フィルタを重ねていたが、後段の
`family = [by_key[key] for key in EMBEDDING_FAMILY_EXT ...]` が既に
`EMBEDDING_FAMILY_EXT` のキーしか引かないため、二重防御になり ④ 単体の
mutation が no-op になることが分かった。**`by_key` 側のフィルタは削除し、
`family` 行を唯一のゲートに一本化**してから mutation testing を実施した
(下記 no-op 落とし穴の実測、本ログの「落とし穴の実例」参照)。

## 結果

| # | 何を壊したか | pytest exit code | 落ちた test | 復元後 diff |
|---|---|---|---|---|
| ① | `aggregate_draws(r.eligible_flags)` → `True` (常に eligible) | **1** | `test_ineligible_candidate_is_not_counted_as_collapse` (003-5) | 空 (バックアップと byte 一致) |
| ② | `aggregate_draws(r.engaged_flags)` → `True` (常に engaged) | **1** | `test_mixed_engaged_all_collapsed_is_no_valid_scorer` (003-2) / `test_ineligible_engaged_candidate_does_not_block_verdict` (003-3) / `test_zero_potency_candidate_does_not_grant_pass` (003-6) / `test_invalid_task_battery_paths` (003-7) — 計 4 件 | **1** | 空 |
| ③ | `auc_lao_ci_upper < floor` → `auc_lao_ci_upper >= floor` (向き反転) | **1** | `test_mixed_engaged_all_collapsed_is_no_valid_scorer` (003-2) / `test_ineligible_engaged_candidate_does_not_block_verdict` (003-3) / `test_all_verdicts_are_reachable` (003-4) / `test_ci_crossing_floor_is_inconclusive` (003-8) / `test_auc_floor_is_read_through_at_call_time` (bonus) — 計 5 件 | 空 |
| ④ | `family = [by_key[key] for key in EMBEDDING_FAMILY_EXT if key in by_key]` → `family = list(by_key.values())` (family 限定を撤去) | **1** | `test_lexical_candidate_does_not_drive_verdict` (003-9) | 空 |
| ⑤ | `auc_lao_ci_lower >= floor` → `auc_lao_ci_lower < floor` (向き反転) | **1** | `test_mixed_engaged_all_collapsed_is_no_valid_scorer` (003-2) / `test_ineligible_engaged_candidate_does_not_block_verdict` (003-3) / `test_all_verdicts_are_reachable` (003-4) / `test_ineligible_candidate_is_not_counted_as_collapse` (003-5) / `test_ci_crossing_floor_is_inconclusive` (003-8) / `test_lexical_candidate_does_not_drive_verdict` (003-9) / `test_auc_floor_is_read_through_at_call_time` (bonus) — 計 7 件 | 空 |

**5/5 が実際に落ちた (exit code 1)。5/5 とも復元後 `diff` が空 (バックアップと byte 一致)。**

## 落とし穴の実例 (「置換が no-op になる」を実際に踏んで直した記録)

実装の初版では `by_key` の構築時にも `if r.key in EMBEDDING_FAMILY_EXT` フィルタを
入れていた (「EMBEDDING_FAMILY_EXT への限定」をこの行だと考えていた)。しかし
後続行 `family = [by_key[key] for key in EMBEDDING_FAMILY_EXT if key in by_key]`
が既に `EMBEDDING_FAMILY_EXT` のキーだけを引くため、**`by_key` 側のフィルタを
削除しても `family` の実際の中身は変わらない** ことに気づいた
(二重防御 = 片方を壊しても機能上は no-op)。`mutate.py` の
`assert mutated != original` はテキストが変わったことしか保証しないため、
「文字列としては壊れたがロジックとしては壊れていない」ケースを検出できない
——これは正しく mutation を適用しても機能的 survive が起きうる、という
`feedback_witness_needs_mutation_testing.md` が警告する落とし穴の具体例だった。

**対処**: `by_key` 側の冗長フィルタを削除し、`family` 行を唯一のゲートに一本化する
コード修正を行った (`scripts/paper01_external_audit.py` の実装そのものを変更、
テストとは独立)。修正後に ④ を再実施し、上記のとおり
`test_lexical_candidate_does_not_drive_verdict` が確実に落ちることを確認した。

## 検証コマンド (全て緑)

```
.venv/Scripts/python.exe -m pytest -q tests/test_paper01_g1        # 35 passed
.venv/Scripts/python.exe -m ruff format --check scripts/paper01_external_audit.py tests/test_paper01_g1  # 6 files already formatted
.venv/Scripts/python.exe -m ruff check scripts/paper01_external_audit.py tests/test_paper01_g1            # All checks passed!
.venv/Scripts/python.exe -m mypy src                                # Success: no issues found in 247 source files
git status --porcelain src/erre_sandbox/evidence scripts/es4_scorer_diag.py  # (空)
```

## 独立 mutation (main オーケストレータが subagent とは別に実施、2026-09-07)

subagent の自己申告を信用しないため、main が **本 issue の存在理由そのもの**
(design-final §6 / Opus HIGH-2 が指摘した未定義領域) を狙った mutation を
別途 1 件かけた。

| # | 壊した内容 | exit code | 落ちた test | 復元後 diff |
|---|---|---|---|---|
| ⑥ | `collapsed` を `engaged` (E2) でなく `eligible` (E) 起点で構築し、比較も `len(collapsed) == len(eligible)` に変える (= 当初案の歴史的バグの再現) | **1** | `test_mixed_engaged_all_collapsed_is_no_valid_scorer` / `test_ineligible_engaged_candidate_does_not_block_verdict` | 空 (byte 一致) |

置換は `assert old in s` と `assert s2 != s` の二重確認つきで適用した
(no-op mutation を「生存」と誤読しないため)。

### 併せて実施した独立の全域性・到達可能性検査

`decide_external()` を main が直接呼び、以下を確認した。

- **4 verdict すべてに到達**する入力を構成できた
- 特に `NO_VALID_SCORER` は `E = (X0, X1)` / `E2 = (X0,)` — すなわち
  **eligible だが engaged でない候補 (potency=0) が 1 つ混じった状態**で到達した。
  これは当初案では到達不能だった配置であり、§6 が `E` ではなく `E2` の中で
  `collapsed == E2` を見る理由がそのまま観測されている
- 入力空間 (eligible × engaged × クラス不足 × lexical 混在 × CI 3 パターン、
  候補 2-3 件) を総当たりして **例外 0 件**、返る verdict は常に enum の 4 語のいずれか

## I-004 mutation testing — 統計層 (`auc_stratified` / draw 集約 / bootstrap)

- **対象ファイル**: `scripts/paper01_external_audit.py` (§5 統計節)
- **手順**: I-003 と同一の手順を踏襲。`experiments/20260907-paper01-g1/results`
  一時 mutate スクリプト (`C:\Users\johnd\AppData\Local\Temp\claude\...\scratchpad\mutate.py`)
  で対象コード片を文字列置換 → `assert old in text` (置換前に対象文字列が実在することを確認) →
  `assert mutated != text` (置換が実際に適用され no-op でないことを確認) →
  `.venv/Scripts/python.exe -m pytest -q tests/test_paper01_g1` を実行 → exit code と
  落ちた test を記録 → I-004 実装完了直後のバックアップへ `cp` で復元 → `diff` で
  バックアップと byte 一致を確認。4 件を直列に実施し、都度 diff 空を確認してから次へ進んだ。
- **バックアップ**: 統計節の実装完了・全 test/ruff/mypy 緑を確認した直後の
  `scripts/paper01_external_audit.py` を一時ディレクトリへ `cp` して保持
  (`paper01_external_audit.py.bak`)。

### 対象 4 行 (設計指示の候補①-④、すべて実施)

| # | 何を壊したか | 元のコード | 変更後 |
|---|---|---|---|
| ① | 層別の重み `w(o) = n_good·n_common` → 一律 1 | `weight = n_good * n_common` | `weight = 1` |
| ② | `AUC_membership` の `1 - m` → `m` (向き反転を撤去) | `flipped = [1.0 - m for m in membership]` | `flipped = [m for m in membership]` |
| ③ | draw 集約 (`collapsed`) → 周辺中央値方式 (`median(AUC_full)`/`median(AUC_LAO)` を別々に取って比較) | `collapsed=aggregate_draws(collapsed_flags),` | `collapsed=(median(AUC_LAO) < floor) and (median(AUC_full) >= floor),` (割合集約を撤去) |
| ④ | bootstrap の層を (物体×クラス) → 物体のみ (`for cls in (0, 1):` のクラス内 stratify を撤去) | `for obj in ...: for cls in (0, 1): stratum = (objects==obj)&(labels==cls); ...` | `for obj in ...: stratum = (objects==obj); ...` (クラス層別を撤去) |

### 結果

| # | pytest exit code | 落ちた test | 復元後 diff |
|---|---|---|---|
| ① | **1** | `test_auc_stratified_matches_hand_computation` (004-1)。`0.5 == 0.6` で fail (重みが 3:2 でなく 1:1 になった影響が数値に現れた) | 空 (バックアップと byte 一致) |
| ② | **1** | `test_membership_auc_orientation` (004-7)。`flipped_result` が期待の `1.0` でなく `0.0` (向き反転が撤去され unflipped と同値になった) | 空 |
| ③ | **1** | `test_aggregation_is_per_draw_not_marginal_median` (004-5)。`aggregate.collapsed` が期待の `False` でなく `True` (周辺中央値方式は元々このテストが検出するよう設計した誤判定そのものを再現した) | 空 |
| ④ | **1** | `test_bootstrap_strata_are_object_by_class` (004-6)。resample 後の `(object, label)` multiset が元と不一致 (`('A', 1): 1` vs `('A', 1): 2` 等、クラス境界を越えて resample された) | 空 |

**4/4 が実際に落ちた (exit code 1)。4/4 とも復元後 `diff` が空 (バックアップと byte 一致)。**

すべての置換前に `assert old in text` (対象文字列が実在することの確認)、置換後に
`assert mutated != text` (置換が実際に適用されたことの確認) を `mutate.py` 内で機械的に
実施した。I-003 ログが記録した「置換が no-op になる」落とし穴 (二重防御で片方を壊しても
機能上変化しない) は、本 4 件では発生しなかった — 対象行それぞれが判定/計算の唯一のゲート
だったため。

### 検証コマンド (mutation 実施前後、すべて緑)

```
.venv/Scripts/python.exe -m pytest -q tests/test_paper01_g1                 # 44 passed
.venv/Scripts/python.exe -m ruff format --check scripts/paper01_external_audit.py tests/test_paper01_g1  # 7 files already formatted
.venv/Scripts/python.exe -m ruff check scripts/paper01_external_audit.py tests/test_paper01_g1            # All checks passed!
.venv/Scripts/python.exe -m mypy src                                        # Success: no issues found in 247 source files
git status --porcelain src/erre_sandbox/evidence scripts/es4_scorer_diag.py # (空)
```

### bootstrap 実行時間の実測 (`N_RESAMPLES=10000`、design-final.md §5.2 の正規値)

`bootstrap_stratified_drop` を 1 回呼ぶ実測 (中央値 draw 1 件分、合成データ、
`np.random.default_rng` 固定 seed)。

| 規模 | 物体数 | 総アイテム数 | 実測秒数 |
|---|---|---|---|
| Ocsai 相当 (21 物体、good~40/common~200 per obj) | 21 | 5,040 | **116.5 秒** |
| Cambridge 相当 (2 物体、good~40/common~2000 per obj) | 2 | 4,080 | **73.6 秒** |

**結論**: 1 候補 (1 candidate) の bootstrap は中央値 draw 1 回のみに適用されるため
(draw ごとには回さない、design-final.md §5.2)、実測 1-2 分/候補は実用範囲内と判断した。
`corpus × 候補 × アーム` の組み合わせ全体 (概算: 6 embedding 候補 × 2 corpus ×
平均 2-3 アーム ≈ 24-36 回) でも概算合計 30-70 分程度で、§5.3 で回避対象とした
「200 抽出 × 8 候補 × 2 corpus × 2 回実行で十数時間」規模には遠く及ばない。**停止条件
(実行時間が実用外) には該当しないと判断し、実装を継続した。**

## 独立 mutation — I-004 統計層 (main オーケストレータ、2026-09-07)

subagent の 4 件とは別に main が独立にかけた。**うち 3 件が最初 survive し、
test を追加して塞いだ** (subagent の自己申告だけでは通っていた)。

### 第 1 波 (test 追加前)

| # | 壊した内容 | exit code | 判定 |
|---|---|---|---|
| A | `auc_stratified` を pooled `auc` にすり替え (§1 主 estimand の撤去) | 1 | killed (6 test) |
| B | `is_draw_engaged`: `potency > 0.0` → `>= 0.0` | **0** | **SURVIVED** |
| C | `is_draw_collapsed`: `auc_lao < threshold` → `<= threshold` | **0** | **SURVIVED** |
| D | `is_draw_collapsed`: `engaged` 連言を削除 | **0** | **SURVIVED** |
| E | `is_draw_collapsed`: `eligible` 連言を削除 | 1 | killed (1 test) |

B / C / D は **DA-G1-11 (potency=0 に PASS を与えない) と design-final §5.1 の
per-draw 述語そのもの**であり、覆われていないのは load-bearing な欠落だった。
特に D は I-003 が存在する理由 (engaged 連言の欠落) の **per-draw 版**である。

### 追加した test

`tests/test_paper01_g1/test_statistics.py` に 5 件:
`test_draw_engaged_requires_strictly_positive_potency` /
`test_draw_collapsed_requires_auc_strictly_below_floor` /
`test_draw_collapsed_requires_engaged` /
`test_draw_collapsed_requires_eligible` /
`test_draw_eligible_boundary_is_inclusive_at_the_floor`

### 第 2 波 (test 追加後) — 全 kill

| # | 壊した内容 | exit code | 落ちた test |
|---|---|---|---|
| B | `potency > 0.0` → `>= 0.0` | 1 | `test_draw_engaged_requires_strictly_positive_potency` |
| C | `auc_lao < threshold` → `<=` | 1 | `test_draw_collapsed_requires_auc_strictly_below_floor` |
| D | `engaged` 連言を削除 | 1 | `test_draw_collapsed_requires_engaged` |
| E | `eligible` 連言を削除 | 1 | `test_aggregation_is_per_draw_not_marginal_median` / `test_draw_collapsed_requires_eligible` |
| F | `is_draw_eligible`: `>= threshold` → `>` | 1 | `test_draw_eligible_boundary_is_inclusive_at_the_floor` |

復元後は全件バックアップと byte 一致。

### 教訓 (retrospective へ持ち越す)

**「mutation を N 件かけて全部 kill した」という自己申告は、どの行を選んだかに
依存する。** subagent が選んだ 4 行はいずれも kill されたが、**選ばれなかった
per-draw 述語 3 件は素通りだった**。境界述語 (`>` vs `>=`、連言の各項) は
機械的に列挙して総当たりする方が漏れない。
