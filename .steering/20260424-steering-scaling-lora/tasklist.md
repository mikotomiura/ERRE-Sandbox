# Tasklist — L6 Steering (LoRA / Scaling / User-Dialogue IF)

> 全て文書タスク、Plan mode は /reimagine のため一時使用 (v1→v2 転回の判断に必要)。
> 2-3h 見込 (v2 採用で design.md が厚くなった反映、~310 行総量)。
> 並走可能 (Slice β / γ の待ち時間に進められる)。
>
> **/reimagine 履歴**: v1 (tasklist 暫定採用 c/a/a) → v2 (defer/observability/2-phase)
> 転回済。詳細 `design-comparison.md`。本 tasklist は v2 実行のためにリライト済。

## Setup

- [x] `feat/steering-scaling-lora` branch を main から切る
- [x] `llm-inference` Skill を Read、VRAM 予算と現在のモデル体系を把握
- [x] `persona-erre` Skill を Read、ERRE mode との関係を把握
- [x] base model 名を `ollama_adapter.py:37` で確定 (`qwen3:8b`)

## /reimagine 適用

- [x] `design-v1.md` に初回案を退避
- [x] requirement.md だけで v2 をゼロ生成 → `design.md`
- [x] `design-comparison.md` で v1/v2 を並列比較
- [x] ユーザーが v2 採用を確定

## design.md (v2 substantive research repository)

- [x] §1 現状スナップショット (推論スタック / persona 分化 / agent 数制約 / WS-UI)
- [x] §2 3 軸の選択肢 taxonomy (各 a-f の 6 択まで網羅)
- [x] §3 M8 共通 preconditions (episodic log / baseline metric / session phase)
- [x] §4 方法論的緊張 (autonomy vs intervention)
- [x] §5 MASTER-PLAN M8 行提案
- [x] §6-§9 実行フロー / 変更対象 / 検証 / Out of Scope / 設計判断履歴

## decisions.md (3 ADR、各 ≤20 行)

- [x] **D1. LoRA による persona 分化 — defer-and-measure**
  - architecture 確定は M9 まで defer、M8 では baseline 計測と log pipeline
  - 次アクション: `m8-episodic-log-pipeline`, `m8-baseline-quality-metric`
- [x] **D2. Agent scaling — observability-triggered**
  - 3 維持 + metric 閾値超過で contrastive +1 (量先行ではなく metric-first)
  - 次アクション: `m8-scaling-bottleneck-profiling`
- [x] **D3. User-dialogue IF — two-phase methodology**
  - autonomous run と Q&A epoch を session_phase で時間分離
  - 次アクション: `m8-session-phase-model`

## MASTER-PLAN.md 更新

- [x] M8 行を追加 (M7 と M9 の間の空白を埋める)
- [x] M9 行に L6 ADR1 defer-and-measure 前提を追記

## Review + PR

- [ ] `decisions.md` の 3 ADR を再読み、Skill 参照 (llm-inference / persona-erre /
      architecture-rules) が各 ADR 末に残っているか確認
- [ ] `wc -l decisions.md` と ADR 別 line count で各 ≤20 行を確認
- [ ] branch diff が **docs のみ** であることを確認 (`git diff --stat` で .md 以外ゼロ)
- [ ] commit 作成 (Conventional Commits、scope は `steering`)
- [ ] `git push -u origin feat/steering-scaling-lora`
- [ ] `gh pr create`、title `docs(steering): L6 — scaling / LoRA / user-dialogue IF roadmap`
- [ ] PR body に v2 採用骨子 + 親 D2 への Ref + /reimagine 履歴を記載
- [ ] merge 後、memory `project_m7_beta_merged.md` を「L6 完了、次は γ or β live-accept」に更新
- [ ] merge 後、本 tasklist を完了記録して close
