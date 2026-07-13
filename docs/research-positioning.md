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
- **認知アーキテクチャの基盤**: CoALA (Sumers et al. 2023) [3] が memory × action × decision の公理系を与える。本研究の認知サイクルはこれを基盤に置くが、**ERRE モード (歩行/茶室/座禅/
  守破離) による状態依存サンプリング変調**を追加する点が独自。
- **経験的アンカー (身体↔創造性)**: Oppezzo & Schwartz (2014) [1] — 歩行が拡散的思考を伸ばす。
  決定的なのは **屋内トレッドミルで壁を向いて歩いても効果が出た**こと → 主因は「新しい風景=
  環境新奇性」ではなく、より内的・身体的なもの (覚醒/固有感覚/DMN 脱抑制) に寄る。
  Thabane et al. (2026) の系統的レビュー・メタ分析 [6] はこの効果を **発散側に限って強く支持**する:
  divergent thinking で d=0.93 [0.44, 1.42] (moderate certainty)、対して convergent thinking は
  d=0.16 [−0.31, 0.63] の **null (very low certainty)**。ただし divergent の positive 研究の多くが
  Oppezzo 単独に由来する点が inconsistency として GRADE で減点されており、**warrant としては強いが
  「効果は身体側に寄る」という機構主張の direct evidence ではない** (§4 の非対称・§7 の過大主張ガード)。
- **理論アンカー (空間探索↔記憶検索の同型性)**: ES-1 (空間移動 → 経路依存な記憶検索) が暗黙に
  前提する「移動と記憶検索は構造的に同型」に対し、Hills, Jones & Todd (2012) [9] が独立の実証的
  裏付けを与える。空間採餌の数理 (optimal foraging / patch-leaving を Marginal Value Theorem で
  定式化) を意味流暢性課題にそのまま適用し、人間の記憶検索が **「局所探索 → パッチ離脱 → 別領域へ
  移動」という空間採餌と同型の動的方策**に従うことを示した (BEAGLE 意味空間上のシミュレーションが
  実際の想起パターン = パッチ内高頻度・低距離 → パッチ間で急な意味距離ジャンプ を再現)。記憶検索と
  空間探索がドメイン汎用の探索制御プロセスを共有するという主張は、ERRE の spatial→memory channel
  (ES-1) の設計前提への外部的な理論支持。**ただし注意**: この同型性は人間の意味空間で強く支持される
  が、**LLM の埋め込み空間や ERRE の記憶再編 seam で同型が成り立つかは別途検証を要する** (ES 系列が
  暗黙に前提する部分であり、direct evidence ではない — §7 の過大主張ガード)。この foraging 枠組みは
  「argmax セルでなくパッチ切替イベントを channel にする」という代替 channel 設計 (arc forward
  disposition §7 の re-entry door ③) の理論的出自でもある。
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
  ではない**、live agent/Godot への接続なし。
- **memory-recomposition seam apparatus 実装 + verdict run = `INCONCLUSIVE` (2026-07-03)**: 上記
  ADR を忠実実装 (`src/erre_sandbox/evidence/memory_recomp_conformance/`、独立性 pin 含む 36 test、
  byte-identical 再現確認)。**verdict = `INCONCLUSIVE` (channel ill-posed)**: 入力チャネル C =
  idle recomposition 遷移分布の argmax セルだが、この分布が near-uniform (実効台 ~1627/2256 —
  ES-2 が観測した near-uniformity の同一 kernel 経由の持ち越し) ゆえ argmax が bootstrap で 18.7%
  しか再現せず (median argmax stability 0.187 < gate 0.5)、well-posed な channel を定義できない。
  独立に synthetic power@1.0 = 0.0 も underpowered を示す。**これは NO_GO と峻別される**
  (H4/substrate の否定でなく、argmax channel が near-uniform 台で不安定という計測器レベルの帰結)。
  文献 [8][9][10] の「argmax 離散要約は不安定」警告を argmax-stability 診断が empirical に実証。
  forward = ADR §6 4点セット付き別 channel 定義 (patch-switch [9] / 連続距離 [8][10]) の
  superseding ADR (本 run では不実施)。
- **M13 arc forward disposition (ADR FROZEN 2026-07-03)**: memseam `INCONCLUSIVE` は scoping §8
  2×2 の右下セル処方 (fork-2 fallback 実行済 → 中核診断再検討) を発動。**採用 = (B)+(C) hybrid**:
  (1) **frozen-synthetic recomposition 計測ラインを bounded close** (arc 全体は継続 —
  INCONCLUSIVE ≠ NO_GO ≠ fallback ルート破綻ゆえ disposition §5 の arc-close 条件は厳密には未成立、
  反証されたのは frozen-substrate instantiation の well-posedness のみ)。(2) **scoping §0 作業仮説を
  reframe** — 「計測壁は semantic 固有」から「frozen fixtures ⇔ running dynamic substrate の区別
  導入。running 上は未検証」へ (D0 structural `NO_STRUCTURAL_FLOOR` も memseam `INCONCLUSIVE` も
  ともに **frozen synthetic fixtures 上**の計測で、running dynamic substrate 上では未検証)。
  (3) 次 primary = **最小 running dynamic 3D-state substrate 建設** (scoping §1/§4 ratified 大方針
  への復帰) + 5 条件 pre-register 付き D0a running 再走。**over-read guard**: 4 壁の機序は少なくとも
  3 系統に分かれ (壁1 ES-2 & 壁4 memseam = 同一 es2_replay kernel の near-uniform 遷移分布 / 壁3 D0 =
  top-k membership 飽和 / 壁2 ES-4 = semantic 自己 anchor 循環)、「4壁→単一原因」の単純合算は行わない
  (主張は壁1&4 の near-uniform replay 限定)。**案 A (別 channel 計測ライン継続) は却下** (survey 候補
  ①外部参照系 [7]/②連続距離 [8][10]/③patch-switch [9] は frozen 上で near-uniformity を回避できる
  pre-registered/desk-audit 根拠を現状欠く = B/C より VoI 低。不能証明でなく未実証、running 後の
  re-entry door 保全)。**forking-paths 封鎖 5 条件** (ratified 復帰 / falsifiable kill / apparatus
  不変 / input trace generator 以外も sealed run 前 freeze / one-shot D0a running run fail は
  arc-close 再検討トリガー)。scoping §8 の 2×2 停止規則 (semantic-track 反永久延期ガード) を次 ADR に
  継承 (D0a running pass は structural floor であって divergence 前進でない)。process = /reimagine
  (v1 機序起点 / v2 framework 義務論起点が独立に (B)+(C) へ収束) + Codex Adopt-with-changes
  (HIGH 3 [案A過剰却下軟化 / semantic-track ガード継承 / forking-paths を input 側にも] 全反映)。
- **最小 running dynamic 3D-state substrate + D0a running 再走 (ADR FROZEN 2026-07-03、doc-only)**: arc
  forward disposition §8 が framework-mandated した次 primary の pre-register。**採用 = 最小 closed-loop
  agent-policy running loop** (G-GEAR 完結・pure Python・deterministic no-LLM policy が既存 physics/tick/
  memory を回し state が agent 自身の history の帰結として進化 = frozen replay でない) + **凍結 D0a
  apparatus を tune せず target を blind uniform walk fixture から running trace に差替**て再走 (ladder/
  floor/verdict/quantize は byte 継承、変更は input trace generator のみ)。**中核的緊張を honest に据える**:
  D0a の failure は **壁3 = within-zone の top-k 飽和** (K_RETRIEVE=8 vs memory 密度 ~4/zone) であり、
  running の主機序約束 (壁1&4 の zone-level 非一様性回避) は R0 (zone-level、既 pass) を動かすだけで R\* を
  前進させない — running substrate が R\* を R1 に進めるには **within-zone 構造**を生み、かつ凍結 retrieval
  apparatus の top-k を生き延びる必要がある。**tune-to-narrative 禁止**: 「running なら within-zone 構造が
  measurable」を保証と書かず、4 つの明示 failure 条件 (within-zone 構造なし / 壁3 が構造を破棄 / policy
  過収束 / policy near-memoryless) + **one-shot kill** (one sealed run fail → arc-close 再検討 ADR 必須
  起票、無限延期しない) で falsifiable 化。**running-ness gate** (history-ablation probe で「frozen replay
  同型でない」を `CI_lower(TV) > practical floor` で run-time 検定) + **paired frozen/running contrast**
  (byte-identical apparatus で blind[既知 R0]/running を並走し R1-pass 差分を running-ness に非循環帰属、
  ただし §5 policy grammar freeze + gate 併存下で成立) + **saturation forensic probe** で壁3 帰属。verdict =
  `STRUCTURAL_READY_RUNNING`/`NO_STRUCTURAL_FLOOR_RUNNING`/`INCONCLUSIVE_RUNNING` (INCONCLUSIVE-first)、
  scoping §8 2×2 継承 (**D0a running pass は structural floor であって divergence 前進でない**、semantic
  track は `NOT_EVALUATED` asset 保全)。**claim 境界 = substrate 配線 + within-zone 計測能力の実証であって
  divergence 検定でない**。ZONE_PROPS sparse (CHASHITSU のみ) ゆえ主機序は prop 非依存の memory/
  preferential-return、R2/R3 は INCONCLUSIVE 既定、CHASHITSU-only pass 時は claim_scope 狭窄。Hills 2012
  [9] は patch/preferential dynamics を **機序原理としてのみ**参照 (channel 採用でない、survey 候補③は
  running 実証後の re-entry door)。process = /reimagine (v1 機序起点 破棄 → 独立 v2 [v1 非開示] が核心収束 →
  v2 spine + hybrid hardening) + Codex Adopt-with-changes (HIGH 2 [policy grammar freeze / ZONE_PROPS
  sparsity 対応] + MEDIUM 3 全反映)。survey channel ①②③ / RQ-SWM-1 / D re-entry は door 保全のまま。
  次工程 (別タスク) = 実 running-loop apparatus + running-trace generator の実装 ADR。
- **実装 ADR + one sealed D0a running run (2026-07-04)**: 実 running-loop apparatus (P-A terminal-anchored
  memory-preferential-return policy + running-trace generator + running-ness gate + forensic 対照) を
  実装・凍結 (commit `104686a`、GPU=0)、one-shot sealed run を tune ゼロで 1 回実行 = verdict
  **`NO_STRUCTURAL_FLOOR_RUNNING`**。R0 (ES-1 anchor) が running trace 上で floor 未達 (median 0.0)、
  contiguity 規則で R\*=None。**ただし R1 (within-zone Δ_1) 自体は強く PASS (median 0.769)、running-ness
  gate も robust に PASS (CI_lower TV 0.317 > floor 0.10)、壁3 (top-k 飽和) は非発火 (`topk_zone_saturated=0`)**
  = 失敗は blind D0 pack が R1 で fail したのとは**別機序** (R0 anchor 信号の running trace 上での不在に局在)。
  **claim 境界 = これは §5-5 one-shot kill 発火 → arc-close 再検討 ADR 必須起票のトリガーであって、
  H4/substrate/divergence の否定でも INCONCLUSIVE (計測器 invalid) でもない** (validity gate 全 pass、R0 は
  valid に測れた FAIL)。over-read 禁止 = STRUCTURAL_READY 未到達ゆえ structural floor は running trace 上で
  未確立、tune 再走は seal 違反。詳細 = `.steering/20260703-m13-running-apparatus-impl/verdict-record.md`。
