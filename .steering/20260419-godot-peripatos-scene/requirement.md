# T17 godot-peripatos-scene

## 背景

T16 `godot-ws-client` (PR #12) で Router の 7 専用 signal 契約が確立し、
`EnvelopeRouter` から `AgentManager` / `WorldManager` に伸びるパイプが
fixture 再生で動くことを headless で検証済み。ただし現在 `AgentManager.gd`
の各 handler は **`print()` ログスタブ**のみで、3D 視覚出力がない。

T17 の役割は 2 つ:

1. **Peripatos ゾーンを 3D 空間として具現化**する
   (`docs/glossary.md` で peripatos = 歩行路 / DMN 活性化 / 発散思考の場として
   定義。アリストテレス由来)
2. **Router signal → avatar 動作の接続を実装**する
   (`agent_updated` → avatar instance / `move_issued` → 位置移動 /
   `animation_changed` → アニメ名切替)

MASTER-PLAN §4.2 で T17 は T16 のみに依存 (工数 1 d)。依存 Skill は
`godot-gdscript`。patterns.md §2 (MainScene 階層) / §3 (AgentAvatar 構造) /
§4 (AgentManager 動的管理) / §5 (AnimationTree 設定手順) / ゾーン座標指針
(peripatos は (-20, 0, 0)〜(20, 0, 0) 東西 40m) を参照。

Phase P MacBook 側ラインの 3 件目。完了後は T18 (optional dashboard) と
T19 (両機 E2E) が続く。

## ゴール

- `scenes/zones/Peripatos.tscn` を新規作成し、MVP 最小の 3D 歩行路を描画
  (PlaneMesh ground / 東西方向のパスを示す簡易マーカー / 境界ボックス)
- `scenes/agents/AgentAvatar.tscn` を新規作成
  (patterns.md §3 準拠: CharacterBody3D + CapsuleMesh + CollisionShape3D +
  AnimationPlayer + Label3D SpeechBubble)
- `scripts/AgentController.gd` を新規作成
  (patterns.md §3 準拠: `agent_id` export / `update_from_envelope` /
  `set_animation` / `_physics_process` で target への直線補間移動)
- `scripts/AgentManager.gd` を拡張
  (patterns.md §4 準拠: `AgentAvatarScene` preload / `_agents` Dictionary /
  `get_or_create_agent` / Router signal → avatar 操作)
- `scripts/WorldManager.gd` を拡張
  (`ZoneManager` 配下に Peripatos.tscn を instance / `ZONE_MAP` 定数を導入)
- Fixture harness 再生時に Kant avatar が add_child される動作を headless で
  ログ検証
- Godot エディタで開いて Peripatos + Kant avatar が render できる状態
  (visual check は手動)

## スコープ

### 含むもの

- `scenes/zones/Peripatos.tscn`
  - PlaneMesh (40m x 8m) をパスとして敷設、StandardMaterial3D で淡色
  - 両脇に境界 BoxMesh 2 本 (あるいは CSG の薄い wall)
  - OmniLight3D 1 本または patterns.md §2 のディレクショナルライト流用
- `scenes/agents/AgentAvatar.tscn`
  - CharacterBody3D ルート + CollisionShape3D (CapsuleShape3D) + MeshInstance3D
    (CapsuleMesh で代用、glTF は M4+)
  - AnimationPlayer (アニメクリップは空、名前だけ登録 "Idle"/"Walking" 等)
  - Label3D SpeechBubble (patterns.md §3 準拠、visible=false 初期)
  - `AgentController.gd` を attach
- `scripts/AgentController.gd`
  - `@export agent_id: String`
  - `update_from_envelope(payload: Dictionary)` — target / animation / speech
  - `set_animation(action: String)` — `ANIMATION_MAP` でマッピング (T17 は
    `AnimationPlayer.play(anim_name)` の呼び出しまで、実クリップなしでも
    crash しないように `has_animation()` ガード)
  - `_physics_process(delta)` — `target_position` への直線補間 + `look_at`
  - `_show_speech(text)` — patterns.md §3 の 5 秒タイマ
- `scripts/AgentManager.gd` 拡張
  - `@export var agent_avatar_scene: PackedScene`
  - `_agents: Dictionary` で agent_id → AgentController
  - `get_or_create_agent(agent_id)` で lazy instance
  - `_on_agent_updated` で avatar の tick/position を反映
  - `_on_move_issued` で controller の target_position 更新
  - `_on_animation_changed` で controller の set_animation
  - `_on_speech_delivered` で controller の _show_speech
- `scripts/WorldManager.gd` 拡張
  - `ZONE_MAP: Dictionary = { "peripatos": preload(...) }`
  - `_ready()` で ZoneManager 配下に peripatos instance を add
  - (other zones は未実装、M5 で拡張)
- `scenes/MainScene.tscn` 修正
  - AgentManager ノードに `agent_avatar_scene` export を設定
- `tests/test_godot_peripatos.py` 新規作成
  - Peripatos.tscn / AgentAvatar.tscn の必須ファイル存在
  - fixture harness 再生後のログに `[AgentManager] avatar instantiated
    agent_id=a_kant_001` が現れる
  - `[AgentController] animation=` のログが `handshake/agent_update/speech/
    move/animation` ごとに期待動作
  - Godot 未 install 時は skip

### 含まないもの

- **glTF インポート / Blender アセット制作** (M4 `memory-semantic-layer` 以降、
  erre-sandbox-blender/ 別パッケージで GPL 隔離)
- **他 4 ゾーン** (study / chashitsu / agora / garden) — M5
  `world-zone-triggers` で一括追加
- **AnimationTree ステートマシン** — T17 は AnimationPlayer 単体で十分
  (実クリップなし、名前のみ)
- **NavigationMesh / ナビ経路探索** — 直線 lerp で代替、M5 ゾーン拡張時に
  再検討
- **ERRE モード視覚効果** (ライティング変化 / ポストプロセス) — M5
  `godot-zone-visuals`
- **UI Dashboard** — T18 optional
- **実 gateway 接続** — T14 完成後 T19 E2E

## 受け入れ条件

- [ ] `scenes/zones/Peripatos.tscn` が Godot エディタで問題なく開け、
      東西方向のパス + 地面 + 境界が render される
- [ ] `scenes/agents/AgentAvatar.tscn` が CharacterBody3D + CapsuleMesh +
      CollisionShape3D + AnimationPlayer + Label3D を含み、AgentController.gd
      を attach している
- [ ] `AgentController.gd` が patterns.md §3 テンプレ準拠で snake_case / 型
      ヒント / `has_animation()` ガード付き `set_animation` を備える
- [ ] `AgentManager.gd` が patterns.md §4 準拠で `get_or_create_agent()` +
      Router signal の 4 ハンドラ (agent_updated / speech_delivered /
      move_issued / animation_changed) が AgentController を操作する
- [ ] `WorldManager.gd` が `ZONE_MAP` 定数を持ち、起動時に peripatos を
      ZoneManager 配下に add_child する
- [ ] Fixture harness 再生で以下のログが順序通り出現:
      `[AgentManager] avatar instantiated agent_id=a_kant_001` →
      `[AgentController] agent_update tick=` →
      `[AgentController] speech=...` →
      `[AgentController] target set zone=peripatos` →
      `[AgentController] animation=walk`
- [ ] `tests/test_godot_peripatos.py` が headless 回帰で pass (Godot 未 install
      は skip)
- [ ] 既存 `tests/test_godot_project.py` / `test_godot_ws_client.py` /
      `test_envelope_kind_sync.py` / 全体 pytest / ruff / format / mypy が
      緑 (100+ pass のベースを維持)
- [ ] `godot_project/` 配下に `.py` ファイル不混入 (architecture-rules)
- [ ] `godot-gdscript` Skill チェックリスト全項目 pass

## 関連ドキュメント

- `.claude/skills/godot-gdscript/SKILL.md` — ルール 1-6
- `.claude/skills/godot-gdscript/patterns.md` — §2 MainScene 階層 / §3
  AgentAvatar / §4 AgentManager / §5 AnimationTree / ゾーン座標指針
- `.steering/20260418-implementation-plan/MASTER-PLAN.md` §4.2 — T17 行
- `.steering/20260418-godot-project-init/decisions.md` — 判断 3 (MainScene
  階層準拠) / 判断 5 (headless boot pytest)
- `.steering/20260418-godot-ws-client/decisions.md` — 判断 1 (3 スクリプト
  分離) / 判断 4 (class_name cross-ref 回避 → Node + has_signal duck typing)
- `docs/glossary.md` L13-14 — 身体的回帰 / Peripatos の定義
- `docs/functional-design.md` — 5 ゾーンの役割
- `docs/architecture.md` §5 フロー 2 反省 (peripatos 入室トリガー)
- `fixtures/control_envelope/*.json` — 再生シナリオ

## 運用メモ

- **タスク種別**: 新機能追加 → 次コマンド `/add-feature` (2026-04-19 ユーザー承認)
- **破壊と構築 (`/reimagine`) 適用: Yes (2026-04-19 ユーザー承認)**
  - **理由**:
    - **Avatar 構造**に複数案: A. CapsuleMesh 単一 / B. 上半身 + 下半身の複合
      mesh / C. 空ノードで glTF 差し替え待ち / D. ProceduralMesh
    - **移動制御**に複数案: A. 直線 lerp / B. Tween / C. NavAgent3D (NavMesh
      前提) / D. CharacterBody3D.move_and_slide
    - **アニメ設計**に複数案: A. AnimationPlayer のみ name logging /
      B. AnimationTree + placeholder graph / C. 完全省略で print のみ
    - **Peripatos 形状**に複数案: A. 直線パス / B. 曲がったパス /
      C. 周回 loop / D. 木々や階段などの景観要素の有無
    - **ZONE_MAP の配置**に複数案: A. WorldManager 内定数 / B. 別ファイル
      `ZoneCatalog.gd` / C. Autoload singleton
  - **適用タイミング**: `/add-feature` で design.md 初回案作成後、実装着手前
- **スコープ方針** (MASTER-PLAN 1d 見積から):
  - Avatar は **CapsuleMesh 単一** を default 案に、/reimagine で再評価
  - 移動は **直線 lerp (AgentController.gd 内 _physics_process)** を default
  - アニメは **AnimationPlayer + has_animation() ガード** を default
  - Peripatos は **直線パス + 地面 + 境界 box** を default
