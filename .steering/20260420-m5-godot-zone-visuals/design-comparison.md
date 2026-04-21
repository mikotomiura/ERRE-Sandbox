# 設計案比較 — m5-godot-zone-visuals

## v1 (初回案) の要旨

既存の `AgentController` + `SpeechBubble` Label3D を **そのまま拡張**する最小
変更パス。`AgentController` に `show_dialog_bubble` / `set_erre_mode` method と
8-mode `const Dictionary` を追加し、既存 `$SpeechBubble` を dialog_turn 用にも
流用。material 干渉対策は scene 側 `resource_local_to_scene=true` で対応。
Zone MVP は plane + 色違い + 装飾 box で「茶室/坐禅室っぽく」寄せる。

## v2 (再生成案) の要旨

**Godot-native composition** で責務分離。DialogBubble / BodyTinter /
ERREModeTheme を独立 script/scene に切り出し、AgentController は調停役に留める。
dialog bubble は SpeechBubble と別チャネル (z-offset で分離)、tint は 0.3s
Tween で滑らかに遷移、Zone は装飾ゼロで PlaneMesh + material のみ (MVP の
受け入れ条件を最小で満たす)。

## 主要な差異

| 観点 | v1 | v2 |
|---|---|---|
| **構造** | AgentController に method 集約 | 子ノードに script 分散 (DialogBubble / BodyTinter) |
| **Bubble channel** | SpeechBubble を流用 (dialog と speech 兼用) | 別 Label3D に分離 (同時表示も破綻しない) |
| **Tint transition** | hard swap (`albedo_color = new`) | 0.3s Tween で遷移 (strobe 回避) |
| **8-mode 色定義の置き場** | `AgentController.ERRE_MODE_COLORS` const | `ERREModeTheme.gd` (共有資源) |
| **material per-instance 化** | scene 側 `resource_local_to_scene = true` | BodyTinter._ready で `.duplicate()` |
| **Zone 装飾** | plane + 低座布団/岩 box 数個 | plane + material のみ (装飾ゼロ) |
| **新規ファイル数** | 4 (2 zone scene + 2 test) | 8 (2 zone + 2 test + DialogBubble scene + 3 script) |
| **修正ファイル数** | 4 (AgentController, AgentManager, WorldManager, AgentAvatar.tscn) | 4 (同左 + AgentAvatar.tscn の script attach 数箇所) |
| **.tscn 編集量** | AgentAvatar.tscn に 2 箇所 (modulate 初期値 + local_to_scene) | AgentAvatar.tscn に script attach + 新子ノード (DialogBubble) |
| **AgentController 肥大化** | ある (method 2 個 + const dict) | 無い (調停 2 method のみ、ロジックは子に閉じ込め) |
| **テスト assertion 粒度** | 2 段 (manager → controller) | 3 段 (manager → controller → 子 node) |
| **Tween 実装責任** | AgentController | DialogBubble (専任) |
| **将来拡張性** | 「次の視覚機能」を追加すると AgentController がさらに肥大 | 同じ composition pattern で子ノード追加するだけ |

## 評価

### v1 の長所

1. **変更規模が小さい** — 既存の SpeechBubble を流用するので新規シーンなし、
   新規 script なし (zone scene 2 + test 2 のみ)
2. **読み手が少ない** — 関連 file が AgentController 中心に集約
3. **PR review が短い** — diff line 数が v2 より少ない見込み
4. **T17 judgement 9 「MainScene.tscn 編集禁止」** への追従は同等

### v1 の短所

1. **AgentController が肥大化する** — 既に 120 行で T17 時点から成長、
   v1 追加で method 4 / const 3 / Tween 管理コードが増える。将来 M6 で
   animation / particle が入ると破綻しやすい
2. **SpeechBubble と DialogBubble の last-wins 衝突** — M4 speech envelope と
   M5 dialog_turn envelope が同時フレームに来ると片方の text が上書きされ情報欠落。
   M5 では speech 使わない可能性もあるが、将来的に両方残す判断が発生すると
   リスク化
3. **Tint の hard swap** — FSM が短周期で揺れた場合 (peripatetic ↔ shallow 等)
   色が ストロボ的に点滅する可能性。live acceptance の視覚品質に直接影響
4. **8-mode 色が AgentController に埋まる** — zone side / UI overlay で同じ
   色を使いたくなった際、二重管理 or import 経路が煩雑

### v2 の長所

1. **責務分離が明確** — DialogBubble は「bubble の生存管理」、BodyTinter は
   「material の色管理」、ERREModeTheme は「色の辞書」と単一責務
