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

## I-005 mutation testing — Cambridge adapter / オーケストレーション新規ロジック

- **対象ファイル**: `scripts/paper01_external_audit.py` (I-005 で新規追加した
  Cambridge adapter + `run_cambridge_split` オーケストレーション部)
- **手順**: I-003/I-004 と同一 (`assert old in s` + `assert new != old` の二重確認 →
  `pytest -q tests/test_paper01_g1 -m "not eval"` → exit code と落ちた test 名を記録 →
  バックアップから `cp` で復元 → `diff` で byte 一致確認)。1 つずつ直列に実施。
  `-m "not eval"` を使ったのは `@pytest.mark.eval` の実 xlsx end-to-end (数分かかる)
  が判定ロジック自体には触れないため — mutation の高速反復に不要な待ち時間を避けた
  (最終確認では eval 込みの `pytest -q tests/test_paper01_g1` をフルセットで実行し
  緑を確認、下記「検証コマンド」参照)。
- **バックアップ**: I-005 実装完了・ruff/mypy/test 全緑を確認した直後の
  `scripts/paper01_external_audit.py` を都度スクラッチディレクトリへ保持し、
  各 mutation 後にそこから復元した。

### 指定された 4 行 (① eligible ② collapsed ③ potency>0 ④ EMBEDDING_FAMILY_EXT) について

`is_draw_eligible` (①) / `is_draw_collapsed` (②) / `is_draw_engaged` の
`potency > 0.0` (③) は **I-004 で導入された関数そのもの**であり、上記 I-004 節
(「§5.1 draw-level 述語」) で境界述語 (`>` vs `>=`、連言の各項) まで含めて
総当たり済み・全 kill 確認済み (`test_draw_eligible_boundary_is_inclusive_at_the_floor`
等)。I-005 はこれらの実装を**一切変更せず**、`build_candidate_report` /
`score_rows_for_draw` 経由で**呼び出すだけ**なので、I-005 側で再度同じ行を
壊すのは冗長 mutation になる可能性が高いと予想したが、**実際に境界 mutation を
再実施して確かめた** (下表「再確認」行)。結果は当初の想定と異なった: **I-005 側
005-1〜005-7 の新規テストは境界 mutation を検出しなかった** (固定フィクスチャが
floor から離れた値を使うため)。①②③の境界保護は依然 I-004 の既存 test だけが
担っており、I-005 はこれらの述語の**正常経路** (境界でない eligible/ineligible)
を `build_candidate_report` 経由で確認するに留まる。これは「同じ行を守る test が
複数あるはず」という思い込みを実測が訂正した例であり、**正直に記録する**。

