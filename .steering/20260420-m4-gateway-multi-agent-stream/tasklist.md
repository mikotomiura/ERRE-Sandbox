# タスクリスト — m4-gateway-multi-agent-stream

## 準備
- [x] `.steering/20260420-m4-planning/design.md` §m4-gateway-multi-agent-stream
- [x] 既存 `gateway.py` / `protocol.py` / `world/tick.py` を読了
- [x] `test_gateway.py` の既存テスト構造 (Layer A / B) 把握

## 設計
- [x] `requirement.md` 記入
- [x] v1 (broadcast 維持 + capability 追加) を `design.md` に記入
- [x] v1 を `design-v1.md` に退避、意図的リセット
- [x] v2 (URL query param ベース server-side filter) を再構築
- [x] `design-comparison.md` 作成 (10 観点)
- [x] 採用: **v2**

## 実装
- [x] `_SERVER_CAPABILITIES` を 10 kinds に拡張
- [x] `_envelope_target_agents(env)` pure function 追加
- [x] `Registry.add` に `subscribed_agents: frozenset[str] | None` 追加
- [x] `Registry.fan_out` に subscription filter 組み込み
- [x] `_InvalidSubscribeError` / `_parse_subscribe_param` / `_SUBSCRIBE_ID_PATTERN`
- [x] `ws_observe` で URL query `?subscribe=` を parse、accept 前に検証
- [x] invalid_subscribe 時の accept → error → close パターン + コメント
- [x] `protocol.py` に `SUBSCRIBE_QUERY_PARAM` / `SUBSCRIBE_DELIMITER` /
      `MAX_SUBSCRIBE_ITEMS` / `MAX_SUBSCRIBE_ID_LENGTH` / `MAX_SUBSCRIBE_RAW_LENGTH`

## テスト
- [x] `tests/test_integration/test_multi_agent_stream.py` 新規 39 件:
  - Layer A: `TestParseSubscribeParam` (10 件、DoS + slug 検証含む)
  - Layer A: `TestEnvelopeTargetAgents` (11 件、exhaustiveness guard 含む)
  - Layer A: `TestRegistrySubscriptionFilter` (6 件)
  - Layer B: `TestSubscribeIntegration` (6 件、3-client dialog 含む)
- [x] `tests/test_integration/test_gateway.py` の capabilities assertion を
      10 kinds に更新 (既存 54 件は regression なし)

## 検証
- [x] `uv run pytest`: **446 passed / 20 skipped** (baseline 407 → +39)
- [x] `uv run ruff check` / `ruff format --check` クリーン

## レビュー
- [x] `code-reviewer`: HIGH ゼロ、MEDIUM 2 件 + LOW 1 件を対応
  - (MEDIUM 1) test 変数シャドーイング解消
  - (MEDIUM 2) `_envelope_target_agents` の exhaustiveness test 追加
  - (LOW 3) accept-order コメント追加
- [x] `security-checker`: HIGH/CRITICAL ゼロ、MEDIUM 2 件を対応
  - (MEDIUM 1) raw 長 pre-check 追加 (`MAX_SUBSCRIBE_RAW_LENGTH`)
  - (MEDIUM 2) slug 正規表現で制御文字・log injection 対策

## ドキュメント
- [x] `docs/architecture.md §Gateway` に M4 routing / capability 10 種 /
      DoS 対策を追記

## 完了処理
- [x] `decisions.md` 作成 (D1-D10)
- [ ] commit: `feat(gateway): m4 multi-agent routing — server-side ?subscribe= + dialog capabilities`
- [ ] push + PR 作成
- [ ] PR review → merge

## 次のタスク
- `m4-cognition-reflection` (#5, #3 merged 済、Axis B logic、critical path 最終盤)
- `m4-multi-agent-orchestrator` (#6, 全 merged 後)
