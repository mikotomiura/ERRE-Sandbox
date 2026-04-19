# T18 ui-dashboard-minimal

## 背景

MVP M2 の critical path は T14 (G-GEAR で進行中) → T19 実行 → T20。
G-GEAR セッションで T14 実装が進む間、MacBook 側では T18
`ui-dashboard-minimal` (MASTER-PLAN 上 optional、0.5d) を進めることで
T19 実行フェーズのデバッグを容易にする。

T19 の E2E 実行は envelope が多数飛び交うため、Godot の 3D ビューだけでは
AgentState / Threshold 違反 / tick jitter / memory 書込状況を観測しづらい。
軽量な HTML ダッシュボードを FastAPI で同一 gateway port で配信することで、
`/dashboard` にアクセスするだけで live 観測が可能になる。

本タスクは optional だが、M7 の 12 時間安定運転時にも再利用できる観測基盤を
先行整備する意味がある。

## ゴール

以下 5 点を達成することで本タスクは完了とする。

1. **Live WS subscriber 付き HTML ダッシュボード** が FastAPI 配下で配信される
   - `GET /dashboard` で SPA (素の HTML + JS) を返す
   - `GET /ws/dashboard` で envelope を購読する
2. **観測 3 パネル** が表示される:
   - **Agent Panel**: 最新 `AgentState`
     (arousal / valence / attention / erre_mode / zone / position)
   - **Envelope Stream**: 直近 50 件の envelope を kind 別に色分け
     (handshake / agent_update / speech / move / animation / world_tick / error)
   - **Metrics Panel**: `M2_THRESHOLDS` と現在値の比較
     (latency p50/p95、tick jitter、memory 書込件数)
3. **Threshold 逸脱の視覚警告**
   (赤色ハイライト + 件数カウンタで即時可視化)
4. **T14 gateway と疎結合 (採用: 方針 A)**
   - T18 は独立した mini FastAPI app (port 8001 想定) として動作
   - 本タスクでは T14 依存なしの stub mode で動作確認
   - T14 完成後は任意で同居させる選択肢を残す
   - `integration/` モジュールの型と定数を再利用
5. **軽量実装**
   - 新規依存は最小 (既存 FastAPI + Pydantic v2 のみ)
   - フロントは素の HTML/JS で SPA ライブラリ (React 等) 不使用
   - Jinja2 もなし (HTML は文字列テンプレート or 静的配信)

## スコープ

### 含むもの
- **`src/erre_sandbox/ui/dashboard/` 新規モジュール**
  (architecture-rules の `ui/` 層として `schemas.py` + `integration/` に依存、
  `cognition/memory/world/inference` には依存しない)
  - `server.py` — FastAPI mini app (stub WS generator 含む)
  - `static/index.html` — SPA エントリ (Vanilla JS)
  - `static/app.js` — WS 購読 + DOM 更新
  - `static/style.css` — 最小スタイル
- **Stub envelope generator** — T14 未完成の間、
  `fixtures/control_envelope/` の JSON を繰り返し stream 生成
  (開発時の視認検証用)
- **Metrics 集計ロジック** — rolling window で latency / jitter / write-rate を
  計算し、`integration.M2_THRESHOLDS` と比較
- **CLI エントリポイント** — `python -m erre_sandbox.ui.dashboard`
  (uvicorn 経由で localhost:8001 起動)
- **テスト** `tests/test_ui/test_dashboard.py`
  - HTTP GET `/dashboard` が 200 + text/html を返す
  - WS `/ws/dashboard` 接続と envelope 配信
  - Threshold 逸脱判定ロジックの unit test
  - Stub generator の決定性
- **ドキュメント**: `.steering/` に requirement / design / tasklist / decisions

### 含まないもの
- **T14 gateway 本体の実装** — 別タスク (G-GEAR 側)。
  本タスクは stub envelope generator のみ
- **認証 / 認可** — localhost 前提、予算ゼロ制約で OAuth 等は導入しない
- **本番用メトリクス収集基盤** (Prometheus / Grafana) —
  M7 `observability-logging` で扱う
- **履歴永続化** — envelope は in-memory の rolling buffer のみ、DB 保存しない
- **複数エージェント表示** — M2 は Kant 単体なので 1 体分の Panel のみ
- **複数ゾーン地図表示** — M2 は Peripatos のみ
- **React / Vue / SvelteKit 等の SPA フレームワーク** — 新規依存回避
- **WebRTC / Server-Sent Events** — WS のみで完結
- **Dark mode / モバイル対応 / i18n** — optional タスクのため最小美観に留める
- **CI への e2e テスト追加** (Playwright 等) —
  テストは FastAPI TestClient の WS 接続検証のみ
- **Godot 側との同期** — Godot は別 WS client として並行動作
  (dashboard は独立観測)

## 受け入れ条件

- [ ] `.steering/20260419-ui-dashboard-minimal/` に requirement.md / design.md /
      tasklist.md / decisions.md が揃う
- [ ] `python -m erre_sandbox.ui.dashboard` で localhost:8001 に app 起動、
      `GET /dashboard` が 200 + text/html を返す
- [ ] ブラウザで `http://localhost:8001/dashboard` を開くと 3 パネル
      (Agent / Envelope Stream / Metrics) が描画される
- [ ] Stub mode で 30 秒間 WS stream を受信し、閾値逸脱時に赤色警告が点灯する
- [ ] `tests/test_ui/test_dashboard.py` が **4 件以上** 全 PASS
      (GET /dashboard、WS 接続、envelope 配信、閾値判定)
- [ ] `uv run ruff check` / `uv run ruff format --check` /
      `uv run mypy src` / `uv run pytest` が全て緑
- [ ] `src/erre_sandbox/ui/` の依存方向が `architecture-rules` 準拠
      (`schemas.py` + `integration/` のみ)
- [ ] MASTER-PLAN 直下 tasklist.md の T18 行が `[x]` + PR 番号併記で更新される
- [ ] 設計判断が自明でない箇所 (stub generator 方式、rolling window 実装) は
      `decisions.md` に記録

## 関連ドキュメント

- `.steering/20260418-implementation-plan/MASTER-PLAN.md` §4.3, §6 (M2 scope)
- `docs/architecture.md` (UI / WS 観点)
- `.steering/20260418-schemas-freeze/` — T05 ControlEnvelope / AgentState
- `.steering/20260418-control-envelope-fixtures/` — T07 fixture 群 (stub 材料)
- `.steering/20260419-m2-integration-e2e/` —
  T19 `integration.M2_THRESHOLDS` / `SessionPhase` 等を参照
- `.claude/skills/architecture-rules/SKILL.md` —
  `ui/` は `schemas.py` のみ依存が既定、`integration/` 追加は decisions.md で記録

## 運用メモ

- **種類**: 新機能追加 (次に `/add-feature` 相当の設計→実装フロー)
- **/reimagine 適用**: Yes
  理由: ダッシュボード構造と stub generator 方式は複数案 (別プロセス/同プロセス、
  fixtures ループ/合成、Vanilla JS/AlpineJS) が考えられ、
  どれが最良か自明でない。MEMORY の feedback_reimagine_trigger / _scope に準拠。
