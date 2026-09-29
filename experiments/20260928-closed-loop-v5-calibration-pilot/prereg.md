# 事前登録 — 閉ループ v5 前段: 挙動較正 pilot (判定に使わない) と、v5 の設計を選ぶ凍結写像

本文書は、pilot のどの実走よりも**前に**凍結する。
- 凍結前に Codex (gpt-5.5/xhigh) の independent review を受けた (設計 1 回・凍結前 1 回)。結果と採否は
  `.steering/20260928-closed-loop-v5-calibration-pilot-prereg/` (ローカル) の `codex-review*.md` と `decisions.md`。
- 凍結後に変更したものは、本登録の結果とみなさない。

本文書は、GPU・実モデル呼び出し・実走を authorize しない。
- driver を書くことと実走 (§8) には、凍結後に別途 user 裁定を要する。v5 の事前登録も別の user 裁定。

既存の凍結物は変更しない (v2 20 本・v3 22 本・v4 manifest 28 本・旧 Stage B・`src/erre_sandbox/evidence/`)。
本登録のコードはそれらを import するだけで、v4 manifest の無変更を test で確かめる。

設計の正本は scoping ADR `.steering/20260928-closed-loop-v5-scoping/design-final.md` (FROZEN、ローカル) の §3・§5。
本登録は ADR §3 (候補・測定量・写像・停止規則) を写す。ADR からの逸脱は §9 の user 裁定だけである。

## 1. 位置づけ

- v4 (prereg `experiments/20260927-closed-loop-divergence-pilot/prereg.md`) は NO_GO_EFFECT_ABSENT
  (`no_go_exploration_limited`) で閉じた。**v5 は v4 の「失敗を直した再試行」ではない**。v4 の verdict・claim はそのまま残る。
- scoping ADR §1・§2 の結論: v5 の候補軸 B・C の成否は、v4 の記録に情報の無いモデルの挙動
  (B = prompt が変わった再訪での反復率 s_changed、C = 探索指示に従う率 ε) で決まる。
- 本 pilot は、その挙動を測るだけの **判定に使わない較正** である。
  - probe を引かない。C_loop・coverage 由来の claim・verdict を計算しない。
  - pilot の記録は v5 の verdict に使わない (v5 は別の r・別の seed で新しく実走する)。
  - pilot の結果から言えるのは「この写像がこの設計を選んだ / door-close した」までで、効果の有無は何も言わない。
- pilot 後の選定の自由度 (軸・R・K・M の選び直し) を閉じるため、測定量・採否への写像・停止規則をここで凍結する。
  写像を pilot の結果を見て変えた場合、その後の登録は「探索的選定の後の確認的登録」と明記しなければならない。

## 2. 設計 (実装 = `scripts/closed_loop_v5_battery.py`)

### 2.1 候補軸 (ADR §3.1、user 裁定 DV-2)
v4 の世界・signature・Ω_dev・成否規則・状態 (aggregator)・状況部・system prompt・実行条件は変えない (v4 battery を import)。

| 軸 | renderer | 表示回転 (巡回量) | 追加 |
|---|---|---|---|
| B | R1 (成功行だけ。試した行なし) | (r + t + ⌊t/12⌋) mod 4 (周ごとに 1 進む) | なし |
| C | R1+ (v4 と同じ成功行 + 試した行) | (r + t) mod 4 (v4 と同じ) | 開発段の探索指示 1 文 |

**C の探索指示文** (user 裁定 DP-2。凍結後は変更しない・反復調整しない):

> 成功した記録の無い条件では、まだ試していない行動も試して、成功する行動を探すこと。

- 置き場所: 状態ブロックと状況部の間の独立の段落 (`状態ブロック + 空行 + 指示文 + 空行 + 状況部`)。
- 機械検査 (`check_axis_renderers`):
  - 指示文は C の user 文にちょうど 1 回。B・system prompt・状態ブロック (全ての極端な状態) には現れない。
  - 指示文を取り除いた C の request は v4 の R1+ の request と byte 一致する。B の request は、表示順の文字列を除いて v4 の R1 と byte 一致する。
  - 指示文は行動 label・状況の値 (weather・時刻・同伴) を含まない (特定の答えを指さない)。
