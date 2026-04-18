# T17 godot-peripatos-scene — 設計案比較 (v1 vs v2)

## v1 (初回案) の要旨

patterns.md §3/§4 のテンプレを**ほぼそのままコピー**する凡庸な素直案。
`class_name AgentController` 宣言 + AnimationTree 採用 + `_physics_process` lerp +
`_move_speed = 2.0` ハードコード + MainScene.tscn に `agent_avatar_scene` export
追加 (load_steps=6→7)。ZONE_MAP Dictionary を WorldManager 内に。自覚的弱点を
V1-W1 ～ W8 として本人が明示。

## v2 (再生成案) の要旨

**3 つの構造的改善**で v1 の弱点を解消:
(1) **Tween 駆動移動**で envelope の `speed` を使用 + idle 時無駄処理ゼロ
(2) **`preload()` 直接参照**で MainScene.tscn を一切触らない (T16 L5 完全解消)
(3) **AnimationPlayer/Tree を除去** + `class_name` 不使用で headless boot 安定化。
テストは module-scoped fixture で subprocess 共有し CI 時間増を抑制。

## 主要な差異

| 観点 | v1 | v2 |
|---|---|---|
| **Avatar ルート** | CharacterBody3D (物理あり) | **Node3D** (物理不要、Tween が移動) |
| **アニメ処理** | AnimationTree + AnimationPlayer (空クリップ、push_error リスク) | **完全除去**、`_current_animation: String` + print のみ |
| **移動制御** | `_physics_process` で lerp + move_and_slide、`_move_speed=2.0` ハードコード | **Tween 駆動**、`duration = distance / envelope.speed` で一発 |
| **Envelope speed の扱い** | 捨てる (V1-W2) | **使う** (duration 計算に反映、fixture の speed=1.3 がログに) |
| **`class_name` 宣言** | `class_name AgentController` あり (V1-W3 parse 失敗リスク) | **宣言なし**、T16 判断 4 完全踏襲 |
| **MainScene.tscn 編集** | load_steps 6→7 + ext_resource +1 (V1-W4 L5 二重蓄積) | **0 行** (preload 直接参照で不要化) |
| **Peripatos 形状** | PlaneMesh 8m 幅 + 連続境界 box (v1 は広場風) | PlaneMesh **4m 幅** + 6 本 post + Start/End marker (歩行路らしさ) |
| **ZONE_MAP** | WorldManager 内 Dict (premature) | WorldManager 内 Dict + **M5 拡張コメント**で意図を宣言 |
| **テスト構造** | 別ファイル、subprocess 別実行 (CI 時間倍増) | **module-scoped fixture** で subprocess 共有、6 assertion 単一実行 |
| **新規ファイル数** | 4 本 | 4 本 (同じ) |
| **修正ファイル数** | 3 本 (AgentManager + WorldManager + MainScene) | **2 本** (AgentManager + WorldManager のみ) |
| **スクリプト行数** | AgentController ~70 行 + AgentManager ~80 行 | AgentController ~75 行 + AgentManager ~70 行 |
| **変更規模 (LOC)** | ~500 (scripts + tscn + tests) | ~460 (MainScene 不変 + scene 簡素化) |
| **Godot エディタ依存** | MainScene を触るので canonical 化が必要 (L5 延長) | **Godot エディタ不要** で完結 |
| **HIGH リスク** | MainScene 手動編集 + class_name cross-ref | **両方解消** |
| **将来の M5 拡張** | 連続境界の拡張が面倒、AnimationTree を剥がす必要 | ZONE_MAP に key 追加、Animation は clip が入った時点で AnimationPlayer を足す |

## 評価 (各案の長所・短所)

### v1 の長所
- **patterns.md 完全準拠**: Skill テンプレ通りで読みやすい
- **AnimationTree 完備**: M5 アニメ追加時に scene 変更なしで差し替えられる (ただし T17 時点では push_error リスクとセット)

### v1 の短所
- **envelope の速度を使わない**: Contract-First 思想に反する (Router が speed を
  signal に含めているのに捨てる)
- **MainScene.tscn 手動編集**: T16 L5 が未消化のまま二重蓄積、load_steps 計算ミス
  リスク
