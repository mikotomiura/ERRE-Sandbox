# 段 1 の読み方の規則 — 既存記録の再解析 (判別性 gate)

- status: **FROZEN** (2026-11-26。集計の前に凍結。この commit の時点で、項目別の集計は実行していない)
- 上位: `.steering/20261126-benchmark-discriminability-scoping/design-final.md` (FROZEN) の §3 段 1、user 裁定 DU-5
- 実装: `scripts/benchmark_stage1_reanalysis.py`。定数はこの文書の写しで、食い違えばこの文書が正しい
- 起票: `.steering/20261126-benchmark-stage1-reanalysis/` (DM-2 = /reimagine の採否、DU-6 = 費用の上限・天井の規則)

## 0. 用途の限定 (DU-5)

- 段 1 の「採る / 保留」は、段 2 の主たる battery の**優先順位づけ**である。
  - battery を閉じる判断ではない。
  - **1 モデル (qwen3:8b) の結果で battery を閉じない。** 保留した battery は、段 2 の後段の候補として残る。
- 旧 verdict を再判定しない。書き換えない。ここで出す区間は検定ではなく、位置と費用の記述である。
- Δ_min・同等域は、ここでは決めない。§5 の Δ は R を見積もるための参照値で、Δ_min ではない。
- 段 1 で見た記録は、段 2 の確認データにしない。段 2 は、seed と割付を分けた新しい記録で判定する。
- 既知の集計値: 4 本の results.json の C (v2 0.785・v3 0.254・G 0.149・O_time 0.105、⊥ はすべて 0) は、規則を作る前から知っていた。
  未知だったものは次の 3 つ。
  - 項目別の d / D
  - replicate の雑音
  - 出力の分類 (q・r)

## 1. 入力 (read-only。sha256 を実行時に照合し、不一致なら停止する)

| key | path | sha256 |
|---|---|---|
| v2_records | experiments/20260926-skill-lever-pilot/results/run/samples.jsonl | d0cf5084201a138f92f391ba60d4c66bd9cab6ce7f0c95d8af0b4b8692f7125a |
| v2_results | experiments/20260926-skill-lever-pilot/results/run/results.json | fc71df8e9c94c5f4005b6267062bb818bba4dbd62fffafacb52902741b8da2c0 |
| v3_records | experiments/20260926-experience-skill-pilot/results/run/samples.jsonl | 52c2140fa9e34c9105197be13acb6a1e6a6eb5f4c1208529194bde1e7a85c8cc |
| v3_results | experiments/20260926-experience-skill-pilot/results/run/results.json | 508893ba1a5c0fff52afd17df25842732b08b28bfee55598961920744d8c3c81 |
| g_records | experiments/20261001-generalization-probe-pilot/results/run/records.jsonl | 97ec2c5b88907583611135d36285e672c723329a9cd4eb2796ebb4348b14766d |
| g_results | experiments/20261001-generalization-probe-pilot/results/run/results.json | 430f2724504f7114486ddc009b7dd753b7d58f17b90098cd0f9113d98dc71d44 |
| g_pilot_records | experiments/20261001-generalization-probe-pilot/results/pilot/records.jsonl | eb9495cd63aa0893d8193a02f305619f3ebb7a2cb5f703a3f56b3027dceba4ef |
| ot_records | experiments/20261008-o-time-probe-pilot/results/run/records.jsonl | 26a18bcd9e179dd4d7f049865b2a024050bdf270f15a65c4c2adb8e9665eb972 |
| ot_results | experiments/20261008-o-time-probe-pilot/results/run/results.json | 156c64affadc6a7e962b321bad8cd218941895e7543d3eb1d95f0a7dc618e274 |
| ot_pilot_records | experiments/20261008-o-time-probe-pilot/results/pilot/records.jsonl | 29935540360d8efdf4863bd1674554cdb356c390b23b7a149c1f73f7fb1dd13b |

- 凍結 dir の scorer・battery・pilot gate は import だけにする。`PYTHONDONTWRITEBYTECODE=1` で実行する。
- JSONL は LF だけで行に割る (`splitlines()` は使わない)。
- G の本走の R は `n_units / (2 族 × 8 つ組)`、O_time の本走の R は `n_units / (2 族 × 6 部屋)` で、それぞれの results.json から読む。

## 2. 項目別に見る量 (対を完成させた d / D)

| battery | 単位 (凍結の関数) | 項目 | 項目の値 |
|---|---|---|---|
| v2 | (族, r) の d = `family_units(component_scores)` | probe 6 | probe ごとに (s_a + s_a_rot)/2 を族で平均し、replicate ごとに持つ |
| v3 | 同上 (`skill_experience_scorer.component_scores`、POINTS_AS)。判定 4 arm だけを使う | probe 6 | 同上 |
| G | (r, 族, つ組) の d = `unit_scores(arm_unit_scores)` | probe 24 | 同上 (族内の 2 arm) |
| O_time | (r, 族, 部屋) の D = `unit_scores(cell_scores)` | 部屋 6 | 部屋ごとに、D を族で平均する |

