# 設計 — M4 Live Validation (G-GEAR 実機)

## 実装アプローチ

本タスクはコード変更を伴わない **evidence 収集タスク**。handoff
(`.steering/_handoff-g-gear-m4-live-validation.md`) の Step 0–8 を忠実に実行し、
各項目の evidence を `evidence/` 配下に保存、最終的に `acceptance.md` で
PASS/FAIL 判定をまとめる。

FAIL が見つかった場合でも本タスク内では修正しない (handoff 最終注記)。
修正 PR は MacBook 側の別タスクに切り出す。

## 変更対象

### 新規作成するファイル

- `.steering/20260420-m4-acceptance-live/requirement.md` (記入済)
- `.steering/20260420-m4-acceptance-live/design.md` (本ファイル)
- `.steering/20260420-m4-acceptance-live/tasklist.md`
- `.steering/20260420-m4-acceptance-live/acceptance.md` — 5 項目 PASS/FAIL まとめ
- `.steering/20260420-m4-acceptance-live/evidence/gateway-health-*.json`
- `.steering/20260420-m4-acceptance-live/evidence/cognition-ticks-*.log`
- `.steering/20260420-m4-acceptance-live/evidence/semantic-memory-dump-*.txt`
- `.steering/20260420-m4-acceptance-live/evidence/dialog-trace-*.log`
- `.steering/20260420-m4-acceptance-live/evidence/_stream_probe.py` — Python WS
  probe ツール (handshake + keep-alive 付き)
- `.steering/20260420-m4-acceptance-live/evidence/godot-3avatar-*.mp4` —
  MacBook で撮影後に追加

### 修正するファイル

- 無し (コード変更ゼロのタスク)

## WS probe の設計判断

### なぜ websocat ではなく Python を使うか

- handoff は `websocat` 前提だが G-GEAR (Windows) に入っていない
- プロジェクトは `websockets` 14.2 を既に使用 → 追加依存ゼロで使える
- `uv run python` 経由で実行することで venv の websockets を利用可

### handshake が必要

gateway の `ws_observe` は Phase 1 (AWAITING_HANDSHAKE) で HandshakeMsg を
待ち、timeout/mismatch 時に ErrorMsg を返して切断する。probe は以下の順を守る:

1. `await ws.recv()` で server handshake を受信
2. `await ws.send(client_handshake_json)` で client handshake を返す
3. その後 envelope を受信し続ける

fixtures/control_envelope/handshake.json を参考に capabilities を構成。

### keep-alive が必要

gateway の `_recv_loop` は `protocol.IDLE_DISCONNECT_S` (60s) client frame 無しで
`idle_disconnect` ErrorMsg を返して切断する。120s probe で切断された実績あり。

対処: 30s 間隔で client handshake を再送する `_keepalive` タスクを probe に組み込み。
handshake 再送は `_recv_loop` の「parsed envelopes は logged as warning but
otherwise ignored」挙動により無害。

## 影響範囲

- **コード**: 無し
- **DB**: `var/m4-live.db` に reflection summary の LLM 応答が書かれる。
  evidence 収集後に削除 (`.gitignore` 配下)
- **network**: gateway が `0.0.0.0:8000` で一時的に LAN listen。
  firewall 外からは届かない前提

## 既存パターンとの整合性

- `.steering/_template/` のディレクトリ構成に従う
- `tests/test_integration/test_multi_agent_stream.py` で使われる
  handshake/envelope パターンと同じ形式を採用

## テスト戦略

- 単体テスト: 不要 (コード変更ゼロ)
- 統合テスト: 本タスク自体が live integration test の役割
- 回帰テスト: pytest baseline を Step 2 で確認 → 0 failures

## ロールバック計画

- コード変更無しのため、ロールバック = `.steering/` から本タスクディレクトリを
  削除するだけ
- `var/m4-live.db` と `var/m4-live.db.phase1-backup` は `.gitignore` 配下なので
  commit されない
- 本 branch (`feature/m4-acceptance-live-evidence`) は `git branch -D` で破棄可

## 想定される FAIL とその扱い

本タスクでは FAIL 時も修正しない (handoff 最終注記)。ただし以下を記録:

- `acceptance.md` に root cause と修正 PR 案を書く
- 「deferred to M5+」と判断される項目は明示
- 修正 PR は MacBook 側の別 branch (`fix/m4-live-*`) で切り出す
