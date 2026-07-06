# Loop Board — ecl-v0-hardening

> 単一書き手 (dashboard 端末) が events を畳んで再描画。worker は events.jsonl に append のみ。
> 更新は `/loop-status`。

task: **ecl-v0-hardening** (M13 ECL v0 determinism hardening Phase 1)
生成: 2026-07-06 / grill+issue-slicing 実起動済 / TASK-PRE Codex = pending

| issue | slice | verify | 状態 | 最終 event |
|---|---|---|---|---|
| 001-alpha | P2(B-2)+W(B-5) record-mode Plane2/clock | parse | ⏳ queued | — |
| 002-beta | R(B-3) retrieval 全順序化 | recheck | ⏳ queued | — |
| 003-gamma | P1(B-1)+C(B-4)+re-bake+version | recheck | ⏳ queued (blocked on α+β) | — |

## 実行方針 (ADR §5 FROZEN)
- 開発: α ∥ β 並行可 (α=loop.py+cycle.py+handoff.py roundtrip / β=retrieval.py、非交差)。
- merge/bake: **γ last で直列** — α・β を先に main merge → γ で単一 re-bake。
- γ は α (loop.py/handoff.py) + β (retrieval.py) の main merge を前提 (Dependencies binding)。

## ゲート
- [x] grill (未解決分岐 0・glossary `top-K over candidate pool` 追加)
- [x] issue-slicing (3 縦スライス)
- [ ] TASK-PRE Codex (issue 独立性・γ last 順序・re-bake 二重計上の第二意見)
- [ ] α 実装 → merge
- [ ] β 実装 → merge
- [ ] γ 実装 (re-bake) → merge
- [ ] 統合フル CI 緑 (pre-push-check)
- [ ] TASK-POST /cross-review
- [ ] PR (feat/ecl-v0-hardening→main)
