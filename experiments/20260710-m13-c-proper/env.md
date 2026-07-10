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

## 実走記録（2026-07-10、封印後 tuning ゼロ）

- **日時**: capture 2026-07-10 09:36→12:20 UTC（≈2h44m、4800 real qwen3 draws）。**platform**: Windows 11 native
  (PYTHONUTF8)。
- **qwen3:8b digest** (full): `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`。
  **ollama**: 0.31.1 / **think**: False（`bank.py:284` 強制）。**VRAM**: 16311 MiB total（16.0 GB pin）。
  **uv.lock sha256**: `9cc70f9dc5d61f6c74c08dee4dd73815993861022a80781a75ef5d873860c0f7`。
- **integrity（verify）**: bank_records/annotation sha256 = manifest 一致 / replay byte 一致
  （`inner_invocations==0`）/ **bank_checksum** `5e991dd6340778196f79c3ba579224e41b55e27647c64ec3694b0648ca6f71fb` /
  records↔annotation row key 一致。scorer は integrity 全 PASS 後に 1 回適用（seal）。
- **cross-platform 決定性**: verdict は **categorical zone**（float 非感応）ゆえ platform 間で自明に同一。permutation は
  numpy PCG64 + seed=20260708（libm 非依存）、TV 比較 9 桁・出力 6 桁量子化、verify は replay round-trip
  （libm 再計算なし）→ byte 一致は構造的保証（ECL v1 **I5-G6** で同一コード経路の WSL glibc⇔Windows UCRT byte 一致を
  実測済）。fresh WSL 環境が deps 欠落のため empirical 再走は非実施（構造保証済機序の再確認ゆえ proportionate 判断、
  honest 記録）。

## verdict（§CB4.4、one-shot・seal）

- **verdict = `NO_CHANNEL_CONFORMANCE`（valid FAIL、= effect-absence の relocated 判定 §CB4.4 branch (b)）**。
- **readouts**（`artifacts/verdict.json`）: rho_hat=**1.0**（8/8 context が (i) PASS、H 0.63–0.75 bit）/ power=**1.0**
  （effective K'=8）/ **tv_bar=0.0381 < δ_min=0.10**（floor 未達）/ permutation **p=0.058 > α=0.05**（非有意、
  reject=False）/ tv_pool=0.0086 / per-context TV 0.010–0.055 / none_rate_max=0.123。
- **決定的意味**: (i) PASS が rho=1.0 で成立 = **substrate は ≥2 zone を license した（H>0）**。壁1&4 の
  「near-uniform=低検出力」は **empirical に反証**（near-uniform base で power=1.0）。死点は §CB2.3 の予言どおり
  **achievable delta_tv→0**（think=False regime で T_on/T_off の zone 分布がほぼ同一、実測 tv_bar≈0.038）。
- **disposition**: valid FAIL → live-channel-conformance family bounded-close（R-budget=1 消費）→ SPDM-landscape
  [SPENT] と両 exhaust → **arc-close 自動執行**（arc §4.3 ratchet）。**over-read guard §CB6**: これは
  effect-absent measurement であって ✗「live channel が zone を偏らせない／substrate 否定／H4 否定／中核命題 否定」
  ではない（第2リンク detectability の否定のみ、firing⇔detectability 分離、5 機序分離、organic 非一般化）。
