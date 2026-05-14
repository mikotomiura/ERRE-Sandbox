# Tier B baseline (no-LoRA) — kant — m9-c-adopt Phase B Step 5a

> **Status**: partial (Vendi lexical-5gram のみ algorithm computed). Vendi
> semantic + Big5 ICC + Burrows Δ は **DA-11 scope narrowing** により
> Phase B 第 4 セッション (別 PR / Mac post-hoc) に defer.

---

## Inputs

- shards: `data/eval/golden/kant_stimulus_run{0..4}.duckdb` (5 shard, PR #160 由来)
- focal speaker: `kant`
- focal turns per shard: 504 (stratified slice + 3 cycle = ~504 turn/run)
- total focal turns: **2520** (5 × 504)
- window size: 100 turns (non-overlapping; tail dropped)
- windows per cluster: 5 (504 / 100 = 5 full + 4 tail dropped)
- total windows: **25** (5 cluster × 5 window) — matches Tier B framework
  cluster size in M9-eval ME-14

---

## Vendi (lexical-5gram) — computed 2026-05-14

artefact: `.steering/20260513-m9-c-adopt/tier-b-baseline-kant-vendi-lexical.json`

| field | value |
|---|---|
| metric | `vendi_lexical_5gram` |
| kernel | char 5-gram Jaccard (deterministic, no ML deps) |
| n_clusters | 5 |
| total_windows | 25 |
| **point** | **75.7692** |
| **CI95 lo** | **75.1892** |
| **CI95 hi** | **76.3720** |
| CI width | 1.1828 |
| bootstrap method | hierarchical-cluster-only (ME-14) |
| n_resamples | 2000 |

Interpretation: under the no-LoRA Ollama qwen3:8b serving, the kant focal
utterances exhibit a per-window character-5-gram diversity score of ~75.8
(out of theoretical max = window size = 100 = identity matrix). High value
indicates substantial lexical surface diversity even within 100-turn
windows. The DA-1 axis direction for the LoRA-on comparison is
**LoRA-on < no-LoRA** (LoRA should concentrate the persona signal,
reducing apparent diversity).

### Lexical-5gram と semantic kernel の関係

- DA-1 採用基準は **semantic kernel (MPNet)** が primary。lexical-5gram は
  diagnostic / Mac eval venv 不在時の代替。
- Phase B 第 4 セッションで [eval] extras + MPNet cache を Mac master 側に
  整え、`compute_baseline_vendi.py --kernel semantic` で再算出。
- semantic kernel 値は character-level diversity を意味的距離に置き換えるため
  lexical-5gram より低い値域 (典型的に 5-25 程度) を取る — direct な値比較
  ではなく direction (LoRA-on < no-LoRA) を見る。

---

## Big5 ICC(C,k) primary + ICC(A,1) diagnostic — DEFERRED

**Status**: 未算出 (Phase B 第 4 セッション scope)

理由:
1. Big5 ICC は per-window Big5 vector が必要 = `compute_big5_icc(big5_per_window)`
2. Big5 vector は `administer_ipip_neo(responder)` で per-window 算出
   (50 question × 5 dim Likert mean)
3. responder = LLM-backed callable: per IPIP-50 statement → 1-5 Likert
4. 規模: 50 question × 25 window × 5 run = **6,250 inference per persona**
5. compute time (Ollama qwen3:8b @ ~3-5s/inf): **~9 hours** for baseline
   alone, plus equivalent compute per LoRA-on shard
6. consumer script (DuckDB shard → IPIP responder → Big5 ICC) は未実装

defer 内容:
- separate PR (`feature/m9-c-adopt-tier-b-icc-consumer`) で
  `scripts/m9-c-adopt/compute_baseline_big5_icc.py` 新規実装
- Ollama backed responder (no-LoRA baseline) と SGLang+LoRA backed
  responder (rank ごと) を switch
- per-window context conditioning は **none** (Salecha et al. 2024
  anti-demand-characteristics 設計に従い、過去 100 turn を context に
  入れず単発 IPIP 投与とする) — または「直前 5 turn の persona 発話」
  を system prompt に挿入する `light context` モード (research design
  decision required)

---

## Burrows Δ — DEFERRED

**Status**: 未算出 (Phase B 第 4 セッション scope)

理由:
1. kant 発話は **混合言語** (de / en / ja) — sample 5 utterances:
   - `Die menschliche Vernunft ist...` (de)
   - `Synthetic a priori judgments...` (en)
   - `行動をもつ者は、常に普遍的立法として行動せよ` (ja)
   - `Geschmack ist die Wahrnehmung...` (de)
   - `Morality and happiness are distinct...` (en)
2. `compute_burrows_delta` は per-language reference 必須:
   - kant German reference: 存在 (`reference_corpus/raw/kant_de.txt` +
     vectors.json)
   - kant English reference: **未整備** (Cambridge Edition 等の
     license-audit pending, M9-eval-system 別 PR scope)
   - Japanese: tokenizer 未実装 (H-2 named limitation)
3. naive 実装 (de utterances のみ filter) では sample size が ~30-40%
   に縮み、CI が広がりすぎる可能性

defer 内容:
- Phase B 第 4 セッションで以下のいずれか:
  - **Option A**: 言語自動判定 (e.g. `langdetect`) で per-utterance
    routing、de は existing reference / en と ja は skip ("limitation"
    扱い)
  - **Option B**: Cambridge Edition Kant English vendoring (M9-eval-system
    `m9-eval-corpus-kant-en` 別 PR を blocker 化)
  - **Option C**: kant baseline で Burrows N/A 扱い (rikyu と同 pattern、
    DA-8 2-of-2 fallback を kant にも適用)
- 採用 option は Phase B 第 4 セッション最初のミーティング判断

---

## Per-rank Vendi (lexical-5gram) — Phase B Step 5d (provisional)

artefacts: `tier-b-pilot-kant-r{4,8,16}-vendi-lexical.json`

| rank | shards | windows | point | CI95 lo | CI95 hi | width |
|---|---|---|---|---|---|---|
| no-LoRA baseline | 5 | 25 | **75.7692** | 75.1892 | 76.3720 | 1.18 |
| 4 (LoRA-on) | 2 | 6 | **86.9267** | 86.2540 | 87.5995 | 1.35 |
| 8 (LoRA-on) | 2 | 6 | **88.6762** | 87.6248 | 89.7276 | 2.10 |
| 16 (LoRA-on) | 2 | 6 | **86.3774** | 86.2398 | 86.5150 | 0.28 |

### 観察 (重要 caveat)

**LoRA-on は no-LoRA baseline より HIGHER lexical Vendi を示した** (DA-1
仮定 "LoRA-on < no-LoRA" の direction と逆)。考えられる説明:

1. **Methodological artifact (最有力候補)**: pilot は **single-turn** stim
   採取 (本セッション scope narrowing、`_focal_turn_count` を 1 に固定)、
   一方 baseline は **multi-turn** dialog (focal kant が dialogue 内で
   alternating turn 発話、続き発話は文脈引きずりで lexically similar)。
   → pilot の per-window prompt diversity が baseline より高い → 自然と
   diversity score が上がる
2. **Lexical kernel の persona signal sensitivity 不足**: LoRA は semantic
   レベルで persona signal を集中させているが、surface character 5-gram
   レベルでは見えない可能性。Phase B 第 4 セッション semantic Vendi で
   要再評価
3. **Window/sample size の差**: baseline 25 window vs pilot 6 window per
   rank、bootstrap CI 比較は強くない (overlapping CI の解釈に注意)

### 限定的解釈 (provisional)

lexical-5gram のみでの DA-1 軸 1 評価は **inconclusive**。Phase B 第 4
セッションで:
- semantic Vendi (MPNet) で再評価
- Big5 ICC で persona-fit 直接評価
- Burrows Δ で stylometric 直接評価
- pilot を multi-turn 採取に拡張するか pilot/baseline の prompt scheme を
  align するかも判断 (DA-12 候補)

**rank 間** の比較 (caveat 同じ条件下):
- rank=4 / rank=16 ≈ 86-87 (close)
- rank=8 ≈ 88.7 (highest)
- 単調性 (rank 上昇 → 効果集中) は **観察されず**、一筋縄ではない signal

→ DA-1 採用判定は **本セッションでは確定しない**。Phase B 第 4 セッション
で 3 軸 (Vendi semantic + ICC + Burrows) 揃いの上で final 確定。

---

## CS-7 per-rank single_lora bench — Phase B Step 5e (partial)

artefacts: `data/eval/m9-c-adopt-bench/single_lora-r{4,8,16}.jsonl`
condition: `--num-prompts 32 --random-input-len 256 --random-output-len 256 --seed 0`
baseline: PR #163 K-β single_lora 34.64 tok/s (no_lora は本セッションで未再採取、
`--enable-lora` flag toggle 必須のため Phase B 第 4 セッション or 後続 PR で
判断)
threshold: 0.7 × 34.64 = 24.25 tok/s