- B の均衡検査 (`check_rotation_balance`、ADR §5): 両軸で各周の巡回量 0〜3 が 3 回ずつ。B は周をまたぐと巡回量が必ず変わり、4 周ごとに位相が戻る。C の巡回は v4 と一致。
- 非漏洩 (`check_non_leakage`): v2 / v4 と同じ integrity 検査 + 世界名 token。byte 予算: 最大 2,629 byte ≤ 3,000 (v2 / v4 と同じ上限)。

### 2.2 pilot の範囲
- ループ段だけを回す。probe・C0・決定性 replay は無い。
- replicate r ∈ {12, 13, 14, 15} (user 裁定 DP-1)、M = 8 (T = 96、user 裁定 DP-4)、4 世界、軸 B と C を各 1 回。
- **呼び出し数 = 2 軸 × 4 世界 × 4 r × 96 = 3,072** (v4 実測 0.18 s/call で約 10 分)。

### 2.3 呼び出し plan (`pilot_plan`)
- r ごとに、t = 0..95 の各 t で、軸を `axis_order(r)` (r が偶数なら B → C、奇数なら C → B) の順に、
  各軸の中で 4 世界を v4 の `world_order(r)` の順に呼ぶ。call_index = plan の位置。記録は plan の接頭辞でなければならない。
- 機械検査 (`check_plan`): (軸, 世界, r, t) の全組をちょうど 1 回、各軸が block の先頭に同数回、世界順の均衡 (v4 と同じ)。

### 2.4 seed
- `pilot_seed(r, t) = 22,260,928 + 1000·r + t`。軸・世界を引数に取らない (両軸・4 世界で共有 = 共通乱数)。
  値域は 22,272,928〜22,276,023。
- 機械検査 (`check_seed_disjoint`): 一意、v2 の probe seed (r < 16・全 probe・k < 20) と v4 のループ段 seed
  (v4 の基点で r < 16・t < 96) の全てと交わらない。
- **v5 prereg への要件**: v5 のループ段・probe の seed は `pilot_seeds()` と交わらないことを機械検査する。

### 2.5 実行条件・記録・driver の要件 (driver は範囲外。仕様だけ登録する)
- 実行条件は v2 / v4 と同じ (`request_meta()`): qwen3:8b、think=False、temperature 0.7、top_p 0.8、
  repeat_penalty 1.0、num_ctx 4096、num_predict 32、options.seed を明示。`meta.json` に記録し、一致しなければ invalid。
- 記録 (1 行 1 JSON、欄は過不足なし、型の coercion をしない): `call_index` / `replicate` / `step` / `seed` (int)、
  `axis` / `world` / `prompt_sha256` (str)、`raw` / `parsed` (str または null)。成否は記録しない。
- 送信する body は、記録済みの履歴から同じ renderer で再計算したものとする (閉ループ)。parse は v2 の `parse_choice`。
- transport 失敗 (再送 3 回後も失敗、raw = null) が起きたら、その記録を最後に止める。再開しない。

## 3. 測定量 (実装 = `scripts/closed_loop_v5_pilot_scorer.py` の `measure`)

候補 M ∈ {4, 6, 8} ごとに、pilot の step < 12M の窓で、軸ごとに計算する (DP-4)。定義は §5 の模擬の意味論に合わせる。
単位は (軸, 世界, r) の連鎖で、状態は連鎖 replay したものを使う。

- **⊥ 率** (世界別、窓内の全ステップ)。**世界別の最大 > 0.2 の軸は、その M で不採用** (再走しない、ADR §3.2)。
- 「前回」= その (世界, r, signature) の直近の ⊥ でない応答。「初訪」= 前回が無い訪問。
- 以下の率は、**事前状態で未成功の signature** で、**今回の応答が表示中の Ω_dev に入る** ものだけを数える。
  - **再訪の分類**: 描画した prompt が今回と同一の以前の訪問があり、その時の応答が表示中の Ω_dev にあれば「同一 prompt」
    (その応答と比べる、ŝ_same・記述)。それ以外は「prompt 変化」(B は 4 周ごとに回転の位相が戻り、5 周目の prompt は
    1 周目と同一になりうる。以前の応答が Ω 外なら模擬と同じく「prompt 変化」に落とす)。
  - **ŝ_changed** (B の挙動値): prompt 変化の再訪で、前回の label が表示中の Ω_dev にあるもの → 前回と同じ label を選んだ率。
  - **ε̂** (C の挙動値): 表示中の選択肢に試行済みが 1 つ以上あり、未試行も残る訪問 → 未試行を選んだ率。
    ρ̂ (未試行を選ばなかった訪問で前回と同じ) と η̂ (未試行を選んだ訪問で規則に当たった) は記述。
  - **λ̂_dev** = max(0, (h_sw − h0) / (1 − h0))。h0 = 同 weather の成功行が 0 本の初訪で規則に当たった率、
    h_sw = 同 weather の成功行が 1 本以上の初訪で規則に当たった率。再訪は含めない。どちらかの n が 0 なら「無し」。
  - **ループ段 base** = 同 weather の成功行が 0 本の初訪の、Ω_dev (正準順) 上の label 割合 (+0.5 の加算平滑化)。
