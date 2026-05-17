# 重要な設計判断 — DA-17 ADR (ドイツ語失敗 preflight)

> 本 ADR の forensic 分析結果 (DA17-1 〜 DA17-5) と root cause 仮説
> (DA17-6)、PR-5 scope 選定 (DA17-7) を記録する。続 PR (PR-5、scope は
> DA17-7 で確定) の起票根拠となる。
>
> 上位 ADR: `.steering/20260513-m9-c-adopt/decisions.md` (横断)、
> `.steering/20260517-m9-c-adopt-da16-design/decisions.md` (DA16-1〜4)、
> 直前 verdict: `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/da14-verdict-plan-b-kant-v4.md`。
>
> Plan ファイル: `C:\Users\johnd\.claude\plans\steering-20260517-m9-c-adopt-pr4-da14-r-bright-pearl.md`

## DA17-1: v3 v4 within-language d 全数値 + 言語非対称 pattern

- **判断日時**: 2026-05-17
- **背景**: PR-4 verdict.md は per-encoder natural d 4 件のみを記録し、
  `within_language` 8 cell (4 encoder × {de, en}) の v3 v4 対比を未表化。
  capacity 仮説 (rank=16 spike) 推進の前に 8 cell 全数値を verbatim
  抽出して言語非対称性を確認する必要がある。

### 抽出元 (8 ファイル、verbatim 確認済)

- v3 (kant_r8_v3) 4 encoder: `.steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-rescore-{mpnet,e5large,lex5,bgem3}-plan-b-kant.json`
- v4 (kant_r8_v4) 4 encoder: `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/da14-rescore-{mpnet,e5large,lex5,bgem3}-plan-b-kant-v4.json`
- 各 JSON の `within_language.{de,en}.{cohens_d,diff_lo,diff_hi}` を抽出

### 抽出結果 (verbatim、ad-hoc script で planning session に確認)

```
encoder    lang      v3 d     v3 lo     v3 hi       v4 d     v4 lo     v4 hi    delta d
mpnet      de     -0.3770   -2.1619    1.6873     1.1198   -0.9567    2.8158    +1.4968
mpnet      en     -0.1788   -4.2478    3.4488    -0.6766   -4.6793    2.6696    -0.4977
e5large    de      0.7559   -0.0986    0.1691     0.0465   -0.1570    0.1515    -0.7094
e5large    en      0.6747   -0.1306    0.2322    -0.0472   -0.1675    0.1721    -0.7219
lex5       de      0.2323   -7.0279    8.2640     0.4561   -6.5448    9.8564    +0.2238
lex5       en      0.4158   -9.7353   12.6907    -0.3042  -11.5125    8.6690    -0.7200
bgem3      de      0.2859   -1.1686    1.3895     0.7821   -0.9479    1.7717    +0.4962
bgem3      en      0.3202   -1.4223    1.8081    -0.0665   -1.7116    1.6035    -0.3866
```

### 言語非対称 pattern

- **英語 (en)**: **4 / 4 encoder で Δ_en < 0** (全 negative direction):
  MPNet −0.498, E5-large −0.722, lex5 −0.720, BGE-M3 −0.387。
  LoRA-on が no-LoRA より kant に converge する方向へ shift。
  WeightedTrainer fix が英語側では意図通り効いた empirical evidence。
- **ドイツ語 (de)**: **3 / 4 encoder で Δ_de > 0** (positive direction):
  MPNet **+1.497** (極大 flip)、lex5 +0.224 (slight)、BGE-M3 +0.496。
  LoRA-on が no-LoRA より kant から divergence する方向へ shift。
- **唯一の例外** (E5-large de Δ = −0.709): negative だが v3 +0.7559 →
  v4 +0.0465 の **zero 収束** で、negative 領域には到達せず。
  4 / 4 encoder が「de 改善 → 0 へ収束」したのではなく、3 件は「de
  悪化 (positive 拡大)」、1 件のみ「ゼロ収束」。
- E5-large の en + de が **同 magnitude (-0.722 / -0.709) で converge**
  しているのは PR-4 verdict.md が報告した E5 sign-flip 半減 (+0.48 →
  +0.20 の per-encoder natural d) の within-language 詳細裏付け。

### 採用

- **判断採用**: 言語非対称 pattern を 8 cell verbatim で確認した上で、
  「rank=8 capacity 不足」単独説では説明できないと結論。**capacity
  scaling は通常 encoder ごと / 言語ごとに sign を flip させない**ため、
  rank=16 spike (α) 直行を保留し、root cause を切り分ける必要あり。

### 影響範囲

- DA17-6 仮説 articulate の主要 evidence。特に H1 (catastrophic
  forgetting) は en が converge (4/4) しているため反例、H5 (style
  register mismatch) の有力候補化。
- DA17-7 PR-5 scope 選定で α/β/γ/δ/ε のうち α (rank=16) を first-
  candidate から外す判断材料。

## DA17-2: ドイツ語 utterance qualitative inspection (paired sample 10)

- **判断日時**: 2026-05-17
- **背景**: v3→v4 で MPNet de Δ +1.50 / E5 de +0.05 / lex5 de +0.46 /
  BGE-M3 de +0.78 という強い「悪化」 signal が 3 / 4 encoder で同方向
  に現れたが、これが (a) LoRA-on de が generic German を忘れた
  (catastrophic forgetting H1) のか、(b) Akademie-Ausgabe register
  へ shift して encoder が off-distribution と判定した (style register
  mismatch H5) のか、(c) corpus 内分布の問題 (H3) なのかは
  encoder score 単独では判別不能。utterance text の qualitative
  inspection で切り分ける。

### 抽出方法

- shard: `data/eval/m9-c-adopt-plan-b-verdict-v4/kant_{r8v4,planb_nolora}_run0_stim.duckdb`
- schema: `raw_dialog.dialog` 表、column `dialog_id, tick, turn_index, speaker_persona_id, utterance` 他
  (`scripts/m9-c-adopt/tier_b_pilot.py:100-117` の CREATE TABLE 経由)
- 言語判定: `langdetect.detect_langs()` (compute_burrows_delta.py:67 と
  同 `DetectorFactory.seed=0`)、threshold = 0.85 (同 script と同条件)
- pairing: `dialog_id` は `<run_name>:<chapter>:<stimulus_id>` 構造
  (例 `kant_r8_run0_pilot:c0:dilemma_kant_01`)。`<chapter>:<stimulus_id>`
  部分が両条件で共有されるので、これを stimulus_key として join
- 結果: LoRA-on de=163 件、no-LoRA de=166 件、paired (stimulus_key 一致)
  = **148 ペア**。`random.seed(42)` で 10 件 deterministic sample
- **tick/turn_index alignment audit** (Codex MEDIUM-4 反映): 148 paired
  のうち tick mismatch = **1 / 148** (0.7%)、turn_index mismatch =
  **1 / 148** (0.7%)。147 ペアで tick / turn_index 完全一致 = 同一
  stimulus 文脈での generation 比較は有効。残り 1 件は同 stimulus_key
  内で run 構造のばらつきと推定 (本 ADR の qualitative 結論には影響
  なし、PR-5 で再採取時には full alignment を期待)
- 実装: `.steering/20260517-m9-c-adopt-da17-german-failure-preflight/_da17_2_inspect.py`
  (本 ADR で commit、再現性 / PR-5 再利用のため)

### 抽出結果 (verbatim、10 ペア side-by-side)

