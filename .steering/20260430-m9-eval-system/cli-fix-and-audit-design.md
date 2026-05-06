# CLI Fix + Audit CLI 設計サマリ — Phase 2 run0 incident 対応

> **scope**: 本ファイルは ME-9 ADR の design hand-off。**実装は本タスクで行わない**。
> 別タスク `m9-eval-cli-partial-fix` (`/start-task` で起票予定) に移管し、
> Plan mode + /reimagine + 着手前 Codex independent review を経て実装する。
> 本ファイルは hand-off 用 spec で、実装側 task の `requirement.md` の起点。

## 背景 (要約)

Phase 2 run0 で 3 cell が wall=360 min で FAILED (focal=381/390/399 prefix
censored)。Codex `gpt-5.5 xhigh` 6 回目 review が Claude 単独案の HIGH 4 件を
切出 (`codex-review-phase2-run0-timeout.md` verbatim)。本ファイルは Codex H3
(partial masquerade contract) と M3 (`eval_audit` CLI 未実装) 反映後の CLI
spec を示す。

## 1. CLI fix scope (`src/erre_sandbox/cli/eval_run_golden.py`)

### 1.1 `_SinkState` 拡張

```python
@dataclass
class _SinkState:
    total: int = 0
    focal: int = 0
    fatal_error: str | None = None    # 既存: DuckDB INSERT 失敗 / runtime drain failure
    soft_timeout: str | None = None   # 新設: wall timeout 到達 (graceful)
    last_zone_by_speaker: dict[str, str] = field(default_factory=dict)
```

`fatal_error` と `soft_timeout` は **mutually exclusive**:

- `fatal_error`: data corruption / I/O 失敗 / runtime drain timeout → rename refuse、
  return 2 (現状維持、Codex HIGH-3/HIGH-6 contract 維持)
- `soft_timeout`: 運用上の wall budget 到達 → rename ALLOW、sidecar 必須、return 3

### 1.2 `_watchdog` 修正

```python
async def _watchdog() -> None:
    while True:
        if state.fatal_error is not None: return
        if enough_event.is_set(): return
        if runtime_task.done(): return
        if time.monotonic() >= wall_deadline:
            state.soft_timeout = f"wall timeout ({wall_timeout_min} min) exceeded"
            # ← fatal_error には触らない (新分類)
            return
        await asyncio.sleep(0.5)
```

### 1.3 `CaptureResult` 拡張

```python
@dataclass
class CaptureResult:
    run_id: str
    output_path: Path
    total_rows: int
    focal_rows: int
    fatal_error: str | None = None
    # --- 新設 ---
    soft_timeout: str | None = None
    partial_capture: bool = False         # = soft_timeout is not None
    stop_reason: str = "complete"         # complete | wall_timeout | fatal_*
    drain_completed: bool = True          # runtime_task drain 成功
    runtime_drain_timeout: bool = False   # _RUNTIME_DRAIN_GRACE_S 超過の有無
    selected_stimulus_ids: list[str] = field(default_factory=list)
```

### 1.4 sidecar `.capture.json` schema

`<output>.capture.json` に以下を atomic write (DuckDB rename と同 fs、
temp+rename パターン):

```json
{
  "schema_version": "1",
  "status": "complete",            // complete | partial
  "stop_reason": "wall_timeout",   // complete | wall_timeout | fatal_<reason>
  "focal_target": 500,
  "focal_observed": 381,
  "total_rows": 1158,
  "wall_timeout_min": 360,
  "drain_completed": true,
  "runtime_drain_timeout": false,
  "git_sha": "85e02ea",
  "captured_at": "2026-05-06T12:00:00Z",
  "persona": "kant",
  "condition": "natural",
  "run_idx": 0,
  "duckdb_path": "/data/eval/phase2/kant_natural_run0.duckdb"
}
```

**unconditional write**: complete でも partial でも fatal でも sidecar は書く
(audit gate で機械的に区別するため)。fatal の場合のみ DuckDB rename を refuse
する点は現状維持。

### 1.5 `_async_main` return code 体系

```python
if result.fatal_error is not None:
    _write_sidecar(sidecar_path, status="fatal", stop_reason=...)  # sidecar も書く
    logger.error("capture FAILED (fatal): %s", result.fatal_error)
    return 2  # 現状維持
if result.soft_timeout is not None:
    _write_sidecar(sidecar_path, status="partial", stop_reason="wall_timeout", ...)
    atomic_temp_rename(temp_path, final_path)  # rename ALLOW
    logger.warning(
        "capture PARTIAL (wall timeout): focal=%d/%d, sidecar=%s",
        result.focal_rows, args.turn_count, sidecar_path,
    )
    return 3  # 新設: partial_publish
_write_sidecar(sidecar_path, status="complete", stop_reason="complete", ...)
atomic_temp_rename(temp_path, final_path)
logger.info("capture OK ...")
return 0
```

### 1.6 stale `.tmp` rescue (Codex H4 反映)

`_resolve_output_paths` の `.tmp.unlink()` 前に sidecar 確認:

```python
if temp.exists():
    sidecar = output.with_suffix(output.suffix + ".capture.json")
    if sidecar.exists() and not args.allow_partial_rescue:
        raise FileExistsError(
            f"stale .tmp found with sidecar (status={...}); "
            f"pass --allow-partial-rescue to delete, or rescue manually first"
        )
    temp.unlink()
```

新 flag `--allow-partial-rescue` は意図的 unlink を明示する safety gate。

## 2. `eval_audit` CLI (`src/erre_sandbox/cli/eval_audit.py`、新設)

### 2.1 用途

