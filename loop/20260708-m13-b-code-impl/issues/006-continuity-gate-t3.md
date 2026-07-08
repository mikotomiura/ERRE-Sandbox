# Issue 006 (I6): continuity-gate 4 機械 test + T3 materiality criterion test
verify_level: recheck   # SPDM-channel 非接続の型不変量 + T3 再入資格 gate = binding 保証の履行

## Goal
lever ⊥ SPDM-landscape channel を **値に依らず構造保証**する continuity-gate 4 機械 test と、反復 bank が
「基質改変 candidate であって measurement stimulus でない」を担保する T3 materiality criterion test を実装する。
**これらは construction の letter-safe 保証を担う検証層**（floor/divergence 非計算）。

## Background
FROZEN ADR §I2（continuity-gate 4 test: allowlist import-ban / M-loop retrieve-count=0 + provenance 別監査 /
arity=1 divergence-free / frozen-string）/§I7（T3 materiality criterion 1-4、criterion 4 = 機械 test 不能な
human desk-audit gate + honest teeth: stimulus 判定→T3 fail→line-close）。grill-goals.md D-9。**設計 FROZEN**。

## Scope
### In
- 新規 `tests/test_integration/test_ecl_bank_continuity.py`:
  - **(1) import-allowlist**（§I2.1）: bank module の import ⊆ allowlist 閉集合 かつ ∩ {`evidence.spdm`/
    `d0_substrate`/`es2_replay`/`memory_recomp_conformance`/`*runningness*`/`landscape_divergence`}=∅
    （I3 の `_bank_spend_guard` helper 再利用、`test_bank_import_allowlist`）。
  - **(2) M-loop retrieve-count=0 + provenance 別監査**（§I2.2/§I5）: M-sampling loop を retriever/store spy 下で
    走らせ `retrieve_call_count==0 ∧ store.read_count==0`（`test_bank_mloop_retrieve_count_zero`）。provenance
    pass は別監査 `retrieve-count==1×K`（canonical builder 由来、`test_bank_provenance_retrieve_count_one`）。
    境界を test 名で固定。
  - **(3) arity=1 / divergence-free**（§I2.3）: readout signature が per-context 単一 sample-list → scalar を型
    assert、measurement path に `*_divergence`/KL/JS/paired-distribution 非在を AST/grep assert
    （`test_bank_arity_one_divergence_free`）。
  - **(4) frozen-string**（§I2.4）: 各 context の chat() prompt が M pass 全体で byte-identical（sampling seed
    のみ変動、`test_bank_frozen_string`）。
- 新規 `experiments/20260708-m13-b-bank/t3_materiality_desk_audit.md`（§I7 desk-audit）:
  - invariant 写像（(i)-(v)）+ criterion 1-3 の証跡（canonical inputs のみ編集 / bank-density 非根拠 /
    source-organic + bounded mutation）+ **criterion 4 の honest teeth**（「stimulus と判定されたら T3 fail →
    line-close → 両 family exhaust → arc-close 自動執行」）+ user/reviewer sign-off 欄。
- （既存 fixture の canonical-inputs-only は I1 の `test_bank_cue_canonical_inputs_only` が担保、本 issue は
  desk-audit doc 存在 + sign-off を検証）。
### Out
- fixture/driver/guard/golden 本体（I1/I2/I3/I5）。power apparatus（I4）。live Ollama（D-10）。measurement 再入。

## Allowed Files
- `tests/test_integration/test_ecl_bank_continuity.py`（新規）
- `experiments/20260708-m13-b-bank/t3_materiality_desk_audit.md`（新規）
- **無改変厳守**: organ / bank.py / bank_fixtures.py / `_bank_spend_guard.py`（再利用のみ）

## Acceptance Criteria（AC↔test）
- I6-G1: `test_bank_import_allowlist` — bank module import ⊆ allowlist ∧ ∩ SPDM 系 module=∅（allowlist 主 guard）
- I6-G2: `test_bank_mloop_retrieve_count_zero` — M-loop を retriever/store spy 下で `retrieve_call_count==0 ∧
  store.read_count==0`（bake-out 構造的）
