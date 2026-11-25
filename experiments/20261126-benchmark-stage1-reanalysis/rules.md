# 段 1 の読み方の規則 — 既存記録の再解析 (判別性 gate)

- status: **FROZEN r2** (2026-11-26。集計の前に凍結)
  - r1 = commit 05c7830。
  - r2 = Codex r1 (Revise) の HIGH 3・MEDIUM 4・LOW 2 を反映した版。
  - r1・r2 のどちらの時点でも、項目別の集計は実行していない。
- 上位: `.steering/20261126-benchmark-discriminability-scoping/design-final.md` (FROZEN) の §3 段 1、user 裁定 DU-5
- 実装: `scripts/benchmark_stage1_reanalysis.py`。定数はこの文書の写しで、食い違えばこの文書が正しい
- 起票: `.steering/20261126-benchmark-stage1-reanalysis/`
  - DM-2 = /reimagine の採否
  - DU-6 = 費用の上限・天井の規則
  - DU-7 = 速度の基準
  - DC-1〜9 = Codex r1 の採否

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
- 既知の値から、規則を作る前に決まっていた枝がある (Codex r1 MEDIUM-4)。
  - |C| ≤ q なので、v2 は C ≈ 0.785 から q ≥ 0.785 で、q < 0.5 に当たらないことが確定していた。
  - ⊥ はすべて 0 なので、⊥ の枝は 4 本とも通ることが確定していた。
  - 全 battery が同じ意味で未知だったわけではない。

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
- 単位の値は、4 本とも、凍結の関数の値と、単位ごとに独立に再計算した値が全件一致することを照合する (O_time は 2 arm × 2 書き方から D を再計算する。Codex r1 MEDIUM-1)。C は results.json と一致することを照合する (許容 1e-12)。一致しなければ停止する。
- 記述として併記するもの (判定には使わない)
  - O_time: 書き方別の C、向き × 書き方の 4 成分、記録に無い行動の率。
  - 成分の符号: 相殺か、負の向きへの集中かを読む。

## 3. 出力の分類

- 対象: battery ごと・lever arm ごと。
- 分類は 5 つ: target (w) / foil / Ω 内の残り (other) / Ω 外 (oov) / ⊥。凍結の `category` 関数で出す。
- q = (w + foil) / 全出力、r = w / (w + foil)。C = q(2r − 1) の分解に使う。
- 通信の欠測はない (4 本とも、記録は全件そろっている)。
- w + foil = 0 の arm の r は、未定義として null で出す。JSON は NaN を書かない (`allow_nan=False`)。

## 4. 雑音の推定法 (replicate を cluster にする)

- replicate の内では、arm・族・書き方・probe が layout と seed を共有している。replicate を cluster にすれば、その結合が保たれる。
- 推定量
  - m_r = replicate r の単位の値の平均。
  - σ_rep = sd(m_r) (不偏)。
  - SE(C) = σ_rep / √R。
  - σ_up = σ_rep · √((R−1) / χ²_{0.05}(R−1))。
- σ_rep の意味: 固定した schedule の上での、replicate 間の SD である。
  - 表示の回転は r で決まる。回転の間の平均の差も、この SD に入る。
- σ_up の意味: m_r を独立な正規の標本とみなした正規近似による、計画用の上限である (Codex r1 MEDIUM-2)。
  - 厳密な信頼限界ではない。m_r がすべて等しければ 0 になる。
  - R が小さい battery (v2 は R 4 で、σ_up ≈ 2.92 σ_rep) では大きく出る。そのまま報告し、補正しない。
- 乱数は使わない (解析解)。
- pilot の masked (G・O_time) から、null の σ_rep を記述として出す。計測台 ADR が許した、雑音の envelope の用途である。採否には使わない。

## 5. R の候補の見積もり (段 2 の参考。Δ_min ではない)

- 式: R_raw(Δ) = max(2, ⌈2 · σ_up² · (z_{1−0.05/30} + z_{0.8})² / Δ²⌉)。
- 意味: **単一の battery で、真の差が 0 の対に対して差 Δ を識別するための、1 対あたりの R の概算** である (Codex r1 MEDIUM-3)。
  - 想定: 両モデルの SD に同じ σ_up を代入する。6 モデルの 15 対・両側・Bonferroni・power 0.8 の正規近似で、モデル間の共分散は 0 と置く。
  - 共分散 0 が保守側になるのは、真の共分散が非負の場合だけである。
  - 段 2 の基準 (同時区間の下限が Δ_min を超える) に読み替えるなら、式の分母に入るのは「真の差 − Δ_min」である。
  - 段 2 全体の power (複数 battery を含む検定族) は、ADR どおり OC で評価する。ここでは主張しない。
