# Design — M8 Scaling Bottleneck Profiling

> Plan mode で承認された hybrid 設計の転記。軸決定と "why" は
> `decisions.md` を、scope と受け入れ条件は `requirement.md` を、
> 作業手順は `tasklist.md` を参照。
>
> Plan agent v1 (counting / σ-based) と v2 (information-theoretic) を
> 独立に走らせ、5 軸比較の上で hybrid (v2-leaning, v1 fallback for
> fatigue) を採用。

## 目的

L6 ADR D2 の M8 precondition: agent scaling を量先行ではなく
metric-first で発火させるための 3 metric を実装し、N=3 live data から
閾値案を確定する。M9 以降の 4th persona 起票は本 spike の閾値判定
出力 (`scaling_alert.log`) に依拠する。

## 採用設計のアーキテクチャ図

```
live run (orchestrator + agents)
   │
   ├── sqlite ``dialog_turns`` table  (M8 #88 の sink)
   │   └── columns: id, dialog_id, tick, turn_index,
   │              speaker_persona_id, addressee_persona_id,
   │              utterance, created_at
   │
   └── journal jsonl (envelope stream from /ws/observe)
       └── ``kind=agent_update`` の top-level entries:
                 agent_state.agent_id, .tick, .position.zone

post-hoc CLI: ``erre-sandbox scaling-metrics --run-db <path> [--journal <jsonl>] [--out <path>]``
   │
   └── evidence.scaling_metrics.aggregate(db_path, journal_path)
          ├── iter_dialog_turns()
          │      ├── compute_pair_information_gain(turns, num_agents)   → bits/turn
          │      └── compute_late_turn_fraction(turns)                   → ratio
          ├── _scan_zone_snapshots(journal_path)
          │      └── compute_zone_kl_from_uniform(snapshots, 5)          → bits
          └── evaluate_thresholds(metrics, thresholds, run_id, log_path)
                 → alerts: list[str] (空なら exit 0、非空なら exit 1)

scaling_alert.log (1 行 TSV per alert)
   timestamp \t metric \t value \t threshold \t run_id
```

## 関数 signature (公開 5 本 + 補助 1 本)

### `compute_pair_information_gain(turns, num_agents, history_k=3) → float | None`

入力: `list[dict]` (各 dict は `speaker_persona_id`, `addressee_persona_id`,
`turn_index`, `dialog_id` を含む)、`num_agents: int`、`history_k: int=3`。

出力: bits/turn で表す mutual information (`H(pair) - H(pair|history_k)`)、
turns が 2 未満なら None。`H` は Laplace smoothing (+0.5/N) +
Miller-Madow correction で計算 (`_compute_entropy_safe`)。

解析的上限: `log2(C(num_agents, 2))`。N=3 で 1.585 bits。

### `compute_late_turn_fraction(turns, budget=6) → float | None`

入力: `list[dict]` (各 dict は `turn_index` を含む)、`budget: int=6`。

出力: `count(turn_index > budget/2) / count(turns)` ∈ [0, 1]。
turns が空なら None。

### `compute_zone_kl_from_uniform(snapshots, n_zones=5) → float | None`

入力: `list[dict]` (各 dict は `agent_id`, `tick`, `zone` を含む、tick
昇順で全 agent 混在可)、`n_zones: int=5`。

出力: bits 単位の `KL(observed || uniform)`。snapshots が 2 未満
(連続区間が形成できない) なら None。

dwell 計算: agent ごとに連続 2 snapshot を pair し、`(tick_{i+1} - tick_i)
× CognitionCycle.DEFAULT_TICK_SECONDS` を `zone_i` (前 snapshot の zone)
の bucket に加算。run 開始/終了の境界 dwell は除外 (連続 pair でない
ため自然に除外される)。

解析的上限: `log2(n_zones)`。5 zone で 2.322 bits。

### `evaluate_thresholds(metrics, thresholds, *, run_id, log_path) → list[str]`

入力:
- `metrics: dict[str, float | None]` ← `aggregate()` 出力 dict の
  `pair_information_gain_bits` / `late_turn_fraction` /
  `zone_kl_from_uniform_bits`
- `thresholds: dict[str, float]` ← デフォルトは
  `{"pair_information_gain_min": 0.30 * log2(C(N,2)),
    "late_turn_fraction_max": 0.60,
    "zone_kl_min": 0.30 * log2(n_zones)}`
- `run_id: str`
- `log_path: Path`

出力: 違反 metric 名の `list[str]`。空なら閾値全クリア。各違反は
`log_path` に 1 行 TSV (timestamp ISO8601, metric_name, value,
threshold, run_id) で append。`metrics[name] is None` の項目は alert
対象から除外 (graceful degradation、D3 採用)。

### `aggregate(run_db_path, journal_path=None) → dict[str, object]`

入力: `Path` 2 つ。`journal_path is None` なら zone metric 計算を
skip → M3 = None で graceful degradation。

出力 (JSON shape `scaling_metrics_v1`):

```json
{
  "schema": "scaling_metrics_v1",
  "run_duration_s": 362.07,
  "num_agents": 3,
  "num_dialog_turns": 12,
  "pair_information_gain_bits": 0.91,
  "pair_information_gain_max_bits": 1.585,
  "late_turn_fraction": 0.42,
  "zone_kl_from_uniform_bits": 0.78,
  "zone_kl_max_bits": 2.322,
  "alerts": []
}
```

