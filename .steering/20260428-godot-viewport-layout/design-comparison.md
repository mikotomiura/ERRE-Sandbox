# 設計案比較 — godot-viewport-layout

> **note (codex review 反映)**: 当初 Claude は本文書を「v2 採用根拠」として
> 書いたが、codex (gpt-5.5, xhigh) が以下 2 点の過大評価を指摘した。
> 訂正を本文書に反映済み:
>
> - 「v2 は v1 の strictly superset」は誤り。HBoxContainer → HSplitContainer
>   と `size_flags_horizontal = 0 → 3` でレイアウト意味論が変わるため、
>   単純な上位互換ではない (regression リスクあり)
> - 「受け入れ条件 6 件」は誤り。`requirement.md` L34-38 では **4 件**
>
> 採用は最終的に **v2.1** (codex の HIGH 3 / MEDIUM 2 を反映、`design.md` 参照)。

## v1 (初回案) の要旨

「最小修正で黒帯を消し、既存 Layout を温存」方針。
`project.godot` に `window/stretch/mode = "canvas_items"` + `aspect = "expand"`
を追加し、Godot 4 のデフォルト disabled stretch を解消。MainScene.tscn は
`HBoxContainer "Split"` のまま、SubViewport に `size_2d_override_stretch=true`
追加と panel 幅 320/340 不整合の解消のみ。collapse/resize 機能なし。

## v2 (再生成案) の要旨

**`HBoxContainer → HSplitContainer` 置換 + collapse toggle ボタン + SubViewport
stretch + window stretch** の 4 軸構成。

- HSplitContainer に置換することで splitter ドラッグによる **resize 機能を
  ネイティブに獲得**
- ReasoningPanel header に ▶ ボタンを追加し、`split_offset` を 60px (collapsed)
  ↔ 340px (expanded) で toggle する **collapse 機能** を実装
- v1 と同等の window/stretch + SubViewport stretch を含む

## 主要な差異

| 観点 | v1 | v2 |
|---|---|---|
| project.godot stretch 設定 | 追加 (canvas_items + expand) | 同 |
| window/size/resizable | 追加 | 同 |
| Split node type | HBoxContainer 維持 | **HSplitContainer に置換** |
| splitter drag による resize | ❌ 不可 | ✅ ネイティブで実装 |
| collapse / expand toggle | ❌ なし | ✅ panel header の ▶ ボタンで実装 |
| ReasoningPanel size_flags_h | 0 (固定幅) のまま | 3 (FILL+EXPAND、HSplit 必須) |
| ReasoningPanel min width | 340 (タイプ + GDScript 統一) | **60** (collapsed 状態で生存) |
| SubViewport size_2d_override_stretch | true 追加 | 同 |
| GDScript 追加量 | ~1 行 (320→340) | ~30 行 (header + toggle) |
| 変更ファイル数 | 3 (project.godot / .tscn / .gd) | 同 (3 ファイル、行数差) |
| 受け入れ条件 L34 (3 解像度全面化) | ✅ 達成 | ✅ 達成 |
| 受け入れ条件 L35 (collapse / resize 可能、min width 生存) | ❌ **未達成** | ✅ 達成 (v2.1 で完成) |
| 受け入れ条件 L36 (ζ-1 surfaces regression なし) | ✅ 達成 | ✅ 達成 |
| 受け入れ条件 L37 (/reimagine v1+v2 並列) | ✅ 達成 (本ドキュメントで満たす) | ✅ 達成 |
| ロールバック容易性 | git revert 1 発 | 同 |

## 評価

### v1 の長所

1. 変更行数最小、レビュー容易
2. UI 構造変更なし → regression リスク最小
3. 「黒帯を消す」だけの最短路

### v1 の短所

1. **受け入れ条件 L35 (collapse / resize) を満たさない**。requirement.md
   が次回 task に分離する前提なら OK だが、現在の requirement は本 task に
   含めている
2. ReasoningPanel が固定幅のまま、4K+ 解像度で相対的に小さく見える問題は
   未解決

### v2 の長所

1. **受け入れ条件 4 件全てを 1 PR で満たす** (要件 L34-37)
2. HSplitContainer は Godot 4 標準ノードで、自作 drag handle 不要
3. collapse 機能で panel が邪魔な時 (zone 全景観察時) に画面 95%+ を 3D に
   割り当てられる、UX 向上幅大
4. v1 と方向性は同じだが collapse/resize 機能を追加 (**strictly superset
   ではない**: HSplitContainer 化により子 size_flags 仕様が変わるため、
   v2 採用は v1 の固定幅契約を捨てる選択を伴う)

### v2 の短所

1. UI 構造変更 (HBoxContainer → HSplitContainer) で僅かながら regression
   リスク。HSplit は HBox 互換の Container 派生だが、子の size_flags 要件が
   異なる (両側 expand 必要)
2. GDScript ~30 行増、`_split = get_parent()` の cast 失敗時の silent fail
   懸念 (assert ガードで対処)
3. v1 比で実装 + 検証コストが ~1.5 倍

## リスク評価

| リスク | v1 影響 | v2 影響 |
|---|---|---|
| 受け入れ条件 L35 未達による follow-up PR | **発生確実**: 別 task で collapse/resize PR | 発生せず |
| HSplitContainer 子の size_flags ハマり | なし | 中: 要事前検証 (Godot docs / 手動 boot) |
| ReasoningPanel 内部の縦伸び挙動変化 | なし | 低: size_flags_v=3 維持 |
| 黒帯の二次原因 (SubViewport size_2d_override_stretch) | 解消 | 解消 |
| 1280x720 / 1920x1080 / 2560x1440 の 3 解像度確認工数 | 必要 | 必要 (差なし) |

## 推奨案

**v2 採用**を推奨する。

### 推奨根拠

1. **要件適合性**: requirement.md L34-36 の受け入れ条件 3 件すべてを v2 のみが
   満たす。v1 採用時は L35 達成のため別 PR が必要となり、本 task が
   "1 PR 最速 land 可能" (requirement L11) という性質を活かせない
2. **追加コストの妥当性**: v2 の追加実装は HSplitContainer 置換 (3 行差) と
   collapse toggle GDScript (~30 行)。1 PR 内で十分扱える規模で、検証も
   同じ 3 解像度ブートに collapse/expand クリックを足すだけ
3. **構造的優位**: v1 が「次の panel UX task の踏み台」になるのに対し、v2 は
   「この PR で UX 着地」という位置付け。M9-LoRA 着手前に live UX 底上げを
   狙う本 task の趣旨 (requirement L17) と整合
4. **本プロジェクトの設計傾向との整合**: PR #111 / PR #113 で SSoT / 構造的
   閉じ込みを優先する判断が積み重なっており、v2 の「1 task で要件閉じ込み」
   は同じ系統

### ハイブリッド余地

- (A) v2 を基本としつつ、**collapse 機能のみ次 task に分離**して v1 寄りに
  簡略化 → splitter drag による resize は残し、▶ ボタンは保留。L35「resize
  可能」「min width 生存」のうち resize は満たすが collapse の便益を取り損なう
- (B) v2 の collapse を **「split_offset min/max toggle」ではなく
  `panel.visible = false`** で実装 → splitter ごと消える挙動になり L35
  「min width で生き残る」を満たさない。不採用

(A) は中間案として成立するが、collapse 30 行のコストはレビュー含め 30 分以下
で済むため、分離する利益が薄い。v2 のままで進めるのが妥当。
