# m9-c-spike — design v2 (`/reimagine` 後、fail-fast + multi-persona 起点)

> **`/reimagine` premise**: v1 を意図的に破棄し、別の出発点から再起草。v1 は
> infrastructure-first + Kant 1 persona + P3 完了待ちで full spike を狙うが、
> **data dependency が外部** (G-GEAR run1 calibration 完了時刻) **に依存**
> という critical risk がある。v2 は **fail-fast (mock-LoRA で infrastructure
> 即検証) + diversification (multi-persona small batch でカバー)** を起点に、
> data-blocked リスクを排除し早期に DB3 fallback 判定材料を得る。

## v2 の基本方針 (v1 との対比)

| 項目 | v1 (infrastructure-first + Kant 1) | v2 (fail-fast + multi-persona) |
|---|---|---|
| 出発点 | bounded Kant spike (M9-B 第3の道 ADR を逐語) | **data-blocked リスク排除 + 早期 fallback 判定** |
| 実走 trigger | P3 golden baseline 完了待ち (~7500 turn) | **2 phase**: ① mock-LoRA で 即 infra 検証 / ② P3 後 multi-persona 実 training |
| persona | Kant 1 のみ | **3 persona (Kant + Nietzsche + Rikyū) rank=4 集合 batch** |
| risk profile | data delay で spike が遅延、fallback 判定材料も遅延 | mock で 即時 fallback 判定可、real training は data 揃い次第 |
| trade-off | M9-B 第3の道 ADR 逐語 (scope 凍結) | scope 拡張 (3 persona、2 phase)、第3の道 ADR を超える |

## 1. Mission (v2、v1 と方向は同じが手段が異なる)

