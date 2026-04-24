# Tasklist — M8 Scaling Bottleneck Profiling

> L6 D2 precondition、~1d 見込 (半日 metric+script、半日 live run + 閾値確定)。
> 開始前に **Plan mode + /reimagine 必須** ("observer fatigue" の操作定義は
> 複数案ありうる、主観 proxy / 客観 proxy の切り分けが判断どころ)。

## 準備
- [ ] L6 ADR D2 を Read
- [ ] `architecture-rules` / `llm-inference` Skill を Read
- [ ] `integration/dialog.py:292-305` の pair enumeration を調査
- [ ] `world/tick.py` の並列 tick 実装を調査 (asyncio.gather 位置)
- [ ] 上流 spike `m8-episodic-log-pipeline` の merge 状況を確認

## metric 定義 (decisions.md に記録)
- [ ] **dialog pair saturation**: 同 zone の agent 全対が連続 N turn 同じ pair で
      閉じている割合 (飽和度 0-1)
- [ ] **observer fatigue**: `reasoning_trace` の salience fluctuation / zone
      entropy / speech rate 急降下を組み合わせた複合 proxy
- [ ] **zone 滞留分布 flat 化**: 5 zone の滞留時間 Gini 係数、低いほど flat (bias
      発火の意味喪失)

## 実装
- [ ] `src/erre_sandbox/evidence/scaling_metrics.py` を追加
      - 3 metric 関数を分離、各 input は episodic log export
      - `evidence/<run>.scaling_metrics.json` を run 終了時に出力
- [ ] 閾値判定コード (`scaling_alert.py`): 閾値超過時に `scaling_alert.log` へ追記
- [ ] fixture-based unit test (test_scaling_metrics.py)

## テスト (MacBook で完走可)
- [ ] 単体: 3 metric 関数が固定 fixture で期待値を返す
- [ ] 単体: 閾値判定の境界条件 (=閾値 / <閾値 / >閾値)
- [ ] 統合: sample log から scaling_metrics.json が生成される e2e

## live run (G-GEAR 必須)
- [ ] G-GEAR で N=3 の 60-90s run × 3-5 本 (bias_p=0.1、L6 D1 baseline と揃える)
- [ ] 3 metric の確率分布を profile.md に記録 (histogram 1 枚 + quantile table)
- [ ] 各 metric の暫定閾値を profile から提案 (例: 90%-ile を warning、95%-ile を
      scaling trigger)

## レビュー
- [ ] `code-reviewer` で metric 関数と閾値判定をレビュー
- [ ] `impact-analyzer` で scaling_alert の発火先 (将来の 4th persona spike) を整理

## ドキュメント
- [ ] `docs/architecture.md` の observability layer に scaling metric を追記
- [ ] `docs/glossary.md` に「observability-triggered scaling」を追加 (本 spike が源)

## 完了処理
- [ ] `design.md` 最終化、`decisions.md` に 3 metric 定義 + 閾値案を固定
- [ ] commit → PR (`feat(evidence): M8 scaling bottleneck profiling`)
- [ ] merge 後、L6 D2 status を「閾値案確定、M9 以降のトリガー判定に使用可」に更新
