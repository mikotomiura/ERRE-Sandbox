# 設計 — security-hardening-pre-m10 (final, post P0-P3 + Codex 13th)

## Status (2026-05-15 closure)

本 branch は **P0-P3 partial hardening** として close。元の 5 finding (§1〜§5) のうち
§3 / §4 / §5 が実装済、§1 / §2 は post-merge follow-up task に defer (Codex 13th
HIGH-5 の判定に従う)。

| Phase | ADR | Scope | Status | Commit |
|---|---|---|---|---|
| P0 | SH-0 | docs scaffold (requirement / design / decisions / tasklist / blockers / codex-12th-review-source.md) + AGENTS / .agents 微修正 | **DONE** | `f5295b5` |
| P1 | SH-3 | `.codex/config.toml` `network_access=false` split + `web_search=live` 据置 | **DONE** | `ad00499` |
| P2 | SH-4 | `cli/eval_run_golden.py --memory-db` symlink+prefix+overwrite guard + 5 unit test | **DONE** | `609037c` |
| P3 | SH-5 | `world/tick.py` 2-queue split (heartbeat coalesce + main drop-oldest + `runtime_backlog_overflow` warning) + 2 unit test | **DONE** | `9061173` |
| P4 | SH-2 | WS shared-token + Origin allow-list + session cap (3-layer auth) | **DEFERRED** | — |
| P5 | SH-1 | Codex hook + CI shell-bypass policy gate | **DEFERRED** | — |
| P6 | — | Codex 13th independent review (HIGH 5 / MEDIUM 2 / LOW 1, Verdict ADOPT-WITH-CHANGES) | **DONE** | `codex-review.md` |
| P6-fix | — | HIGH-1 / HIGH-3 / HIGH-5 反映 commit | **DONE** | (本 PR の追加 commit) |

### 不変条件 (Codex 独立 fact-check 済)

- `SCHEMA_VERSION = "0.10.0-m7h"` (`schemas.py:44`) 不変
- `data/eval/golden/` 30 cells 変更ゼロ (`git diff main..HEAD -- data/eval/golden` = empty)
- `src/erre_sandbox/evidence/` 変更ゼロ
- `ErrorMsg` schema 不変 (`code: str` に新値 `"runtime_backlog_overflow"` を入れるのみ、Literal/Enum 拡張なし)
- world → integration の逆向き import なし (`_make_runtime_error` を `tick.py` 内に私的定義)
- ruff / mypy / format clean、pytest 1378 passed / 32 skipped / 52 deselected

### M10-0 着手の go/no-go (Codex META-1 反映)

P4 (SH-2 WS auth) + P5 (SH-1 hook+CI) は M10-0 着手前に follow-up task で消化必須。
詳細は `blockers.md` の M10-0 gate セクション参照。

---

## v1 initial draft (履歴保持)

承認済み plan `/Users/johnd/.claude/plans/agile-chasing-sifakis.md` をもとに、
`.steering/_template/design.md` 構造で詳細化した v1。次ステップで `/reimagine`
を §2 (WS token+Origin+cap) + §5 (queue split) のみ適用、v2 と比較して
`design-final.md` に確定する。

## 実装アプローチ

Codex 12th review 5 件を **defense-in-depth × M9 baseline 不可侵** の二軸で消化する。

- **defense-in-depth**: §1 hook + CI / §2 token + Origin + cap / §3 network split /
  §4 path validation / §5 queue bound の **3 層独立** 化
- **M9 baseline 不可侵**: `data/eval/golden/` 30 cells + `src/erre_sandbox/evidence/`
  には触れない、`SCHEMA_VERSION` (`schemas.py:44` `"0.10.0-m7h"`) 不変
- **back-compat 優先**: WS token は `require_token=False` default、`/tmp/p3a_natural_*`
  default path 維持、`0.0.0.0` host default 据置 (Mac↔G-GEAR LAN rsync 保護)

各 finding は独立 commit、最終 1 PR squash で M10 着手前の baseline 完成。

## 変更対象

### 修正するファイル

**§1 hook + CI** (CI が最終防衛線、hook は first-line nuisance filter)
- `.codex/hooks.json:28-39` — `PreToolUse` matcher を `apply_patch|Edit|Write|exec_command|Bash` に拡張 (~5 行)
- `.codex/hooks/pre_tool_use_policy.py` — 新 helper `shell_write_targets(command)` (~50 行)、`.steering` completeness guard を shell 経路でも発火
- `.github/workflows/ci.yml` — 新 job `policy-grep-gate` を `eval-egress-grep-gate` (L83-137) の下に (~30 行)、ruff `T201` の backstop + `.steering` completeness check

