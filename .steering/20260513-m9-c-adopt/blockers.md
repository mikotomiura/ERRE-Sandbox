# ブロッカー記録 — m9-c-adopt Phase A (Codex HIGH 4 / MEDIUM 6 / LOW 3 反映後)

> 4 区分: **hard** (Phase B-G 着手不可) / **soft** (回避策あり、観察必要)
> / **defer** (本 PR で扱わない、別 PR で対応) / **uncertainty**
> (empirical 検証で初めて closure)。

---

## Hard blockers (Phase B-G 着手不可)

### H-1: 3 persona golden baseline (PR #160) で nietzsche / rikyu のデータ揃い確認

- **発生日時**: 2026-05-13 (Phase A 起草時)
- **症状**: A-2 (3 persona expansion) は M9-eval Phase B+C で 3 persona
  × 5 run × 500 turn の golden baseline が **既に存在する前提**
  (PR #160 で kant 含む 30 cell golden baseline 採取)。しかし nietzsche /
  rikyu の Tier B baseline ICC (no LoRA) が **計算済みかは未確認**。
  もし baseline ICC が未計算なら、A-6 で LoRA-on Tier B との比較が
  できず、quorum 評価不能。
- **依存タスク**: Phase C (nietzsche / rikyu training) 着手前に baseline
  ICC 計算が完了している必要。M9-eval-system の `tier_b_bootstrap_pair.py`
  consumer 経由で算出
- **解決方法 (planned)**:
  1. Phase A 完了 → Phase B 着手前に 3 persona の baseline ICC が
     `data/eval/m9-c-adopt-tier-b/baseline/{persona}_no_lora.duckdb`
     に揃っているか check
  2. 揃っていない場合は別 PR (`feature/m9-c-adopt-baseline-backfill`)
     で M9-eval P4b 完了 wait or 手動 backfill
- **trigger** (本 blocker fire / 解消判断):
  - 解消条件: 3 persona × baseline Tier B (Vendi + ICC + Burrows Δ) が
    Phase B+C golden baseline shard から算出済
  - fire 継続条件: nietzsche / rikyu の baseline ICC 未計算
- **影響範囲**: Phase B-G 全体 (A-6 Tier B 比較不能 → A-8 verdict 不可)
- **教訓**: M9-eval-system の Tier B framework 完成度を adopt phase
  着手前に check する habit、PR #160 merge 後の Tier B 完了 verification
  step を tasklist に明示すべき

### H-2: rikyu Japanese tokenizer 未実装 (Burrows Δ N/A、Codex MEDIUM-2 / LOW-3 反映)

- **発生日時**: 2026-05-13 (Codex review MEDIUM-2 / LOW-3 で hard blocker
  化要求)
- **症状**: rikyu (千利休、Japanese persona) の corpus は MeCab/fugashi/
  Sudachi 等の Japanese-aware tokenizer 必須。現状 ERRE 評価系は英文
  前提で構築、Japanese morphological tokenizer 未実装。Burrows Δ が
  rikyu で N/A、DA-8 で 2-of-2 fallback を named limitation 扱いとした
  が、tokenizer 実装が本来の解決
- **依存タスク**: 別 PR `m9-eval-corpus-rikyu-tokenizer` (M9-eval-system
  scope) で fugashi/MeCab を Tier B Burrows Δ pipeline に integrate
- **解決方法 (planned)**:
  1. **A 案** (pragmatic): fugashi/MeCab を `pyproject.toml [eval]`
     extra に追加、`tier_b_burrows_delta.py` consumer で Japanese
     detection (rikyu persona_id) 時に切替
  2. **B 案** (defer): rikyu 永続 2-of-2 fallback、tokenizer 実装は
     M10 範囲
- **trigger**:
  - 解消条件: rikyu Burrows Δ が `tier_b_bootstrap_pair.py` で
    valid value 返す (N/A でない)
  - fire 継続条件: rikyu Burrows = N/A
- **影響範囲**: A-6 (rikyu Tier B のみ)、A-8 (rikyu の DA-8 2-of-2
  fallback) — kant / nietzsche は影響なし
- **教訓**: Japanese persona 評価は corpus tokenizer が前提、persona
  expansion 設計時に corpus 言語ごとの evaluator readiness check が
  必要 (Codex MEDIUM-2 で確認、引用: arxiv:2010.06858 fugashi paper)

---

## Soft blockers (回避策あり、観察必要)

### S-1: SGLang 0.5.10.post1 upstream regression リスク

- **発生日時**: 2026-05-13 (Codex HIGH-3 で SGLang multi-LoRA
  fragmentation 注意喚起)
- **症状**: SGLang 0.5.10.post1 は spike で empirical 8ms latency
  確認済だが、3 adapter concurrent serving での fragmentation behavior
  (P-LoRA / S-LoRA / dLoRA で documented) は未測。upstream で
  scheduling / batching が変わる場合、本 PR DA-2 の SGLang-only
  rollout が degrade する可能性
- **回避策**:
  - Phase E の A-4b real-after stress bench で memory growth + queue
    wait monitor、threshold fire で DB3 re-arm trigger
  - SGLang 0.6 stable release で fragmentation 改善が confirmed → version
    pin amendment 別 PR
- **trigger**:
  - fire: A-4b で queue wait p99 > 30s OR memory growth > 500MB/1h
    sustained → DB3 re-arm
  - 解消: SGLang upstream で改善 confirmed、または vLLM migration 完了

### S-2: `--max-lora-rank >= 16` への CS-1 amendment (Codex HIGH-1 反映)

- **発生日時**: 2026-05-13 (Codex HIGH-1)
- **症状**: spike CS-1 で `--max-lora-rank 8` を pin、本 PR DA-1 で
  rank=16 を sweep 範囲に含めるため、`--max-lora-rank >= 16` (rank=32
  tail-sweep fire 時は 32) への amendment が必要。CS-1 自体は immutable
  だが、launch args の rank-related field は本 PR で update
- **回避策**:
  - CS-1 amendment 候補として本 PR で記録、Phase B 着手前に M9-C-spike
    decisions.md CS-1 amendment 別 PR で update
  - `docs/runbooks/m9-c-adapter-swap-runbook.md` (DB8) の launch SOP に
    Phase B 着手前 `--max-lora-rank` amendment 手順を追記
- **trigger**:
  - fire: CS-1 amendment 未実施で rank=16 sweep 実施 → SGLang が
    rank=16 adapter を reject
  - 解消: CS-1 amendment merge + runbook update

### S-3: VRAM peak rank=16 / rank=32 で headroom 圧迫リスク

- **発生日時**: 2026-05-13 (Phase A 起草時、CS-4 budget 検証)
- **症状**: CS-4 で base 8.7GB + adapter 3 × ~30MB = ~8.8GB peak
  (rank=8)。rank=16 で adapter ~60MB / activation 増、rank=32 で
  ~200MB / activation 大幅増。CS-4 amendment で fp8 serving 10.86GB
  peak (rank=8) を観察済、rank=16 / 32 でさらに増える可能性
- **回避策**:
  - Phase B 開始時に `nvidia-smi --query-gpu=memory.used` per-step
    sampling、peak > 14GB で early abort
  - rank=32 tail-sweep fire 時は --quantization fp8 + --mem-fraction-static
    0.85 を継続、必要に応じて --max-total-tokens 1024 に縮める
- **trigger**:
  - fire: rank=16 で VRAM peak > 14GB → CS-4 amendment、rank=16 評価
    打ち切り (rank=8 final)
  - fire: rank=32 で OOM → tail-sweep 中止、rank=16 final
  - 解消: rank=16 peak < 13GB 観察 → continue

---

## Defer (本 PR で扱わない、別 PR で対応)

### D-1: PEFT vs unsloth final 選定 (M9-C-spike D-2 継続)

- **症状**: M9-C-spike D-2 で defer、本 PR でも rank sweep 結果次第
- **defer 理由**: rank=8/16 で PEFT empirical 確認、性能差 < 5% なら
  PEFT 維持、> 10% なら unsloth 評価 (別 PR)
- **trigger** (defer 解除条件): rank sweep で unsloth 性能差 > 10%
  観察、または PEFT 0.20+ で breaking change

### D-2: 4 persona 目以降 (Confucius / Socrates 等、M10 範囲)

- **症状**: 本 PR は 3 persona (kant/nietzsche/rikyu) のみ
- **defer 理由**: M10 範囲、本 PR scope 外
- **trigger**: M10 着手時 (3 persona adopt 完了 + soak 1 week 後)

### D-3: vLLM full migration (DB3 NON-FIRE 後の future option)

- **症状**: SGLang-first 採用、vLLM は DA-2 で late-binding のみ記録
- **defer 理由**: Codex MEDIUM-1 で "vLLM dynamic updating is
  security-sensitive" 指摘、Phase D skeleton 不要
- **trigger**: DB3 re-arm trigger fire (SGLang launch fail 3 連続 OR
  adapter load p99 > 500ms 24h sustained OR Tier B quorum 0-of-3 OR
  multi_lora_3 memory growth > 500MB/1h sustained)

### D-4: M9-eval-system Tier C P6 judge LLM integration

- **症状**: 本 PR は Tier B framework consumer のみ
- **defer 理由**: M9-eval-system ME-* に閉じる、本 PR scope 外
- **trigger**: M9-D-eval-tier-c 着手時 (Phase H 候補)

### D-5: SGLang 0.6+ release upgrade (M9-C-spike S-1 継続)

- **症状**: M9-C-spike S-1 で SGLang 0.6 stable release 未確認 → 0.5.10.post1
  pin
- **defer 理由**: upstream 動向 watch、breaking change なければ pin 維持
- **trigger**: SGLang 0.6 stable + 互換性確認 + fragmentation 改善

---

## Uncertainty (empirical 検証で初めて closure)

### U-1: rank=32 必要性 (Codex HIGH-1 反映、DA-1 conditional re-open)

- **症状**: rank ∈ {4, 8, 16} default sweep で rank=32 不要かは empirical
  未確認
- **closure path**: Phase B で rank=16 throughput PASS + Vendi/ICC/Burrows
  のいずれか未達 → rank=32 tail-sweep fire、または rank=8→16 で sharp
  gain (delta > 0.5) → rank=32 tail-sweep fire
- **trigger**: Phase B 完了時、tail-sweep fire 条件を満たすかで判定

### U-2: provisional Tier B threshold (d≥0.3 / ICC≥0.6 / Burrows≥10%) operational soundness (Codex HIGH-2)

- **症状**: provisional pin は本 PR の **screen**、final pin は P4b/P4c
  完了後
- **closure path**: Phase F の A-8 verdict 報告で marginal pass 該当
  数を観察、literature update / Vendi sensitivity panel (ME-10) で
  shoulder 再定義 → DA-11+ で tighten
- **trigger**: marginal pass が 2-of-3 metric 全てで観察 → DA-9 retrain
  cycle、3 metric とも CI clear → ADOPT 確定

### U-3: fp8 serving acceptance (CS-4 amendment 由来)

- **症状**: K-α serving は fp8 base 強制、M9-eval P6 judge LLM が
  fp8 base output を accept するか未検証
- **closure path**: Phase E で 3 persona Tier B 採取 (fp8 serving)、
  Phase F で M9-eval Tier C P6 judge との互換確認 (M9-eval-system 側
  実装が完成 = M9-D-eval-tier-c 着手後)
- **trigger**: Phase F の Tier C P6 integration 試験で fp8 serving
  output が judge LLM で reject → CS-4 amendment、fp16 serving への
  fallback 検討

### U-4: SGLang multi_lora_3 fragmentation real workload behavior (Codex HIGH-3)

- **症状**: spike で single_lora vs no_lora のみ実測、N=3 multi-LoRA
  での fragmentation 未測
- **closure path**: Phase D mock-first bench (CS-7 4 trigger) →
  Phase E real-after stress bench (CS-7 拡張 + churn diagnostic + memory
  growth)、CS-7 全 NON-FIRE で AC-4 PASS
- **trigger**: A-4b stress bench で memory growth > 500MB/1h sustained
  OR queue wait p99 > 30s → DB3 re-arm trigger fire

### U-5: 8-mode FSM regression (Codex 言及なし、D-5 由来)

- **症状**: K-α deep_work mode smoke のみ、残り 7 mode は LoRA-on で
  未測
- **closure path**: Phase E FSM smoke 24 cell PASS で closure (DA-7
  pass 基準 = final mode 一致のみ)
- **trigger**: 24 cell のうち 1 でも fail → LoRA 採用 reconsider、
  Phase F verdict reject candidate