- **Ω 外率** (世界別): 未成功の signature での ⊥ でない応答のうち、表示中の Ω_dev に無いものの率。
- **重複の扱い**: 4 世界が seed を共有するので、同じ (prompt_sha256, seed) の呼び出しは 1 回の抽選として 1 件に畳む。
  代表は call_index の最初の 1 件。世界別の ⊥・Ω 外は畳まない。
- **保守限界** (DP-5): 挙動の率は、(a) 畳んだ呼び出し単位の Wilson 95% と (b) 非空の (世界, r) cluster の数を n・
  cluster 率の平均を p とする Wilson 95% の外側 (下限は小さい方、上限は大きい方)。n = 0 は下限 0・上限 1。
  ⊥ と Ω 外の上限は、世界別の呼び出し単位 Wilson 95% 上限の最大 (DC-9: 世界別の cluster は 4 個で、cluster 単位では
  ⊥ 0 件でも上限 0.49 になり、写像が原理的に door-close になる)。

## 4. 検証 (測定の前に。`validate`)

評価順に適用し、最初に当たったもので止める。`computed` 以外では測定量を出さず、写像を計算しない。
1. **invalid**: battery の機械検査違反 / 要求条件の不一致 / 記録の schema 違反 / schedule (plan の接頭辞でない・
   key・seed の不一致・transport 失敗の後に記録が続く) / 再 parse の不一致 / 連鎖 replay の prompt sha 不一致。
2. **not_computed**: transport 失敗がある / 記録が 3,072 件に満たない。
- invalid・not_computed のとき、再走・再開は別の user 裁定。pilot を「通るまで」回し直さない。

## 5. 凍結 v5 模擬 (実装 = `scripts/closed_loop_v5_sim.py`)

ADR §2.1 の原型 (`sim/v5_feasibility.py`) を写し、C を植える機構を加える。CPU のみ。

**dev 段 = 経験的混合方策** (κ に依らない。モデルの dev 段の挙動は pilot で測る値で、植える対象ではない)。
未成功の signature で、上から最初に当たった分岐をとる。分岐ごとに独立の一様乱数を使う。
0. ⊥ (確率 b)。行動なし。
1. 同 signature の成功行 → 規則。
2. C のみ: 表示中に試行済みがあり未試行も残るとき、確率 ε で未試行から選ぶ (一様 / base を未試行に制限して正規化)。
   選ばなければ確率 ρ で前回を写す。
3. 同一 prompt の以前の訪問があれば確率 s_same でその時の応答を反復。無ければ、前回の label が表示中にあるとき
   確率 s_changed で前回を反復。
4. 同 weather の成功行が 1 本以上あれば確率 λ_dev で規則。
5. base (表示中の 4 選択肢上の分布)。
最後に、未成功の signature で ⊥ でない応答は確率 oov で Ω_dev 外の label (失敗・試行に数える)。
- 乱数の結合は v4 と同じ: 描画した prompt が同一の世界は同じ一様乱数 (v4 の `_state_keys` / `_coupled`)。
- 逐次の参照実装 (結合と「同一 prompt」を描画した messages の完全一致で判定) と、同じ乱数で完全一致することを test で pin した。
- 原型からの修正: 分岐ごとに独立の一様乱数、⊥ で「前回」を更新しない、同一 prompt の記憶 (4 周前の位相の戻りを扱う)。

**probe 段 = v4 と同一の植え付け**: e = clip(κ·g(n)·1[n > 0] + sd·Z, −1, 1) (g = flat / graded、Z は世界 × replicate)。
E[C] は閉形式 (v4 の `expected_units` と数値一致する表引き版)、κ の格子 (0.04 刻み) で E[C] = 目標 を解く。
K 回は、1 回目を引いた後、各回が確率 k_rep で 1 回目を反復し、残りは独立に引く (DP-3)。
null は κ = 0、size は E[C] = τ の κ、power は E[C] = 2τ の κ。pipeline (C0 ⊥ gate → ループ ⊥ gate → probe ⊥ gate →
3 分岐) と判定式は v4 / v2 の凍結関数を import する。

