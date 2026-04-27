# M9 LoRA pre-plan — 成長機構と適用 gate の設計

## 背景

live 検証 issue D1+D2:
- D1 (04/22) 「具体的にどのようにして agent が成長していくのかなど。
  現在は全くわからない。xAI 化するのも良いのかも」
- D2 (04/22) 「全体のプランを練る (どれぐらいデータを集めたら LoRA を
  適用するか、agent を増やしていくか、対話できるようにするか否か)」

M7-α〜ζ で関係性ループ + persona divergence + live observation tooling が
揃った。M9 で persona ごとの LoRA fine-tuning に進むが、その前に「いつ・
何を・どうやって」LoRA を適用するかの意思決定文書が独立して存在しない。
MASTER-PLAN §11 R12 は roadmap-level で、data threshold / go-no-go /
agent expansion の具体基準が欠落。

## ゴール

M9 着手前に decisions.md に以下を記録:
- LoRA 適用 trigger 閾値 (episodic_log row 数 / dialog_turn 数 /
  baseline_metric)
- persona 別 base model + adapter rank + dataset 構成
- agent 数拡張 (3 → N) 判断基準
- player ↔ agent dialog 開放判断基準 (M11 整合)
- LoRA degradation rollback シナリオ

## スコープ

### 含むもの
- M8 episodic_log / session_phase / baseline_metric 利用前提の data
  pipeline 設計
- δ run-02 / ζ run-01-zeta 数値 baseline 起点の閾値導出
- 成長 UI / xAI 化要件 (D1 後半) の洗い出し

### 含まないもの
- 実 LoRA training 実行 (M9 本体)
- 新 model architecture 採用

## 受け入れ条件

- [ ] decisions.md に 5 意思決定 enumerated + 根拠付き
- [ ] data threshold が ζ run-01-zeta 数値で照合可能
- [ ] /reimagine v1+v2 並列で hybrid 採用記録
- [ ] tasklist.md に M9 着手の prerequisites 列挙

## 関連ドキュメント

- `.steering/20260418-implementation-plan/MASTER-PLAN.md` §11 R12
- `.steering/20260426-m7-slice-zeta-live-resonance/run-01-zeta/observation.md`
- `.steering/20260426-m7-slice-zeta-live-resonance/decisions.md` D2
