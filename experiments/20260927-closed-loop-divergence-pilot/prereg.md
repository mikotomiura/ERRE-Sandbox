# 事前登録 v4 — 閉ループ分散 pilot: 同一 base から、自分で採取した経験状態で、エージェント間の選択を分岐させられるか

本文書は、pilot のどの実走よりも**前に**凍結する。
- 凍結前に Codex (gpt-5.5/xhigh) の independent review を 2 回受けた。結果と、指摘ごとの採否は次に記録した (いずれもローカル)。
  - `.steering/20260927-closed-loop-prereg-v4/codex-review.md` (1 回目: HIGH 1・MEDIUM 3・LOW 1、全て反映)
  - `.steering/20260927-closed-loop-prereg-v4/codex-review-2.md` (2 回目: HIGH 0・MEDIUM 2・LOW 1、全て反映)
  - 同 dir の `decisions.md` (DC4-1〜5、DC5-1〜3)
- 凍結後に変更したものは、本登録の結果とみなさない。
- 凍結 commit と manifest の sha256 は、判断 ADR (`.steering/20260927-closed-loop-prereg-v4/design-final.md`、ローカル) に記録する。

本文書は、GPU・実モデル呼び出し・sealed run・spend を authorize しない。
- driver を書くことと実走 (§8) には、凍結後に別途 user 裁定を要する。

既存の凍結物は変更しない。
- 事前登録 v2 と、その凍結 20 本
- 事前登録 v3 と、その凍結 22 本
- 旧 Stage B の事前登録
- `src/erre_sandbox/evidence/`

設計の正本は scoping ADR `.steering/20260927-closed-loop-divergence-scoping/design-final.md` (FROZEN、ローカル)。
- 本登録は、ADR の推定量・閉ループの構成・判定の枠・claim の上限を写す。
- ADR から逸脱した点は、user 裁定 3 件 (DU-1・DU-2・DU-3) だけである (§2.5・§6)。

## 1. 問い・位置づけ・claim の上限

**目標** (user 明言 2026-09-27): 全員が同一の base (qwen3:8b、think=False、重みは共有) を使い、prompt に置く状態の違いによってエージェント間の選択を分岐させる。

**問い**: 自分の行動と、その結果から育てた状態を prompt に置いたとき、held-out probe での閉集合選択が、族内のエージェント間で、**自分の経験の向きに** τ を超えて分かれるか。
- 族内のエージェントは、同一の base・空の初期状態・同じ system prompt から始まる。
- 違うのは、経験する世界 (決定的な成否規則) だけである。

**前段との違い**:
- v2 (PASS、C = 0.785) と v3 (INCONCLUSIVE) は、状態を**外から与えた**。
- 本件では、各エージェントが自分で状態を採取する。
  - 自分の選択 → 環境が成否を返す → 決定的な aggregator が状態を更新する。
- したがって、状態は経路とともに育つ (閉ループ)。

**CLD との区別** (ADR §0):
- 分散の源は、実走の全期間にわたって違う、外生の環境規則である。
- 量は、終点での族内の符号付き対比である。
- 同じ世界で seed・摂動・初期 prompt だけが違う状態や、エージェント間距離の時間に対する傾きは、分散の源にも指標にも使わない (停止規則)。
- 「経路依存」は claim にしない。

**PASS の claim の上限**は §9 のとおり。
- 抽出を行うのは aggregator である。モデルが outcome から規則を抽出したことは主張しない。
- PASS しても、次は自動では再開しない (再開には別の事前登録が要る)。
  - CLD
  - Stage B
  - weight-space door
  - M13 measurement-line
- door-close は正当な Done である。

## 2. 設計

### 2.1 世界と battery (v2 のものをそのまま使う)

v2 から次を変えずに使う (`scripts/skill_lever_battery.py` と `scripts/stage_b_battery.py` を import)。
- 状況 signature 18 通り
- 行動 label 6 語彙
- 開発 signature 12 個・held-out probe 6 個 (互いに素)
- 4 つの規則表 (世界)
  - A: rain→read_book、clear→walk_path、wind→tend_moss
  - A_rot = A ∘ next
  - B = σ ∘ A
  - B_rot = σ ∘ A_rot
- probe の Ω_q (4 世界の規則が指す選択肢と 1 対 1)
- replicate r の layout
  - Ω_q の表示順: (r + probe 番号) mod 4 だけ巡回
  - 開発 signature の置換 π_r
- probe の decoding seed = `sample_seed(r, probe, k)`

**世界 = ペルソナ** (ADR D2):
- ペルソナは、経験する世界だけで個体化する。
- persona YAML も初期の種も使わない。
- 族は {A, A_rot} と {B, B_rot}。
- 世界名は prompt に出さない (非漏洩の機械検査)。

### 2.2 状態と renderer (実装 = `scripts/closed_loop_battery.py`)

**状態** = aggregator が更新する次の 2 つ。
- 成功した開発 signature の集合
- 試した (signature, 行動) の集合

成否は決定的である (ADR D3)。
- 行動 = 世界の規則[weather] のとき成功、それ以外は失敗。
- ⊥ と Ω 外も失敗とする。
- ⊥ は試行に数えない (行動が無い)。語彙内の label は、Ω 外でも試行に数える。

**renderer** = **R1+** (§6 の選定。ADR の予備。ADR は R1 と R1+ の選択を模擬に委ねている)。
- R1+ は 2 節から成る。
- 節 1 は R1 の行と byte 一致する (機械検査)。
  ```
  これまでの経験の記録:
  成功した行動:
  条件: <weather> / <time> / <company> → 行動: <label> (成功あり)
  …
  試した行動 (成否を問わない):
  条件: <weather> / <time> / <company> → 試した: <label>、<label>
  …
  ```
- 行の順:
  - 行の順は π_r に固定する。変わるのは行の有無だけである。
  - 試した label の並びは語彙の順にする (試した順は recency を持ち込むので使わない)。
- 空の節は `(なし)` と書く。
- R1 (選ばれなかった primary) の空状態は `(成功した記録はない)`。
- 行の文言は、真実で、回数を含まない固定の形にする。
  - 「成功あり」は、その signature でその行動が 1 回以上成功したことを表す。
  - 「試した」は、1 回以上選んだことを表す。成否は問わない。
  - **R1+ では、ある signature で「試した」のに「成功した行動」に無い行動が失敗だったことを、消去法で推定できる**。これは §9 の claim で扱う。
