# 事前登録 — 個性化 door 条件①: weight-space の seed floor (spike)

本文書は計算の**前に**凍結する。凍結前に Codex (gpt-5.5/xhigh) の independent review を受け、1 周目 (Revise: HIGH 2・MEDIUM 4・LOW 3) と 2 周目 (Adopt-with-changes: HIGH 0・MEDIUM 3・LOW 2) の指摘を全て反映した (`.steering/20260926-individuation-door-condition1/codex-review.md` / `codex-review-2.md`、ローカル)。計算スクリプト `scripts/individuation_wellposedness.py` は起動時に
本ファイルの sha256 を観測して `results/results.json` の `prereg_sha256` に書く。本文書を凍結後に
変更した場合、その結果は本登録の結果ではない。

ADR 本体 (ローカル) = `.steering/20260926-individuation-door-condition1/design.md`。

## 1. 問い

weight-space は、M11-C3b の behavioral space が与えなかった noise floor を与えるのか。
具体的には: **同一 corpus・同一設定で seed だけ変えて学習した persona-LoRA 3 本の間の散らばりが、
それらの base からの変位より小さいか**。これは floor の存在の必要条件であり、個体間の分化も
J-space も測らない (§7)。

## 2. 入力 (固定)

| 役割 | path (repo 相対、gitignore 済・著者機のみ) |
|---|---|
| seed 42 | `data/lora/m9-c-adopt-v2/kant_constrained_mlp_gate_seed42_v1/adapter_model.safetensors` |
| seed 43 | `data/lora/m9-c-adopt-v2/kant_constrained_mlp_gate_seed43_v1/adapter_model.safetensors` |
| seed 44 | `data/lora/m9-c-adopt-v2/kant_constrained_mlp_gate_seed44_v1/adapter_model.safetensors` |
| 陽性対照 | `data/lora/m9-c-adopt-v2/kant_constrained_mlp_gate_seed42_v1/checkpoint-1000/adapter_model.safetensors` |
| 陰性対照 | `checkpoints/mock_kant_r8/adapter_model.safetensors` (ΔW≡0) |

各ファイルの sha256 は results.json に記録する。3 本は r=16、lora_alpha=32、target =
q/k/v/o/gate_proj、2500 step SFT、warm-start なし。seed は初期化に加え ja_drop 5% の部分標本と
eval split も動かすので、ここで測る floor は「初期化 + データ部分標本」の合算である。

除外 (結果を見る前に決定): KTO spike adapter 群は全 seed が同一 SFT adapter から warm-start しており、
seed 間類似度が共有初期値で偽に高く出るため使わない。

## 3. 計量

module m (36 層 × {q,k,v,o,gate}_proj = 180) ごとに ΔW = s·B·A (s = α/r = 2)。

- **判定計量 1 = cos_G**: ΔW から定義される出力側 Gram G = ΔWΔWᵀ の Frobenius cosine (方向の再現性)。
  ⟨Ga, Gb⟩_F = ‖ΔWaᵀΔWb‖_F² を r×r 行列の trace で計算する。
- **判定計量 2 = ρ_G** = ‖Ga − Gb‖_F / mean(‖Ga‖_F, ‖Gb‖_F) (正規化しない。ノルムの食い違いも散らばりに数える)。
- G を選ぶ理由 (解釈補助であって判定の前提ではない): LoRA の A は seed 固有の乱数初期値付近に留まりやすく、
  raw ΔW の入力側は seed ゲージが支配しうる。G = s²·B(AAᵀ)Bᵀ は AAᵀ ≈ cI なら ∝ BBᵀ になる。AAᵀ ≈ cI が
  成り立たなくても G は ΔW の出力側共分散として定義どおり有効で、その場合は「seed ゲージを除いた学習成分」
  という解釈だけが弱まる (D0 で記述報告)。
- **ノルムが 0 の module** (陰性対照) では cos_G は UNDEFINED とし、数値として集計しない。
- 集約: pair ごとに 180 module の cos_G と ρ_G の中央値 (UNDEFINED を含む pair は判定計量が無い = 仮説不成立)。

## 4. null

- **N-seed** (本命): 同一データ・別 seed の 3 pair (42,43) (42,44) (43,44)。
- **N-shift** (無関係な LoRA 同士の基準): pair (a,b) について、同じ module 型で層 l と層 l'≠l を組んだ
  全組合せの cos_G。pair ごとに分布を作り、その 99 パーセンタイル (numpy `percentile`、
  `method="linear"`) を閾値とする。隣接層の共有構造で null は膨らみうる (= H1 を落としやすい側)。

## 5. 判定 rule

### G0 validity (1 つでも落ちたら `INVALID_SCORER`、H1/H2 は評価しない)
- G0-a: 5 入力が全て読める (sha256 計算・読込・parse の例外は捕捉して G0-a fail とし、例外終了しない)。
  module の親 path が正しい (q/k/v/o は self_attn、gate は mlp)。3 seed と
  陽性対照の module 集合が {0..35} × {q,k,v,o,gate}_proj と完全一致し、B・A の shape が一致し、
  adapter_config の r / lora_alpha / use_rslora / rank_pattern / alpha_pattern / target_modules (集合) が一致する。
