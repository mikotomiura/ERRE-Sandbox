# 重要な設計判断 — godot-viewport-layout

## D1: 設計案の採用 (v1 / v2 / v2.1)

- **判断日時**: 2026-04-28
- **背景**: F3「Godot world 画面が小さい問題」の UI レイアウト改修。設計判断は
  複数案ありうるため /reimagine 対象 (requirement L38)
- **選択肢**:
  - A: v1 (最小修正、`window/stretch/*` のみ、collapse/resize なし)
  - B: v2 (Claude 自己再生成、`HSplitContainer` + collapse toggle、HIGH 級盲点を含む)
  - C: v2.1 (codex review 反映後、HIGH 3 + MEDIUM 2 + LOW 1 を構造的に解消)
- **採用**: **C (v2.1)**
- **理由**: requirement.md L34-37 の受け入れ条件 4 件すべてを満たす唯一の案。
  Claude 単独の v2 採用判断には 3 つの実装バグ可能性 (`split_offset` deprecated /
  数値矛盾 / collapse が幅縮小だけ) が含まれており、codex (gpt-5.5 xhigh) の
  independent review がこれらを切り出した
- **トレードオフ**: v1 比で実装行数 +50 行、検証コスト +1 PR 内 (codex review 1 回)
- **影響範囲**: project.godot / MainScene.tscn / ReasoningPanel.gd / .steering/
- **見直しタイミング**: HSplitContainer の挙動が想定外の場合、または将来 panel
  を別 parent (overlay 等) に移動する task が起きた時

## D2: split_offset (singular) と split_offsets (PackedInt32Array) の両対応

- **判断日時**: 2026-04-28
- **背景**: codex HIGH-1 (Godot 4.6 で `split_offset` は deprecated、`split_offsets`
  が canonical) と code-reviewer HIGH (実装 vs design.md の API 乖離)。Claude の
  当初実装は `split_offset` (singular) のみで、`split_offsets` API の存在確認を
  していなかった
- **選択肢**:
  - A: `split_offset` (singular) のみ使用、deprecated warning 受容
  - B: `split_offsets` (array) のみ使用、4.5 以前との互換性を捨てる
  - C: 実行時 property 検出で両対応 (`if "split_offsets" in _split: ... else: ...`)
- **採用**: **C (両対応)**
- **理由**: 4.6.2 で `split_offsets` が存在することは既存テスト 12/12 pass で確認済。
  ただし将来 4.5 以前の Godot にダウングレードする可能性、CI 上の Godot
  バージョン非統一リスクを考えると両対応がコスト最小で安全マージン最大。
  `clamp_split_offset()` は両 API 世代で存在するので末尾 1 行で安全に呼べる
- **トレードオフ**: 実装は 2 行から 4 行に増えるが、`_apply_split_offset()` 関数に
  集約されているので可読性低下なし
- **影響範囲**: `ReasoningPanel.gd::_apply_split_offset()` 1 関数
- **見直しタイミング**: Godot 5 移行時、または 4.6 が最低サポートと確定した時に
  片方に統一可能

## D3: codex review を /reimagine の最終判断材料に組み込む運用

- **判断日時**: 2026-04-28
- **背景**: 本 task では Claude が v1/v2 を /reimagine で生成、自己判断で v2 を
  採用した直後にユーザーが「codex にも評価してもらう」と指示。codex は HIGH 3 件
  の盲点を発見し、Claude 単独判断では実装後に発見されていた可能性が高い
- **選択肢**:
  - A: Claude /reimagine 単独で確定、codex は補助的にしか使わない
  - B: 重要設計には Claude /reimagine + codex independent review の 2 段階
- **採用**: **B (2 段階レビュー)** を本プロジェクトの設計慣行として暫定採用
- **理由**: 単一エージェントの 1 発案にバイアスが残るリスク (memory:
  feedback_reimagine_trigger) は Claude 内 /reimagine だけでは構造的に閉じない。
  別モデル (gpt-5.5) の independent review で 3 つの実装バグを未然に回避できた
  実績がある
- **トレードオフ**: codex review に 1-2 分追加で時間消費。tokens は両エージェントで
  消費するが ROI は高い
- **影響範囲**: 今後の高難度設計 task (アーキテクチャ / 公開 API / 難バグ等) の
  Plan mode フロー
- **見直しタイミング**: codex / 別モデルの reviewing コストが高すぎる、または
  Claude 単独で十分な品質を出せると確信できる時点

## 受け入れ条件チェック (requirement.md L34-37)

| # | 条件 | 結果 |
|---|---|---|
| L34 | 1280x720 / 1920x1080 / 2560x1440 で 3D viewport がほぼ全面 | 📋 ローカル手動 verify (ユーザー側) |
| L35 | ReasoningPanel が collapse / resize 可能、minimum width で生き残る | ✅ 実装完了 (HSplitContainer + ▶ button、60px collapsed) |
| L36 | OptionButton / camera 操作 / day-night ambient regression なし | ✅ Godot regression 12/12 pass + full pytest 1044 pass |
| L37 | /reimagine v1+v2 並列 (anchor 設計は複数案ありうる) | ✅ design-comparison.md + codex-review.md 両方で 2 案以上比較 |

機械検証ログ:
- `uv run pytest tests/test_godot_*.py` → 12/12 pass (peripatos 6 + dialog_bubble 3 + mode_tint 2 + ws_client 1)
- `uv run pytest -m "not godot"` → 1031 passed exit=0 (regression なし)
- `uv run pytest` (full、Godot 含む) → 1044 passed exit=0
- `uv run ruff check src tests` → exit=0
- `uv run ruff format --check src tests` → exit=0
- `uv run mypy src` → exit=0

## レビュー対応サマリ

### codex review (gpt-5.5, xhigh) — 全件反映済
- HIGH-1 (split_offset deprecated) → D2 で両対応
- HIGH-2 (320/340/60 矛盾) → 定数 PANEL_EXPANDED_WIDTH/COLLAPSED_WIDTH 分離で解消
- HIGH-3 (collapse で body hide) → `_body_container.visible` で解消
- MEDIUM-4 (size_2d_override_stretch no-op) → 追加せず
- MEDIUM-5 (drag 幅永続化) → `_last_expanded_offset` + `dragged` signal で解消
- LOW-6 (button を panel root に add) → `_build_header(parent)` で vbox 配下に明示

### code-reviewer (Claude subagent) — 反映 / 持ち越し
- HIGH (split_offsets vs split_offset 乖離) → D2 で両対応に解消
- MEDIUM (alias シャドウイング) → コメント追加で解消
- MEDIUM (header の SIZE_EXPAND_FILL) → コメントで補足、実用上問題なし
- MEDIUM (toggle atomic 性) → GDScript single-thread のため LOW 級と判断、対応なし
- LOW (has_signal 防御の過剰) → 一貫性低下を許容、現状維持
- LOW (tscn / GDScript の 340 二重定義) → Godot 慣習に従い tscn 値はエディタ用 default として残置