- **byte 予算**:
  - 描画 prompt の最大は 2,504 byte。r < 12・両 renderer・全世界で、全て成功かつ全語彙を試行した状態を含めて計算し、test で pin した。
  - 上限は 3,000 byte。3,000 + template 64 + num_predict 32 ≤ num_ctx 4,096 なので、切り詰めが起こりえないことを静的に保証する。
- **非漏洩**: v2 と同じ `integrity_violations` に、世界名の token を加えて検査する。状態には次を入れない。
  - probe signature
  - probe id
  - probe から選択肢への対応
  - 世界名

### 2.3 ループ段 (ADR D4)

- replicate r・世界 w ごとに、開発 12 signature を π_r 順に **M = 4** 周する (T = 48 ステップ、§6 の選定)。
- ステップ t の状況 = π_r の (t mod 12) 番目。
- 選択肢 Ω_dev = 4 世界の規則が、その weather に指す 4 行動。表示では正準順を (r + t) mod 4 だけ巡回する。
  - 各周の中で、巡回量 0〜3 はそれぞれ 3 回ずつ使われる (機械検査)。
  - weather ごとの位置の均衡は保証しない。その位置効果は、power 模擬で実際の巡回として扱う。
- **prompt** = 状態ブロック + 空行 + 状況部。状況部は v2 の probe 部と同じ書式 (test で byte 一致を pin)。
- **seed** = `loop_seed(r, t) = 21,260,926 + 1000·r + t`。
  - 世界を引数に取らないので、4 世界で共有する (共通乱数)。
  - probe の seed とは値域が互いに素 (r < 12・t < 48 と r < 12・q < 6・k < 20 の全組で検査)。
- 最後の周の後、held-out の 6 probe × K を v2 と同じ seed・同じ回転で引く。probe の回答は状態に戻さない。
- **N0 = C0**: 状態ブロック無しで probe を引く。v2 の C0 と byte 一致する。
  - 定理 (§2.5) から、状態を育てない arm は C ≡ 0 である。
  - したがって、推定の対照にはせず、C0 の ⊥ gate と記述にだけ使う (ADR D6)。

### 2.4 呼び出し plan (凍結順、`closed_loop_battery.plan`)

1. C0 を全て呼ぶ ((r, probe, k) の辞書順)。
2. replicate r ごとに次を呼ぶ。
   - ループ段: t = 0..47 の各 t で、4 世界を `world_order(r)` の順に呼ぶ。
     - `world_order(r)` = (A, A_rot, B, B_rot) を r mod 4 だけ巡回した順。
   - probe 段: (probe, k) の各 block で、同じ順に呼ぶ。
   - 世界を跨いで同じ (r, t) を隣接して呼ぶ (interleave)。世界の順は replicate ごとに回転する。
     R = 8 なら、各世界が block 内の各位置に 2 回ずつ来る (機械検査)。
3. 最後に、決定性の replay として r ごとに 9 件を呼ぶ (§10)。判定には使わない。

**call_index の規則**:
- call_index = plan の中での位置。
- 記録は plan の接頭辞でなければならない。

**driver の要件** (driver は本登録の範囲外。仕様だけ登録する):
- 送信する body は、記録済みの履歴[:t] から同じ renderer で再計算したものとする。
- transport 失敗 (再送 3 回後も失敗) が起きたら、その記録を最後に run を止める。
- 再開はしない。

呼び出し数 = R (30K + 48M) + 9R = 8 × (150 + 192) + 72 = **2,808** (判定に使うのは 2,736)。

### 2.5 相殺の射程と fixture 表 (ADR §3.1、`results/fixture_table.json`)

**定理** (state-blind):
- 族内の 2 エージェントは、空の初期状態・system prompt・signature 順・表示回転・decoding seed 系列を共有する。
- 状態を読まない方策 (状況・選択肢・seed だけの関数) は、両世界でループ段の行動列が一致する (t に関する帰納法)。
- probe でも同じ seed なので同じ選択になり、s_a + s_a′ = 0 が単位ごとに厳密に成り立つ。
- test で次の 3 種について、両 renderer・全単位で d = 0 を pin した。
  - seed → 表示位置
  - 語彙の事前順位
  - 状況と seed の hash
- R1+ では、行があるかどうかが outcome に由来する。したがって、定理は state-blind 止まりである。

**状態を読むが weather に結び付けない方策**は、fixture 表として登録し、C_loop への寄与を模擬で固定した。
- 方策は状態テキストを読み、表示された選択肢から決定的に選ぶ。同点は表示順で破る。
- 候補が無ければ base から引く。
- 登録した方策:
  - F1 状態内で最多の label
  - F2 最初の行の label
  - F3 最後の行の label
  - F4 行数 mod 4 番目の位置
  - F5 空か否か
  - F6 label × 位置
  - F7 自分の直前の選択の反復
  - F8 weather を無視した近傍 (時刻・同伴が一致する成功行)
  - F9〜F11 状態テキストの hash 3 種
  - F12 試行回数が最少の label (R1+)
  - F13 試行回数が最多の label (R1+)
  - 陽性対照 P: weather が一致する成功行の lookup
- 計算の範囲:
  - base 4 種
  - mode P: dev 段は植えた方策 κ ∈ {0, κ_τ, κ_2τ}、probe 段は fixture
  - mode L: 両段で確率 ρ ∈ {0.5, 1} で fixture
  - 各 250 反復 × R
- **gate (user 裁定 DU-1・DU-3)**: 正側だけに掛け、2 段にする。
  - 硬い gate: 登録 fixture の (mean + 3SE) の最大 < τ/2 = 0.15 (2 つ重なっても τ に届かない)。
  - 列挙: (mean + 3SE) ≥ τ/4 = 0.075 の fixture は、scorer の凍結定数 `FLAGGED_FIXTURES` に列挙し、
    PASS の文に注記を必ず入れる (§9)。manifest 検査は、fixture 表の rows から gate と列挙を再計算し、
    表の要約欄と scorer の定数に一致することを確かめる。
  - 経緯: ADR の gate は「最大 < τ/4」だった。再生成した表で F1 が 1 設定だけこれを超え、R1+ がすでに
    ADR の予備だったので、止めて user に報告し、裁定 DU-3 で 2 段にした。
  - 結果: 硬い gate: 最大は F1_most_label (measured・mode P・C=0.6) の mean +0.0786・SE 0.0032・mean + 3SE = 0.0883 < τ/2 = 0.15。τ/4 = 0.075 以上の列挙 = ['F1_most_label']。**硬い gate は合格**。
  - F1 が正になるのは、dev 段が状態を読めている (κ が大きい) ときだけである。R1+ の状態テキストで最も多く
    現れる label は自分の規則なので、weather を見ずに最多 label を選んでも、自分の経験の向きに少し寄る。
    経験に由来するが weather に結び付かない弱い信号であり、単独では τ に届かない。
  - fixture ごとの要約 (全 20 設定 = base 4 × mode P の 3 + mode L の 2):

