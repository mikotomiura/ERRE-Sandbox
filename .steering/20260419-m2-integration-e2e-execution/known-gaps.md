# T19 実施後に判明した残存課題 (Known Gaps)

T19 両機合流ライブ検証 (2026-04-19) の過程で明示的に発覚した
**構造的ギャップ** とその対処方針を記録する。
本ドキュメントは MVP M2 の closeout (T20) および M4 kickoff の入力となる。

---

## GAP-1: WorldRuntime → Gateway の実配線スクリプトが未実装

### 症状
`python -m erre_sandbox.integration.gateway` は起動時に
`_NullRuntime()` (`src/erre_sandbox/integration/gateway.py:444-458`)
を default で注入する。`_NullRuntime.recv_envelope()` は永久に
`asyncio.Event().wait()` で sleep するため、gateway から broadcast される
`ControlEnvelope` は **ゼロ件**。

### 影響
以下が **単体 gateway 起動では視認検証不能**:

- Avatar Tween 移動 (MoveMsg が届かない)
- 30Hz 描画の負荷評価 (更新トリガなし)
- `WorldTickMsg` 1Hz 受信確認
- `agent_update` 流量プロファイル
- ERRE mode 遷移の視認 (`SHALLOW → PERIPATETIC`)

### 根本原因
個別モジュールは完成しているが、**それらを連結する orchestration layer が欠落**:

| モジュール | 状態 | 役割 |
|---|---|---|
| T11 `inference/ollama_adapter` | ✅ 単体完成 | LLM 推論 |
| T12 `cognition/cycle` | ✅ 単体完成 | 1-tick CoALA/ERRE pipeline |
| T13 `world/tick` | ✅ 単体完成 | Scheduler + zones + envelope queue |
| T14 `integration/gateway` | ✅ 単体完成 | WS fan-out |
| **glue script** | ❌ **欠落** | 上記を起動 + WorldRuntime を gateway に inject |

欠落しているもの (例):
```python
# src/erre_sandbox/__main__.py  (想定される単一エントリ)
async def run_full_stack():
    persona = load_persona("personas/kant.yaml")
    memory = MemoryStore(":memory:")
    inference = OllamaChatClient()
    cycle = CognitionCycle(persona=persona, memory=memory, inference=inference)
    runtime = WorldRuntime(clock=RealClock())
    runtime.register_agent(persona, cycle_handler=cycle.step)
    app = make_app(runtime=runtime)
    await asyncio.gather(runtime.run(), uvicorn.Server(app).serve())
```

このような glue は M2 のスコープ外で、各タスク (T11-T14) の責務境界を尊重した結果。

### 対処方針: M4 で明示タスク化

MASTER-PLAN の M4 `gateway-multi-agent-stream` タスクに **このギャップを明記**
し、以下を成果物とする:

1. **Full-stack orchestrator** — `src/erre_sandbox/main.py` or
   `src/erre_sandbox/runtime.py` などの名前で 1 つのエントリポイント
2. **Persona loading → agent registration → cycle orchestration → gateway inject** の
   連鎖を 100-200 行程度の非同期関数として実装
3. **1 agent × 1 zone** の M2 スコープから入り、M4 で複数 agent に拡張
4. **`python -m erre_sandbox`** で G-GEAR 側 1 コマンド起動できる体験

### 暫定回避策 (本タスクで採用せず)

- **Stub 混在**: gateway に `ui/dashboard/stub.py` 的な fixture 循環 runtime を
  組み込む → 実運用と乖離するため非採用
- **MockRuntime で gateway を直接叩く**: テストコード的手段。live verification
  にはならない
- **Godot を offline replay モードで動作確認**: T16 の FixtureHarness は別設計
  で稼働中。T14 live とは別検証経路

---

## GAP-2: Avatar 動作の自動化テストが存在しない

### 症状
Godot 側の live integration は「人の目で視認する」しか方法がない。
CI で実行可能な headless 試験は:

- `tests/test_godot_peripatos.py` (T17 fixture replay)
- `tests/test_godot_ws_client.py` (T16 fixture replay)

の 2 つ。いずれも **real WS を通らない** (FixturePlayer で envelope を直接注入)。

