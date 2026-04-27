# World asset Blender pipeline — primitive box の解消と建物多様化

## 背景

live 検証 issue A2+A3 + ζ-3 verify frame (observation.md):
- A2 (04/26) 「のっぺりとした感じ・茶室など世界自体がすごい薄い感じ」
- A3 (04/21) 「茶室など現在建てられているフォールドの建物をもう少し
  大きく + デザインも多様性を持たせる」

ζ-3 verify でも `chashitsu` zone は primitive box / plane で、AO/Fog/
法線マップ全欠落。`erre-sandbox-blender/` (GPL-3.0、本体と分離) は scaffold
済だが `assets/environment/` への .glb pipeline 未到達。`Chashitsu.tscn:4-8`
の "Blender-produced .glb supersedes when present" コメントだけ残存。

## ゴール

`.blend` → headless `.glb` export → `godot_project/assets/environment/`
配置 → Godot zone scene が `.glb` 優先 fall-back する pipeline を動作
させる。最低 1 zone (chashitsu) で primitive 置換完了。

## スコープ

### 含むもの
- `blender --background --python` ヘッドレス export script
- chashitsu の本格モデル化 (4畳半 + 床の間 + nijiri-guchi + matsukaze
  iron kettle 配置点)
- AO bake / lightmap / 法線マップ
- Godot 側 `Chashitsu.tscn` の `.glb` 優先 fall-back
- F2 placeholder humanoid avatar との衝突確認

### 含まないもの
- 全 5 zone 置換 (chashitsu のみで V&V)
- texture 高精細化
- skinning アニメーション (`agent-presence-visualization` の F2 担当)

## 受け入れ条件

- [ ] `make export-blender` 等の単一コマンドで `chashitsu.glb` build
- [ ] CI で GPL 分離維持 (`bpy` import が `src/erre_sandbox/` に漏れない)
- [ ] Godot で `.glb` 配置時は primitive を suppress、fall-back 時 primitive
- [ ] live G-GEAR で chashitsu zone が建物として認識可能
- [ ] `architecture-rules` Skill の GPL 分離条項 test gate

## 関連ドキュメント

- `architecture-rules` / `blender-pipeline` / `godot-gdscript` Skill
- `.steering/20260426-m7-slice-zeta-live-resonance/decisions.md` D2
