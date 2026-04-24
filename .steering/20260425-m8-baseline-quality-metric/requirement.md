# M8 Spike — Baseline Quality Metric

## 背景

L6 ADR D1 (`defer-and-measure`) の M8 precondition。LoRA 導入後の比較基準点として、
prompt-only での会話品質を定量化する baseline を M8 時点で固定する必要がある。
baseline なしでは M9 で A1-b (全 persona LoRA) / A1-c (hybrid) / A1-e (RAG) の
優劣を事後判定できない。metric は L6 D1 根拠節が示唆した 3 本
(対話 fidelity / affinity 推移 / `bias.fired` 頻度) を採用。

## ゴール

- 3 metric の定義が定量可能な形で確定 (計算式 + 入力 event + 出力単位)
- 1 run 終了時に `evidence/<run>.baseline_metrics.json` が自動生成される
- M8 baseline run の 3-5 本を実施し、`baseline.md` に平均 / 分散 / 代表値を記録
- M9 で比較 run を流した時、同フォーマットで diff 可能

## スコープ

### 含むもの
- 3 metric の定義確定 (decisions.md に記録)
- 集計 script (`src/erre_sandbox/evidence/baseline_metrics.py` 等)
- 既存 `evidence/_stream_probe_m6.py` への hook 追加 (run 終了時に metric 算出)
- baseline run 3-5 本 (G-GEAR 必須、MacBook では live 不可)
- `.steering/20260425-m8-baseline-quality-metric/baseline.md` への結果記録

### 含まないもの
- LoRA 訓練・比較 run (M9 スコープ)
- 新規 metric 追加 (MoS / perplexity 等)、M8 は 3 metric に絞る
- Godot side の metric 可視化 (observability 別 spike)

## 受け入れ条件

- [ ] 3 metric の数式が decisions.md に記録、reproduceable
- [ ] 1 baseline run 終了後に `evidence/<run>.baseline_metrics.json` が生成される
- [ ] n=3-5 baseline run の「平均 / 分散 / 代表値」が `baseline.md` table で記録
- [ ] baseline run 間での metric の揺らぎが decisions.md の期待レンジ内
- [ ] M8 episodic log pipeline の export 出力と整合 (同 run、同 turn count)

## 関連ドキュメント

- 親 ADR: `.steering/20260424-steering-scaling-lora/decisions.md` D1
- 上流 spike: `.steering/20260425-m8-episodic-log-pipeline/` (log が baseline の入力)
- 関連 Skill: `llm-inference` (run 環境)、`test-standards` (fixture)、
  `persona-erre` (affinity 定義)

## メモ: live run 必須

baseline 測定は G-GEAR (Ubuntu + Ollama) 必須で MacBook 単独では完走不可。
Mac での作業は metric 定義確定・script 実装・fixture ベースの unit test まで。
G-GEAR セッション時に live run を実施、結果を本 dir に追記する 2 段構成。
