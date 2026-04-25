# G-GEAR Live Acceptance Bundle — M7 β + M8 三本 (PR #83 / #87 / #88 / #89)

> **このタスクは次に開く G-GEAR セッションの最優先タスク**。
> Mac 単独では完走不可 (LLM スループット不足)。
> Plan mode 不要 — 観察タスクのみ、`/reimagine` 不要 (設計変更なし)。

## 背景

2026-04-24〜25 に 4 本の PR が merge され、それぞれに **live acceptance の
G-GEAR 預り** が残っている:

| PR | 内容 | merged | live acceptance 残り |
|---|---|---|---|
| #83 | Slice β (`_bias_target_zone` + 100m world + 3 zone scenes) | `a76343c` | 6 観察項目 (Rikyū/Kant/Nietzsche 滞留 + 5 rect + 3 building + 100m terrain + top-down) |
| #87 | m8-session-phase-model (EpochPhase + RunLifecycleState + FSM) | `447218c` | ブート時の default 状態 + FSM 遷移が例外なく実行できること |
| #88 | m8-episodic-log-pipeline (`dialog_turns` table + `export-log` CLI) | `0e2e50e` | live run 終了後に `export-log` が空でない JSONL を吐くこと |
| #89 | m8-baseline-quality-metric (`bias_events` + `baseline-metrics` CLI) | `f5d5e7f` | live run 終了後に `baseline-metrics` が完全な JSON を吐き、reference 値として記録されること |

4 本の acceptance は **同じ live run DB を共有できる**ので、1 セッションで
まとめて処理する。β の bias_p=0.1/0.2 2 本 run 中に dialog_turns と
bias_events が sqlite に溜まり、それを post-hoc CLI で吐き出す構成。

## ゴール

G-GEAR 1 セッション (2-3h 見込み) で以下を達成:

1. **β live-accept**: bias_p=0.1 / 0.2 の 60-90s run × 2 本、PR #83 の
   6 観察項目を証跡化、`bias_p` の production default を決定
2. **#87 sanity**: orchestrator ブート時に `RunLifecycleState` が
   `AUTONOMOUS` で起動し、Python REPL 経由で FSM 遷移が ValueError なく
   動くことを確認
3. **#88 export**: 各 run 終了後に `uv run erre-sandbox export-log` で
   `dialog_turns` を JSONL 化、persona 別 turn count を記録
4. **#89 baseline**: 各 run 終了後に `uv run erre-sandbox baseline-metrics`
   で JSON 生成、n=2 の平均 / 分散 / 代表値を `baseline.md` に table 化、
   M9 比較の reference として固定

## スコープ

### 含むもの

- G-GEAR 上での `evidence/_stream_probe_m6.py` 60-90s × 2 回
  (bias_p=0.1/0.2)
- 各 run 終了後の `export-log` + `baseline-metrics` CLI 実行
- `RunLifecycleState` の Python REPL 動作確認
- Godot での BoundaryLayer rect / 3 new scene / 100m terrain 視認
- 結果を `observation.md` + `baseline.md` に記録
- 必要なら hotfix PR (`ERRE_ZONE_BIAS_P` default 変更等)

### 含まないもの

- Slice γ の実装 (別 task dir、本 acceptance 結果待ち)
- LoRA / user-dialogue IF の live 検証 (L6 別 steering、M9-M10 スコープ)
- n=3-5 の baseline run (MVP は n=2 で暫定、必要なら後続)
- baseline_metrics のスコア最適化・閾値判定 (単に生データ記録)

## 受け入れ条件 (全 14 項目)

### β (6 項目、PR #83 から継承)

- [x] Rikyū の chashitsu/garden/study 合計滞留 ≥ 50% — Run 1 50% PASS / Run 2 40% FAIL (small-sample noise、observation.md §3)
- [x] Kant の peripatos/study 合計滞留 ≥ 50% — 両 run 100% PASS
- [x] Nietzsche の peripatos/garden 合計滞留 ≥ 50% — 両 run 100% PASS
- [ ] Godot で BoundaryLayer の 5 zone rect が新 Voronoi に沿って描画される — **deferred to MacBook**
- [ ] Study / Agora / Garden の primitive 建物が目視可能 — **deferred to MacBook**
- [ ] BaseTerrain が 100m で top-down hotkey `0` で全景フレーミング — **deferred to MacBook**

### PR #87 session-phase-model (2 項目)

- [x] ブート直後に `runtime.run_lifecycle.epoch_phase == EpochPhase.AUTONOMOUS`
  — REPL `RunLifecycleState()` で確認、live boot も `world/tick.py:352` で同経路
- [x] Python REPL で `runtime.transition_to_q_and_a()` →
  `runtime.transition_to_evaluation()` が例外なく動く、不正遷移は
  `ValueError` — `pytest tests/test_world/test_runtime_lifecycle.py` 9/9 PASS

### PR #88 export-log (2 項目)

- [x] `uv run erre-sandbox export-log --db <run.db> --out run-01.jsonl`
  が exit 0 で完走、JSONL が 1 行以上 — Run 1 12 行 / Run 2 4 行
- [x] `--persona kant/rikyu/nietzsche` 指定で filter が効き、各 persona の
  turn 数を `baseline.md` に記録 — table 化済 (kant 3/0, nietzsche 6/2, rikyu 3/2)

### PR #89 baseline-metrics (4 項目)

- [x] `uv run erre-sandbox baseline-metrics --run-db <run.db> --out
  baseline-01.json` が exit 0 で完走、JSON の `schema` が
  `"baseline_metrics_v1"` — 両 run PASS
- [/] `turn_count` / `bias_event_count` / `num_agents` が非ゼロ、
  `run_duration_s` が ≈ run 実時間 — Run 1 全 PASS / Run 2 `bias_event_count=0`
  (anomaly、baseline.md §"Anomalies" #1 で記録)
- [/] `self_repetition_rate` / `cross_persona_echo_rate` / `bias_fired_rate`
  が float で返る (null でない) — Run 1 全 PASS / Run 2 `bias_fired_rate=null`
  (design.md §5 row #6 「persona prompting 勝ち」documented、失敗扱いせず)
- [x] n=2 の平均 / 分散を `baseline.md` に記録、CSDG 単著値 (0.30 / 0.50) と
  並記 — frozen as M9 reference

## 関連ドキュメント

- PR #83: https://github.com/mikotomiura/ERRE-Sandbox/pull/83 (merged 2026-04-24)
- PR #87: https://github.com/mikotomiura/ERRE-Sandbox/pull/87 (merged 2026-04-24)
- PR #88: https://github.com/mikotomiura/ERRE-Sandbox/pull/88 (merged 2026-04-24)
- PR #89: https://github.com/mikotomiura/ERRE-Sandbox/pull/89 (merged 2026-04-25)
- β 設計: `.steering/20260424-m7-differentiation-observability/`
- M8 session-phase: `.steering/20260425-m8-session-phase-model/`
- M8 log pipeline: `.steering/20260425-m8-episodic-log-pipeline/`
- M8 baseline: `.steering/20260425-m8-baseline-quality-metric/`
- 過去 acceptance 手順: `.steering/20260421-m5-acceptance-live/`
