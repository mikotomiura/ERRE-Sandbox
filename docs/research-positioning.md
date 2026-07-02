# 研究ポジショニング

> このファイルは「なぜこの研究が成立するか」の上流 SSOT。
> `docs/functional-design.md` / `docs/architecture.md` はここから導出される。
> 本文中の外部根拠には `[n]` を付け、`docs/references.md` (中央書誌) を参照する。
>
> **注記 (retroactive 生成)**: 本ファイルは Phase R1 を遡及的に実行して
> 2026-06-28 に作成した。問い・仮説・差分は新規に発明したものではなく、
> 既に進行済みの研究 chain (中核命題 → terminal close → M13 身体性 substrate arc)
> から **抽出** したものである。経緯の一次記録は `.steering/`・auto-memory・
> `src/erre_sandbox/evidence/` にある。本ファイルはそれらを「研究の所在」として
> 一枚に圧縮する役割を持つ。

## 1. コアの問い

- **一言の問い**: 偉人の認知習慣を再実装した LLM エージェントにおいて、「意図的非効率性」と
  「身体的回帰」を一級の設計プリミティブとして与えたとき、**閉ループ的で経路依存的な
  de-novo の発散 (知的創発)** は立ち上がるのか。
- **一言のメッセージ (現在の最前線)**: Oppezzo & Schwartz (2014) の「歩くと拡散的思考が伸びる」
  効果 [1] を、身体を持たない確率機器 (LLM) で再現できるか。ただし人間の機構は身体側に
  寄っている疑いが強いため、in-silico で測れるのは **「身体を経由しない代替ルート
  (移動で構造化された記憶の組み替え) だけで拡散が駆動できるか」** に限られる。
- **流行りからの離脱**: 現行の LLM エージェント研究は「効率」「タスク達成」「人間水準の再現」を
  暗黙の目的関数に置く。本研究はその逆 — **非効率・身体運動・注意の弛緩が高次認知を駆動する**
  という認知神経科学の知見 [1] を設計の一級プリミティブに昇格させ、効率最大化が原理的に
  到達できない種類の創発を観察可能にする。「より賢いエージェント」ではなく「**違う道で
  創発に届くエージェント**」を問う。

## 2. 目指す世界 (Vision)

- **実現したい世界**: 固定スクリプトでも効率最適化でもなく、空間を歩き・身体的習慣に回帰し・
  注意を意図的に弛緩させることで、**個体の規則からは予測できない文化・儀式・発散的アイデアが
  立ち上がる「生きた村」**。ゲーム開発者がそれを NPC ミドルウェアとして埋め込める形で。
- **実現したときに変わること**:
  - 生成エージェント社会研究が「人間の模倣度」ではなく「**創発の機構的十分条件**」を
    問えるようになる。
  - 「身体性は創造性に本質的か」という認知科学の問いに、in-silico の対照実験という
    新しい探索器具を提供する (人間被験者実験の事前 probe)。
  - 効率を絶対善としない AI 設計の存在証明。

## 3. 先行研究ランドスケープ (暫定)

> ⚠️ ここは positioning を書ける最低限の地図。網羅的精読は後続 `/literature-review` の仕事。

- **生成エージェント社会の潮流**: Park et al. (2023) の Generative Agents [2] が memory stream +
  reflection + planning で創発的社会行動を示し、Project Sid / PIANO [4] が多体・多モジュール
  認知で「AI 文明」へスケールした。いずれも **目的関数は人間らしさ・社会的整合・規模**であり、
  「非効率を意図的に注入する」設計軸は持たない。
- **認知アーキテクチャの基盤**: CoALA (Sumers et al. 2023) [3] が memory × action × decision の
  公理系を与える。本研究の認知サイクルはこれを基盤に置くが、**ERRE モード (歩行/茶室/座禅/
  守破離) による状態依存サンプリング変調**を追加する点が独自。
- **経験的アンカー (身体↔創造性)**: Oppezzo & Schwartz (2014) [1] — 歩行が拡散的思考を伸ばす。
  決定的なのは **屋内トレッドミルで壁を向いて歩いても効果が出た**こと → 主因は「新しい風景=
  環境新奇性」ではなく、より内的・身体的なもの (覚醒/固有感覚/DMN 脱抑制) に寄る。
  Thabane et al. (2026) の系統的レビュー・メタ分析 [6] はこの効果を **発散側に限って強く支持**する:
  divergent thinking で d=0.93 [0.44, 1.42] (moderate certainty)、対して convergent thinking は
  d=0.16 [−0.31, 0.63] の **null (very low certainty)**。ただし divergent の positive 研究の多くが
  Oppezzo 単独に由来する点が inconsistency として GRADE で減点されており、**warrant としては強いが
  「効果は身体側に寄る」という機構主張の direct evidence ではない** (§4 の非対称・§7 の過大主張ガード)。