- arm ごとの |s の平均| は使わない。
  - O_time では、札の数が大きい行を選ぶ方策 (`digit_rank("max")`) が、書き方別の C で ±1 になり、対を完成させた D で 0 になる。これは test で固定している。
- 単位の値は、自前で集計した値と凍結の関数の値が一致することを照合する。C は results.json と一致することを照合する (許容 1e-12)。一致しなければ停止する。
- 記述として併記するもの (判定には使わない)
  - O_time: 書き方別の C、向き × 書き方の 4 成分、記録に無い行動の率。
  - 成分の符号: 相殺か、負の向きへの集中かを読む。

## 3. 出力の分類

- 対象: battery ごと・lever arm ごと。
- 分類は 5 つ: target (w) / foil / Ω 内の残り (other) / Ω 外 (oov) / ⊥。凍結の `category` 関数で出す。
- q = (w + foil) / 全出力、r = w / (w + foil)。C = q(2r − 1) の分解に使う。
- 通信の欠測はない (4 本とも、記録は全件そろっている)。

## 4. 雑音の推定法 (replicate を cluster にする)

- replicate の内では、arm・族・書き方・probe が layout と seed を共有している。replicate を cluster にすれば、その結合が保たれる。
- 推定量
  - m_r = replicate r の単位の値の平均。
  - σ_rep = sd(m_r) (不偏)。
  - SE(C) = σ_rep / √R。
  - σ_up = σ_rep · √((R−1) / χ²_{0.05}(R−1)) (σ の上側 95% 限界)。
- R が小さい battery (v2 は R 4) では σ_up が大きく出る。そのまま報告し、補正しない。
- 乱数は使わない (解析解)。
- pilot の masked (G・O_time) から、null の σ_rep を記述として出す。計測台 ADR が許した、雑音の envelope の用途である。採否には使わない。

## 5. R の候補の見積もり (段 2 の参考。Δ_min ではない)

- 式: R(Δ) = max(2, ⌈2 · σ_up² · (z_{1−0.05/30} + z_{0.8})² / Δ²⌉)。
  - 想定: 6 モデルの 15 対、両側、Bonferroni、power 0.8。
  - モデル間の共分散は 0 と置く (保守側)。
- Δ の格子は {0.10, 0.15, 0.20}。
- 時間 = R × (1 replicate の呼び出し数) × (1 呼び出しの秒)。
  - 1 replicate の呼び出し数は、記録の全呼び出し数 / R で、C0・対照 arm を含む。
  - 1 呼び出しの秒は、qwen3:8b の本走の実績 (ADR §2 の表)。

| battery | 1 呼び出しの秒 |
|---|---|
| v2 | 200/1200 |
| v3 | 420/2160 |
| G | 375/1728 |
| O_time | 7500/13824 |

  - 14B は 2 倍程度と見込む (未実測)。表の時間は qwen3:8b の速度で出す。
- 参考に、σ = 1 (モデルに依らない上限) の R と時間も併記する。

## 6. 採る / 保留の規則 (順に当てる。最初に当たった理由を記録する)

- (a) **妥当性**: 次のどちらかに当たれば保留する (理由 = validity)。
  - いずれかの lever arm で ⊥ 率 > 0.2。
  - battery 全体の q < 0.5 (q が NaN の場合を含む)。q < 0.5 のときは得点差の過半が対の二択への入り方で決まり、「属性が定める向き」の比較として読みにくい。
- (b) **天井**: C + 1.96 · SE ≥ 0.95 なら保留する (理由 = ceiling)。
  - 8B が上限に近いと、≲14B の上側には差の余地がないためである。
  - **床では保留しない**。8B が床でも、他の族や 14B で差が出うる。
- (c) **費用**: (a)・(b) を通った battery を、R(Δ = 0.15) の時間が短い順に並べる (同じなら名前順)。1 モデルあたりの累計が **3 時間以内** に収まるところまでを ADOPT とする。
  - 超える battery は保留する (理由 = cost)。その battery を足した場合の累計を併記する。
  - 3 時間 × 6 モデル = 18 時間。ADR §4 の 14〜20 時間の範囲に入る。
- 判定の入力 (noise・R の表・決定) に非有限の値があれば、停止する。

## 7. 段 2 に渡すもの

- 主たる battery (ADOPT) と、保留した battery とその理由。
- battery ごとの値: σ_rep・σ_up・SE、pilot の masked の null σ、R の候補の表、出力の分類 (q・r・⊥)、項目別の d / D。
- 段 2 の事前登録で、改めて決めるもの: Δ_min・同等域・α・R・入場・OC (ADR §2.7 の順)。
