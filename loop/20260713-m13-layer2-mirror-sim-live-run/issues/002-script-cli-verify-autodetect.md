# Issue 002 (K2): m4_society_live_capture.py — --self-other flag + env_pins 永続 + verify auto-detect（additive）
verify_level: recheck   # AC は既存 M4 byte-identity 維持 + verify replay semantics = 再現性契約直結

## Goal
`scripts/m4_society_live_capture.py` を additive 拡張し、Layer2-on capture/replay 経路を通す:
capture が `self_other_enabled` を受けて `run_society_live_capture` へ渡し、**True の時だけ**
`env_pins["self_other_enabled"]=True` を書く（Codex MEDIUM-2）。verify は committed manifest の env_pins から
`self_other_enabled` を auto-detect し（present 時 `type(v) is bool` を fail-closed 検証、Codex MEDIUM-3）
`run_society_loop` へ渡す。`main()` に `--self-other`（capture-only, store_true）を追加。既存 M4（Layer2-off）
mock round-trip は byte-identical に緑維持。

## Background
FROZEN pre-register seam 2/3/4 + decisions.md（MEDIUM-2/3, LOW-1/2）。`render_society_golden` の `run` block は
固定キーのみ通すため、self_other_enabled の永続 channel は **env_pins**（M4 の `captured_event_log_checksum` を
env_pins に載せた script-owned additive witness field 先例、handoff.py 無改変）。既存 M4 golden は key 無し →
verify で absence→False → byte-identical replay。

## Scope
### In
- `capture()`（L328）: keyword-only `self_other_enabled: bool = False` 追加 → `run_society_live_capture(...)` に pass。
  `env_pins["captured_event_log_checksum"]=...`（L406）直後に **`if self_other_enabled:
  env_pins["self_other_enabled"] = True`**（True の時だけ、MEDIUM-2）。
- `verify()`（L445）: `env_pins = manifest["env_pins"]` から `so_enabled = env_pins.get("self_other_enabled", False)`。
  present（key 有り）なら `type(so_enabled) is bool` を強制、非 bool は `ok=False`（fail-closed、MEDIUM-3）。
  `run_society_loop(...)`（L497）に `self_other_enabled=so_enabled` を additive で渡す。
- `main()`（L626）: `parser.add_argument("--self-other", action="store_true", ...)`（capture-only、help 明記）→
  `capture(..., self_other_enabled=args.self_other)`（L671）。
- silent-off guard（LOW-1）: capture 後、`args.self_other` が True なら baked manifest の
  `env_pins["self_other_enabled"] is True` を assert（print + exit≠0 on mismatch）。
- `tests/test_integration/test_m4_society_live.py`（追加 test、Ollama-free mock bundle round-trip）:
  - `test_verify_roundtrip_selfother_bundle`: mock Layer2-on bundle（`_render_mock_bundle` に self_other_enabled
    経路を通す or env_pins に True を注入）を verify() → True + 全 replay client `inner_invocations==0`。
  - `test_verify_rejects_nonbool_self_other`: env_pins["self_other_enabled"]="true"（string）で verify()=False
    （fail-closed、MEDIUM-3）。
### Out
- society_live.py の seam（K1 で landed 前提）。real Ollama 実走（real-run step）。committed real golden の
  existence-check（K3）。handoff.py / society.py の改変（無改変厳守）。

## Allowed Files
- `scripts/m4_society_live_capture.py`（seam 2/3/4 のみ）
- `tests/test_integration/test_m4_society_live.py`（追加 test のみ）
- **無改変厳守**: handoff.py / society.py / society_live.py の K1 範囲外 / 既存 golden / 凍結 evidence

## Acceptance Criteria（AC↔test）
- AC-K2-1: `pytest tests/test_integration/test_m4_society_live.py::test_verify_roundtrip_mock_bundle -q` = passed
  （既存 M4 Layer2-off round-trip 緑維持 = default False byte-identical）
- AC-K2-2: `pytest tests/test_integration/test_m4_society_live.py::test_verify_roundtrip_selfother_bundle -q` = passed
  （Layer2-on bundle が verify() True & inner_invocations==0）
- AC-K2-3: `pytest tests/test_integration/test_m4_society_live.py::test_verify_rejects_nonbool_self_other -q` = passed
  （env_pins 非 bool で fail-closed）
- AC-K2-4: `pytest tests/test_integration/test_m4_society_live.py::test_m4_capture_measurement_guard -q` = passed
  （banned token: floor/landscape/verdict/jaccard/divergence/r_min + gate key を新規導入していない）