- **文体的同一性の計測**: Burrows Δ (2002) [5] を persona identity drift の計測に転用
  (M9-eval Tier-A)。

## 4. 差分 = 研究の所在

> 「先行研究と被っていないか」ではなく、「先行研究 ↔ §2 で目指す世界 の間に何が
> 研究として立ち上がるか」を書く。

- **先人がやり残していること**: 生成エージェント研究 [2][4] は創発を **示した**が、その創発が
  「効率最適化の副産物」なのか「意図的非効率が駆動した別ルート」なのかを **分離していない**。
  身体↔創造性の心理学 [1] は人間で示したが、その効果が **身体側機構**に由来するのか
  **記憶再編側だけでも十分**なのかを切り分ける器具を持たない (人間からは身体を外せない)。
- **自分の問いが埋める空白**: LLM は身体を持たないがゆえに、Oppezzo 効果の **唯一の操作可能
  チャネル = 「移動が、どの記憶を次の生成の条件にするかを変える (空間的検索の再編)」** だけを
  単離できる。これは人間実験では原理的に不可能な切断。**「記憶再編チャネル単独で
  path-dependent な発散の種が生めるか」**という、人間でも先行 AI 研究でも測れなかった問いが
  ここで立ち上がる。
- **皮肉な非対称 (研究メッセージの核)**: 人間の効果主機構は身体側 (再現不能)、我々が操作できる
  のは記憶再編側のみ。ゆえに positive が出ても「Oppezzo を再現した」ではなく
  「**移動で構造化された記憶だけで拡散が駆動できる、という別ルートの十分性**」の実証になる。
  人間とは違う道で同じ現象に届く、という主張。
- **なぜ今、自分にこれができるのか**: ローカル LLM + 3D 空間 substrate + 凍結された認知契約
  (`schemas.py`) + 事前登録された verdict 機構が揃い、**身体を外した対照実験**を予算ゼロで
  反復できる環境が既に建っている (M2 機能完了 → M13 substrate arc)。

## 5. 仮説

> 反証可能な形で。中核命題は既に一度 close 済み (§8 参照)。現在の最前線は M13 arc の ES 系列。

- **H0 (中核命題、CLOSED)**: 閉ループの認知だけで de-novo の path-dependent 発散が立ち上がる。
  → **bounded-non-divergence で CLOSE** (反証でなく「substrate 未建設」の疑い、§8)。
- **H1 (ES-1、GO)**: 空間的移動は、記憶の浮かび方 (検索) を **経路依存**に変える土台を持つ。
  → 非循環 scenario 実走で **GO** (necessary-substrate conformance、median D_obs=0.667 /
  CI lower=0.619)。
- **H2 (ES-2、bounded INCONCLUSIVE)**: その土台の上で経験を組み替え、**matched null を超える
  path-dependent な novel idea seed** を生成できる。
  → measurable 化 (set-Jaccard → 有向遷移分布 + JS divergence) を施しても **真の low-power で
  INCONCLUSIVE**。JS は非飽和を達成したが遷移分布がほぼ一様で、全 64 seed で d_obs<d_self
  (metric artifact でなく真の検出力不足と峻別済)。これは **bounded finding** であり、後続
  H3/H4 の **必須前提ではない** (下記 arc 再定義)。
- **H3 (ES-3、GO)**: 歩行 (locomotion 運動史) は実際の sampling 変調 channel を駆動できる。
  → locomotion EMA → resolved sampling (temperature primary / top_p secondary) channel が、
  因果・分離・恒等性消失で配線されたことを **GO** で実証 (D_loco=0.0468 / CI_lower=0.0453 ≥
  AMP_FLOOR、zone-function control=7.4e-17 で非トートロジー、ablation で bit-identical 消失)。
  ただしこれは **channel 配線の conformance** であって「歩行 → 創造的発散」そのものではない。