`EMBEDDING_FAMILY_EXT` への限定 (④) は **`decide_external()` 内 (I-003 で mutation
済み)** と **I-005 の `run_cambridge_split()` 内 (新規)** の**二箇所**に存在する
別々のゲートである。前者は判定そのもの、後者は「どの候補を高コストな
bootstrapped 経路 (`build_candidate_report`、DA-G1-23 の計算予算制限) に
乗せるか」を決める。I-005 では**後者**を対象に mutation した (下表 #4)。

### 結果

| # | 壊した内容 | pytest exit code | 落ちた test | 復元後 diff |
|---|---|---|---|---|
| 再確認 | `is_draw_eligible`: `>=` → `>` (I-004 と同一行、I-005 側テストからも到達するか確認) | **1** | `test_draw_eligible_boundary_is_inclusive_at_the_floor` (I-004 側) のみ。**I-005 側 005-1〜005-7 は落ちなかった** — `_report_via_pipeline` の固定フィクスチャ (`_HIGH_SEP_*`≈1.0 / `_LOW_SEP_*`≈0.4-0.5) が floor=0.8 の境界から離れているため、境界 1 mutation は I-005 側テストからは検出不能 (正直に記録: 「I-005 の新規テストが①②③述語に依存する形で書かれている」という当初の想定は境界に関して誤りだった。①②③自体の境界保護は I-004 の既存 test が担い、I-005 側は非境界の値で正常経路のみを確認する設計になっている) | 空 |
| 1 | `draw_size()`: `min(_c.N_R_MAX, pool_size)` → `max(...)` (k の上下限を逆転 = design-final §4.1 の凍結式) | **1** | `test_arm_a_draw_texts_reproduces_and_diverges_with_seed` / `test_verdict_uses_arm_a_median_only` / `test_negative_controls_do_not_drive_verdict` / `test_both_split_schemes_reported` (numpy が `Cannot take a larger sample than population` で例外) / `test_draw_size_is_min_of_cap_and_pool` (I-002 側) — 計 5 件 | 空 |
| 2 | `nc1_partner_object()`: `ordered[(idx + 1) % len(ordered)]` → `ordered[idx % len(ordered)]` (巡回シフトを撤去 = 自分自身が partner になる) | **1** | `test_nc1_object_pairing_is_deterministic` (005-12) | 空 |
| 3a | `build_object_split_context()`: `dropped=len(dedup_common) < _c.N_R_MIN` → `dropped=False` (物体除外ゲートを丸ごと無効化) | **1** | `test_object_dropped_when_pool_too_small` (005-11) | 空 |
| 3b | 同ゲート: `<` → `<=` (境界のみ 1 個ずらす off-by-one) | **1 回目 = 0 (生存)** → test 追加後 **1 (kill)** | (生存時は無し) → `test_object_at_min_pool_boundary_is_not_dropped` (新規追加) | 空 |
| 4 | `run_cambridge_split()`: `if cand.key in EMBEDDING_FAMILY_EXT:` → `if True:` (X5/X6 も bootstrapped 経路に乗せる = DA-G1-23 計算予算制限の撤去) | **1** | `test_verdict_uses_arm_a_median_only` (`build_candidate_report` 呼び出し集合が `EMBEDDING_FAMILY_EXT` と一致しない) | 空 |

**5/6 が初回で kill、1/6 (#3b) が生存 → test 追加で kill、6/6 が最終的に kill。
6/6 とも復元後 `diff` が空 (バックアップと byte 一致)。**

### 生存した mutant (#3b) と対処

`dropped=len(dedup_common) < _c.N_R_MIN` を `<=` に緩めても、既存の 2 test
(`test_object_dropped_when_pool_too_small` は pool=1 で境界から遠い / 
`test_active_object_is_not_dropped` は pool=20 でこれも境界から遠い) はどちらも
**境界値 (pool サイズ == N_R_MIN == 8) を一度も突かない**ため mutant を検出できず、
`pytest -q tests/test_paper01_g1 -m "not eval"` は **68 passed** のまま緑だった
(exit code 0 = 生存)。

**対処**: `test_object_at_min_pool_boundary_is_not_dropped`
(`tests/test_paper01_g1/test_external_audit.py`) を追加。SPLIT-BLOCK は
`len(rows)//2` を split0 に渡すため、high-dim (16 次元) 乱数ベクトルで
dedupe による衝突が起きない `common_use_only` 行を `2*N_R_MIN` 件 (→ pool
ちょうど 8) / `2*N_R_MIN-2` 件 (→ pool ちょうど 7) 用意し、**8 件は non-drop
/ 7 件は drop** の両側を同一関数 (`build_object_split_context`) に通して assert
する形にした。追加後に #3b を再実施し、上表のとおり確実に落ちることを確認した
(exit code 1、落ちた test = `test_object_at_min_pool_boundary_is_not_dropped`)。
これは `feedback_witness_needs_mutation_testing.md` が警告する「境界を突かない
負例は何も検査していない」の実例そのものであり、I-004 retrospective の教訓
(「選ばれなかった per-draw 述語は素通りする」) が I-005 でも再発した
(今回は per-draw 述語ではなく object-drop 述語だったが同じ構造の穴)。

### 副次的な発見 (#4 の kill 経路について)

#4 (`EMBEDDING_FAMILY_EXT` 限定の撤去) を壊しても **verdict 自体は変化しなかった**
(`decide_external()` 側の同名ゲートが I-003 で既に凍結されており、X5/X6 の
report が渡っても判定時点で弾かれるため)。kill したのは
`test_verdict_uses_arm_a_median_only` の「`build_candidate_report` (高コストな
bootstrapped 経路) が呼ばれた候補集合」への直接 assert であり、**verdict の
正しさとは独立に「計算予算を守っているか」を検査する経路**が必要だったことを
示している。二重防御 (`decide_external` 内の filter が verdict を保護し、
`run_cambridge_split` 内の filter が計算コストを保護する) は設計として妥当だが、
**どちらか片方のテストだけでは他方の回帰を検出できない**ことが実測で確認された。

### 検証コマンド (mutation 完了後、全て緑)

```
.venv/Scripts/python.exe -m pytest -q tests/test_paper01_g1                # 全 test (eval 込み)
.venv/Scripts/python.exe -m ruff format --check scripts/paper01_external_audit.py tests/test_paper01_g1
.venv/Scripts/python.exe -m ruff check scripts/paper01_external_audit.py tests/test_paper01_g1
.venv/Scripts/python.exe -m mypy src
git status --porcelain src/erre_sandbox/evidence scripts/es4_scorer_diag.py scripts/paper01_fetch_sources.py  # 空
```

## 独立レビュー — I-005 (main オーケストレータ、2026-09-07)

mutation ではなく**結果 JSON の読解**で 2 件の欠落を検出したので記録する。

### 欠落 1: `*_median` という名前が across-draw 中央値ではなかった

`CandidateExternalReport.auc_full_median` などは実際には
**「drop の中央値 draw」の値** (median-by-drop draw) であって
`median_b(AUC_full)` ではない。中央値 draw は `drop` で選ばれるので、
両者は一致しない。

実データで矛盾が見えた: Cambridge SPLIT-PARITY の X0 は
`auc_full_median = 0.8156` (floor 0.80 を越えている) なのに、
**floor を越える draw は 200 中 32.5% しかない**。この 2 つを並べた表を
論文に出すと、読者には内部矛盾に見える。

- **対処**: `auc_full_at_median_draw` / `auc_lao_at_median_draw` /
  `drop_at_median_draw` / `potency_at_median_draw` に改名した。
  判定 (`decide_external`) はこれらの値を使わない (使うのは per-draw flags と
  bootstrap CI) ので、判定規則には影響しない。
- **pin**: `test_median_draw_values_are_not_across_draw_medians` —
  中央値-by-drop draw が across-draw 中央値と**実際に食い違う**入力を構成し、
  両者が別物であることを assert する。

### 欠落 2: §5.1 が要求する報告統計が埋め込み候補側に出ていなかった

design-final §5.1 は「崩落抽出割合 / `median_b(drop)` / draw の 5-95 パーセンタイル」を
報告項目として要求している。`DrawAggregate` はこれらを計算していたが、
**JSON へ emit されていたのは lexical 候補 (X5/X6) だけ**で、
判定対象である埋め込み候補 (X0-X3c) では `report` + `bootstrap` しか出ていなかった。

- **対処**: `CandidateStatisticalSummary` に `aggregate: DrawAggregate` を足し、
  bootstrapped 経路でも emit する。
- **pin**: `test_candidate_summary_emits_section_5_1_reporting_block`

### 教訓

**mutation testing はコードの内部整合しか見ない。** この 2 件はどちらも
「全 test が緑・全 mutant が kill」の状態で残っていた欠落であり、
**出力 JSON を実際に読んで数字の意味を突き合わせる**ことでしか出てこなかった。

## I-006 mutation testing — Ocsai adapter (jsonl parse / ARM-C / ARM-X / object drop gate)

- **対象ファイル**: `scripts/paper01_external_audit.py` (I-006 で新規追加した Ocsai
  adapter 節: `parse_ocsai_records` / `load_ocsai_rows` / `object_has_both_gold_classes` /
  `ocsai_high_frequency_texts` / `arm_c_texts` / `arm_x_scored_candidates` /
  `run_ocsai_split`) と `scripts/paper01_fetch_sources.py` (I-001 の凍結
  `ocsai_gold_label`。**指示②の二値化境界は I-001 の既存コードだが、issue から
  「最低限」と明示指定されたため、一時 mutate → test → 復元 → diff byte一致確認の
  同一手順で検査した。恒久的な改変は一切なし**)。
- **手順**: I-003〜I-005 と同一 (`mutate.py` で `assert old in text` (対象文字列の実在確認) →
  `assert mutated != text` (置換が実際に適用され no-op でないことの確認) → 置換適用 →
  `.venv/Scripts/python.exe -m pytest -q tests/test_paper01_g1 -m "not eval"` を実行 →
  exit code と落ちた test 名を記録 → I-006 実装完了直後のバックアップへ `cp` で復元 →
  `diff` で byte 一致を確認。1 つずつ直列に実施し、都度 diff 空を確認してから次へ進んだ。
- **バックアップ**: I-006 実装完了・ruff/mypy/test (`-m "not eval"`) 全緑を確認した直後の
  `scripts/paper01_external_audit.py` と `scripts/paper01_fetch_sources.py` を
  それぞれ scratchpad へ `cp` で保持 (`paper01_external_audit.py.bak` /
  `paper01_fetch_sources.py.bak`)。

### 指定された 6 種 (① 連結順 ② 二値化境界 ③ EXT_A2_MIN_SUPPORT 境界 ④ ARM-X anchor 出自
⑤ verdict への ARM-C 混入 ⑥ 物体除外ゲート境界) — 総当たり (①②③⑥は境界を複数パターン実施)

| # | 壊した内容 | 元のコード | 変更後 | 1 回目 exit code | 落ちた test |
|---|---|---|---|---|---|
| ① | `OCSAI_CONCAT_ORDER` の並び順を反転 (連結順の入れ替え) | `("train", "val", "test")` | `("test", "val", "train")` | **1** | `test_ocsai_concat_order_is_fixed` (006-1) / `test_preregistration_constants_match_config` (I-002 側、bonus) |
| ②a | `ocsai_gold_label` (paper01_fetch_sources.py, 凍結・一時 mutate): `score == 10` → `score <= 10` | `if score == _OCSAI_COMMON_SCORE:` | `if score <= _OCSAI_COMMON_SCORE:` | **1 回目 = 0 (生存)** → test 追加後 **1** | (生存時は無し) → `test_ocsai_binarisation_bands` (006-3、`resp 9` ケース追加後) |
| ②b | 同ファイル: `score >= 40` → `score > 40` | `if score >= _OCSAI_GOOD_MIN_SCORE:` | `if score > _OCSAI_GOOD_MIN_SCORE:` | **1** | `test_ocsai_binarisation_bands` (006-3、`resp 40` が `KeyError` で脱落) |
| ③a | `EXT_A2_MIN_SUPPORT` 境界: `>=` → `>` (支持 2 を 3 に事実上厳格化) | `if counts[text] >= min_support and ...` | `if counts[text] > min_support and ...` | **1** | `test_arm_c_missing_support_is_recorded` (006-4) |
| ③b | 同ゲート: `min_support` を無視して `>= 1` に緩和 (実質フィルタ撤去) | `if counts[text] >= min_support and ...` | `if counts[text] >= 1 and ...` | **1** | `test_arm_c_missing_support_is_recorded` (006-4、"brick" の support=1 ケースが誤って A2 に混入) |
| ④ | ARM-X の anchor 出自を Cambridge から Ocsai (`ocsai_paperclip_ctx`) にすり替え | `cambridge_ctx = build_object_split_context("paperclip", cambridge_paperclip_rows, scheme, vmaps.get("mpnet", {}))` | `cambridge_ctx = ocsai_paperclip_ctx` | **1 回目 = 0 (生存)** → test 再設計後 **1** | (生存時は無し) → `test_arm_x_is_source_crossed` (006-8、spy ベースに再設計後) |
| ⑤ | `arm_c_report` が非空なら `result["verdict"]` を強制上書き (ARM-C を verdict に混入) | `result["arm_c"] = {...}` の直後 | 同上 + `if arm_c_report: result["verdict"] = {"verdict": "PASS", "mutated": True}` | **1** | `test_verdict_comes_from_arm_a_only` (006-5、`run_cambridge_split` 直接呼び出しとの oracle 比較で検出) |
| ⑥a | `object_has_both_gold_classes`: 両条件を `>= 0` に緩和 (ゲート全撤去) | `return n_good >= 1 and n_common >= 1` | `return n_good >= 0 and n_common >= 0` | **1 回目 = 0 (生存)** → test 追加後 **1** | (生存時は無し) → `test_dropped_objects_are_reported` (006-7、"commonpoor" 追加後) |
| ⑥b | 同ゲート: `n_common` 連言を削除 (good 側の条件だけ残す) | `return n_good >= 1 and n_common >= 1` | `return n_good >= 1` | **1 回目 = 0 (生存)** → 同上 test 追加後 **1** | (生存時は無し) → `test_dropped_objects_are_reported` (006-7) |

**9/9 (①②a②b③a③b④⑤⑥a⑥b) が最終的に kill、9/9 とも復元後 `diff` が byte 一致
(`paper01_external_audit.py` / `paper01_fetch_sources.py` とも)。うち 3 件 (②a/④/⑥a・⑥b)
が初回 survive → test を追加/再設計して kill (下記詳細)。**

### 生存した mutant と対処 (3 件)

**②a (`score == 10` → `score <= 10`)**: 当初の `test_ocsai_binarisation_bands`
(006-3) は 10/11/39/40 の 4 点しか検査しておらず、**10 未満のスコアを一切構成して
いなかった**ため `<=10` に緩めても common 側の判定結果 (`resp 10` のみ common) が
偶然一致し、`pytest -q tests/test_paper01_g1 -m "not eval"` は **79 passed** の
まま緑だった (exit code 0 = 生存)。design-final.md §8 は score スケールを
10-50 と事前登録しており 10 未満は実データに現れないが、**境界の頑健性は別**
(I-005 retrospective の教訓「境界値をピンポイントで突く test を最初から書く」が
ここでも再発)。**対処**: `resp 9` (score=9) を追加し `"resp 9" not in by_text`
を assert。再実施で確実に kill (`KeyError` 相当ではなく `common_use_only` へ
誤分類されて assert 失敗) を確認した。

**④ (ARM-X anchor を Cambridge → Ocsai にすり替え)**: 当初の
`test_arm_x_is_source_crossed` (006-8) は `arm_x_scored_candidates` の返す
**AUC ベースの集約統計** (`DrawAggregate`) を比較していたが、この単体テストの
stub encoder は good/common を **半空間で完全分離**するため、good 側のスコアは
使うアンカー集合に関わらず常に rarity=1.0 (直交ゆえ cos=0)、common 側同士も
判別方向自体は崩れず、**AUC (および AUC 由来の集約統計) がアンカーの出自に
依らず一致してしまう** (raw score は実際に違う値になっていたが、rank/AUC は
偶然不変だった)。`pytest -q tests/test_paper01_g1 -m "not eval"` は
**79 passed** のまま緑 (exit code 0 = 生存)。**対処**: AUC 比較をやめ、
`mod.build_object_split_context` に `monkeypatch` で spy を仕込み、
`arm_x_scored_candidates` 内部でアンカー構築に実際に渡された `rows` 引数を
直接捕捉して `cambridge_rows` と一致すること (`ocsai_rows` とは不一致であること)
を assert する形に再設計した。この mutation は `cambridge_ctx` を
`ocsai_paperclip_ctx` に直接エイリアスして `build_object_split_context` の
呼び出し自体をスキップするため、spy が一度も発火せず `captured_rows == []`
という形で確実に検出できることも確認した。**教訓**: 「クリーンに分離された
合成 embedding」は判別力を測る目的には有用だが、**「どの参照集合を使ったか」
という配線の正しさを検査する目的には不向き** (AUC が飽和して不変になる)。
配線を検査したいときは統計量でなく生の呼び出し引数を spy で直接見るべき、
という一般則を得た。

**⑥a/⑥b (`object_has_both_gold_classes` の両境界)**: 当初の
`test_dropped_objects_are_reported` (006-7) は "toosmall" (プールサイズゲートで
落ちる)・"goldpoor" (`n_good=0`)・"boundarygood" (`n_good=1`、境界) の 3 種類しか
構成しておらず、**`n_common` 側の欠乏ケースを一度も構成していなかった**ため、
`n_good >= 0 and n_common >= 0` (ゲート全撤去) と `n_good >= 1` (`n_common` 連言
削除) の両方とも `79 passed` のまま緑だった (exit code 0 = 生存、2 件とも)。
**対処**: `_rows_common_then_good` (common を低 row_id・good を高 row_id に置く
既存ヘルパ) を使い、split1 (採点対象プール) には good だけが残り
common が 0 件になる "commonpoor" (`n_common=20, n_good=20`) を追加。プールサイズ
ゲート (split0 の common プールは 20 件 >= N_R_MIN なので pool-size では落ちない)
と gold-class ゲートの `n_common` 半分だけを狙い撃ちする構成にした。再実施で
⑥a/⑥b とも確実に kill (`dropped_objects` に `commonpoor` が欠落) を確認した。

### 検証コマンド (mutation 完了後、全て緑)

```
.venv/Scripts/python.exe -m pytest -q tests/test_paper01_g1 -m "not eval"        # 79 passed, 2 deselected
.venv/Scripts/python.exe -m ruff format --check scripts/paper01_external_audit.py tests/test_paper01_g1  # 9 files already formatted
.venv/Scripts/python.exe -m ruff check scripts/paper01_external_audit.py tests/test_paper01_g1            # All checks passed!
.venv/Scripts/python.exe -m mypy src                                        # Success: no issues found in 247 source files
git status --porcelain src/erre_sandbox/evidence scripts/es4_scorer_diag.py scripts/paper01_fetch_sources.py  # 空
```

### 教訓 (I-006 retrospective へ持ち越す)

**I-004/I-005 で繰り返し確認された「境界値をピンポイントで突く test を最初から
書かないと mutant が生存する」というパターンが I-006 でも 3/9 (33%) で再発した。**
今回新たに得た教訓は、**「AUC/verdict のような集約統計は、配線ミス (どの入力を
使ったか) を検出する目的には不十分な場合がある」**という点 (④ の生存)。
生の統計量が偶然不変になりうる合成データでは、配線の正しさは統計量でなく
**関数呼び出しの引数そのものを spy で直接検査する**方が確実であり、この教訓は
今後 source-crossed / cross-corpus な配線を検査する mutation test 全般に
持ち越す価値がある。

## I-007 mutation testing — fidelity pin (`fidelity_candidate_matches` / `main --fidelity`)

- **対象ファイル**: `scripts/paper01_external_audit.py` (I-007 で新規追加した
  §2 fidelity pin 節: `fidelity_candidate_matches` / `measure_c4_fidelity` /
  `measure_c0_fidelity` / `run_fidelity` / `write_fidelity` / `main` の
  `--fidelity` 分岐)。`es4_scorer_diag.py` は無改変 (`_diag.*` 経由で参照するのみ)。
- **手順**: I-003〜I-006 と同一 (`mutate_i007.py` — scratchpad 常設の小スクリプトで
  `assert old in text` (対象文字列の実在確認) → `assert mutated != text`
  (置換が実際に適用され no-op でないことの確認) → 置換適用 →
  `.venv/Scripts/python.exe -m pytest -q tests/test_paper01_g1 -m "not eval"` を実行 →
  exit code と落ちた test 名を記録 → I-007 実装完了直後のバックアップへ `cp` で復元 →
  `diff` で byte 一致を確認。1 つずつ直列に実施し、都度 diff 空を確認してから次へ進んだ。
- **バックアップ**: I-007 実装完了 (後述の AUC_membership 修正込み)・
  ruff/mypy/test 全緑を確認した直後の `scripts/paper01_external_audit.py` を
  scratchpad へ `cp` で保持 (`paper01_external_audit.py.bak`)。

### issue が指定した最低 4 種 + 独立に追加した 2 種 (計 6 件、境界を突くパターンで総当たり)

| # | 対象 | 元のコード | 変更後 |
|---|---|---|---|
| ① 許容誤差を緩める | `fidelity_candidate_matches` の完全一致判定 | `return auc_full == expected_full and auc_lao == expected_lao` | `return abs(auc_full - expected_full) < 0.5 and abs(auc_lao - expected_lao) < 0.5` |
| ② 不一致でも exit 0 | `main` の `--fidelity` 分岐、mismatch 時の exit code | `exit_code = 1` | `exit_code = 0` |
| ③ 期待値定数を書き換える | `C4_EXPECTED_AUC_FULL` | `Final[float] = 0.995` | `Final[float] = 0.85` |
| ④a auc_full/auc_lao の取り違え (C4 call site) | `measure_c4_fidelity` 内 `fidelity_candidate_matches(...)` 呼び出し | `gr.auc_full, gr.auc_leave_anchor_out,` | `gr.auc_leave_anchor_out, gr.auc_full,` (引数順序を入れ替え) |
| ④b auc_full/auc_lao の取り違え (C0 call site) | `measure_c0_fidelity` 内、同型の別コード箇所 | 同上 (C0 側) | 同上 (C0 側) |
| ⑤ (追加) `--fidelity` 分岐そのものが配線されていない | `main` の `if args.fidelity:` | `if args.fidelity:` | `if False and args.fidelity:` |

**注記 (③ の値選定)**: 当初 `0.995 → 0.9` で試したところ、無関係な I-002 の
`test_thresholds_are_imported_not_redefined` (`0.9` を banned threshold literal として
AST 走査で検出する既存 test) が**先に**落ちて自テストの kill を覆い隠したため、
`0.9` を避けて `0.85` に変更し、**自作の `test_expected_constants_are_frozen_to_the_sealed_diagnostic_json`
単体で kill されること**を確認し直した (下表参照)。

### 結果

| # | pytest exit code | 落ちた test | 復元後 diff |
|---|---|---|---|
| ① | **1** | `test_fidelity_candidate_matches_requires_both_statistics` / `test_fidelity_candidate_matches_no_tolerance_band` — 計 2 件 | 空 (バックアップと byte 一致) |
| ② | **1** | `test_fidelity_mismatch_exits_nonzero` | 空 |
| ③ | **1** | `test_expected_constants_are_frozen_to_the_sealed_diagnostic_json` | 空 |
| ④a | **1** | `test_measure_c4_fidelity_does_not_swap_full_and_lao` | 空 |
| ④b | **1** | `test_measure_c0_fidelity_does_not_swap_full_and_lao` | 空 |
| ⑤ | **1** | `test_fidelity_mismatch_exits_nonzero` / `test_fidelity_match_exits_zero` / `test_main_fidelity_flag_does_not_write_config` — 計 3 件 | 空 |

**6/6 が初回で kill (生存 mutant ゼロ)。6/6 とも復元後 `diff` が空 (バックアップと byte 一致)。**
最終確認として `scripts/paper01_external_audit.py` を `paper01_external_audit.py.bak` と
`diff` し、byte 一致 (`FILE_MATCHES_BACKUP_BYTE_IDENTICAL`) を確認した。

④a/④b を C4/C0 双方の call site で**別々に**実施したのは、I-005 retrospective の教訓
(「同じ述語クラスでも call site が違えば別々に mutation する」) を踏襲したもの。
両方とも初回で kill され、2 本の spy test (`test_measure_c4_fidelity_does_not_swap_full_and_lao` /
`test_measure_c0_fidelity_does_not_swap_full_and_lao`) が各々の call site に固有であることを
実測で確認した。

### 独立レビュー (結果 JSON の読解で検出した欠落、mutation ではない)

`--fidelity` を実走して `fidelity.json` を目視した際、**`auc_membership` の初版実装が
`auc_full` と数学的に恒等 (tautology) になっていた**ことを検出した (I-005 の
「教訓」節が警告する「mutation testing はコードの内部整合しか見ない」の再発)。

- **原因**: `fidelity_membership_and_potency` の初版は `m` (membership) を
  **連続値の max cosine similarity** (`1 - rarity_full`) として `auc_membership(m, labels)`
  に渡していた。しかし `auc_membership` は内部で `1 - m` に反転してから `auc()` を呼ぶため、
  `1 - m = 1 - (1 - rarity_full) = rarity_full` となり、**結局 `auc(rarity_full, labels)`
  = `auc_full` そのもの**を計算していた (実測値: C0/C4 とも 0.99/0.995 — `auc_full` と
  完全一致、design-final.md §2 の committed 値 0.750/0.7188 とは**別物**だった)。
- **検出**: design-final.md の Opus MEDIUM-6 が明記する閉形式
  `AUC_membership = 0.5 + (near_dup_common − near_dup_good) / 2` に実測の near-dup 率
  (C0: good 0.000/common 0.500、C4: good 0.000/common 0.4375) を代入すると
  **0.75 / 0.71875** となり、これが committed 値 (0.750/0.7188) と一致することから、
  `m` は**近傍複製の二値判定 (`max_r sim(x,r) ≥ REF_DEDUP`)** であるべきと結論した
  (`potency_and_near_dup` が同じ閾値述語を既に計算している)。
- **対処**: `fidelity_membership_and_potency` を `m` = 二値近傍複製フラグに修正
  (`near_dup_flags = [1.0 if s >= _c.REF_DEDUP else 0.0 for s in max_sim]` →
  `auc_membership(near_dup_flags, labels)`)。修正後の実測値は C0=0.75 / C4=0.71875
  (≈0.7188) で design-final.md §2 と一致。**`auc_full`/`auc_lao`/near-dup 率/potency
  (007-1〜007-5 の AC 本体) はこの修正の影響を受けない** (別関数の計算)。
- **教訓**: 「関数を呼べば動く」ことと「その関数に渡す値の意味論が正しい」ことは別。
  既存ユーティリティ (`auc_membership`) の docstring だけを読んで `m` を決めると、
  **数式的には妥当だが実際には別の量に退化する**呼び方をしうる。**出力 JSON を実際に
  読み、独立に導出した閉形式と突き合わせる**ことでしか検出できなかった (AC のどれにも
  `auc_membership` の厳密な一致は要求されていないため、test は落ちなかった)。

### 検証コマンド (mutation 完了後、修正込みで全て緑)

```
.venv/Scripts/python.exe -m pytest -q tests/test_paper01_g1 -m "not eval"        # 91 passed, 4 deselected
PYTHONHASHSEED=20260907 HF_HUB_OFFLINE=1 \
  .venv/Scripts/python.exe -m pytest -q tests/test_paper01_g1/test_fidelity.py -m "eval"  # 2 passed, 12 deselected
.venv/Scripts/python.exe -m ruff format --check scripts/paper01_external_audit.py tests/test_paper01_g1  # 10 files already formatted
.venv/Scripts/python.exe -m ruff check scripts/paper01_external_audit.py tests/test_paper01_g1            # All checks passed!
.venv/Scripts/python.exe -m mypy src                                        # Success: no issues found in 247 source files
git status --porcelain src/erre_sandbox/evidence scripts/es4_scorer_diag.py scripts/paper01_fetch_sources.py experiments/20260701-es4-scorer-diag  # 空
PYTHONHASHSEED=20260907 HF_HUB_OFFLINE=1 .venv/Scripts/python.exe scripts/paper01_external_audit.py --fidelity  # exit 0, all_match=true
```
