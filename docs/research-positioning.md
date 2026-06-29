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
- **H4 (ES-4、staged、未走)**: その channel を LLM 生成に当てたとき、**locomotion 駆動の温度
  actuator が qwen3:8b (frozen decoding) の出力を divergent-favoring regime に動かす sufficiency**
  があるか。→ ES-2 の種生成を介さず ES-1/ES-3 channel に直接配線する **actuator calibration**。
  3 重 negative control 下で staged (Phase 0 feasibility/power gate → Phase 1 full) に測る。
  **これは「発散研究」ではなく actuator sufficiency test** であり、GO でも中核命題の再証明でも
  genuine な創造の主張でもない (§7 過大主張ガード)。

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
4. **actuator を校正する (ES-4、staged)**: ES-3 channel を LLM 生成に当て、locomotion 駆動の
   温度 actuator が qwen3:8b 出力を divergent-favoring regime に動かす sufficiency を、3 重
   negative control 下で staged (Phase 0 feasibility/power gate → Phase 1 full) に測る。
   ES-2 種生成チャネルを介さない直接 calibration。
5. **主張 (over-claim guard 付き)**: ES-4 が PASS/GO なら「locomotion→sampling actuator が
   frozen decoding 下で出力を divergent-favoring regime に動かす **sufficiency**」止まり、
   NO_GO/null なら「単一 temperature 軸では発散を担えない honest negative」。**どちらに転んでも
   情報量がある**が、いずれも「歩行が genuine な創造的発散を生む」「中核命題の再証明」は主張しない。

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
- **ES-4 の claim 境界 (actuator sufficiency 止まり)**: ES-4 GO の意味は
  **「locomotion→sampling actuator (open-loop forward channel) が、qwen3:8b local under frozen
  decoding で、出力を divergent-favoring regime に動かす sufficiency」**に厳密限定する。**「歩行が
  genuine な創造的発散を生む」とも「閉ループ創発 (中核命題) の再証明」とも言わない**。locomotion は
  temperature の唯一の channel ゆえ「temperature を超える locomotion 固有の発散」は構造的に
  存在しない (honest)。generic な温度効果と scorer-entropy artifact は 3 重 negative control 下に
  置く (§8)。

## 8. 成功基準 / 反証条件

- **成功とみなす条件 (現最前線 = ES-4)**: ES-3 GO (channel 配線) を達成済 → ES-4 進資格。
  ES-4 は **staged**: Phase 0 (feasibility / power / hard budget gate) が PASS した場合のみ、
  ES-4 ADR で凍結済の N・閾値・課題 battery・scorer で Phase 1 full run に進む。Phase 1 の成功 =
  **3 重 negative control 下で actuator が divergent-favoring effect を生む sufficiency**。
  *(数値定数・battery・estimand 演算・閾値は ES-4 ADR が freeze する。本 SSOT は方向と claim
  境界のみを記し、apparatus を焼かない。)*
- **反証条件 / verdict 語彙 (falsification)**:
  - ES-4 Phase 0/1 の verdict 語彙 = `PASS` / `INCONCLUSIVE_UNDERPOWERED` / `INVALID_SCORER` /
    `INVALID_TASK_BATTERY` / `NO_GO_EFFECT_ABSENT`。**apparatus-invalid を低検出力と混同しない**
    (ES-2 で「metric artifact と真の low-power を峻別」した同型規律)。
  - `NO_GO_EFFECT_ABSENT` = **前進的 finding** (単一 temperature 軸では発散を担えない =
    richer channel re-entry の trigger)。ES-2 が bounded INCONCLUSIVE に留まったのも同様に
    「答えが出ていない」を honest に記録した finding であり、下流の必須前提にはしない。
  - 中核命題 H0 は既に bounded envelope 内で **non-divergence として CLOSE** 済み — 同一空間の
    薄いプロキシ再走は禁止 (継続バイアスガード)。ES-4 は中核命題 (閉ループ δ 増幅) と機構が別
    (単一 forward channel・no feedback amplification) ゆえ再 litigate しない。
  - **two-sided guard**: positive/negative の **両方が finding** であり、片側のみを成功とする
    設計を禁じる。**verdict 未取得の ES-4 を「成功する」と書かない** (forking-paths ガード)。
- **現状の到達点 (2026-06-29)**: ES-1 GO / ES-2 bounded INCONCLUSIVE / ES-3 GO。ES-4 は方向
  決定 ADR が FROZEN され、両 phase full pre-register の ES-4 ADR 起票待ち (未走)。「身体なしの
  記憶再編ルートで発散の十分機構が存在するか」という核心の問いには **まだ答えを出していない**。

## 9. スコープ / 非スコープ

- **やる**:
  - 身体を外した in-silico での「記憶再編チャネル単独」の発散種生成の測定 (ES 系列)。
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
