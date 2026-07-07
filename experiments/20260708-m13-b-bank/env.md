# M13 B — 反復 frozen-context bank golden — environment / status

- **実験**: M13 B（反復 frozen-context bank）Issue 005 — annotation side-file（opaque）+
  mock construction 検証 run + bank golden replay + cross-platform 記録欄
- **apparatus**: `scripts/ecl_bank_capture.py`（`--capture` / `--verify`）+
  `src/erre_sandbox/integration/embodied/bank.py`（I2）+
  `src/erre_sandbox/integration/embodied/bank_fixtures.py`（I1）
- **ADR**: `.steering/20260707-m13-b-impl-design/design-final.md`（FROZEN、binding、§I4/§I5）
- **裁定**: D-10（mock-only）— **live shakedown は OUT**。real Ollama を一切起動しない。
  本 golden は real qwen3:8b を含まない（I3 相当の sealed live run は本 issue の scope 外）。

## status（2026-07-08、I5 mock golden 完了）

- `artifacts/` に committed mock golden 3 ファイルを commit:
  `bank_records.jsonl`（K×M×2 = 16 件の `BankLlmCallRecord`、replay 用）/
  `bank_annotation.jsonl`（16 件の raw-row annotation、opaque）/ `manifest.json`。
- `run.sh` = mock capture（Ollama-free、K=`BANK_K_GOLDEN`=2、M=`BANK_M_GOLDEN`=4）。
- `repro.sh` = Ollama-free replay-verify（committed bank records のみから frozen context を
  再構成 → `BankRecordReplayClient.for_replay` で bake-out M-loop 再走 → byte 一致）。

## 実走環境（Windows native、mock-only ゆえ live capture 環境情報は非該当）

- **日時 / platform**: 2026-07-08、Windows 11 native（G-GEAR）。
- **python**: 3.11.15 / **packages**: httpx 0.28.1 / pydantic 2.13.2（`manifest.json` の
  `env_pins` に pin 済み、`--verify` は committed `env_pins` を再利用し再スナップショットしない）。
- **bank_checksum**: `ae6f67b0bc45424295185f3ba63e9fcc4f2886f3512345a516865c4f76c928ec`。
- **call_cap**: actual=16 / cap=16（`2·M·K` = `2*4*2`、§I4 fail-fast 境界に一致、超過なし）。

## cross-platform byte 一致（I5-G6、手動実測記録欄 — 本 subagent 実行対象外）

`feedback_golden_crossplatform_float_drift` 同手順（6 桁量子化が libm cos/sin drift を吸収する
はずだが、本 golden は幾何 float を含まない — sampling の 3 float（temperature/top_p/
repeat_penalty）のみが量子化対象で、zone-pick は categorical（Zone enum）ゆえ float 非感応）。

- **WSL Linux (glibc) 実測**: 未実施（main 統合時に手動実測、このセクションに追記）。
  手順: WSL2 上で `bash experiments/20260708-m13-b-bank/repro.sh` を実行し、
  `[verify] BANK GOLDEN OK` + 上記 `bank_checksum` と byte 一致することを確認。
- **Windows (UCRT) 実測**: 済（本 env.md 生成時、上記 `bank_checksum` が実測値）。

## 決定論

- provenance pass（K 回、各 2 condition、retrieve-count=1×K）と bake-out M-loop（K×M×2、
  retrieve-count=0）は別々の mock chat client で駆動（§I2 call-count 分離監査の construction 側精神）。
- `--verify` は committed `bank_records.jsonl` のみから K frozen context を再構成し
  （provenance pass も chat call も再実行しない）、`BankRecordReplayClient.for_replay` で
  bake-out M-loop を再走 → `inner_invocations == 0` + byte 一致（I5-G2）。
- annotation side-file は raw row のみ（`{frozen_ctx_id, condition, mc_index,
  pre_bias_destination_zone, resolved_from}`）。H/count/diversity/divergence は一切非計算
  （§I4、`BANK_ANNOTATION_SCHEMA_VERSION` = `ecl-bank-annotation-1`）。

## scope

construction であって measurement でない。floor/landscape/verdict/divergence 非計算、
`evidence`/`spdm`/`runningness` 非 import、R-budget 未消費、holding 不可侵。
