# 設計 — m9-eval-cli-partial-fix

> **status**: EXECUTED (2026-05-06、PR pending)
> Verdict: Adopt-with-changes (HIGH 2 / MEDIUM 4 / LOW 3 全反映)
> 実装結果: 1316 全 tests PASS / ruff / mypy clean / Codex review HIGH 全反映
>
> 承認 plan file: `~/.claude/plans/sleepy-fluttering-lake.md`
> 起点 spec: `.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md`
> 採否記録: `decisions.md` (本タスク内)

## 採用案: 案 A' (案 A + Pydantic model_validator inline)

### 構造的ポイント (Codex review 反映後)
- `_SinkState` / `CaptureResult` を **field 拡張** で改修 (新 module 抽出はしない)
- mutual exclusivity は **平の `@dataclass` + `set_fatal()` / `set_soft_timeout()`
  helper** で runtime assertion (Codex M1 採用、Pydantic dataclass は採らず
  既存 pattern との整合を優先)
- sidecar I/O は新規 `evidence/capture_sidecar.py` に集約 (約 100 LoC、
  `atomic_temp_rename` 再利用)。`SidecarV1` のみ Pydantic v2、
  `model_config = ConfigDict(extra="allow")` で forward compat (Codex Q2)
- `CaptureStatus = Literal["complete", "partial", "fatal"]` を共有型として導入、
  `_async_main` は `match status:` + `assert_never` で網羅性検査 (Codex L3)
- `_RUNTIME_DRAIN_GRACE_S = 60.0` に引き上げ (Codex M2、cognition tick ~120s に
  対し 30s は false fatal を増やす懸念)
- `eval_audit.py` は **self-contained** で `duckdb.connect(..., read_only=True)`、
  `--report-json` は atomic write + training-ish path warn (Codex M3)
- 同一 run 性検証 (Codex H1): `SELECT DISTINCT run_id` を `f"{persona}_{condition}
  _run{run_idx}"` と比較、不一致は return 5
- complete 判定強化 (Codex H2): `focal_rows >= turn_count` 必須、`runtime_task`
  例外捕捉 → fatal_error 変換、未達なら `stop_reason="fatal_incomplete_before_target"`
- stale `.tmp` rescue は 2 段 flag (Codex M4):
  - sidecar validation 成功 → `--allow-partial-rescue` で unlink
  - sidecar validation 失敗 (壊れた sidecar) → `--force-rescue` を別途要求

