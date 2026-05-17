# PR-2 WeightedTrainer Blocker 2 fix (kant Plan B PHASE_E_A6 第 1 段)

## 背景

`feature/m9-c-adopt-da16-design` (PR #186 merged) で DA-16 ADR が成立
し、kant Plan B PHASE_E_A6 routing で **候補 A** (WeightedTrainer fix
→ kant_r8_v4 retrain → DA-14 rerun verdict) が採用された
(decisions.md DA16-1)。本 PR-2 は ADR 採用の第 1 段で、ADR 確定
方針 (`.mean()` reduce、DA16-2) の **単純実装** を行う。

`src/erre_sandbox/training/weighting.py:411-462` の
`compute_weighted_causal_lm_loss` は現在 verbatim:

```python
return (per_example_loss * weights).sum() / torch.clamp(weights.sum(), min=1e-8)
```

`per_device_train_batch_size=1` (DI-7 で VRAM 制約により確定) で
micro-batch を作ると `per_example_loss` shape は `(1,)`、`weights`
shape も `(1,)` で、`(l[0]*w) / w = l[0]` と weight が数学的に
相殺される。retrain blockers.md ブロッカー 2 (verbatim):

> 「DA-14 weighting (`compute_example_weight`、coefficient 0.35/0.20/
>  0.15/0.30、normalise to mean=1) は採用したが、実 training 上は
>  unweighted average と等価に振る舞っていた可能性。DA-14 verdict
>  REJECT の原因の一つが「weighting が効いていない」だった可能性も
>  否定できない。」

これを `.mean()` reduce ((a)-refined、DA16-2) で修正し、batch=1 +
grad_accum 経路で weight が gradient に乗るようにする。

## ゴール

`compute_weighted_causal_lm_loss` が batch=1 で weight 効果を gradient
magnitude に伝える state を達成し、続 PR-3 (kant_r8_v4 retrain) で
DA-14 weighting が実効化された retrain を可能にする。

## スコープ

### 含むもの

- `src/erre_sandbox/training/weighting.py:411-462` の reduce 式を
  `.mean()` に変更
- docstring 更新 (意味論変更 + 前提 mean=1 正規化 weights)
- `tests/test_training/test_weighted_trainer.py` の既存 2 件の
  expected を `.mean()` 基準に書き換え
- 新規 regression test 3 件追加 (DA-16 codex review HIGH-2 反映):
  - `test_..._batch1_weight_changes_loss_magnitude` (Blocker 2
    regression detector)
  - `test_..._batch1_gradient_norm_scales_with_weight` (gradient
    経路 regression detector)
  - `test_..._batch2_per_example_loss_differs_weight_takes_effect`
    (batch=2 fixture 強化、既存 fixture の weight 検出力ゼロ盲点を補強)
- `pre-push-check.ps1` 4 段全 pass (1510 既存 + 3 新規 ~= 1513 件)
- Codex independent review (WSL2 経由)、HIGH 反映
- 続 PR-3 用 next-session prompt 起票

### 含まないもの

- `WeightedTrainer.compute_loss` (`train_kant_lora.py:1687-1715`) の
  変更 (内部関数の数式変更のみ、call site API 不変)
- kant_r8_v4 retrain の **実行** (別 PR-3 scope、~5h GPU)
- DA-14 rerun verdict (別 PR-4 scope)
- rank=16 spike (別 PR-5 scope、PR-4 REJECT 時のみ)
- nietzsche / rikyu Plan B 展開 (PR-4 ADOPT 後の別 ADR)
- 新たな weighting 数式設計 (DA16-2 で確定済、本 PR では実装のみ)

## 受け入れ条件

- [ ] `weighting.py:462` の reduce 式が `(per_example_loss * weights).mean()`
- [ ] docstring に意味論変更 (batch=1 + grad_accum で weight が gradient
      に乗る、mean=1 正規化 weights 前提) を明記
- [ ] 既存 2 件 (`test_..._weighted_sum_matches_manual` /
      `test_..._handles_label_minus_100`) が新 reduce 式 expected で PASS
- [ ] 新規 3 件 (batch=1 magnitude / batch=1 grad norm / batch=2
      per-example differs) が PASS
- [ ] `WeightedTrainer.compute_loss` (train_kant_lora.py:1690-1715) は
      無変更、return signature `(weighted_loss, outputs) if return_outputs
      else weighted_loss` 不変
- [ ] `pre-push-check.ps1` 4 段全 pass (ruff format --check / ruff check
      / mypy src / pytest -q)
- [ ] Codex review WSL2 経由で起動、`codex-review.md` verbatim 保存、
      HIGH 反映
- [ ] PR-3 用 next-session prompt 起票
- [ ] commit + push + `gh pr create --base main`
- [ ] memory `project_plan_b_kant_phase_e_a6.md` を PR-2 status で update

## 関連ドキュメント

- `.steering/20260517-m9-c-adopt-da16-design/decisions.md` DA16-1〜DA16-4
  (本 PR が依拠する fix 方針)
- `.steering/20260517-m9-c-adopt-da16-design/design.md` PR-2 section
- `.steering/20260517-m9-c-adopt-da16-design/blockers.md` 持ち越し 1
  (WeightedTrainer Blocker 2)
- `.steering/20260517-m9-c-adopt-da16-design/codex-review.md` (HIGH-1
  eval_loss / HIGH-2 batch=2 fixture)
- `.steering/20260516-m9-c-adopt-plan-b-eval-gen/decisions.md` DR-1
  (kant Plan B verdict REJECT で PHASE_E_A6 確定)
- `.steering/20260518-m9-c-adopt-plan-b-retrain/blockers.md` ブロッカー 2
- `src/erre_sandbox/training/weighting.py:411-462`
- `src/erre_sandbox/training/train_kant_lora.py:1687-1715`
- `tests/test_training/test_weighted_trainer.py`
- memory `feedback_pre_push_ci_parity.md`
- memory `project_plan_b_kant_phase_e_a6.md`
- CLAUDE.md 「禁止事項」「Codex との連携」
