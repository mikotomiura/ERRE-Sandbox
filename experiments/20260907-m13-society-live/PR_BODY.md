# M13 案 B — ミラー/society Layer2 を live 閉包経路へ（配線であって aha ではない）

> **honest framing（不可侵）**: land したのは **配線 / construction** であって
> **aha / emergence / effect ではない**。「N 体が live で相互作用した」は
> **配線到達性の boolean** であって社会的創発の実証ではない。ミラーは
> **prompt-level self-other context (construction wiring)** であって心の理論ではない。
> **wall-clock real-time session ではない**（`ManualClock(start=0.0)` + scripted in-process 摂動）。
> door② UNMET・計測ライン CLOSE・R-budget=0・holding は**いずれも不変**。`verdict` は明示 `None`。
> **M4 の `memory_centroid` collapse は解決していない。**
> **real qwen3 の実走は本 PR では一度も行っていない**（user の明示 spend ratify が要る別ゲート）。

## 何をしたか

M2 Layer2 の「ミラー」と N 体 society を、PR #89-91 で land した live 閉包経路に乗せた。
採用した経路は **「駆動ループを二本のままにせず一本にする」**:

- live 側は独自 scheduler を持たない。`society.py::run_society_loop` を**そのまま live の駆動ループ**に使う。
- inbound は既存 public kwarg `observation_factories` に router を渡して満たす。
- outbound は既存の生産者のまま。**live root は `inject_envelope` を呼ばない**（spy で 0 回を pin）。
- `society.py` には **additive kwarg 2 本だけ**（`two_phase_knob` / `on_runtime_ready`）。
  どちらも既定値で **byte-identical**、production `bootstrap()` は無改変。
- 新規 `integration/embodied/society_live_loop.py` は閉包専用 composition root。

設計は FROZEN ADR（`.steering/20260906-m13-society-live-closure/design-final.md`、
Plan + `/reimagine` + user 裁定 + Codex 設計レビュー Adopt-with-changes / HIGH4・MED5・LOW3 全反映）に従う。
`society.py` は M4 以降 frozen 扱いのため、本 ADR は **superseding ADR** として機能する。

## 縦スライス（Loop Engineering、全 7 issue DONE_CONFIRMED）

| issue | 内容 |
|---|---|
| I1 | `society.py` の additive seam 2 本（await できる readiness barrier / knob 素通し） |
| I2 | `SocietyInboundRouter`（idempotent drain coordinator / 5 分割 ledger / `wall_clock` pin） |
| I3 | 閉包 composition root + 同一 event loop `TaskGroup` supervisor |
| I4 | W-N1 到達性 + W-N3 outbound ownership witness |
| I5 | W-N2 ミラーが live cognition call に乗った witness |
| I6 | W-N4 Plane G byte-parity + request conformance spy |
| I7 | sealed real-run ハーネス（**code-path のみ**、実走は別ゲート） |

**実行方式**: main はオーケストレータに徹し、issue ごとに subagent を立てた。
各 attempt を `test-runner`(Haiku) → `loop-watchdog`(Haiku) で客観検証し、
**executor の自己申告を verdict にしていない**。

## acceptance（boolean / count のみ、`verdict` は明示 `None`）

- **W-N1**: injected な各 correlation-id が**狙った agent** の seam を通過した boolean。
  到達性の母集団は **injected のみ**（`rejected` / `dropped` は plain count で別枠）。
  seam 粒度は **3 段で非一様**（per-correlation / per (agent, window) / tick-level co-occurrence）で、
  **「到達性は因果ではない」**を `note` に明記。
- **W-N2**: committed prompt に非空の self-other segment が乗ったことの boolean。
  disjointness は **observation 由来 memory field に限定**（Codex L-2）。
  **新規 LLM call を作らない**（call 数 = N × ticks 不変）。
- **W-N3**: **cognition kind 限定**（`move` / `speech` / `animation` / `agent_update`）の多重集合一致。
  consume 側 ledger は **`gateway.py` 完全無改変**のまま public な `Registry.reserve_slot` から取る
  （**`drain_envelopes()` の事後観測は使わない** = Codex H-2 が却下した race 経路）。
  `dialog_*` は **plain count annotation（非 gate）**、除外理由をコードに明記（完全版は別 ADR）。
- **W-N4**: knob-on capture → **knob-off の無改変 `run_society_loop`** への replay で
  `ecl_trace_checksum` / `event_log_checksum` が **byte 一致**。
  **replay 側 spy** で `(agent_id, window, system_prompt, user_prompt)` を照合し、
  **`sampling` は型の形で照合対象外**（Codex H-4）。
