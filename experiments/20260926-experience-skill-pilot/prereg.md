# 事前登録 v3 — 経験由来 Skill pilot: 成否の集計から規則を抽出して、凍結 8B の閉集合選択を動かせるか

本文書は pilot のどの実走よりも**前に**凍結する。
- 凍結前に Codex (gpt-5.5/xhigh) の independent review を受けた。結果と指摘の採否は
  `.steering/20260926-experience-skill-prereg-v3/codex-review.md` と `decisions.md` (ローカル) に記録した。
- 凍結後の変更は本登録の結果とみなさない。凍結 commit と sha256 は判断 ADR
  (`.steering/20260926-experience-skill-prereg-v3/design-final.md`、ローカル) に記録する。

本文書は GPU・実モデル呼び出し・sealed run・spend を authorize しない。pilot の実走 (§8) には、凍結後に別途
user 裁定を要する。

既存の凍結物は変更しない。
- 事前登録 v2 (`experiments/20260926-skill-lever-pilot/prereg.md`、sha256 `7970a598…`) とその凍結 20 本
- 旧 Stage B 事前登録

本登録は v2 の判定式・閾値・probe・layout・seed・実行条件を、そのまま import して使う (§11)。
scoping ADR = `.steering/20260926-experience-skill-scoping/design-final.md` (ローカル)。

## 1. 問い・位置づけ・claim の上限

**問い**: 次の状態を prompt に置くと、凍結 base (qwen3:8b、think=False) の held-out probe 上の閉集合選択が、
**成否の集計が示す向きに**、τ を超えて動くか。
- 族内で行動 label の列が同一で、成否の欄だけが違う
- 経験の記録 = 決定的な合成 episode の、(条件, 行動) ごとの成否集計

- v2 (PASS、C = 0.785、claim = rule lookup) との違いは状態の形 1 変数だけである。
  - v2 の状態 = 規則の一覧 12 行 (成功行だけ)。
  - v3 の状態 = 36 行の成否集計。成功行 12 と失敗行 24。
- v3 の族内の foil は「label 列が同じで成否が反転したもの」である。したがって、選択が向きを持つには、成否の欄と
  weather を結び付けて読む必要がある。「どこかで成功した label を選ぶ」だけの読み方は族内で相殺される (§2.5)。
- **PASS の claim の上限** (§9) = 「**合成の決定的 episode** の成否集計の欄から weather と行動の対応を抽出し、
  発達中に出現しなかった状況の選択に使った (outcome-conditioned rule extraction)」。
  - 「自分の行動履歴から」は主張しない。
  - 揺らぎのある経験の統合・時系列からの集計・transfer 一般・個体化も主張しない。
- PASS しても次の経路は自動で再開しない (再開には別の事前登録が要る)。
  - Stage B
  - weight-space door
  - M13 measurement-line
- 落ちた場合の claim は §9 の分岐表のとおりに絞る。door-close は正当な Done である。

## 2. 設計

### 2.1 battery (v2 のものをそのまま使う)

v2 から次を変えずに使う (`scripts/skill_lever_battery.py` と `scripts/stage_b_battery.py` を import)。
- 状況 signature 18 通り
- 行動 label 6 語彙 (全て 9 文字)
- 発達 signature 12 個・held-out probe 6 個 (互いに素)
- 規則表 A と σ
- 4 arm の規則表
  - A: rain→read_book、clear→walk_path、wind→tend_moss
  - A_rot = A ∘ next
  - B = σ ∘ A
  - B_rot = σ ∘ A_rot
- probe ごとの Ω_q (4 arm の指す選択肢と 1 対 1)
- replicate r の layout
  - Ω_q の表示順を (r + probe 番号) mod 4 だけ巡回
  - 発達 signature の置換 π_r = `default_rng(20260926 + r).permutation(12)`
- decoding seed = 20260926 + 10000·r + 100·probe + k (arm 間で共有)

### 2.2 状態 = 合成経験の成否集計 (実装 = `scripts/skill_experience_battery.py`)

- **試行列**: 発達 signature (weather w) ごとに、正準順 [A(w), σA(w), A(next w)] の 3 行動を各 3 回試行する。
  族 B はその σ 像 [σA(w), A(w), σA(next w)]。LLM は使わない。
- **成否**: arm の規則表で決定的に決まる。arm a は、試行行動 = a(w) なら成功 3 / 失敗 0、それ以外なら成功 0 / 失敗 3。
  各 signature で成功は 1 行。状態は 36 行 (成功 12 / 失敗 24)。
