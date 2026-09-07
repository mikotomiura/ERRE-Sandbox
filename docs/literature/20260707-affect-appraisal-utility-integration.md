# 感情・主観効用・認知的評価・行動観察の統合モデル — 先行研究サーヴェイ + ERRE 整合性ジャッジ

> **作成日**: 2026-07-07
> **作成体制**: サーヴェイ = Opus サブエージェント / 整合性ジャッジ = Fable 5(本体)
> **位置づけ**: これは **research-scoping の探索ドキュメント**であって、ADR でも
> measurement-line の起票でもない。M13 arc の verdict 機構・R-budget・holding は
> **一切消費しない**。本ドキュメントの提案を実際に走らせるには別途 ADR が要る(§10.3)。
> **claim 境界**: 本書は「ERRE がこの方向を測れるか/建てられるか」の desk-audit であって、
> 感情推定の効果を測った/建てたではない。

---

## 0. このジャッジの読み方

中心問い(再掲):

> LLM ベースのエージェントは、行動履歴・発話・選好・環境状態から、感情状態を
> **直接ラベル分類する (emotion label prediction)** のではなく、行動経済学的な
> **主観効用・認知的評価過程・目標阻害/達成・予測誤差・対処可能性**などの
> **中間潜在変数**を通じて推定できるか。

サーヴェイ本文(先行研究マップ全文)は本ドキュメント末尾 §A に格納した。以下 §1–§9 は
その survey を土台に、**ERRE-Sandbox の実コードに接地した具体ジャッジ**である。

ジャッジの一言結論を先に置く:

> **ERRE は中心問いを追える稀な基盤を持つが、現状の感情モデルはまさに問いが否定する
> 「直接ラベル方式」で実装されている。** 中間変数経由への移行は技術的に可能で、しかも
> ERRE 固有の資産(5 ゾーン・memory stream・ES-3 因果配線・verdict 機構)が
> 先行研究の 3 大空白(4 軸統合評価の不在 / 記憶更新一貫性軸の空白 / 中間変数の非同定性)を
> 攻める構造的優位になる。ただし **2 つの hard な壁**——(i) inverse RL 非同定性、
> (ii) `think=false` ローカル LLM の低エントロピーが appraisal reasoning を潰すリスク——が
> あり、これを設計制約として先に殺さない限り「測れるかをまず測る」arc 規律を PASS できない。

---

## 1. 研究背景 — 中心問いと ERRE 現状の実コード接地

### 1.1 なぜ「ラベルでなく中間変数」なのか(問いの正当化)

survey 領域8 が示す通り、感情ラベルには**原理的に ground-truth が無い**
(Barrett 2017 の構成主義、annotator 完全一致 ~20%、[W]『Rethinking Emotion
Annotations』arXiv:2412.07906)。一方 appraisal 次元(pleasantness / control /
certainty / goal-congruence 等)は **annotator 一致がはるかに高い**
(crowd-enVENT, Troiano et al. 2023 [W])。つまり「中間変数経由」は単なる好みでなく、
**より測定信頼性の高い量を経由する**という方法論的合理性を持つ。これが問いの核。

### 1.2 ERRE の現状 = 直接ラベル方式(実コード確認済み)

`src/erre_sandbox/schemas.py` と `src/erre_sandbox/cognition/state.py` を精読した結果、
ERRE の感情モデルは中心問いが**乗り越えようとしている当の方式**で実装されている:

**(a) 状態表現(`schemas.py`)**
- `Cognitive`: Russell 円環 `valence`/`arousal`(即時 affect)＋ Plutchik
  `dominant_emotion`(離散ラベル)＋ ドライブ `motivation`/`stress`/`curiosity`
  ＋ `dmn_activation`/`active_goals`(free-form 文字列 list、最大 10)。
- `Physical`: 長時間スケール体性状態 `mood_baseline`/`emotional_conflict`/
  `cognitive_load`/`fatigue`/`breath_rate`。

**(b) 更新機構(`cognition/state.py`)= ここが問いの争点**
- **LLM 自己申告**: `LLMPlan` が `valence_delta`/`arousal_delta`/`motivation_delta` を
  直接出し、`llm_weight=0.7` + noise + clamp で適用(`apply_llm_delta`, `state.py:228`)。
- **ハードコード event→体性インパクト**: `_PHYSICAL_EVENT_IMPACT` 辞書が
  `speech`/`zone_transition`/`proximity`/`temporal` 等の event を固定係数で
  `Physical` に流す(`_event_impact`)。`speech` は `emotional_impact` を乗せる。
- **関係性シンク(レビューで補完)**: `world/tick.py::apply_affinity_delta`
  (`tick.py:853-863`)が負の affinity delta から `Physical.emotional_conflict` を
  **直接書き込む**(`state.py:42-50` の decay と対)。これは (a) 自己申告でも (b) event
  辞書でもない**第3の独立チャネル**。§6.2 の appraisal 置換設計はこのチャネルの
  存置/置換を明示する必要がある(§6.2 に反映)。

**判定**: ERRE は感情を **(1) LLM が次元値/ラベルを直接出力** ＋ **(2) event 型ごとの
固定写像** ＋ **(3) 関係性シンク**で構成している。**appraisal / subjective-utility /
prediction-error / coping_potential を明示的中間変数として経由していない。**
`active_goals` が free-form 文字列としてあるのみで、`goal_congruence`・`coping_potential`・
`prediction_error` のフィールドも、それらを behavior/選好から推定する経路も存在しない
(src 全域 grep で 0 hit、レビュー確認済)。

これは survey 領域1(affective computing の label-centric 限界)の ERRE 版の具現である。
**中心問いは、この現状アーキテクチャそのものへの設計批判として読める。**

### 1.3 ただし ERRE は「中間変数化」の precedent を既に持っている

同時に、ERRE は中心問いを追うのに必要な**設計 idiom を別文脈で既に確立**している。
これがこの提案を「絵空事でない」ものにしている:

| ERRE 既存資産 | 実体 | 中間変数化への転用可能性 |
|---|---|---|
| **ES-3 locomotion→sampling** | `LocomotionState.lam`(EMA)→ `compose_sampling` 第3項で temperature 変調(配線・活性化済、v1 GO) | 「身体状態 → 中間変数 → 行動変調」の**因果配線 precedent**。appraisal→行動 の同型配線が可能なことの存在証明 |
| **`WorldModelUpdateHint`(M10-C **実装済・MERGED**、レビュー訂正)** | `direction: Literal["strengthen","weaken","no_change"]` + `cited_memory_ids ≥ 1` 必須。free-form 禁止。`contracts/cognition_layers.py:411` に実装、`parse.py:96` で LLMPlan 組込、`world_model.apply_world_model_update_hint` で citation-subset 検証まで稼働(`architecture.md:405` = MERGED) | 中間変数を **bounded primitive + 記憶引用必須**で LLM に出させる型の precedent。**計画でなく実コード資産**ゆえ §6.1 の `AppraisalState` は実物パターンを直接踏襲できる |
| **5 ゾーン world** | study/peripatos/chashitsu/agora/garden | inverse RL 非同定性(§9-i)を緩和する**環境多様性の資源**(Cao et al. 2021 [W]: 複数環境で報酬同定可能) |
| **memory stream + reflection** | CoALA/PIANO 系、`sqlite-vec`、importance>150 で反省 | survey 未解決2「記憶更新一貫性を評価軸にする研究の空白」に**直接位置する**基盤 |
| **verdict 機構 + two-plane determinism** | GO/NO_GO/INCONCLUSIVE、falsifiable pre-register、replay checksum | label 予測でなく behavioral outcome で **falsifiable に評価する**arc の house pattern |

---

## 2. 先行研究マップ(要約 + ERRE 接点)

全文は §A。ここでは **ERRE ジャッジに load-bearing な 8 領域の要点**のみ圧縮する。

1. **Affective Computing**(Picard 1997 [K]): 感情=ラベルへの写像。ERRE 現状(§1.2)の
   系譜そのもの。2024–26 に分野内部から「単一 ground-truth 無し」の反省(領域8 に連続)。
2. **Cognitive Appraisal Theory**: Lazarus/Scherer CPM/OCC/Roseman [K][W] →
   計算モデル化 **EMA**(Gratch & Marsella 2004 [W]、coping が信念・意図を書き換える)/
   **FAtiMA**(OCC ベース multi-agent キャラクタ、3D 箱庭の直接先例)/ WASABI。
   LLM 版: **Chain-of-Emotion**(Croissant 2024 [W]、appraisal を明示的中間表現化)/
   **RECAP**(appraisal 中間変数へ変換して条件付け)。← **ERRE が採るべき系譜**。
3. **Theory of Mind**: Kosinski 2023 の創発主張 → Ullman/Shapira の反証 [W]。論争は
   **literal ToM(他者行動予測)vs functional ToM(相手適応)**へ移行(Riemer 2025 [W])。
   **SimpleToM**(Gu 2024 [W]: 心的状態は当てるが行動予測で急落)は論点B の直接先例。
   → ERRE の感情推定は本質的に ToM の一種。この分野の懐疑を正面から引き受ける必要。
4. **Subjective Utility / 行動経済学**: Prospect Theory(Kahneman-Tversky 1979 [W]、
   参照点依存=「目標阻害/達成」と直結)。behavior→utility 逆推定 = **IRL**
   (Ng & Russell 2000 [W]、**自ら非同定性を指摘**)。← §9-i の壁の源泉。
5. **Active Inference / FEP**: Friston 2010 [W]。**Joffily & Coricelli 2013 [W] が
   「感情価 = 自由エネルギーの時間微分」と formal 定義** = ERRE「予測誤差」中間変数の
   最も直接的な formal 先例。ただし LLM 実装は survey 未解決6 の空白。
6. **Embodied AI / interoception**: Prinz『embodied appraisal』[W]、Seth の
   interoceptive inference [W]、Barrett 構成主義 [W]。ERRE の ES-3(身体→sampling)は
   embodied appraisal の**計算的類比**だが、interoception を明示モデル化していない差分。
7. **Mirror-Neuron-Inspired Alignment**: Rizzolatti/Gallese [W] の神経基盤 →
   ML アナログ = **Third-Person Imitation Learning**(Stadie 2017 [W]、観察↔実行の
   共有潜在空間)/ **Self-Other Overlap**(AE Studio 2024 [W]、LoRA で自己-他者表現の
   重なり増、**査読前**)/ **Embodied Representation Alignment w/ Mirror Neurons**
   (Zhu 2025 ICCV [W])。← 論点A の核。**"functional analog であって神経再現でない"**。
8. **データ品質・バイアス**: ground-truth 不在、annotator 一致 ~20%、文化バイアス、
   **appraisal 次元は一致高**(crowd-enVENT [W])、LLM は不確実性を潰す
   (Inoshita 2026 [W-snippet])。← §9-iii の要件源泉。

---

## 3. ERRE 整合性ジャッジ(本ドキュメントの核心)

### 3.1 中心問いへの適合度判定

**適合度: 高(ただし条件付き)。** ERRE は中心問いを追うために設計されたわけではないが、
偶然にも中心問いが要求する 4 条件をほぼ満たす稀な基盤である:

