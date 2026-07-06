# Issue 003 (γ): RNG run-sequence + checksum canonical + 最終単一 re-bake + version bump — P1(B-1)+C(B-4)
verify_level: recheck   # golden 再生成 + reproduction 契約 (version/checksum) 変更ゆえ独立再検証

## Goal
(1) `EclRecordMode` に mutable `_rng_cache` memoize (get-then-assign) を入れ RNG を run-sequence 化 (P1)。
(2) `ecl_trace_checksum` に `separators=(",",":")`+`ensure_ascii=False`+`allow_nan=False` を inline し
CANONICAL_JSON_RULES と統一・非有限は raise (C)。(3) `MANIFEST_SCHEMA_VERSION` `-1→-2` bump +
manifest に `replay_checksum_algorithm`/`replay_checksum_json_rules` 出力。(4) **α・β を main merge した後**、
`scripts/ecl_v0_golden.py --bake` を **単一回**実行し committed golden を再生成 + AC2 expected checksum 更新。

## Background
FROZEN ADR §3.1 (P1) + §3.5 (C) + §4 (re-bake/version)、Codex LOW (get-then-assign/setdefault 不可・
docstring 修正) + MEDIUM-1 (ensure_ascii) + LOW (manifest checksum-rule fields)。frozen `policy.py:363` の
「run 毎 1 度生成・sequence 消費」idiom 写経。loop→handoff は循環ゆえ `canonical_dumps` import 不可 → inline。
γ で単一 bake ゆえ {P1 trace 値変化 + C checksum bytes + W artifact SHA 決定化 + β decisions.jsonl 波及} を
一括捕捉、cross-issue 順序ハザード構造的不発生。**α・β merge 後に着手 (γ last)。設計 FROZEN。**

## Scope
### In
- `embodiment.py` `EclRecordMode`: `_rng_cache: dict[tuple[str,str], random.Random] = field(default_factory=dict,
  compare=False, repr=False)` 追加。`substream` を get-then-assign memoize (setdefault 不可)。docstring の
  "lightweight config" → "deterministic handle を持つ record-mode runtime object" へ修正。
- `loop.py` `ecl_trace_checksum`: `json.dumps(canonical, sort_keys=True, separators=(",",":"),
  ensure_ascii=False, allow_nan=False)` に。`DETERMINISM_CHECKLIST` の「distinct sort_keys-only」注記を
  「canonical 統一」へ更新 (handoff.py 側)。
- `handoff.py` `MANIFEST_SCHEMA_VERSION` `-1→-2` + `build_manifest` に `replay_checksum_algorithm="sha256"` +
  `replay_checksum_json_rules` (canonical rules) 出力。
- `scripts/ecl_v0_golden.py --bake` 単一回 → `tests/fixtures/ecl_v0_golden/` の 4 artifact 再生成。
- `tests/test_integration/test_ecl_handoff.py` AC2 強化: expected checksum 更新 + `rendered["decisions.jsonl"]
  == committed` を assert (W pin 済ゆえ byte 安定、D-γ1) + `:174-186` 注記更新。
### Out
- measurement 再入 (holding 不可侵)。
- α/β の scope (P2/W/R は α・β で完了済前提)。

## Allowed Files
- `src/erre_sandbox/cognition/embodiment.py`
- `src/erre_sandbox/integration/embodied/loop.py` (`ecl_trace_checksum` のみ)
- `src/erre_sandbox/integration/embodied/handoff.py` (`MANIFEST_SCHEMA_VERSION` / `build_manifest` / checklist 注記)
- `tests/fixtures/ecl_v0_golden/*` (再生成 golden、4 artifact)
- `tests/test_cognition/test_ecl_embodiment.py` (γ-G1 RNG sequence)
- `tests/test_integration/test_ecl_loop.py` (γ-G2 checksum canonical drift-pin)
- `tests/test_integration/test_ecl_handoff.py` (γ-G3 version/fields + γ-G4 AC2 強化)

## Acceptance Criteria (AC↔test マッピング)
- γ-G1 (P1): `test_ecl_record_mode_rng_is_run_sequenced` 緑 — `substream(agent,"micro")` 反復呼が同一 `Random`
  (memoize) → per-tick jitter distinct>1、同 run_id の 2 EclRecordMode で draw 列 byte 一致
- γ-G2 (C): `test_ecl_trace_checksum_canonical_rules` 緑 — `ecl_trace_checksum` が separators/ensure_ascii=False/
  allow_nan=False 適用・非有限 float は raise + loop-checksum の canonicalization が `CANONICAL_JSON_RULES` と
  同一である drift-pin
- γ-G3 (version): `test_manifest_version_and_replay_checksum_fields` 緑 — `MANIFEST_SCHEMA_VERSION=="ecl-v0-handoff-2"`
  + manifest `replay_checksum_algorithm=="sha256"` + `replay_checksum_json_rules` 存在
- γ-G4 (re-bake): `test_ecl_v0_handoff_golden_sample_matches` 強化版緑 — 新 golden で checksum 一致 **かつ
  `rendered["decisions.jsonl"] == committed`** + `test_ecl_v0_golden_rebake_is_deterministic` (α-G6) 緑
- γ-G5 (verify): `python scripts/ecl_v0_golden.py --verify` exit 0 (新 committed golden)
- γ-G6 (2x-bake Stop gate): `--bake` 相当 2 回で全 4 artifact SHA 一致 (非決定なら Stop→未 pin source 特定)
- γ-G7 CI parity: `bash scripts/dev/pre-push-check.sh` 4 段全 pass

## Test Plan
`pytest -q tests/test_cognition/test_ecl_embodiment.py tests/test_integration/` → α・β merge 済 main で
`scripts/ecl_v0_golden.py --bake` 単一回 → `--verify` exit 0 → 全 regression + pre-push CI parity。
verify=recheck ゆえ loop-watchdog が pin 済 golden test を独立再実行。

## Stop Conditions
- 全 AC 緑 + golden re-bake 決定的 (Done)
- 2x-bake 非決定 (未 pin wall-clock/RNG/clock 残存) → Stop
- checksum canonical 変更が想定外の consumer 契約 test を壊す → 調査→Stop
- budget 到達 (Stop)

## Dependencies
- **α (Issue 001) + β (Issue 002) を main merge 済であること (γ last、binding)**。α の loop.py/handoff.py 変更 +
  β の retrieval.py 変更を land した後の main で single re-bake するため。

## Status
QUEUED (blocked on α+β merge)

## Execution Result
(完了時に記入)
