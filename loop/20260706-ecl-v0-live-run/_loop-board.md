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
| 001 | live-capture apparatus (ThinkOffChatClient+harness+protocol/env) | recheck | subagent (fresh) | — | **DONE** db4d276 |
| 002 | Ollama-free replay-verify apparatus (O3a/O3b/O5) | recheck | subagent (fresh) | 001 | **DONE** 93a68b4 |
| 003 | sealed live run + committed artifact (G-GEAR live qwen3:8b) | manual | **人手 sealed gate** | 001+002 | **DONE** ce598fb (GO) |
| 004 | live-golden finalize + cross-platform confirm | recheck | in-session | 003 | **DONE** 5d0ca1a |

依存 = 001→002→003→004 (直列、003 は live Ollama 一発ゆえ loop 外)。全 subagent は fresh context + 独立 recheck。

## verdict = GO (construction validated、first-contact 成功)
sealed run (003): O1 完走 / O2 replay 再現 / O3a-b cross-platform WSL byte 一致 (`a528d547…`) → **Done=
O1∧O2∧O3a∧O3b HOLDS** / O5=**32/32** (全 tick parsed-history-dependent、think=False load-bearing) / O4 非縮退
(zone 2・target 32)。ECL v0 organ が real qwen3:8b で substrate を end-to-end 駆動。measurement 非再入 holding 維持。

## TASK-PRE / TASK-POST Codex
- TASK-PRE (b24e5b4): Adopt-with-changes (HIGH2/MEDIUM3/LOW1、全反映)。
- TASK-POST (6d6ac0d): code-reviewer(Opus)=Mergeable(HIGH 0) ∥ Codex=Adopt-with-changes (HIGH-1 manifest
  再検証 + MEDIUM-1 LIVE_MODEL pin、反映、manifest byte-identical 実測)。

## 次アクション
統合 CI 緑 → PR (feat/ecl-v0-live-run→main)。次 primary = 候補 B (N体化) or C (measurement gate) 別 ADR。

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