| 中心問いが要求するもの | ERRE の充足状況 |
|---|---|
| 行動・発話・選好・環境状態が観測可能 | ✅ memory stream / 発話 / RelationshipBond.affinity / 5 ゾーン占有が全て log 可能 |
| 中間変数を一級市民にできる型システム | △ `WorldModelUpdateHint` 型 precedent はあるが appraisal フィールド自体は未実装 |
| 中間変数→行動 の因果配線 | ✅ ES-3 が「状態→sampling→行動」の配線を GO で実証済(同型移植可能) |
| label でなく behavioral outcome で評価 | ✅ verdict 機構・replay・5 ゾーン行動軌跡 |

**結論**: 中心問いと ERRE の相性は構造的に良い。障害は「基盤の欠如」ではなく
「現状が直接ラベル方式で実装されている(§1.2)ことと、2 つの hard な壁(§9)」である。

### 3.2 決定的な緊張(survey 申し送りの核 × ERRE)

survey 担当が申し送った最重要の緊張を、ERRE に接地して再定式化する:

> **appraisal 中間変数は annotation 信頼性が高い(crowd-enVENT [W])。しかし
> ERRE が推定したいのは「状況記述テキストからの appraisal」ではなく
> 「行動軌跡からの appraisal 逆推定」であり、後者は inverse RL の非同定性
> (Cao et al. 2021 / Skalse et al. 2023 [W])を構造的に継承する。**

crowd-enVENT の高一致は **appraisal を状況記述から前向きに annotate** した結果であって、
**行動のみからの逆推定の同定可能性を保証しない**。ERRE で「Kant の歩行軌跡と発話から
彼の goal_congruence を推定する」のは後者であり、ここが死点になりうる。

**ERRE 固有の緩和材料(2 者レビューで大幅に条件付け)**: Cao et al.(2021)[W] は
entropy 正則化・既知動学の下で「2 つの異なる割引率、または**同一報酬 × 異なる遷移力学**の
複数 MDP があれば**スカラー報酬関数**を定数を除いて同定可能」と証明した。この定理を
ERRE に持ち込むには **2 つの load-bearing かつ未検証の前提**があり、素朴な「5 ゾーン =
構造的優位」は over-claim である:

1. **報酬 ≠ appraisal(圏の飛躍)**: 定理の対象はスカラー報酬。ERRE の appraisal は
   `goal_congruence`/`coping_potential`/`prediction_error`… の**多次元認知チェック**で、
   reward-identifiability 定理をそのまま適用できる保証はない。
2. **ゾーン間 appraisal 生成不変性(内在的に破れうる)**: 定理が効くのは
   「同一報酬 × 異なる動学」のとき。しかし ERRE の設計そのもの(ERRE モードは
   **ゾーン依存で認知を変える**)から、appraisal 生成関数は**ゾーン依存**である公算が高い。
   すると 5 ゾーンは "same-reward-different-dynamics" ではなく "**different-reward**" 環境に
   なり、定理は何も保証しない。**ERRE 自身のゾーン条件付き認知という核心設計が、この
   緩和材料を内在的に無効化しうる。**

**訂正後の主張**: 「5 ゾーンが同定可能性の資源」ではなく、「**§6.3 H-C の {1,3,5} ゾーン
反実仮想的制限介入**が複数環境条件を(条件付きで)構成しうる。ただし前件として
**ゾーン間 appraisal 生成不変性**を検証対象に格上げする必要があり、LLM エージェントへの
定理適用は類比に留まる」。5 ゾーンは自動的優位ではなく、不変性が成り立つ場合にのみ資源。

### 3.3 過大主張ガード — ミラーニューロン(論点A の ERRE 適用)

survey 論点A の結論を ERRE の語彙規約(glossary の禁止用語ルール、過大主張ガード)に
接地する:

- **やってよい表現**: 「観察行動表現と自己行動表現を共有潜在空間に整合させる
  **functional analog**(self-other latent alignment)を導入する」。
  実装候補は Self-Other Overlap(AE Studio 2024 [W])/ 対称埋め込み(Zhu 2025 [W])。
- **禁止表現**: 「ミラーニューロンを実装した」「神経機構を再現した」。
  survey が示す通りこれは citation-inaccurate かつ ERRE 過大主張ガード違反。
- **ERRE 予算制約との衝突注意**: SOO は LoRA fine-tuning を要する。ERRE の
  M9-eval 系 LoRA パイプラインは存在するが GPU 実走コストがあり、予算ゼロ制約下では
  **推論時 prompt レベルの self-other simulation(SimToM 型 [W])を先に試すべき**
  (fine-tuning は後段)。

### 3.4 governance 上の重大注記 — これは「第3の measurement family」

**これは実務上いちばん見落とされやすい点なので明示する。** ERRE の現行規律
(`forward-primary-post-v1` ADR、MEMORY.md)では、arc の measurement family は
**2 つに凍結列挙**されている(SPDM-landscape structural-floor = SPENT /
live-channel-conformance = C-design で REFUSE)。感情推定を **measured claim** として
起票することは、この列挙に入らない **第3の measurement family の新設**に相当**しうる**。
規律は「第3 family 化は from-scratch・非反射の独立 ADR を要す」と定めている。

**ただし family 判定は未審査(レビュー MEDIUM、要注意)**: 規律は family を「名前でなく
structural invariant(estimand family / data-generating channel / 回避する 5 壁 /
tie→same-family)で定義」する(`research-positioning.md:508`)。ここで **H-B(§5)の
data-generating channel = live LLM の `destination_zone` 選択列**は、既存の
**live-channel-conformance family と同一チャネル**である。`tie→same-family` 条項の下では、
H-B は「第3 family」でなく **既存 family 内の新 candidate** に分類されうる。その場合の
governance 経路は「非反射の第3 family ADR」ではなく **「残り 1 回の family budget を賭ける
再 C-design」**(B-scoping ADR T3 の『(i) を攻める基質改変が eligibility 必須』付き、
`:566`)に変わり、**未達なら arc-close 自動執行**に直結する遥かに重い賭けになる。
→ **measurement 化の ADR を書く前に、この invariant テスト(特に tie→same-family)を
明示的に適用して family 帰属を確定すること**。construction 先行という実務結論はどちらの
分類でも不変だが、measurement gate の前件が全く異なる。

したがってこの提案は 2 つの経路のどちらかを選ぶ必要がある:

1. **construction 経路(推奨、holding 保全)**: ECL v0/v1 と同じく
   「感情の中間変数化を **建てる**(器官化)」に留め、divergence/floor/verdict を出さない。
   two-plane determinism・continuity gate の house pattern をそのまま継承。
   → arc の R-budget を消費せず、measurement-line 再入も発生しない。
2. **measurement 経路(重い)**: 「中間変数経由推定が label 方式を上回る」を
   **測る**なら、第3 measurement family 新設 ADR(非反射・futility gate 付き)が前件。

**§5–§8 の実験設計は、まず経路1(construction)として設計する。** これは arc の
現在の holding 姿勢と整合し、かつ「測れるかをまず測る」規律に沿う(測定は後段)。

### 3.5 最重要の未解決穴 — H-A は「直接ラベル方式」を脱していない(2 者独立収束)

Fable/Opus 両レビューが**独立に同じ急所**を突いた。本ドキュメントで最も load-bearing な
自己批判として明示する:

> **提案していた H-A(LLM が bounded appraisal primitive + `cited_memory_ids` を出力)は、
> §1.2 で私自身が批判した「LLM が次元値/ラベルを直接出力する直接方式」から実質的に
> 脱していない。** ラベルを `dominant_emotion` → `goal_congruence` に**引っ越しただけ**で、
> 生成機序(LLM 直接出力)は同一。中心問いが要求するのは「行動履歴からの**逆推定**を
> 経由する中間変数」だが、`cited_memory_ids` 必須の LLM 自己申告は「引用記憶に条件付いた
> 自己申告」であって**行動からの逆推定ではない**。§1.2 の批判文が H-A に verbatim で当たる。

さらに `cited_memory_ids` は arc の傷と同型の **circularity** を生む: appraisal を
記憶引用で出させ、評価軸(iii)で「appraisal が変わると memory importance/検索順が一貫方向に
動くか」を測ると、**memory → appraisal → memory の自己参照ループ**になり軸(iii)が
トートロジー化する。これは ES-4 を崩落させた **embedding rarity の自己 anchor 循環**、
running-substrate を殺した **R0 anchor collapse** と**同型の失敗機序**。
`cited_memory_ids` を「幻覚を構造排除」の純 positive としてのみ扱っていたのは片手落ちで、
**(1) 直接方式への逆戻り + (2) 自己参照循環という二重の穴**を開けていた。

**必須の是正(下流 ADR の前件)**: 次の 2 択のいずれかを明示すること。
- **(選択肢1・推奨) H-A を真の inverse 推定器に再設計**: 入力 = 行動軌跡
  (ゾーン遷移列・滞在時間・発話タイミング等の behavioral stream)、出力に memory 引用を
  含めない。appraisal は「行動から逆算される潜在」として推定する。
- **(選択肢2・claim 後退) 現機序を保つなら claim 境界を明示的に下げる**: 「これは
  逆推定でなく**記憶条件付き自己申告**であり、§1.2 の直接方式批判を脱していない。中心問いの
  『中間変数経由推定』の部分的 construction にとどまる」と honest に記す。

いずれの場合も、評価軸(iii)/(iv)は **推定入力ストリーム(発話・memory)と検証出力ストリーム
(滞在時間・反復行動)の disjointness を pre-register** しない限り循環する(§7 に反映)。

---

## 4. 未解決問題(ERRE が攻めうる空白)

survey の open problems 9 件のうち、**ERRE が構造的優位を持つ**ものに ★ を付す:

1. ★★ **4 軸統合評価方法論の不在**(survey 最大の空白): label 精度を超える
   4 軸(行動予測 / 介入成功 / 記憶更新一貫性 / 効用妥当性)を単一枠組みで統合した
   評価は先行研究に**存在しない**。ERRE は behavioral outcome を自然に観測できる
   multi-agent 3D 基盤ゆえ、この空白を埋める構造的優位を持つ。
2. ★★ **記憶更新一貫性を感情評価軸にする研究の空白**: ERRE の memory stream +
   reflection が直接位置する。「appraisal 推定が変わると記憶の書き込み/検索が
   一貫して変わるか」は ERRE でこそ測れる。
3. ★ **単一環境での中間変数の非同定性 × 環境多様性の回復力**: 5 ゾーンが
   Cao et al.(2021)[W] の "複数環境" 資源になるかは未検証。ERRE がその apparatus。
4. ★ **appraisal 中間層の因果的検証(閉ループ)**: Tak et al.(2025)[W] は
   内部表現操作までだが、**行動レベルの閉ループ因果**は乏しい。ES-3 の
   「身体→中間変数→行動」配線がこの検証台。
5. **functional ToM(相手適応)の標準ベンチ不在**(Riemer 2025 [W]): ERRE の
   multi-agent 相互作用が観測環境になりうる。
6. **予測誤差ベース感情(Joffily & Coricelli 2013 [W])の LLM 実装の空白**:
   「感情価 = 自由エネルギー時間微分」の閉ループ実装は未確認。
7. ★★ **`think=false` ローカル小モデルでの appraisal 推定の成否**(survey 未解決8 の
   ERRE 版): これは空白であると同時に **ERRE 最大のリスク**でもある(§9-ii)。
   qwen3:8b の低エントロピー生成で多段 appraisal reasoning が保てるかは完全に未検証。
8. **appraisal annotation の高信頼性を LLM 逆推定に転写できるか**(§3.2 の緊張)。

---

## 5. 仮説(falsifiable)

