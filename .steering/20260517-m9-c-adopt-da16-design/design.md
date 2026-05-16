# 設計 — DA-16 ADR (kant Plan B PHASE_E_A6 順序判断)

## 実装アプローチ (本 PR = ADR doc-only)

本 PR は **doc-only ADR** で、以下のみを成果物とする:

1. `.steering/20260517-m9-c-adopt-da16-design/` 5 標準 file + Codex
   review + PR-2 用 next-session prompt
2. memory `project_plan_b_kant_phase_e_a6.md` の update (採用候補 + PR
   分割確定で更新)

実コードへの変更は **本 PR では一切行わない**。後続 PR (PR-2 / PR-3 /
PR-4 / PR-5) で分割実装する (decisions.md DA16-3 参照)。

### 採用候補と PR 分割 (DA16-1 + DA16-3 から再掲)

```
本 PR (DA-16 ADR, doc-only)
        │
        └→ PR-2 (WeightedTrainer fix)  ← ~2h、~50 行 diff + 新規 test
             │
             └→ PR-3 (kant_r8_v4 retrain) ← ~5h、GPU 占有、adapter artifact
                  │
                  └→ PR-4 (DA-14 rerun verdict) ← ~3h、PR #184 pipeline 再利用
                       │
                       ├→ ADOPT → nietzsche / rikyu Plan B 展開 (別 ADR)
                       └→ REJECT → PR-5 (rank=16 spike) ← ~6h、条件付き
                                         │
                                         └→ ADOPT/REJECT → 別 ADR で次判断
```

## 変更対象 (本 PR doc-only)

### 修正するファイル

- なし (実コードへの変更は PR-2 以降)

### 新規作成するファイル

- `.steering/20260517-m9-c-adopt-da16-design/requirement.md`
- `.steering/20260517-m9-c-adopt-da16-design/design.md` (本 file)
- `.steering/20260517-m9-c-adopt-da16-design/decisions.md` (DA16-1〜DA16-4)
- `.steering/20260517-m9-c-adopt-da16-design/tasklist.md`
- `.steering/20260517-m9-c-adopt-da16-design/blockers.md`
  (WeightedTrainer Blocker 2 持ち越し)
- `.steering/20260517-m9-c-adopt-da16-design/codex-review-prompt.md`
  (WSL2 経由起動用)
- `.steering/20260517-m9-c-adopt-da16-design/codex-review.md`
  (Codex 出力 verbatim 保存)
- `.steering/20260517-m9-c-adopt-da16-design/
  next-session-prompt-FINAL-pr2-weighted-trainer-fix.md`
  (PR-2 用 handoff prompt)

### 削除するファイル

- なし

## 続 PR 実装方針 (DA16-2 から再掲、PR-2 で実装される)

### PR-2: WeightedTrainer fix (`.mean()` reduce 採用)

**修正箇所**:
- `src/erre_sandbox/training/weighting.py:411-462` (`compute_weighted_
  causal_lm_loss`):
  ```python
  # 旧 (L462):
  return (per_example_loss * weights).sum() / torch.clamp(weights.sum(), min=1e-8)
  # 新:
  return (per_example_loss * weights).mean()
  ```
  + docstring に意味論変更 (`mean=1` 正規化 weights 前提) を追記
- `tests/test_training/test_weighted_trainer.py`:
  - 既存 2 件 (`test_..._weighted_sum_matches_manual` /
    `test_..._handles_label_minus_100`) の `expected = ... / weights.sum()`
    部分を `expected = (per_example_loss * weights).mean()` に書き換え
  - **新規 test 1 件追加**:
    `test_weighted_trainer_compute_loss_batch1_weight_changes_loss_magnitude`
    — batch=1 で weight=2.0 と weight=1.0 を比較し loss magnitude が比例
    変化することを assert (current bug の regression detector)
  - **新規 test 2 件追加** (DA16-2 トレードオフ言及):
    `test_weighted_trainer_compute_loss_batch1_gradient_norm_scales_with_weight`
    — batch=1 で weight=2.0 と weight=1.0 で `loss.backward()` 実行後の
    `param.grad.norm()` 比率が weight 比率と一致することを assert
- `src/erre_sandbox/training/train_kant_lora.py:1690-1715`
  (WeightedTrainer.compute_loss): **無変更** (内部関数の数式変更のみ)

**新 invocation**: 既存 `scripts/m9-c-adopt/train_plan_b_kant.sh` の
invocation は無変更、adapter 名のみ `kant_r8_v3` → `kant_r8_v4` に
update (PR-3 で)。

### PR-3: kant_r8_v4 retrain

- DR-4 (SGLang launch v5 + piecewise CUDA graph disable) の invocation で
  retrain serving は不要 (training 中の SGLang 起動なし)
- DR-7 の eval_loss trajectory monitoring を v4 でも適用、best step
  selection
- HuggingFace Hub に adapter binary push (`mikotomiura/erre-kant-r8-v4-
  loraadapter` 想定、別 storage に push して binary は git 外)
- forensic JSON (`train_metadata.json`) のみ git commit

### PR-4: DA-14 rerun verdict (PR #184 pipeline 再利用)

