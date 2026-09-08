## M13 aha-substrate-embodiment — locomotion-driven traversal harness（construction）

aha 測定 close（PR #86、well-posedness spike）を承けた **M13 situated-3D-substrate 建設の第一歩**。「二相 knob（DMN↔ECN 調合）を、traversal 自身が earn した λ>0 tick で **embodied 発火**させる舞台」を organ 無改変で建設する。**construction であって measurement 再入ではない**（effect/aha/verdict は一切測らない）。

FROZEN ADR = `.steering/20260723-m13-aha-substrate-embodiment/design-final.md`（Plan mode + `/reimagine` + Codex independent review〔設計時、Adopt-with-changes〕反映）。Loop Engineering で 4 issue を subagent-per-issue 実装（実装=Sonnet / review=Opus / 各 attempt 検証=Haiku、全 issue loop-watchdog recheck で DONE_CONFIRMED）。

### 何を建てたか

- **scripted planner が waypoint observation を消費する決定論 traversal harness**（`src/erre_sandbox/integration/embodied/traversal_live.py` 新設）。凍結 itinerary `peripatos→agora→garden→chashitsu→study→peripatos`（5 distinct zones / 5 cross-zone legs / 6 waypoint visits）を歩き、zone 横断で `advance_lambda` の λ を earn → 二相 knob が λ>0 の evaluation tick で発火。
- **organ 6ファイル無改変（Option A）**: 既存 `two_phase_live.run_two_phase_capture` を plan-source 差し替えのみで再利用（loop/cycle/handoff/two_phase/embodiment/geometry は read-only、全 issue 通して `git diff` 空を検証）。
- **Phase 4b の λ₀ seed 依存を解消**: λ を seed せず traversal の move で earn（tick0=seed λ=0 非発火・tick1+ 発火を実測 pin）。

### Witnesses（exact/checksum/boolean のみ、tune-to-pass 閉塞）

| | 内容 |
|---|---|
| **W1** replay fidelity | 記録 route（end-of-tick 物理 zone）== 凍結 itinerary exact-match。teeth = 500-tick undershoot で mismatch する回帰（同語反復でない＝物理到達を要求） |
| **W2** λ update-path | `expected_move_ticks=(0,1,2,3,4)` / `expected_positive_lambda_ticks=(1,2,3,4)` を frozen route から純粋導出し byte-pin。計算 λ 系列 = 実 run の SamplingSpy eligible-tick 完全一致（独立系統の cross-check） |
| **W3** knob algebra | `sign_inversion_fired`（λ>0 eval tick で符号反転、**符号確認のみ・生成品質/aha 不問**）+ generation-phase control（λ>0 でも σ 同一ゆえ knob-on≡off、非 vacuous に pin）+ record-knob-on pin |
| **W4** determinism | committed golden `--verify` byte-identical + 二層 fidelity anchor（A: `run_two_phase_capture(knob=None)`≡`run_ecl_loop` / B: knob-on vs knob=None が sampling allowlist 外差分ゼロ）+ 6桁量子化（provenance 再量子化）+ Win/WSL byte-parity-ready |

### Issue 004 = real qwen3 + real embedding channel-exercise（**code-path のみ land**）

`--real`（`OllamaChatClient` think=false + real `EmbeddingClient` nomic-embed-text 768d、新規依存なし）+ record→replay 決定論（`EmbeddingRecordReplayClient`）+ 非 gate channel-exercise witness（settled 空振りも honest 区別）。**real sealed 実走は user spend ratify hard gate ゆえ未実行**（mock unit のみ CI、`experiments/20260723-aha-traversal-real/` scaffold は artifacts 未作成・BLOCKED 明記）。

### claim 境界 / guard（不可侵）

construction-only・measurement 非再入。**firing ≈ 恒等式**で「aha 実在」証明でない（over-read 禁止）。effect/divergence/floor/aha proxy/verdict 非 emit（AST measurement-guard が module+script+test を scan して機構固定）、verdict=None、side file。**door② UNMET / door CLOSED / R-budget=0 / holding / measurement-line CLOSE 不変**。real embedding は zone routing の梃子でない（DA-1 embedding⊥zone）。emergent traversal は defer — **real mode も scripted waypoint stimulus に対する unscripted response であって emergent route ではない**（Codex 指摘で honest 訂正済）。

### レビュー coverage

- **per-issue code-reviewer(Opus)**: 各 issue HIGH ゼロ、MEDIUM/LOW 全反映。
- **TASK-POST cross-review**:
  - code-reviewer(Opus) 統合 leg = **HIGH なし・merge 可**。MEDIUM1（AST guard の script scan を full 3-hole へ復元）+ LOW 反映。
  - Codex(gpt-5.5/xhigh) = 1 回目は Windows sandbox のプロセス起動障害でファイル読取不能→捏造せず未成立報告、2 回目は diff 埋め込みで成立。**Verdict=Adopt-with-changes**。HIGH 2 件は diff 除外由来の false positive（envelope_stream.jsonl / repro.ps1 は commit 実在、pre-push 3808 passed で契約実証）、genuine な MEDIUM3+LOW2 反映。**うち LOW-2 で real mode の「emergent」over-read を独立検出 → honest 訂正**（Opus・実装者とも見落とし、独立第二意見の価値）。
  - verbatim = `.steering/20260723-m13-aha-substrate-embodiment/codex-review-taskpost.md`。

### Known-limitations（DA-9、user 裁定済）

- **Win/WSL byte-parity 物理実測は follow-up developer step**: golden は M4/phase4b（Win/WSL 通過実績）と同一量子化パイプライン継承で **byte-parity-ready** だが、WSL checkout が origin/main から 261-commit divergent（OSS cleanup 履歴 force-update 由来）で物理再 bake は defer。
- **golden `ecl_trace.jsonl` = 5.1MB**（10000行、physics=2000×5leg×全物理tick記録の構造的帰結、tune-to-pass 回避で物理数を緩めず受容）。
- **real qwen3 sealed 実走は別 spend ratify**（本 PR は code-path のみ）。

### CI

`pwsh scripts/dev/pre-push-check.ps1` 4 段全緑（ruff format --check / ruff check / mypy src / pytest -q = **3808 passed**）。既存 golden（v0/m2/m4/phase4b）回帰ゼロ。

Refs: `.steering/20260723-m13-aha-substrate-embodiment/` / `loop/20260723-m13-aha-substrate-embodiment/`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
