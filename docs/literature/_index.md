# 文献カード インデックス

`/literature-review` が生成する落合フォーマットのカード一覧。新トピックごとに追記される。

| 日付 | トピック | ファイル | カード数 | 「やり残し」要約 |
|---|---|---|---|---|
| 2026-07-02 | divergent-thinking-benchmarks | `20260702-divergent-thinking-benchmarks.md` | 5 | SemDis=独立外部意味空間への距離 (self-anchor 循環を要求しない設計) / DAT・Wu et al.=新規性を離散台の集合比較でなく連続値 (pairwise距離・汎化距離) で定義すれば ES-2 の飽和問題を回避しうる / Hills et al.=移動↔記憶検索の同型性への独立理論的裏付け (research-positioning §3 追記候補) / Bartoli et al.=fluency 固定+特定チャネル分離という control 設計は ERRE (ES-3/D0) と独立収束した house pattern |
| 2026-07-13 | aha-insight-neuroscience | `20260713-aha-insight-neuroscience.md` | 12 | salience switch [12][13] + DMN-ECN dynamics [18][19] = **construction ターゲット** (λ↔二相 bias knob、measurement 非要) / aSTG marker [14][15]・reward [16][17]・EEG marker [20][21] = **measurement 領域** (凍結ライン内、離散化/scorer 化は第2リンク circularity 再来) / Sandkühler [20]=restructuring・suddenness・confidence の3軸は生物学的裏付けあり **だが warmth は無し (非対称)** / Organisciak [22]=LLM-judge は response *originality* を教師あり検証 (aha-moment 検出とは別物) / DeepSeek-R1 [23] "aha moment"=observational 命名で形式的 scorer でない、Yang et al.[24] epoch-0 反例が素朴形式化の失敗を実証 → **壁2 (scorer 先行解決) は survey 段で未解決、Phase 2 fork を construction 寄りに制約** |
| 2026-07-17 | jlens-jacobian-lens | `20260717-jlens-jacobian-lens.md` | 2 | J-lens [25] = 平均 Jacobian `E[∂h_final/∂h_ℓ]` で中間 activation → 将来 token verbalize ポテンシャルを可視化、J-space (sparse subframe・総 variance <10%・有意味な J-lens ベクトル ≤25 本) を global workspace と主張 **だが Claude 4.5/4.6 での検証で qwen3 未検証・単一 token 限定・機序不明の自認限界** / repo [26] = **Apache-2.0**・白箱 PyTorch+transformers **backward pass 必須**・完全ローカル・**"reference implementation, not maintained"** → **本質は measurement-grade 内部読み出し**。二相捕捉 regime (§(b) は think=True *text trace* の質的 existence 用) への fold は原則5 (neural ROI→内部軌跡の比喩写像禁止) に抵触 → fork ADR で guard-first 判定 (推奨=B REJECT/DEFER) |

> 各カードは `docs/literature/<YYYYMMDD>-<topic-slug>.md`。
> 出典は `docs/references.md` に append-only で登録される。
> カードの 6 項目フォーマットは `.claude/skills/literature-card/` が強制する。