- `scripts/m9-c-adopt/run_plan_b_post_eval.sh` を PR-3 adapter で再実行
- `data/eval/m9-c-adopt-plan-b-verdict-v4/*.duckdb` 4 shard を生成
  (~30 min GPU)
- `rescore_vendi_alt_kernel.py` を 4 encoder (MPNet/E5/lex5/BGE-M3) で
  実行
- `aggregate_plan_b_axes.py` で 4-axis verdict、`da14-verdict-plan-b-
  kant-v4.json` + `.md` を生成
- ADOPT/REJECT を `da14-verdict-plan-b-kant-v4.md` Phase E A-6 section
  で確定、本 ADR DA16-3 の dependency graph に従い次の PR (PR-5 or
  nietzsche/rikyu) を起動

### PR-5: rank=16 spike (条件付き、PR-4 REJECT 時のみ)

- `train_kant_lora.py` の rank=8 → rank=16 切り替え (CLI flag or config)
- VRAM 検証: rank=16 で `--quantization fp8 --max-total-tokens 2048
  --max-running-requests 1` 構成が 16 GB VRAM に乗るか事前 spike
  (~30 min)
- retrain (~3h) + verdict (~30 min) で kant_r16_v1 を評価
- 別 ADR で次判断 (ADOPT なら nietzsche/rikyu、REJECT なら Plan C 候補
  へ展開)

## 影響範囲

### 本 PR (doc-only) の影響

- `.steering/` 配下のみ新規ファイル、コード・データへの変更なし
- nietzsche / rikyu Plan B 展開は **本 ADR で明示的に保留宣言** (PR-4
  ADOPT まで)
- 他 m9 系 task (M9-eval, M9-individual-layer) は本 ADR と独立、影響なし

### PR-2 以降の影響予測 (本 PR scope 外)

- `compute_weighted_causal_lm_loss` の意味論変更 → v3 v4 間で **train_loss
  scale + 学習軌道の意味** は直接比較不可 (新式で weight が gradient
  magnitude に乗るため convergence path が変動)。**eval_loss は比較可能**
  — eval examples は `sample_weight=1.0` (`train_kant_lora.py:761-765`、
  Codex review HIGH-1 指摘)、eval batch=1 (`per_device_eval_batch_size=1`、
  DR-6) で旧式と新式が数値一致するため、EarlyStoppingCallback + 標準 CE
  比較 + `train_metadata.json` 記録に副作用なし
- v3 retrain 由来の forensic 数値 (`data/eval/m9-c-adopt-plan-b-verdict/
  *.duckdb`) は archive、v4 で別 directory に生成
- v3 adapter (`mikotomiura/erre-kant-r8-v3-loraadapter`、HuggingFace Hub)
  は **保持** (PR-3 で v4 と並行存在、forensic 再現性のため deprecate
  しない)
- 既存 `test_weighted_trainer.py` の fixture (weights=[3.0, 1.0]、
  全 example 同一 margin=2.0) は per-example loss identical で weight
  検出力ゼロ (Codex review HIGH-2 指摘)。expected 書き換えに加えて
  **per-example loss が異なる fixture** の新規 test を 1 件追加 (PR-2 で
  実装、margin=2.0/0.5 差分で weighted mean に weight 効果が反映される
  ことを assert)

## 既存パターンとの整合性

### Plan-Execute 分離パターン (CLAUDE.md "禁止事項")

- 「Plan mode 外で設計判断を確定しない」: 本 ADR が設計確定、PR-2 以降は
  実装のみで再判断しない
- 「高難度設計で /reimagine を省略しない」: 本 ADR で /reimagine 適用済、
  decisions.md DA16-1 で再生成案との比較を verbatim 引用で記録

### Codex independent review パターン (CLAUDE.md "Codex との連携")

- 高難度設計 / 大 PR merge 前に Codex review を挟む規則を本 ADR にも適用
- 起動経路は **WSL2 経由** で `codex exec` を呼ぶ (PR #184 blockers.md
  ブロッカー 2 教訓: Windows + PowerShell + Codex の hook 干渉回避)
- HIGH 指摘は本 PR 内で反映、MEDIUM/LOW は `decisions.md` の追加 entry
  または PR-2 への持ち越しとして明記

### Pre-push CI parity パターン (CLAUDE.md "禁止事項")

- doc-only PR でも `pre-push-check.sh|.ps1` 4 段必須
  (memory `feedback_pre_push_ci_parity.md` 教訓: PR #181 で CI fail
  事後追従が起きた reflection)
- ruff format --check / ruff check / mypy src / pytest -q の 4 段、
  doc-only でも skip 禁止

### .steering record パターン (CLAUDE.md "作業記録ルール")

- 5 標準 file (requirement / design / tasklist / blockers / decisions)
  を必ず作成、本 PR でも省略しない
- task-name は `m9-c-adopt-da16-design`、date prefix は今日 (20260517)

## テスト戦略

### 本 PR (doc-only) のテスト

- doc-only のため新規コードテストなし
- pre-push-check.sh の 4 段 (ruff format/check, mypy, pytest) 全 pass で
  既存 1510 件 + α が green であることを CI 等価に確認 (memory `feedback_
  pre_push_ci_parity.md` 4 段定義)