- **1 行の文面**: 「条件: <weather> / <time> / <company> → 行動: <label> (成功 3 / 失敗 0)」、または
  「… (成功 0 / 失敗 3)」。成功行は v2 lever 行と文面が同一 (test で pin)。
- **配置**: block (= 1 signature の 3 行) の順は π_r。block 内は、正準順を (r + j) mod 3 だけ巡回する。
  j は π_r で並べた後の描画順 index であり、正準 signature 番号ではない。
  - 12 block × 巡回 3 なので、**各 r の中で** 成功行の block 内位置が 4/4/4 に均衡する。
  - R によらず成り立つ。r < 12 の全てで検査する。
- **族内の一致**: 族 {A, A_rot} と {B, B_rot} の 2 状態について、次を機械検査する。
  - 成否の欄を正規化で消すと byte 一致する (成否の欄だけが違う)。
  - 試行行動・signature・描画位置の列が族内 (対照を含む) で一致する。
  - 成否の全体頻度が 12/24 である。
- **prompt**: v2 と同じ system prompt と probe 部。user prompt は「これまでの経験の記録:」+ 36 行 + 空行 + probe 部。
  C0 は probe 部のみで、v2 の C0 と byte 一致する。
- **byte 予算**: 描画 prompt の最大は 2,909 byte (r < 12・全 arm・全 probe で計算し test で pin)。
  - 上限は 3,000 byte。3,000 + template 64 + num_predict 32 ≤ num_ctx 4,096 (token 数 ≤ UTF-8 byte 数)。
  - したがって、**切り詰めが起こりえないことを静的に保証**する。
- **非漏洩**: v2 と同じ `integrity_violations` に arm 名 token を加えて検査する。状態・prompt に次を入れない。
  - probe id
  - probe signature から選択肢への対応表
  - arm / stream の識別子

  状態の条件は発達 signature のみ。

### 2.3 arm (9 本)

| arm | 状態 | 役割 |
|---|---|---|
| A / A_rot / B / B_rot | §2.2 の成否集計 (各 arm の規則表で成否が決まる) | **判定** (verdict 5 語) |
| L_A / L_A_rot / L_B / L_B_rot | 対応する判定 arm の状態から、**失敗行の label だけ** を語彙外の filler (`wash_cups` / `fold_mats`、9 文字、parse で ⊥) に置き換えたもの | **長さ・形式の陽性対照** (§9 の claim 分岐にだけ使う) |
| C0 | 状態なし | ⊥ gate と記述報告 |

- 対照 L_x は判定 arm x と同じ選択肢を指し、同じ foil を持つ。判定 arm x との違いは次のとおり。
  - byte 長・行数・成否の欄と配置・巡回は完全に同一 (機械検査)。
  - 違いは失敗行の label だけ。
- 対照の状態では、選択肢 Ω_q に出る label が状態に現れる場合、それは成功行に限る。つまり対照は「v2 の rule lookup を v3 の
  長さ・形式の枠で」測る。
- 対照族 {L_A, L_A_rot} / {L_B, L_B_rot} の相殺は v2 型 (label 多重集合・signature 順・byte 長の一致)。
- 判定 5 語は判定 4 arm だけで決まる。対照の結果は判定 verdict と C を変えない (test で pin)。

### 2.4 replicate と呼び出し順

- 同じ r の中では、全 9 arm が同じ layout と同じ decoding seed 列を共有する。
- 呼び出し順 (凍結):
  1. C0 を全て ((r, probe, k) の辞書順)
  2. 状態 arm は、(r, probe, k) の block ごとに 8 arm を呼ぶ。block 内の arm 順は
     (A, A_rot, B, B_rot, L_A, L_A_rot, L_B, L_B_rot) を、block 通し番号 mod 8 だけ巡回したもの。
     v2 driver DR-2 と同じ考え方で、族内差・判定と対照の差に時間ドリフトが乗らない。
- 各 sample は run 全体の通し番号 `call_index` を持つ。scorer は次を検査する。
  - C0 の全呼び出しが状態 arm より先
  - call_index が一意
  - 呼び出し順が凍結順と矛盾しない

### 2.5 相殺の射程と登録 nuisance 方策 (合成 fixture、`tests/test_skill_experience/test_nuisance.py`)

