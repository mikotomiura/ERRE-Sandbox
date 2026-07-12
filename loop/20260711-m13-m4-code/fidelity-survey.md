# M4 fidelity 先行研究サーヴェイ + 改善計画（3D society viewer）

> user 指示「geometry-nodes/Godot の人体デザイン・各世界の情景制作・プロジェクションマッピング等の先人の
> 具体的知見・財産をサーヴェイしたのちに改善」（2026-07-12）に対する survey。3 subagent が web で裏取り。
> dev-tooling の技術サーヴェイ（thesis 正典でないため `docs/references.md` には未登録、出典はインライン）。
> **全案の制約適合**: construction≠measurement（R-budget=0、記録済み society の表現であって測定値の可視化でない、
> over-read 禁止）/ GPL 分離（bpy は erre-sandbox-blender/、Godot は GDScript）/ offline 決定再生 / dev-only。

## 決定性の共通前提（3 survey 収束）
- Blender geometry nodes は本質的に決定的。Random Value は **ID/index 駆動**で再現可能（seed に固定 Integer 配線、
  または index を ID に）。**Object Info の seed 出力（UUID ハッシュ）は使わない**（非決定源）。→ 既存 index 駆動
  レイアウトは seed-free 決定性を満たす。
- Godot 側の光・空気・投影（WorldEnvironment/fog/tonemap/GI/Decal/light_projector/Viewport）は geometry を触らず
  GPL 非依存・dev-only に閉じられる。決定性 witness は M4 で確立済み「量子化構造 fp（glTF accessor min/max）+
  placement canonicalizer 比較」を踏襲（視覚出力そのものは witness にしない）。
- アセットは **CC0 一択**（Poly Haven / ambientCG / Quaternius / Kenney / poly.pizza）= GPL 汚染なし・埋め込み可・
  商用可・帰属不要。**Mixamo は raw 再配布懸念で回避**。

---

## トラック A — agent（人体）デザイン
1. **[最小] Godot per-agent 色 + primitive prop**（GDScript のみ、GPL 回避、決定的）: `material_override` を
   index→HSV 固定式（黄金角 `hue=index*0.618%1`）で付与 + 識別 prop（球=天文/円錐=帽子/立方=書物）。シルエットを
   変えず色×小道具で識別性が跳ねる（stylized の王道）。★まずこれで十分な可能性大。
2. **CC0 低ポリ humanoid**（Quaternius/Kenney/poly.pizza の rigged .glb）+ 案1 の色分け。primitive→人型で
   シルエットが「人」に。公開リポジトリ同梱可。初手は静的 or 単純 idle（決定再生を壊さない）。
3. **Blender Skin Modifier で stylized 人型 bake → .glb**（GPL 隔離側）: persona 別少数パラメータ（身長/肩幅/prop）
   で肉付け→apply→.glb。シルエット自体を persona 別に。寸法は定数テーブル（seed-free）。
4. **geometry-nodes で index 駆動 stylized silhouette**（M4 の geo-nodes 資産と統一）: プリミティブ合成の記号的
   人型を ID 駆動で。フル人体 GN は新興＝標準外ゆえ記号的に留める。
5. **[defer] VRM トゥーンアバター**: dev-only には過剰、determinism 検証面最大。北極星。
- 出典: Blender Random Value <https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/utilities/random_value.html> /
  GeoNodes for game dev <https://www.strayspark.studio/blog/blender-geometry-nodes-game-dev-2026> /
  Rigged char w/ GeoNodes <https://80.lv/articles/a-rigged-character-animated-with-geometry-nodes-in-blender> /
  Skin Modifier <https://www.gamedev.net/articles/visual-arts/using-the-skin-modifier-in-blender-to-quickly-model-creatures-r5004/> /
  Quaternius CC0 <https://quaternius.com/> / poly.pizza People <https://poly.pizza/explore/People-and-Characters> /
  Mixamo FAQ（再配布不可）<https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html> /
  Silhouette design <https://adventuregamers.com/article/a-look-at-graphics-character-design-in-silhouette> /
  Stylized art <https://meliorgames.com/game-art-design/what-is-stylized-game-art-techniques-and-examples/>

## トラック B — 各世界の情景アート
1. **[最小] WorldEnvironment tonemap = ACES + adjustments**（Godot のみ）: 明部 desaturate + contrast/saturation
   1.1–1.2、direct=やや黄・ambient=青/紫で「画」になる。
2. **時間帯ライティング preset**（DirectionalLight 角度/色 + ProceduralSky）: chashitsu=夕(暖・長影)/agora・peripatos=
   正午(明石)/garden=柔朝/study=室内間接。固定 preset ゆえ決定的。
3. **Volumetric fog で空気感**（統合 GPU でも軽い、FogVolume で領域限定）: peripatos 柱廊に god-ray、garden/chashitsu
   に低もや。density のみ zone 別。
4. **zone 別マテリアルパレット**（様式）: 和(chashitsu/garden)=アースカラー低彩度・土壁/木/竹/苔/砂利、枯山水=岩=山・
   砂利目=水波紋。ギリシャ(agora/peripatos)=大理石白+Doric 列柱・stoa 列柱廊。CC0 PBR(ambientCG) を index で material_index 切替。
