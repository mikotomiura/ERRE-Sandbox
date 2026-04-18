# T16 godot-ws-client

## 背景

T15 `godot-project-init` で `godot_project/` の scaffold が完了し、
`MainScene.tscn` に `WebSocketClient (Node)` が配置されているが `.gd` は
未 attach の状態。Phase P MacBook 側ラインの 2 件目として、この空ノードに
WebSocket クライアントとルーティングロジックを実装する。

Contract-First 方針 (MASTER-PLAN §2.2) により、T14 `gateway-fastapi-ws`
(G-GEAR 側) の完成を待たずに開発する。T07 で固めた
`fixtures/control_envelope/*.json` (tick=42 の coherent scenario) を
developer fixture mode で再生し、実機 gateway 完成時に差し替え可能な
構造にする。

7 kind (handshake / agent_update / speech / move / animation / world_tick /
error) が `schemas.py` の discriminated union で凍結済み (T05)。
Godot 側は `kind` フィールドで分岐し、各ハンドラへ dispatch する。

## ゴール

- `WebSocketClient.gd` が **実 WebSocket 接続** と **自動再接続 (5 秒間隔)** を
  `.claude/skills/godot-gdscript/patterns.md §1` 準拠で提供する
- **Developer fixture mode** で `fixtures/control_envelope/*.json` を
  filesystem から読み、`envelope_received` シグナルに流せる
- **EnvelopeRouter** (or AgentManager) が 7 kind を全て受け取り、
  対応ハンドラにルーティングする (未知 kind は `push_warning`、crash しない)
- Godot headless テストで fixture 再生 → envelope dispatch の回帰が回る
- `.claude/skills/godot-gdscript/SKILL.md` チェックリストを全て満たす

## スコープ

### 含むもの

- `godot_project/scripts/WebSocketClient.gd` — WebSocketPeer + 再接続 +
  `envelope_received (Dictionary)` / `connection_status_changed (bool)` signal
- `godot_project/scripts/EnvelopeRouter.gd` — `kind` で分岐し、
  AgentManager / WorldManager / SpeechBubbleContainer / DebugOverlay 等へ dispatch
- `godot_project/scripts/AgentManager.gd` — 動的エージェント生成 + envelope 適用
  (patterns.md §4 相当、ただし T16 ではアバターシーンなしで `print`/シグナル発火のみ)
- **Developer fixture mode** — `FixturePlayer.gd` または `WebSocketClient.gd` の
  モード切替で `fixtures/control_envelope/*.json` を `FileAccess.open` → parse →
  `envelope_received` 発火 (順序・間隔は設計時決定)
- エラー処理: malformed JSON / unknown kind / connection lost / fixture not found
- `tests/test_godot_ws_client.py` — Godot headless で fixture 再生 → ログ検査

### 含まないもの

- T17 `godot-peripatos-scene` (具体的 3D ゾーン制作 / NavigationMesh)
- AnimationTree / AgentAvatar のアニメーションクリップと .glb アセット (T17 以降)
- 実 gateway への接続検証 (T14 完成後に T19 で E2E)
- `ui/godot_bridge.py` Python 側ブリッジ (Python 側は T14 `gateway-fastapi-ws` の責務)
- msgpack サポート (MVP は JSON のみ。architecture.md §4 に準拠)
- ERRE モード視覚効果 (M5 `godot-zone-visuals` 以降)

## 受け入れ条件

- [ ] `WebSocketClient.gd` が `.claude/skills/godot-gdscript/SKILL.md`
      ルール 1-6 を満たす (命名 / 再接続 / kind 分岐 / Python 不混入 等)
- [ ] 7 kind (handshake / agent_update / speech / move / animation / world_tick /
      error) 全てが `EnvelopeRouter` で受信・ルーティングできる
- [ ] Developer fixture mode で `fixtures/control_envelope/*.json` を再生し、
      handshake → agent_update → speech → move → animation の順序がログ出力される
- [ ] 未知 `kind` を受けた時に `push_warning` で警告し、crash しない
- [ ] gateway 切断 → 5 秒 → 自動再接続のサイクルが godot headless で観測できる
- [ ] `tests/test_godot_ws_client.py` が Godot headless boot → fixture 再生 →
      正常終了 (exit 0) を検証する (Godot 未 install 環境は skip)
- [ ] `godot_project/` 配下に `.py` ファイルを追加していない
      (architecture-rules / godot-gdscript ルール 6)
- [ ] `ruff check` / `ruff format --check` / `mypy src` / `pytest` が全て緑
      (既存 T15 テスト含む)

## 関連ドキュメント

- `.claude/skills/godot-gdscript/SKILL.md` — ルール 1-6、チェックリスト
- `.claude/skills/godot-gdscript/patterns.md` — §1 WebSocket 完全実装、
  §2 MainScene 階層、§4 AgentManager
- `.steering/20260418-implementation-plan/MASTER-PLAN.md` §4.2 — T16 依存 (T15)、
  参照 Skill (godot-gdscript, error-handling)
- `.steering/20260418-godot-project-init/decisions.md` — 判断 3
  (MainScene 階層 patterns.md §2 準拠) / 判断 5 (pytest headless boot)
- `fixtures/control_envelope/README.md` — T07 specimen (tick=42 Kant peripatos)
- `src/erre_sandbox/schemas.py` §7 — ControlEnvelope discriminated union
- `docs/architecture.md` §4 — G-GEAR ↔ MacBook WebSocket 接続
- `.claude/skills/error-handling/` — WebSocket 再接続パターン (Python 側参考)

## 運用メモ

- **タスク種別**: 新機能追加 → 次コマンド `/add-feature`
- **破壊と構築 (`/reimagine`) 適用: Yes (2026-04-18 ユーザー承認)**
  - **理由**:
    - Fixture 再生モードの設計に複数案あり (例: A. 内部 array / B. ls 順 /
      C. playlist YAML / D. `FixturePlayer.gd` 分離 vs `WebSocketClient.gd` 内蔵)
    - `EnvelopeRouter` と `AgentManager` の責務分割も複数案
      (A. Router が全 kind を処理 / B. 各 Manager に dispatch / C. Observer pattern)
    - godot-gdscript patterns.md §1/§4 の密接依存は固いが、上位設計で案を
      破壊・再生成し比較する価値が高い
  - **適用タイミング**: `/add-feature` で design.md 初回案を作成後、実装着手前
- **スコープ確定事項** (2026-04-18 ユーザー承認):
  - `AgentManager.gd` は T16 に含む (ただしアバター生成なし、**ログスタブのみ**)
  - Fixture 再生は **0.5s 間隔の連続再生** を最小案とし、間隔パラメータ化は後続
    (design で具体化)
