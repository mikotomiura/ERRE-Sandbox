# Decisions — M5 Planning

本タスク (M5 計画策定) で下したユーザー決定および非自明な設計判断の記録。

## 判断 1: M5 scope = ERRE mode FSM + dialog_turn LLM 生成 両輪

- **判断日時**: 2026-04-20
- **背景**: MASTER-PLAN §5 の M5 定義 (ERRE mode 6 種切替) と M4 acceptance
  の "dialog_turn は M5 で LLM 接続時に実装" 明記に矛盾があり、scope 確定が必要
- **選択肢**:
  - A: MASTER-PLAN 通り ERRE mode FSM のみ (dialog_turn は M6 へ繰越)
  - B: ERRE mode FSM + dialog_turn LLM 生成 両輪 (両 deferred を一気に回収) ← **採用**
  - C: dialog_turn LLM 生成 + Godot 表示のみ (ERRE mode FSM を M6 へ後ろ倒し)
- **理由**: M4 acceptance で dialog_turn を M5 と明言しており、切り離すと acceptance 記録
  との整合が崩れる。両輪は schema bump 1 回で一緒に凍結した方が contract の二重更新を避けられる。
  M5 acceptance の完了条件も両輪揃った状態で自然に 7 項目揃う
- **トレードオフ**: scope が大きくなり 4-6 日 + spike 0.5 日 = 4.5-6.5 日の工数。
  C 案なら 2-3 日で済むが acceptance 記録との整合修正が必要
- **影響範囲**: `schemas.py`, `integration/dialog.py`, 新規 `erre/` パッケージ,
  `bootstrap.py`, `godot_project/scripts`, 全 sub-task の規模と数
- **見直しタイミング**: `m5-llm-spike` で dialog_turn プロンプト品質が実用水準に届かない
  ことが判明した場合、C 案 (mode のみ先行) へ退避する選択肢を残す

## 判断 2: schema `0.3.0-m5` へ minor bump

- **判断日時**: 2026-04-20
- **背景**: M5 で `DialogTurnMsg.turn_index` 追加、`DialogCloseMsg.reason="exhausted"`
  追加、`Cognitive.dialog_turn_budget` 追加、新 Protocol 追加が必要
- **選択肢**:
  - A: M5 開始時に 0.3.0-m5 へ bump (Contract-First で freeze) ← **採用**
  - B: scope 確定後に判断
  - C: 0.2.0-m4 を維持 (内部 state のみの変更と見なす)
- **理由**: dialog_turn emit 時の envelope が wire 上で `turn_index` を含むため、
  schema 凍結が先行しないと Godot side の consumer が parse 失敗する。
  `DialogCloseMsg.reason` literal 拡張も wire 互換の観点で schema_version が上がる。
  追加は全て additive (default 付き optional + literal 拡張)、既存 M4 fixture と
  backward 互換。M4 での Contract-First 成功例 (手戻り ゼロ) を踏襲
- **トレードオフ**: fixture 再生成と conftest 更新が必要、初期オーバーヘッドが 0.5-1 日
- **影響範囲**: `schemas.py`, `fixtures/control_envelope/*`, `tests/schema_golden/*`,
  `conftest.py`, GDScript 側の envelope parse (既存 EnvelopeRouter.gd は additive で parse 可)
- **見直しタイミング**: spike で `turn_index` 以外の新 field が必要と判明した場合
  (例: stop-reason token の明示化)、contracts-freeze 着手前に再確定

## 判断 3: /reimagine (破壊と構築) を M5 planning 全体に適用

- **判断日時**: 2026-04-20
- **背景**: memory `feedback_reimagine_scope.md` で「content curation 含め、迷ったら適用」
  ルール。M5 は public contract (schema) を bump するアーキテクチャ判断を含む
- **選択肢**:
  - A: M5 planning 全体に適用 (2 案作って比較して採用) ← **採用**
  - B: sub-task ごとに判断
  - C: 適用せず単一案で進む
- **理由**: M4 が 3-軸分解 1 案で進んでしまい、dialog_turn LLM 生成の
  プロンプト品質リスクが最後まで見えなかった。初回案 (案 A = M4 パターン再適用) を
  意図的に破棄して対抗案 (案 B = Risk-First Vertical Slicing) を並べたことで、
  LLM spike を先行させる hybrid に到達できた
- **トレードオフ**: planning 段階で 1-2 日の余計な時間がかかるが、実装中の手戻り
  リスクを前倒しで潰せる
- **影響範囲**: 本 planning タスクの design-v1.md / design-comparison.md / design.md
  の 3 ファイル構成、および以降の sub-task 群の順序 (spike が先行する)
