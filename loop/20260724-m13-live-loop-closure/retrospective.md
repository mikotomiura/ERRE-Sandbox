# retrospective — M13 live 双方向ループ閉包（実装）

## 結果
FROZEN ADR の I1〜I6 を Loop（subagent-per-issue）で完遂。branch `feat/m13-live-loop-closure`、
local commit `a332286`。統合 CI parity 全 4 段 PASS（pytest 3863 passed）。push/PR/merge は user 裁定。

## honest（不可侵、達成状態）
**配線であって aha/emergence/effect でない。** wiring reached each seam を W-live（到達性のみ）で witness、
W-golden（byte-parity）は regression guard。door② UNMET・計測 CLOSE・R-budget=0・holding 不変。
organ / production(`bootstrap()`/`world/tick.py`) / `ControlEnvelope` outbound / 既存 golden は無改変。

## 効いた点
- **実読 grounding を先に固めた**: HIGH-1 outbound owner（`_consume_result` 単一）/ HIGH-3 schema 分離 /
  I2/I3/I4 seam を実コードで確定してから issue 化 → 各 subagent が flail せず一発で緑。
- **disjoint file set の並行実行**: I5(Godot) を I3-docstring と、I4 を I5 と並行（parallel=1 を disjoint 時のみ緩和）
  → 待ち時間を圧縮。競合する live_loop.py 系（I3/I4/I6）は sequential 厳守。
- **verify_level=recheck の Haiku 独立再走 + 境界の Bash 客観確認**を全 issue で二重化 → 自己申告を客観打消し。
- **cross-review の二者差分が価値**: Opus Approve でも Codex が honest-framing の緩み 2 HIGH（`firing_summary_detail`
  verbatim / `emitted_envelope` の per-corr 過大表現）を独立検出 → 反映で witness を binding に厳密一致。

## 詰まり / 学び
- **Codex sandbox shell `CreateProcessAsUserW 1312`**（auth は OK）: 統合 diff を pipe すれば review 可能
  （ADR 時と同条件）。`codex exec` は shell retry で時間を食うので Bash tool の 2min default を超える→背景実行必須。
- **`.steering/` は gitignore**: PR link は tracked な `loop/` の `design-final-ref.md` / `codex-review-post.md` に置く
  （前タスク 20260723 の `design-final-ref.md` パターン踏襲）。
- **grep フィルタ `_loop` が `live_loop.py` に誤マッチ**: 境界確認の除外パターンは要注意（機能面は別 grep で担保した）。

## 残（user 裁定）
push / PR 作成 / 最終 merge / I7 real qwen3 sealed 実走（code-path のみ・spend ratify 別ゲート）/
I5 headless-godot 実効 send（環境 gate、本機 godot 無し）/ WSL⇄Win byte-parity 実測。