| rank | output tok/s | ttft p50 ms | ttft p99 ms | e2e p99 ms | itl p99 ms | success |
|---|---|---|---|---|---|---|
| 4 | **33.82** | 75092 | 137359 | 142512 | 33.3 | 32/32 |
| 8 | **33.77** | 76340 | 139402 | 143553 | 32.8 | 32/32 |
| 16 | **33.72** | 73361 | 137847 | 142965 | 32.9 | 32/32 |

### CS-7 4 trigger 評価

1. **p95 e2e > 2x baseline**: 33.7+ tok/s vs 34.64 baseline = 0.97x → **NOT FIRE**
2. **output tok/s < 24.25 threshold**: 33.7-33.8 tok/s → **NOT FIRE**
3. **adapter-misrouting**: Step 4 multi_pin sanity で 3 rank 異なる出力確認済 → **NOT FIRE**
4. **timeout (any)**: 32/32 success、0 error → **NOT FIRE**

→ **CS-7 4 trigger 全 NON-FIRE for single_lora-r{4,8,16}** (DA-1 軸 4 throughput PASS)

### 観察

- 3 rank 間で throughput **ほぼ同一** (33.7-33.8 tok/s ± 0.05): single_lora
  での rank cost は無視可能、DA-1 ceiling 内で smaller rank 採用基準は
  serving 観点では meaningless (Tier B differentiation が決定的)
