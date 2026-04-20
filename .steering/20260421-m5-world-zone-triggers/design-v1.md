# 設計 — m5-world-zone-triggers (v1 初回案)

**/reimagine 対象**: architecture-rules 更新と DI パターンの選択肢が多い。
本 v1 を書いた後に `design-v1.md` へ退避し、v2 をゼロから生成して比較する。

## 実装アプローチ

**Direct injection into `WorldRuntime`** で、`_on_cognition_tick` の末尾に
FSM step を挿入する。architecture-rules は `world/ → erre/` を明示許可に更新。

### 処理フロー (既存 + 追加)

```
Physics tick (30Hz):
  - Kinematics step, zone change 判定
  - ZoneTransitionEvent を rt.pending に append         ← 既存
Cognition tick (10s):
  - For each rt:
    - obs_snapshot = list(rt.pending)                   ← 新規 (FSM 用 snapshot)
    - _step_one (rt.pending 消費 → cognition.step)      ← 既存
  - For each rt / result pair:
    - _consume_result (rt.state 更新)                   ← 既存
    - FSM step:                                          ← 新規
      - candidate = erre_policy.next_mode(
          current=rt.state.erre.name,
          zone=rt.state.position.zone,
          observations=obs_snapshot,
          tick=rt.state.tick,
        )
      - If candidate not None:
        - new_erre = ERREMode(name=candidate, entered_at_tick=rt.state.tick)
        - emit ERREModeShiftEvent into rt.pending
          (for the NEXT cognition tick's memory/reflection)
        - rt.state = rt.state.model_copy(update={"erre": new_erre})
  - _run_dialog_tick                                    ← 既存
```

### Hook location: `_on_cognition_tick` (末尾) の理由

- `_consume_result` の後に呼ぶことで、FSM は "cognition が state を更新した後" の
  ERRE mode を current として見る。通常 cognition は mode 名を変えないので、
  FSM の入力は前 tick の mode。ただし cognition が mode を書き換えた場合でも
  FSM はそれを current として尊重する
- 観測は cognition.step が消費する前に snapshot (observations が一度きりの
  生ログ) を取る必要がある。`_step_one` 冒頭で `rt.pending` を clear するため、
  その前に capture
- Physics tick ではなく cognition tick にした理由: (1) fatigue / shuhari 判定は
  cognition 由来のため cognition 後が自然、(2) 30Hz で FSM を呼ぶのは無駄、
  (3) ERRE mode の sampling override は次 cognition step で効くので cognition 境界
  と一致させる方が意図明瞭

### DI pattern: constructor + attach method

既存の `DialogScheduler` 注入パターン (`attach_dialog_scheduler`) をそのまま踏襲:

- `WorldRuntime.__init__(*, erre_policy: ERREModeTransitionPolicy | None = None)`
- `WorldRuntime.attach_erre_policy(policy: ERREModeTransitionPolicy) -> None`

デフォルト `None` → FSM 無効 (既存挙動を維持、bootstrap が明示的に attach しない
限り dead code はない)。

### Layer rule: `world/ → erre/` を architecture-rules に追加

`world/` が `erre_sandbox.erre` の **concrete class** を import することを許可する。
ただし `world/tick.py` は可能な限り Protocol type でタイプヒントする:

- `from erre_sandbox.schemas import ERREModeTransitionPolicy` (Protocol 型)
- concrete `DefaultERREModePolicy` は bootstrap が選択・注入

`world/` は Protocol 経由で FSM を呼ぶだけなので、本質的な「`world/` が `erre/`
を知っている」依存ではない。architecture-rules の更新は安全策として明示化する。

## 変更対象

### 修正するファイル

- `src/erre_sandbox/world/tick.py`:
  - import 追加: `ERREMode`, `ERREModeName`, `ERREModeShiftEvent`,
    `ERREModeTransitionPolicy` (schemas のみ)
  - `WorldRuntime.__init__` に `erre_policy` 引数追加
  - `WorldRuntime.attach_erre_policy` メソッド追加
  - `_on_cognition_tick` 内で obs_snapshot 取得 + FSM step 追加
  - `_step_one` は変更しない (observation consume は既存の通り)
- `.claude/skills/architecture-rules/SKILL.md`:
  - 依存テーブルに `world/ → erre/` を allowed で追加
  - 「新しいファイルの配置判断フロー」に必要なら ERRE mode FSM の注記
- `docs/architecture.md`:
  - `world/` レイヤーの説明に「ERRE mode FSM を `erre/` から注入」の記述を追加
- `tests/test_world/test_tick.py` (既存):
  - FSM 未注入で既存 test PASS (変更なしで OK)
  - 新規 test cases:
    - `test_cognition_tick_applies_erre_fsm_on_zone_entry`
    - `test_cognition_tick_emits_mode_shift_event`
    - `test_cognition_tick_noop_when_fsm_returns_none`
    - `test_cognition_tick_without_policy_skips_fsm`
    - `test_attach_erre_policy_post_construction`

### 新規作成するファイル

- なし (test の新 function は既存ファイル内)

### 削除するファイル

- なし

## 影響範囲

- **wire 互換**: なし (contract 層は未変更)
- **bootstrap.py**: 本 task では変更しない。`m5-orchestrator-integration` で
  `DefaultERREModePolicy()` を生成・`runtime.attach_erre_policy(policy)` で wire
- **既存 test**: FSM default None なので既存 tests/test_world/* は無変更で PASS
- **architecture-rules**: `world/ → erre/` 許可追加が本 task の最大 meta-change

## 既存パターンとの整合性

- DialogScheduler の注入パターン (`attach_dialog_scheduler`) を 1:1 複製
- `model_copy(update={...})` の state 更新パターンは既存 `_on_physics_tick` L352 と
  `_consume_result` L459 に precedent あり
- `ERREModeShiftEvent` emit は既存 `ZoneTransitionEvent` emit (L354) と同パターン
- Protocol 型でタイプヒントし、concrete は DI で差替可能にするのは
  `InMemoryDialogScheduler` と同構造

## テスト戦略

### 単体 (`tests/test_world/test_tick.py`)

- `test_erre_policy_not_injected_keeps_mode_static` — default None 時に既存
  挙動を維持 (shift 非発火)
- `test_zone_entry_triggers_mode_transition` — 物理 tick で peripatos 入場 →
  次 cognition tick で erre.name が PERIPATETIC に
- `test_mode_shift_event_emitted_to_pending` — 遷移発生時に次 tick の pending に
  ERREModeShiftEvent が載ること (memory/reflection が拾えるように)
- `test_fsm_returns_none_leaves_state_unchanged` — Mock policy で None 返却 →
  `rt.state.erre` 変わらず、pending に ERREModeShiftEvent も載らず
- `test_attach_erre_policy_after_construction` — constructor で None、後から
  attach で注入できる
- `test_custom_erre_policy_observed_obs_snapshot` — Mock policy を注入して
  `obs_snapshot` が期待通り渡ることを spy で検証

### 回帰

- 既存 `tests/test_world/*` 全 PASS
- 既存 `tests/test_bootstrap*` (FSM 未 wire 状態を維持) PASS

### 統合

- 本 task では integration test は追加しない (bootstrap wiring は
  `m5-orchestrator-integration` で追加)

## ロールバック計画

- 単一 PR `feature/m5-world-zone-triggers`
- 問題時は `git revert`。`erre_policy=None` default なので runtime 挙動は
  attach しない限り unchanged
- architecture-rules の update も同時 revert (関連変更)

## 設計判断の履歴

(採用後に追記)