- R_cost = R_raw を、表示位置が一巡する最小の倍数に切り上げた値 (Codex r1 HIGH-1)。時間・順序・累計は R_cost で計算する。
  - 倍数は各 battery の `check_position_balance` による。v2・v3 は 4、G・O_time は 3。
  - split-half と OC が成り立つかは、段 2 で別に確かめる。
- Δ の格子は {0.10, 0.15, 0.20}。
- 時間 = R_cost × (1 replicate の呼び出し数) × (1 呼び出しの秒)。
  - 整数の秒数と呼び出し数から、有理数で正確に計算する。並べ替えと上限との比較も、丸める前の値で行う (Codex r1 HIGH-3)。
  - 1 replicate の呼び出し数は、記録の全呼び出し数 / R で、C0・対照 arm を含む。
  - 1 呼び出しの秒は、qwen3:8b の本走の実績 (ADR §2 の表)。

| battery | 1 呼び出しの秒 |
|---|---|
| v2 | 200/1200 |
| v3 | 420/2160 |
| G | 375/1728 |
| O_time | 7500/13824 |

- 速度の基準 (DU-7、Codex r1 HIGH-2)
  - 判定に使う時間は、qwen3:8b の速度で換算した時間である。
  - 「1 モデルあたり 3 時間」は、**モデルを平均した 8B 換算の本走の予算**と定義する。
    - 14B は 2 倍遅く、小さいモデルは速いので、平均はおよそ 1 倍と置く (未実測の仮定)。
  - 14B の速度 (2 倍) での時間は、記述の列 (`hours_14b_assumed`) に併記する。判定には使わない。
  - 資格確認 (pilot)・再送は、この予算の外に別枠で置く (ADR §4・BL-3)。
- 参考に、σ = 1 (モデルに依らない上限) の R と時間も併記する。

## 6. 採る / 保留の規則 (順に当てる。最初に当たった理由を記録する)

- (a) **妥当性**: 次のどちらかに当たれば保留する (理由 = validity)。
  - いずれかの lever arm で ⊥ 率 > 0.2。
  - battery 全体の q < 0.5 (q が NaN の場合を含む)。
    - q < 0.5 から直接言えるのは、「過半の出力が target / foil の外にある」ことまでである。
    - その場合、C が対の二択の内の向き (r) より二択への入り方 (q) に強く依存するので、優先度を下げる。
    - モデル間の得点差のうち、どれだけが q に由来するかは、この条件では決まらない (Codex r1 MEDIUM-4)。
- (b) **天井**: C + 1.96 · SE ≥ 0.95 なら保留する (理由 = ceiling)。
  - これは「区間の上端が 0.95 に届いたので、優先度を下げる」という意味である。
  - 天井に到達した証拠としては扱わない。不確実性が大きいために上端が届いた場合を含むからである (Codex r1 MEDIUM-2)。
  - 8B が上限に近いと、≲14B の上側には差の余地がないためである。
  - **床では保留しない**。8B が床でも、他の族や 14B で差が出うる。
- (c) **費用**: (a)・(b) を通った battery を、R_cost(Δ = 0.15) の 8B 換算の時間が短い順に並べる (同じ時間なら名前順)。
  - 累計が **3 時間以内** (ちょうど 3 時間を含む) に収まるところまでを ADOPT とする。
  - 超える battery は保留する (理由 = cost)。その battery を足した場合の累計を併記する。
  - 3 時間 × 6 モデル = 18 時間。ADR §4 の 14〜20 時間の範囲に入る。
- 判定の入力の検証 (Codex r1 LOW-1)
  - q の NaN は (a) で保留する。
  - それ以外の判定の入力 (⊥ 率の最大・C・SE) に非有限の値があれば、判定の前に停止する。noise・R の表も同様に検査する。
- R の逆算: G・O_time の n_units は、整数で、割り切れて、R ≥ 2 でなければ停止する (Codex r1 LOW-2)。

## 7. 段 2 に渡すもの

- 主たる battery (ADOPT) と、保留した battery とその理由。
- battery ごとの値: σ_rep・σ_up・SE、pilot の masked の null σ、R の候補の表、出力の分類 (q・r・⊥)、項目別の d / D。
- 段 2 の事前登録で、改めて決めるもの: Δ_min・同等域・α・R・入場・OC (ADR §2.7 の順)。
