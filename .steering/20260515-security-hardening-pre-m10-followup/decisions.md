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

Codex 14th HIGH-1 で SH-2 startup gate が既存 Godot LAN workflow を破壊することが判明。escape hatch `--allow-unauthenticated-lan` (SH-FOLLOWUP-3 参照) を使って既存 workflow が不変であることを実機で確認する:

```bash
# Mac 側 (本 PR の branch)
uv run python -m erre_sandbox \
  --host 0.0.0.0 --port 8000 \
  --allow-unauthenticated-lan \
  --skip-health-check \
  --personas kant,nietzsche,rikyu &
SERVER_PID=$!
sleep 3

# G-GEAR 側 (curl で WS handshake without token / without Origin)
curl -i -N \
  -H "Connection: Upgrade" -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
  -H "Sec-WebSocket-Version: 13" \
  http://mac.local:8000/ws/observe
# Expected: 101 Switching Protocols (--allow-unauthenticated-lan なので token / Origin 不要)
# Server log は "SH-2 unsafe LAN dev posture acknowledged" WARNING を含む

kill $SERVER_PID
```

本 smoke は手動。`tests/test_integration/test_gateway.py::TestWebSocketAuth::test_back_compat_no_token_required_by_default` で代替自動化済 (single-host TestClient 経由、`make_app` 直接ルートなので startup gate は通らない)。

## SH-FOLLOWUP-3 — Codex 14th HIGH-1 `--allow-unauthenticated-lan` escape hatch

- **判断日時**: 2026-05-15 (Codex 14th review 反映)
- **背景**: Codex 14th HIGH-1 が指摘 — SH-2 startup gate (`host=0.0.0.0` + 全 3 gate 無効を `RuntimeError` で拒否) は Godot LAN workflow を破壊する。Godot 4.6 native WS client は Origin header を送信しないので `--allowed-origins=...` は実質機能せず、`--require-token` は Godot 側 WS client patch (`feat/ws-token-enforce` follow-up task) を待つ必要がある、`--host=127.0.0.1` は Mac↔G-GEAR LAN 破壊で実害。
- **選択肢**:
  - **A**: Godot WS client を本 PR で patch して token 送信対応 → scope 大幅拡大、Godot live test 必要、`feat/ws-token-enforce` を本 PR に merge する形
  - B: Godot 用に Origin 免除分岐を追加 → SH-2 ADR の "3 layer independent" 原則破る
  - **C** (採用): 明示的 escape hatch `--allow-unauthenticated-lan` を追加し、loud warning ログを毎起動出す。Godot patch が landing したら `feat/ws-token-enforce` PR でこの flag を deprecate → 削除する 2-PR sequence
- **採用**: **C**
- **理由**:
  - A は本 PR scope (security hardening + M10-0 gate 解除) を大きく超え、Godot live testing が必要で工数 +5h 以上
  - B は 3-layer 独立性を毀損し、将来別 client (Slack bridge / dashboard) が同様 exception を要求する伝統を作る risk
  - C は startup gate の安全性原則 ("unsafe combo は consent 必須") を守りつつ、運用上の現実 (Godot 未パッチ) を妥協する。loud warning で hide 不可
- **トレードオフ**:
  - Empty `--allow-unauthenticated-lan` flag は SH-2 ADR の "consent 必須" 原則を字義的に満たすが、運用上は "知らぬ間に on になってる" risk が残る (CI doc 参照すれば確認できる)
  - Godot 4.6 WS client が token 対応するまで本 flag が事実上 default になる可能性。`feat/ws-token-enforce` PR で deprecate + 削除の 2-PR sequence を `tasklist.md` に記録
- **影響範囲**: `bootstrap.py` `BootConfig.allow_unauthenticated_lan` + `_validate_ws_auth_config` bypass、`__main__.py` `--allow-unauthenticated-lan` flag、`docs/development-guidelines.md` / `README.md` 更新、`.steering/20260515-.../decisions.md` 本 ADR addendum
- **見直しタイミング**:
  - `feat/ws-token-enforce` task が Godot WS client patch + `require_token=True` default を入れた時点で本 flag を deprecated 化し、6 ヶ月後に削除
  - OSF 公開時 (M14+?) はこの flag を強制 off にする (production refuses unsafe LAN)

## SH-FOLLOWUP-4 — Codex 14th HIGH-2 banned-import CI を grep → AST 化

- **判断日時**: 2026-05-15 (Codex 14th review 反映)
- **背景**: Codex 14th HIGH-2 — `policy-grep-gate` の banned-import grep が `import openai, os` (comma form) を miss する。regex は `(openai|anthropic))[[:space:]]` で末尾 whitespace を要求しているが `openai,` は comma で whitespace なし。
- **選択肢**:
  - A: regex を comma / alias 両対応に拡張 → `import openai.submodule` などの bypass が残る可能性
  - **B** (採用): Python `ast.walk` ベースの専用 script (`scripts/policy_banned_imports.py`) を CI から呼ぶ → 全 import 形式を構文レベルで網羅
  - C: ruff custom rule を作る → ruff 拡張 API は plugin 必要で overkill
- **採用**: **B**
- **理由**:
  - AST scanner は Python 公式 grammar に従う形式すべてを catch (comma / alias / submodule / from-import / from-submodule-import)
  - CI が `uv run` 経由なので追加 dependency 不要 (標準 `ast` モジュール)
  - 単体 unit test を `tests/test_codex_hooks/test_banned_imports_ast.py` で書ける (`scripts/policy_banned_imports.scan_file()` を直接 import)
- **トレードオフ**: 純 regex より遅い (microbenchmark 10ms vs 100ms 程度) が CI 全体時間に対しては誤差
- **影響範囲**: `scripts/policy_banned_imports.py` 新規、`.github/workflows/ci.yml` `policy-grep-gate` の grep step を script invocation に置換、`tests/test_codex_hooks/test_banned_imports_ast.py` 新規 (11 unit test)
- **見直しタイミング**: 新 banned import (`google.generativeai` 等) を追加するときは `BANNED_ROOTS` set に追加するだけ

## Codex 14th MEDIUM-1 / MEDIUM-2 / LOW-2 defer

- **MEDIUM-1** (shell-write regex coverage 広げる: `cp`, `dd`, python heredoc, workspace 名 absolute path): **本 task では defer**。理由: 5 red-team case + 2 negative path で IDE-time guardrail として valuable、CI AST scan が最終防衛線として fall back する。広い shell parser 化は別 task で言語化整理する価値あり (e.g. `feat/codex-hook-shell-parser`)
- **MEDIUM-2** (`.steering` CI gate を changed dir 要求に強化): **本 task では defer**。理由: 現在の "ある complete dir で OK" は CLAUDE.md の rule "全実装は .steering に記録" を厳密に enforce しない。ただし changed dir 要求は autonomous mode で task 切り替え時の friction を増やす可能性 (リネーム / シンボリックリンク等)。次 review cycle で別 ADR として整理
- **LOW-2** (CycleResult full-fidelity test): **本 task では defer**。理由: `_consume_result` は `_enqueue_with_drop_oldest` を通る同型経路なので shared-helper proof で gate decision として十分。次に runtime lifecycle を変更するタスク (e.g. M10-0 `WorldModelUpdateHint` 統合) で full-fidelity test を追加する
