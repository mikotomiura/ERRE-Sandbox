# Profile — M8 Scaling Bottleneck Profiling Calibration

> 4 sample N=3 live runs (1 reuse + 3 fresh on G-GEAR) で metric の暫定分布を
> 取得。decisions.md D4 の解析的閾値が live data の分布と整合するか確認する
> initial calibration。decisions.md D4 で「% 値は live 後に最終化」と pin した
> ものを、本ファイルの観察を根拠に確定 / 微調整する。

## 環境

- **G-GEAR**: Windows 11 Home / NVIDIA RTX 5060 Ti 16GB / Ollama 0.21.2 / qwen3:8b
- **bias_p**: 0.1 (δ baseline と一致、`ERRE_ZONE_BIAS_P=0.1`)
- **personas**: kant, nietzsche, rikyu (N=3)
- **schema**: `scaling_metrics_v1` (本 spike で導入)

## Sample 一覧 (post code-review fix)

| sample | source | duration | dialog_turn | dialog_initiate | num_agents (turns 観測) | M1 bits | M2 | M3 bits | alerts |
|---|---|---|---|---|---|---|---|---|---|
| A | δ run-02 reuse (`runs/run-01/`) | 360s | 12 | 2 | 3 | 0.594 | 0.333 | 0.719 | (none) |
| B | fresh G-GEAR | 90s | 1 | 1 | 2 | None | 0.0 | 0.771 | (none) |
| C | fresh G-GEAR | 90s | 1 | 1 | 2 | None | 0.0 | 0.997 | (none) |
| D | fresh G-GEAR | 120s | 4 | 2 | 2 | 0.0 | 0.0 | 0.767 | (none, post-fix) |

### 初回 calibration の bug と code-review fix (2026-04-26)

初回実行では sample D で M1 alert が fire したが、code-reviewer の HIGH 指摘で
これは **N=2 false positive** だったことが判明:

* `default_thresholds()` の旧式 `math.log2(max(2, num_agents*(num_agents-1)//2))` は
  N=2 のとき C(2,2)=1 だが `max(2, 1)=2` で上限が 1.0 bit に膨張
* threshold 0.30 × 1.0 = 0.30 が分布外要求になり、M1=0 (degenerate marginal) で
  必ず trigger
* 修正: `_pair_max_bits(num_agents)` ヘルパに切り出し、`n_pairs < 2` で 0.0 を返す。
  `_zone_max_bits(n_zones)` も同形ガード。閾値 0 と strict `<` で degenerate
  ケースを silent neutralise

修正後は sample D の M1 = 0 / threshold = 0 で no-alert に flip。再計算済み
JSON は `runs/run-0N/run-0N.scaling_metrics.json` にコミット (run_id は
`sample-NN-recompute` ラベル)。

retrospect: 初回 sample D の "true positive" は **観測者視点では正しい signal**
だった (kant↔nietzsche pair に dialog が完全集中 → relational saturation 極限)
が、N=2 は分母が 1 pair しかない構造的限界で、metric 自体が gate-judgement に
不適。N=2 では metric を silent skip して 4th persona spawn 判定から外すのが
正しい挙動。

artifacts: `runs/run-NN/` 配下に jsonl + scaling_metrics.json + orchestrator.log を保存。
DB は run ごとに `runs/run-NN/run-NN.db` として local 保管したが gitignore 想定 (per-run
M1/M2 再現は journal+DB 両方が要、journal+scaling_metrics 出力のみ committed)。

## 観察 1 — M1 (pair_information_gain) の small-sample 挙動

### 観察値 (有効サンプル: A, D)

* A: 0.594 bits (max 1.585、解析的上限の **37.5%**) ✅
* D: 0.000 bits (max 1.000、解析的上限の **0.0%**) ❌

### 計算可能性

`compute_pair_information_gain` は `history_k + 1 = 4` turn 必要。

