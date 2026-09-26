# 事前登録 v2 — Skill lever-only feasibility pilot: 書かれた規則は凍結 8B の閉集合選択を動かすか

本文書は pilot のどの実走よりも**前に**凍結する。凍結前に Codex (gpt-5.5/xhigh) の independent review を受け
(Adopt-with-changes: HIGH 2・MEDIUM 4・LOW 1、全て反映。`.steering/20260926-skill-lever-pilot-prereg/codex-review.md`)、
指摘の採否を `.steering/20260926-skill-lever-pilot-prereg/decisions.md` (ローカル) に記録した。凍結後の変更は本登録の
結果とみなさない。凍結 commit と sha256 は判断 ADR (`.steering/20260926-skill-lever-pilot-prereg/design-final.md`、
ローカル) に記録する。

本文書は GPU・実モデル呼び出し・sealed run・spend を authorize しない。pilot 実走 (§8) は凍結後に別途 user 裁定を要する。

旧 Stage B 事前登録 (`experiments/20260926-developmental-substrate-stage-b/prereg.md`、sha256 `ba7b16a5…`) は変更
しない。本登録はその閾値・判定行を流用しない (§11)。

## 1. 問い・位置づけ・claim の上限

**問い**: 手書きの Skill 状態 (lever = 発達 signature に対する規則の一覧) を prompt に注入すると、凍結 base
(qwen3:8b、think=False) の held-out probe 上の閉集合選択が、**書かれた規則の向きに**、replicate の散らばりを超えて
動くか。

- 旧 Stage B は B-pre 不成立で停止した (B-pre が見たのは文脈 cue の効果であり、規則を注入したときの効果は未測定)。
- これまでの実測は「入力側の器官は実在するが、凍結 8B の出力へ届く最後の一段がほぼゼロ」で揃っている。Skill は
  この欠けた変換器の候補であり、本 pilot は **外部状態で凍結 8B の出力が動くか** の判定でもある。この位置づけを
  理由に閾値を甘くしない。
- **claim の上限 = 「書かれた規則を外部状態経由で読めた (rule lookup)」**。経験から育った状態による分化 (旧 B3) は
  主張しない。PASS しても Stage B を自動で再開しない (再開は別の事前登録)。
- 落ちた場合は外部 Skill 状態の経路を閉じる。door-close は正当な Done。

## 2. 設計

### 2.1 battery (旧ドラフト `scripts/stage_b_battery.py` の値をそのまま使う)

- 状況 signature = weather {rain, clear, wind} × time {dawn, noon, dusk} × company {alone, paired} (18 通り)。
  規則を担う特徴は weather。
- 行動 label (6 語彙) = read_book / sit_quiet / walk_path / talk_peer / tend_moss / rest_eyes (全て 9 文字)。
- 発達 signature 12 個 (Skill エントリの条件に使う) と held-out probe 6 個 (各 weather 2 個) は互いに素。probe は
  weather を共有するが signature 全体は発達に出現しない。
- 規則表 A: rain→read_book、clear→walk_path、wind→tend_moss。σ = (read_book sit_quiet)(walk_path talk_peer)
  (tend_moss rest_eyes)。

### 2.2 arm (5 本、実装 = `scripts/skill_lever_battery.py`)

| arm | 規則 (weather w → 行動) | 役割 |
|---|---|---|
| A | A(w) | 判定 |
| A_rot | A(next(w))、next = rain→clear→wind→rain | 判定 (A の foil) |
| B | σ(A(w)) | 判定 |
| B_rot | σ(A(next(w))) | 判定 (B の foil) |
| C0 | 状態なし | ⊥ gate と記述報告のみ |

- probe q (weather w) で 4 arm が指す選択肢 w_a(q) は相異なり、Ω_q = {A(w), A(next(w)), σA(w), σA(next(w))}
  と 1 対 1 に対応する。Ω_q は σ で閉じる。
