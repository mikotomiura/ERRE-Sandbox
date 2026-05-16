# DA-15 draft V1 — main agent 生成

> **生成主体**: main Claude Code session (Opus 4.7)。本 file は **/reimagine
> 対象**であり、V2 (Task tool subagent 独立生成) と比較して使い分ける。確定 ADR
> ではない。

## 0. 直接の empirical 事実 (前提)

- DA-14 verdict (`da14-verdict-v2-kant.json`):
  - Vendi semantic Cohen's d = **-0.179** (target ≤ -0.5; correct sign, 36% of
    magnitude target)
  - Burrows reduction = **+0.43%** (target ≥ 5%; positive but 11.7× short)
  - ICC(A,1) = **0.913** ✅ (threshold 0.55、CI 0.881-0.969)
  - throughput 98.8% ✅
  - kant 2-of-3 primary quorum **未達**
- Pre-training weight audit (`weight-audit.json`):
  - N_eff = 3886.4 ✅
  - top 5% weight share = 0.139 ✅
  - **de+en weighted mass = 0.489** ⚠️ soft warning (target 0.60)
  - per-language: ja=0.498, en=0.278, de=0.211, mixed=0.013
- Training execution (DI-7): 4000 steps 完走、final eval_loss = 0.180
  (step 2000 で 0.166 → final 0.180、軽微 over-fit 兆候)、peak_vram = 10.62 GB
- 方向性 vs prior: Vendi が **wrong sign → correct sign** に反転 (prior +1.39 →
  v2 -0.13)。Burrows は prior -1.38 → v2 -0.49 でわずか後退。

## 1. 候補 Plan の equal-footing trade-off

### Plan A: Vendi kernel swap

**Hypothesis**: 現行 `sentence-transformers/all-mpnet-base-v2` (英語中心の汎用
encoder) は **persona-style shift に対し過剰に invariant** で、ドイツ語哲学体
で Kant 様 long-form syntax を出力しても embedding 距離が伸びない。multilingual
encoder (e.g. `intfloat/multilingual-e5-large`, `BAAI/bge-m3`) や哲学
domain-tuned BERT に swap すると、同じ生成 token から大きな Vendi shift が
測定できる可能性。

| 項目 | 値 |
|---|---|
| 必要新規データ | ゼロ (既存 multi-turn pilot 出力を再 score) |
| 必要新規 training | ゼロ |
| compute 見積 | **~15-30min** (kernel install + n=6 windows × 2 conditions × 2 personas を再 score) |
| codebase 変更面積 | 小 (`compute_baseline_vendi.py` の embedding model 引数追加 + multilingual-e5 install) |
| C1-C4 gap address | ❌ training-side gap には touch せず、**measurement-side のみ** |
| predicted Cohen's d 改善幅 | -0.3 to -0.7 (kernel 依存、prior art 要 Codex 調査) |
| risk: 反転 | kernel が LoRA-on / no-LoRA **両方を同等に shift** させて diff が縮む可能性 |
| risk: 後追い | 別 kernel で pass しても "Vendi instrument の選択を後付けで都合よく変えた" と読まれ HIGH-3 グレーゾーン (threshold 自体は不変だが、metric 計算手法が変わる) |
| reversibility | 完全 (training 不要、いつでも mpnet に戻れる) |

**HIGH-3 grey-zone note**: DA-14 thresholds は `vendi_semantic` axis の数値
(d ≤ -0.5) を変えないが、**kernel を変えると d の母集団が変わる**。これは
"threshold movement ではない" と解釈可能だが、Codex 側で "metric methodology の
post-hoc shift も HIGH-3 同等" と判定される可能性あり。ADR D-15 では明示的に
"kernel change は metric **methodology** の改善であり threshold movement ではない"
を rationale で語る必要がある。

### Plan B: Candidate C targeted hybrid (de+en mass 補強)