- G0-b: 自己 pair (a,a) の cos_G が全 module で 1 (許容 1e-6)。
- G0-c: 陰性対照 (mock) の module 集合が {0..35} × {q,k,v,o}_proj と完全一致し、ΔW ノルムが全 module で 0 で、cos_G が UNDEFINED を返す (0 や 1 に畳まれない)。
- G0-d: 同 seed trajectory の sanity check (seed42 checkpoint-1000 vs seed42 最終) の中央値 cos_G が、同 pair の
  N-shift p99 を超える。初期値を共有するので高くて当然の組であり、これは seed ゲージを超えた検出力の証明では
  ない。計量コードの正しさの主証拠は合成行列 test (`tests/test_individuation_wellposedness/`) である。

### 仮説
- **H1** (seed 間に共有構造がある): 3 pair 全てで median_m cos_G(一致 module) > p99(N-shift)。
- **H2** (出力側 Gram の複製の散らばりが base からの変位より小さい): 3 pair 全てで
  median_m cos_G > 0.5 **かつ** median_m ρ_G < 1。
  0.5 の導出: 正規化 Gram Ĝ で ‖Ĝa − Ĝb‖ < ‖Ĝa − 0‖ (base = 0 からの距離) ⇔ cos_G > 0.5 (方向)。
  1 の導出: ‖Ga − Gb‖ < mean(‖Ga − 0‖, ‖Gb − 0‖) (ノルムを含む変位)。方向だけ揃いノルムが大きく食い違う
  場合は ρ_G で落ちる。
- 解釈の範囲 (ρ_G): cos_G と ρ_G はいずれも共通スケールに不変で、更新の絶対的な大きさは判定しない
  (relative geometry のみ)。‖ΔW‖_F の最小値・中央値を記述報告する。
- 解釈の範囲 (H1): H1 が通っても示すのは「同一 module 位置での seed 間の再現性が層ずらし null を超えた」までで、
  persona 固有性は主張しない (別 persona や random-data の対照が無い)。

### verdict (docs/research-positioning.md §8 の既存語のみ、新設しない)
- G0 のいずれかが fail → `INVALID_SCORER`
- G0 pass ∧ H1 ∧ H2 → `PASS`
- G0 pass ∧ H2 ∧ ¬H1 → `INCONCLUSIVE_UNDERPOWERED` (複製は再現するが、層ずらし null がそれを無関係な層同士と
  識別できない = この null の識別力不足。layer 横断で共有される構造があると null が膨らむ経路)
- それ以外 (G0 pass ∧ ¬H2) → `NO_GO_EFFECT_ABSENT` (適用範囲は「この spike の scorer・入力で、出力側 Gram の
  seed floor が変位より小さいことが観測されない」まで。weight-space 一般や J-space の否定ではない)

## 6. door 帰結 (事前に凍結、二者択一)

- `PASS` → 個性化 door を **door-open 候補として条件②へ進める**。②③では同じ rule を J-space で再確立する
  義務を負う。PASS は「個性化した」ことを意味しない (§7)。
- `NO_GO_EFFECT_ABSENT` または `INCONCLUSIVE_UNDERPOWERED` → **door を開けない = 閉じて arc に終端を付ける**
  (条件①が満たされないので②へ進む根拠が無い)。M11-C3b terminate ADR の会計方式 (functional artifact +
  方法論 finding + ADOPT negative verdict) を踏襲し、reactivate path を用意する。終端の文言は「この spike で
  条件①を満たさなかった」に限定し、weight-space 一般・J-space を否定しない。`INCONCLUSIVE_UNDERPOWERED` の
  reactivate path は「識別力のある別 null (別 persona / random-data の LoRA) を安価に用意できたとき」。
  「J-space なら救える」は、それ自体を別 ADR で安価な証拠によって示さない限り再開理由にしない。
- `INVALID_SCORER` → verdict を出さず、user 裁定に回す。

## 7. 限界 (結果によらず ADR に書く)

- 測るのは persona-LoRA P の **複製可能性** (floor の存在の必要条件)。個体 i = P + δ_i の分化は、
  個体ごとの履歴で学習した LoRA が要り、本 spike では測らない。
- ΔW-space と J-space は別 estimand。ΔW で PASS しても J で成り立つ保証はない。
- 入力は kant 単一 persona・1 設定・3 seed。一般化しない。
- LoRA 本体は非公開 (gitignore) で、外部の再計算は不可。計量コードは合成行列の test で CI 上で検査する。
- `go-no-go-adr.md` §9 の frozen 値は一切使わない。0.5 は幾何からの導出、p99 は in-data null。

## 8. 記述報告 (判定に使わない)

raw ΔW の cosine と ρ = ‖ΔWa − ΔWb‖ / mean(‖ΔWa‖, ‖ΔWb‖)、module 型別の cos_G 内訳、層ずらし null の中央値、
D0 = A の初期値 (kaiming uniform、境界 1/√d_in) からの逸脱統計 (行ノルム、境界超過率、AAᵀ の非対角比)。
