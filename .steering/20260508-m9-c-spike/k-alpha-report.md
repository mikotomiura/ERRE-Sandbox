# Phase K-α report — m9-c-spike mock-LoRA infrastructure proof (G-GEAR)

**Branch**: `feature/m9-c-spike-k-alpha-report`
**Host**: G-GEAR (Windows 11, RTX 5060 Ti 16GB, CUDA 12.x, Python 3.11.15, uv 0.11.7)
**Date**: 2026-05-09
**Handoff source**: `.steering/20260508-m9-c-spike/k-alpha-handoff-prompt.md` (commit
`959af6f`)

This report is the **G-GEAR side report-back** required by the K-α handoff
prompt §"Report-back format". It records each Step's actual command + output,
DB3 fire judgement against the three immediate-fire conditions (CS-8), and any
CS-N amendment values observed.

---

## Summary

Phase K-α surfaced **two distinct issues**, both of which need Mac-side
review before Phase K α can be retried:

1. **Latent build bug in `tools/spike/build_mock_lora.py`** (Phase J,
   shipped via PR #153). `LoraConfig(init_lora_weights="default")` raises
   `ValueError` on peft 0.19.1 — the string `"default"` is not in the
   accepted `bool | Literal[...]` set. **Fixed in this PR** by switching to
   `init_lora_weights=True`; the human-readable sentinel metadata is
   preserved.
2. **CS-1 platform incompat — DB3 fire condition #1 fired with scope
   nuance**. `sglang-kernel==0.4.1` (transitive of `sglang==0.5.10.post1`)
   ships only `manylinux2014_x86_64` / `aarch64` wheels. Native Windows
   install fails at uv resolution; WSL2 / Docker are not installed on this
   G-GEAR host. The fire is **install-side platform compat**, NOT CUDA
   runtime mismatch. Recommendation: amend CS-1 to declare a Linux
   execution boundary (WSL2 / Docker / separate Linux host) before
   firing the DB3 → vLLM fallback (vLLM has the same constraint).

| # | Step                                  | Status | DB3 fire? |
|---|---------------------------------------|:------:|:---------:|
| 1 | mock-LoRA build (CS-9)                |  ✅    |     —     |
| 2 | SGLang `--enable-lora` launch (CS-1)  |  ❌    |   **#1**  |
| 3 | `/load_lora_adapter` PEFT direct (CS-6)|  ⏸️    |     —     |
| 4 | chat round trip (CS-9 identity)       |  ⏸️    |     —     |
| 5 | ERRE FSM 8-mode smoke (CS-8 #3)       |  ⏸️    |     —     |

(⏸️ = deferred pending Linux substrate; not failed)

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

## DB3 fire decision (CS-8)

**DB3 condition #1 (SGLang `--enable-lora` launch failure) → FIRED**, with
the following **scope nuance**:

- **What fired**: install-side platform compat (no `sglang-kernel` wheel for
  Windows).
- **What did NOT fire**: CUDA driver mismatch, runtime crash, OOM, kernel
  symbol missing. The CUDA driver chain (RTX 5060 Ti, 16GB) has not been
  exercised by SGLang yet — this is purely a packaging boundary failure.
- **What CS-8 originally anticipated as #1**: "起動失敗 (e.g. CUDA driver
  mismatch / wheel install failure)". The wheel-install branch fits, but
  the wheel-install failure here is **upstream Linux-only**, not
  GPU-dependency-version-mismatch on a wheel that *does exist* for the
  platform.

**Recommendation for the M9-B / M9-C ADR re-open** (Mac-side decision):

1. **Do NOT immediately fire DB3 fallback to vLLM** — vLLM has the same
   platform constraint (Linux-only CUDA kernels). Switching the adapter
   target (SGLang → vLLM) does not solve a *Windows-native execution*
   problem.
2. **Re-frame CS-1 launch boundary**: the supported substrate for the
   Phase K α/β infrastructure is Linux (WSL2 on G-GEAR, Docker on G-GEAR,
   or a separate Linux host). Update CS-1 to make this explicit and add the
   wheel-coverage check to the ADR re-open conditions.
3. **Pick the minimum-cost path before Phase K α retry**:
   - WSL2 install + Ubuntu 22.04 + CUDA passthrough (driver already on host;
     `nvidia-smi` works in WSL2 with `wsl --update`).
   - Docker Desktop with NVIDIA Container Toolkit (heavier, but isolates the
     stack).
   - A separate Linux GPU host (cleanest, but breaks the "G-GEAR is the
     execution machine" project assumption — see auto-memory
     `reference_g_gear_host.md`).

The author of this report has no authority to re-open the ADR; the choice
between the three options is for the Mac-side review session.

## CS-N amendments (recommended; pending Mac-side adoption)

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
> Fixed in this PR (the K-α report PR).

### Diagnostic CS-N items NOT amended

CS-7 (N=3 throughput) and CS-8 (adapter swap latency 5-condition) are
**unmoved** — they are diagnostic measurements that can only be taken
against a live SGLang server, which Step 2 prevented. The CS-7 / CS-8
amendment ledgers should remain blank pending a Linux-substrate K-α retry.

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
