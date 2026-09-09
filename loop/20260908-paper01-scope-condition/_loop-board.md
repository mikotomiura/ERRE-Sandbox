# Loop Board — 20260908-paper01-scope-condition   ⏱ updated 2026-09-09
進捗 **9/9 done** · 🔄0 running · ⛔0 blocked · **実走完了 · verdict = `DO_NOT_WRITE` (「書かない」枝)** · 実走後 CI 緑 `8a17919` (4235 passed / 53 skipped) · draft PR #96 · **merge は user 裁定**

| # | issue | 状態 | phase | try | verify | branch | note | PR |
|---|-------|------|-------|-----|--------|--------|------|----|
| 001 | 実験雛形 + 事前登録凍結 + 共有 dataclass 契約 | ✅ done | merged | 1 | test✓ tc✓ lint✓ fmt✓ | worktree-agent-aad818922e579bb7d | watchdog 独立再検証で DONE_CONFIRMED。9 test = AC 001-1..9 に 1:1、mutation 19/19 KILL・生存 0。`e801ca2` で feature へ統合済 | – |
| 001b | 共有契約の穴埋め (TASK-PRE HIGH-3/4/5+MED-1) + 節 anchor | ✅ done | merged | 1 | test✓ tc✓ lint✓ fmt✓ | worktree-agent-a156ae8 | 独立再検証=orchestrator (DA-SC-21)。full 3972 passed/exit 0、mutation 11/11 KILL。witness の過大申告を実測で訂正 (`872ae26`)。`72c5c5d` で統合 | – |
| 002 | 疎化層 leader clustering + ρ (fidelity pin (a)) | ✅ done | merged | 1 | test✓ tc✓ lint✓ fmt✓ | worktree-agent-ab0953a | executor が 429 で強制終了→実装/test/mutation は完了済だったので orchestrator が verify 回し直して commit。27 passed、mutation 7/7 KILL。`c5ed0e4` で統合 | – |
| 003 | Stage 0 Δ=T−S 分解 + ラベル層別 | ✅ done | merged | 1 | test✓ tc✓ lint✓ fmt✓ | worktree-agent-a4cb2df | 適用範囲を純 max-cos に限定 (X1/X2 拒否)。engaged 述語は `near_dup_flags_from_similarity` を verbatim 使用。mutation 14/14 必須 kill (M4=到達不能を honest 記録)。`e973229` | – |
| 004 | Stage 1 deflation 検定 | ✅ done | merged | 1 | test✓ tc✓ lint✓ fmt✓ | worktree-agent-a709562 | **境界 3 mutant を orchestrator が実測**: `<=`→`<` (2 kill) / 閉→開区間 (2 kill) / **INCONCLUSIVE→REJECTED 丸め (5 kill)**。mutation 7/7 KILL。`372757d` | – |
| 005 | `decide_scope()` 全域・非恒真・F1-F7 | ✅ done | merged | 2 | test✓ tc✓ lint✓ fmt✓ | worktree-agent-a12c948 | **中核 witness 実測確認済**: INCONCLUSIVE→WRITE 漏れ mutant を当てると `test_inconclusive_never_derives_write_right` のみ落ちる (1F/38P)。真理値表 576 組合せ網羅、mutation 11/11 KILL。`3ab8549` で統合 | – |
| 006 | τ\* 較正 + セル配線 (fidelity pin (b)) | ✅ done | merged | 1 | test✓ tc✓ lint✓ fmt✓ | worktree-agent-a5c3f0f | 全部の合流点。ブロッカー 2 を `decide_scope()` 無改変・呼び出し側を合わせて解決、spy で実配線 pin。85 passed/1 skipped (skip = fidelity pin (b))、mutation 8/8 KILL。`cf501ff` で統合 | – |
| 007a | `--fidelity` 本体 + `--scope` の Cambridge 配線 + run.sh 一式 | ✅ done | merged | 1 | test✓ tc✓ lint✓ fmt✓ | worktree-agent-adf4ba0 | **実走なし・ネットワーク取得なし**。exit code 三分岐 (0/1=不一致/2=データ欠如)。notes.md は結果節がプレースホルダのみ。mutation 7/7 KILL。`b51efb9` | – |
| 007b | 実走 + verdict の honest 記録 | ✅ done | pushed | 1 | test✓ tc✓ lint✓ fmt✓ | main checkout (逐次実行、subagent なし) | **user 認可を得て実走**。Gate 1 = `--fidelity` exit 0 で **pin (b) 初回実行が G1 ARM-A を再現 (ブロッカー 3 CLOSED)**。run.sh exit 0 + marker、2 回実行 SHA-256 一致。**verdict = `DO_NOT_WRITE`** (`condition_c_supported=false` / `stage1_outcome=DEFLATION_REJECTED` / `fail_reason=null`)。意味突き合わせで退行 3 件検出 → Limitations 9/10/11。`62404b6`+`8a17919` | #96 |

## 出口 (design-final.md §5、確定)

**「書かない」枝。論文 01 は単独では出さない。** Stage 1 は deflation を棄却したが、
Stage 2 で条件 C が支持されなかった (ARM-S が両分割とも `PASS`)。
`fail_reason=null` = F1-F7 のいずれも非該当 ⇒ **構成不能でも監査未作動でもなく、
装置は動いて条件 C が実測で支持されなかった**。

- **Done は達成** (DA-SC-4: 「C が支持された」ことではなく「事前登録した測定が完走し
  凍結済み判定関数が全域で verdict を出した」こと)。**結果が期待と逆でも
  `design-final.md` を開かなかった。**
- 次: G1 + 本タスクの結果とハーネスを**論文 03 の方法節 / limitation に畳む** (別タスク)。
  **B-G1-5 (タイトル / repo 名) の再検討は発動しない。**

## 完了したゲート

- **TASK-PRE 完了** (Codex gpt-5.5、191,098 tokens)。Verdict **Revise** / HIGH 5 / MEDIUM 5 / LOW 2。
  HIGH 4 件を実物で検証し**すべて実在**を確認 → `issues/001b.md` と 002-007 本文へ反映済 (`cc1dd96`)。
  原文 = `.steering/.../\_codex-preplan.md` (verbatim)。**ただし DA-SC-14 に反する無断起動**
  だった (DA-SC-16 に honest 記録)。
- **TASK-POST 完了** (`/cross-review`)。code-reviewer(Opus) HIGH 0 / MEDIUM 2 / LOW 4、
  Codex HIGH 0 / MEDIUM 2 / LOW 1。**MEDIUM 4 件は二者で重複ゼロ**、全件 + LOW 1 反映。
  Codex 側は NumPy DLL load failure で**静的読解のみ** (DA-SC-22)。
- **フルスイートは統合時に 1 回だけ** (DA-SC-20)。per-issue executor には持たせない
  (30 分 suite の並行実行は flaky + 切り分けが濁る。実際に 3 回の停止と誤 kill を招いた)。
- **実走後 CI parity** (`8a17919`): ALL CHECKS PASSED / 4235 passed / 53 skipped / 27:36。

## 未解決 (board 外)

- worktree `agent-aad818922e579bb7d` が locked のまま残存 (pid 20564 = 中断済セッション)。
  branch は統合済のため機能上の支障はないが、掃除は保留。
