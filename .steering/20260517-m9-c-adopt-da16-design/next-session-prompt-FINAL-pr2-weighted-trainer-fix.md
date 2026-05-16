# Next-session 開始プロンプト — PR-2 WeightedTrainer Blocker 2 fix (kant Plan B PHASE_E_A6 第 1 段)

**用途**: 新セッション最初に貼り付け (下の ``` で囲まれた部分のみ)

**前提**:
- DA-16 ADR 起票 PR (`feature/m9-c-adopt-da16-design`、本セッションで作成)
  が merged 済 (`.steering/20260517-m9-c-adopt-da16-design/decisions.md`
  DA16-1〜DA16-4 で順序判断 = 候補 A、fix 方針 = `.mean()` reduce
  ((a)-refined) が確定)
- WeightedTrainer Blocker 2 (sample weight collapse、batch=1 で weight
  数学的相殺) の実装修正は **本 PR-2 scope**
- PR-3 (kant_r8_v4 retrain) / PR-4 (DA-14 rerun verdict) / PR-5
  (rank=16 spike、条件付き) はそれぞれ後続 PR で実装
- nietzsche / rikyu の Plan B 展開は kant verdict ADOPT 待ちで現在
  **保留**

**branch**: 新規 `feature/m9-c-adopt-pr2-weighted-trainer-fix` を
**main** から切る
**scope**: WeightedTrainer fix 実装 (~50 行 diff + 新規 regression test
2 件)、~2h envelope
**Plan mode 任意**: 本 PR は ADR で確定済み方針の単純実装 (DA-16 ADR
DA16-2 で `.mean()` reduce 確定済)。新たな設計判断が必要な場合のみ
Plan mode + /reimagine

---

```
m9-c-adopt PR-2 (WeightedTrainer Blocker 2 fix) を実行する。
DA-16 ADR (`.steering/20260517-m9-c-adopt-da16-design/decisions.md`)
DA16-2 で `.mean()` reduce ((a)-refined) が修正方針として確定済。
本 PR は ADR 確定方針の単純実装。

## 目的 (本セッション、~2h envelope)

1. `feature/m9-c-adopt-pr2-weighted-trainer-fix` branch (main 派生) 作成
2. `/start-task` で `.steering/<YYYYMMDD>-m9-c-adopt-pr2-weighted-
   trainer-fix/` 5 標準 file を template から起票
3. `src/erre_sandbox/training/weighting.py:411-462` の
   `compute_weighted_causal_lm_loss` の reduce 式を変更:
   ```python
   # 旧 (L462):
   return (per_example_loss * weights).sum() / torch.clamp(weights.sum(), min=1e-8)
   # 新:
   return (per_example_loss * weights).mean()
   ```
   + docstring に意味論変更 (mean=1 正規化 weights 前提、batch=1
   + grad_accum での gradient response 維持) を追記
4. `tests/test_training/test_weighted_trainer.py` の既存 2 件を新式
   ベースに書き換え:
   - `test_weighted_trainer_compute_loss_weighted_sum_matches_manual`:
     `expected = (per_example_loss * weights).mean()` に変更
   - `test_weighted_trainer_compute_loss_handles_label_minus_100`:
     同様に `.mean()` 基準で expected を再計算
5. **新規 regression test 3 件追加** (DA-16 Codex review HIGH-2 反映):
   - `test_weighted_trainer_compute_loss_batch1_weight_changes_loss_magnitude`
     — batch=1 で weight=2.0 vs weight=1.0 の loss 比率が 2:1 に
     なることを assert (Blocker 2 の regression detector、旧式では w
     相殺で常に同値となり test fail することで構造的に検出)
   - `test_weighted_trainer_compute_loss_batch1_gradient_norm_scales_with_weight`
     — synthetic `torch.nn.Linear(vocab, vocab)` で `loss.backward()`
     後の `param.weight.grad.norm()` 比率が weight 比率と (rel_tol=1e-4
     で) 一致を assert
   - `test_weighted_trainer_compute_loss_batch2_per_example_loss_differs_weight_takes_effect`
     — `_build_logits_targeting` の margin を example A=2.0、example B=0.5
     (per-example CE が異なる fixture) で構築、weights=[3.0, 1.0] の
     weighted mean が unweighted mean と異なることを assert。既存 fixture
     (両 example 同一 margin で weight 検出力ゼロ) の盲点を補強し、後続
     reduce 式変更時に確実に fail させる (DA-16 codex-review.md HIGH-2
     参照)
6. `WeightedTrainer.compute_loss` (`train_kant_lora.py:1687-1715`) は
   **無変更** (内部関数の数式変更のみ、call site の API contract は不変)
7. pre-push CI parity (ruff format --check + ruff check + mypy src
   + pytest -q) 全 pass を確認
8. Codex independent review (WSL2 経由で起動):
   ```bash
   wsl -d Ubuntu-22.04 -- bash -c '
     cd /mnt/c/ERRE-Sand_Box && \
     cat .steering/<task>/codex-review-prompt.md | \
     cmd.exe /c "codex exec --skip-git-repo-check"
   ' > .steering/<task>/codex-review.md 2> .steering/<task>/codex-review.stderr
   ```
   HIGH/MEDIUM/LOW を verbatim 保存、HIGH は本 PR 内で反映
9. commit + push + `gh pr create --base main`
10. 続 PR-3 (kant_r8_v4 retrain) 用 next-session prompt を起票

## NOT in scope (本 PR-2)

- kant_r8_v4 retrain の **実行** (別 PR-3 scope、~5h GPU)
- DA-14 rerun verdict (別 PR-4 scope)
- rank=16 spike (別 PR-5 scope、PR-4 REJECT 時のみ)
- nietzsche / rikyu の Plan B 展開 (PR-4 ADOPT 後の別 ADR)
- 新たな weighting 数式設計 (DA16-2 で確定済、本 PR では実装のみ)

## 最初に必ず Read する file (内面化必須)

1. `.steering/20260517-m9-c-adopt-da16-design/decisions.md` DA16-1〜DA16-4
   (本 PR が依拠する fix 方針)
2. `.steering/20260517-m9-c-adopt-da16-design/design.md` PR-2 section
   (修正箇所 + test 追加の詳細)
3. `.steering/20260517-m9-c-adopt-da16-design/blockers.md` 持ち越し 1
   (WeightedTrainer Blocker 2 の症状 + 修正方針)
4. `.steering/20260517-m9-c-adopt-da16-design/codex-review.md`
   (DA-16 ADR への Codex HIGH/MEDIUM 反映確認、特に DA16-2 数式に
   HIGH 指摘があれば本 PR 実装に取り込む)
5. `src/erre_sandbox/training/weighting.py:411-462`
   (修正対象、Codex HIGH-C verbatim docstring の更新含む)
6. `src/erre_sandbox/training/train_kant_lora.py:1687-1715`
   (WeightedTrainer.compute_loss、本 PR では call site 無変更を確認)
7. `tests/test_training/test_weighted_trainer.py` (既存 3 件 + 新規 2
   件、計 5 件)
8. memory `feedback_pre_push_ci_parity.md` (push 前 4 段 check 必須)
9. memory `project_plan_b_kant_phase_e_a6.md` (DA-16 採用候補 A + PR
   分割 graph)
10. `CLAUDE.md` 「禁止事項」「Codex との連携」(WSL2 経由起動)

## 留意点 (HIGH 違反防止)

- **DA-16 ADR 確定済方針からの逸脱禁止**: 本 PR は実装のみ、新たな数式
  設計や reduce 形式変更は別 ADR (DA16-2 見直しタイミング参照)
- **既存 test の verbatim 修正禁止**: 既存 2 件は expected 式の
  書き換えで済む。test 構造や fixture 自体を改変しない (Codex HIGH-C
  verbatim 数式の test boundary を保つ)
- **新規 regression test の意味論明示**: docstring + comment で
  「Blocker 2 (batch=1 weight collapse) の regression detector」と
  明記、将来 reduce 式が再変更されたら必ず fail するよう設計
- **HF Trainer compute_loss API contract 不変**: `(weighted_loss,
  outputs) if return_outputs else weighted_loss` の return signature
  を維持、`prediction_loss_only=True` 経路を壊さない
- **Pre-push CI parity check 抜きでの push 禁止** (CLAUDE.md 禁止事項)
- **Codex review は WSL2 経由で起動**: DA-16 ADR PR で動作確認済の
  cmd.exe wrapper pattern を採用 (`.steering/20260517-m9-c-adopt-da16-
  design/codex-review.md` の起動例参照)
- **train_loss scale + 学習軌道の v3 v4 非比較性**: 新式
  `(l*w).mean()` で weight が gradient magnitude に乗るため
  train_loss scale + step pace + best step 位置の v3 v4 直接比較は
  避ける (Codex review HIGH-1 反映: DA16-2 トレードオフ参照)。
  **eval_loss は比較可能** — eval examples は `sample_weight=1.0`
  (`train_kant_lora.py:761-765`) で eval batch=1 のため新旧式が数値
  一致、v3 eval_loss=`0.18259` との standard CE 直接比較は OK

## 完了条件

- [ ] `feature/m9-c-adopt-pr2-weighted-trainer-fix` branch (main 派生)
      作成
- [ ] `.steering/<YYYYMMDD>-m9-c-adopt-pr2-weighted-trainer-fix/`
      5 標準 file を template から起票
- [ ] `weighting.py:462` の reduce 式を `.mean()` に変更 + docstring 更新
- [ ] `test_weighted_trainer.py` 既存 2 件の expected 書き換え
- [ ] `test_weighted_trainer.py` 新規 2 件 (batch=1 loss magnitude /
      gradient norm scaling) 追加
- [ ] `WeightedTrainer.compute_loss` の API contract 不変を確認 (無変更)
- [ ] `pre-push-check.sh|.ps1` 4 段全 pass (既存 1510 件 + 新規 3 件で
      ~1513 件 PASS)
- [ ] Codex independent review **WSL2 経由で起動**、`codex-review.md`
      verbatim 保存、HIGH 反映
- [ ] 続 PR-3 (kant_r8_v4 retrain) 用 next-session prompt 起票
- [ ] commit + push + `gh pr create --base main`
- [ ] memory `project_plan_b_kant_phase_e_a6.md` を PR-2 merge で update
```

---

**実施推奨タイミング**: DA-16 ADR PR merge 直後、~1 週間以内。PR-2
完了で PR-3 (kant_r8_v4 retrain) を起動できる。nietzsche / rikyu Plan B
展開は PR-4 verdict ADOPT 待ちで継続保留。
