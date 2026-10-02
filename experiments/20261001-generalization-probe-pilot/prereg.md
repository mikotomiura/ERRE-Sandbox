# 事前登録 — 候補 G (汎化 probe): 環境が与えた観察だけが違う同一 base のエージェントは、状態に答えの無い状況で、世界の潜在構造の向きに違う選択をするか

- status: **PILOT-FROZEN** (2026-10-02、user 裁定 DU-4。第 1 段の封印。確認実験の FROZEN ではない)
- 日付: 2026-10-01 (起草)・2026-10-02 (Codex review 1〜4 回目の反映、第 1 段の凍結)
- 凍結は 2 段 (§9、Codex HIGH-3):
  - 第 1 段 `PILOT-FROZEN`: pilot の計画・機械判定・本走の設計を封印する。計測台 ADR §5 が gate の適用外とする「判定に使わない較正 pilot」の
    事前登録に当たる。条件 = 見取り図が door-close でない (§7)・変異試験が全 KILLED (§10)・user の ratify。
  - 第 2 段 `FROZEN` (確認実験): pilot の GO・driver の certification・証拠の結び付きが揃い、計測台 ADR §5 の gate 6 点が揃ってから。
    第 2 段は第 1 段の封印 (`manifest.json`) を照合し、prereg は status 行だけが変わったことを要求する (Codex 2 回目 HIGH-2)。
  - DRAFT・PILOT-FROZEN の間、本走の `run.sh main` は manifest の照合で止まる。
- 本文書は GPU・実モデル呼び出し・driver・null pilot の実行・本走を authorize しない。pilot の実行 (§8) は第 1 段の後に、本走 (§9) は第 2 段の後に、
  それぞれ別の user 裁定を要する。
- 設計の正本:
  - (A) 統合系 scoping ADR (`.steering/20261001-integrated-divergence-scoping/design-final.md`、FROZEN) §1・§3.5・§5・§6・§7・§8・§9
  - 計測台 ADR (`.steering/20261001-measurement-bench-scoping/design-final.md`、FROZEN) §2.1.1・§4.1・§4.3・§4.4・§5・§6
  - 本登録の設計の経緯 (/reimagine の 2 案と採否・Codex review の verbatim と採否): `.steering/20261001-generalization-probe-prereg/` (ローカル)
- 凍結物は変えない: v2〜v5・(b) の manifest の対象、旧 Stage B、`src/erre_sandbox/evidence/`。本登録のコードは旧 Stage B の scorer
  (verdict の 5 語と α) を import するだけである。v2 の scorer・battery は import しない (推定量の式と判定の構造を、新しい battery の上に実装し直した)。

---

## 0. 閉じた chain との関係の登録 (gate 0)

判定基準 (計測台 §1.1 を継ぐ): 本登録が、閉じた chain の問い・推定量・データの生成 channel・較正の対象・判定基準のどれかを、閉じた文脈で
再び動かすか。関係は token でなく実質で書き、争いがあれば「当たる」側に倒す。

| # | 閉じた chain / door | 本登録で触れうるもの | 扱い |
|---|---|---|---|
| 1 | M13 の計測ライン (2 family SPENT・CLOSE) | 統合系の substrate | **使わない** (統合系 ADR DU-1)。ECL・society・3D・SPDM の検索・live の λ・zone の隣接を、推定量の入力を生む過程に入れない。第 3 family を立てず、R-budget を消費も付与もしない |
| 2 | 閉集合 battery のリンク (ii) (2026-10-01 打ち止め) | エージェント自身の探索 | 問わない。経験は環境が観察として与え (開ループ)、エージェントは dev で行動しない。battery も新しい (6 語彙・4 世界の battery ではない) |
| 3 | (b) 歩行 → decode (door-close) | 歩行の decode | 使わない。decode は v2 と同じ着座 (T 0.7・top_p 0.8) |
| 4 | v5 B・C (door-close) | 表示の変化 | 使わない |
| 5 | v4 (`NO_GO_EFFECT_ABSENT`) | 既知の挙動の値 | 判定に使わない |
| 6 | v3 (`INCONCLUSIVE_UNDERPOWERED`、抽出の問い) | 経験の行を読む | **重なりを登録する**: 「経験の行を読む」点で v3 と重なる。違い: 状態は成功行だけ (失敗行・成否の集計を置かない) で、v3 の抽出 (成否の欄から規則を取り出す) を問わない。問うのは、状態に無い key への汎化である。v3 の verdict を再評価しない |
| 7 | v2 (PASS、claim の上限 = rule lookup) | 推定量・判定の構造・族の構造・行の文面 | 継ぐ (式と構造を新しい battery で実装し直す)。**v2 の claim を広げない**。本登録の PASS が lookup の再現でないことは、probe の key が状態に無いこと (機械検査)・key を見ない方策の C が厳密に 0 であること (§6 の定理)・登録した字面の写し方の fixture (§6) の範囲で区別する |
| 8 | CLD (H0) の停止規則 | 曝露の順・seed | 継承。同じ世界で seed・摂動・初期 prompt だけが違う状態を、分散の源にも指標にもしない。差の源は世界の規則 (族の回転) だけ。時間傾きを指標にしない |
| 9 | Stage B (B-pre で停止) | 経験から育つ状態 | 使わない (状態は決定的な aggregator が観察から作る) |
| 10 | weight-space door (CLOSED) | — | 使わない |
| 11 | reasoning-trace・ES-4・D0・aha | 「思考」の語 | 閉集合の選択だけを使う。自由文・trace・J-space を使わない。「思考の分散」を自由文の意味で言わない |
| 12 | M2 appraisal・ミラー・シム | 他者の観察 | 使わない |
| 13 | 自由文 scorer の資格試験 (door-close) | — | 触れない |
| 14 | 計測台 ADR (FROZEN) | gate 6 点 | 本登録は計測台の gate を適用する最初の事前登録。gate を変えない (§13 の対応表) |
| 15 | 統合系 scoping ADR (FROZEN) | 候補 G の定義・bridge・claim | §5〜§8 を具体化する。統合系ではない (§11) |

## 1. 問い・位置づけ・claim の上限

**問い**: 1 つの凍結 qwen3:8b (think=False) の上で、同じ base・空の初期状態のエージェントに、環境が与えた観察の成功行だけを状態として見せる。
観察は、世界の規則 (生き物の分類 → 成功する行動) だけが族の中で違う。このとき、状態に一度も現れない生き物 (probe の key) の状況で、
選択が**その世界の潜在構造 (分類) の向きに**、τ を超えて違うか。

- 位置づけ: 統合系 ADR §3.5 の設計方針 (probe の答えが状態に書かれていない) の具体化。現行目標 (2026-09-27「同一 base から、ペルソナごとの
  思考の分散」) を、閉集合 C で、lookup の外挿でない形で問う。統合系ではない (3D・H1・H3 の寄与は問えない)。
- 推定量 C は、族内の選択分布 TV に対する、向きの付いた下界 (v2 と同じ)。
- 汎化の直接の事前情報は無い (統合系 ADR §7 の読み 5)。INCONCLUSIVE に終わる公算もある。それは規則による door-close の条件ではない (研究者判断として起こした)。
- claim の上限と license は §11。

## 2. 設計 (実装 = `scripts/generalization_probe_battery.py`)

### 2.1 世界と潜在構造

- 状況 = 生き物 (key) × 場所 {library, workshop} × 同伴 {solo, pair}。場所と同伴は distractor (規則に関わらない)。
- **潜在 = 生き物の分類** {bird, fish, insect}。分類名は本走の prompt に一度も出さない (機械検査)。
- arm の規則 = 分類 → 行動。正準の対応 A: bird → sort_cards、fish → fold_linen、insect → stack_cups。
  - A_rot = A ∘ next (bird → fish → insect → bird)。B = σ ∘ A、B_rot = σ ∘ A_rot。σ = (sort_cards wind_clock)(fold_linen count_keys)(stack_cups tidy_shelf)。
  - 族 = {A, A_rot}・{B, B_rot}。族内の回転が、base の事前の連想 (分類と行動の結び付き) を相殺する。
