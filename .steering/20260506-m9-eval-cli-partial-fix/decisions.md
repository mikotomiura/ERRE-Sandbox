# 重要な設計判断 — m9-eval-cli-partial-fix

> Plan mode で確定した採用案 (案 A') と、Codex `gpt-5.5 xhigh` independent
> review (2026-05-06、tokens=151,853、Verdict: Adopt-with-changes) を経た
> HIGH/MEDIUM/LOW の採否記録。

## 判断 1: 採用案は 案 A' (案 A + Pydantic model_validator inline) ハイブリッド

- **判断日時**: 2026-05-06 (Plan mode)
- **背景**: ME-9 ADR で確定した「soft_timeout 分離 + sidecar + audit CLI」方針を
  実装する際、(a) 現 ADR 通りの minimal-change か、(b) lifecycle hook で contract
  layer を抽出するか、(c) ゼロ再生成 (DuckDB run_meta / event log) か、を選ぶ
- **選択肢**:
  - A: minimal-change (field 追加のみ)
  - B: enum + publisher 全抽出 (+250 LoC)
  - C-1: DuckDB run_meta table (sidecar 廃止)
  - C-2: event log + reducer (schema_version 跳ね上げ)
  - **A'**: A ベース + Pydantic `@model_validator` で mutual exclusivity 機械化
- **採用**: A'
- **理由**:
  - spec 1.4 sidecar v1 schema verbatim 互換、Codex review 7 回目を spec 起点で実施可能
  - 状態数 6 / 遷移 5 通りで案 B の enum 抽出は YAGNI
  - 案 C 系は spec 起票やり直し + Phase 2 既存 30 cell との混在運用不可
- **トレードオフ**: `_async_main` の 3-armed if-elif は許容、`_SinkState` field
  併存問題は validator で型保証
- **影響範囲**: `eval_run_golden.py` + 新規 `evidence/capture_sidecar.py` /
  `cli/eval_audit.py`
- **見直しタイミング**: M9-B `event_log` 拡張時、または partial publish の
  運用が複雑化したら案 B/C 系に refactor

## 判断 2: HIGH 2 件 (Codex H1/H2) を全反映

- **判断日時**: 2026-05-06 (Codex review 後)
- **背景**: Codex が「audit gate と complete 判定の 2 点は実装前に固めないと
  partial/fatal の誤採用余地が残る」と Adopt-with-changes 判定。CLAUDE.md
  「HIGH: 実装前に必ず反映」規約に従い設計を更新

### H1. audit が sidecar と DuckDB の同一 run 性を検証していない
- **採用**: 反映
- **変更**: `eval_audit.py` で `SELECT DISTINCT run_id FROM raw_dialog.dialog`
  を取得し、`f"{persona}_{condition}_run{run_idx}"` (sidecar の persona/
  condition/run_idx から組み立てた expected run_id) と一致しない場合 return 5
  (DB-sidecar mismatch) とする。`duckdb_path` は rsync 後に絶対 path が変わる
  ため補助情報扱いに留める

### H2. complete 判定が focal target 到達を必須にしていない
- **採用**: 反映
- **変更**:
  1. `_async_main` の complete branch (現 line 1190 周辺) に `result.focal_rows
     >= args.turn_count` 必須条件を追加。未達なら status=fatal、stop_reason=
     "fatal_incomplete_before_target"、return 2
  2. `runtime_task` の例外は `asyncio.wait_for` で再 raise されると sidecar を
     残さず落ちる risk があるため、try/except で捕捉して `state.fatal_error =
     f"runtime_task raised: {exc}"` に変換する
- **影響**: drain finally (1000-1010) と complete branch の双方を要修正

## 判断 3: MEDIUM 4 件の採否

### M1. `_SinkState` の Pydantic validator は assignment を保証しない
- **背景**: `_SinkState` は mutable で `fatal_error` / `soft_timeout` が生成後
  に代入される。通常 dataclass では `@model_validator` は効かず、
  Pydantic dataclass + `validate_assignment=True` が必要
- **選択肢**:
  - A: Pydantic v2 `pydantic.dataclasses.dataclass(config=ConfigDict(
    validate_assignment=True))` に切替
  - B: 平の dataclass + `set_fatal()` / `set_soft_timeout()` helper で runtime
    assertion (mutual exclusivity を helper 内で raise)
- **採用**: B
- **理由**: 既存 `eval_run_golden.py` は `@dataclass` 一貫のパターンで Pydantic
  を使っていない (`SidecarV1` が初の Pydantic 採用)。helper method で十分な
  runtime safety + 既存 readability 維持
- **影響**: `_SinkState` は @dataclass 維持、setter helper 2 個追加 (15 行程度)

### M2. drain grace 30s → 60s 推奨
- **背景**: cognition tick が約 120s なので 30s は in-flight tick の drain
  完了確率が低く、false fatal を増やす可能性
- **選択肢**:
  - A: 30s 維持 (現状)
  - B: 60s に引き上げ (P3 全体で +30s × N(cell) ≈ +15 min for 30 cells)
  - C: drain incomplete を partial publish に降格
- **採用**: B
- **理由**: B のコスト (15 min) は P3 全体 wall budget (run1=600 min cell × 30)
  と比べ無視可能 (0.08%)。false fatal 削減の安全性利得が大きい。
  C は Codex も「checkpoint/close 保証が弱い」として不採用推奨
- **影響**: `_RUNTIME_DRAIN_GRACE_S = 60.0` に変更、`runtime_drain_timeout=True`
  の field 記録は維持 (drain timeout は fatal 維持)

### M3. audit の direct DuckDB は許容、ただし `--report-json` 安全弁を定義
- **背景**: training egress guard 経由は不要 (COUNT のみ) だが、
  `--report-json` の出力先安全弁は別問題
- **選択肢**:
  - A: 何もしない (operator 責任)
  - B: `--report-json` を atomic write、batch exit code 順位付け、`data/eval/
    training/` 配下への出力を warn (refuse はしない)
  - C: `connect_analysis_view()` か evidence helper に COUNT ロジックを寄せる
- **採用**: B
- **理由**: B は cheap (atomic write は新規 helper を再利用、warn は path 検査
  のみ)。C は evidence/ 層への refactor を呼び範囲を広げる。今回は B で十分
- **影響**: `eval_audit.py` の report writer に atomic temp+rename 採用、
  training-ish path (`data/eval/training/` 下、または `training_view` keyword
  含む) で stderr warn

### M4. 壊れた sidecar の rescue は専用 `--force-rescue` flag
- **背景**: sidecar が存在するが Pydantic validation 失敗時、
  `--allow-partial-rescue` だけで unlink できると unknown state を消せる
- **選択肢**:
  - A: `--allow-partial-rescue` で OK (現案)
  - B: `--force-rescue` を別 flag として要求、status unknown を stderr 明示
- **採用**: B
- **理由**: 「silent 破棄を防ぐ」HIGH-4 の主旨により忠実。flag cardinality 増
  (+1) は許容範囲。stderr 表記で operator が unknown state を認識可能
- **影響**: `_resolve_output_paths` の sidecar 同居判定で
  `try: read_sidecar() except ValidationError: --force-rescue 必須`、
  validation 成功時は `--allow-partial-rescue` で unlink 許可

## 判断 4: LOW 3 件は今回採用 (cheap)

### L1. `selected_stimulus_ids` を planned list と明記
- **採用**: 反映
- **変更**: `CaptureResult.selected_stimulus_ids` の docstring に "planned
  list (replay reproducibility 用、実消費 subset とは無関係)" と明記。
  実消費 subset が必要な future task では別 field を追加

### L2. `stop_reason` Literal 化、`wall_timeout_min` の null 方針
- **採用**: 反映
- **変更**:
  - `SidecarV1.stop_reason: Literal["complete", "wall_timeout",
    "fatal_duckdb_insert", "fatal_ollama", "fatal_drain_timeout",
    "fatal_incomplete_before_target", "fatal_runtime_exception"]` で固定
  - `wall_timeout_min` は CLI 引数値を **常に記録** (natural / stimulus 共通、
    wall 発火しなくても CLI で渡された値を保存。partial / fatal / complete
    全 status で同じ値が入る)
  - `CaptureStatus = Literal["complete", "partial", "fatal"]` を `SidecarV1`
    と共有

### L3. `assert_never` は Literal helper がある場合のみ
- **採用**: L2 で `CaptureStatus` Literal を導入するため、`_async_main` の
  3 分岐 `match` + `assert_never` を採用 (網羅性検査)。元 plan 提案の
  3-armed if-elif は match expression に置換

## Codex Q&A 簡易記録

| Q | Codex 回答 | 採用判断 |
|---|---|---|
| Q1 drain grace | 60s 推奨、drain timeout fatal 維持 | M2 反映 (60s) |
| Q2 schema_version forward compat | A (extra="allow") + 明文化 | spec 通り、`extra="allow"` を `SidecarV1.model_config` に追加 |
| Q3 training egress guard | MEDIUM (direct DuckDB 許容) | M3 反映 (`--report-json` 安全弁追加) |
| Q4 selected_stimulus_ids | (a) 全 N 個 (planned list) | L1 反映 (docstring 明記) |
| Q5 force-rescue | B 推奨 (--force-rescue 別 flag) | M4 反映 (採用) |

## 変更後の design summary (反映後)

- `_SinkState`: `@dataclass` 維持、`set_fatal()` / `set_soft_timeout()` helper
- `_RUNTIME_DRAIN_GRACE_S = 60.0`
- `_async_main`: `match status:` + `assert_never`
- `runtime_task` 例外捕捉 → `state.fatal_error` 変換
- `complete branch`: `focal_rows >= turn_count` 必須
- `eval_audit`: `SELECT DISTINCT run_id` で同一 run 性検証 (return 5)
- `eval_audit`: `--report-json` atomic write + training-ish path warn
- `eval_audit`: `--force-rescue` 別 flag (sidecar validation 失敗時)
- `SidecarV1`: `stop_reason` Literal、`extra="allow"` for forward compat
- `CaptureStatus = Literal["complete", "partial", "fatal"]` 共有

## 判断 5: 第 2 round 内部 review 反映 (2026-05-06)

実装後 PR 直前に code-reviewer + security-checker subagent で内部レビュー。

### code-reviewer (HIGH 1 / MEDIUM 3)
- **HIGH-CR1** (`eval_run_golden.py:143`): orphan docstring literal の dead code
  → **採用 (即修正)**: docstring 統合済
- **MEDIUM-CR1**: `_SinkState.set_soft_timeout()` after `set_fatal()` の
  AssertionError 経路テスト不足
  → **採用**: `test_sink_state_set_soft_timeout_after_fatal_raises` 追加
- **MEDIUM-CR2**: wall→drain timeout escalation の統合テスト不足
  → **採用**: `test_sink_state_drain_timeout_after_wall_escalates_to_fatal` 追加
- **MEDIUM-CR3** (`eval_audit.py:216`): `_audit_batch` glob 0 件で silent EXIT_PASS
  → **採用**: glob 0 マッチで `logger.warning` (return code は破壊変更回避で維持)

### security-checker (CRITICAL/HIGH なし、MEDIUM 3 / LOW 4)
- **MEDIUM-Sec1** (`capture_sidecar.py:118`): DoS via large JSON sidecar
  → **採用**: `_SIDECAR_MAX_BYTES = 1 MB` の defensive cap を `read_sidecar` に追加
- **MEDIUM-Sec2** (`eval_run_golden.py:1396`): sidecar `duckdb_path` に絶対 path
  記録、OSF 公開時にローカルユーザー名漏洩リスク
  → **defer**: publish-time tooling で redact (本 CLI は local artefact 用)、
  `blockers.md` D-5 に記録
- **MEDIUM-Sec3** (`eval_audit.py:185`): training-ish path warn-only ポリシー
  → **defer**: 現状の意図的設計 (Codex M3)、`--strict` flag 将来追加は
  `blockers.md` D-6 に記録
- **LOW-Sec1-4**: パストラバーサル / `_git_sha_short` PATH 依存 / `extra=allow`
  キー数 / symlink 解決 → 個人研究環境のため現状維持で妥当

### 反映後の差分 (検証済)
- 1318 全 tests PASS (eval 31 件、+2 from MEDIUM-CR1/CR2)
- ruff / mypy clean
- diff: `_SIDECAR_MAX_BYTES` (+10 行)、`_audit_batch` warn (+9 行)、test 2 件
  (+60 行)、orphan docstring 削除 (-1 行)

## 関連参照

- Codex review: `codex-review-cli-fix.md` (verbatim、HIGH 2 / MEDIUM 4 / LOW 3)
- Codex prompt: `codex-review-prompt-cli-fix.md`
- Plan file: `~/.claude/plans/sleepy-fluttering-lake.md`
- 起点 spec: `.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md`
- ADR: `.steering/20260430-m9-eval-system/decisions.md` ME-9
