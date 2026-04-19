# T19 m2-integration-e2e — 試験契約先行設計フェーズ

## 背景

MVP M2 の critical path は **T14 (G-GEAR, `gateway-fastapi-ws`) → T19 (両機, `m2-integration-e2e`) → T20 (両機, `m2-acceptance`, タグ `v0.1.0-m2`)**。
T14 実装は G-GEAR 側で後続着手予定だが、T19 の E2E 試験設計を先行させないと
「何をもって MVP 完了とするか」の基準が曖昧なまま T14 実装に入り、
- 試験観点の抜け漏れ (e.g. 観測量・レイテンシ・異常系) による T20 リワーク
- T14 実装者 (G-GEAR セッション) と試験設計者 (MacBook セッション) の非同期による契約ズレ
のリスクが高まる。

MacBook が **Contract master** である本プロジェクトの原則に沿い、
integration 契約・E2E シナリオ・受け入れメトリクス・fixture 群を MacBook 側で先に凍結することで、
T14 実装および T20 acceptance に必要な「試験契約」を供給する。

本タスクは **T19 の設計フェーズのみ** を実施する (実行フェーズは T14 完成後、G-GEAR セッション合流時に着手)。

## ゴール

本タスク (T19 設計フェーズ) は以下 5 つの成果物を凍結することで完了とする:

1. **E2E シナリオ凍結**
   M2 で検証すべきユーザーストーリー (例: "Kant が Peripatos を歩きながら状態遷移し、
   記憶が memory-store に書かれる") を複数個、**具体的な時系列** として記録。
2. **受け入れメトリクス定義**
   レイテンシ予算 (tick → WS → Godot、数百 ms オーダー)、tick 安定性、
   memory 書込み率、状態遷移の妥当性 (半数式の動作範囲) を **数値で策定**。
3. **integration 契約の凍結**
   T14 gateway が提供すべき WS エンドポイント・メッセージ型・セッション寿命を
   Contract 補足文書として確定 (T05 schemas-freeze の延長としての integration contract)。
4. **test harness skeleton 配置**
   `tests/test_integration/` に E2E テストの骨組みとフィクスチャを配置
   (本タスクでは実行しない。T14 完成後の G-GEAR セッションで点灯)。
5. **T20 acceptance criteria 一覧**
   タグ `v0.1.0-m2` を打つための最終チェックリスト
   (観測・ログ・再現性・ドキュメント) を策定。

成果物は **設計ドキュメント + skeleton コード** のみ。
本タスクで T14 実装や実 E2E 実行は行わない。

## スコープ

### 含むもの
- `.steering/20260419-m2-integration-e2e/` 配下の設計ドキュメント
  (requirement.md / design.md / tasklist.md / decisions.md / 必要に応じ blockers.md)
- **E2E シナリオ定義書** (`scenarios.md`) — Kant × Peripatos 前提の 3-5 シナリオを時系列で記述
- **integration 契約文書** (`integration-contract.md`) — T14 が提供すべき
  WS エンドポイント、メッセージ型、セッションライフサイクル、エラー応答
  (T05 schemas-freeze の Observation / ControlEnvelope / AgentState を参照)
- **受け入れメトリクス定義** (`metrics.md`) — p50/p95 レイテンシ、
  tick jitter 許容、半数式動作範囲の数値、memory 書込み率など
- **test harness skeleton** — `tests/test_integration/` ディレクトリ骨格
  + `conftest.py` + skeleton テストファイル群
  (`@pytest.mark.skip("T19 実行フェーズ待ち")` で一時スキップ)
- **T20 acceptance チェックリスト** (`t20-acceptance-checklist.md`)
- **`/reimagine` による設計案の二案比較** (design-v1.md → design-comparison.md → design.md)

### 含まないもの
- **T14 `gateway-fastapi-ws` の実装** — G-GEAR 側の後続タスク
- **実 E2E 実行・skeleton テストの点灯** — T14 完成後の T19 実行フェーズで実施
- **M4 以降の拡張** (3 体対話、反省、ERRE モード FSM、複数ゾーン)
  本タスクは Kant 単体 × Peripatos 単ゾーンに限定
- **Godot 側の新規シーン追加** — T17 peripatos の既存シーンを前提とし変更しない
- **LLM 推論の性能チューニング / VRAM 再最適化** — llm-inference Skill 領域
- **Blender アセット更新 / 3D モデル追加** — 既存 PlaneMesh + post を前提
- **CI/CD ワークフロー変更** — skeleton テストは skip マーク付与で既存 CI を壊さないように置く
- **クラウド LLM API 利用** (予算ゼロ制約)

## 受け入れ条件

- [ ] `.steering/20260419-m2-integration-e2e/` に requirement.md / design.md / tasklist.md / decisions.md が揃っている
- [ ] `scenarios.md` に M2 で検証すべき E2E シナリオが **3 件以上** (Kant × Peripatos) 時系列で記載されている
- [ ] `integration-contract.md` に T14 が実装すべき WS API 契約
  (endpoint / message types / session lifecycle / error responses) が
  **T14 実装者がそのまま着手できる粒度** で記載されている
- [ ] `metrics.md` に p50/p95 latency、tick jitter、memory 書込み率、
  半数式動作範囲の受け入れ閾値が **数値** で定義されている
- [ ] `tests/test_integration/conftest.py` と skeleton テスト (最低 3 件) が配置され、
  `@pytest.mark.skip("T19 実行フェーズ待ち")` 付きで CI が緑のまま
- [ ] `t20-acceptance-checklist.md` に MVP タグ `v0.1.0-m2` を打つための最終チェック項目が網羅されている
- [ ] `/reimagine` を適用し design-v1.md → design-comparison.md → design.md の順で二案比較が記録されている
- [ ] 本タスクの PR がマージされた時点で `ruff check` / `ruff format --check` / `mypy src` / `pytest` が緑
- [ ] MASTER-PLAN 直下 tasklist.md に T19 (設計フェーズ完了) が反映され、PR 番号が併記されている

## 関連ドキュメント

- `.steering/20260418-implementation-plan/MASTER-PLAN.md` §4.3 依存グラフ、§6 M2 scope
- `docs/architecture.md` (WS / Gateway / E2E 観点)
- `docs/development-guidelines.md` (テスト方針、CI)
- `.steering/20260418-schemas-freeze/` — T05 で凍結された Observation / ControlEnvelope / AgentState
- `.steering/20260418-control-envelope-fixtures/` — T07 fixture 群
- `.steering/20260418-godot-ws-client/` — T16 で決定した WS Router 仕様
- `.steering/20260419-godot-peripatos-scene/` — T17 Peripatos シーン仕様
- `.steering/20260419-inference-ollama-adapter/` — T11 推論アダプタ
- `.steering/20260419-cognition-cycle-minimal/` — T12 1-tick pipeline
- `.steering/20260419-world-tick-zones/` — T13 scheduler + zones

## 運用メモ

- **種類**: その他 (設計フェーズ中心、実装は skeleton のみ)
- **/reimagine 適用**: Yes (理由: 統合試験契約の設計は複数案が想定され、
  どの粒度で契約を固めるかが自明でないため。MEMORY の feedback_reimagine_trigger に準拠)