### 影響
T20 acceptance `ACC-SCENARIO-WALKING` の "live" 部分は **手動視認のみ**。
将来リグレッションしても検出されない。

### 対処方針: M7 observability-logging フェーズで検討

headless Godot + 実 WS の automated E2E は M7 `examples-walking-thinkers-12h` で
扱う候補。M2/M4 時点では手動視認 + スクリーンショット記録で妥協。

---

## GAP-3: gateway `/health` の `active_sessions` counter が監視されていない

### 症状
T19 live verification 中、MacBook Godot 接続時に G-GEAR gateway の
`/health` 応答の `active_sessions` が 0 → 1 に増えたか未計測。
Gateway 側には counter は実装済みだが、**MacBook 側から定期 probe する
軽量スクリプト / curl ループがない**。

### 影響
「Godot が何らかの理由で接続していると思い込んでいる」という silent
failure を検出できない可能性。

### 対処方針: T20 acceptance で calibration 運用を追加

T20 acceptance runbook (`t20-acceptance-checklist.md`) に以下を追加提案:
- ACC-SESSION-COUNTER: MacBook から `curl http://<ip>:8000/health | jq .active_sessions`
  を 1 Hz で叩き、Godot 接続中は 1 以上を確認

---

## GAP-4: Godot 4.6 への自動アップグレードによるシーン diff が大きい

### 症状
本 PR で Godot が MainScene.tscn を format=3 に変換し、全ノードに
`unique_id=...` を付与、各スクリプトに `.uid` sidecar を生成。
結果として diff が 40 行超。

### 影響
レビュー時に「これは Godot の auto-upgrade か、実質的な変更か」の
判別負担がある。次回 Godot マイナー更新時にも同様の diff が発生する
可能性。

### 対処方針: 記録のみ (今回は許容)

- `project.godot` の `config_version=5` / `features=PackedStringArray("4.6", ...)` が
  4.6 対応完了を示す
- `.uid` sidecar は一度 commit すれば再生成されない (idempotent)
- 次回 Godot 更新時は「意図的にアップグレードするかどうか」をタスクとして計画

---

## GAP-5: `_NullRuntime` が standalone debug 用であるという注意書きが README に未反映

### 症状
`gateway.py:447-449` に `"All production starts should inject a real runtime via
make_app."` と書いてあるが、**プロジェクト README / docs/architecture.md には
この注意がない**。MacBook セッション初日の live 検証では、この default 挙動に
気づかずにデバッグ時間を消費した。

### 対処方針: T20 acceptance で docs 更新時に反映

T20 の `ACC-DOCS-UPDATED` 作業で `docs/architecture.md` の Gateway セクションに:
- `_NullRuntime` は debug-only default、production 起動には `WorldRuntime` inject 必須
- 単一エントリ orchestrator (M4 で整備予定) への参照

を追記する。

---

## サマリ

| ID | タイトル | 影響範囲 | 対処 | 解消状態 |
|---|---|---|---|---|
| GAP-1 | WorldRuntime↔Gateway 配線欠落 | Avatar live 不可 | **M4 `gateway-multi-agent-stream` で対処** | ⏳ 未解消 (M4 待ち) |
| GAP-2 | Godot live の自動化なし | リグレッション検出不可 | M7 で検討 | ⏳ 未解消 (M7 待ち) |
| GAP-3 | `/health` counter 監視なし | silent failure リスク | T20 acceptance に追加 | ✅ 解消 (T20: `.steering/20260419-m2-acceptance/session-counter-runbook.md`) |
| GAP-4 | Godot 4.6 diff の大きさ | レビュー負担 | 記録のみ | 🟡 記録のみ (対応せず) |
| GAP-5 | `_NullRuntime` 説明の docs 欠落 | 初見ハマり | T20 docs 更新で対処 | ✅ 解消 (T20: `docs/architecture.md` §Gateway (G-GEAR)) |

## 参照

- T19 MacBook live 検証記録: `macbook-verification.md`
- T14 gateway 設計: `.steering/20260419-gateway-fastapi-ws/`
- MASTER-PLAN: `.steering/20260418-implementation-plan/MASTER-PLAN.md` §4.3