2. **AgentController の成長を止められる** — 将来の視覚機能も子ノード追加で
   吸収できる (M6 の animation もこのパターンで拡張しやすい)
3. **SpeechBubble / DialogBubble 共存可能** — 並列 Label3D で last-wins 衝突
   なし。M5 speech 不使用の判断が後付けで変わっても安全
4. **Tint transition が滑らか** — 0.3s Tween で strobe 回避。acceptance 録画の
   視覚品質が安定
5. **ERREModeTheme が re-usable** — zone side / UI overlay からも参照可能、
   single source of truth
6. **テスト 3 段 assertion** — 委譲チェーンが壊れた時の原因特定が早い
   (どの段で落ちたか stdout で一目)

### v2 の短所

1. **ファイル数増** — 新規 8 file (v1 は 4)。PR が大きくなる
2. **Godot scene の複雑度↑** — AgentAvatar.tscn に子ノードが増える
3. **BodyTinter の `.duplicate()` per-instance 化は同等の冗長さ** — v1 の
   `resource_local_to_scene` と比べて memory footprint は同じ、runtime
   オーバーヘッドは `.duplicate()` 側がわずかに大きいが無視できる
4. **preload-based 参照の書き味** — autoload にしない判断の分、各 consumer に
   `preload("res://scripts/theme/ERREModeTheme.gd")` を書く必要あり
5. **AgentController の委譲 method は「method chain の一段増やしただけ」に
   見える側面** — yagni 的に過剰と映る可能性

## 推奨案

**hybrid (v2 ベース + v1 の簡潔要素を取り込む)** — 理由:

### hybrid で採用する (v2 由来)

- **DialogBubble を独立 scene/script に分離** (v2 §3)。 speech と衝突しない
  z-offset 配置。Tween + Timer による replace semantics を DialogBubble に閉じる
- **BodyTinter を Body ノードにアタッチ**し、tint transition を 0.3s Tween 化
  (v2 §3、strobe 回避)
- **ERREModeTheme.gd を独立 const-only script** に切り出し、`static func
  color_for` で露出 (v2 §3、将来 zone/UI reuse 余地を残す)
- **Zone は装飾ゼロ**、PlaneMesh + material のみ (v2 §Zone MVP)。acceptance
  受け入れ条件を最小で満たし、30Hz リスクを最小化
- **テスト 3 段 assertion** (v2 §テスト戦略)

### hybrid で v1 寄りに戻す

- **material per-instance 化は scene 側 `resource_local_to_scene = true`** で
  対応 (v1 §)。BodyTinter.gd の `.duplicate()` を省き、実行時ロジックをさらに
  薄くする (BodyTinter は `apply_mode` の Tween のみ担当)
- **AgentManager への signal wiring**: dialog_initiate_received の connect は
  v2 で「向き調整は M6」と触れたが、v1 通り M5 では connect しない (yagni、
  pure log 行もノイズになる)。dialog_close_received も pure log、
  dialog_turn_received のみ実働

### hybrid で新しく追加

- **ERREModeTheme.gd に `class_name ERREModeTheme`** を付ける (v2 §リスク 3)。
  static func 呼出しなので T16 judgement 4 の「cross-ref TYPE annotation」
  問題は回避される

採用理由:

- **v1 の「変更規模最小」は魅力だが、AgentController 肥大化と tint strobe
  の 2 リスクは acceptance 品質に直撃する** (特に #6 録画評価)
- **v2 の「composition」はこのプロジェクトの既存パターン (WorldManager /
  EnvelopeRouter の責務分離) と思想整合**がある
- **装飾ゼロの Zone** は MVP の本質を外さず、録画時の構図工夫で回避可能
- **material_override の per-instance 化は scene 側** が一番 cost 小 (v1 採用)。
  BodyTinter のコードを小さく保てる
- hybrid にすることで「v2 の構造優位」と「v1 の最小変更志向」のいい所取り

## 最終 design.md にまとめるべきこと

1. v2 §実装アプローチ の 3 コンポーネント (DialogBubble / BodyTinter / ERREModeTheme) を採用
2. material 複製は scene 側 `resource_local_to_scene = true` (v1)
3. dialog_initiate / dialog_close の receive は M5 では実装しない (v1、yagni)
4. Zone は装飾ゼロ (v2)
5. テスト 3 段 assertion + fixture replay (v2)
6. 新規ファイル数: 7 (DialogBubble scene/gd + BodyTinter.gd + ERREModeTheme.gd +
   Chashitsu.tscn + Zazen.tscn + test 2 本) — v1 より 3 file 増、v2 より 1 減