**Hypothesis**: pre-training audit の唯一の soft warning である de+en weighted
mass = 0.489 (target 0.60) を補強すれば、Kantian discriminative signal が
proper magnitude に届く可能性。retrain v2 design-final.md §3.3 で fallback
として規定された Candidate C を起動する。

**Step 0 feasibility scan 結果** (`scripts/m9-c-adopt/` の Glob + dataset.py の
Grep):
- de-focused monolog generator は **未実装**。`src/erre_sandbox/training/
  dataset.py` の monolog re-cast は natural shards の 2-turn Kant pair を
  language 無 differentiation で抽出している。
- 2 sub-option:
  - **B-1 (cheap)**: 既存 `dataset.py` の monolog re-cast に `where language=="de"`
    filter を追加 + DI-3 cap=500 解除。新規 data 採取ゼロ、コード変更 ~50 行。
    ただし既存 5022 examples 中 de=15.9% (≈800)、その中の連続 2-turn Kant pair
    は ~5-7% (≈40-60 examples) と推測され、**250+ 採取 target には不足**。
  - **B-2 (expensive)**: 新規 driver script (`scripts/m9-c-adopt/
    de_focused_monolog_collector.py`) を書き、G-GEAR で de-biased prompt を
    投げて新規 dialog を採取。~3h G-GEAR + ~1.5h driver 実装。
- B-1 単独では 250 examples 集まらない可能性大 → **B-1 + B-2 ハイブリッドが
  現実的**。

| 項目 | 値 |
|---|---|
| 必要新規データ | de monolog 250+ (B-1 で ~50、B-2 で残り採取) |
| 必要新規 training | full retrain (max_steps=4000 維持、weighted、rank=8) |
| compute 見積 | driver 実装 1.5h + 新規採取 ~3h + training ~16h + pilot recapture 1h + DA-14 verdict 30min ≈ **~22h** (envelope 24h で abort) |
| codebase 変更面積 | 中 (dataset.py + 新 collector script + cap config 開放) |
| C1-C4 gap address | C1 (de mass) を直接 address、C3 (monolog) 部分 address |
| predicted Cohen's d 改善幅 | -0.3 to -0.6 (de mass を 11pp 上げる効果は線形外挿で 0.4 程度) |
| risk: 採取自然性 | driver-generated de prompt が natural Kant 対話と分布乖離 |
| risk: eval contamination | new dialog が eval split と group key 衝突しないか group-aware split を厳格に維持 |
| reversibility | 中 (新 adapter 生成、旧 adapter 廃棄せず保持) |

### Plan C: Longer training / rank 拡大

**Hypothesis**: model capacity (rank) or 学習量 (max_steps) を増やすと
magnitude が伸びる可能性。retrain v2 の eval_loss step 2000 = 0.166 → final =
0.180 で軽微 over-fit 兆候があり、rank=8 では capacity 飽和の可能性。rank=16
で 2× params、または max_steps=8000 で 2× iterations。

| 項目 | 値 |
|---|---|
| 必要新規データ | ゼロ |
| 必要新規 training | full retrain (rank=16 or max_steps=8000) |
| compute 見積 | DI-7 で rank=8 / max_steps=4000 が 16h19m 実測。**rank=16 は forward+backward の memory + flops で linear ~2×、step time 14.23s/it からの線形外挿で 32-40h**。max_steps=8000 は同様に 32h。**12 GB VRAM safety margin 超過 risk あり** (rank=8 で peak_vram=10.62 GB)。step time 上昇 (5.35s → 14.23s/it) が rank=16 で再現すれば実 envelope は **48-64h** に膨らむ可能性。 |
| codebase 変更面積 | 小 (rank or max_steps の hyperparameter 変更のみ) |
| C1-C4 gap address | ❌ training-side gap には touch せず、capacity 任せ |
| predicted Cohen's d 改善幅 | -0.1 to -0.4 (over-fit signal が既にあり、capacity 増は marginal gain。literature でも rank 8→16 は ~30-50% capacity gain で linear improvement は限定的) |
| risk: over-fit 加速 | eval_loss step 2000→final で軽微 over-fit、capacity 増は加速 risk |
| risk: VRAM 超過 | rank=16 で 16 GB GPU OOM の可能性、batch=1 まで絞っても peak 12-14 GB 想定 |
| reversibility | 低 (32-48h GPU 拘束、ROI が出ない場合 sunk cost 大) |