5. **象徴 prop を index 駆動 GN 追加**: chashitsu=石灯籠/蹲踞/飛石/竹垣、garden=砂利目+配石、agora=stoa ニッチ+据物、
   peripatos=列柱リズム+ベンチ、study=書架/書見台。primitive 合成 GN、index%N で決定的振り分け。
6. **Doric 比率・stoa リズムで列柱様式化**: 柱径:柱高≈1:7 + entablature 帯 + 簡易 cornice を index 駆動、柱間反復。
7. **[GPU 要確認] SDFGI で間接光・接地感**: 屋外 zone に。chashitsu/study は ReflectionProbe/軽 GI 代替。zone 単位 ON/OFF。
8. **CC0 HDRI で IBL**（Poly Haven/ambientCG、埋め込み可）: zone 別 HDRI で空気感が跳ねる。ProceduralSky と二択/併用。
- 出典: Volumetric fog <https://docs.godotengine.org/en/stable/tutorials/3d/volumetric_fog.html> /
  Fog volumes <https://godotengine.org/article/fog-volumes-arrive-in-godot-4/> /
  Godot 光環境 <https://hexaquo.at/pages/environment-and-light-in-godot-setting-up-for-photorealistic-3d-graphics/> /
  WorldEnvironment/PBR <https://bitsoulhosting.com/marketplace/blog/godot-4-environment-lighting-worldenvironment-sky-shaders-pbr> /
  Tonemap <https://school.gdquest.com/glossary/tonemap> / 枯山水 <https://en.wikipedia.org/wiki/Japanese_dry_garden> /
  茶室 <https://illustrarch.com/art-culture/74677-japanese-tea-house.html> / Stoa <https://en.wikipedia.org/wiki/Stoa> /
  Doric <https://www.architecturecourses.org/learn/doric-architecture> / Poly Haven License <https://polyhaven.com/license> /
  ambientCG <https://ambientcg.com/>

## トラック C — プロジェクションマッピング（Godot 翻訳）
- 本質 = 「面と光の一致」（warping + edge blending）、原点 = 静止造形に記録済みの語り/表情を投影して活かす（1969
  Haunted Mansion 歌う胸像、Svoboda Laterna Magika）→ **offline 決定再生と相性が良い**。
- Godot 手段: **Decal**（面へテクスチャ投影、normal/distance_fade）/ **Light3D `light_projector`**（gobo、要
  shadow_enabled + Forward+）/ **triplanar shader**（UV 非依存 world 投影）/ **SubViewport→ViewportTexture**（動的映像）。
1. **[最小] Decal で agent 軌跡を地面投影**: 記録済み経路を光の帯/足跡に。ERRE モードで色分け。
2. **SpotLight `light_projector` で zone 象徴 gobo**（格子/木漏れ日/円相）: 認知モード入場で光を強める。要 Forward+。
3. **発話を床/壁に triplanar 投影**: Label3D→SubViewport→triplanar albedo。日本語フォント埋め込み・解像度固定で決定的。
4. **SubViewport で「内面(reasoning trace)」を茶室/書斎の面に投影**: 記録済みトレース**文字列**を表示（数値メトリクス
   でない = over-read 回避）。replay 該当区間のみ有効化。
5. **zone 認知モードを色光 warping で全景投影**: categorical state の色分け（連続メトリクス mapping はしない）。
6. **[defer] mirror/self-other seam を投影の映り込みで**（M2 Layer2 landed 後）。
- 出典: Projection mapping <https://en.wikipedia.org/wiki/Projection_mapping> /
  史 <https://studiogiggle.co.uk/event/projection-mapping-a-short-history/> /
  Decals <https://docs.godotengine.org/en/stable/tutorials/3d/using_decals.html> /
  Light3D <https://docs.godotengine.org/en/stable/classes/class_light3d.html> /
  Triplanar <https://godotshaders.com/shader/triplanar-mapping/> /
  Viewport as texture <https://docs.godotengine.org/en/stable/tutorials/shaders/using_viewport_as_texture.html>

---

## 推奨する段階実装（コスト小→大、制約適合順）
- **Wave 1（Godot のみ・GPL/決定性リスクゼロ・即効）**: A1（per-agent 色+prop）/ B1（ACES tonemap）/ B2（時間帯
  preset）/ B3（volumetric fog）/ C1（Decal 軌跡）。dev viewer 拡張のみ、アセット DL 不要。「素朴さ」を最大効率で緩和。
- **Wave 2（CC0 アセット同梱・要 network DL = user 承認）**: A2（CC0 humanoid）/ B8（CC0 HDRI）/ B4（CC0 PBR パレット）。
  ライセンス出所を NOTICE 記録。
- **Wave 3（Blender GN 側・様式化本体）**: B5/B6（象徴 prop + Doric/stoa 比率）/ A3/A4（人型 bake）。witness は M4 の
  量子化構造比較を再利用。erre-sandbox-blender/ 内で完結。
- **Wave 4（要 GPU 予算 / 別 ADR 待ち）**: B7（SDFGI）/ C3/C4（発話・内面投影、フォント/Viewport 決定性の手当て）/
  A5（VRM）/ C6（mirror、Layer2 待ち）。
- **別軸（構築タスク）**: 「複数 zone・多エージェントのリッチな society run を録る」= golden を豊かにする（現 golden は
  2 agent 全 peripatos）。動きの乏しさはこれで解消。measurement 非再入を守る record-mode 拡張。