### 不採用案 (記録のみ)
- **案 B (enum + publisher 全抽出)**: state 数 6 個 / 遷移 5 通りで YAGNI、
  +250 LoC の認知負荷増分が機械的型保証 (案 A' で 15 行で達成済) の利得を上回らない
- **案 C-1 (DuckDB run_meta table)**: spec 1.4 sidecar schema 非互換、
  Phase 2 既存 30 cell との混在運用不可
- **案 C-2 (event log + reducer)**: schema_version 跳ね上げで Codex spec
  起票やり直し、+750 LoC で本タスクの minimal-change 期待を逸脱

詳細比較マトリクスは Plan agent 出力 (Phase 2) を `~/.claude/plans/sleepy-fluttering-lake.md`
の "Recommended Approach" 節に転記済。

## 変更対象 (file:line + 方向性)

### 修正
| Anchor | 変更方向 |
|---|---|
| `src/erre_sandbox/cli/eval_run_golden.py:135` (`_RUNTIME_DRAIN_GRACE_S`) | `30.0` → `60.0` (Codex M2) |
| `eval_run_golden.py:207-218` (`_SinkState`) | `soft_timeout: str \| None = None` 追加 + `set_fatal()` / `set_soft_timeout()` helper で mutual exclusive を runtime assert (Codex M1)。@dataclass 維持 |
| `eval_run_golden.py:191-204` (`CaptureResult`) | `soft_timeout / partial_capture / stop_reason / drain_completed / runtime_drain_timeout` 5 field 追加。`selected_stimulus_ids` の docstring に planned list と明記 (Codex L1) |
| `eval_run_golden.py:978-996` (`_watchdog`) | wall timeout 分岐 (993) を `state.set_soft_timeout(...)` に切替、`fatal_error` 触らず |
| `eval_run_golden.py:1000-1010` (drain finally) | `state.fatal_error or ...` を `if not state.soft_timeout: state.set_fatal(...)` 条件付き上書きに修正。`runtime_task` の例外を try/except で捕捉 → `state.set_fatal(f"runtime_task raised: {exc}")` (Codex H2) |
| `eval_run_golden.py:599-614` (`_resolve_output_paths`) | `allow_partial_rescue: bool` + `force_rescue: bool` 引数追加。sidecar 同居 + validation 成功時は `--allow-partial-rescue` で unlink、validation 失敗時は `--force-rescue` を要求 (Codex M4) |
| `eval_run_golden.py:1034-` (`_build_arg_parser`) | `--allow-partial-rescue` / `--force-rescue` 2 flag 追加 |
| `eval_run_golden.py:1135-1200` (`_async_main`) | `match status:` + `assert_never` (Codex L3)、complete branch は `result.focal_rows >= args.turn_count` 必須 (Codex H2)、未達なら status=fatal + stop_reason="fatal_incomplete_before_target" + return 2、partial: rename allow + return 3、fatal: rename refuse + return 2、全分岐で sidecar **unconditional write** |
| `eval_run_golden.py:872-883` (Ollama 早期 return) | sidecar status=fatal + stop_reason="fatal_ollama" を必ず書く |
| `eval_run_golden.py:470` (DuckDB INSERT) | 既存 `state.fatal_error = ...` を `state.set_fatal(...)` に置換 |
| `tests/test_cli/test_eval_run_golden.py` | `test_resolve_output_paths_*` (101-125) の rewrite + 新規 5 件 + 例外捕捉テスト 1 件 |
| `.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md:188-201` | audit step を新 contract (return 0/4/5/6 + sidecar + run_id 検証 + wall budget=600 + run1 calibration step) で更新 |

### 新規
- `src/erre_sandbox/evidence/capture_sidecar.py` (約 100 LoC)
  - `CaptureStatus = Literal["complete", "partial", "fatal"]` 共有型
  - `StopReason = Literal["complete", "wall_timeout", "fatal_duckdb_insert",
    "fatal_ollama", "fatal_drain_timeout", "fatal_incomplete_before_target",
    "fatal_runtime_exception"]` (Codex L2)
  - `SidecarV1` Pydantic v2 BaseModel (spec 1.4 schema 準拠)
    - `model_config = ConfigDict(extra="allow")` (forward compat、Codex Q2)
    - `status: CaptureStatus`、`stop_reason: StopReason`
    - `wall_timeout_min: int` (常に CLI 値を記録、Codex L2)
  - `write_sidecar_atomic(path: Path, payload: SidecarV1) -> None`
    (`evidence/eval_store.py:402` の `atomic_temp_rename` 再利用)
  - `read_sidecar(path: Path) -> SidecarV1` (validation 失敗は `ValidationError`)
- `src/erre_sandbox/cli/eval_audit.py` (約 280 LoC)
  - `main()` 単独 entry (既存 4 CLI と同形式)
  - argparse: `--duckdb` / `--duckdb-glob` / `--focal-target` / `--allow-partial`
    / `--report-json` / (内部) training-ish path warn
  - single-cell return:
    - 0 (PASS): complete + focal>=target、または partial + `--allow-partial`
    - 4: missing sidecar (legacy 互換、明示区別)
    - 5: DB-sidecar mismatch (`total_rows` / focal カウント / **run_id** Codex H1)
    - 6: incomplete (complete + focal<target) または partial without `--allow-partial`
  - DuckDB は self-contained `duckdb.connect(str(path), read_only=True)`
  - batch: glob 展開 + JSON report **atomic write** (Codex M3)、batch exit code は
    最も悪い single result (max() rule) を採用、training-ish path 出力時は stderr warn
- `tests/test_cli/test_eval_audit.py` (audit 8 件 = spec 7 + run_id mismatch 1)
- `tests/test_evidence/test_capture_sidecar.py` (4 件、schema validation +
  atomic round-trip + Literal 検証 + extra=allow forward compat)

## 影響範囲

- caller の `eval_run_master_runner` は **存在しない** ため Python 内 caller 影響ゼロ
- 外部影響は `g-gear-p3-launch-prompt.md` の更新のみ
- 既存 capture (sidecar なし) は `eval_audit` が return 4 で明示的に区別、
  legacy 互換性破壊なし

## 既存パターンとの整合性

- atomic temp+rename: `evidence/eval_store.py:402-424` `atomic_temp_rename` を再利用
- DuckDB read-only: `evidence/eval_store.py:225` の `connect_training_view` 系
  パターンを self-contained で再現
- CLI 構造: 既存 `main()` 単独 entry 4 件 (eval_run_golden / baseline_metrics /
  export_log / scaling_metrics) と同形式
- test fixture: `tests/test_cli/test_eval_run_golden.py:133-151` `_stub_text_inference` /
  `:234, 253` broken-sink monkeypatch を再利用
- Pydantic schema: `schemas.py` の ControlEnvelope 等と異なり、eval/capture
  文脈に閉じる discriminated union 型は `evidence/capture_sidecar.py` に局所配置

## テスト戦略

### 単体 (`pytest -q tests/test_cli/test_eval_run_golden.py
tests/test_cli/test_eval_audit.py tests/test_evidence/test_capture_sidecar.py`)
- CLI fix 6 件: wall_timeout sidecar / fatal keeps tmp / complete sidecar /
  resolve_output_paths refuses stale tmp (allow_partial_rescue 系) /
  resolve_output_paths refuses corrupted sidecar (force_rescue 系、Codex M4) /
  async_main return 3 / **runtime_task exception 捕捉 → fatal 変換 (Codex H2)** /
  **complete branch focal_rows 未達で fatal 変換 (Codex H2)**
- audit 8 件: complete-pass / complete-fail / partial-allow / partial-refuse /
  missing-sidecar / DB-mismatch (rows) / **run_id-mismatch (Codex H1)** /
  batch-json (atomic + max() exit code)
- sidecar 4 件: schema validation / atomic round-trip / Literal 違反は
  ValidationError / extra=allow で未知 field を許容

### 統合 (任意)
- 実 runtime + mock client、wall=2s 強制で end-to-end 1 件

### E2E
- 不要 (CLI 単体タスク、Phase 2 run1 calibration は別タスク)

## ロールバック計画

- 単一 PR (squash merge 想定)、revert で完全復元
- sidecar v1 は forward-compatible: `schema_version` 読みで future v2 を warning skip
- 既存 capture (sidecar なし) は audit が return 4 で明示区別、legacy 互換性破壊なし

## Phase 0: 着手前 Codex review (本 design.md に対して実施)

### 投げる 5 個の疑問点

1. **drain timeout grace 30s の妥当性** (`_RUNTIME_DRAIN_GRACE_S = 30.0` at
   eval_run_golden.py:135)
2. **sidecar schema_version の forward compat 戦略** (Pydantic discriminated
   union + `extra="allow"` の採否)
3. **`eval_audit.py` の training egress guard 経由可否** (本 Plan は self-contained
   確定だが structural safety として再考する余地)
4. **partial publish 時の `selected_stimulus_ids` の扱い** (subset vs 全 list)
5. **`--allow-partial-rescue` の安全装置強度** (sidecar 自身が壊れていた場合の
   graceful degradation policy)

### 起動コマンド
```bash
cat .steering/20260506-m9-eval-cli-partial-fix/codex-review-prompt-cli-fix.md \
    | codex exec --skip-git-repo-check
```

出力は `codex-review-cli-fix.md` に **verbatim** 保存。HIGH 全反映、MEDIUM 採否を
`decisions.md` に追記、LOW は `blockers.md` 持ち越し可。

## 関連参照

- spec hand-off: `.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md`
- ADR: `.steering/20260430-m9-eval-system/decisions.md` ME-9
- incident review (Codex 6 回目): `.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.md`
- 承認 plan file: `~/.claude/plans/sleepy-fluttering-lake.md`
