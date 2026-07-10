# M13 C-proper — powered bank sealed run（環境 / status）

- **実験**: live-channel-conformance の powered sealed run（実 spend R-budget=1）。反復 frozen-context bank を
  real qwen3:8b で M=300・K=8 実走し、§CB4.4 verdict で λ→sampling→zone bias（第2リンク）detectability を決着。
- **apparatus**:
  - capture/verify = `scripts/ecl_bank_cproper_capture.py`（provenance=mock / M-loop=live qwen3、think=False）。
  - scorer = `src/erre_sandbox/integration/embodied/bank_scorer.py`（annotation → §CB4.4 verdict）。
  - 再利用（read-only）= `bank.py`（`run_bank_mloop`）/ `bank_fixtures.py`（`run_provenance_pass`）/
    `bank_power.py`（power + null 校正 + 閾値）。
- **ADR**: `.steering/20260708-m13-c-design-bank/design-final.md` §CB4（pre-register、不可侵）+
  `.steering/20260710-m13-c-proper/design-final.md` §S（scorer、run 前凍結）。

## status（PRE-RUN — 未実走、実 spend 未消費）

- scorer + capture harness + test 実装済（`test_ecl_bank_scorer.py` 14 / `test_ecl_bank_cproper_capture.py` 2、
  pre-push 4 段対象）。**scorer は Codex review → HIGH 反映 → commit（seal）してから実走**。
- **実走前 binding gate**:
  1. scorer を committed 凍結（result-independent、forking-paths seal）。
  2. **user spend 再確認（AskUserQuestion）** = R-budget=1 消費 + valid FAIL→arc-close 自動執行を明示 ratify。
- `run.sh` = live capture（要 live Ollama + qwen3:8b pull、`QWEN3_DIGEST`/`OLLAMA_VERSION`/`VRAM_GB`/
  `UV_LOCK_SHA256` を env で渡す）。
- `repro.sh` = Ollama-free replay-verify + scorer verdict（Windows bake ⇔ WSL byte 一致を両 platform で実測）。

## 事前登録（§CB4 / §S、run 前固定・実走後 tuning ゼロ）

- **estimand**: per frozen context の P(zone|ctx,T_on) vs P(zone|ctx,T_off)（5-way categorical、M=300 × K=8、
  T_on=`LocomotionState(lam=λ_ctx)` / T_off=`locomotion=None`、zone bias off・pre-bias readout）。
- **(i) criterion**: H(zone|ctx)≥0.5 bit を ρ≥0.5 context で満たす。未達 collapse → `NO_CHANNEL_CONFORMANCE`。
- **power**: effective K' で `categorical_multinomial_power(pooling=True, seed=20260708)`≥0.8、δ_min=0.10 TV。
- **observed shift**: 層別 within-context 置換検定（TV̄、seed=20260708）+ TV̄≥δ_min（reimagine v2、user 裁定）。
- **verdict schema（§CB4.4 5 分岐）**: DETECTED / NO_CHANNEL_CONFORMANCE(valid FAIL) /
  INCONCLUSIVE_UNDERPOWERED(非消費) / INCONCLUSIVE(非消費)。
- **think=False 強制**（H3、`bank.py:284`）/ 全 float 6 桁量子化（WSL byte 一致）/ tune-to-pass 封鎖。

## 実走後に記録（TBD）

- 日時 / platform / qwen3:8b digest / ollama version / VRAM / uv.lock sha256 / packages。
- `bank_checksum` / WSL replay byte 一致 / **verdict**（verdict.json）/ disposition（over-read guard §CB6）。