- **族** = {A, A_rot} と {B, B_rot}。族内の 2 arm の状態は、同じ発達 signature を同じ順で並べ、行動 label の集合と
  頻度が一致し、weather との対応だけが違う。ゆえに次の **登録した nuisance class** は §3 の推定量で 0 になる
  (合成 fixture で確認): 文脈に出た label を選ぶだけ (priming)、label そのものへの固定の事前傾向、表示位置だけで
  選ぶ、状態の最後のエントリの label を選ぶ (recency、probe の weather の均衡で打ち消し合う)。これら以外の読み方
  (例: 状態中の位置 × 選択肢の位置 × label の交互作用) まで相殺されることは保証しない (Codex MEDIUM-4)。
- 旧型の A vs B 対比は priming と交絡する (A の状態には A 側 label しか出てこない) ので判定に使わない
  (§10 で記述報告のみ)。

### 2.3 replicate と counterbalance

- replicate r = counterbalance の 1 セル。同じ r の中では**全 arm が同じ layout と同じ decoding seed 列を共有**する。
- Ω_q の表示順: 正準順 (A, A_rot, B, B_rot の指す選択肢) を (r + probe 番号) mod 4 だけ巡回。R が 4 の倍数なので、
  各 probe で各選択肢が各表示位置に同数回来る。
- Skill エントリの配置順: 発達 signature の置換 π_r = `numpy.random.default_rng(20260926 + r).permutation(12)`。
  全 arm で共有し、行動 label を鍵にしない。
- decoding seed = 20260926 + 10000·r + 100·(probe 番号) + k (arm 間で共有)。

### 2.4 prompt (凍結 renderer)

- system: 「あなたは与えられた状況で、示された行動の中から 1 つを選ぶ。」 (persona なし)
- user (lever arm): 「これまでの経験の記録:」+ 各エントリ「条件: <weather> / <time> / <company> → 行動: <label>
  (成功 3 / 失敗 0)」を π_r 順に 12 行 + 空行 + probe 部。C0 は probe 部のみ。
- probe 部: 「状況: 天候=<w>、時刻=<t>、同伴=<c>。\n次の行動から 1 つだけ選び、行動名だけを答えよ: <Ω_q を表示順に「、」区切り>」
- 非漏洩 (機械検査、旧 prereg §2.2 と同じ `integrity_violations` + arm 名): 状態・prompt に probe id、probe
  signature から選択肢への対応表、arm / stream の識別子を入れない。状態の条件は発達 signature のみ。
- 描画 prompt の最大は 1,161 byte。上限 3,000 byte + template 64 + num_predict 32 ≤ num_ctx 4,096 (token 数 ≤ UTF-8
  byte 数) で、**切り詰めが起こりえないことを静的に保証**する (runtime の prompt_eval_count は prefix cache で
  値が変わりうるので使わない)。

## 3. estimand

- 成分 s_{a,r} = (arm a・replicate r の全 probe × K sample のうち w_a を選んだ数 − foil_a を選んだ数) / (6K)。
  foil_a = 族内の相手 arm が指す選択肢 (A↔A_rot、B↔B_rot)。
