# 重要な設計判断 — PR-2 WeightedTrainer Blocker 2 fix

> 本 PR は ADR 確定方針の **単純実装** のため、新規の設計判断は基本的に
> 発生しない。本 file は実装過程で出てきた局所判断 (test fixture の
> 新規ヘルパー名・実装ディテール等) のみを記録する。
>
> 横断 ADR は `.steering/20260513-m9-c-adopt/decisions.md`、PR-2 の依拠
> 方針は `.steering/20260517-m9-c-adopt-da16-design/decisions.md`
> DA16-1〜DA16-4 を参照。

## DP2-1: 新規 test ヘルパー `_build_logits_targeting_variable_margin` を追加 (既存 `_build_logits_targeting` は互換維持)

- **判断日時**: 2026-05-17
- **背景**: Codex HIGH-2 反映で「per-example loss が異なる fixture」の
  新規 batch=2 test を追加するため、既存 `_build_logits_targeting`
  (margin=2.0 ハードコード) を置き換えるか拡張するかの判断が必要。
  既存 2 件 test は同ヘルパーを使用しており、書き換えると test
  diff が広がる。
- **選択肢**:
  - **A**: 既存ヘルパーに `margin: float = 2.0` 引数を追加 (default で
    既存呼び出し互換)。新規 test は `margin=0.5` を渡せる
  - **B**: 新規 helper `_build_logits_targeting_variable_margin(labels,
    margins_per_example)` を別関数で追加。既存ヘルパーは無変更で
    backward compat 完全保持
  - **C**: 既存ヘルパーを drop して全 test を新型に書き換え
- **採用**: **A** (既存ヘルパーに per-example margins 引数を追加)
- **理由**:
  1. 既存ヘルパーは「全 example 同一 margin」が default の挙動として
     残す必要なし — 新型 (per-example margins) が generalisation。
     既存 test 2 件は新型を `margins=[2.0, 2.0]` で呼び出して挙動互換
  2. **B** は helper 数増 → maintenance cost。1 ヘルパーで責務が
     single の方が読みやすい
  3. **C** は test 構造改変で diff が広がり、code-reviewer + Codex
     review の精査負担が上がる
- **トレードオフ**:
  - 既存 test 2 件の `_build_logits_targeting(labels)` → `_build_
    logits_targeting(labels, margins=[2.0, 2.0])` への書き換えが必要
    (引数追加で diff 出る) → ただし default で旧挙動 fallback できる
    なら呼び出し側書き換え不要
- **影響範囲**:
  - `tests/test_training/test_weighted_trainer.py:32-52` の helper 定義
  - 既存 2 件 test の `_build_logits_targeting(labels)` 呼び出し
    (margin 引数の default 値を 2.0 にすれば書き換え不要)

**最終実装方針**: `_build_logits_targeting(labels, *, vocab=5, margins=
None)` で `margins is None` の場合は全 example margin=2.0 で fallback、
list が渡された場合は per-example margin を適用。

## DP2-2: `torch.clamp(..., min=1e-8)` の epsilon を新式で削除

- **判断日時**: 2026-05-17
- **背景**: 旧式 `(l*w).sum() / torch.clamp(weights.sum(), min=1e-8)` の
  `torch.clamp` は zero-weight batch (weights.sum()=0) 防御だったが、
  新式 `(l*w).mean()` では分母が `batch_size` (常に >0) で `torch.clamp`
  自体が不要。
- **選択肢**:
  - A: epsilon 削除 (`.mean()` のみ)
  - B: epsilon 残置 (paranoia、コード読みやすさ)
- **採用**: **A** (削除)
- **理由**:
  1. `.mean()` の分母は tensor の要素数で torch が内部で扱う、
     batch=0 が来ない限り zero 不可
  2. `compute_example_weight` の upstream で pool 空ケースは error
     として弾かれる (空 pool で weight=0 が batch に並ぶ経路はない)
  3. 不要な epsilon は意味論を曖昧にする (なぜ 1e-8?)
- **トレードオフ**:
  - 万一 weights=[0.0, 0.0] のような病的 input が来た場合、新式は
    `(0 + 0)/2 = 0` を返す (NaN ではないが情報損失)。旧式は
    `0 / 1e-8 = 0` で同 result → 実害なし
- **影響範囲**: `weighting.py:462` の最終行

## DP2-4: Codex review MEDIUM-1 反映 — docstring の "guarantees" 弱化 + batch≥2 "nearly identical" の in-expectation caveat

