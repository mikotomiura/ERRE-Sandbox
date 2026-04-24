# M8 Spike — Episodic Log Pipeline

## 背景

L6 ADR D1 (`defer-and-measure`) の M8 precondition。現状 dialog_turn /
reasoning_trace / reflection_event は sqlite-vec に記録されるが、persona 別 turn
count を取得する公式 query が無く、M9 LoRA 訓練前提の「≥1000 turns/persona」
(MASTER-PLAN L146) を定量的にトラッキングできない。M4-M7 の live log を
完全永続化し、LoRA 訓練用データセットへの export 経路を整備する。

## ゴール

- dialog_turn / reasoning_trace / reflection_event が漏れなく sqlite に記録される
- persona 別 turn count が SQL 1 発で取得でき、M8 baseline run で数値化される
- LoRA 訓練想定フォーマット (JSONL / Parquet) へ export できる CLI が存在する

## スコープ

### 含むもの
- log schema の完全化 (persona_id / session_id / turn_index を全 event に付与)
- persona-scoped count query の SQL サンプル集作成
- `uv run erre-sandbox export-log --format parquet --out <path>` 相当の CLI
- M8 baseline run で現状 turn count を測定、`log-snapshot.md` に記録

### 含まないもの
- LoRA 訓練そのもの (M9 スコープ)
- DPO ペア抽出 / 選別ロジック (別 spike、恐らく M9 early task)
- Parquet 以外の format (Arrow / Avro 等)

## 受け入れ条件

- [ ] dialog_turn / reasoning_trace / reflection_event の schema が全て persona_id を持つ
- [ ] persona 別 turn count が SQL 1 query で取得可能 (`SELECT persona_id, COUNT(*) FROM ...`)
- [ ] export CLI が JSONL と Parquet の両方をサポート
- [ ] M4-M7 live log 総数と export 後のレコード数が一致 (欠損ゼロ)
- [ ] `.steering/20260425-m8-episodic-log-pipeline/log-snapshot.md` に persona 別 count + 日次推移を記録

## 関連ドキュメント

- 親 ADR: `.steering/20260424-steering-scaling-lora/decisions.md` D1
- 関連 Skill: `architecture-rules` (memory/ レイヤー追記)、`test-standards` (sqlite 一時 DB)
- MASTER-PLAN: L146 (M9 LoRA 前提)
- cross-ref 兄弟 spike: `.steering/20260425-m8-baseline-quality-metric/` (本 spike の
  export 出力を消費して baseline metric を算出)

## メモ: spike 粒度は暫定

L6 decisions.md の横断メモ通り、この 4 spike (`m8-episodic-log-pipeline` /
`m8-baseline-quality-metric` / `m8-scaling-bottleneck-profiling` /
`m8-session-phase-model`) を 1 umbrella にするか 2 ペアにするか 4 独立にするかは
**M8 planning セッション最初に決定**。本 scaffold は 4 独立前提で書かれているが、
merge 可能性を残した粒度になっている。
