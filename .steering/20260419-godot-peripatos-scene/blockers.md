# ブロッカー・懸案事項 — T17 godot-peripatos-scene

本タスクの実装中に解決できず、後続で対応すべき LOW 懸案を記録する。
HIGH / MEDIUM は全て解消済み (`decisions.md` 判断 2/3/4/5/9/10 参照)。

## LOW (後続タスクで対応)

### L1: SpeechBubble の auto-hide が未実装

- **起点**: v2 design.md + code-reviewer LOW
- **内容**: `AgentController.show_speech()` は `_speech_bubble.visible = true`
  にするが自動で false に戻さない。patterns.md §3 は `await create_timer(5.0)`
  で 5 秒後に hide するが、T17 では headless テストでハングを避けるため除去
- **対処**: M5 `godot-zone-visuals` で Timer ノード (one_shot=true) を使った
  auto-hide を追加。その際、create_timer await ではなく Timer.start + signal
  connect でシーン tear-down 耐性を持たせる
- **対応時期**: M5

### L2: T16 L5 (MainScene.tscn canonical 化) が未消化のまま

- **起点**: T16 decisions.md 判断 9 の L5
- **内容**: T16 で MainScene.tscn を手動編集した。T17 では MainScene.tscn を
  触っていないので L5 は新たに蓄積していないが、T16 時点の懸案として残存
- **対処**: Godot エディタが利用可能になったセッションで MainScene.tscn を
  開いて再保存 → canonical diff を単独コミット
- **対応時期**: 次の Godot エディタセッション

### L3: avatar 数に上限がない

- **起点**: security-checker LOW #5
- **内容**: `AgentManager._avatars` Dictionary に無制限にエージェントを
  積み上げられる。LAN 内 G-GEAR gateway 前提では悪意的可能性は低いが、bug で
  大量 agent_id が送信される事故への防御なし
- **対処候補**: `const MAX_AVATARS: int = 50` を AgentManager に追加し、
  `_avatars.size() >= MAX_AVATARS` で push_warning + null 返却
- **対応時期**: M7 `memory-decay-compression` で 5-8 体運用を想定する時に
  上限値を本番チューニング

### L4: `look_at` の Y 軸平行 edge case

- **起点**: security-checker LOW #3
- **内容**: 水平化した `horizontal_dest` が `global_position` と厳密に等しい
  場合 `is_equal_approx` でガードするが、極端に近い (float 精度の端) ケースで
  undefined behavior
- **対処候補**: cross product の長さで平行性を判定 (Godot 4.x では
  `Basis.looking_at` の内部実装を参考に)
- **対応時期**: M5 以降、実 avatar 挙動観察して必要性判断

### L5: agent_id のログインジェクション耐性なし

- **起点**: security-checker LOW #4
- **内容**: `agent_id` は G-GEAR gateway からの信頼入力だが、制御文字
  (`\n`, `\r`, ANSI) が混入した場合 print ログが汚染される
- **対処候補**: `set_agent_id()` で正規表現 `^[A-Za-z0-9_-]+$` バリデーション
- **対応時期**: M7 observability-logging で構造化ログを導入する時に一括対応

### L6: test_godot_peripatos.py と test_godot_ws_client.py の subprocess 重複

- **起点**: code-reviewer LOW #10
- **内容**: 両テストが同じ FixtureHarness.tscn を起動する 2 回の subprocess
  実行で、CI 時間が ~11s ずつ計 ~22s かかる
- **対処候補**: `conftest.py` に session-scoped な `harness_result` フィクスチャ
  を昇格させ、両テストが共有
- **対応時期**: CI 時間が問題になった段階 (M7 observability-logging 以降に
  テストが増えた時に再評価)

## 解決済み (参考)

- HIGH (code-reviewer #1): class_name AgentController を宣言、コメント修正
  で docstring と実装の整合 (判断 6)
- MEDIUM (security #1): `is_finite()` ガードを `set_move_target` /
  `update_position_from_state` に追加 (判断 9)
- MEDIUM (security #2): `MAX_TWEEN_DURATION = 30.0` クランプ導入 (判断 9)
- MEDIUM (code-reviewer #2): `look_at` を水平方向のみに制限 (判断 10)
- MEDIUM (code-reviewer #4): Peripatos Post 配置の非対称の理由を design.md
  に記述 (判断 8)
- MEDIUM (code-reviewer #6): `test_no_errors_and_clean_exit` の二重 skip を
  `_combined` に統一