| fixture | mean の最小 | (mean + 3SE) の最大 |
|---|---|---|
| F1_most_label | -0.0692 | +0.0883 |
| F2_first_row | -0.0729 | +0.0270 |
| F3_last_row | -0.0490 | +0.0325 |
| F4_line_count | -0.0034 | +0.0070 |
| F5_nonempty | +0.0000 | +0.0000 |
| F6_label_x_position | -0.0333 | +0.0221 |
| F7_repeat_previous | -0.0109 | +0.0026 |
| F8_neighbor | -0.9719 | -0.1527 |
| F9_hash_a | -0.0035 | +0.0188 |
| F10_hash_b | -0.0104 | +0.0064 |
| F11_hash_c | -0.0018 | +0.0346 |
| F12_least_tried | -0.0144 | +0.0101 |
| F13_most_tried | +0.0000 | +0.0321 |
| P_lookup | +0.3130 | +0.9983 |

- **負の寄与は gate に掛けない**。
  - F8 近傍は、battery の構造 (A_rot = A ∘ next) から、常に族の foil を指す: 最も負なのは F8_neighbor (uniform・mode P・C=0.6) の mean -0.9719。
  - ADR の |·| の gate は、ADR 自身が必須にした F8 によって到達不能になる。そこで user 裁定で、gate を正側に限った。
  - 負の寄与は、§9 の NO_GO の claim の範囲に含める (「成否を読んだが、weather でなく近傍で結び付けた」も NO_GO に含まれうる)。
- 帰結:
  - 登録した方策の中に、τ/2 以上の偽の正方向を作るものは無い。τ/4 を超えたのは F1 だけで、PASS の文に明記する。
  - 上記以外の読み方まで相殺されることは保証しない。

## 3. estimand (v2 と同じ式、ADR §1)

- **成分**: s_{a,r} = (t_a を選んだ数 − t_{a′} を選んだ数) / (6K)。
  - t_a = 世界 a の規則が指す選択肢。a′ = 族の相方。
  - ⊥ と Ω 外は分母に含め、分子に数えない。
- **単位**: d_{r,f} = (s_{a,r} + s_{a′,r}) / 2。単位は 2R 個。
- **C_loop** = mean d。
- **TV 下界**:
  - probe ごとに、E[d] = (x + y)/2 ≤ TV(P_a, P_a′) が成り立つ。
  - よって C_loop は、**held-out probe 上の、族内エージェント間の選択分布 TV に対する、向きの付いた下界** (期待値の意味で) である。
  - 本文・後続文書では、常にこの限定を付けて呼ぶ。内部状態や「思考」一般の距離とは呼ばない。
- **検定**:
  - 族内で世界ラベルを入れ替えると d の符号が反転する。
  - そこで、符号反転の全列挙 (2^{2R} 通り、観測を含む、片側) で検定する。
  - 厳密なのは C = 0 の null に対してだけである。
  - τ 判定 (`signflip_p(d − τ)`) は、d が τ について対称であることを仮定する。
    - したがって、τ 判定は **対称性の仮定と、OC 模擬で校正した判定** として扱う (ADR §1 の 2)。
    - 校正は §6 で、閉ループが生む単位分布の下で行った。

## 4. 実行条件・記録・parse・連鎖 replay

**実行条件**は v2 と同じ。
- model `qwen3:8b`、think=False
- temperature 0.7、top_p 0.8、repeat_penalty 1.0
- num_ctx 4096、num_predict 32、options.seed を明示
- run はこの要求条件を `meta.json` に記録する。`request_meta()` と一致しなければ INVALID_SCORER。

**R = 8、K = 5、M = 4、renderer = R1+** (§6 の選定)。

**記録** (1 行 1 JSON object、欄は過不足なし、型の coercion をしない):
- 欄: `call_index` / `replicate` / `seed` (int)、`phase` / `world` / `prompt_sha256` (str)、`step` (int または null)、`probe_id` (str または null)、`k` (int または null)、`raw` / `parsed` (str または null)。
- phase と欄の組み合わせ:
  - `loop`: step を持ち、probe_id / k は null。
  - `c0` と `probe`: probe_id / k を持ち、step は null。
  - `replay`: 元の呼び出しの key を持つ。
- **成否は記録しない**。driver の申告を使わず、scorer が導出する。
- 読めない行・欄違い・型違い・phase との不整合・meta が object でない場合は、INVALID_SCORER (reason `record_schema`)。

**parse** は v2 の `parse_choice` を import する。
- NFKC → 小文字化 → think tag の除去 → 6 label のうち、ちょうど 1 種ならそれ。それ以外は ⊥。
- 生テキスト `raw` を全件保存する。記録の `parsed` と再 parse が一致しなければ INVALID_SCORER。

**連鎖 replay** (ADR §3.3): scorer は (世界, r) ごとに次を行う。
1. 状態を空で始める。
2. t の順に、記録した行動と世界の規則と renderer から prompt を再構成し、sha256 を記録と照合する。
3. 成否を導出し、状態を更新する。
4. ループが完了したら、終状態から描いた probe の prompt も照合する。
- C0 の prompt と、replay の prompt (元の呼び出しと同一) も照合する。
- 不一致があれば INVALID_SCORER (reason `chain_replay`)。

## 5. 判定 rule (verdict は `docs/research-positioning.md` §8 の 5 語のみ)

評価順に適用し、最初に当たったものを verdict とする。**τ = 0.30** (user 裁定、v2/v3 と同じ literal)。α = 0.05。

