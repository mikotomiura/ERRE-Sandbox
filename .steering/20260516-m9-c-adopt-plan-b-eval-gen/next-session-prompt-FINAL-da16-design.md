# Next-session 開始プロンプト — DA-16 ADR design (kant Phase E A-6 順序判断)

**用途**: 新セッション最初に貼り付け (下の ``` で囲まれた部分のみ)

**前提**:
- PR #184 (`feature/m9-c-adopt-plan-b-eval-gen`) merged 済
  (`.steering/20260516-m9-c-adopt-plan-b-eval-gen/decisions.md` DR-1 で
  kant Plan B verdict = **PHASE_E_A6** 確定)
- WeightedTrainer Blocker 2 (sample weight collapse、batch=1 で weight
  数学的相殺) が retrain Blocker 2 として記録済
  (`.steering/20260518-m9-c-adopt-plan-b-retrain/blockers.md`)
- nietzsche / rikyu の Plan B 展開は kant verdict ADOPT 待ちで現在
  **保留**

**branch**: 新規 `feature/m9-c-adopt-da16-design` を **main** から切る
**scope**: ADR 起票 (doc-only、~2h envelope)。実装は別 PR に分離
**Plan mode 必須**: 設計判断 PR のため Shift+Tab で Plan mode + Opus
**/reimagine 必須**: rank=16 spike vs WeightedTrainer fix の順序判断は
**高難度設計** (どちらを先にやるかで実験 design が大きく変わる)

---

```
m9-c-adopt の Phase E A-6 / DA-16 ADR design を実行する。
PR #184 で kant Plan B verdict = PHASE_E_A6 (REJECT) が確定したため、
次の investment 方針を ADR で確定する。本 PR は **doc-only** で、
WeightedTrainer 修正・rank=16 retrain・eval shard 生成は別 PR scope。

## 目的 (本セッション、~2h envelope)

1. **Plan mode** (Shift+Tab で Opus) に切り替え、まず `/start-task`
   で `.steering/<YYYYMMDD>-m9-c-adopt-da16-design/` を起票
2. **`/reimagine`** で初回案を破棄し、再生成案と並べて順序判断:
   - 候補 A: **rank=8 のまま WeightedTrainer Blocker 2 修正 → 再 retrain**
     (低コスト ~50 行 diff、clean A/B、weight 効果のみ検証)
   - 候補 B: **rank=16 spike を先に試行** (capacity expansion 優先、
     weight 効果と交絡)
   - 候補 C: **両方同時に変更** (NOT recommended、root cause 切り分け不能)
3. 採用候補を `decisions.md` DA16-1 に記録、根拠 (Plan B kant の
   per-encoder direction disagreement、Burrows reduction% 負値、
   eval_loss vs gate axis 乖離) を verbatim 引用
4. `design.md` で採用候補の実装方針 (file 変更箇所、unit test 範囲、
   retrain envelope、新 verdict 計算 pipeline 再利用) を確定
5. `blockers.md` に WeightedTrainer Blocker 2 を本 PR scope 外として
   持ち越し、修正 PR への handoff を明文化
6. Codex independent review (WSL2 経由で起動、PR #184 のような
   Windows hook 干渉を回避):
   - `wsl -d Ubuntu-22.04 -- bash -c 'cd /mnt/c/ERRE-Sand_Box && cat
     .steering/<task>/codex-review-prompt.md | codex exec --skip-git-repo-check'`
   - HIGH/MEDIUM/LOW を `codex-review.md` に verbatim 保存
7. 続 PR (PR-2: WeightedTrainer fix) 用 next-session prompt を起票
8. pre-push CI parity → commit + push + `gh pr create`

## NOT in scope (本セッション)

- WeightedTrainer Blocker 2 の **実装修正** (別 PR-2 scope)
- rank=16 spike (別 PR-5 scope、PR-3/4 verdict 後)
- 新 retrain (kant_r8_v4)、新 eval shard 生成
- nietzsche / rikyu の Plan B 展開 (kant verdict ADOPT 待ち、現在保留)

## 最初に必ず Read する file (内面化必須)

1. `.steering/20260516-m9-c-adopt-plan-b-eval-gen/decisions.md` DE-1〜DR-1
   (本 PR が依拠する verdict 結果 + root cause hypothesis)
2. `.steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-verdict-plan-b-kant.md`
   (4-axis verdict + per-encoder direction 結果)
3. `.steering/20260516-m9-c-adopt-plan-b-eval-gen/blockers.md` ブロッカー 2
   (Codex Windows hook 干渉教訓、本 PR で WSL2 経由を採用)
4. `.steering/20260518-m9-c-adopt-plan-b-retrain/blockers.md` ブロッカー 2
   (WeightedTrainer sample weight collapse の根拠 + 暫定対応案 (a)/(b)/(c))
5. `.steering/20260518-m9-c-adopt-plan-b-retrain/decisions.md` DR-5 / DR-6
   (WeightedTrainer の compute_loss 構造 + 関連パッチ歴)
6. `src/erre_sandbox/training/weighting.py:411`
   (`compute_weighted_causal_lm_loss` の数式実装)
7. `src/erre_sandbox/training/train_kant_lora.py:WeightedTrainer.compute_loss`
   (L1690-1704 + DR-5 patch 適用後の現状)
8. `tests/test_training/test_weighted_trainer.py` (既存 weighting unit test、
   batch=2 のみ pass する盲点を確認)
9. memory `project_plan_b_kant_phase_e_a6.md` (本 ADR の起点となる verdict 結果)
10. memory `feedback_pre_push_ci_parity.md` (push 前 4 段 check 必須)
11. memory `feedback_claude_md_strict_compliance.md` (Plan mode 必須、
    /reimagine 必須、Skill Read 必須)
12. `CLAUDE.md` 「Plan mode 必須」「/reimagine 必須」「禁止事項」(設計確定前の
    実装着手禁止 + 高難度設計の 1 発案禁止)

## 留意点 (HIGH 違反防止)

- **Plan mode 必須**: ADR は設計確定の典型例。Shift+Tab で Plan + Opus、
  承認前に decisions.md に書き込まない
- **/reimagine 必須**: 候補 A vs B vs C は構造的に異なる実験 design で
  「初回案 1 発で確定」してはいけない (Codex review でも MEDIUM 指摘の
  余地あり)
- **本 PR は doc-only**: ADR + steering + handoff prompt のみ。実装は
  PR-2 以降に分離 (Plan-Execute 分離原則)
- **Codex review は WSL2 経由で起動**: PR #184 の Windows hook 干渉
  教訓を反映 (blockers.md ブロッカー 2)
- **DA-14 thresholds 不変**: rank=16 spike や WeightedTrainer fix で
  retrain 結果が borderline でも threshold 移動禁止 (Plan B でも厳守)
- **Pre-push CI parity check 抜きでの push 禁止** (CLAUDE.md 禁止事項)
- **WeightedTrainer Blocker 2 の修正案 (a)/(b)/(c) は本 ADR で 1 つに**
  **確定**: 別 PR-2 で迷わないよう、本 ADR で実装方針まで明文化
  (例: 候補 (a) `compute_loss` 内で `weights.sum()` 割り戻しを止める)

## 完了条件

- [ ] Plan mode + Opus で `feature/m9-c-adopt-da16-design` branch
      (main 派生) 作成
- [ ] `/start-task` で `.steering/<YYYYMMDD>-m9-c-adopt-da16-design/`
      5 標準 file (本 prompt の前提に従って Read 完了後に着手)
- [ ] **Plan mode 内で `/reimagine`** で初回案破棄 → 再生成案と比較
- [ ] `decisions.md` DA16-1 で順序判断確定 (候補 A/B/C のどれを採用
      するか、根拠 verbatim 引用)
- [ ] `design.md` で採用候補の実装方針 + 続 PR scope 分割
- [ ] `blockers.md` で WeightedTrainer Blocker 2 を別 PR-2 として持ち越し
- [ ] Codex independent review **WSL2 経由で起動** + verbatim 保存
- [ ] 続 PR-2 (WeightedTrainer fix) 用 next-session prompt 起票
- [ ] `pre-push-check.sh|.ps1` 4 段全 pass 確認 → commit + push +
      `gh pr create`
- [ ] memory `project_plan_b_kant_phase_e_a6.md` を採用候補 A/B/C
      確定で update
```

---

**実施推奨タイミング**: kant Plan B verdict が現状 REJECT で保留中、
nietzsche / rikyu の Plan B 展開も blocked。本 ADR が確定するまで
他の m9-c-adopt 系 PR は実質ブロックされるため、**最優先**。
