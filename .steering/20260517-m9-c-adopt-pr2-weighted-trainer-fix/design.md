# 設計 — PR-2 WeightedTrainer Blocker 2 fix

## 実装アプローチ

DA-16 ADR DA16-2 で確定済の **(a)-refined: `.mean()` reduce** をそのまま
実装する。本 PR で新たな設計判断はない (実装のみ)。

### 修正方針

`compute_weighted_causal_lm_loss` の最終 reduce 式を:

```python
# 旧 (weighting.py:462):
return (per_example_loss * weights).sum() / torch.clamp(weights.sum(), min=1e-8)
# 新:
return (per_example_loss * weights).mean()
```

`compute_example_weight` が pool 全体で mean=1 正規化を保証するため、
batch≥2 では `(l*w).mean() ≈ (l*w).sum()/batch_size` で旧式
`sum(l*w)/sum(w) ≈ sum(l*w)/batch_size (since mean(w)≈1)` とほぼ
同 scale。**batch=1 では新式 `(l[0]*w[0]).mean() = l[0]*w[0]` で weight
が gradient magnitude に乗る** — これが本 PR の主目的。

`torch.clamp(..., min=1e-8)` の epsilon は zero-weight batch 防御
だったが、新式では `weights.mean()` の分母が常に 1 (mean=1 正規化済)
で zero になり得ないため不要。Mean=0 は対象 pool が空のときのみで、
それは upstream で error として扱われる。

## 変更対象

### 修正するファイル

- `src/erre_sandbox/training/weighting.py:411-462`
  (`compute_weighted_causal_lm_loss`):
  - L462 の reduce 式を `.mean()` へ
  - L412-442 docstring を新意味論 + batch=1 grad-aware 説明で更新
  - L437-441 Notes section に「`compute_example_weight` の mean=1
    正規化が前提」を明記
- `tests/test_training/test_weighted_trainer.py`:
  - 既存 2 件 (L55-111, L114-167) の expected 式を `.mean()` 基準に
    書き換え (L93, L155 部分)
  - 既存 1 件 (L169-175, `_rejects_seq_len_one`) は無変更
  - 新規 3 件追加 (詳細は「テスト戦略」)

### 新規作成するファイル

- `.steering/20260517-m9-c-adopt-pr2-weighted-trainer-fix/`
  - `requirement.md`、`design.md` (本 file)、`decisions.md`、
    `tasklist.md`、`blockers.md`
  - `codex-review-prompt.md` (WSL2 起動用)
  - `codex-review.md` (Codex 出力 verbatim 保存)
  - `next-session-prompt-FINAL-pr3-kant-r8-v4-retrain.md`

### 削除するファイル

- なし

### 無変更を確認

- `src/erre_sandbox/training/train_kant_lora.py:1687-1715`
  (`WeightedTrainer.compute_loss`): API contract 不変
  - return signature `(weighted_loss, outputs) if return_outputs else
    weighted_loss`
  - `prediction_loss_only=True` 経路の動作不変 (内部関数の数式変更のみ)
  - `inputs.pop("sample_weight")` / `inputs.pop("labels")` の順序不変

## 影響範囲

### 数値的影響

- **train_loss scale + 学習軌道の v3 v4 非比較性** (DA16-2 トレードオフ):
  新式 `(l*w).mean()` で weight が gradient に乗るため、step pace +
  best step 位置 + train_loss absolute value は v3 (旧式 retrain) と
  直接比較できない
- **eval_loss は比較可能** (Codex HIGH-1 反映済): eval examples は
  `sample_weight=1.0` (`train_kant_lora.py:761-765`、`for ex in eval_
  examples: ex["sample_weight"] = 1.0`)、eval batch=1 (`per_device_
  eval_batch_size=1`、DR-6) の組み合わせで:
  - 旧式: `(l[0] * 1.0) / 1.0 = l[0]`
  - 新式: `(l[0] * 1.0).mean() = l[0]`
  → eval_loss は両式で数値一致、v3 `eval_loss=0.18259` と v4 eval_loss は
  標準 CE として直接比較可能。EarlyStoppingCallback + `train_metadata.
  json` 記録 + dashboards 比較に副作用なし

### 既存テストへの影響