| sample | turns | M1 計算可? |
|---|---|---|
| A | 12 | ✅ yes |
| B | 1 | ❌ None (graceful) |
| C | 1 | ❌ None |
| D | 4 | ✅ yes (ぎりぎり) |

**B/C は M1 = None で alert 評価から graceful に除外 → CLI exit 0**。
これは設計通り (decisions.md D3, evaluate_thresholds の None skip 規約) で、
短い run / dialog 不足の状況で false positive を出さない安全弁として機能した。

### Sample D の MI=0 解釈

D の 4 turns: kant→nietzsche, nietzsche→kant, kant→nietzsche, nietzsche→kant。
unordered pair に collapse すると **全て {kant, nietzsche}** の 1 ペアのみ。
marginal 分布も conditional 分布も degenerate → H(pair) ≈ H(pair|history) ≈ 0
(smoothing noise) → MI = 0。

これは観測者視点で「次の pair が完全に予測できる」状態だが、N=2 (= C(N,2)=1
pair しか存在しない) という構造的限界に由来し、metric を gate-judgement に使う
には不適。post-fix では analytic upper bound = 0 → threshold = 0 → M1 = 0 が
strict `<` を満たさず alert は出ない (silent skip と等価)。

### 解析的閾値 (30%) の妥当性

| sample | num_agents | M1/max | 閾値 0.30 と比較 | alert? | 判定 |
|---|---|---|---|---|---|
| A | 3 | 37.5% | > 30% | no | ✅ saturation 余裕あり |
| D | 2 | 0.0% | (max=0) | no | ✅ N=2 silent skip |

A は ample に saturation 余裕あり、D は構造的限界で metric 不適 (silent skip)。
**N≥3 で 30% 閾値が正常動作**する根拠は本 sample では sample A 1 件のみ。M9 で
N=3 long-run + N=4 sample が揃った段階で M1 閾値の最終 calibration を行う。本
spike では「30% × log2(C(N,2)) を確定哲学」として、% 値の最終確定は M9 へ。

## 観察 2 — M2 (late_turn_fraction) の小サンプル振動

### 観察値

* A: 0.333 (12 turns、turn_index 0..5 で midpoint 3 を超えるのは 4-5 → 4/12)
* B: 0.0 (1 turn @ turn_index 0)
* C: 0.0 (1 turn @ turn_index 0)
* D: 0.0 (4 turns 全部 turn_index 0)

### Live signal の質

90-120s の short run では M2 が 0.0 に張り付き、saturation シグナルとしての
解像度が低い。M2 は本来「dialog 後半まで進んでいる = 観測者の注意が turn 序盤
で枯れている」を測る metric だが、短い run では dialog 自体が turn 0-1 で
打ち切られて post-midpoint まで届かない。

### 解析的閾値 (60%) の妥当性

サンプル中 **誰も M2 > 0.5 にすら届かなかった**。閾値 0.60 は relevant data
で trigger に近づくか不明だが、**healthy run では false positive を出さない**
ことは確認できた。

→ 閾値 60% は **provisional**。M9 で長 run (>360s) を重ねたあと再評価。本 spike
では「short run で M2 信号が貧弱」を限界として記録するに留める。

## 観察 3 — M3 (zone_kl_from_uniform) の安定性

### 観察値

| sample | duration | M3 bits | M3/max (= log2(5)=2.322) |
|---|---|---|---|
| A | 360s | 0.719 | 31.0% |
| B | 90s | 0.771 | 33.2% |
| C | 90s | 0.997 | 42.9% |
| D | 120s | 0.767 | 33.0% |

5 zone のうち 4 zone (study/peripatos/chashitsu/garden) が活用、agora は
ほぼ未使用。bias_p=0.1 ベースの zone 分布は uniform から ~30% の divergence
を保つ — 全 sample が **解析的閾値 30% より上** に留まり、healthy 運用の
zone-bias-effective 状態を示す。