- **判断日時**: 2026-05-17
- **背景**: Codex independent review (`codex-review.md`) で MEDIUM-1
  指摘:
  > 「`compute_example_weight` "guarantees" mean=1 via
  > `normalise_weights_to_mean_one`; strictly, `compute_example_weight`
  > returns raw weights, and the training pipeline normalizes them at
  > `train_kant_lora.py:742`. Also, "nearly identical" scales for
  > `batch_size >= 2`; that is only true in expectation over shuffled
  > batches. For small batches, the new loss equals old loss times local
  > `mean(weights)`, which can be materially different.」
- **採用**: docstring を以下の 2 点で書き換える:
  1. `compute_example_weight` 自体が mean=1 を guarantee しない、
     pipeline で `normalise_weights_to_mean_one` を呼ぶ side で
     enforce している (`train_kant_lora.py:742` を cite)
  2. batch≥2 の "nearly identical" は **in expectation over shuffled
     batches** であり、small batch では local `mean(weights)` で scale
     が変動することを明記。retrain trajectory の train_loss 解釈時に
     reducer artefact と model/corpus effect を取り違えないように caveat
- **理由**: Codex の指摘は完全に正しい — `compute_example_weight` は
  raw weight を返すだけ、normalisation は caller の責務。docstring の
  "guarantees" 表現は責務分担を誤伝する。また batch≥2 の "nearly
  identical" は 大数法則的 in-expectation でしか成立しないため、
  short retrain run の trajectory 解釈で誤読されるリスクがあり、
  caveat を明記する責任がある (DA16-2 の "train_loss scale 非比較" 注記
  と整合的)
- **影響範囲**: `weighting.py:443-462` の docstring (semantic note section)
- **見直しタイミング**: 将来 weighting pipeline 改修で normalisation
  経路が変更された場合 (例: per-batch normalisation 導入 等)、本
  docstring の "caller responsible" 部分を更新

## DP2-5: Codex review LOW-1 反映 — train_kant_lora.py:1697-1706 comment drift 修正

- **判断日時**: 2026-05-17
- **背景**: Codex independent review LOW-1 指摘:
  > 「The comment says "Loss semantics are unchanged" and
  > `compute_weighted_causal_lm_loss` is the "verbatim Codex HIGH-C
  > implementation" at `train_kant_lora.py:1703`. After DA-16, only
  > the shift/recompute contract is unchanged; the reducer semantics
  > are intentionally changed.」
- **採用**: comment を「shift/recompute contract は HIGH-C verbatim 維持、
  reducer は DA-16 ADR DA16-2 で意図的に変更」と明示するよう書き換え。
  `WeightedTrainer.compute_loss` 本体は無変更 (PR-2 next-session-prompt
  の "train_kant_lora.py:1687-1715 は無変更" 制約は API contract に対する
  ものでありコメント更新は別)
- **理由**: comment drift は maintenance text として誤導的。LOW でも本 PR
  で同時に修正できる scope (~10 行のコメント差し替えのみ) のため defer
  しない
- **影響範囲**: `train_kant_lora.py:1697-1706` (10 行のコメント書き換え、
  function body と call-site API contract は無変更)
- **見直しタイミング**: 将来 `compute_weighted_causal_lm_loss` の reducer
  が再変更された場合、本 comment も同時に更新する

## DP2-3: 既存 test L102-111 の comment 更新

- **判断日時**: 2026-05-17
- **背景**: 既存 test
  `test_weighted_trainer_compute_loss_weighted_sum_matches_manual`
  L102-111 の comment は旧式の挙動 (weighted mean = per_example_loss[0]
  regardless of weights) を説明している。新式でも fixture 都合
  (両 example 同一 margin) で結果は同じだが、comment は新式の数式に
  明示更新する必要あり。
- **選択肢**:
  - A: comment を新式の数式 + Codex HIGH-2 言及で書き換える
  - B: comment を最小限の言及で更新 (本 PR で別新規 test が盲点補強
    するため重複説明回避)
- **採用**: **A** (新式数式 + Codex HIGH-2 言及で書き換え)
- **理由**:
  1. 既存 test 単体で読んだとき、新式数式と fixture の関係が明示
     されている方が intent が伝わる
  2. Codex HIGH-2 言及で「この test は数式 verify のみ、weight 効果
     検証は test_3 で補強」と pointing する方が test 間の責務分担が
     明確
- **影響範囲**: `test_weighted_trainer.py:102-111` (comment block 更新)
