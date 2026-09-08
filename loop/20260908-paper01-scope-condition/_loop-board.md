# Loop Board — 20260908-paper01-scope-condition   ⏱ updated 07:44 UTC (1分前)
進捗 1/7 done · 🔄0 running · ⛔0 blocked · tokens ?/2,000,000

| # | issue | 状態 | phase | try | verify | branch | note | PR |
|---|-------|------|-------|-----|--------|--------|------|----|
| 001 | 実験雛形 + 事前登録凍結 + 共有 dataclass 契約 | ✅ done | merged | 1 | test✓ tc✓ lint✓ fmt✓ | worktree-agent-aad818922e579bb7d | watchdog 独立再検証で DONE_CONFIRMED。9 test = AC 001-1..9 に 1:1、mutation 19/19 KILL・生存 0。`e801ca2` で feature へ統合済 | – |
| 002 | 疎化層 leader clustering + ρ (fidelity pin (a)) | ⏳ queued | – | 0 | – | – | deps I-001 充足 = 実行可 | – |
| 003 | Stage 0 Δ=T−S 分解 + ラベル層別 | ⏳ queued | – | 0 | – | – | deps I-001 充足 = 実行可 | – |
| 004 | Stage 1 deflation 検定 | ⏳ queued | – | 0 | – | – | deps I-001 充足 = 実行可。**支持に倒れると論文を書かない**判定 | – |
| 005 | `decide_scope()` 全域・非恒真・F1-F7 | ⏳ queued | – | 0 | – | – | deps I-001 充足 = 実行可。encoder/統計を使わない純ロジック | – |
| 006 | τ\* 較正 + セル配線 (fidelity pin (b)) | ⏳ queued | – | 0 | – | – | deps I-002..I-005 = **全部の合流点** | – |
| 007 | 実走 + `run.sh` + `notes.md` (honest verdict) | ⏳ queued | – | 0 | – | – | deps I-006 | – |

## 現在のゲート

- **TASK-PRE (Codex gpt-5.5 / issue 独立性の第二意見)**: 実行中。
  出力 → `.steering/20260908-paper01-scope-condition/_codex-preplan.md` (verbatim)。
  I-002..I-005 の fan-out は**この結果を見てから**。
- 並列度 = 2 (`_loop-config.json` の `budget.parallel`)。
- **注意**: I-002..I-005 は 4 本とも `scripts/paper01_scope_condition.py` の別セクションを
  編集する。合流順序は TASK-PRE の推奨に従う。

## 未解決 (board 外)

- worktree `agent-aad818922e579bb7d` が locked のまま残存 (pid 20564 = 中断済セッション)。
  branch は統合済のため機能上の支障はないが、掃除は保留。
