# 重要な設計判断 — T17 godot-peripatos-scene

## 判断 1: v2 採用 — Tween 駆動 + preload 直接参照 + class_name 回避

- **判断日時**: 2026-04-19
- **背景**: v1 素直案 (patterns.md §3/§4 直コピー) は V1-W1〜W8 の 8 弱点を抱え、
  特に V1-W1 (AnimationTree 空クリップ) / V1-W2 (move_speed ハードコードで
  envelope speed 無視) / V1-W3 (class_name cross-ref で parse 失敗) / V1-W4
  (MainScene 手動編集 L5 二重蓄積) が致命
- **選択肢**: v1 / v2 / ハイブリッド (H1-H3)
- **採用**: **v2 フル採用**
- **理由**: V1 致命 4 件を構造で解消、T16 判断 4/9 を再現せず不要化、
  Contract-First の徹底、ハイブリッドは v2 効果を部分的に損なう
- **詳細**: `design-comparison.md`

## 判断 2: Avatar ルートを CharacterBody3D から Node3D に変更 (patterns.md §3 逸脱)

- **判断日時**: 2026-04-19
- **背景**: patterns.md §3 は CharacterBody3D + move_and_slide() を想定。しかし
  T17 では衝突判定 / 物理応答が不要 (他エージェント / 障害物なし)
- **選択肢**: A. patterns.md §3 準拠 (CharacterBody3D + CollisionShape3D) /
  B. Node3D + Tween 駆動
- **採用**: B
- **理由**:
  - Tween は `tween_property(self, "global_position", dest, duration)` 一行で
    移動を完結させる。CharacterBody3D は不要
  - CollisionShape3D は M4+ で NavigationMesh や衝突判定を追加する段階で導入
  - scene ノード数減 → headless boot が速く安定
- **影響範囲**: patterns.md の §3 を更新すべきか議論 (M4 時に再検討)
- **見直し**: M5 `world-zone-triggers` でエージェント間衝突が必要になった時に
  CharacterBody3D へ昇格

## 判断 3: AnimationPlayer / AnimationTree を scene から除去

- **判断日時**: 2026-04-19
- **背景**: V1-W1 — アニメクリップが存在しない段階で AnimationTree + 
  state_machine.travel("Walking") を呼ぶと push_error が出る
- **選択肢**: A. 空クリップ登録 + has_animation() ガード / B. AnimationPlayer
  のみ / C. 完全除去 + `_current_animation: String` で log のみ
- **採用**: C
- **理由**:
  - push_error リスクゼロ
  - scene がシンプルで Godot エディタでの visual check が楽
  - Router の signal contract (`animation_changed`) は不変、controller 内
    ハンドラ本体のみ変更で済む
  - M4 glTF 段階で AnimationPlayer を scene に足して controller の
    `set_animation` 本体を `AnimationPlayer.play(name)` に差し替えるだけ
- **トレードオフ**: visual なアニメ確認は M4 まで待つ (T17 範囲外)

## 判断 4: `AgentManager` が `preload()` で AgentAvatar.tscn を直接参照

- **判断日時**: 2026-04-19
- **背景**: V1-W4 — v1 は `@export var agent_avatar_scene: PackedScene` で
  MainScene.tscn に export 配線。T16 L5 (MainScene 手動編集 canonical 化未了)
  と二重蓄積する
- **選択肢**:
  - A. `@export` + MainScene.tscn に ext_resource + load_steps 更新
  - B. AgentManager 内で `const AVATAR_SCENE := preload(...)` 直接参照
- **採用**: B
- **理由**:
  - **MainScene.tscn を一切触らない** → L5 完全解消
  - T17 は avatar scene を動的に差し替える要件がない (M4 glTF 移行時に
    preload パスを変えるだけ)
  - Godot エディタ非依存で作業が完結
- **トレードオフ**: avatar scene 差し替えが preload パス変更 (コード変更) に
  なる。M4 の glTF 統合で特段のコストではない

## 判断 5: Tween 駆動移動で envelope の `speed` を使用 (Contract-First)

- **判断日時**: 2026-04-19
- **背景**: V1-W2 — v1 は `_move_speed = 2.0` ハードコード、envelope の
  `speed` を捨てる。Router の signal `move_issued(agent_id, target, speed)` が
  speed を渡しているのに活用しない Contract 違反
- **採用**: `duration = min(distance / max(speed, MIN_EFFECTIVE_SPEED),
  MAX_TWEEN_DURATION)` で Tween duration を計算