**基準** (v4 の `Criteria` をそのまま使う、DV-4): C = 2τ = 0.60 を植えられる (κ ≤ 1 で届き、抽選の平均が目標 ± 0.02)・
P(PASS | 0.6) ≥ 0.8・P(NO_GO | 0) ≥ 0.8・P(PASS | τ) と P(NO_GO | τ) が上限以下
(sd ≤ 0.3 は α + 3SE、sd = 0.5 は 1.5α)。τ = 0.30、α = 0.05。

## 6. 採否への写像 (実装 = `scripts/closed_loop_v5_select.py`、ADR §3.3)

1. §4 が `computed` でなければ写像を計算しない (`not_mapped`)。certification (§7) が不備なら何も計算しない。
2. 候補 M の窓で ⊥ gate に落ちた軸は、その M で審査しない。
3. **固定値** (保守側): B の s_changed = ŝ_changed の上限、C の ε = ε̂ の下限・ρ = 1、s_same = 0.96 (v4 の実測)、
   oov = max(0.05, Ω 外率の上限)。
4. **攪乱格子** (全点で基準を満たすことを要求する):
   - dev 段: λ_dev {pilot の点推定 (無ければ 0), v4 の 0.43388} × base {pilot のループ段, v4 のループ段, v4 の C0 実測 (位置効果つき)} ×
     b {0, b_hi} (b_hi = ⊥ 率の上限、床なし、DP-6) × 未試行の選び方 {一様, base 制限} (C のみ)。
   - probe 段: base {measured, uniform, label_skew, position_skew} × sd {0.05, 0.3, 0.5} × g {flat, graded} × k_rep {0, 0.944}。
   - v4 の較正値 (λ_dev = 0.43387853…・ループ段 base) は v4 の実走記録から ADR §2.1 の定義で再計算した値と一致することを test で pin。
5. **候補** (R, K, M) ∈ {8, 12} × {5, 10} × {4, 6, 8} を (呼び出し数 R(30K + 48M), M, R) の昇順に並べ、各候補で軸 B → C の順に審査する。
   - screening 2,000 回: 格子点を (dev 点, probe 点) の順に審査し、最初の違反点で打ち切る。
   - screening を通ったら本確認 10⁴ 回 (同じ順に審査し、違反点があればそこで打ち切って不合格。合格は全点で満たしたときだけ)。
   - **最初に本確認を通った (軸, R, K, M) を v5 の設計とする** (呼び出し数最少、同数は M・R の小さい順、同じ候補では B → C)。
6. **どれも通らなければ door-close** (v5 を起こさず、v4 の NO_GO と ADR の原因記述で閉じる)。これは正当な Done である。
- 模擬の seed は、点の記述 (軸・dev 点・probe 点・R・K・M・回数・段) の canonical JSON の sha256 の先頭 8 byte (little-endian)。
  評価順に依らない。判定は full precision で行い、丸めは出力だけ。
- 写像は `run.sh` で 2 回計算し、出力の byte 一致を確かめる。

## 7. 検査器の Done 条件 (CPU、実モデル不使用)

- test (`tests/test_closed_loop_v5/`、計 79): battery 15 (陽性対照つき)・scorer 24 (方策から答えが決まる合成 run と
  手で数えられる場面で分母の境界を pin)・sim 17 (逐次参照との完全一致・v4 の閉形式との数値一致・植え付け・⊥ gate・
  k_rep・seed)・写像 15 (保守値・格子・候補順・選定規則・door-close・窓・certification)・manifest 8。
- **変異試験** (`scripts/closed_loop_v5_mutation_check.py`、`results/pilot_mutation.json`): battery 21・scorer 22・
  sim 16・写像 16 の計 75 変異が **全て KILLED**。落ちた test が意図した判定行のものかを照合し、no-op・anchor 不一致は
  不合格。試走で生存した 2 変異は等価変異と判断して登録から外した (ε̂ の分母条件「未試行が残る」は、未成功の signature
  では規則を未試行なので常に真 / C の結合 key の試行行は、結合の下で成功が出るまで族内の試行集合が一致するので冗長)。
  **全 KILLED が certification の条件** (§6-1)。certification は 10 ファイル (本登録の 4 本と import する凍結物 6 本)
  の sha256 に結び付く。
