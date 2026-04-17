---
name: blender-pipeline
description: >
  Blender アセットパイプラインと GPL 分離規則。
  erre-sandbox-blender/ パッケージのコードを書く・修正する時、
  .blend ファイルを .glb にエクスポートする時、
  Godot 向けスキンメッシュアバターのリグ・アニメーションを作成する時に必須参照。
  blender --background --python でヘッドレス自動化スクリプトを書く時、
  godot_project/assets/ に 3D モデルを追加する時に自動召喚される。
  import bpy を src/erre_sandbox/ に書くことは絶対禁止
  (architecture-rules Skill 参照)。
  GPL-3.0 ライセンスのコードは erre-sandbox-blender/ に完全分離すること。
allowed-tools: Read, Grep, Glob
---

# Blender Pipeline

## このスキルの目的

ERRE-Sandbox の 3D アバター (スキンメッシュ + アニメーション) は Blender で制作し、
.glb/.gltf 形式で Godot にインポートする。Blender の Python API (`bpy`) は GPL-2+ のため、
本体 (Apache-2.0 OR MIT) とは別パッケージに分離する。
この分離を確実に守りつつ、アセットパイプラインの自動化を実現する。

**注意**: この機能は将来的な拡張であり、MVP には含まれない。

## ルール 1: `import bpy` を src/erre_sandbox/ に書かない (最重要)

```python
# ❌ 絶��禁止 — src/erre_sandbox/ 内で bpy を import
# src/erre_sandbox/assets/export.py  ← このファイル自体が存在してはいけない
import bpy
from bpy.types import Object, Armature
```

```python
# ✅ 正しい — erre-sandbox-blender/ パッケージ内で bpy を使う
# erre-sandbox-blender/src/erre_sandbox_blender/export.py
import bpy  # GPL-3.0 パッケージ内なので OK
```

**理由**: `import bpy` を含むファイルは GPL-2+ の派生物となり、
Apache-2.0 OR MIT デュアルライセンスと法的に矛盾する。

## ルール 2: パッケージ分離

```
erre-sandbox/                    # Apache-2.0 OR MIT (本体)
├── src/erre_sandbox/            # bpy import 禁止
├── godot_project/assets/        # .glb ファイルの配置先
└── ...

erre-sandbox-blender/            # GPL-3.0-or-later (別リポジトリまたは別ディレクトリ)
├── src/erre_sandbox_blender/
│   ├── __init__.py
│   ├── export_avatar.py         # アバターエクスポート
│   ├── export_animation.py      # アニメーションエクスポート
│   └── rig_validator.py         # リグ検証
├── scripts/
│   └── batch_export.py          # CLI バッチエクスポート
├── assets/
│   └── *.blend                  # Blender ソースファイル
├── pyproject.toml
├── LICENSE                      # GPL-3.0-or-later
└── README.md
```

```python
# ✅ 良い例 — erre-sandbox-blender/ の pyproject.toml
# [project]
# name = "erre-sandbox-blender"
# license = "GPL-3.0-or-later"
# requires-python = ">=3.11"
# dependencies = []  # bpy は Blender 内蔵、pip install 不要
```

```python
# ❌ 悪い例 — 本体の pyproject.toml に bpy 依存を追加
# [project]
# dependencies = ["bpy"]  # GPL 混入！
```

## ルール 3: GPL ファイルのライセンスヘッダー

`erre-sandbox-blender/` 内のすべての `.py` ファイルに GPL ヘッダーを付与。

```python
# ✅ 良い例 — GPL ヘッダー
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 ERRE-Sandbox Contributors
#
# This file is part of erre-sandbox-blender.
# It is distributed under the terms of the GNU General Public License v3.0 or later.

import bpy
```

```python
# ❌ 悪い例 — ヘッダーなし
import bpy  # ライセンスが不明
```

## ルール 4: .blend → .glb エクスポートフロー

```
[1] Blender で制作
    erre-sandbox-blender/assets/avatar_kant.blend

[2] ヘッドレスエクスポート (CLI)
    blender --background avatar_kant.blend --python scripts/batch_export.py

[3] 出力先
    erre-sandbox/godot_project/assets/avatars/Kant.glb

[4] Godot でインポート
    Godot が .glb を自動認識して .import ファイルを生成
```

```python
# ✅ 良い例 — ヘッドレスエクスポートスクリプト
# erre-sandbox-blender/scripts/batch_export.py
# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
import sys
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent.parent / "erre-sandbox" / "godot_project" / "assets" / "avatars"


def export_glb(output_name: str) -> None:
    """Export current scene as .glb with animations."""
    output_path = OUTPUT_DIR / f"{output_name}.glb"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    bpy.ops.export_scene.gltf(
        filepath=str(output_path),
        export_format="GLB",
        export_animations=True,
        export_skins=True,
        export_morph=False,
        export_lights=False,
        export_cameras=False,
    )
    print(f"Exported: {output_path}")


if __name__ == "__main__":
    argv = sys.argv
    if "--" in argv:
        args = argv[argv.index("--") + 1:]
        if args:
            export_glb(args[0])
```

```bash
# ✅ 良い例 — CLI 実行
blender --background erre-sandbox-blender/assets/avatar_kant.blend \
  --python erre-sandbox-blender/scripts/batch_export.py \
  -- KantAvatar

# ❌ 悪い例 — Blender GUI でエクスポートして手動コピー
# → 再現不可能、自動化できない
```

## ルール 5: リグとアニメーションの命名規則 (Godot 互換)

Godot が glTF インポート時にアニメーション名を認識するため、
Blender 側で正確な命名が必要。

| Blender Action 名 | Godot での認識名 | 対応する agent action |
|---|---|---|
| `Idle` | `Idle` | `idle` |
| `Walking` | `Walking` | `walk` |
| `Sitting` | `Sitting` | `sit` |
| `Bowing` | `Bowing` | `bow` |
| `Speaking` | `Speaking` | `speak` |
| `Meditating` | `Meditating` | `reflect` |

**Bone 命名**: Mixamo 互換推奨 (Hips, Spine, Head, LeftArm, RightArm...)

## ルール 6: スキンメッシュの要件

```
必須要件:
- 単一の Armature オブジェクト
- Vertex Weight が全頂点に設定されている
- ポリゴン数: < 5,000 faces (ローポリ)
- テクスチャ: 512x512 以下 (モバイル互換)
- マテリアル: Principled BSDF → glTF PBR に自動変換される設定

非推奨:
- Shape Keys (Morph Targets) — パフォーマンスコスト
- 複数 Armature — Godot インポート時に問題を起こす
- 未適用の Modifier — エクスポート前に Apply
```

## チェックリスト

- [ ] `import bpy` が `src/erre_sandbox/` に存在しないか (`grep -r "import bpy" src/`)
- [ ] Blender コードが `erre-sandbox-blender/` に分離されているか
- [ ] GPL ライセンスヘッダーが全 `.py` ファイルに付いているか
- [ ] エクスポートが CLI (`blender --background --python`) で再現可能か
- [ ] 出力先が `godot_project/assets/` であるか
- [ ] アニメーション Action 名が PascalCase で Godot と一致しているか
- [ ] リグが単一 Armature で、Bone 名が Mixamo 互換か
- [ ] ポリゴン数が 5,000 faces 以下か

## 補足資料

- `pipeline.md` — エクスポート手順詳細、命名規則対応表、リグ要件チェックリスト

## 関連する他の Skill

- `architecture-rules` — GPL 分離ルール、`import bpy` 禁止の根拠
- `godot-gdscript` — エクスポートした .glb を Godot で使用するパターン
