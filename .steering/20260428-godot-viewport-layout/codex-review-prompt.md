# Codex review prompt — godot-viewport-layout v1 vs v2

> このファイルは codex (CLI または `.codex/agents/erre-reviewer.toml`) に
> 食わせるための **independent second-opinion レビュー** プロンプト。
> Claude 側は v2 採用判断を既に行ったが、本プロジェクトの最大リスク
> 「単一エージェントの 1 発案にバイアスが残る」(memory: feedback_reimagine_trigger)
> を構造的に閉じるため、別エージェントで再評価する。

## あなたへの依頼

ERRE-Sandbox の Godot UI レイアウト改修 task `.steering/20260428-godot-viewport-layout/`
について、**Claude が生成した v1 / v2 設計案** と **採用判断 (v2)** を
independent な視点でレビューしてほしい。

具体的には:

1. **v1 / v2 の比較表が公平か**: v1 の長所が過小評価されていないか、
   v2 の弱点が見落とされていないか
2. **採用された v2 の盲点**: HSplitContainer + collapse toggle + window stretch
   の組合せで気付かれていない副作用 / Godot 特有の落とし穴
3. **第 3 案の余地**: v1/v2 のいずれでもない、より優れたアプローチが
   存在するか (例: `AnchorPreset` ベースの floating overlay、`SplitOffset`
   バインドの永続化、`Window` ノードの分離など)
4. **要件適合性の再評価**: requirement.md L34-38 の受け入れ条件 4 件に対し、
   v2 が真に必要かつ十分か

## 参照すべきファイル

- `.steering/20260428-godot-viewport-layout/requirement.md` — 受け入れ条件
- `.steering/20260428-godot-viewport-layout/design-v1.md` — 初回案
- `.steering/20260428-godot-viewport-layout/design.md` — v2 (再生成案、採用)
- `.steering/20260428-godot-viewport-layout/design-comparison.md` — Claude 比較
- `godot_project/project.godot` — 現状 [display] (L23-26)
- `godot_project/scenes/MainScene.tscn` — 現状 scene tree (100 行)
- `godot_project/scripts/ReasoningPanel.gd` — 現状 panel 実装 (517 行)
- `.steering/20260426-m7-slice-zeta-live-resonance/observation.md:488-490`
  — F3 の一次記録「3D canvas occupies ~50% of window with large black margins」

## 報告フォーマット

以下の構造で 200-400 行を目処に:

### 1. 比較表の公平性チェック
- v1 / v2 の各観点について、Claude 評価との差異 (同意 / 異議 / 加筆)

### 2. v2 の盲点 (重要度順)
- HIGH / MEDIUM / LOW で 3-7 件
- 各項目: 「現象 / 根拠 / 影響範囲 / 推奨対処」

### 3. 第 3 案 (もしあれば)
- 名称、要旨、v1/v2 比でどこが優れるか、どこが劣るか
- 1-2 案で十分

### 4. 最終推奨
- v1 / v2 / 第 3 案 / hybrid のどれを推奨するか
- 根拠を 2-3 行で

### 5. 実装着手前の必須確認事項
- 着手前に検証 / 計測すべきこと (例: 「2.5K 解像度で SubViewportContainer の
  sample 数」「HSplitContainer の RTL レイアウト挙動」など)
- 1-3 件