1. **INVALID_SCORER** — 次のいずれか。
   - certification (`results/v4_mutation.json`) の不備。
     - 無い、または全変異が KILLED でない。
     - 記録 sha256 が、現在の次の 7 ファイルと一致しない。
       - `closed_loop_{scorer,battery,sim}.py`
       - `skill_lever_{scorer,battery}.py`
       - `stage_b_{scorer,battery}.py`
   - battery の機械検査に違反。
     - 選択肢の 1 対 1・Ω_q の位置の均衡・Ω_dev
     - seed の互いに素
     - 空状態と R1 ⊂ R1+
     - C0 = v2・世界順の均衡
     - 非漏洩・byte 予算
   - 要求条件の不一致。
   - 記録の schema 違反。
   - **schedule 監査**。
     - 記録が凍結 plan の接頭辞でない (call_index の欠番・重複、key の不一致を含む)。
     - seed の不一致。
     - transport 失敗の後に記録が続く。
   - 再 parse の不一致。
   - **連鎖 replay** の不一致。
2. **計算しない** (`status=not_computed`、verdict なし) — 次のいずれか。
   - transport 失敗の記録がある。
   - C0 が揃っていない。
   - 判定に使う本体 (ループと probe) が揃っていない。ただし、C0 が揃って C0 gate が落ちた場合は 3 へ進む。
   - replay の欠けは判定を止めない。
3. **INVALID_TASK_BATTERY** — 次の順に見る。
   - C0 の ⊥ 率 > 0.2。
   - いずれかの世界の、ループ段の ⊥ 率 > 0.2。
   - probe の `bottom_gate_ok` 違反 (世界ごとに ⊥ ≤ 0.2、判定族内の ⊥ 率差 < τ/4 = 0.075)。
4. **PASS** — (d − τ) の符号反転検定で p < α、かつ 4 成分 mean_r s_{a,r} がすべて > 0。
5. **NO_GO_EFFECT_ABSENT** — (τ − d) の符号反転検定で p < α。
6. **INCONCLUSIVE_UNDERPOWERED** — それ以外。

補足:
- 判定式 (⊥ gate・3 分岐・符号反転・成分) は、凍結 v2 scorer の純粋関数 (`bottom_gate_ok` / `decide` / `tests_exact` / `component_scores` / `family_units`) を import する。
- **coverage は verdict gate にしない** (ADR D8)。記述と claim_branch にだけ使う (§9)。

## 6. power と size (凍結前に、判定と同じコードで計算、`results/power_table.json`)

- power 表は、certification と同じ 7 ファイルの sha256 を記録する。
- manifest 検査は、その一致と、選定 (renderer, R, K, M) = scorer の凍結値であることを確かめる。

**模擬** (`scripts/closed_loop_sim.py`、CPU): 実際のループの部品を使う。
- 使う部品: 世界の規則・π_r・Ω_dev の巡回・probe の layout・v2 の ⊥ gate / 3 分岐 / 符号反転。
- vectorize 版は、逐次の参照実装と、同じ一様乱数の下で状態が完全に一致する (test で pin)。

**植える方策** (1 次元の強さ κ ∈ [0, 1]):
- dev 段:
  - 同じ signature の成功行があれば、確率 κ で従う。
  - 無ければ、同じ weather の成功行 (distinct な signature 数 n ≥ 1) に、確率 λ(n) で従う。
  - どちらでもなければ base から引く。
  - R1+ では、既に試した行動の重みを (1 − γ) 倍にする (全選択肢を試していれば回避しない)。
  - ⊥ (確率 b) と Ω 外 (⊥ 以外の 5%) は失敗とする。
- **λ の版** (ADR §3.4 の感度分析):
  - flat: λ(n) = κ
  - graded: λ(1) = κ/2、λ(2, 3) = 3κ/4、λ(4) = κ
- probe 段:
  - e = clip(κ·g(n)·1[n > 0] + sd·Z, −1, 1)。Z は世界 × replicate の標準正規。
  - e > 0 なら確率 e で自分の成功行の label を選ぶ。e < 0 なら確率 |e| で foil を選ぶ (v2/v3 と同じ対称な攪乱)。残りは base。
- **γ = κ** (user 裁定 DU-2)。
  - R1+ の power は、「モデルが既に試した行動を、成功行を読むのと同じ強さで避ける」という仮定に依る。
  - γ = κ/2 と γ = 0 の値は、下に記述として併記する。この仮定は claim に入れない。
- 乱数の結合:
  - ループ段で 2 世界の状態 (= prompt) が同一なら、同じ一様乱数を使う。違えば独立にする。
    - 実モデルは、prompt が違えば同じ seed でも別の出力を返す。独立は、単位分散について保守側である。
  - probe 段は独立にする。

**base の 4 種**:
- uniform
- label_skew (A の規則の label に 0.7)
- position_skew (表示先頭に 0.7)
- **measured** (C0 の実測)
  - 模型は softmax(α[weather, label] + β[位置]) の L2 罰則付き MLE (Newton 法、σ = 2)。
  - データは v3 の C0 240 件と、v2 にだけある key 120 件の計 360 件。
    - 重なる 120 key は、v2 と v3 で raw が byte 一致する。
  - 推定値は `MEASURED_ALPHA` / `MEASURED_BETA` として封印した。
  - test で、凍結入力 2 ファイルの sha と、再推定値 = 定数を pin した。
  - 実測の偏りは強い: rain → read_book と clear → tend_moss は、全巡回の平均で約 0.013。
  - C0 の偏りを、状態ブロックがある開発 signature に外挿するのは、仮定である。

**真の C** = E[C_loop]。
- dev 段は Monte Carlo、probe 段は clip した正規の閉形式で求める。
- κ の格子 (0.04 刻み) で E[C] を計算し、目標の C を与える κ を線形補間で解く。
- **κ = 1 でも届かなければ「植えられない」とし、その候補は不合格にする**。
- 植える効果量は δ_plant = 2τ = 0.60、閾値は τ = 0.30 (別の数にする。Stage B の教訓)。

**攪乱格子 (48 点)**: base 4 × ⊥ 率 b {0, 0.1} × sd {0.05, 0.3, 0.5} × λ 版 {flat, graded}。

**条件** (全 48 点で、v3 を継承):
- power: P(PASS | C = 0.6) ≥ 0.8、P(NO_GO | C = 0) ≥ 0.8
- size: P(PASS | C = τ) と P(NO_GO | C = τ) が上限以下
  - 上限は、sd ≤ 0.3 では α + 3SE、sd = 0.5 では 1.5α = 0.075 (v3 の user 裁定を継承)
  - size は、**閉ループが生む単位分布** (coverage の混合・固着で歪んだ分布) の下で、C = τ を植えて測る。これが §3 の τ 判定の校正である。