arc の verdict 語彙(GO/NO_GO/INCONCLUSIVE)と two-sided guard に沿って起票する。
**H-A は construction 仮説、H-B/H-C は将来の measurement 仮説(第3 family 起票が前件)。**

- **H-A(construction、まず建てる。§3.5 で再設計)**: appraisal 中間変数
  (`goal_congruence`, `coping_potential`, `prediction_error`)を認知サイクルに器官化し、
  それが `Cognitive`(valence/arousal)と**決定論的に**接続され、ES-3 型の因果配線
  (appraisal→行動変調)が continuity gate を通る器官を建てられる。**§3.5 の是正により、
  H-A は選択肢1(行動軌跡入力・memory 引用を出力に含めない inverse 推定器)を推奨形とする。**
  選択肢2(記憶条件付き自己申告)を採るなら claim を「直接方式の部分 construction」に後退。
  → 反証 = continuity gate FAIL(appraisal を介入しても行動が動かない=配線が死んでいる)。
- **H-B(measurement 候補①・行動予測軸)**: 中間変数経由モデルは、直接ラベル方式より
  **他者の次行動(次ゾーン選択 / 発話有無 / dialog 継続)を高精度に予測**する
  (SimpleToM [W] 型の行動予測評価)。→ 反証 = matched null(label 方式)と有意差なし。
- **H-C(measurement 候補②・非同定性回復。§3.2 訂正を反映)**: {1,3,5} ゾーンの
  **反実仮想的制限介入**で構成した環境集合は、単一環境より appraisal 推定を同定可能に
  近づける(Cao et al. 2021 [W] の類比。前件 = **ゾーン間 appraisal 生成不変性**が成り立つこと)。
  → **反証(primary)= 環境数に対する推定安定性の単調改善が出ない**(単調性 contrast を主とする)。
  → **反証(secondary)= bootstrap 安定性が floor 未達**(cf. memseam argmax stability 0.187)。
  floor を primary にすると壁3/壁5 の教訓どおり「非同定」と「floor 誤較正」を分離できず
  one-shot kill を再演するため、**単調性を primary・floor を secondary** にする(レビュー反映)。

> **two-sided guard**: positive も negative も finding。特に H-C が NO_GO なら
> 「行動からの appraisal 逆推定は ERRE substrate では非同定」という**強い negative
> finding**(inverse RL 理論の in-silico 確証)になる。これは失敗でなく成果。

---

## 6. 実験設計

**経路1(construction)先行**。measurement(H-B/H-C)は第3 family ADR 後。

### 6.1 Phase 0 — 中間変数スキーマの pre-register(doc-only)

- `AppraisalState`(新 Pydantic サブモデル)を設計: `goal_congruence: _Signed`,
  `coping_potential: _Unit`, `prediction_error: _Unit`, `certainty: _Unit`,
  `novelty: _Unit`(Scherer CPM / OCC の最小サブセット、[W] crowd-enVENT の高一致次元を選定)。
  各値は `WorldModelUpdateHint` 型に倣い **`cited_memory_ids ≥ 1` 必須**(free-form 禁止で
  幻覚を構造排除)。`AgentState` に **nullable additive**(`locomotion=None` 同型で
  後方互換 byte-identical を保証)。
- **think=false エントロピー probe(§9-ii の壁を先に殺す)**: qwen3:8b で 5 appraisal
  次元を JSON 出力させ、同一 context を M 回サンプルして**次元値の分散が縮退しないか**を
  desk-audit。縮退するなら appraisal reasoning は think=false で不成立 → 設計変更が前件。
  (C-design で判明した think=false 低エントロピー collapse risk の appraisal 版。)

### 6.2 Phase 1 — construction(器官化、H-A)

- appraisal を LLM に出させ → `Cognitive.valence/arousal` へ**決定論的写像**
  (現状の LLM 自己申告 delta を appraisal 経由に置換)。
- **continuity gate(exact-oracle、ECL v0 の house pattern 継承)**: positive control
  =「goal_congruence を負に介入 → valence が下がる」、negative control =「無関係次元
  介入 → valence 不変」を**座標決定的等価/相異のみ**で検査。統計/floor/verdict 非出力。
- replay checksum で two-plane determinism 保証(appraisal LLM call は Plane 2 記録)。

### 6.3 Phase 2 — measurement(H-B/H-C、第3 family ADR 後のみ)

- **H-B 行動予測**: N 体で走らせ、`(appraisal 経由モデル / label 直接モデル)`の
  2 群で「次ゾーン選択」を hold-out 予測。matched null(label 群)との差を pre-register
  MDE で検定。**B(N体化)ADR の反復 frozen-context bank apparatus をそのまま流用可能**
  (単一 frozen context × M 回 MC = 各 context 1-sample 死点を殺す既存設計)。
- **H-C 非同定性**: 同一ペルソナを {1 ゾーン, 3 ゾーン, 5 ゾーン} で観測し、appraisal
  推定の bootstrap 安定性が環境数で単調改善するかを測る(Cao et al. 2021 [W] の in-silico 版)。

### 6.4 ミラー/self-other(論点A、独立の小 spike)

- **予算ゼロ優先**: fine-tuning(SOO)前に **SimToM 型 prompt** [W] で「他者の
  appraisal をシミュレートして自分の RelationshipBond.affinity を更新」する
  self-other simulation を試す。continuity gate =「他者 appraisal 介入 → affinity 変化」。
  fine-tuning(SOO)は効果が prompt レベルで見えたら後段。

---

## 7. 評価指標(4 軸、survey 論点B の空白を埋める設計)

survey が「4 軸統合は存在しない」と指摘した空白を、ERRE の測定可能量で具体化する:

| 軸 | ERRE での操作的指標 | 先行 anchor | 循環回避の要点 |
|---|---|---|---|
| **(i) 行動予測精度** | 次ゾーン選択 / 発話有無 / dialog 継続の hold-out 予測 log-loss | SimpleToM [W] | appraisal を予測に使う群 vs label 群の**差分**で測る(絶対精度でなく) |
| **(ii) 介入成功率** | 「相手の coping_potential を上げる発話」後に相手の stress が実際に下がった割合 | EmoBench Application [W], RECAP [W] | **前件 = stress 駆動チャネルの construction**(レビュー MEDIUM: 現行コードに `stress` を**上げる書き込み経路が無く**毎 tick 一律減衰のみ [`state.py:256`]、`LLMPlan` に stress_delta 無し → 現状 null 群でも「下がった割合」~1 で検出力ゼロ = dead channel)。介入と outcome を別 tick・別 RNG stream で分離 |
| **(iii) 記憶更新一貫性** | appraisal 推定が変わった時、memory importance / 検索順が**一貫方向**に動くか | Generative Agents reflection [W] | **ERRE 独自の空白**(survey 未解決2)。**循環ガード必須(§3.5)**: appraisal 推定と memory importance 付与が同一 LLM 由来だと自己整合で trivially 成立(ES-4 自己 anchor 崩落と同型)。**推定入力ストリーム(発話・memory)と検証出力の disjointness を pre-register** |
| **(iv) 主観効用推定妥当性** | 推定 utility が実際の選好(ゾーン滞在時間 / 反復行動)を再現するか | Prospect Theory [W], IRL [W] | 非同定性ガード(§3.2 訂正)**＋循環ガード**: utility を行動から推定して行動で検証すると循環。**推定入力と検証出力ストリームの disjointness を pre-register**(§3.5)。5 ゾーン主張は不変性前件付き(H-C) |

> **重要な設計原則(arc house pattern の継承)**: どの軸も **matched null との差分**で
> 測り、absolute score を verdict にしない。memseam の教訓(near-uniform 台で argmax
> stability 0.187)から、各指標に **bootstrap 安定性 gate** を前置する。

---

## 8. 実装ロードマップ

| Milestone | 内容 | 経路 | R-budget | 前件 |
|---|---|---|---|---|
| **M-Aff-(-1)** | **2 つの cheap kill gate**(レビュー反映): (a) think=false エントロピー probe / (b) ゾーン間 appraisal 生成不変性 desk-audit。**両方 pass しない限り器官化に着手しない** | doc-only/probe | 未消費 | 本ドキュメント |
| **M-Aff-0** | `AppraisalState` スキーマ pre-register(実装済 `WorldModelUpdateHint` パターン踏襲)+ H-A を inverse 推定器として再設計(§3.5) | doc-only | 未消費 | M-Aff-(-1) 両 gate pass |
| **M-Aff-1** | appraisal 器官化 + continuity gate + replay(H-A) | construction | 未消費 | M-Aff-0 |
| **M-Aff-S** | SimToM 型 self-other simulation spike(論点A) | construction | 未消費 | M-Aff-1(独立でも可) |
| **M-Aff-2** | 行動予測 / 非同定性 measurement(H-B/H-C) | **measurement** | **第3 family ADR 要** | M-Aff-1 GO + 非反射 ADR |
| **M-Aff-3** | SOO LoRA fine-tuning(効果が prompt で見えた場合のみ) | construction+GPU | 未消費 | M-Aff-S で prompt レベル効果確認 |

**順序の原理**: 「測れるかをまず測る」arc 規律に従い、**construction(建てる)→
think=false probe(壁を殺す)→ measurement(第3 family ADR 経由)**の順。
M-Aff-0 の think=false probe が縮退を示したら、そこで**設計変更 or bounded close**
(measurement へ進む前に殺す)。

---

## 9. リスク

**壁は 2 つが hard、残りは管理可能。**

- ★★ **(i) inverse RL 非同定性(理論的 hard 壁)**: 行動からの appraisal/utility
  逆推定は原理的に非同定(Ng & Russell 2000, Cao et al. 2021, Skalse et al. 2023 [W])。
  **緩和 = 5 ゾーン環境多様性(§3.2)+ appraisal 次元の事前 anchor(crowd-enVENT の
  高一致次元に限定)+ cited_memory_ids 必須**。それでも単一ゾーン・単一 tick では
  非同定が残る。H-C がこれを直接測る。
- ★★ **(ii) `think=false` 低エントロピー崩壊(ERRE 固有 hard 壁)**: qwen3:8b を
  think=false で回すのは ERRE の load-bearing 設計(全 tick parseable、v1 で実証)だが、
  **これは多段 appraisal reasoning(Chain-of-Emotion / Appraisal Reasoning Graph [W])と
  正面衝突する**。低エントロピー生成は appraisal 次元を定型句へ縮退させる恐れ。
  C-design が doc-only desk-audit で「think=false 低エントロピーが zone naming を context
  支配に潰す」と **architecture 上 予測(empirical には未確定)**(`research-positioning.md:534`、
  ADR 自身が`:543`で「REFUSE は測っていない」と over-read 禁止)。**先行証拠が失敗を予測する
  =これは最も可能性の高い kill 点**ゆえ、**緩和 = probe を construction 投資の前に standalone
  kill gate として前置(§8 の Phase -1)。縮退するなら think 部分活性 or 外部 appraisal
  reasoner を別 tick で(予算制約と衝突するので後段)**。arc の「予測 ≠ 判明」evidence-status
  規律に従い「判明済」とは書かない(レビュー HIGH-2 反映)。
- **(iii) データ品質(survey 領域8)**: LLM は annotation 不確実性を潰す
  (Inoshita 2026 [W-snippet])。**緩和 = ラベルでなく appraisal 次元で評価
  (そもそも本提案の趣旨)+ 文化バイアス注意(多文化ペルソナ = ERRE で特に重大)**。