- **H4 (ES-4、bounded closed as measurement line; effect unjudged)**: その channel を LLM 生成に
  当てたとき、locomotion 駆動の温度 actuator が qwen3:8b (frozen decoding) 出力を divergent-favoring
  regime に動かす sufficiency があるか。→ staged (Phase 0 gate → Phase 1) の **actuator sufficiency
  test** として起票したが、**計測ラインが frozen apparatus 下で建たず bounded close**。主語 =
  Phase 0 sealed run `INVALID_SCORER` + 方向 C offline 診断 `NO_VALID_SCORER`。二重 bottleneck =
  ① on-task rarity 計測器を非循環に測れない (全 embedding rarity が leave-anchor-out audit で崩落 =
  R_object anchor の自己認識循環、唯一 lexical Jaccard も entropy 還元可能 + 効果 floor 未満) +
  ② actuator channel の near-null 信号 (温度 +0.3 で estimand 構造ほぼ不変)。**棄却されたのは ES-4 の
  計測器であって H4 効果ではない — H4 効果は未判定** (効果判定 gate に未到達、反証していない)。GO でも
  中核命題再証明でも genuine 創造でもない (§7)。D (GPU-only scorer) / richer-channel は §8 の
  pre-validation gate 付き preserved re-entry。

> **arc 再定義 (旧直列鎖の撤回)**: 当初の鎖は「ES-2 が path-dependent な種を生み、その種が
> ES-3 で sampling 変調を介して発話に効く」という **直列依存**で描いていた。ES-2 が bounded
> INCONCLUSIVE に留まったため、**未検証の入力 (種生成チャネル) を下流に流さない**。ES-3/ES-4 は
> ES-2 GO に依存せず、**ES-1 が建てた spatial→memory channel の上に locomotion→sampling を
> 直接配線する並列 seam** として正規化する (ES-2 は再訪可能な別 seam として保全)。

## 6. シナリオ

> 問い → 検証 → 主張 までの筋。

1. **substrate を建てる (ES-1)**: blind uniform walk を実 ADJACENCY 上で走らせ、形成位置が
   walk の帰結になる非循環設計で「移動 → 経路依存記憶」の土台の有無を測る → GO。
2. **種を生む (ES-2、並列 seam・bounded)**: 凍結 substrate 上で idle replay-walk
   (preferential-return) により経験を組み替え、有向遷移分布 + JS divergence の連言 verdict で
   「path-dependent な種生成」を測る → measurable 化しても **真の low-power で INCONCLUSIVE**。
   未検証ゆえ下流に流さず、bounded finding として保全 (再訪可能な別 seam)。
3. **channel を配線する (ES-3)**: ES-2 の種を介さず、ES-1 の spatial→memory 土台の上に
   locomotion (運動史 EMA) → sampling (temperature/top_p) channel を直接配線し、因果・分離・
   恒等性消失 (ablation で bit-identical 消失) で conformance を測る → GO。
4. **actuator を校正する (ES-4、staged) → 計測ライン bounded close**: ES-3 channel を LLM 生成に
   当て、locomotion 駆動の温度 actuator の sufficiency を staged に測ろうとしたが、**frozen apparatus
   下で on-task rarity 計測器が非循環に建たず bounded close** (Phase 0 `INVALID_SCORER` + 診断
   `NO_VALID_SCORER`)。棄却は計測器であって H4 効果ではない (未判定)。
5. **主張 (measurement line close / H4 効果未判定)**: ES-4 は actuator sufficiency について
   **sufficiency も insufficiency も claim しない** — valid 計測器が建たず verdict に未到達。
   near-null channel signal は再走優先度を下げる forensic であって negative verdict ではない。
   forward = 別の sampling proxy でも GPU-only-scorer 再走でもなく、**フル仮説をテスト可能にする
   substrate 建設 + 非循環 measurement prevalidation を先に建てる** (§8)。ES-1/ES-3 の GO
   conformance は次 substrate milestone の入力資産として保全する。
6. **substrate を建てる (scoping FROZEN 2026-07-01)**: 次 milestone = **situated 3D embodiment**
   (名指しの missing substrate) を新規次元に、outcome を structural/behavioral に付け替え、計測基盤
   ファーストで **二層 D0 pack** (structural conformance + semantic prevalidation) を G-GEAR 先行で
   valid 化してから cross-machine Godot フル apparatus を次工程へ。これは substrate + 計測能力の前進で
   あって **divergence 仮説の検定ではない** (§8 claim 境界・2×2 停止規則)。

## 7. 成功時の社会的インパクト

