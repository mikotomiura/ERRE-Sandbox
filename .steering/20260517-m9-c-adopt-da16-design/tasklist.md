# タスクリスト — DA-16 ADR (kant Plan B PHASE_E_A6 順序判断)

## 準備
- [x] `.steering/20260516-m9-c-adopt-plan-b-eval-gen/decisions.md` DE-1〜DR-1 を Read
- [x] `.steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-verdict-plan-b-kant.md` を Read
- [x] `.steering/20260516-m9-c-adopt-plan-b-eval-gen/blockers.md` ブロッカー 2 を Read
- [x] `.steering/20260518-m9-c-adopt-plan-b-retrain/blockers.md` ブロッカー 2 を Read
- [x] `.steering/20260518-m9-c-adopt-plan-b-retrain/decisions.md` DR-5 / DR-6 を Read
- [x] `src/erre_sandbox/training/weighting.py:411` を Read
- [x] `src/erre_sandbox/training/train_kant_lora.py:1690-1715` を Read
- [x] `tests/test_training/test_weighted_trainer.py` を Read
- [x] memory `project_plan_b_kant_phase_e_a6.md` を確認
- [x] memory `feedback_pre_push_ci_parity.md` を確認
- [x] memory `feedback_claude_md_strict_compliance.md` を確認

## 設計判断 (Plan mode 相当 + /reimagine)
- [x] 初回案を意図的に破棄し、再生成案と並べて比較 (decisions.md DA16-1)
- [x] DA16-1: 順序判断 (候補 A/B/C の構造的比較、verbatim 引用で根拠記録)
- [x] DA16-2: WeightedTrainer fix 方針 (`.mean()` reduce、(a)-refined)
- [x] DA16-3: 続 PR scope 分割 (PR-2/3/4/5 の dependency graph)
- [x] DA16-4: DA-14 thresholds 不変宣言

## ステアリング書類
- [x] `requirement.md` 完成 (背景 / ゴール / スコープ / 受け入れ条件)
- [x] `design.md` 完成 (実装アプローチ / 変更対象 / 影響範囲 / ロールバック)
- [x] `decisions.md` 完成 (DA16-1〜DA16-4)
- [x] `blockers.md` 完成 (WeightedTrainer Blocker 2 持ち越し)
- [x] `tasklist.md` 完成 (本 file)

## Codex independent review (WSL2 経由必須)
- [x] `codex-review-prompt.md` 起票 (HIGH/MEDIUM/LOW format 指定)
- [x] WSL2 経由で `codex exec --skip-git-repo-check` 起動
      (Linux native codex v0.130.0、Node 20 + CODEX_HOME=/mnt/c/Users/
      johnd/.codex で Windows auth.json 流用、xhigh reasoning effort)
- [x] `codex-review.md` verbatim 保存 (user feedback authoritative、
      Codex CLI background は budget 超過リスク回避で TaskStop)
- [x] HIGH 指摘 (HIGH-1 eval_loss 比較性 / HIGH-2 batch=2 test fixture
      検出力) を本 PR 内で反映 (decisions.md DA16-2 トレードオフ +
      design.md 影響範囲/テスト戦略 + next-session-prompt + memory)
- [x] MEDIUM/LOW 指摘なし

## 続 PR-2 用 handoff
- [x] `next-session-prompt-FINAL-pr2-weighted-trainer-fix.md` 起票
      (PR-2 scope: weighting.py + test_weighted_trainer.py の修正、
      新規 3 件 test 追加に update)

## 完了処理 (commit + push + PR)
- [x] memory `project_plan_b_kant_phase_e_a6.md` を採用候補 A 確定 +
      PR-2/3/4/5 scope + Codex HIGH-1/HIGH-2 反映で update
- [ ] `pre-push-check.sh` または `.ps1` 4 段全 pass 確認
      (ruff format --check / ruff check / mypy src / pytest -q)
- [ ] git add + commit (Conventional Commits 形式、scope=m9-c-adopt)
- [ ] git push origin feature/m9-c-adopt-da16-design
- [ ] `gh pr create --base main --title "docs(steering): m9-c-adopt — DA-16 ADR (kant Plan B PHASE_E_A6 順序判断)"`
- [ ] PR description で `codex-review.md` をリンク参照
- [ ] PR URL を user に返却

## 持ち越し (本 PR scope 外、続 PR で扱う)
- WeightedTrainer Blocker 2 の **実装修正** (PR-2 scope)
- kant_r8_v4 retrain 実行 (PR-3 scope)
- DA-14 rerun verdict (PR-4 scope)
- rank=16 spike (PR-5 scope、PR-4 REJECT 時のみ)
- nietzsche / rikyu の Plan B 展開 (PR-4 ADOPT 後の別 ADR)
