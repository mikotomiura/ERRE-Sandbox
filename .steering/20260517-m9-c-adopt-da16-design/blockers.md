# ブロッカー記録 — DA-16 ADR (kant Plan B PHASE_E_A6 順序判断)

## 持ち越しブロッカー (本 PR scope 外、続 PR で対処)

### 持ち越し 1: WeightedTrainer Blocker 2 — sample weight collapse (PR-2 scope)

- **持ち越し元**:
  `.steering/20260518-m9-c-adopt-plan-b-retrain/blockers.md` ブロッカー 2
- **症状要約**:
  `compute_weighted_causal_lm_loss` (`src/erre_sandbox/training/
  weighting.py:411`) の reduce 式
  `(per_example_loss * weights).sum() / torch.clamp(weights.sum(),
  min=1e-8)` は `per_device_train_batch_size=1` のとき
  `(per_example_loss[0] * w[0]) / w[0] = per_example_loss[0]` で
  weight が数学的に相殺される。grad_accum=8 でも HF Trainer の
  micro-batch independent backward 経路で weight 効果が消失する。
  DA-14 weighting (`compute_example_weight`、coefficient
  0.35/0.20/0.15/0.30、normalise to mean=1) が training 中に gradient
  へ反映されていなかった可能性。
- **本 PR での扱い**: **実装修正は scope 外** (DA16-3 で PR-2 として
  分割確定)。本 ADR では修正方針 (DA16-2 で `.mean()` reduce、(a)-
  refined を採用) のみ確定。
- **PR-2 への handoff**:
  - `.steering/20260517-m9-c-adopt-da16-design/
    next-session-prompt-FINAL-pr2-weighted-trainer-fix.md` に PR-2 用
    next-session prompt を起票
  - PR-2 scope: `weighting.py:411` の reduce 式 + docstring 更新、
    `test_weighted_trainer.py` の既存 2 件 expected 書き換え + 新規 3 件
    (batch=1 loss magnitude / batch=1 gradient norm scaling / batch=2
    per-example loss が異なる fixture で weighted mean 検証) 追加
    (Codex review HIGH-2 で 3 件目を追加、既存 fixture の検出力ゼロ盲点を
    補強)
- **PR-2 完了基準**:
  - 既存 1510 件 + 新規 3 件で `pytest -q` 全 PASS (~1513 件)
  - `pre-push-check.sh` 4 段全 pass
  - Codex review HIGH 指摘なしで merge
- **教訓** (本 ADR で得た):
  - per-example loss reduction を実装する時、batch=1 と grad_accum>1
    の組み合わせで weight が数学的に相殺される構造的バグを生みやすい
  - **unit test fixture が batch>=2 で組まれていると本問題は検出不能**。
    PR-2 では batch=1 + synthetic gradient response test を必須化する
  - Codex HIGH-C verbatim 採用時、verbatim 数式が暗黙前提する batch
    size を含む context を後続 implementation で確認する手順を CLAUDE.md
    "Codex との連携" section に追加する候補 (本 ADR では scope 外、
    Plan B retrospective で議論)

### 持ち越し 2: rank=16 spike (PR-5 scope、条件付き)

- **持ち越し元**:
  - 本 ADR DA16-1 root cause 仮説 2 (rank=8 capacity 不足)
  - DR-1 (PHASE_E_A6 routing) の next step として記録
- **症状要約**: kant の Burrows/style 信号は de_monolog に集中、rank=8
  では LoRA adapter capacity 不足の可能性。rank=16 で capacity 2 倍に
  すると weighted retrain で signal が学習可能になるか検証する。
- **本 PR での扱い**: **PR-5 として条件付き持ち越し**。PR-4 (kant_r8_v4
  verdict) が REJECT 確定時のみ起動。ADOPT なら不要。
- **PR-5 起動前提条件**:
  - PR-2 (WeightedTrainer fix) merge 済
  - PR-3 (kant_r8_v4 retrain) merge 済
  - PR-4 (DA-14 rerun verdict) で REJECT 確定
- **PR-5 起動時の design 検討項目** (本 ADR で先決め、PR-5 起票時に
  spike 結果で更新):
  - VRAM 検証: rank=16 で `--quantization fp8 --max-total-tokens 2048
    --max-running-requests 1` (DR-4) が 16 GB VRAM に乗るか
    (~30 min spike)
  - eval_loss 比較不能性: v4 (fix 後 rank=8) と r16_v1 (fix 後 rank=16)
    では同一 reduce 式なので eval_loss 直接比較可能 (DA16-2 トレード
    オフが両 PR 共通)
  - PR-4 verdict の "どの axis が borderline か" で rank=16 が解決
    可能性を持つかを再評価 (corpus mismatch 仮説なら rank=16 も無効)

### 持ち越し 3: nietzsche / rikyu Plan B 展開 (PR-4 ADOPT 後の別 ADR)

- **持ち越し元**: PR #184 prompt 「nietzsche / rikyu の Plan B 展開は
  kant verdict ADOPT 待ちで現在保留」
- **症状要約**: kant verdict が ADOPT に至らない限り、nietzsche / rikyu
  でも同じ encoder agreement FAIL を踏む確率が高い (root cause が
  weighting bug なら全 persona 共通)。本 ADR で展開保留を明示的に
  決定。
- **本 PR での扱い**: **保留宣言のみ**、別 ADR 起票は PR-4 ADOPT 後。
- **保留解除条件**: PR-4 (kant_r8_v4 verdict) で ADOPT 確定
- **保留解除後の design 検討項目** (別 ADR の scope):
  - nietzsche / rikyu それぞれの DA-14 weighting coefficient 設計
    (kant 0.35/0.20/0.15/0.30 が persona 横断で適切か)
  - SGLang serving の persona swap (LoRA adapter hot swap or 別 serve)
  - eval shard 採取の persona-specific stimulus 設計

## 本セッション中に発生したブロッカー

(現時点なし)

> Codex independent review 起動時に PR #184 と同様の Windows hook 干渉
> が起きた場合、ブロッカー 4 として追記する。WSL2 経由で起動するため
> 干渉は回避できる想定 (eval-gen blockers.md ブロッカー 2 教訓)。
