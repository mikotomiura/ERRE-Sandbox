# Tasklist — M8 Baseline Quality Metric

> L6 D1 precondition、~1d 見込 (半日 定義+script、半日 live run)。
> 開始前に **Plan mode + /reimagine 必須** (metric 定義に複数案ありうる、
> 特に "fidelity" は主観/客観の切り分けが必要)。

## 準備
- [ ] L6 ADR D1 を Read
- [ ] `llm-inference` / `persona-erre` / `test-standards` Skill を Read
- [ ] 既存 `evidence/_stream_probe_m6.py` と `evidence/*.summary.json` を調査
- [ ] 上流 spike `m8-episodic-log-pipeline` の merge 状況を確認

## metric 定義 (decisions.md に記録)
- [ ] **対話 fidelity**: persona 間 trigram overlap / persona-specific keyword
      presence / reply-on-topic rate のいずれか (CSDG Layer 2 参考)
- [ ] **affinity 推移**: AgentState.relationships から agent-pair affinity の
      時系列勾配、run 平均と分散
- [ ] **`bias.fired` 頻度**: 3 agent × run 時間 × bias_p で正規化した発火回数

## 実装
- [ ] `src/erre_sandbox/evidence/baseline_metrics.py` を追加
      - input: episodic log export (Parquet or sqlite query)
      - output: `evidence/<run>.baseline_metrics.json`
      - 3 metric それぞれの計算関数を分離
- [ ] `_stream_probe_m6.py` の run 終了 hook に metric 集計を追加
- [ ] fixture-based unit test (test_baseline_metrics.py)

## テスト (MacBook で完走可)
- [ ] 単体: 3 metric 関数が固定 fixture で期待値を返す
- [ ] 単体: metric JSON schema が安定 (version bump せずに読める)
- [ ] 統合: sample log から metric JSON が生成される e2e

## live run (G-GEAR 必須)
- [ ] G-GEAR で 60-90s baseline run × 3-5 本 (bias_p=0.1 固定)
- [ ] 3 metric の JSON を集計、`baseline.md` に table 化
- [ ] 平均 / 分散 / 代表値を記録、M9 比較の reference として固定

## レビュー
- [ ] `code-reviewer` で metric 関数と JSON schema をレビュー
- [ ] `security-checker` (PII が metric に混入しないか、軽く)

## ドキュメント
- [ ] `docs/architecture.md` の evidence layer に baseline metric を追記
- [ ] `docs/glossary.md` に「baseline quality metric」を追加

## 完了処理
- [ ] `design.md` 最終化、`decisions.md` に metric 定義を固定
- [ ] commit → PR (`feat(evidence): M8 baseline quality metric`)
- [ ] merge 後、L6 D1 を「baseline 固定済、M9 比較準備完了」に更新
