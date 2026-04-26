# Decisions — M8 Scaling Bottleneck Profiling

> Plan mode で v1 (counting / σ-based) と v2 (information-theoretic /
> analytic-bound) を独立に組ませ、ハイブリッド (v2 を主、v1 を補助) を
> 採用。本ファイルは ADR 体裁: 現状 / 選択肢 / 採用 / 根拠 / 次アクション の
> 5 節構造を全 ADR で hold する。

## D1 — pair_information_gain (M1) を mutual information で定義

### 現状

ADR D2 (`observability-triggered`) は dialog pair saturation を 3 metric
の 1 つに掲げているが、operationalization は概念止まり。`requirement.md`
は「同 zone の agent 全対が連続 N turn 同じ pair で閉じている割合」と
記述。

### 選択肢

- **A** (v1): `1 - unique_pairs_in_window / C(N,2)` (ratio counting)
- **B** (v2): `H(pair) - H(pair | history_k)` (mutual information、bits)
- **C**: 上位 1 pair の turn share (top-pair concentration)

### 採用

**B (v2)** を採用。M1 は `pair_information_gain` (単位 bits/turn)。
直近 `history_k=3` turn の pair 列を condition に観測者が次の pair を
予測できる程度を、unconditional Shannon entropy `H(pair)` から差し引いた
mutual information で表す。値 ↓ = 観測者が次の pair を読める = relational
saturation。解析的上限は `log2(C(N,2))`、N=3 で 1.585 bits。

### 根拠

- ADR D2 の哲学「観測限界 = closure condition」と直交しない (観測者の
  情報摂取量を直接測る)
- N に依存しない (上限が `log2(C(N,2))` で解析的)
- M7-δ run-02 の "concentration > volume" 教訓 (turn 数より dyad 偏向が
  belief promotion を駆動した) と整合。MI は dyad 偏向を検出する
- 選択肢 A は ratio で N=3 では離散値が 4 段階しか取れず分解能不足
- 選択肢 C は 1 pair に焦点化しすぎ、3 pair 以上の偏向を検出できない

### 次アクション

- `compute_pair_information_gain(turns, num_agents, history_k=3)` を
  `scaling_metrics.py` に実装
- Laplace smoothing (+0.5/N) + Miller-Madow correction で小サンプル
  bias 補正
- 閾値は **D4** で議論

## D2 — observer_fatigue (M2) は v1 の単純比率を採用

### 現状

`requirement.md` は「reasoning_trace の salience fluctuation / zone
entropy / speech rate 急降下を組み合わせた複合 proxy」と記述。pre-plan
研究は「観察難 (主観) vs compute (客観)」の切り分けを Plan で確定する
よう要求。

### 選択肢

- **A** (v1, simple ratio): `(turn_index > dialog_turn_budget/2) の割合`
- **B** (v2, entropy slope): utterance Shannon entropy の trailing
  window 内 slope (linear regression vs turn_index)
- **C**: Ollama response latency p95 (compute resource downstream)
- **D**: 複合 (A + B + C を normalize して合算)

### 採用

**A (v1)** を採用。M2 は `late_turn_fraction` (ratio in 0..1)。
`dialog_turn_budget = 6` の半分 (= 3) を境に turn_index>3 が dialog_turn
全体に占める割合。値 ↑ = dialog 後半偏向 = 観測者の注意が turn 序盤で
枯れている proxy。

### 根拠

- 小サンプル耐性: B (entropy slope) は trailing window で最低 5 turn
  必要、N=3 / 60-90s / total ~12-17 turn の本 spike では noise 過多
- C (Ollama latency) は compute 領域 (llm-inference Skill 範囲) で
  本 spike scope 外
- D (composite) は v1 design で reject (calibration を簡潔化、各 metric
  独立で 3 本の閾値を出す方針が requirement.md L34 と整合)
- v2 entropy slope への昇格は M9 で run 5+ 集まった後の reconsider に
  譲る (Out of scope)

### 次アクション

- `compute_late_turn_fraction(turns, budget=6)` を実装
- 閾値は **D4** で議論

## D3 — zone_kl_from_uniform (M3) を KL divergence で定義

### 現状