- size の基準を満たさない場合の代替 (ADR §1 の 2):
  - τ 判定を、有界な平均に対する保守的な信頼区間 (WSR betting) に切り替える。
  - 結果: 選定した設計は、閉ループの単位分布の下で全 48 点の size 基準を満たした (下表)。**切り替えは発動しない**。
    判定は v2/v3 と同じ符号反転の τ 判定である。

**選定規則**:
- renderer は R1 → R1+ の順 (ADR: R1 が primary、R1+ は予備)。
- その中で、(R, K, M) ∈ {4, 8, 12} × {5, 10, 20} × {3, 4} を呼び出し数 R(30K + 48M) の少ない順に並べる。
- 2,000 回の screening を通ったものを、10⁴ 回で本確認する。
- 最初に全 48 点で通ったものを選ぶ。
- screening は、最初の違反点で打ち切り、その点を理由として残す。

**screening** (2,000 回。× の理由は最初の違反点):

| renderer | (R, K, M) | 呼び出し | 判定 | 理由 |
|---|---|---|---|---|
| R1 | (4, 5, 3) | 1,176 | × | measured・b0.0・sd0.05・graded で植えられない (κ = 1 で E[C] = 0.552) |
| R1 | (4, 5, 4) | 1,368 | × | measured・b0.0・sd0.3・graded で植えられない (κ = 1 で E[C] = 0.587) |
| R1 | (4, 10, 3) | 1,776 | × | measured・b0.0・sd0.05・graded で植えられない (κ = 1 で E[C] = 0.552) |
| R1 | (4, 10, 4) | 1,968 | × | measured・b0.0・sd0.3・graded で植えられない (κ = 1 で E[C] = 0.587) |
| R1 | (8, 5, 3) | 2,352 | × | measured・b0.0・sd0.05・flat で植えられない (κ = 1 で E[C] = 0.564) |
| R1 | (8, 5, 4) | 2,736 | × | measured・b0.0・sd0.05・graded で植えられない (κ = 1 で E[C] = 0.586) |
| R1 | (4, 20, 3) | 2,976 | × | measured・b0.0・sd0.05・graded で植えられない (κ = 1 で E[C] = 0.552) |
| R1 | (4, 20, 4) | 3,168 | × | measured・b0.0・sd0.3・graded で植えられない (κ = 1 で E[C] = 0.587) |
| R1 | (12, 5, 3) | 3,528 | × | measured・b0.0・sd0.05・flat で植えられない (κ = 1 で E[C] = 0.567) |
| R1 | (8, 10, 3) | 3,552 | × | measured・b0.0・sd0.05・flat で植えられない (κ = 1 で E[C] = 0.564) |
| R1 | (8, 10, 4) | 3,936 | × | measured・b0.0・sd0.05・graded で植えられない (κ = 1 で E[C] = 0.586) |
| R1 | (12, 5, 4) | 4,104 | × | measured・b0.0・sd0.05・graded で植えられない (κ = 1 で E[C] = 0.588) |
| R1 | (12, 10, 3) | 5,328 | × | measured・b0.0・sd0.05・flat で植えられない (κ = 1 で E[C] = 0.567) |
| R1 | (12, 10, 4) | 5,904 | × | measured・b0.0・sd0.05・graded で植えられない (κ = 1 で E[C] = 0.588) |
| R1 | (8, 20, 3) | 5,952 | × | measured・b0.0・sd0.05・flat で植えられない (κ = 1 で E[C] = 0.564) |
| R1 | (8, 20, 4) | 6,336 | × | measured・b0.0・sd0.05・graded で植えられない (κ = 1 で E[C] = 0.586) |
| R1 | (12, 20, 3) | 8,928 | × | measured・b0.0・sd0.05・flat で植えられない (κ = 1 で E[C] = 0.567) |
| R1 | (12, 20, 4) | 9,504 | × | measured・b0.0・sd0.05・graded で植えられない (κ = 1 で E[C] = 0.588) |
| R1plus | (4, 5, 3) | 1,176 | × | measured・b0.0・sd0.5・flat で P(NO_GO\|0) = 0.675 |
| R1plus | (4, 5, 4) | 1,368 | × | measured・b0.0・sd0.5・flat で P(NO_GO\|0) = 0.684 |
| R1plus | (4, 10, 3) | 1,776 | × | measured・b0.0・sd0.5・flat で P(NO_GO\|0) = 0.686 |
| R1plus | (4, 10, 4) | 1,968 | × | measured・b0.0・sd0.5・flat で P(NO_GO\|0) = 0.689 |
| R1plus | (8, 5, 3) | 2,352 | × | measured・b0.1・sd0.5・graded で植えられない (κ = 1 で E[C] = 0.583) |
| R1plus | (8, 5, 4) | 2,736 | ○ |  |
| R1plus | (4, 20, 3) | 2,976 | × | measured・b0.0・sd0.5・flat で P(NO_GO\|0) = 0.698 |
| R1plus | (4, 20, 4) | 3,168 | × | measured・b0.0・sd0.5・flat で P(NO_GO\|0) = 0.694 |
| R1plus | (12, 5, 3) | 3,528 | × | measured・b0.1・sd0.5・graded で植えられない (κ = 1 で E[C] = 0.581) |
| R1plus | (8, 10, 3) | 3,552 | × | measured・b0.1・sd0.5・graded で植えられない (κ = 1 で E[C] = 0.583) |
| R1plus | (8, 10, 4) | 3,936 | ○ |  |
| R1plus | (12, 5, 4) | 4,104 | ○ |  |
| R1plus | (12, 10, 3) | 5,328 | × | measured・b0.1・sd0.5・graded で植えられない (κ = 1 で E[C] = 0.581) |
| R1plus | (12, 10, 4) | 5,904 | ○ |  |
| R1plus | (8, 20, 3) | 5,952 | × | measured・b0.1・sd0.5・graded で植えられない (κ = 1 で E[C] = 0.583) |
| R1plus | (8, 20, 4) | 6,336 | ○ |  |
| R1plus | (12, 20, 3) | 8,928 | × | measured・b0.1・sd0.5・graded で植えられない (κ = 1 で E[C] = 0.581) |
| R1plus | (12, 20, 4) | 9,504 | ○ |  |