- **(iv) ToM 懐疑の継承(survey 領域3)**: 感情推定は ToM の一種ゆえ Clever Hans 批判
  (Shapira 2024 [W])/ 行動予測での急落(SimpleToM [W])を引き受ける。
  **緩和 = literal でなく functional ToM(相手適応)を評価軸に(Riemer 2025 [W])**。
- **(v) 過大主張(§3.3)**: ミラーニューロン=神経再現の主張は禁止。
  **緩和 = "functional analog / self-other alignment" 表現を凍結明記**。
- **(vi) governance(§3.4)**: measurement 化は第3 family。**緩和 = construction 先行、
  measurement は非反射 ADR 経由のみ**。

---

## 10. まとめと次アクション

### 10.1 ジャッジ総括

ERRE は中心問いを追う**稀に良い基盤**(5 ゾーン・memory stream・ES-3 因果配線・
verdict 機構)を持つが、現状の感情モデルは**問いが否定する直接ラベル方式**で実装されている
(§1.2)。中間変数化は技術的に可能で、しかも survey の 3 大空白(4 軸統合評価 /
記憶更新一貫性軸 / 中間変数非同定性)を攻める構造的優位がある。障害は基盤の欠如でなく、
**2 つの hard な壁(inverse RL 非同定性 / think=false 低エントロピー崩壊)**である。

### 10.2 最も load-bearing な 5 判断(レビュー反映後)

1. **greenlight を 2 cheap kill で硬化**(§8 M-Aff-(-1)、レビュー確定): think=false
   エントロピー probe ＋ ゾーン間 appraisal 生成不変性 desk-audit の**両方が pass するまで
   appraisal 器官の construction に着手しない**。両者とも安価に殺せる = arc の
   「測れるかをまず測る」規律を自分の提案に最も攻撃的に適用。
2. **H-A を inverse 推定器として再設計**(§3.5、両レビュー独立収束): `cited_memory_ids`
   自己申告のままでは直接ラベル方式を脱せず自己参照循環を作る。行動軌跡入力・memory 引用を
   出力に含めない形へ。採れないなら claim を「直接方式の部分 construction」に honest に後退。
3. **construction 先行**(§3.4 経路1)。measurement は family-invariant テスト(§3.4)で
   帰属を確定してから。第3 family でなく既存 family 内 candidate = 残 budget=1 の賭けの
   可能性があり、この分岐を未審査で measurement gate を書かない。arc holding 保全。
4. **Cao/5-ゾーン主張は不変性前件付き**(§3.2 訂正)。5 ゾーンは自動的優位でなく、
   ゾーン間 appraisal 生成不変性が成り立つ場合にのみ資源(= 判断1 の gate(b))。
5. **ミラーは functional analog として、SimToM 型 prompt から**(fine-tuning は後段、予算)。

### 10.3 次アクション(未実行 = ユーザ判断待ち)

本ドキュメントは探索 desk-audit であり、**まだ何も起票・実装していない**。前進させるなら:

- **(推奨) M-Aff-0 の ADR 化**: `AppraisalState` スキーマ + think=false probe を
  Plan mode + /reimagine + Codex で pre-register(doc-only、R-budget 未消費)。
- **references.md 登録**: survey の [W] 検証済み文献を append-only で `docs/references.md`
  に登録(現状 [1]–[11]、次は [12] から)。§A の未検証 [未検証] 5 件は登録前に一次確認。
- **literature card 化**: survey を `.claude/skills/literature-card` の 6 項目
  フォーマットで `_index.md` に追記。

---

## 11. レビュー結果と反映(2 者独立レビュー、2026-07-07)

本ドキュメントは 2 者独立レビューを通した(CLAUDE.md の independent-review 規律 =
同一モデル 1 発案の構造バイアスを別モデルで閉じる)。

- **Fable レビュー(実コード照合中心)**: verdict = **Adopt-with-changes**。
- **Opus レビュー(学術・戦略健全性、別モデル)**: verdict = **Adopt-with-changes**。

両者は独立に**同一の急所**へ収束した(= 高信頼): (1) H-A が直接ラベル方式を脱していない +
`cited_memory_ids` の自己参照循環、(2) Cao 5-ゾーン同定可能性の over-claim。

### 反映済み(本文に適用)

| # | 指摘(出所) | 反映箇所 |
|---|---|---|
| HIGH | H-A は直接出力方式を脱せず + memory→appraisal→memory 循環(両者独立収束) | §3.5 新設・§5 H-A 再設計・§7(iii)(iv) disjointness |
| HIGH | Cao/5-ゾーン同定可能性の over-claim(reward≠appraisal / ゾーン依存で different-reward)(両者) | §3.2 全面条件付け・§5 H-C 再設計 |
| HIGH(Fable) | `WorldModelUpdateHint` は M10-C **実装済・MERGED**(計画と誤記 = under-claim) | §1.3 表 訂正 |
| HIGH(Fable) | §9-ii「判明済」は over-claim(C-design は architecture 予測、empirical 未確定) | §9-ii・§10.2 訂正 |
| MEDIUM(Fable) | 第3 family 判定が未審査(tie→same-family で H-B は既存 family 新 candidate の可能性) | §3.4 audit 節追加 |
| MEDIUM(Fable) | §7(ii) stress は dead channel(上げる書き込み経路が無い) | §7 表 訂正 |
| MEDIUM(Fable) | §1.2 診断が第3チャネル(`emotional_conflict` 関係性シンク)を欠落 | §1.2 補完 |
| MEDIUM(Opus) | think=false probe を construction 前の standalone kill gate に(VoI) | §8 M-Aff-(-1) 追加 |
| MEDIUM(Opus) | H-C は単調性を primary・floor を secondary に(one-shot kill 再演回避) | §5 H-C 訂正 |
| LOW(Fable) | 関数名 `_compose_cognitive` は非在(実体 `apply_llm_delta`) | §1.2 訂正 |

### 未反映(残課題として明示・次 ADR で扱う)

- **MEDIUM(Opus)/§1.1・§0 の forward≠inverse**: appraisal annotation の高信頼性は
  **forward(状況記述→appraisal)の性質**であり、ERRE が使う **inverse(行動→appraisal)には
  転写されない**。§1.1 の方法論的合理性はこの限定付きで読むこと(冒頭 claim の弱点)。
- **MEDIUM(Opus)/§5 Joffily formal 系譜の誇張**: 提案の `prediction_error` は LLM 自己申告の
  `_Unit` スカラーで、変分自由エネルギー F も dF/dt も生成モデルも継承しない。
  「最も直接的な formal 先例」は heuristic ラベルへの着想であって formal 継承ではない。
- **MEDIUM(Opus)/構成 sequencing**: この affect 方向は construction であり、宣言済み次 primary
  **B(substrate-enrichment、反復 frozen-context bank が PRIMARY / N体化は Milestone 2+ に defer)**
  と個人開発の帯域を奪い合う。pivot でなく **同族の parallel/継続**だが、affect-construction と
  B-construction のどちらを先にするかの戦略判断は本ドキュメント外(user 裁定事項)。
- **MEDIUM(Opus)/決定論 drift surface**: appraisal 活性化後は record/replay に tick あたり
  最大 5 個の追加 LLM 由来 float/JSON が乗り、cross-platform 1-ULP libm drift 面が拡大する
  (`feedback_golden_crossplatform_float_drift` の教訓)。byte-identical 後方互換は
  `appraisal=None` のときのみ。§6.2 の replay checksum 主張はこの drift-surface 拡大を含む。

### スチールマン(Opus 観点3)への応答 — 確定版判断

> **最強の反論**: 「ERRE は稀な基盤」は apparatus-presence と measurable-signal を混同。
> arc は floor を 5 度建てられず(壁1-5)、running 唯一試行も `NO_STRUCTURAL_FLOOR_RUNNING`。
> 「構造的優位」の資産(5 ゾーン・memory・ES-3)は near-uniform / stability 0.187 / D_obs→0 を
> 生んだ**同一 kernel-level substrate**であり、その上に**より非同定な** appraisal を積むのは
> 時期尚早。H-C が bootstrap 安定性(0.187 と同じ量)に還元される事実は赤信号。

**確定版応答(Fable)**: construction 先行に徹し floor を建てると claim しない限り
「時期尚早な measurement」は governance 的に回避される。しかし steelman の深い刃は残る——
**器官化 construction 自体が帯域の賭け**で、その最終 payoff(measurement)は arc を繰り返し
殺した非同定性の壁の後ろにある。ゆえに**本ドキュメントの greenlight 条件を硬化する**:
§8 の **M-Aff-(-1)(think=false probe + ゾーン不変性 desk-audit)の 2 cheap kill が両方
pass しない限り、appraisal 器官の construction 投資に着手しない**。これは reject でなく、
arc 自身の「測れるかをまず測る」論理を**自分の提案により攻撃的に適用**した建設的硬化である。

---

## §A. サーヴェイ本文(Opus サブエージェント、2026-07-07)

> 以下は先行研究サーヴェイの全文(先行研究マップ・深掘り論点 A/B/C・open problems・
> 参考文献リスト)。検証表記: **[W]**=web 検証済 / **[W-snippet]**=スニペット確認
> (中確度)/ **[K]**=定番だが一次未確認 / **[未検証]**=要一次確認。

_(以下は survey 担当が返した本文を verbatim 格納。要約していない。HTML エスケープのみ
markdown 用に復元。)_

---

# 先行研究サーヴェイ: 中間潜在変数を介した LLM エージェントによる感情推定

**担当: 学術サーヴェイ / 対象: ERRE-Sandbox 設計整合性の上流入力 / 作成日: 2026-07-07**
**射程: 先行研究の整理と未解決問題の抽出まで(ERRE への採否判断は含まない)**

> **検証表記の凡例**
> - **[W]** = 本セッションで web 検索により実在(arXiv ID/DOI/venue)を確認
> - **[W-snippet]** = web 検索スニペットで存在を確認したが一次 fetch までは未実施(中確度)
> - **[K]** = training knowledge に基づく定番文献(古典であり広く既知だが本セッションで一次 URL 未確認のもの)
> - **[未検証]** = ID/著者を確認できず、捏造リスクを排除できないもの。引用前に一次確認必須

---

## 1. エグゼクティブサマリ

中心問い ―「LLM エージェントは感情を **直接ラベル分類** するのではなく、appraisal・主観効用・予測誤差・coping 可能性などの **中間潜在変数** を介して推定できるか」― に対する現時点の学術的到達点は、**「原理的には有望だが、識別可能性と評価方法論の両面で未確立」** と要約できる。(a) 認知的評価理論(appraisal theory)の計算モデル化は EMA/FAtiMA/WASABI など 20 年の蓄積があり、LLM 時代には crowd-enVENT [W] のような appraisal 次元付きコーパスと、CAREBench・"Beyond Context to Cognitive Appraisal"(Yeo & Jaidka 2025)[W] のような **appraisal を明示的中間層に置くベンチマーク**が 2024–2026 に急増した。(b) しかし LLM は「支配的な感情ラベルは当てるが、appraisal と特定感情の対応付けや、annotation の分布的不確実性の再現は苦手」という頑健な否定的知見(Inoshita et al. 2026 [W-snippet]、"fragile cognitive reasoning" 2025 [W])が繰り返し得られている。(c) Theory of Mind 研究では 2023 年の「創発」主張(Kosinski)[W] が Ullman/Shapira/Riemer らの反証 [W] を招き、論争は「genuine か shortcut か」から **「literal ToM(他者行動予測)対 functional ToM(相手への適応)」というベンチマーク妥当性そのもの**へ移行した(Riemer et al. ICML 2025 [W])。(d) 中間変数を behavior から逆推定する試みは inverse RL の **非同定性(ill-posedness)**という 25 年来の壁(Ng & Russell 2000 [W]、Cao et al. 2021 [W]、Skalse et al. 2023 [W])を継承しており、これは ERRE の「行動履歴から appraisal/utility を推定する」構想の中核的リスクである。(e) ミラーニューロンを「自己-他者の共有潜在空間整合」という **実装概念**として扱う路線は、AI 安全の Self-Other Overlap(AE Studio 2024)[W] と Embodied Representation Alignment(ICCV 2025)[W] という二つの具体的機械学習実装を得たが、いずれも「神経再現」ではなく **functional analog** である。総じて、**label prediction を超える評価軸(行動予測・介入成功・記憶更新一貫性・効用妥当性)を 4 軸統合した評価方法論はまだ存在せず**、そこが最大の研究空白である。