### Sample C の peak 値

C は 4 zone のうち 1 zone に dwell 集中 (dialog 短かったため)。M3 = 42.9% で
他 sample より高い (= zone bias 強い、healthy 寄り)。

### 解析的閾値 (30%) の妥当性

全 sample が閾値より上 (alert 出ず)。**閾値 30% を確定**。M9 以降で 4 zone
未使用パターンが連続発生したら (例: agora が常に空)、閾値を 35% に締める
再 calibration を検討する。

## 5/50/95 percentile (有効 sample のみ)

サンプル数が少なく percentile の confidence interval は広い (CI ≈ ±15%)。
M9 で n≥10 を蓄積後に CI と percentile を再計算する。

| metric | n_effective | min | max | ratio (min/max) |
|---|---|---|---|---|
| M1 (pair_information_gain) | 2 (A, D) | 0.0 | 0.594 | 0%-37.5% (max=1.585) |
| M2 (late_turn_fraction) | 4 | 0.0 | 0.333 | 0%-33.3% |
| M3 (zone_kl_from_uniform) | 4 | 0.719 | 0.997 | 31.0%-42.9% (max=2.322) |

## scaling_alert.log

post-fix では sample A-D いずれも alert 出ず、`scaling_alert.log` は空 (= ファイル
非生成)。**alert 機構 (write + exit 1)** は code-review fix 前の sample D で 1 件
書き込み + exit 1 を確認した実績があり、修正前 log の内容は以下:

```
2026-04-26T09:15:06.930551+00:00\tpair_information_gain\t0.000000\t0.300000\tsample-d-fresh-120s
```

修正後は同データで alerts=[] / exit 0 となるが、`evaluate_thresholds` の境界条件
3 通り (=, <, >) は単体テストで pin 済み (`test_evaluate_thresholds_*`、N=2
silent skip テストも追加済み)。

## 結論 — decisions.md D4 への反映

* **M1 閾値 30% × log2(C(N,2)) を確定哲学として採用**:
  - N=3 で max=1.585、threshold=0.476。sample A 0.594 (=37.5%) で healthy
  - **N=2 は構造的限界で silent skip** (`_pair_max_bits` で 0.0 を返し strict `<` で除外)
  - % 値の最終確定は N=3 long-run + N=4 sample が揃った M9 へ defer
* **M3 閾値 30% × log2(n_zones) を確定**: 全 sample 31-43% で false positive 出ず
* **M2 閾値 60% は provisional**: short run では M2 信号貧弱、long-run (>360s)
  での再評価を M9 へ defer
* **M9 への引き継ぎ事項**:
  - n≥10 sample 蓄積後の percentile / CI 再計算
  - long-run (>360s) での M2 distribution 確認
  - 4 zone 未使用パターンが恒常化したら M3 閾値を 35% に締める
  - σ-based fallback の追加検討

## 派生観察 (informational, not gates)

* **dialog_initiate cold-start**: 90s run (B/C) は dialog が 1 件しか発火せず、
  M1 が None で評価不能になる。120s+ で安定して 2+ dialog が出る (D, A)。M9 以降の
  live calibration は **min duration 120s** を guideline とする
* **agora 未使用**: 全 sample で agora の dwell がほぼ 0。bias_p=0.1 では
  preferred_zones 以外 (agora は 3 persona の preferred ではない) への drift が
  弱い。M9 で 4th persona を agora 主体にする実験が立てられる
* **MacBook (`192.168.3.118`) の連続接続**: 全 fresh run で MacBook が
  /ws/observe に reconnect を繰り返した (1-2 接続/秒)。これは Godot 側の自動
  再接続パターンで、δ run-02 で観察した `WebSocketDisconnect (1000)` cosmetic
  log noise (`.steering/20260426-m7-delta-live-fix/decisions.md` D2) と同根。
  本 spike scope 外、ε で対応
