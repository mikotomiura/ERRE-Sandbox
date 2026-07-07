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

- **WSL Linux (glibc) 実測**: **本機 (G-GEAR) では未実施** — インストール済み WSL は Ubuntu-22.04 だが
  **WSL1** かつ `/root/erre-sandbox` に synced repo/venv が無く、feat/m13-b-bank の checkout + 依存構築が
  未整備のため、本統合セッションでは empirical な WSL 実測を行えなかった（honest 記録）。
- **cross-platform 一致の analytical 論拠（float drift risk ≈ 0）**: 本 golden の committed artifact は
  **libm 由来の幾何 float を一切含まない** — bank_records の float は sampling の 3 値
  （temperature/top_p/repeat_penalty）のみで、これらは persona default sampling の**固定定数**（cos/sin 等の
  platform 依存 libm 演算を経ない）。zone-pick は categorical（Zone enum → 文字列）ゆえ float 非感応。∴
  Windows(UCRT) と Linux(glibc) の bake は byte-identical になるはず（`feedback_golden_crossplatform_float_
  drift` が対象とする sub-ULP drift の発生源が本 golden に存在しない）。
- **effective Linux 検証（CI）**: `test_bank_golden_replay_checksum` / `test_bank_golden_categorical_byte_
  stable` は CI（Linux glibc）で走り、committed golden の replay checksum 一致を Linux 上で確認する（committed
  bytes の Linux 上での読取・checksum 一致 = replay 決定性の cross-platform 確認）。ただし Linux 上での
  **再 bake** byte 一致は本 test では検証しない（replay-only）。
- **残タスク（I5-G6 の empirical closure）**: 上記 analytical 論拠で risk はほぼゼロだが、empirical に閉じるには
  (a) WSL2 or Linux 実機で `bash experiments/20260708-m13-b-bank/repro.sh` を実行し `bank_checksum` byte 一致を
  確認するか、(b) golden 再 bake test を Linux CI に追加する、のいずれか。**TASK-POST /cross-review + user 裁定**へ。
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
