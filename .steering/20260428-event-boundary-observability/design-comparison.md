# 設計案比較

## v1 (初回案) の要旨

- ReasoningTrace に **3 sparse top-level fields** (`trigger_kind`, `trigger_zone`, `trigger_ref_id`) を additive 追加
- ProximityEvent にも **`zone: Zone | None`** を additive 追加 (initiator zone を inject、prev_zone snapshot で race 対策)
- Cognition cycle に `_trace_event_boundary()` helper、優先度ベースで 1 件選択
- **Godot ReasoningPanel に TRIGGER セクション 1 行追加** (`[icon] [ref_id] @ [zone]`)、Unicode glyph icon
- world / cognition / godot の 4 commit
- M7ζ `latest_belief_kind` パターンに完全準拠

## v2 (再生成案) の要旨

- ReasoningTrace に **1 nested `TriggerEventTag` 構造体** (`kind` + `zone` + `summary` ≤80 chars) を additive 追加
- ProximityEvent は **無変更** (cognition cycle が `AgentState.position.zone` から trigger zone を引く)
- Cognition cycle に `_pick_trigger_event()` 純関数、優先度ベースで 1 件選択 + `summary` 文字列生成
- **Panel + 空間** の 2 modality: ReasoningPanel TRIGGER 行 + BoundaryLayer.`pulse_zone()` で **zone rect 0.6s amber pulse**
- schema / cognition / fixtures / godot panel / godot pulse の 5 commit (bisect 性確保)
- 既存 BoundaryLayer (yellow affordance / cyan proximity 描画) を 30 行未満で extend

## 主要な差異

| 観点 | v1 | v2 |
|---|---|---|
| **Schema 形** | sparse 3 fields top-level | nested 1 struct (`TriggerEventTag`) |
| **summary 文字列** | なし (kind + ref_id のみ) | あり (≤80 chars 自由テキスト) |
| **ProximityEvent zone** | additive 追加 (initiator inject) | 無変更 (cycle 側で AgentState から取得) |
| **race 対策** | `prev_zone` snapshot 必須 | 不要 (1 tick 内整合は cycle が担保) |
| **schema bump** | `0.9.0-m7z → 0.10.0-m7h` | `0.9.0-m7z → 0.10.0-m9` |
| **trigger kind 種類** | 8 種 (`zone_transition / affordance / proximity / temporal / biorhythm / speech / internal / none`) | 9 種 (上記 + `erre_mode_shift / perception`、 `none` 削除し `None` で表現) |
| **モダリティ** | panel テキスト 1 行のみ | panel テキスト + zone 空間 highlight (Tween pulse) |
| **Godot 変更ファイル** | ReasoningPanel.gd + Strings.gd | ReasoningPanel.gd + Strings.gd + **BoundaryLayer.gd + EnvelopeRouter.gd** |
| **新 signal 追加** | なし | `zone_pulse_requested(zone, tick)` 追加 |
| **commit 数** | 4 | 5 |
| **テストファイル** | test_schemas / test_cognition_cycle / test_world_tick の 3 拡張 | test_schemas / test_envelope_fixtures / **新 test_cognition_trigger_pick** の 3 |
| **既存パターン参照** | M7ζ `latest_belief_kind` (sparse Optional) | M7ζ `latest_belief_kind` (additive None) + `ZoneLayout` (nested model) + `_decision_with_affinity` (純関数装飾) |
| **wire 互換失敗時挙動** | panel に空文字列 / null crash 余地 | panel に dash 静的フォールバック |
| **侵襲度 (LoC 推定)** | schemas +5 / cognition +30 / world +6 / godot +25 = **~66** | schemas +12 / cognition +35 / godot +60 (panel +20, boundary +30, router +5, strings +5) = **~107** |

## 評価

### v1 の長所

- **侵襲度が小さい** (~66 LoC): pure additive sparse field、世界に新概念を導入しない
- **既存パターン完全踏襲**: M7ζ `latest_belief_kind` と同形 1 種で正規化、認知負荷が低い
- **schema 形が flat**: nested model のないシンプルな読み出し (Pydantic / Godot 両側で `dict.get`)
- **テストが分かりやすい**: top-level field の wire-compat、helper の table-driven、tick の zone inject の 3 軸で網羅
- **commit 数が少ない** (4): merge までの review コストが低い

### v1 の短所

- **panel テキストのみ**: 「空間上のどこ」が text (`@ chashitsu`) でしか伝わらず、live で 3 体並走時に panel と world を視線往復する必要
- **summary がない**: `[icon] bowl_01 @ chashitsu` だと "なぜ" がぼやける (ref_id だけでは因果が伝わらない)
- **ProximityEvent.zone race**: `step_kinematics` 後の位置動的変化への対策で `prev_zone` snapshot が必要 → 実装が delicate、後続変更で壊れやすい
- **`trigger_kind="none"` の必要性**: enum に `none` を含めるか None で表現するかの曖昧性 (v2 は None で統一)

### v2 の長所