- **outcome-blind 方策** (成否の欄を読まないもの) は、推定量の単位ごとに**厳密に 0** になる。
  - 例: priming・label の事前傾向・位置・recency・先頭行、成否の欄を消した prompt の任意関数
  - 理由: 族内 2 状態は成否の欄以外が byte 一致し、decoding seed も共有するので、選択が族内で一致し、
    s_a + s_{a'} = 0 となる。
  - fixture で pin した: 上記 4 種 + hash 型の任意方策 3 種で、全単位 d = 0。
- 成否を読むが weather と結び付けない方策は、この定理の範囲外である。個別に C を計算して pin した。
  - 方策は表示された Ω_q の中から決定的に選び、同点は表示順で破る。
  - いずれも NO_GO。

  | 方策 | C (R = 8) |
  |---|---|
  | 成功回数が最多の label / 失敗回数が最少の label / 成功率が最高の label | 0 |
  | 最初の成功行 / 最後の成功行の label | 0 |
  | 成功行の直後の行 / 直前の行の label | −1/12 / +1/12 |
  | 時刻・同伴が probe と一致する signature の成功行 (weather を無視した近傍) | **−1** (foil を指す。保守側) |
  | 陽性対照: weather が一致する成功行 | +1 (PASS) |

- 帰結:
  - 登録した方策の中に、偽 PASS を作るものは無い。
  - 近傍方策は C を負に押す。したがって **NO_GO には「成否は読んだが weather でなく近傍で結び付けた」も含まれうる**
    (§9 の NO_GO claim の範囲内)。
  - 上記以外の読み方まで相殺されることは保証しない。

## 3. estimand (v2 と同じ式)

- **成分** s_{a,r} = (w_a を選んだ数 − foil_a を選んだ数) / (6K)。
  - arm a・replicate r の全 probe × K sample について数える。
  - foil_a = 族内の相手 arm が指す選択肢。
  - ⊥・OOΩ・Ω_q 内の残り 2 選択肢は、分母に含め、w にも foil にも数えない。
- **単位** d_{r,f} = (s_{a,r} + s_{a',r}) / 2 (族 f = {a, a'})。単位は 2R 個。
- **C** = mean d。完全な抽出なら 1 (⊥ 率 b なら 1−b)。outcome-blind なら 0。
- 族内で arm ラベルを入れ替えると d の符号が反転する。したがって、符号反転の全列挙 (2^{2R} 通り、観測を含む、片側)
  で検定する。単位を sample や probe にしない。
- 対照 4 arm にも同じ式を当て、対照の C と verdict を別に出す。

## 4. 実行条件と parse (v2 と同一、凍結)

- 実行条件は v2 と同じ。
  - model `qwen3:8b`、think=False
  - temperature 0.7、top_p 0.8、repeat_penalty 1.0
  - num_ctx 4096、num_predict 32、options.seed を明示
- run はこの要求条件を `meta.json` に記録する。`request_meta()` (v2 と同じ関数) と一致しなければ INVALID_SCORER。
- **R = 8、K = 5** (§6 の power 表の選定)。9 arm × 8 × 6 probe × 5 = **2,160 呼び出し**。
  上限は R_max = 12・K ≤ 20 (user 裁定)。
- 記録の schema は v2 と同一 (1 行 1 JSON object)。
  - 欄は過不足なく、`call_index` / `replicate` / `k` / `seed` (int)、`arm` / `probe_id` / `prompt_sha256` (str)、
    `raw` / `parsed` (str または null)。
  - 型の coercion をしない。
  - 読めない行・欄の過不足・型違い・meta が JSON object でない場合は、例外で止めず INVALID_SCORER
    (reason `record_schema`)。
- parse は v2 の `parse_choice` を import する。入力値の全クラスと扱いは v2 §4 の表のとおり。
  - transport 失敗 (再送 3 回後も失敗) → `raw = null` → run 全体が not_computed (⊥ にしない)
  - NFKC → 小文字化、think tag の除去
  - 6 label のちょうど 1 種 → その label。0 種・2 種以上 → ⊥
  - 語彙内だが Ω_q 外 → OOΩ
- 対照の filler は語彙外なので、応答が filler だけなら ⊥ になる。
- 生テキスト `raw` を全件保存する。記録 `parsed` と再 parse が一致しなければ INVALID_SCORER。

## 5. 判定 rule (verdict は `docs/research-positioning.md` §8 の 5 語のみ)

評価順に適用し、最初に当たったものを verdict とする。**τ = 0.30** (user 裁定、v2 と同じ literal)。α = 0.05。
v2 の C = 0.785 は閾値に使わない。0.785 から閾値を導くと、実測を見てから閾値を選ぶ自由度になる。

1. **INVALID_SCORER** — 次のいずれか。
   - certification (`results/v3_mutation.json`) の不備。
     - 無い、または全変異 KILLED でない。
     - 記録 sha256 が現在の次の 6 ファイルと一致しない。
       - `skill_experience_scorer.py` / `skill_experience_battery.py`
       - `skill_lever_scorer.py` / `skill_lever_battery.py`
       - `stage_b_scorer.py` / `stage_b_battery.py`
   - battery の機械検査に違反。
     - 選択肢の 1 対 1
     - Ω_q の位置の均衡
     - 族内の成否欄以外の byte 一致
     - 成否頻度と成功行の位置の均衡
     - 族内の試行列の共有
     - 対照の構成と対照族の均衡
     - 同 r の probe 部の共有
     - 非漏洩
     - byte 予算
   - 要求条件 `meta.json` が凍結値と不一致。
   - 記録の schema 違反 (§4)。
   - 記録の構造違反。
     - key (arm, r, probe, k) の重複
     - 凍結 grid (9 arm × R × 6 × K) の外の key
     - seed の不一致
     - prompt が凍結 renderer と不一致 (sha256)
     - 記録 parse と再 parse の不一致
     - call_index の重複・負値
     - C0 の終わりより前の状態 arm 呼び出し
     - 呼び出し順が凍結順と矛盾
2. **計算しない** (`status=not_computed`、verdict なし) — 次のいずれか。
   - transport 失敗の記録がある。
   - C0 / 判定 arm の行が欠ける。ただし C0 が揃って C0 gate が落ちた場合は 3 へ。
3. **INVALID_TASK_BATTERY** — 次のいずれか。
   - C0 の ⊥ 率 > 0.2。
   - 判定 4 arm のいずれかの ⊥ 率 > 0.2。
   - 判定族内の ⊥ 率差 ≥ τ/4 = 0.075。
4. **PASS** — 次の両方を満たす。
   - (d − τ) の符号反転検定で p < α (= 片側下限 > τ)。
   - 判定 4 成分 mean_r s_{a,r} がすべて > 0。
5. **NO_GO_EFFECT_ABSENT** — (τ − d) の符号反転検定で p < α (= 片側上限 < τ)。
6. **INCONCLUSIVE_UNDERPOWERED** — それ以外。

- 判定式 (⊥ gate・3 分岐・符号反転) は凍結 v2 scorer の純粋関数 (`bottom_gate_ok` / `decide` / `tests_exact`) を
  import する。
- 4 と 5 は同じ d に対する逆向きの片側検定なので、同時には成立しない。
- C > 0 の検定 p は記述報告にとどめる。
- **対照の verdict**: 対照 4 arm に同じ 3〜6 (対照 4 arm の ⊥ gate を含む) を当てて出す。
  - 対照の行が欠けると、対照は not_computed。
  - 対照の ⊥ gate・欠け・verdict は、判定 verdict に影響しない。

## 6. power と size (凍結前に scorer 実装で計算、`results/power_table.json`)

- power 表は certification と同じ 6 ファイルの sha256 を記録する。manifest 検査は、その一致と、選定 (R, K) =
  scorer の凍結値を確かめる (凍結する判定コードそのもので計算した証拠)。
- **効果の定義**: 表の「真の C」は **clip 後の期待値** である。
  - 模擬 (`skill_experience_scorer.simulate`) の効果モデルは v2 と同じ。
    - arm a・replicate r の名目効果は e = μ + N(0, sd²)。
    - λ = clip(e/(1−b), −1, 1)。
    - ⊥ 以外の質量を (1−|λ|)·base と |λ|·(w または foil の点質量) の混合にする。
  - v2 との違いは、名目値 μ を「(1−b)·E[clip((μ+sd·Z)/(1−b), −1, 1)] = 真の C」となるように補正して植えること
    (閉形式の clipped normal を bisection で解く。Monte Carlo との一致を test で pin)。
  - sd = 0.5・b = 0.1 では、τ = 0.30 を植えるのに名目 0.331、0.60 には 0.723 が要る。
  - 名目値で植えると、真の C が τ を下回り、NO_GO が膨らんで見える (scoping DE-5 / Codex MEDIUM-1)。
  - 表には名目値を併記する (`nominal`)。
- 植える効果量 δ_plant = 2τ = 0.60 と、閾値 τ = 0.30 を別の数にする (DB-1 の修正、v2 と同じ)。
- 攪乱格子 (18 点): base ∈ {uniform, label_skew (1 label に 0.7), position_skew (表示先頭に 0.7)} ×
  ⊥ 率 b ∈ {0, 0.1} × sd ∈ {0.05, 0.3, 0.5}。OOΩ は ⊥ 以外の 5%。
- 条件 (全 18 点で):
  - power: P(PASS | C = δ_plant) ≥ 0.8、P(NO_GO | C = 0) ≥ 0.8。
  - size: P(PASS | C = τ) と P(NO_GO | C = τ) が上限以下。
    - sd ≤ 0.3 の点の上限は α + 3SE (10^4 回で 0.0565。v2 と同じ)。
    - **sd = 0.5 の点の上限は 1.5α = 0.075** (user 裁定)。
- sd = 0.5 の上限を別にする理由: 真の C = τ を植えても、符号反転検定の size は sd = 0.5 で 0.050〜0.061 になる
  (凍結前の模擬、10^4 回)。
  - R を 4〜24 に振っても横ばいで、(R, K) の選択では直せない。
  - 符号反転検定は τ まわりの対称性の検定である。clip で単位分布が歪むと、平均の検定としての size がわずかに
    膨らむ。
  - v2 の上限をそのまま当てると、選定が MC ノイズで決まり、候補が 1 つも通らない可能性がある (DB-1 型の到達不能)。
  - 1.5α はこの既知の膨らみを覆い、粗い破綻 (例: size 0.1) は検出する。
  - この規則は、実データを見る前に、模擬だけから決めた。
    候補 (R, K) の選定を回す前に user 裁定で固定し、全候補・全攪乱に一律に当てる。
    `power_table.json` には、全候補の screening 行 (合否と各条件の値) を残す (Codex MEDIUM-1)。
- 選定規則: (R, K) ∈ {4, 8, 12} × {5, 10, 20} を呼び出し数の少ない順に並べる。2,000 回の screening を通ったものを
  10^4 回で本確認し、最初に全 18 点で通ったものを選ぶ (v2 と同じ手順)。

**screening** (2,000 回、× の理由は最初の違反点):

| (R, K) | 呼び出し | 判定 | 理由 |
|---|---|---|---|
| (4, 5) | 1,080 | × | sd=0.5 で power 不足 (例: uniform・b0 で P(NO_GO\|0) = 0.68) |
| (4, 10) | 2,160 | × | 同上 (P(NO_GO\|0) = 0.70) |
| (8, 5) | 2,160 | ○ | |
| (12, 5) | 3,240 | ○ | |
| (4, 20) | 4,320 | × | sd=0.5 で power 不足 |
| (8, 10) | 4,320 | × | position_skew・b0.1・sd0.3 で P(PASS\|τ) = 0.066 (上限 0.0646) |
| (12, 10) | 6,480 | × | uniform・b0.1・sd0.3 で P(PASS\|τ) = 0.0655 |
| (8, 20) | 8,640 | × | uniform・b0.1・sd0.05 で P(PASS\|τ) = 0.066 |
| (12, 20) | 12,960 | × | sd0.3 の 2 点で P(PASS\|τ) = 0.0675 / 0.0685 |

- 読み: R が 4 だと、sd = 0.5 で power が足りない。
- K が大きい候補は、sd ≤ 0.3 でも size が上限付近になった。
  - K が大きいと多項の揺らぎが小さく、clip による単位分布の歪みが見えやすくなる。
  - 2,000 回の MC の揺らぎ (SE ≈ 0.005) と区別できない境界である。
- 規則は呼び出し数の少ない順に最初の合格を採るので、選定は (8, 5) で止まる。

**本確認 (R = 8、K = 5、10^4 回) の全 18 点**:

| sd | P(PASS\|0.6) 最悪 | P(NO_GO\|0) 最悪 | P(PASS\|τ) 最大 | P(NO_GO\|τ) 最大 | 上限 |
|---|---|---|---|---|---|
| 0.05 | 0.984 | 0.984 | 0.049 | 0.048 | 0.0565 |
| 0.3 | 0.981 | 0.982 | 0.052 | 0.052 | 0.0565 |
| 0.5 | 0.948 | 0.933 | 0.058 | 0.046 | 0.075 |

→ **R = 8、K = 5 を凍結**。9 arm × 8 × 6 × 5 = 2,160 呼び出し (v2 の 1,200 の 1.8 倍)。

**OC 曲線** (R = 8、K = 5、10^4 回、真の C = clip 後の期待値。PASS / NO_GO / INCONCLUSIVE / INVALID_TB):

| 真の C | uniform・b0・sd0.05 | label_skew・b0.1・sd0.3 | label_skew・b0.1・sd0.5 |
|---|---|---|---|
| 0.0 | 0.000 / 1.000 / 0.000 / 0.000 | 0.000 / 0.982 / 0.001 / 0.017 | 0.000 / 0.933 / 0.050 / 0.017 |
| 0.1 | 0.000 / 1.000 / 0.000 / 0.000 | 0.000 / 0.928 / 0.056 / 0.015 | 0.000 / 0.701 / 0.285 / 0.015 |
| 0.2 | 0.000 / 0.984 / 0.016 / 0.000 | 0.000 / 0.485 / 0.499 / 0.015 | 0.004 / 0.281 / 0.698 / 0.016 |
| 0.3 | 0.047 / 0.043 / 0.911 / 0.000 | 0.047 / 0.052 / 0.886 / 0.015 | 0.053 / 0.046 / 0.887 / 0.015 |
| 0.4 | 0.981 / 0.000 / 0.020 / 0.000 | 0.457 / 0.000 / 0.526 / 0.017 | 0.319 / 0.002 / 0.663 / 0.016 |
| 0.5 | 1.000 / 0.000 / 0.000 / 0.000 | 0.914 / 0.000 / 0.068 / 0.018 | 0.757 / 0.000 / 0.225 / 0.017 |
| 0.6 | 1.000 / 0.000 / 0.000 / 0.000 | 0.981 / 0.000 / 0.003 / 0.016 | 0.965 / 0.000 / 0.020 / 0.015 |

- 読み: 攪乱が大きいと、0.1〜0.5 の中間の効果は INCONCLUSIVE に落ちやすい。
- INVALID_TASK_BATTERY の約 1.5% は、b = 0.1 で判定族内の ⊥ 率差が偶然 0.075 を超える分である
  (v2 と同じく、設計上のコストとして受け入れる)。
- 格子外の攪乱では power が下がり、INCONCLUSIVE に落ちる。それは NO_GO でも PASS でもない、と正直に報告する。
- 対照 4 arm は判定 4 arm と同じ推定量・同じ K・同じ R なので、同じ効果モデルの下で同じ OC を持つ
  (対照の power は別途計算しない)。

## 7. 検査器の Done 条件 (CPU、実モデル不使用)

- **全 verdict 枝に到達する合成 fixture** (`tests/test_skill_experience/test_scorer.py`)。
  - PASS: 抽出どおり、C = 0.4
  - NO_GO: 一様 null、C = 0.2
  - INCONCLUSIVE: C = τ、d が割れる、1 arm だけ読まない
  - INVALID_TASK_BATTERY: C0 ⊥、判定 arm ⊥、族内 ⊥ 差
  - INVALID_SCORER: certification の無し・古い・未合格・6 ファイルのいずれかを含まない、battery 違反、meta 不一致、
    重複、grid 外、seed、v2 renderer の prompt、parse 不一致、C0 より前の状態 arm、呼び出し順、call_index 重複、
    記録 / meta の schema 違反
  - not_computed: transport 失敗、判定行の欠け、C0 行の欠け
  - 5 語すべての到達を 1 つの test でも確認する。
- **対照と claim 分岐**: 次の 4 つと、分岐表の全行を fixture で確認する。
  - 判定 NO_GO ∧ 対照 PASS → 長さ・形式で説明されない側の claim
  - 対照 NO_GO → 絞った claim
  - 対照 ⊥ は対照だけに効く
  - 対照行の欠けは判定を変えない
- **登録 nuisance** (§2.5、`test_nuisance.py`)。
- **battery の機械検査** (`test_battery.py`)。
  - 族内一致・位置均衡・対照の構成は、「わざと壊した状態を捕まえる」陽性対照 test を添える。
  - 成功行 = v2 lever 行も確認する。
- **OC 模擬の性質** (`test_power.py`)。
  - clip 後の期待値の閉形式 = Monte Carlo
  - 名目値の逆算
  - clip 補正で τ での PASS/NO_GO がほぼ対称になる
  - δ_plant と τ の分離
  - null で NO_GO
  - 模擬に ⊥ gate が効く
  - sd = 0.5 で R について単調に 0.8 を超える (頭打ちが無い)
  - size 上限の規則
- **変異試験** (`scripts/skill_experience_mutation_check.py`)。
  - 落ちた test が意図した判定行のものかを照合する。no-op・anchor 不一致は不合格。
  - v3 固有の変異 52 本 (scorer 39・battery 13)。
    - 推定量: 対照 arm の写像なし / ⊥ を分母から
    - 判定: 下限を 0 に / PASS 以外を NO_GO / 成分条件の削除
    - 対照: 判定を対照で / 対照を判定で / 対照 PASS 条件の削除 / claim に対照を渡さない / 対照 ⊥ を判定に効かせる /
      対照の欠けを検査しない
    - ⊥ gate 2 種
    - transport を ⊥ に
    - not_computed の欠け検査 2 種 (C0 行・判定 arm 行)
    - INVALID_SCORER の照合削除 16 種 (certification・v2 scorer の包含・旧 Stage B battery の包含・battery・meta・seed・renderer・
      v2 renderer で期待値・parse・重複・grid・C0 先行・call_index・呼び出し順・block 内の arm 巡回・schema)
    - 模擬: clip 補正の削除 / 閉形式の sd 項 / 模擬の ⊥ gate / 模擬の下限 / sd 広域の上限 2 種 / 選定条件
    - battery: 巡回の削除 / 巡回の block 番号 / 成否の label 固定 / 失敗行の削除 (v2 への退化) / 族内の試行列ずらし /
      族内一致検査の削除 / 位置均衡検査の削除 / filler を語彙に / 対照の置き換え削除 / 対照検査の削除 /
      byte 予算検査の削除 / 成功行の文面 / C0 に状態
  - **全 KILLED が certification の条件** (§5-1)。
  - import する v2 の純粋関数は変異させない。v2 certification (34 変異、全 KILLED) が既に kill を確認しており、
    本 certification はそれらの sha256 に結び付ける。
  - 変異中は「commit 済み manifest = 現在のファイル」の test を外す。

## 8. 実走と判定の手順 (凍結後、user 裁定)

1. user 裁定で実走を許可する。
   - driver は §2.2〜2.4 の renderer・呼び出し順と §4 の要求条件で呼び出す。
   - 1 行 1 sample を `results/run/samples.jsonl` に、要求条件を `results/run/meta.json` に書く。
   - C0 を先に全て走らせ、C0 ⊥ 率を確認してから状態 arm を走らせる。C0 が落ちたら状態 arm は走らせず、調整もしない。
   - 途中で R・K・prompt・parse を変えない。
2. 判定 = `bash experiments/20260926-experience-skill-pilot/run.sh`。
   - 最初に **凍結 v2 manifest** を照合する。
   - 次に **凍結 v3 manifest** (`manifest.json`) を照合する。
     - 対象: 本登録・v3 の判定コード・判定 CLI・変異 harness・power 表生成・manifest 検査・import する v2 /
       旧資産 4 本・test・certification・power 表・run.sh・SEED の sha256
     - あわせて、certification と power 表の記録 sha256 が現在の判定コードと一致し、power 表の選定 (R, K) が
       凍結値と一致することを確かめる。
   - 1 つでも違えば判定を計算しない。
   - certification は凍結時のものを読むだけで、実走後に変異 harness を回し直さない。
   - その後にだけ判定を計算する (`set -e`、`;` で連結しない)。2 回計算して byte 一致を確かめる。
3. 凍結前の確認は構造 (件数・型・None の有無) までに限る。本登録の作成者は、凍結時点で実データを 1 件も持っていない。

## 9. claim 境界 (判定 verdict と対照 verdict の分岐、`claim_branch`)

| 判定 verdict | 対照 verdict | claim_branch | 書いてよい範囲 |
|---|---|---|---|
| PASS | (問わない、記述報告) | `pass_outcome_conditioned_rule_extraction` | 下の PASS の文 |
| NO_GO | PASS | `no_go_not_explained_by_length_or_format` | 下の NO_GO の文 + 対照の文 |
| NO_GO | NO_GO / INCONCLUSIVE / INVALID_TASK_BATTERY / not_computed | `no_go_this_renderer_only` | 下の NO_GO の文のみ |
| INCONCLUSIVE / INVALID | — | (なし) | 測れなかった、まで |

- **PASS**: 次の範囲まで。
  - 「この base (qwen3:8b・think=False・persona なし)・この battery・この 36 行の renderer で、**合成の決定的
    episode** の成否集計を prompt に置いた。」
  - 「すると、発達中に出現しなかった状況の閉集合選択が、成否の集計が示す向きに τ = 0.30 を超えて動いた
    (outcome-conditioned rule extraction)。」
  - 「このとき、label の出現・事前傾向・位置など成否の欄を読まない寄与は相殺した。」

  主張しないもの:
  - 自分の行動履歴からの学習
  - 揺らぎのある経験の統合
  - 時系列からの集計
  - transfer 一般
  - 個体化

  Stage B は自動で再開しない。
- **NO_GO**: 「**この 36 行・決定的成否集計の renderer では**、成否の集計が示す規則が選択を τ 以上動かすことは
  (片側 95% で) 否定される」まで。
  - 「v2 で効いていたのは label の有無だった」とは書かない。
  - 近傍方策 (§2.5、C = −1) による負の押し下げも、この範囲に含まれうる。
- **対照の文** (対照 PASS のときのみ): 次のとおりに書く。
  - 「同じ行数・長さ・成否の欄と配置を持ち、失敗行の label だけが選択肢外の filler である状態では、同じ規則が
    τ を超えて選択を動かした。」
  - 「したがって、この renderer での不達は、長さ・行数・形式だけでは説明されない。」
  - 「不達は、失敗行の label が選択肢内の label として競合する条件では、この base が成否の欄と weather を用いた
    抽出に到達しなかったことと整合する。」

  書かないもの:
  - 「成否の欄を読めない」と断定すること。対照は失敗行の label を語彙外にするので、失敗 label の語彙内競合・
    抑制・salience の変化も同時に変わる。それらと成否の読み取りは、この対照では分けられない (Codex HIGH-1)。
  - 他の base・persona あり・他の renderer への一般化
  - 研究方針への含意 (base を変えるか、内部状態を対象にするか)。これは別途 user 裁定。
- **INCONCLUSIVE / INVALID**: 「測れなかった」までにとどめ、効果の有無を書かない。
- 論文の本数・分割を本登録から決めない。

## 10. 記述報告 (判定に使わない)

- C0 の選択分布 (label 別・表示位置別) と、位置の偏り。
- 判定 4 成分と対照 4 成分、C > 0 の検定 p。
- arm 別の ⊥ / OOΩ / Ω_q 内の残りの率。filler を答えた率 (対照)。
- C_v3 / C_v2 と成分別の差。v2 (C = 0.785) は別 run で、実行条件・probe・layout・seed は同一。記述上の上限
  anchor であって、判定には使わない。
- 対照 C − 判定 C (失敗行の label が選択肢と競合することの効果の記述)。
- 生テキストが label と厳密一致しなかった率。

## 11. v2 からの差分と流用

| 項目 | v3 |
|---|---|
| 状態 | 規則一覧 12 行 → 成否集計 36 行 (§2.2)。成功行の文面は同一 |
| 族の foil | label 集合を回す → 同じ試行列で成否だけを回す。outcome-blind 方策の相殺が、登録 class から定理の形に強まる (§2.5) |
| 対照 | 新設: 長さ・形式の陽性対照 4 arm (§2.3、scoping Codex HIGH-1) |
| 判定式・τ・α・⊥ gate・parse・実行条件・probe・layout・seed | v2 の凍結関数・値を import (変更なし) |
| (R, K) | (4, 10) → (8, 5)。格子に sd = 0.5 を追加し、真の C を clip 後の期待値で定義 (§6) |
| size 条件 | sd ≤ 0.3 は v2 と同じ α + 3SE。sd = 0.5 は 1.5α (§6、user 裁定) |
| 呼び出し順 | C0 先行に加え、block 内巡回の凍結順を検査 (v2 driver DR-2 を判定側で強制) |
| v2 の欠陥の反省 (DB-1・DB-3・DB-4・閾値の循環) | v2 §11 の対応をそのまま継承。加えて、sd = 0.5 で size の選定が MC ノイズで決まる到達不能を、凍結前に模擬で発見し、規則として固定した |
