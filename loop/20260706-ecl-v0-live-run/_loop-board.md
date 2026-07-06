# Loop board — M13 Phase 1 sealed live run (候補 A)

> `/loop-status` が events→board を再描画 (single writer)。手動 seed = 計画完了時点。
> ADR = FROZEN (`.steering/20260706-m13-forward-primary/design-final.md`)。measurement 非再入 holding 不可侵。

## Phase 1a (計画) = DONE
- grilling skill 実起動 → grill-goals.md (I1-I4 named test、D-1..8、**軸1=No** = ADR 未被覆 fork なし)。
- issue-slicing skill 実起動 → issues/001-004。
- loop config/events/board 初期化。

## issue 進捗

| # | issue | verify_level | mode | dep | status |
|---|---|---|---|---|---|
| 001 | live-capture apparatus (ThinkOffChatClient+harness+protocol/env) | recheck | autonomous /loop-issue | — | QUEUED |
| 002 | Ollama-free replay-verify apparatus (O3a/O3b/O5、synthetic テンプレ) | recheck | autonomous /loop-issue | 001 | QUEUED |
| 003 | sealed live run + committed artifact (G-GEAR live qwen3:8b) | manual | **人手 sealed gate** | 001+002 | QUEUED |
| 004 | live-golden finalize + cross-platform confirm | recheck | autonomous /loop-issue | 003 | QUEUED |

依存 = 001→002→003→004 (概ね直列、003 は live Ollama 一発ゆえ loop 外)。

## 掛け合わせる条件分岐 (6 軸)
1. grill 被覆: **No** (fork なし) → issue 直行 (Yes なら Stop→superseding ADR)。
2. 実行モード: 001/002/004=worktree /loop-issue+loop-watchdog / 003=人手 sealed gate。
3. verify_level: 001/002/004=recheck / (003=manual)。
4. 並行/直列: 001→002→003→004 直列 (003 前提 001+002)。
5. sealed verdict (003 後): Done+O5+O4非縮退→**GO**→次primary別ADR / replay 非決定→**Stop→superseding hardening** /
   O5==0·O4縮退→**construction 妥当性 branch**。
6. cross-platform: WSL byte 一致→O3a/O3b pass / drift→**Stop** (量子化漏れ)。

## 次アクション
- **/clear 推奨** (重い実装ループ前、handoff)。fresh session で next-session-prompt-phase1.md を貼付 →
  TASK-PRE Codex → 001 から worktree /loop-issue。
