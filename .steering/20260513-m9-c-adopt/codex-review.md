ADOPT-WITH-CHANGES

**HIGH**

[HIGH-1] Rank sweep and serving contract are inconsistent  
v3 can exclude rank=32 from the default sweep, but it must not permanently close U1 without a conditional tail-sweep trigger. Current Qwen-class evidence is mixed: LoRA Land used rank 8, but PLORA’s Qwen2.5-7B sweep found task-dependent optima including rank 32, and P-React reports rank-sensitive personality modeling.  
Also, CS-1’s inherited SGLang launch uses `--max-lora-rank 8`; v3 rank `{4,8,16}` requires Phase B/D launch args and benchmark configs to set `--max-lora-rank >= 16`, otherwise rank 16 cannot be a real adoption candidate.  
Reflect before merge: default `{4,8,16}` is acceptable only with `rank=32` re-open if rank16 passes throughput but misses Vendi/ICC/Burrows, or if PLORA-like sensitivity appears in Phase B.  
Citations: https://arxiv.org/abs/2405.00732, https://openreview.net/pdf?id=azsnOWy9MZ, https://aclanthology.org/2025.findings-acl.328.pdf, https://sgl-project.github.io/advanced_features/lora.html

[HIGH-2] Tier B provisional thresholds cannot be point-threshold adoption gates  
`d >= 0.3 / ICC >= 0.6 / Burrows reduction >= 10%` is operationally usable as a provisional screen, but not as a merge-ready adoption verdict unless paired with bootstrap CI direction, baseline comparison, and ME-11’s ICC consumer split.  
Cohen-style effect-size rules make 0.3 a small-to-marginal effect, not a robust persona-discriminative shoulder. Koo & Li place ICC 0.6 in “moderate” reliability, but ME-11 already says adoption drift needs absolute-agreement semantics, not blind reuse of reliability fallback thresholds.  
Reflect before merge: DA-8/DA-9 must say point thresholds produce `ADOPT-WITH-CHANGES` unless the CI lower bound also clears the threshold and all metric directionality is positive versus no-LoRA baseline. Final thresholds should still be pinned after P4b/P4c empirical calibration.  
Citations: https://arxiv.org/abs/2410.16491, https://pubmed.ncbi.nlm.nih.gov/27330520/, https://lakens.github.io/statistical_inferences/06-effectsize.html, https://www.anthropic.com/research/persona-vectors

[HIGH-3] SGLang multi-LoRA stability is documented, not production-proven for ERRE’s live path  
SGLang docs support multi-adapter serving, dynamic loading, pinning, and csgmv, but the same docs warn that overlap loading can reduce multi-adapter prefill batching and increase TTFT. That is exactly the failure mode ERRE cares about for 3 persona live cognition.  
P-LoRA, S-LoRA, and dLoRA all treat adapter churn, heterogeneous ranks, batching, and memory fragmentation as first-class serving problems. A mock-first + real-after benchmark is necessary but not enough if it only runs a short CS-7 harness.  
Reflect before merge: Phase E/F needs a real `multi_lora_3` stress pass with pinned steady-state and a churn diagnostic, reporting TTFT/ITL/e2e p99, queue wait if available, misrouting, timeout, and memory growth.  
Citations: https://sgl-project.github.io/advanced_features/lora.html, https://arxiv.org/abs/2512.20210, https://arxiv.org/abs/2311.03285, https://www.usenix.org/system/files/osdi24-wu-bingyang.pdf

[HIGH-4] Production loader safety needs manifest-grade integrity, not only path + `is_mock`  
The hard block is directionally correct, but `weight_path in data/lora/m9-c-adopt/` plus `is_mock=True` is not enough for production safety. It must reject path traversal, symlink escape, missing PEFT config, `.bin` pickle fallback, wrong base model, wrong rank, wrong target modules, and checksum mismatch.  
Use a signed or at least immutable local manifest containing adapter name, persona id, base model, rank, target modules, sha256 for `adapter_model.safetensors`, training git sha, and mock flag. The runtime audit log should record the manifest id and outcome, not raw prompts or secret-bearing paths.  
Reflect before merge: define `AdapterIntegrityError` and `ProductionLoaderRejectError` against the manifest contract, not ad hoc filesystem inspection.  
Citations: https://huggingface.co/docs/peft/v0.12.0/developer_guides/checkpoint, https://huggingface.co/docs/huggingface_hub/en/guides/upload, https://arxiv.org/abs/2501.02170, https://github.com/huggingface/safetensors

**MEDIUM**

[MEDIUM-1] vLLM should remain late-bound, not first-class in Phase A.  
DB3 plus CS-8 support SGLang-first. vLLM current docs support LoRA and runtime loading, but dynamic updating is security-sensitive and has live issues such as load success not affecting output. Record current vLLM evidence and re-arm triggers in DA-2, but do not add a Phase D skeleton.  
Citations: https://docs.vllm.ai/en/v0.15.0/features/lora/, https://github.com/vllm-project/vllm/issues/18372

[MEDIUM-2] Rikyu 2-of-2 fallback is acceptable only as a named limitation.  
Japanese Burrows N/A should not be treated as equivalent to a pass. ME-* precedent supports limitation handling, but decisions.md must mark rikyu as `Burrows=N/A(tokenizer-unimplemented)` and add a blocker for Japanese tokenization.  
Citations: https://arxiv.org/abs/2010.06858, https://pubmed.ncbi.nlm.nih.gov/41144514/, https://doi.org/10.2964/jsik_2020_035