- **2 modality 同時提示**: 「気づきの起点」を panel テキスト (因果命題) と zone pulse (空間焦点) の **2 系統** で出す → 眼球 1 サッカードで読める
- **summary を持つ**: ≤80 chars で「Linden-Allee に入った」のような自然言語要約が出せ、ref_id 単独より因果が伝わる
- **ProximityEvent 無変更**: race 対策不要、cycle.py 側だけ閉じる
- **bisect 性が高い**: 5 commit に分けて schema → cycle → fixtures → panel → pulse の各段で確認できる
- **既存 BoundaryLayer 資産活用**: 既に zone 境界線を引いている layer を pulse 拡張するだけで世界観整合
- **wire 互換失敗時の dash フォールバック**: nested struct の `None` から panel は静的に "—" 表示、null crash しにくい

### v2 の短所

- **侵襲度が大きい** (~107 LoC): nested model + Tween pulse + 新 signal で +60% LoC
- **新概念導入**: `TriggerEventTag` という新型が schema に増える (v1 は既存型の拡張のみ)
- **Godot 変更ファイル数が多い** (4 files vs 2): review 範囲広がる
- **2 modality 同期問題**: panel 表示と zone pulse のタイミング差 (1-2 frame) が live で不自然に見える可能性
- **amber pulse が既存 yellow affordance circle と色被りリスク** (v2 risk #2 で言及)
- **summary 文字列の生成負荷**: cognition cycle が 80 chars 以内に意味要約する logic を持つ → 国際化や i18n 整合に notes 必要

## 推奨案

**ハイブリッド (v2 ベース + v1 風 race 対策の取り込み)**

理由:

1. **2 modality (panel + zone pulse) は要件 C2 「どこの箇所のフィールドで...境界線」の本意により近い** — 「境界線」は単語そのものが空間的 metaphor で、panel テキストだけでは "境界" の意味を満たしきれない。BoundaryLayer pulse は要件原文に整合
2. **summary 文字列は live 観察体験を質的に底上げする** — `[icon] bowl_01 @ chashitsu` より `[icon] 茶碗を取り上げた @ chashitsu` の方が user は因果を読める。研究 observatory 価値に直結 (M9 LoRA pre-plan の "推奨第 1 候補" 理由とも整合)
3. **ProximityEvent 無変更は実装健全性で勝る** — race 対策の `prev_zone` snapshot は将来的な world tick refactor で壊れやすい。cycle 側の現在 zone 取得で済むなら `ProximityEvent.zone` という義務を schema に植えない方が良い
4. **侵襲度差 +40 LoC は受容可能** — godot-viewport-layout (PR #115/#116) の HSplit + collapsible で +200 LoC を 1 PR で merge した実績あり。本タスクは 5 commit 分割で review コストを吸収

ハイブリッドで取り込む v1 要素:

- **Tween pulse の amber 色被り対策** (v2 risk #2): v1 で考慮されていた icon glyph の色設計議論を pulse 色選定に転用 → amber 不採用、既存 yellow affordance との区別を確保 (例: violet / cyan-bright)
- **schema bump 表記**: v1 の `0.10.0-m7h` (M7 系として一貫) を採用、v2 の `0.10.0-m9` ではなく
- **commit 4 (godot UI) と commit 5 (pulse) の分離**: v2 の bisect 性を維持

ハイブリッドで除外する v2 要素:

- **`trigger_kind="erre_mode_shift" / "perception"`**: v1 の 8 種に統一、erre_mode_shift / perception は M10+ で再検討 (現 cycle に正規源がない)
- **`summary` 80 chars 上限**: live 観察用には十分だが、要件「1 行表示」を勘案して **60 chars 上限** に短縮 (panel 幅 320px / 13pt フォントの実 visual budget)

## ハイブリッド最終構造 (design-final.md 候補)

| 観点 | ハイブリッド |
|---|---|
| Schema | `TriggerEventTag` nested struct (kind + zone + summary≤60chars) を `ReasoningTrace` に additive |
| Trigger kind 種類 | 8 種 (`zone_transition / affordance / proximity / temporal / biorhythm / speech / internal / unknown`) |
| ProximityEvent | 無変更 |
| Cognition | `_pick_trigger_event(observations, current_zone) -> TriggerEventTag | None` 純関数 |
| Modality | Panel TRIGGER 行 + BoundaryLayer.`pulse_zone()` (色は **violet** で affordance yellow と区別) |
| Schema bump | `0.10.0-m7h` (M7 系一貫) |
| Commit 数 | 5 (schema → cycle → fixtures → panel → pulse) |
| 既存パターン参照 | M7ζ `latest_belief_kind` + `ZoneLayout` nested + `_decision_with_affinity` |
| Codex review 対象 | 本ハイブリッドを independent review にかけ HIGH 指摘を反映 |

## 次工程

ユーザーに採用判断を仰ぐ。承認後、design.md を **ハイブリッド最終構造**に書き換え、
Codex CLI (`codex review`) で independent review、HIGH 指摘を design-final.md に反映、
その後 tasklist.md を埋めて実装着手。