`requirement.md` は「5 zone の滞留時間 Gini 係数、低いほど flat (bias
発火の意味喪失)」。pre-plan 研究は zone info の log source が
`dialog_turns` table に **無い** ことを確認、journal の
`agent_update.position.zone` か新 sqlite table か denormalize かを Plan で
確定するよう要求。

### 選択肢

- **A** (v1, Gini): per-agent zone dwell time の Gini 係数、全 agent 平均
- **B** (v2, KL from uniform): zone occupancy 分布と uniform の
  Kullback-Leibler divergence (bits)
- **C**: Shannon entropy `H(zone)` (uniform から測らず絶対値)

### 採用

**B (v2)** を採用。M3 は `zone_kl_from_uniform` (単位 bits)。全 agent の
per-zone occupancy seconds を normalize → `KL(observed || uniform)`。
値 ↑ = zone 偏向 = bias 効いている (healthy)、値 ↓ = uniform 化 = bias
失効 = scaling trigger。解析的上限は `log2(n_zones)`、5 zone で 2.322 bits。

入力 source: **journal の `agent_update.agent_state.position.zone`**
(top-level dict、tick + agent_id + position.zone)。schema 変更
(denormalize / 新 table) は requirement.md L29 で scope 外。`--journal`
省略時は M3 = `None` で graceful degradation。

### 根拠

- KL は単位が bits で M1 と揃う (decisions.md の解析が可能)
- N=2 でも well-defined (Gini は N=2 で degenerate)
- uniform prior (1/n_zones) は強い仮定だが、本 spike では「zone bias の
  失効」を測るのが目的で、uniform からの divergence が落ちる = bias
  失効と素直に解釈できる
- C (絶対 entropy) は最大値が `log2(5)` で B の `log2(5)` と同じだが、
  「bias 効いていない = 0 ではなく log2(5)」と方向が逆で読みにくい
- 選択肢 A の Gini は M1/M3 と単位が揃わない (ratio vs bits)

### 次アクション

- `compute_zone_kl_from_uniform(snapshots, n_zones=5)` を実装
- snapshot 列の dwell 復元: 連続 2 snapshot 間の Δtick × tick_seconds を
  zone bucket に加算 (run 開始/終了の境界 dwell は除外)
- `--journal` 欠落時は M3 = `None`、`evaluate_thresholds()` で `None`
  metric は alert 対象から除外、CLI exit code は M1/M2 のみで判定
- 閾値は **D4** で議論

## D4 — 閾値判定は σ-based を捨て解析的上限の % で表現

### 現状

pre-plan 研究 §軸 2 は「`mean + 1.5σ` を各 metric に apply」を提案。
しかし N=3、run-count 3-5 では σ 推定の自由度が足りず noise に跳ね
上がる。

### 選択肢

- **A** (v1): `mean + 1.5σ` empirical thresholds
- **B** (v2): 解析的上限の % (e.g., 30% × log2(C(N,2)))
- **C**: trend (連続 K turn で減少) trigger
- **D**: A + B 両方 (二段構え)

### 採用

**B (v2)** を採用。3 metric の trigger 条件:

| metric | trigger 条件 | 根拠 |
|---|---|---|
| M1 (pair_information_gain) | < 30% × log2(C(N,2)) | relational headroom 7 割消費 |
| M2 (late_turn_fraction) | > 0.6 | dialog 後半 60% 偏向 (経験則) |
| M3 (zone_kl_from_uniform) | < 30% × log2(n_zones) | uniform divergence 30% 未満 = flat |

3 metric は独立スカラー (composite C は採用しない、requirement.md L34
「閾値案 3 本」と整合)。1 metric でも trigger → `scaling_alert.log` に
1 行 TSV (`timestamp\tmetric\tvalue\tthreshold\trun_id`) 追記 → CLI exit
code 1。

`%` 値 (M1=30%, M2=0.6, M3=30%) は **provisional**。live calibration
(N=3, 60-90s × 3 + δ run-01/run-02 流用 = 5 sample) 後、観測値の
5-95 percentile が解析閾値の外なら `decisions.md` に増分版を追記。
本 ADR は「解析的上限の % を選ぶ哲学」を確定する。

### Live calibration 後の閾値確定 (2026-04-26)