**§2 WS auth** (3-layer independent: token + Origin + cap)
- `src/erre_sandbox/integration/protocol.py:52` 近傍 — `DEFAULT_ALLOWED_ORIGINS` + `MAX_ACTIVE_SESSIONS=8` を `Final` constant で追加 (~10 行)
- `src/erre_sandbox/integration/gateway.py:194-202` — `Registry.add()` を `reserve_slot()` / `release_slot()` に置換 (~20 行)、cap 超過時 `SessionCapExceededError` raise
- `src/erre_sandbox/integration/gateway.py:518-552` — `ws_observe()` の `accept()` (L545) 前に Origin/token/cap check を挿入 (~30 行)、close code 1008 (policy) / 1013 (try-again-later)
- `src/erre_sandbox/bootstrap.py:70-71` — `BootConfig` に `ws_token` / `require_token` / `allowed_origins` / `max_sessions` field 追加、`_resolve_ws_token()` helper (~30 行)
- `src/erre_sandbox/__main__.py:73-74` — `--ws-token` / `--require-token` / `--allowed-origins` / `--max-sessions` CLI flag 追加 (~15 行)

**§3 Codex network** (1-line config + doc)
- `.codex/config.toml:10` — `network_access = true` → `false`
- `.codex/config.toml:4` — `web_search = "live"` **据置** (decoupled feature)
- `AGENTS.md` — 新セクション "Network access policy"、SGLang v0.3+ multi-LoRA 発見実績 citation
- `.agents/skills/erre-workflow/SKILL.md` — 同ノート (machine-readable)

**§4 eval CLI path guard**
- `src/erre_sandbox/cli/eval_run_golden.py:711-775` 近傍 — `_resolve_memory_db_path()` helper + `ALLOWED_MEMORY_DB_PREFIXES` (~50 行)
- `src/erre_sandbox/cli/eval_run_golden.py:1029-1030` — unconditional unlink を helper 経由に
- `src/erre_sandbox/cli/eval_run_golden.py:1269-1292` — 既存 `--overwrite` 3-flag パターンに `--overwrite-memory-db` 追加

**§5 runtime queue**
- `src/erre_sandbox/world/tick.py:386` — `_envelopes` 単一 unbounded を `_heartbeat_envelopes` (maxsize=1 coalesce) + `_envelopes` (maxsize=1024 drop-oldest) の 2-queue に分割 (~10 行)
- `src/erre_sandbox/world/tick.py:722` — `inject_envelope()` の `put_nowait` を drop-oldest + ErrorMsg `runtime_backlog_overflow` warning に (~15 行)
- `src/erre_sandbox/world/tick.py:1271` — heartbeat 経路を coalesce 化 (~10 行)
- `src/erre_sandbox/world/tick.py:1340` — `_consume_result` も §5-2 と同型 (~15 行)
- `src/erre_sandbox/world/tick.py` `recv_envelope` — 2-queue race-merge (FIFO within priority class) (~20 行)

**Doc**
- `docs/architecture.md:330` — 「認証なし (LAN 内前提)」を「shared-token (opt-in) + Origin allow-list + session cap (LAN 内前提)」に
- `docs/development-guidelines.md` — `var/secrets/ws_token` rotate 運用ノート
- `README.md` — `mkdir -p var/secrets && chmod 700 var/secrets` 初回 provisioning 手順

### 新規作成するファイル

- `tests/test_codex_hooks/__init__.py`
- `tests/test_codex_hooks/test_shell_bypass_policy.py` — red-team 5 ケース
- `.steering/20260513-security-hardening-pre-m10/decisions.md` — ADR `SH-1`〜`SH-5`
- `.steering/20260513-security-hardening-pre-m10/codex-review-prompt.md` — Codex 13th 入力
- `.steering/20260513-security-hardening-pre-m10/codex-review.md` — Codex 13th verbatim 保存
- `.steering/20260513-security-hardening-pre-m10/design-final.md` — /reimagine 後の確定版

### 削除するファイル

なし。M9 baseline 不可侵。

## 影響範囲

