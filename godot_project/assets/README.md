# `assets/` — 3D モデル・テクスチャ

Blender でオーサリングした `.blend` を `.glb` にエクスポートして置くディレクトリ。

## ルール — GPL 分離

Blender は **GPL-2+** であり、`import bpy` したコードは GPL 派生物になる。
したがって:

1. **このディレクトリに `.blend` / `.py` を置かない** — GPL 汚染を避ける。
   `.blend` は別パッケージ `erre-sandbox-blender/` (GPL-3) に配置し、
   そこから `blender --background --python export.py` で `.glb` を出力して
   本ディレクトリに置く
2. **ここには `.glb` / `.png` / `.jpg` / `.wav` など Apache-2.0 / MIT /
   CC-BY / CC0 互換フォーマットのみ** を置く
3. **`.gltf` + 外部テクスチャ** よりも **`.glb` 単一ファイル** を推奨
   (hash 安定性・プラットフォーム互換性)

関連 Skill: `.claude/skills/blender-pipeline/SKILL.md` (Blender → glTF
エクスポートスクリプト、GPL 分離の法的根拠)

## 予定される配置 (M4+)

```
assets/
├── avatars/         # 偉人アバター (Kant.glb, Nietzsche.glb, ...)
├── environment/     # ゾーン背景 (Linden-Allee.glb 等)
└── textures/        # 単独テクスチャ (skybox 等)
```

T15 時点では空。Blender パイプライン整備 (M4) で実アセット追加。