- **理由**:
  - envelope の speed=1.3 が `speed=1.30` として log に反映 → fixture テストで
    verifiable
  - `MIN_EFFECTIVE_SPEED = 0.01` で speed=0/負値の divide-by-zero ガード
  - `MAX_TWEEN_DURATION = 30.0` で極端に長い Tween を防止 (security review
    MEDIUM #2)
- **影響範囲**: AgentController.set_move_target、test_godot_peripatos.py の
  `test_move_uses_envelope_speed` でガード

## 判断 6: `class_name AgentController` は宣言するが、他スクリプトから型として参照しない

- **判断日時**: 2026-04-19 (code review HIGH #1 対応)
- **背景**: T16 判断 4 は class_name の「**使用**」(型注釈) を禁止、「**宣言**」
  は禁止していない。EnvelopeRouter / AgentManager / WorldManager / WebSocketClient
  は全て `class_name` を宣言している
- **選択肢**:
  - A. AgentController に class_name 宣言なし (v2 初期案)
  - B. class_name AgentController を宣言、ただし AgentManager は `Node` 型 +
    `has_method` で duck typing
- **採用**: B
- **理由**:
  - 他スクリプトとの一貫性 (EnvelopeRouter 等と揃う)
  - IDE 補完が効く
  - T16 判断 4 の意図は型注釈の cross-ref 禁止、宣言は OK
- **AgentManager の型扱い**: `avatar := AVATAR_SCENE.instantiate()` の戻り値は
  `Node` 型として受け、`avatar.has_method("set_agent_id")` で duck typing

## 判断 7: ZONE_MAP を WorldManager 内 Dictionary として採用 (明示コメント付き)

- **判断日時**: 2026-04-19
- **背景**: V1-W7 — 1 エントリ (peripatos のみ) の時点で Dictionary を
  持ち出すのは premature abstraction の懸念
- **選択肢**:
  - A. 単一 preload 変数 (YAGNI)
  - B. Dictionary + M5 拡張コメント (意図の明示)
  - C. Autoload singleton
- **採用**: B
- **理由**:
  - M5 `world-zone-triggers` で study / chashitsu / agora / garden が追加される
    ことが MASTER-PLAN で確定
  - Dictionary 採用により、M5 の差分は**key 追加 1 行のみ**で完了
  - コメントで M5 意図を明示することで「なぜ Dictionary なのか」を後続が
    即理解できる
- **ゾーン名規則**: key は schemas.py の `Zone` literal (lowercase snake_case)、
  node 名は `.capitalize()` で PascalCase (`ZoneManager/Peripatos`)

## 判断 8: Peripatos の Post 配置を非対称に

- **判断日時**: 2026-04-19 (code review MEDIUM #4 対応)
- **背景**: Post 6 本を「南北均等 (各 3 本)」にするか「非対称」にするか
- **採用**: 北側 4 本 (x=-16/-8/0/+8) / 南側 2 本 (x=-8/+8) の非対称
- **理由**:
  - Kant のケーニヒスベルク散歩道のメタファー (南北に川・街が広がる非対称環境)
    を視覚に投影
  - 北側の密度で「仕切り感」、南側の疎度で「抜け感」を演出
  - M5 以降で garden / agora を南側に配置する時、非対称が視線誘導の基礎になる
- **見直し**: M5 で peripatos 景観を拡張する際、非対称ルールを維持するか要検討

## 判断 9: セキュリティ対応として `is_finite()` / `MAX_TWEEN_DURATION` を導入

- **判断日時**: 2026-04-19 (security review MEDIUM #1/#2 対応)
- **背景**: envelope 由来の Dictionary 値を Vector3 / Tween duration に変換する
  際、malformed 値 (NaN / inf / 極端値) が来た時のガードが必要
- **採用**:
  - `set_move_target` と `update_position_from_state` で `dest.is_finite()`
    ガード → 失敗時は push_warning + 早期 return
  - Tween duration を `min(distance / speed, MAX_TWEEN_DURATION)` でクランプ
    (`MAX_TWEEN_DURATION = 30.0` 秒)
- **理由**:
  - NaN を Transform3D に代入すると AABB culling が破綻し scene tree 全体に
    影響
  - duration = 数百日の Tween はメモリに長期滞留しリークに近い挙動
  - LAN 内前提でも gateway バグでの事故を防げる

## 判断 10: `look_at` を水平方向のみに (Y 軸の pitch を抑制)

- **判断日時**: 2026-04-19 (code review MEDIUM #2 対応)
- **背景**: `look_at(dest, Vector3.UP)` で dest.y が avatar.y と異なる場合、
  avatar が地面を見下ろす / 空を仰ぐ方向に傾く
- **採用**: `look_at(Vector3(dest.x, global_position.y, dest.z), Vector3.UP)`
  で水平方向のみを見る
- **理由**:
  - 歩行ゾーンで avatar が地面を凝視する visual は不自然
  - `global_position.is_equal_approx(horizontal_dest)` ガードで真上/真下方向の
    崩れを排除
  - look_at の up vector 平行問題を予防