---

## 2. 領域別 先行研究マップ

### 領域1: Affective Computing(Picard 起点、label-centric な限界)

| 著者(年) | 貢献 | ERRE の問いとの接点 | 限界 |
|---|---|---|---|
| **Picard (1997)** *Affective Computing*, MIT Press [K] | 分野を定義した基礎書。計算機が感情を認識・表現・保持する枠組みを提唱 | 感情を計算対象とする起点。ERRE の Emotion サブモデルの系譜 | LLM 以前。計算モデルは初期的、認識=分類の枠 |
| **Poria, Majumder, Mihalcea, Hovy (2019)** ERC survey, arXiv:1905.02947 [W-snippet] | 会話内感情認識(ERC)の課題(文脈・話者・感情シフト)を整理した代表的サーベイ | 対話履歴からの感情推定の定番枠組み | **label-prediction 精度中心**のパラダイム |
| **MER survey (2025)** arXiv:2505.20511 [W-snippet] / **Affective Computing in the Era of LLMs** arXiv:2408.04638 [W-snippet] | マルチモーダル ERC と LLM 時代の affective computing を俯瞰 | 最新の技術地図 | いずれも依然ラベル分類パラダイム内の整理 |
| **"Modelling Emotions is an Elusive Pursuit"** arXiv:2603.23017 [W-snippet] / **npj AI (2025)** "Affective computing has changed: the foundation model disruption" [W-snippet] | 基盤モデルによる affective computing の地殻変動と、ground-truth の原理的困難を問題化 | ERRE が「ラベルでなく中間変数」に賭ける理由の外部的裏付け | 問題提起中心、代替方法論は未確立 |

**この領域の総括**: affective computing は成立当初から感情を **カテゴリ/次元ラベルへの写像**として扱い、精度(F1/accuracy)で評価してきた。この label-centric 性こそ ERRE が乗り越えようとする対象であり、2024–2026 に分野内部から「感情に単一 ground-truth は無い」という反省(領域8と連続)が噴出している。

### 領域2: Cognitive Appraisal Theory とその計算モデル化

**心理学基盤:**
- **Lazarus (1991)** *Emotion and Adaptation* [K] — appraisal(一次/二次評価)と coping を感情の中核とする。EMA の理論的母体(Smith & Lazarus)。
- **Scherer (2001)** Component Process Model(CPM): relevance→implication→coping potential→normative の 4 段階逐次評価(multilevel sequential checking)[W-snippet]。限界: 逐次チェックの実験的検証が困難(著者自身が指摘)。
- **Ortony, Clore, Collins (1988)** *The Cognitive Structure of Emotions*(**OCC model**)[W]: event/agent/object の三分類から 22 感情型を体系化。FAtiMA など多くのエージェントの基盤。限界: 認知評価に限定し身体・表情を除外。
- **Roseman (1991)** *Appraisal Determinants of Discrete Emotions*, Cognition & Emotion 5(3):161–200, DOI:10.1080/02699939108411034 [W]: 5 appraisal の組合せで 13 感情を決定。限界: 離散カテゴリ前提で次元的感情観と緊張。

**appraisal 駆動エージェント・アーキテクチャ(計算モデル化):**

| 著者(年) | システム | 貢献 | ERRE の問いとの接点 | 限界 |
|---|---|---|---|---|
| **Gratch & Marsella (2004)** Cognitive Systems Research 5(4):269–306, DOI:10.1016/j.cogsys.2004.02.002 [W] | **EMA** (EMotion and Adaptation) | appraisal と **coping**(wishful thinking/distancing/resignation が信念・欲求・意図を書き換える)を統合した領域独立の計算的感情モデル | ERRE の「coping 可能性」中間変数の直接の先祖。appraisal→行動変調の古典的実装 | シンボリック・ルール依存で学習性が低い |
| **Becker-Asano (2008)** *WASABI*, IOS Press, ISBN 9781586039110 [W] | **WASABI** | 3 次元 affect 空間で一次/二次感情の動態をモデル化、埋め込み容易 | 感情の連続的力学(ERRE の連続物理と接続しうる) | 単一エージェント・身体動態中心、社会推論は薄い |
| **Dias & Paiva (2005)**; **Dias, Mascarenhas, Paiva (2014)** FAtiMA Modular, DOI:10.1007/978-3-319-12973-0_3; Toolkit arXiv:2103.03020 [W] | **FAtiMA** | OCC ベース appraisal で共感を誘発する自律キャラクタ | multi-agent 3D 箱庭でのキャラクタ appraisal の直接先例 | 手作業のドメイン記述に依存 |
| **Pynadath & Marsella (2005)** IJCAI 2005 [W-snippet] | **PsychSim** | 決定理論 + 再帰的 ToM による社会シミュレーション、appraisal を ToM 推論と結合 | 領域3(ToM)と領域2(appraisal)の橋渡しの古典 | スケール・計算コスト |

**LLM ベースの appraisal / 感情シミュレーション(2023–2026):**

| 著者(年) | 貢献 | 接点 | 限界 |
|---|---|---|---|
| **Huang et al. (2023)** *EmotionBench*, arXiv:2308.03656 [W] | appraisal theory に基づく 428 状況/36 因子で、喚起前後の自己申告尺度で LLM の感情反応を人間と比較 | appraisal を評価軸に使う先駆 | 8 種の負感情限定、自己申告=ラベル的応答 |
| **Croissant, Frister, Schofield, McCall (2024)** *Chain-of-Emotion*, arXiv:2309.05076 / PLOS ONE 19(5):e0301033 [W] | appraisal を**明示的中間表現**とする Chain-of-Emotion 構造 + emotion memory がゲームエージェントの UX を改善 | **中間変数アーキテクチャ**の LLM 実装。ERRE の memory 統合と近い | 評価は UX/内容分析中心、内的妥当性は間接 |
| **Liu et al. (2024)** *CAPE*, arXiv:2410.14145 [W] | cognitive appraisal に基づく中国語感情生成データセット(個人特性・状況・個体評価) | appraisal 次元付き生成データ | 単一言語、下流妥当性限定 |
| **Srinivasan et al. (2025)** *RECAP*, arXiv:2509.10746 [W-snippet] | 患者入力を appraisal 中間変数(次元別 Likert)へ変換して生成を条件付け、固定オントロジー非依存 | **推論時に appraisal を経由**する透明な条件付け | 医療対話特化 |
| **Zhang et al. (2026)** *EmoLLM: Appraisal-Grounded Cognitive-Emotional Co-Reasoning*, arXiv:2603.16553 [未検証・著者要再確認] | Appraisal Reasoning Graph で事実/appraisal 次元/感情状態/応答戦略へ分解する co-reasoning | appraisal graph = 中間変数の構造化 | 査読ステータス不明、**著者名の一次確認が必要** |

> **注**: 「AppraisalGPT」は該当文献を確認できず、**存在しない可能性が高い**。CAMEL(Li et al. 2023 NeurIPS)は role-play society であり appraisal 感情モデルではない。

### 領域3: Theory of Mind(2023–2026 の LLM ToM 論争)

**A. 初期「創発」主張と批判:**

| 著者(年) | 貢献 | 限界 |
|---|---|---|
| **Kosinski (2023/2024)** arXiv:2302.02083 / PNAS 2024 DOI:10.1073/pnas.2405460121 [W] | 40 の false-belief 課題で GPT-4 が 75%、6歳児相当の ToM が自発創発したと提起 | 統制が甘くショートカット/汚染を排除できず。タイトルも "May"→"Might" と後退 |
| **Ullman (2023)** arXiv:2302.08399 [W] | ToM 原理を保つ**些細な改変**で成績が崩壊すると示す | 反例提示中心、体系化なし |
| **Sap, Le Bras, Fried, Choi (2022)** arXiv:2210.13312 / EMNLP 2022 [W] | SocialIQa・ToMi で GPT-3 が人間より大幅に低く「N-ToM はまだ遠い」 | GPT-3 世代、GPT-4 以降に直接は当てはまらない |
| **Shapira et al. (2023/2024)** arXiv:2305.14763 / EACL 2024 [W] | adversarial 例に脆弱、見かけの成功は **Clever Hans**(浅いヒューリスティクス)由来 | 内部機序の説明には踏み込まない |
| **Strachan et al. (2024)** *Nature Human Behaviour* 8(7):1285–1295, DOI:10.1038/s41562-024-01882-z [W] | 1,907 人の人間と GPT/LLaMA2 を同一バッテリーで比較。GPT-4 は誤信念・間接依頼・ミスディレクションで人間並み、**faux pas(失言認識)は苦手** | 行動一致は示すが「機序が人間と同型か」は判定不能と留保 |

**B. 手法(simulation-based prompting):**
- **Wilf, Lee, Liang, Morency (2023/2024)** *SimToM* / *Think Twice*, arXiv:2311.10227 / ACL 2024 [W]: Simulation Theory の視点取得に着想した 2 段階プロンプト(登場人物の知識で文脈をフィルタ→回答)。学習不要で既存手法を大きく上回る。限界: プロンプト工学による底上げで、内在的 ToM 獲得ではない。**← 領域7(ミラー/シミュレーション)と直結する重要ノード。**

**C. 新ベンチマーク(2023–2024):** FANToM(Kim et al. 2023, EMNLP, arXiv:2310.15421 [W])/ ToMBench(Chen et al. 2024, ACL, arXiv:2402.15052 [W])/ OpenToM(Xu et al. 2024, ACL, arXiv:2402.06044 [W])/ Hi-ToM(高階再帰 ToM, arXiv:2310.16755 [W])/ NegotiationToM(BDI ベース交渉, arXiv:2404.13627 [W])/ MMToM-QA(マルチモーダル, ACL 2024 Outstanding; **arXiv ID は未検証**だが論文実在は確実)/ BigToM(Gandhi et al. 2023, NeurIPS, arXiv:2306.15448 [W])。総じて **SOTA も人間に劣る**。

**D. 2025–2026 の論争の現在地(ERRE に最も重要):**
- **Gu, Tafjord et al. (2024/2026)** *SimpleToM*, arXiv:2410.13648 / ICLR 2026 [W]: 心的状態推論(明示)→**行動予測→行動判断(応用)**の多層で検証。SOTA は心的状態は当てるが「その知識を使った二次予測」で急落する乖離を露呈。**← 論点B の「行動予測での評価」の直接先例。**
- **Riemer et al. (2024/2025)** *Position: ToM Benchmarks are Broken for LLMs*, arXiv:2412.19726 / ICML 2025 [W]: 既存ベンチは「新しい相手への in-context 適応」を測れない。**"literal ToM"(他者行動予測)対 "functional ToM"(相手に合わせ適応)を区別**し、強い literal 性能は functional を含意しないと実証。**← ERRE の multi-agent 相互適応の評価枠に直結。**

