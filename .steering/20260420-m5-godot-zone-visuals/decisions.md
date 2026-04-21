# 設計判断 — m5-godot-zone-visuals

## 判断 1: hybrid 採用 (v2 composition + v1 scene-side material)

- **判断日時**: 2026-04-20
- **背景**: design-v1 (AgentController に method 集約) と design-v2 (composition
  with DialogBubble / BodyTinter / ERREModeTheme) を比較
- **選択肢**:
  - A: v1 (最小変更、既存 SpeechBubble 流用、hard swap tint)
  - B: v2 (責務分離、別 Label3D、Tween tint、ERREModeTheme autoload 無し)
  - C: hybrid (v2 ベース + v1 の scene-side `resource_local_to_scene=true`) ← **採用**
- **理由**:
  - v2 の composition は将来の視覚機能 (M6 animation) を controller 肥大化させず
    取り込める
  - SpeechBubble と別チャネル化することで last-wins 衝突を物理的に排除
  - tint を 0.3s Tween で遷移させることで FSM 短周期振動時の strobe を回避
  - material 複製は scene 側 `resource_local_to_scene=true` 一発で済ませ、
    BodyTinter の runtime コードを 1 行減らせる (v1 採用)
  - ERREModeTheme を autoload 化しないことで `project.godot` を触らず済む
- **トレードオフ**: 新規ファイル数 7 (v1: 4、v2: 8)。scene の複雑度も増す。
  ただし composition の利点がそれを上回ると評価
- **影響範囲**: `godot_project/scripts/agents/*`, `godot_project/scripts/theme/*`,
  `godot_project/scenes/agents/AgentAvatar.tscn`

## 判断 2: Peripatos 装飾 retreat + BaseTerrain 導入 (M4 live 違和感対処)

- **判断日時**: 2026-04-20
- **背景**: M4 live 検証時にユーザーが観察した 2 つの違和感:
  - #1: avatar が Peripatos の StartMarker / EndMarker / Posts を貫通歩行
  - #2: avatar が Peripatos plane (40x4) の外を歩く時に void 上を歩いて見える
- **選択肢**:
  - A: CharacterBody3D + 物理衝突 (正攻法だが大規模 refactor)
  - B: Godot 側 AABB clamp logic (ZoneRegistry + clamp_to_walkable)
  - C: 視覚のみの対処 (BaseTerrain 追加 + Peripatos 装飾 retreat) ← **採用**
- **理由**:
  - ユーザーが「MVP のため最小限修正」を明示的に希望
  - Python 側 `src/erre_sandbox/` 無変更の制約 (G-GEAR 並列作業との独立性維持)
  - BaseTerrain (60x60 中立土色) で void 上歩行は視覚的に解消
  - Peripatos の StartMarker/EndMarker (歩行線 Z=0 上) は削除、PostN/S (Z=±2)
    は Z=±3 に退避して歩行 corridor から排除
  - 厳密な zone 境界強制は Python 側 `world/zones.py` + 後続
    `m5-world-zone-triggers` (G-GEAR) に委ねる
- **トレードオフ**: avatar がさらに遠く (BaseTerrain の 60x60 の外) に行くと
  まだ void 上歩行になる。ただし通常の動作範囲では発生しない想定
- **影響範囲**: `godot_project/scenes/zones/BaseTerrain.tscn` (新規)、
  `godot_project/scenes/zones/Peripatos.tscn` (StartMarker/EndMarker 削除 +
  Post Z 位置変更)、`WorldManager.gd` ZONE_MAP に base_terrain 先頭追加

## 判断 3: ERREModeTheme は preload 経由参照 (class_name parse-order 回避)

- **判断日時**: 2026-04-20
- **背景**: 初回実装で `BodyTinter.gd` が `ERREModeTheme.color_for(mode)` と
  `class_name` 参照したところ、headless first-boot で parse error
  (`Identifier "ERREModeTheme" not declared in the current scope`)
- **選択肢**:
  - A: autoload singleton 化 (project.godot 編集)
  - B: preload で const に bind → その const 経由で static func 呼出 ← **採用**
  - C: class_name のまま Godot editor で一度開いて `.godot/` cache 生成
- **理由**:
  - B は最小変更。T16 judgement 4 (class_name cross-ref が first-boot で失敗) と
    同系統の問題で、preload 化が既確立の回避パターン
  - A は project.godot を触る必要があり原則違反
  - C は CI 環境で cache 生成が保証されないので NG
- **トレードオフ**: preload const 名 `ERREModeTheme` が Godot built-in `Theme`
  クラスと衝突しないよう命名注意 (実際テスト実行中に test-runner が
  `Theme` → `ERREModeTheme` に rename 済)
- **影響範囲**: `BodyTinter.gd` のみ (DialogBubble は ERREModeTheme を参照しない)

## 判断 4: code review MEDIUM 3 件のうち #3 のみ対処、#1 #2 は受容

- **判断日時**: 2026-04-20
- **背景**: code-reviewer sub-agent が MEDIUM 3 件を指摘
  - #1: `AgentController._body` の型ヒントが `MeshInstance3D` のまま、
    BodyTinter を `as BodyTinter` でキャストしていない
  - #2: `DialogBubble.show_for` で `duration_s < 0.6` のとき fade_in+fade_out が
    合計時間を超過するエッジケース
  - #3: `AgentManager._on_agent_updated` で `erre.name` が null なら
    `str(null)="null"` で ERREModeTheme の unknown-mode 警告が出る
- **選択肢**:
  - A: 3 件全て対処 (完璧主義)
  - B: 実害がある #3 のみ対処、#1 #2 は現状維持 ← **採用**
  - C: ユーザー判断を仰ぐ
- **理由**:
  - #3 は gateway が `erre.name=null` を送ると即座に spurious warning が stdout
    に出る実害パス。null ガードで即防げる
  - #1 は parse-order 回避のために現状 has_method ガード経由で委譲しており、
    cast を入れると再び class_name cross-ref 問題に触れるリスクあり (現状維持が安全)
  - #2 は `DEFAULT_DIALOG_DURATION_SEC=4.0` 固定で呼ばれており、duration_s が
    0.6 未満になる経路は現状無い。Python 側から可変 duration を渡す経路が
    できた時点で再対処する
  - auto mode でユーザーを細かく中断させない
- **トレードオフ**: #1 と #2 は blockers.md に持ち越し。LOW 優先度で M6 以降に
  拾う
- **対処コード**: `AgentManager.gd` の `_on_agent_updated` で `raw_mode is String`
  ガードを追加、null/非文字列時は no-op

## 判断 5: dialog_initiate / dialog_close は AgentManager に connect しない (yagni)

- **判断日時**: 2026-04-20 (design-comparison 時点)
- **背景**: `EnvelopeRouter.gd` は `dialog_initiate_received` と
  `dialog_close_received` の 2 signal も emit する
- **選択肢**:
  - A: 3 signal 全 connect + log 出力
  - B: `dialog_turn_received` のみ connect ← **採用**
  - C: M6 で向き調整と同時に 3 signal 統合 wiring
- **理由**:
  - bubble は DialogBubble の Tween/Timer で自然消滅するので close 受信不要
  - initiate の向き調整は M5 scope 外 (M6 以降)
  - pure log 行はノイズになるので connect する価値無し
- **トレードオフ**: 将来 initiate/close を消費したい時に AgentManager に
  signal connect を追加する手間が発生。ただし additive 変更なので容易
- **影響範囲**: AgentManager.gd の `_REQUIRED_SIGNALS` / `_ready` で 1 signal 分のみ