- **manifest** (`scripts/closed_loop_v5_manifest.py`、`manifest.json`): prereg・run.sh・SEED・certification・見取り図・
  本登録のコード 6 本・import する凍結物 6 本・v4 の実走記録 (較正値の入力)・test 7 本。

## 8. 実走と写像の手順 (凍結後、user 裁定)

1. user 裁定で driver と実走を許可する。driver は §2 の renderer・plan・seed と §2.5 の実行条件で呼び出し、
   `results/run/records.jsonl` と `results/run/meta.json` を書く。途中で軸・r・M・指示文・parse を変えない。
2. 写像 = `bash experiments/20260928-closed-loop-v5-calibration-pilot/run.sh`。
   - 凍結 v2 manifest → 凍結 v4 manifest → 本登録の manifest (certification・見取り図とコードの結び付きを含む) の順に照合し、
     1 つでも違えば計算しない。
   - 検証 → 測定 → 写像を 2 回計算し、byte 一致を確かめる。所要は 10 時間を超えうる (見取り図の実測、§10)。
     セッションに依らない process で走らせる。
3. 凍結前に実データとして読んだのは v4 の実走記録 (ADR の原因記述と v4 較正値) だけである。本登録の pilot の実走データは、
   凍結時点で 1 件も存在しない。

## 9. ADR からの逸脱と、実データ前に写像を変えた経緯 (user 裁定)

| id | 内容 | 理由 |
|---|---|---|
| DP-1 | pilot の r を ADR §3.2 の {8..11} から {12..15} に | ADR §3.3 の候補 R = 12 は r = 0..11 を使い {8..11} と layout が重なる (ADR 内の矛盾)。ADR の意図 (v5 と layout 非重複) を優先 |
| DP-4 | pilot の M を ADR §3.2 の 4 から 8 に (3,072 呼び出し)、候補 M ごとの窓で測る | 候補 M ∈ {6, 8} への外挿を無くす (Codex HIGH)。B は 5 周目に回転の位相が戻る |
| DP-5 | 保守限界を「呼び出し単位と cluster 単位の Wilson の外側」に | 呼び出し単位の Wilson は (世界, r) 内の相関を無視して狭すぎる (Codex HIGH) |
| DP-3 | 攪乱格子に k_rep {0, 0.944} と未試行の選び方 {一様, base 制限} を追加 | v4 の模擬は K 回を独立とみなしていた (実測の同一 prompt・別 seed 一致 0.944)。一様な未試行選択は楽観側 |
| DP-6 | ⊥ 率の格子値から v4 の床 0.1 を外し、pilot の実測上限にする | 下記 |

**実データ前に、仮想の挙動値で写像を試走して規則を変えた事実** (DP-6):
- 仮想の測定量 (ε 下限 0.8、探索は十分) で写像を試走すると、格子点「b = 0.1 × k_rep = 0.944」では ⊥ も K 回反復され、
  族内の ⊥ 率差が probe の ⊥ gate を超えて約 40% が INVALID_TASK_BATTERY になり、P(PASS | 0.6) ≈ 0.60 で全候補が落ちた
  (b = 0 や k_rep = 0 では 0.96〜1.0、size も上限内、10⁴ 回)。床 0.1 のままでは写像が pilot の結果に依らず door-close
  になる (恒真の選定) ので、床を外した。v4 の実走の ⊥ 率は全段で 0.0 である。
- この変更は pilot の実データが存在しない時点で行った。仮想値は §10 の見取り図と同じ種類のもので、実データではない。

## 10. 見取り図 (判定に使わない、`results/decision_table.json`)

仮想の挙動値 (B の ŝ_changed 上限・C の ε̂ 下限) を与え、λ_dev と base は v4 の値、⊥・Ω 外は 0 件相当として、
写像を凍結した回数で回した結果。pilot の結果の読み方の目安で、写像そのものではない。
- ⊥・Ω 外が 0 件相当 = 上限を窓の世界別呼び出し数 (12M × 4) の 0 件の Wilson 上限に置く
  (b_hi = 0.0196 / 0.0132 / 0.0099 (M = 4 / 6 / 8)、oov は床の 0.05)。
- 格子の「pilot」の λ_dev・base は v4 の値と同じになるので、dev 段の格子点には重複がある。
- 表は `closed_loop_v5_select.py --decision-table` が certification と同じ 10 ファイルの sha256 に結び付けて書いた
  (`target_sha256`)。