`profile.md` の 4 sample (1 reuse + 3 fresh G-GEAR runs) で initial
calibration を実施し、以下を確定:

| metric | 閾値 | 確定根拠 |
|---|---|---|
| M1 pair_information_gain | < 30% × log2(C(N,2)) | 哲学確定。N=2 は分母 1 pair で構造的限界 → 上限 0 / threshold 0 / strict `<` で silent skip。% 値の最終 calibration は M9 で N≥3 sample 蓄積後 |
| M2 late_turn_fraction | > 0.6 | **provisional** — short run では M2 が 0.0 に張り付き relevant data 不足。M9 で long-run 再評価へ defer |
| M3 zone_kl_from_uniform | < 30% × log2(n_zones) | 全 sample 31-43% で false positive 出ず |

### Code-review fix の retrospect (HIGH 指摘 1 件)

初回実装の `default_thresholds` は `math.log2(max(2, num_agents*(N-1)//2))`
で N=2 のとき `max(2,1)=2` → 上限 1.0 bit に膨張、threshold 0.3 が分布外要求と
なり M1=0 (degenerate) で必ず false positive。

修正: `_pair_max_bits(num_agents)` / `_zone_max_bits(n_zones)` ヘルパに切り出し、
`n_pairs < 2` で 0.0 を返すように。閾値 0 と strict `<` で degenerate ケースを
silent neutralise する設計に変更。N=2 の false positive 防止テスト
(`test_default_thresholds_n2_neutralises_pair_metric`) を追加。

修正前 sample D で観察された M1 alert (`scaling_alert.log` 1 行記録 + CLI exit
1) は **alert 機構動作の存在証明** として retain (live で write + exit 1 が動作
する run-time evidence)。修正後は同 data で alerts=[] / exit 0、境界条件単体
テストで write/skip の両 path 検証済み。

### 根拠

- N に依存しない次元無し閾値 (N=3 でも N=10 でも同じ式)
- 小サンプル耐性 (σ 推定の暴れを回避)
- `log2(C(N,2))` / `log2(n_zones)` は解析的に決まる、calibration 不要
- M2 だけ ratio 閾値なのは v1 採用 (D2) との整合 (entropy slope 化を
  したら % 表現に揃えられるが M9 へ deferral)
- σ-based fallback は M9 で run 5+ 蓄積後に追加検討 (Out of scope)

### 次アクション

- `evaluate_thresholds(metrics, thresholds, run_id, log_path)` 実装
- 単体テストで境界条件 (=, <, >) 3 通り pin
- live calibration 後に観測値が解析閾値外なら % を 30→40 等に微調整、
  本 ADR に追記

## D5 — D3 (session_phase model) との metric scope 分離

### 現状

ADR D2 の A2-f (「user を 4 体目扱い」) は ADR D3 (`session_phase`
model) と交叉。本 spike の閾値が autonomous run 用と Q&A epoch 用で
異なるべきかを Plan で確定する。

### 選択肢

- **A**: 本 spike の metric は AUTONOMOUS phase の dialog_turn のみ計算、
  Q&A phase の user 発話は metric から除外
- **B**: 両 phase を含めて計算、phase 別 breakdown を出力
- **C**: phase 区別せず (= D3 未実装の現状と等価)

### 採用

**A** を採用 (デフォルト)。ただし D3 (`session_phase` field) が現時点で
未実装のため、本 spike では **C 等価動作** (全 turn を AUTONOMOUS とみなして
計算)。decisions.md に「D3 実装後に `aggregate()` 内で
`session_phase != AUTONOMOUS` の turn を filter で落とす一段落を追加」
旨を明記。

### 根拠

- ADR D2 の閾値判定対象は autonomous behavior の質、Q&A は user 介入で
  bias 発生、metric が真の trigger を反映しなくなる
- D3 未実装の現状で B を実装するのは over-engineering (Out of scope)
- C (区別なし) で出発し、D3 実装時に `aggregate()` の 1 行追加で A に
  移行するのが最小変更

### 次アクション

- `aggregate()` の docstring に「D3 実装後の filter 拡張点」を明記
- 本 spike の live calibration は全て `autonomous_only` 仮定 (D3 未実装
  なので等価動作)