| 領域 | 影響 | 対処 |
|---|---|---|
| Mac↔G-GEAR LAN rsync workflow | `require_token=False` default で **無影響** | tasklist で smoke 検証 |
| Godot 4.4 WS client | Origin/token 未対応の場合、loopback 経由は変更なし | empty Origin 受容 if-branch を実装時 audit |
| M9-eval golden baseline | **完全に触らない** | CI に `git diff origin/main..HEAD -- data/eval/golden` 検証 |
| existing pytest suite | gateway / tick / cli の signature 互換維持 | `Registry.add()` deprecation 経由で 1 リリース cycle 移行 |
| schema 互換 | `SCHEMA_VERSION` 不変、`ErrorMsg` の新 code `"runtime_backlog_overflow"` を流用 | schema bump 回避 |

## 既存パターンとの整合性

- **§2 reject-before-accept**: `gateway.py:523-543` の subscribe parse error path と同型
- **§2 drop-oldest + ErrorMsg warning**: `gateway.py:208-258` `Registry.fan_out` の既存実装 (helper `_make_error` も同所)
- **§4 path validation**: `cli/eval_run_golden.py:711-775` `_resolve_output_paths` の `.tmp` cleanup pattern
- **§4 3-flag escalation**: `cli/eval_run_golden.py:1269-1292` `--overwrite` / `--allow-partial-rescue` / `--force-rescue`
- **§5 bounded queue**: `integration/protocol.py:52` `MAX_ENVELOPE_BACKLOG = 256` の `Final[int]` 配置
- **§1 grep gate**: `.github/workflows/ci.yml:83-137` `eval-egress-grep-gate` の job 構造
- **§1 deny pattern**: `.codex/hooks/pre_tool_use_policy.py:11-24` の既存 deny rule set

## テスト戦略

### 単体テスト (新規 + 既存拡張)

- **§1**: `tests/test_codex_hooks/test_shell_bypass_policy.py` 5 ケース (sed/echo/tee/python-c/heredoc)
- **§2**: `tests/test_integration/test_gateway.py` 拡張 6 ケース (token miss/mismatch/match、origin reject、cap close 1013、back-compat default)
- **§4**: `tests/test_cli/test_eval_run_golden.py` 拡張 4 ケース (symlink/prefix/exists/overwrite)
- **§5**: `tests/test_world/test_runtime_lifecycle.py` 拡張 2 ケース (overflow warning、heartbeat coalesce)

### 統合テスト

- 既存 `test_gateway.py:193-210` `test_fan_out_drops_oldest_*` が runtime 側でも green を維持
- 既存 `test_multi_agent_stream.py` が token=None default で green

### E2E

- **Mac↔G-GEAR LAN smoke**: 手動 (decisions.md に手順記録)、`require_token=False` で
  既存 rsync workflow 不変を確認。token rotation の opt-in 検証は別 PR (Godot 4.4
  WS client patch が前提)
- **Codex hook smoke**: `echo '{...}' | uv run python .codex/hooks/pre_tool_use_policy.py` で
  deny 確認

## ロールバック計画

- §1: `.codex/hooks.json` matcher を `apply_patch|Edit|Write` に戻す (single commit revert)
- §2: `require_token=False` default なので enforce していない、`bootstrap.py` の
  config 削除 + `gateway.py` の auth gate コメントアウトで back-out
- §3: `.codex/config.toml` の `network_access` を `true` に戻す (1-line revert)
- §4: `_resolve_memory_db_path` を削除、L1029-1030 の unconditional unlink に戻す
- §5: `_envelopes` を `asyncio.Queue()` (unbounded) に戻す、`_heartbeat_envelopes` 削除

全 §i は独立 revert 可能。一括 PR を merge 後に問題発生時は **finding 単位で
revert PR** を出す方針。

## /reimagine 適用範囲 (次ステップ)

| § | /reimagine 適用 | 理由 |
|---|---|---|
| §1 hook + CI | **No** | CI grep gate は既存 `eval-egress-grep-gate` の port、単一案 |
| §2 WS auth | **Yes** | token 方式 / Origin allowlist 粒度 / cap 計算で複数案 |
| §3 Codex network | **No** | 1-line config 変更、単一案 |
| §4 path guard | **No** | 既存 `--overwrite` 3-flag パターンの port、単一案 |
| §5 queue split | **Yes** | 1-queue vs 2-queue vs 3-queue + drop policy で複数案 |

§2 + §5 の /reimagine 結果と本 v1 案を比較して `design-final.md` で確定 → 実装着手。