| 仮想値 (B の ŝ 上限 / C の ε̂ 下限) | 写像の出力 | 経過 |
|---|---|---|
| 0.0 / 0.8 | **C・R = 8・K = 5・M = 6** (3,504 呼び出し) | 本確認 10⁴ 回で 1,152 点すべて合格。最悪値は P(PASS \| 0.6) 0.917・P(NO_GO \| 0) 0.896 (下限 0.8)、P(PASS \| τ) 0.061・P(NO_GO \| τ) 0.055 (上限は sd ≤ 0.3 で 0.0565、sd = 0.5 で 0.075。0.061 は前者を超えるので sd = 0.5 の点)。それより前の審査では、(8, 5, 4) の B・C と (8, 5, 6) の B が screening で落ちた |
| 0.5 / 0.5 | **door-close** | C は最大の候補 (12, 10, 8) だけが screening を通った。本確認では 260 点目 (sd = 0.3) で P(PASS \| τ) = 0.0566 が上限 0.0565 を超えて不合格になった。B は全候補の screening で落ちた |
| 0.9 / 0.2 | **door-close** | 全候補の screening で、B・C とも 1〜155 点目で落ちた |

読み方 (判定に使わない):
- **B は、見取り図の範囲では一度も選ばれなかった**。ŝ = 0 (前回を全く反復しない) でも、審査した 2 候補 (8, 5, 4)・(8, 5, 6)
  では、どちらも最初の違反が「C = 2τ を植えられない」だった (probe base = measured のとき κ = 1 で E[C] = 0.598〜0.599、
  coverage 0.82〜0.85)。ŝ ≥ 0.5 では全 12 候補で落ちた。最初の違反は、ŝ = 0.5 の (8, 5, 8) が size だった
  (P(NO_GO | τ) 0.065) ほかは、すべて C = 2τ に届かないことだった (κ = 1 で 0.48〜0.59)。
  ŝ = 0 でより大きい候補を審査した結果は表に無い (行 1 は C が先に選ばれて止まった)。
- C の合否の境は ε̂ 下限 0.5〜0.8 の間にある。ε̂ 下限 0.5 では、12 候補の最初の違反のうち 10 件が size で、
  上限との差はわずかだった (screening の上限 0.0646 に対して 0.065〜0.069。本確認の 1 件は上記)。
  残り 2 件は C = 2τ に届かなかった。ε̂ 下限 0.2 では、12 候補のうち 11 件が C = 2τ に届かず、1 件 ((8, 5, 8)) が size で落ちた。
- **所要** (16 論理コアの G-GEAR・CPU のみ、1 回の計算): 行 1 は 6.1 時間 (C (8, 5, 6) の screening 1.1 時間・本確認 4.7 時間)、
  行 2 は 2.5 時間、行 3 は 0.4 時間。合計 8.9 時間。§8 の写像は 2 回計算するので、候補が本確認に進むと、合わせて 10 時間を超えうる。

## 11. v5 prereg への binding 要件

- v5 の軸・(R, K, M) は §6 の写像の出力だけで決める。door-close なら v5 を起こさない。
- v5 の r は < 12、seed は `pilot_seeds()` と交わらない (機械検査)。
- C を採る場合 (ADR §5、Codex MEDIUM): v5 prereg は次を機械検査する。
  指示文は開発段の user 文にだけ現れ、system prompt・状態ヘッダ・状態行・probe の request に現れない (全 request の文字列検査)/
  probe の request 全体 (system + user) は v4 の probe と、状態ブロック以外で byte 一致する / 状態 schema に指示文の token が入らない /
  呼び出しは単発 (会話履歴なし)。
- 登録 fixture の追加 (ADR §5: F14・F15、C なら F16・F17) と F1 の τ/4 列挙の再計算、fixture gate の 2 段は v5 prereg で行う。
- pilot の記録は v5 の verdict・power・fixture の計算に使わない (§6 の写像の入力としてだけ使う)。
- claim の上限 (ADR §4) を継承する。B なら「表示順を周で変えた下で」、C なら「開発段で探索を指示した下で」を PASS の文に付す。

## 12. 非再開 (継承)

CLD・Stage B・weight-space door・M13 を再開しない。論文の本数・分割を本登録から決めない。
同じ世界で seed・摂動・初期 prompt の差だけが違う状態や、距離の時間傾きを分散の源・指標にしない。
