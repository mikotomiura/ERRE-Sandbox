# Reproducing the byte-exact replay claim

This repository claims that a simulation with a real, non-deterministic language
model inside its loop can be **replayed byte-for-byte, across operating
systems**. This file is how you check that claim yourself.

You need neither a language model nor a GPU. The replay is driven from records
committed to this repository, and it asserts that zero language-model calls were
made while replaying. (Installing the runtime dependencies first needs a package
index, as any install does; the replay itself opens no connection at all.)

**Permanent reference.** The archived snapshot of this repository is
[`10.5281/zenodo.22718679`](https://doi.org/10.5281/zenodo.22718679) (concept DOI — always resolves to the
latest archived version; `10.5281/zenodo.22718680` is the `v0.0.1` release
specifically). GitHub Actions logs and the state of `main` both move; the DOI
does not. Cite the concept DOI, and use the archived snapshot if you want the
exact bytes a claim was made about.

**What you are checking, precisely.** You are checking a **replay-verify**: the
committed records are replayed and the re-rendered bytes are compared against
the committed bytes, on your machine. You are *not* re-baking the bundles.
Baking requires a real Ollama host and a ratified spend, and it was done on the
author's Windows machine. That distinction is load-bearing and is stated again
in the limits section below.

---

## 1. Prerequisites

