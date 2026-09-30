# 事前登録 (凍結しなかった) — 探索を身体側へ (b) 歩行 → decode 条件: 挙動較正 pilot (判定に使わない) と、本登録の設計を選ぶ写像

> **status: 凍結しなかった。door-close (2026-09-30、user 裁定 DU-4)。**
> - 凍結の直前に、写像を仮想の挙動値と合成 pilot で試走した (見取り図、§13)。
>   最も有利な仮想挙動 (s_same = s_changed = 0) でも、写像は何も選ばなかった。
> - つまり、§13 の見取り図で定めた仮想挙動 family (s を振り、λ_dev・base・⊥・Ω 外を固定) と、凍結前の door-close 判定条件
>   (s = 0 が door-close なら恒真とみなす) の下で、この写像は pilot の結果に依らず door-close になる (恒真の選定)。
>   あらゆる測定値のベクトルについての数学的な全称ではない (Codex 3 回目 MEDIUM-1)。
>   主因は、k_rep 0.944 の probe 点の size が上限 (α + 3SE) の際にあり、全格子点の合格を求めると必ずどこかで越えることである。
>   v4 から継承した凍結基準と、候補 (R ≤ 12・K ≤ 10・M ≤ 8) の構造から来る。
> - 凍結前の取り決め (§13) に従って user 裁定を仰ぎ、写像を凍結せずに door-close を確定した。
>   **較正 pilot・driver・GPU は起こさない。本登録も起こさない**。
> - 記録の範囲は §16。
>   - 言えるのは「この検定の設計では、(b) は開発段の挙動に依らず検定を起こせない」までである。
>   - 歩行の decode でのモデルの挙動については、何も測っておらず、何も言わない。
> - 以下の §1〜§12・§14 は、凍結しようとした内容の記録として残す。
>   機械一式・変異試験の certification・見取り図は、`manifest.json` が証拠として sha256 で結び付ける。
>   `body_walk_manifest.py --verify` は凍結条件を満たさないことを報告して止まるので、`run.sh` も止まる。