- **W-N5**: `run_society_loop(two_phase_knob=None, on_runtime_ready=None)` が現状と byte-identical。

## 無改変境界（ADR §4）

`git diff origin/main..HEAD` 上、`src/` の変更は **`society.py`（+66 / -0、additive kwarg ちょうど 2 本）**と
**新規 `society_live_loop.py`** のみ。organ（`cognition/**` / `world/**` /
`integration/embodied/{loop,two_phase_live,traversal_live,handoff}.py` / `erre/**` /
`contracts/geometry.py` / 凍結 `evidence/**`）、production `bootstrap.py`、`gateway.py`、`inbound.py`、
`live_loop.py`、`society_live.py`、`ControlEnvelope`、SCHEMA_VERSION、既存 golden、
共有 `tests/test_integration/_measurement_guard.py` は**いずれも無改変**。

**3 本目の kwarg は足していない**（Stop S1 非該当）。Stop S1〜S5 いずれも非該当。

## TASK-POST `/cross-review`（二者レビュー）

`code-reviewer`(Opus) と `Codex`(gpt-5.5) の二者。**指摘がほとんど重ならなかった**ことに意味がある。

### HIGH 2 件（いずれも反映済）

1. **Opus**: `target_agent_routing` seam の非恒真性が test で pin されていなかった。
   **mutation 実験で実証** — 第二項を削っても 40 test 全緑だった。
   第一項は `world_perturbation_to_perception` の無条件写像ゆえ恒真なので、
   **W-N1 の唯一の N 体 routing witness が「壊れても気付けない」状態**だった。
   → 誤バケツ row を**同じ witness 関数に通す**負例を追加。
   **orchestrator が mutation 実験を再現し、削除で実際に test が落ちることを確認**
   （`1 failed, 41 passed` → 復元後 `42 passed`）。
2. **Codex**: `scope_boundary` が capture_mode に依らず共有される annotation なのに
   **無条件で real qwen3 到達を主張**しており、**commit 済みの rehearsal manifest**
   （`real_backend=false`）に載っていた。→ 条件形へ統一し manifest を再生成。
   **`replay_checksum` は不変**（記述のみの修正）。

### 一致点

`SocietyBroadcastLedger.detach()` の解放漏れ — Opus が「dead code」を指摘 → 修正 →
**Codex が「例外経路は依然として塞がっていない」**と捕まえた。修正が半分だったことを二者目が検出。

### MEDIUM 8 / LOW 6

7 件反映（例外経路 detach、live root への measurement guard 適用、provenance gate の digest 形式検証、
`--force-reason` の必須化と記録、manifest の L1 条件化、seam の検出能力の docstring 明記、
`side_files` 文言の実態合わせ）。`society_live_loop.py` の 3 分割は **follow-up `/refactor` へ defer**、
LOW 5 件は `blockers.md` に defer 理由付きで持ち越し。

## 検証

- **pre-push CI parity 4 段 ALL CHECKS PASSED（exit 0）** — ruff format --check / ruff check /
  mypy src / pytest -q (non-godot)
- witness test を **3 回連続実行して完全一致**（flaky なし）
- **real 未実走の証拠**: `experiments/20260907-m13-society-live/artifacts/` 不在、
  session 中 `ollama` 未実行、`run.ps1` の env ゲートが python 起動より前、
  spend gate が `capture()` 本体にあり `OllamaChatClient` の import より前（AST で pin）

## 残る hard gate（**いずれも user 裁定**）

- **最終 merge**
- **real qwen3 sealed 実走**（spend ratify）— ハーネスは land 済
- **WSL byte-parity の実測**（D3）— committed rehearsal bundle を Linux 側で `--verify` する経路。
  **測っている範囲** = UCRT で bake した bytes が glibc replay で同一であって、
  Linux 上で再 bake したのではない

## 記録

- ADR / 設計判断: `.steering/20260906-m13-society-live-closure/{design-final,decisions,blockers}.md`
- Codex verbatim: `.steering/20260906-m13-society-live-closure/codex-review-taskpost.md`
- Loop: `loop/20260906-m13-society-live-closure/{_loop-events.jsonl,issues/,retrospective.md}`

実装中の設計判断は **DA-SLC-4〜9** として記録した。**いずれも orchestrator 判断であって user 裁定ではない**
（とくに **DA-SLC-4** = §M8 spend guard の閉 allowlist に `erre_sandbox.erre.two_phase` を 1 語追加、
**DA-SLC-7** = rate limit による executor モデルの一時振替）。

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01PVkyWmYiyNEHdRCu8rzUrZ