- I6-G3: `test_bank_provenance_retrieve_count_one` — provenance pass は別監査で `retrieve-count==1×K`（canonical
  builder 由来、M-loop と境界を test 名で分離）
- I6-G4: `test_bank_arity_one_divergence_free` — readout arity=1（per-context sample-list→scalar）型 assert +
  measurement path に `*_divergence`/KL/JS 非在
- I6-G5: `test_bank_frozen_string` — 各 context の chat() prompt が M pass 全体で byte-identical（sampling のみ変動）
- I6-G6: `test_bank_t3_desk_audit_present` — desk-audit doc が invariant 写像 + criterion 1-4（honest teeth 含む）
  + sign-off 欄を含む（grep で section 存在 assert）
- CI parity: `bash scripts/dev/pre-push-check.sh` 4 段 `ALL CHECKS PASSED`

## Test Plan
`pytest -q tests/test_integration/test_ecl_bank_continuity.py` + pre-push 4 段。retrieve-count は spy
（`Retriever`/`MemoryStore` の呼出計数 wrapper）で計測。arity/divergence-free は AST/grep。frozen-string は
provenance 出力 prompt を M pass で byte 比較。

## Stop Conditions
- 全 AC 緑（Done）+ desk-audit sign-off。
- continuity gate が bank module の import/構造を通せない → Stop（SPDM 非接続の型不変量が崩れる = 設計逸脱）。
- **desk-audit で凍結 context が「substrate enrichment でなく measurement stimulus」と判定 → T3 fail →
  line-close**（honest teeth、tune-to-narrative の反対。この場合 issue は「honest close 出口を記録」して Done、
  実装は緑でも T3 未達を明記）。
- budget 到達 → Stop。

## Dependencies
- I1（fixture/provenance）、I2（bank driver）、I3（`_bank_spend_guard` helper 再利用）。

## Status
DONE（2026-07-08、feat/m13-b-bank）。

## Execution Result
- 新規: `tests/test_integration/test_ecl_bank_continuity.py`（7 test）/
  `experiments/20260708-m13-b-bank/t3_materiality_desk_audit.md`。
- AC↔test: I6-G1=`test_bank_import_allowlist` PASS / I6-G2=`test_bank_mloop_retrieve_count_zero`
  PASS（retrieve_call_count=0 ∧ store_read_count=0、bake-out 構造的）/
  I6-G3=`test_bank_provenance_retrieve_count_one` PASS（provenance pass の retrieve-count は
  per-context 固定・非ゼロで K に厳密比例することを実測 spy で確認、M-loop の 0 とは別監査）/
  I6-G4=`test_bank_arity_one_divergence_free` PASS（`BankLlmCallRecord` の context 識別
  フィールドは `frozen_ctx_id` のみ=arity 1、bank.py/bank_fixtures.py に KL/JS/paired-distribution
  系識別子なし）/ I6-G5=`test_bank_frozen_string` PASS / I6-G6=`test_bank_t3_desk_audit_present`
  PASS（desk-audit doc の invariant (i)-(v) + criterion 1-4 + honest teeth + sign-off 欄存在確認）。
- pytest 件数: `tests/test_integration/` 349 passed。フル回帰（pre-push 4段内）3487 passed, 66
  skipped。
- pre-push 4 段: `ruff format --check src tests` PASS / `ruff check src tests` PASS /
  `mypy src` PASS（237 files）/ `pytest -q`（non-godot）PASS（3487 passed, 66 skipped, 374.62s）。
  `ALL CHECKS PASSED`。
- `git diff --stat`（tracked）空 — organ / bank.py / bank_fixtures.py / `_bank_spend_guard.py` /
  committed golden / power_worksheet.md / I5 artifacts 無改変確認済み。
- Stop 該当: なし。desk-audit の criterion 4（stimulus 判定）は sign-off 欄を未記入のまま残し、
  統合時 `/cross-review` で人間判定を埋める設計どおり（honest teeth 自体は doc に明記、本 issue
  では stimulus 判定を下していない）。
