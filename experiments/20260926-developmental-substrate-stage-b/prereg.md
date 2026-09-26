# 事前登録 — developmental substrate Stage B: 経験から育つ外部 Skill 状態による分化 (符号付き対比)

本文書は Stage B のどのゲートの計算・実走よりも**前に**凍結する。凍結前に Codex (gpt-5.5/xhigh) の independent
review を受け (1 周目 Adopt-with-changes: HIGH 4・MEDIUM 5・LOW 3 / 2 周目 Adopt-with-changes: HIGH 2・MEDIUM 3・LOW 3)、
指摘を反映した (`.steering/20260926-developmental-substrate-scoping/codex-review.md` / `codex-review-2.md`、ローカル。
採否は同 `decisions.md`)。凍結後の変更は本登録の結果と
みなさない。凍結 commit と sha256 は判断 ADR (`.steering/20260926-developmental-substrate-scoping/design-final.md`、
ローカル) に記録する。

本文書は実装・GPU・sealed run を authorize しない。B2 / B3 の実走はそれぞれ user 裁定を要する (§7)。

## 1. 問い

frozen base の LLM に、経験から育つ外部の Skill 状態を持たせたとき、**異なる経験を与えた個体の間に、同じ経験を
与えた複製の散らばりを超える、経験と整合した方向の選択の差**が、発達中に出現しなかった状況 (held-out probe) で
生じるか。

- 位置づけ: M11-C3b (生成自由文の個体化) を同じ問いで測り直すものではなく、**より狭い構成概念の新規 scoping**
  (M11-C3b terminate ADR §2.2 (a) 系の envelope 変更として別 ADR を経由する)。
- 既存の 2 回 (M11-C3b の生成自由文 centroid、条件① の出力側 Gram) は、どちらも符号なし距離を primary にし、
  個体内の揺らぎが個体の変位と同程度で落ちた。符号なし距離は効果 0 でも noise で正になる。本登録はこれを
  **仮説として**扱い (過去の collapse の原因だと断定しない)、estimand を符号付き・個体単位に変える。
- 本登録は「思考が分散したか」「豊かな個体化が起きたか」を問わない (§8 claim 境界)。

## 2. 設計

### 2.1 要素

- **base**: 単一の frozen base (qwen3:8b、think=False) と単一の base persona。
- **経験 stream**: 2 本 (A, B)。環境の結果は**固定の規則表で決まり、LLM・他 agent・judge が決めない**。
  A と B は規則性を鏡像にする (例: A では状況の特徴 f を持つとき行動 a1 が成功、B では同じ f で a2 が成功)。
- **replicate**: 各 stream × 各セルに R 本。replicate 間で変えるのは **LLM の sampling seed だけ** (イベント列・
  順序・停止 step は固定)。条件① で seed の散らばりに学習手続き (データ部分標本・early stopping の step) が
  合算された教訓による。seed の集合は stream 間で対応させる (A の r 番目と B の r 番目は同じ seed)。
- **Skill 状態 (新規機構、B3 前に別の実装 ADR で実装)**: 閉じた primitive action の系列 + 離散特徴の
  preconditions + provenance (episode id) + 成功・失敗回数。自由文 content は採点に使わない。PROCEDURAL memory は
  現状 writer 無し・既定 retrieval 外の空の保存枠であり、流用する場合も新規機構として扱う。
- **snapshot**: 発達終了時に各個体の外部状態を固定し、以後の probe で更新しない。
- **probe bank Q**: 各 probe q は列挙済みの選択肢集合 Ω_q を持ち、出力は enum 強制で parse する。各 q について
  **A 整合選択肢 g_A(q) と B 整合選択肢 g_B(q) (相異なる) を実験前に固定**する。
- **K**: 各 (個体, probe) の sample 数。全セル共通。

### 2.2 非漏洩 contract (Codex HIGH-1)

C が「状態に書かれた答えを読んだだけ」にならないため、次を要求する。

- **held-out の定義**: probe の (precondition signature, Ω_q) の組は、発達中に出現したどの状況の組とも一致しない。
  整合選択肢 g_X(q) は、規則表の特徴 f と probe の特徴の事前固定の関係から決める (probe は f を共有するが、
  signature 全体は新しい)。