- **`class_name` cross-ref**: T16 判断 4 で確認済みの parse 失敗が再発する可能性
- **AnimationTree + 空クリップ**: state_machine.travel("Walking") が
  "Walking" ノードなしで呼ばれ push_error → `test_godot_ws_client.py` の
  `"ERROR:" not in ...` / `rc == 0` に失敗する可能性
- **`_physics_process` 常時 lerp**: 停止後も毎フレーム distance 計算、idle 判定の
  プリシージョン不足 (V1-W6)
- **test 2 subprocess**: CI 時間倍増

### v2 の長所
- **envelope の speed を使う**: Contract 準拠、fixture の `speed=1.3` がそのまま
  log に出る (テストで verifiable)
- **MainScene.tscn 不変**: L5 二重蓄積が完全になくなる + Godot エディタ利用制約が
  T17 から消える
- **Tween 駆動**: stop 判定が明確 (Tween が自動終了)、idle 時無駄処理ゼロ、
  `look_at` を `tween_property` 前に一度呼ぶだけで向き制御も完結
- **シーンが軽量**: AnimationTree 除去で .tscn のノード数が減り、Godot 4.6.2 の
  headless boot が速く安定
- **テスト 1 subprocess / 6 assertion**: CI 時間増を抑えつつ検証範囲を広げる
- **M4 glTF 移行が直線的**: AnimationPlayer を scene に追加して controller の
  `set_animation` 本体を置き換えるだけ、既存の log 仕様も維持可能
- **Peripatos の "道らしさ"**: 4m 幅 + 離散 post + Start/End marker で歩行路感が
  出る、DMN 連想の視覚メタファーに近づく

### v2 の短所
- **patterns.md からの逸脱**: §3 が CharacterBody3D + AnimationPlayer + AnimationTree
  を前提としている部分を明示的に逸脱。decisions.md で理由を記録する必要あり
- **Tween の挙動**: Godot 4.x の Tween は Node の free で自動キャンセルされるが、
  fixture 再生中のシーン遷移 (今回は発生しない) ではエッジケースが出る可能性
- **Speech bubble の auto-hide なし**: 5 秒タイマを外したので最初の speech が
  ずっと表示される (M5 で auto-hide 追加予定)
- **`class_name` 不使用の IDE 補完の弱さ**: AgentController の各メソッドが IDE
  補完に乗らない。ただし Godot エディタは preload で得た scene の root に対して
  export 情報を解析するので致命ではない

## 推奨案

**v2 を採用**。理由:

1. **V1-W1/W2/W3/W4 (致命 4 件) をすべて構造で解消**
   - AnimationTree 除去 → 空クリップ push_error なし
   - Tween で speed 活用 → Contract 準拠
   - class_name 不使用 → headless parse 安定
   - preload 直接参照 → MainScene 不変
2. **T16 の judgment 遵守**: 判断 4 (class_name 回避) / 判断 9 (手動編集記録) の
   両方を T17 で再現せず、むしろ不要化する
3. **テスト設計が合理的**: module-scoped fixture で CI 時間を抑えつつ検証密度を
   上げる (6 assertion vs v1 の ~4 assertion)
4. **M4 移行が直線的**: AnimationPlayer 追加で既存コードを最小変更、Contract の
   signal shape は不変
5. **patterns.md 逸脱の正当性**: §3 は glTF を前提にした完成形。T17 の primitive
   段階では逸脱が合理的 (decisions.md に記録)

**採用判断日**: 2026-04-19
**採用根拠**: V1 致命 4 件 (W1/W2/W3/W4) を構造で解消、MainScene.tscn 不変に
よる T16 L5 完全排除、envelope speed 利用で Contract-First 思想の徹底、テスト
設計の効率化

## ハイブリッドの可能性検討

ユーザーが「ハイブリッド」を選択する場合の切り出し候補:

- **H1: v2 から Tween 移動 + MainScene 不変を採用、Avatar は v1 の CharacterBody3D + AnimationPlayer を維持**
  - W3 (class_name) / W1 (AnimationTree) は残る。中途半端
- **H2: v2 ほぼ全採用、ただし `class_name AgentController` を宣言する**
  - T16 判断 4 に反する。headless parse リスク増
- **H3: v2 全採用、ただし `_physics_process` lerp を併用 (Tween と冗長)**
  - 無意味な複雑化

**推奨は v2 フル採用**。ハイブリッドは v2 の構造的改善を部分的に損なう。
