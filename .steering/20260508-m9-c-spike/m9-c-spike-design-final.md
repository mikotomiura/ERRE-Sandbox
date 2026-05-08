# m9-c-spike — design final (Codex Verdict: ADOPT-WITH-CHANGES、HIGH 4 全反映)

> v3 hybrid を出発点に、Codex independent review (`codex-review-m9-c-spike.md`、
> 198K tok、HIGH 4 / MEDIUM 6 / LOW 3) を全反映した最終 design。
>
> Closing note (Codex 引用):「Adopt v3 hybrid, not v1 or v2, but only after the
> changes above. Phase α is valuable as an early infrastructure proof; Phase β
> should stay bounded to Kant rank=8 to preserve the M9-B third-option ADR.
> The main correction is to demote mock latency from decisive DB3 evidence to
> a diagnostic unless it proves hard API/format failure.」

## 0. Mission (不変)

Kant 1 persona の bounded LoRA spike (M9-B 第3の道 ADR、PR #127)。
non-authoritative、評価系構築中の LoRA 学習・adapter swap・runtime 技術リスク
早期検出が目的。

5 deliverable:

1. SGLang LoRA endpoint 動作確認 (API 失敗/format 拒否で即 fallback fire)
2. **adapter swap latency** 実測 (cold/warm/pinned/unpinned/no-LoRA baseline と
   比較した repeated measurement、HIGH-2)
3. **N=3 同時 request throughput** 実測 (SGLang `bench_serving` harness、
   no-LoRA / single-LoRA baseline と比較、HIGH-4)
4. M5 resonance / ERRE FSM regression 確認 (SGLang LoRA 経路で破綻なし)
5. adapter swap runbook (DB8) 起草 (本 spike 完了後、実測値込み)

## 1. HIGH-1 反映 — `list_adapters()` API 設計修正

### 確定事項

- **削除**: `SGLangChatClient.list_adapters() -> list[LoRAAdapterRef]` (current
  SGLang docs に該当 endpoint なし、HIGH-1)
- **代替**: 内部 client-side state + reconciliation through load/unload
  response payloads。`SGLangChatClient` が `_loaded: dict[str, LoRAAdapterRef]`
  を保持し、`load_adapter` / `unload_adapter` の response で update
- **Version pin**: `sglang==0.5.10.post1` (PyPI 2026-04-08 latest stable、
  HIGH-1 / MEDIUM-1 反映)。"v0.3+ stable" の vague な表現は破棄
- **API field 名**: SGLang serializes は `lora_name` / `lora_path` / `pinned`
  に統一 (LOW-3)。`LoRAAdapterRef.adapter_name` は internal ERRE naming で
  serialization 時に `lora_name` にマップ

### API 修正

```python
@dataclass(frozen=True, slots=True)
class LoRAAdapterRef:
    """Identifier for a loaded LoRA adapter (internal ERRE naming)."""
    adapter_name: str        # serializes to SGLang `lora_name`
    weight_path: str         # serializes to SGLang `lora_path`
    base_model: str          # ERRE-side metadata
    rank: int
    pinned: bool = False     # SGLang `pinned` field


class SGLangChatClient:
    def __init__(self, *, base_url: str, default_model: str,
                 sglang_version: str = "0.5.10.post1",
                 httpx_client: httpx.AsyncClient | None = None) -> None:
        self._loaded: dict[str, LoRAAdapterRef] = {}
        ...

    async def load_adapter(self, ref: LoRAAdapterRef) -> None:
        """POST /load_lora_adapter; update self._loaded on 2xx."""
        # serializes ref → {"lora_name": ref.adapter_name, "lora_path": ref.weight_path,
        #                    "pinned": ref.pinned}

    async def unload_adapter(self, name: str) -> None:
        """POST /unload_lora_adapter; remove from self._loaded on 2xx."""

    @property
    def loaded_adapters(self) -> tuple[LoRAAdapterRef, ...]:
        """Client-side known set; not a server query."""
        return tuple(self._loaded.values())

    # NOTE: list_adapters() removed — no documented SGLang endpoint as of
    # 0.5.10.post1. Client maintains state via load/unload responses.
```

## 2. HIGH-2 反映 — Mock-LoRA latency は diagnostic、DB3 fallback decisive ではない

### 確定事項 (Codex HIGH-2 quotation)

> Change the DB3 trigger rule: API failure or FSM regression can fire
> immediately; latency fallback requires repeated local measurements across
> cold load, warm reload, pinned, unpinned, and no-LoRA baselines, using a
> PEFT no-op adapter with the same rank/target_modules as the intended Kant
> adapter.

### DB3 fallback fire 条件 (HIGH-2 反映で再定義)

- **即時 fire (mock-LoRA でも fire)**:
  - SGLang `--enable-lora` 起動失敗
  - `/load_lora_adapter` が PEFT format 拒否 (HTTP 4xx/5xx)
  - M5 resonance / ERRE FSM が SGLang LoRA 経路で regression
- **diagnostic 扱い (real Kant adapter で confirmation 必要)**:
  - adapter swap latency >500ms (cold/warm/pinned/unpinned/no-LoRA baseline と
    比較、real adapter で確認後 fire 判断)
  - N=3 throughput collapse の閾値未達 (HIGH-4 で再定義)

### Phase α (Mock) の役割再定義

- ✅ API proof (load/unload mechanism、format validation)
- ✅ FSM route smoke testing (resonance / ERRE FSM 経路の adapter 透過確認)
- ✅ adapter format validation (PEFT directory 直接 load test、HIGH-1 / MEDIUM-2)
- ❌ DB3 fallback decisive evidence (real adapter で再測定必須)

## 3. HIGH-3 反映 — Training sufficiency は realized example 数 + contamination assertion

### 確定事項 (HIGH-3 quotation)

> v3 should define a Phase β gate on `len(build_examples(... persona_id="kant"))`,
> plus a hard fail if `epoch_phase == evaluation` or `individual_layer_enabled`
> is present and true. If `individual_layer_enabled` is absent because DB11
> follow-up is not merged, Phase β must record that as a blocker, not silently
> proceed.

### Phase β 着手 gate (修正)

```python
# src/erre_sandbox/training/train_kant_lora.py 入口
def assert_phase_beta_ready(
    db_path: Path,
    persona_id: str = "kant",
    *,
    min_examples: int,  # CS ADR で literature-based に確定 (≥1000 提案)
    individual_layer_enabled_required: bool = True,
) -> int:
    """Hard-fail gate before Phase β real training (HIGH-3)."""
    relation = connect_training_view(db_path)
    raw_rows = list(relation.iter_rows())

    # epoch_phase=evaluation の sentinel hard fail
    eval_rows = [r for r in raw_rows if r.get("epoch_phase") == "evaluation"]
    if eval_rows:
        raise EvaluationContaminationError(
            f"connect_training_view returned {len(eval_rows)} evaluation rows;"
            " training must abort"
        )

    # individual_layer_enabled column の存在確認 (DB11 follow-up gate)
    if individual_layer_enabled_required:
        if "individual_layer_enabled" not in relation.columns:
            raise BlockerNotResolvedError(
                "ALLOWED_RAW_DIALOG_KEYS does not include"
                " 'individual_layer_enabled' — DB11 enforcement is blocked on"
                " m9-individual-layer-schema-add task. Phase β cannot proceed."
            )
        ind_rows = [r for r in raw_rows if r.get("individual_layer_enabled") is True]
        if ind_rows:
            raise EvaluationContaminationError(
                f"{len(ind_rows)} rows have individual_layer_enabled=True;"
                " training must abort (DB11)"
            )

    examples = build_examples(raw_rows, persona_id=persona_id)
    if len(examples) < min_examples:
        raise InsufficientTrainingDataError(
            f"only {len(examples)} usable Kant assistant-target examples;"
            f" Phase β requires ≥{min_examples}"
        )
    return len(examples)
```

### 修正含意

- "~2500 turn" の表現は **estimate のみ**、Phase β 着手前に
  `len(build_examples(persona_id="kant"))` で **realized example 数** を測る
- `individual_layer_enabled` field が `ALLOWED_RAW_DIALOG_KEYS` に未追加の現状
  は **blocker**、silent proceed 禁止 (`m9-individual-layer-schema-add` の merge
  待ち)
- `min_examples` 閾値は **literature-based に決める** (Codex 推奨 BIG5-CHAT
  100k は overshoot、P-Tailor / Anthropic persona vector を引いて ~1000 を
  CS-3 ADR で justify)

## 4. HIGH-4 反映 — N=3 collapse は SGLang `bench_serving` で形式定義

### 確定事項 (HIGH-4 quotation)

> Define collapse as a comparison against no-LoRA and single-LoRA baselines:
> same prompts, same sampling, `--max-loras-per-batch 3`, three concurrent
> requests pinned to three adapter names, `--max-concurrency 3`, plus
> p50/p95/p99 TTFT, ITL, e2e latency, output tokens/s, HTTP error rate, and
> queue wait if available. A reasonable spike trigger is either p95 e2e > 2x
> single-LoRA baseline, output tok/s < 70% baseline, any adapter-misrouting,
> or any request timeout.

### N=3 benchmark protocol (CS-7 ADR で確定)

| 軸 | 値 |
|---|---|
| Tool | SGLang `bench_serving` harness |
| baselines | no-LoRA / single-LoRA Kant only / N=3 multi-LoRA (Kant + 2 mock) |
| 同時 concurrency | 3 (`--max-concurrency 3`) |
| LoRA constraints | `--max-loras-per-batch 3 --max-lora-rank 8 --max-loaded-loras 3` |
| sampling | identical 3 conditions、`--seed 0` 等 deterministic |
| metrics | TTFT p50/p95/p99 / ITL / e2e latency / output tok/s / HTTP error rate / queue wait |
| **collapse trigger (any one of)** | p95 e2e > 2x single-LoRA baseline、output tok/s < 70% baseline、adapter-misrouting (Kant prompt → Nietzsche adapter response detected by sentinel)、request timeout |

mock-LoRA で観測された collapse は **diagnostic**、real Kant rank=8 で
confirmation 後に DB3 fallback fire 判断 (HIGH-2 整合)。

## 5. MEDIUM 反映

### MEDIUM-1: SGLang version pin

- `sglang==0.5.10.post1` (PyPI 2026-04-08 latest)
- CUDA build: G-GEAR の RTX 5060 Ti 16GB は CUDA 12.x、SGLang 0.5.10.post1 の
  公式 wheel が CUDA 12.4 / 12.6 でビルドされている前提
- launch args の CS ADR (CS-1) に固定:
  `python -m sglang.launch_server --model qwen/Qwen3-8B
   --enable-lora --max-loras-per-batch 3 --max-lora-rank 8
   --max-loaded-loras 3 --port 30000`

### MEDIUM-2: PEFT directory validation 先行

- `peft.LoraConfig` + `model.save_pretrained(<path>)` が emit する
  `adapter_config.json` + `adapter_model.safetensors` を SGLang に
  直接 load 試験
- conversion script は **直接 load 失敗時のみ起草** (premature optimization 禁止)
- Phase α の Phase A1 で direct load test (mock-LoRA で confirm)

### MEDIUM-3: VRAM budget explicit

- `gradient_checkpointing=True` 強制
- `bnb_4bit_use_double_quant=True` (nested quantization、HIGH 反映)
- `batch_size=1`, `gradient_accumulation_steps=8`, `seq_length=2048` を
  initial config (CS-4 で確定)
- `nvidia-smi` 採取と peak memory logging を training entry point に組込
- VRAM 計画 (再試算):
  - Qwen3-8B NF4 + double quant: ~5.0GB
  - LoRA rank=8 adapter: ~50MB
  - gradient_checkpointing で gradient 削減: ~1.5GB
  - optimizer state (PEFT only LoRA params): ~0.2GB
  - activation: ~1.5GB (seq=2048, batch=1)
  - buffer: ~0.5GB
  - **合計**: **~8.7GB**、headroom **~7.3GB** (v1 estimate より広い)

### MEDIUM-4: rank=8 は continuity hypothesis

- "rank=8 が universally adequate" の主張を design から削除
- ADR (CS-5) に「rank=8 は M9-C-adopt 統一 spike との continuity hypothesis、
  rank sweep は M9-C-adopt 範囲」と明記
- LoRA Land / P-Tailor は rank=4-16 で persona shaping 報告、universal best
  rank なし

### MEDIUM-5: vLLM fallback path 更新

- DB3 fallback ADR (本 spike scope 外、別タスク fire 時起票) で vLLM **0.15+**
  multi-LoRA を比較対象に
- 環境変数 `VLLM_ALLOW_RUNTIME_LORA_UPDATING=True` の security risk warning
  (trusted environment only) を docstring 明示
- 旧認識 (vLLM v0.6+ baseline) は破棄

### MEDIUM-6: steering files populate

- `decisions.md` に CS-1〜CS-9 ADR、各 5 要素
- `tasklist.md` に Phase G-K (実装 phase) sub-items 列挙
- `blockers.md` に dependency + defer 記録
- `design.md` は本 design-final.md の summary を貼付して populate

## 6. LOW 反映

### LOW-1: build_mock_lora.py refusal guard + metadata

```python
# tools/spike/build_mock_lora.py (新設、Phase α)
"""Build a deterministic no-op PEFT LoRA adapter for SGLang infrastructure proof.

Output safetensors carries metadata sentinel ``mock=true`` so production
adapter loaders can reject it. Refusal guard rejects writes under ``src/``
or any path containing ``checkpoint`` or ``production``.

Reads no model weights — generates an identity-transform LoRA per HF PEFT
default initialization (B initialized to 0, A from kaiming uniform; result
is no-op until trained, LOW-2).
"""

OUTPUT_METADATA: dict[str, str] = {
    "mock": "true",
    "base_model": "qwen/Qwen3-8B",
    "rank": "8",
    "target_modules": "q_proj,k_proj,v_proj,o_proj",
    "init_lora_weights": "default",  # PEFT default (no-op identity)
    "git_sha": "<runtime>",
}

_FORBIDDEN_PATH_PREFIXES = ("src/", "src\\")
_FORBIDDEN_PATH_SUBSTRINGS = ("checkpoint", "production")


def build_mock_lora(output_dir: Path) -> Path:
    if any(str(output_dir).startswith(p) for p in _FORBIDDEN_PATH_PREFIXES):
        raise ValueError(f"refusal guard: cannot write under src/")
    if any(s in str(output_dir).lower() for s in _FORBIDDEN_PATH_SUBSTRINGS):
        raise ValueError(f"refusal guard: cannot write to production paths")
    ...
```

### LOW-2: PEFT default no-op initialization

- mock-LoRA は **PEFT default `init_lora_weights="default"`** を採用
  (B=0 で identity transform、Kant adapter と base model 出力は同一)
- random A/B は FSM smoke test を confuse する (Kant prompt で nonsense 出力 →
  M5 resonance / ERRE FSM regression false positive リスク)

### LOW-3: SGLang naming convention

- `LoRAAdapterRef.adapter_name` → SGLang `lora_name` (serialization)
- `LoRAAdapterRef.weight_path` → SGLang `lora_path`
- `LoRAAdapterRef.pinned` → SGLang `pinned`
- internal ERRE 側は ERRE-style naming 維持、boundary で field rename

## 7. 最終 commitment matrix (v3 → final)

| 項目 | v3 案 | final (Codex 反映後) |
|---|---|---|
| Phase 構造 | α (mock) + β (real) | 同 (HIGH-2 で α latency demote 済) |
| Spike persona | Kant 1 | 不変 |
| Adapter rank | rank=8 | 不変 (continuity hypothesis、MEDIUM-4) |
| SGLang version | "v0.3+" vague | **`sglang==0.5.10.post1` pin** (HIGH-1 / MEDIUM-1) |
| `list_adapters()` API | あり | **削除、internal state + load/unload reconciliation** (HIGH-1) |
| Mock-LoRA init | random or HF hub borrow | **PEFT default no-op identity** (LOW-2) |
| Mock-LoRA isolation | `tools/spike/` | 同 + **refusal guard + metadata sentinel** (LOW-1) |
| DB3 fallback fire (latency) | mock 単独で可 | **real adapter で confirmation 必須** (HIGH-2) |
| Training data minimum | "~2500 turn" estimate | **`len(build_examples(...))` realized + literature `min_examples`** (HIGH-3) |
| `individual_layer_enabled` 取扱 | 明示せず | **blocker hard-fail、silent proceed 禁止** (HIGH-3) |
| N=3 collapse 検出 | "no collapse" | **SGLang `bench_serving` + 4 trigger condition** (HIGH-4) |
| VRAM 予算 | 9.7-10.2GB headroom 5.8GB | **gradient_checkpointing + nested quant + memory logging で 8.7GB headroom 7.3GB** (MEDIUM-3) |
| PEFT format 検証 | 自前 conversion 想定 | **PEFT directory directly 試験、conversion は失敗時のみ** (MEDIUM-2) |
| rank adequacy claim | rank=8 sufficient | **continuity hypothesis のみ、rank sweep は M9-C-adopt** (MEDIUM-4) |
| vLLM fallback baseline | v0.6+ | **v0.15+ + `VLLM_ALLOW_RUNTIME_LORA_UPDATING` security warn** (MEDIUM-5) |
| API field naming | ERRE internal | **`lora_name`/`lora_path`/`pinned` SGLang naming** (LOW-3) |

## 8. 新規 ADR (`decisions.md` 追記対象、CS-1〜CS-9)

各 ADR は 5 要素 (決定 / 根拠 / 棄却 / 影響 / re-open 条件) で詳述:

- **CS-1**: SGLang version pin = `sglang==0.5.10.post1`、launch args 固定 (HIGH-1 / MEDIUM-1)
- **CS-2**: SGLang adapter API は load/unload + internal client-state、`list_adapters()` は無 (HIGH-1)
- **CS-3**: Phase β 着手 gate = realized `min_examples` literature-based + contamination assertion (HIGH-3)
- **CS-4**: VRAM budget = `gradient_checkpointing=True` + double quant + batch=1 + seq=2048 + memory logging (MEDIUM-3)
- **CS-5**: rank=8 は continuity hypothesis、universal adequacy 主張せず (MEDIUM-4)
- **CS-6**: PEFT directory direct load 試験先行、conversion 失敗時のみ自前 script (MEDIUM-2)
- **CS-7**: N=3 collapse 検出 = SGLang `bench_serving` + 4 trigger condition (HIGH-4)
- **CS-8**: DB3 fallback trigger は API failure / FSM regression 即時、latency は real adapter confirmation 必須 (HIGH-2)
- **CS-9**: Mock-LoRA は PEFT default no-op + refusal guard + metadata sentinel + `tools/spike/` 隔離 (LOW-1 / LOW-2 / LOW-3)

## 9. tasklist.md 更新対象 (Phase G-K)

- Phase G: pyproject.toml `[training]` extra 追加 (peft / transformers /
  datasets / accelerate / bitsandbytes、SGLang は `[inference]` 既存に依存)
- Phase H: `sglang_adapter.py` 新設 + tests (mock httpx、6 unit + 1 integration)
- Phase I: `training/` module + `prompt_builder.py` + `dataset.py` +
  `train_kant_lora.py` + `assert_phase_beta_ready()` gate + tests (10-12 件)
- Phase J: `tools/spike/build_mock_lora.py` + refusal guard tests (4 件)
- Phase K α: G-GEAR mock-LoRA infrastructure proof (data 不要、
  immediate execution after Phase G-J merge):
  - SGLang launch、mock-LoRA load/unload smoke test
  - PEFT format direct load validation
  - FSM regression smoke test (M5 resonance / ERRE FSM 経路)
  - **DB3 fallback fire 判断 (API failure / format reject / FSM regression
    only、latency は diagnostic)**
- Phase K β: G-GEAR real Kant training (P3 完了 + DB11 follow-up merge trigger):
  - `assert_phase_beta_ready()` gate 通過確認
  - Kant rank=8 PEFT QLoRA NF4 train run (実走 ~2-4h)
  - SGLang `/load_lora_adapter` で実 Kant adapter load
  - SGLang `bench_serving` で N=3 throughput 実測 (HIGH-4 protocol)
  - cold/warm/pinned/unpinned/no-LoRA baseline と adapter swap latency 比較
  - **DB3 fallback fire 判断 (latency real confirmation)**
- Phase L: adapter swap runbook (DB8) 起草 + `decisions.md` CS-N に実測値反映
  + PR 作成

## 10. 新規 blockers.md 記録対象

### Hard blockers (Phase β 着手不可)

- **`m9-individual-layer-schema-add`**: `ALLOWED_RAW_DIALOG_KEYS` に
  `individual_layer_enabled` 追加 + training-view 入口 assert + grep gate。
  本タスクは別 PR、未 merge なら Phase β `assert_phase_beta_ready()` で
  raise (HIGH-3)
- **M9-eval P3 golden baseline 採取完了**: G-GEAR run1 calibration → run2-4
  で 3 persona × 5 run × 500 turn 採取、Kant 部分 ~2500 turn (estimate) を
  Phase β training data に使用 (HIGH-3 で realized example 数で再判定)

### Soft blockers (Phase α は実行可能、Phase β で要確認)

- **SGLang 0.5.10.post1 G-GEAR install**: CUDA 12.x wheel 入手、
  `--enable-lora` 起動確認 (Phase K α 内で先行検証)
- **VRAM 予算実測**: G-GEAR 上で `gradient_checkpointing=True` +
  double quant + batch=1 + seq=2048 で peak memory が 8.7GB に収まるか
  (Phase K β 内で実測、超過時は CS-4 ADR 修正)
- **PEFT format SGLang 受付**: `peft.save_pretrained()` 出力を直接 load
  test、失敗時は conversion script 起草 (Phase K α 内、MEDIUM-2)

## 11. effort estimate (final)

### 本セッション (Plan + scaffold + Codex review)

| Phase | 推定 | status |
|---|---|---|
| A: scaffold + requirement.md | 30min | ✓ |
| B: design-v1.md | 1h | ✓ |
| C: /reimagine v2 + comparison.md | 1h | ✓ |
| D: Codex review prompt + execution + 反映 | 1.5h | ✓ |
| E: design-final + decisions.md ADR | 1.5h | 進行中 |
| F: tasklist + blockers 整備 | 30min | next |
| **本セッション合計** | **~6h** (Codex 反映で +0.5h vs plan) | |

### 次セッション以降 (実装 + 実走、P3 完了 trigger 後)

| Phase | 推定 |
|---|---|
| G: pyproject.toml [training] extras | 30min |
| H: sglang_adapter.py + tests (HIGH-1 反映で list_adapters 削除、internal state) | 2h |
| I: training/ module + prompt builder + dataset + train script + Phase β gate + tests | 4h (HIGH-3 反映で gate logic 追加) |
| J: tools/spike/build_mock_lora.py (LOW-1/-2 反映で refusal guard + no-op init) + tests | 1h |
| K α: G-GEAR mock-LoRA infrastructure proof (data 不要、即実行) | 2h |
| K β: G-GEAR real Kant training (P3 + DB11 follow-up trigger): training run + adapter load + bench_serving + cold/warm/pinned baseline 比較 (HIGH-2 / HIGH-4) | 6h |
| L: adapter swap runbook (DB8) + 実測値反映 + PR | 1h |
| **次セッション以降合計** | **~16-17h** (3-4 セッション、Codex HIGH-2/-3/-4 反映で +3-4h vs v3 plan) |

## 12. /clear hand-off note

context が 30%↑なら `/clear`、次セッション resume 時は:

1. `m9-c-spike-design-final.md` (本書) を Read
2. `decisions.md` CS-1〜CS-9 を Read
3. `codex-review-m9-c-spike.md` の HIGH 4 + MEDIUM 6 + LOW 3 を verbatim 確認
4. `tasklist.md` Phase G-L sub-items を確認
5. branch `feat/m9-c-spike` 作成 → Phase G-J 実装着手
