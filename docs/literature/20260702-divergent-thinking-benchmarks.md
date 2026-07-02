# 文献カード集: 発散的思考/新規性の評価手法 + 認知探索/探索-活用トレードオフ

> サーヴェイ目的: M13-ES arc が繰り返しぶつかっている「評価器 (scorer) の自己循環問題」
> (ES-4: semantic rarity scorer が leave-anchor-out audit で崩落 / ES-2: 記憶組み替えの新規性を
> 測る estimand が構造的低検出力) に対して、認知科学・行動経済学の確立された評価手法・理論から
> 非循環な設計の手がかりを探す。5 本を落合フォーマットでカード化。

---

# 文献カード: SemDis — 多重意味空間アンサンブルによる発散的思考の自動採点

- **日付**: 2026-07-02
- **トピック**: divergent-thinking-benchmarks
- **出典**: [7] (docs/references.md)
- **key**: DOI:10.3758/s13428-020-01453-w

## 1. それはどんなもの?
Alternate Uses Task (AUT) 等の発散的思考課題の回答を、刺激語 (cue) と回答語の **意味距離
(semantic distance)** で自動採点する公開プラットフォーム SemDis。5 つの独立した意味空間
(LSA/GloVe/word2vec 等の異なる訓練コーパス・アルゴリズム) でコサイン距離を計算し、その平均
(またはベイズ推定による重み付き合成) を採点値とする。

## 2. 先行研究と比べてどこがすごい?
従来の人手採点 (rater が「独創的か」を主観評価) はコストが高く rater 間バイアスも大きい。単一の
意味空間による自動採点は、その空間固有のノイズ・バイアスに引きずられるリスクがあったが、
SemDis は **複数の独立空間のアンサンブル** によりこの単一モデル依存を緩和し、人手採点との
相関 (収束的妥当性) を実証した。

## 3. 技術や手法の肝はどこ?
採点対象は **刺激語↔回答語の距離** (within-item、2 項間) であり、ES-4 が試みた「生成テキスト↔
自前構築 common-use reference corpus」という **self-built anchor への距離** とは構造が異なる。
SemDis の「意味空間」は既存の大規模独立コーパスから訓練された固定モデルであり、評価対象の生成
プロセスとは因果的に無関係 (=非自己言及)。複数空間の平均を取ることで単一空間の偶発的な
歪みも緩和する。

## 4. どうやって有効だと検証した?
人手採点との相関 (収束的妥当性)、他の確立された創造性指標との相関 (併存的妥当性) で検証。
Behavior Research Methods 誌の方法論論文として、複数データセット・複数意味空間の比較を報告。

## 5. 議論はあるか?
後続研究 (Beyond Semantic Distance, Organ et al. 系) は LLM ベースの採点が SemDis を上回ると
報告しており、意味空間の選択自体が結果に影響することも指摘されている (Hogrefe誌の Composites
論文)。また SemDis も「意味的に遠い = 独創的」という前提自体は ES-2/ES-4 と共有しており、
この前提が破綻するケース (無意味な単語の羅列が高スコアになる等) への頑健性は別途検証が必要。

## 6. 次に読むべき論文は?
Organisciak et al. "Beyond Semantic Distance: Automated Scoring of Divergent Thinking Greatly
Improves with Large Language Models" (LLM ベース採点との比較、ES-4 の LLM-judge 設計に直結)。

---
## やり残し (1 行)
> ES-4 が崩壊した「self-built anchor への距離」でなく「独立外部コーパス由来の固定意味空間との
> 距離」という設計 (SemDis の肝) を、memory-recomposition seam の代替 estimand 候補として検討
> する余地がある → research-positioning.md §8 の re-entry door 候補として記録可。

---

# 文献カード: Divergent Association Task (DAT) — 集合内 pairwise 距離による発散的思考測定

- **日付**: 2026-07-02
- **トピック**: divergent-thinking-benchmarks
- **出典**: [8] (docs/references.md)
- **key**: DOI:10.1073/pnas.2022340118

