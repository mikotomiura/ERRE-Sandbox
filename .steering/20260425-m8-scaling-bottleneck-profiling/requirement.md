# M8 Spike — Scaling Bottleneck Profiling

## 背景

L6 ADR D2 (`observability-triggered`) の M8 precondition。現状 agent scaling は
`integration/dialog.py:113` の "M4 targets N≤3" で止まっており、4 体目追加の
科学的トリガーが未定義。量先行 (N を増やして困るか見る) は research 目的
(異質認知習慣の相互作用観察) から外れる。N=3 の live data から 3 metric 候補
(dialog pair saturation / observer fatigue / zone 滞留分布の flat 化) を
計測し、scaling トリガー閾値を定量的に提案する。

## ゴール

- 3 metric の定量ロジックが `src/erre_sandbox/evidence/scaling_metrics.py` に実装
- N=3 の live run から 3 metric の実測値 (平均 / 分散 / 極値) を取得
- 閾値案を 3 本 decisions.md に記録 (例: "saturation > 0.85 で +1 検討")
- 閾値超過時に `scaling_alert.log` へ追記する観察機構の雛形

## スコープ

### 含むもの
- 3 metric の定義確定と script 実装
- N=3 の live run 3-5 本を実施、metric の確率分布を推定
- 閾値案を decisions.md に 3 本記録 (各 metric に 1 本)
- `scaling_alert.log` 雛形 (実装は最小、判定コードのみ)

### 含まないもの
- 4th persona の選定 / 追加実装 (M9 or later)
- `dialog.py:113` の N 依存ハードコード解消 (M9 or later の別 task)
- Dialog scheduler の tier / cooldown 再設計 (M9 以降)

## 受け入れ条件

- [ ] 3 metric の定義が decisions.md に reproduceable 形式で記録
- [ ] `scaling_metrics.py` が live log から 3 metric を計算可能
- [ ] N=3 live run 3-5 本で metric 値が得られ、平均と分散が profile.md に記録
- [ ] 各 metric の閾値案 1 本を decisions.md に記録 (根拠つき)
- [ ] 閾値判定コードが `scaling_alert.log` に 1 行追記するユニット動作を確認

## 関連ドキュメント

- 親 ADR: `.steering/20260424-steering-scaling-lora/decisions.md` D2
- 上流 spike: `.steering/20260425-m8-episodic-log-pipeline/` (log 入力)
- 関連 Skill: `architecture-rules` (dialog.py の N 依存は本 spike で解消しない、
  判定層の追加のみ)、`llm-inference` (並列予算 `OLLAMA_NUM_PARALLEL=4`)
- 参考: `integration/dialog.py:292-305` の `_iter_colocated_pairs` (C(N,2) 爆発源)

## メモ: D3 との交叉

D2 の A2-f 選択肢「user を 4 体目扱い」は D3 と交叉している。本 spike の閾値が
autonomous run に対する判定だと明示し、Q&A epoch (D3 採用 A3-d) 中の user 発話は
metric カウントから **除外** する設計を decisions.md で明示する。