- **潜在構造を選んだ根拠** (統合系 ADR §9 リスク 2・3、実データの前に固定):
  - 分類の所属が曖昧でない (構成概念の妥当性)。初回案の天候の寒暖 (二値) は、drought・sultry など所属が曖昧な語が混じるので退けた (decisions DM-1)。
  - よく知られた動物名の pool が広く、字面の重なりを避けやすい。
  - 3 クラスの巡回は v2 の 3 周の回転と同型で、v2 の推定量・成分の構造をそのまま継げる。
  - 潜在は 1 つだけ置く (どれで判定するかの自由度を作らない)。汎化されやすさを見て選んでいない (モデルの出力を見ていない)。
- 行動 label 6 語 (新語彙): sort_cards・fold_linen・stack_cups・wind_clock・count_keys・tidy_shelf。分類に中立な動作を選んだ。
  互いに文字 4-gram を共有しない。

### 2.2 dev の状況と probe

- **dev の状況 12** = 場所 × 同伴の 4 組 × 3 分類。各 (組, 分類) にちょうど 1 つの dev key:
  bird {sparrow, heron, pigeon, magpie}・fish {trout, carp, herring, sardine}・insect {beetle, hornet, locust, mosquito} (各 key 1 行)。
  - どの probe から見ても、distractor の一致の型 (2 つとも / 場所だけ / 同伴だけ / 無し) ごとに、各分類の行がちょうど 1 つある。
- **probe 24** = 8 つ組 × 3 分類。つ組 j は組 j mod 4 を共有し、分類ごとに 1 つの probe key を持つ:
  - bird {falcon, ostrich, hawk, stork, canary, penguin, eagle, robin}
  - fish {halibut, salmon, guppy, marlin, tuna, barracuda, anchovy, minnow}
  - insect {mantis, cicada, flea, weevil, midge, earwig, wasp, aphid}
  - probe の key は dev にも状態にも現れない。dev key は probe 文に現れない (機械検査)。
  - probe の key は、dev key・label・distractor のどれとも文字 4-gram を共有せず、部分文字列の関係にない (機械検査)。
- **probe key を選んだ手順** (`scripts/generalization_probe_key_selection.py`、出力 `results/key_selection.json`、モデル不使用):
  1. pool = 各分類の、よく知られた動物名で、4 文字以上・分類を示す語素 (fly・bug・bee・fish・bird) を含まない・上の 4-gram 条件を満たし・
     一般的な意味が動物以外に強く寄らない語 (pike・mullet・snapper を外した。外した語と理由は出力の `excluded`)。
  2. 目的関数 = R ∈ {6, 12, 18} と、key の字面を使う登録方策 66 種 (§6) での max |C|。**選定用の行順** (本走と別の seed 20261002) の上で計算し、
     本走の行順は選定に使わない (Codex HIGH-4)。
  3. seed 20261001 の乱択初期値 × 200 回、各回で交換の山登り。最良は max |C| = 0.0208。
  - 見たのは字面の方策の C だけで、モデルの出力・汎化のしやすさは見ていない。選定は再実行で同じ割り当てを返す (test と manifest が照合)。
  - 本走の行順の上の fixture gate (§6) は、選定の後の確認である。落ちたら door-close とし、選び直さない。
  - 限界: 選んだ語に、モデルが分類を知らない語が混じりうる (midge・aphid・earwig など)。§8 の知識確認で止める (語を差し替えない)。

### 2.3 族・arm・Ω (Codex HIGH-1 で改めた)

| arm | 規則 (分類 c → 行動) | 役割 |
|---|---|---|
| A | A(c) | 判定 |
| A_rot | A(next c) | 判定 (A の foil) |
| B | σA(c) | 判定 |
| B_rot | σA(next c) | 判定 (B の foil) |

- **Ω = 族の 3 label** (族 A は {sort_cards, fold_linen, stack_cups}、族 B は σ 像)。**分類に依らない**。
  表示順は族の正準順を (r + j) mod 3 だけ巡回し、つ組の 3 probe と族内の 2 arm で共有する。
  - 旧案 (Ω = 4 arm の指す選択肢) では Ω が probe の分類で違い、key を見ずに分類が分かった。Codex はその経路で C = 1 になる方策を示した (HIGH-1)。
- **つ組の 3 probe の prompt は probe key だけが違う** (状態・行順・distractor・Ω・表示順が同じ。機械検査 `check_triple_prompts_differ_only_in_key`)。
- 族内の 2 状態は、同じ dev の状況を同じ順で並べ、label の頻度ベクトルが一致し (各 label 4 行)、分類との対応だけが違う (機械検査)。
  統合系 ADR §5.1 の (x, x, y) の反例 (置換で (y, y, x) になり頻度が変わる) を test で pin した。
- C0 (状態なし) は置かない。Ω が族ごとになり、v2 の C0 の役割 (⊥ gate) は lever 腕・masked 腕の ⊥ gate と pilot の知識確認が担う (decisions DC-13)。

### 2.4 曝露と aggregator (状態の生成)

- 環境は、族で共通の固定の試行 schedule を与える: dev の状況ごとに、族の 3 行動を各 3 回試す。成否は arm の世界の規則で決まる
  (行動 = 規則の行動なら成功)。エージェントは dev で行動しない (開ループ、エージェント自身の探索を問わない)。
