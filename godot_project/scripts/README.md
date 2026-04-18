# `scripts/` — GDScript

MainScene とそのサブノードに attach される `.gd` を置くディレクトリ。

| ファイル | 役割 | 追加タスク |
| --- | --- | --- |
| `WorldManager.gd` | MainScene root。boot ログ + 後続で WebSocketClient ↔ AgentManager の配線 | T15 (本 dir 設置時に scaffold) |
| `WebSocketClient.gd` | `ws://g-gear.local:8000/stream` を poll、`envelope_received(Dictionary)` signal を emit | T16 godot-ws-client |
| `AgentController.gd` | `CharacterBody3D` 派生。受信した `agent_update` / `move` / `animation` / `speech` で自身を更新 | T16 / T17 |
| `AgentManager.gd` | 新 agent_id の出現時にアバターを instance、既存は AgentController へ dispatch | T16 |

## ルール (godot-gdscript SKILL ルール 1)

| 対象 | 規則 |
| --- | --- |
| ファイル名 / class_name | PascalCase |
| 変数・関数 | snake_case |
| 定数 | UPPER_SNAKE_CASE |
| signal | snake_case |

## 参考実装

`.claude/skills/godot-gdscript/patterns.md` に WebSocketClient /
AgentController の完全実装例がある。T16 着手時にそのままコピーで start。

## 禁止

- `.py` ファイル (architecture-rules; Python は `src/erre_sandbox/` に置く)
- GPL 依存ライブラリの import