G-GEAR launch prompt が要求する audit gate (現 main に未実装、Codex M3)。
DuckDB file + sidecar を **両方** 検査して complete か機械的に判定。

### 2.2 spec

```bash
python -m erre_sandbox.cli.eval_audit \
    --duckdb data/eval/phase2/kant_natural_run0.duckdb \
    --focal-target 500 \
    [--allow-partial]   # diagnostic 用、default refuse
```

**判定ロジック**:

```python
def audit(duckdb_path: Path, focal_target: int, allow_partial: bool) -> int:
    sidecar = duckdb_path.with_suffix(duckdb_path.suffix + ".capture.json")
    if not sidecar.exists():
        return 4  # missing sidecar (= legacy or corrupt)
    meta = json.loads(sidecar.read_text())
    # row count cross-check
    with duckdb.connect(str(duckdb_path), read_only=True) as con:
        actual_rows = con.execute(
            "SELECT COUNT(*) FROM raw_dialog.dialog"
        ).fetchone()[0]
        actual_focal = con.execute(
            "SELECT COUNT(*) FROM raw_dialog.dialog "
            "WHERE speaker_persona_id = ?", [meta["persona"]],
        ).fetchone()[0]
    if actual_rows != meta["total_rows"]:
        return 5  # sidecar / DB mismatch
    if actual_focal != meta["focal_observed"]:
        return 5
    if meta["status"] == "complete" and actual_focal >= focal_target:
        return 0  # PASS
    if meta["status"] == "partial" and allow_partial:
        return 0  # diagnostic PASS (caller 明示)
    return 6  # FAIL: incomplete or partial without --allow-partial
```

### 2.3 batch mode (Phase 2 全体 sweep)

```bash
python -m erre_sandbox.cli.eval_audit \
    --duckdb-glob 'data/eval/phase2/*_run*.duckdb' \
    --focal-target 500 \
    --report-json audit-report.json
```

JSON report:
```json
{
  "audited_at": "...",
  "total": 30,
  "complete": 28,
  "partial": 1,
  "missing_sidecar": 0,
  "mismatch": 0,
  "fail": 1,
  "details": [...]
}
```

## 3. test 設計

### 3.1 unit (CLI fix)

- `test_capture_natural_wall_timeout_writes_sidecar`: stub runtime で wall=1s
  発火、sidecar `status=partial` 検証
- `test_capture_natural_fatal_keeps_tmp_no_rename`: DuckDB INSERT 失敗時、
  rename refuse + sidecar `status=fatal` 検証
- `test_capture_natural_complete_writes_sidecar_status_complete`: 正常完了、
  rename + sidecar `status=complete` 検証
- `test_resolve_output_paths_refuses_stale_tmp_with_sidecar`:
  `--allow-partial-rescue` 無しで stale unlink を refuse
- `test_async_main_return_code_partial`: focal_observed < target で wall timeout、
  return 3 検証

### 3.2 unit (`eval_audit` CLI)

- complete + focal_observed >= target → 0
- complete + focal_observed < target → 6
- partial + `--allow-partial` → 0
- partial without flag → 6
- missing sidecar → 4
- DB / sidecar row count mismatch → 5
- batch mode JSON report 出力検証

### 3.3 integration

- 実 ollama (mock client) で 30s wall timeout、partial sidecar + DB count
  一致を end-to-end 検証

## 4. 受け入れ条件 (`m9-eval-cli-partial-fix` task の definition of done)

1. `eval_run_golden.py` に上記 spec の改修、既存 tests (`test_eval_run_golden.py`)
   の rewrite 必要件は明示
2. `eval_audit.py` 新設 (single-cell + batch mode)
3. test suite 全 PASS、新規 unit 7-9 件追加 (CLI fix + audit)
4. PR description で本 spec ファイルへリンク、Codex independent review (本
   spec 起点) 結果を `codex-review-cli-fix.md` verbatim 保存
5. PR merge 後 `g-gear-p3-launch-prompt.md` を再 launch 想定に更新
   (wall budget + run1 calibration step + audit step)

## 5. 関連 reference

- ADR: `decisions.md` ME-9 (本 spec の確定 ADR)
- incident: `blockers.md` "active incident: Phase 2 run0 wall-timeout (2026-05-06)"
- Codex review: `codex-review-phase2-run0-timeout.md` (verbatim)
- Codex prompt: `codex-review-prompt-phase2-run0-timeout.md`
- Sample-size correction の前提 (HIGH-2 で破綻): `scripts/p3a_decide.py:360`
  iid sample-mean 近似
- HIGH-6 contract 出典: `eval_run_golden.py:36-39` (元の Codex P3a Step 1
  review HIGH-6)

## 6. 本タスク内で行う行動 (CLI fix 着手前の準備)

1. ✅ `codex-review-prompt-phase2-run0-timeout.md` 作成 (本 incident 起票)
2. ✅ `codex-review-phase2-run0-timeout.md` verbatim 保存
3. ✅ `.codex/budget.json` 更新 (281,778 tok / +81K overrun / warn)
4. ✅ `decisions.md` ME-9 ADR 追加
5. ✅ `blockers.md` active incident 追加
6. ✅ 本ファイル `cli-fix-and-audit-design.md` 起票
7. ⏳ G-GEAR rescue verify (`.tmp` + `.tmp.wal` 存在確認、別 G-GEAR セッション)
8. ⏳ `g-gear-p3-launch-prompt.md` 更新 (wall budget + run1 calibration step)
9. ⏳ commit ( + 関連 .steering ファイル) して本タスク内対応 close
10. ⏳ 別セッションで `/start-task m9-eval-cli-partial-fix` 起票、本 spec を
    `requirement.md` 起点として実装着手