- **arc-close 再検討 ADR (FROZEN 2026-07-04、doc-only)**: §5-5 one-shot kill 発火を受けた高難度方向決定。
  **決定的新事実の機序診断** (tune せず as-is) = 失敗は想定機序 (壁3 top-k 飽和) でなく **R0 anchor collapse**
  (別機序 = 壁5)。R0 (position-quantized cross-arm landscape divergence) = 0.0 に潰れたのは、P-A policy が
  **terminal-anchored** (両 arm が同一 terminal への return-to-home errand) ゆえ zone-level 占有分布が収束し、
  blind uniform-walk が生んでいた cross-arm zone-level 乖離を running policy が除去したため。**contiguity の
  R0→R1 順序仮定こそが、この scenario 下の artifact** (within-zone 乖離 0.769 ≫ zone-level 乖離 0.0 の逆転)。
  = **(i)-dominant** (R0 readout × terminal-anchored policy の estimand mismatch) であって **(ii) substrate
  欠損でない** (within-zone は running trace 上で measurable、ただし R1 advance 自体は running-specific でなく
  running-ness は別 gate が certify)。**裁定 = arc-close 却下 + frozen⇔running structural-floor measurement
  line (SPDM-landscape R0/R1 contiguity ladder instrument) を bounded-close**。arc-close 却下は **over-read
  guard の演繹** (distinct 5th 機序 + (ii) corroborated ゆえ arc 全体 refutation は禁じられた読み替え、
  INCONCLUSIVE 規律論でなく valid FAIL 下の演繹)。process/cost VoI 枯渇 steelman も却下 (instrument-VoI ≠
  arc-VoI、cost 懸念は ratchet が address)。**forward = anti-deferral teeth** = automatic 再走ゼロ + costed
  superseding re-entry gate (6 項目 + futility) + **escalation ratchet + R-budget = arc-wide 最大 1 回**
  (次の同型 valid FAIL は estimand class 異同を問わず再検討なしで arc-close 自動執行、serial-relabeling 封鎖) +
  **holding disposition** (substrate 構築大方針は保全・arc 継続、次 primary の construction scoping は別タスク、
  ただし measurement-line 再入を隠す経路なし)。within-zone measurability finding (R1 強 PASS) は verdict を
  昇格させない preserved asset。5 機序分離 (壁1&4 near-uniformity / 壁2 semantic 循環 / 壁3 top-k 飽和 /
  壁5 policy-induced zone 収束) は単純合算しない。process = /reimagine (v1 機序起点 破棄 → 独立 v2 [framework
  義務論起点] が arc-close 却下 + bounded-close へ独立収束 → v2 spine + v1 機序 graft hybrid) + Codex
  Adopt-with-changes (事実誤認 HIGH なし、HIGH 2 [estimand-class 抜け穴 → R-budget=1 / substrate corroborated
  の over-claim 軟化] + MEDIUM 3 + LOW 1 全反映)。詳細 =
  `.steering/20260704-m13-arc-close-reconsideration/design-final.md`。
- **construction milestone 第一 deliverable scoping ADR (FROZEN 2026-07-05、doc-only)**: arc-close ADR §3.4 が
  別タスクに委ねた「next primary = construction milestone 具体 scoping」の履行。**計測でなく建設側へ舵を切る初
  primary の第一 deliverable を切る**。決定的な現状事実 = **substrate は既に大部分存在するが「二重トラックに
  分断」** — (A) ライブ LLM 認知ループ (`world/tick`→`cognition/cycle`、複数ペルソナ・Godot LIVE seam 稼働だが
  移動は抽象 zone-centroid で seed 決定論を欠く) と (B) frozen running-substrate P-A ループ (連続
  `step_kinematics`+履歴依存 memory geometry+replay checksum だが no-LLM/headless)。**核心的欠落 = A と B が別
  トラック**。**採用 = 「Embodied Cognition Loop v0 (単一 live agent)」** = (A) の LLM 移動決定を (B) の連続物理+
  履歴依存 retrieval-centroid 幾何の上で実行する統合器官を新規 non-evidence モジュールで建てる (`evidence/**` は
  read-only 参照ミラーのみ)。載せる = 連続物理化 + 履歴依存目的地幾何 + ES-3 locomotion 活性化 + record/replay
  spine + cross-machine handoff contract。区切り = 単一 agent (N 体化/長 horizon/Godot art/measurement は後続・
  holding)。**construction ≠ measurement**: 成果物 = 動く器官 + replay checksum (再現性という construction 品質)
  であって structural floor verdict でない。**LLM 非決定 = two-plane determinism** (Plane 1 幾何/物理/memory/
  RNG/clock/ids = byte 決定的 / Plane 2 LLM = full `LLMPlan`+provenance を記録し replay 決定的、recorded-decision
  boundary に隔離) で「LLM を loop に入れる」と「replay 決定性」「将来の測定可能性 (holding 解除)」を両立。
  **anti-thin-proxy**: 実 physics/memory/render を同一ループに載せる (カテゴリ差 = thin proxy からの necessary な
  離脱条件、sufficient でない) + `test_history_channel_continuity` を **deterministic causal wiring test** 化
  (positive/negative control で memory→geometry→movement 導通を検査、統計/floor/landscape 一切なし = measurement
  再入回避)。**binding 継承** = construction/non-measurement 限定・measurement-line (SPDM-landscape R0/R1) 再入は
  holding (costed ADR + escalation ratchet 経由のみ)・over-read 禁止・5 機序分離・大方針保全・scoping §8 2×2
  (semantic `NOT_EVALUATED`、LLM utterance 生成は construction であって semantic divergence measurement でない)。
  cross-machine = G-GEAR が trace/decisions/manifest 出力 + converter が wire-schema conform (Godot 側検証は
  bounded scope、**「Godot 無改変」claim は Codex H1 で撤回** — `FixturePlayer` は固定 playlist のみ)、handoff
  spec doc を SSOT 化。process = /reimagine (v1 convergence-first 破棄 → 独立 v2 が **A×B 統合器官へ独立収束** →
  v2 spine [two-plane determinism / continuity gate / FixturePlayer 再利用] + v1 framing graft + continuity-gate
  ガードレール hybrid) + Codex **Verdict=Revise → HIGH 4** [FixturePlayer 事実誤認裏取り済 / LLM 決定ログ閉集合 =
  full LLMPlan / Plane 1 非決定源拡充 / continuity gate causal 化] **+ MEDIUM 3 + LOW 1 全反映後
  Adopt-with-changes**。**claim 境界 = substrate 建設であって floor を建てた/測ったでない** (floor 確立は holding)。
  次工程 (別タスク) = Embodied Cognition Loop v0 の実 apparatus 実装 ADR。詳細 =
  `.steering/20260704-m13-construction-milestone-scoping/design-final.md`。
- **Embodied Cognition Loop v0 実装-design ADR (FROZEN 2026-07-05、doc-only)**: construction scoping ADR §7 が
  別タスクに委ねた「実 apparatus 実装 ADR」の履行 = **建設側の初 primary の技術契約 (HOW) を sealed 実装前に
  pre-register**。scoping が WHAT/WHY (A×B 分断を閉じる) を確定済ゆえ本 ADR は 6 中核論点 (モジュール配置 /
  policy grammar freeze / two-plane determinism 閉集合 / continuity gate causal 定義 / handoff schema /
  acceptance test 凍結) を裁定する。**決定的な設計判断 = モジュール配置で「履歴依存 resolution を world→cognition
  へ引き上げる」ことで import 方向緊張を解消** (cognition は memory を合法 import、world には具体座標 MoveMsg を
  渡すので既存 default_spawn 分岐が発火せず world ほぼ無改変 = 既存 live loop を単一ループのまま器官化)。幾何定数を
  `contracts/geometry.py` に限定 SSOT 昇格、履歴幾何を `cognition/embodiment.py`、record/replay+converter を
  `integration/embodied/`、world は injected-sink 1 本 (live no-op) に配置。**policy grammar = LLM は
  destination_zone 選択のみ・座標生成禁止** (tune-to-pass 防止)、`retrieve(k_agent, k_world=0)` で self memory に
  限定。**two-plane determinism = 器官内で発火した全 LLM call を記録** (v0 は reflection を record mode で disable)
  + Plane 1 完全 pin (named substream / fixed clock / deterministic id / 全順序 tie-break / physics-tick と
  agent-tick 分離)。**continuity gate = exact-oracle の deterministic causal wiring test** (`target ==
  reflect_clamp(centroid + fixed_jitter, Z)`、統計/floor/landscape 不使用、verdict token を出さない =
  measurement-line 再入でない、"NOT a structural-floor verdict; verdict は holding")。handoff = manifest
  (SCHEMA_VERSION + env pins + coord + tick mapping + canonical JSON + artifact hashes + golden) + Godot は
  dev-only bounded replay player (「Godot 無改変」claim は撤回済)。process = /reimagine (v1 並列 offline 器官 破棄
  → 独立 v2 が **live seam 器官化へ独立収束** → v2 spine + v1 決定性 harness 規律 graft hybrid) + Codex
  **Verdict=Revise → HIGH 3** [reflection LLM の Plane 2 欠落 / k_world=0 欠落 / continuity ε tune-to-pass 穴]
  **+ MEDIUM 3 + LOW 1 全反映後 freeze** (189K token・実ファイル検証)。**claim 境界 = 動く器官の技術契約であって
  floor verdict でない** (measurement-line 再入は holding、continuity gate は construction wiring 検査)。次工程
  (別タスク) = 本 ADR を binding 前提に ECL v0 実コード実装 (Loop Engineering 適用判断)。詳細 =
  `.steering/20260705-ecl-v0-impl-design/design-final.md`。
- **現状の到達点 (2026-07-04)**: ES-1 GO / ES-2 bounded INCONCLUSIVE / ES-3 GO / **ES-4 計測ライン
  bounded close (H4 効果未判定)** / **M13-SUB1 D0 pack structural = `NO_STRUCTURAL_FLOOR`
  (apparatus パラメータ限定の honest negative) → situated-3D-richness bounded close + arc 継続**
  / **memory-recomposition seam = `INCONCLUSIVE` (channel ill-posed: near-uniform 遷移分布の argmax
  が不安定、median stability 0.187 < 0.5)** / **arc forward disposition = (B)+(C) hybrid**
  (frozen 計測ライン bounded close + 診断を frozen⇔running 区別で reframe + 次 primary = 最小
  running dynamic 3D substrate 建設) / **最小 running dynamic 3D-state substrate + D0a running 再走
  ADR pre-register (FROZEN、doc-only) → 実装 + one sealed run 完了 (2026-07-04) = `NO_STRUCTURAL_FLOOR_RUNNING`
  (R0 anchor が running trace 上で未達、R1 自体は PASS・running-ness gate PASS・壁3 非発火、§5-5 one-shot
  kill 発火 → arc-close 再検討 ADR 起票へ)**。「身体なしの記憶再編ルートで発散の十分機構が
  存在するか」という核心の問いには **まだ答えを出していない** — arc の 2 つの structural 計測失敗
  (D0/memseam) がともに **frozen synthetic fixtures 上**であり、running dynamic substrate 上でも
  **structural floor は R0 anchor で未確立** (計測は valid、H4/divergence 否定でない) という
  一回限りの disciplined return の結果を得た。この sealed 結果が **frozen⇔running 区別の下での 1 データ点**
  であり、それを受けた **arc-close 再検討 ADR (FROZEN 2026-07-04) = arc-close 却下 + structural-floor
  measurement line (instrument) bounded-close + escalation ratchet (R-budget=arc-wide 最大 1 回) 付き holding
  disposition** に至った。すなわち計測器 (SPDM-landscape contiguity ladder) は複数 distinct 機序で structural
  floor を gating できなかったが、それは substrate/H4/divergence の否定でなく、substrate 構築大方針は保全され
  arc は継続する。**この holding を消費して construction milestone 第一 deliverable scoping ADR (FROZEN
  2026-07-05) = 「Embodied Cognition Loop v0 (単一 live agent)」= 二重トラック (ライブ LLM 認知 A × frozen
  running-substrate B) の核心的欠落 = A×B 分断を、LLM 移動決定を連続物理+履歴依存 memory 幾何の上で実行する
  統合器官として最初に閉じる方向を確定した** (計測でなく建設側へ舵を切る初 primary、two-plane determinism +
  causal continuity gate で construction≠measurement を担保、measurement-line 再入は依然 holding)。**この方向を
  受けた Embodied Cognition Loop v0 実装-design ADR (FROZEN 2026-07-05) が技術契約 (HOW) を sealed 実装前に
  pre-register** = モジュール配置で resolution を cognition へ引き上げ import 緊張を解消 (既存 live loop を単一
  ループのまま器官化)、policy grammar freeze (LLM 選択のみ)、two-plane determinism (全 LLM call 記録 + Plane 1
  完全 pin)、continuity gate を exact-oracle causal wiring test 化 (measurement 非再入)、handoff schema + Godot
  bounded scope。Codex Verdict=Revise → HIGH3/MEDIUM3/LOW1 全反映後 freeze。次工程 = 本 ADR を binding 前提に
  ECL v0 実コード実装 (別タスク、Loop Engineering 適用判断、measurement-line 再入は costed superseding ADR +
  R-budget 経由のみ)。**この実装-design ADR を binding 前提に ECL v0 実コード実装 (I1-I5) が完了した