- **成功時の影響**: 「創発に身体は必須か」という認知科学の長年の問いに、**人間からは外せない
  変数を外せる** in-silico 対照という新しい方法論を提供する。生成エージェント社会研究に
  「効率以外の目的関数」の存在証明を与える。ゲーム/エンタメに「効率最適化では作れない
  生きた村」を実装可能にする。
- **過大主張ガード (スコープ内に収める)**: 本研究は **身体性そのものを claim しない**。
  神経科学類推および Oppezzo (2014) [1] / Thabane meta-analysis (2026) [6] は *warrant であって
  direct causal evidence ではない* と凍結明記する (divergent は moderate certainty で強根拠、
  convergent null は very low certainty)。positive でも「人間機構の再現」ではなく「別ルートの
  十分性」に主張を限定する。ES-2 が測るのは厳密には **「発散の前段 = 経路依存的な種の生成」**で
  あって発散そのものではない (claim 境界)。
- **ES-4 の claim 境界 (計測ライン close / 何も claim しない)**: ES-4 は actuator sufficiency に
  ついて **sufficiency も insufficiency も claim しない**。valid な非循環計測器が frozen apparatus
  下で建たず verdict に未到達だからである (Phase 0 `INVALID_SCORER` + 診断 `NO_VALID_SCORER`)。
  **棄却されたのは ES-4 の計測器であって H4 効果ではない — H4 効果は未判定** (「歩行が genuine な
  発散を生む」とも「単一 temperature 軸では発散を担えない」とも言わない)。near-null channel signal は
  再走優先度を下げる forensic であって negative verdict ではない。大 dose / richer-channel は現 ES-4
  frozen honest envelope の外ゆえ扱わず、別仮説として pre-validation gate 付きで re-entry しうる (§8)。

## 8. 成功基準 / 反証条件

- **ES-4 の disposition (計測ライン bounded close)**: ES-4 は staged で起票し Phase 0 sealed run を
  実走したが、verdict = `INVALID_SCORER` (Phase 0) + `NO_VALID_SCORER` (方向 C offline 診断) →
  **on-task rarity 計測ラインを bounded close**。主語は計測器 validity の失敗であって H4 効果ではない
  (効果判定 gate に未到達 = **H4 効果は未判定**)。
- **「測れるかをまず測る」= arc-level 規律 (明文化)**: 中核命題 H0 が検出力壁で、ES-4 が計測器の
  非トートロジー壁で死んだ二重の経験を踏まえ、**sealed run に投資する前に計測 validity を非循環に
  establish できることを必須ゲート**とする。この 2 連続失敗は **research-management / VoI rationale**
  であって arc 命題への empirical 反証ではない (ES-1/ES-3 GO を巻き込まない)。
- **反証条件 / verdict 語彙 (falsification)**:
  - ES-4 Phase 0/1 の verdict 語彙 = `PASS` / `INCONCLUSIVE_UNDERPOWERED` / `INVALID_SCORER` /
    `INVALID_TASK_BATTERY` / `NO_GO_EFFECT_ABSENT`。**apparatus-invalid を低検出力と混同しない**
    (ES-2 で「metric artifact と真の low-power を峻別」した同型規律)。実際に発火したのは
    `INVALID_SCORER` (計測器 validity)。
  - **`NO_GO_EFFECT_ABSENT` は今回 "未取得 verdict"** — ES-4 は効果判定 gate に到達していないため
    「単一 temperature 軸では発散を担えない」という negative は **取得していない** (near-null channel
    は forensic であって verdict でない)。この語彙は将来 valid 計測器下でのみ発火しうる。
  - 中核命題 H0 は既に bounded envelope 内で **non-divergence として CLOSE** 済み — 同一空間の
    薄いプロキシ再走は禁止 (継続バイアスガード)。ES-4 も中核命題 (閉ループ δ 増幅) と機構が別
    (単一 forward channel・no feedback amplification) ゆえ再 litigate しない。
  - **two-sided guard**: positive/negative の **両方が finding**。**verdict 未取得の ES-4 を「成功する」
    とも「H4 は偽」とも書かない** (forking-paths ガード)。
- **forward / re-entry (disposition ADR FROZEN 2026-07-01)**: forward = 別 sampling proxy でも
  GPU-only-scorer 再走でもなく、**フル仮説をテスト可能にする substrate 建設**。次 substrate milestone は
  long horizon / memory recomposition / situated 3D state / closed-loop action-observation のいずれか新規
  次元を追加し、第一成果物に **非循環 measurement prevalidation (`D0 pack`)** を含める。D (GPU-only scorer
  再入) / richer-channel は **pre-validation gate 付き preserved re-entry** = GPU 禁止でなく「sealed run 前に
  非循環 validity を示せない scorer を block」。