- **状態・prompt に入れてはならないもの**: probe id、probe の signature そのもの、probe (id / signature) から
  g_A / g_B への対応表 (probe ごとの answer key)、stream id や「A」「B」の文字列。action label 自体は禁止しない
  (Skill 状態は primitive action 系列を持つので、probe の選択肢と同じ label が現れるのは避けられない)。
  Skill 状態が持てるのは、**発達中に出現した signature に対する** action 系列だけ (Codex 2 周目 LOW-1)。
- **機械検査 (B3 の integrity)**: 全 snapshot について、probe の signature と完全一致する precondition が存在しない
  こと、禁止文字列が状態と probe prompt に出現しないことを検査する。違反 → INVALID_SCORER。
- lever (B2) の人手 Skill も同じ contract に従う (発達中に出現する signature に対する規則として書く)。
- この contract を満たす battery を構成できない場合、claim は「transfer」でなく「外部状態の rule lookup」に弱め、
  その旨を B1 の時点で記録する (結果を見る前)。

### 2.3 stream の同型条件 (Codex HIGH-2)

置換検定は、null の下で A / B が交換可能であることに依存する。これを担保するため、A と B は次を一致させる。

- episode 数・イベント順序の構造・テンプレート・文の長さ。規則表の違いは (f → a1) と (f → a2) の入れ替えだけ。
- action label と Ω_q 内の option 位置はカウンターバランスする (g_A が先頭に来る probe と g_B が先頭に来る probe を
  同数にする)。
- stream id を prompt・状態に出さない (§2.2)。

### 2.4 2×2 のセル

| セル | 経験 | Skill 機構 | 役割 |
|---|---|---|---|
| DI | 異なる (A / B) | on (経験から育つ) | **primary** |
| DC | 異なる (A / B) | off (episodic のみ = 現行機構) | 比較対照 (判定外、§10) |
| CI | 共通 (全個体 A) | on | **陰性対照** + 実現 power の分散源 |
| CC | 共通 (全個体 A) | off | seed null (記述報告) |

## 3. primary estimand

個体 i、所属 stream k(i) ∈ {A, B}、反対側を k̄(i)。個体 i の X 整合率 r_i^X = (i の全 probe × K sample のうち
g_X(q) を選んだ割合)。⊥ (unparseable) は分母に含め、どちらの整合選択肢にも数えない。

- 個体スコア s_i = r_i^{k(i)} − r_i^{k̄(i)}
- C_A = mean_{i∈A} s_i、C_B = mean_{j∈B} s_j
- **C = (C_A + C_B) / 2**

(これは「stream k の個体の k 整合率 − 他 stream の個体の同じ整合率」を両側で平均した量と一致する。) persona 由来の
選択肢への共通の偏りは、両 stream で符号が逆に入るため C で相殺される。null (stream が選択に効かず、§2.3 の同型条件
が成り立つ) では E[C] = 0。C_A と C_B、r^A と r^B の独立性は仮定しない (Codex MEDIUM-2)。判定は joint な統計量 C を
個体単位の置換で評価する。

**検定**: DI の 2R 個体について stream ラベルの全割当 (各 stream R 個体、C(2R, R) 通り、観測割当を含む) を列挙し、
p = #{割当: C_perm ≥ C_obs} / C(2R, R) (片側、観測を分母と分子に含む)。列挙が 10^6 を超える場合のみ m = 10^5 の
無作為置換で p = (b+1)/(m+1)。α = 0.05。R ≥ 4 は最小 p = 1/70 ≈ 0.014 < α のための下限であり、実際の R は B2 の
power 計画で凍結する (§4)。

## 4. 閾値と power (条件① や go-no-go §9 の値は使わない)

- **C_lever (B2 の陽性対照)**: 発達させず、stream 整合の Skill を人手で書いて注入した個体 (A 整合 R_2 本 / B 整合 R_2 本)
  で §3 の C を測った値。「外部 Skill 状態がこの battery の選択を動かせる上限側の目安」。
- **δ_min = C_lever / 2**: 発達個体の C が、0 (null) と C_lever のどちらに近いかの中点。C ≥ δ_min ⇔ 発達個体は
  null より lever 側にある。
