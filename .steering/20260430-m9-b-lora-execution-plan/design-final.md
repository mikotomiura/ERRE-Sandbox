# Design Final — M9-B LoRA Execution Plan (v3 hybrid: 評価基盤先行 + 並行 Kant spike)

> このドキュメントは Plan→Clear→Execute ハンドオフ規則に従い、`/clear` 後でも独立に
> Read 可能な体裁で書かれている。10 軸の ADR は `decisions.md` (DB1-DB10) に対応する。
>
> v1 (Claude 単独 LoRA-first 案) は `design-v1.md` で破棄。
> v2 (/reimagine 評価基盤先行案) は `design-v2.md` に保存。
> v1/v2 比較は `design-comparison.md`、外部 reviewer (Codex `gpt-5.5` `xhigh`) は
> `codex-review.md` に verbatim 保存。本書は **codex review HIGH 4 件すべてを反映**
> + **codex の指摘した第 3 の道 (bounded Kant spike on SGLang in parallel with eval-system)**
> を取り込んだ最終 hybrid。

## 設計思想 (v3 final)

LoRA 適用の go-no-go gate は評価系完成後に判定する **(v2-B 路線維持)** が、
**LoRA 学習・adapter swap・runtime に関する技術リスクは、
single-persona (Kant) bounded spike を SGLang 上で並行実施して早期に潰す**
(codex review final note 提案)。

key 転換:
1. **SGLang-first**: SGLang は v0.3+ で multi-LoRA / dynamic load/unload / pinned adapters /
   overlap loading / `--enable-lora` を documented サポート (codex HIGH-3、SGLang docs)。
   vLLM full migration は破棄、measured spike failure 時のみ fallback
2. **trigger relaxation**: 4 条件 AND は D1 ADR と矛盾 (codex HIGH-1)。
   `floor AND (coverage OR plateau OR timebox)` に緩和。divergence stability は diagnostic、
   hard gate ではない
3. **offensive gate 統計的厳密化**: 「5%」固定を破棄、composite + bootstrap CI + 2-of-3 quorum
   (codex HIGH-2)
4. **train/eval 物理分離**: Parquet boolean flag は不十分 (codex HIGH-4)。raw training
   table は metric-free、metric は sidecar table に分離
5. **bounded parallel Kant spike**: 評価系構築と並行で、Kant 1 persona に対し SGLang LoRA
   adapter swap + 学習 loop を non-authoritative spike として走らせる。**adoption 判断は
   評価系完成後の post-spike re-evaluation でのみ行う**

## 10 軸の確定 (DB1-DB10 ADR cross-ref)

### A. 量子化戦略 (DB1) → QLoRA NF4 default + AWQ/GPTQ alternatives recorded

- **default**: QLoRA NF4 (bnb double-quantization)、base ~4-5GB、3 persona base 共有 + adapter ~50MB/persona
- **alternatives 記録 (MEDIUM-2 反映)**:
  - AWQ + LoRA: serving-side quality 維持
  - GPTQ + LoRA: 量子化品質トレードオフ
  - 8-bit LoRA: NF4 で 4-bit が品質面で破綻した時の fallback
- **判断**: 「唯一現実解」ではなく「conservative default」と framing。Kant spike で
  実測 quality 検証

### B. Library 選定 (DB2) → defer to M9-C kickoff

- PEFT vs unsloth は M9-eval-system 完了後の M9-C 着手時に spike (rank=8 統一)
- **codex 開示の追加**: SGLang の LoRA training compatibility は別途確認必要
  (training は別 framework、SGLang は serving)。学習は HF Transformers + PEFT/unsloth、
  serving は SGLang LoRA adapter 形式に変換

### C. Serving 移行判断 (DB3) → **SGLang-first, vLLM fallback only** (HIGH-3 反映)

- 現行 SGLang 維持
- LoRA は SGLang `--enable-lora` + `/load_lora_adapter` で実装
- multi-LoRA + overlap loading は documented サポート (SGLang docs cited by codex)
- vLLM への migration は **measured spike failure** が条件:
  - adapter swap latency > 500ms (G-GEAR で 3 persona 切替不能)
  - batching collapse (N=3 同時 request で throughput drop)
  - integration regression (M5 resonance / ERRE FSM が破綻)
- いずれも spike で実測してから判断

**v1/v2 → v3 の最大の cost saving**: M5 以降の resonance 機構の再配線が不要

