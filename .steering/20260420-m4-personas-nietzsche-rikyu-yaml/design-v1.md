# 設計 — m4-personas-nietzsche-rikyu-yaml (v1: 初回案、哲学史的トポス駆動)

> **位置付け**: v1 は `/reimagine` 適用のため `design-v1.md` に退避される
> 初回案。意図的に最初に思いついた素直な解釈を書き、後で v2 と比較する。

## 実装アプローチ

`personas/kant.yaml` のテンプレートをそのまま踏襲し、Nietzsche と Rikyu それぞれを
**哲学史/美学史のトポス (canon 的トピック)** から再構成する。

- **Nietzsche**: Zarathustra 的「高山の孤独散策」+ 偏頭痛 + 残存的な音楽性 +
  アフォリズム生成 + 書物への懐疑 (身体性の復権) を柱にする。
- **Rikyu**: 茶室の幾何 (にじり口の狭さ) + 露地の歩行 + 道具配置の間
  + 秀吉関係の非対称緊張 + 切腹命令に至る pragmatics を柱にする。

両者とも ERRE モード候補としては `ri_create` / `ha_deviate` (Nietzsche) と
`chashitsu` / `zazen` (Rikyu) が dominant になるよう sampling を調整する。

## 変更対象

### 新規作成
- `personas/nietzsche.yaml` — Nietzsche ペルソナ
- `personas/rikyu.yaml` — Rikyu ペルソナ
- `tests/test_personas/__init__.py` — package marker
- `tests/test_personas/test_load_all.py` — `personas/*.yaml` 全件 validation

### 修正
- `tests/test_personas.py` — 既存 Kant テストは維持、新パッケージに move しない
  (既存の test_kant_* が fixture scope=module で動くため破壊的 move を避ける)

## persona 下書き (v1)

### Nietzsche (v1)
- `persona_id: nietzsche`
- `display_name: Friedrich Nietzsche`
- `era: "1844-1900"`
- `primary_corpus_refs: [kaufmann1974, safranski2002, klossowski1969]`
- `personality`:
  - openness 0.95 / conscientiousness 0.55 / extraversion 0.30 / agreeableness 0.20
  - neuroticism 0.80 / wabi 0.40 / ma_sense 0.50
- `cognitive_habits` (6 項目):
  1. (fact) Sils Maria 周辺の高山散歩 6-8 時間/日、peripatos
  2. (fact) 偏頭痛発作時の強制的臥床、study (non-peripatos)
  3. (legend) アフォリズム連鎖生成時の発話は音楽的リズムを伴う
  4. (fact) 書物へ距離、1 日 1-2 時間のみ読書制限 (眼精疲労で強制)
  5. (speculative) 偏頭痛後の神経可塑性 window = creative burst
  6. (speculative) Wagner 決別後の審美判断変容を DMN 再組織と仮説
- `preferred_zones`: [peripatos, garden, study]
- `default_sampling`: temperature 0.90 / top_p 0.92 / repeat_penalty 0.95
  (ri_create 寄り — 高温、ペナルティ緩、アフォリズム連鎖向け)

### Rikyu (v1)
- `persona_id: rikyu`
- `display_name: 千 利休`
- `era: "1522-1591"`
- `primary_corpus_refs: [kumakura1989, haga1978, nampo_namporoku]`
- `personality`:
  - openness 0.70 / conscientiousness 0.92 / extraversion 0.25 / agreeableness 0.55
  - neuroticism 0.25 / wabi 0.98 / ma_sense 0.95
- `cognitive_habits` (5 項目):
  1. (fact) 2 畳の草庵 (待庵) 設計、にじり口 65cm、chashitsu
  2. (fact) 露地の敷石配置で客人歩速を制御、garden
  3. (legend) 道具の出し入れに 7 段階の間 (ma) を設ける、chashitsu
  4. (fact) 秀吉主催大茶会での寡黙な所作、agora
  5. (speculative) 茶室の暗度 (明るさ) コントロールが感覚遮断で DMN 活性化
- `preferred_zones`: [chashitsu, garden]
- `default_sampling`: temperature 0.40 / top_p 0.75 / repeat_penalty 1.20
  (chashitsu + zazen 寄り — 低温、ペナルティ強、収束的)

## 影響範囲

- ペルソナ 2 体追加のみ。既存 kant 回帰なし
- `test_personas/test_load_all.py` は新パッケージ `tests/test_personas/`
  を導入するため、古い `tests/test_personas.py` との名前衝突が起きないか
  確認 (pytest は両方を discover する)
- bootstrap 側は変更なし

## 既存パターンとの整合性

- `personas/kant.yaml` のコメントヘッダ方針 (Flag convention / 設計 rationale 参照) を踏襲
- `source` は Harvard 名-年 形式 (kaufmann1974 等)
- `mechanism` は 1 文で cognitive-neuroscience 根拠を記述
- `trigger_zone` は 5 zone or null

## テスト戦略

- 新規 `tests/test_personas/test_load_all.py`:
  - `parametrize` で `personas/*.yaml` 全件を `PersonaSpec` に validate
  - 各 persona ごとに minimal assertion (persona_id 一致、habits≥4、flag 配分)
  - 3 体が同一の `default_sampling` 値を持たないことを assert
    (差別化が維持されている proxy)
- 既存 `tests/test_personas.py` は無変更 (Kant regression)

## ロールバック計画

- YAML のみの追加変更。revert 一発
- 本 PR merge 後に bootstrap が新 persona を require する場所なし
  (orchestrator 側は M4 最後のタスクで統合)

## 設計判断の履歴

- 初回案 (v1、本ファイル) を `design-v1.md` に退避予定
- `/reimagine` で v2 を再生成、`design-comparison.md` で比較
- 採用案を `decisions.md` に記録
