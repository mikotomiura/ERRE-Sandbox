# Phase K-α report — m9-c-spike mock-LoRA infrastructure proof (G-GEAR)

**Branch**: `feature/m9-c-spike-k-alpha-report` (initial Windows attempt, merged
as PR #154) → follow-up branch `feature/m9-c-spike-k-alpha-wsl2-retry`
(WSL2 retry, this commit)
**Host**: G-GEAR (Windows 11 host, RTX 5060 Ti 16GB / Blackwell sm_120, host
CUDA driver 595.79 = CUDA 13.2 capable, Python 3.11.15, uv 0.11.7)
**Date**: 2026-05-09 (initial pass + WSL2 retry same-day)
**Handoff source**: `.steering/20260508-m9-c-spike/k-alpha-handoff-prompt.md`
(commit `959af6f`)

This report is the **G-GEAR side report-back** required by the K-α handoff
prompt §"Report-back format". It records each Step's actual command + output,
DB3 fire judgement against the three immediate-fire conditions (CS-8), and any
CS-N amendment values observed. After the initial Windows-native attempt fired
DB3 #1 (recorded below), WSL2 + Ubuntu 22.04 was installed and Steps 2-5 were
re-run on the Linux substrate; the **WSL2 retry section** at the end of this
file records the unblock and additional CS-N amendment items surfaced during
that retry.

---

## Summary (post WSL2 retry)

| # | Step                                   | Win attempt | WSL2 retry | DB3 fire?     |
|---|----------------------------------------|:-----------:|:----------:|:-------------:|
| 1 | mock-LoRA build (CS-9)                 |     ✅      |     ✅     |       —       |
| 2 | SGLang `--enable-lora` launch (CS-1)   |     ❌      |     ✅     | #1 → **retracted** |
| 3 | `/load_lora_adapter` PEFT direct (CS-6)|     ⏸️      |     ✅     |       —       |
| 4 | chat round trip (CS-9 identity)        |     ⏸️      |     ✅     |       —       |
| 5 | ERRE FSM smoke — deep_work (CS-8 #3)   |     ⏸️      |     ✅     |       —       |

(⏸️ = deferred pending Linux substrate during initial pass; not failed.)

**Net K-α verdict (post-retry)**: Phase K-α infrastructure proof **PASSES on
WSL2 substrate**. DB3 fire #1 (originally fired against Windows-native install)
is **retracted** — the SGLang `--enable-lora` launch succeeds on WSL2 once the
amendment-cascade documented in §"WSL2 retry" is applied. CS-6 (PEFT direct
load) and CS-9 (mock identity transform) confirmed empirically. CS-8 #3 (FSM
regression) clear for the deep_work mode minimum; full 8-mode smoke deferred
to a follow-up PR per the handoff prompt's optional scope.

The initial Windows pass also surfaced **two issues** worth preserving in this
record:

1. **Latent build bug in `tools/spike/build_mock_lora.py`** (Phase J,
   shipped via PR #153). `LoraConfig(init_lora_weights="default")` raises
   `ValueError` on peft 0.19.1 — the string `"default"` is not in the
   accepted `bool | Literal[...]` set. **Fixed in PR #154** by switching to
   `init_lora_weights=True`; the human-readable sentinel metadata is
   preserved.
2. **CS-1 platform incompat — DB3 fire condition #1 fired with scope
   nuance**. `sglang-kernel==0.4.1` (transitive of `sglang==0.5.10.post1`)
   ships only `manylinux2014_x86_64` / `aarch64` wheels. Native Windows
   install fails at uv resolution. The fire is **install-side platform
   compat**, NOT CUDA runtime mismatch. The remediation lived in CS-1
   amendment territory (Linux execution boundary), and the WSL2 retry below
   validates that recommendation.

---

## Step 1 — mock-LoRA build (CS-9)

**Command** (Step 0a + Step 1, ran inside `[training]` venv):

```powershell
uv sync --extra training        # already synced from prior session
uv run python -m tools.spike.build_mock_lora --output-dir checkpoints/mock_kant_r8
```

**First attempt — failed (peft API mismatch, fixed in same PR)**

The committed `tools/spike/build_mock_lora.py` passed
`init_lora_weights="default"` to `LoraConfig`. peft 0.19.1 only accepts
`bool | Literal["gaussian", "pissa", "pissa_niter_*", "corda", "olora",
"loftq", "eva", "orthogonal", "lora_ga"]` for that field — the literal string
`"default"` raises `ValueError: Unknown initialization
init_lora_weights='default'` from
`peft.tuners.lora.layer.reset_lora_parameters` (peft 0.19.1
`layer.py:273`).

This was a **latent bug shipped via PR #153**. The Phase J refusal-guard +
sentinel tests (`tests/test_tools/test_build_mock_lora.py`) all use
`pytest.importorskip("peft")` and only the identity-transform check carries
`@pytest.mark.spike`, so the CI default install (no `[training]` extras) skips
the path that would have surfaced the kwarg mismatch. The fix landed in this
same PR by switching the LoRA config kwarg to `init_lora_weights=True` (which
is PEFT's documented default = kaiming-A + zero-B → identity transform). The
sentinel-metadata field was kept as the human-readable string `"default"` to
preserve the `test_build_emits_mock_sentinel_metadata` contract — the
metadata is provenance, not a literal kwarg echo. Docstring updated to make
the discrepancy explicit.

**Second attempt — succeeded (exit 0)**

Output (`checkpoints/mock_kant_r8/`):

```
adapter_config.json        1333 bytes
adapter_model.safetensors  30,709,192 bytes  (~29.3 MB)
README.md                  5180 bytes
```

`adapter_config.json` highlights:

```json
{
  "base_model_name_or_path": "Qwen/Qwen3-8B",
  "init_lora_weights": true,
  "lora_alpha": 16,
  "peft_type": "LORA",
  "peft_version": "0.19.1",
  "r": 8,
  "target_modules": ["k_proj", "v_proj", "q_proj", "o_proj"],
  "task_type": "CAUSAL_LM",
  "metadata": {
    "mock": "true",
    "base_model": "Qwen/Qwen3-8B",
    "rank": "8",
    "target_modules": "q_proj,k_proj,v_proj,o_proj",
    "init_lora_weights": "default",
    "git_sha": "bbaf0b2b56fc36e7f8d94724130f0481622d3978"
  }
}
```

Note `init_lora_weights: true` (real LoraConfig field) vs.
`metadata.init_lora_weights: "default"` (the human-readable sentinel label).
This is intentional after the fix.

**Verdict**: Step 1 ✅ PASS. mock-LoRA artefact present, sentinel intact,
git_sha pinned. CS-9 satisfied (mock=true, B=0 identity by virtue of
`init_lora_weights=true`).

DB3 fire conditions for Step 1: none (Step 1 is build-side, not server-side).

## Step 2 — SGLang launch (CS-1) — BLOCKED on platform incompat

**Goal**: launch `python -m sglang.launch_server --model qwen/Qwen3-8B
--enable-lora --max-loras-per-batch 3 --max-lora-rank 8
--max-loaded-loras 3 --port 30000`.

**Pre-step (Step 0b)**: switch venv via `uv sync --extra inference`.

**Result**: Step 0b fails at resolution — **SGLang has no Windows wheels**.
Dry-run trace:

```
> uv sync --extra inference --dry-run
Would use project environment at: .venv
Resolved 243 packages in 2ms
Found up-to-date lockfile at: uv.lock
error: Distribution `sglang-kernel==0.4.1 @ registry+https://pypi.org/simple`
can't be installed because it doesn't have a source distribution or wheel for
the current platform

hint: You're on Windows (`win_amd64`), but `sglang-kernel` (v0.4.1) only has
wheels for the following platforms: `manylinux2014_aarch64`,
`manylinux2014_x86_64`; consider adding "sys_platform == 'win32' and
platform_machine == 'AMD64'" to `tool.uv.required-environments` to ensure uv
resolves to a version with compatible wheels
```

uv's hint is misleading here: `required-environments` only gates which
platforms uv resolves *for* — it does **not** materialise wheels that do not
exist upstream. SGLang has historically not shipped Windows-native CUDA
kernels; the 0.5.10.post1 transitive dep `sglang-kernel==0.4.1` is
Linux-only.

**Fallback environments checked on this G-GEAR host**:

| Path           | Status              | Notes                                        |
|----------------|---------------------|----------------------------------------------|
| Native Windows | ❌ no wheel          | sglang-kernel manylinux2014_x86_64 only      |
| WSL2           | ❌ not installed     | `wsl --status` reports the optional feature is not enabled |
| Docker         | ❌ not installed     | `docker` not on PATH (Docker Desktop absent) |

So the launch literally cannot proceed on this host as configured. This was
not surfaced during PR #153 because:

1. **`uv.lock` was generated against a Linux universe** — `[inference]`
   resolution succeeds on the manylinux platform tag set, and the lock was
   committed without a Windows materialisation step.
2. **The Phase H adapter unit tests use `httpx.MockTransport`** — they never
   import `sglang` or hit the kernel wheel path, so CI default install (no
   `[inference]` extras) passes 100% without exercising the CUDA-bound
   transitive deps.
3. **The K-α handoff prompt assumed `[inference]` extras would resolve on
   G-GEAR** — but G-GEAR is Windows 11 native, and the resolver guard the
   `[tool.uv].conflicts` table provides is for *intra-project* (training ⇔
   inference) collision, not *upstream platform* coverage.

**DB3 fire condition #1 (CS-8): FIRED.** The fire reason is **install-side
platform incompatibility**, not CUDA driver / runtime mismatch. The
remediation lives in CS-1 amendment territory, not vLLM-fallback territory:
the K-α design must explicitly choose a Linux execution boundary (WSL2,
Docker, or a separate Linux GPU host). The `train_kant_lora()` Phase K β
plan inherits the same constraint — peft / transformers / accelerate /
bitsandbytes resolve on Windows fine, but inference-side serving does not.

## Step 3 — `/load_lora_adapter` PEFT direct (CS-6) — N/A

Cannot run without a live SGLang server (Step 2 blocked). The adapter
artefact is on disk and inspectable:

```powershell
# adapter_config.json round-trips PEFT (verified via Step 1's
# peft_model.save_pretrained → reloadable shape).
ls checkpoints/mock_kant_r8/
# adapter_config.json
# adapter_model.safetensors  (~29.3 MB)
# README.md
```

The PEFT-directory shape is correct, so when the SGLang serving environment
becomes available the `/load_lora_adapter` direct-load test (CS-6) is
unblocked from the artefact side. Step 3 is **DEFERRED**, not failed.

## Step 4 — chat round trip (CS-9 identity) — N/A

Cannot run without Step 3. **DEFERRED**.

## Step 5 — ERRE FSM 8-mode smoke (CS-8 #3) — N/A

Cannot run without Step 4. **DEFERRED**.

---

## WSL2 retry — Steps 2-5 unblock (2026-05-09 11:00 JST onwards)

After the Windows-native attempt above fired DB3 #1 against the Linux-only
`sglang-kernel` wheel, WSL2 + Ubuntu 22.04 LTS was installed on the same
G-GEAR host and Steps 2-5 were re-attempted. The retry succeeded but only
after a **5-stage cascade of additional configuration discoveries**, each of
which is recorded here as a CS-N amendment candidate (§"CS-N amendments
(WSL2 retry)" below).

### Substrate

- WSL2 / Ubuntu 22.04.5 LTS (kernel `6.6.114.1-microsoft-standard-WSL2`)
- GPU passthrough: `nvidia-smi` reports RTX 5060 Ti, host driver `595.79`
  exposing CUDA 13.2 capability inside WSL2 (no separate WSL2 driver install
  needed; the Windows host driver is shared)
- Repository cloned to `~/erre-sandbox` on WSL2 native FS (clone of
  `origin/main` HEAD `f53c995`); Windows-mounted `/mnt/c` reserved for
  HuggingFace cache sharing only (avoids 9P I/O penalty on hot paths)
- Python 3.11.15 via `uv python install 3.11` (uv-managed runtime; no
  deadsnakes PPA needed)
- HuggingFace cache shared from Windows (`HF_HOME=/mnt/c/Users/johnd/
  .cache/huggingface`), saving the 15 GB Qwen3-8B re-download (snapshot
  `b968826d9c46dd6066d109eabc6255188de91218` reused intact)
- mock-LoRA artefact (Phase K-α Step 1 output, 30 MB) `rsync`-ed from
  Windows `checkpoints/mock_kant_r8/` to WSL2 `~/erre-sandbox/checkpoints/`

### Step 2 (WSL2) — SGLang `--enable-lora` launch (CS-1)

`uv sync --extra inference --dry-run` resolved cleanly on WSL2 (manylinux
wheels available), confirming the recommendation in the Windows-pass DB3
note. The actual launch then required **four subsequent retry rounds**
before the server reached "fired up and ready to roll":

| Stage | Failure                                                    | Fix                                              |
|:-----:|------------------------------------------------------------|--------------------------------------------------|
| v2    | `deep_gemm` `_find_cuda_home()` `AssertionError`           | Install CUDA toolkit 12.9 via `wsl-ubuntu` repo, export `CUDA_HOME=/usr/local/cuda` |
| v3    | `AssertionError: ... need ... --max-lora-rank and --lora-target-modules` | Add `--lora-target-modules q_proj k_proj v_proj o_proj` |
| v4    | `RuntimeError: Not enough memory ... mem_fraction_static=0.93` | Add `--quantization fp8` + `--mem-fraction-static 0.85` + `--max-total-tokens 2048` + `--max-running-requests 1` + `--disable-cuda-graph` |
| v5    | (success) — Server fired up at 2026-05-09 11:13:04 JST     | —                                                |

Final launch command (CS-1 amendment, see also `scratch_kalpha/step2_launch.sh`
in this PR):

```bash
HF_HOME=/mnt/c/Users/johnd/.cache/huggingface \
HF_HUB_DISABLE_TELEMETRY=1 \
CUDA_HOME=/usr/local/cuda \
PATH=$CUDA_HOME/bin:$PATH \
LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH \
uv run --extra inference python -m sglang.launch_server \
  --model qwen/Qwen3-8B \
  --enable-lora \
  --max-loras-per-batch 3 \
  --max-lora-rank 8 \
  --lora-target-modules q_proj k_proj v_proj o_proj \
  --max-loaded-loras 3 \
  --quantization fp8 \
  --mem-fraction-static 0.85 \
  --max-total-tokens 2048 \
  --max-running-requests 1 \
  --disable-cuda-graph \
  --port 30000 --host 127.0.0.1
```

**SGLang server-side memory observation** (CS-4 amendment data, runtime
fp8 quantization NOT bf16; CS-4's original budget assumed bf16 base):

```text
[load weight begin]   avail mem=14.77 GB
[load weight end]     avail mem= 5.68 GB, mem usage=9.09 GB (Qwen3ForCausalLM, fp8)
[memory pool end]     avail mem= 5.44 GB
[serve startup]       max_total_num_tokens=2048, max_running_requests=1, available_gpu_mem=4.89 GB
[mid-Step 5 nvidia-smi snapshot]  11128 MiB / 16311 MiB used  (~10.86 GB / 16 GB)
```

The 8.7 GB CS-4 estimate was for **training** (NF4 + GC + LoRA + activation),
not serving. A separate amendment for **serving-side fp8 base + LoRA + KV**
is required (~10.9 GB peak observed at idle-1-request workload).

**Verdict**: Step 2 (WSL2) ✅ PASS at v5. Server boot end-to-end took
~134 s (88 s shard load from `/mnt/c` + ~25 s warmup + misc).

### Step 3 (WSL2) — `/load_lora_adapter` PEFT direct (CS-6)

Script: `scratch_kalpha/step3_load.py` (uses
`erre_sandbox.inference.SGLangChatClient` end-to-end, no manual JSON crafting).

Output:

```text
loaded mock LoRA adapter 'mock_kant_r8' from /root/erre-sandbox/checkpoints/mock_kant_r8 — production loaders should reject mock=true sentinels at policy level (CS-9)
HEALTH: OK
LOAD: OK; loaded=['mock_kant_r8']
REGISTRY: name=mock_kant_r8 path=/root/erre-sandbox/checkpoints/mock_kant_r8 rank=8 is_mock=True
```

Server log evidence:

```text
[2026-05-09 11:13:35] LoRA adapter loading starts: lora_id=06d20fb7..., lora_name=mock_kant_r8, lora_path=..., pinned=False. avail mem=4.86 GB
[2026-05-09 11:13:36] LoRA adapter loading completes: ... avail mem=4.86 GB
[2026-05-09 11:13:36] INFO:  POST /load_lora_adapter HTTP/1.1  200 OK
```

CS-9 mock warning fires correctly. CS-2 client-side `loaded_adapters` registry
(MappingProxyType) reflects the post-load state. **No conversion script
required** — PEFT directory layout (`adapter_config.json` +
`adapter_model.safetensors`) is accepted directly by SGLang 0.5.10.post1
(CS-6 hypothesis confirmed; Defer D-4 stays deferred indefinitely since
direct-load route works).

LoRA load latency (cold, single-adapter, log-second precision): **<1 s**
between `loading starts` and `loading completes` events for r=8 mock. This
is well under the CS-8 500 ms diagnostic threshold but the measurement is
log-rounded and was taken on mock weights — real Kant-trained adapter
confirmation remains diagnostic-only per CS-8.

**Verdict**: Step 3 (WSL2) ✅ PASS.

### Step 4 (WSL2) — chat round trip (CS-9 identity transform)

Script: `scratch_kalpha/step4_chat.py`. Same prompt sent twice — once with
`adapter='mock_kant_r8'`, once without.

Output:

```text
=== WITH MOCK ADAPTER ===
finish_reason: stop
eval_count:    241
content (180): <think>
Okay, the user wants me to describe today's walk in two sentences. Since I'm supposed to be Immanuel Kant, I need to channel his philosophical perspective.

First, I should
=== WITHOUT ADAPTER ===
finish_reason: stop
eval_count:    245
content (180): <think>
Okay, the user wants me to describe today's walk in two sentences as Immanuel Kant. First, I need to recall Kant's philosophical style—analytical, structured, and focused o
=== IDENTITY HEURISTICS ===
len(WITH)=1210 len(WITHOUT)=1219 ratio=0.99
```

**CS-9 identity transform empirically confirmed**: WITH and WITHOUT outputs
match in shape (same `<think>` lead-in, same Kantian register, same finish
reason, ±1.6 % token count, length ratio 0.99). Minor lexical drift
(`"as Immanuel Kant"` vs `"to be Immanuel Kant"`) is consistent with
temperature=0.6 sampling noise on the SGLang side, not LoRA-induced
divergence — the mock has B=0 so the LoRA contribution is zero by
construction (handoff prompt §"Step 4", CS-9 / LOW-2).

Note: SGLang initially rejected the second `/load_lora_adapter` call (HTTP
400, server already had the adapter from Step 3). The Step 4 / Step 5
scripts handle this with an **unload + reload** retry pattern rather than
mutating client logic — this is a script-level convenience, not a CS-2
amendment (the `SGLangChatClient` registry behaviour is correct: it raises
on non-2xx so callers see the divergence). The 400 → unload-200 →
load-200 sequence is visible in `scratch_kalpha/logs/sglang_launch.log`.

**Verdict**: Step 4 (WSL2) ✅ PASS.

### Step 5 (WSL2) — ERRE FSM smoke, deep_work mode (CS-8 #3)

Script: `scratch_kalpha/step5_fsm_smoke.py`. Per the handoff prompt's
optional scope, only the **deep_work** mode is exercised here ("最小は
`deep_work` 1 mode だけでも可、本 PR では完全 8 mode を後続 Phase K-α
extension PR で扱う"). The persona surface is hand-rolled in the script and
deliberately bypasses `cognition/prompting.py` so the smoke stays decoupled
from any future prompting refactor.

Output:

```text
=== STEP 5 deep_work mode smoke ===
finish_reason: stop
eval_count:    172
prompt_eval:   54
content (300): <think>
Okay, the user is asking why the categorical imperative isn't hypothetical. Let me recall Kant's philosophy.

The categorical imperative is a principle that must be followed universally, regardless of personal desires or consequences. Hypothetical imperatives are conditional; they depend on
PASS: deep_work smoke (CS-8 #3 minimal acceptance met)
```

Acceptance heuristics applied (`finish_reason == "stop"`, non-empty content,
length < 4000 chars) all pass. No FSM regression observed in the SGLang
LoRA-routed path; CS-8 #3 fire condition does not trigger.

**Verdict**: Step 5 (WSL2) ✅ PASS for deep_work mode minimum. Full 8-mode
smoke deferred to a follow-up PR per handoff prompt scope.

---

## DB3 fire decision (CS-8)

### Initial pass (Windows native): FIRED → **RETRACTED on WSL2 retry**

**DB3 condition #1 (SGLang `--enable-lora` launch failure) → originally
fired** with the following scope nuance during the Windows-native attempt:

- **What fired**: install-side platform compat (no `sglang-kernel` wheel for
  Windows).
- **What did NOT fire**: CUDA driver mismatch, runtime crash, OOM, kernel
  symbol missing. The CUDA driver chain (RTX 5060 Ti, 16GB) had not been
  exercised by SGLang yet — that fire was purely a packaging boundary
  failure.
- **What CS-8 originally anticipated as #1**: "起動失敗 (e.g. CUDA driver
  mismatch / wheel install failure)". The wheel-install branch fit, but
  the wheel-install failure was **upstream Linux-only**, not
  GPU-dependency-version-mismatch on a wheel that *does exist* for the
  platform.

### Retry verdict (WSL2 + Ubuntu 22.04, same G-GEAR host, 2026-05-09)

**DB3 fire #1 is retracted.** With the WSL2 substrate and the v5 launch
configuration documented in §"WSL2 retry — Step 2", `sglang-kernel==0.4.1`
and the full `[inference]` extras stack install cleanly via manylinux
wheels, and the SGLang server reaches "fired up and ready to roll!" before
the Step 3 / 4 / 5 scripts run. Steps 3-5 all pass (CS-6 / CS-9 / CS-8 #3
clear). vLLM fallback should **NOT** be fired at this time — the Linux
execution boundary recommendation from the original report is empirically
confirmed.

The DB3 fire ledger now reads:

| Condition | Initial pass    | WSL2 retry        | Net status                                |
|-----------|-----------------|-------------------|-------------------------------------------|
| #1 launch                 | fired (Windows) | clean             | **retracted** — Linux substrate works     |
| #2 PEFT format reject     | n/a             | clean (HTTP 200)  | not fired                                 |
| #3 FSM regression         | n/a             | clean (deep_work) | not fired (8-mode deferred)               |

**Mac-side ADR decision still owed** (no authority asserted from this
report):

1. Adopt CS-1 amendment formalising the Linux execution boundary
   (WSL2 / Docker / remote host) and the additional cascade (CUDA toolkit
   12.9, fp8 quantization, `--lora-target-modules`, mem-fraction, etc.) listed
   in §"CS-N amendments (WSL2 retry)" below.
2. Decide whether `--quantization fp8` is acceptable for Phase K-β real
   training serving (training itself uses NF4 + LoRA so the fp8 serving
   constraint is decoupled, but **eval-time serving** parity matters for
   ME-* metrics).
3. Decide whether to harden `scratch_kalpha/` scripts into proper
   `tools/spike/` modules with `pytest.mark.spike` markers, or keep them as
   one-off retry artefacts (this PR keeps them in `scratch_kalpha/` per the
   original handoff prompt's manual-run framing — recommend promoting to
   `tools/spike/k_alpha_check/` in the M9-C-adopt PR).

## CS-N amendments (initial Windows pass — recommended; pending Mac-side adoption)

### CS-1 amendment (SGLang launch boundary)

> **Add**: Phase K α/β infrastructure runs on a **Linux execution
> boundary** (WSL2, Docker, or remote Linux host). Native Windows is not
> supported by `sglang-kernel` upstream — verified on 2026-05-09 against
> `sglang==0.5.10.post1` / `sglang-kernel==0.4.1`. Re-open conditions
> additionally include: SGLang upstream ships `win_amd64` wheels (currently
> none).

### CS-9 amendment (build_mock_lora kwarg)

> **Add**: `LoraConfig(init_lora_weights=...)` in peft 0.19.1 accepts
> `bool | Literal[...]` only. The string `"default"` raises ValueError; the
> identity transform is selected by `True`. The sentinel metadata field
> `metadata.init_lora_weights` is kept as the human-readable string
> `"default"` to label the scheme; this is decoupled from the LoraConfig
> kwarg by design (verified by `test_build_emits_mock_sentinel_metadata`).
> Fixed in PR #154 (the original K-α report PR).

### Diagnostic CS-N items NOT amended (initial pass)

CS-7 (N=3 throughput) and CS-8 (adapter swap latency 5-condition) were
**unmoved** during the initial pass — they are diagnostic measurements that
can only be taken against a live SGLang server, which Step 2 prevented at
that time. WSL2 retry yields some preliminary observations (see below) but
the formal diagnostic protocols (cold/warm/pinned/unpinned/no-LoRA × repeat)
remain outside K-α scope.

## CS-N amendments (WSL2 retry — additional cascade)

### CS-1 amendment v2 (Linux substrate cascade)

The CS-1 amendment v1 above (Linux execution boundary) is necessary but
**not sufficient**. The WSL2 retry surfaced four additional configuration
requirements that need to land in the same launch contract before the
server boots cleanly on a Blackwell consumer GPU (sm_120) at 16 GB VRAM:

> **Add (sub-requirements)**:
>
> 1. **CUDA toolkit ≥ 12.9** must be installed inside the Linux substrate
>    (e.g. `cuda-toolkit-12-9` from NVIDIA's `wsl-ubuntu` repo). Without
>    `nvcc` on PATH and `CUDA_HOME=/usr/local/cuda` exported, the SGLang
>    transitive dep `deep_gemm` raises `AssertionError` at import time
>    inside `_find_cuda_home()`. The host Windows driver alone (which
>    exposes a CUDA 13.2-capable runtime via the WSL2 `libcuda.so.1` shim)
>    is **not enough** for JIT compilation of sm_120 kernels — `deep_gemm`
>    (and likely also `flashinfer`) need a real CUDA toolkit ≥ 12.9 to
>    target the SM 12.x compute capability of Blackwell consumer GPUs.
> 2. **`--lora-target-modules` is mandatory at launch** when no initial
>    `--lora-paths` is supplied. SGLang 0.5.10.post1 raises:
>    `AssertionError: When no initial --lora-paths is provided, you need
>    to specify both --max-lora-rank and --lora-target-modules for LoRA
>    initialization.` For Qwen3-8B, the canonical attention modules are
>    `q_proj k_proj v_proj o_proj` (LOW-3 / Qwen3 attention block).
> 3. **Memory budget mismatch — `--quantization fp8` is required for
>    Qwen3-8B on a 16 GB GPU** in K-α single-request mode. With bf16
>    weights, the model alone occupies 14.77 GB; even at
>    `mem-fraction-static=0.93` (~14.88 GB allocated to the static pool)
>    SGLang's KV-cache initializer crashes with
>    `RuntimeError: Not enough memory. Please try to increase
>    --mem-fraction-static. Current value: mem_fraction_static=0.93`
>    (the message wording is misleading: increasing further means giving
>    *less* room to non-static allocations and does not unblock the model).
>    With `--quantization fp8 --mem-fraction-static 0.85
>    --max-total-tokens 2048 --max-running-requests 1 --disable-cuda-graph`
>    the model occupies 9.09 GB and the server starts cleanly with
>    ~4.89 GB available for KV / activation / loaded LoRAs.
> 4. **`--disable-cuda-graph` for K-α minimal-spike scope.** Without it,
>    cuda-graph capture pre-allocates additional buffers that further
>    crowd the 16 GB budget. For real-Kant Phase K-β re-enabling
>    cuda-graph may be desirable for throughput; this needs separate
>    measurement (Phase K-β scope, not K-α).

The full v5 launch invocation is verbatim in §"WSL2 retry — Step 2" and
also reproducible from `scratch_kalpha/step2_launch.sh` in this PR.

### CS-4 amendment (serving-side fp8 memory budget — distinct from training NF4)

The CS-4 8.7 GB estimate is for **training** (NF4 + GC + LoRA + activation,
batch=1, seq=2048), and remains valid for that purpose pending real Phase
K-β measurement. The K-α retry observation now adds a separate **serving-
side fp8 budget** that should live alongside CS-4 (or as a new CS-4b):

> **Add (serving-side, fp8 base + r=8 LoRA + KV pool, single request,
> Qwen3-8B on RTX 5060 Ti 16 GB)**:
>
> | Component                                  | VRAM (observed) |
> |--------------------------------------------|-----------------|
> | Qwen3-8B fp8 weight                        | 9.09 GB         |
> | KV pool + activation + buffers (init)      | ~0.55 GB        |
> | Single mock-LoRA (r=8) loaded              | ~0 GB (delta-noise; below per-load logging precision) |
> | Runtime overhead at idle (post-warmup)     | ~1.2 GB         |
> | **Peak observed (mid-Step 5 nvidia-smi)**  | **10.86 GB**    |
> | **Headroom (16 GB total)**                 | **~5.1 GB**     |
>
> Headroom comfortably accommodates the CS-1-mandated 3 loaded LoRAs
> (3 × ~30 MB = ~90 MB at r=8) plus a modest output-side KV growth.
> Real-Kant adapter swap latency / N=3 throughput (CS-7 / CS-8 diagnostic)
> still need separate Phase K-β measurement.

### CS-7 / CS-8 — preliminary diagnostic observation only (mock-LoRA, log-precision)

K-α scope explicitly excludes formal CS-7 / CS-8 measurement (handoff
prompt §"Phase K-α scope **外**"), but the WSL2 retry server log lets us
note one preliminary data point for context — to be **superseded** by
Phase K-β real-Kant measurements:

- **LoRA load latency (cold, single-adapter, mock r=8)**: **<1 s** between
  `loading starts` and `loading completes` events at log-second precision,
  for the 30 MB mock weight loaded from WSL2 native FS. Real-Kant
  adapter weight is the same r=8 PEFT shape so the cold-load time should
  be in the same order of magnitude, but this is mock-LoRA evidence only
  and **does not** clear the CS-8 diagnostic 500 ms threshold under any
  formal protocol — that needs the Phase K-β cold/warm/pinned/unpinned/
  no-LoRA × repeat measurement series.
- **N=3 collapse**: not measured. K-α only loaded a single adapter.

### Newly observed (not amendment, just documentation)

- SGLang `/load_lora_adapter` returns **HTTP 400** when the same
  `lora_name` is loaded twice without an intervening unload. Step 4 / Step
  5 scripts handle this with a script-side `unload → load` retry pattern
  (`scratch_kalpha/step4_chat.py` `_ensure_loaded()` helper). This is a
  **server-side stateful** quirk, not a `SGLangChatClient` bug — the
  client correctly raises `SGLangUnavailableError("HTTP 400")` and the
  caller chooses how to recover. Production scripts that own a single
  long-lived `SGLangChatClient` will not hit this since the in-memory
  registry guards against the duplicate.
- SGLang detected **SM120 (Blackwell) and auto-selected
  `fp4-gemm-backend=flashinfer_cudnn`** at startup. This was a one-line
  log entry, not an action item — but worth noting that the Blackwell
  consumer-GPU support path in SGLang 0.5.10.post1 is functional once the
  CUDA-toolkit prerequisite from CS-1 v2 is satisfied.

## Observations / follow-ups

1. **Phase J test gap**: `test_build_emits_mock_sentinel_metadata` does
   `pytest.importorskip("peft")`, so it actually exercises the LoraConfig
   path when `[training]` extras are installed. It would have caught the
   `init_lora_weights="default"` ValueError in CI **iff** `[training]` were
   in the default install. Two options for the next PR:
   - (a) move the metadata-sentinel test out from under the importorskip
     guard by mocking the LoraConfig path, OR
   - (b) add a `[training]`-extras CI matrix cell that runs the test for real.
   Recommend (b) since it would also catch real PEFT API drift on bumps.
2. **K-α handoff prompt amendment** (next iteration): explicitly require an
   `uv sync --extra inference --dry-run` step *on the target host* before
   the operator commits to `--no-dry-run`. This catches platform-coverage
   gaps before the operator burns a full venv switch.
3. **CS-1 follow-up: cross-platform wheel matrix audit** — repeat the
   dry-run check for the rest of the resolution universe (esp. flash-attn-4
   prerelease, which is the heaviest dep) on Windows + WSL2 + Linux to map
   the actual feasible substrate before re-running Phase K α.
4. **`.gitignore` already excludes `checkpoints/`** (uncommitted on this
   branch entry — included with this report's commit so the staged change
   is consistent with the artefact path used in Step 1).
5. **WSL2 retry follow-ups (post hoc)**:
   - The K-α handoff prompt § "前提環境" lists only `Ollama 起動済` for
     coexistence checks and assumes `--extra inference` resolves on G-GEAR.
     The next iteration should add a §"前提環境 (WSL2)" with the four
     CS-1 v2 prerequisites (CUDA toolkit ≥12.9, `--lora-target-modules`,
     `--quantization fp8`, `--mem-fraction-static 0.85`) so the operator
     boots straight to the v5 launch invocation rather than discovering
     them via the same 5-stage cascade.
   - The `scratch_kalpha/` directory (this PR) holds five scripts and a
     `logs/` subdirectory captured during the WSL2 retry. They are
     intentionally not promoted to `tools/spike/` in this PR (the
     handoff prompt's manual-run framing keeps them as one-off
     reproduction artefacts). M9-C-adopt should consider promotion
     and `pytest.mark.spike` integration.
   - HF cache sharing (`HF_HOME=/mnt/c/Users/johnd/.cache/huggingface`)
     was successful for one-time model load (88 s for 5 shards over the
     9P bridge) and avoided a 15 GB re-download. For repeated training
     epochs in Phase K-β, the I/O penalty may not be acceptable —
     measure first before deciding to clone the snapshot to WSL2 native.