**この領域の総括**: 論争は「genuine ToM か shortcut か」から **「ベンチマーク自体が測るべきものを測れているか」**へ移行。ERRE の「感情/appraisal 推定」は本質的に他者の心的状態推論=ToM の一種であり、この分野の懐疑(頑健でない/応用段で崩れる/相手適応が欠落)を正面から引き受ける必要がある。

### 領域4: Subjective Utility / 行動経済学

| 著者(年) | 貢献 | 接点 | 限界 |
|---|---|---|---|
| **Kahneman & Tversky (1979)** *Prospect Theory*, Econometrica 47(2):263–291, DOI:10.2307/1914185 [W] | 期待効用理論への反証。**参照点依存・損失回避・確率加重** | ERRE の「主観効用」中間変数の理論的核。reference dependence は「目標阻害/達成」と直結 | 元版は結果 2 個以下の gamble 限定 |
| **Tversky & Kahneman (1992)** Cumulative Prospect Theory, J. Risk & Uncertainty 5(4):297–323, DOI:10.1007/BF00122574 [W] | 累積決定加重で任意個数の結果へ拡張、fourfold pattern | 効用を状態依存で定式化 | パラメータが文脈・母集団依存 |
| **Ng & Russell (2000)** *Algorithms for IRL*, ICML 2000 [W] | 専門家方策から報酬を復元する IRL を定式化 | **behavior→utility 逆推定**の起点。ERRE の中核構想 | **報酬の非同定性(ill-posedness)を自ら指摘**(→ 論点C) |
| **Ziebart et al. (2008)** *MaxEnt IRL*, AAAI 2008 [W] | 最大エントロピーで軌跡分布を与え、多義性を確率的に解消 | 行動履歴からの分布的 utility 推定 | 分配関数が有限 MDP 依存、大規模でスケール困難 |
| **FA-IRL (2025)** arXiv:2510.06092 [W-snippet]; **"IRL Meets LLM Post-Training" survey (2025)** arXiv:2507.13158 [W-snippet] | RLHF/DPO を IRL として再解釈し、**LLM の訓練時報酬を behavior から逆推定**。失敗事例に着目して非同定性を緩和 | LLM を「効用推定器」として使う最新路線 | 非同定性を継承、"revealing example" の選別に依存 |

### 領域5: Active Inference / Free Energy Principle

| 著者(年) | 貢献 | 接点 | 限界 |
|---|---|---|---|
| **Friston (2010)** "The free-energy principle: a unified brain theory?", Nature Reviews Neuroscience 11(2):127–138, DOI:10.1038/nrn2787 [W] | 知覚・行動・学習を **自由エネルギー(予測誤差)最小化**の単一原理で統一 | ERRE の「予測誤差」中間変数の理論的源泉 | 感情は主題化せず、反証可能性批判あり |
| **Joffily & Coricelli (2013)** "Emotional Valence and the Free-Energy Principle", PLoS Comput Biol 9(6):e1003094, DOI:10.1371/journal.pcbi.1003094 [W] | **感情価を自由エネルギーの時間微分(1階・2階)として形式的に定義**し、hope/fear/relief 等の力学を導出 | 「感情=予測誤差の勾配」という ERRE 構想の最も直接的な formal 先例 | 理論・シミュレーション中心、人間データ検証が限定的 |
| **Seth (2013)** "Interoceptive inference, emotion, and the embodied self", Trends Cogn Sci 17(11):565–573, DOI:10.1016/j.tics.2013.09.007 [W] | 感情を**内受容信号の原因への能動的推論**とみなし、appraisal を予測処理へ拡張 | 領域6(身体性)と5(予測誤差)の橋渡し | 概念的レビュー、内受容予測誤差の分離測定は未確立 |
| **Seth & Friston (2016)** "Active interoceptive inference and the emotional brain", Phil Trans R Soc B 371(1708):20160007, DOI:10.1098/rstb.2016.0007 [W] | 感情脳を階層的生成モデルとして定式化、下降予測が autonomic reflex を制御 | 身体化された予測的感情の完成形 | 生成モデルは概念提案にとどまる |
| **Sun et al. (2025)** *npj Digital Medicine* 8:119, arXiv:2407.21051 [W] | actor–critic プロンプトを active inference で基礎づけ LLM 応答の信頼性向上 | LLM × active inference の実装例 | **「active inference」は比喩的枠組み**で真の変分自由エネルギー最適化ではない |

### 領域6: Embodied AI / embodied appraisal / interoception

| 著者(年) | 貢献 | 接点 | 限界 |
|---|---|---|---|
| **Prinz (2004)** *Gut Reactions*, Oxford UP, ISBN 9780195151459 [W] | 感情を **embodied appraisal**(身体状態の知覚でありつつ危険・喪失を知覚する)と定義、James–Lange を復権 | ERRE の「身体的回帰」(peripatos/chashitsu)が感情に果たす役割の哲学的基盤 | 哲学的議論中心、身体知覚が内容を担う機構は論争的 |
| **Barrett (2017)** "The theory of constructed emotion", SCAN 12(1):1–23, DOI:10.1093/scan/nsw154 [W] | 感情を生得的カテゴリでなく **内受容予測 + 概念的カテゴリ化による構成物** | 感情ラベルの ground-truth 否定(領域8と連続)の理論的裏付け | 構成主義は反証設計が困難、基本感情説との決着継続中 |
| **Damasio (1994)** *Descartes' Error* / **Bechara et al. (1997)** Science 275:1293–1295 [W] | **somatic marker 仮説**: 身体信号が vmPFC を介し不確実下の意思決定をバイアス | 「効用・選好が感情由来」という主張(領域4と接続) | Dunn et al. (2006) 等の批判あり(SMH の因果的必然性) |

> **ERRE への接点補足**: ERRE は locomotion(歩行)→sampling temperature の変調チャネルを配線済(ES-3)。これは「身体状態が認知(サンプリング)を変える」という embodied appraisal / interoceptive inference の**計算的類比**として位置づけられる。ただし ERRE は現状 interoception(内受容)を明示モデル化していない点が Seth/Barrett 系との差分。

### 領域7: Mirror-Neuron-Inspired Representation Alignment

**神経科学・哲学基盤:**
- **Rizzolatti & Craighero (2004)** "The Mirror-Neuron System", Annu Rev Neurosci 27:169–192, DOI:10.1146/annurev.neuro.27.070203.144230 [W]: 観察-実行マッチングの標準レビュー。限界: 相関記述中心、因果的必要性は射程外。
- **Gallese & Goldman (1998)** "Mirror neurons and the simulation theory of mind-reading", Trends Cogn Sci 2(12):493–501, DOI:10.1016/S1364-6613(98)01262-5 [W]: ミラー機構を **Simulation Theory** と架橋(theory-theory では予測されない)。限界: 概念的架橋が主。
- **Gallese (2005, 2007)** embodied simulation / shared manifold [W](2001 の shared manifold は号・頁未精査): ミラー機構を共感・間主観性へ一般化。
- **シミュレーション説 vs 理論説**: Gordon (1986) [W] / Goldman (2006) *Simulating Minds* [W]。ST 内でも Gordon(内省不要の急進派)と Goldman(自己内省前提)が対立。

**機械学習アナログ(自己-他者共有潜在空間):**

| 著者(年) | 貢献 | ERRE の問いとの接点 | 限界 |
|---|---|---|---|
| **Stadie, Abbeel, Sutskever (2017)** *Third-Person Imitation Learning*, arXiv:1703.01703 / ICLR 2017 [W] | 観察空間と行為者空間を GAN の domain confusion で **同一潜在空間に写像**し、視点非依存表現から三人称デモを模倣 | **観察↔実行の共有埋め込み**の代表的 ML 実装。論点A の直接的先例 | 視点差以外のドメインギャップに脆弱、discriminator 依存で不安定 |
| **Carauleanu, Vaiana, Rosenblatt, Berg, Schwerz de Lucena (2024)** *Towards Safe and Honest AI Agents with Neural Self-Other Overlap*, arXiv:2412.16325 [W] | 共感の神経科学に着想し **自己表現と他者表現の潜在的重なり(SOO)**を LoRA fine-tuning で増やし、欺瞞応答を大幅減(Mistral-7B 73.6→17.2%) | ERRE の multi-agent で「自己と他者の表現整合」を実装する最も具体的な現代路線 | **査読前 preprint + NeurIPS 2024 ワークショップ口頭 + LessWrong/EA Forum ブログ**が実体(母体 AE Studio)。"deception" の operationalization が narrow |
| **Zhu, Zhang, Ren, Huang, Xu, Wang (2025)** *Embodied Representation Alignment with Mirror Neurons*, arXiv:2509.21136 / ICCV 2025, pp.11948–11957 [W] | 行為理解と身体実行の中間表現が**自発的に整列**することを観察し、2 枚の線形層 + 対比学習で **action-observation 対称埋め込み**を明示的にアライン(相互情報最大化) | 論点A の中核:ミラー着想の representation alignment の最新実装 | 設計が単純(linear-map + contrastive)、般化検証はこれから |

> **[未検証]** *Proprioceptive-visual correspondence enables self-other distinction in humanoid robots*(arXiv:2606.13222)/ *Mirror-Neuron Patterns in AI Alignment*(arXiv:2511.01885)は検索でヒットするが著者・主張未確認。引用非推奨。

### 領域8: 感情データセットの品質・バイアス問題

| 論点 | 代表的知見・文献 | ERRE への含意 |
|---|---|---|
| **ground-truth の原理的不在** | 感情は内的現象で外部検証不能、「感情に ground truth は無い」。多くのデータセットは speaker の真の感情でなく **perceived emotion** を annotate すると明言(2024 vision survey / Barrett 2017)[W] | ラベル精度で評価する限り上限がある。ERRE の「中間変数経由」戦略の正当化 |
| **annotator 一致の低さ** | categorical 感情で **完全一致は約 20%**、約 25% は明確な多数決ラベルを欠く(Rethinking Emotion Annotations, arXiv:2412.07906 [W]) | 単一 gold label を前提にした評価は本質的にノイズを含む |
| **文化バイアス** | 多くのデータセットが西洋中心、表情/表出の文化差(東アジアは抑制的等)で global 適用時に劣化(bias mitigation survey, Springer 2025 [W]) | 偉人ペルソナ(多文化)を扱う ERRE で特に重大 |
| **appraisal ベース annotation の高一致** | Hofmann et al. (2020) は appraisal 次元(pleasantness/control/certainty 等)で **annotator が良好に一致**し自動予測も機能。**Troiano et al. (2023) crowd-enVENT**(6,600 event × 21 appraisal 次元)[W]、Dimensional Modeling(arXiv:2206.05238)[W] | **appraisal 中間変数は感情ラベルより annotation 信頼性が高い可能性** ― 論点B/データ品質の鍵 |
| **LLM は不確実性を再現しない** | Inoshita et al. (2026, arXiv:2604.27345)[W-snippet]: LLM は支配ラベルは当てるが **annotation 不一致(分布的不確実性)を再現できない** | ERRE で LLM を感情推定器に使う際、分布較正が課題 |
| **多言語化の潮流** | BRIGHTER(28 言語, arXiv:2502.11926)/ SemEval-2025 Task 11(arXiv:2503.07269)[W] | データ品質改善の最新動向 |

