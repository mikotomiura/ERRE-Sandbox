# Design — M8 Baseline Quality Metric (L6 D1 残り半分)

> 本ドキュメントは Plan mode で承認された設計の転記。軸決定と "why" は
> `decisions.md` を参照。scope と受け入れ条件は `requirement.md`、作業手順は
> `tasklist.md` を参照。

## 目的

L6 ADR D1 (`defer-and-measure`) の M8 precondition 後半。M9 LoRA 導入後に
A1-b / A1-c / A1-e の優劣を比較するための *定量的 reference point* を
M8 時点で固定する。baseline なしでは M9 の効果測定が不能。

## Phase 1 で判明した前提

1. **`RelationshipBond.affinity` は死に体フィールド** — `schemas.py:422` に
   `affinity: _Signed = 0.0` はあるが、`src/` 全域に mutation logic がゼロ。
   → metric 2 「affinity 推移」はこの spike ではブロッカー。
2. **`bias.fired` は debug log のみで structured sink なし** — `cognition/
   cycle.py:686-692` は `logger.debug(...)`。metric 3 の入力取得には sink
   追加が必要。
3. **`_stream_probe_m6.py` は standalone** — `.steering/20260421-m6-observatory/
   evidence/` 配下。metric 集計は downstream (post-hoc on persisted data)
   が自然。
4. **`iter_dialog_turns()` は fidelity metric の入力として十分** (PR #88)。
5. **CSDG trigram 閾値 (0.30 / 0.50) は single-author 前提** — ERRE の
   multi-persona dialog には「自己反復」と「persona 間 echo」の 2 次元が
   必要。

## 採用設計 (v2)

### アーキテクチャ図

```
_apply_zone_bias (cognition/cycle.py)
    └── bias_sink callable (optional, default None)
            │
            ▼
    _persist_bias_event closure (bootstrap.py)
            │ (agent_id → persona_id 解決)
            ▼
    MemoryStore.add_bias_event_sync (memory/store.py)
            │
            ▼
    sqlite: bias_events テーブル

erre-sandbox baseline-metrics --run-db <path> --out <json>  (post-hoc)
    └── evidence.metrics.aggregate(db_path)
            ├── iter_dialog_turns() → compute_self_repetition_rate
            ├── iter_dialog_turns() → compute_cross_persona_echo_rate
            └── iter_bias_events() → compute_bias_fired_rate
```

### metric 定義

#### metric 1a — `fidelity.self_repetition_rate`

- 入力: `iter_dialog_turns()` の全 row、`speaker_persona_id` でグループ化
- 計算: 各 persona について、自身の直近 N=5 turn 内の任意 2 turn 間の
  trigram 重複率を平均
- 単位: `[0.0, 1.0]` の float。LOW ほど persona の発話が自己反復していない
- baseline 期待: CSDG echo_threshold=0.30 前後。M8 MVP では参考値

#### metric 1b — `fidelity.cross_persona_echo_rate`

- 入力: `iter_dialog_turns()` の全 row
- 計算: `speaker_persona_id` が異なる任意の turn ペア間の trigram 重複率
  を平均 (window: 同 dialog_id 内か直近 10 turn)
- 単位: `[0.0, 1.0]`。LOW ほど persona 同士が言語的に区別できている
- baseline 期待: CSDG reject_threshold=0.50 より遙かに低い値のはず

#### metric 2 — `bias_fired_rate`

- 入力: `iter_bias_events()` の全 row、`persona_id` と `bias_p` でグループ化
- 計算: `events_for_persona / (run_duration_s * num_agents_of_persona *
  bias_p)` — 発火の「期待値に対する実測比」
- 単位: dimensionless、1.0 が「bias_p が指示する確率どおりに発火」
- baseline 期待: 1.0 近辺 (cognition の zone 選択が preferred に十分反した
  ケースで bias 確率どおり発火していることを検証)

#### deferred — `affinity_trajectory`

- 本 spike では実装せず、baseline JSON に `null` を field として保持
- L6 D1 residual として `m8-affinity-dynamics` を別 spike 起票

### 変更ファイル (詳細は Post-Plan フロー参照)

| Path | 変更 |
|---|---|
| `src/erre_sandbox/memory/store.py` | bias_events table + add_bias_event_sync/async + iter_bias_events |
| `src/erre_sandbox/cognition/cycle.py` | BiasFiredEvent dataclass + bias_sink 引数 |
| `src/erre_sandbox/bootstrap.py` | _persist_bias_event closure + wire-up |
| `src/erre_sandbox/__main__.py` | _SUBCOMMANDS に baseline-metrics 追加 |
| `src/erre_sandbox/cli/baseline_metrics.py` | 新規 (register/run) |
| `src/erre_sandbox/evidence/__init__.py` | 新規 (package marker) |
| `src/erre_sandbox/evidence/metrics.py` | 新規 (pure functions + aggregate) |
| `tests/test_evidence/test_metrics.py` | 新規 |
| `tests/test_memory/test_store.py` | bias_events テスト追加 |
| `tests/test_cognition/test_cycle.py` | sink call テスト追加 |
| `tests/test_cli_baseline_metrics.py` | 新規 |

### SCHEMA_VERSION

**変更なし** (`0.5.0-m8` を維持)。wire 形式は無変更、sqlite schema 追加のみ
(PR #88 と同方針)。

## 検証手順

### Mac 完走分

- `uv run pytest tests/test_evidence/` → 5-8 本 PASS
- `uv run pytest tests/test_memory/test_store.py -k bias_event` → 3-4 本
- `uv run pytest tests/test_cli_baseline_metrics.py` → CLI round-trip
- `uv run pytest tests/test_cognition/test_cycle.py -k bias_sink` → 1-2 本
- 全体 regression なし (現 797 + 新規 ≈12-16)

### 契約整合性

- `git diff --stat main...HEAD` が src / tests / .steering のみ
- `grep 'SCHEMA_VERSION' src/erre_sandbox/schemas.py` → `0.5.0-m8` 維持
- `grep -rn "affinity" src/` が `schemas.py:422` のみ

### G-GEAR acceptance (本 PR 後、別 session)

- live run 60-90s × 3-5 本 (bias_p=0.1、personas=kant,rikyu,nietzsche)
- `erre-sandbox export-log` + `erre-sandbox baseline-metrics` で JSON 生成
- 平均 / 分散 / 代表値を `baseline.md` に記録、M9 比較の reference 固定

## Out of Scope

- affinity mutation logic の設計・実装 (別 spike `m8-affinity-dynamics`)
- ReasoningTraceMsg / ReflectionEventMsg の永続化
- session_id / Q&A epoch 境界での per-phase metric
- Parquet export (M9 LoRA task で追加)
- Godot 側 metric 可視化
- `BiasFiredMsg` の wire-level 公開 (現時点は process 内 sink で足る)

## 設計判断の履歴

- Plan mode で /reimagine 5 軸 (A: metric 本数 / B: bias capture / C:
  trigram 閾値 / D: 集計 timing / E: sink 注入点) を展開し、各 v1 vs v2
  (+v3) で比較、全軸で v2 採用
- 採用理由の詳細は `decisions.md`
