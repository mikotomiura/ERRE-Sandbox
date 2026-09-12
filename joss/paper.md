---
title: 'Two-plane determinism: byte-exact cross-platform replay of LLM-in-the-loop agent simulations'
tags:
  - Python
  - reproducibility
  - deterministic replay
  - multi-agent simulation
  - large language models
authors:
  - name: Mikoto Miura
    orcid: 0009-0000-4196-0508
    affiliation: 1
affiliations:
  - name: Independent Researcher
    index: 1
date: 12 September 2026
bibliography: paper.bib
---

# Summary

ERRE-Sandbox is a Python apparatus for embodied multi-agent simulations that run a local
language model inside the loop. Its design separates two planes of state. Physics, memory
geometry, random-number streams, clocks, identifiers and scheduler order are pinned in a
*simulation plane*; every model call is recorded and replayed in a *model-call plane*.

Under that separation a run is byte-exact across operating systems. Byte-exact here means
that every emitted artifact re-renders to identical bytes under the documented
canonicalisation, which quantises floating-point values to six decimals — not that raw
IEEE-754 results agree. The quantum is chosen against measurement: the largest cross-libm
drift observed in the frozen trigonometric path is 8.88e-16, about one unit in the last place
and non-amplifying, six orders of magnitude below the 5e-7 half-quantum that decides rounding.

A sealed three-agent run driven by a real `qwen3:8b` re-renders to identical hashes on
Windows and on Linux, checked by public CI on every pull request.

# Statement of need

Putting a language model inside a simulation loop costs reproducibility. Without a
reproduction contract, a disagreement about a result cannot be separated into "the analysis is
wrong" and "the run was different". Determinism is a precondition for auditing such systems,
not a finishing touch. Frameworks for LLM-driven agent societies
[@park2023generative; @al2024projectsid] treat the model as an opaque service and do not offer
such a contract.

The obstacle is that non-determinism enters from two unrelated directions at once. One is the
model call itself. The other is everything around it: floating-point differences between C
runtimes, hash-seeded iteration order, wall clocks, UUIDs, and the order in which agents are
scheduled inside a step. Pinning only the first leaves runs that still diverge; pinning only
the second leaves the model free to diverge. ERRE-Sandbox exists to pin both at once, and to
make the resulting claim checkable by a reader who has neither a GPU nor a language model.

# State of the field

Deterministic replay of LLM agents is not new, and this work claims no novelty in it. agrepl
[@mudasiru2026agrepl] intercepts external interactions at the transport layer through a
man-in-the-middle proxy and reports replay fidelity F = 1.0 over 250 instances across five
workloads. AgentRR [@feng2025agentrr] also records and replays agent executions, but toward a
different end — reusing experience rather than verifying determinism. "Record and replay"
thus names at least two distinct goals in this literature.

What is left open is the layer the proxy does not reach.

|  | agrepl [@mudasiru2026agrepl] | ERRE-Sandbox |
| --- | --- | --- |
| Simulation-side state (physics, RNG, clocks, identifiers, scheduler order) | Not addressed; the proxy intercepts external calls and does not pin the simulation itself | Pinned and checksummed as a first-class plane |
| Cross-platform byte equality | Not claimed; fidelity is reported inside one isolated environment | Windows-authored bundles re-render identically under Linux and under a second, independent Windows |
| Numerical justification of the canonicalisation | Out of scope | Quantum chosen against measured cross-libm drift |

: Delta against the closest prior system.

# Software design

The design question was where to cut: between what the simulation decides and what the model
decides, pinning each side by its own mechanism.

| Simulation plane pins | Model-call plane pins |
| --- | --- |
| Physics step and memory geometry; named RNG substreams seeded through SHA-512, independent of `PYTHONHASHSEED`; a frozen retrieval clock; memory identifiers and timestamps derived from the tick; a total order over retrieval ties; envelope send times; recorded environment pins | Every action-model call recorded with an outcome tag (`ok`, `unparseable`, `raised`), so failure paths replay too; replay injects the recorded response and calls no model; reflection is disabled while recording, closing the second model-side source |

: What each plane pins. The enumerations are maintained in code as `DETERMINISM_CHECKLIST`
and `M2_NBODY_DETERMINISM_CHECKLIST`.

Several agents add a pin with no single-agent analogue: the order in which they are stepped
within a cognition window. It is fixed by sorted agent identifiers, executed strictly
sequentially with no `asyncio.gather` fan-out, recorded in the environment pins as
`society_cognition_step_order`, and checksummed; `uuid4`-derived dialogue identifiers were
removed for reintroducing non-determinism through the same door. This is where the separation
earns its cost. A transport-layer replay can record the sequence of requests that did occur,
but it does not pin, audit or checksum the simulation-internal order that produced them. The
argument holds only for two or more agents; with a single agent there is one possible order
and nothing to pin.

