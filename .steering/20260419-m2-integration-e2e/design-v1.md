# 設計 (v1 初回案)

## 実装アプローチ

**「Contract 文書を積み上げる」アプローチ** — 設計成果物を独立した Markdown ファイル群として
`.steering/20260419-m2-integration-e2e/` 内に並列配置し、それぞれに単一責務を持たせる。
試験実行は T14 完成後のため、本タスクでは「文書 + skeleton コード」のみを出す。

### 構造
```
.steering/20260419-m2-integration-e2e/
├── requirement.md              (済)
├── design.md                   (this file)
├── tasklist.md                 (TODO)
├── decisions.md                (TODO)
├── scenarios.md                (新規) — E2E シナリオの時系列記述
├── integration-contract.md     (新規) — T14 実装者向け WS API 契約
├── metrics.md                  (新規) — 受け入れメトリクスの数値定義
└── t20-acceptance-checklist.md (新規) — MVP タグ前チェックリスト
```

### 理由
- T14 実装者 (将来の G-GEAR セッション) が **1 ファイル読めば着手できる** 粒度を担保
- 各文書に単一責務を持たせると PR レビュー時の差分も読みやすい
- `integration-contract.md` は T05 schemas-freeze の拡張 (Contract 補足) として機能し、
  既存契約との整合を取りやすい

## 変更対象

### 修正するファイル
- `.steering/20260418-implementation-plan/tasklist.md`
  — T19 行に設計フェーズ完了マークと PR 番号を併記
- `.steering/20260419-m2-integration-e2e/requirement.md`
  — 既に記入済み (変更なし、参照のみ)

### 新規作成するファイル

**設計ドキュメント**:
- `.steering/20260419-m2-integration-e2e/scenarios.md`
  — 以下 3-5 シナリオを時系列で記述
    - S1: Kant 起動 → Peripatos 歩行 → observation 受信
    - S2: 歩行中の状態遷移 (Shallow → Peripatetic) + AgentState 更新
    - S3: 記憶書込み (memory-store へ episodic 4 件, semantic 1 件)
    - S4 (optional): tick 抜け検知 (Godot 側 heartbeat)
    - S5 (optional): disconnect → reconnect 耐性
- `.steering/20260419-m2-integration-e2e/integration-contract.md`
  — `GET /ws/agent/{agent_id}` 定義、handshake, tick push, ack, error, close
- `.steering/20260419-m2-integration-e2e/metrics.md`
  — 受け入れ閾値:
    - p50 tick→WS latency < 100ms, p95 < 250ms
    - tick jitter σ < 20%
    - memory 書込み成功率 > 98%
    - AgentState.arousal は 0.0-1.0 範囲で逸脱 0 件
- `.steering/20260419-m2-integration-e2e/t20-acceptance-checklist.md`
  — MVP タグ `v0.1.0-m2` 前チェック 10-15 項目
- `.steering/20260419-m2-integration-e2e/decisions.md`
  — 本設計での判断 5-7 件 (Contract 文書を分けた理由、メトリクス粒度、skeleton の skip 戦略等)
- `.steering/20260419-m2-integration-e2e/design-v1.md` (reimagine 時退避用)
- `.steering/20260419-m2-integration-e2e/design-comparison.md` (reimagine 時生成)

**Skeleton コード**:
- `tests/test_integration/__init__.py` — 空
- `tests/test_integration/conftest.py` — 共通 fixture
    - `agent_state_fixture` (Kant 起動直後)
    - `observation_stream_fixture` (tick 模擬)
    - `ws_client_fixture` (Godot 側 stub)
- `tests/test_integration/test_scenario_walking.py` — S1/S2 の skeleton
- `tests/test_integration/test_scenario_memory_write.py` — S3 の skeleton
- `tests/test_integration/test_scenario_tick_robustness.py` — S4/S5 の skeleton

すべて `@pytest.mark.skip(reason="T19 実行フェーズ待ち (T14 完成後に点灯)")` を付与。

### 削除するファイル
- なし

## 影響範囲

| 領域 | 影響 | 対処 |
|---|---|---|
| `src/erre_sandbox/` | なし (本タスクは設計のみ) | — |
| `tests/` | `tests/test_integration/` 新規ディレクトリ | skip 付与で CI 緑を維持 |
| CI (`.github/workflows/ci.yml`) | 新 test dir を自動収集 | `pytest` のデフォルト収集で拾われる。skip で failing なし |
| Godot 側 | なし | — |
| `.steering/` | `20260419-m2-integration-e2e/` と `20260418-implementation-plan/tasklist.md` | 本タスクで完結 |
| docs/ | なし (MASTER-PLAN 内で閉じる) | — |

## 既存パターンとの整合性

- **`.steering/` 命名規約**: 既存 `20260419-cognition-cycle-minimal/` 等の文書構成を踏襲
- **Contract 文書**: T05 schemas-freeze / T07 fixtures の「Contract-first」姿勢を継承
- **test 命名**: `tests/test_memory/` `tests/test_cognition/` 等のディレクトリ別分割を踏襲
- **skip pattern**: pytest の `@pytest.mark.skip(reason=...)` 公式機能を使用、カスタムマーカーは導入しない
- **metrics 数値**: CSDG の 3 層 Critic (重み 0.40/0.35/0.25) のような明示数値化の姿勢を流用

## テスト戦略

- **単体テスト**: 本タスクではなし (設計のみ)
- **統合テスト (skeleton)**: `tests/test_integration/` に 3-5 件を配置、
  全件 `@pytest.mark.skip` で CI 上は no-op
- **E2E 実行**: T14 完成後の T19 実行フェーズで skip を外し、G-GEAR + MacBook
  の両機で Godot ヘッドレス実行を含めた実機 E2E を回す (本タスク外)
- **検証**: ローカルで `uv run pytest -v` を実行し、
  新規 skeleton 件が `SKIPPED` としてカウントされていることを確認

## ロールバック計画

本タスクは設計・skeleton のみの追加なので、以下で完全に戻せる:

```bash
git checkout main
git branch -D feature/m2-integration-e2e
rm -rf .steering/20260419-m2-integration-e2e/ tests/test_integration/
```

MASTER-PLAN 直下 tasklist.md の T19 マーク更新も別コミットにしておくと部分ロールバックが楽。

## リスク

| リスク | 影響 | 緩和策 |
|---|---|---|
| Contract が T14 実装時に不足 | T14 実装者が設計追記を迫られる | `integration-contract.md` に Q&A セクションを設け、不確定点を明示 |
| メトリクス閾値が厳しすぎる | T19 実行時に常に赤 | 初期値は保守的に設定、実測後に decisions.md で調整ログ残す |
| skeleton テストが陳腐化 | T14 完成時に API ズレ | `integration-contract.md` と skeleton の参照を明示、レビュー時に整合確認 |
| Godot ヘッドレス実行の複雑さ | E2E が不安定 | skeleton 段階では WS クライアント stub のみ、Godot 実機は T19 実行フェーズで扱う |
