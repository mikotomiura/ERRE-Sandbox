<div align="center">

# 🏛️ ERRE-Sandbox

**Autonomous 3D Society Emerging from the Cognitive Habits of Great Thinkers**

A research platform that re-implements the cognitive habits of historical
thinkers as locally-hosted LLM agents inhabiting a shared 3D world —
built around two first-class primitives: **deliberate inefficiency** and
**embodied return**.

[![CI](https://github.com/mikotomiura/ERRE-Sandbox/actions/workflows/ci.yml/badge.svg)](https://github.com/mikotomiura/ERRE-Sandbox/actions/workflows/ci.yml)
[![License: Apache-2.0 OR MIT](https://img.shields.io/badge/license-Apache--2.0%20OR%20MIT-blue.svg)](#-license)
[![Python 3.11](https://img.shields.io/badge/python-3.11-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Godot 4.6](https://img.shields.io/badge/Godot-4.6-478CBF.svg?logo=godotengine&logoColor=white)](https://godotengine.org/)
[![Code style: Ruff](https://img.shields.io/badge/code%20style-ruff-261230.svg)](https://github.com/astral-sh/ruff)

**English** | [日本語](README.ja.md)

</div>

---

## ✨ What is ERRE-Sandbox?

ERRE-Sandbox boots a small society of historical thinkers — currently
**Kant / Nietzsche / Rikyū** — as local LLM agents that walk, reflect, and
converse inside a Godot 4.6 world. Rather than optimizing for throughput,
the system treats *inefficiency* (peripatetic wandering, tea-room stillness,
zazen) and *embodied return* (moving the body to reset cognition) as design
primitives, then observes what emergent intellectual behavior appears.

- 🧠 **Cognitive habits as code** — each thinker's habits, ERRE-mode sampling
  overrides, and public-domain source references live in `personas/*.yaml`.
- 🌀 **ERRE-mode FSM** — `peripatetic / chashitsu / zazen / shu-kata /
  ha-deviate / ri-create / deep-work / shallow` drive sampling + behavior.
- 🪟 **Observable reasoning** — trigger-event tags propagate from the Python
  `Reflector` to the Godot reasoning panel, so an operator sees *why* a
  reflection fired.
- 🔬 **Evidence-grade evaluation** — a post-hoc metric layer (Burrows Δ /
  MATTR / NLI / novelty / Big5 ICC / Vendi diversity) with hierarchical
  bootstrap CIs, run on isolated DuckDB shards.

---

## 🧭 Status

> **Wire schema `0.11.0-m13es3`** · three-agent society live on Godot 4.6 ·
> M9-C-adopt (kant LoRA pilot) **closed** · next milestone: **M10-11 evaluation framework**

The three-agent society boots through
`uv run erre-sandbox --personas kant,nietzsche,rikyu`, with the M5 ERRE-mode
FSM, multi-turn LLM dialog, and all rendered zone scenes (`peripatos` /
`chashitsu` / `zazen` / `agora` / `garden` plus `study` / `base_terrain`).

**M9-C-adopt — Kant LoRA ADOPT pilot: completed with a REJECT verdict
(2026-05-25).** The kant-style LoRA *can* improve Burrows stylometric
fidelity (and clears ICC / throughput gates), but **cannot simultaneously
converge output diversity across the encoder panel** — the Vendi-Burrows
*simultaneity* is non-achievable within the tested design space (two
structurally distinct mechanisms, `case A` auxiliary-loss and `case B`
preference optimization, fail on the same axis). This is recorded as a
**completion + methodological finding + ADOPT-negative**, not a failure.
The research program was deliberately **terminated** (disposition and any
future research accounted for separately).

**Next — M10-11: 4-layer evaluation framework + statistical report.**
Layer 1 spatial / Layer 2 semantic / Layer 3 ritual / Layer 4 third-party
(LLM-as-judge), with Benjamini-Hochberg FDR correction (n ≥ 20) and OSF
pre-registration, reusing the existing Tier-A/B evidence metrics and DuckDB
contract. See `docs/functional-design.md` §5 and MASTER-PLAN §5.

<details>
<summary>Earlier landmarks</summary>

- **M9-C-adopt Plan B kant chain** (2026-05): PR-7…PR-24 → retrain (KTO,
  composite Burrows preference) → PR-21 REJECT verdict → terminate ADR →
  terminal-hygiene cleanup (verdict narrative + da14⇆da19 fold doc).
- **M9-eval Phase 2** (2026-05): `qwen3:8b` golden-battery driver +
  audit gate, 4-layer `raw_dialog` ↔ `metrics` DuckDB contract.
- **M9-A event-boundary observability** (2026-04): `TriggerEventTag`
  end-to-end through the reasoning panel.
- **CI pipeline** (2026-04): 3-parallel CI (`lint` / `typecheck` / `test`).
- Release tags: `v0.1.0-m2` → `v0.3.0-m5` (ERRE FSM + LLM dialog + zones).

</details>

---

## 🧱 Architecture

| Layer | Path | Responsibility |
|---|---|---|
| **Python core** | `src/erre_sandbox/` | Pydantic v2 schemas, inference adapters (Ollama / SGLang), sqlite-vec memory, CoALA-inspired cognition cycle (`Reflector`), ERRE FSM (`erre/`), world tick loop, proximity dialog scheduler |
| **Contracts** | `src/erre_sandbox/contracts/` | Lightweight pydantic-only boundary (`thresholds.py`, `eval_paths.py`) importable without heavy deps |
| **Evidence** | `src/erre_sandbox/evidence/` | Post-hoc metrics: M8 baseline/scaling, M9-eval Tier-A (Burrows / MATTR / NLI / novelty / Empath), Tier-B (Big5 ICC / Vendi), bootstrap CI, golden driver |
| **CLIs** | `src/erre_sandbox/cli/` | `erre-sandbox` (`run` / `export-log` / `baseline-metrics` / `scaling-metrics`) + standalone `eval_run_golden` / `eval_audit` |
| **Godot frontend** | `godot_project/` | 3D visualization over a WebSocket bridge: humanoid avatars, ERRE-mode tint, dialog bubbles, reasoning panel, six scenes |
| **Personas** | `personas/*.yaml` | Per-thinker habits, ERRE-mode sampling overrides, public-domain sources (`kant` / `nietzsche` / `rikyu`) |

The dependency rule is strict: `src/erre_sandbox/` never imports GPL code
(any Blender integration is isolated in the separately-packaged
`erre-sandbox-blender/`), and cloud LLM APIs are never a required
dependency (zero-budget constraint).

---

## 🚀 Getting started

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run pytest -m "not godot"

# boot the three-agent society
uv run erre-sandbox --personas kant,nietzsche,rikyu
```

Heavy ML deps (sentence-transformers, scipy, ollama, empath, arch) for the
evaluation pipeline are isolated under extras:

```bash
uv sync --extra eval        # M9-eval Tier-A/B metrics
```

CI (`.github/workflows/ci.yml`) runs the four checks above in three parallel
jobs on every push to `main` and every PR. Enable the local pre-commit hook
once after cloning:

```bash
uv tool install pre-commit && pre-commit install
```

### 🔐 WebSocket auth (optional)

The orchestrator's WebSocket endpoint ships three independent, default-off
gates (shared token / Origin allow-list / session cap). `bootstrap()`
refuses to start with `host=0.0.0.0` *and* all gates off, so a bare
`--host=0.0.0.0` cannot silently expose the server. For LAN development:

```bash
uv run python -m erre_sandbox --allow-unauthenticated-lan   # loud warning each boot
```

Token provisioning, rotation, and override priority are documented in
`docs/development-guidelines.md`.

---

## 🗂️ Layout & docs

| Document | When to read |
|---|---|
| `docs/functional-design.md` | feature intent, requirements, the 4-layer eval framework |
| `docs/architecture.md` | tech stack & end-to-end data flow |
| `docs/repository-structure.md` | authoritative file layout & dependency direction |
| `docs/development-guidelines.md` | coding standards, Git workflow, test policy |
| `docs/glossary.md` | ERRE terms (peripatos, chashitsu, shu-ha-ri, …) |

---

## 📜 License

Dual-licensed under **Apache-2.0 OR MIT** at your choice — see `LICENSE`,
`LICENSE-MIT`, and `NOTICE`. Any Blender-side integration lives in a
separately-packaged **GPL-3.0** project (`erre-sandbox-blender/`) to prevent
license contamination.