**本確認** (R1+・R = 8・K = 5・M = 4、10⁴ 回、全 48 点):

| sd | P(PASS\|0.6) 最悪 | P(NO_GO\|0) 最悪 | P(PASS\|τ) 最大 | P(NO_GO\|τ) 最大 | 上限 | 植えた C の最大誤差 |
|---|---|---|---|---|---|---|
| 0.05 | 0.983 | 0.985 | 0.048 | 0.049 | 0.0565 | 0.0017 |
| 0.3 | 0.982 | 0.983 | 0.051 | 0.051 | 0.0565 | 0.0014 |
| 0.5 | 0.948 | 0.937 | 0.055 | 0.045 | 0.0750 | 0.0091 |

→ **R1+・R = 8・K = 5・M = 4 を凍結**。

**OC 曲線** (b = 0.1・sd = 0.3、10⁴ 回、PASS / NO_GO / INCONCLUSIVE / INVALID_TB):

(λ = graded)

| 真の C | measured | uniform | label_skew | position_skew |
|---|---|---|---|---|
| 0.0 | 0.000 / 0.984 / 0.000 / 0.016 | 0.000 / 0.985 / 0.000 / 0.015 | 0.000 / 0.984 / 0.000 / 0.016 | 0.000 / 0.983 / 0.000 / 0.017 |
| 0.1 | 0.000 / 0.964 / 0.019 / 0.017 | 0.000 / 0.958 / 0.026 / 0.016 | 0.000 / 0.956 / 0.029 / 0.015 | 0.000 / 0.959 / 0.024 / 0.017 |
| 0.2 | 0.000 / 0.582 / 0.403 / 0.015 | 0.001 / 0.546 / 0.437 / 0.016 | 0.000 / 0.551 / 0.433 / 0.016 | 0.000 / 0.561 / 0.421 / 0.017 |
| 0.3 | 0.036 / 0.040 / 0.908 / 0.015 | 0.050 / 0.043 / 0.893 / 0.014 | 0.039 / 0.049 / 0.898 / 0.014 | 0.048 / 0.043 / 0.893 / 0.015 |
| 0.4 | 0.537 / 0.000 / 0.446 / 0.017 | 0.567 / 0.000 / 0.418 / 0.014 | 0.477 / 0.001 / 0.507 / 0.016 | 0.574 / 0.000 / 0.410 / 0.015 |
| 0.5 | 0.968 / 0.000 / 0.017 / 0.015 | 0.964 / 0.000 / 0.020 / 0.016 | 0.927 / 0.000 / 0.060 / 0.012 | 0.965 / 0.000 / 0.020 / 0.016 |
| 0.6 | 0.984 / 0.000 / 0.000 / 0.016 | 0.986 / 0.000 / 0.000 / 0.014 | 0.982 / 0.000 / 0.002 / 0.016 | 0.986 / 0.000 / 0.000 / 0.014 |

**λ の層別** (C = 0.6 を植えたときの probe セル。層 = その weather の成功 signature 数):

| 格子点 | κ | n=0 (割合 / w−foil) | n=1 | n=2〜3 | n=4 |
|---|---|---|---|---|---|
| measured・b0.1・sd0.3・flat | 0.890 | 0.146 / -0.262 | 0.012 / +0.691 | 0.073 / +0.702 | 0.769 / +0.752 |
| measured・b0.1・sd0.3・graded | 0.932 | 0.126 / -0.271 | 0.023 / +0.269 | 0.145 / +0.551 | 0.705 / +0.776 |
| uniform・b0.1・sd0.3・flat | 0.695 | 0.005 / +0.000 | 0.005 / +0.603 | 0.107 / +0.603 | 0.883 / +0.603 |
| uniform・b0.1・sd0.3・graded | 0.736 | 0.004 / +0.000 | 0.010 / +0.330 | 0.195 / +0.489 | 0.791 / +0.635 |
| label_skew・b0.1・sd0.3・flat | 0.738 | 0.051 / -0.129 | 0.021 / +0.585 | 0.153 / +0.588 | 0.775 / +0.650 |
| label_skew・b0.1・sd0.3・graded | 0.805 | 0.036 / -0.127 | 0.036 / +0.259 | 0.232 / +0.466 | 0.697 / +0.700 |
| position_skew・b0.1・sd0.3・flat | 0.704 | 0.018 / +0.007 | 0.009 / +0.613 | 0.120 / +0.610 | 0.853 / +0.611 |
| position_skew・b0.1・sd0.3・graded | 0.755 | 0.015 / +0.007 | 0.018 / +0.340 | 0.225 / +0.498 | 0.742 / +0.648 |

- 読み: 実測 base では、発見できなかった weather の probe (n = 0、約 13〜15%) が負になる (base が foil 側の label に寄るため)。C の大半は、その weather の全 signature を発見したセル (n = 4) から来る。
- graded 版では n = 1 のセルの寄与が約 0.27 に下がるが、n = 1 のセルは 1〜2% しかなく、全体への影響は小さい。

**γ の感度** (DU-2 の記述。R1+・M = 4・R = 8、b = 0.1・sd = 0.3、κ = 1 での E[C] と、C = 0.6 が植えられるか)。
実測 base では、γ < κ だと C = 0.6 を植えられない。**本登録の power は γ = κ の仮定に依る** (この仮定は claim に入れない):

| γ | base・λ | κ = 1 での E[C] | 終点 coverage | C = 0.6 を植えられるか | 実測 base での P(PASS\|0.6) |
|---|---|---|---|---|---|
| κ·0.5 | measured・flat | 0.557 | 0.760 | × |  |
| κ·0.5 | measured・graded | 0.522 | 0.760 | × |  |
| κ·0.5 | uniform・flat | 0.785 | 0.990 | ○ |  |
| κ·0.5 | uniform・graded | 0.765 | 0.990 | ○ |  |
| κ·0.5 | label_skew・flat | 0.702 | 0.899 | ○ |  |
| κ·0.5 | label_skew・graded | 0.656 | 0.899 | ○ |  |
| κ·0.5 | position_skew・flat | 0.768 | 0.964 | ○ |  |
| κ·0.5 | position_skew・graded | 0.744 | 0.964 | ○ |  |
| κ·0.0 | measured・flat | 0.501 | 0.699 | × |  |
| κ·0.0 | measured・graded | 0.470 | 0.699 | × |  |
| κ·0.0 | uniform・flat | 0.775 | 0.979 | ○ |  |
| κ·0.0 | uniform・graded | 0.752 | 0.979 | ○ |  |
| κ·0.0 | label_skew・flat | 0.632 | 0.822 | ○ |  |
| κ·0.0 | label_skew・graded | 0.589 | 0.822 | × |  |
| κ·0.0 | position_skew・flat | 0.748 | 0.935 | ○ |  |
| κ·0.0 | position_skew・graded | 0.723 | 0.935 | ○ |  |