- TTFT p50 ~75 sec: `--max-running-requests 1` で 32 prompt が serialized、
  N=1 concurrency 想定が prompt queue を直列化、これは実ライブ inference の
  Latency-per-request ではない (queue effect)
- ITL p99 ~33 ms: SGLang fp8 + LoRA delta に対して Blackwell GPU で十分高速

---

## DA-1 4 軸 intersection に対する影響 (Step 5f 連動)

DA-1 採用基準 (decisions.md より):
1. Vendi semantic point + CI lower + direction (LoRA-on < no-LoRA)
2. Big5 ICC(C,k) ≥ 0.6 point + CI lower
3. Burrows Δ reduction ≥ 10% point + CI lower
4. throughput ≥ 24.25 tok/s ceiling

本セッション scope narrowing (DA-11) の結果、本セッションでは:
- **軸 1 (Vendi)**: lexical-5gram のみ。semantic は Mac post-hoc
- **軸 2 (Big5 ICC)**: 未評価 (Phase B 第 4 セッション)
- **軸 3 (Burrows)**: 未評価 (Phase B 第 4 セッション)
- **軸 4 (throughput)**: Step 5e bench で本セッション内に評価可能

→ Step 5f の rank 採用判定は **Vendi lexical + throughput** の 2 軸 +
Step 4 multi_pin sanity の 3 rank 出力差異の qualitative review で
**provisional** に行い、final 採用は Phase B 第 4 セッションで
ICC + Burrows + semantic Vendi 揃った後の改めて DA-1 4 軸 intersection
で確定する。

---

## 関連

- 計算 script: `scripts/m9-c-adopt/compute_baseline_vendi.py`
- bootstrap CI ヘルパ: `src/erre_sandbox/evidence/bootstrap_ci.py`
- Vendi pure helper: `src/erre_sandbox/evidence/tier_b/vendi.py`
- Big5 ICC pure helper: `src/erre_sandbox/evidence/tier_b/big5_icc.py`
- Burrows pure helper: `src/erre_sandbox/evidence/tier_a/burrows.py`
- IPIP-50 administering: `src/erre_sandbox/evidence/tier_b/ipip_neo.py`
- DA-11 ADR: `decisions.md` (本 PR で追加)