### D. Dataset trigger 閾値 (DB4) → `floor AND (coverage OR plateau OR timebox)` (HIGH-1 反映)

**新トリガー条件**:
- **MUST (floor)**: self_rep ≤ 0.10 AND cross_echo ≤ 0.10 (継続要件)
- **ANY ONE OF**:
  - **coverage**: dialog_turn ≥ 300/persona (D1 ADR の v1 を緩和、500→300、ζ scale 実態反映)
  - **plateau**: prompting + persona YAML 拡張のみで Tier B metric が 2 連続 run で <5% improvement (operational definition は HIGH-2 quorum logic に統合)
  - **timebox**: 8 セッション (~2 calendar weeks at solo cadence) 経過

**divergence stability** (ζ 36:74:16 ±10%) は **diagnostic** (warning trigger) のみ。
hard gate にしない (codex 指摘)

**v1/v2 4-AND からの relaxation**: floor は必須維持、それ以外はいずれかで OK。
**timebox の追加**: solo project の momentum loss 防止 (codex Q2 反映)

### E. Parquet export schema (DB5) → **raw + sidecar 分離** (HIGH-4 反映)

#### Raw training table (`raw_dialog/`)
**metric-free**。training loader が直接 import する table。
```
schema:
  - run_id: str
  - persona_id: str (partition key)
  - turn_idx: int
  - timestamp: float
  - mode: str (ERREMode)
  - zone: str
  - dialog_turn_text: str
  - reasoning_trace_text: str (nullable)
  - episodic_log_event: str (nullable)
  - embedding: list[float] (768d, nomic)
```
partition: `evaluation_epoch=*/persona_id=*/run_id=*/`
**training は `evaluation_epoch=false` partition のみ読む** (contract で強制)

#### Sidecar metrics table (`metrics/`)
評価 metric は別 table。`run_id + persona_id + turn_idx` で raw に join。
```
schema:
  - run_id: str
  - persona_id: str (partition key)
  - turn_idx: int
  - tier: str  # "A" | "B" | "C"
  - metric_name: str
  - metric_value: float
  - metric_metadata: dict
```

**train/eval contamination 解消**: training pipeline が metric column に物理的にアクセスできない。
training-view contract: `raw_dialog/evaluation_epoch=false/` のみ読む

### F. 評価 epoch 分離 (DB6) → Run-level flag + 物理 partition + sidecar (HIGH-4 反映 統合)

- `evaluation_epoch: bool` を Run config 必須化、Default `False`
- Parquet partition で物理分離 (`evaluation_epoch=*/`)
- sidecar metrics table も同 partition 構造
- evaluation 頻度 policy (MEDIUM-4 反映):
  - **Tier A**: per turn (cheap、~50ms)
  - **Tier B**: per 100 turns (Vendi / IPIP-NEO / Big5 ICC)
  - **Tier C**: nightly offline batch (Prometheus 2 / G-Eval / FANToM-adapted)
  - 同時 GPU contention 回避: Tier C は autonomous run 停止時のみ

### G. Persona N=4 拡張時期 (DB7) → defer to M10 + synthetic heldout 4th persona (LOW-1 反映)

- Runtime N=4 は M10 まで完全 defer
- ただし **eval pipeline test には mocked 4th persona scenario を含める** (LOW-1)
- 評価系が 3 persona 専用に overfit するのを防ぐ
- agora 主体 YAML 雛形は M10 着手時に起草

### H. Adapter swap runbook (DB8) → SGLang `/load_lora_adapter` first

- SGLang `/load_lora_adapter` REST endpoint で adapter dynamic load
- multi-LoRA: `--max-loras N` + `--max-lora-rank R` 起動オプション
- pinned adapters: hot path persona は pin
- runbook 起草は **bounded Kant spike 完了後**、実測値 (latency / cold start / throughput) 込み

### I. Baseline drift gate (DB9) → **composite + bootstrap CI + 2-of-3 quorum** (HIGH-2 反映)

#### Primary composite per persona
各 persona の Tier B から 3 sub-metric を選定して composite:
- `vendi_score` (semantic kernel)
- `big5_stability_icc` (across-mode personality stability)
- `burrows_delta_to_reference` (persona-fit)