> **探索的選定の後の確認的登録である (として起こそうとした)。**
> - (b) は、v5 の scoping が DV-2 で候補外にした D 軸 (開発段の decode 温度) に当たる。
> - それを、v5 の較正 pilot の結果 (凍結写像の出力 door-close、PR #133) を見た **後に** 選んでいる
>   (scoping ADR `.steering/20260930-exploration-by-body-scoping/design-final.md` §0、ローカル)。
> - 本登録が確認的なのは、この選定の後に置いた pilot の範囲・測定量・写像・停止規則に対してだけである。
>   D 軸を選んだこと自体は探索的である。
>
> **endpoint (λ = 1) に限る** (user 裁定 DU-2、Codex HIGH-1)。
> - 開発段の decode は、ERRE の歩行 channel の凍結値の上限 endpoint だけである。
> - 本登録の claim も door-close も「凍結 channel 上限 endpoint」でのことに限る。λ < 1 については何も言わない。

本文書は、pilot のどの実走よりも**前に**凍結する予定だった (上の status のとおり、凍結しなかった)。
- 凍結前に Codex (gpt-5.5/xhigh) の independent review を 2 回受けた (設計 1 回・凍結前 1 回)。
  結果と採否は `.steering/20260930-body-exploration-calibration-prereg/` (ローカル) の `codex-review*.md` と `decisions.md`。
- pilot の実走データは 1 件も存在しない。

本文書は、GPU・実モデル呼び出し・driver・実走を authorize しない。
- driver を書くことと実走 (§11) には、凍結後に別途 user 裁定を要する。本登録の事前登録も別の user 裁定。

既存の凍結物は変更しない。
- v2・v3・v4・v5 の manifest の対象、旧 Stage B、`src/erre_sandbox/evidence/`。
- v5 の写像・候補・格子。ERRE の sampling の凍結値。
- 本登録のコードは、それらを import するだけである。v4・v5 manifest の無変更を test で確かめる。

設計の正本は scoping ADR (FROZEN) の §3 ((b) の定義)・§4 (claim の上限)・§6 (較正と写像の原則)・§8-1 (必須項目)。
本登録の設計の経緯 (/reimagine の 2 案と採否) は `.steering/20260930-body-exploration-calibration-prereg/design-final.md`。

## 1. 位置づけ

- v4 は NO_GO_EFFECT_ABSENT (探索の不足) で閉じた。v5 の較正写像は door-close だった。**本登録は v4・v5 の「失敗を直した再試行」ではない**。
  v4・v5 の verdict・claim・写像の出力はそのまま残る。
- scoping ADR §1 の結論:
  - 構造 (身体・環境) が探索の「方向」まで担う設計は、「既知の読み + 被覆の工学」に縮退する。
  - (b) は、探索の「量」だけを身体の channel が担い、「方向」をモデル自身の分布に残す。
  - (b) の成否は、v2〜v5 の記録に情報の無いモデルの挙動で決まる。v2〜v5 の全呼び出しは T 0.7・top_p 0.8 だった。
- 本 pilot は、その挙動を測るだけの **判定に使わない較正** である。
  - probe・C0 を引かない。C_loop・verdict を計算しない。
  - pilot の記録は本登録の verdict に使わない (本登録は別の r・別の seed で新しく実走する)。
  - pilot の結果から言えるのは「この写像がこの設計を選んだ / door-close した」までである。効果の有無は何も言わない。
- pilot 後の選定の自由度 (R・K・M の選び直し、格子・候補の変更) を閉じるため、測定量・写像・停止規則をここで凍結する。

## 2. 設計 (実装 = `scripts/body_walk_battery.py`)

### 2.1 腕 W
- 世界・signature・Ω_dev・成否規則・状態 (aggregator)・状況部・system prompt・parse は v4 のまま (v4 battery を import)。
- renderer は R1 (成功行だけ。試した行なし)。表示回転は v4 と同じ (r + t) mod 4 で、周で不変 (12 ≡ 0 mod 4)。
- request の messages は v4 の `loop_messages(state, world, r, t, RENDERER_R1)` と byte 一致する。違うのは decode の 3 値だけである。

### 2.2 開発段の decode = 歩行 (ADR §3、user 裁定 DU-2)
- 値は、ERRE の live 凍結値を合成した `walk_sampling()` の出力そのものである。
  - 式: `compose_sampling(SamplingBase(0.7, 0.8, 1.0), SAMPLING_DELTA_BY_MODE[PERIPATETIC], locomotion_delta(LocomotionState(lam=1.0), gain_t=DEFAULT_LOCO_GAIN_T, gain_p=DEFAULT_LOCO_GAIN_P))`
  - 手で書いた定数を正本にしない。
- 実値 (2026-09-30 の観測): temperature = 1.3、top_p = 0.9500000000000001、repeat_penalty = 0.9。いずれも clamp の内側である。
- 封印 `FROZEN_WALK`:
  - 上の実値を凍結時の観測として持つ。
  - `check_sampling` は、`walk_sampling()` の出力がこれと一致することを要求する。
  - 凍結後に ERRE の凍結値が変わると battery 違反になり、pilot は invalid になる。
  - このため、ERRE の source は manifest に入れない。
- 着座 (本登録の probe・C0) は v2 の値 (T 0.7・top_p 0.8・repeat_penalty 1.0) のままとする。
- 機械検査 (`check_sampling`):
  - 歩行は合成の和そのもの (clamp されていない) である。
  - 向きは T と top_p が上がり、repeat_penalty が下がる。
  - 着座は v2 の値である。
  - meta は歩行の値を持つ。

### 2.3 非漏洩・byte 予算
- `check_non_leakage`: v2 / v4 と同じ integrity 検査と、世界名 token の検査を、全 r・全世界・空と全成功の状態の R1 の prompt で行う。
- byte 予算は、最大 1,077 byte ≤ 3,000 (v2 / v4 と同じ上限)。

## 3. pilot の範囲・plan・seed

- ループ段だけを回す。probe・C0 は無い。
- replicate r ∈ {16, …, 27} (12 個、user 裁定 DU-3)、M = 8 (T = 96)、4 世界。**ループ段の呼び出し数 = 4 × 12 × 96 = 4,608**。
- 決定性 replay (判定に使わない):
  - r ごとに 9 件ある。対象は、t = 0 の先頭世界、t = 47 の 4 世界、t = 95 の 4 世界。
  - 全ループの後に、元の呼び出しと同じ request・seed で送る (108 件)。**総呼び出し数 = 4,716**。
- plan (`pilot_plan`):
  - r ごとに、t = 0..95 の各 t で、4 世界を v4 の `world_order(r)` の順に呼ぶ。
  - その後に replay を r ごとに置く。
  - call_index は plan の位置で、記録は plan の接頭辞でなければならない。
- 機械検査:
  - `check_replicates`:
    - r は本登録が使いうる r (< 12、候補 R ≤ 12) と、v5 pilot の r (12〜15) に重ならない。
    - r は一意で、r mod 4 の各値が 3 回ずつ現れる。
  - `check_plan`:
    - ループ部分は (世界, r, t) をちょうど 1 回ずつ、凍結順に含む。
    - replay 部分は登録した対象だけである。
    - 世界順は均衡している。
  - `check_rotation`: v4 と同じ回転で、周で不変。各周で巡回量 0〜3 が 3 回ずつ。
- seed: `pilot_seed(r, t) = 23,260,930 + 1000·r + t`。世界を引数に取らない (4 世界で共有 = 共通乱数)。
  - 値域は 23,276,930〜23,288,025。
  - `check_seed_disjoint`: seed は一意で、次のすべてと交わらない。
    - v2 の probe seed (r < 32・全 probe・k < 20)
    - v4 のループ段 seed (r < 32・t < 96)
    - v5 pilot の `pilot_seeds()`

## 4. 実行条件・記録・driver の要件 (driver は範囲外。仕様だけ登録する)

- 要求条件と実行環境 (`request_meta_walk()`) は、次の 3 つから成る。
  - v2 の `request_meta()`: qwen3:8b、think = False、num_ctx 4096、num_predict 32。
  - 歩行の 3 値 (§2.2)。
  - driver が **実行時に観測した** 環境 3 値 (Codex HIGH-1、§5):
    - `ollama_version` = `0.32.12` (GET /api/version)
    - `model_digest` = `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41` (GET /api/tags の qwen3:8b)
    - `model_parameters` (POST /api/show の `parameters` 文字列をそのまま):
      stop ×2・temperature 0.6・top_k 20・top_p 0.95・repeat_penalty 1
  - `meta.json` に記録し、key の集合・値・型の全てが一致しなければ invalid (Codex 2 回目 MEDIUM、DC-6)。
    `False == 0` や `4096 == 4096.0` を通さない (記録と同じく型の coercion をしない)。
- driver への要件:
  - 環境の 3 値は手で書かない。実行の開始時と終了時に観測し、両者が一致しなければ公開しない。
  - options は v2〜v5 と同じ 6 key (seed・num_ctx・num_predict・temperature・top_p・repeat_penalty) で、歩行の 3 値を送る。
  - 送る float は `walk_sampling()` の出力そのものとする (top_p = 0.9500000000000001)。
- 記録 (1 行 1 JSON、欄は過不足なし、型の coercion をしない):
  - int: `call_index` / `replicate` / `step` / `seed`
  - str: `phase` (`loop` / `replay`) / `world` / `prompt_sha256`
  - str または null: `raw` / `parsed`
  - 成否は記録しない。
  - JSON は `ensure_ascii=True` で書く (U+2028 などで行が割れないように。写像は改行文字だけで行を区切る)。
- 送信する body は、記録済みの履歴から R1 で再計算したものとする (閉ループ)。replay は元の呼び出しと同じ body を送る。
  parse は v2 の `parse_choice`。
- transport 失敗 (再送後も失敗、raw = null) が起きたら、その記録を最後に止める。再開しない。

## 5. sampler の順 (scoping ADR BL-2 の確認。GPU 不要、公開 source で確認)

- Ollama 0.32.12 (tag `v0.32.12` = commit `e0e1d3c7`) は、sampling を同梱の llama.cpp `llama-server` に委ねる。
  llama.cpp は `LLAMA_CPP_VERSION` = b10380 (commit `0b1bad14`)。
  - Ollama の `llm/llama_server.go` は、次の欄を送る: temperature・top_k・top_p・min_p・repeat_penalty・repeat_last_n・
    frequency_penalty・presence_penalty・typical_p・seed。
  - 順序 (`samplers`) は送らず、起動引数にも `--samplers` は無い。
- したがって、順序は llama.cpp の既定 (`common/common.h`) になる:
  **penalties → dry → top_n_sigma → top_k → typical_p → top_p → min_p → xtc → temperature** → dist(seed)。
  - dry・top_n_sigma・xtc は既定で無効。typical_p = 1.0 も無効。
  - min_p は Ollama が 0 を常に送るので無効。
  - top_k は、要求で送らないので、qwen3:8b の Modelfile の 20 になる。repeat_last_n は Ollama 既定の 64。
- 読み (解釈にだけ使う。写像の式には入らない):
  - top_p の nucleus は、温度をかける前 (top_k 20 の後、T = 1 相当の分布) で決まる。
    - T 1.3 は nucleus の中を平らにするだけで、外の label を戻さない。
    - 到達できる label の集合を広げるのは、top_p 0.8 → 0.95 の方である。
  - repeat_penalty は penalties 段で最初にかかる。
    - 窓 (直近 64 token) には prompt の token も入る (`tools/server/server-context.cpp` の `init_sampler`)。
    - 0.9 では、窓の中の token の logit が上がる (正は ÷0.9、負は ×0.9)。
    - 主に、prompt の末尾にある表示中の 4 選択肢が上がる。正の logit 同士の差は広がるので、温度と逆向きに働く。
  - 1.0 (v2〜v5) は恒等である (`is_disabled`)。
- 写像への入れ方:
  - 挙動は、この sampler chain の下で測る。
  - 版・model digest・model parameters を実行時に観測して照合する (§4)。これで chain を 1 か所で固定する。
  - llama.cpp の版は API から読めないが、公式 build では Ollama の版に同梱の `LLAMA_CPP_VERSION` で決まるので、版の一致で代える。

## 6. 測定量 (実装 = `scripts/body_walk_pilot_scorer.py` の `measure`)

候補 M ∈ {4, 6, 8} ごとに、pilot の step < 12M の窓で計算する。定義は §8 の模擬の意味論に合わせる (v5 の定義を 1 腕で)。
単位は (世界, r) の連鎖で、状態は連鎖 replay したものを使う。

- **⊥ 率** (世界別、窓内の全ステップ)。**世界別の最大 > 0.2 の M は審査しない** (再走しない)。
- 「前回」= その (世界, r, signature) の直近の ⊥ でない応答。「初訪」= 前回が無い訪問。
- 以下の率は、**未成功の signature** で、**今回の応答が表示中の Ω_dev に入る** ものだけを数える。
  - **ŝ_same**:
    - 描画した prompt が今回と **完全一致** する以前の訪問があり (`prompt_sha256` で判定する)、その応答 (⊥ でない直近) が表示中にある再訪を数える。
    - その応答と同じ label を選んだ率。
  - **ŝ_changed**: それ以外の再訪で、前回の label が表示中にあるもの → 前回と同じ label を選んだ率。
  - **h0・h_sw・λ̂_dev**:
    - h0 = 同 weather の成功が 0 の初訪で規則に当たった率。h_sw = 同 weather の成功が 1 以上の初訪で規則に当たった率。
    - λ̂_dev = max(0, (h_sw − h0) / (1 − h0))。どちらかの n が 0、または h0 = 1 なら「無し」。
  - **base** = 同 weather の成功が 0 の初訪の、Ω_dev (正準順) 上の label 割合 (+0.5 の加算平滑化、(k + 0.5) / (n + 2))。
    label ごとの Tally も持つ。
  - **低事前 label**:
    - 各 weather で、平滑化後の点推定が最小の label (同値は正準順の先)。
    - その生の数 k / n の保守限界も出す。
- **Ω 外率** (世界別): 未成功の signature での ⊥ でない応答のうち、表示中の Ω_dev に無いものの率。
- **畳み方** (Codex MEDIUM-2):
  - 4 世界が seed を共有するので、同じ (prompt_sha256, seed) の呼び出しは 1 回の抽選とみなす。
  - ŝ_same・ŝ_changed・base (label 別 Tally)・h0・h_sw は、call_index の最初の 1 件に畳む。
  - 世界別の ⊥・Ω 外は畳まない。
- **保守限界** (v5 DP-5):
  - 挙動の率は、(a) と (b) の外側をとる (下限は小さい方、上限は大きい方)。n = 0 は下限 0・上限 1。
    - (a) 畳んだ呼び出し単位の Wilson 95%
    - (b) 非空の (世界, r) cluster の数を n、cluster 率の平均を p とする Wilson 95%
  - ⊥ と Ω 外の上限は、世界別の呼び出し単位 Wilson 95% 上限の最大 (v5 DC-9)。
- **経験点の入力** (`chains`):
  - 窓 M の終状態 = r block (`PILOT_R` の順) × 4 世界の、成功集合 (開発 signature 順の 0/1) と ⊥ 数。
- **決定性** (記述。scoping ADR §3):
  - (i) ループ段で (prompt_sha256, seed) が同一の呼び出し群の raw 一致率 (t = 0 は各 r で 4 世界が同一)。
  - (ii) 登録 replay の、元の呼び出しとの raw 一致率。
  - いずれかが 1.0 未満なら、本登録は相殺を「期待値で 0」と書く (v4 と同じ)。
  - C = 0 の null の検定は交換可能性に依るので、この率には依存しない。

## 7. 検証 (測定の前に。`validate`)

評価順に適用し、最初に当たったもので止める。`computed` 以外では測定量を出さず、写像を計算しない。
1. **invalid**: 次のどれか。
   - battery の機械検査違反 (`FROZEN_WALK` の封印を含む)
   - 要求条件・実行環境の不一致
   - 記録の schema 違反
   - schedule (plan の接頭辞でない・key・seed の不一致・transport 失敗の後に記録が続く)
   - 再 parse の不一致
   - 連鎖 replay の prompt sha 不一致
   - replay の prompt が元と不一致
2. **not_computed**: ループ部分に transport 失敗がある / ループ部分が 4,608 件に満たない。
   - replay 部分の欠け・失敗は止めない (決定性の n に出る)。
- invalid・not_computed のとき、再走・再開は別の user 裁定とする。pilot を「通るまで」回し直さない。

## 8. 凍結模擬 (実装 = `scripts/body_walk_sim.py`)

**dev 段 (パラメトリック) = 経験的混合方策** (v5 の分岐から探索指示の分岐を除いたもの)。
- κ に依らない。
- 未成功の signature で、上から最初に当たった分岐をとる。分岐ごとに独立の一様乱数を使う。
  0. ⊥ (確率 b)。行動なし。
  1. 成功済みなら規則。
  3. 描画した prompt が今回と同一の以前の訪問があり、その応答が表示中なら、確率 s_same でその応答を反復する。
     無ければ、前回の label が表示中のとき、確率 s_changed で前回を反復する。
  4. 同 weather の成功が 1 以上あれば、確率 λ_dev で規則。
  5. base (表示中の 4 選択肢上の分布)。
- 最後に、未成功の signature で ⊥ でない応答は、確率 oov で Ω_dev 外の label になる (失敗に数える)。
- **同一 prompt の key は成功集合の bitmask** (scoping ADR §1.3・Codex MEDIUM-2 の要件)。
  - R1 の描画は (世界, 成功集合, signature, 表示順) の関数で、表示順は signature ごとに周で不変なので、bitmask は描画状態そのものである。
  - 成功数と表示回転の近似は使わない。
- 逐次の参照実装 (`simulate_dev_reference`) は、同一 prompt と結合を、描画した messages の完全一致で判定する。
  vectorize 版と、同じ一様乱数で完全一致することを test で pin した (結合の両端・⊥・Ω 外・⊥ の後の同一 prompt の再訪を含む 7 設定)。
- **結合** (Codex MEDIUM-1):
  - coupled: 描画が同一の世界は同じ一様乱数を使う (v4 の `_state_keys` / `_coupled`)。
  - independent: 世界ごとに独立。
  - 写像は両端を審査する。
- **経験点**:
  - pilot の窓 M の終状態を、r block 単位で復元抽出する (4 世界がまとめて同じ block)。これで本登録の R 個分の `DevResult` を作る。
  - 族内の共通 seed の結合は、そのまま保たれる。
  - 全点合格の条件に足すだけなので、候補を助ける方向には働かない。小さい候補を落とし、大きい候補または door-close に寄せる。
- **probe 段・基準**: v5 模擬の `kappa_curve` / `design_criteria` を import して使う。
  - これらは `DevResult` だけに依り、軸に依らない。
  - probe 段は v4 と同一の植え付け e = clip(κ·g(n)·1[n > 0] + sd·Z, −1, 1)。K 回は k_rep で 1 回目を反復する。
  - 基準は v4 の `Criteria`:
    - C = 2τ = 0.60 を κ ≤ 1 で植えられ、抽選の平均が目標 ± 0.02。
    - P(PASS | 2τ) ≥ 0.8。
    - P(NO_GO | 0) ≥ 0.8。
    - P(PASS | τ) と P(NO_GO | τ) が上限以下 (sd ≤ 0.3 は α + 3SE、sd = 0.5 は 1.5α)。
    - τ = 0.30、α = 0.05。
- **合成 pilot** (`synthetic_records`):
  - 逐次参照の方策を mock model にして、凍結 plan どおりの記録を作る。
  - 一様乱数は (描画 prompt の sha256, seed) から導く。同一の request は同一の応答になる。
  - scorer の回収 test・写像の end-to-end test・見取り図 (§13) に使う。

## 9. 採否への写像 (実装 = `scripts/body_walk_select.py`)

1. certification (§10) が不備なら何も計算しない (`invalid_certification`)。§7 が `computed` でなければ写像を計算しない (`not_mapped`)。
2. 窓 M で世界別 ⊥ の最大 > 0.2 なら、その M の候補を審査しない。
3. **固定値** (保守側):
   - s_same = ŝ_same の上限
   - s_changed = ŝ_changed の上限
   - oov = max(0.05, Ω 外率の上限)
   - b_hi = ⊥ 率の上限 (床なし、v5 DP-6)
4. **攪乱格子** (全点で基準を満たすことを要求する):
   - dev 段 (18 点):
     - 経験点 2 点: 経験 dev × b {0, b_hi}。
     - パラメトリック 16 点: λ_dev × base × b × 結合。
       - λ_dev {pilot の点推定 (無ければ 0), v4 の 0.43387853…}
       - base {pilot, pilot_low}
       - b {0, b_hi}
       - 結合 {coupled, independent}
     - **pilot_low** (Codex LOW-1):
       - 各 weather で、低事前 label ℓ (§6) の質量を、その生の数の保守下限 lo に置く。
         lo = 呼び出し単位 Wilson 下限と cluster 単位 Wilson 下限の小さい方。
       - 他の label a は p_a · (1 − lo) / (1 − p_ℓ) にする。
       - lo = 0 なら ℓ の質量は 0 になる (その世界の規則は、その weather で base から発見できない)。
     - b_hi = 0 なら b は 1 値に畳む。
   - probe 段 (48 点、v5 と同じ):
     - base {measured, uniform, label_skew, position_skew}
     - sd {0.05, 0.3, 0.5}
     - g {flat, graded}
     - k_rep {0, 0.944}
   - v4 の較正値 (λ_dev・ループ段 base) は v5 の凍結写像から import する (v5 の test が v4 の実走記録からの再計算との一致を pin 済み)。
5. **候補** (R, K, M) ∈ {8, 12} × {5, 10} × {4, 6, 8} を、(呼び出し数 R(30K + 48M), M, R) の昇順に並べる (v5 と同じ)。
   - screening 2,000 回: 格子点を (dev 点, probe 点) の順に審査し、最初の違反点で打ち切る。dev 点は経験点が先。
   - screening を通ったら、本確認 10⁴ 回 (同じ順に審査し、違反点があればそこで打ち切って不合格。合格は全点で満たしたときだけ)。
   - **最初に本確認を通った (R, K, M) を、本登録の設計とする**。
6. **どれも通らなければ door-close** (本登録を起こさない)。これを既定とし、正当な Done である。
   - 呼称は「凍結 channel 上限 endpoint での door-close」。
- 模擬の seed は、点の記述 (dev 点・probe 点・R・K・M・回数・段) の canonical JSON の sha256 の先頭 8 byte (v5 の `point_seed`)。
  評価順に依らない。
- 判定は full precision で行い、丸めは出力だけとする。
- 写像は `run.sh` で 2 回計算し、出力の byte 一致を確かめる。

## 10. 検査器の Done 条件 (CPU、実モデル不使用)

- test (`tests/test_body_walk/`): 計 115 件 (battery 29・scorer 41・模擬 15・写像 19・manifest 11)。
  - battery: 陽性対照つき。
  - scorer: 方策から答えが決まる合成 run・手で数えられる場面・独立の数え直しで、分母の境界を pin する。
  - 模擬: 逐次参照との完全一致・key が描画状態そのもの・結合の両端・経験点の block 抽出・合成 pilot の決定性。
  - 写像: 保守値・pilot_low の式・格子・候補順・選定規則・door-close・窓・引数の受け渡し・見取り図の入力。
- **変異試験** (`scripts/body_walk_mutation_check.py`、`results/pilot_mutation.json`):
  - battery 24・scorer 27・模擬 14・写像 32 の計 97 変異が **全て KILLED**。
  - 落ちた test が、意図した判定行のものかを照合する。no-op・anchor 不一致は不合格。
  - 等価変異と判断して登録から外したもの (harness の docstring):
    - 同一 prompt の key を bitmask から成功数に替える (連鎖の中で成功集合は単調なので、数の一致 ⇔ 集合の一致)。
    - ŝ_same の比較相手を直近の応答に替える (同じ理由)。
    - base の正規化を外す (表は Ω_dev 上で和が 1)。
  - **全 KILLED が certification の条件** (§9-1)。
  - certification は、コード 14 本 (本登録の 4 本と import する凍結物 10 本)・test 7 本・変異 harness の sha256 と、
    変異ごとの明細 (label・status・期待 test・落ちた test) を持つ。
    写像の入口 (`load_certification`) は、明細が 1 件以上・label が一意・全て KILLED であることと、sha256 を照合する。
    manifest は、明細が登録変異の集合 (label と期待 test) と完全一致することを照合する (Codex 2 回目 HIGH、DC-5)。
- **manifest** (`scripts/body_walk_manifest.py`、`manifest.json`) の対象:
  - prereg・run.sh・SEED・certification・見取り図
  - 本登録のコード 6 本・test 7 本
  - import する凍結物 10 本

## 11. 実走と写像の手順 (凍結後、user 裁定) — 凍結しなかったので実行しない (DU-4)

`run.sh` は、本 manifest の `--verify` が凍結条件を満たさないことを報告して止まる。以下は予定していた手順の記録である。

- 公式の経路は `run.sh` だけである (Codex 3 回目 MEDIUM-2)。
  - 低レベルの CLI (`python -m scripts.body_walk_select --records … --meta … --cert …`) は、certification だけを照合する。
    manifest の凍結条件は通らない。
  - この経路を記録に使ってはならない。
  - CLI に gate を足さないのは、`body_walk_select.py` を変えると、certification と見取り図 (7.2 時間) の結び付きが外れて、
    計算し直しになるためである。
  - 実害の面でも、較正 pilot の実データは存在せず、driver も書かない (DU-4)。

1. user 裁定で driver と実走を許可する。
   - driver は §3 の plan・seed と §4 の実行条件で呼び出す。
   - `results/run/records.jsonl` と `results/run/meta.json` を書く。
   - 途中で r・M・decode・parse を変えない。
2. 写像 = `bash experiments/20260930-body-walk-calibration-pilot/run.sh`。
   - 凍結 v2 → v4 → v5 → 本登録の manifest (certification・見取り図とコードの結び付きを含む) の順に照合する。1 つでも違えば計算しない。
   - 検証 → 測定 → 写像を 2 回計算し、byte 一致を確かめる。
   - 候補が本確認に進むと、所要は数時間を超えうる (§13)。セッションに依らない process で走らせる。
3. 凍結前に実データとして読んだものは、v2〜v5 の実走記録 (v5 の選定出力を含む、scoping ADR の原因記述と較正値) だけである。
   本 pilot の実走データは、凍結時点で 1 件も存在しない。
   - 期待値の観測 (§4) は Ollama の API の読み取りで、推論はしていない。

## 12. 設計の経緯と、実データ前に決めたこと

| id | 内容 | 理由 |
|---|---|---|
| DU-1 | /reimagine はハイブリッド。パラメトリックな保守点 (v1) に、pilot の終状態の経験点と合成 pilot (v2) を足す | v1 だけでは模型の楽観 (反復の二重計上・base と反復の独立・結合の仮定、scoping ADR の Codex MEDIUM-3) が素通りする |
| DU-2 | λ は endpoint のみ | ADR の既定で、調整せずに選べる唯一の点。格子にすると選定の自由度と多重性が増える |
| DU-3 | pilot の r は 12 個 (16..27) | cluster が 48 個になり、保守限界が狭まる。経験点で R = 12 を作るとき block の重複が支配しない |
| DC-1 | 実行環境の 3 値を meta で照合 | Codex HIGH-1: 版を要求するだけでは、model 側の既定 (top_k 20) を固定できない |
| DC-2 | 結合の両端を格子に入れる | Codex MEDIUM-1: 決定性が 1.0 未満だと、結合の仮定が理想化になる。v4 は T 0.7 で既に 0.99 / 0.986 だった |
| DC-3 | 畳む対象を明記 | Codex MEDIUM-2 |
| DC-4 | pilot_low の式を固定 | Codex LOW-1 |

- 反復の二重計上の向き:
  - 記憶のない sampler では、同一 prompt の再訪は同じ分布からの独立な抽出になる。
  - 測った ŝ_same は、偶然の一致を含む。
  - 模擬は「s_same で反復、しなければ base から引く (偶然の一致がもう一度起きうる)」なので、未成功の signature での反復を過大に見る。
    つまり保守側である。
  - 合成 pilot の test で、測った反復率が植えた値以上に出ることを pin した。

## 13. 見取り図 (判定に使わない、`results/decision_table.json`)

仮想の挙動値を与えた合成 pilot を、凍結しようとした写像 (`map_run`、certification の照合なし) に通した結果である。
pilot の結果の読み方の目安として作ったもので、写像そのものではない。
- 仮想の挙動: s_same = s_changed = s ∈ {0, 0.5, 0.9}。
  - λ_dev は v4 の値。⊥ と Ω 外は 0。
  - base は v4 のループ段 base を p^(0.7/1.3) で平らにした仮想値 (scoping ADR §1.3 の近似)。
- 合成 pilot は §3 の plan そのものである (12 r・M = 8・4,716 呼び出し)。scorer で測り、保守限界を置いてから写像する。
  - 測った反復率は、偶然の一致を含むので、植えた s より上に出る (§12)。
  - たとえば s = 0 でも、上限は ŝ_same 0.33〜0.39・ŝ_changed 0.33 になる。
- 所要 (16 論理コアの G-GEAR・CPU のみ): 7.2 時間。
- 表は `body_walk_select.py --decision-table` が書いた。
  certification と同じ 14 ファイルの sha256 に結び付く (`target_sha256`)。

| 仮想値 s | 写像の出力 | 経過 |
|---|---|---|
| 0.0 | **door-close** | 12 候補のうち 10 候補が screening で落ちた。9 件が size、1 件が到達不能。(8, 10, 6)・(12, 5, 8) は screening を全 864 点で通ったが、本確認で size が上限を超えた |
| 0.5 | **door-close** | 12 候補とも screening で落ちた。9 件が 2τ に到達不能 (被覆 0.85〜0.89)、3 件が size |
| 0.9 | **door-close** | 12 候補とも screening の 1〜3 点目で落ちた。11 件が到達不能 (被覆 0.72〜0.81)、1 件が size |

s = 0 の行の中身:
- 被覆・到達:
  - 被覆は 0.81〜0.98。κ = 1 での E[C] は 0.57〜0.93。
  - ほとんどの格子点で C = 2τ を植えられた。
  - 例外は、M = 4 で pilot_low の点の被覆が 0.81 に下がり、probe base = measured で届かなかったもの ((12, 5, 4))。
- size の違反 (screening、2,000 回):
  - P(PASS | τ) は 0.065〜0.072 で、上限 0.0646 を超えた。
  - 違反点は、ほぼ全て probe の k_rep = 0.944 (K 回がほぼ同じ応答を繰り返す、v4 の実測値) の点だった。
  - 同じ点を 10⁴ 回で測り直すと 0.048〜0.058 だった (凍結前の確認、`decisions.md` DM-3)。
    MC の揺らぎと、α をわずかに上回る真の size が重なっている。
- size の違反 (本確認、10⁴ 回、上限 0.0565):
  - (8, 10, 6) は 114 点目で 0.0568 だった (結合 coupled・probe uniform・sd 0.3・flat・k_rep 0.944)。
  - (12, 5, 8) は 284 点目で 0.0576 だった (独立結合・position_skew・sd 0.3・graded・k_rep 0.944)。
  - 審査した点の最悪値は、次のとおり。
    - P(PASS | 2τ) 0.920 / 0.971 (下限 0.8)
    - P(NO_GO | 0) 0.898 / 0.976 (下限 0.8)
    - P(PASS | τ) 0.062 / 0.060。これは sd = 0.5 の点で、上限 0.075 の内側。
- 読み:
  - s = 0 は、開発段が最も探索する仮想挙動である。そこでも 864 点の全点合格を求めると、size の上限の際の点がどこかで必ず越える。
  - したがって、この仮想挙動 family と凍結前の判定条件の下で、この写像は pilot の結果に依らず door-close になる。
  - s ≥ 0.5 では、R1 の probe base の天井 (被覆 ≳ 0.9 が要る、scoping ADR §5) が先に効く。

凍結前の取り決め: s = 0 の行が door-close なら、写像は恒真の door-close であり、凍結前に user 裁定を仰ぐ
(v5 DP-6 の教訓)。manifest はこの条件を機械検査する (`freeze_violations`)。
- user 裁定 DU-4 (2026-09-30): 「door-close を今確定する」を採った。
- 却下した案は次の 2 つ。
  - k_rep 0.944 の点の size 上限を 1.5α にするなど、実データ前に基準を変えて見取り図を計算し直す。
    v4 から継承した基準 (v5 DV-4) からの逸脱になる。最も有利な仮想挙動が通るように基準を緩めることにもなる。
  - 恒真を承知で凍結して pilot を回す。GPU を使う意味が無い。

## 14. 本登録への binding 要件 (本登録は起こさない、DU-4。起こす場合に課す予定だった要件の記録)

- 本登録の (R, K, M) は §9 の写像の出力だけで決める。door-close なら本登録を起こさない。
- 本登録の r は < 12。ループ段・probe の seed は `pilot_seeds()` と交わらないことを機械検査する。
- 開発段の decode は `walk_sampling()` の出力 (FROZEN_WALK と一致) を送る。
- probe・C0 の decode は v2 の値で、probe の request は v4 の probe の R1 の描画と byte 一致する (状態ブロック以外も含めて)。
- 実行環境は §4 と同じ 3 値 (Ollama 0.32.12・同じ model digest・同じ parameters) を観測して照合する。版を変えるなら §5 を再確認する。
- 登録 fixture の追加・F1 の τ/4 列挙の再計算・fixture gate の 2 段は、本登録の prereg で行う。
- pilot の記録は、本登録の verdict・power・fixture の計算に使わない (§9 の写像の入力としてだけ使う)。
- claim の上限 (scoping ADR §4) を継承する。PASS の文には次を付す。
  - 「探索の方向はモデル自身の (平らにした) 分布で、量を身体の channel が与えた」
  - 終点の状態と v2 の 12 行一覧の距離 (coverage・行数・発見した weather の数)
  - 高い T での決定性の実測値 (§6、本 pilot と本登録の両方)
  - 「探索的選定の後の確認的登録」
  - 「凍結 channel 上限 endpoint (λ = 1)」
- 言わないこと: 歩行・身体性の効果、人間の歩行と創造性の機構、λ < 1 についての主張。

## 15. 非再開 (継承)

- CLD・Stage B・weight-space door・M13 の閉じた chain を再開しない。
- 論文の本数・分割を本登録から決めない。
- 同じ世界で、seed・摂動・初期 prompt の差だけが違う状態を、分散の源にしない。距離の時間傾きを指標にしない (v4 ADR §0)。
- T・top_p を凍結 channel の外へ上げない (付け替え、scoping ADR §7-2)。

## 16. door-close の記録 (2026-09-30、user 裁定 DU-4)

- **言えること**:
  - v4 から継承した凍結基準と、§13 の見取り図で定めた仮想挙動 family・凍結前の door-close 判定条件の下で、
    (b) の検定は開発段の挙動に依らず起こせない。あらゆる測定値のベクトルについての数学的な全称ではない (Codex 3 回目 MEDIUM-1)。
    基準の中身: C = 2τ を κ ≤ 1 で植え、power 0.8・NO_GO 0.8・size 上限を、48 の probe 攪乱点 × 18 の dev 点の全てで満たすこと。
  - 候補の範囲は、R ≤ 12・K ≤ 10・M ≤ 8・R1 の renderer・probe の k_rep 攪乱 {0, 0.944} である。
  - 根拠: 最も有利な仮想挙動 (s = 0) でも、写像は door-close だった (§13)。
    これは検定の設計容量の限界であり、モデルの挙動についての記述ではない。
- **言わないこと**:
  - 歩行の decode (T 1.3・top_p 0.95・repeat_penalty 0.9) での、qwen3:8b の閉集合選択の決定性・反復率・低事前 label への質量。
    較正 pilot を実走していないので、何も測っていない。
  - 探索の効果の有無。λ < 1 についての主張。「歩行」「身体性」の効果。
- **呼称**:
  - 「凍結 channel 上限 endpoint (λ = 1) の検定を、継承した凍結基準の下で起こせない door-close (設計容量による、挙動の測定なし)」。
  - v5 の door-close は「測った挙動が写像の基準に届かなかった」ものだった。本件はそれと種類が違うので、書き分ける。
- **閉じる経路**:
  - 同一 base の prompt 状態 route のうち、探索を身体の decode 条件に持たせる経路 (scoping ADR の (b))。
  - scoping ADR §8 の他の選択肢 ((a) を検定でない実装として採る、route の door-close) の裁定は、本登録の範囲外。
- **再訪の条件** (いずれも別の scoping と user 裁定):
  - 凍結基準 (特に size の上限と k_rep の攪乱) を、実データ前に別の根拠で改めるとき。
  - probe の天井を持たない renderer に移るとき。
