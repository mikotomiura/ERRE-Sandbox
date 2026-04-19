# 設計 — T19 実行フェーズ

## 実装アプローチ

**「MockRuntime + TestClient で skeleton を点灯 + 直接 MemoryStore で memory 検証 + 観測ログ fixture」** の 3 本柱で構成する。

### 核となる着想

T19 設計フェーズ (PR #23) で `integration/scenarios.py` / `metrics.py` /
`acceptance.py` が凍結され、T14 gateway (PR #24) の `test_gateway.py` が
**`MockRuntime` + `TestClient.portal.call(mock_runtime.put, env)`** で
envelope 注入 → WS 側受信を検証する確立されたパターンを既に整備済み。

本タスクはそのパターンを **シナリオ次元に拡張** するだけで済む。つまり
scenario の各 step が「何を注入したら何を受信するか」を実環境でなく
MockRuntime の契約テストとして検証する。
完全な E2E (実 Ollama + 実 sqlite-vec) は本タスクの範囲ではなく、
G-GEAR 側 smoke run として別経路で確認する。

### 3 つの検証レイヤー

| レイヤー | 対象 | 手法 | CI 稼働 |
|---|---|---|---|
| **B1: Gateway 契約** | walking / tick_robustness | MockRuntime + TestClient | 常時 ON |
| **B2: Memory 契約** | memory_write | 直接 MemoryStore + FakeEmbedder | 常時 ON |
| **C: 実機 smoke** | ollama + gateway live | G-GEAR で手動 1 回 | 手動、ログ残し |

Layer C は本タスクでは **smoke run 1 回のみ**、結果を decisions.md に記録する。
連続的な Layer C テストは M7 observability 以降で検討。

## 変更対象

### 修正するファイル

- `tests/test_integration/test_scenario_walking.py`
  - `pytestmark = pytest.mark.skip(...)` 行を削除
  - 4 つの skeleton テストを MockRuntime + TestClient 実装で点灯
  - 各 step の expected envelope (AgentUpdateMsg / WorldTickMsg / MoveMsg / AnimationMsg) を注入 → 受信 → 型/フィールド検証
- `tests/test_integration/test_scenario_memory_write.py`
  - skip 解除
  - 3 つの skeleton テストを 直接 MemoryStore + FakeEmbedder で点灯
  - 4 episodic + 1 semantic 書込 → sqlite-vec 行数検証、prefix 検証
- `tests/test_integration/test_scenario_tick_robustness.py`
  - skip 解除
  - 4 つの skeleton テストを TestClient disconnect/reconnect で点灯
  - heartbeat 耐性、session 再起動、agent_id 継続を検証
- `tests/test_integration/conftest.py`
  - `FakeEmbedder` クラス追加 (decisions.md D1)
  - `memory_store_with_fake_embedder` async fixture 追加
  - `m2_logger` fixture 追加 (`M2_LOG_PATH` env var で jsonl 書き出し切替)
- `.steering/20260418-implementation-plan/tasklist.md`
  - T19 行「実行フェーズ完了」マーク + 本タスク PR 番号併記 (commit 分離、Phase F で実施)

### 新規作成するファイル

- `.steering/20260419-m2-integration-e2e-execution/handoff-to-macbook.md`
  - MacBook セッションで実施すべき項目 (ACC-DOCS-UPDATED / ACC-TAG-READY /
    Godot 実機検証) を列挙
- `.steering/20260419-m2-integration-e2e-execution/decisions.md`
  - D1: FakeEmbedder 採用理由 (deterministic + prefix 強制)
  - D2: Layer C を smoke run 1 回に限定する理由
  - D3: jsonl logger を opt-in env var にする理由
  - D4: 4 episodic + 1 semantic の書き分け方 (event_type → kind mapping)
  - D5: tick_robustness で ManualClock 不採用 (TestClient の timer を直接利用)

### 削除するファイル

- なし

## 影響範囲

| 領域 | 影響 | 対処 |
|---|---|---|
| `tests/test_integration/` | 4 ファイル修正、11 件の skip 解除 + 内容実装 | Layer B 戦略のため Ollama/ネットワーク不要、CI 常時 ON で安全 |
| `src/erre_sandbox/` | 変更なし | MockRuntime / MemoryStore の既存 API を消費するのみ |
| CI (`.github/workflows/ci.yml`) | 追加変更なし | 既存 pytest で新テストが自動収集される |
| Godot 側 | なし | MacBook セッションに handoff |
| ログファイル | `logs/m2-acceptance-run.jsonl` (opt-in) | `.gitignore` に `logs/` を追加、env var `M2_LOG_PATH` 設定時のみ書き出し |
| `docs/` | なし | T20 で `docs/architecture.md` 更新 |
| MASTER-PLAN | T19 行に PR 番号追記のみ | commit 分離 |

## 既存パターンとの整合性

- **MockRuntime + TestClient + portal.call**: `test_gateway.py` で確立済みの injection パターンを scenario 単位に拡張
- **`pytestmark = pytest.mark.skip(...)` の外し方**: T19 設計フェーズ PR #23 で skeleton が配置された時と同じ箇所 (`module-level pytestmark`) を 1 行削除
- **conftest fixture の分層**: 既存の `MockRuntime` / `app` / `client` に続き、`memory_store_with_fake_embedder` を並置。
  `test-standards` Skill の「共通フィクスチャは conftest に集約」原則に従う
- **FakeEmbedder の実装**: `src/erre_sandbox/memory/embedding.py` の `QUERY_PREFIX` / `DOC_PREFIX` を消費する deterministic 版。
  `memory/embedding.py` を触らず、tests/ 内でのみ使用 (本体コード汚染回避)
- **frozen 定数の消費**: scenario の step / threshold は `integration/` の凍結値を import して assert に使う。ハードコード禁止
- **decisions.md の 5 件構造**: 既存 T14/T17/T11/T12/T13 の decisions.md と同じ「D1 ~ D5 の frozen list」形式

## テスト戦略

### 単体テスト (Layer B1: Gateway 契約)

`test_scenario_walking.py`:
- step0: `AgentUpdateMsg(erre_mode=SHALLOW, zone=PERIPATOS)` を inject → 受信、型/フィールド検証
- step1: `WorldTickMsg(tick=1, active_agents=1)` を inject → 受信
- step2: `MoveMsg(speed>0)` を inject → 受信、`erre_mode=PERIPATETIC` への遷移を `AgentUpdateMsg` 2 件目で検証
- step3: `AnimationMsg(animation="walk")` を inject → 受信 (Godot 側相当)

`test_scenario_tick_robustness.py`:
- step0: 初期 AgentUpdateMsg 受信
- step1: heartbeat 1 つ drop (= `WorldTickMsg` を 1 tick ぶん inject せず、次の tick を inject) → ErrorMsg 非発報を確認
- step2: WS close → 再 `websocket_connect` → 新 HandshakeMsg が届く、`schema_version` 一致、`server_hs.tick == 0` (fresh session)
- step3: reconnect 後の AgentUpdateMsg `agent_id` が disconnect 前と同一 (MockRuntime が同じ agent_id で inject)

### 単体テスト (Layer B2: Memory 契約)

`test_scenario_memory_write.py`:
- step0 (scenario の前提確認): `SCENARIO_MEMORY_WRITE.steps == 3` と ERRE モード
- step1 (4 episodic + 1 semantic 書込): `MemoryStore.insert_episodic()` を 4 回、`insert_semantic()` を 1 回呼び、
  `count_episodic() == 4` / `count_semantic() == 1` を検証
- step2 (prefix 検証): 書込 embedding が `DOC_PREFIX` で始まることを FakeEmbedder 経由で確認

### 統合テスト

本タスクでは **Layer C を smoke run 1 回に限定** する:
1. G-GEAR で `ollama list | grep qwen3:8b` が存在することを確認
2. `uv run python -m erre_sandbox.integration.gateway` を起動
3. `uv run python -c "websockets_client.py"` (ad-hoc) で `/ws/observe` に handshake → 1 frame 受信して正常終了を確認
4. 結果を `decisions.md D2` の付記として記録、ログは `logs/m2-smoke-run-TS.txt` に残す

### 観測ログ (jsonl)

環境変数 `M2_LOG_PATH` が設定されている場合のみ、`m2_logger` fixture が
`logs/m2-acceptance-run.jsonl` に以下の行を書き出す:

```json
{"ts": "2026-04-19T12:34:56Z", "scenario": "S_WALKING", "step": 2, "latency_ms": 12.3, "kind": "move"}
```

CI ではこの env を設定しないため、ログは生成されない。
Layer C smoke run や手動検証では `export M2_LOG_PATH=logs/m2-acceptance-run.jsonl` で有効化する。

## ロールバック計画

```bash
git checkout main
git branch -D feature/m2-integration-e2e-execution
# tests/test_integration/ の skip マーカーが復活するのみ、src/ への影響はゼロ
```

本タスクは新規コード追加は最小限 (FakeEmbedder + m2_logger のみ、tests/ 内)
で src/erre_sandbox/ への影響がないため、ロールバック時に他タスクへ波及しない。

## リスク

| リスク | 影響 | 緩和策 |
|---|---|---|
| Layer B のみでは真の E2E にならず T20 で破綻 | M2 MVP 未達 | Layer C smoke run 1 回を必須化、結果を decisions.md D2 に残す |
| MockRuntime の inject が時系列を保証しない | 順序依存の assertion が flaky | 各 step 間で `got = _recv_envelope(ws)` を同期点とする (既存パターン) |
| FakeEmbedder が本番と乖離し memory 契約で誤検知 | 実 Ollama 時の破綻隠蔽 | Layer C smoke run で 1 回だけ nomic-embed-text 実機に通す、embed_dim=768 を検証 |
| TestClient の WebSocket disconnect が非同期で competing | tick_robustness テスト flaky | `fast_timeouts` fixture の idle=0.5s パターンを転用、timeout を短く絞る |
| jsonl logger が CI で環境差異を生む | CI green 不安定 | env var `M2_LOG_PATH` を CI で **設定しない** → no-op |
| MacBook 側検証 (Godot 30Hz) が本 PR で未検証のまま | M2 検収条件未達 | `handoff-to-macbook.md` に明示、T20 で MacBook セッション必須と宣言 |
| Layer C smoke run が Ollama 起動失敗で完了しない | G-GEAR 側合否不明 | 失敗時は decisions.md D2 に「smoke run 未達」と記録、MacBook 合流時に再試行 |

## 設計判断の履歴

- **初回案 (未 reimagine, v1 に該当)**: skeleton の `@pytest.mark.skip` を外して TODO を
  1 つ 1 つ実装するだけの単純案 → 採用
- **/reimagine 判断**: 本タスクは **reimagine 不適用** (requirement.md 運用メモに記載)。
  理由: T19 設計フェーズで /reimagine 適用済みの v2 設計 (契約先行) に沿うだけで、
  実装アプローチは一意に決まっている (MockRuntime パターン再利用)。
  実装中にアーキ判断が浮上したら個別に /reimagine 検討。

## 実装中に確定した追加判断 (post-implementation diff)

当初の本設計書から **変更/追加** された項目を事後に記録する:

1. **M2Logger にパストラバーサル防御を追加** (code-reviewer HIGH 対応)
   - 当初: `M2_LOG_PATH` 環境変数の値をそのまま `Path(path)` で使用
   - 変更後: `_ALLOWED_LOG_ROOT = <project>/logs/` を定義し、`Path(path).resolve().relative_to(_ALLOWED_LOG_ROOT)` で配下検証、違反時は `M2LogPathError` を raise
   - 影響: `tests/test_integration/conftest.py`、新規クラス `M2LogPathError` / 定数 `_ALLOWED_LOG_ROOT`
   - 実機テストで `C:/Windows/Temp/evil.jsonl` の rejection と `logs/*.jsonl` の acceptance を確認

2. **prefix 検証テストを `fake_embedder` 単独依存に簡素化** (code-reviewer MED 6 対応)
   - 当初: `memory_store_with_fake_embedder` fixture を受け取り store は捨てる設計
   - 変更後: `fake_embedder` のみを fixture として受け取る (store 作成コスト省略)
   - 影響: `tests/test_integration/test_scenario_memory_write.py::test_s_memory_write_embedding_prefix_applied`

3. **`make_agent_state` fixture 参照に `MakeAgentState` 型エイリアスを付与** (code-reviewer MED 2 対応)
   - 当初: fixture 引数は型注釈なし (`make_agent_state,`)
   - 変更後: `make_agent_state: MakeAgentState` とし、`from tests.conftest import MakeAgentState` を TYPE_CHECKING ブロックに追加
   - 影響: `test_scenario_walking.py` / `test_scenario_tick_robustness.py`

4. **MASTER-PLAN T19 行を `[x]` でなく `[ ]` として扱う運用ルール確定**
   - G-GEAR 側実行フェーズが完了しても、T19 全体 (MacBook 側 Godot 30Hz 実機検証) が
     残っている限り MASTER-PLAN の T19 行には `[ ]` を維持する
   - 両機タスクの closeout は MacBook セッション合流時に両機の実施状況を
     確認して初めて `[x]` に昇格させる

これら 4 件は本設計の意図 (機械可読契約 + Layer B/C 最小実装) を変えず、
実装段階で明らかになった品質/運用上の改善のみを追加している。