(2026-07-05、feat/ecl-v0)** = contracts/geometry SSOT 昇格 (I1) / cognition/embodiment 履歴依存目的地幾何 +
continuity gate exact-oracle (I2) / live seam foundation (cycle+world seam、flag-off byte-invariant、
reflection record-mode disable、I3) / integration determinism harness + replay checksum (record/replay LLM
adapter、two-plane determinism、I4) / cross-machine handoff converter+manifest+committed golden + Godot
dev-only replay player (I5)。**得られたもの = 単一 live LLM 認知ループが連続 physics + 履歴依存 memory 幾何の
上を走り、決定的に record/replay され、G-GEAR→MacBook を跨ぐ handoff golden (1 agent × 8 tick、replay checksum
安定、history 依存は centroid が担保 = 8 distinct move target) として焼かれた construction apparatus** (統計/
floor/landscape/verdict を出さない measurement 非再入を ast guard で機械的に保証、flag-off byte-invariant で
既存 live 経路無影響)。**measurement は依然 holding**。TASK-POST 二者レビュー (code-reviewer(Opus) + Codex
(gpt-5.5)) が v0 apparatus では非発火の determinism-hardening 候補 (RNG substream の tick-across 消費 idiom /
LLM fallback replay-safety / retrieval tie-break の truncation 前適用 / checksum canonicalization 統一) を検出、
これらは frozen I2/I3/I4 改変を要するため **単一 superseding ADR (「ECL v0 determinism hardening」) 候補として
pre-register** (v0 の construction claim・determinism・再現性は不変)。**この hardening ADR は実装完了
(2026-07-06、PR #55 MERGED、main=a758c47)** = 5 漏れ→3 slice (α/β/γ) を Loop Engineering で実装、golden re-bake
v2 (2x-bake 決定的)、substrate は live/長尺/多体に耐える determinism を獲得。
- **hardening 後の forward primary 決定 ADR = sealed live run (単一 live agent、候補 A) を FROZEN (2026-07-06、
  doc-only)**。決定的観察 = **ECL v0 organ は実装・hardening 済だが一度も real LLM と接触していない** (golden は
  架空 LLMPlan の replay、evidence/running は no-LLM)。ゆえ次の最小・最大 VoI・holding 保全の一歩 = organ を
  real qwen3:8b で一度封印実走する **first-contact** (B=N体化 と C=measurement 再入 はこれを前提とする論理的
  前件)。**B は A の GO 後に後置、C は holding 保全で却下** (live-validation 前に希少 R-budget=arc-wide 1 を焼く
  のは VoI 最劣)。HOW = `RecordReplayChatClient(inner=ThinkOffChatClient(OllamaChatClient(qwen3:8b)))` を record
  mode で駆動 → captured real Plane2 → **Ollama-free deterministic replay-verify** (embedding は mock 維持 =
  minimal reality surface、real は action LLM の決定のみ)。sealed run は `experiments/<date>/` 実験配置。事前登録
  観測量 = O1 完走 / O2 replay 再現 / O3a-b cross-platform / O4 非縮退 (annotation) / O5 parsed-action path
  (annotation)、**Done = O1∧O2∧O3a∧O3b、verdict なし** (construction validation であって measurement verdict で
  ない、floor/landscape/verdict 非出力、holding 不可侵)。reimagine v1/v2 独立収束 (A/mock/verdict なし) + hybrid
  + Codex Verdict=Adopt-with-changes (事実誤認 HIGH なし、HIGH2/MEDIUM2/LOW1 全反映)。次工程 (別タスク、Phase 1)
  = Loop Engineering で sealed live run 実装 (I1 harness+ThinkOffChatClient / I2 protocol+env pin / I3 sealed run+
  committed artifact / I4 Ollama-free replay-verify)。sealed run の結果 (GO / Stop→superseding / construction
  妥当性 branch) が次 primary を条件付き駆動。
- **sealed live run = first-contact GO (PR #57、2026-07-06)**。organ を real qwen3:8b で N=32 封印実走 →
  **Done=O1∧O2∧O3a∧O3b HOLDS** (cross-platform WSL byte 一致) + O5=32/32 + O4 非縮退。決定的発見 = `think=False`
  (`ThinkOffChatClient`) が load-bearing (全 tick parseable)。construction validation であって measurement
  verdict でない (holding 保全、R-budget 未消費)。
- **次 primary = ECL v1 ADR (移動経路→sampling チャネルのライブ活性化) を FROZEN (2026-07-07、doc-only)**。決定的
  観察 = **first-contact GO 済 organ は ES-3 locomotion→sampling チャネルを配線済だが未活性** (`AgentState.
  locomotion=None`)。ゆえ物語 (§1/§7、Oppezzo [1]/DMN [11]) の中心「移動経路による発散」を、器官が自らの zone
  移動決定 (EMA λ) で sampling を変調する閉ループとして **機構的に instantiate** する construction 拡張 (単一
  agent)。**scope = ES-3 活性化 first** (C=measurement 直行は holding 保全で却下 — 過去の記憶チャネル near-uniform
  低検出力を器官で実信号確認する前に希少 R-budget を焼くのは VoI 最劣、B=N体化は後置)。HOW = 既存 `agent_state`
  引数経由で seeded `LocomotionState(lam=0.0)` を渡すだけ (**organ src 改変ゼロ**、decision-level move_t = frozen
  ES-3 意味論)。determinism は replay が sampling 無視・checksum が幾何のみゆえ **新非決定源ゼロ** (λ/sampling は
  実 loop の Ollama-free replay を sampling-spy で観測、offline 再構成でなく)。事前登録 = **Done=V1∧V2∧V3a∧V3b**
  (reproducibility) + V4a (λ distinct>1) / V4b (seeded/None spied replay の sampling 相異) / V5 (parsed-action) =
  channel-active annotation (boolean/counting・統計禁止・side file)、**verdict なし** (construction validation、
  floor/landscape/verdict/conformance/D_loco 非出力、evidence 非 import、holding 不可侵)。reimagine α/β 8 軸独立
  収束 + hybrid + Codex Verdict=Adopt-with-changes (事実誤認 HIGH なし、HIGH2/MEDIUM3/LOW2 全反映、うち HIGH-1 =
  V4b は sampling-spy 必須 [replay は recorded call を記録し recomposed sampling を捨てる])。次工程 (別タスク、
  Phase 1) = Loop Engineering で実装 (I1 live_v1 harness+λ0 pin+spy / I2 protocol+V1-V5+強化 guard / I3 sealed run
  人手 gate+WSL byte 一致 / I4 replay-verify+V4 on/off annotation)。
- **ECL v1 Phase 1 実装 + sealed run = GO (PR #59 MERGED、2026-07-07、main=b3ab1c7)**。ADR (PR #58) を binding 前提に
  Loop Engineering で I1..I3 を実装。**I3 sealed live run = GO (construction validated、閉ループ発火)**: organ を
  real qwen3:8b で N=32 封印実走 → **Done=V1∧V2∧V3a∧V3b HOLDS** (cross-platform WSL Linux glibc / Windows UCRT で
  replay_checksum byte 一致 + 全 artifact SHA 一致、6桁量子化が libm drift 吸収) + channel-active annotation
  **V4a distinct=29 / V4b modulated=28 / V5=32/32** (= 移動が実際に sampling を変調する live 器官を建設、歩行→発散の
  計測でない)。organ src 改変ゼロ (seeded `LocomotionState(lam=0.0)` を `agent_state` 経由)。measurement 非再入
  (floor/landscape/verdict/D_loco/divergence 非出力、evidence 非 import、**R-budget 未消費**、holding 不可侵)。
  λ0/persona/N の実走後 tuning ゼロ。**過去 5 度の計測失敗が一度も持たなかった "live で発火する channel 信号" を
  arc が初めて取得**。
- **hardening 後→v1 GO を受けた forward-primary-post-v1 ADR (FROZEN 2026-07-07、doc-only) = R-budget の 2-named-family
  再設計 + 次 primary = C-design**。決めるべきは 2 つの coupled 決定 = **決定 0 (escalation ratchet / R-budget の
  再設計、user 問題提起「1-and-done は厳しすぎる、増やしてよいのでは」)** × **決定 1 (次 primary = C 計測再入 /
  B N体化 / その他)**。**決定 0 = arc-close 再検討 ADR §4.3 (R-budget = arc-wide 最大 1 回、任意 estimand class の
  valid FAIL→arc-close 自動執行) を superseding** — user 懸念を満たしつつ paradox (反射的に増やせるなら実質 ∞ =
  規律ゼロ) を殺さない緩和として、single arc-wide budget を **有限・凍結・列挙された 2 つの named measurement family
  (SPDM-landscape structural-floor family = SPENT / live-channel-conformance family = v1 GO が生んだ第2 family)、
  各独立 1-and-done** へ置換。**valid FAIL はその family の計測ラインを bounded-close (arc 全体でなく)、両 family
  exhaust で arc-close 自動執行**。列挙数 2 は「arc が現在 GO/asset precedent を持つ distinct measurement family の
  数」で原理化 (恣意的 novel-class 許容でなく、general per-class rule 無し、第3 family 化は from-scratch・非反射の
  独立 ADR を要す)。family を **名前でなく structural invariant で定義** (estimand family / data-generating channel /
  回避する 5 壁 / banned same-family variants / tie→same-family) し serial-relabeling を封鎖。本 ADR は spend 認可を
  grant せず (C-design が eligibility 審査)、非反射条項で FAIL 後増額を禁止 (arc-close §1.4 D3 整合)、下限
  (無限計測禁止・futility・over-read guard・5 機序分離・未知 failure も valid FAIL 受容) を継承。**決定 1 = C-design**
  (doc-only 計測設計 ADR、C の前段) = arc-close §4.2 が必須化した hard futility 前段を doc-only で撃つ superseding
  ADR の前半。**budget 未消費・floor 非計算・holding 保全・REFUSE 可能**。live-locomotion channel が 5 壁 (特に
  壁1&4 near-uniform 低検出力・壁2 semantic 循環) を構造的に回避しうるかを desk-audit + estimand pre-register し、
  候補ごとに **`AUTHORIZE_C_PROPER` か `REFUSE_MEASUREMENT_LINE` を 1 回だけ出す** (同一 candidate 再起票禁止、
  REFUSE→計測ライン close か B fallback)。C-proper (今 budget を焼く) は futility 前段を飛ばす letter 違反ゆえ却下、
  B (N体化) は measurement 可否確認前の substrate 肥大ゆえ後置 (C-design REFUSE 時の principled fallback として保全)。
  process = /reimagine (α [asset-continuity 起点、per-class budget] 破棄 → 独立 β [deontological 起点、R-budget の
  目的から演繹] が 8 軸で支配収束 → hybrid) + Codex **Verdict=Revise → 事実誤認 HIGH なし、HIGH3 [N_novel 原理化 /
  invariant 定義 / C-design 再起票封鎖] + MEDIUM3 + LOW2 全反映後 freeze** (緩和を open な per-class 許容から
  列挙 named 2-family へ硬化)。**claim 境界 = measurement 規律の再設計 + 計測設計への着手であって floor を測った/
  divergence を示したでない** (V4a/V4b は construction annotation、R-budget は C-design AUTHORIZE まで未消費)。
  詳細 = `.steering/20260707-m13-forward-primary-post-v1/design-final.md`。次工程 = C-design ADR (別セッション、
  Plan+reimagine+Codex、doc-only)。
- **C-design ADR = `REFUSE_MEASUREMENT_LINE` → B principled fallback を FROZEN (2026-07-07、doc-only)**。
  forward-primary-post-v1 決定 1 (C-design) の履行 = arc §4.2 が必須化した **hard futility 前段を doc-only で撃つ**
  superseding ADR の前半。live-locomotion channel (λ が sampling を変調する閉ループ) が下流離散決定 (zone 選択列) を
  非循環に偏らせるかの estimand を desk-audit。**決定的な実コード確証 = λ→zone の因果は 2 リンクに分かれる**:
  第1リンク (λ→sampling 変調、`compose_sampling` 第3項) は ES-3 GO / v1 の V4a distinct=29 / V4b modulated=28 が
  測る **firing 済**信号だが、第2リンク (sampling→zone 選択 bias) は **未測定** — 離散 zone 決定 = LLM の
  `LLMPlan.destination_zone` (memory_centroid は zone 内座標のみ決定、zone は LLM が選ぶ) で、λ→zone は
  「sampling が LLM トークン分布を変える確率的間接経路」のみ (決定論的 λ→zone 項は非在)。**verdict = REFUSE**:
  第2リンクの detectability を **doc-only・no-spend 条件下で立証できない** (唯一の firing 資産 V4a/V4b は第1リンクのみ、
  v1 sealed run は各 context 1 サンプルゆえ P(zone|ctx,T_on/off) 推定不能) + architecture が微小効果を予測
  (think=False 低エントロピー zone naming / memory-anchored 座標 / context 支配 [v1 zone study 6・peripatos 26 は
  温度でなく context 駆動] / Δtemp observed 最大 +0.149 / λ 非依存 persona confound) → **hard futility gate を honest に
  PASS できない** = 「測れるかをまず測る」arc 規律の適用であって effect-absent verdict でも defeatism でもない。
  **disposition = B principled fallback (user ratify)**: REFUSE (doc-only・budget 未消費) は §D0.2(b) の exhaust
  (valid FAIL / bounded-close = budget 消費を伴う) に当たらず **live-channel-conformance family を exhaust しない**
  ゆえ arc-close 非発火・R-budget=1 保全。B (N体化) で substrate を enrich し **具体閾値 (条件付き zone entropy 下限 /
  repeated frozen-context bank / MDE power apparatus) を named で pre-register**、未達なら計測ライン close (無限 B ループ
  禁止 teeth) → 両 family exhaust なら arc-close 自動執行。**claim 境界 = 計測設計の可否判定であって floor を測った/
  zone bias を否定した/H4 を否定したでない** (REFUSE は測っていない、V4a/V4b は construction annotation で第1リンク、
  第1リンク GO は第2リンク detectability を含意しない)。process = /reimagine (α [asset-continuity 起点、AUTHORIZE 傾き]
  破棄 → 独立 β [family invariant + futility 目的から演繹] が支配収束 → hybrid、firing⇔detectability 混同の棄却が核) +
  Codex **Verdict=Adopt-with-changes → 事実誤認 HIGH なし、HIGH1 [§D0.3 futility-gate-fail→close との衝突処理明文化] +
  MEDIUM2 [B teeth 強化 / 「原理的不能」を no-spend 条件下に scope 限定] + LOW1 [Δtemp 数値固定] 全反映**
  (中核 REFUSE + 第1/第2リンク分離 honest を repo 実読で支持、V4a/V4b から AUTHORIZE を導く経路なし)。詳細 =
  `.steering/20260707-m13-c-design/design-final.md`。次工程 = B (N体化) ADR (別セッション、REFUSE→B fallback を消費)。
- **B (substrate-enrichment) scoping ADR = 反復 frozen-context bank 主軸を FROZEN (2026-07-07、doc-only、user 裁定)**。
  C-design の REFUSE→B fallback を消費する construction 方向決定 (WHAT/WHY)。**決定的発見 = reimagine v1 (society 起点)
  と v2 (futility 起点) が逆方向から「N体化は teeth に最適でない」に独立収束**: N体化は (ii) repeated frozen-context
  bank と直交 (live society は各 context を trajectory 依存で unique 化) / (i) 相互観測はむしろ条件付き zone entropy を
  下げ confound を増やす / determinism surface を最大化 (scheduler interleaving・pair separation・dialog RNG・
  async gather の 4 新非決定源、A→B 後置の理由そのもの)。**採用 enrichment 形 = 反復 frozen-context bank を
  futility-critical PRIMARY 骨格** (C-design が名指した唯一の非循環 clean estimand [単一 frozen context × M 回 MC] の
  apparatus、estimability 死点 [C2-a の 1-sample/context] を殺す唯一の候補、determinism surface 拡大は MC-index
  substream 追加のみで最小・単一 agent 埋込を触らず N=1 byte 不変維持) + 有界 entropy lever SECONDARY (memory-geometry
  narrow か凍結社会シーン、実選択 defer)。**N体化 full society は北極星 (Autonomous 3D Society) として保持し Milestone
  2+ に defer** (measurability を単一 agent 上で決着してから scale する A→B 後置規律の継続)。**teeth T1 の honest 判定 =
  skeleton 固定 (具体値 M_min/K/H_min/ρ/δ_min は impl-design まで未確定、「達成済み」でない)**: (ii) 反復 bank・
  (iii) MDE power apparatus は構造として達成可能だが、**(i) 条件付き zone entropy 下限は B 単独では doc-only 保証不能**
  (think=False の empirical collapse risk = コードが保証するのは think=False 強制 + 単一 JSON enum destination_zone +
  parse 後単一 zone まで、条件付き分布 H(zone|ctx) は empirical にしか判明しない) → 反復 bank が生成する construction
  副産物 annotation を次 C-design が読んで empirical に判明、**H_min 未達なら line-close → SPDM-landscape [SPENT] と
  両 family exhaust → arc-close 自動執行** (§C4.3 T4、REFUSE→B は arc-close を遠ざけない)。**T3 same-candidate ban 締結
  (Codex HIGH-4) = 反復 bank それ自体は apparatus/annotation であって再入 candidate でない** (「sampling 密度で
  materially different」を再入資格の根拠にしない)、再 C-design eligibility には (i) を攻める基質改変が必須。**claim 境界 =
  enrichment 形の scoping であって measurement を実行した/floor を測った/(i) を保証した/H4 を肯定否定したでない**
  (construction、budget 未消費、B は divergence 非計算、firing⇔detectability 混同禁止継承)。process = /reimagine
  (v1 society 起点 / v2 futility 起点 盲目並列 → 逆方向から N体化≠teeth 最適に独立収束 → hybrid = v2 spine + v1 graft) +
  Codex **Verdict=Adopt-with-changes → 事実誤認 HIGH なし、HIGH-4 [T3 letter 締結] + MEDIUM2 [(i) 文言弱化 / spend
  境界 binding 禁止] + LOW2 [B4 文言 / relabel guard] + 補足 [T1 skeleton] 全反映**。詳細 =
  `.steering/20260707-m13-b-nbody-scoping/design-final.md`。次工程 = B impl-design ADR (HOW、別タスク) → 実コード実装
  (Loop Engineering 判断)。基質改変を経て (i) named 閾値を annotation 上満たせば materially 異なる live-channel-
  conformance candidate の再 C-design 可 (family budget=1 消費)、未達なら計測ライン close → 両 family exhaust → arc-close。
- **B impl-design ADR = 反復 frozen-context bank 技術契約を FROZEN (2026-07-08、doc-only、user 裁定)**。B scoping
  §B5.4 が送った HOW を実コード前に凍結する impl-design (ECL v0 impl-design と同型 = tune-to-pass 穴・measurement
  誘惑漂流・T3 抵触を実装前に閉塞)。**決定的発見 = reimagine の v1 (memory-geometry narrow enrichment) は
  category error として破棄**: prompting.py 実読で `format_memories` は memory content のみ描画し location/zone を
  LLM 不可視、`resolve_destination`/centroid は zone 内座標のみ決め zone-pick を動かさない → memory 幾何を enrich
  しても H(zone|ctx) は 1 bit も動かない。独立再生成 v2 (prompt-level 競合-destination cue、zone-pick は resolver
  上流の prompt cue で起きると演繹) が correctness/continuity-gate/relabel の 3 軸で支配。**採用 = v2 spine +
  substrate-provenance graft** = lever は器官が LLM に見せる cue (affordance/observation/persona.preferred_zones/
  memory content) を複数 zone が near-equal に licensed になるよう対称構築、凍結 context は enriched substrate から
  live 器官が 1 pass 生成した実 prompt を凍結 (T3 materiality + live-channel-conformance を provenance で担保)、
  M-sampling は凍結 (prompt, T_on/T_off sampling) を chat() へ M 回 bake-out (retrieve-count=0 の最強
  continuity-gate)。**continuity-gate = 4 機械 test** (allowlist import-ban / M-loop retrieve-count=0 / arity=1
  divergence-free readout / frozen-string) で SPDM-landscape channel (arity=2 retrieval-landscape divergence)
  への relabel を型不変量で構造封鎖。**Codex Verdict=Revise → 事実誤認 HIGH 2 + HIGH 2 + MEDIUM 3 + LOW 3 全反映**:
  (1) `_bias_target_zone` (default ERRE_ZONE_BIAS_P=0.2) が post-LLM で zone を persona preferred_zones へ差し替え
  得る交絡 (lever の対称 preferred_zones と交絡) → zone bias off + pre-bias parsed zone readout、(2) bake-out 直
  chat() record は full-cycle EclDecisionRecord と別 schema → bank 専用 BankLlmCallRecord、(3) T3 materiality の
  provenance graft 単独は tie→same-family を超えない → materiality criterion 4 点 (canonical inputs のみ編集 /
  bank-density 非根拠 / source-organic bounded mutation / **stimulus 判定なら T3 fail→line-close の honest teeth**、
  user ratify)、(4) raw-row の暗黙集計穴 → AST guard に Counter/set/groupby/numpy/scipy/statistics 追加 +
  annotation opaque。**claim 境界 = HOW 契約の pre-register であって (i) を保証した/measurement を実行した/floor を
  測ったでない** (construction、budget 未消費、(i) 条件付き zone entropy 下限は B 単独 doc-only 保証不能を維持 =
  think=False collapse risk は empirical property、全 fixture collapse なら honest 報告 → line-close → 両 family
  exhaust → arc-close 自動執行、detectability は本 candidate class 内限定で organic 一般化禁止)。詳細 =
  `.steering/20260707-m13-b-impl-design/design-final.md`。次工程 = 反復 bank 実コード実装 (別タスク、Loop
  Engineering、I1-I6 縦スライス)。実 spend の powered bank sampling run は C-proper AUTHORIZE 後のみ。
- **C-design #2 ADR = bank candidate に `AUTHORIZE_C_PROPER` を FROZEN (2026-07-10、doc-only、user 裁定 + T3
  criterion 4=substrate enrichment)**。B 反復 bank 実コード完了 (PR #64 MERGED、main=474346c、I1-I6 + cross-review
  全反映) を受け、materially-different bank candidate (M-sample estimability + competing-cue substrate) が
  live-channel-conformance family invariant に適合し 5 壁を回避しうるかを desk-audit し hard futility gate を通した
  C-design #2 (#1 の同 family REFUSE を覆せるか)。**決定的発見 = #1 REFUSE の根は estimability の死点 (v1 は各
  context 1-sample で P(zone|ctx,T) 推定不能) であり、B の M-sample bank がこれを直接解消**。power worksheet
  (`bank_power.py`、M=300/K=8/δ=0.10/H_min=0.5/ρ=0.5、proposal 乖離ゼロ) が **壁1&4 を再定位**: near-uniform
  `[0.2]×5` は power=1.0 (「near-uniform=低検出力」は誤り)、真の死点は **achievable delta_tv→0 (think=False
  collapse)** = empirical measurement target (collapse demo power≈0.18)。**Codex Verdict=Revise → 事実誤認 1 +
  HIGH 2 + MEDIUM 3 全反映が決定的に honest 化**: [FACT] ES-4 Phase 0 は validity+power のみでなく
  `NO_GO_EFFECT_ABSENT` (pilot upper-CI < floor) の effect-absence 分岐を持つ (`verdict_report.py:205`) → bank は
  validity+power を PASS するが **effect-absence 分岐は pre-spend pilot=spend ゆえ C-proper verdict schema へ
  relocate (意識的 deviation) = effect-absence risk を R-budget=1 の spend が全面負担**、[HIGH-2] 「(i) doc-only
  必須なら矛盾」は撤回 → §D1.2 は REFUSE を letter 上許可、AUTHORIZE は design-intent consistency に基づく推奨で
  **letter 強制でなく user 裁定が決した**。**claim 境界 = bank は #1 REFUSE の根を解消し hard futility gate の
  validity+power を PASS したであって、live channel が zone を偏らせた/H4 肯定/R-budget を焼いた/効果が存在すると
  示したでない** (未測定、budget 未消費、firing⇔detectability 混同禁止、AUTHORIZE は effect-present verdict でない)。
  詳細 = `.steering/20260708-m13-c-design-bank/design-final.md`。次工程 = powered sealed run (別タスク、実 spend
  live-channel-conformance R-budget=1 消費、think=False 強制・powered M/K・WSL byte 一致・tune-to-pass 封鎖) →
  verdict schema で evaluation → collapse なら valid FAIL → 両 family exhaust (SPDM-landscape は SPENT) →
  arc-close 自動執行。
- **C-proper powered sealed run = verdict `NO_CHANNEL_CONFORMANCE` (valid FAIL) → arc measurement-line CLOSE
  (2026-07-10、実 spend、user ratify)**。C-design #2 の `AUTHORIZE_C_PROPER` (PR #65 MERGED) を binding 前提に、
  凍結 C-proper scorer (Codex Verdict=Revise の HIGH 3 + MEDIUM 3 を実走前に全反映 = integrity seal / powered-scale
  強制 / permutation p の Phipson–Smyth 保守補正 / schema robustness) を建て、**real qwen3:8b で M=300·K=8
  (4800 draws)・think=False の powered sealed run** を one-shot 実走し、§CB4.4 verdict schema を実計算した。
  **結果 = `NO_CHANNEL_CONFORMANCE` (valid FAIL、§CB4.4 branch (b) effect-absent)**: rho_hat=1.0 (8/8 context が
  H(zone|ctx)=0.63–0.75 bit で (i) PASS) / power=1.0 (effective K'=8、fully powered) / **tv_bar=0.0381 < δ_min=0.10
  (floor 未達)・permutation p=0.058 > α=0.05 (非有意)**。**決定的発見 = 第2リンク (sampling→zone 選択 bias) は
  powered な計測下で pre-register 済 floor に detectable でない**。かつ **壁1&4 の「near-uniform=低検出力」は empirical
  に反証** (near-uniform 基質で power=1.0、rho=1.0)、死点は C-design #2 §CB2.3 の予言どおり **achievable delta_tv→0
  (think=False regime で T_on≈T_off の zone 分布)** に宿った。**disposition = valid FAIL → live-channel-conformance
  family bounded-close (R-budget=1 消費) → SPDM-landscape [SPENT] と両 family exhaust → arc §4.3 ratchet で
  arc measurement-line の CLOSE を自動執行**。**claim 境界 (over-read guard §CB6、不可侵)**: これは
  **effect-absent measurement** であって ✗「live channel が zone を偏らせない/substrate 否定/H4 否定/中核命題 否定/
  divergence 否定」ではない — (i) PASS (rho=1.0) が示すとおり substrate は ≥2 zone を license しており、否定されたのは
  **第2リンクの detectability (本 candidate class 内、pre-register 済 floor)** のみ (firing⇔detectability 分離、
  5 機序分離、organic scene 非一般化)。**arc-close の意味 (§5.1–5.2 letter)**: M13 situated-3D-substrate arc の
  **measurement ライン**の bounded 終端 (両 named R-budget family が exhaust) であって、**substrate 建設の大方針
  (ECL 器官・situated 3D embodiment) の close ではない** (scope 分離)。arc-close は「効果を否定した/floor を測った/
  中核命題を裁定した」でなく、**valid+powered な計測が第2リンク detectability を registered floor で absent と
  measure し、budget 規律が計測ラインを閉じる designed-honest な終端** (§CB5.2 item 5)。詳細 =
  `.steering/20260710-m13-c-proper/design-final.md` + `experiments/20260710-m13-c-proper/`
  (env.md + sealed artifacts、bank_checksum `5e991dd6…`)。
- **post-C-proper forward disposition = (B) 計測 line CLOSE 維持 + 建設 pivot、reasoning-trace door 保全のみ
  (FROZEN 2026-07-11、doc-only・非 spend、user ratify)**。C-proper 後の方向を **doc-only の (1) 原因診断 +
  (2) 計測再入 desk-audit** で確定 (実 spend ゼロ、新規実走なし)。**原因診断 (over-read guard §CB6 付き)**: 確定 =
  第2リンク (sampling→zone bias) は registered floor で detectable でない / C-proper bank apparatus 上の categorical
  substrate は健全 (rho=1.0、H(zone|ctx)=0.63–0.75 bit・mean≈0.68、organic scene 非一般化)。効果が弱いのは spread
  不在でなく「その spread が λ で動かない」から。**並置仮説 (分離せず = C-proper は原因分離 design でない)** =
  (a) think トレードオフ 〔think=False が plan 保証と引換に sampling→zone 感度を殺す、C-proper 封印 apparatus/
  think=False bank 内で反証不能、中核テーゼと響く〕/ (b) λ→温度ゲイン微小 (+0.12) / (c) zone 上流決定。
  **計測再入 desk-audit (re-entry bar 適用)**: 決定的 letter = **§D0.2(D0-e) 非反射条項** — 本タスク = post-C-proper
  (直前 FAIL への反応) 文脈ゆえ、ここで新 measurement family を起票することは名指しで禁じられた反射経路。加えて
  measurement family = ちょうど 2 が両 exhaust (残 budget=0、general per-class rule 無し)。**reasoning-trace 候補
  (推論トレースの発散を測る) の 2 点セット crux** = (a) `<think>` 二相マネジメント (plan 抑制 / trace 捕捉) は Ollama+
  qwen3 で plausible だが**必要条件**、(b) 非循環 trace-divergence estimand/scorer が**致命欠落** (embedding-novelty は
  壁2 = ES-4 embedding rarity 自己 anchor 循環 = INVALID_SCORER の再来) → (b) 未達なら死点が「zone 不動」から
  「trace 発散が循環 scorer で測れない」へ**移動するだけ**。family 分類 = tie→既存 spent family (SPDM-landscape 側
  or live-channel-conformance 側、どちらも SPENT) or 3rd-family (本文脈で D0-e 禁止)、re-entry item 2 (futility gate)
  desk-audit FAIL。∴ **本文脈で measurement 再入不能**。**door 保全 (sketch なし、user 裁定 door 粒度)** の発動条件
  3 点 (すべて必須) = (1) 本 FAIL 文脈から分離した from-scratch・非反射の独立 forward ADR / (2) wall-2 非循環
  trace-scorer の先行解決 / (3) `<think>` 二相捕捉 enabler。door は「開く」でなく「保全」、実 spend は別タスク +
  user spend ratify を要す。**process (正典)** = reimagine (v1 機序起点 意図破棄 → v2 seal-letter 起点 独立再生成、
  両案が「(b) 致命欠落」「本文脈再入不能・door 将来保全」に独立収束) + Codex independent review (**Verdict=
  Adopt-with-changes、HIGH なし**、MEDIUM 2 [反証不能 scope 限定 / tie 先拡張] + LOW 3 全反映)。**claim 境界
  (over-read guard §5.1/§CB6、不可侵)** = ✗「効果不在を確定 / reasoning-trace は無価値と裁定 (door 保全) /
  substrate・中核命題・H4 否定 / 二度と計測しない (door は正規経路で保全) / 原因を特定 (並置仮説) / 新 spend を
  authorize (doc-only)」。**閉じたのは measurement ライン**であって substrate 建設大方針でも reasoning-trace door
  でもない。pivot 先候補 (別 scoping タスク) = M2 N体 embodied society (Project Sid [4]) / M3 long-horizon
  endurance / M4 Godot 可視化。詳細 = `.steering/20260711-m13-post-cproper-disposition/design-final.md`
  (+ design-v1/v2/comparison / codex-review.md verbatim / decisions.md)。
- **construction milestone-2 scoping ADR (FROZEN 2026-07-11、doc-only・非 spend、user ratify)**: post-C-proper
  disposition (B) の建設 pivot の第一歩 = 次に建てる construction milestone を M2/M3/M4 から 1 つ確定する
  doc-only scoping (実 spend ゼロ、measurement 非再入、holding 不可侵)。**採用 = M2 (N体 embodied society)**。
  reimagine α (M2-first) × β (M4-first) 独立生成 → **M2 spine + β graft + M3 post** (可視化は既存 live seam の
  N体 primitive 拡張で焼き、full Blender skinned-humanoid 可視化は M4 残置。M3 endurance は post-M2 =
  society 成立後、反復幅≠endurance-length)。**二層構造** (Codex HIGH-1 crux 一意化) = **Layer1 (N体 composition
  + 並行 determinism、機序非依存) が milestone を定義する GATING** + **Layer2 (self-other/mirror functional
  analog、user 着眼 2026-07-11) は bounded construction attempt** (難航しても M2 を invalidate しない、実装順序
  Layer1→Layer2 binding)。self-other/mirror = **ミラー・シム (mirror-sim、`glossary.md`)** = 守破離「守=模倣」・
  cognitive habits と直結し単一 agent では不成立で N体でこそ意味を持つ functional analog、文献カード
  [affect-appraisal 統合サーヴェイ] desk-audit 済 construction 経路。**4 規律
  (binding)** = (a) construction-mode only (SimToM prompt-level・causal wiring・floor/verdict/scorer なし) /
  (b) functional analog 語彙 (✗ミラーニューロン実装/神経再現) / (c) 予算ゼロ SimToM prompt 先行 (SOO LoRA は
  後段 defer) / (d) appraisal measurement (行動予測 H-B / 非同定性 H-C + AppraisalState measurement 部分) 非混入
  = potential 第3 measurement family (closed-adjacent、非反射独立 ADR 前件、本 scoping 対象外)。**acceptance =
  causal wiring / boolean のみ** (floor/landscape/verdict/scorer/D_* なし、ECL v0 continuity-gate 同型) =
  Layer1 は versioned event/decision log 全体 checksum (geometry はその一部) / Layer2 は closed fixture の
  `depends_on_other_observation ∈ {true,false}` boolean wiring のみ (magnitude/quality/prediction accuracy 禁止)。
  **決定的な honest 論点 = N体化の非対称**: B-nbody-scoping は N体を *measurement* teeth 非最適で defer 裁定したが
  本 ADR は *construction* primary — 矛盾でなく目的関数が違い、**measurement-line CLOSE (C-proper) が「N体を
  defer させていた理由 (measurement 非最適)」を本 construction ADR の選定 non-governing 化した** (cherry-pick でなく
  CLOSE という事実が前提を変えた、Codex MEDIUM-1 で "moot"→"non-governing/deferred" に弱化・risk は残存)。
  **claim 境界 = construction milestone 確定 + high-level scope であって floor/divergence/measurement でない**
  (N体 emergence は construction 現象で measured divergence でない、5 機序分離継承、reasoning-trace door 保全のまま)。
  process = /reimagine (v1[α] 意図破棄 → 独立 v2[β] → M2 spine + β graft) + Codex **Verdict=Adopt-with-changes**
  (「M2 選定は後付けでなく measurement-line CLOSE 後の目的関数変更として defensible」是認、HIGH 3 [Layer2 gating
  一意化 / determinism 対象を event-log 全体へ / replay-log と causal-fixture 分離] + MEDIUM 4 + LOW 3 全反映)。
  次工程 (別タスク) = 選定 M2 の impl-design ADR (HOW) → 実コード (Loop Engineering)。詳細 =
  `.steering/20260711-m13-construction-m2-scoping/design-final.md` (+ design-v1/v2/comparison / codex-review.md
  verbatim / decisions.md)。
- **M2 impl-design ADR = HOW 技術契約 pre-register (FROZEN 2026-07-11、doc-only・非 spend・measurement 非再入)**:
  M2 scoping (WHAT/WHY) を受け、sealed 実コード前に HOW を pre-register する impl-design (ECL v0 / B と同型の
  正典パターン scoping →【impl-design】→ 実コード)。**reimagine v1(α: Layer1+Layer2 統合 1 本) 意図破棄 → v2(β:
  Layer1-only 先行) 独立生成 → β spine + Layer2 seam graft + Placement-1** (user ratify AskUserQuestion)。
  **裁定 = 本 ADR は Layer1 (N体 determinism, GATING) の HOW を full 契約化**、Layer2 (ミラー・シム) は
  **seam/readiness 契約のみ graft** (event-log の self-other slot を最小 wire envelope で予約 + continuity 原則
  + 4 規律)、内部 HOW (prompt schema/continuity fixture) は Layer1 実コード land 後の別 mirror-sim impl-design
  ADR へ defer (scoping §2.3.1 実装順序 binding を ADR 分割で機械担保)。配置 = `integration/embodied/society.py`
  新規 (loop.py Plane2/checksum + handoff.py [既に N体前方互換] 再利用、run_ecl_loop 無改変)。**Layer1 契約核** =
  record-mode 逐次 sorted scheduler (asyncio.gather を record mode で捨てる = run_ecl_loop 単一 agent 直駆動の
  N体一般化、live は gather 保持) + per-agent/per-pair named RNG substream + **b-nbody §B4 侵入経路 sorted 化**
  (separation/proximity `combinations(values,2)` / 非 sorted values() / async gather / dialog RNG) + discovery
  guard (登録順 permutation → 同一 checksum、DB ORDER BY、canonical key sort) + **versioned event/decision log
  全体 checksum** (geometry はその一部) + spend ast-guard + acceptance test 凍結 (causal wiring/boolean のみ、
  floor/verdict でない)。**実コード確証を binding** (impl-design は ADR 由来でなく code-verify、FixturePlayer H1
  教訓): WorldRuntime N体保持 / run_ecl_loop 単一 agent 逐次直駆動 / handoff 既に sorted(agent_id)→order_slot /
  dialog injected Random。process = /reimagine + Codex **Verdict=Adopt-with-changes** (事実誤認 HIGH なし、
  HIGH 4 [token guard を executable AST 限定 / N=1 byte 不変を legacy·M2 canonical-equivalent の 2 経路二分 /
  「N≤2 byte 不変」撤回→N=1 限定+sorted pair canonical / set blanket ban 撤回→sorted(set) allow] + MEDIUM 4 +
  LOW 1 全反映)。**claim 境界 = HOW 技術契約の pre-register であって floor/divergence/measurement でない**
  (holding 不可侵・R-budget=0、over-read 禁止、reasoning-trace door 保全のまま)。次工程 (別タスク) = M2 実コード
  (Loop Engineering、Layer1 I1-I6 → Layer2 別 ADR 後の別 Loop)。詳細 =
  `.steering/20260711-m13-m2-impl-design/design-final.md` (+ design-v1/v2/comparison / codex-review.md verbatim /
  decisions.md)。
- **M2 Layer1 実コード landed (2026-07-11、construction・実装 spend、measurement spend でない = R-budget=0 不変)**:
  M2 impl-design ADR (Layer1 HOW、FROZEN PR #71) を binding 前提に、**Layer1 (N体 composition + 並行
  determinism, GATING) を Loop Engineering (I1-I6 subagent-per-issue、worktree /loop-issue) で実装しきった** 初の
  実コード。`integration/embodied/society.py` 新規 (N体決定的 driver = record-mode 逐次 sorted scheduler、
  run_ecl_loop 無改変で N=1 byte-identical) + `world/tick.py` §B4 侵入経路 sorted 化 (separation/proximity
  combinations / 非 sorted values() を `_sorted_runtimes()` 経由、live 挙動不変) + `step_cognition_once` public
  seam + **versioned event/decision log 全体 checksum** (geometry はその一部、self_other slot は null で予約=
  Layer2-ready) + per-agent/per-pair named RNG substream (pair_key=canonical JSON array) + discovery guard
  (登録順 permutation → 同一 checksum) + record-mode dialog 逐次配線 (utterance=決定的テンプレート、LLM call
  ゼロ) + handoff N体 additive schema (`m2-society-1`、legacy byte unchanged / M2 N=1 canonical-equivalent の
  **2 経路二分**) + committed N体 golden + spend ast-guard。**acceptance = §M9 全 test 緑** (causal wiring /
  boolean、floor/verdict でない): event_log_checksum_stable / determinism_permutation / determinism_checklist /
  pair_interaction_deterministic / legacy_byte_unchanged / n1_canonical_equivalent / handoff_manifest_pins /
  log_carries_self_other_slot_forward_compat / no_measurement_computation / llm_call_cap。**統合フル pre-push
  4 段 ALL CHECKS PASSED (3580 passed)**、**DG-2 cross-platform byte parity = WSL Ubuntu byte 一致実測 PASS**
  (6 桁量子化が libm 1-ULP drift 封鎖)。TASK-POST cross-review = code-reviewer(Opus) LGTM/HIGH なし + Codex
  (Windows sandbox degrade、observable concern fold-in)、MEDIUM 2 件反映 (spend guard を handoff 拡張 / decisions
  明示 sort、golden byte 不変)。**決定的 construction 発見**: (i) dialog を record-mode driver に配線する際 uuid4
  dialog_id が checksum 混入で latent 非決定 → per-pair seeded 採番で封鎖 (I4)、(ii) N=1 society driver は
  run_ecl_loop と byte-identical (単一 agent 埋込 per-agent 純関数不変の強 witness)。**claim 境界 = construction
  (再現可能な N体 substrate を建てた) であって measurement でない** (N体 emergence は construction 現象で measured
  divergence でない、checksum は再現性であって floor でない、firing⇔detectability 混同禁止、over-read 禁止、
  5 機序分離継承、holding 不可侵、reasoning-trace door 保全のまま)。次工程 = Layer2 (ミラー・シム) mirror-sim
  impl-design ADR (Layer1 land 後、実 API 上で prompt schema/continuity fixture を確定) → 別 Loop。詳細 =
  `.steering/20260711-m13-m2-society-layer1-code/` + `loop/20260711-m13-m2-society-layer1-code/`。
- **M4 situated 3D 可視化 scoping ADR (FROZEN 2026-07-11、G-GEAR、user 裁定 ratify・doc-only・非 spend・
  R-budget=0 不変)**: 建設 pivot の第2 milestone。Layer1 (PR #72) が供給した決定的 N体 substrate + committed
  golden + handoff (`m2-society-1`) + Godot playback を**初めて 3D で「動く N体 society」として可視化する建設
  spike の WHAT/WHY + high-level scope**。正典パターン scoping (本 ADR) →【impl-design】→ 実コード。**技術 =
  geometry nodes (Blender) は user 裁定で確定**、reimagine は HOW/scope を weigh (使うか否かは論点でない)。
  **reimagine v1 (最大構成: 環境+avatar 両方 geo nodes + skinned rig/anim + live WS) 意図破棄 → v2 (最小逆算:
  「楽しめる動く 3D N体 society」から逆算) 独立生成 → v2 spine + v1 zone 網羅 graft** (user ratify)。**選定** =
  環境=geometry nodes で 5 zone (study/peripatos/chashitsu/agora/garden) 手続き生成 → zone 単位 .glb export →
  `godot_project/assets/environment/` 消費 (既存 `erre-sandbox-blender/export_chashitsu.py` 手続き primitive→glTF
  先例の進化形) / avatar = primitive placeholder (skinned humanoid rig/anim は fidelity として後続 defer) / 消費 =
  offline committed-golden 決定的再生 (新規 dev viewer、live WS defer・LLM 非接触) / 全景 = dev-only wrapper
  (既存 `MainScene.tscn` は production WebSocketClient 接続済ゆえ無改変)。**replay 入力 role split** = position/motion
  は `ecl_trace.jsonl` の `(physics_tick_index, order_slot)`、speech/animation は `envelope_stream.jsonl`
  (Codex MEDIUM-2)。**GPL 分離 binding** (bpy を `src/erre_sandbox/` に絶対置かない、`erre-sandbox-blender/`
  GPL-3.0 分離、.glb はデータゆえ Godot 消費可)。**acceptance = causal wiring / boolean / 再現性のみ** (AC1 決定的
  build [再走 byte 不変] / AC2 golden→N avatar order_slot 配置・trace 通り移動 / AC3 決定性 / AC4 5 zone 描画 /
  AC5 measurement 面ゼロ [evidence/spdm/runningness/floor/landscape/verdict/scorer/bank*/D_* を import も emit も
  しない denylist、Codex HIGH-1 で本文同幅化])。process = /reimagine + Codex **Verdict=Adopt-with-changes**
  (Windows PowerShell sandbox degrade を Node REPL フォールバックで回避し完走、HIGH-1 [AC5 guard 幅] + FACT×2
  [座標 SSOT=`contracts.geometry.ZONE_CENTERS`/`world.zones` は shim、golden trace 全 peripatos で "zone 間移動"
  は齟齬] + MEDIUM×3 全反映、LOW-2 [新 Blender script SPDX header] は impl-design defer)。**claim 境界 =
  construction (substrate を observe する可視化) であって measurement でない** (可視化は observe、floor/verdict/
  divergence を作らない・測らない、「2体が golden 通り移動」は construction 現象で measured convergence でない、
  golden が両者 peripatos なのは fixture 性質であって measured 収束でない、firing⇔detectability 混同禁止、over-read
  禁止、holding 不可侵・R-budget=0、reasoning-trace door 保全のまま)。次工程 (別タスク) = M4 impl-design ADR
  (HOW = geometry nodes ノードグラフ / zone .glb 粒度 / dev viewer 具体 / 決定的再生検証 / Zazen 非 zone 扱い /
  GPL export 自動化 + SPDX header) → 実コード (Loop)。Layer2 mirror-sim impl-design ADR は別トラック併存。詳細 =
  `.steering/20260711-m13-m4-3d-visualization-scoping/design-final.md` (+ design.md [reimagine 2 案] /
  codex-review.md verbatim / decisions.md)。

- **M4 situated 3D 可視化 impl-design ADR (FROZEN 2026-07-11、G-GEAR、user 裁定 ratify・doc-only・非 spend・
  R-budget=0 不変)**: 上記 scoping (PR #73) を binding 前提に **HOW (Blender/Godot 技術契約) を実コード
  (Loop) の前に pre-register**。正典パターン scoping →【impl-design (本 ADR)】→ 実コード。**reimagine** =
  初回案 v1 (geometry nodes を chashitsu export の素直な進化、AC1 を .glb raw byte 再走一致で担保、
  EclReplayPlayer 拡張) を意図破棄 → v2 (acceptance 逆算で決定性契約を二分) 独立生成 → **ハイブリッド
  (v2 spine + v1 の段階移行 graft)** を user ratify。**HOW 技術契約の核 = 決定性 witness を raw .glb byte
  cross-machine 一致にしない**: (i) **AC1 = seed-free 決定的パラメトリック geometry** (Distribute
  Points/未固定 Random 禁止、index 駆動格子) の **量子化構造フィンガープリント** (mesh/頂点数/bbox/material、
  6 桁量子化 = handoff の landed 規律移植、glTF accessor min/max を純 GLB-JSON パーサで JSON header から取得、
  binary decode 不要) + 同一機 byte idempotency (開発者側、Blender 必須) の二層 witness / (ii) **AC2/AC3 =
  新規 `SocietyReplayViewer.gd`** (dev-only、`EclReplayPlayer.gd` 無改変) が **committed golden を headless
  再生し placement/replay 列を dump → Python canonicalizer で byte 比較** (motion=`ecl_trace` 値の
  pass-through echo、Godot runtime float→str を witness にしない) / (iii) **座標** = `contracts.geometry.
  ZONE_CENTERS` から `zone_layout.json` 純生成 + `.tscn` root transform drift を 6 桁 exact で閉じる
  (既存 `.tscn` 手書き `33.33` は authority `33.333…` と実 drift → 実装 Loop で是正) / **.glb 粒度** =
  zone 単位・local content 原点中心 + 共有 BaseTerrain (既存 100m primitive) + Godot .tscn root で
  ZONE_CENTERS 配置 / **AC5** = M2 spend ast-guard 踏襲 (.py executable-AST + .gd text scan、denylist 全幅、
  identifier ban と path/import guard を分けて false positive 抑制) / **Zazen 非 zone** (ERRE mode、AC4
  5 zone に非含) / **SPDX GPL header** 新規 Blender script 必須 + `export_chashitsu.py` 是正。process =
  /reimagine + Codex **Verdict=Adopt-with-changes** (sandbox degrade を web 検索 [Khronos glTF 2.0 仕様裏取り]
  で完走、HIGH-1 [accessor min/max は mesh-local bounds、node transform=identity binding + fail-closed] +
  HIGH-2 [圧縮/外部 buffer geometry を禁止 fail-closed] + HIGH-3 [Godot runtime float→str を witness に
  しない] を FROZEN 前反映、MEDIUM×4 [order_slot 非 join key/denylist 分割/.tscn 6桁 exact/非 GPL tool 配置] +
  LOW×2 反映)。**claim 境界 = construction であって measurement でない** (fingerprint/placement checksum は
  再現性 witness であって metric/floor/verdict/scorer/閾値/aggregate に接続しない、over-read 禁止、holding
  不可侵・R-budget=0、reasoning-trace door 保全)。次工程 = M4 実コード (Loop、§9 issue 縦スライス → worktree
  `/loop-issue` → cross-review)。Layer2 mirror-sim impl-design ADR は別トラック併存。詳細 =
  `.steering/20260711-m13-m4-impl-design/design-final.md` (+ design.md/design-comparison.md [reimagine 2 案] /
  codex-review.md verbatim / decisions.md)。

- **M4 situated 3D 可視化 実コード landed (2026-07-12、G-GEAR、construction・実装 spend・measurement spend
  でない = R-budget=0 不変)**: 上記 impl-design (PR #74) の HOW を実コードへ。Loop Engineering =
  **subagent-per-issue** (worktree /loop-issue モデルの実体、各 worker → loop-watchdog の verify_level=recheck
  独立再走で done gate、I1-I6 全緑)。成果 = **5 zone geometry-nodes 環境 .glb + 6 桁量子化構造 fingerprint**
  (純 GLB-JSON パーサ [bpy 非依存] で committed .glb 再計算 → committed fingerprint と byte 一致、非 identity
  node transform/圧縮 ext/external buffer/sparse-only POSITION を fail-closed、同一機 idempotency sha256 一致) +
  **dev-only `SocietyReplayViewer.gd`** (golden N体 substrate を headless 再生、motion=`ecl_trace` pass-through
  echo / speech·anim=`envelope_stream` [move 非位置]、別 clock domain 独立系列、`EclReplayPlayer.gd`/`MainScene.tscn`
  無改変) + **headless placement dump → Python canonicalizer 正規化 → committed `expected_placement.jsonl`
  byte 一致** (N=2 order_slot 順・trace 通り) + **measurement-zero guard** (.py executable-AST [Attribute/keyword
  scan 込み] + .gd text scan、denylist 全幅) + **GPL/SPDX 境界 guard**。**cross-platform 決定性 = WSL byte
  parity 実測** (5 fingerprint + expected_placement Linux 再生成 byte 一致)。統合フル CI 緑 (3659 passed) +
  TASK-POST cross-review (code-reviewer[Opus] + Codex[gpt-5.5]、**両者 HIGH=なし**、MEDIUM 3 反映 = parser
  fail-closed 完全実装 [§1.3 HIGH-2] / guard scan 拡張 / .tscn コメント是正)。**claim 境界 = construction であって
  measurement でない** (fingerprint/placement checksum は再現性 witness であって metric/floor/verdict/scorer に
  接続しない、over-read 禁止、firing⇔detectability 混同禁止、5 機序分離継承、holding 不可侵・R-budget=0、
  reasoning-trace door 保全)。「2 avatar が golden 通り move」は construction 現象で measured
  convergence/divergence でない (golden は 2 体とも全 peripatos = fixture 性質)。**保留 (user 裁定待ち)** =
  interactive mode の scene 実体化・avatar 駆動 (design §3.4 と issue I5「最小実装で可」の乖離、推奨 = M4 fidelity
  別 ADR へ defer)。詳細 = `loop/20260711-m13-m4-code/` (issues I1-I6 / retrospective / _loop-events) +
  `.steering/20260711-m13-m4-code/` (decisions [判断6+cross-review 採否] / code-reviewer-review.md /
  codex-review.md verbatim)。次工程 = Layer2 mirror-sim impl-design ADR (別トラック併存) or M4 fidelity
  (skinned humanoid) 別 ADR (順序 + interactive 裁定は user)。

- **M4 society run enrichment 実コード landed (2026-07-13、G-GEAR、construction・real qwen3:8b 実装 spend・
  measurement spend でない = R-budget=0 不変、PR #76)**: 上記 M4 可視化 (PR #75) の薄い golden
  (2 agent・全 tick peripatos・scripted plan) を **real qwen3:8b sealed golden へ enrichment**。ECL v0
  live-capture(N=1) を society scope に 1:1 mirror し、**N=3 agent (kant/nietzsche/rikyu、初期 zone=
  study/peripatos/chashitsu) society run を real qwen3:8b sealed capture (record-mode, think=False, seed=0,
  horizon=12) で封印記録** → 新 golden `tests/fixtures/m4_society_live_golden/` + Godot viewer 可視化 +
  headless placement byte-parity。Loop Engineering = **subagent-per-issue** (I1-I5、各 worker →
  test-runner→loop-watchdog verify_level=recheck 独立再走で done gate)。成果 = `society_live.py` N体
  live-capture harness (固定 constructor、`build_society_live_env_pins`、annotation 型 observables) +
  `m4_society_live_capture.py` `--capture`/`--verify` + R3 per-agent from-jsonl decoder (既存
  `handoff.recorded_calls_from_jsonl` に委譲、order_slot は fail-closed 検証のみ) + `SocietyReplayScene.tscn`
  Avatar2 + replay test `[m2,m4]` parametrize (m2 回帰ゼロ)。**honest outcome (over-read guard)** = real
  qwen3:8b は **genuine に 5 distinct destination_zone を author** (llm_status=ok 36/36、fallback ゼロ) し
  **R1「think=False で zone 移動しない」を empirical 反証**、しかし rendered zone は locomotion resolver
  (`resolved_from=memory_centroid`、mocked constant embedding、§設計通り action-LLM のみ live) で単一
  peripatos に collapse = **honest single rendered-zone (壁1&4 と同 kernel、first-class pass、動きを捏造しない・
  multi-zone へ toward-tune しない)**。**判断3 (superseding ADR、frozen `society.py` 改変・user 裁定)** =
  I5 cross-platform closure で `event_log_checksum` の Win↔Linux drift を検出 → 根本原因を per-category →
  field-level diff で完全 localize (`_decision_projection` が `envelope_provenance` を生 `model_dump_json`
  文字列で載せ、埋め込まれた full-precision `cognitive.valence`/`mood_baseline` [physiology dynamics/libm] が
  last-ULP drift、他 float は 6桁量子化を通るが provenance だけ素通り = `society.py` 自身の §M4.4「every float
  quantised」invariant 違反、M2 Layer1 latent gap を M4 live run が初露見) → **既存 proven helper
  `handoff._quantize_embedded_json` (rendered decisions で使用中、serializer 一致) を `_decision_projection` に
  適用** → WSL byte-parity 実測 PASS (`e22ecc91` が Win==Linux 一致)。M2 は committed event_log_checksum を
  持たず property test のみゆえ regression なし。**cross-platform 決定性 = WSL byte parity 実測** (replay +
  event_log + manifest 再render + fingerprint 全 Linux 一致) + pre-push 4段 ALL CHECKS PASSED (3676 passed)。
  process = user 裁定 (A=量子化 fix + ADR) + Codex 個別 review (実装前、HIGH3 [M2 no-op 条件不足→exact test
  化 / parse fail-fast / 量子化 float 限定 bool 除外]・MEDIUM5 全反映) + TASK-POST /cross-review (code-reviewer
  [Opus] + Codex [gpt-5.5]、**両者 HIGH=なし**、MEDIUM 反映 = verify decoder fail-closed 統一 / WSL parity
  最新 HEAD 再記録 / R3 global order は checksum witness で担保)。**claim 境界 = construction であって
  measurement でない** (checksum/fingerprint/placement は再現性 witness であって metric/floor/verdict/scorer/
  divergence に接続しない、observables は annotation 型、over-read 禁止、firing⇔detectability 混同禁止、holding
  不可侵・R-budget=0、reasoning-trace door 保全)。詳細 = `loop/20260712-m13-m4-society-enrichment/`
  (issues I1-I5 / retrospective / _loop-events) + `.steering/20260712-m13-m4-society-enrichment/`
  (design-final / decisions [判断1-3 + Codex 採否] / blockers [BLOCKER-2 診断] / codex-review* verbatim)。
  次工程 = memory `project_m4_society_enrichment` 記録 / real embedding で rendered multi-zone を genuine に
  出す別 ADR (memory_centroid collapse 解消) / M2 Layer2 mirror-sim / M4 fidelity Wave 2 (skinned humanoid)。
- **M2 Layer2 (ミラー・シム = self-other functional analog) impl-design ADR + 実コード landed (2026-07-13、
  construction・実装 spend、measurement spend でない = R-budget=0 不変)**: M2 の第二 cognitive 次元 =
  **self-other/mirror functional analog (bounded construction attempt、GATING は Layer1)** を、HOW 技術契約の
  pre-register (impl-design ADR、FROZEN 2026-07-13) → 実コード (Loop Engineering、J1-J5 縦スライス) の正典
  パターンで landed。**HOW 契約核** = (a) seam = **single-call transient prompt-context injection** — observer の
  既存 cognition call に他者 window-(t-1) 記録行動由来の self-other context を **M10-B `world_model_entries`
  idiom** で注入 (**新 LLM call を作らない** = 予算ゼロ SimToM prompt 先行の最純粋形、空なら byte-identical・
  USER 側・memory 非書込み transient、default-off で Layer1 byte-identical) + pure builder (strict prefix filter
  `other != observer` ∧ `source_window = t-1 < window_index` で self/future leak 構造排除) / (b) continuity =
  **exact-oracle boolean wiring** (builder purity + behavior-dependency 二点 witness、`depends_on_other_observation`
  は test 計算値で LLM 非 emit、**poison fixture** で replay ⊥ causal-fixture 分離を反証可能に固定) / (c)
  disjointness = **runtime write-spy** で self-other が episodic memory 非書込み (ES-4 self-anchor collapse 同型
  循環を構造排除) / (d) payload = run-level 集約 + 継承 serializer + allowed scalar {str,int,bool,None}
  (**float-free** で cross-platform drift 構造回避) + list canonical pre-sort + 禁止 field 名 / (e) handoff
  Layer2 additive schema (`m2-selfother-1`、slot None=Layer1 byte-unchanged) + spend ast-guard。process =
  /reimagine (v1[explicit two-step] 意図破棄 → v2[single-call injection] 独立生成 → **v2 spine + v1 pure builder
  graft**) + Codex **Verdict=Revise の HIGH 4 全反映** (poison fixture / no-future-self-leak / determinism 契約
  完全 pin / runtime write-spy) + MEDIUM 5 / LOW 2。**実コード** = `cognition/prompting.py` (self_other_context
  kwarg) + `cognition/cycle.py` / `world/tick.py` (transient thread) + `integration/embodied/society.py`
  (build_self_other_context + SelfOtherContext 型 + run_society_loop `self_other_enabled` + run-level slot 集約、
  逐次 sorted scheduler ループ無改変) + `handoff.py` (Layer2 additive bump)。**acceptance = §L10 test 13 本緑**
  (全 boolean/count/AST-only、floor/verdict/scorer/statistics ゼロ): wiring_continuity_positive/negative /
  context_builder_purity / slot_provenance / replay_causal_separation (poison) / no_future_or_self_leak /
  disjointness (write-spy) / event_log_checksum_stable / n1_degenerate (4 経路) / world_model_coexist_deterministic /
  functional_analog_vocabulary / no_measurement_computation / llm_call_cap。**統合フル pre-push 4 段 ALL CHECKS
  PASSED (3692 passed)**、**Layer2 golden WSL byte-parity 実測 PASS** (4 artifact、payload float-free + 継承
  serializer + 6桁量子化)。TASK-POST cross-review = code-reviewer(Opus 実読)=**Approve/HIGH なし** + Codex
  (Windows sandbox degrade→embedded-diff)=**Revise、HIGH 2 [utterance json escape / adversarial disjointness] +
  MEDIUM 3 [proximity 非 observer-relative relabel / window<=0 guard / checksum comment 是正] 全反映**。**決定的
  construction 発見** = (i) observed utterance の raw prompt 補間は prompt-injection 面ゆえ json escape が bounded
  契約の必要条件、(ii) disjointness は echoing mock で「LLM が segment を echo しても memory sink 非到達」を
  adversarial に固定して初めて non-vacuous、(iii) 新 LLM call を作らない設計ゆえ on/off call-count 同一 = seam の
  最純粋 witness。**claim 境界 = construction (相互観察する N体 society の中核=ミラー・シムを建てた) であって
  measurement でない** (self-other 相互変調は construction 現象で measured divergence でない、continuity は causal
  wiring/boolean であって floor/magnitude でない、magnitude 非読取=covert scorer 禁止、firing⇔detectability
  混同禁止、over-read 禁止、5 機序分離継承、holding 不可侵・R-budget=0、reasoning-trace door 保全のまま、SOO
  LoRA は defer=prompt-level SimToM のみ)。**landing で construction milestone M2 完結** (Layer1 GATING + Layer2
  bounded、相互観察する N体 embodied society が建つ)。次工程 = memory `project_m13_m2_layer2_code` 記録 / M3
  endurance or M4 fidelity Wave 2 の別 scoping。詳細 = `.steering/20260713-m13-m2-layer2-impl-design/`
  (design-final / decisions / codex-review verbatim) + `.steering/20260713-m13-m2-layer2-code/`
  (cross-review-synthesis / codex-review* / blockers) + `loop/20260713-m13-m2-layer2-code/` (issues J1-J5)。

- **M2 Layer2 (ミラー・シム) real 封印実走 validate (2026-07-13、construction・実 qwen3:8b capture spend、
  measurement spend でない = R-budget=0 不変)**: landed 済み Layer2 (mock/replay の continuity gate のみ) を
  **real qwen3:8b で初封印実走**し、self-other context が genuine に prompt へ注入され LLM が応答するかを sealed
  golden で record→replay-verify した。`self_other_enabled` を society_live 収録 harness + `m4_society_live_capture`
  CLI に **additive thread** (既存 Layer2-off path byte-identical、env_pins additive witness は True 時のみ書込・
  False 除去) し、`tests/fixtures/m2_layer2_live_golden/` (N=3 kant/nietzsche/rikyu、think=False、seed=0、
  horizon=12) を bake。**honest outcome (acceptance = 非意味論 boolean のみ)**: (1) self-other 注入 = tick0 全
  framing 不在 / tick 1..11 全 observer framing 有り + observed set == `sorted(all_agents)-{observer}` + 自己行なし
  (**構造完全**)、(2) LLM 応答 36/36 decode + 構造 parse、(3) Windows record→replay byte-parity (inner_invocations=0)、
  (4) **WSL cross-platform byte-parity Win==Linux 実測**。**over-read guard (Codex pre-register HIGH-1 = material)**:
  think=False 縮退 / rendering collapse を acceptance/見送り の gating にしない (covert scorer 禁止) → non-gating
  human memo (「semantic uptake not assessed」)。**rendering collapse 診断** (M4 finding 再確認、artifact
  observation): authored `destination_zone` は 5 zone label を含んだが segment 内 `zone=` は peripatos に collapse
  (memory_centroid) → multi-zone rendering fix は別 scoping で deferred。**claim 境界 = construction (ミラー・シムの
  wiring が real qwen3 で発火し LLM が応答する) であって measurement でない** (semantic effect = 他者観察が行動を
  どれだけ変えたか は measured でない、magnitude 非読取、holding 不可侵・R-budget=0、reasoning-trace door 保全)。
  TASK-POST cross-review = code-reviewer(Opus) Approve/HIGH・MEDIUM なし + Codex(gpt-5.5) 最終 merge 止める HIGH なし
  (Codex MEDIUM = helper pop-on-False + M4 golden no-key test 反映)。**PR #78**。詳細 =
  `.steering/20260713-m13-layer2-mirror-sim-live-run/` (design / decisions / codex-review* / findings) +
  `experiments/20260713-m13-layer2-live/` (run.sh / results) + `loop/20260713-m13-layer2-mirror-sim-live-run/`
  (issues K1-K3)。次工程 = (C) multi-zone rendering fix (deferred scoping) or M3 endurance の別 scoping。

- **aha!/DMN-ECN forward — Phase 1 survey + Phase 2 reasoning-trace door scoping ADR (2026-07-13、doc-only・非 spend・
  measurement 非 authorize)**: M2 Layer2 real validate (PR #78) 後の forward direction。着想 (user) = 「aha! = DMN・ECN
  の黄金比調合を歩行 λ で調整」。既存 substrate (ERRE モード = DMN↔ECN スペクトル `erre/sampling_table.py` + 歩行 λ =
  発散一方向 `erre/locomotion_sampling.py`) の gap = 生成↔評価の二相交替 (調合 switch) が λ に未結線。
  **Phase 1 survey (PR #79 MERGED)**: aha!/insight 神経科学 + 計算論的 insight-scoring/LLM-judge を落合フォーマットで
  6 テーマ 12 論文カード化 ([12]-[24]、`docs/literature/20260713-aha-insight-neuroscience.md`)。**honest verdict =
  壁2 (非循環 scorer 先行解決) は survey 段で未解決 → fork を construction 寄りに制約**。salience switch/DMN-ECN dynamics =
  construction ターゲット / marker・reward・scorer = measurement 領域 (離散化は第2リンク detectability circularity の
  aha 版を再来)。DeepSeek-R1 "aha moment" [23] は observational 命名で形式的 scorer でなく Yang et al. [24] epoch-0 反例。
  **Phase 2 door scoping ADR (PR #80、doc-only、Plan mode + reimagine + Codex)**: (a) `<think>` トレードオフ (決定性 vs
  二相可観測性、両立不能ゆえ別 capture 体制が必然) + (b) 二相捕捉 regime の**設計** (think=True 非決定を existence として
  観察、record→観察のみ・verdict/scorer/floor なし、sealed-golden 無改変、over-read guard 付き。**実装しない**) + (c)
  **construction/measurement fork 判定 = construction-only を推奨・reasoning-trace door は CLOSED 維持** (reimagine v1
  mechanism-first 意図破棄 → v2 door-discipline-first 独立再生成、両案 construction-only 収束、採用 = v2 spine + v1 knob
  スケッチ graft) + (d) **door 3 条件 ledger** (① 本 ADR プロセスとして satisfied・非反射 / door-open 条件としては未消費、
  ② 壁2 UNMET = binding blocker、③ 二相捕捉 enabler DESIGNED・存在確認は Phase 3 pending)。Codex independent review
  (gpt-5.5/xhigh) Verdict = **Adopt-with-changes、HIGH 0 / MEDIUM 3 / LOW 3、事実誤認なし、全 6 件反映済**。**claim 境界 =
  fork の *推奨* であって door を開ける行為ではない** (door-open は将来別 from-scratch spend タスク + **user 裁定**、②解決
  条件付き)。measurement 非 authorize、aha を離散 scorer で測らない、R-budget=0 / holding / measurement-line CLOSE 不変、
  5 機序分離継承。詳細 = `.steering/20260713-aha-phase2-door-scoping/` (design-final / decisions / design-v1/v2/comparison /
  codex-review* verbatim)。次工程 = Phase 3 (think=True LLM 稼働検証、real qwen3 construction spend、verdict なし、
  record→観察のみ) → Phase 4 = **本 ADR 推奨の construction-only** (λ↔二相 knob 建設、Phase 3 存在確認を承けた後)。
  measurement door fork (aha-judge 別文脈 from-scratch) は door 条件② (壁2 非循環 scorer) 解決 + **user 裁定**時のみ到達可能で、
  本 ADR では開けない。

## 9. スコープ / 非スコープ

- **やる**:
  - 身体を外した in-silico での「記憶再編チャネル単独」の発散種生成の測定 (ES 系列)。
  - **situated 3D embodiment substrate の建設と、その出力を structural/behavioral outcome で非循環に測る
    計測基盤 (二層 D0 pack) の先行 valid 化** (substrate scoping FROZEN 2026-07-01)。
  - **construction milestone 第一 deliverable = Embodied Cognition Loop v0 (単一 live agent) の建設** —
    ライブ LLM 認知 (A) と frozen running-substrate (B) の分断を閉じ、LLM 移動決定を連続物理+履歴依存 memory
    幾何の上で実行する統合器官を建てる (construction scoping FROZEN 2026-07-05、measurement でなく建設、
    two-plane determinism で将来の測定可能性を保全、measurement-line 再入は holding)。**技術契約 (HOW) は実装-design
    ADR (FROZEN 2026-07-05) で pre-register 済** = resolution を cognition へ引き上げ既存 live loop を単一ループの
    まま器官化 / policy grammar freeze / 全 LLM call 記録 + Plane 1 完全 pin / continuity gate = exact-oracle
    causal wiring test (measurement 非再入) / handoff schema + Godot dev-only bounded player。**実コード実装
    (I1-I5) は完了 (2026-07-05、feat/ecl-v0)** = 単一 live ループ器官化 + committed handoff golden、measurement
    非再入は ast guard で機械保証、determinism-hardening 候補は superseding ADR に pre-register。
  - **construction milestone-2 = M2 (N体 embodied society) の建設** — ECL v0/v1 の単一 embodied 器官を N 体へ
    composition (Layer1 = 並行 determinism、milestone を定義する GATING) + self-other/mirror functional analog を
    第一 cognitive 次元 (Layer2 = bounded construction attempt、4 規律付き = construction-mode only / functional
    analog 語彙 / 予算ゼロ SimToM prompt / appraisal measurement 非混入)。可視化は既存 live seam の N体 primitive
    拡張、full Blender 可視化は M4 残置、M3 endurance は post-M2 (construction scoping FROZEN 2026-07-11、
    measurement でなく建設、acceptance は causal wiring/boolean のみ、holding 不可侵・R-budget 未消費)。**Layer1
    (N体 determinism) の技術契約 (HOW) は M2 impl-design ADR (FROZEN 2026-07-11、doc-only) で pre-register 済** =
    society.py 逐次 sorted scheduler + §B4 侵入経路 sorted 化 + versioned event/decision log 全体 checksum +
    spend ast-guard、Layer2 (ミラー・シム) は seam 契約のみで内部 HOW は Layer1 land 後の別 ADR、**実コードは別
    タスク (Loop Engineering、Layer1 I1-I6 → Layer2 別 ADR)**。
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
