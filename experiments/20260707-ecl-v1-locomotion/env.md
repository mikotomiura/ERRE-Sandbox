# ECL v1 locomotion sealed run — environment / status

- **実験**: M13 ECL v1 = ES-3 locomotion→sampling チャネルのライブ活性化 (construction)
- **apparatus**: `scripts/ecl_v1_live_capture.py` (`--capture` / `--verify`) +
  `src/erre_sandbox/integration/embodied/live_v1.py`
- **ADR**: `.steering/20260707-ecl-v1-adr/design-final.md` (FROZEN、binding)

## status (2026-07-07、Phase 1 完了時点)
- **`artifacts/` は空 (I3 待ち)。** I3 = sealed live run (real qwen3:8b、N=32、
  locomotion 活性) は **人手 sealed gate の別セッション**で実走し artifact を commit する
  (user 裁定 2026-07-07)。本 scaffold は Phase 1 (I1/I2/I4) の apparatus 完成分。
- `run.sh` = live capture (要 live Ollama + qwen3:8b pull)。
- `repro.sh` = Ollama-free replay-verify (V2/V3a) + re-render (V3b) + V4a/V4b annotation side file
  (`channel_activation_annotation.json`、manifest SHA 集合外)。
- I3 実走日が 2026-07-07 と異なる場合、dir 名を実走日にリネーム可
  (`docs/experiment-tracking.md` 規約)。

## 事前登録 (§F、ADR)
- **Done = V1∧V2∧V3a∧V3b** (reproducibility)。
- **V4a/V4b/V5 = annotation** (非 gate、side file、tune-to-pass 禁止)。**verdict なし**。
- V3b cross-platform byte 一致 (WSL Linux glibc / Windows UCRT) は I3 で実測
  (6桁量子化が libm drift を吸収、`feedback_golden_crossplatform_float_drift`)。

## 決定論
- replay は sampling 無視・checksum は幾何のみ → locomotion 活性化は新非決定源ゼロ (§E)。
- verify は **seeded state** で replay (Codex MEDIUM-2)。
- V4a/V4b は sampling-spy が recomposed per-tick sampling を捕捉 (Codex HIGH-1)。
