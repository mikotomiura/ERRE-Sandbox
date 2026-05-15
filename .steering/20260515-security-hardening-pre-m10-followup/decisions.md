# 設計判断 — security-hardening-pre-m10-followup

本 task は **親 task `.steering/20260513-security-hardening-pre-m10/decisions.md` の SH-1 / SH-2 ADR をそのまま実装する** ため、新 ADR を立てない。以下は親 ADR の verbatim 引用 (linkback 付き) + 開始時 fact-check の記録 + 本 task 中に発生した implementation-level 判断 (ADR addendum 形式)。

---

## SH-1 (親 task verbatim 引用) — Hook + CI shell-bypass defense

Source: `.steering/20260513-security-hardening-pre-m10/decisions.md` SH-1

- **判断日時**: 2026-05-13
- **背景**: `codex_issue.md` §1 HIGH。`.codex/hooks.json:28-39` matcher が `apply_patch|Edit|Write` のみ、`exec_command` 経由の shell 書き込みが `.steering` completeness guard / banned import check を通過する。
- **選択肢**:
  - A: hook matcher 拡張のみ (`exec_command|Bash` 追加)
  - B: CI grep gate 追加のみ (`policy-grep-gate` job)
  - **C**: hook + CI の両層
- **採用**: **C**
- **理由**:
  - hook 単独 (A) は `apply_patch` 偽装で素通り、bypass risk が残る
  - CI 単独 (B) は feedback latency が遅い (PR push 後)、IDE 内即時 deny の UX を失う
  - 両層 (C) は既存 `eval-egress-grep-gate` (`ci.yml:83-137`) が同型パターンとして validated、defense-in-depth 完成
- **トレードオフ**: 開発時の hook 誤検知 (false positive) リスク増。red-team test 5 ケースで pattern 妥当性を担保
- **影響範囲**: `.codex/hooks/` + `.github/workflows/ci.yml` + 新規 `tests/test_codex_hooks/`
- **見直しタイミング**: red-team test で誤検知率 >5% に達した場合、または CI grep gate が M9-eval / m9-c-spike 系の正当なツール使用をブロックした場合

---

## SH-2 (親 task verbatim 引用) — WebSocket 3-layer auth (token + Origin + cap)

Source: `.steering/20260513-security-hardening-pre-m10/decisions.md` SH-2

- **判断日時**: 2026-05-13
- **背景**: `codex_issue.md` §2 MEDIUM。`__main__.py:73-74` / `bootstrap.py:70-71` default `0.0.0.0:8000`、`integration/gateway.py:501-652` `ws_observe()` に認証 / Origin / session cap いずれもなし。Mac↔G-GEAR LAN rsync workflow は LAN 内前提だが、共有 Wi-Fi 誤公開時の blast radius が無制限。
- **選択肢** (Plan agent enumeration + AskUserQuestion):
  - **A. Token rollout: back-compat 優先** (`require_token=False` default、Godot patch を別 PR、enforce は後続)
  - B. Token rollout: 同一 PR 強制 (P4 で Godot WS client patch も含める)
  - C. Token rollout: Godot 免除 list (loopback の Godot は token 不要)
- **採用**: **A** (ユーザー選択、2026-05-13 AskUserQuestion)
- **理由**:
  - A は blast radius 最小 (Godot 未パッチでも continue)、PR 単位の独立性高い
  - B は Godot patch を blocker 化、本 PR scope 拡大 + Godot live test 必要で工数 +5h
  - C は認証ロジック分岐増、SH-2 の "3 layer independent" 原則を破る
- **トレードオフ**: A 採用で token 機構は **存在するが強制しない** 初期状態、別 PR で `require_token=True` default 化が必要。記録: `tasklist.md` に follow-up task 起票
- **追加判断**:
  - **`MAX_ACTIVE_SESSIONS = 8`** (Mac+G-GEAR Godot + curl + slack + M10 per-persona UI × 3、4 では tight、16 は memory waste で却下、AskUserQuestion 結果)
  - **Token storage**: file `var/secrets/ws_token` primary + env `ERRE_WS_TOKEN` fallback + explicit `--ws-token` arg は test のみ (`ps -E` leak 回避)
  - **Origin allowlist**: 空 list ⇒ check disabled (Godot native WS empty Origin 対応)、`host=0.0.0.0` + empty origin + `require_token=False` は startup error で誤公開予防
- **棄却**:
  - mTLS (運用負荷過大、cert rotate 必要)
  - cookie auth (Godot native WS が cookie 非対応)
  - `127.0.0.1` 強制 (Mac↔G-GEAR LAN rsync workflow 実害)
- **影響範囲**: `__main__.py` / `bootstrap.py` / `integration/gateway.py` / `integration/protocol.py` / `docs/architecture.md` / `README.md` / `docs/development-guidelines.md` / `tests/test_integration/test_gateway.py`
- **見直しタイミング**:
  - Godot 4.4 WS client が token 対応した時点で `require_token=True` default 化の follow-up PR
  - `MAX_ACTIVE_SESSIONS=8` が M11 で不足判明した場合、cap 値 reopen
  - LAN 外公開要件が発生した場合 (M14+? OSF 公開時)、mTLS 検討