## 2. Decision matrix

| 軸 | Plan A | Plan B | Plan C |
|---|---|---|---|
| empirical evidence-grounded | △ (kernel 仮説) | ✅ (audit soft warning が直接) | △ (over-fit signal あり、capacity 増は逆効果可) |
| compute cost | **15-30min** (圧倒) | ~22h | 32-64h |
| reversibility | **完全** | 中 | 低 |
| predicted effect size 上限 | -0.7 (best case) | -0.6 | -0.4 |
| HIGH-3 risk | △ grey-zone (methodology shift) | ✅ clean | ✅ clean |
| C1-C4 gap address | ❌ measurement-side | ✅ training-side (C1) | ❌ |

## 3. V1 採用案 (provisional)

**Sequential escalation: Plan A → Plan B → Plan C**

理由:
1. **Cheapest first**: Plan A は 30min、Plan B は 22h、Plan C は 48-64h。
   A で pass すれば B/C 実行不要。
2. **Reversibility cascade**: A 完全可逆 → B 中可逆 → C 低可逆。失敗 ROI が
   早期低コスト fix で済む。
3. **Evidence-grounded ordering**: A は "kernel が原因かも" の low-confidence
   仮説、B は audit soft warning という具体的 empirical evidence、C は over-fit
   signal を踏まえると逆効果可能性すらある。**evidence 強度では B > A > C** だが、
   compute cost が evidence 強度を凌駕する。

採用 Plan の re-evaluation criteria (Plan A 後):
- **Plan A pass criteria**: DA-14 4 軸を multilingual-e5 kernel で再計算し、Vendi
  d ≤ -0.5 + Burrows reduction ≥ 5% + ICC ≥ 0.55 を 2-of-3 で満たす
- **Plan A 後の escalate trigger**:
  - Vendi d ≤ -0.5 pass + Burrows reduction < 2% → Plan B (Burrows は training-
    side data shift が必要)
  - Vendi d ≤ -0.5 pass + Burrows 2-5% partial → Plan B-1 のみ (cheap filter
    extension)
  - Vendi d > -0.5 still fail → kernel 仮説 reject、Plan B fall through

## 4. HIGH-3 self-review (本 draft 用、最終は blockers.md に固定)

- [x] DA-14 thresholds (Vendi d ≤ -0.5、Burrows reduction ≥ 5%、ICC ≥ 0.55) は
      本 draft 内で**一度も変更されていない**
- [x] 各 Plan の "predicted effect size" は threshold との比較として書かれて
      おり、threshold 自体を再定義していない
- [x] "post-hoc" / "緩める" / "見直す" を threshold に適用する文言は無い
- [ ] **Open question (Codex に投げる)**: Plan A の kernel swap が "metric
      methodology の post-hoc shift = HIGH-3 同等" と解釈されるか? V1 では
      "kernel change は methodology 改善 ≠ threshold movement" と立場を取る。

## 5. Open questions (Codex review に投げる)

1. Plan A の kernel swap は HIGH-3 grey-zone か (rationale の妥当性)
2. multilingual-e5 / bge-m3 等 candidate kernel に persona-discriminative power
   の prior art evidence はあるか
3. Plan C で rank=16 にすると 16 GB GPU で OOM risk はどの程度か (literature
   anchor: Qwen3-8B + LoRA r=16 + NF4 の peak VRAM)
4. Plan A → B → C sequential escalation の経済合理性は妥当か、それとも B 並列
   準備が ROI 高いか
5. de+en mass 0.489 → 0.60 (+11.3pp) が Cohen's d を 0.18 → 0.5 にする線形性は
   どの程度信頼できるか
