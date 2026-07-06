# Loop Board — ecl-v0-hardening

> 単一書き手 (dashboard 端末) が events を畳んで再描画。worker は events.jsonl に append のみ。
> 更新は `/loop-status`。

task: **ecl-v0-hardening** (M13 ECL v0 determinism hardening Phase 1)
生成: 2026-07-06 / grill+issue-slicing 実起動済 / TASK-PRE Codex = pending

| issue | slice | verify | 状態 | 最終 event |
|---|---|---|---|---|
| 001-alpha | P2(B-2)+W(B-5) record-mode Plane2/clock | parse | ✅ done | issue_done 4d25425 (3364 passed) |
| 002-beta | R(B-3) retrieval 全順序化 | recheck | ✅ done | issue_done aea74d8 (3366 passed, golden 不変) |
| 003-gamma | P1(B-1)+C(B-4)+re-bake+version | recheck | ✅ done | issue_done 26ab07e (3369 passed, 2x-bake 決定的, checksum 11a4554) |

## 実行方針 (ADR §5 FROZEN)
- 開発: α ∥ β 並行可 (α=loop.py+cycle.py+handoff.py roundtrip / β=retrieval.py、非交差)。
- merge/bake: **γ last で直列** — α・β を先に main merge → γ で単一 re-bake。
- γ は α (loop.py/handoff.py) + β (retrieval.py) の main merge を前提 (Dependencies binding)。

## ゲート
- [x] grill (未解決分岐 0・glossary `top-K over candidate pool` 追加)
- [x] issue-slicing (3 縦スライス)
- [x] TASK-PRE Codex (Adopt-with-changes、HIGH なし、findings 5 件反映)
- [x] α 実装 (4d25425)
- [x] β 実装 (aea74d8)
- [x] γ 実装 (re-bake v2、26ab07e)
- [x] 統合フル CI 緑 (pre-push src tests 4 段、3369 passed / 66 skipped / golden verify OK)
- [x] TASK-POST /cross-review (二者 HIGH なし = Mergeable。CR-M1/M2/L2 + Codex-L1 反映 = review-fixes faf47a9、3370 passed)
- [ ] PR (feat/ecl-v0-hardening→main) — 最終 pre-push ゲート後
