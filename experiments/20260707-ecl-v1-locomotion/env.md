# ECL v1 locomotion sealed run — environment / status

- **実験**: M13 ECL v1 = ES-3 locomotion→sampling チャネルのライブ活性化 (construction)
- **apparatus**: `scripts/ecl_v1_live_capture.py` (`--capture` / `--verify`) +
  `src/erre_sandbox/integration/embodied/live_v1.py`
- **ADR**: `.steering/20260707-ecl-v1-adr/design-final.md` (FROZEN、binding)

## status (2026-07-07、I3 sealed run 完了)
- **I3 sealed live run 実走済 = `artifacts/` に 4 handoff artifact + V4 annotation side file を commit。**
  real qwen3:8b、N=32 cognition × 20 physics = 640 world tick、locomotion 活性
  (seeded `LocomotionState(lam=0.0)`)、人手 sealed gate (2026-07-07、G-GEAR)。
- `run.sh` = live capture (要 live Ollama + qwen3:8b pull)。
- `repro.sh` = Ollama-free replay-verify (V2/V3a) + re-render (V3b) + V4a/V4b annotation side file
  (`channel_activation_annotation.json`、manifest SHA 集合外)。

## 実走環境 (I3、封印前 pre-register 固定・実走後 tuning ゼロ)
- **日時 / platform**: 2026-07-07、capture = Windows 11 native (PYTHONUTF8=1)、
  cross-platform verify = WSL2 Ubuntu 22.04 (glibc) + Windows (UCRT)。
- **qwen3:8b digest** (full): `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`
  (manifest pin = 16 文字 prefix `500a1f067a9f7826`、v0 踏襲)。
- **ollama**: 0.31.1 / **think**: False (`ThinkOffChatClient` 経由、cycle 無改変)。
- **VRAM**: 16311 MiB total (RTX 5060 Ti 16GB、manifest pin = 16.0 GB)。
- **uv.lock sha256** (full): `9cc70f9dc5d61f6c74c08dee4dd73815993861022a80781a75ef5d873860c0f7`
  (manifest pin = 16 文字 prefix `9cc70f9dc5d61f6c`)。
- **packages** (WSL/Win 一致): httpx 0.28.1 / pydantic 2.13.2 / python 3.11.15。
- **replay_checksum**: `f389a292d19340e5ce8f35f3562499c25222a1876729f510cb1ac0db318d626f`。

## verdict (§F、2026-07-07)
- **Done = V1∧V2∧V3a∧V3b HOLDS**:
  - **V1** 完走 = exit 0 で 4 artifact 生成 (decisions 32 / ecl_trace 640 / envelope 96 / manifest)。
  - **V2** replay 再現 = seeded state で committed decisions を replay → `replay_checksum` byte 一致 +
    `inner_invocations==0`。
  - **V3a/V3b cross-platform** = 同一 committed artifacts を **WSL Linux (glibc) と Windows (UCRT)** で
    `--verify` → replay_checksum byte 一致 + 全 artifact SHA + manifest byte-identical re-render 両 platform 一致
    (6桁量子化が libm drift 吸収、実測)。
- **channel-active annotation (非 gate、side file)**: **V4a distinct=29** (>1) / **V4b modulated=28** (≥1) /
  `checksums_match=True`。**V5 = 32/32** (全 tick `llm_status==ok`∧`plan≠None`∧`resolved_from==memory_centroid`)。
- **verdict = D4 → GO (construction validated、閉ループ発火)**。移動が実際に sampling を変調する live 器官を
  建設 (歩行→発散の計測でない)。measurement 非再入 (floor/landscape/verdict/D_loco/divergence 非出力、evidence
  非 import、R-budget=arc-wide 1 未消費、holding 不可侵)。λ0/persona/N の実走後 tuning ゼロ。

## 事前登録 (§F、ADR)
- **Done = V1∧V2∧V3a∧V3b** (reproducibility)。
- **V4a/V4b/V5 = annotation** (非 gate、side file、tune-to-pass 禁止)。**verdict なし**。
- V3b cross-platform byte 一致 (WSL Linux glibc / Windows UCRT) は I3 で実測
  (6桁量子化が libm drift を吸収、`feedback_golden_crossplatform_float_drift`)。

## 決定論
- replay は sampling 無視・checksum は幾何のみ → locomotion 活性化は新非決定源ゼロ (§E)。
- verify は **seeded state** で replay (Codex MEDIUM-2)。
- V4a/V4b は sampling-spy が recomposed per-tick sampling を捕捉 (Codex HIGH-1)。
