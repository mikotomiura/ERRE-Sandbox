# Design v1 — Claude 初回案 (10 軸: LoRA 実装最優先路線)

> ⚠️ **このドキュメントは /reimagine 適用のため意図的に v2 と対比する初回案として保存される。
> 実装方針は design-final.md で確定する。**

## 設計思想 (v1 の暗黙前提)

m9-lora-pre-plan の 5 ADR (D1-D5) を尊重しつつ、未決事項を **「LoRA を回せば
persona divergence は伸びる」** という前提のもと最短経路で実装着手する路線。
評価系 (J 軸) は framework 宣言だけにとどめ、本格実装は M9-eval-system に切り出す。

短期的 deliverable: M9-C で 3 persona の LoRA adapter を学習・swap 動作させること。

## 10 軸の決定 (v1)

### A. 量子化戦略 → **QLoRA (NF4) 採用**

**根拠**:
- G-GEAR VRAM 16GB、qwen3:8b base ≈ 16GB FP16 → そのままでは 3 persona 載らない
- QLoRA (NF4 + double-quantization) で base を 4-5GB に圧縮、3 persona base 共有 + adapter (~50MB/persona) で 6GB 強で済む
- 性能低下は LoRA 系 paper で 1-2% 前後、許容範囲

**棄却**:
- LoRA FP16: VRAM 不足 (3 persona swap 不可)
- INT8 + LoRA: NF4 ほど圧縮されず QLoRA の上位互換性なし

### B. Library 選定 → **unsloth 採用**

**根拠**:
- QLoRA 最適化済 + 2-5x 高速学習
- G-GEAR 単機運用、学習時間が最大の現実制約
- rank=8 統一で初回 spike

**棄却**:
- PEFT (HuggingFace 公式): unsloth より遅い、ecosystem 厚いが本プロジェクトでは benefit 小

### C. Serving 移行判断 → **vLLM full migration**

**根拠**:
- vLLM `--enable-lora` は LoRA hot swap の決定版、`LoRARequest` API で adapter 切替
- SGLang LoRA は v0.3+ で対応開始、安定性未検証
- 現行 SGLang は OpenAI 互換 endpoint なので migration コスト中程度

**棄却**:
- SGLang 維持: LoRA 機能不足
- ハイブリッド (推論 SGLang + LoRA は vLLM): 二重運用コスト過大

### D. Dataset trigger 閾値 → **AND 強条件**

**決定**: 以下 3 条件が **すべて** 満たされたら LoRA 適用 fire
1. `dialog_turn ≥ 500` per persona (質的閾値の代理)
2. `divergence_ratio` (ζ 36:74:16 cadence 起点) が ±10% 以内に維持
3. `baseline floor`: self_rep ≤ 0.10 AND cross_echo ≤ 0.10

**根拠**: AND の方が誤適用 (思想的偏向の固着) を避けられる

**棄却**:
- OR 条件: 早すぎる適用で baseline drift リスク

### E. Parquet export schema → **flat 結合 + persona_id partition**

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
  - evaluation_epoch: bool
```

partition: `persona_id=*/run_id=*/`

### F. 評価 epoch 分離 → **Run-level boolean flag**

- `evaluation_epoch: bool` を Run config + Parquet schema に追加
- Default `False` (autonomous = training input)
- Evaluation run は手動切替、autonomous log と物理的に分離 (Parquet partition 別ディレクトリ)

### G. Persona N=4 拡張時期 → **M9-B 中に YAML 起草、spike は M9-C**

- agora 主体 (4 人目候補) の persona YAML 雛形を本タスク中に起草
- VRAM 実測は M9-C で base 共有 (QLoRA) + 4 adapter 同時 load の VRAM 試算と実測

### H. Adapter swap runbook → **vLLM LoRARequest 経由**

- vLLM `--enable-lora --max-loras 4 --max-lora-rank 16` で起動
- request 時に `LoRARequest(lora_name, lora_int_id, lora_local_path)` で adapter 指定
- cold start latency: 推定 3-5s (adapter load on GPU)、cache hit で <100ms
- SGLang 互換 API ラッパは別途実装、本タスクでは scope out

### I. Baseline drift gate → **margin 50% で auto rollback**

- self_rep > 0.15 (baseline 0.10 の +50%) で警告
- cross_echo > 0.15 で警告
- いずれか発生で次 run 自動的に previous adapter に rollback、log 記録

### J. 思想家らしさ評価系 framework → **Tier A のみ M9-B 内、Tier B-D は M9-eval-system**

- M9-B: Tier A (per-turn cheap metrics) 5 個を schema に組み込む宣言
  - LIWC-22 (要 license 評価)
  - Burrows' Delta to thinker reference corpus
  - MATTR
  - semantic novelty (MPNet embedding distance)
  - persona_contradiction_rate (NLI head)
- M9-eval-system: Tier B-D (Vendi / Prometheus / FANToM / FActScore / 専門家 review) を切り出し
- **攻めの gate (J5)**: v1 では「floor 維持のみ」採用 (適用前 baseline からの劣化を auto rollback、改善は要求しない)

## 数値 gate サマリ (v1)

| Gate | 条件 | 動作 |
|---|---|---|
| Dataset trigger | dialog_turn ≥ 500 AND divergence ±10% AND floor (self_rep ≤ 0.10, cross_echo ≤ 0.10) | LoRA 適用 fire |
| Baseline drift | self_rep > 0.15 OR cross_echo > 0.15 | 自動 rollback |
| VRAM | base 5GB + 4 adapter ≤ 8GB total | N=4 拡張可 |
| 攻めの gate (J5) | "floor 維持のみ" | 改善要求なし |

## 実装順序 (M9-C へのハンドオフ)

1. vLLM `--enable-lora` 起動、SGLang 撤退
2. Parquet pipeline 実装 (E schema)
3. unsloth で persona 1 (Kant) の QLoRA spike (rank=8、500 turn 起点)
4. 学習 loop + evaluation epoch 切替実装
5. baseline floor + drift gate 実装
6. agora 主体 (persona 4) YAML 起草
7. N=4 VRAM 実測
8. adapter swap runbook 文書化
9. Tier A metric を schema 組込
10. M9-eval-system キックオフ (J 軸 Tier B-D)

## 想定される v1 の弱点 (self-critique)

(これは /reimagine 起動時に v2 で攻める論点になる候補)

1. **評価系後置の論理矛盾**: J6 で M9-eval-system に切り出すが、攻めの gate がない状態で
   LoRA 適用したとき「思想家らしさが向上したか」を測れない → 適用の成否判定不能
2. **AND 強条件の現実性**: 3 条件すべて満たすのは現状では数 run 必要、いつ trigger するか不確実
3. **vLLM full migration コスト**: SGLang 撤退は M5 以降の resonance 機構や ERRE mode FSM の
   再配線が必要で、見積もり甘い可能性
4. **LIWC license**: 商用 license が必要 (LIWC-22)、zero-budget 制約と矛盾の懸念
5. **「LoRA を回せば divergence は伸びる」前提の検証なし**: prompting + persona YAML 拡張で
   現在の divergence をどこまで伸ばせるかの天井を測っていない。LoRA 適用の必要性自体が
   empirically 立証されていない可能性
6. **Burrows' Delta は philosophical 翻訳に弱い**: Kant 独原典 vs 英訳の差異が persona-fit
   metric を汚染する可能性
7. **idea density の persona-conditional 性**: Rikyu LOW vs Kant HIGH を絶対値 gate で扱うと誤検知
