# Mutation log — Loop I-001b (contract fix: Stage1 tri-state + ScopeVerdict field + InternalReference owner + section anchors)

- **日時**: 2026-09-08
- **対象**: `scripts/paper01_scope_condition.py`（本 issue が触った差分のみ）
- **検証範囲**: `pytest -q tests/test_paper01_scope`（AC 001-1..001-9 + 001b-1..001b-8 全 15 test）
- **手法**: `feedback_witness_needs_mutation_testing` の規律に従い、判定行/契約を機械的に
  1 箇所ずつ壊す mutant を当て、test が落ちる (kill) か確認する。各 mutant で
  `assert old in s` → `assert new != old` → 書込み → `assert new in on_disk` → verify 実行 →
  復元 → **復元後の byte 一致を SHA-256 で assert**、の手順を自動化したハーネスで実施
  (`C:\Users\johnd\AppData\Local\Temp\claude\C--ERRE-Sand-Box\f33f2702-2785-4497-8a5a-f5a9ee7b5619\scratchpad\mutate_001b.py`)。
- **注意 (ツール側の学び)**: 本ファイルは Windows チェックアウトで一貫して CRLF
  (595/595 行が `\r\n`、bare LF 0)。`pathlib.Path.write_text()` のデフォルト
  universal-newline 変換に頼ると、`\n` 空間での mutate → 書込み → 復元の往復で
  意図せず改行コードが正規化され、**内容は正しいのに SHA-256 不一致になる**
  false failure を最初に踏んだ (M1 の 1 回目の試行)。修正: 読込時に `\r\n → \n` を
  明示変換してマッチングし、書込み時に `\n → \r\n` を明示変換してから
  raw bytes で書く方式に変更し、以後は正しく動作した。

## Mutant 一覧 (11 件、生存 0)

| # | 対象 | 変更内容 | 期待 kill 理由 (AC) | 結果 | kill した test |
|---|---|---|---|---|---|
| M1 | `STAGE1_OUTCOME_ENUM` | `"INCONCLUSIVE"` → `"DEFLATION_REJECTED"` (issue 001b-MUT 名指しの mutant。3 状態を 2 状態に潰す) | 001b-1, 001b-4, 001-2/001-3 | **KILLED** | `test_config_matches_preregistration`, `test_config_mismatch_is_detected`, `test_stage1_outcome_enum_is_frozen`, `test_inconclusive_is_not_rejection` |
| M2 | `STAGE1_OUTCOME_ENUM` | 先頭 2 要素を入れ替え (順序破壊) | 001b-1 (順序込み凍結) | **KILLED** | `test_config_matches_preregistration`, `test_config_mismatch_is_detected`, `test_stage1_outcome_enum_is_frozen` |
| M3 | `Stage1Result` | `drop_p5_eligible` フィールドを削除 | 001b-3, 001b-8 | **KILLED** | `test_shared_result_contracts_are_frozen`, `test_stage1_result_contract_is_extended`, `test_inconclusive_is_not_rejection` |
| M4 | `Stage1Result` | `n_objects_pool_short: int` → `float` (型のみ改変) | 001b-3, 001b-8 | **KILLED** | `test_shared_result_contracts_are_frozen`, `test_stage1_result_contract_is_extended` |
| M5 | `ScopeVerdict` | `t_confound_note_required` フィールドを削除 | 001b-5, 001b-8 | **KILLED** | `test_shared_result_contracts_are_frozen`, `test_scope_verdict_contract_is_extended` |
| M6 | `InternalReference` docstring | 所有者を I-006 → I-002 に差し戻し | 001b-6 | **KILLED** | `test_internal_reference_owner_is_i006` |
| M7 | 節 anchor | I-002 anchor ブロックを削除 | 001b-7 | **KILLED** | `test_section_anchors_exist_in_order` |
| M8 | 節 anchor | I-003 と I-004 の anchor 順序を入れ替え | 001b-7 | **KILLED** | `test_section_anchors_exist_in_order` |
| M9 | `Stage1Result` | `frozen=True` → `frozen=False` | 001b-8 | **KILLED** | `test_shared_result_contracts_are_frozen` |
| M10 | `ScopeVerdict` | `frozen=True` → `frozen=False` | 001b-8 | **KILLED** | `test_shared_result_contracts_are_frozen` |
| M11 | `collect_preregistration()` | `"stage1_outcome_enum"` キー登録を削除 | 001b-1, 001b-2 | **KILLED** | `test_config_matches_preregistration`, `test_config_mismatch_is_detected`, `test_stage1_outcome_enum_is_frozen` |

**生存 mutant: 0 / 11。**

## AC 001b-MUT の核心 mutant (M1) の確認

issue 本文が名指しした mutant ("`INCONCLUSIVE` を `DEFLATION_REJECTED` に写す") は M1。
**4 本の test に同時に落ちる** ことを確認した。特に `test_inconclusive_is_not_rejection`
(AC 001b-4 の専用 test) が、`mod.STAGE1_OUTCOME_ENUM` から値を読んで
`Stage1Result` インスタンスを構築する構造になっているため、
この mutant で `inconclusive.stage1_outcome == rejected.stage1_outcome`
(両方とも `"DEFLATION_REJECTED"` に潰れる) となり、
`assert inconclusive.stage1_outcome != rejected.stage1_outcome` で失敗する
— これが「判定不能が棄却に潰れたら test が落ちる」の直接証拠。

## 出力 JSON の意味突き合わせ (mutation 後の追加工程)

`experiments/20260908-paper01-scope-condition/config.json` を再生成後、実読みして
`design-final.md` §9 (frozen pre-registration table) および新規
`stage1_outcome_enum` と 1 対 1 で突き合わせた:

- `stage1_outcome_enum`: `["DEFLATION_SUPPORTED", "DEFLATION_REJECTED", "INCONCLUSIVE"]`
  — design-final.md §3 Stage 1 の表 (:165) が凍結した「判定不能として記録」の語彙と一致。
  3 値・この順序であることを確認 (`test_stage1_outcome_enum_is_frozen` が pin)。
- 既存 8 キー (`seed` / `tau_grid` / `stage1_replicates` / `stage1_draw_index` /
  `stage1_internal_good_counts` / `stage1_internal_drop_ref` / `delta_ts_candidates` /
  `delta_material_eps` / `fail_precedence` / `scope_verdict_enum` / `thresholds`) は
  値が無変更であることを diff で確認 (`git diff` は `stage1_outcome_enum` の
  5 行追加のみ)。**余分なキー追加・既存値の意図しない変化はゼロ**。
- 意味欠落の再発防止チェック: `Stage1Result` / `ScopeVerdict` の新規フィールドは
  すべて issue 001b の Scope In 表と名前・型が完全一致することを
  `test_stage1_result_contract_is_extended` / `test_scope_verdict_contract_is_extended`
  で個別 pin 済み (G1 の反省 — 全 test 緑・全 mutant kill でも意味欠落が
  JSON を読んで初めて見つかった、を再演しないための工程)。

## 復元確認

全 11 mutant 適用後、`scripts/paper01_scope_condition.py` を SHA-256 で
mutation 前の on-disk バイト列と比較し、**完全一致**を確認
(`final restore hash match: True`)。mutation 後の最終 sanity run
(`pytest -q tests/test_paper01_scope`) も exit 0 (15 passed)。
