# Tasklist — 認知深化 7-point 提案 判定タスク

## Phase 0: 把握 (DONE)

- [x] 既存コードベース探索 (LLMPlan / persona / memory / belief / shuhari)
- [x] M9-B LoRA design-final.md の前提確認
- [x] Codex daily budget 確認 (1M/day、新日の 2026-05-08 OK)

## Phase 1: 判定文書作成 (DONE)

- [x] requirement.md 起票 (背景 + 7 提案 + 既存衝突 + 受入条件)
- [x] design.md 起票 (Claude 単独 initial 判定)
- [x] tasklist.md 起票 (本ファイル)

## Phase 2: User clarification 反映 (DONE 2026-05-08)

- [x] 3 点 clarification を requirement.md に追記
- [x] design-clarified.md 起票 (二層アーキテクチャ解釈、判定 3 件反転)
- [x] codex-review-prompt.md 更新 (二層解釈 + 7 新 question を反映)

## Phase 3: 独立判定 (DONE)

- [x] /reimagine subagent 起動 (background、design-reimagine.md 生成完了)
- [x] /reimagine 完了 — Compression-Loop counter-proposal 取得 (5/7 validate、6/7 reject)
- [x] User decision: Option A 確定 (新個体 + 二層 + 完全な人間化)
- [x] codex-review-prompt.md を Option A stress-test 焦点に更新
- [x] Codex independent review 完了 (197K tokens、ADOPT-WITH-CHANGES、HIGH 7/MEDIUM 5/LOW 3)
- [x] codex-review.md verbatim 保存

## Phase 4: 統合 (DONE)

- [x] 3 ソース (Claude / reimagine / Codex) 突合 → design-final.md
- [x] design-final.md 起票 (採用判定 + phasing + operational 制約 + acceptance 定量)
- [x] decisions.md 起票 (DA-1〜DA-13、ADR、reject 理由含む)
- [x] HIGH 7 件すべて反映確認 (HIGH-1 thesis re-articulation / HIGH-2 LLM 自己宣言予防 /
      HIGH-3 LoRA contamination / HIGH-4 Burrows 役割 / HIGH-5 S1-S3 縮小 /
      HIGH-6 cache safe / HIGH-7 scope MVP)

## Phase 5: ハンドオフ (pending、auto mode で走らせる)

- [x] TOE Reasoning model アイディアの設計判断を
      `toe-reasoning-model-judgment.md` として外付け記憶化 (2026-05-11)
- [ ] CLAUDE.md / functional-design.md の thesis re-articulation 反映要否判断 (M10-0 着手前)
- [ ] PR #127 (M9-B) design-final.md に "individual_layer_enabled=false manifest +
      exclusion rule" 追記タスク作成 (M9-B execution kick 前)
- [ ] M10-0 task の `.steering/` dir 作成 (M9 完了後 kick、個体化 metric / dataset manifest /
      cache benchmark / prompt ordering contract)
- [ ] M10-A scaffold task の `.steering/` dir 作成
- [ ] auto memory に project_cognition_deepen_decision を保存 (DA-1 thesis re-articulation /
      Option A choice / phasing M10-0 → M11-C → M12+ gate)

## 非範囲

- 実装着手 (本タスクは判定のみ、実装は M10-0 配下の後続タスクで)
- M9-eval / M9-B / G-GEAR run1 calibration の中断・修正
- philosopher_seed 名称の最終決定 (rename しない、loader wrapper で対応 = DA-8)

## 非範囲

- 実装着手 (本タスクは判定のみ、実装は M10-A 配下の後続タスクで)
- M9-eval / M9-B / G-GEAR run1 calibration の中断・修正
- philosopher_seed 名称の最終決定 (Codex review で代替命名候補も募る)