- **substrate milestone scoping (方向決定 ADR FROZEN 2026-07-01)**: 上記 forward を具体化。**採用 =
  situated 3D embodiment を新規生成次元** (post_close_direction 名指しの「実際の missing substrate」)、
  **outcome class を semantic-text 発散から structural/behavioral に付け替える** (ES-1/ES-3 が非循環に測れた
  precedent)。順序 = **計測基盤ファースト** (G-GEAR 上で二層 D0 pack を先行 valid 化してから cross-machine
  Godot フル apparatus を次工程に支出)。**二層 D0 pack** = (a) structural conformance track [D0a synthetic
  trace + D0b 最小 live/replay smoke] + (b) semantic reference-free-originality prevalidation track (壁を攻め
  D re-entry を開く)。**claim 境界**: この milestone は substrate 建設 + 計測能力の前進であって
  **divergence 仮説そのものの検定ではない** (necessary-substrate + measurement-capability、ES-1/ES-3 同型)。
  **停止規則 (2×2)**: structural READY ∧ semantic NO_VALID_SCORER の場合、semantic scorer superseding ADR を
  通すまで「divergence に近づいた」と主張禁止 (structural 積み上げによる永久 defer を block)。memory
  recomposition は 3D substrate の component/fallback seam に、closed-loop (RQ-SWM-1) は 3 条件付き re-entry
  door に保全。核心診断「計測壁は semantic 固有」は **作業仮説** (richer structural の測定可能性は D0 で実証)。
- **M13-SUB1 D0 pack apparatus 事前登録 (ADR FROZEN 2026-07-01、doc-only)**: 上記 scoping の apparatus
  具体化。第一成果物 = **二層 D0 pack + 最小 deterministic 3D-state 生成 stub** を G-GEAR 完結で pre-register
  (数値 floor + verdict schema を run 前凍結、実装・GPU run は更に次工程)。(a) structural conformance =
  ES-1 retrieval-landscape estimand を **complexity ladder R0(=ES-1)→R1(連続位置)→R2(kinematics)→R3(action⇄obs
  closure)** に一般化し、readout 固定・state richness 可変で「どの複雑度まで richer structural を非循環に
  測れるか」を rung ごとに実証 (**anti-collapse gate** で R1 が ES-1 を黙って再測定する偽 GO を封鎖)。live 層は
  authoritative physics が Python 側 (`step_kinematics`+`ManualClock`) ゆえ **D0b-runtime を必須**とし、真の
  Godot render-loop coupling は cross-machine milestone に defer。(b) semantic reference-free-originality
  prevalidation = **独立 provenance corpus + leave-anchor-out hard gate + surviving-fraction floor +
  entropy-residual 固定 baseline 直交 gate** で ES-4 の自己 anchor 認識循環を構造的に不能化。process =
  /reimagine (v1 破棄→独立 v2→hybrid) + Codex ADOPT-WITH-CHANGES 7 件全反映。**claim 境界 = substrate 配線 +
  計測能力の実証であって divergence 検定でない** (2×2 停止規則配線)。