## 1. それはどんなもの?
被験者に「できるだけ意味的に無関係な名詞を 10 個挙げよ」と指示し、挙げられた 10 語間の
**pairwise 意味距離 (GloVe embedding cosine) の平均** を発散的思考スコアとする単純な課題
(Olson et al. 2021, PNAS)。N=8,914 の大規模検証。

## 2. 先行研究と比べてどこがすごい?
AUT (Alternate Uses Task) 等は用途の「有用性」判定を要し採点が複雑だが、DAT は
**単語間距離のみ** で完結し、既存の確立された創造性尺度 (AUT、Big Five の openness 等) と
同等以上の予測力を大規模サンプルで示した。課題設計そのものが極めて単純 (1 分程度) で
自動採点が容易。

## 3. 技術や手法の肝はどこ?
新規性の定義が **「外部の参照コーパスからの距離」でなく「自己生成集合の内部 pairwise 距離」**
である点が構造的に重要。ES-4 の circularity (自前 anchor への self-referential 判定) を
そもそも要求しない設計。ただし ES-2 も本来同じ「集合内部」の発想だったが、ES-2 は **離散
tuple の集合メンバーシップ (Jaccard/JS)** で識別不能に陥った。DAT は **連続値のコサイン距離の
平均** という滑らかな統計量を使う点が異なり、これが離散台の飽和問題を回避している可能性が
ある。

## 4. どうやって有効だと検証した?
8,914 名の大規模オンライン調査で、DAT スコアと (a) 他の確立された創造性テスト、(b) 職業的
創造性の自己申告、(c) 趣味の多様性等との相関を報告。予測的妥当性は既存尺度と同等以上。

## 5. 議論はあるか?
「無関係な単語を並べる」ことと「実際の創造的問題解決」の関係は間接的 (construct validity の
議論が残る)。単語想起という言語タスクに閉じており、ERRE の空間移動→記憶組み替えという
非言語的プロセスへの直接移植は自明でない。

## 6. 次に読むべき論文は?
Constructional Divergent Association Task (CXN-DAT) — 文脈依存版への拡張、意味距離だけで
なく構文的多様性を組み込む試み。

---
## やり残し (1 行)
> memory-recomposition seam の estimand を「離散台上の集合比較 (ES-2 の失敗パターン)」でなく
> 「連続値 pairwise 距離の集合内平均 (DAT パターン)」に設計し直せば、ES-2 の飽和問題を
> 回避できる可能性がある → 次回実装セッションでの estimand 代替案として検討価値あり
> (ただし本 ADR は既に ratify 済のため、これは re-entry candidate として保全するに留める)。

---

# 文献カード: Optimal Foraging in Semantic Memory — 記憶探索と空間採餌の構造的同型性

- **日付**: 2026-07-02
- **トピック**: divergent-thinking-benchmarks
- **出典**: [9] (docs/references.md)
- **key**: DOI:10.1037/a0027373

## 1. それはどんなもの?
動物の空間採餌 (optimal foraging theory、patch-leaving/Marginal Value Theorem) の数理モデルを
記憶検索 (意味流暢性課題: 3 分間で動物名を可能な限り想起) にそのまま適用し、人間の記憶検索が
「局所探索→パッチ離脱→別領域への移動」という **空間採餌と同型の動的方策** に従うことを示した
理論的ノート (Hills, Jones & Todd, 2012, Psychological Review)。

## 2. 先行研究と比べてどこがすごい?
記憶検索と空間探索を「アナロジー」ではなく **同一の最適化問題として定式化** し、両者が
ドメイン汎用の探索制御プロセスを共有するという主張に定量的裏付けを与えた。BEAGLE 意味空間
モデル上で構築した「意味探索空間」での動的シミュレーションが、実際の人間の想起パターン
(パッチ内での高頻度・低距離想起→パッチ間移動での急激な意味距離ジャンプ) を再現。

