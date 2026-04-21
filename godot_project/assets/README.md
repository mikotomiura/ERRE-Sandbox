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
├── environment/     # ゾーン背景 (chashitsu_v1.glb, ...) — M6-C で初着地
└── textures/        # 単独テクスチャ (skybox 等)
```

## M6-C (2026-04-22): chashitsu_v1 着地経路

- ソース: `../../erre-sandbox-blender/scripts/export_chashitsu.py`
  (procedural builder: 6×6 m / 高 3.5 m / 床の間 / 囲炉裏 / 釜 / 茶碗 x2 / 切妻屋根)
- ビルド: `blender --background --python erre-sandbox-blender/scripts/export_chashitsu.py`
- 成果物: `environment/chashitsu_v1.glb` (このディレクトリに自動配置)
- 消費側: `../scenes/zones/Chashitsu.tscn` が `load_from_path` で optional に読み込む
  — `.glb` 未生成でも primitive-only の fallback 姿で boot 可能。

他 4 ゾーン (study / agora / garden) は M7 で同じパターンを適用。
