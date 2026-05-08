# m9-c-spike — design v1 (infrastructure-first 起点)

> 本 v1 は意図的に `/reimagine` で破壊される対象。次の v2 が別の出発点 (例:
> training-quality-first / mock-LoRA-first 等) から再生成され、
> `m9-c-spike-design-comparison.md` で hybrid v3 候補を検討する。HIGH 検出は
> Codex review に委ねる。
>
> Refs: M9-B `decisions.md` DB1-DB11 + 第3の道 ADR (PR #127)、CLAUDE.md
> 「Codex を積極活用」、`schemas.py::EpochPhase` (L254)、
> `inference/ollama_adapter.py::OllamaChatClient` (API 雛形)、
> `evidence/eval_store.py::connect_training_view` (DB5 entry)。

## 1. Mission

`src/erre_sandbox/inference/sglang_adapter.py` 新設 + `src/erre_sandbox/training/`
module 新設で、Kant 1 persona の bounded LoRA spike を実行可能にする。本 spike
は **non-authoritative** — adoption 判断は M9-eval-system 完成後の post-spike
re-eval まで保留。

ゴールは下記 5 deliverable (Phase 1 探索で抽出):

1. SGLang LoRA endpoint 動作確認 (`--enable-lora` + `/load_lora_adapter`)
2. **adapter swap latency** 実測 (>500ms は DB3 vLLM fallback fire)
3. **N=3 同時 request throughput** 実測 (collapse なし)
4. **M5 resonance / ERRE FSM regression** 確認 (SGLang LoRA 経路で破綻なし)
5. **adapter swap runbook (DB8)** 起草 (実測値込み、本 spike 完了後)

## 2. v1 commit (推奨初期方向)

| 項目 | v1 commit | 根拠 |
|---|---|---|
| Spike scope | Kant 1 persona、既存 dialog_turn (`epoch_phase != EVALUATION`) のみ training data | 第3の道 ADR、DB4 dataset trigger |
| Base model | qwen3:8b (M9-eval と同じ) | MASTER-PLAN 確定、cross-spike consistency |
| Quantization | QLoRA NF4 (default) | DB1 default |
| Library | PEFT (公式・ecosystem 厚い) | DB2 暫定、final は M9-C-adopt |
| Adapter rank | rank=8 統一 | DB2 hybrid (M9-C-adopt rank=8 統一 spike と整合) |
| Serving | SGLang `--enable-lora` + `/load_lora_adapter` REST | DB3、Codex HIGH-3 で v0.3+ stable 確認済 |
| Training data minimum | P3 golden baseline 7500 turn (Kant 部分 ~2500 turn) | DB4 coverage 300/persona、Kant 単独 pilot ~40-50 turn は不足 |
| Adapter swap latency target | <500ms | DB3 vLLM fallback 条件 (>500ms fire) |

## 3. SGLang adapter 拡張 API skeleton

### `src/erre_sandbox/inference/sglang_adapter.py` (新設)

`OllamaChatClient` API signature を踏襲しつつ、LoRA load/unload を追加:

```python
"""SGLang adapter — multi-LoRA aware chat client.

Wraps the SGLang HTTP server (started with ``--enable-lora --max-loras N
--max-lora-rank R``) to provide an OllamaChatClient-compatible chat surface
plus the additional LoRA load/unload REST endpoints documented in SGLang
v0.3+ (multi-LoRA / dynamic load/unload / pinned adapters / overlap loading,
M9-B DB3 / Codex HIGH-3).

The adapter is read by the live inference path (``inference/server.py``) for
LoRA-enabled persona serving. Tests pass an ``httpx_client`` stub so the
heavy server dep never fires in CI.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import httpx

from erre_sandbox.inference.ollama_adapter import (
    ChatMessage,
    ChatResponse,
    SamplingParameters,
)


@dataclass(frozen=True, slots=True)
class LoRAAdapterRef:
    """Identifier for a loaded LoRA adapter on the SGLang server."""
    adapter_name: str        # e.g. "kant-r8-nf4-2026-05-08"
    base_model: str          # e.g. "qwen/Qwen3-8B"
    rank: int                # 8 in the M9-C-spike default
    pinned: bool = False     # SGLang pinned adapter optimisation


class SGLangUnavailableError(RuntimeError):
    """Raised when the SGLang HTTP server returns a non-200 / connection error.

    Mirrors :class:`OllamaUnavailableError` so the caller can handle both
    backends symmetrically. ``error_handling`` Skill applies (retry policy
    in ``error-handling.examples.md``).
    """


class SGLangChatClient:
    """SGLang HTTP chat client with multi-LoRA support.

    The constructor only stores config; the heavy ``httpx.AsyncClient`` is
    created lazily on first call and reused per process. The load/unload
    methods speak to SGLang ``/load_lora_adapter`` and
    ``/unload_lora_adapter`` REST endpoints.
    """

    def __init__(
        self,
        *,
        base_url: str,
        default_model: str,
        httpx_client: httpx.AsyncClient | None = None,
    ) -> None: ...

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        sampling: SamplingParameters,
        model: str | None = None,
        adapter: LoRAAdapterRef | None = None,
    ) -> ChatResponse:
        """Mirror OllamaChatClient.chat with optional adapter routing."""

    async def load_adapter(
        self,
        ref: LoRAAdapterRef,
        *,
        weight_path: str,
    ) -> None:
        """POST /load_lora_adapter; idempotent when ref already loaded."""

    async def unload_adapter(self, ref: LoRAAdapterRef) -> None:
        """POST /unload_lora_adapter; idempotent when not loaded."""

    async def list_adapters(self) -> list[LoRAAdapterRef]:
        """GET /list_lora_adapters; returns currently loaded adapters."""

    async def close(self) -> None:
        """Release the lazy httpx.AsyncClient (idempotent)."""
```

**Key design choice (v1)**: REST endpoint URL は SGLang v0.3+ documented の
`/load_lora_adapter` POST (Codex HIGH-3 reflection)。Codex review で current
SGLang version の正確な endpoint path を確認させる。

## 4. training/ module skeleton (新設)

### `src/erre_sandbox/training/__init__.py`

```python
"""LoRA fine-tuning pipeline for ERRE-Sandbox personas.

This package is pure post-hoc / off-line — it never participates in the live
inference path. The single training-egress entry from raw_dialog is
:func:`erre_sandbox.evidence.eval_store.connect_training_view` (DB5 contract);
this package consumes that read-only view and produces LoRA adapter weights.

Architectural constraint (M9-B DB5/DB6):
* Reads ``raw_dialog.dialog`` only (never the ``metrics`` schema).
* Filters to ``epoch_phase != EpochPhase.EVALUATION`` rows.
* Writes adapter checkpoints to disk; no metric-shaped output.

DB11 contamination prevention: when ``individual_layer_enabled`` field is
added to the raw_dialog allow-list (separate task
``m9-individual-layer-schema-add``), this package will assert
``individual_layer_enabled is False`` for every consumed row (M10-A onward).
"""
```

### `src/erre_sandbox/training/prompt_builder.py` (新設)

```python
"""Convert raw_dialog rows into PEFT SFTTrainer-compatible prompt/completion.

Pure-function module: takes a sequence of raw_dialog dicts (per
:func:`connect_training_view`) and emits ``(system, user, assistant)``
triples or HuggingFace ``messages`` format depending on the trainer.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TrainingExample:
    """One PEFT-ready conditional generation example."""
    system: str        # persona prompt (deterministic)
    user: str          # last interlocutor utterance + zone context
    assistant: str     # target utterance (the persona's reply)
    persona_id: str
    run_id: str
    metadata: Mapping[str, object]  # tick, turn_index, mode, zone


def build_examples(
    rows: Iterable[Mapping[str, object]],
    *,
    persona_id: str,
    epoch_phase_filter: tuple[str, ...] = ("autonomous", "q_and_a"),
) -> list[TrainingExample]:
    """Convert raw_dialog rows to TrainingExample list.

    Args:
        rows: Iterator from :func:`connect_training_view().iter_rows`.
        persona_id: Filter to this persona's utterances as the assistant
            target. Other personas appear as user-side context.
        epoch_phase_filter: Only include rows with epoch_phase in this
            tuple. Default excludes EpochPhase.EVALUATION rows.

    Returns:
        List of TrainingExample, ordered by (run_id, tick, turn_index).
    """
```

### `src/erre_sandbox/training/dataset.py` (新設)

```python
"""HuggingFace ``datasets.Dataset`` adapter for PEFT SFTTrainer.

Wraps :func:`build_examples` output as a ``datasets.Dataset`` with the
columns SFTTrainer expects (``messages`` or ``text`` depending on
formatting_func). Tests use a stub Dataset to keep the heavy ``datasets``
import out of CI.
"""

from collections.abc import Sequence

from erre_sandbox.training.prompt_builder import TrainingExample


def to_hf_dataset(examples: Sequence[TrainingExample]):  # noqa: ANN201 — ds.Dataset return
    """Return ``datasets.Dataset`` formatted for SFTTrainer."""
```

### `src/erre_sandbox/training/train_kant_lora.py` (新設、CLI)

```python
"""CLI: train Kant LoRA adapter on G-GEAR (RTX 5060 Ti 16GB).

Run:
    uv run python -m erre_sandbox.training.train_kant_lora \
        --db <path-to-golden-baseline.duckdb> \
        --output-dir checkpoints/kant-r8-nf4-<date>

Reads raw_dialog via :func:`connect_training_view`, builds Kant training
examples, fine-tunes Qwen3-8B with QLoRA NF4 + rank=8 PEFT adapter, saves
the adapter as safetensors. The output is then loaded into SGLang via
:meth:`SGLangChatClient.load_adapter`.
"""
```

## 5. VRAM 予算試算 (RTX 5060 Ti 16GB)

| 項目 | VRAM |
|---|---|
| Qwen3-8B base, NF4 quantization | ~5.2GB |
| LoRA adapter (rank=8, all-proj target_modules) | ~50MB |
| Training gradient + optimizer state (PEFT QLoRA) | ~3.0-3.5GB |
| Activation memory (batch=1, seq=2048) | ~1.0GB |
| Buffer / fragmentation | ~0.5GB |
| **合計 (training)** | **~9.7-10.2GB** |
| **headroom (16GB - 10.2)** | **~5.8GB** |

**marginal**: training 中は OOM リスク低い (5.8GB headroom)。serving 時は base
+ 1-3 active adapters で ~5.5GB のみ、余裕。

**Codex で確認させる**:

- gradient_checkpointing による gradient 削減で headroom 改善できるか
- 8-bit LoRA (bitsandbytes) vs NF4 QLoRA の VRAM 差
- accumulation_steps を上げれば effective batch を維持できるか

## 6. Training data 利用可能量 (Phase 1 で確認済)

- **現状 (P3 calibration 段階)**: Kant pilot data は ~40-50 turn (LoRA training
  には不足)
- **P3 golden baseline 完了後**: 3 persona × 5 run × 500 turn = **7500 turn**
  のうち Kant 部分は ~2500 turn (`epoch_phase != EVALUATION` の autonomous +
  q_and_a)
- **2500 turn は LoRA spike として sufficient** (DB4 coverage 300/persona の
  ~8 倍、prior art も 2024 LoRA persona-conditioning literature で同程度)
- **本 PR では code path のみ起草**、実走は P3 完了 trigger で次セッション

## 7. Test plan (本 PR scope 外、次セッション以降の Phase H/I/J)

### `tests/test_inference/test_sglang_adapter.py` (新設、Phase H、6 件)

1. `test_sglang_chat_client_chat_round_trip` — httpx mock で chat round trip
2. `test_sglang_chat_client_load_adapter_idempotent` — load×2 で 2 回目 noop
3. `test_sglang_chat_client_unload_adapter_idempotent` — unload×2 で 2 回目 noop
4. `test_sglang_chat_client_list_adapters_returns_loaded` — load → list で
   adapter ref 含む
5. `test_sglang_chat_client_unavailable_error_on_500` — server 500 →
   `SGLangUnavailableError`
6. `test_sglang_chat_client_close_idempotent` — close×2 で 2 回目 noop

### `tests/test_training/test_prompt_builder.py` (新設、Phase I、4 件)

1. `test_build_examples_filters_evaluation_epoch` — `epoch_phase=evaluation`
   行 0 件
2. `test_build_examples_orders_by_tick_turn_index` — sort 確認
3. `test_build_examples_persona_assistant_target` — Kant のみ assistant、
   他 persona は user context
4. `test_build_examples_empty_raw_dialog_returns_empty` — boundary

### `tests/test_training/test_dataset.py` (新設、Phase I、2 件)

1. `test_to_hf_dataset_shape_matches_sft_trainer` — column 名 / 行数
2. `test_to_hf_dataset_seed_stable` — reproducibility

### G-GEAR 実走 phase (Phase J、P3 完了後)

- adapter swap latency p50 / p95 / p99 (target <500ms p95)
- N=3 同時 request throughput (req/s collapse なし)
- FSM regression (peripatos / chashitsu / zazen / shu_kata / ha_deviate /
  ri_create / deep_work / shallow 8 mode で adapter 経路 OK)
- training run time (`train_kant_lora.py` run、~2-4h on RTX 5060 Ti 16GB)

## 8. v1 で意図的に未解決にしている点 (`/reimagine` + Codex で challenge)

- **SGLang version pin**: v0.3 vs v0.4 vs v0.5 のどれが multi-LoRA stable か
  (Codex web search で changelog 確認)
- **adapter format conversion**: PEFT safetensors → SGLang `--lora-paths`
  受付形式の互換性 (undocumented なら vLLM swap)
- **training data minimum**: 2500 turn (P3 完了後 Kant 部分) で sufficient か、
  prior art 確認
- **gradient_checkpointing 採用可否**: VRAM 9.7-10.2GB を 7.5-8GB に下げる
  trade-off (training time +20-30%)
- **Mock-LoRA fallback** (戦略 C): data-blocked 時の代替案、infrastructure
  proof のみ早期実施
- **Multi-persona small batch** (戦略 D): Kant 単独 vs Kant+Nietzsche+Rikyū
  の trade-off (rank=4 で総量稼ぐ)
- **AWQ + LoRA early eval** (戦略 E): DB1 alternatives 1 を spike 内で前倒し
  検証
- **VRAM headroom margin**: 5.8GB は実用上 sufficient か (CUDA fragmentation /
  long-context generation の overhead 込み)

## 9. ADR alignment (絶対遵守)

| ADR | 制約 | v1 対応 |
|---|---|---|
| DB1 | QLoRA NF4 default | v1 採用 |
| DB2 | PEFT 暫定 | v1 採用、final は M9-C-adopt |
| DB3 | SGLang `--enable-lora` + `/load_lora_adapter` | v1 採用、>500ms latency で fallback fire |
| DB4 | dataset trigger 300/persona | v1 採用、Kant ~2500 turn は fire 可 (M9-C-adopt 範囲) |
| DB5/DB6 | raw_dialog vs metrics 物理分離、`epoch_phase != EVALUATION` filter | training/prompt_builder で filter 強制 |
| DB8 | adapter swap runbook は spike 完了後 | Phase J で起草 |
| DB10 | spike は non-authoritative | requirement.md / docstring に明示 |
| DB11 | individual_layer_enabled enforcement は別タスク | blockers.md に記録、本 spike では明示せず |
| 第3の道 ADR | bounded Kant spike on SGLang、M9-eval と並行 | 本タスク全体が該当 |

## 10. Out of scope (本タスク全体)

- LoRA 採用判定 (M9-C-adopt 範囲、DB9 quorum 通過必須)
- 3 persona 展開 (Nietzsche / Rikyū)、本 spike は Kant 1 のみ
- Tier C judge LLM (M9-eval P6 範囲)
- M9-eval P3 golden baseline 採取自体 (G-GEAR run1 calibration → run2-4、
  別タスク)
- Burrows reference corpus 整備 (Tier A 既存範囲、blockers.md defer)
- persona refactor / philosopher_seed (M10-A 範囲、認知深化 PR #144)
- DB11 contamination assert 実装 (`m9-individual-layer-schema-add` 別タスク)
- vLLM full migration 実装 (DB3 fallback fire 時のみ別タスク化)
- PEFT vs unsloth final 選定 (M9-C-adopt 範囲)

## 11. Effort estimate

### 本セッション (Plan + scaffold + Codex review まで)

| Sub-step | 推定 |
|---|---|
| Phase A: scaffold + requirement.md | 30min ✓ (本 phase 内) |
| Phase B: design-v1.md (本書) | 1h ✓ |
| Phase C: /reimagine v2 + comparison | 1h |
| Phase D: Codex review prompt + execution | 1.5h |
| Phase E: design-final + decisions.md ADR | 1h |
| Phase F: tasklist + blockers 整備 | 30min |
| **本セッション合計** | **~5.5h** |

### 次セッション以降 (実装 + 実走、P3 完了 trigger 後)

| Phase | 推定 |
|---|---|
| G: pyproject.toml [training] extras | 30min |
| H: sglang_adapter.py + tests | 2-3h |
| I: training/ module + prompt builder + dataset + train script + tests | 3-4h |
| J: G-GEAR 実走 (P3 完了後): training run + adapter load + latency 実測 | 4-6h |
| K: adapter swap runbook (DB8) + PR | 1h |
| **次セッション以降合計** | **~10-14h** (2-3 セッション) |