## 3. 技術や手法の肝はどこ?
想起系列を意味空間上の軌跡として扱い、**パッチ内滞在時間・パッチ間移動 (switch) のタイミング**
を Marginal Value Theorem (現在パッチの収穫率が全体平均収穫率を下回った時点で離脱するのが
最適) で予測する。この「switch 検出」は連続的な意味距離の時系列から統計的に導出可能であり、
ERRE の `C` (idle recomposition の遷移パターン) 設計における **argmax セルでなく「パッチ切替
イベント」を channel として使う** という代替設計のヒントになりうる。

## 4. どうやって有効だと検証した?
意味流暢性課題の実データ (人間の想起系列) に対し、モデル予測の switch タイミング・想起順序を
比較し、ランダム探索や貪欲探索など他の探索方策よりも良い適合を示した。

## 5. 議論はあるか?
意味空間モデル (BEAGLE) 自体の構築方法への依存性、パッチ境界の定義の恣意性が指摘されうる。
また「空間採餌」と「意味検索」の同型性は経験的に強く支持されるが、これが LLM の埋め込み空間
上でも同様に成立するかは別途検証が必要 (ERRE の memory-recomposition seam が暗黙に前提として
いる部分)。

## 6. 次に読むべき論文は?
Hills (2015) "Foraging in Semantic Fields: How We Search Through Memory" — Hills 2012 の
後続レビュー、より広範な認知探索理論への統合。

---
## やり残し (1 行)
> ES-1 (空間移動→記憶検索) が暗黙に仮定している「移動と記憶検索は構造的に同型」という前提に
> 対し、Hills et al. は独立した実証的裏付けを与える先行研究として引用可能
> (research-positioning.md §3 の理論的アンカーとして追記候補)。

---

# 文献カード: Generalization guides human exploration in vast decision spaces — 汎化による新規性価値づけ

- **日付**: 2026-07-02
- **トピック**: divergent-thinking-benchmarks
- **出典**: [10] (docs/references.md)
- **key**: DOI:10.1038/s41562-018-0467-4

## 1. それはどんなもの?
巨大な (最大 121 本腕の) bandit 課題で、人間が未知の選択肢をどう探索するかを検証。
Gaussian Process による報酬の空間的汎化 (似た選択肢は似た報酬を持つと推定) と Upper
Confidence Bound (UCB) 型の「不確実性ボーナス」を組み合わせたモデルが、人間の探索行動を
最も良く説明することを示した (Wu, Schulz, Speekenbrink, Nelson & Meder, 2018, Nature Human
Behaviour)。

## 2. 先行研究と比べてどこがすごい?
従来の探索モデル (単純な ε-greedy や、選択肢ごとに独立な不確実性推定) は選択肢数が多い
「広大な意思決定空間」でスケールしないが、本研究は **類似構造への汎化 (generalization)** を
導入することで、少数の試行から広大な空間全体の価値を推定する人間の能力を説明した。

## 3. 技術や手法の肝はどこ?
「新規性」を単なる未探索フラグでなく、**汎化された不確実性 (どれだけ他の選択肢の情報から
遠いか)** として連続値で定義する。これは ERRE の C→D channel-conformance 設計における
「新規性」の定義 — argmax セルという離散的要約でなく、既知領域からの汎化距離という連続的
指標 — の代替候補になりうる。UCB 的な expected-improvement + novelty-uncertainty の両目的の
Pareto frontier 上に人間の選択の 65-80% が乗るという定量結果も、探索と活用の二軸分解の
妥当性を支持する。

## 4. どうやって有効だと検証した?
複数の bandit 実験 (選択肢数 1〜121) で人間の選択データを収集し、複数の計算モデル
(汎化あり/なし、UCB あり/なし) の尤度をベイズモデル比較で評価。汎化+UCB モデルが最も
高い説明力を示した。

