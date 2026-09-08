# Loop Board — 20260908-paper01-scope-condition   ⏱ updated 12:30 UTC
進捗 6/8 done · 🔄1 running · ⛔0 blocked · tokens ?/2,000,000

| # | issue | 状態 | phase | try | verify | branch | note | PR |
|---|-------|------|-------|-----|--------|--------|------|----|
| 001 | 実験雛形 + 事前登録凍結 + 共有 dataclass 契約 | ✅ done | merged | 1 | test✓ tc✓ lint✓ fmt✓ | worktree-agent-aad818922e579bb7d | watchdog 独立再検証で DONE_CONFIRMED。9 test = AC 001-1..9 に 1:1、mutation 19/19 KILL・生存 0。`e801ca2` で feature へ統合済 | – |
| 001b | 共有契約の穴埋め (TASK-PRE HIGH-3/4/5+MED-1) + 節 anchor | ✅ done | merged | 1 | test✓ tc✓ lint✓ fmt✓ | worktree-agent-a156ae8 | 独立再検証=orchestrator (DA-SC-21)。full 3972 passed/exit 0、mutation 11/11 KILL。witness の過大申告を実測で訂正 (`872ae26`)。`72c5c5d` で統合 | – |
| 002 | 疎化層 leader clustering + ρ (fidelity pin (a)) | ✅ done | merged | 1 | test✓ tc✓ lint✓ fmt✓ | worktree-agent-ab0953a | executor が 429 で強制終了→実装/test/mutation は完了済だったので orchestrator が verify 回し直して commit。27 passed、mutation 7/7 KILL。`c5ed0e4` で統合 | – |
| 003 | Stage 0 Δ=T−S 分解 + ラベル層別 | ✅ done | merged | 1 | test✓ tc✓ lint✓ fmt✓ | worktree-agent-a4cb2df | 適用範囲を純 max-cos に限定 (X1/X2 拒否)。engaged 述語は `near_dup_flags_from_similarity` を verbatim 使用。mutation 14/14 必須 kill (M4=到達不能を honest 記録)。`e973229` | – |
| 004 | Stage 1 deflation 検定 | ✅ done | merged | 1 | test✓ tc✓ lint✓ fmt✓ | worktree-agent-a709562 | **境界 3 mutant を orchestrator が実測**: `<=`→`<` (2 kill) / 閉→開区間 (2 kill) / **INCONCLUSIVE→REJECTED 丸め (5 kill)**。mutation 7/7 KILL。`372757d` | – |
| 005 | `decide_scope()` 全域・非恒真・F1-F7 | ✅ done | merged | 2 | test✓ tc✓ lint✓ fmt✓ | worktree-agent-a12c948 | **中核 witness 実測確認済**: INCONCLUSIVE→WRITE 漏れ mutant を当てると `test_inconclusive_never_derives_write_right` のみ落ちる (1F/38P)。真理値表 576 組合せ網羅、mutation 11/11 KILL。`3ab8549` で統合 | – |
| 006 | τ\* 較正 + セル配線 (fidelity pin (b)) | ⏳ queued | – | 0 | – | – | deps I-002..I-005 = **全部の合流点** | – |
| 007 | 実走 + `run.sh` + `notes.md` (honest verdict) | ⏳ queued | – | 0 | – | – | deps I-006 | – |

## 現在のゲート

- **TASK-PRE 完了** (Codex gpt-5.5、191,098 tokens)。Verdict **Revise** / HIGH 5 / MEDIUM 5 / LOW 2。
  HIGH 4 件を実物で検証し**すべて実在**を確認 → `issues/001b.md` と 002-007 本文へ反映済 (`cc1dd96`)。
  原文 = `.steering/.../\_codex-preplan.md` (verbatim)。
- **wave 1 実行中**: I-002 + I-005。次 wave = I-003 + I-004 → I-006 → I-007。
- **フルスイートは統合時に 1 回だけ** (DA-SC-20)。per-issue executor には持たせない
  (30 分 suite の並行実行は flaky + 切り分けが濁る。実際に 3 回の停止と誤 kill を招いた)。

## 未解決 (board 外)

- worktree `agent-aad818922e579bb7d` が locked のまま残存 (pid 20564 = 中断済セッション)。
  branch は統合済のため機能上の支障はないが、掃除は保留。