- **B2 は one-shot calibration (Codex HIGH-3)**: B2 の実行前に persona / Q / K / R_2 / prompt renderer / scorer /
  seed list / parse rule / 規則表を凍結する。B2 の後に許される操作は「停止」か「δ_min と R の数値凍結」だけで、
  Q・K・persona・renderer・scorer の調整は許さない (調整したければ新しい事前登録)。
- **lever の十分性**: C_lever について §3 検定 p < 0.05 ∧ C_lever の両成分 > 0 ∧ 「R ≤ R_max で power(δ_min) ≥ 0.8
  を達成できる」こと。満たさない = lever が弱すぎて分解能が無い。**R_max の値・根拠・GPU budget は B1 完了後、
  B2 実行許可の前に user 裁定として B2 approval record に凍結し、B2 の結果を見た後は変更しない** (Codex 2 周目 MEDIUM-1)。
- **⊥ の上界 (Codex HIGH-4)**: セル X について b_X = max over 成分 of |stream 間の平均 ⊥ 率の差|。⊥ の stream 間差が
  C の一成分を動かしうる量は b_X 以下。**b_lever < δ_min/2 かつ b_DI < δ_min/2** を要求する。
- **power の模擬 (効果は選択確率の上で植える、Codex 2 周目 HIGH-2)**: 源となる個体集合 P の各個体 i・各 probe q の
  経験分布 p_iq (Ω_q ∪ {⊥} 上、plug-in) を使う。
  1. 対称化: p'_iq(g_A) = p'_iq(g_B) = (p_iq(g_A) + p_iq(g_B)) / 2。他の選択肢と ⊥ はそのまま (効果 0・個体差と ⊥ は保存)。
  2. 1 回の模擬で P から 2R 個体を復元抽出し、無作為に R / R の 2 群に割り当てる。
  3. 効果の注入: 模擬 A 群の各 (i, q) で g_B から g_A へ min(δ_min/2, p'_iq(g_B)) の確率質量を移す。模擬 B 群は逆向き。
     (clamp は効果を小さくする側にだけ働くので power は保守的になる。確率は simplex 内に留まる。)
  4. 各 (i, q) で K sample を多項抽出し、r^A, r^B, ⊥ を再計算して §5-3 の PASS 条件 (ablation を除く、⊥ 上界を含む) を
     全て適用する。10^4 回の通過率を power(δ_min; R) とする。
- **計画 power (B2 で R を決める)**: P = B2 の lever 個体。power ≥ 0.8 を満たす最小の R (≥ 4) を B3 の R として凍結する。
- **実現 power (INCONCLUSIVE の判定用)**: P = B3 の CI セル個体 (Skill on・共通経験、stream ラベルを持たない)。DI の
  結果に依存しない。power は R の選定と INCONCLUSIVE / NO_GO の振り分けにだけ使い、PASS の判定には使わない。

## 5. 判定 rule (verdict は `docs/research-positioning.md` §8 の 5 語のみ、新設しない)

評価順に適用し、最初に当たったものを verdict とする。

1. **INVALID_SCORER**: 次のいずれか。
   - B1 の合成データ検査 (§6) に 1 つでも落ちる。
   - §2.2 の非漏洩 integrity 検査に違反する。
   - CI セル (陰性対照) に事前固定の疑似ラベルを振って §3 の検定をかけ、p < 0.05 (共通経験なのに分離 = 漏れ、
     または昇格が偶然の差を雪だるま式に増幅)。疑似ラベルは `numpy.random.default_rng(20260926)` で replicate 番号の
     順列を 1 回引き、前半を疑似 A・後半を疑似 B とする (Codex MEDIUM-4)。この項の偽警報率は α = 5% で、
     それを受け入れる設計上のコストとして記録する (Codex 2 周目 MEDIUM-2 で維持を確認)。
2. **INVALID_TASK_BATTERY**: 次のいずれか。
   - B-pre (§7) が不成立。
   - B2 で lever の十分性 (§4) を満たさない (人手で規則を注入しても選択が分解能を持って動かない = battery が
     状態の差を表現できない)。
   - b_lever ≥ δ_min/2 または b_DI ≥ δ_min/2 (⊥ の差だけで判定が動きうる)。
3. **PASS**: 次の全て。
   - DI の §3 検定で p < 0.05
   - C ≥ δ_min
   - C_A > 0 かつ C_B > 0
   - **ablation (paired、Codex 1 周目 HIGH-4 / 2 周目 HIGH-1)**: 同じ DI 個体の snapshot から Skill 状態だけを外し
     (episodic は残す)、同じ probe・同じ probe 順序・同じ decoding seed で個体スコア s_i^abl を測る。次の 2 つを
     両方満たす (効果の担体が Skill 状態であって episodic memory ではない)。
     - 点推定: C_abl ≤ C / 2 (C_abl は s^abl から §3 と同じ式で計算)
     - paired 検定: d_i = s_i − s_i^abl の平均 > 0 を、個体単位の符号反転置換 (2^{2R} 通り列挙、片側、観測を含む) で
       p < 0.05
4. **INCONCLUSIVE_UNDERPOWERED**: PASS でなく、実現 power (§4) < 0.8。
5. **NO_GO_EFFECT_ABSENT**: それ以外 (実現 power ≥ 0.8 で PASS 条件のいずれかが不成立)。適用範囲は「この base・
   persona・規則表・battery で、発達した Skill 状態が経験整合の分化を lever の半分以上に運ぶことは観測されない」まで。

ablation だけが落ちて他が成立した場合も NO_GO_EFFECT_ABSENT (Skill 仮説について) とし、「経験依存の分化は
episodic 経由で観測された」を記述報告にだけ書く (これは Skill の効果ではなく、主 verdict と混ぜない)。

## 6. 検査器の Done 条件 (B1、CPU、実モデル不使用)

scorer は実データを見る前に次を全て満たす。

- **陽性対照 (合成)**: 効果 δ を植えた合成個体 (個体分散は B-pre の within-context 分散から作る) で、δ が十分大きい
  とき PASS を返す。
- **陰性対照 (合成)**:
  - (n1) 効果 0 → PASS を返さない。置換の偽陽性率が α に一致する (10^4 回模擬で 0.05 ± 0.01)。
  - (n2) M11-C3b 型 fixture: 個体ごとの変位は大きいが方向が経験と無関係 (無作為) → PASS を返さない。
  - (n3) 片側だけの効果 (C_A > 0, C_B = 0 で平均 C は大きい) → PASS を返さない。
  - (n4) 非漏洩違反を含む snapshot → INVALID_SCORER を返す。
- **変異試験**: 次の mutant を全て kill する (test が落ちる)。
  - (m1) 置換単位を個体から sample に変える
  - (m2) 整合対応 g_A / g_B を反転する
  - (m3) ablation 条項を削除する
  - (m4) C の代わりに |C| で判定する
  - (m5) 両成分の符号条件を削除する / C_A だけで判定する
  - (m6) ⊥ を整合選択に数える、または分母から落とす
  - (m7) δ_min を lever の記録から読まずリテラルで持つ (権威ファイル = lever 記録を変異させて判定が変わること)
  - (m8) CI 陰性対照の行を削除する
  - (m9) δ_min 条項を削除する
  - (m10) ⊥ 上界条項を削除する
  - (m11) power 分岐 (INCONCLUSIVE / NO_GO の振り分け) を削除する
  - (m12) 観測割当を p の分子・分母から落とす
  - (m13) ablation を unpaired (別 seed) にする / ablation の点推定条件か paired 検定のどちらかを削除する
  - (m15) power 模擬の効果注入を s への直接加算に変える (simplex 外の個体が生じることを検出する test で kill)
  - (m14) 非漏洩 integrity 検査を削除する
- 各変異が「落ちた理由」が意図した判定行であることを照合する (no-op 変異・恒真を除く)。

## 7. ゲート順序 (各ゲートの失敗で停止、door-close も正当な Done)

| ゲート | 内容 | 資源 | 停止条件 |
|---|---|---|---|
| **B-pre** | M13 C-proper bank の再解析 | CPU、既存 artifact | 下記 rule 不成立 → INVALID_TASK_BATTERY |
| **B1** | scorer 実装と §6、battery の非漏洩・同型の構成 | CPU | §6 不合格 → INVALID_SCORER |
| **B2** | lever (人手 Skill 注入) の one-shot calibration | 実モデル小規模 (GPU、user 裁定) | §5-2 → INVALID_TASK_BATTERY |
| **B3** | Skill 機構の実装 (別 ADR) と DI / DC / CI / CC の発達 sealed run | 実装 + GPU (user 裁定) | §5 の verdict |

**B-pre rule** (入力 = `experiments/20260710-m13-c-proper/artifacts/bank_annotation.jsonl`、git blob 由来の sha256
`378b5423d5b9d927f884e4381c80dd2116ef9342b6f05a92a07b12cd17bdc6fc` (LF)、8 context × 2 条件 × 300 sample、
列 `pre_bias_destination_zone`)。

- 分布は zone ラベルの経験分布 (plug-in、平滑化なし)。TV(p, q) = ½ Σ_z |p(z) − q(z)|。
- 各 context c・各条件の 300 sample を、固定乱数の balanced split で 150 / 150 に分ける: `numpy.random.default_rng(20260926)`
  で `mc_index` 0..299 の順列を 1 回だけ引き、前半 150 を半分 1、後半を半分 2 とする (全 context・両条件で同じ分割。
  `mc_index` の偶奇が生成順・RNG stride と結び付く artifact を避ける、Codex 2 周目 MEDIUM-3)。
- within(c) = TV(半分 1, 半分 2)
- between(c, c') = TV(c の半分 1, c' の半分 1) (同じ標本数でバイアスを揃える)
- 床 = within の最大値 (8 context)
- 成立 = 28 対の between の中央値 > 床、を 2 条件 (on / off) の両方で満たす

B-pre の claim は「閉集合選択が文脈で動く最低限の CPU proxy」に限る (Codex MEDIUM-3)。bank は Stage B の battery
そのものではなく、context は cue の内容が互いに違うので、成立しても「閉じた選択が文脈の内容に応じて sampling の床を
超えて動く」ことまでで、経験から育つ状態が選択を動かすことの証拠ではない。M11-C3b terminate ADR §2.3 guard 4 の
安価な証拠は **B-pre と B2 の組**で満たす (B2 は小規模 dry-run)。本登録の作成者は凍結前に bank の選択分布を見て
いない (構造 = context 数・sample 数・parse 経路のみ確認。公表済みの within-context エントロピー 0.63〜0.75 bit は既知)。

## 8. claim 境界

- PASS でも言えるのは「この base・persona・規則表・battery で、経験から育った外部 Skill 状態が、発達中に出現しなかった
  閉集合選択を、同じ経験の複製の散らばりを超えて、経験と整合した方向に分化させた」まで。整合方向を実験者が規則表に
  埋め込むので、「環境が教えた規則を外部状態経由で書いて読めた」と区別できない部分が残る。「思考が分散した」
  「個体化した (一般)」とは書かない。§2.2 の contract を満たせなかった場合は「transfer」とも書かない。
- NO_GO / INVALID は「この設定で観測されない / 計測できない」まで。外部状態一般・Skill 一般の否定ではない。
- 条件① (weight-space door CLOSED) の結論は本登録の根拠に使わず、本登録の結果でも更新しない。
- mental model は新層を立てない。副次として予測を測る場合も判定に使わない。
- 論文の本数・分割を本登録から決めない。

## 9. persona 模倣と個体化の区別 (observable)

- persona の共通偏りは C で相殺される (§3)。
- 記述報告: 全個体の平均の移動 (persona / 機構による共通移動) を除いた個体偏差、二重乖離 (A 個体は A 整合選択肢で、
  B 個体は B 整合選択肢で整合率が高い交差)。
- base persona を「developmental prior」と呼ぶ場合、それは base の選択分布 (状態なし) のことで、個体化の証拠に
  数えない (条件① DA-4 の「persona 適応 ≠ 個体化」と同型)。

## 10. 記述報告 (判定に使わない)

- DC セル (判定外、Codex MEDIUM-5): C_DC を報告する。**C_DC ≥ C_DI / 2 のときは、PASS の claim に「経験のみ
  (episodic) でも Skill 機構ありの半分以上の分化が出た」を併記し、Skill 機構固有の寄与を強く書かない**。
  副次 H2 = C_DI − C_DC (セルラベル置換、片側) も報告する。
- 入れ子の雑音: probe 内 split-half TV、replicate 間 TV、stream 間 TV (符号なし、大きさの記述のみ)。
- 各セルの ⊥ 率、Skill 状態の数・昇格・retire の統計、CC セルの C。