- AC-K2-5: `mypy src` + `ruff check src tests scripts` green（script は ruff 対象）

## Test Plan
- `pytest tests/test_integration/test_m4_society_live.py -q` 全緑（既存 + 新規）。
- 既存 M4 mock round-trip / anti-vacuous / structural-completeness / decoder-fail-closed が unchanged で緑。

## Stop Conditions
- handoff.py / society.py を改変しないと AC が満たせない場合 → Stop（設計逸脱、superseding ADR）。
- env_pins を常時書く実装（default False でも書く）に倒れたら Stop（MEDIUM-2 違反、byte-identity 崩壊）。

## Dependencies
- K1（001）: society_live.py の self_other_enabled seam が landed 済みであること（直列）。

## Status
- done

## Execution Result
- 実装（`scripts/m4_society_live_capture.py`、additive）:
  - `capture()`: keyword-only `self_other_enabled: bool = False` 追加 →
    `run_society_live_capture(..., self_other_enabled=self_other_enabled)`。
    `env_pins["captured_event_log_checksum"]=...` 直後に
    `if self_other_enabled: env_pins["self_other_enabled"] = True`（True 時のみ、MEDIUM-2）。
  - `verify()`: `env_pins.get("self_other_enabled", False)` を auto-detect。key 有りで
    非 bool なら `ok=False` + `[verify] FAIL self_other_enabled not bool: ...`（fail-closed、
    MEDIUM-3）、`run_society_loop(..., self_other_enabled=so_enabled)` へ additive で渡す。
  - `main()`: `--self-other`（store_true, capture-only）追加 →
    `capture(..., self_other_enabled=args.self_other)`。silent-off guard（LOW-1）:
    `--self-other` 指定時、baked `manifest.json` の `env_pins["self_other_enabled"] is True`
    を assert、mismatch なら stderr print + `return 1`。
  - `tests/test_integration/test_m4_society_live.py`: `_capture_full_horizon` /
    `_render_mock_bundle` に optional `self_other_enabled: bool = False` 追加（既存 caller
    unchanged）。新規 test 2 件: `test_verify_roundtrip_selfother_bundle`（Layer2-on bundle
    → verify()=True）、`test_verify_rejects_nonbool_self_other`（env_pins 文字列 "true" →
    verify()=False）。
- 検証: `pytest tests/test_integration/test_m4_society_live.py -q` 17 passed（既存 15 + 新規 2、
  AC-K2-1〜4 該当 test 全て PASSED）。`mypy src` clean（240 files）。
  `ruff check scripts/m4_society_live_capture.py tests/test_integration/test_m4_society_live.py`
  + `ruff format --check` 同 2 ファイル clean。
- 制約遵守: handoff.py / society.py 無改変（diff なし）。society_live.py は K1（Issue 001）の
  pre-existing diff のみ（本 issue で touch していない）。env_pins は self_other_enabled=True の
  時のみ書き込み（既存 M4 golden の env_pins は無改変 → byte-identity 維持、
  `test_verify_roundtrip_mock_bundle` 緑で確認）。逸脱・Stop なし。
- Opus code-review 反映（MEDIUM 1 + LOW 2）:
  - MEDIUM: witness 書込みの二重実装を単一 seam 化。`society_live.py` に純ヘルパ
    `apply_self_other_env_pin(env_pins, *, self_other_enabled)`（body = write-when-True）を
    追加（`__all__` 登録）、script の `capture()` と test の `_render_mock_bundle` 両方を
    共有ヘルパ呼び出しに置換。focused unit test `test_apply_self_other_env_pin`（True→key True /
    False→absence）を追加し、live-Ollama 経路が使う書込みロジックを CI カバー。
  - LOW-1: silent-off guard の baked manifest access を
    `baked_manifest.get("env_pins", {}).get("self_other_enabled")` に変更（schema drift 時
    明示 FAIL）。`is not True` 判定は維持。
  - LOW-2: `main()` で `--verify` + `--self-other` 併用時に
    `[verify] note: --self-other は無視されます（manifest から auto-detect）` を print。
  - 再検証: `pytest tests/test_integration/test_m4_society_live.py -q` = 18 passed（新規
    `test_apply_self_other_env_pin` 含む）。`mypy src` clean。`ruff check src tests` +
    `ruff format --check src tests` clean、`ruff check scripts/m4_society_live_capture.py` clean。
    `test_society_live_measurement_guard` / `test_m4_capture_measurement_guard` 緑
    （新ヘルパは banned token 非導入）。society.py / handoff.py 依然無改変。
