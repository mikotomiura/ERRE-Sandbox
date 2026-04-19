# 設計判断 — T19 実行フェーズ

## D1: FakeEmbedder を tests/ 内に実装 (本体 embedding.py を触らない)

**判断**: `tests/test_integration/conftest.py` に `FakeEmbedder` クラスを追加し、
`src/erre_sandbox/memory/embedding.py` の `EmbeddingClient` を継承しない
ダックタイピングで置き換える。

**理由**:
- 本体 `embedding.py` の `QUERY_PREFIX` / `DOC_PREFIX` は T10 で強制ルール (D5) として
  凍結済み。テスト側で同じプレフィックスを検証するために fake を作るのは自然だが、
  本体に `FakeEmbedder` 相当のクラスを置くと「テスト用コードが本体に漏れる」アンチパターン
- `memory/store.py` の insert API は embedding を引数で受け取る設計 (T10 実装参照) のため、
  fake を差し込むには「embedding を呼ぶ側 (= テスト)」で差し替えれば十分
- architecture-rules Skill: `tests/` は本体へ依存、本体は `tests/` に非依存という方向を保つ

**実装** (実装本体は `tests/test_integration/conftest.py` 参照):
```python
class FakeEmbedder:
    """Deterministic embedder for Layer B2 memory tests.

    hash(text) -> float32 vector[768] with DOC_PREFIX/QUERY_PREFIX enforced.
    """
    def __init__(self) -> None:
        self.last_docs: list[str] = []
        self.last_queries: list[str] = []

    async def embed_document(self, text: str) -> list[float]:
        prefixed = f"{DOC_PREFIX}{text}"
        self.last_docs.append(prefixed)  # prefix 付きで記録、検証側で startswith 確認
        return self._vec(prefixed)

    async def embed_query(self, text: str) -> list[float]:
        prefixed = f"{QUERY_PREFIX}{text}"
        self.last_queries.append(prefixed)
        return self._vec(prefixed)
```

**last_docs/last_queries に prefix 付きで格納する理由**: テスト側で
`last_docs[i].startswith(DOC_PREFIX)` を assert するための自然な形。
prefix なしで記録すると「付与前の生テキスト」と「実 embedding 入力」が分離し、
契約検証の意図が不明瞭になる。

## D2: Layer C を smoke run 1 回に限定

**判断**: 実 Ollama + 実 sqlite-vec を使う Layer C テストは CI に載せず、
G-GEAR 側で手動 smoke run 1 回を行い、結果を本ファイルに追記する。

**理由**:
- CI 環境では Ollama 起動 + `qwen3:8b` (5.2GB) ロードが非現実的
  (GitHub Actions の VRAM 無し、時間制限 6h 内に納まらない)
- 本 PR の目的は「skeleton 点灯 + 契約検証」であり、実推論の回帰は
  M7 observability 以降のスコープ (MASTER-PLAN §5)
- MVP M2 検収条件 §4.4 は「ログで『10秒ごとの認知サイクル完了』確認」
  と手動検証を前提としており、smoke run 1 回で十分

**Smoke run 結果** (2026-04-19 G-GEAR 実施):

```
[2026-04-19] G-GEAR smoke run — ALL GREEN
- Ollama serve: ok (既起動、/api/tags 200 で models 2 件確認)
- qwen3:8b present: ok (ID 500a1f067a9f, 5.2 GB, Q4_K_M, 8.2B params)
- nomic-embed-text present: ok (ID 0a109f422b47, 274 MB, F16, 137M params)
- Gateway 起動: ok (uv run python -m erre_sandbox.integration.gateway --host 127.0.0.1 --port 8765)
- Gateway /health: ok (HTTP 200, {"schema_version":"0.1.0-m2","status":"ok","active_sessions":0})
- Gateway shutdown: ok (port 8765 リッスン解放確認)
ログ: logs/m2-smoke-run-gateway-20260419.txt
```