- **見直しタイミング**: spike 結果が想定外 (例: qwen3:8b で peripatos 対話が完全に
  幻覚ベース) だった場合、design.md を破棄して再 reimagine する

## 判断 4: LLM spike は throwaway (コード commit しない)

- **判断日時**: 2026-04-20
- **背景**: spike はプロンプト shape の経験的決定が目的で、実装コードは後続の
  `m5-dialog-turn-generator` で正式実装される
- **選択肢**:
  - A: spike コードを commit せず、知見のみ `.steering/20260421-m5-llm-spike/decisions.md` に残す ← **採用**
  - B: spike コードを `experiments/` 的ディレクトリに commit
- **理由**: spike の目的は「捨てる前提の探索」。commit すると技術負債化し、後続 sub-task
  との参照関係が曖昧になる。知見だけを steering に残せば contract-freeze と
  turn-generator の設計に反映できる
- **トレードオフ**: 再現性が低下するが、experiments の spike を参照することは想定しない
- **影響範囲**: `.steering/20260420-m5-llm-spike/` は `decisions.md` 中心の薄い構成、
  ad-hoc scripts は `/tmp` で実行し commit しない

## 判断 5: Godot 視覚化の粒度 = MVP (Label3D + tint、AnimationPlayer は M6)

- **判断日時**: 2026-04-20
- **背景**: M5 acceptance #5/#6 で「bubble 表示」「mode tint 目視可能」が PASS 基準。
  過剰に凝る必要がないが、未実装だと acceptance が通らない
- **選択肢**:
  - A: Label3D + material.albedo_color tint + Tween fade (MVP) ← **採用**
  - B: AnimationPlayer + particle system + per-mode 3D models (本格化)
  - C: UI CanvasLayer で bubble を 2D 固定
- **理由**: A は既存 SpeechBubble と同パターンで再利用性が高い。B は M5 scope が
  FSM + LLM で既に大きいため割り当てが足りない。C は 3D 空間の位置情報を失い、
  「誰が誰に話しているか」の視覚的連想が崩れる
- **トレードオフ**: AnimationPlayer の本格利用は M6 に deferral。M5 の Godot は
  「形だけ」の視覚表現で留まる
- **影響範囲**: `godot_project/scenes/agents/AgentAvatar.tscn` (DialogBubble Label3D 追加)、
  `godot_project/scripts/AgentController.gd` (set_erre_mode + show_dialog_bubble 追加)

## 判断 6: Feature flag 3 種で rollback 可能性を担保

- **判断日時**: 2026-04-20
- **背景**: M5 の新機能で live acceptance が通らない場合、git revert せずに
  flag OFF で M4 相当に戻せる体制が必要 (運用負荷低減)
- **選択肢**:
  - A: `--disable-erre-fsm` / `--disable-dialog-turn` / `--disable-mode-sampling` ← **採用**
  - B: git revert 依存のみ
  - C: 環境変数で制御
- **理由**: A はユーザー (運用者) が再起動だけで切替可能。B は revert 漏れのリスク。
  C は M4 の CLI flag 設計パターン (e.g. `--skip-health-check`) に不整合
- **トレードオフ**: flag ON/OFF の両方を test で covering する必要があり、test 数が
  +5-10 件。ただし feature flag の testing は M4 でも軽微に実施済
- **影響範囲**: `src/erre_sandbox/__main__.py` (flag 宣言)、`bootstrap.py` (wiring 分岐)、
  `tests/test_bootstrap.py` + `tests/test_main.py` の拡張

## 判断 7: タスクディレクトリ prefix = 20260420 (plan ファイルの 20260421 と相違)

- **判断日時**: 2026-04-20
- **背景**: 承認済 plan ファイル `async-petting-moon.md` は M5 task を `20260421-m5-*`
  と前置していたが、本タスク開始時点で `date` コマンドは `20260420` を返した
- **選択肢**:
  - A: 実際の date に合わせて `20260420-m5-*` ← **採用**
  - B: plan の通り `20260421-m5-*`
- **理由**: M4 の naming 規約 ("タスク開始日を prefix") に従うと実施日 = 2026-04-20。
  plan ファイルの `20260421-` は "翌日着手想定" の推測値だった
- **トレードオフ**: 無し (plan の description は prefix 変更に依存しない)
- **影響範囲**: `.steering/20260420-m5-*` の 9 ディレクトリ全て (llm-spike / contracts-freeze /
  erre-mode-fsm / ... / acceptance-live)
