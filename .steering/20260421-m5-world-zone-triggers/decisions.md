# Decisions — m5-world-zone-triggers

本タスク (ERRE mode FSM を実行フローに wire up) で下した非自明な設計判断の記録。

## 判断 1: /reimagine で v2 (cognition 層内包) を採用

- **判断日時**: 2026-04-21
- **背景**: FSM 呼出しの layer / location に複数案がある。v1 は `world/tick.py`
  に直接フック (`world/ → erre/` layer 許可が必要)、v2 は
  `CognitionCycle.step()` に内包 (`cognition/ → erre/` のみ許可)。
- **選択肢**:
  - A (v1): world/tick.py で FSM を呼ぶ。`WorldRuntime.attach_erre_policy` 新設
  - B (v2): cognition/cycle.py で FSM を呼ぶ。`CognitionCycle(erre_policy=...)` ← **採用**
- **理由**:
  1. ERRE mode は認知状態 → cognition 層が自然な owner
  2. `world/tick.py` 完全無変更で regression リスク最小 (M4 で安定した実装)
  3. mode 変更が同 tick 内で有効 (Step 5 の LLM sampling が新 mode 参照)
  4. `reflector` 注入パターンと対称
  5. `m5-orchestrator-integration` の wiring が単純 (`CognitionCycle(erre_policy=DefaultERREModePolicy())` の 1 行)
- **トレードオフ**: `CognitionCycle` の責務が広がる (ただし本来 cognition の仕事なので妥当)
- **影響範囲**: `src/erre_sandbox/cognition/cycle.py` (`__init__` + helper + Step 2.5 挿入)
- **見直しタイミング**: もし将来 mode 遷移を cognition cycle とは別のタイミングで
  実行したい需要が出たら、別 hook を用意するか v1 の world-runtime 呼出しパターンを
  追加する

## 判断 2: architecture-rules を更新し `cognition/ → erre/` を明示許可

- **判断日時**: 2026-04-21
- **背景**: 前タスク `m5-erre-mode-fsm` の decisions.md §4 で先送りした layer 依存
  判断を、本タスクで決着させる必要。
- **選択肢**:
  - A: `world/ → erre/` を許可 (v1 採用時)
  - B: `cognition/ → erre/` を許可、`world/ → erre/` は明示禁止 ← **採用**
- **理由**: v2 採用に合わせて。cognition は既に domain logic を抱えるので erre 依存
  は自然。world は runtime 骨格に留め erre の具体は知らない方が layer 境界が明瞭
- **変更内容**:
  - `cognition/` 依存先: `inference/, memory/, schemas.py` → `+ erre/`
  - `world/` 依存禁止: `ui/` → `+ erre/`
  - `erre/` 依存禁止: 既存 `world/, ui/` → `+ cognition/` (循環防止)
- **影響範囲**: `.claude/skills/architecture-rules/SKILL.md` 依存テーブル
- **見直しタイミング**: v1 への切替えが必要になった場合 (現状想定なし)

## 判断 3: FSM hook を Step 2 と Step 3 の間に挿入

- **判断日時**: 2026-04-21
- **背景**: `CognitionCycle.step()` の 9-step pipeline のどこに FSM を入れるか。
- **選択肢**:
  - A: Step 1 直後 (episodic write の後)
  - B: Step 2 と Step 3 の間 (advance_physical の後、reflection trigger の前) ← **採用**
  - C: Step 9 直前 (new_cognitive と合流)
  - D: Step 10 (reflection と同列)
- **理由**: Step 5-6 の LLM call が `agent_state.erre.sampling_overrides` を使う
  (line 203)。FSM を Step 5 より前に置けば同 tick 内で新 mode の sampling が
  反映される (**zero-tick latency**)。Step 2 直後は "Physical 更新後の state" を
  FSM が見られる順序で、reflection trigger (Step 3) より前だから reflection が
  mode 遷移後の state を見られる
- **トレードオフ**: `advance_physical` が zone を変更するケースが将来発生したら
  FSM は旧 zone で判断する (現在は physical は zone を変えないので safe)。この
  制約を docstring に明記
- **影響範囲**: `cycle.py::step` 内の挿入位置、`_fallback` が FSM 更新済 state を
  受け取る flow

## 判断 4: ERREModeShiftEvent を本 task では emit しない

- **判断日時**: 2026-04-21
- **背景**: FSM が mode を変えた時、`ERREModeShiftEvent` (Observation) を下流に
  流すか決める必要。
- **選択肢**:
  - A: 今 tick の observations に追記 (次以降の cycle 判断 / reflection に影響)
  - B: CycleResult.envelopes に追加 (Godot / memory への explicit signal)
  - C: emit しない。`AgentUpdateMsg` に含まれる `agent_state.erre` の変化で
    伝播させる ← **採用**
- **理由**: (1) `AgentUpdateMsg` は Step 9 で必ず emit され、Godot は
  `agent_update.agent_state.erre` から変化を検知できる、(2) 本 tick の
  `observations` に追記すると reflection trigger に predictable 以上の影響が
  出て副作用が複雑化する、(3) 追加の event stream を導入せず最小変更に留める
- **トレードオフ**: 将来 reflection が "mode が変わった瞬間" を学習対象にしたい
  時に追加する必要 (easy to backfill: 1 行追加で可能)
- **影響範囲**: なし (emit しないだけ)
- **見直しタイミング**: reflection scoring で mode shift を importance 源に
  したい需要が出た時 (M6+)

## 判断 5: `candidate == current` を no-op として扱う

- **判断日時**: 2026-04-21
- **背景**: code-reviewer MEDIUM 指摘。Protocol docstring は
  "must differ from current" と要求するが、実装が違反した場合の defensive guard
  が不在。
- **選択肢**:
  - A: Protocol 違反として例外を投げる
  - B: no-op として処理 (`agent_state` unchanged) ← **採用**
  - C: そのまま新 `ERREMode(entered_at_tick=tick)` を作る (= 既存挙動、意図せず
    transition を mark)
- **理由**: B は最小限の影響で defensive に動く。Protocol 違反で crash する
  よりは、loop を壊さず "宣言上の transition なし" にする方が運用安全
- **トレードオフ**: 違反を静かに握りつぶすので policy 実装者の debug が難しくなる
  可能性 (ただし `logger.debug` で transition log が出ないので間接的に検出可能)
- **影響範囲**: `_maybe_apply_erre_fsm` の guard 1 行、対応する regression test
  1 件

## 判断 6: code-reviewer MEDIUM/LOW を反映

- **判断日時**: 2026-04-21
- **対応**:
  - MEDIUM 1 (FSM が pre-physical zone を見る) → docstring に明示注記追加
    (現状 `advance_physical` が zone 変えないので safe、将来変わった時の hook 済)
  - MEDIUM 2 (candidate == current guard) → 判断 5 参照、guard + test 追加
  - LOW 3 (Protocol runtime_checkable) → 現状 Protocol は非 runtime_checkable
    なので受容 (必要性が出たら後で追加)
  - LOW 4 (`_fallback` docstring) → 現状 docstring は十分、受容 (軽微)
