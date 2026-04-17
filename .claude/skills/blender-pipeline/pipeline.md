# Blender Pipeline — エクスポートワークフロー詳細

---

## エクスポートワークフロー全体像

```
┌─────────────────────────────────────────────────────────┐
│ erre-sandbox-blender/ (GPL-3.0)                         │
│                                                         │
│  [1] Blender で制作                                      │
│      assets/avatar_kant.blend                            │
│            │                                             │
│  [2] リグ検証                                            │
│      blender --background ... --python rig_validator.py  │
│            │                                             │
│  [3] ヘッドレスエクスポート                               │
│      blender --background ... --python batch_export.py   │
│            │                                             │
└────────────┼────────────────────────────────────────────┘
             │
             ↓ .glb ファイル (バイナリ、ライセンス感染なし)
             │
┌────────────┼────────────────────────────────────────────┐
│ erre-sandbox/ (Apache-2.0 OR MIT)                       │
│            │                                             │
│  [4] godot_project/assets/avatars/Kant.glb               │
│            │                                             │
│  [5] Godot が .import ファイルを自動生成                  │
│      → AnimationPlayer / AnimationTree で使用            │
└─────────────────────────────────────────────────────────┘
```

**重要**: `.glb` ファイル自体は「データ」であり、GPL の著作権 (copyleft) は及ばない。
Blender で生成した .glb を Apache/MIT プロジェクトに含めることは法的に問題ない。
GPL が感染するのは「bpy を import するソースコード」のみ。

---

## Blender ↔ Godot 命名規則対応表

### Bone 命名 (Mixamo 互換)

| Bone 名 | 役割 |
|---|---|
| `Hips` | ルートボーン |
| `Spine` / `Spine1` / `Spine2` | 背骨 |
| `Neck` / `Head` | 首・頭 |
| `LeftShoulder` / `LeftArm` / `LeftForeArm` / `LeftHand` | 左腕 |
| `RightShoulder` / `RightArm` / `RightForeArm` / `RightHand` | 右腕 |
| `LeftUpLeg` / `LeftLeg` / `LeftFoot` | 左脚 |
| `RightUpLeg` / `RightLeg` / `RightFoot` | 右脚 |

---

## リグ要件チェックリスト

### エクスポート前 (Blender 内)

- [ ] **Armature が 1 つだけ**: 複数 Armature は Godot インポート時にエラーの原因
- [ ] **Bone 名が Mixamo 互換**: 上記テーブルに準拠
- [ ] **Rest Pose が T-Pose**: Retarget しやすい標準姿勢
- [ ] **Apply All Transforms**: `Ctrl+A` → All Transforms を適用済み
- [ ] **Modifiers を Apply**: Mirror, Subdivision 等のモディファイアを Apply 済み
- [ ] **Weight Paint が全頂点に設定**: Vertex Group に割り当てのない頂点がないか
- [ ] **ポリゴン数 < 5,000**: Decimate Modifier で調整
- [ ] **テクスチャ 512x512 以下**: Image Editor でリサイズ
- [ ] **マテリアル**: Principled BSDF を使用 (glTF PBR に自動変換)
- [ ] **UV マップ**: 1 つの UV マップのみ (命名: `UVMap`)

### アニメーション

- [ ] **Action 名が PascalCase**: `Idle`, `Walking`, `Sitting`, `Bowing`, `Speaking`, `Meditating`
- [ ] **ループアニメーション**: Idle / Walking / Sitting / Speaking / Meditating は NLA でループ設定
- [ ] **ワンショットアニメーション**: Bowing はループなし
- [ ] **FPS = 30**: Godot のデフォルトと一致
- [ ] **Fake User を設定**: Action が自動削除されないよう F ボタンで保護

---

## ヘッドレスエクスポートの実行例

### 単一アバターのエクスポート

```bash
blender --background \
  erre-sandbox-blender/assets/avatar_kant.blend \
  --python erre-sandbox-blender/scripts/batch_export.py \
  -- KantAvatar

# 出力: erre-sandbox/godot_project/assets/avatars/KantAvatar.glb
```

### 全アバターの一括エクスポート

```bash
#!/bin/bash
# erre-sandbox-blender/scripts/export_all.sh
ASSETS_DIR="erre-sandbox-blender/assets"
SCRIPT="erre-sandbox-blender/scripts/batch_export.py"

for blend_file in "$ASSETS_DIR"/avatar_*.blend; do
    name=$(basename "$blend_file" .blend | sed 's/avatar_//')
    # snake_case → PascalCase
    pascal_name=$(echo "$name" | sed -E 's/(^|_)([a-z])/\U\2/g')
    echo "Exporting: $blend_file → ${pascal_name}Avatar.glb"
    blender --background "$blend_file" --python "$SCRIPT" -- "${pascal_name}Avatar"
done
```

---

## リグ検証スクリプト

```python
# erre-sandbox-blender/src/erre_sandbox_blender/rig_validator.py
# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
import sys

REQUIRED_BONES = [
    "Hips", "Spine", "Spine1", "Spine2", "Neck", "Head",
    "LeftShoulder", "LeftArm", "LeftForeArm", "LeftHand",
    "RightShoulder", "RightArm", "RightForeArm", "RightHand",
    "LeftUpLeg", "LeftLeg", "LeftFoot",
    "RightUpLeg", "RightLeg", "RightFoot",
]

REQUIRED_ACTIONS = ["Idle", "Walking", "Sitting", "Bowing", "Speaking", "Meditating"]

MAX_FACES = 5000


def validate() -> list[str]:
    """Validate the current .blend file for Godot export readiness."""
    errors: list[str] = []

    # Armature チェック
    armatures = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
    if len(armatures) != 1:
        errors.append(f"Expected 1 Armature, found {len(armatures)}")
    elif armatures:
        arm = armatures[0]
        bone_names = {b.name for b in arm.data.bones}
        for required in REQUIRED_BONES:
            if required not in bone_names:
                errors.append(f"Missing bone: {required}")

    # ポリゴン数チェック
    for obj in bpy.data.objects:
        if obj.type == "MESH":
            face_count = len(obj.data.polygons)
            if face_count > MAX_FACES:
                errors.append(f"Mesh '{obj.name}' has {face_count} faces (max {MAX_FACES})")

    # アニメーションチェック
    action_names = {action.name for action in bpy.data.actions}
    for required in REQUIRED_ACTIONS:
        if required not in action_names:
            errors.append(f"Missing action: {required}")

    # Modifier チェック
    for obj in bpy.data.objects:
        if obj.type == "MESH" and obj.modifiers:
            errors.append(
                f"Mesh '{obj.name}' has unapplied modifiers: "
                f"{[m.name for m in obj.modifiers]}"
            )

    return errors


if __name__ == "__main__":
    errors = validate()
    if errors:
        print("VALIDATION FAILED:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("VALIDATION PASSED: Ready for export")
        sys.exit(0)
```

使用方法:
```bash
blender --background avatar_kant.blend \
  --python erre-sandbox-blender/src/erre_sandbox_blender/rig_validator.py
```