**固着** (κ = 1 での E[C] の上限と coverage): 

| renderer | M | base・b・λ | κ = 1 での E[C] (R=8) | 終点 coverage |
|---|---|---|---|---|
| R1 | 3 | measured・b0.1・flat | 0.486 | 0.647 |
| R1 | 3 | measured・b0.1・graded | 0.427 | 0.647 |
| R1 | 3 | uniform・b0.1・flat | 0.833 | 0.944 |
| R1 | 3 | uniform・b0.1・graded | 0.765 | 0.944 |
| R1 | 4 | measured・b0.1・flat | 0.540 | 0.699 |
| R1 | 4 | measured・b0.1・graded | 0.498 | 0.699 |
| R1 | 4 | uniform・b0.1・flat | 0.863 | 0.979 |
| R1 | 4 | uniform・b0.1・graded | 0.831 | 0.979 |
| R1plus | 3 | measured・b0.1・flat | 0.762 | 0.896 |
| R1plus | 3 | measured・b0.1・graded | 0.683 | 0.896 |
| R1plus | 3 | uniform・b0.1・flat | 0.868 | 0.984 |
| R1plus | 3 | uniform・b0.1・graded | 0.808 | 0.984 |
| R1plus | 4 | measured・b0.1・flat | 0.878 | 0.996 |
| R1plus | 4 | measured・b0.1・graded | 0.836 | 0.996 |
| R1plus | 4 | uniform・b0.1・flat | 0.882 | 1.000 |
| R1plus | 4 | uniform・b0.1・graded | 0.865 | 1.000 |

## 7. 検査器の Done 条件 (CPU、実モデル不使用)

**全 verdict 枝に到達する合成 fixture** (`tests/test_closed_loop/test_scorer.py`):
- `synth` は driver の仕様を写した合成 run で、凍結 plan・連鎖・renderer を使う。
- PASS: 完全な reader (C = 1)、C = 0.5
- NO_GO: state-blind (全単位 0)、C = 0.1、探索しない世界
- INCONCLUSIVE: C = τ、1 世界の成分 0
- INVALID_TASK_BATTERY: C0 ⊥、ループ段 ⊥、probe ⊥、族内 ⊥ 差
- INVALID_SCORER:
  - certification の無し・古い・未合格・7 ファイル
  - battery・meta
  - schedule (欠番・世界の入れ替え・C0 より前・seed 2 種・transport 失敗の後の記録)
  - 再 parse
  - 連鎖 (loop 段の改ざん・成否の偽装・renderer の取り違え・誤った終状態からの probe・C0・replay)
  - 記録 schema 7 種
- not_computed: transport 失敗、C0 の欠け、本体の欠け。replay の欠けは判定を止めない。
- 5 語すべての到達を、1 つの test でも確認する。

**claim 分岐** の全行を確認する。PASS の文に coverage の値が入ることも確認する。

**相殺の定理と fixture** (`test_fixtures.py`):
- state-blind 3 種で、全単位 d = 0
- 陽性対照
- 近傍が負になること
- gate が正側だけであること・硬い gate τ/2・τ/4 の列挙
- 登録の一覧

**battery** (`test_battery.py`):
- 文言・空状態・π_r・語彙順・R1 ⊂ R1+
- 成否の更新・seed・Ω_dev・C0・plan・世界順・replay・非漏洩・byte 予算
- 壊した状態を捕まえる陽性対照を添える。

**模擬** (`test_power.py`・`test_base_fit.py`):
- 逐次の参照との完全一致 (4 設定)
- 同一状態での乱数共有
- 閉形式 = MC
- κ = 0 で E[C] = 0
- 解析 = 抽選の平均
- λ の版・R1+ の回避・R1 の固着
- 植えられない点の検出
- ⊥ gate 3 段
- size 上限の規則
- 基準の 4 条件と到達可能性
- 実測 base の封印

**変異試験** (`scripts/closed_loop_mutation_check.py`):
- 変異は計 79 本 (scorer 33・battery 18・sim 28)。
  - scorer: 連鎖 replay 5・schedule 5・parse と ⊥ gate 7・計算しない 2・判定 3・coverage と claim 5・
    INVALID_SCORER の照合 6
  - battery: 巡回・seed・世界順・成否の更新・文言・空状態・予算・seed 衝突・巡回均衡・漏洩・C0・plan・replay・世界順均衡
  - sim: 乱数結合 3 (Codex HIGH の再発を含む)・γ・λ・同一 signature・回避・⊥ gate 2・閉形式・foil 質量・
    植え付け 3・size 上限 2・基準 2・fixture gate 4・実測 base・Ω 外 2・参照実装・近傍の登録
- 落ちた test が意図した判定行のものかを照合する。no-op・anchor 不一致は不合格にする。
- **全 KILLED が certification の条件** (§5-1)。
- import する v2 の純粋関数は変異させない。v2 certification がすでに kill を確認している。
- 変異中は、「commit 済み manifest = 現在のファイル」の test を外す。

## 8. 実走と判定の手順 (凍結後、user 裁定)

1. user 裁定で driver と実走を許可する。
   - driver は、§2.2〜2.4 の renderer・plan と、§4 の要求条件で呼び出す。
   - 1 行 1 呼び出しを `results/run/records.jsonl` に、要求条件を `results/run/meta.json` に書く。
   - C0 を先に全て走らせ、C0 の ⊥ 率を確認してから状態側を走らせる。C0 が落ちたら状態側は走らせず、調整もしない。
   - 途中で R・K・M・renderer・prompt・parse を変えない。