- `test_weighted_trainer_compute_loss_weighted_sum_matches_manual`
  (L55-111): expected 式 (L93) を `(per_example_loss * weights).sum() /
  weights.sum()` から `(per_example_loss * weights).mean()` に書き換え。
  既存 fixture (batch=2、両 example 同一 margin=2.0) では per-example
  loss が等しく、`weights=[3.0, 1.0]` でも weighted mean = unweighted
  mean = per_example_loss[0] と等しいため、数値は **両式で同一**。
  test 本体の comment (L102-111) を新数式 + Codex HIGH-2 言及で更新
- `test_weighted_trainer_compute_loss_handles_label_minus_100`
  (L114-167): expected 式 (L155) を同様に `.mean()` 基準へ。fixture
  (batch=2、weights=[2.0, 1.0]、example A 2 valid / B 0 valid) では
  per_example_loss = (per_A, 0)、新式 expected = (2.0 * per_A + 1.0 *
  0.0) / 2 = per_A、旧式 expected = (2.0 * per_A + 1.0 * 0.0) / 3.0 =
  2.0 * per_A / 3.0 → **数値は変わる**。test の comment (L138-144) も
  新式 expected で更新
- `test_weighted_trainer_compute_loss_rejects_seq_len_one` (L169-175):
  無変更 (seq_len=1 の ValueError 検証は新式と無関係)

### Codex review HIGH-2 反映 — 既存 fixture の weight 検出力盲点

既存 batch=2 fixture (`_build_logits_targeting` で全 example 同一
margin=2.0) では per-example CE が両 example identical のため、
`weights=[3.0, 1.0]` でも weighted mean = unweighted mean。test 自体は
数式の正しさを検証するが、**weight 効果の "回帰検出力" がゼロ**:

```python
# L102-111 で test 自身が明示:
# The two examples are constructed to have IDENTICAL per-token CE per
# position (same margin construction), so per_example_loss is the same
# for both. The weighted mean then collapses to that shared value
# regardless of the (3.0, 1.0) weight vector.
```

この盲点を補強するため、本 PR で新規 batch=2 test 1 件追加 (per-example
loss が異なる fixture)。

## 既存パターンとの整合性

### Codex HIGH-C verbatim docstring pattern

`compute_weighted_causal_lm_loss` の docstring は元々 Codex HIGH-C
verbatim を引用している。新式に更新する際も「verbatim 引用部 + 本 PR
での意味論変更」の二段構造を保つ (verbatim 部を改ざんしない、新式は
別 paragraph で追記)。

### Lazy import pattern (extras-only deps)

`import torch` は L443-444 で関数内 lazy import (extras-only 方針)。
本 PR で `import torch.nn` を関数内に追加する必要はなく、既存の
`torch_fn` 経由で済む。

### pytest.importorskip pattern

新規 3 件 test も既存 file 上部の `torch = pytest.importorskip("torch")`
を継承するため、`[training]` extras 未導入環境 (CI default profile)
では自動 skip。

### Plan-Execute 分離パターン

本 PR は ADR 確定方針の単純実装。新たな設計判断が発生した場合は
Plan mode + /reimagine + 別 ADR が必要 (CLAUDE.md 「Plan mode 外で
設計判断を確定しない」)。

### Pre-push CI parity パターン

`pre-push-check.ps1` 4 段必須 (CLAUDE.md 禁止事項、memory
`feedback_pre_push_ci_parity.md`)。

## テスト戦略

### 既存テスト書き換え (2 件)

- `test_weighted_trainer_compute_loss_weighted_sum_matches_manual`:
  - expected 式: `(per_example_loss * weights).sum() / weights.sum()`
    → `(per_example_loss * weights).mean()`
  - 数値: 両 example 同一 per-example loss + mean=`sum/2` で旧式と
    実質同値 (fixture 都合) — test 文字列は新式に明示
- `test_weighted_trainer_compute_loss_handles_label_minus_100`:
  - expected 式: 同様に `.mean()` 基準へ
  - 数値: per_example_loss = [per_A, 0] のため expected =
    `(2.0 * per_A + 0.0) / 2 = per_A` (旧式は `2.0 * per_A / 3.0`)
  - comment 更新: 新式 expected の計算根拠を新記述で

### 新規 regression test (3 件)

#### test_1: `test_weighted_trainer_compute_loss_batch1_weight_changes_loss_magnitude`