**補足**: 本 smoke run は WS `/ws/observe` への ad-hoc client 接続は含めなかった
(handshake の往復は test_gateway.py Layer B で 54 件 CI-green で保証済み)。
実接続の Live 検証は MacBook/Godot セッション合流時に `handoff-to-macbook.md`
の該当項目として実施する。

## D3: jsonl observability ロガーを opt-in env var にする

**判断**: `tests/test_integration/conftest.py` の `m2_logger` fixture は
環境変数 `M2_LOG_PATH` が設定されている場合のみ書き出しを行う no-op デフォルト。

**理由**:
- CI では log 書出しを抑制したい (artifact 肥大化、並列実行時の競合)
- 手動 Layer C smoke run や `pytest --count=3` reproducibility 検証の際に
  `M2_LOG_PATH=logs/m2-acceptance-run.jsonl uv run pytest ...` で点灯できれば十分
- t20-acceptance-checklist.md の ACC-LOGS-PERSISTED / ACC-REPRO-SEED は
  この fixture 経由で手動実行時に満たす運用

**実装方針**: fixture は常に存在し、env 未設定なら `log(...)` が no-op。
テストコード側は存在を意識せず `m2_logger.log(scenario_id, step, latency_ms, kind)` を呼ぶだけ。

## D4: 4 episodic + 1 semantic の書き分け方針

**判断**: `SCENARIO_MEMORY_WRITE` 実行時の memory write を、
以下のルールで `MemoryKind` にマップする:

| 書込内容 | kind | 数 |
|---|---|---|
| Kant が歩きながら観察した環境 (雲、光、風景) | `EPISODIC` | 3 |
| Kant が他エージェント/NPC と短く交わした挨拶 | `EPISODIC` | 1 |
| Kant の自問自答から蒸留された抽象的信念 (例: "Aesthetic judgment must be disinterested") | `SEMANTIC` | 1 |

**理由**:
- `scenarios.py` の `SCENARIO_MEMORY_WRITE` step 1 は
  「4 episodic + 1 semantic を memory-store へ書込」と明記
- CSDG 参照 (MASTER-PLAN.md §B.2 T10): 2 層構造 (ShortTerm=Episodic / LongTerm=Semantic) の
  比率。歩行中は episodic が主、semantic は reflection トリガー時のみ
- M4 以降 reflection が実装されたら比率は変わるが、M2 では固定比率で良い

**Python 側対応**: `test_scenario_memory_write.py` は上記 5 件をハードコードで inject し、
`MemoryStore.count_by_kind(MemoryKind.EPISODIC)` `== 4`,
`MemoryStore.count_by_kind(MemoryKind.SEMANTIC)` `== 1` で assert する。

## D5: tick_robustness で ManualClock ではなく TestClient 素のタイマ

**判断**: `test_scenario_tick_robustness.py` は `ManualClock.advance(dt)` を
使わず、`TestClient.websocket_connect` context manager の enter/exit で
disconnect/reconnect を表現する。

**理由**:
- `ManualClock` を使うと `WorldRuntime` を本物で立てる必要があり、
  本タスクの「MockRuntime + TestClient 最小構成」方針から逸脱
- disconnect/reconnect の本質は **session の 2 度目の `HandshakeMsg` 交換**。
  これは TestClient の `websocket_connect` を 2 回呼ぶだけで再現可能
- `fast_timeouts` fixture で `HANDSHAKE_TIMEOUT_S=0.3, IDLE_DISCONNECT_S=0.5`
  に絞り、テストが sub-second で完了する設計 (既存 test_gateway.py と同じ)
- agent_id 継続の検証は MockRuntime が持つ "agent_id を決めて inject" できる
  自由度を活かす (同じ id で両 session に inject)

**補足**: `HEARTBEAT_INTERVAL_S=1.0` は本体固定。3x 耐性の検証は
tick 番号 (tick=1, tick=3 を inject し tick=2 をスキップ) で代替し、
実時間経過をシミュレートしない (flaky 対策)。