---

## 3. 深掘り論点 A / B / C の考察

### 論点A: ミラーニューロンの LLM 内再現可能性

**結論: 「神経再現」は不可能だが、"functional analog" としての self-other latent alignment は既に部分的に実装されており、ERRE の構成では predictive simulation として代替可能。ただし誇大主張は厳に避けるべき。**

ミラーニューロンを「観察行動表現と自己行動表現を共有潜在空間に整合させる実装概念」と限定して扱えば、機械学習側には既に三つの構成的対応物が存在する:

1. **Action-observation 対称埋め込み** — Zhu et al.(ICCV 2025)[W] が「観察表現と実行表現は訓練中に自発的に整列し、2 層 + 対比学習で明示的にアラインできる」ことを示した。これはミラーニューロンの「観察=実行の同一符号化」という最も定義的な性質の functional 実装である。
2. **Self-other overlap(自己-他者表現の重なり)** — AE Studio(2024)[W] が LoRA で自己表現と他者表現の潜在的重なりを増やせることを示した。ミラーニューロンと「共感/正直さ」を結ぶ神経科学的知見(自己-他者表現の overlap が honest behavior と相関)を工学的に逆利用したもの。
3. **Predictive simulation / 視点取得** — SimToM(Wilf et al. ACL 2024)[W] は、Simulation Theory(Gallese & Goldman 1998)を prompt レベルで実装し「他者の知識状態をシミュレートして推論する」。LLM 内での「他者のシミュレーション」は重み共有ではなくコンテキスト条件付き forward pass として実現される。

**本質的に再現できないもの / functional に代替されるもの:**

| 神経科学的性質 | LLM 内での地位 |
|---|---|
| 単一ニューロン粒度の観察-実行発火同一性 | **再現不可**(そもそも粒度が異なる。主張は圏外) |
| 運動系との身体的結合(motor resonance) | ERRE は身体を持つ(locomotion)が、LLM 本体は運動前野を持たない。**部分的に world-loop で functional 代替** |
| 観察と実行の**共有表現** | **functional に再現可能**(Zhu et al., Stadie et al.) |
| 他者の内部状態の**シミュレーション**(ST) | **functional に代替**(SimToM、ただし「浅い模倣」批判あり) |
| 自己-他者境界の可塑性 | **functional に操作可能**(SOO fine-tuning) |

**誇大主張回避のための境界明示**: これらはすべて **"functional analog であって神経再現ではない"**。特に (a) LLM の「共有潜在空間」は生物学的ミラー系の因果的役割(行為理解に必要か)を継承しないこと、(b) SimToM 型の「シミュレーション」は Shapira et al.(2024)の Clever Hans 批判 [W] を免れないこと、(c) SOO は査読前で robustness 未確立(narrow な deception ベンチ限定)であること — を必ず併記すべき。ERRE の設計整合性判断では「ミラーニューロンを実装した」ではなく「self-other alignment を functional に導入した」と表現するのが citation-accurate。

### 論点B: label prediction を超える評価の先行例

**結論: 4 軸(行動予測・介入成功・記憶更新一貫性・効用妥当性)を個別に扱う先行例は各々存在するが、4 軸を統合した評価方法論は確認できず = 明確な研究空白。**

軸ごとの先行例:

- **(i) 行動予測精度** — **SimpleToM**(Gu et al., ICLR 2026)[W] が「心的状態推論→**行動予測**→行動判断」の多層評価を確立し、「状態は当てるが行動予測で急落」という乖離を測った。Riemer et al.(ICML 2025)[W] の **functional ToM(他者行動予測としての ToM)**もこの軸。EMA(Gratch & Marsella)[W] は appraisal→coping→**行動変化**を出力するので、行動で評価する素地がある。
- **(ii) 介入/支援成功率** — **RESORT**(Yeo & Ong 2023 の appraisal 次元に基づく cognitive reappraisal)[W-snippet]、EmoBench の Emotional **Application** タスク(効果的な感情的応答の推奨)[W]、RECAP(医療対話の appraisal 条件付き支援)[W-snippet]。ただし「支援成功」を behavioral outcome で測る枠組みは臨床外では未成熟。
- **(iii) 記憶更新の一貫性** — Chain-of-Emotion(Croissant et al. 2024)[W] が emotion memory を持つが評価は UX 中心。**この軸を明示的な評価指標にした研究はほぼ空白**(Generative Agents(Park et al. UIST 2023)[W] の reflection/memory 一貫性評価が最も近いが感情特化ではない)。
- **(iv) 主観効用推定の妥当性** — Prospect Theory の枠(領域4)を LLM に適用する研究は始まったばかり(FA-IRL 2025 [W])。効用を latent にしたエージェントの妥当性検証は inverse RL の非同定性(論点C)に直面する。

**appraisal を latent 変数として評価する方法論の現状**: CAREBench(arXiv:2605.17176)[W]、"Beyond Context to Cognitive Appraisal"(Yeo & Jaidka, ACL Findings 2025, arXiv:2506.00334)[W] が **appraisal を明示的中間層に置き、forward(文脈→感情)と backward(感情→文脈)双方向の推論**を評価する。Tak et al.(*Mechanistic Interpretability of Emotion Inference*, ACL 2025, arXiv:2502.05489)[W] は LLM 内部の appraisal 表現を局在特定し **因果的に操作**して生成を steer した ― これは「appraisal が本当に中間変数として機能しているか」を内部表現レベルで検証する先進例。Reichman et al.(ICLR 2026, arXiv:2603.09205)[W-snippet]「Emotion is Not Just a Label」は感情を予測対象でなく潜在因子として扱う旗印的タイトル。ただし **これらはいずれも「appraisal→感情ラベル」の予測を最終評価に使っており、4 軸の behavioral 評価には至っていない**。

### 論点C: 中間変数の識別可能性 / confound

**結論: 行動から appraisal/utility/prediction-error を逆推定する試みは、inverse RL の非同定性という 25 年来の理論的壁を構造的に継承する。これは ERRE の中核的リスクであり、識別可能性を担保する追加制約(複数環境・複数割引率・正則化)が理論上必須。**

- **inverse RL の ill-posedness** — Ng & Russell(2000)[W] が定式化時点で「同一の最適方策を生む報酬関数は無数に存在する」と自ら指摘。Russell(1998)以来の根本問題。MaxEnt IRL(Ziebart et al. 2008)[W] は分布正則化で多義性を確率的に緩和したが根絶はしない。
- **identifiability の formal 特徴づけ** — Cao, Cohen, Szpruch(NeurIPS 2021, arXiv:2106.03498)[W]: エントロピー正則化下で「与えられた方策を生む報酬集合」を完全特徴づけし、**2 つの異なる割引率または十分に異なる環境**があれば報酬を定数を除いて復元可能と証明。→ ERRE への含意: **単一環境・単一エージェントの行動履歴だけでは appraisal/utility は原理的に非同定**。複数ゾーン(study/peripatos/chashitsu/agora/garden)という環境多様性が識別可能性の資源になりうる。
- **partial identifiability** — Skalse et al.(ICML 2023, arXiv:2203.07475)[W]: demonstration・trajectory comparison 等の **データ源ごとに部分同定性(invariance 集合)**を特徴づけた。→ どの behavioral データ源が appraisal のどの次元を identify するかを事前に設計する必要。
- **appraisal の underdetermination** — appraisal 理論自体も、同一行動が複数の appraisal 布置から生じうる(例: 回避行動は「脅威×低 coping」からも「低 relevance」からも生じる)。Scherer CPM の逐次チェックは実験的に分離困難(領域2で既述)。crowd-enVENT [W] で annotator 一致が高いのは **状況記述テキストから**の annotation だからであり、**行動のみからの逆推定**は別問題。
- **LLM 固有の confound** — LLM を appraisal 推定器に使うと、(a) persona/文脈による表面的手掛かり(Clever Hans, Shapira et al. [W])、(b) annotation 分布の不確実性を潰す(Inoshita et al. [W-snippet])という二重の confound が入る。

**ERRE 設計への含意(判断は Fable に委ねるが、事実として)**: 行動履歴から中間変数を「推定できるか」は、識別可能性を担保する **設計上の追加制約**(複数環境の活用、appraisal 次元の事前 anchor、内部表現の mechanistic 検証)の有無に決定的に依存する。単純な「behavior→appraisal 回帰」は非同定に陥る公算が高い。

---

## 4. 未解決問題(open problems)― ERRE が攻めうる空白

1. **[最大の空白] 4 軸統合評価方法論の不在**: label 精度を超える 4 軸(行動予測・介入成功・記憶更新一貫性・効用妥当性)を **単一フレームワークで統合**した評価は先行研究に存在しない(論点B)。ERRE は multi-agent 3D 箱庭という **behavioral outcome を自然に観測できる基盤**を持つため、この空白を埋める構造的優位がある。
2. **記憶更新の一貫性を評価軸にする研究の空白**: (iii) の軸は Generative Agents 系の reflection 一貫性評価が最も近いが、**感情/appraisal に特化した記憶更新一貫性の指標**は未確立。ERRE の memory stream + reflection(CoALA/PIANO 系)はこの空白に直接位置する。
3. **単一環境での中間変数の非同定性**: inverse RL の identifiability 理論(Cao et al. 2021 [W])は「複数環境/複数割引率があれば識別可能」と示すが、**appraisal 中間変数について環境多様性が識別可能性をどこまで回復するか**は未検証。ERRE の 5 ゾーン構成はこの実験的検証の apparatus になりうる。
4. **appraisal 中間層が「本当に中間変数として機能しているか」の因果的検証**: Tak et al.(2025)[W] が mechanistic interpretability で内部表現を操作した先例はあるが、**行動レベルの因果(appraisal を介入すると行動がどう変わるか)**を閉ループで検証した研究は乏しい。ERRE の locomotion→sampling チャネル(ES-3)は「身体状態→中間変数→行動」の因果配線の検証台。
5. **functional ToM(相手適応)の標準ベンチ不在**: Riemer et al.(2025)[W] が literal/functional の区別を提起したが functional ToM のベンチは揺籃期。ERRE の multi-agent 相互作用は functional ToM の観測環境になりうる。
6. **予測誤差ベース感情(Joffily & Coricelli 2013 [W])の LLM エージェント実装の空白**: 「感情=自由エネルギーの時間微分」という formal 定義を、実際の LLM エージェントの閉ループで実装・検証した研究は確認できない(Sun et al. 2025 は比喩的 [W])。ERRE の予測誤差中間変数はここに位置しうる。
7. **appraisal annotation の高信頼性を LLM 推定に転写できるか**: crowd-enVENT [W] は appraisal 次元の annotator 一致が高いことを示すが、**LLM が行動から appraisal を推定した時に同等の信頼性が保てるか**は未検証(Inoshita et al. [W-snippet] は不確実性再現の失敗を示唆)。
8. **予算ゼロ制約下の中間変数推定**: 上記研究の多くは GPT-4 級 API 前提。**ローカル小規模モデル(qwen3:8b, think=false)で appraisal 中間変数推定がどこまで成立するか**は完全な空白。ERRE 固有の制約が新しい問いを生む。
9. **self-other overlap の robustness**: SOO(AE Studio 2024 [W])は narrow な deception ベンチ限定・査読前。**multi-agent 社会シミュレーションでの self-other alignment の一般化**は未検証の空白。

---

## 5. 参考文献リスト

