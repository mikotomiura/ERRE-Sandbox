# Codex Review (gpt-5.5, xhigh reasoning, 2026-04-28)

> codex CLI v0.125.0 / session 019dd2d1-991c-7be2-ba39-8afa16bdcba4 / 242,896 tokens
> プロンプト: `.steering/20260428-godot-viewport-layout/codex-review-prompt.md`

### 1. 比較表の公平性チェック

- 同意: v1 は [requirement.md L35](/Users/johnd/ERRE-Sand%20Box/.steering/20260428-godot-viewport-layout/requirement.md:35) の `collapse / resize` を満たさないため、そのまま採用は不可。これは Claude 評価どおり。
- 異議: [design-comparison.md L63](/Users/johnd/ERRE-Sand%20Box/.steering/20260428-godot-viewport-layout/design-comparison.md:63) の「v2 は v1 の strictly superset」は過大評価。v2 は `HBoxContainer -> HSplitContainer` と `size_flags_horizontal = 0 -> 3` でレイアウト意味論を変えるため、単純な上位互換ではない。
- 加筆: v1 の長所は「変更行数最小」だけでなく、現行の `ReasoningPanel` 固定幅契約 [MainScene.tscn L69-L74](/Users/johnd/ERRE-Sand%20Box/godot_project/scenes/MainScene.tscn:69) と `_build_tree()` の前提 [ReasoningPanel.gd L88-L93](/Users/johnd/ERRE-Sand%20Box/godot_project/scripts/ReasoningPanel.gd:88) を壊さない点。これは regression リスクとしてもっと重く見るべき。
- 異議: `v2` の「受け入れ条件を全て満たす」は未確定。特に [design.md L53-L61](/Users/johnd/ERRE-Sand%20Box/.steering/20260428-godot-viewport-layout/design.md:53) の `split_offset = -340` と両子 `EXPAND` は、340px 右パネルを保証しない可能性が高い。
- 加筆: [design-comparison.md L59](/Users/johnd/ERRE-Sand%20Box/.steering/20260428-godot-viewport-layout/design-comparison.md:59) は「受け入れ条件 6 件」と書くが、実際は [requirement.md L34-L38](/Users/johnd/ERRE-Sand%20Box/.steering/20260428-godot-viewport-layout/requirement.md:34) の 4 件。小さいがレビュー品質の赤信号。

### 2. v2 の盲点

- HIGH: `split_offset` の前提が危うい。
  根拠: Godot 4.6 の `SplitContainer.split_offset` は deprecated で、実体は `split_offsets[0]`。デフォルト位置は expand flags と minimum sizes に依存する。公式 docs: https://docs.godotengine.org/en/4.6/classes/class_splitcontainer.html
  影響: `-340` が「右 340px」を意味するとは限らず、1280px で右パネルが巨大化する可能性がある。
  推奨: `split_offsets = PackedInt32Array([...])` を使い、実測 `size.x` から右幅を計算。`clamp_split_offset()` も呼ぶ。

- HIGH: v2 内に 320→340 と 320→60 の矛盾がある。
  根拠: [design.md L21](/Users/johnd/ERRE-Sand%20Box/.steering/20260428-godot-viewport-layout/design.md:21) は 340 統一、同 [L63-L65](/Users/johnd/ERRE-Sand%20Box/.steering/20260428-godot-viewport-layout/design.md:63) は 60 へ変更。
  影響: 実装者が expanded minimum と collapsed minimum を混同する。
  推奨: `PANEL_EXPANDED_WIDTH = 340`, `PANEL_COLLAPSED_WIDTH = 60` を分け、`custom_minimum_size` を状態に応じて切り替える。

- HIGH: collapse が「幅を狭めるだけ」で、内容を畳んでいない。
  根拠: 現 panel は `OptionButton` と多数の label を `VBoxContainer` に積む構造 [ReasoningPanel.gd L111-L158](/Users/johnd/ERRE-Sand%20Box/godot_project/scripts/ReasoningPanel.gd:111)。
  影響: 60px 幅で UI が潰れる、クリック領域だけ残る、見た目が壊れる。
  推奨: collapsed 時は body container を `visible = false`、header/collapse button だけ残す。

- MEDIUM: `size_2d_override_stretch = true` は黒帯対策として過大評価。
  根拠: Godot docs では `size_2d_override` が 0 なら override は無効。`SubViewportContainer.stretch = true` は既に現行 scene にある [MainScene.tscn L32-L33](/Users/johnd/ERRE-Sand%20Box/godot_project/scenes/MainScene.tscn:32)。公式 docs: https://docs.godotengine.org/en/4.6/classes/class_subviewport.html
  影響: 追加しても no-op の可能性がある。
  推奨: 実際に効くのは `window/stretch/*` と `SubViewportContainer` の実測 size。スクショで確認。

- MEDIUM: resize 後に collapse/expand するとユーザー幅を失う。
  根拠: v2 は `_EXPANDED_OFFSET := -340` 固定 [design.md L68-L85](/Users/johnd/ERRE-Sand%20Box/.steering/20260428-godot-viewport-layout/design.md:68)。
  影響: splitter drag の UX が「保存されない resize」になる。
  推奨: `dragged` signal で last expanded width/offset を保存し、expand は保存値へ戻す。

- LOW: `Button` を root に `add_child()` するサンプルは危険。
  根拠: sample [design.md L73-L80](/Users/johnd/ERRE-Sand%20Box/.steering/20260428-godot-viewport-layout/design.md:73) は `vbox` ではなく panel root に追加している。
  影響: anchor/layout 管理外になり、背景や margin と重なる。
  推奨: `Header` と `Body` を `VBoxContainer` 配下に明示する。

### 3. 第 3 案

- 案 A: `HSplitContainer v2.1 measured/persistent split`
  要旨: v2 を基礎にするが、右 panel は固定初期幅 340、collapsed 60、drag 結果を保存、`split_offsets` + `clamp_split_offset()` で管理する。
  優れる点: L35 を満たしつつ、v2 の hardcoded offset 問題を閉じる。
  劣る点: v2 より実装が 10-20 行増える。

- 案 B: `Full-rect world + right floating overlay`
  要旨: `WorldView` は常時 full rect、ReasoningPanel を右 anchor overlay とし、collapse は slide/hide。
  優れる点: [requirement.md L34](/Users/johnd/ERRE-Sand%20Box/.steering/20260428-godot-viewport-layout/requirement.md:34) の「3D viewport ほぼ全面」は最も強い。
  劣る点: resize handle 自作が必要で、Godot native split の利点を失う。

### 4. 最終推奨

`v2 そのまま` ではなく、案 A の hybrid を推奨。  
v1 は L35 未達なので requirement を変えない限り不可。v2 の方向性は正しいが、`split_offset` 固定値、collapsed content、resize 復元を直してから着手すべき。

### 5. 実装着手前の必須確認事項

- 1280/1920/2560 で `Split.size.x`, `WorldView.size.x`, `ReasoningPanel.size.x`, `WorldViewport.size` をログ出力し、黒帯原因が stretch か split 配分かを分ける。
- Godot 4.6 で `split_offset` と `split_offsets` の scene serialization を確認。deprecated API ではなく `split_offsets` 優先。
- collapse 中に `OptionButton`、camera drag、left click selection、day-night ambient が壊れないことを手動確認。既存 headless tests [test_godot_project.py L51-L79](/Users/johnd/ERRE-Sand%20Box/tests/test_godot_project.py:51) だけでは視覚・入力 regression は捕まらない。