`tier_b/` 完成 (PR #148) で DB9 quorum gate が機能する状態の今、本 spike の
**早期 deliverable** は infrastructure proof。Kant adapter quality は M9-eval
P3 完了後に "real training" phase でつかむ。それまで infrastructure proof は
**mock-LoRA で 即実行** し、DB3 fallback 判定 (>500ms latency / N=3 collapse /
FSM regression) を **data-independent に得る**。

5 deliverable は v1 と同じ:

1. SGLang LoRA endpoint 動作確認
2. adapter swap latency 実測
3. N=3 同時 request throughput 実測
4. M5 resonance / ERRE FSM regression 確認
5. adapter swap runbook (DB8) 起草

ただし v2 では deliverable 1-4 を **mock-LoRA で 即実行可能**、deliverable
5 (runbook) は real training data 込みで後段で起草。

## 2. v2 の 2 phase 構造

### Phase α: Mock-LoRA infrastructure proof (data 不要、即実行可)

- 既存 PEFT で **dummy weights** (random init or 既存 HuggingFace LoRA hub
  から借用) を `safetensors` 形式で保存
- SGLang `--enable-lora` 起動、`/load_lora_adapter` でこの mock を load
- adapter swap latency を実測 (mock weight でも load/unload mechanism は real
  と同じ)
- N=3 同時 request で throughput 確認 (mock adapter ×3 を pinned で運用)
- M5 resonance / ERRE FSM が SGLang LoRA 経路で破綻なし確認

→ **deliverable 1-4 を data-independent に early ship**、DB3 fallback 判定材料
を確定 (>500ms なら vLLM 別タスク fire、<500ms なら SGLang-first 確定)

### Phase β: Multi-persona real training (P3 完了後)

- P3 golden baseline 採取完了 (3 persona × 5 run × 500 turn = 7500 turn) を
  trigger
- **3 persona (Kant + Nietzsche + Rikyū)** を rank=4 (rank=8 ではない、
  data 量から trade-off) で集合 batch 学習
- 各 persona ~2500 turn で training data 量を確保
- M9-eval Tier B (Vendi / Big5 ICC / Burrows Δ) で persona-conditional
  quality signal を測定 → DB9 quorum 判定材料

## 3. v2 commit (推奨初期方向)

| 項目 | v2 commit | 根拠 |
|---|---|---|
| Phase α実走 | mock-LoRA で **即実行**、本 PR scope 内で完結可 | data delay リスク排除 |
| Phase β実走 | 3 persona rank=4 集合 batch、P3 完了後 | data 量と persona coverage の trade-off |
| Base model | qwen3:8b (v1 と同じ) | MASTER-PLAN 確定 |
| Quantization | QLoRA NF4 (v1 と同じ) | DB1 default |
| Library | PEFT (v1 と同じ) | DB2 暫定 |
| **Adapter rank** | **rank=4** (v1 の rank=8 ではない) | 3 persona × ~2500 turn × rank=4 で VRAM/time trade-off |
| Serving | SGLang `--enable-lora` + `/load_lora_adapter` (v1 と同じ) | DB3 |
| Mock weight source | random init or HF LoRA hub (例: `qwen-r4-dummy`) | infrastructure proof のみ目的、quality 不問 |
| Training data minimum (Phase β) | 3 persona × ~2500 turn = 7500 turn | P3 golden baseline 完了の delivered |

## 4. v2 が v1 から変える点

### Phase α (Mock-LoRA、新規)

```python
# tools/spike/build_mock_lora.py (新設、Phase α)
"""Build a deterministic random-init LoRA adapter for SGLang infrastructure proof.

The adapter is *not* trained on persona data — its weights are seeded
random orthogonal matrices that pass safetensors / SGLang format
validation. The purpose is to verify the load/unload/inference path
end-to-end without waiting for P3 golden baseline.

Quality is not tested here; M9-eval Tier B Vendi / Big5 ICC will surface
the mock as low-quality if mistakenly enabled in production (defence in
depth — DB9 quorum prevents adoption).
"""
```

### Phase β (Multi-persona batch、新規)

```python
# src/erre_sandbox/training/train_multi_persona_lora.py (新設、Phase β)
"""Train Kant + Nietzsche + Rikyū LoRA adapters on G-GEAR via multi-persona
batch (rank=4).

Each persona gets its own adapter file (kant-r4-nf4-<date>.safetensors,
etc.), loaded into SGLang via separate /load_lora_adapter calls.
Multi-persona batch saves training time vs sequential 3-spike runs.
"""
```

### 比較: API skeleton 全体

v1 の `SGLangChatClient` API は v2 でも同じ (mock-LoRA load も real-LoRA load
も `load_adapter()` で透過扱い)。違いは:

- v1: `train_kant_lora.py` 単体、Kant 1 persona
- v2: `train_multi_persona_lora.py` + `tools/spike/build_mock_lora.py`、
  3 persona + mock 経路

## 5. VRAM 予算 (v2、3 persona rank=4)

| 項目 | VRAM (Phase α mock) | VRAM (Phase β 3 persona rank=4) |
|---|---|---|
| Qwen3-8B base, NF4 | 5.2GB | 5.2GB |
| LoRA adapter (rank=4 × 3 persona) | ~75MB (Phase β、3 active) | ~25MB (Phase α、mock 1) |
| Training gradient (Phase β、active 1 persona at a time) | — (Phase α は training なし) | ~2.0-2.5GB (rank=4 で v1 の 60%) |
| Activation memory | ~1.0GB | ~1.0GB |
| Buffer / fragmentation | ~0.5GB | ~0.5GB |
| **合計 (training)** | — | **~8.7-9.2GB** |
| **合計 (serving 3 active)** | ~7.5GB | **~7.5GB** |
| **headroom (16GB - peak)** | — | **~6.8-7.3GB** (v1 5.8GB より広い) |

v2 は **rank=4 で VRAM headroom 1GB 増**、training time も 60% 程度に短縮。
trade-off は **adapter expressivity 低下** (rank=4 < rank=8) だが、persona-
conditional adaptation には sufficient (Donnellan-style 2024 LoRA persona
literature は rank=4-8 で adequate と報告、Codex 確認させる)。

## 6. v2 が v1 を破壊する点

- **rank=8 → rank=4**: M9-C-adopt の "rank=8 統一 spike" との整合性は崩れる
  (M9-C-adopt は rank=8 で改めて検証)、本 spike は rank=4 trade-off
- **Kant 1 persona → 3 persona batch**: 第3の道 ADR の "Kant 1 persona" 文言を
  超える scope 拡張、ADR 修正が必要
- **mock-LoRA を本タスク内で実行**: M9-B `decisions.md` で言及されない選択肢、
  ADR 新規起票必要 (CS-N で)
- **2 phase 構造**: M9-B `decisions.md` の単一 spike phase 設計を 2 phase に
  分割

## 7. v2 が捨てている v1 の正しさ (hybrid v3 候補)

v1 が正しい点 (v2 が損なうべきでないもの):

- **bounded scope**: M9-B 第3の道 ADR の "bounded, non-authoritative single-
  persona" は scope creep 防止策。v2 で 3 persona に拡張する正当性は data 量
  (Kant 単独 ~2500 turn は十分) では弱い
- **rank=8 統一**: M9-C-adopt の rank=8 統一 spike と continuity を保つほうが
  研究 timeline で coherent
- **mock-LoRA は不要**: SGLang HIGH-3 で v0.3+ stable と確認済、mock proof
  なくても real Kant LoRA で sufficient
- **8h 工数**: solo cadence で v1 ~8h、v2 は ~12h で +50%

→ **hybrid v3 候補**:

- Phase α (mock-LoRA infra proof) は **採用** (data-blocked 時の hedge、本 PR
  scope 内で完結可、Codex P4a HIGH-3 like の早期 fallback 判定材料)
- Phase β は **Kant 1 persona rank=8 (v1 採用)** に戻す (M9-B 第3の道 ADR と
  continuity、M9-C-adopt rank=8 統一 spike とも整合)
- 3 persona batch は **M9-C-adopt 範囲に defer** (本 spike では Kant のみ)
- mock-LoRA は **infra proof 専用 tool** として `tools/spike/build_mock_lora.py`
  に隔離 (production code 外、`src/` に置かない)

## 8. v3 の primary value proposition

**v3 = v1 (Kant 1 persona rank=8) + Phase α (mock-LoRA infra proof)** の hybrid:

- Phase α (mock) で deliverable 1-4 を **data-independent に early ship**
  (1-2 セッション、P3 完了待ち不要)
- Phase β (real) で Kant adapter quality signal を **P3 完了 trigger** で
  実走 (3 persona batch ではなく Kant 1、M9-B ADR 整合)
- 3 persona batch は M9-C-adopt territory に保留 (scope creep 防止)

工数: Phase α ~3h + Phase β ~8h = ~11h (v1 8h と v2 12h の中間)、ただし
Phase α は P3 待ちでなく即実行可能なので **早期 unblock value** が大きい。

## 9. v2 で意図的に未解決にしている点 (Codex review challenge)

- **mock-LoRA の SGLang format compatibility**: random-init weight で
  `/load_lora_adapter` が拒否されるリスク (PEFT format validation)
- **Phase α / β 切り替えの timing**: P3 完了見込みが不確実な中、Phase α 完了
  後に Phase β を開始する trigger は何か
- **rank=4 vs rank=8 の persona expressivity gap**: 2024-2026 prior art 確認
- **3 persona batch training の interference**: shared base + per-persona
  adapter で persona 間 contamination ゼロ確認 (DB11-like 概念)
- **scope creep risk**: v2 は M9-B 第3の道 ADR の "bounded single-persona" を
  超える、ADR 修正の coast 高い

## 10. Effort estimate (v2)

| Phase | 推定 (v2) |
|---|---|
| 全体 | **~12h** (v1 8h と比較で +50%) |

trade-off:

- 工数 +50% (1 セッション余分)
- 得るもの: data-independent infra proof で **早期 fallback 判定**、3 persona
  coverage で persona-conditional 一般性確認
- 失うもの: scope 拡張 (M9-B 第3の道 ADR からの逸脱、ADR 修正必要)
