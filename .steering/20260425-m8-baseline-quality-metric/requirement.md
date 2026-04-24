# M8 Spike — Baseline Quality Metric (v2 scope)

## 背景

L6 ADR D1 (`defer-and-measure`) の M8 precondition。LoRA 導入後の比較基準
点として、prompt-only での会話品質を定量化する baseline を M8 時点で固定
する必要がある。baseline なしでは M9 で A1-b (全 persona LoRA) / A1-c
(hybrid) / A1-e (RAG) の優劣を事後判定できない。

Phase 1 探索で **`RelationshipBond.affinity` に mutation logic がゼロ**
であることが判明したため、metric 本数を 3 → 2 に縮小し、affinity は別
spike (`m8-affinity-dynamics`、L6 D1 residual) に defer する (decisions.md
D1 参照)。

## ゴール (v2)

- 2 metric の定義が定量可能な形で確定 (計算式 + 入力 event + 出力単位)
  - `fidelity.self_repetition_rate` (persona 内自己反復 trigram 率)
  - `fidelity.cross_persona_echo_rate` (persona 間 echo trigram 率)
  - `bias_fired_rate` (bias_p 正規化発火比)
- post-hoc CLI `erre-sandbox baseline-metrics --run-db <path> --out <json>`
  が実装され、fixture DB で期待値 JSON を返す
- M8 baseline run の 3-5 本を G-GEAR で実施 (別セッション)、`baseline.md`
  に平均 / 分散 / 代表値を記録
- M9 で比較 run を流した時、同フォーマットで diff 可能

## スコープ

### 含むもの (v2)

- 2 metric の定義確定 (`decisions.md` D1-D5 に記録)
- `bias_events` sqlite table + `MemoryStore` の 3 method
- `cognition/cycle.py::_apply_zone_bias` に optional `bias_sink` 引数追加
- `bootstrap.py` で `_persist_bias_event` closure を wire-up
- `src/erre_sandbox/evidence/metrics.py` (pure 関数集) + `aggregate()`
- `src/erre_sandbox/cli/baseline_metrics.py` + `__main__.py` 登録
- fixture ベースの unit test (metric / store / cognition / CLI)
- G-GEAR acceptance は別セッション (baseline run 3-5 本 + `baseline.md` 記録)

### 含まないもの (v1 → v2 で外した項目)

- **affinity metric の実装** — defer to `m8-affinity-dynamics` (L6 D1 residual)
- 新規 metric 追加 (MoS / perplexity 等)
- Godot side の metric 可視化 (observability 別 spike)
- Parquet export (M9 LoRA task で必要になってから)
- `BiasFiredMsg` の wire-level 公開 (SCHEMA_VERSION bump を避ける)
- session_id / Q&A epoch 境界の per-phase metric

## 受け入れ条件

- [ ] 2 metric の数式が `decisions.md` に記録、再現可能
- [ ] affinity defer の根拠が `decisions.md` D1 に明示
- [ ] `uv run erre-sandbox baseline-metrics --help` で subcommand が表示
- [ ] fixture DB (3 dialog turn + 2 bias event) に対し期待値 JSON が出力
- [ ] 全テスト (現 ~797 + 新規 ≈12-16) が PASS
- [ ] `SCHEMA_VERSION` は `0.5.0-m8` のまま (wire 無変更の証跡)
- [ ] `git diff --stat main...HEAD` が src / tests / .steering のみ
- [ ] `grep 'pyarrow\|pandas' pyproject.toml` がゼロ (依存追加なし)

## 関連ドキュメント

- 親 ADR: `.steering/20260424-steering-scaling-lora/decisions.md` D1
- 上流 spike: `.steering/20260425-m8-episodic-log-pipeline/` (iter_dialog_turns 提供)
- 後続 spike (新規起票予定): `m8-affinity-dynamics` (L6 D1 residual)
- 関連 Skill: `llm-inference` (run 環境)、`test-standards` (fixture)、
  `persona-erre` (affinity 定義)
- Plan 原本: `/Users/johnd/.claude/plans/misty-marinating-scone.md`

## メモ: G-GEAR live run 必須 (baseline 固定は別セッション)

baseline 測定は G-GEAR (Ubuntu + Ollama) 必須で MacBook 単独では完走不可。
本 PR の受け入れ条件は Mac で完走可能な実装 + unit test まで。G-GEAR
セッション時に live run を実施、結果を本 dir `baseline.md` に追記する
2 段構成 (PR #87, #88 と同方針)。
