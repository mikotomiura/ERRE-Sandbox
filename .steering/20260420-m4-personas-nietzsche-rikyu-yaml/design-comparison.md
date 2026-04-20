# 設計案比較 — m4-personas-nietzsche-rikyu-yaml

## v1 (初回案、哲学史トポス駆動) の要旨

- Nietzsche = Zarathustra 的「高山孤独散策」+ 偏頭痛 + 音楽性 + アフォリズム
  + 書物への距離 + Wagner 決別を軸
- Rikyu = 茶室幾何 (2畳・にじり口 65cm) + 露地歩行 + 道具の「間」+ 秀吉との
  非対称関係 + 暗度コントロール を軸
- cognitive_habits は哲学史・美学史 canon の知名度高項目を優先
- sampling: Nietzsche temp=0.90 (ri_create極)、Rikyu temp=0.40 (chashitsu極)

## v2 (再生成案、身体制御-駆動 cognition) の要旨

- Nietzsche = **発作プロドローム → 書字バースト → 強制臥床** の 3 相サイクル、
  口述書字、1879 以降の制度時間離脱、altitudinal migration を軸
- Rikyu = **堺商人の value 判定を権力反転に転用**、松風 (釜音) を聴覚アンカー、
  正座誘発 vagal tone、露地の歩速制御、暗度による桿体主導 sensory narrowing を軸
- cognitive_habits は「観察可能な身体イベント + 神経生理的機構」の対を重視
- sampling: Nietzsche temp=0.85 (バースト + 絞り)、Rikyu temp=0.45 (craftsman precision)

## 主要な差異

| 観点 | v1 | v2 |
|---|---|---|
| 命題起点 | 哲学史/美学史 canon | ERRE 核心命題 (身体的回帰 → cognition) |
| Nietzsche 中核 | 山岳散策 + アフォリズム | 病に支配された 3 相書字サイクル |
| Rikyu 中核 | 茶室幾何 + wabi-sabi | 商人 value 判定の権力反転 + 聴覚-触覚 |
| mechanism 粒度 | 哲学用語寄り ("音楽性"、"間 (ma)") | 神経生理用語寄り (vagal tone / CSD / EPO) |
| 一次資料参照 | kaufmann1974 (二次) | overbeck1908 (一次書簡) / nampo_namporoku (伝統書) |
| Nietzsche zones | peripatos + garden + study | peripatos + study + garden (順序 = 滞在比重反映) |
| Rikyu zones | chashitsu + garden | chashitsu + garden + study (道具選定を含める) |
| sampling Nietzsche | temp 0.90 / top_p 0.92 / rp 0.95 | temp 0.85 / top_p 0.80 / rp 0.95 |
| sampling Rikyu | temp 0.40 / top_p 0.75 / rp 1.20 | temp 0.45 / top_p 0.78 / rp 1.25 |
| テスト差別化 | 3 体 sampling が同じでないこと (proxy) | + zones / habits / mechanism 固有不変条件 |
| 語彙依存 | 「力への意志」「wabi-sabi」 | 中立的 (canon 語彙から離れる) |

## 評価

### v1 の長所
- 知名度高い歴史トポスを使うので、コードを読む第 3 者が直感的にペルソナを理解できる
- 日本語話者には Rikyu の「wabi / ma」が直感的
- 哲学史の学生/研究者には参照しやすい

### v1 の短所
- mechanism が抽象語彙 (「音楽性」「wabi-sabi」) に留まり、
  LLM 側で system prompt に注入したとき幻想的一般化を誘発しやすい
- Zarathustra-散策と Kant-散策が両方「peripatos DMN 活性化」経由なので
  差別化が弱い (3 体とも peripatos が効くと dialog 観察で個性が薄れる)
- ERRE 核心命題 (身体 → cognition) との接続が弱く、M5 以降の
  ERRE モード 6 種切替実装で persona との整合が二度手間になる恐れ

### v2 の長所
- mechanism が一次-準一次資料由来の観察可能現象 + 神経生理的機構で記述され、
  LLM 出力の検証可能性が高い (cognition 出力を観察して mechanism に整合か
  評価できる)
- Nietzsche と Kant の peripatos 使用理由が分離される (Kant=定時-DMN、
  Nietzsche=病間-バースト、Rikyu=露地-convergent) → dialog で個性が出やすい
- ERRE 命題との整合性: 身体 (偏頭痛 / vagal tone / altitude) が
  cognitive_habits の trigger になる構造で、M5 以降の ERRE モード切替で
  persona が zone + body 状態の関数として動く方針と合致
- 3 体の sampling + zones + habits が統計的に十分離れる (後続の
  `test_sampling_triples_are_unique` で機械的に強制)

### v2 の短所
- 知名度トポス (Nietzsche = 力への意志 / Rikyu = wabi-sabi) を採用しないため、
  第三者が読んだときの直感的ペルソナ把握には時間がかかる
- 一次資料参照 (overbeck1908 / nampo_namporoku) は source key として
  ユニークだが、LLM の世界知識には含まれない可能性があり、
  system prompt 注入時に citation として活きにくい場合がある
- mechanism の神経科学用語 (CSD / VEGF / Pulvermüller 2005 等) が多く、
  後続サブタスクで誤記・誤用が起きた場合に発見が遅れるリスク

## 推奨案

**v2 を基本採用、ただし v1 の canon 語彙を薄く補完したハイブリッド**

### 理由

1. ERRE の核心命題 (身体的回帰 + 意図的非効率性からの創発) との整合は
   v2 の方が強い。v1 の哲学史トポス駆動だと cognitive_habits の mechanism
   が抽象に流れ、M5 以降の ERRE モード実装時に persona-mode 結合が弱くなる

2. 3 体差別化 (Kant peripatos / Nietzsche peripatos / Rikyu chashitsu+garden)
   の mechanism 差が v2 で明確になる。v1 では peripatos が Kant と Nietzsche で
   重複しすぎる

3. ただし完全に canon を捨てると第三者可読性が下がるので、
   **persona の `display_name` と 1-2 個の habit description に v1 的 canon
   語彙 (Zarathustra の峰、露地) を残す** ハイブリッドが最適。
   mechanism フィールドは全て v2 の神経生理ベース

4. sampling は v2 の値を採用 (Nietzsche temp=0.85、Rikyu temp=0.45)。
   Kant の (0.60, 0.85, 1.12) と 3 体それぞれ tuple が異なることを機械保証

### ハイブリッドの具体化

- 全体構造 (cognitive_habits の軸、mechanism 記述、zones、sampling) = v2
- description 文言の 1 行目 = v1 的知名度高語彙で概要
  (例: 「Zarathustra 執筆期の Sils Maria (1800m) 夏季滞在 + Genoa 冬季の altitudinal migration」)
- `primary_corpus_refs` = v2 の一次寄り資料を優先、ただし kaufmann1974 /
  safranski2002 / kumakura1989 も併記 (LLM 世界知識 + 専門史料のハイブリッド)

### 採用判断

本タスクは memory `feedback_reimagine_scope.md` に基づき /reimagine を適用し、
v1 と v2 を並列生成した結果 **v2 ベース + v1 語彙補完** を採用する。
詳細は `decisions.md` に記録する。