---

## SH-FOLLOWUP-1 — `deny()` exit code 解釈の確定

- **判断日時**: 2026-05-15 (本 task 開始時 fact-check)
- **背景**: 起点プロンプト `.steering/20260513-security-hardening-pre-m10/next-session-prompt-followup.md` Step 3 の hook smoke 検証で「exit 2 + deny message」を期待していたが、実機 `pre_tool_use_policy.py:37` の `deny()` は **exit 0 + JSON `permissionDecision:"deny"`** を返す (Codex 公式 hook protocol)。
- **選択肢** (AskUserQuestion):
  - **A**: JSON deny を維持、smoke 検証を JSON match に修正 (Recommended、ユーザー採用)
  - B: `deny()` を return 2 に変更 + JSON も併用
  - C: プロンプト通り exit 2 のみ (JSON 廃止)
- **採用**: **A**
- **理由**:
  - 現実装は Codex 公式 `permissionDecision: "deny"` JSON 構造を採用、reason 文字列が structured で telemetry 親和性が高い
  - B は二重化だが既存 `deny()` 呼出箇所 (4 箇所) の挙動は実用上変わらず、変更 cost に見合わない
  - C は structured reason を捨てる退行
- **トレードオフ**: hook smoke 検証手順がプロンプト本文と異なる (`jq -e '.hookSpecificOutput.permissionDecision == "deny"'`)。本 ADR で記録、Codex 14th review prompt にも明記
- **影響範囲**: `tests/test_codex_hooks/test_shell_bypass_policy.py` の assert は stdout JSON match、`.steering/20260513-security-hardening-pre-m10/next-session-prompt-followup.md` Step 3 hook smoke 行は本 task 後 stale 化 (修正不要、`git rm next-session-prompt.md` 同梱で発生する `next-session-prompt-followup.md` も同様に close 時に処理判定)
- **見直しタイミング**: Codex CLI の hook protocol が future version で exit code based に強制移行した場合

---

## SH-FOLLOWUP-2 — CI policy-grep-gate の T201 backstop 設計

- **判断日時**: 2026-05-15 (本 task 開始時 fact-check)
- **背景**: 親 task design-final.md L67 で `grep -rnE '^\s*print\s*\(' src/erre_sandbox/` を T201 backstop として設計していたが、Bash fact-check で `src/erre_sandbox/inference/ollama_adapter.py:145` に既存の **noqa なし raw print()** が存在することが判明。CI は現状 green なので ruff 側に何らかの allow 経路がある (file-level skip or pyproject extra exemption の可能性)。
- **選択肢** (AskUserQuestion):
  - **A**: ruff と同等の例外 (cli/** 除外 + 行 noqa 尊重) — `uv run ruff check --select T201 src/erre_sandbox` 再実行で代替 (Recommended、ユーザー採用)
  - B: 厳格 grep で全 print() を block (既存 `ollama_adapter.py:145` も対象、本 PR で `# noqa: T201` 追加か `logger.debug` 置換必要)
  - C: print rule は CI grep から外す、import 禁止と `.steering` completeness のみ grep
- **採用**: **A**
- **理由**:
  - 既存 CI green を破壊しない (retro-active breakage なし)
  - ruff exemption は pyproject + per-line noqa で集約管理、CI grep で重複 enforce すると drift risk
  - SH-1 design-final.md L67 「ruff T201 の backstop」要件は、grep ではなく ruff 自身の冪等再実行でも満たされる (CI 内別 job で実行 = backstop)
- **トレードオフ**: 厳格 grep より弱い ("ruff 自身の bug" が backstop で検出できない)。ruff version pin と CI step 順序で品質保証
- **影響範囲**: `.github/workflows/ci.yml` `policy-grep-gate` job の print step は `uv run ruff check --select T201 src/erre_sandbox` に。grep は openai/anthropic + bpy + `.steering` completeness のみ
- **見直しタイミング**: ruff `T201` が future version で削除 / rename された場合、または `ollama_adapter.py:145` を本来正しく block すべき判断が後日発生した場合 (別 task で audit)

---

## SH-FOLLOWUP-3 — (placeholder)

Codex 14th review で MEDIUM 切出時にここに ADR addendum を追加する。

---

## Mac↔G-GEAR LAN smoke 手順 (P4d 必須、SH-2 ADR の見直しタイミングに関連)

`require_token=False` default で既存 rsync workflow が不変であることを実機で確認:

```bash
# Mac 側 (本 PR の branch)
uv run python -m erre_sandbox --host 0.0.0.0 --port 8000 \
  --personas study/peripatos --check-ollama false &
SERVER_PID=$!
sleep 3

# G-GEAR 側 (curl で WS handshake without token)
curl -i -N \
  -H "Connection: Upgrade" -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
  -H "Sec-WebSocket-Version: 13" \
  http://mac.local:8000/observe
# Expected: 101 Switching Protocols (require_token=False なので token 不要)

kill $SERVER_PID
```

本 smoke は手動。`tests/test_integration/test_gateway.py::TestWebSocketAuth::test_back_compat_no_token_required_by_default` で代替自動化済 (single-host TestClient 経由)。