**目的**: Blocker 2 (batch=1 weight collapse) の構造的回帰検出。
batch=1 で weight=2.0 と weight=1.0 の loss 比率が 2:1 になることを
assert。旧式 `(l*w)/w = l` では常に同値 → fail で Blocker 2 を検出。

**fixture**: batch=1, seq=4, vocab=5, labels=`[[1,2,3,4]]`,
`_build_logits_targeting` で構築。

**assertion**:
- `loss_w2 = compute_weighted_causal_lm_loss(logits, labels, weights=[2.0])`
- `loss_w1 = compute_weighted_causal_lm_loss(logits, labels, weights=[1.0])`
- `math.isclose(loss_w2 / loss_w1, 2.0, rel_tol=1e-6)`

#### test_2: `test_weighted_trainer_compute_loss_batch1_gradient_norm_scales_with_weight`

**目的**: gradient 経路 regression detector。`loss.backward()` 後の
`param.grad.norm()` 比率が weight 比率と一致を assert。

**fixture**: synthetic `torch.nn.Linear(vocab, vocab)` をパラメタとして
2 回 zero_grad → forward → backward して `.weight.grad.norm()` を比較。
batch=1, seq=4, vocab=5, labels と logits は test_1 と同型。

**assertion**:
- `grad_norm_w2 / grad_norm_w1` が 2.0 と `rel_tol=1e-4` で一致

実装 pseudo:

```python
def test_..._batch1_gradient_norm_scales_with_weight() -> None:
    torch.manual_seed(0)
    vocab = 5
    linear = torch.nn.Linear(vocab, vocab, bias=False)
    labels = torch.tensor([[1, 2, 3, 4]], dtype=torch.long)
    # Build raw input (use one-hot or random tensor) so the model is
    # `linear` applied to embed-like input. seq=4, embed_dim=vocab.
    inp = torch.eye(vocab)[labels[0]].unsqueeze(0)  # (1, seq, vocab)

    def _run(w: float) -> float:
        linear.zero_grad()
        out = linear(inp)  # (1, seq, vocab)
        loss = compute_weighted_causal_lm_loss(
            out, labels, torch.tensor([w], dtype=torch.float32)
        )
        loss.backward()
        return float(linear.weight.grad.norm().item())

    g1 = _run(1.0)
    g2 = _run(2.0)
    assert math.isclose(g2 / g1, 2.0, rel_tol=1e-4)
```

#### test_3: `test_weighted_trainer_compute_loss_batch2_per_example_loss_differs_weight_takes_effect`

**目的**: Codex HIGH-2 反映。既存 fixture の盲点 (全 example 同一
margin → weight 検出力ゼロ) を補強。per-example loss が異なる fixture
で weight 効果を検証。

**fixture**: batch=2, seq=4, vocab=5。`_build_logits_targeting_variable_
margin` ヘルパーを新設、example A の margin=2.0、example B の margin=
0.5 で構築。これにより per_example_loss[0] ≠ per_example_loss[1]。

**assertion**:
- `weights=[3.0, 1.0]`
- `weighted_loss = compute_weighted_causal_lm_loss(...)`
- `unweighted_mean = per_example_loss.mean()`
- `math.isclose(weighted_loss, (per_example_loss * weights).mean(),
  rel_tol=1e-6)` (新式 expected との一致)
- `not math.isclose(weighted_loss, unweighted_mean, rel_tol=1e-2)`
  (weight 効果が反映されている = unweighted と異なる)

実装方針: 既存 `_build_logits_targeting` の `margin = 2.0` ハードコード
を見直し、`margin: float` 引数を取れる variant ヘルパー
(`_build_logits_targeting_variable_margin`) を新設。旧ヘルパーは互換
維持 (既存 2 件 test が使用)。

### Pre-push CI parity

`pre-push-check.ps1` 4 段全 pass。既存 1510 件 + 新規 3 件 = ~1513 件
PASS が PR-2 merge 条件。

## ロールバック計画

- `git revert <merge-commit>` で `weighting.py:462` + test_weighted_
  trainer.py が v3 形式 (`.sum()/weights.sum()`) に戻る
- PR-3 (kant_r8_v4 retrain) 開始前なら影響なし
- PR-3 開始後の revert は v4 adapter を archive 化、v3 で再開