[uv](https://docs.astral.sh/uv/) and Python 3.11. Nothing else.

```bash
git clone https://github.com/mikotomiura/ERRE-Sandbox.git
cd ERRE-Sandbox
```

Do not disable git's line-ending handling or re-checkout with a different
`core.autocrlf`: the hashes below are hashes of **checked-out bytes**, and
`.gitattributes` is what keeps them stable on every platform.

---

## 2. The one command

The same string works in PowerShell on Windows and in bash on Linux and macOS:

```
uv run --frozen --no-dev python scripts/verify_committed_artifacts.py
```

It takes a few seconds. Exit code `0` means everything below passed.

`--frozen --no-dev` is part of the claim, not a shortcut: it pins the
environment to `uv.lock` and installs the **runtime dependencies only** — no
pytest, no machine-learning extras. If that succeeds, replaying these bundles
demonstrably needs none of them.

### What it verifies

| target | committed bytes | what the replay proves |
|---|---|---|
| `society-real` | `experiments/20260907-m13-society-live/artifacts/` | a sealed run with **real `qwen3:8b` + `nomic-embed-text`**, 3 agents × 12 cognition windows × 20 physics ticks, 36 model calls and 112 embeddings, replays to identical bytes |
| `society-rehearsal` | `experiments/20260907-m13-society-live/rehearsal/` | the model-free rehearsal at the same pre-registered shape, through the same verify path |
| `live-loop-real` | `experiments/20260904-m13-live-loop-live/artifacts/` | the sealed single-agent live-loop run (32 cognition ticks) replays to identical bytes |
| `live-loop-rehearsal` | `experiments/20260904-m13-live-loop-live/rehearsal/` | the model-free rehearsal of the same |
| `ecl-v0-golden` | `tests/fixtures/ecl_v0_golden/` | the smallest fixture: single agent, scripted plane 2 |

For each target the verifier re-renders every artifact and compares it against
the committed SHA-256 in that bundle's own `manifest.json`, re-derives the side
annotations into a temporary directory and compares those against the committed
copies byte-for-byte, and checks that the replay made **zero** language-model
calls. It then compares every file's checked-out bytes against
[`docs/artifact-hashes.md`](docs/artifact-hashes.md).

Each target runs in its own subprocess, under the `ERRE_ZONE_BIAS_P` value that
bundle records in its own `env_pins`; the value used is printed for each target.
Nothing is exported into your shell. This is replaying a sealed artifact under
its own recorded provenance — running a bundle under some other value would be
verifying a different artifact, not the one that was baked.

### To verify one target only

```
uv run --frozen --no-dev python scripts/verify_committed_artifacts.py --only ecl-v0-golden
```

(`--list-targets` prints the names. The hash-table comparison is skipped for a
partial run, because the table covers every target.)

---

## 3. The full test suite

The command above is the short path. The long path is the suite that public CI
runs, which additionally exercises the harnesses, the spend gates, the
non-determinism scanner and its own negative fixtures:

```bash
uv sync
uv run pytest -m "not godot and not eval and not spike and not training and not inference"
```

The deselected markers need extras (heavy ML dependencies, a GPU, or a Godot
binary) that the claim does not depend on. That marker expression is not
restated here by hand: `.github/workflows/ci.yml`'s `test` job owns it and
`tests/test_architecture/test_pre_push_ci_parity.py` fails if this file's copy
drifts from it.

The three tests that carry the cross-platform claim specifically are:

```
tests/test_integration/test_m13_society_live_capture.py::test_committed_sealed_real_bundle_verifies
tests/test_integration/test_m13_live_loop_capture.py::test_committed_sealed_real_bundle_verifies
tests/test_integration/test_m13_society_live_capture.py::test_committed_rehearsal_bundle_verifies
```

---

## 4. Expected hashes

[`docs/artifact-hashes.md`](docs/artifact-hashes.md) lists the SHA-256 and byte
count of every file the claim rests on. It is **generated**, not written by
hand, and the command in section 2 regenerates it from disk and fails if it
disagrees — so it cannot quietly rot.

It is not the same thing as `paper/data-hashes.md`, which is an untracked
transport record for two separate manuscript repositories.

---

## 5. What public CI already enforces, and what it does not

Every pull request runs, on both `ubuntu-latest` and `windows-latest`:

- the `repro` job — literally the command in section 2, with runtime
  dependencies only;
- the `test` job — the full suite from section 3.

The Windows runner image is a different machine from the author's, which is the
point: the bundles were baked under Windows (UCRT) and are verified under both
glibc and a second, independent Windows.

**Limits, stated plainly:**

- **CI enforces replay-verify, not baking.** No CI job regenerates a bundle. The
  claim that these bytes were produced on Windows is the author's, evidenced by
  the manifests' environment pins, not by a public CI witness.
- **A CI runner is a clean machine, but it is not a third party.** What is
  mechanically enforced is that the procedure works on a fresh machine that is
  not the author's — not that an independent person read this file and ran it.
- **Godot-side reproduction is not in CI.** Those tests self-skip without a
  Godot binary, and they compare a documented canonical placement rather than
  raw bytes.
- This apparatus is a single codebase, exercised with a single model family, by
  a single author.

An earlier Windows CI run earned this section its caution: it failed because
`uv.lock` was outside `.gitattributes`' `eol=lf` coverage, so GitHub's Windows
image (which defaults to `core.autocrlf=true`) checked it out as CRLF and
changed a pinned hash. The author's machine and the Linux runner are both LF and
could never have seen it.

---

## 6. Reading the manifests

Each bundle's `manifest.json` records the environment it was baked under, the
per-file SHA-256 set, the canonical JSON rules (including the 6-digit float
quantisation that absorbs cross-libm drift), and a determinism checklist.

One erratum you will hit if you read them closely: the sealed society bundle's
`annotations.real_run_status` still reads *"NOT RUN as of Issue 007"*. That text
was frozen into the harness **before** the ratified real run, and the bundle's
bytes cannot be edited after the fact without destroying the very thing being
verified. The authoritative fields are `env_pins.capture_mode` (`"real"`),
`env_pins.real_backend` (`true`), and the pinned model digest and Ollama
version. The erratum is written up in
`experiments/20260907-m13-society-live/env.md`.

---

## 7. Where things live

| what | where |
|---|---|
| the two planes, quantisation and record/replay | `src/erre_sandbox/integration/embodied/handoff.py`, `.../loop.py` |
| the non-determinism scanner and its negative fixtures | `src/erre_sandbox/integration/embodied/society_live_loop.py`, `tests/test_integration/test_society_live_loop.py` |
| capture harnesses (spend-gated; they refuse without explicit ratification) | `scripts/m13_society_live_capture.py`, `scripts/m13_live_loop_capture.py` |
| per-experiment provenance | `experiments/*/env.md`, `notes.md`, `SEED` |
| architecture | `docs/architecture.md` |
| how to cite | `CITATION.cff` |
