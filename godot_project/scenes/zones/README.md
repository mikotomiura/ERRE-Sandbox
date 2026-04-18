# `scenes/zones/` — ゾーンシーン

ERRE-Sandbox の 5 ゾーンに対応する `*.tscn` を配置するディレクトリ。

| ファイル (予定) | ゾーン名 (schemas.py `Zone` enum) | 追加タスク |
| --- | --- | --- |
| `Study.tscn` | `study` | T17 + M5 |
| `Peripatos.tscn` | `peripatos` | T17 godot-peripatos-scene ★M2 MVP の主役 |
| `Chashitsu.tscn` | `chashitsu` | M5 zone 拡張 |
| `Agora.tscn` | `agora` | M5 zone 拡張 |
| `Garden.tscn` | `garden` | M5 zone 拡張 |

## ルール

- **ファイル名は PascalCase** (godot-gdscript SKILL ルール 1): `Peripatos.tscn`
- **Godot 内のノード名も PascalCase**: `$ZoneManager/Peripatos`
- **schemas.py `Zone` enum は lower_snake_case** (`"peripatos"`) — スキーマ ↔
  ノード名のマッピングは GDScript 側の `ZONE_MAP: Dictionary = {...}` で
  吸収する (patterns.md ルール 4 参照)
- **1 ゾーン 1 シーンファイル**。1 scene に複数ゾーンを混ぜない
- **.glb アセットは `../../assets/` 以下から `preload`** し、シーン内には
  バイナリを埋め込まない (git diff 可読性)

関連 Skill: `.claude/skills/godot-gdscript/SKILL.md` ルール 4。