- 決定的な aggregator が、(状況, 行動) ごとに成否を数え、失敗の無い成功だけを固定の文言の行に記録する。研究者は規則を書かない。
  - 行の文面は v2 の lever 行と同じ形: 「条件: <key> / <場所> / <同伴> → 行動: <label> (成功 3 / 失敗 0)」。
  - **成功行だけにした理由**: v3 の抽出の問い (成否の欄から規則を取り出す、U2) と分けるため。未知を「状態に無い key への汎化」の 1 段に絞る (§0 #6)。
- 状態は 12 行。aggregator の出力が世界の規則と一致し、各 dev の状況にちょうど 1 行あることを機械検査する。

### 2.5 単位・layout・seed (依存の単位、gate 2)

- **単位** u = (族 f, つ組 j, replicate r)。本走の単位は 2 × 8 × R 個。本走の R = 18 (§7 の選定規則)。
- 単位ごとに状態の行順 π_u = `default_rng([20261001, f, j, r]).permutation(12)`。族内の 2 arm とつ組の 3 probe で共有する。
- 選択肢の表示順は §2.3。R が 3 の倍数なら、各 (族, つ組) で各 label が各表示位置に R/3 回来る (機械検査)。
- **decoding seed** = 20261001 + 1,000,000·g + 10,000·r + 100·(つ組番号 j) + k。g は名前空間 (本走の族 0 / 族 1 = 0 / 1、pilot の masked 族 0 / 1 = 3 / 4、
  知識確認 = 6、知識確認の欄は key 番号)。**族内の 2 arm とつ組の 3 probe で共有し (共通乱数)、単位の間では共有しない**。
  本走と pilot の seed は交わらない (機械検査)。seed の欄を probe 番号でなくつ組番号にしたのは、probe 番号が分類を運び、seed を読む方策が
  key を見ずに分類を知りうるため (Codex 2 回目 HIGH-1)。
- K = 1 (セルごとに 1 回)。理由: v2 の実走記録 (出所 = v2 `results/run/samples.jsonl`、用途 = 雑音構造の目安、v2 の verdict は再評価しない) で、
  セル内 K = 10 回の最頻の割合が 0.992 (97% のセルで 10 回とも同じ応答) だった。K を増やしても情報はほとんど増えず、独立な単位を増やす方が
  τ 判定の天井 (§5.3) を下げる。

### 2.6 prompt (凍結 renderer)

- system: 「あなたは与えられた状況で、示された行動の中から 1 つを選ぶ。」(v2 と同じ、persona なし)
- user: 「これまでの経験の記録:」+ 12 行 (π_u の順) + 空行 + probe 部。
- probe 部: 「状況: 生き物=<key>、場所=<場所>、同伴=<同伴>。\n次の行動から 1 つだけ選び、行動名だけを答えよ: <Ω を表示順に「、」区切り>」
- 非漏洩 (機械検査): 本走の prompt に分類名・arm 名・probe id を入れない。
- byte 予算: 描画 prompt の最大は約 1.2 KB。上限 3,000 + template 64 + num_predict 32 ≤ num_ctx 4,096 (token 数 ≤ UTF-8 byte 数) で、
  切り詰めが起こりえないことを静的に保証する (r < 24・masked を含む全 prompt で検査)。

### 2.7 battery の機械検査 (`battery_violations`、判定の前に必ず通す)

label 頻度ベクトルの族内一致 (各 4) / aggregator の出力と世界の規則 / 曝露 schedule の族内一致 / dev の (組, 分類) の 1 対 1 /
つ組の distractor の共有と組の均等な使用 / 4 arm の指す選択肢の相異と族の Ω への所属 / **つ組の prompt が probe key 以外で一致** /
probe key の非出現 / 字面の 4-gram / 非漏洩 / 表示位置の均衡 / 族内の prompt が label 以外で一致 / byte 予算 /
masked の状態 (§8) が key を含まず key の欄以外は本走と同じ / 選定用の行順が本走と別 / 知識確認の正答位置の均衡 / seed の名前空間の分離。

## 3. estimand (v2 と同じ式、単位だけ新しい)

- 単位の成分 s_{a,u} = (w_a を選んだ数 − foil_a を選んだ数) / (3K)。つ組の 3 probe × K。
  - w_a = arm a の規則が probe で指す選択肢。foil_a = 族内の相手 arm が指す選択肢。
  - ⊥・OOΩ (語彙内だが Ω 外)・Ω の残り 1 つは、分母に含め、w にも foil にも数えない。
- 単位 d_u = (s_{a,u} + s_{a',u}) / 2 (族 f = {a, a'})。族内で arm ラベルを入れ替えると d の符号が反転する。
- **C = mean_u d_u**。完全な汎化 = 1 (⊥ 率 b なら 1 − b)。probe key に依らない選択 = 0 (§6 の定理)。成分 = arm ごとの s の平均 (4 つ)。

## 4. 実行条件・parse・記録 (凍結。driver は本登録の範囲外で、仕様だけ登録する)

- model `qwen3:8b`、think=False、temperature 0.7、top_p 0.8、repeat_penalty 1.0、num_ctx 4096、num_predict 32、options.seed を明示 (v2 と同じ着座)。
- **meta.json** = `{"request": request_meta(), "observed": {"model_digest", "ollama_version", "template_sha256"}}` (Codex MEDIUM-11)。
  - request が凍結値と違えば INVALID_SCORER。observed は driver が実行環境から読む値 (モデル実体・版・chat template の同定)。
  - 本走の observed が pilot の observed と違えば INVALID_SCORER (pilot の機械判定の出力が observed を記録する)。
- **記録の schema** (1 行 1 JSON object、欄は過不足なく): `call_index` / `replicate` / `k` / `seed` (int、bool を int に読み替えない)、
  `arm` / `probe_id` / `prompt_sha256` (str)、`raw` / `parsed` (str または null)。違反は例外で止めず INVALID_SCORER。
- 呼び出し順 (driver への要件、判定は call_index の一意性だけを検査する): 単位の順に、族内の 2 arm を交互に。
- **parse** (`parse_choice`、v2 と同じ規則を新語彙で、test で pin): NFKC → 小文字化 → 閉じた think ブロックを除去 (閉じない tag が残れば ⊥) →
  6 label のちょうど 1 種を単語境界で含めばその label (`sort cards`・`sort-cards` も同じ label)。0 種・2 種以上は ⊥。
  transport 失敗 (同じ seed で 3 回まで再送して解けないもの) は `raw = null` を記録し、run 全体を `status=not_computed` にする (⊥ にしない)。

## 5. 判定 rule (verdict は `docs/research-positioning.md` §8 の 5 語のみ。実装 = `scripts/generalization_probe_scorer.py`)

評価順に適用し、最初に当たったものを verdict とする。**τ = 0.30**・**α = 0.05** (v2 の literal を継ぐ)。

1. **INVALID_SCORER** — certification (`results/certification.json`) が無い・全 KILLED でない・記録 sha256 が現在のコードと一致しない /
   battery の機械検査 (§2.7) の違反 / fixture gate (§6) の違反 / meta の違反 (§4) / 記録の schema・構造の違反 (重複・grid 外・seed・prompt・parse・call_index)。
2. **計算しない** (`status=not_computed`、verdict なし) — transport 失敗の記録がある、または行が欠ける。
3. **INVALID_TASK_BATTERY** — lever 4 arm のいずれかの ⊥ 率 > min(0.2, pilot の masked の最大 ⊥ 率 + 0.05) (envelope、§8.3)、
   または族内の ⊥ 率差 ≥ τ/4。
4. **PASS** — E⁺ ≥ 1/α **かつ** 4 成分がすべて > 0。
5. **NO_GO_EFFECT_ABSENT** — E⁻ ≥ 1/α。
6. **INCONCLUSIVE_UNDERPOWERED** — それ以外。

### 5.1 τ 判定 (統合系 ADR §6 gate 2 の (a)、BL-3)

- E⁺ = mean_{λ∈Λ⁺} Π_u (1 + λ(d_u − τ))、Λ⁺ = {j/4 · 1/(1+τ) : j = 1..4}。
- E⁻ = mean_{μ∈Λ⁻} Π_u (1 + μ(τ − d_u))、Λ⁻ = {j/4 · 1/(1−τ) : j = 1..4}。
- E⁰ = 平均 > 0 の同型の e-value (記述報告だけ)。v2 の符号反転の p は使わない (単位が 16 を超え、全列挙できず、対称性に依る)。
- 判定式を v2 から変えたが、v2〜v5 の判定は再評価しない。

### 5.2 有効性 (gate 2 の前提の監査。計測台 §2.1.1 の 4 項目)

- **推論の対象** (Codex HIGH-4): 主な推論は、**固定した prompt の schedule 全体** (項目・行順・表示順・seed) に条件付けた、decoding の抽出についての
  推論である。帰無は「単位平均の平均 (1/n) Σ_u μ_u ≤ τ」、μ_u = その単位の prompt での E[d_u] (期待値は decoding について)。
  - 新しい layout・新しい項目への一般化は、この推論から言わない (§11)。probe key の選定は本走と別の行順で行ったので (§2.2)、
    本走の行順は選定の事象に条件付いていない。
- **定理**: 単位の d が独立で [−1, 1] に有界なら、帰無の下で固定の λ について E[Π_u(1 + λ(d_u − τ))] = Π_u(1 + λ(μ_u − τ)) ≤ (1 + λ(μ̄ − τ))^n ≤ 1
  (各因子は λ ≤ 1/(1+τ) で非負。AM-GM)。混合も同じ。Markov で P(E⁺ ≥ 1/α) ≤ α。NO_GO 枝も同じ (μ ≤ 1/(1−τ))。
  2 枝は同時に立たない (log の凹性で、d̄ ≤ τ なら E⁺ ≤ 1、d̄ ≥ τ なら E⁻ ≤ 1。test で pin)。対称性・同分布・交換可能性を仮定しない。
  保証は枝ごとの α である。4 成分の条件・⊥ gate との積集合は PASS の size を増やさない (Codex が確認)。
- **依存の単位**: 単位 = (族, つ組, r)。単位の間で seed を共有せず、状態の行順は単位ごとに引く。単位の中で 2 arm × 3 probe が layout を共有し、
  2 arm が seed を共有する。単位の間の独立は、別の seed の呼び出しが独立な抽出であるという理想化 (v2〜v5 と同じ) に依る。
- **相殺の条件** (機械検査): 族内の label 頻度ベクトルの一致・曝露 schedule の一致・族内の prompt が label 以外で一致・つ組の prompt が key 以外で一致・
  表示位置の均衡・seed の共有と分離。
- **鋭い null** (state を読まない) では、族内の 2 arm の prompt の違いが label だけで、seed を共有するので、選択が一致して d_u = 0。
  さらに §6 の定理により、probe key を見ない方策 (prompt の key 以外と seed の関数) は、どの単位でも d_u = 0。
  どちらも帰無の 1 点で、上の定理はそれより広い帰無の領域を覆う。

### 5.3 判定の天井 (雑音ゼロでも要る大きさ)

有界の平均の検定は、帰無 {m を確率 p、−1 を確率 1 − p} を排除できないので、全単位が m でも m ≥ (1+τ)·α^(−1/n) − 1 が要る
(n = 96: 0.34、n = 192: 0.32、n = 288: 0.31)。本登録が単位を細かく取り K = 1 にしたのは、この天井を下げるためである。

## 6. fixture 表 (登録した写し方、L4。実装 = `scripts/generalization_probe_fixtures.py`、出力 `results/fixture_table.json`)

- モデルが登録した方策に完全に従ったときの C を、凍結した設計 (全単位・本走の行順・表示順) の上で厳密に計算する。
- **gate** (統合系 ADR §5.2、v4 ADR §3.1 の型): 登録 fixture 全体の最大 |C| < τ/4 = 0.075。判定の INVALID_SCORER にも組み込む。
- **定理 (key を見ない方策)**: つ組の 3 probe は、prompt が probe key だけ違い (§2.3)、decoding seed が同じである (§2.5)。
  よって、prompt の key 以外と seed の関数である方策の出力は、つ組で同じ label L になる。arm a について L は 3 分類のうちちょうど 1 つで w、
  1 つで foil、1 つで other なので、つ組の寄与の和は 0。**どの単位でも d = 0** である。
  - 決定的な decode (同じ prompt・seed で同じ出力) のモデルは、key を見ないならこの方策に入る。decode に非決定性が残る分は、key に依らない
    揺らぎとして期待値 0 と書く (理想化)。
  - Ω や表示順から分類を推す「設計を知った」方策 (Codex 1 回目の Ω→既存行の lookup を含む) と、seed から分類番号を読む方策
    (Codex 2 回目の反例。seed がつ組で同じなので分類を運ばない) もこれに入る。test で pin した。
  - gate は、登録した key を見ない方策が表で厳密に 0 であることも要求する (0 でなければ実装の誤り)。
- 登録した方策 120 種 (同点処理 {表示順で最初, 最後} × fallback {表示の先頭, 末尾, ⊥} の変種を含む):
  - **key を見ない方策**: distractor の一致による最近傍の 1 行 (一致の重みを等しく / 場所を重く / 同伴を重く)・一致の上位 3 / 5 行の投票・
    完全一致の行の投票・状態で最多の label・最初 / 最後の行・行数 mod 3 の表示位置・空状態 (表示の先頭)・label × 位置 (2 種)・
    Ω に無い label からの lookup (Codex の反例)・表示の先頭からの lookup。
  - **key の字面を使う方策**: 最近傍の dev key (編集距離・連続する最長共通部分文字列・最長共通部分列・文字 2-gram / 3-gram の Jaccard・長さ・頭文字・
    末尾の文字・辞書順の隣)、編集距離と 2-gram の上位 3 の投票 (Codex LOW-12 で部分文字列と部分列を分けた)。
- 結果 (本走の行順、R ∈ {6, 12, 18}): 最大 |C| = 0.0469・0.0391・0.0417。gate を通る。key を見ない方策は全 R で厳密に 0。
  - 陽性対照 (gate の対象外): 分類を読む方策 C = +1、次の分類の行を写す方策 (逆向きの一形) C = −1/2。
- 限界: 登録した 120 方策を超える保証は無い。方策を probe ごとに使い分ける (条件付きの写し) と相殺するとは限らない。
  claim は「登録した写し方では説明できない」までである (§11)。

## 7. 見取り図 (gate 4、判定に使わない。実装 = `scripts/generalization_probe_sim.py`、出力 `results/sketch.json`)

### 7.1 模型・形・規則 (実データ前に固定)

- **生成の模型**: セル = (単位, つ組の probe, arm)、K = 1。⊥ は確率 b。残りの質量で、確率 |λ| で w (λ > 0) か foil (λ < 0) を選び、それ以外は
  base (Ω の 3 label と OOΩ 5%) から引く。混合の形では E[C] = (1 − b) · E[λ]。対数オッズの形だけは base (label_skew) の w の対数オッズに β を足す。
- **族内の 2 arm の乱数の結合** (Codex MEDIUM-10 で「両端」を「代表的な 3 結合」に改めた): `crn` = 共通の一様乱数 (同じ seed の写し。
  族内の 2 arm とつ組の 3 probe で共有、Codex 2 回目 HIGH-1)、`indep` = 独立、`anti` = 逆向き (u と 1 − u、⊥ も逆向き)。
  結合の全ての場合を覆うとは言わない。
- **形** (統合系 ADR §5.2 の 6 形を、本登録の単位で書いたもの):
  1 一様の混合 (sd 0.05 = 最も有利、sd 0.3) / 2 集中 (分類の 1/3・2/3 にだけ出る) /
  3 全か無か (セル・単位・arm × 単位・項目。項目 = (族, つ組, probe) で r を通じて固定) / 4 事前偏り × 対数オッズ /
  5 弱い null (単位で 0.4 が 5/7・−1 が 2/7) / 6 逆向きの汎化 (項目の 1/6 が λ = −1、残りで平均を合わせる)。
  - 本設計では r が単位の間で共有する乱数を持たない (行順・seed は単位ごと) ので、ADR の「arm × replicate の全か無か」は arm × 単位の全か無かとして置く。
  - 帰無の領域: 境界 E[C] = τ の全形 (両枝) と、二点の極値 (PASS 枝 {m, −1}、NO_GO 枝 {m, +1}、平均 = τ)。
  - 項目単位の形は、項目の数を厳密にして実現平均を目標に一致させる (帰無は固定した schedule に条件付ける、§5.2・decisions DD-2)。
- **攪乱点 18** = base {uniform, label_skew, position_skew} × ⊥ {0, 0.1} × 結合 {crn, indep, anti}。対数オッズの形は base = label_skew の 6 点。
- **size の上限と MC の採否を別の数にする** (計測台 §4.3。計測台の実装 ADR が無いので本登録で定めた。Codex MEDIUM-9):
  上限 = α (§5.2 の定理による真の size の上限)。MC の採否: 棄却の数 X について、合格は X ≤ x、棄却は X ≥ x + 1。x は
  P(X > x) ≤ 0.01 / G を満たす最小の整数 (X ~ Binomial(N, α)、N = 10⁴、G = その R の size の点の数 × seed 数。Codex 2 回目 LOW-6)。
  誤棄却 (真の size が α の候補を MC の揺らぎで落とす) の族全体の率を 0.01 以下に抑える。誤採用は定理が防ぐ。
- **R の選定規則** (user 裁定 DU-1 と Codex HIGH-1 の帰結。下の「逸脱の記録」): 本走の R は候補 {6, 12, 18} の最大 R_MAIN = 18。
  R_MAIN が次の 3 条件をすべて満たせば選び、満たさなければ door-close (凍結しない)。他の R は境目と size の報告のためだけに計算する。
  1. 18 攪乱点で、一様 sd 0.05 / sd 0.3 の P(PASS | E[C] = 2τ) ≥ 0.8、対数オッズの形 (6 点) でも ≥ 0.8。
  2. 18 攪乱点で、一様 sd 0.05 / sd 0.3 の P(NO_GO | E[C] = 0) ≥ 0.8。
  3. 全形の境界と帰無の領域で、両枝の棄却の数が合格 (X ≤ x)。
  最も有利な行 (一様 sd 0.05・uniform・⊥ 0・crn) が、どの R でも E[C] = 2τ の点で power 0.8 に届かなければ door-close。
- **逸脱の記録** (実データ前):
  - 当初の規則は「候補 {4, 8, 12, 16} を小さい順に見て 3 条件を満たす最初の R」だった。初回の見取り図では 4 候補とも 3 条件を満たし、R = 4 になった。
    v2 の実走 (1,200 呼び出しで約 3.3 分) から、本走の呼び出しは数分で済み、「最小の R」の経済性の理由が失われていた。
    見取り図を見た後の変更なので、user 裁定 DU-1 (2026-10-02) を得て「候補の最大」に改めた。通すための変更ではない (4 候補とも通っていた)。
  - Codex HIGH-1 の反映で Ω を族の 3 label にし、表示位置の均衡のため R を 3 の倍数にした。候補を {6, 12, 18}、R_MAIN を 18 にした
    (DU-1 の趣旨 = 候補の最大・費用は無視できる、を継ぐ)。
  - どの変更でも、モデルの出力は 1 件も見ていない。

### 7.2 結果 (JSON から機械生成、`scripts/generalization_probe_render_sketch.py`)

<!-- SKETCH:BEGIN -->

**条件** (`results/sketch.json`、2 回の独立な実行で byte 一致):
- 判定式は凍結する scorer (`e_values`・`decide`・⊥ gate) をそのまま使った。R の候補 [6, 12, 18]、K = 1、τ = 0.3・α = 0.05・植える効果 2τ = 0.6。
- 回数: power の点は 2,000 回、size の点は 10,000 回、各 2 seed ([20261001, 20261002])。power は 2 seed の平均、size は大きい方。
- 攪乱点 18 = base {uniform, label_skew, position_skew} × ⊥ {0, 0.1} × 結合 {crn, indep, anti}。対数オッズの形は base = label_skew の 6 点。
- **size の上限 = α (定理、§5.2)** と **MC の採否** を別の数にした。棄却の数 X について合格は X ≤ x、棄却は X ≥ x + 1。x は P(X > x) ≤ 0.01/G を満たす最小の整数 (X ~ Binomial(N, α)、G = その R の size の点の数 × seed 数)。表の閾値 (率) は x / N。

**表 1**: R ごとの選定規則の 3 条件 (§7 の docstring と `select`)。

| R | 単位 | 呼び出し | P(PASS \| 2τ) ≥ 0.8 | P(NO_GO \| 0) ≥ 0.8 | size ≤ 閾値 | 最悪の size | size の点 G | 閾値 (率) |
|---|---|---|---|---|---|---|---|---|
| 6 | 96 | 576 | ○ | ○ | ○ | 0.0066 | 996 | 0.0595 |
| 12 | 192 | 1152 | ○ | ○ | ○ | 0.0059 | 996 | 0.0595 |
| 18 | 288 | 1728 | ○ | ○ | ○ | 0.0063 | 996 | 0.0595 |

**選定**: R = 18。最も有利な行 (一様 sd 0.05・uniform・⊥ 0・crn) が 2τ で power 0.8 に届く: はい。

**表 2**: 選定規則の power の最悪値 (攪乱点の中で最小)。

| R | P(PASS \| 2τ) 一様 sd 0.05 | 一様 sd 0.3 | 対数オッズ | P(NO_GO \| 0) 一様 sd 0.05 | 一様 sd 0.3 |
|---|---|---|---|---|---|
| 6 | 0.899 | 0.894 | 0.894 | 0.901 | 0.895 |
| 12 | 0.990 | 0.991 | 0.990 | 0.991 | 0.990 |
| 18 | 0.998 | 0.999 | 0.999 | 0.998 | 0.999 |

**表 3**: 形ごとの power 0.8 の境目 E[C] (掃引の線形補間、判定に使わない)。各欄 有利 (uniform・⊥ 0・crn) / 不利 (label_skew・⊥ 0.1・anti)。

| 形 | R = 6 | R = 12 | R = 18 | 到達上限 (有利 / 不利) |
|---|---|---|---|---|
| 一様の混合 sd 0.05 (最も有利) | 0.434 / 0.443 | 0.391 / 0.393 | 0.373 / 0.376 | 1.000 / 0.900 |
| 一様の混合 sd 0.3 | 0.427 / 0.457 | 0.389 / 0.400 | 0.373 / 0.385 | 1.000 / 0.900 |
| 分類の 1/3 に集中 | 届かない / 届かない | 届かない / 届かない | 0.321 / 届かない | 0.333 / 0.300 |
| 分類の 2/3 に集中 | 0.409 / 0.426 | 0.371 / 0.384 | 0.362 / 0.370 | 0.667 / 0.600 |
| セルの全か無か | 0.398 / 0.432 | 0.366 / 0.384 | 0.349 / 0.369 | 1.000 / 0.900 |
| 単位の全か無か | 0.465 / 0.506 | 0.425 / 0.437 | 0.401 / 0.413 | 1.000 / 0.900 |
| arm × 単位の全か無か | 0.423 / 0.473 | 0.385 / 0.415 | 0.370 / 0.394 | 1.000 / 0.900 |
| 項目の全か無か (r を通じて固定) | 0.393 / 0.444 | 0.365 / 0.404 | 0.346 / 0.397 | 1.000 / 0.900 |
| 事前偏り × 対数オッズ (base = label_skew) | 0.449 / 0.446 | 0.443 / 0.417 | 0.439 / 0.410 | 0.949 / 0.854 |
| 逆向きの汎化 (項目の 1/6 が λ = −1) | 0.471 / 0.462 | 0.423 / 0.409 | 0.404 / 0.390 | 0.667 / 0.600 |

**表 4**: 枝ごとの size の最悪値 (攪乱点の中で最大、2 seed の大きい方)。境界 E[C] = τ の全形と、帰無の領域 (弱い null・二点の極値)。

| 点 | 枝 | R = 6 | R = 12 | R = 18 |
|---|---|---|---|---|
| 一様の混合 sd 0.05 (最も有利) | PASS | 0.0052 | 0.0058 | 0.0047 |
| 一様の混合 sd 0.05 (最も有利) | NO_GO | 0.0051 | 0.0037 | 0.0032 |
| 一様の混合 sd 0.3 | PASS | 0.0060 | 0.0056 | 0.0045 |
| 一様の混合 sd 0.3 | NO_GO | 0.0044 | 0.0028 | 0.0029 |
| 分類の 1/3 に集中 | PASS | 0.0038 | 0.0053 | 0.0063 |
| 分類の 1/3 に集中 | NO_GO | 0.0055 | 0.0046 | 0.0046 |
| 分類の 2/3 に集中 | PASS | 0.0049 | 0.0059 | 0.0055 |
| 分類の 2/3 に集中 | NO_GO | 0.0047 | 0.0038 | 0.0033 |
| セルの全か無か | PASS | 0.0046 | 0.0053 | 0.0056 |
| セルの全か無か | NO_GO | 0.0049 | 0.0042 | 0.0036 |
| 単位の全か無か | PASS | 0.0066 | 0.0042 | 0.0036 |
| 単位の全か無か | NO_GO | 0.0032 | 0.0022 | 0.0025 |
| arm × 単位の全か無か | PASS | 0.0048 | 0.0052 | 0.0055 |
| arm × 単位の全か無か | NO_GO | 0.0033 | 0.0030 | 0.0025 |
| 項目の全か無か (r を通じて固定) | PASS | 0.0009 | 0.0005 | 0.0006 |
| 項目の全か無か (r を通じて固定) | NO_GO | 0.0003 | 0.0003 | 0.0002 |
| 事前偏り × 対数オッズ (base = label_skew) | PASS | 0.0006 | 0.0003 | 0.0001 |
| 事前偏り × 対数オッズ (base = label_skew) | NO_GO | 0.0045 | 0.0031 | 0.0034 |
| 逆向きの汎化 (項目の 1/6 が λ = −1) | PASS | 0.0003 | 0.0005 | 0.0006 |
| 逆向きの汎化 (項目の 1/6 が λ = −1) | NO_GO | 0.0004 | 0.0002 | 0.0003 |
| 弱い null (単位で 0.4 が 5/7・−1 が 2/7) | PASS | 0.0000 | 0.0000 | 0.0000 |
| 二点の極値 {m, −1} m = 0.4 | PASS | 0.0052 | 0.0047 | 0.0031 |
| 二点の極値 {m, −1} m = 0.6 | PASS | 0.0037 | 0.0034 | 0.0024 |
| 二点の極値 {m, −1} m = 0.8 | PASS | 0.0036 | 0.0028 | 0.0026 |
| 二点の極値 {m, −1} m = 1.0 | PASS | 0.0030 | 0.0027 | 0.0024 |
| 二点の極値 {m, +1} m = -1.0 | NO_GO | 0.0028 | 0.0012 | 0.0005 |
| 二点の極値 {m, +1} m = -0.5 | NO_GO | 0.0027 | 0.0018 | 0.0012 |
| 二点の極値 {m, +1} m = 0.0 | NO_GO | 0.0027 | 0.0024 | 0.0026 |
| 二点の極値 {m, +1} m = 0.2 | NO_GO | 0.0033 | 0.0034 | 0.0027 |

**表 5**: 定理の直接の確認 (判定式に、単位 d を二点分布から直接与えた棄却率、10⁴ 回 × 2 seed の大きい方)。

| 二点 | R = 6 | R = 12 | R = 18 |
|---|---|---|---|
| {-0.5, +1} (NO_GO 枝) | 0.0016 | 0.0013 | 0.0014 |
| {-1.0, +1} (NO_GO 枝) | 0.0016 | 0.0006 | 0.0003 |
| {0.0, +1} (NO_GO 枝) | 0.0019 | 0.0014 | 0.0033 |
| {0.2, +1} (NO_GO 枝) | 0.0065 | 0.0034 | 0.0020 |
| {0.4, −1} (PASS 枝) | 0.0007 | 0.0015 | 0.0030 |
| {0.6, −1} (PASS 枝) | 0.0041 | 0.0027 | 0.0017 |
| {0.8, −1} (PASS 枝) | 0.0023 | 0.0013 | 0.0018 |
| {1.0, −1} (PASS 枝) | 0.0025 | 0.0020 | 0.0019 |

<!-- SKETCH:END -->

### 7.3 読み (判定ではない。凍結の可否・有効にする枝・claim を限る範囲だけを決める)

1. **最も有利な行は door-close でない**: 一様 sd 0.05 (uniform・⊥ 0・crn) の power 0.8 の境目は E[C] 0.37 (R = 18)、到達上限は 1.0。
   選定規則の 3 条件は R = 6・12・18 のすべてで満たされ、規則どおり R_MAIN = 18 が選ばれた。
2. **両枝を有効にする**: 境界 E[C] = τ の全形と帰無の領域 (弱い null・二点の極値・逆向き・項目の全か無か) で、両枝の size の最悪値は
   0.0066 で、上限 α = 0.05 の内側だった (表 4・表 5)。統合系 ADR §7 で符号反転の判定が破れた形 (全か無かの NO_GO 側 0.065〜0.080、
   族単位の非対称の PASS 側 ≥ 0.31) を含めて、§5.2 の定理が覆う。NO_GO の枝を外さず、claim を形で限らない (NO_GO の claim は §11 の上限まで)。
3. **R = 18 の境目** (表 3、有利 / 不利): 一様 0.37 / 0.38〜0.39、セル・arm × 単位・項目の全か無か 0.35〜0.37 / 0.37〜0.40、
   単位の全か無か 0.40 / 0.41、対数オッズ 0.44 / 0.41、逆向き 1/6 で 0.40 / 0.39、分類の 2/3 に集中 0.36 / 0.37。
   lookup (v2、C = 0.785) の 0.44〜0.56 倍。統合系 ADR §7 の「0.6〜0.7 倍」から下がったのは、単位を細かく取り K = 1 にしたため (§5.3)。
4. **届かない形**: 分類の 1/3 にだけ出る集中は到達上限 0.33 で、R = 18 の有利な攪乱点でだけ境目 0.321 に届く。汎化される分類が 1 つだけなら、
   ほぼ検出できない (INCONCLUSIVE)。
5. **読みの限界**: 模擬は ⊥ と OOΩ を一様に置き、族内の 2 arm の結合を代表的な 3 つ (crn はつ組の 3 probe でも共有) でだけ見た。
   実の雑音は null pilot (§8) の spike-in で、R = 18 について条件付きで見る。power の値は混合の仮定と模型の上の値で、実際の汎化の形が
   模型の外 (例: layout に強く依る全か無か) なら下がる。size は模型に依らない (定理)。

## 8. null pilot (gate 3、判定に使わない。実装 = `scripts/generalization_probe_pilot_gate.py`)

### 8.1 計画 (実行は第 1 段の凍結の後の別の user 裁定、GPU)

| 腕 | 内容 | r | K | 呼び出し |
|---|---|---|---|---|
| M_A / M_A_rot / M_B / M_B_rot | masked の状態: 本走と同じ状態の key の欄を「不明」にしたもの (label・distractor・行順・Ω・表示順は本走と同じ形) | 50〜55 | 1 | 576 |
| KNOW | 潜在の知識確認: 36 key (dev 12 + probe 24) の分類を閉集合 {bird, fish, insect} で答えさせる。正答の位置は 3 試行で 3 位置を一巡する (Codex HIGH-2) | — | 3 | 108 |

- 合計 684 呼び出し。実行条件・parse・記録の schema・meta は本走と同じ (KNOW の parse は分類名のちょうど 1 種)。
- masked の状態は潜在の情報を持たない。状態を読む雑音 (行の label の写し・位置の偏り) は含む。null の C は観測値として spike-in の較正に使い、
  0 であることを仮定しない (Codex HIGH-4)。
- pilot の r・seed は本走と交わらない (機械検査)。**pilot の記録は本走の verdict に使わない** (資格と確認の分離)。

### 8.2 機械判定 (第 1 段で凍結。順に適用)

1. STOP (records): certification・meta・schema・構造の違反、または見取り図が R を選ばなかった。
2. not_computed: transport 失敗・欠け。
3. **STOP (knowledge)**: どれかの key で、3 回のうち正答が 2 回未満。構成概念 (モデルが研究者の分類を共有する) が成り立たない。
   本走の verdict 語では INVALID_TASK_BATTERY に当たる。key を差し替えない (差し替えは実データの後の設計変更になる)。
   常に先頭 / 末尾を答える方策は、全 key で 1/3 しか当たらずここで止まる (test で pin)。
4. **STOP (envelope)**: masked の腕の ⊥ 率 > 0.2、または族内の ⊥ 率差 ≥ τ/4。
5. **spike-in の OC**: R の候補のうち見取り図が選んだ R 以上のもの (選定は R = 18 で、候補の最大も 18 なので、18 だけ) を見て、
   次をすべて満たせば **GO**。満たさなければ **STOP (power、door-close)**。
   - P(PASS | E[C] = 2τ) ≥ 0.8、P(NO_GO | E[C] = 0) ≥ 0.8、P(PASS | τ)・P(NO_GO | τ) が合格 (率 ≤ x / N、N = 2,000、点の数 6 で
     x / N = 0.065)、既知量への較正 (下) が成り立つ。5 条件のそれぞれを単独で破る test と変異がある (Codex MEDIUM-8)。
   - OC の ⊥ gate は、本走と同じ上限 min(0.2, pilot の masked の最大 ⊥ 率 + 0.05) を使う (Codex 2 回目 MEDIUM-4)。
- 出力 (`results/pilot/gate.json`) は、本走の判定が読む値 (GO と R・masked の最大 ⊥ 率・observed) と、入力 (記録・meta・certification・見取り図) の sha256 を持つ。
- driver は pilot の provenance (`results/pilot/provenance.json`) に、自分の sha256 と、自分が書いた記録・meta の sha256 (`driver_sha256`・`records_sha256`・
  `meta_sha256`) を記録する。第 2 段は、3 つとも現在のファイル (certify された driver・照合する記録・meta) と一致することを要求する
  (別の実行の provenance を混ぜた記録を通さない。Codex 3 回目 HIGH-2)。

### 8.3 spike-in の契約 (計測台 §4.1 の 6 項目)

- **条件付き OC**: OC は「この null 記録に条件付けた値」で、母集団 (同じ条件の将来の実走) への保証ではない。size は §5.2 の定理で守られ、pilot に依らない。
  pilot の不確実性は power の見積りにだけ効く。
- **再標本化の単位と依存構造** (Codex MEDIUM-7): 単位 (族, つ組, r) を、(族, つ組, 表示の回転) の層ごとに本走の割付数 (R/3) だけ復元抽出する
  (単位の中の 2 arm × 3 probe の結合と、本走の表示位置の割付を保つ)。pilot の r を 6 個にして、各層に 2 単位を置いた。
- **既知量への較正**: masked の記録の上で、⊥ でないセルを確率 λ で w (目標が null の C より小さければ foil) に置き換える。
  λ = (目標 − C_null) / (1 − b̂ − C_null) (foil の向きは対称の式)。注入の後に、実現した平均が目標から 0.01 以内であることを確かめる (外れたら OC を不合格)。
- **pilot の不確実性**: 外側の再標本化はしない。理由: size は定理で守られ、pilot の不確実性は power (INCONCLUSIVE の率) にだけ効く。OC を条件付きと書く。
- **選定の評価**: 注入法と envelope は実データ前に固定した。R は見取り図の規則で決まり (18)、pilot は 18 の合否だけを見る (選定の自由度は無い)。
- **確認の実走との分離**: pilot の記録 (r 50〜55、別の seed の名前空間) を本走の verdict に使わない。
- **混合の仮定**: 効果を null の挙動に重なる混合と仮定する。効果が雑音の構造 (⊥・決定性・label の事前傾向) を変える場合は、§7 の見取り図
  (対数オッズの形・3 結合) で別に見る。
- **envelope** (計測台 §5、Codex MEDIUM-6): OC は pilot の雑音に条件付く。本走の arm ごとの ⊥ 率の上限を min(0.2, pilot の masked の最大 ⊥ 率 + 0.05)
  とし、外れたら INVALID_TASK_BATTERY (battery が想定どおりに振る舞わなかった)。余裕 0.05 は実データ前に固定した。

## 9. 凍結と実走の手順 (それぞれ別の user 裁定)

### 9.1 第 1 段 `PILOT-FROZEN`

1. 見取り図が R_MAIN = 18 を選び、最も有利な行が 2τ に届き、変異試験が全 KILLED で meta-test が登録どおりに落ちたことを確かめる。
2. prereg の status を `**PILOT-FROZEN**` にし、`uv run python scripts/generalization_probe_manifest.py --write --stage pilot` で `manifest.json` を書く。
3. `--verify --stage pilot` が `MANIFEST OK (stage pilot)` を出すことを確かめ、commit する。

### 9.2 null pilot (第 1 段の後、user 裁定で GPU を許可した後)

1. driver (範囲外、別途書いて変異試験で certify する) が §8.1 の plan を §4 の条件で呼び、`results/pilot/{records.jsonl,meta.json,provenance.json}` を書く。
2. `bash experiments/20261001-generalization-probe-pilot/run.sh pilot`: manifest の照合 (stage pilot) → 機械判定を 2 回計算して byte 一致 → `results/pilot/gate.json`。
3. STOP なら本走を起こさない (理由ごとの記録は §11)。

### 9.3 第 2 段 `FROZEN` (確認実験)

1. 第 2 段の照合 (`--verify --stage main`、manifest が機械的に行う。Codex 2 回目 HIGH-2・HIGH-3・MEDIUM-5、3 回目 HIGH-1・HIGH-2、4 回目 HIGH-1):
   - 第 1 段の封印: `manifest.json` があり、prereg は status 行以外 (`prereg_body_sha256`)、他の対象は sha256 が封印時と同じ。
   - pilot: 凍結した機械判定を記録から再計算し、GO・R・masked の最大 ⊥ 率・observed が `gate.json` と一致する。R が 18。入力の sha256 が現在の記録と一致する。
   - driver: provenance の driver・記録・meta の sha256 が現在のファイルと一致する (§8.2)。driver の certification が契約を満たす
     (各行が一意の label・KILLED・空でない期待診断・期待診断のどれかで実際に落ちた、登録変異の集合 = driver の harness の `MUTANTS`、
     meta-test が driver の harness の `META_CASES` (先頭 = label、末尾 = 落ちるべき test の集合) と一対一で、各ケースの期待集合が実際の失敗に
     含まれる、driver・driver の test・harness の sha256。Codex 2 回目 HIGH-3・3 回目 HIGH-1)。登録 (`MUTANTS`・`META_CASES`) 自体も、
     label が一意の文字列で期待集合が空でない test 名の集合でなければ、照合の表を作らずに拒否する (Codex 4 回目 HIGH-1)。
2. prereg の status を `**FROZEN**` にし、`--write --stage main` で `manifest_main.json` を書く。対象 = 第 1 段の対象 + 固定した証拠の集合
   (`manifest.json`・pilot の記録・meta・provenance・機械判定の出力・driver・driver の harness・driver の test・driver の certification)。
3. `--verify --stage main` が `MANIFEST OK (stage main)` を出すことを確かめ、commit する。

### 9.4 本走 (第 2 段の後、さらに別の user 裁定で GPU を許可した後)

1. driver が §2 の設計・§4 の条件で lever 4 arm を呼ぶ (R = 18、pilot と同じ実行環境)。途中で R・prompt・parse を変えない。
2. `bash experiments/20261001-generalization-probe-pilot/run.sh main`: manifest の照合 (stage main) → 判定を 2 回計算して byte 一致 → `results/run/results.json`。
3. certification は凍結時のものを読むだけで、実走後に変異 harness を回し直さない。凍結前の確認は構造 (件数・型) まで。

## 10. 検査器の Done 条件 (CPU、実モデル不使用)

- test (`tests/test_generalization_probe/`): battery・fixture・scorer・見取り図・pilot の機械判定・manifest。各判定の枝 (5 語と not_computed) に
  到達する合成の記録を含む。scorer と pilot の機械判定の CLI を入口から通す smoke test を含む (Codex HIGH-5)。
- **変異試験** (`scripts/generalization_probe_mutation_check.py`、`results/certification.json`):
  - 変異は 4 つ組 (名前・変異・期待診断 = 落ちるべき test・理由) で登録した。battery 19・fixture 11・scorer 39・見取り図 21・pilot 判定 23・
    manifest 49 の計 162 (manifest の判定行も対象。外す test は成果物の sha256 一致の 1 件だけ。Codex 2 回目 MEDIUM-5・3 回目・4 回目)。
  - 判定は 3 通りに分けて報告する: 対照 (無変異) が落ちた → harness を止める / 変異が捕まらなかった (SURVIVED) / 落ちたが理由が違う
    (WRONG_REASON・COLLECTION_ERROR)。KILLED に数えるのは期待した test が落ちたものだけ。
  - meta-test: 複製ツリーで `decide` を常に INCONCLUSIVE に、`structure_violations` を空に潰し、依存する test が実際に落ちることを見る。
    manifest は、meta-test が登録ケースと一対一で各ケースの期待集合をすべて実際に落としたこと、各変異の行が期待した test のどれかで
    実際に落ちたこと (記録した失敗の集合と期待診断の共通部分が空でない) を照合する (Codex 3 回目 HIGH-1)。照合の表を作る前に、登録
    (変異と meta-test のケース) の label が一意の文字列で期待集合が空でないことも確かめる (Codex 4 回目 HIGH-1)。
  - **全 KILLED と meta-test の成立が certification の条件** (§5-1)。
- **manifest** (`scripts/generalization_probe_manifest.py`): 結び付き (certification・見取り図の sha256・期待する点の完全性・行からの 3 条件と
  閾値と最有利行の到達と選定の再計算・fixture 表の再計算・key 選定) と、段ごとの凍結条件を分ける。certification は manifest 検査自体の sha256 も持つ。
  見取り図は、凍結した設定 (`params` 全体)、行の R、seed ごとの結果が率の組として成り立つこと (4 判定が有限・[0, 1]・合計 1・MC の回数の格子の上、
  実現 C が有限)、size の最悪値、sweep の点の完全性 (R × 形 × 有利・不利、到達上限までの格子) と到達上限・`pass` を seed ごとの結果から、
  最有利行の到達と境目の表を sweep から計算し直して照合する (Codex 3 回目 MEDIUM-3)。JSON の真偽値は数値に数えず、`params` は型まで含めて
  照合する (Codex 4 回目 LOW-2)。

## 11. claim の上限と license (統合系 ADR §8)

| 結果 | 言えること | 言わないこと |
|---|---|---|
| PASS | 「1 つの凍結 qwen3:8b の上で、同じ base・空の初期状態のエージェントが、環境が与えた観察だけの違いで、状態に答えの無い held-out の状況で、この人工の潜在構造 (生き物の分類) の向きに τ を超えて違う選択をした (族内の選択分布 TV の向き付き下界)。その違いは、probe key を見ない方策 (prompt の key 以外と seed の関数) では決定的な decode の下で生じず (§6 の定理)、登録した字面の写し方 (§6) でも説明できない」。必ず付す: fixture の寄与の上限 (最大 |C|)・効果の形の見取り図 (§7)・採った τ 判定 (§5.1 の betting e-value)・推論が固定した prompt の schedule に条件付きであること | 汎化の機構 (類推・規則の帰納・意味の近さ)。登録外の字面の写し方を排除したこと。新しい layout・新しい項目・項目の母集団への一般化。自由文の「思考」。統合系・身体性・3D・H1・H3 の寄与。エージェント自身の探索。v2 の claim (rule lookup) の拡大 |
| NO_GO | 「この潜在構造・この battery・この schedule での、平均の潜在方向の対比 E[C] は τ 未満」まで | 汎化の総量・汎化の存在の否定。選択分布の差全体の否定 (C は向き付きの平均で、正と逆向きの汎化が相殺しうる)。他の潜在構造 |
| INCONCLUSIVE / INVALID | 測れなかった、まで | 効果の有無 |
| pilot の STOP (knowledge) | 「モデルが登録した key の分類を答えられなかったので、この battery では問えない」まで | 汎化の有無 |
| pilot の STOP (power) | 「この雑音の下で、この設計は検定を起こせない (設計容量の door-close)」まで | 汎化の有無 |

言わないこと (全体): 統合系が発散しない / する。H4・「歩行」「身体性」の効果。閉集合 battery でのリンク (ii) の結論の書き換え。
v2〜v5・(b) の verdict・door-close の書き換え。自由文の意味での「思考の分散」。

## 12. 設計の経緯と、実データ前に決めたこと

| id | 内容 | 理由 |
|---|---|---|
| DM-1 | /reimagine はハイブリッド (user 裁定): 潜在 = 再生成案の分類 3 クラス、単位・τ 判定・凍結の段 = 初回案 | 同じ呼び出し数で、セル単位は power 0.8 の境目が E[C] ≈ 0.40、v2 型の単位は ≈ 0.6 (Plan の CPU 試算) |
| DU-1 | 本走の R = 候補の最大 (user 裁定 2026-10-02、見取り図の後・実データの前) | §7.1 の逸脱の記録 |
| DD-1 | τ 判定 = 固定 λ の混合の betting e-value (ADR gate 2 の (a)) | 異質な単位平均でも AM-GM と Markov で有効。(b) の −b は、逆向きの汎化を bridge が排除できない (ADR §5.2 の形 6) ので根拠が立たない |
| DD-2 | 帰無を固定した schedule に条件付ける | 項目ごとの効果が r を通じて固定なら、条件付けない平均では単位が独立でない。模擬で確かめた (項目の効果を模擬ごとに無作為に引くと境界で PASS の率 0.21、項目の数を厳密にすると ≈ 0) |
| DD-3 | K = 1、単位 = (族, つ組, r) | §2.5・§5.3 |
| DD-4 | 成功行だけの状態 | v3 の抽出の問いと分ける (§2.4) |
| DD-5 | probe key を、字面の方策の釣り合いの決定的な探索で選んだ (選定用の行順で) | §2.2。モデルの出力を見ていない |
| DD-7 | 4 成分 > 0 の条件を v2 から継ぐ | 1 arm だけが動く場合に PASS させない。対数オッズの形で power を下げる (§7) ことを承知で継ぐ |
| DC4-1〜2 | Codex review 4 回目の採否 (3 回目の反映の差分に限る。HIGH 1・LOW 1、全て採用。判定コードと見取り図の値は変わらない) | 登録 (MUTANTS・META_CASES) の形の検証 (空の期待集合・label の重複を拒否)・JSON の真偽値を数値に数えない |
| DC3-1〜3 | Codex review 3 回目の採否 (HIGH 2・MEDIUM 1、全て採用。判定コードと見取り図の値は変わらない) | 変異と meta-test が期待した test で実際に落ちたことの照合 (driver も)・provenance が driver と記録・meta を同時に結ぶ・見取り図の sweep・率・設定・境目の再計算 |
| DC2-1〜6 | Codex review 2 回目の採否 (HIGH 3・MEDIUM 2・LOW 1、全て採用) | seed をつ組で共有 (seed を読む方策も d = 0)・第 2 段が第 1 段の封印を照合・driver の certification の契約・OC に本走の envelope・manifest が見取り図と pilot を再計算 (manifest も変異の対象)・二項の閾値の説明 |
| DC-1〜13 | Codex review 1 回目の採否 (HIGH 5・MEDIUM 6・LOW 1、全て採用) | Ω を族の 3 label に (key を見ない方策の C = 0 が定理になった)・知識確認の正答位置の均衡・2 段の凍結・選定用の行順と schedule 条件付きの推論・CLI の修正・envelope・層別の再標本化・certification の穴・二項の閾値・3 結合・モデルの同定・部分列の方策・C0 を外す |

## 13. 計測台の gate 6 点との対応

| 点 | 本登録での満たし方 | 状態 |
|---|---|---|
| 0 登録 | §0 の表 (v2・v3 との重なりを含む) | 済 |
| 1 certification | §10 の変異 162 と meta-test 2。driver の certification は第 2 段の条件 (契約は第 1 段で固定) | 判定コード: 162 / 162 KILLED・meta-test 成立 (`results/certification.json`)。driver: 第 2 段で |
| 2 前提の監査 | §5.2 (推論の対象・定理・依存の単位・相殺の条件) と §6 の定理 | 済 |
| 3 雑音と spike-in | §8 (null pilot の計画・機械判定・spike-in の契約)。証拠は pilot の後に機械的に得る | 計画を登録 (第 1 段)。証拠は第 2 段の条件 |
| 4 形の見取り図 | §7 (10 形 + 帰無の領域、18 攪乱点、size の上限と MC の採否を分離) | 最も有利な行は door-close でない。R = 18 が 3 条件を満たす。両枝を有効にする (size の最悪 0.0066) |
| 5 bridge | 統合系 ADR §5.2 を本登録の battery で具体化 (§1・§2・§6・§7)。Codex review 1〜4 回目 (いずれも Revise、全て反映) | 済 |

## 14. 非再開・やらないこと (継承)

- CLD・Stage B・weight-space door・M13 の閉じた chain を再開しない。閉集合 battery でリンク (ii) を問わない。
- 同じ世界で seed・摂動・初期 prompt の差だけが違う状態を、分散の源にしない。距離の時間傾きを指標にしない。
- 見取り図を見てから、通すために基準・形・潜在構造を変えない (変えるなら実データ前の逸脱として user 裁定と記録。§7.1)。
- 論文の本数・分割を本登録から決めない。research-positioning の書き換えは別途 user 裁定。