#### Statistical operationalization
- **Bootstrap CI** over turns/runs: each metric の 95% CI を持つ
- **Quorum rule**: 2-of-3 sub-metric が CI で baseline からネガティブ方向に regress
  → rollback fire
- **Single regression**: warning ログのみ、rollback しない

#### Defensive canary (守りの drift)
- self_rep > 0.15 OR cross_echo > 0.15 (any 1 trigger) → auto rollback (これは即座、CI 待たない)

#### Adoption gate (攻めの gate)
- **Initial run** (first LoRA application): floor 維持で許容 (warmup 認める)
- **Subsequent runs (≥2)**: 2-of-3 sub-metric が CI で baseline 上回り (positive direction)
  → adoption 確定。期待 effect size は **persona-conditional に bootstrap で決める**
  (5% 固定棄却、codex HIGH-2)
- **3 連続 run** で adoption 条件未達 → 当該 LoRA 設定 (rank / dataset) を破棄、再 spike

### J. 思想家らしさ評価系 framework (DB10) → 4-tier + persona-conditional + multi-channel

#### M9-B 内 deliverable: **specs only** (MEDIUM-1 反映)
M9-B では実装コードを出さず、以下の **spec ドキュメント**のみ deliverable:
- Tier A-D metric の interface 定義
- Parquet schema (raw + sidecar) 定義
- golden set 採取の technical spec
- Burrows' Delta reference corpus 整備計画
- LIWC license 評価 + OSS alternative (Empath / spaCy / 自作 dictionary) decision tree

#### Tier 階層 (research-evaluation-metrics.md ベース)

**Tier A (per-turn, cheap, ~50ms total)**:
- LIWC-22 OR Empath OR custom dictionary (license 確定後選定)
- Burrows' Delta to thinker reference (per-language、translation 別 baseline)
- MATTR
- semantic novelty (MPNet embedding distance)
- repetition_rate, cross_persona_echo_rate (既存)
- persona_contradiction_rate (NLI head, 新規)

**Tier B (per-100-turn, medium)**:
- Vendi Score (semantic kernel、200-turn rolling window)
- IPIP-NEO-120 via local 7B-Q4 (questionnaire administration)
- Big5 stability ICC across mode

**Tier C (per-session offline, expensive)**:
- Prometheus 2 rubric assessment (CharacterBench 6-aspect taxonomy で instantiate)
- G-Eval logit-weighted scoring (Wachsmuth Toulmin 5 dimension)
- FANToM-adapted ToM probe (chashitsu info-asymmetric minimal pair)
- ROSCOE on reasoning trace (informativeness + self-consistency)

**Tier D (sparse manual)**:
- FActScore-adapted against Kant/Nietzsche/Rikyu canonical corpus
- 専門家 qualitative review
- RoleEval-adapted biographical MCQ pre-gate

#### Persona-conditional gate
- Idea density: Kant HIGH 期待 / Rikyu LOW 期待 (低が persona-fit)
- Allusion rate: persona 別 target rate
- Vendi Score 解釈: persona の「思考の幅」依存

→ **gate 設計は absolute value ではなく persona-baseline からの bootstrap CI 偏差**

#### Golden set ステージング (MEDIUM-3 反映)
- M9-eval-system: **100/persona** seed (smoke test 用)
- LoRA 採用判定: **300/persona** acceptance threshold
- 学術発表時: **1000/persona** publication-grade

#### Multi-channel honest framing
- 「single thinker-likeness score」は採用しない (research-evaluation-metrics.md L326-349)
- formal benchmark = floor、proxy = exploratory、expert review = final
- LIWC OSS alternative (Empath / spaCy) は proxy であり LIWC 等価ではない (LOW-2 反映)
- Big-Five claim は LIWC 商用 license + validation あって初めて成立、proxy ベースの
  Big-Five claim は honest に避ける

## 数値 gate サマリ (final)