- markdown lint は pyproject.toml に未設定なので本 PR では skip

### PR-2 のテスト計画 (本 PR で先決め)

- 既存 `test_weighted_trainer.py` 2 件: expected 式を `.mean()` 基準に
  書き換え後 PASS 維持
- 新規 1 件 (Blocker 2 regression detector): `test_weighted_trainer_
  compute_loss_batch1_weight_changes_loss_magnitude` — batch=1 で
  weight=2.0 vs weight=1.0 の loss 比率が 2:1 であることを assert
  (mean=1 正規化前の weight)。**旧式では w が相殺されて常に同値となり、
  本 test は fail する** ことで Blocker 2 を構造的に検出する
- 新規 1 件 (gradient 経路 regression detector): `test_weighted_trainer_
  compute_loss_batch1_gradient_norm_scales_with_weight` — synthetic param
  (`torch.nn.Linear(vocab, vocab)`) で `loss.backward()` 後の
  `param.weight.grad.norm()` 比率が weight 比率と (rel_tol=1e-4 で)
  一致を assert
- 新規 1 件 (Codex HIGH-2 反映、batch=2 fixture 強化): `test_weighted_
  trainer_compute_loss_batch2_per_example_loss_differs_weight_takes_
  effect` — `_build_logits_targeting` の margin を example A=2.0、
  example B=0.5 (per-example CE が異なる fixture) で構築、weights=[3.0,
  1.0] の weighted mean が unweighted mean と異なる ことを assert。
  既存 fixture の "weight 検出力ゼロ" 盲点を補強し、後続 reduce 式
  変更時に確実に fail させる
- 既存 1510 件 + 新規 3 件で計 ~1513 件、`pytest -q` 全 PASS が PR-2
  merge 条件

### PR-3 / PR-4 / PR-5 のテスト計画 (本 ADR では scope outline のみ)

- PR-3: 既存 `tests/test_training/` パスのみ、retrain 自体は test scope
  外 (GPU 必要)
- PR-4: PR #184 で追加された `tests/test_scripts/test_rescore_vendi_alt_
  kernel_cli.py` + `test_aggregate_plan_b_axes.py` を再利用、新 adapter
  での invocation smoke
- PR-5: PR-3 と同じ test 構成、rank=16 用 fixture 追加なし (CLI flag
  のみ)

## ロールバック計画

### 本 PR (doc-only) のロールバック

- 本 PR は doc-only なので `git revert <merge-commit>` で完全に元の state
  に戻る
- 副作用 (memory file update) のみ手動 revert: memory `project_plan_b_
  kant_phase_e_a6.md` を更新前の state に戻す
- nietzsche / rikyu Plan B 展開の保留方針は本 ADR が source、本 PR
  revert で保留解除と解釈される (実際は revert 後も verdict REJECT は
  事実なので展開は不可、別 ADR で再確定が必要)

### PR-2 のロールバック (本 PR scope 外、参考情報)

- `compute_weighted_causal_lm_loss` の式と test 2 件を v3 形式に revert
- v3 retrain 結果は archive にあるので test と式の整合性のみ復旧
- PR-2 merge 後 PR-3 開始前なら revert 軽い、PR-3 開始後は v4 adapter
  を archive 化して revert

### PR-3 / PR-4 のロールバック (本 PR scope 外)

- PR-3: v4 adapter を HuggingFace から delete または rename、forensic
  JSON を archive
- PR-4: v4 verdict JSON + shards を `data/eval/m9-c-adopt-plan-b-verdict-
  v4/_archive/` に移動、`da14-verdict-plan-b-kant-v4.json` を deprecate

## Codex independent review 計画 (本 PR 内で実施)

### 起動方法 (WSL2 経由、PR #184 blockers.md ブロッカー 2 教訓)

```bash
wsl -d Ubuntu-22.04 -- bash -c '
  cd /mnt/c/ERRE-Sand_Box && \
  cat .steering/20260517-m9-c-adopt-da16-design/codex-review-prompt.md | \
  codex exec --skip-git-repo-check
' > .steering/20260517-m9-c-adopt-da16-design/codex-review.md 2>&1
```

### `codex-review-prompt.md` に含む項目

1. 本 ADR の文脈 (kant Plan B PHASE_E_A6 routing、根因仮説 2 つ)
2. 採用候補 A (WeightedTrainer fix 先行) の根拠
3. WeightedTrainer fix 方針 (`.mean()` reduce) の意味論変更説明
4. 続 PR 分割 (PR-2/3/4/5) の dependency graph
5. 報告フォーマット: HIGH / MEDIUM / LOW を明示、行番号付き引用を要求
6. 参照ファイル一覧 (本 ADR file + requirement.md 関連ドキュメント)

### 反映ルール (CLAUDE.md "Codex との連携")

- HIGH: 本 PR 内で必ず反映 (decisions.md に追加 entry、または design.md
  を更新)
- MEDIUM: 採否を decisions.md に追記、defer 理由を明示
- LOW: blockers.md に持ち越し可、PR-2 で再検討