## 5. 議論はあるか?
Author Correction (2020) が出ており、統計処理の一部修正が入っている (結論への影響は限定的と
されるが原典確認が必要)。また bandit 課題という抽象的な意思決定枠組みが、ERRE の空間移動や
記憶組み替えのような身体的・連想的プロセスにそのまま適用できるかは検証が必要。

## 6. 次に読むべき論文は?
Nature Human Behaviour の Author Correction (2020) 本体、および同著者らの後続研究
(社会的学習下での探索行動への拡張等)。

---
## やり残し (1 行)
> 「新規性」を離散カテゴリ (argmax セル) でなく汎化距離という連続値で定義する設計は、DAT
> カードと同じ方向性 (連続値化による離散台飽和の回避) を示唆し、memory-recomposition seam の
> 将来的な estimand 再設計候補として合流しうる。

---

# 文献カード: DMN の因果的操作と発散的思考の originality — 刺激研究による直接検証

- **日付**: 2026-07-02
- **トピック**: divergent-thinking-benchmarks
- **出典**: [11] (docs/references.md)
- **key**: DOI:10.1093/brain/awae199

## 1. それはどんなもの?
てんかん患者 13 名の頭蓋内電極 (stereo-EEG) を用いて、default mode network (DMN) の電気生理
学的活動を mind wandering 課題と Alternate Uses Task (AUT、発散的思考課題) で直接記録し、
さらに **直接皮質刺激によって DMN 領域を操作** し、AUT の originality (独創性) スコアへの
因果的影響を検証した (Bartoli et al., 2024, Brain)。

## 2. 先行研究と比べてどこがすごい?
これまでの DMN↔創造性研究の多くは fMRI による相関的証拠に留まっていたが、本研究は **直接刺激
による因果操作** で「DMN 活動が発散的思考の originality を causally 支える」ことを示した点で
画期的。かつ fluency (量) と originality (質) を分離して測定し、DMN 操作が **fluency に
影響せず originality のみを選択的に低下させる** ことを示した (交絡分離の精度が高い)。

## 3. 技術や手法の肝はどこ?
AUT という確立ベンチマークタスクを使いつつ、**同一課題内で fluency と originality を分離
測定** し、操作 (刺激) の効果を originality だけに帰属させる実験デザイン。この
「fluency を一定に保ちながら特定チャネルの効果だけを分離する」という設計思想は、ERRE の
ES-3 (zone-function control で locomotion→sampling の非トートロジー性を実証) や D0 pack
(anti-ES-1-collapse gate で R1 が R0 を黙って再測定する偽 GO を封鎖) の control 設計と
構造的に同型。

## 4. どうやって有効だと検証した?
stereo-EEG による高解像度神経記録 + 直接皮質刺激という侵襲的だが精密な手法。ガンマ帯域
パワー増加・シータ帯域パワー低下という DMN 活動の電気生理学的シグネチャを特定し、刺激による
抑制が originality スコアのみを選択的に低下させることを統計的に確認。

## 5. 議論はあるか?
被験者はてんかん患者 (臨床的必要性から電極留置) であり、健常者への一般化には注意が必要。
また DMN という脳領域固有の因果構造が、LLM のような非生物学的システムの「発散」メカニズムに
どこまで類推可能かは全く別の問題 (身体性なしに DMN 相当の機能単位が存在するかは自明でない)。

## 6. 次に読むべき論文は?
同著者らの先行研究、また DMN と外部注意ネットワーク (executive control network) の
切り替えダイナミクスに関するレビュー (創造的プロセスの二重過程モデル)。

---
## やり残し (1 行)
> 「fluency を一定に保ちながら特定チャネルの効果のみを分離する」という control 設計は既に
> ERRE (ES-3 zone-function control、D0 anti-collapse gate) が独立に到達している house pattern
> であり、この先行研究はその設計思想への外部的な理論的支持として research-positioning.md §3
> に追記する価値がある。