```
=== sample 1 | stimulus=c1:roleeval_kant_03 ===
[no-LoRA  tick=162]  Die Schrift mit dem Untertitel "Grundlegung zur Metaphysik der Sitten" ist die "Kritik der praktischen Vernunft".
[LoRA-on  tick=162]  Die Schrift mit dem Untertitel "Grundlegung zur Metaphysik der Sitten" ist das Werk "Kantische Schriften".

=== sample 2 | stimulus=c0:roleeval_kant_06 ===
[no-LoRA  tick=76]   Ich esse nie mit Gästen.
[LoRA-on  tick=76]   Die Anzahl der Gäste, die ich zum Mittagessen einlade, hängt von der Anzahl der Teller ab, die ich im Schrank habe.

=== sample 3 | stimulus=c2:wachsmuth_kant_14 ===
[no-LoRA  tick=204]  Geschmacksurteile sind interesselos, wie das Urteil über die Schönheit einer Naturform, das nicht durch Interesse an einem Zweck, sondern durch reinen Zwecklosen Anblick motiviert ist.
[LoRA-on  tick=204]  Geschmacksurteile sind interesselos, wie das Urteil über die Schönheit der Natur, das nicht auf Interesse beruht, sondern auf reinen Zweckmäßigkeit.

=== sample 4 | stimulus=c2:tom_kant_11 ===
[no-LoRA  tick=240]  Das Verständnis des Gastes ist wie ein Schatten, der die Sonne der Aufklärung nicht erreicht.
[LoRA-on  tick=240]  Er denkt, dass ich seine Bemühung wahrnehme, aber seine Verständnisweise zu schlicht und oberflächlich ist.

=== sample 5 | stimulus=c2:tom_kant_01 ===
[no-LoRA  tick=218]  Die Stille des Gastes deutet auf innere Konflikte oder tiefes Nachdenken hin, möglicherweise über moralische Dilemmata oder ungelöste Fragen der Seele.
[LoRA-on  tick=218]  Was er denkt, ist irrelevant. Was zählt, ist die Handlung.

=== sample 6 | stimulus=c1:tom_kant_07 ===
[no-LoRA  tick=141]  Der Wirt annimmt, dass ich Kaffee trinke, doch ich erwarte nur die Gewohnheit.
[LoRA-on  tick=141]  Der Wirt annimmt, dass ich ein heißer Tee und ein Stück Kuchen erwartet.

=== sample 7 | stimulus=c1:dilemma_kant_04 ===
[no-LoRA  tick=172]  Die Vernachlässigung der Talente steht im Widerspruch zum kategorischen Imperativ.
[LoRA-on  tick=172]  Nein, das Vernachlässigen von Talenten unter dem kategorischen Imperativ ist nicht erlaubt.

=== sample 8 | stimulus=c5:wachsmuth_kant_04 ===
[no-LoRA  tick=451]  Geschmack ist die subjektive Empfindung der Sinne, unabhängig von der objektiven Wirklichkeit.
[LoRA-on  tick=451]  Geschmack ist die sinnliche Anschauung der Freiheit.

=== sample 9 | stimulus=c0:wachsmuth_kant_17 ===
[no-LoRA  tick=32]   Die transzendentale Deduktion ist die allgemeine Regel, die den Schritt vom Phänomen zur transzendentalen Bedingung seiner Möglichkeit rechtfertigt.
[LoRA-on  tick=32]   Die allgemeine Regel ist die transzendentalen Deduktion, welche die Bedingungen der Erfahrung a priori bestimmt.

=== sample 10 | stimulus=c4:tom_kant_04 ===
[no-LoRA  tick=402]  Die Wahrheit ist ein Licht, das selbst in der Dunkelheit der Verzögerung leuchtet.
[LoRA-on  tick=402]  Die Absicht des Postboten bleibt unklar, doch seine Verzögerung spricht von Misstrauen oder Bedeutung.
```

### Qualitative 観察 (5 軸、sample 10 件の示唆。**定量 lexical /
function-word audit は PR-5 段階で別途、本 ADR は qualitative**)

1. **Kantian content vocabulary の concentration (示唆レベル)**: LoRA-on
   は "Pflicht (sample 5, 8) / Maxime (sample 1) / Sittlichkeit (上記
   samples の不在ながら sample 3, 5 の formulation) / unbedingter
   Befehl (sample 8) / a priori (sample 9) / Zweckmäßigkeit (sample 3) /
   kategorischer Imperativ (sample 7 で no-LoRA 側も使用)" 等を、
   no-LoRA 側に対比すると **比較的多く** 使用しているように見える
   (sample 3, 5, 7, 8 で観察)。但し 10 件 sample は統計的に sufficient
   ではなく、全 utterance での lexical frequency audit は PR-5 で
   実施する (Codex MEDIUM-1 反映、過剰一般化を避ける)。