- ⊥ (§4) と OOΩ (語彙内だが Ω_q 外の label) と Ω_q 内の残り 2 選択肢は、分母に含め、w にも foil にも数えない。
- 単位 d_{r,f} = (s_{a,r} + s_{a',r}) / 2、族 f = {a, a'}。単位は 2R 個。
- **C = mean d = 4 成分の平均**。完全 lookup = 1 (⊥ 率 b なら 1−b)、priming のみ = 0、無関係 = 0。
- 族内で arm ラベルを入れ替えると d の符号が反転する (a の foil = a' の w)。null (書かれた規則の対応が選択に効かない)
  の下で d は 0 の周りに対称なので、**符号反転の全列挙** (2^{2R} 通り、観測を含む、片側) で検定する。単位を sample や
  probe にしない (擬似反復)。

## 4. 実行条件と parse (凍結)

- model `qwen3:8b`、think=False、temperature 0.7、top_p 0.8、repeat_penalty 1.0、num_ctx 4096、num_predict 32、
  options.seed を明示。run はこの要求条件を `meta.json` に記録し、`request_meta()` と一致しなければ INVALID_SCORER。
- **R = 4、K = 10** (§6 の power 表の選定)。5 arm × 4 × 6 probe × 10 = 1,200 呼び出し。R_max = 12・K ≤ 20 (user 裁定)。
- 呼び出し順: C0 を全て先に実走し、§5-3 の C0 gate を計算してから lever 4 arm を実走する (C0 が落ちたら lever は
  走らせない、調整もしない)。各 sample は run 全体の通し番号 `call_index` を持ち、scorer は「全 C0 の call_index <
  全 lever の call_index」と一意性を検査する (Codex MEDIUM-1)。
- **記録の schema** (1 行 1 JSON object、欄は過不足なく): `call_index` / `replicate` / `k` / `seed` (int、bool や
  float を int に読み替えない)、`arm` / `probe_id` / `prompt_sha256` (str)、`raw` / `parsed` (str または null)。
  JSON として読めない行・欄の過不足・型違い・meta が JSON object でない場合は、例外で止めず INVALID_SCORER
  (reason `record_schema`) を返す (Codex MEDIUM-3)。

**入力値の全クラスと扱い** (`parse_choice`、test で pin):

| 入力 | 扱い |
|---|---|
| transport 失敗 (例外・非 200・timeout) | 同じ seed で 3 回まで再送。解けなければ `raw = null` を記録 → run 全体が `status=not_computed` (verdict を書かない、⊥ にしない) |
| 全ての入力 | 最初に NFKC → 小文字化 (大文字・全角の think tag も同じ形になる、Codex MEDIUM-2) |
| `<think>…</think>` を含む | 閉じたブロックを除去してから下へ。閉じていない tag (`<think` / `</think`) が残れば ⊥ |
| 空・空白のみ・句読点のみ (除去後) | ⊥ |
| 前後の空白・引用符・`*`・括弧・句読点 | 除去してから照合 |
| 6 label のちょうど 1 種を単語境界 (英数字でない) で含む (`read book` / `read-book` も同じ label) | その label |
| 0 種 (語彙外・日本語訳など) | ⊥ |
| 2 種以上 | ⊥ (先頭を採らない) |
| 語彙内だが Ω_q 外の label | OOΩ (分母に入り、w・foil に数えない) |

- 生テキスト `raw` を全件保存し、記録された `parsed` が再 parse と一致しなければ INVALID_SCORER。
- 既知の限界: 否定文 (「read_book ではなく…」で 1 種だけ現れる場合) は label として数える。

## 5. 判定 rule (verdict は `docs/research-positioning.md` §8 の 5 語のみ)

評価順に適用し、最初に当たったものを verdict とする。**τ = 0.30** (user 裁定)。α = 0.05。

1. **INVALID_SCORER** — 次のいずれか。
   - certification (`results/v2_mutation.json`) が無い・全変異 KILLED でない・記録 sha256 が現在の
     `skill_lever_scorer.py` / `skill_lever_battery.py` / `stage_b_scorer.py` / `stage_b_battery.py` と一致しない。
   - battery の機械検査 (選択肢の 1 対 1・族内 label 多重集合・位置の均衡・同 r の probe 部と seed の共有・非漏洩・
     prompt byte 予算) に違反。
   - 要求条件 `meta.json` が凍結値と不一致。
   - 記録の schema 違反 (§4)。
   - 記録の構造違反: key (arm, r, probe, k) の重複、凍結 grid (5 arm × R × 6 × K) の外の key、seed 不一致、prompt が
     凍結 renderer と不一致 (sha256)、記録 parse と再 parse の不一致、call_index の重複・負値、C0 の終わりより前の
     lever 呼び出し。
2. **計算しない** (`status=not_computed`、verdict なし) — transport 失敗の記録がある、または C0 / lever の行が欠ける
   (ただし C0 が揃って C0 gate が落ちた場合は 3 へ)。
3. **INVALID_TASK_BATTERY** — 次のいずれか。
   - C0 の ⊥ 率 > 0.2。
   - lever 4 arm のいずれかの ⊥ 率 > 0.2。
   - 族内の ⊥ 率差 ≥ τ/4 = 0.075。
4. **PASS** — (d − τ) の符号反転検定で p < α (= 片側下限 > τ) **かつ** 4 成分 mean_r s_{a,r} がすべて > 0。
5. **NO_GO_EFFECT_ABSENT** — (τ − d) の符号反転検定で p < α (= 片側上限 < τ)。
6. **INCONCLUSIVE_UNDERPOWERED** — それ以外 (区間が τ をまたぐ、または C は大きいが成分のどれかが ≤ 0)。

- 4 と 5 は、同じ d に対して「τ より大」と「τ より小」の片側検定なので同時には成立しない。
- C > 0 の検定 (d の符号反転 p) は記述報告。4 が成り立てば実質的に含意され、判定行として検出できない
  (変異試験で kill できない行を判定に置かない)。
- 旧 prereg の「実現 power < 0.8 → INCONCLUSIVE」は使わない (到達性が模擬 pool に依存する)。NO_GO は同等性型の
  検定で直接示す。

## 6. power と size (凍結前に scorer 実装で計算、`results/power_table.json`)

- power 表は certification と同じ 4 ファイル (判定コード) の sha256 を記録し、manifest 検査がその一致を確かめる
  (凍結する判定コードそのもので計算した証拠、Codex HIGH-1)。

- **植える効果量 δ_plant = 2τ = 0.60 と閾値 τ = 0.30 を別の数にする** (旧 §4 は効果をちょうど閾値に植えたため
  power が ~0.5 で頭打ちだった、DB-1)。
- 模擬 (`skill_lever_scorer.simulate`): arm a・replicate r の効果 e = C + N(0, sd²)、λ = clip(e/(1−b), −1, 1)。
  ⊥ 以外の質量を (1−|λ|)·base と |λ|·(w または foil の点質量) の混合にし (simplex 内)、各 (arm, r, probe) で K
  sample を多項抽出。判定と同じ ⊥ gate と `decide` を通す。符号反転は 16 単位以下なら全列挙 (判定の `signflip_p` と
  一致することを test で確認)。
- 攪乱格子 (12 点): base ∈ {uniform, label_skew (1 label に 0.7), position_skew (表示先頭に 0.7)} × ⊥ 率 b ∈ {0, 0.1}
  × sd ∈ {0.05, 0.3}。OOΩ は ⊥ 以外の 5%。
- 条件 (全 12 点で): P(PASS | C=δ_plant) ≥ 0.8、P(NO_GO | C=0) ≥ 0.8、P(PASS | C=τ) ≤ α + 3SE、
  P(NO_GO | C=τ) ≤ α + 3SE (10^4 回で上限 0.0565)。
- 選定規則: (R, K) ∈ {4, 8, 12} × {5, 10, 20} を呼び出し数の少ない順に、2,000 回の screening を通ったものから
  10^4 回で本確認し、最初に全 12 点で通ったもの。

**screening** (2,000 回): (4,5) ×、(4,10) ○、(8,5) ○、(12,5) ○、(4,20) ○、(8,10) ○、(12,10) ○、(8,20) ×、(12,20) ○。
(8,20) の × は uniform・b=0.1・sd=0.05 の P(PASS|C=τ) = 0.066 (上限 0.0646)。同じ点を 10^4 回・2 seed で再計算すると
0.0445 / 0.0464 で、2,000 回の MC 揺らぎ。(4,5) の × は label_skew・b=0.1・sd=0.3 で P(PASS|δ_plant) = 0.799。

**本確認 (R=4, K=10、10^4 回) の最悪値**: P(PASS|0.6) ≥ 0.907 (label_skew・b=0・sd=0.3)、P(NO_GO|0) ≥ 0.933
(label_skew・b=0.1・sd=0.3)、P(PASS|0.3) ≤ 0.047、P(NO_GO|0.3) ≤ 0.053。→ **R = 4、K = 10 を凍結**。

**OC 曲線** (R=4, K=10、10^4 回、verdict の率):

| 真の C | uniform・b0・sd0.05: PASS / NO_GO | label_skew・b0.1・sd0.3: PASS / NO_GO / INC / INVALID_TB | position_skew・b0.1・sd0.3: PASS / NO_GO |
|---|---|---|---|
| 0.0 | 0.000 / 1.000 | 0.000 / 0.933 / 0.051 / 0.016 | 0.000 / 0.948 |
| 0.1 | 0.000 / 1.000 | 0.000 / 0.694 / 0.289 / 0.017 | 0.000 / 0.718 |
| 0.2 | 0.000 / 0.948 | 0.003 / 0.295 / 0.687 / 0.016 | 0.002 / 0.305 |
| 0.3 | 0.041 / 0.043 | 0.041 / 0.053 / 0.893 / 0.014 | 0.042 / 0.048 |
| 0.4 | 0.945 / 0.000 | 0.253 / 0.003 / 0.728 / 0.017 | 0.287 / 0.003 |
| 0.5 | 1.000 / 0.000 | 0.645 / 0.000 / 0.339 / 0.016 | 0.710 / 0.000 |
| 0.6 | 1.000 / 0.000 | 0.909 / 0.000 / 0.078 / 0.013 | 0.942 / 0.000 |

- 読み: 攪乱が大きいと、0.1〜0.5 の中間の効果は INCONCLUSIVE に落ちやすい。INVALID_TASK_BATTERY の ~1.5% は
  b = 0.1 で族内 ⊥ 率差が偶然 0.075 を超える分 (設計上のコストとして受け入れる)。
- 格子外の攪乱 (例: layout によって規則を全く読む/全く読まない sd ≈ 0.5) では power は下がり、INCONCLUSIVE に
  落ちる。それは NO_GO でも PASS でもない、と正直に報告する。

## 7. 検査器の Done 条件 (CPU、実モデル不使用)

- **各 verdict 枝に到達する合成 fixture** (`tests/test_skill_lever/test_scorer.py`): lookup → PASS、C=0.4 → PASS、
  priming のみ → NO_GO (旧型 A vs B 対比では > 0.3 に出ることも同じ test で示す)、一様 null → NO_GO、C=0.2 → NO_GO、
  C=τ → INCONCLUSIVE、d が 0.9/−0.3 に割れる → INCONCLUSIVE、1 arm だけ読まない → INCONCLUSIVE、recency のみ →
  NO_GO、表示位置のみ → NO_GO、C0 ⊥ → INVALID_TB、lever ⊥ → INVALID_TB、族内 ⊥ 差 → INVALID_TB、certification
  無し/古い/未合格・meta 不一致・重複・grid 外・seed・prompt・parse 不一致・call_index 重複・C0 より前の lever・
  記録/meta の schema 違反 (9 + 3 種) → INVALID_SCORER、transport 失敗・行の欠け → not_computed。5 語すべての到達を
  1 つの test でも確認。
- parse の入力クラス (§4 の表) を全て test で pin (`test_parse.py`)。
- battery の機械検査 (`test_battery.py`)、OC 模擬の性質 (`test_power.py`: δ_plant と τ の分離、null で NO_GO、模擬に
  ⊥ gate が効く、効果について単調、模擬の符号反転 p = 判定の `signflip_p`)。
- **変異試験** (`scripts/skill_lever_mutation_check.py`、落ちた test が意図した判定行のものかを照合、no-op・anchor
  不一致は不合格): 34 変異 (foil を反対族に / ⊥ を分母から落とす / 成分条件削除 / 下限を 0 に / PASS 以外を全て NO_GO /
  上限検定を 0 に / 植える効果 = 閾値 / ⊥ gate 3 種 / C0 gate / transport 失敗を ⊥ に / certification・seed・prompt・
  parse・重複・grid・meta の照合削除 / parse 2 種 / 閉じない think / think 除去を正規化の前に / 模擬の gate と下限 /
  C0 先行・call_index 一意性の検査削除 / int 欄の型検査を緩める / schema 違反を例外に落とす / 位置巡回削除 /
  A_rot = A / エントリ順を arm ごとに / 族内 signature 順検査の削除 / num_ctx 不足 / C0 に状態)。全 KILLED が
  certification の条件 (§5-1)。変異中は「commit 済み manifest = 現在のファイル」の test を外す (入れたままだと全変異が
  その test で落ち、生き残りを覆い隠す)。

## 8. 実走と判定の手順 (凍結後、user 裁定)

1. user 裁定で実走を許可する。driver は §2.4 の renderer と §4 の要求条件で呼び出し、1 行 1 sample を
   `results/run/samples.jsonl` に、要求条件を `results/run/meta.json` に書く。C0 を先に全て走らせ、C0 ⊥ 率を確認して
   から lever を走らせる。途中で R・K・prompt・parse を変えない。
2. 判定 = `bash experiments/20260926-skill-lever-pilot/run.sh`。最初に **凍結 manifest** (`manifest.json`、本登録・
   scorer・battery・判定 CLI・変異 harness・power 表生成・manifest 検査・旧 scorer/battery・test・certification・
   power 表・run.sh・SEED の sha256) を照合し、あわせて certification と power 表の記録 sha256 が現在の判定コードと
   一致し、power 表の選定 (R, K) が凍結値と一致することを確かめる。1 つでも違えば判定を計算しない。certification は
   凍結時のものを読むだけで、**実走後に変異 harness を回し直さない** (データを見た後に scorer / test を変えて
   certification を取り直す経路を閉じる、Codex HIGH-2)。その後にだけ判定を計算する (`set -e`、`;` で連結しない)。
   2 回計算して byte 一致。manifest 自体の sha256 は判断 ADR と git 履歴に残す。
3. 凍結前の確認は構造 (件数・型・None の有無) まで。本登録の作成者は凍結時点で実データを 1 件も持っていない。

## 9. claim 境界

- **PASS**: 「この base (qwen3:8b・think=False・persona なし)・この battery・この renderer で、手書きの規則の一覧を
  prompt に置くと、発達中に出現しなかった状況の閉集合選択が、label priming と label の事前傾向を相殺した上で、
  規則の向きに τ = 0.30 を超えて動いた (rule lookup)」まで。経験から育った状態の効果、transfer 一般、思考の分散、
  個体化は主張しない。Stage B は自動で再開しない。
- **NO_GO**: 「この設定では、書かれた規則が選択を τ 以上動かすことは (片側 95% で) 否定される」まで。外部状態一般・
  他の base・persona あり・他の battery には一般化しない。研究方針への含意 (base を変えるか、出力でなく内部状態を
  対象にするか) は別途 user 裁定。
- **INCONCLUSIVE / INVALID**: 測れなかった、まで。効果の有無を書かない。
- 論文の本数・分割を本登録から決めない。

## 10. 記述報告 (判定に使わない)

- C0 の選択分布 (label 別・表示位置別)、位置の偏り。
- 旧型の対比 r_A(g_A) − r_A(g_B) 等 (priming と交絡することを明記)。
- 成分 4 つ、C > 0 の検定 p、arm 別の ⊥ / OOΩ / Ω_q 内の残りの率、C0 と lever arm の差。
- 生テキストが label と厳密一致しなかった率 (冗長な応答の率)。

## 11. 旧 prereg の欠陥への対応

| 旧 prereg の欠陥 | 本登録 |
|---|---|
| DB-1 power が ~0.5 で頭打ち (効果を閾値ちょうどに植えた) | δ_plant = 2τ と τ を分離。NO_GO は同等性型で直接示す。全 verdict 枝に到達 fixture。OC 表を凍結前に計算 |
| DB-3 None の扱いが未定義 | §4 で入力の全クラスを列挙。transport 失敗は ⊥ でなく not_computed |
| DB-4 検査より先に本計算 | run.sh は manifest 照合 → 判定の順、`set -e`。実走後に harness を回し直さない |
| 閾値を lever から導く循環 (δ_min = C_lever/2) | 本 pilot では lever 自体が検定対象なので使わない。τ は user 裁定の literal |
| A vs B 対比が label priming と交絡 (本登録の reimagine で発見) | foil arm (A_rot / B_rot) で priming と事前傾向を相殺 |