`alerts` は `evaluate_thresholds()` の返り値 (デフォルト閾値で評価)。
`zone_kl_*` は `journal_path is None` なら `null`。

### `_compute_entropy_safe(counts) → float`

補助: `counts: list[int]` → Shannon entropy in bits with Laplace
smoothing (+0.5 per slot) and Miller-Madow correction (`+(K-1) /
(2N)` where K = nonzero categories, N = total observations).

## CLI subcommand `scaling-metrics`

```
erre-sandbox scaling-metrics --run-db <path> [--journal <jsonl>] [--out <path>] [--alert-log <path>]
```

- `--run-db` (required): sqlite path. 不存在なら exit 2 + stderr msg
- `--journal` (optional): NDJSON path. 省略 → M3 metric None
- `--out` (default `-`): JSON 出力先。`-` なら stdout
- `--alert-log` (default `var/scaling_alert.log`): TSV log 追記先
- exit code: 0 (alerts 空) / 1 (alerts 非空) / 2 (引数エラー)

`baseline_metrics.py:28-80` の `register/run` 形を踏襲。

## test 戦略

`tests/test_evidence/test_scaling_metrics.py` (~200 行):

### Unit (pure functions)

- `compute_pair_information_gain`:
  - 空入力 → None
  - 1 turn → None
  - 2 turn 同 pair → 0 bits (predictable, no info gain over history)
  - 4 turn 全部別 pair (N=3 で max diversity) → 上限近い値 (`pytest.approx`)
- `compute_late_turn_fraction`:
  - 空入力 → None
  - 全 turn が turn_index ≤ 3 → 0.0
  - 全 turn が turn_index > 3 → 1.0
  - 半々 → 0.5
- `compute_zone_kl_from_uniform`:
  - 空入力 / 1 snapshot → None
  - 全 snapshot 同 zone → 上限 `log2(5)` (`pytest.approx`)
  - 5 zone 等分 → 0.0
  - 偏った 2 zone (60/40) → 既知の手計算値 (fixture コメントに pen+paper)
- `_compute_entropy_safe`:
  - 全 0 counts → 0.0
  - 一様 counts → log2(K) - Miller-Madow correction
  - 単一非ゼロ → 0.0 + correction

### Threshold

- `evaluate_thresholds` 境界 3 通り (=, <, >):
  - M1 == 30% threshold → no alert (条件は `<` なので等号は OK)
  - M1 < 30% threshold → alert 追加
  - M2 == 0.60 → no alert (条件は `>`)
  - M2 > 0.60 → alert 追加
  - M3 None (graceful) → alert に含まれない
- log 追記: 違反 1 件で 1 行 TSV、フォーマット pin

### e2e

- temp sqlite (3 turn) + temp jsonl (5 agent_update) → `aggregate()`
  → JSON shape (`schema=scaling_metrics_v1`)
- `journal_path=None` → `zone_kl_from_uniform_bits=null`,
  `alerts` に M3 含まれない
- 閾値 trigger 1 件で `--alert-log` に行追加、CLI exit code 1

## live calibration 計画

- 既存 δ run-01 (122s, 17 turn) と run-02 (362s, 12 turn) の
  (`var/run-delta.db` + `run-NN.jsonl`) を補助 sample として再分析
  - duration < 180s の run は補助扱い (mean/σ から除外、histogram 併記)
- 新規: G-GEAR で N=3, bias_p=0.1, **60-90s × 3 本** を取る
- 計 5 sample で profile.md (histogram + 5/50/95 percentile)
- 解析的閾値 (M1 0.476, M3 0.696) が live 分布外なら decisions.md
  D4 に追記、% 値を 30→40 等に micro-tune

artifacts dir: `.steering/20260425-m8-scaling-bottleneck-profiling/runs/run-NN/`
- `run-NN.jsonl` / `run-NN.db_summary.json` (m7d 流用) /
- `run-NN.scaling_metrics.json` (本 spike 出力) /
- `orchestrator.log`

## 既存実装の再利用

| 既存 | 再利用先 |
|---|---|
| `src/erre_sandbox/evidence/metrics.py:223-282` (`aggregate()`) | I/O wrapper の thin/pure 分離パターン (`_conn.close()` の sync close 含む) |
| `src/erre_sandbox/evidence/metrics.py:82-116` (`compute_self_repetition_rate`) | per-persona window mean → cross-mean の二段集計テンプレート (M1 で reuse) |
| `src/erre_sandbox/cli/baseline_metrics.py:28-80` | argparse `register()` + `run()` 形、exit code 規約 |
| `.steering/20260426-m7-slice-delta/evidence/_db_summary_m7d.py:36-80` | db+journal 両入力 CLI 先例 (`sqlite3.Row` factory + jsonl iter) |
| `src/erre_sandbox/memory/store.py:860-873` | `iter_dialog_turns(persona, exclude_persona, since, limit)` を `aggregate` 内で全件 iter |

## 関連 ADR

- 親: `.steering/20260424-steering-scaling-lora/decisions.md` D2
  (observability-triggered)
- 上流 spike: `.steering/20260425-m8-episodic-log-pipeline/` (PR #88、
  `dialog_turns` table の sink)
- δ baseline: `.steering/20260426-m7-slice-delta/` (run-01/run-02 の
  data を本 spike の補助 sample として流用)