2. 判定 = `bash experiments/20260927-closed-loop-divergence-pilot/run.sh`。
   - 最初に **凍結 v2 manifest** を照合する。
   - 次に **凍結 v4 manifest** (`manifest.json`) を照合する。
     - 対象: 本登録・判定コード・判定 CLI・変異 harness・表生成・manifest 検査・import する v2 / 旧資産・evidence の divergence・実測 base の入力 2 ファイル・test・certification・power 表・fixture 表・run.sh・SEED。
     - あわせて、certification と両表の記録 sha256 が現在のコードと一致し、選定が凍結値と一致し、fixture gate が合格であることを確かめる。
   - 1 つでも違えば、判定を計算しない。
   - certification は凍結時のものを読むだけで、実走後に変異 harness を回し直さない。
   - 判定を 2 回計算し、byte 一致を確かめる。
3. 凍結前に実データとして読んだのは、v2 / v3 の C0 記録 (実測 base の推定と決定性の観測) だけである。本登録の実走データは、凍結時点で 1 件も存在しない。

## 9. claim 境界 (ADR §5、`claim_branch`)

| verdict | claim_branch | 書いてよい範囲 |
|---|---|---|
| PASS | `pass_within_discovered_rows` | 下の PASS の文 (evaluate が template から生成) |
| NO_GO | `no_go_exploration_limited` (終点 weather coverage < 2/3) / `no_go_lookup_limited` (それ以外) | 下の NO_GO の文 |
| INCONCLUSIVE / INVALID / not_computed | (なし) | 測れなかった、まで |

### PASS
**言えること**: 1 つの凍結 qwen3:8b (think=False) の上で、次の条件のエージェントが、held-out 状況で違う選択をした。
- 違うのは、合成した 18 状況の環境が持つ、決定的な成否規則だけ。
- 各自が、自分の行動と結果から、aggregator が prompt に置く状態を育てた。
- 選択の違いは、自分の経験の向きにあり、大きさは τ を超えた。
- C_loop は、held-out probe 上の族内エージェント間の選択分布 TV に対する、向きの付いた下界である。

**PASS の文には、次を必ず入れる**:
- 終点の weather coverage
- 発見した weather の数
- 全 weather を発見した率
- signature coverage
- τ/4 を超えた fixture の注記 (`FLAGGED_NOTE`): 「weather を読まず状態内で最多の label を選ぶ読み方 (fixture F1) でも、実測 base・C = 0.6 の模擬で約 0.08 の正の寄与が生じうる」

言えるのは「発見済みの成功行を aggregator が prompt にした範囲で、held-out の選択が動いた」まで。全規則の発見を含意しない。

**言わないこと**:
- モデル自身が outcome から規則を抽出したこと。抽出と試行の集計は aggregator が行う。
- 失敗の読み取り、雑音のある経験の統合。
  - ただし R1+ では、失敗を消去法で推定できる情報が状態にある。そのため、失敗の読み取りが寄与した可能性は排除しない。
- 「思考」一般・開放的な行動空間。
- エージェント間の相互作用、persona・個体性の特性、長い時間軸。
- 「自分の」履歴であることの必要性 (yoked 対照が無いため)。
- CLD・Stage B・weight-space door・M13 について何か。
- power が依った γ = κ の仮定 (§6) を、モデルの性質として書くこと。

### NO_GO
言えるのは「**この R1+・この M = 4・この世界の設計では**、ループは τ に届かない (片側 95%)」まで。
- coverage の記述で、探索の不足 (`no_go_exploration_limited`) と lookup の不足 (`no_go_lookup_limited`) を枝分けする。
- 近傍方策 (§2.5 の F8、負の寄与) による押し下げも、この範囲に含まれうる。

### INCONCLUSIVE / INVALID
「測れなかった」までにとどめる。効果の有無は書かない。

### 共通
- 論文の本数・分割を本登録から決めない。
- 後段の扉 (いずれも開けるかは user 裁定): R2 (モデル自身が成否を読む)・確率的な成否・yoked 対照・エージェント間の相互作用。

## 10. 記述報告 (判定に使わない)

- 族内の probe 分布の TV (`tv_distance` を import) と、K を折半した雑音床。
- λ の層別 (probe セルを、その weather の成功 signature 数 0 / 1 / 2〜3 / 4 で分け、w − foil の平均)。
- 終点の coverage (weather・signature・世界別)。
- C0 の選択分布、ループ段の世界別 ⊥ 率、C > 0 の検定 p。
- **決定性** (ADR §3.4):
  - (i) run の中で、prompt と seed が同一の呼び出し群の raw 一致率。t = 0 は、各 r で必ず 4 世界が同一である。
  - (ii) 登録 replay 9R 件の、元の呼び出しとの raw 一致率。
    - 部分集合は r ごとに、ループ t = 0 の先頭世界、ループ最終 t の 4 世界、probe (q00, k = 0) の 4 世界。
  - (iii) 参考: v4 の C0 と、v2 / v3 の C0 の同 key での一致 (凍結前の観測では、v2 と v3 の間で 120/120 が一致)。
  - 規則: (i) (ii) のいずれかが 1.0 未満なら、§2.5 の「厳密に 0」を「期待値で 0」に格下げして書く。
    C = 0 の null に対する検定の妥当性は、交換可能性に依るので、この率には依存しない。

## 11. ADR・v2・v3 からの差分

| 項目 | v4 |
|---|---|
| 状態 | 外から与えた一覧 (v2 / v3) → 自分の行動と結果から aggregator が育てる (閉ループ) |
| 推定量 | v2 と同じ式。族内エージェント間の選択分布 TV の、向き付き下界として読む |
| renderer | R1+ (ADR の予備)。R1 は実測 base で C = 0.6 を植えられない (§6) |
| fixture gate | ADR の |·| < τ/4 → 正側だけ (DU-1)、硬い gate < τ/2 と τ/4 以上の列挙の 2 段 (DU-3)。負は NO_GO の claim、列挙は PASS の文に含める |
| power の仮定 | R1+ の回避 γ = κ (user 裁定 DU-2)。κ/2・0 は記述 |
| 判定式・τ・α・⊥ gate・parse・実行条件・probe・layout・probe seed | v2 の凍結関数・値を import (変更なし) |
| INVALID_SCORER | schedule 監査・連鎖 replay を追加 |
| INVALID_TASK_BATTERY | ループ段の世界別 ⊥ > 0.2 を追加 |
| coverage | gate にしない。claim_branch と PASS の文にだけ使う |
| (R, K, M) | (8, 5, 4)。v3 と同じ選定規則・size 上限 |