Canonicalisation is the seam between the planes. Artifacts are serialised as canonical JSON —
sorted keys, compact separators, `ensure_ascii=False`, and non-finite values raising rather
than being hashed silently — with every float quantised to six decimals. One cost surfaced
twice: floats already serialised inside an embedded JSON string bypass the quantiser, so
projection boundaries re-quantise, and that hole is documented rather than assumed closed.

The quantum needs justifying because the underlying problem is known and unsolved. The C++
committee paper P3375R3 states plainly that "C++ does not support reproducible programming.
In fact, the standard does not specify floating point behaviour at all"
[@davidson2025p3375], and exhibits identical sources producing different values across
compilers. The response here is not to solve that but to bound it: the measured drift is
8.88e-16 against a 5e-7 half-quantum, so both platforms round identically with six orders of
magnitude to spare. The trade-off is real — six decimals discards spatial resolution below a
micron — and is stated so readers can judge whether the same bound suits their application.

# Research impact statement

A sealed run exercises three agents over twelve cognition windows of twenty physics ticks
each, driven by a real `qwen3:8b` and a real embedding model, making 36 model calls and 112
embedding calls under a fixed seed; the harness refuses to spend without explicit
ratification. Replaying the committed records reproduces every artifact's SHA-256, with zero
model invocations on every replay channel and request conformance holding on 36 of 36 model
calls and 112 of 112 embeddings.

Public CI runs the same verification on `ubuntu-latest` and `windows-latest` for every pull
request, the Windows runner being a different machine from the author's. What CI enforces is
replay-verify, not baking: no job regenerates a bundle, and the claim that these bytes were
produced under Windows rests on the manifests' environment pins, not on a CI witness.

A reader can close the replay side alone, with one command that needs runtime dependencies
only — no test framework, no machine-learning extras, no GPU and no language model. This is
not a reproduction of the live bake. Its value is narrower and checkable: the replay
regenerates the outputs while making zero model invocations, and the regenerated bytes match
hashes committed in the repository. The non-determinism scanner is held to the same standard:
one test closes a negative and a clean fixture together, so the detector is shown not to be
vacuous — the failure mode @shulepov2026mutation documents empirically.

*Research usage.* Two preregistered audits have been run on this apparatus, in the same style
of frozen-parameter control described by @otterson2026adversarial. Both returned null or
non-supporting results, and their artifacts are committed in the public repository.

*Development history.* The public commit history is short by construction: the repository was
re-created with a single clean commit on 2026-05-31 to strip research scaffolding before
publication, discarding the earlier history, and 293 commits have accumulated since (measured
2026-09-12). Development runs further back. Tracked documentation carries a dated chain to
2026-04-21 and cites merged pull requests numbered 117–127 from 2026-04-30, a numbering the
current repository does not share.

# Limitations

The immutability of the frozen measurement apparatus is enforced by discipline alone: there
is no CI diff gate and no pinned-hash test over it. The static egress check is a deliberately
weak backstop, with a behavioural test as the primary boundary. This is one codebase,
exercised with one model family, by one developer.

Two boundaries bear repeating because they are easy to over-read. CI enforces replay-verify
and never baking, which remains on the author's machine. And a CI runner is a clean machine
but not a third party: what is shown is that the procedure works away from the author's
machine, not that an independent person ran it. Replay opens no network connection, though
installing dependencies needs a package index like any install.

Godot-side reproduction sits outside all of this. No end-to-end demonstration through a live
engine has been performed; those local headless tests (`SocietyReplayViewer.gd` under
`--headless`) self-skip without a Godot binary (4.6.2 here, located via `GODOT_BIN`) and so
never run in CI; they compare a documented canonical placement rather than raw bytes; and they
exercise only placement import and export, not live cognition, embedding or engine-side
physics. An unresolved defect also collapses the rendered zone layout to a single zone.

The two-phase sampling control did not fire during the sealed run; no eligible tick occurred.
That is a legitimate preregistered outcome, it was not re-run to force firing, and no claim of
any behavioural consequence is made anywhere in this paper.

One caution was earned rather than anticipated: an early Windows CI run failed because the
lockfile sat outside the repository's line-ending pins, so the Windows image checked it out
with different line endings and changed a pinned hash — invisible to the author's machine and
the Linux runner, which are both LF.

# AI usage disclosure

This project was developed with substantial AI assistance, disclosed here in full. Claude
(Anthropic; Opus, Sonnet and Haiku models, via Claude Code) was used for implementation,
refactoring, test scaffolding, documentation, and drafting of this paper's text; OpenAI Codex
(`gpt-5.5`) was used for independent design and code review. Assistance is visible in the
public record rather than asserted here: 254 of the 293 public commits carry `Co-Authored-By`
trailers naming the model used (measured 2026-09-12).

All AI-assisted output was reviewed, edited and validated by the human author, who made the
core design decisions — including the two-plane separation, the canonicalisation rules and
quantum, the scope of every claim in this paper, and the venue and title of this submission.
Validation is not self-reported: the replay-verify claims are enforced by repository tests and
public CI, and the guards were themselves checked by mutation. The Windows bake provenance
remains the manifest-backed author report stated above.

# Acknowledgements

This work received no financial support.

# References
