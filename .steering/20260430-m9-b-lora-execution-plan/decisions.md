# Decisions — M9-B LoRA Execution Plan (10 ADR: DB1-DB10)

## ADR 体裁

各 ADR は 5 要素 (決定 / 根拠 / 棄却 / 影響 / re-open 条件) で記録。
本 ADR set は m9-lora-pre-plan の D1-D5 (PR #110 merged) を **継承し、M9 実行 phase の
詳細を確定** する位置づけ。Codex independent review (`codex-review.md`) で得た 10 finding
(HIGH 4 / MEDIUM 4 / LOW 2) を全件反映済。

---

## DB1 — 量子化戦略: QLoRA NF4 default + alternatives recorded

- **決定**: 学習時 quantization は **QLoRA NF4 (bnb double-quantization)** を default 採用。
  alternatives (AWQ + LoRA / GPTQ + LoRA / 8-bit LoRA) を記録、bounded Kant spike で
  実測 quality を検証してから default を維持・変更する。
- **根拠**:
  - G-GEAR 16GB + qwen3:8b (FP16 ~16GB) + 3 persona swap で base ~4-5GB 圧縮が必要
  - QLoRA NF4 + double-quantization で 1-2% 性能低下、許容範囲
  - codex MEDIUM-2 指摘: 「唯一現実解」は overstated、conservative default と framing
- **棄却**:
  - LoRA FP16: VRAM 不足
  - INT8 + LoRA: NF4 の上位互換なし
- **影響**:
  - 学習 pipeline は HF Transformers + PEFT/unsloth (M9-C-spike で確定)
  - serving は SGLang LoRA adapter format に変換 (DB3)
- **re-open 条件**:
  - Kant spike で NF4 quality が許容範囲外 → 8-bit LoRA fallback
  - SGLang AWQ + LoRA 互換が confirmed → AWQ への serving migration 検討

---

## DB2 — Library 選定: defer to M9-C kickoff

- **決定**: PEFT vs unsloth の選定は **M9-eval-system + M9-C-spike 完了後の M9-C-adopt 着手時**
  に rank=8 統一 spike で決める。M9-B / M9-eval-system では library を確定しない。
- **根拠**:
  - 学習 library 選定は LoRA を実際に走らせる時点で十分
  - 先行決定する benefit なし (premature optimization)
  - codex review Q3 反映: 必要な時点での実測判断
- **棄却**:
  - v1: unsloth 即採用 → 性能 benefit 未実測のまま commit するリスク
- **影響**:
  - M9-C-spike では一時的に PEFT (公式・ecosystem 厚い) を使用、final 選定は別
- **re-open 条件**:
  - unsloth の SGLang LoRA adapter format compatibility が問題
  - PEFT の学習速度が solo cadence に対し過大

---

## DB3 — Serving 移行判断: **SGLang-first, vLLM fallback only** (HIGH-3 反映)

- **決定**: **現行 SGLang を維持し、LoRA は SGLang `--enable-lora` + `/load_lora_adapter`
  で実装する**。vLLM full migration は **measured spike failure 時のみ** fallback。
- **根拠**:
  - codex HIGH-3: SGLang は v0.3+ で multi-LoRA / dynamic load/unload / pinned adapters /
    overlap loading / `--enable-lora` を documented サポート
    ([SGLang docs](https://docs.sglang.io/advanced_features/lora.html))
  - 私の v1/v2 認識 (SGLang LoRA 安定性未検証) は stale だった
  - vLLM full migration は M5 以降の resonance 機構 / ERRE FSM 再配線が必要、コスト過大
- **棄却**:
  - v1 / v2: vLLM full migration → cost 過大、SGLang stale 認識に基づく
- **影響**:
  - M5 resonance / ERRE FSM 配線そのまま維持 (大きな cost saving)
  - LoRA adapter format は SGLang 互換に変換が必要
- **re-open 条件 (vLLM fallback fire)**:
  - Kant spike で adapter swap latency > 500ms
  - N=3 同時 request で throughput collapse
  - resonance / FSM が SGLang LoRA 経路で regression

---

## DB4 — Dataset trigger 閾値: `floor AND (coverage OR plateau OR timebox)` (HIGH-1 反映)

- **決定**: LoRA 適用 trigger を **`floor MUST AND (coverage 300/persona OR plateau OR timebox)`**
  に確定。divergence stability は **diagnostic** のみ、hard gate にしない。
  - **MUST (floor)**: self_rep ≤ 0.10 AND cross_echo ≤ 0.10 (継続要件)
  - **ANY ONE OF**:
    - coverage: dialog_turn ≥ **300/persona** (旧 500 から緩和)
    - plateau: prompting + persona YAML 拡張のみで Tier B metric が **2 連続 run で
      <5% improvement** (operational definition は DB9 quorum logic に統合)
    - timebox: **8 セッション** (~2 calendar weeks at solo cadence) 経過
  - **diagnostic (warning only)**: divergence_ratio が ζ 36:74:16 ±10% を逸脱
- **根拠**:
  - codex HIGH-1: 4-AND は m9-lora-pre-plan D1 ADR (floor + (coverage OR plateau)) と矛盾
  - D1 既存 ADR で 500/persona は ζ scale で実質 unreachable と warning 済
    (`.steering/20260428-m9-lora-pre-plan/decisions.md:44-50`)
  - timebox 追加は solo project の momentum loss 防止 (codex Q2 反映)
- **棄却**:
  - v1/v2 4-AND: D1 ADR と矛盾、unreachable リスク
  - 500/persona: ζ scale で達成困難
- **影響**:
  - LoRA 適用が現実的タイミングで fire 可能
  - timebox により M9 milestone delay が bounded
- **re-open 条件**:
  - 300/persona も実態で困難 → 再 relax (200/persona) 検討
  - timebox 8 session が早すぎ・遅すぎ判明 → 調整

---

## DB5 — Parquet schema: **raw + sidecar 物理分離** (HIGH-4 反映)

- **決定**: training data と evaluation metric を **物理的に別 table** に保存。
  - **raw_dialog/**: metric-free training table。`evaluation_epoch=*/persona_id=*/run_id=*/`
    partition、training は `evaluation_epoch=false/` のみ読む contract で強制。
  - **metrics/**: sidecar evaluation metric table。`run_id + persona_id + turn_idx` で
    raw に join。tier (A/B/C) + metric_name + metric_value + metadata schema。
- **根拠**:
  - codex HIGH-4: boolean flag (evaluation_epoch) だけでは training pipeline が物理的に
    metric column にアクセス可能、汚染リスク (judge artifact 学習)
  - 物理分離 + training-view contract で contamination を構造的に不可能にする
- **棄却**:
  - v1/v2: 単一 Parquet schema に metric column 統合 → contamination リスク
- **影響**:
  - Parquet pipeline 実装 (M9-eval-system) の複雑度が中程度増加
  - training loader は明示的に `raw_dialog/evaluation_epoch=false/` のみ読む実装
  - dashboard / analysis は raw + metrics を join して使用
- **re-open 条件**:
  - sidecar join overhead が training latency に影響大
  - schema migration が必要な structural change

---

## DB6 — Evaluation epoch 分離: Run-level flag + 物理 partition + sidecar (HIGH-4 統合) + 頻度 policy (MEDIUM-4)

- **決定**:
  - `evaluation_epoch: bool` を Run config 必須化、Default `False`
  - Parquet partition で物理分離 (`raw_dialog/evaluation_epoch=*/`)
  - sidecar metrics table も同 partition 構造
  - **頻度 policy**:
    - **Tier A**: per turn (cheap, ~50ms total)
    - **Tier B**: per 100 turns (Vendi / IPIP-NEO / Big5 ICC)
    - **Tier C**: nightly offline batch (Prometheus 2 / G-Eval / FANToM-adapted) — autonomous run 停止時のみ実行
- **根拠**:
  - codex HIGH-4 + MEDIUM-4: Tier C judge LLM (Prometheus 2 8x7B class) は qwen3:8b agent
    と VRAM contention、同時実行不可
  - 物理 partition は HIGH-4 解消の core mechanism
- **棄却**:
  - v1/v2 の boolean flag 単独: contamination リスク
  - Tier C を per-100-turn に走らせる案: VRAM contention で agent 停止
- **影響**:
  - autonomous loop に nightly batch slot 追加が必要
  - dashboard は per-tier の latency profile を表示
- **re-open 条件**:
  - Tier C judge LLM が smaller model に置換可能で contention 解消

---

## DB7 — Persona N=4 拡張時期: defer to M10 + synthetic heldout 4th in eval tests (LOW-1 反映)

- **決定**:
  - Runtime N=4 (agora 主体 4 人目 actual deploy) は **M10 まで完全 defer**
  - ただし **eval pipeline test には mocked 4th persona scenario を含める**
- **根拠**:
  - M9-B / M9-eval-system 期間は N=3 の divergence 漸近線 + 評価系構築が優先
  - codex LOW-1: eval pipeline が N=3 専用に overfit するのを防ぐため、synthetic 4th
    persona を test fixture として使う
  - 4 人目の persona YAML 起草 / reference corpus 整備 / golden set は M10 着手時に開始
- **棄却**:
  - v1: M9-B 中 YAML 起草 → 評価系設計を複雑化
  - 完全 defer (synthetic も含めない): eval pipeline overfit リスク
- **影響**:
  - eval pipeline test に synthetic persona fixture 追加
  - M10 で agora 主体 candidate を再評価
- **re-open 条件**:
  - N=3 の divergence が早期に saturate、4 人目で extension が必要
  - M10 timeline で 4 人目 candidate が確定

---

## DB8 — Adapter swap runbook: SGLang `/load_lora_adapter` first

- **決定**:
  - **SGLang `/load_lora_adapter` REST endpoint** で adapter dynamic load
  - `--max-loras N` + `--max-lora-rank R` 起動オプション
  - hot path persona は `pinned adapters` で pin
  - **runbook 起草は M9-C-spike 完了後**、実測値 (latency / cold start / throughput) 込み
- **根拠**:
  - DB3 (SGLang-first) と整合
  - SGLang docs cited by codex
  - 実測値なしの runbook は無価値、spike 完了後に書く
- **棄却**:
  - v1/v2 vLLM LoRARequest API ラッパ路線 → DB3 で破棄
- **影響**:
  - M9-C-spike が runbook の前提
- **re-open 条件**:
  - SGLang LoRA で adapter swap が機能不全 → vLLM fallback (DB3 re-open)

---

## DB9 — Drift gate: composite + bootstrap CI + 2-of-3 quorum (HIGH-2 反映)

- **決定**: drift gate を **統計的に厳密** に運用:
  - **Primary composite per persona**: 各 persona の Tier B から 3 sub-metric:
    - `vendi_score` (semantic kernel)
    - `big5_stability_icc` (across-mode personality stability)
    - `burrows_delta_to_reference` (persona-fit)
  - **Bootstrap CI** over turns/runs: 各 sub-metric の 95% CI を計算
  - **Quorum rule**:
    - rollback (drift): 2-of-3 sub-metric が CI で baseline negative 方向
    - adoption: 2-of-3 sub-metric が CI で baseline positive 方向
  - **Single regression**: warning ログのみ、rollback しない
  - **Defensive canary** (即時): self_rep > 0.15 OR cross_echo > 0.15 (any 1) → CI 待たず auto rollback
  - **Initial run** (first LoRA application): floor 維持で許容 (warmup 認可)
  - **Subsequent runs (≥2)**: 2-of-3 quorum で adoption / rollback 判定
  - **3 連続 adoption 失敗**: LoRA 設定 (rank / dataset) を破棄、再 spike
- **根拠**:
  - codex HIGH-2: 「5%」固定 + Tier B noise → false rollback / metric gaming リスク
  - bootstrap CI + quorum で statistical robustness
  - Effect size は persona-conditional に bootstrap で決める (固定 5% を破棄)
- **棄却**:
  - v1 「floor 維持のみ」: 効果測定不能
  - v2 「絶対 5% 改善」: noise floor が persona 依存、根拠不十分
- **影響**:
  - bootstrap CI 実装 (M9-eval-system)
  - quorum logic 実装 (M9-C-adopt)
- **re-open 条件**:
  - 3 sub-metric の選定が実態で不適切 (例: vendi_score が persona に discriminative でない)
  - CI 計算 cost が prohibitive

---

## DB10 — J 評価系 framework: 4-tier + persona-conditional + multi-channel (specs only in M9-B)

- **決定**:
  - **M9-B 内 deliverable は specs のみ** (実装コードは出さない、MEDIUM-1 反映)
  - **4-tier 階層** (research-evaluation-metrics.md ベース):
    - Tier A: per-turn cheap (LIWC/Empath / Burrows Delta / MATTR / semantic novelty / NLI)
    - Tier B: per-100-turn (Vendi Score / IPIP-NEO / Big5 stability ICC)
    - Tier C: per-session offline (Prometheus 2 / G-Eval / FANToM-adapted / ROSCOE)
    - Tier D: sparse manual (FActScore-adapted / 専門家 review / RoleEval-adapted MCQ)
  - **persona-conditional gate**: absolute value ではなく persona-baseline からの bootstrap
    CI 偏差 (Rikyu LOW idea density は適正、Kant HIGH も適正)
  - **golden set staging** (MEDIUM-3 反映):
    - M9-eval-system: **100/persona seed**
    - LoRA 採用判定: **300/persona acceptance**
    - 学術発表時: **1000/persona publication-grade**
  - **multi-channel honest framing**: single thinker-likeness score 採用しない、
    formal benchmark = floor / proxy = exploratory / expert review = final
  - **LIWC alternatives honest framing** (LOW-2 反映): Empath/spaCy は proxy であり LIWC 等価ではない、
    Big-Five claim は LIWC 商用 license + validation あって初めて成立、proxy ベースの
    Big-Five claim は honest に避ける
- **根拠**:
  - research-evaluation-metrics.md L326-349 honest gap assessment
  - codex MEDIUM-1 / 3 / LOW-2 反映
- **棄却**:
  - v1: framework 宣言のみ、内容空白
  - v2 単独: M9-B 内で Tier A 実装まで含む scope creep
  - 「single thinker-likeness score」: research-evaluation-metrics.md と Codex 双方が棄却
- **影響**:
  - M9-eval-system が独立タスクとして大規模化
  - golden set 採取に専門知識 (philosopher domain expert) が必要
- **re-open 条件**:
  - golden set 整備が solo cadence に対し時間的に困難
  - LIWC license が approve、商用使用可

---

## ADR 横断: third option (codex final note 反映)

**bounded, non-authoritative single-persona Kant LoRA spike を SGLang 上で M9-eval-system
と並行実施する**。adoption 判断は評価系完成後の post-spike re-eval まで保留。

- **目的**: 評価系構築中に LoRA 学習・adapter swap・runtime 技術リスクを早期検出
- **non-authoritative**: spike の結果のみで adoption しない (評価系 gate 通過必須)
- **scope**: Kant 1 persona のみ、既存 dialog_turn を training data として use、
  `evaluation_epoch=false` partition のみ
- **deliverable**: SGLang LoRA endpoint 動作確認 + adapter swap latency 実測 +
  vLLM migration 必要性 measured 判断材料
- **タスク**: 別タスク `M9-C-spike` として切り出し (新規 scaffold)

---

## DB11 — Cognition deepening contamination prevention (PR #144 Codex HIGH-3 反映、addendum 2026-05-08)

PR #144 (`docs/cognition-deepen-decision-2026-05-08`、main=`e641f8d`) で確定した認知深化
二層 architecture から、M9-B LoRA training pipeline への contamination 防止 ADR を追加。

### 決定

raw_dialog metadata に `individual_layer_enabled: bool` field を追加 (default=false)。
training-view contract loader は **`evaluation_epoch=false AND individual_layer_enabled=false`**
の両方を満たす行のみ訓練 eligible とする。training pipeline 入口で
`all(row.metadata.individual_layer_enabled is False)` を assert し、contamination
検出時は fail-fast。

### 根拠

PR #144 Codex `gpt-5.5 xhigh` review HIGH-3 (`M9-B LoRA training contamination`):
> Individual layer を M9-B 前または並行で cognition に混ぜると、LoRA が philosopher_base
> ではなく「個体 overlay 済み Kant」を学習する。PR #127 の固定 Kant style 前提を破り、
> 後続の base/individual 分解が測定不能になる。

固定 Kant style を保証する training を維持するため、Individual layer が現れた tick の
raw_dialog は **どんな状況でも** training export から除外する。

### 棄却

- 「flag を追加せず、M10-A scaffold 開始時に手動で training export を一時停止する」案:
  human-error 余地が高く、M9-B execution が M10-A と時系列で重なる場合に防御不能
- 「`evaluation_epoch=true` を流用する」案: eval / cognition deepening の 2 軸は orthogonal
  (cognition deepening enabled かつ eval ではない tick がありうる)、統一は意味歪曲
- 「runtime check のみで partition を切らない」案: dataset レベルの persistence で固定する
  ことで、後段 pipeline が flag を尊重する保証が強化される

### 影響

- DB5 (Parquet schema 物理分離) に `individual_layer_enabled` field を 1 つ追加 (additive)
- DB6 (Evaluation epoch 分離) の training-view contract に AND 条件を追加 (additive)
- M9-eval-system Parquet pipeline 実装時に flag 対応必須
- M9-C-adopt (LoRA execution) で training-view loader assert 実装必須
- M10-A scaffold 設計時に `individual_layer_enabled=true` set 責務を明示

### re-open 条件

- 認知深化 phasing が M11+ 以降で根本的に変更され、Individual layer の概念自体が撤回された
  場合 (現時点では PR #144 で確定済み、撤回 path は M12+ research re-evaluation の
  empirical evidence 後でのみ可能)
- LoRA を Individual layer にも適用すると判断された場合 (PR #144 M12+ research gate 該当、
  その時点で contamination 防止 logic を再設計)

### Cross-reference

- PR #144 design-final.md §2.1 (M9 trunk との接続 / M9-B LoRA contamination 防止)
- PR #144 decisions.md DA-8 (philosopher_seed refactor ADOPT-WITH-CHANGES)
- `.steering/20260508-cognition-deepen-7point-proposal/codex-review.md` HIGH-3