| Gate | 条件 | 動作 |
|---|---|---|
| **Trigger** | floor (self_rep≤0.10 AND echo≤0.10) AND (coverage 300/persona OR plateau 2-run<5% OR timebox 8 session) | LoRA 適用 fire |
| **Defensive canary** | self_rep>0.15 OR echo>0.15 (any 1) | 即時 auto rollback |
| **Adoption (initial run)** | floor 維持 | 採用 (warmup 認可) |
| **Adoption (run ≥2)** | 2-of-3 Tier B sub-metric (Vendi / Big5 ICC / Burrows Delta) が CI で baseline positive 方向 | 採用確定 |
| **Drift (post-LoRA)** | 2-of-3 Tier B sub-metric が CI で baseline negative 方向 | rollback |
| **3 連続 adoption 失敗** | 上記 adoption 条件 3 run 連続未達 | LoRA 設定破棄、再 spike |
| **VRAM** | base 5GB + 3 adapter ≤ 7GB total (N=3 維持) | M10 で N=4 再評価 |
| **eval ready** | golden baseline 採取 (3 persona × 5 run × 500 turn) + Tier B (Vendi+ICC) 実装完了 | LoRA adoption 判断 enabled |

## 実装順序 (final, 4 タスク並行構造)

### M9-B (本タスク, planning + spec only)
- [x] requirement.md + research + design v1/v2/comparison + codex review
- [ ] design-final.md (本書) commit + decisions.md + blockers.md + tasklist.md commit
- [ ] M9-eval-system + M9-C-spike + M9-C スコープ確定
- src/ 変更ゼロ

### M9-eval-system (新タスク, M9-B 後)
- Parquet pipeline 実装 (raw + sidecar 分離)
- Tier A 実装
- Tier B 実装 (Vendi / IPIP-NEO / Big5 stability ICC)
- golden baseline 採取 (3 persona × 5 run × 500 turn)
- golden set 整備 (100/persona seed → 300 acceptance ロードマップ)
- Tier C 一部 (Prometheus 2 + G-Eval) 実装
- evaluation pipeline 自動化 + dashboard

### M9-C-spike (新タスク, **M9-eval-system と並行**) ← codex 第 3 の道
**bounded, non-authoritative single-persona Kant spike**:
- SGLang `--enable-lora` + `/load_lora_adapter` 動作確認
- HF Transformers + PEFT (or unsloth) で Kant LoRA 学習 (rank=8, dataset 既存 dialog_turn)
- adapter swap latency / cold start / throughput 実測
- M9 → vLLM migration 必要性の measured 判断材料
- **adoption 判断は M9-eval-system 完成後 post-spike re-eval まで保留**
- 学習データは training-view (`evaluation_epoch=false`) のみ使用、汚染防止

### M9-C-adopt (旧 M9-C, M9-eval-system + M9-C-spike + 評価系 ready 達成後)
- adoption gate (DB9) で LoRA 採用判断
- 3 persona に展開
- 双方向 drift gate 実装
- adapter swap runbook 文書化
- M10 への handoff (N=4 拡張判断)

## codex review 反映マッピング

| Finding | 反映先 | Status |
|---|---|---|
| HIGH-1 (4-AND trigger) | DB4 → `floor AND (coverage OR plateau OR timebox)` | ✅ 反映 |
| HIGH-2 (offensive gate stat) | DB9 → composite + bootstrap CI + 2-of-3 quorum | ✅ 反映 |
| HIGH-3 (vLLM stale) | DB3 → SGLang-first | ✅ 反映 (大規模変更) |
| HIGH-4 (train/eval contamination) | DB5/DB6 → raw + sidecar 分離 | ✅ 反映 |
| MEDIUM-1 (M9-B scope) | DB10 → specs only 明文化 | ✅ 反映 |
| MEDIUM-2 (QLoRA "唯一現実解") | DB1 → conservative default + alternatives recorded | ✅ 反映 |
| MEDIUM-3 (golden set 100→300→1000) | DB10 → staging adopted | ✅ 反映 |
| MEDIUM-4 (eval frequency VRAM) | DB6 → Tier A/B/C frequency policy | ✅ 反映 |
| LOW-1 (synthetic 4th persona) | DB7 → eval test scenario として採用 | ✅ 反映 |
| LOW-2 (LIWC alternatives honest) | DB10 → proxy/equivalence honest framing | ✅ 反映 |
| **Final note (third option)** | M9-C-spike として並行構造化 | ✅ **反映 = 設計の中核転換** |

## 残存リスク (LOW defer to blockers.md)

`blockers.md` 参照。主な defer:
- LIWC 商用 license の最終可否判定 (M9-eval-system 中)
- Burrows' Delta multi-language strategy 詳細 (M9-eval-system 中)
- Prometheus 2 / G-Eval bias mitigation runbook (M9-eval-system 中)
- 専門家 qualitative review の人 selection (M9-C-adopt 直前)
