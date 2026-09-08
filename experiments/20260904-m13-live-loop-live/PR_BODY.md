## 何をしたか

M13 live-loop **I7 の sealed real run を実走**した。PR #90 で landed した封印ハーネス
(`scripts/m13_live_loop_capture.py`) を、事前登録どおりのパラメータで **real qwen3:8b
(think=False) + real nomic-embed-text** に対して **1 回だけ**走らせ、出た結果をそのまま記録する。

設計は FROZEN ADR (`.steering/20260724-m13-live-loop-closure/design-final.md` §5 Issue 007)、
事前登録は `LIVE_LOOP_OBSERVABLES` が SSOT。**実走のためのコード変更はゼロ**
(`scripts/m13_live_loop_capture.py` も `src/**` も無改変)。

## honest framing (不可侵・最重要)

**これは配線 (wiring) の real 実走であって、aha / emergence / effect ではない。**

- 全 gate 緑で言えることは **"wiring reached each seam (live, real qwen3)"** のみ。
  事前登録した bounded 摂動が perception → cognition → knob → movement → envelope の各 seam に
  real backend 越しに到達し、その run 全体が committed bytes から決定論的に再構成できた、という
  boolean 観察である。
- **firing ≠ detectability**。evaluation-phase の符号反転が起きたことは、その bias が
  zone / 行動 / aha を変えることを意味しない。それは凍結された第2リンクで、本 run は測っていない。
- door② **UNMET**・計測ライン **CLOSE**・R-budget=0・holding は**すべて不変**。
  `verdict: null` を明示 emit しており、measurement には再入していない。

### I7 固有の 2 境界 (記述から落とさない)

1. **real なのは cognition 面のみ**。摂動は scripted bounded 列を `InboundSink` に直接投入する構成で、
   **live Godot クライアントは使っていない** (Godot send 契約は I5 で検証済、本機に godot バイナリ無し)。
2. **wall-clock real-time セッションではない**。byte-parity 規律のため `ManualClock(start=0.0)`。
   「live」= cognition チャネルが real、という意味。

## 結果 (2026-09-06、1 回のみ・tuning ゼロ)

`run.ps1` を 1 回 (09:29:11〜09:30:40 JST、89 秒、exit 0)。再走 / パラメータ変更 / `--force` なし。
provenance は実走直前に Ollama `/api/tags` で再確認し事前登録値と一致
(qwen3:8b digest `500a1f06…b8b41` = Phase 4b と同一 pull、ollama 0.32.12、RTX 5060 Ti 16GB)。

| Done | 判定 | 実測 |
|---|---|---|
| **L1** 完走 | **PASS** | exit 0 / 32 cognition × 20 physics tick / 6 artifact / injected perturbations 32 |
| **L2** 決定論 replay | **PASS** | Plane G checksum `43eb904d…2888eb` = manifest 一致 / 両チャネル `inner_invocations=0` / embedding 97/97 / request conformance LLM 32/32・embedding 97/97 / 5 artifact SHA-256 全一致 / `manifest.json` 再 render byte 一致 / envelope 96 通 schema 準拠 / **Plane L 再駆動が Plane G と同一 checksum** |
| **L3** cross-platform | **PASS** | 本機 WSL に project venv 不在ゆえ直接実測不可 → **Linux CI (glibc) で committed real bundle を verify**。run `34002303463` job `101403225525` で `test_m13_live_loop_capture.py` **24/24 pass・skip 0** = 追加 2 test が skip されず実行されて緑 |

annotation (**非 gate**・side file・Done 集合外・`verdict=None`):

- `wiring_reachability.json` — 32/32 corr-id が 5 seam 全到達 / `no_double_send=True` /
  `target_agent_mismatch_count=0` / envelope kind 各 32
- `two_phase_firing_annotation.json` — `fired=True` / eligible 29 / 符号反転 29 / `fail_mode=None`

**settle しなかった (firing した)**。ただし **tick 0-2 の 3 tick は λ=0 で非 eligible**
(λ を earn するまでの settle 区間) で、eligible は tick 3 以降の 29。rehearsal では非 eligible が
tick 0 の 1 つだけだったので、**real backend の方が settle が 2 tick 長い** — これは配線の失敗ではなく、
real LLM の行動列が scripted rehearsal と異なるという当然の帰結。

なお事前登録は「settle は正当な結果・発火するまで再走しない」と定めており、本 run は
その規律の下で 1 回だけ走らせた結果がたまたま firing だった、という順序である
(firing を得るための再走・パラメータ探索はしていない)。

## L3 が測っている範囲 (過剰主張しない)

Windows (UCRT) で bake した bundle の **committed bytes** が Linux (glibc) 上の replay で
同一 checksum / 同一 SHA になること。**Linux 上で capture を再 bake したのではない**
(CI に real Ollama が無いので原理的に不可)。6 桁量子化が libm drift を吸収するという既存の主張
(memory `feedback_golden_crossplatform_float_drift`) の、real bundle での確認である。

## 変更点

- `experiments/20260904-m13-live-loop-live/artifacts/` — **sealed real bundle を新規 commit**
  (6 artifact + 2 side annotation)
- `experiments/20260904-m13-live-loop-live/env.md` / `notes.md` — TBD 欄を実測値で埋め、結果節を追加
- `.steering/20260904-m13-live-loop-i7-real-run/tasklist.md` / `blockers.md` — spend gate を close、
  B-2 解消 / B-3 を「Linux CI 経由」に経路変更して解消
- `tests/test_integration/test_m13_live_loop_capture.py` — **L3 用に 2 test 追加** (CI で実行済・skip されていないことを確認)
  (`test_committed_sealed_real_bundle_verifies` / `test_committed_sealed_real_bundle_is_a_real_capture`)。
  どちらも `artifacts/` 不在の checkout では **skip** するので、bundle 未生成でも CI は壊れない

**無改変**: `scripts/m13_live_loop_capture.py` / `src/**` (organ / live_loop / inbound / gateway /
production / 凍結 `evidence/**`) / 既存 golden / `ControlEnvelope`。

## 追試

```powershell
.\experiments\20260904-m13-live-loop-live\repro.ps1 -Real   # Ollama-free、接続ゼロ・spend ゼロ
```

## 残 (本 PR の scope 外)

- 実 Godot クライアント + real qwen3 の end-to-end live セッション (MacBook、godot env-gate)
- organ 側 strict replay mode (`blockers.md` B-1、superseding ADR が必要)
- PR #88 (Godot traversal rendering、draft) の disposition

Refs: `.steering/20260904-m13-live-loop-i7-real-run/`

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01PVkyWmYiyNEHdRCu8rzUrZ