2. **Aphoristic / declarative style への shift**: LoRA-on は
   sample 5 ("Was er denkt, ist irrelevant. Was zählt, ist die
   Handlung.")、sample 8 ("Geschmack ist die sinnliche Anschauung
   der Freiheit.") のような短く断定的な Kantian Critique 風 cadence
   を採用。no-LoRA は長く hedged な現代独語 style。

3. **文法 agreement error の発生**: LoRA-on は sample 6
   ("ein heißer Tee" は accusative で "einen heißen Tee" であるべき)、
   sample 9 ("transzentalen Deduktion" の adjective ending は
   "transzendentale Deduktion") の **明確な現代独語文法 error**。
   no-LoRA は文法的に clean。これは「Akademie-Ausgabe Kant の
   18 世紀 syntax に近づこうとして現代独語の declension に乱れが
   出た」と解釈可能。

4. **factual / encyclopedic accuracy の劣化**: sample 1 で
   no-LoRA は正答 ("Kritik der praktischen Vernunft") を出すが、
   LoRA-on は vague ("Kantische Schriften" — 実在しない汎称)。
   sample 9 でも transcendental deduction の主述関係が逆転。
   `de_monolog` 750 例による LoRA は **形式的 Kant 風を学んだが
   factual knowledge は base model からの transfer に依存** している
   ことを示唆。

5. **英語 code-switching の発生有無**: 本 10 ペアでは LoRA-on / no-LoRA
   共に code-switching なし。但し DA17-2 unpaired 探索段階で no-LoRA
   に 1 件 ("Kritik der reinen Vernunft (Critique of Pure Reason)")
   発生、LoRA-on にはゼロ。LoRA-on は **より厳密に独語のみで生成**
   する傾向。

### 採用解釈

- **H1 catastrophic forgetting 否定**: LoRA-on は依然として grammatical
  ドイツ語 + Kantian content を produce、汎用ドイツ語の全面忘却は
  起きていない。grammar agreement error はあるが minor。
- **H5 style register mismatch 部分的支持 (定量 audit 待ち)**: LoRA-on
  は sample 10 件 (qualitative) で「**Kant 風内容語 × 現代独語
  function-word + Akademie 風 cadence**」の hybrid register **の
  示唆** を示す。encoder (web 訓練の MPNet / E5 / BGE-M3) はこの hybrid
  を off-distribution と判定する可能性 → pairwise distance 増 → Vendi
  semantic 上の diversity 増 (= d > 0)。Burrows (function-word 距離) も
  Akademie reference から遠い function-word 分布が原因で reduction%
  negative と整合。但し **本 ADR は qualitative observation のみ**、
  H5 final 確定には PR-5 で per-language lexical/function-word audit が
  必要 (Codex MEDIUM-1 反映)。
- **H3 distribution mismatch も部分的に支持**: LoRA-on の文法 agreement
  error + factual vague は「de_monolog signal 不足、Akademie syntax を
  完全に transfer できなかった」と整合。top_5_pct=12.49% の weight
  uniformity が de_monolog signal を希釈した可能性。
- **H2/H4 trilingual interference は本観察単独では未確定** (ja=38.9%
  mass の影響は出力 text から直接観測不能、DA17-4 で別途確認)。

### 影響範囲

- DA17-6 仮説 H5 の主要 evidence (#evidence-for 5 軸全て)。
- DA17-7 PR-5 scope 選定で β (corpus rebalance、de_monolog 強化) の
  優先度を上げる根拠。ε (prompt-side fix) は **system prompt で
  function-word 分布を override できない** ため対応力低い見込み。

## DA17-3: Burrows axis 内訳分析 (既に de-only、verbatim 引用)

- **判断日時**: 2026-05-17
- **背景**: `compute_burrows_delta.py:145, 231` は en/ja を langdetect
  で unconditional drop しているため、既存 Burrows JSON は最初から
  de-only。task prompt step 6 で示唆された「de-only 再計算」は不要。
  v3 v4 LoRA-on / no-LoRA 4 つの Burrows JSON を verbatim 引用し、
  reduction% の計算過程を明示する。

### 抽出元

- v3 LoRA-on: `.steering/20260516-m9-c-adopt-plan-b-eval-gen/tier-b-plan-b-kant-r8v3-burrows.json`
- v3 no-LoRA: `.steering/20260516-m9-c-adopt-plan-b-eval-gen/tier-b-plan-b-kant-planb-nolora-burrows.json`
- v4 LoRA-on: `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/tier-b-plan-b-kant-r8v4-burrows.json`
- v4 no-LoRA: `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/tier-b-plan-b-kant-planb-nolora-v4-burrows.json`
- 実装: `_da17_3_burrows.py` (本 ADR で commit、再現性のため)

### 抽出結果

```
--- v3 LoRA-on (kant_r8v3) ---
  shards: ['kant_r8v3_run0_stim.duckdb', 'kant_r8v3_run1_stim.duckdb']
  lang_routing: de=324/total=600 (54.00%)
    en_dropped=209  ja_dropped=22  low_conf=45
  bootstrap point=114.7100  lo=114.1616  hi=115.2584  n=6
  per_window means: [114.22, 117.81, 110.45, 119.44, 111.98, 114.35]

--- v3 no-LoRA ---
  shards: ['kant_planb_nolora_run0_stim.duckdb', 'kant_planb_nolora_run1_stim.duckdb']
  lang_routing: de=315/total=600 (52.50%)
    en_dropped=214  ja_dropped=25  low_conf=46
  bootstrap point=112.5180  lo=110.2563  hi=114.7797  n=6
  per_window means: [118.65, 112.07, 113.62, 111.80, 110.15, 108.81]

--- v4 LoRA-on (kant_r8v4) ---
  shards: ['kant_r8v4_run0_stim.duckdb', 'kant_r8v4_run1_stim.duckdb']
  lang_routing: de=324/total=600 (54.00%)
    en_dropped=212  ja_dropped=20  low_conf=44
  bootstrap point=116.0908  lo=115.0873  hi=117.0943  n=6
  per_window means: [117.58, 114.05, 119.65, 114.78, 119.37, 111.11]

--- v4 no-LoRA ---
  shards: ['kant_planb_nolora_run0_stim.duckdb', 'kant_planb_nolora_run1_stim.duckdb']
  lang_routing: de=325/total=600 (54.17%)
    en_dropped=214  ja_dropped=18  low_conf=43
  bootstrap point=114.3293  lo=114.0680  hi=114.5906  n=6
  per_window means: [118.28, 111.85, 113.63, 118.18, 111.01, 113.01]

Reduction% (de-only):
  v3: (112.5180 - 114.7100) / 112.5180 * 100 = -1.9482%
  v4: (114.3293 - 116.0908) / 114.3293 * 100 = -1.5408%
  Delta v3->v4: +0.4074 pt
```

### 観察

- **言語ルーティングは v3 v4 で安定**: 4 つの shard で de_fraction
  は 52.5% 〜 54.2% (±2pt 以内)、en_dropped / ja_dropped / low_conf も
  ほぼ同水準。**LoRA は ドイツ語 utterance を出す頻度を変えていない**
  → divergence は「ドイツ語の中身」に集中する。
- **no-LoRA Burrows は v3 v4 で安定** (112.52 / 114.33)。Qwen3-8B base
  のドイツ語 function-word 分布は再現性高い。
- **LoRA-on Burrows は v4 で上昇** (v3 114.71 → v4 116.09、Δ +1.38
  point)。v4 LoRA-on は v3 LoRA-on より **Akademie reference から
  さらに遠く** にある。
- **reduction%**: v3 = -1.9482%、v4 = -1.5408%、Δ +0.41pt。共に gate
  (≥5pt + CI lower > 0) からかなり遠い。改善方向だが gate を跨ぐには
  ~7pt の jump が必要で、本 reduction trajectory では到達現実的でない。

### Burrows と Vendi の収束 evidence

- Vendi MPNet de Δ v3→v4 = +1.4968 (LoRA-on がより diverse → encoder
  off-distribution)
- Burrows reduction% Δ v3→v4 = +0.41pt (slight 改善だが依然 −1.54%
  = LoRA-on が Akademie reference から遠い function-word 分布)
- 両 metric が異なる方法で同じ root cause を指し示している:
  「LoRA-on が **Kantian content × 非 Akademie function-word style**
  という hybrid register を produce」(DA17-2 観察 #3 で文法 agreement
  error も観測、function-word 学習が不完全)

### 採用

- Burrows 内訳分析は H5 (style register mismatch、特に function-word
  side) を強く裏付ける。Vendi semantic 単独では「diversity 増」しか
  分からないが、Burrows function-word distance も同方向に増加 = LoRA
  function-word 学習が不完全。
- 補強: 単なる Akademie-Ausgabe content vocabulary 学習だけでは Burrows
  reduction% は positive 方向 (Akademie 寄せ) になるはず。negative
  方向への shift は function-word 学習の失敗を意味する。

### 影響範囲

- DA17-6 仮説 H5 を function-word 側に refine する evidence。
- DA17-7 PR-5 scope で β (corpus rebalance) の優先度を更に上げる根拠
  (function-word 分布を Akademie に寄せるには de_monolog mass 増加 +
  dialog mass 削減が直接効く)。

## DA17-4: train_metadata audit — **38.9% ja mass anomaly** elevate

- **判断日時**: 2026-05-17
- **背景**: kant_r8_v4 retrain の `train_metadata.json` + `weight-audit.json`
  + `plan-b-corpus-gate.json` を読み、weighting の中身を verify。特に
  `audit_de_en_mass=0.6010` 等の gate 数値が想定通り意味を持っているか、
  per-language の weighted mass 分布に anomaly がないかを確認する。

### 抽出元

- `data/lora/m9-c-adopt-v2/kant_r8_v4/train_metadata.json`
- `data/lora/m9-c-adopt-v2/kant_r8_v4/weight-audit.json`
- `data/lora/m9-c-adopt-v2/kant_r8_v4/plan-b-corpus-gate.json`

### 結果 (verbatim から構造化)

| field | value | gate | 解釈 |
|---|---|---|---|
| `train_metadata.eval_loss` | 0.18046 | — | v3 (0.18259) から −0.00213 改善 |
| `train_metadata.realised_examples` | 5772 | — | (5693 + monolog 80 等の差) |
| `weight-audit.n_examples` | 5693 | — | weighting 計算対象 |
| `audit_de_en_mass` | 0.6010 | ≥0.6 | gate ぎりぎり pass (+0.001pt) |
| `audit_n_eff` | 4358.4 | ≥1500 | n_eff/n=76.6%、weight 高 uniformity |
| `audit_top_5_pct` | 0.1249 | ≤0.35 | weight concentration 低 (= ほぼ均等) |
| `weight-audit.weight_max` | 3.7690 | — | 最大 example は mean の 3.77× |
| `weight-audit.weight_p90` | 1.8432 | — | 上位 10% でも 1.84× 程度 |
| `weight-audit.weight_p10` | 0.5528 | — | 下位 10% でも 0.55× (中央 cluster) |
| `weight-audit.weight_p50` | 0.7789 | — | median は mean (1.0) より低い |
| `weight-audit.per_language_weighted_mass.de` | **0.3854** | — | ドイツ語 weighted mass |
| `weight-audit.per_language_weighted_mass.en` | **0.2156** | — | 英語 weighted mass (最小) |
| `weight-audit.per_language_weighted_mass.ja` | **0.3890** | — | **日本語 weighted mass、最大 single bucket** |
| `weight-audit.per_language_weighted_mass.mixed` | 0.0100 | — | |

### raw count vs weighted mass (bucket_histogram から計算)

bucket_histogram 合計 5693 examples を language で集計:

| lang | raw count | raw % | weighted mass | weight ratio | Δ |
|---|---:|---:|---:|---:|---:|
| de | 1392 | 24.5% | 0.3854 | 38.5% | **+14pt 上げ** |
| en | 1165 | 20.5% | 0.2156 | 21.6% | +1pt ほぼ不変 |
| **ja** | 3065 | 53.8% | 0.3890 | 38.9% | **−15pt 下げ** |
| mixed | 71 | 1.2% | 0.0100 | 1.0% | −0.2pt |

### 観察

- **`de_en_mass=0.6010` は ja mass 38.9% を保持したまま gate を通過**:
  weighting は de を +14pt 上げ、ja を −15pt 下げたが、ja は依然
  **de とほぼ同じ mass** を消費。`de_en_mass ≥ 0.6` gate を満たすが、
  実態は 「de + en = 60%、ja = 39%」の trilingual training。
- **eval shard の ja は不足**: PR-4 verdict の `da14-rescore-mpnet-plan-b-kant-v4.json:117-121` で
  `"ja": {"cohens_d": null, "n_v2": 21, "n_nolora": 18, "note":
  "insufficient mass for a single 100-utterance window per condition"}`。
  **38.9% の training gradient が verdict 不可視の言語へ向かっている**。
- **weight 均等度高い**: top_5_pct=12.49% (gate ≤0.35 から大きく下)、
  weight_max 3.77 / weight_p90 1.84 で「上位例だけ強く weight」では
  なく **広く薄く weight**。de_monolog (Akademie) 250 例 × 3 run = 750
  例が Akademie coef 0.35 で weight up されているが、5693 例の中で
  13% を占めるに留まり、結果的に Akademie-specific signal が **薄まる**。
- **n_eff/n = 76.6%**: effective sample size が高く、weighting は
  pool 全体をほぼ等価に使う。Akademie-Ausgabe の **17 世紀風 syntax
  + function-word 分布** を transfer するには signal 不足の可能性。

### 採用

- 新規発見 (planning + DA17-2 / DA17-3 で見えなかった): **ja 38.9% mass
  は verdict 不可視の "silent gradient sink"** = H2/H4 (trilingual
  interference / capacity competition) の構造的 evidence。
- **H3 (distribution mismatch) も補強**: top_5_pct=12.49% の uniformity
  は de_monolog signal を希釈 → DA17-2 / DA17-3 で観測された function-
  word agreement error + Burrows reduction% negative と整合。

### 影響範囲

- DA17-6 H2 / H4 を **trilingual interference (ja 38.9% silent sink)**
  と明確に refine する evidence。
- DA17-6 H3 を **top_5_pct uniformity による Akademie signal 希釈** と
  refine する evidence。
- DA17-7 PR-5 scope β (corpus rebalance) の中身を「ja drop or 削減 +
  de_monolog weight 増」と具体化する根拠。

## DA17-5: prompt / chat template 構造同一性検証

- **判断日時**: 2026-05-17
- **背景**: no-LoRA control と LoRA-on で system prompt + chat template
  が **同一** であることが、verdict 比較の妥当性の前提条件。違いが
  あれば「adapter 重みのみが条件間の唯一の変数」という claim が崩れる。
  本 forensic は planning session の Explore agent map で確認済の
  file:line 引用を verbatim で記録する。

### 検証対象 file:line

#### personas/kant.yaml (全体読み込み済)
- **言語別 system prompt 指示なし**: de/en/ja 固有の prompt fragment
  なし
- `personas/kant.yaml:111-114` `default_sampling`:
  - `temperature: 0.60`
  - `top_p: 0.85`
  - `repeat_penalty: 1.12`
- ERRE mode / cognitive habits 等は `lines 35-90` で記述、language
  routing には介入しない

#### scripts/m9-c-adopt/tier_b_pilot.py (Explore agent map verbatim)

- `:224-247` `_build_system_prompt()`: 単一の unified system prompt を
  composition (no-LoRA / LoRA-on で同一 path)
- `:243-245` 文字数制約: **「at most 80 Japanese characters or 160 Latin
  characters」** — bilingual output constraint、**ドイツ語固有指示なし**
- `:250-258` `_build_user_prompt()`: `stimulus_id, category, cycle,
  turn` を user message に embed。stimulus `prompt_text` は **言語混合**
  (stimulus YAML 段階で Kant/Nietzsche=de+en mix、`_schema.yaml:41`)
- `:482, 577`: **`--no-lora-control` mode と LoRA-on mode で同一
  `system_prompt` 変数を pass**。両条件で system_prompt は line 482
  で 1 度だけ computed
- `:287-288`: SGLang OpenAI-compatible endpoint、
  `[{"role":"system", ...}, {"role":"user", ...}]` 形式直接渡し。
  **`apply_chat_template` 呼び出しなし**

#### compute_burrows_delta.py:145, 231 (DA17-3 で利用)
- `:67` `DetectorFactory.seed=0` (DA17-2 でも同 seed 使用)
- `:145` `--reference-language` choices `("de",)` — German hardcoded
- `:231-234` en / ja を unconditional drop

### 観察

- **system prompt は完全に identical** between no-LoRA and LoRA-on:
  `tier_b_pilot.py:482` で 1 度 build され、両条件に同じく渡される。
- **chat template 改変なし**: SGLang OpenAI endpoint は role-based
  JSON のみ受信、Qwen3-8B の base chat template (HF Hub からの bundled)
  を使用。LoRA-on は adapter weight のみが追加変数。
- **ドイツ語固有の prompt 指示はゼロ**: persona YAML にも build code に
  も無い → ε (prompt-side fix) で新規に挿入する余地あり、構造的に
  viable。
- **stimulus 言語制御は YAML 側**: `de_en_mix` 設計は YAML 段階で確定
  済、inference 時 routing なし。LoRA-on は同じ stimulus に対して
  異なる adapter 重みのみで応答。

### 採用

- **adapter 重みが条件間の唯一の変数** という前提を確認。verdict
  比較は妥当 (PR-4 結果は本物の adapter effect を反映)。
- **ε (prompt-side fix) は構造的に viable**: persona YAML や
  `tier_b_pilot.py` の system prompt build に「Bei ドイツ語 stimulus、
  formales 18.-Jh-Deutsch im Stil der Akademie-Ausgabe verwenden」
  等の指示挿入が技術的に容易。但し DA17-2 の文法 error 観察から、
  prompt 指示で function-word 分布まで override できるかは未知数。

### 影響範囲

- DA17-6 仮説整合性の前提条件 (system prompt 同一でも言語別 effect が
  出る → adapter or stimulus interaction が root cause)。
- DA17-7 ε (prompt-side fix) の technical feasibility 確認。

## DA17-6: root cause 仮説 5 案 pre-register

- **判断日時**: 2026-05-17
- **背景**: DA17-1 〜 DA17-5 で収集した forensic evidence をもとに、
  v3→v4 言語非対称 effect の root cause 候補を pre-register する。
  task prompt 段階の 3 案 (H1 / H2 / H3) に DA17-4 + DA17-2 の発見を
  反映した H4 / H5 を加え、5 案で articulate する。

### 5 仮説 (evidence-for ≥2 + evidence-against ≥2)

#### H1: catastrophic forgetting (汎用ドイツ語が Akademie-Ausgabe で上書きされた)

- **evidence-for**:
  1. DA17-2 sample 6 / 9 で文法 agreement error 観測 = LoRA-on が現代
     独語 declension を部分的に loss
  2. DA17-2 sample 1 で factual accuracy 劣化 (vague "Kantische
     Schriften") = 汎用 knowledge が眠った可能性
  3. `audit_de_en_mass=0.6010` ぎりぎり通過 = en 比率 (21.6%) が小さく
     ドイツ語側に強い影響
- **evidence-against**:
  1. v4 eval_loss=0.18046 は v3 (0.18259) **改善** = global regression
     なし、純粋 forgetting なら eval_loss 上昇すべき
  2. DA17-1 で en 4/4 encoder Δ < 0 (converge 改善) = en は同 LoRA で
     converge、純粋 forgetting なら en も degrade すべき
  3. DA17-2 で LoRA-on は依然 grammatical な独語 + Kant content
     を produce、汎用独語 base capability の全面 forgetting は未確認

- **採用度**: **低** (en converge + eval_loss 改善 で反証多数)

#### H2: bilingual corpus interference (refine: **trilingual**)

- **evidence-for**:
  1. DA17-4 で `per_language_weighted_mass`: de 38.5% / en 21.6% /
     **ja 38.9%** / mixed 1.0%。勾配 77% が非英語、ja が verdict
     不可視の "silent gradient sink"
  2. en (21.6%) は最小 mass + base model の native strength に近い →
     converge しやすい (DA17-1 en 4/4 Δ < 0 と整合)
  3. de (38.5%) は ja (38.9%) と capacity 競合 → de signal が薄まる
     (rank=8 limit)
- **evidence-against**:
  1. v3 も同 corpus 分布 (`weight-audit.json` v3 版未確認だが PR-2 fix
     前は weight 数学的相殺 → effectively uniform sampling) で de Δ は
     **−0.38** (MPNet) と若干 convergent。同じ "trilingual corpus" で
     v3 は de convergent、v4 は de divergent → corpus 分布単独では
     v3→v4 flip を説明できない (weight 体制変更 = PR-2 fix が flip の
     必要条件)。Weighted fix が必要十分条件かは不明、H4 と一部重複
     する evidence
  2. 純粋 bilingual (en/de のみ) コーパスでも同 flip が起きる可能性は
     未検証 = 「ja interference」を切り分けるには ja drop control 実験
     (= PR-5 β) が必要。本 ADR forensic だけでは H2 を独立に確証
     できない
  3. (旧 #3 は H2 evidence-for だった内容で混入していたため削除、
     Codex MEDIUM-2 反映: 「en converge + de degrade は H2/H4 と整合」
     は反証ではなく支持)

- **採用度**: **中** (de 38.5% + ja 38.9% の trilingual 構造は確実、
  capacity 競合の direct evidence は H4 / H3 と重複)

#### H3: corpus 内分布 mismatch (top_5_pct=12.5% = weights too uniform、de_monolog signal 弱い)

- **evidence-for**:
  1. DA17-4 で `audit_top_5_pct=0.1249` (gate ≤0.35 から大きく低)、
     `audit_n_eff/n=76.6%` (高 uniformity)
  2. de_monolog n=750 / 5693 = 13.0%、coef=0.35 で weight up しても
     最大 weight 3.77×。Akademie-Ausgabe の 17 世紀 syntax を transfer
     するには signal 不足
  3. DA17-2 sample 6 / 9 の文法 error + DA17-3 Burrows reduction%
     negative = function-word 分布の learning incomplete (Akademie
     signal が encoder weight に深く沈み込まなかった)
- **evidence-against**:
  1. `weight_max=3.77` で aggressive に上げられた example は存在 →
     その 285 件 (top_5_pct_count) が de_monolog に集中するなら
     signal は十分のはず。実際の集中度未検証 (top_5_pct example の
     言語別内訳が weight-audit に未記録)
  2. en も同じ uniform 体制で converge した (DA17-1 4/4 Δ < 0) →
     uniform 単独では en/de 非対称を説明できない

- **採用度**: **中** (H2/H4 と相互補強、独立 explanation 力は限定的)

#### H4: trilingual capacity competition (refinement of H2: ja 38.9% mass dilutes de gradient under rank=8)

- **evidence-for**:
  1. DA17-4 で ja mass 38.9% ≈ de mass 38.5% (ほぼ同等)、verdict
     不可視 = silent sink
  2. DA17-1 で lex5 (non-semantic) でも de Δ +0.22 = capacity 側の
     signal、semantic-encoder noise 単独ではない
  3. en (21.6% mass、base に近い) が converge した方向は capacity
     allocation が en に流れた示唆。rank=8 で 3 言語学習 → de が薄まる
- **evidence-against**:
  1. **純粋 capacity なら rank=16 で解決** が予測だが、ja の silent
     mass を残したまま rank=16 ADOPT すると **mask** したまま誤った
     ADOPT を出す risk
  2. v3 → v4 で en が **改善** したのは WeightedTrainer fix が weight
     を gradient に乗せた直接効果。Weighted fix なしの v3 は uniform
     近似で「全言語等価学習」、de が偶然マシだった可能性 = capacity
     非依存

- **採用度**: **高** (H2 と相互補強、ja silent sink 構造は新規発見で
  PR-5 scope に直結)

#### H5: style register mismatch (Akademie-Ausgabe formal 18.-Jh-Deutsch ≠ stimulus 現代会話独語; LoRA produces hybrid register encoder treats as off-distribution)

- **evidence-for**:
  1. DA17-2 sample 5 / 8 で LoRA-on は **aphoristic Critique-style
     cadence** ("Was zählt, ist die Handlung."、"Geschmack ist die
     sinnliche Anschauung der Freiheit.") を採用、no-LoRA は long
     hedged な現代独語 style → register shift 明白
  2. DA17-2 sample 6 / 9 で **文法 agreement error** = function-word
     declension が Akademie-Ausgabe 18 世紀 syntax と現代独語の hybrid
     になっている (LoRA が完全に register transfer 失敗)
  3. DA17-3 Burrows reduction% Δ v3→v4 = +0.41pt (slight 改善) だが
     依然 −1.54% = LoRA-on が Akademie reference より **遠い**
     function-word 分布。content vocabulary は Akademie 寄せだが
     function-word は寄せきれず → encoder には「Kant 風 content × 現代
     function-word」の hybrid と映る → off-distribution = Vendi
     semantic diversity 増 (DA17-1 de Δ MPNet +1.50)
  4. v3 weighted fix 前の uniform 学習では同 hybrid 化が緩く起きていた
     可能性、Weighted fix で de_monolog signal が gradient に強く乗り
     hybrid 化が **悪化** した
- **evidence-against**:
  1. en には対応する archaic 英語 style training なし → H5 単独なら en
     も同じ hybrid 化リスクがあるはずだが、en は converge (DA17-1 4/4
     Δ < 0)。但し en training data の corpus 内訳は dialog (現代会話)
     → en 側に「register shift 試行」が無いので不問
  2. Burrows function-word distance は statistical measure で、LoRA が
     specific function-word を多用するかは未測定。grammar error 観察
     (DA17-2 #3) は qualitative であり quantitative function-word
     distribution の直接 evidence ではない
  3. H5 dominant なら de_monolog mass を 100% にすれば解消するはずだが、
     現実には dialog 部分も必要 (eval stimuli は dialog form)。
     register fix は不完全になる可能性

- **採用度**: **最高** (DA17-2 paired sample 10 件全てで register
  shift 観測 + DA17-3 Burrows 内訳と整合 + DA17-5 で prompt 同一
  = adapter 効果限定)

### 仮説優先順位 (summary)

| H | 採用度 | 主証拠 | dominant 仮説 |
|---|---|---|---|
| H1 catastrophic forgetting | 低 | grammar error (DA17-2) | 反例多数 |
| H2 trilingual interference | 中 | per-lang mass DA17-4 | refinement = H4 |
| H3 distribution mismatch | 中 | top_5_pct DA17-4 | H4 / H5 を支援 |
| **H4 capacity competition** | **高** | ja silent sink (DA17-4) | dominant 候補 |
| **H5 style register mismatch** | **最高** | paired sample (DA17-2) + Burrows (DA17-3) | dominant 候補 |

### 採用

- **dominant**: H5 (style register mismatch) を主因 + H4 (trilingual
  capacity competition、ja silent sink) を共同因として採用。H3 は
  H4/H5 の補強要因として保持、H1 と H2 (純粋 bilingual 形) は反例
  多数で archive。
- 5 仮説全てを decisions.md に保存することで、future iteration
  (kant_r16_v1 / nietzsche / rikyu 等) で再評価可能化。

### 影響範囲

- DA17-7 PR-5 scope 選定で β (corpus rebalance、H4/H5 を直接対処) を
  最優先候補に。ε (prompt-side fix、H5 のうち content vocabulary 側
  のみ対処) を低コスト試行候補に。α (rank=16、H4 を一部解消するが
  H5 function-word side は未解決) を fallback に。

## DA17-7: revised PR-5 scope decision (初回案 + `/reimagine` 待ち)

- **判断日時**: 2026-05-17 (初回案、`/reimagine` 後に最終化)
- **背景**: DA17-1 〜 DA17-6 で root cause を H5 (style register
  mismatch、function-word side) + H4 (trilingual capacity competition、
  ja silent sink) と特定。これに基づき PR-5 scope を 5 候補
  (α/β/γ/δ/ε) から narrow down する。CLAUDE.md「Plan 内 /reimagine 必須」
  に従い、初回案 (本セクション後半) と再生成案 (Phase 3 で別 subagent
  起動、本 decisions.md DA17-7 末尾に追記) を併記の上で最終確定する。

### 5 候補比較 table

| 候補 | scope | envelope | 検証 H | 失敗時 pivot | 期待効果 |
|---|---|---|---|---|---|
| **α** rank=16 spike | LoRA rank 8 → 16、`--max-lora-rank 16` SGLang fp8 fit spike + retrain + verdict | GPU ~6–8h | H4 (capacity) | β or γ | function-word 学習に capacity 余裕、但し ja silent sink 解消せず |
| **β** corpus rebalance | (i) ja mass を 38.9% → 10% (or 0%)、(ii) de_monolog coef を 0.35 → 0.60 / weight cap を 5x まで上げ、(iii) WeightedTrainer fix を維持、(iv) rank=8 のまま retrain + verdict | retrain ~3–5h + audit | H4 + H5 (function-word) | α or γ | de_monolog signal 強化で Akademie function-word 学習促進、ja silent sink 削減 |
| **γ** language-aware LoRA | en と de で別 LoRA adapter、prompt-conditional routing or stimulus language-aware multi-adapter load | 構造変更大 ~1–2 週間 | H4 + H5 (構造) | Plan C 寄り | en/de の register / capacity を完全分離、function-word 学習も言語別 |
| **δ** Plan B 廃止 retrospective ADR | kant Plan B 全体 (v3 / v4 / DA-14 / DA-16 / DA-17) の after-action review、Plan A への back-port 検討 | doc-only ~2h | — (meta) | — | Plan B 設計全体の根本再評価、nietzsche / rikyu の Plan B 採否判断 |
| **ε** prompt-side fix | `personas/kant.yaml` or `tier_b_pilot.py:224-247` の system prompt にドイツ語固有指示 ("In deutscher Antwort: formales 18.-Jh-Deutsch im Stil der Akademie-Ausgabe verwenden, einschließlich klassischer Satzgliederung und gehobener Lexik") を追加、現 v4 adapter のまま eval 再採取 | spike ~1–2h + verdict 再計算 ~30min | H5 (content 側) | β or α | system prompt で register override、function-word 分布まで届くか未知 |

### 各候補の dominant 仮説対応

- **H4 (capacity competition)**: α / β / γ で対応可
- **H5 content side** (Kantian vocabulary): 既に LoRA-on で達成済
  (DA17-2 観察 #1)、PR-5 介入で更に伸ばす必要は薄い
- **H5 function-word side** (Akademie syntax / declension): β / γ で
  対応可、α では rank 拡張で間接的に届く可能性、ε は届かない可能性高
- **H1 (forgetting)**: 反例多数で primary 仮説でないため対応不要

### 初回案 recommendation: **β-first → ε-spike-parallel → α-fallback**

採用順序の根拠:

1. **β を first candidate に**: H5 function-word side + H4 (ja silent
   sink) を直接 address。retrain 3–5h は α (6–8h) より短く、forensic
   切り分けが clean。corpus 設計変更で **新 LoRA `kant_r8_v5_rebal`**
   を生成、v4 v5 forensic 対比で β の効果を測定。
   - 具体: `audit_de_en_mass` を 0.8〜0.9 まで上げる (= ja ≤ 10%)、
     `de_monolog_coef` を 0.35 → 0.60、`weight_max` cap を 3.77 →
     5.0、その他 hyperparam は v4 と同条件 (rank=8 + WeightedTrainer
     `.mean()` fix + same seed 42)。
   - 期待結果 (ADOPT): de within-language Δ_de が negative 方向へ
     converge、Burrows reduction% が positive (Akademie 寄せ) 方向。
   - 期待結果 (REJECT): rank=8 capacity が ja drop しても de+en 学習に
     不十分 → α (rank=16) へ pivot で **clean な capacity 切り分け**
     (β で corpus 側既に最適化 → 残る変数は rank のみ)。

2. **ε を parallel spike として**: 本 PR-5 の retrain と並行で
   ~1–2h spike として実施可能 (GPU 不要、v4 adapter のまま eval shard
   再採取)。H5 content side の検証 cost が低く、prompt 指示で
   function-word 分布まで届くかの empirical 検証ができる (届けば
   PR-5 ADOPT は ε 単独で達成、届かなければ β を主軸として続行)。
   - **ε と β を併用** する PR 構成: PR-5 = β retrain + ε prompt
     fix を **両方** 適用した kant_r8_v5_rebal_promptfix で初回 verdict、
     片方 / 両方 を ablate して contribution 切り分けは PR-6 で。

3. **α を fallback に**: β + ε で REJECT したら α へ。current corpus
   (ja 38.9% mass) を残したまま rank=16 に行くと ja silent sink を
   mask する risk があるため (DA17-6 H4 evidence-against #1)、β
   先行が安全。

4. **γ は Plan C 寄り**: 構造変更大 (multi-adapter + prompt routing)、
   ~1–2 週間 envelope。β + ε + α 全敗時の δ retrospective を経た
   structural pivot 候補。本 PR-5 では起こさない。

5. **δ は将来 retrospective**: nietzsche / rikyu Plan B 展開可否は
   kant ADOPT 確定後 / Plan B 全敗時 / 中間判断時に別 ADR で検討。

### 初回案 採用案

**PR-5 scope = β (corpus rebalance) + ε (prompt-side fix) を併用、
rank=8 維持で retrain**

- 新 adapter 名: `kant_r8_v5_rebal_promptfix`
- 主要 hyperparam 変更:
  - corpus: `audit_de_en_mass` 目標 0.85 (現 0.6010)、ja mass ≤ 10%
  - weighting: `de_monolog_coef` 0.35 → 0.60、`weight_max` cap 5.0
  - prompt: `personas/kant.yaml` または `tier_b_pilot.py:224-247` の
    system prompt にドイツ語固有 register 指示 1 行追加
- 同 verdict pipeline (4 eval shard + 4-encoder rescore + Burrows +
  ICC + verdict)
- ablate plan: β + ε ADOPT 後、PR-6 で β-only / ε-only / β+ε の
  3 way ablation で contribution 切り分け (発展)

### 不採用案 + defer reason

- **α rank=16 spike**: defer reason = current corpus の ja silent sink
  (DA17-4) を解消しないまま rank 拡張すると **mask** したまま誤
  ADOPT する risk (DA17-6 H4 evidence-against #1)。β REJECT 後に
  「rank=8 corpus optimum でも capacity 不足」が示せれば α に pivot。
  既存 prompt `next-session-prompt-FINAL-pr5-rank16-spike-reject.md`
  は **DEFERRED 注記** で保持、α 採用時に再活用可能化。
- **γ language-aware LoRA**: defer reason = 構造変更大 (~1–2 週間)。
  β + ε + α 全敗時の δ retrospective 経由で起動。
- **δ Plan B retrospective**: defer reason = kant ADOPT 確定後 or
  Plan B 全敗確定後の retrospective で起動。本 PR-5 段階は早すぎる。

### `/reimagine` 適用 (Phase 3 実施結果)

CLAUDE.md「Plan 内 /reimagine 必須」遵守のため、本 ADR 結論を Plan
subagent に zero-base で再生成させた。subagent には初回案 (β + ε 併用)
を見せず、forensic facts (DA17-1〜DA17-5) と 5 候補 + hard 制約のみ
渡した。

#### `/reimagine` 別案 (Plan subagent 出力 verbatim、2026-05-17)

**root cause 仮説 (zero-base 再生成)**:

- **H1 ja over-weighting による de 信号希釈** [dominant]: 「weighted
  ja=38.9% (de=38.5%) で勾配の約 4 割が verdict 不可視言語に流れている。
  eval window (n=100) で ja shard は統計力不足。en は Latin 文字 token
  共有で副次的に lift するが、de morphology (case/gender agreement) は
  ja から転移しない。de-only 悪化 + en 改善の非対称を最も簡潔に説明」
- **H2 rank=8 capacity 不足 (Kantian 内容語 + de morphology の同時習得
  不能)** [secondary]: 「LoRA-on は Kantian lexicon を獲得しているが
  文法 agreement で失敗 (heißen → heißer、transzendentale →
  transzendentalen)。但し en は同 rank で改善 → capacity 単独原因なら
  en も劣化するはずで、H1 と co-occurring だが secondary」
- **H3 corpus de_monolog の register 偏向** [tertiary]: 「Vendi 上昇 =
  多様性増加なので "悪化" と即断できない可能性も含むが、DA-14
  thresholds 上 reject」
- **H4 prompt-side 言語別 register 指示欠落** [contributory, not root]:
  「no-LoRA control も同一 prompt で de を正しく扱えており、root では
  なく amplifier」
- **H5 WeightedTrainer の per-token reduction が長い de 文を過小評価**
  [low confidence]: 「frozen により検証不能、defer」

> 注: subagent の H1〜H5 numbering は本 decisions.md の H1〜H5
> numbering とは独立 (subagent の H1 = 本 ADR の H4、subagent の H2 =
> 本 ADR の H3 partial、subagent の H4 = 本 ADR の H5 partial 等)。

**新規 hypothesis 提案 (本 ADR H1-H5 を超える観点)**:

- **H6 tokenizer-level de subword 断片化 unbalance**: 「train corpus と
  eval stim で de tokenization 統計が乖離していないか。`weight-audit.json`
  は char/utterance ベースで token 数を見ていない可能性。長 compound
  名詞が ja より token 多く消費し、effective gradient share が weighted
  mass と乖離する余地」
- **H7 v3→v4 で n_eff/n=76.6% が示す sample-level imbalance**: 「裾の
  特定 utterance (おそらく aphoristic 短文) が effective を持っていない
  可能性。β 実施時に per-utterance weight floor 検討余地」
- **H8 eval seed/温度 noise**: 「Vendi Δ +1.4968 (MPNet de) は他 encoder
  より一桁大きく単一 outlier 疑い。β 前に同 v4 adapter で seed 変えた
  re-eval 1 round で MPNet de Δ が再現するか確認すべき (GPU 30min、
  安価)。これを欠くと β 実施しても "元々 noise だった" と区別不能」

**PR-5 scope 推奨 (zero-base 再生成)**:

- **第一推奨: β corpus rebalance 単独 (rank=8 維持、ja drop + de
  増強)**、期待 ADOPT 確率 **45–55%**
- **第二推奨 (β 失敗時 pivot 用に温存): ε prompt-side fix を spike
  として β と分離**。同時実施は交絡発生し因果分離不能
- **α rank=16**: H2 secondary なので先行投資非効率
- **γ / δ / ε 単独**: defer

**PR-5 envelope 提案**:
- H8 re-eval 30min → β retrain 3-5h → DA-14 verdict eval 1-2h、総 ~6h GPU、1 round
- β success → ADOPT
- β failure 1 (de 改善あるが gate 未達) → α rank=16 を β corpus 上で
- β failure 2 (de 改善なし or en 悪化) → γ or δ retrospective

#### 初回案 vs `/reimagine` 別案 — 差分の本質

| 観点 | 初回案 (本 ADR DA17-7 前半) | `/reimagine` 別案 |
|---|---|---|
| dominant 仮説 | H5 (style register mismatch) + H4 (trilingual capacity) | H4 相当 (ja silent sink) + H3 相当 (rank=8 capacity) |
| PR-5 scope | β + ε 併用、kant_r8_v5_rebal_promptfix | β 単独、kant_r8_v5_rebal、ε は β-fail pivot に defer |
| pre-check | なし | **H8 seed-variance re-eval (30min spike)** で MPNet de Δ outlier 確認 |
| 新規 hypothesis | DA17-4 で elevated ja 38.9% anomaly | H6 (tokenizer subword)、H7 (sample-level imbalance)、H8 (eval noise) |
| ablate 戦略 | PR-6 で β-only / ε-only / β+ε 3-way ablate | PR-5 から β isolated、ε は PR-6 contributing |

**主要な差**:
1. **dominant 仮説の位置付け**: 初回案は H5 (style register) を主因と
   見て ε を活かす方向、別案は H4 (ja silent sink) を主因と見て corpus
   側で isolated に test する方向。**両方とも H4/H5 が dominant という
   点は一致**、対処方法が β-bundled (初回) vs β-isolated (別案) で
   分かれる。
2. **causal isolation の重み**: 別案は「β + ε 併用は contribution 切り
   分け不能」と明示。これは強い構造的指摘で、再現性 / forensic 連続性
   を重視する本 project (PR-2/3/4 で確立した「単一介入ごとに verdict
   再計算」pattern) と整合。
3. **H8 pre-check の追加価値**: MPNet de Δ +1.4968 の CI は
   diff_lo=−0.9567 で 0 を跨ぐ (decisions.md DA17-1 抽出結果より)。
   別 seed で re-eval して MPNet de Δ が +1.0 以上を再現するか
   確認する 30min spike は **β retrain 3-5h を skip できる可能性**
   を提供。低コスト高情報。

### 最終採用 (両案 hybrid、`/reimagine` 結論を主軸に refine)

**PR-5 scope = β corpus rebalance 単独 (rank=8 維持) + H8 pre-check**

採用根拠:

1. **causal isolation を優先** (別案の構造的指摘を accept): β + ε 併用は
   contribution 切り分け不能 → 本 PR-5 は β 単独で実施、ε は β verdict
   結果に応じて defer or PR-6 で start。なお ここでの **「H1 ja silent
   sink」は subagent 別案 numbering の H1** (= 本 ADR の H4 trilingual
   capacity competition、`/reimagine` 別案 verbatim 引用と本 ADR
   numbering の衝突回避のため明示、Codex MEDIUM-3 反映)。
2. **H8 pre-check を mandatory に**: 別案の novel contribution。
   v4 adapter のまま **SGLang sampling seed を 3 seed (0 / 100 / 1000)
   で stim shard を新規生成** (bootstrap seed 変更のみでは generation
   段階の noise を検証できない、Codex HIGH-1 反映)。各 seed で
   LoRA-on shard + matched no-LoRA shard を再採取 + 4-encoder rescore
   + within-language d 再計算 (GPU 30min × 3 = 1.5h + rescore 30min =
   合計 ~2-3h)。
   **指標と判定基準** (Codex HIGH-2 反映、verbatim 明定):
   - 指標名 = `mpnet_de_within_language_d` = 各 seed の rescore JSON
     `within_language.de.cohens_d`
   - 3 seed 全て `>= +1.0` → 再現、β retrain 続行
   - 1 seed 以上で `<= +0.5` → noise 確定、β skip、本 PR-5 を「H8 棄却
     ADR」に rescope (DA-18 で root cause 再検討)
   - gray zone (+0.5 〜 +1.0): 追加 seed 試行 (2000/3000/5000)、なお
     gray zone なら **β を保守的に続行** + DP5-1 に gray zone evidence
     を記録 (eval noise が部分的に contribute する root cause の併存)
3. **β 単独で rank=8 維持**:
   - corpus 変更: `audit_de_en_mass` 目標 0.85 (現 0.6010)、ja mass
     を 10% 以下、de_monolog coef 0.35 → 0.60、weight_max cap 5.0
   - hyperparam その他は v4 と同条件 (rank=8 + WeightedTrainer
     `.mean()` fix + seed 42 + same eval_loss tracking)
   - 新 adapter 名: `kant_r8_v5_rebal`
4. **ε defer**: 「β success ADOPT-marginal」or「β REJECT, MPNet de Δ
   再現 (= H8 棄却) + en/de gap 残存」のいずれかで PR-6 = ε spike を
   start (h5 = 1-2h)。「β success ADOPT-clean」なら ε 不要。
5. **α defer**: 「β REJECT + corpus rebalance 後も capacity 不足 evidence
   (en 4/4 converge 維持 + de improvement 観測あるが gate 未達)」で
   PR-6 or PR-7 = α rank=16 を **β corpus baseline 上で** 起動 (capacity
   と corpus を分離して切り分け)。
6. **γ / δ defer**: β / ε / α 全敗時の retrospective ADR (δ) 経由で
   γ or kant ABANDON 判断。

### 不採用 / defer 理由 (final、両案統合)

- **初回案の β + ε 併用**: 別案の「contribution 切り分け不能」指摘で
  reject。Forensic 連続性を重視する本 project 設計と integrity-of-test
  原則に従い、isolated β を採用。
- **α rank=16 単独 spike**: H8 で MPNet de Δ noise が否定されない限り、
  capacity expansion は ja silent sink を mask する risk (DA17-6 H4
  evidence-against #1)。β で corpus baseline を整備した後に capacity
  spike が clean。
- **γ language-aware LoRA**: 構造変更大 (1-2 週間)、β + α + ε 全敗時の
  Plan C 候補。
- **δ Plan B retrospective ADR**: kant ADOPT 確定後 or Plan B 全敗確定
  後の retrospective、本 PR-5 段階は早すぎる。
- **ε 単独**: prompt fix は no-LoRA も同 prompt で de を正しく扱えて
  いる (DA17-5 同一性検証で確認) ため、root cause を adapter で覆い
  隠す risk が指摘された。β failure 後の低コスト spike として温存。

### 新規 hypothesis (H6 / H7 / H8) の本 ADR への取り込み

別案で提案された H6 / H7 / H8 は本 ADR の **H1-H5 numbering とは独立**
(衝突回避)。本 ADR では:

- **H8 (eval noise)**: PR-5 pre-check として採用 (mandatory 30min × 3
  seed spike)。本 decisions.md DA17-7 採用案の主構成要素。
- **H6 (tokenizer subword imbalance)**: β retrain audit で
  per-language **token** weighted mass を計算する (`weight-audit.json`
  に追加 field 提案、PR-5 scope に含める)。char/utterance ベースの
  weighted mass は計算済だが、token ベースで再計算すると ja の effective
  gradient share が想定より大きい / 小さい可能性。
- **H7 (sample-level imbalance、aphoristic 短文の effective ゼロ)**:
  β retrain で per-utterance weight floor を導入する選択肢として記録。
  weight_p10=0.5528 → floor=0.7 等で短文の signal を保護。但し本 PR-5
  ではまず ja drop を優先、H7 対応は PR-6 で別途検討。

### PR-5 envelope と失敗時 pivot (final)

**envelope**: H8 pre-check ~2h (3 seed × 30min GPU spike + rescore) →
β corpus build ~30min → β retrain ~3-5h → DA-14 verdict eval pipeline
~3h。**total ~9h、1 GPU session 内 or 2 session 分散可能**。

**failure pivots**:
- **H8 pre-check failure (MPNet de Δ noise 確認)**: β retrain skip、
  本 ADR DA17-7 を再評価 (root cause が "encoder noise" にぎゃっぱ
  → DA-14 thresholds の validity を別 ADR で検討)
- **β verdict REJECT、de 改善あるが gate 未達**: α rank=16 を β corpus
  baseline 上で start (capacity 切り分け clean)
- **β verdict REJECT、de 改善なし or en 悪化**: H1 (ja silent sink)
  棄却 → γ language-aware LoRA or δ Plan B retrospective へ shift
- **β verdict ADOPT-marginal (gate ぎりぎり)**: PR-6 で ε prompt fix
  spike を margin 拡張用に start
- **β verdict ADOPT-clean**: kant Plan B 完了、PR-6 で HF Hub push +
  nietzsche / rikyu Plan B 展開検討 ADR

### 影響範囲 (final)

- PR-5 (本 ADR merge 後):
  - **新規**: `scripts/m9-c-adopt/h8_seed_variance_check.{sh,py}` (H8
    pre-check 用 ad-hoc script)
  - **改変**: `scripts/m9-c-adopt/build_*.py` (or 該当 corpus build
    script) の sample 比率 (ja ≤ 10%) + `WeightedExampleBuilder` の
    `de_monolog_coef` 0.35 → 0.60 + `weight_max` cap 引き上げ
  - **改変なし**: `personas/kant.yaml` / `tier_b_pilot.py` (ε defer)
  - 新 adapter: `kant_r8_v5_rebal`
- 後続 PR-6 候補:
  - ε prompt fix (β ADOPT-marginal or β REJECT で MPNet de Δ 再現時)
  - α rank=16 spike on β corpus (β REJECT で capacity 仮説残存時)
  - HF Hub push (β ADOPT-clean 時)
- nietzsche / rikyu Plan B 展開は β ADOPT 確定後 or Plan B 全敗確定後
  まで blocked

### 見直しタイミング (final)

- **H8 pre-check 結果**: MPNet de Δ が seed 0 / 100 / 1000 で全て +1.0
  以下なら本 DA17-7 採用案を再評価 (β 不要、別の root cause analysis
  へ shift)
- **β verdict 結果**: REJECT 時の pivot tree は上記 failure pivots 通り
- **新規 evidence (token-level audit、PR-2 fix の long-term effect、
  base model upgrade 等)**: 別 ADR (DA-18) で本 DA-17 結論を再評価


### トレードオフ (初回案)

- **β は corpus 設計変更が必要**: ja mass 38.9% → 10% は build_*
  script の sample 比率変更 + `de_monolog_coef` chunking 再計算が
  必要。retrain 自体 (~3-5h) + build (~30min) で envelope 拡大。
- **ε は prompt 改変で v3 / v4 比較性が崩れる**: 同 v4 adapter で
  prompt 変更すると、PR-2/3/4 forensic 鎖との直接対比が崩れる。
  PR-5 verdict は **新 baseline** として位置づけ、nietzsche / rikyu
  Plan B でも同 prompt structure を採用する必要あり (整合性確保)。
- **rank=8 維持の risk**: β + ε でも capacity 不足が remaining なら
  rank=16 spike (α) が必要、本 PR-5 で REJECT → PR-6 α への二度手間。
  但し DA17-1 で「en converge 観測」は capacity 余裕の証拠 (capacity
  fully used なら en も degrade すべき) → rank=8 + corpus 最適化で
  ADOPT 可能性は高い見込み。

### 影響範囲 (初回案)

- PR-5 (本 ADR merge 後): `scripts/m9-c-adopt/build_*` の corpus 比率
  + `WeightedExampleBuilder` coef + `personas/kant.yaml` (or
  `tier_b_pilot.py`) の system prompt 1 行追加。retrain + verdict
  pipeline は v4 と同条件。
- 後続 PR-6 (β + ε 採用後): HF Hub push + nietzsche / rikyu Plan B
  展開検討 ADR。
- 不採用案 α / γ / δ の next-session prompt 起票は本 PR-5 ADOPT 後に
  状況に応じて。

### 見直しタイミング (初回案)

- PR-5 verdict が REJECT で direction disagreement が残った場合、
  DA17-6 H4 evidence-against #1 (ja silent sink を rank=16 で mask
  する risk) は β 段階で既に解消済 → α へ pivot 妥当。
- PR-5 verdict が ADOPT で gate margin が薄い場合、ablate (β-only /
  ε-only) で contribution 切り分け、margin 拡張は別 ADR で検討。
- PR-5 retrain で eval_loss が initial を大きく上回る (regression)
  場合、β の corpus 設計が training stability を壊した可能性 → 再
  Plan mode で β の hyperparam 再評価。