[MEDIUM-3] Requirement AC-1 still conflicts with v3 rank scope.  
`requirement.md` still states `{4,8,16,32}` while hybrid v3 says `{4,8,16}`. Update AC-1 or `design-final.md` will be internally inconsistent. Treat this as DA-1 trace, not a blocker if HIGH-1 tail-sweep trigger is added.  
Citations: https://openreview.net/pdf?id=azsnOWy9MZ, https://arxiv.org/abs/2405.00732

[MEDIUM-4] Big5 metric semantics need ME-11 alignment.  
If Phase E uses ICC(C,k), say it is a stability/reliability metric. If adoption wants LoRA persona-fit rather than response consistency, also report ICC(A,1) or another absolute-agreement measure as diagnostic before DA-9 final verdict.  
Citation: https://pubmed.ncbi.nlm.nih.gov/27330520/

[MEDIUM-5] Persona-specific sampling preservation is correct but needs a regression assertion.  
Keeping YAML `default_sampling` separate from LoRA is the right design. Add a Phase D/E assertion that all live-path calls still go through `compose_sampling()` and that SGLang options cannot override temperature/top_p/repeat_penalty.  
Citation: https://www.anthropic.com/research/persona-vectors

[MEDIUM-6] `min_examples=1000` remains an SLO, not a quality proof.  
CS-3 made 1000 examples an operational gate. Phase C should state that passing it only permits training; Tier B is still required to prove persona signal, especially because BIG5-CHAT uses a much larger 100,000-dialogue setup.  
Citation: https://arxiv.org/abs/2410.16491

**LOW**

[LOW-1] Add audit-log retention and redaction rules.  
The audit log is useful, but specify rotation, retention, and no raw prompt/persona prompt content.  
Citation: https://huggingface.co/docs/hub/main/adapters

[LOW-2] Checksum latency should be measured but not block design merge.  
Hashing `adapter_model.safetensors` is correct; just add the cold-load measurement to Phase F so CS-8 latency remains traceable.  
Citation: https://github.com/huggingface/safetensors

[LOW-3] Add a Japanese tokenizer implementation note to blockers.md.  
`fugashi`/MeCab is the pragmatic first option; Sudachi can be a later comparison if corpus segmentation quality matters.  
Citation: https://arxiv.org/abs/2010.06858

**Prior Art Summary**

1. LoRA rank sweep on Qwen-class 8B models: LoRA Land used “LoRA rank of 8” across 310 models, supporting rank8 as a practical anchor. PLORA’s Qwen2.5-7B evidence says there is “no single rule of thumb” and shows optimal rank 16 or 32 depending on task. P-React/P-Tailor-style personality work is rank-sensitive and uses much larger aggregate expert capacity. Conclusion: exclude rank32 from default compute only with a conditional re-open.

2. Persona-conditional evaluation thresholds: BIG5-CHAT uses 100,000 dialogues and reports BFI/IPIP-NEO high/low separation, but it does not provide ERRE-ready Vendi/Burrows thresholds. Cohen d 0.3 is small-to-marginal, ICC 0.6 is moderate, and Anthropic persona vectors emphasize monitoring trait shifts over fixed universal cutoffs. Conclusion: provisional pins are operational screens, not final adoption constants.

3. SGLang multi-LoRA fragmentation behavior: SGLang docs say it can support multiple LoRA adapters in one batch and document pinning, csgmv, `max_loras_per_batch`, and overlap loading. The same page warns overlap loading can “increase TTFT” when batching is reduced. P-LoRA/S-LoRA/dLoRA confirm fragmentation and scheduling are real multi-LoRA serving issues. Conclusion: SGLang-only is acceptable, but “production stable” needs ERRE measurement.

4. vLLM v0.15+ multi-LoRA runtime load: vLLM supports LoRA serving and dynamic load/unload behind `VLLM_ALLOW_RUNTIME_LORA_UPDATING`, but docs and issues show it is security-sensitive and not risk-free. Conclusion: keep vLLM as DB3 late-binding, not first-class Phase A.

5. Japanese tokenizer for Burrows Delta: Japanese has no whitespace segmentation; fugashi/MeCab exists specifically because tokenization is non-trivial. Japanese stylometry prior art uses morphemes, POS bigrams, function-word unigrams, and function phrases. Conclusion: rikyu 2-of-2 is acceptable as temporary limitation, not as a permanent metric asymmetry.

6. Production LoRA loader safety: PEFT defaults to safetensors, HF Hub stores content-addressed hashes, and safetensors adoption exists because pickle-backed `.bin` has security risk. Conclusion: path filter + `is_mock` is directionally right but must become a manifest/checksum policy.

**Closing Note**

Adopt hybrid v3, not v1 or v2, after the HIGH changes. COQ-1: rank32 permanent exclusion is HIGH-risk; default exclusion is acceptable only with conditional tail sweep and `--max-lora-rank` contract fix. COQ-2: provisional Tier B pins are operationally sound only with CI and baseline direction; final empirical pin should wait for P4b/P4c. COQ-3: vLLM first-class is not worth Phase A scope, but DA-2 must preserve late-binding with current docs and triggers. COQ-4: rikyu 2-of-2 fallback is acceptable as a documented limitation with a tokenizer blocker, not as a normal quorum variant.
