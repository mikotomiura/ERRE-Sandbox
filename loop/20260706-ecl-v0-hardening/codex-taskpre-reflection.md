# TASK-PRE Codex reflection — ECL v0 hardening Phase 1

> Codex (gpt-5.5/xhigh/read-only) verbatim = `.steering/20260706-m13-ecl-v0-determinism-hardening/_codex-preplan.md`。
> **Verdict = Adopt with changes、HIGH blocker なし**。sequencing 主張 (α/β 独立 merge 可・γ last) 妥当と確認。
> prompt = `codex-taskpre-prompt.md` (機密なし)。tokens ≈ 179,776 (per-invocation 200K 内、daily 1M 内)。

## findings 反映 (5 件: MEDIUM 3 / LOW 2)
- **M-1 (α 後方互換)**: `RecordedLlmCall` union は `outcome="ok"` default + `_from_dict` が `outcome` 欠を許容
  (`data.get("outcome","ok")`)、`response` optional。既存 committed decisions.jsonl (outcome 欠・response 有) の
  replay を壊さない。→ **α subagent prompt に binding 明記**。
- **M-2 (α raised replay の stream 前進)**: replay で `raised` は **再送の前に** recorded call を `_used` へ
  append + `_replay_index` 前進させる (現行 client は成功後にのみ append)。driver は per-tick before/after の
  明示 count で対応付け、`used[-1]` blind 参照や位置参照をしない。→ **α subagent prompt に binding 明記**。
- **M-3 (γ 2x-bake gate)**: 2x-bake 決定性 gate は **全 4 artifact (manifest.json 含む) を fresh-render 2 回**し
  **同一 env_pins** で byte/SHA 一致比較する形でなければ不十分 (既存 `--verify` は committed hash 照合のみで
  fresh 2 回 render しない)。→ **α-G6 test = `run_golden`→`render_golden(env_pins=FIXED)` を 2 回・全 4 byte 一致**
  に確定 (grill D-α3 を M-3 で補強)。γ subagent にも継承。
- **L-1 (β 候補 pool 表現)**: candidate pool は flat 50 でなく **kind (episodic/semantic) × scope (agent/world)
  ごと 50**。→ glossary `top-K over candidate pool` 修正済 + β subagent prompt / docstring に反映。
- **L-2 (β "1 memory/tick" 不正確)**: 実測 = golden の tick 1 に stress follow-up 由来の余分 memory `0001-01` 有。
  安全な主張 = **ECL top-K に届く candidates は k_ecl=8 を超えない** (retrieval time で candidates ≤ 8、
  truncation 不発)。→ **本 orchestrator が β sort 変更を一時適用し ECL 29 test 全 pass (AC2 golden 含む) を実測確認**、
  β の golden-invariance を empirical 確定。β issue の rationale を「candidates ≤ k_ecl=8 で truncation 不発」に修正。

## sequencing 確定 (Codex 回答)
- Q1: 独立十分。α/β 独立 merge 可、γ binding-last。α/γ は同 loop.py/handoff.py を別意味領域で触る (Plane2/clock vs
  checksum/manifest)、隠れ結合は `RecordedLlmCall` schema のみ (単一ブランチ逐次実装で構造的に解消)。
- Q2: sequencing 主張は互換 caveat 付きで正しい。**本 orchestrator が β を実測して確定済**。
- Q3: γ 単一 re-bake は α+β 後なら {P1+C+W+β 波及} を一括捕捉。既存 `--verify` 単独に依存せず 2x-bake gate を追加。
- Q5: slice 境界・verify_level (α=parse / β=recheck / γ=recheck) 妥当。

## 単一ブランチ逐次実装の決定 (worktree 並列の代替根拠)
α (loop/cycle/handoff) と β (retrieval) はファイル非交差。単一エージェント逐次では worktree 並列隔離の利得は
index 競合回避のみ → 各 slice を **subagent (worktree 隔離・fresh context)** に投げて実現。最終 PR ターゲット
`feat/ecl-v0-hardening→main` は単一 PR ゆえ、α→β→γ(re-bake last) を同一 feature ブランチに集約する。
「α・β を先に merge → γ で bake」の ADR 要件は「γ の bake が α+β を含む tree で走る」ことで満たされる。