- **M13-SUB1 D0 pack structural track 実装 + verdict run (PR #44 MERGED)**: apparatus 事前登録の忠実
  実装。verdict = **`structural_status=NO_STRUCTURAL_FLOOR`、`R*=R0`**。R0 (ES-1 anchor) は非循環に
  測れたが、R1 の anti-ES-1-collapse gate は floor 未達 (`median(Δ_1)=0.0`、64 seed 中 63 が exact
  ゼロ)。機序解析 = retrieval top-k membership が zone-level 情報のみで決まる構造的低検出力
  (**この apparatus パラメータ組 [K_RETRIEVE/M_MEMORIES/SPATIAL_GAMMA] 限定の honest negative**、
  metric のバグでも一般的な「richer structural 測定不能」の証明でもない)。TASK-POST `/cross-review`
  の HIGH 3 件反映後も verdict は byte-identical に不変。
- **M13-SUB1 forward disposition (ADR FROZEN 2026-07-02)**: 上記 `NO_STRUCTURAL_FLOOR` は scoping ADR
  §4 の falsifiable 条件 (i) に該当し、fork-2 fallback (memory-recomposition seam) を発動。**採用 =
  situated-3D-richness (R1+) を primary structural target から bounded close するが、M13 substrate
  arc 全体は継続** (棄却スコープ = 現行 apparatus パラメータ下の R1+ 測定ラインのみ、ES-1/ES-3 GO・
  「身体性 substrate を建てる」大方針は不変)。memory-recomposition seam は **自動昇格でなく**、
  ES-2 failure mechanism 対応・検出力方針・cost ceiling・stop rule・success/fail token・
  tune-to-pass 防止の 6 項目を必須とする costed pre-register ADR をゲートとする条件付き re-entry。
  fork C (semantic track) は `NOT_EVALUATED` のまま deprioritize (破棄でない)。process = /reimagine
  (v1=bounded pivot 自動昇格 → 破棄 → v2=arc 全体 close 優先で独立再生成 → hybrid) + Codex
  Adopt-with-changes (MEDIUM 2 + LOW 2 全反映)。
- **memory-recomposition seam costed pre-register ADR (ADR FROZEN 2026-07-02)**: disposition ADR
  §4 の 6 項目ゲートを満たす形で re-entry を具体化。**estimand を ES-2 の output-diversity 型
  (生成物集合の多様性を外側から要約) から ES-1/ES-3 が非循環に GO した channel-conformance 型
  (入力チャネルが下流の離散決定を因果的に偏らせるか) へ転換**: 入力チャネル `C` = idle
  recomposition batch の pooled content-bigram 遷移分布の argmax セル、下流決定 `D` = 独立 RNG
  stream で再インスタンス化した post-idle walk (`C` の formation zone 一致項のみ既存 `POLYA_ALPHA`
  を再利用)。stop rule は D0 pack §8 型の 2×2 (apparatus 有効性 × conformance CI 符号)、verdict
  token は ES-1/ES-2/ES-3 と同型の `GO`/`NO_GO`/`INCONCLUSIVE`。process = /reimagine (v1 破棄→
  独立 v2 [v1 と独立に同一 estimand class 転換へ収束]→hybrid) + Codex (Verdict=Revise→HIGH3
  [`C` の型誤り/cost ceiling と tune-to-pass 凍結の矛盾/gate 数値閾値未定義]・MEDIUM2・LOW1 全反映)。
  **claim 境界 = necessary-substrate 型の下流因果偏り測定であって H4 (身体性が発散を生む) の証明
  ではない**、live agent/Godot への接続なし。次工程 = apparatus 実装 + verdict run (別 fresh
  session)。
- **現状の到達点 (2026-07-02)**: ES-1 GO / ES-2 bounded INCONCLUSIVE / ES-3 GO / **ES-4 計測ライン
  bounded close (H4 効果未判定)** / **M13-SUB1 D0 pack structural = `NO_STRUCTURAL_FLOOR`
  (apparatus パラメータ限定の honest negative) → situated-3D-richness bounded close + arc 継続**
  / **memory-recomposition seam costed pre-register ADR = FROZEN (estimand class 転換の設計完了、
  実装・verdict run は未実施)**。「身体なしの記憶再編ルートで発散の十分機構が存在するか」という
  核心の問いには **まだ答えを出していない** (計測器が zone-level を超える richness を今の
  apparatus では測れていない、memory-recomposition seam の verdict run もこれから)。

## 9. スコープ / 非スコープ

- **やる**:
  - 身体を外した in-silico での「記憶再編チャネル単独」の発散種生成の測定 (ES 系列)。
  - **situated 3D embodiment substrate の建設と、その出力を structural/behavioral outcome で非循環に測る
    計測基盤 (二層 D0 pack) の先行 valid 化** (substrate scoping FROZEN 2026-07-01)。
  - 事前登録された falsifiable な GO/NO_GO verdict と two-sided guard の徹底。
  - 凍結された認知契約・apparatus 上での非循環・matched-null 設計。
- **やらない**:
  - 身体性そのものの claim / 人間機構の再現主張 (warrant 止まり)。
  - クラウド LLM API への必須依存 (予算ゼロ制約)。
  - 一度 close した中核命題の同一空間での薄い再走 (継続バイアス)。
  - GPL 依存の `src/erre_sandbox/` への混入。
  - 効率/タスク達成を暗黙の目的関数に戻すこと。

## References

本文中の `[n]` は `docs/references.md` (中央書誌) を参照。採番は append-only。