### A. 本セッションで web 検証済み [W](arXiv ID/DOI/venue を確認)

**Theory of Mind:**
1. Kosinski (2023/2024). *Theory of Mind May/Might Have Spontaneously Emerged in LLMs*. arXiv:2302.02083 / PNAS 2024, DOI:10.1073/pnas.2405460121
2. Ullman (2023). *LLMs Fail on Trivial Alterations to ToM Tasks*. arXiv:2302.08399
3. Sap, Le Bras, Fried, Choi (2022). *Neural Theory-of-Mind?*. arXiv:2210.13312 / EMNLP 2022
4. Shapira et al. (2023/2024). *Clever Hans or Neural ToM?*. arXiv:2305.14763 / EACL 2024
5. Strachan et al. (2024). *Testing theory of mind in LLMs and humans*. Nature Human Behaviour 8(7):1285–1295, DOI:10.1038/s41562-024-01882-z
6. Wilf, Lee, Liang, Morency (2023/2024). *SimToM / Think Twice*. arXiv:2311.10227 / ACL 2024
7. Kim et al. (2023). *FANToM*. arXiv:2310.15421 / EMNLP 2023
8. Chen et al. (2024). *ToMBench*. arXiv:2402.15052 / ACL 2024
9. Xu et al. (2024). *OpenToM*. arXiv:2402.06044 / ACL 2024
10. Wu et al. (2023). *Hi-ToM*. arXiv:2310.16755 / Findings of EMNLP 2023
11. *NegotiationToM* (2024). arXiv:2404.13627 / Findings of EMNLP 2024
12. Gandhi et al. (2023). *BigToM*. arXiv:2306.15448 / NeurIPS 2023 D&B
13. Gu, Tafjord et al. (2024/2026). *SimpleToM*. arXiv:2410.13648 / ICLR 2026
14. Riemer et al. (2024/2025). *Position: ToM Benchmarks are Broken for LLMs*. arXiv:2412.19726 / ICML 2025

**Appraisal / 感情シミュレーション / 評価:**
15. Ortony, Clore, Collins (1988). *The Cognitive Structure of Emotions* (OCC). Cambridge UP
16. Roseman (1991). *Appraisal Determinants of Discrete Emotions*. Cognition & Emotion 5(3):161–200, DOI:10.1080/02699939108411034
17. Gratch & Marsella (2004). *A Domain-Independent Framework for Modeling Emotion* (EMA). Cognitive Systems Research 5(4):269–306, DOI:10.1016/j.cogsys.2004.02.002
18. Becker-Asano (2008). *WASABI*. IOS Press, ISBN 9781586039110
19. Dias, Mascarenhas, Paiva (2014). *FAtiMA Modular*. DOI:10.1007/978-3-319-12973-0_3; FAtiMA Toolkit arXiv:2103.03020
20. Huang et al. (2023). *EmotionBench*. arXiv:2308.03656
21. Sabour et al. (2024). *EmoBench*. arXiv:2402.12071 / ACL 2024
22. *EmoBench-M* (2025). arXiv:2502.04424
23. Croissant, Frister, Schofield, McCall (2024). *Appraisal-Based Chain-of-Emotion Architecture*. arXiv:2309.05076 / PLOS ONE 19(5):e0301033
24. Liu et al. (2024). *CAPE*. arXiv:2410.14145
25. Yeo & Jaidka (2025). *Beyond Context to Cognitive Appraisal: Emotion Reasoning as a ToM Benchmark*. arXiv:2506.00334 / ACL Findings 2025
26. Tak, Banayeeanzade, Bolourani, Kian, Jia, Gratch (2025). *Mechanistic Interpretability of Emotion Inference in LLMs*. arXiv:2502.05489 / ACL 2025
27. *CAREBench: Evaluating LLMs' Emotion Understanding by Assessing Cognitive Appraisal Reasoning* (2026). arXiv:2605.17176
28. *Large language models show fragile cognitive reasoning about human emotions* (2025). arXiv:2508.05880

**主観効用 / inverse RL 識別可能性:**
29. Kahneman & Tversky (1979). *Prospect Theory*. Econometrica 47(2):263–291, DOI:10.2307/1914185
30. Tversky & Kahneman (1992). *Cumulative Prospect Theory*. J. Risk & Uncertainty 5(4):297–323, DOI:10.1007/BF00122574
31. Ng & Russell (2000). *Algorithms for Inverse Reinforcement Learning*. ICML 2000
32. Ziebart et al. (2008). *Maximum Entropy IRL*. AAAI 2008
33. Cao, Cohen, Szpruch (2021). *Identifiability in Inverse Reinforcement Learning*. arXiv:2106.03498 / NeurIPS 2021
34. Skalse, Farrugia-Roberts, Russell, Abate, Gleave (2023). *Invariance in Policy Optimisation and Partial Identifiability in Reward Learning*. arXiv:2203.07475 / ICML 2023

**Active Inference / 身体化:**
35. Friston (2010). *The free-energy principle: a unified brain theory?*. Nature Reviews Neuroscience 11(2):127–138, DOI:10.1038/nrn2787
36. Joffily & Coricelli (2013). *Emotional Valence and the Free-Energy Principle*. PLoS Comput Biol 9(6):e1003094, DOI:10.1371/journal.pcbi.1003094
37. Seth (2013). *Interoceptive inference, emotion, and the embodied self*. Trends Cogn Sci 17(11):565–573, DOI:10.1016/j.tics.2013.09.007
38. Seth & Friston (2016). *Active interoceptive inference and the emotional brain*. Phil Trans R Soc B 371(1708):20160007, DOI:10.1098/rstb.2016.0007
39. Prinz (2004). *Gut Reactions: A Perceptual Theory of Emotion*. Oxford UP, ISBN 9780195151459
40. Barrett (2017). *The theory of constructed emotion*. SCAN 12(1):1–23, DOI:10.1093/scan/nsw154
41. Bechara, Damasio, Tranel, Damasio (1997). *Deciding advantageously before knowing the advantageous strategy*. Science 275(5304):1293–1295
42. Sun et al. (2025). *An active inference strategy for prompting reliable responses from LLMs in medical practice*. npj Digital Medicine 8:119 / arXiv:2407.21051

**ミラーニューロン / self-other alignment:**
43. Rizzolatti & Craighero (2004). *The Mirror-Neuron System*. Annu Rev Neurosci 27:169–192, DOI:10.1146/annurev.neuro.27.070203.144230
44. Gallese & Goldman (1998). *Mirror neurons and the simulation theory of mind-reading*. Trends Cogn Sci 2(12):493–501, DOI:10.1016/S1364-6613(98)01262-5
45. Gordon (1986). *Folk Psychology as Simulation*. Mind & Language 1(2):158–171, DOI:10.1111/j.1468-0017.1986.tb00324.x
46. Goldman (2006). *Simulating Minds*. Oxford UP
47. Stadie, Abbeel, Sutskever (2017). *Third-Person Imitation Learning*. arXiv:1703.01703 / ICLR 2017
48. Carauleanu, Vaiana, Rosenblatt, Berg, Schwerz de Lucena (2024). *Towards Safe and Honest AI Agents with Neural Self-Other Overlap*. arXiv:2412.16325 / NeurIPS 2024 Workshop(**査読前 preprint + ワークショップ + ブログ**, 母体 AE Studio)
49. Zhu, Zhang, Ren, Huang, Xu, Wang (2025). *Embodied Representation Alignment with Mirror Neurons*. arXiv:2509.21136 / ICCV 2025

**データセット品質・バイアス / ERRE 関連アーキテクチャ:**
50. *Rethinking Emotion Annotations in the Era of LLMs* (2024). arXiv:2412.07906
51. Troiano et al. (2023). *crowd-enVENT*(appraisal 次元付きコーパス)/ *Dimensional Modeling of Emotions in Text with Appraisal Theories*. arXiv:2206.05238
52. *BRIGHTER* (2025). arXiv:2502.11926 / *SemEval-2025 Task 11*. arXiv:2503.07269
53. Park et al. (2023). *Generative Agents: Interactive Simulacra of Human Behavior*. UIST 2023

### B. Training knowledge に基づく定番文献 [K](本セッションで一次 URL 未確認、ただし広く既知)

54. Picard (1997). *Affective Computing*. MIT Press
55. Lazarus (1991). *Emotion and Adaptation*. Oxford UP
56. Scherer (2001). *Appraisal Considered as a Process of Multilevel Sequential Checking* (CPM). in *Appraisal Processes in Emotion*, Oxford UP
57. Pynadath & Marsella (2005). *PsychSim*. IJCAI 2005 [W-snippet で存在確認]
58. Damasio (1994). *Descartes' Error*. Putnam/Grosset

### C. web スニペットのみで確認 [W-snippet](中確度、一次 fetch 未実施)

59. Poria, Majumder, Mihalcea, Hovy (2019). ERC survey. arXiv:1905.02947
60. *Affective Computing in the Era of LLMs: A Survey from the NLP Perspective* (2024). arXiv:2408.04638
61. Srinivasan et al. (2025). *RECAP*. arXiv:2509.10746
62. Reichman et al. (2026). *Emotion is Not Just a Label*. arXiv:2603.09205 / ICLR 2026
63. Inoshita, Zhou, Kawai, Yada (2026). *LLMs Capture Emotion Labels, Not Emotion Uncertainty*. arXiv:2604.27345
64. FA-IRL (2025). *Learning from Failures: LLM Alignment through Failure-Aware Inverse RL*. arXiv:2510.06092
65. *Inverse Reinforcement Learning Meets LLM Post-Training* survey (2025). arXiv:2507.13158
66. RESORT framework / Yeo & Ong (2023)(6 appraisal 次元の cognitive reappraisal)

### D. 未検証・要注意 [未検証](引用前に一次確認必須。捏造リスク排除できず)

- **Zhang et al. (2026). *EmoLLM*. arXiv:2603.16553** — 存在は示唆されるが **著者名の一次確認が必要**
- **"When Preferences Fail to Become Incentives" arXiv:2606.22974** — 存在確認できず、**捏造の可能性**
- **MMToM-QA の arXiv ID**(2401.08743 とされる)— ACL 2024 Outstanding 受賞・論文実在は確実だが arXiv ID を verbatim 未確認
- **arXiv:2606.13222**(humanoid self-other distinction)/ **arXiv:2511.01885**(Mirror-Neuron Patterns in AI Alignment)— 著者・主張未確認、**引用非推奨**
- **「AppraisalGPT」** — 該当文献なし、**存在しない可能性が高い**

---

### サーヴェイ担当からの申し送り(Fable への引き継ぎメモ)

- **最も load-bearing な発見**: (1) label を超える 4 軸統合評価は先行研究に**存在しない空白**(論点B/未解決1)、(2) appraisal 中間変数は感情ラベルより **annotation 信頼性が高い**という経験的裏付けがある(crowd-enVENT)一方、(3) 行動からの逆推定は **inverse RL 非同定性**を構造的に継承する(論点C)。この (2) と (3) の緊張が ERRE 設計判断の核心になると思われる。
- **引用注意**: Self-Other Overlap(参考文献48)は査読前 preprint + ワークショップ + ブログが実体。"ミラーニューロンを実装した"ではなく "self-other alignment の functional analog" と表現するのが citation-accurate(論点A)。
- **要一次確認**: セクション D の 5 件は本文中でも [未検証] 表記のまま扱った。ERRE の正式ドキュメント(docs/references.md への登録)に上げる際は一次ソース確認を推奨。
