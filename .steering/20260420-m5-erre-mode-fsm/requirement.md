# m5-erre-mode-fsm — ERRE mode 遷移 FSM の実装

## 背景

M5 は ERRE mode FSM + dialog_turn LLM 生成の両輪。`m5-contracts-freeze` (PR #56,
merged 2026-04-20) で `ERREModeTransitionPolicy` Protocol が凍結済。

現状の ERRE mode 割り当てはブート時に `_ZONE_TO_DEFAULT_ERRE_MODE` 静的マップで 1 回
だけ走るだけで、以降は変化しない (`bootstrap.py:121` `_build_initial_state`)。
MASTER-PLAN §5 の M5 定義 (ERRE モード 6 種切替) と planning design.md の
"event-driven FSM に置換" を満たすには、world tick 毎に現在 mode の継続/遷移を判定
するコンクリート実装が必要。

本タスクは `ERREModeTransitionPolicy` Protocol の **concrete 実装** だけを owns する。
zone change 検出・sampling 反映・bootstrap wiring は後続 sub-task に委ねる。

## ゴール

`src/erre_sandbox/erre/` パッケージを新設し、`ERREModeTransitionPolicy` を実装した
concrete クラスを配置する。8 ERRE mode 全ての遷移パターン (zone entry / fatigue
signal / shuhari promotion / manual override) を unit test で網羅する。後続の
`m5-world-zone-triggers` と `m5-orchestrator-integration` が本クラスを import して
`WorldRuntime` 経由で wire できる状態まで仕上げる。

## スコープ

### 含むもの

- **新規パッケージ** `src/erre_sandbox/erre/`:
  - `__init__.py` — 公開 API export
  - `fsm.py` — `ERREModeTransitionPolicy` Protocol の concrete 実装
    (クラス名は design で確定。現時点の候補: `DefaultERREModePolicy`)
- **遷移規則** (Observation ストリームを入力):
  - `ZoneTransitionEvent` → zone の default ERRE mode へ遷移 (zone-mode map は
    persona-erre Skill §ルール 5 に準拠、既存 `_ZONE_TO_DEFAULT_ERRE_MODE` を移植)
  - `ERREModeShiftEvent`with `reason="external"` → manual override (そのまま承認)
  - `InternalEvent` with 特定 content パターン → fatigue / shuhari 遷移 (後続 task が
    InternalEvent を synthesize する前提で、本 task では content prefix ベースの
    minimal 判定を実装)
  - 上記以外 → `None` を返す (= 現在 mode 維持)
- **Zone → Default Mode map の移設**: `bootstrap.py` の `_ZONE_TO_DEFAULT_ERRE_MODE`
  を `erre/fsm.py` に移し、bootstrap 側は import する (import 方向は
  architecture-rules に従って安全: bootstrap → erre は OK)
- **Unit test**:
  - `tests/test_erre/` パッケージ新設
  - `tests/test_erre/__init__.py`
  - `tests/test_erre/test_fsm.py` — 遷移規則の 8 mode 全パターン + 境界ケース
- **型/リント整合**: ruff / mypy (strict) 全 PASS、既存 test に回帰なし

### 含まないもの

- **world/tick.py への zone change hook** → `m5-world-zone-triggers` の責務
- **sampling override の live 反映** → `m5-erre-sampling-override-live` の責務
- **`bootstrap.py` / `WorldRuntime` の wiring** → `m5-orchestrator-integration` の責務
- **Godot 側の mode tint 視覚化** → `m5-godot-zone-visuals` の責務
- **InternalEvent を synthesize する側 (fatigue / shuhari の検出ロジック)** →
  本 task は InternalEvent が入力として来た場合の扱いだけ実装。synthesize は
  後続 (world-zone-triggers か別 task)
- **persona YAML 変更 / zone 追加**

## 受け入れ条件

- [ ] `src/erre_sandbox/erre/__init__.py` / `fsm.py` が新設され、
      `ERREModeTransitionPolicy` Protocol に適合する concrete クラスを export
- [ ] `DefaultERREModePolicy.next_mode()` が:
  - [ ] `ZoneTransitionEvent` 受信 → to_zone の default mode を返す (現在 mode が
        同じ場合は `None` を返す)
  - [ ] `ERREModeShiftEvent(reason="external")` 受信 → `current` を返す
  - [ ] `InternalEvent` with `content.startswith("fatigue:")` → CHASHITSU へ遷移 (仮)
  - [ ] `InternalEvent` with `content.startswith("shuhari_promote:")` → shuhari
        stage に対応する mode (`shu_kata` / `ha_deviate` / `ri_create`) へ遷移
  - [ ] 上記以外 → `None` を返す
- [ ] `bootstrap.py` の静的 map が `erre.fsm.ZONE_TO_DEFAULT_ERRE_MODE` の import に
      置き換わり、boot 時の挙動は unchanged (既存 bootstrap test PASS)
- [ ] `tests/test_erre/test_fsm.py` で 8 mode 全遷移 + 境界 (zone same / 未知 event)
      をカバー、全 PASS
- [ ] `uv run pytest -q` 全 PASS (0 failures)
- [ ] `uv run ruff check src tests` / `ruff format --check` PASS
- [ ] `uv run mypy src/erre_sandbox` 0 errors
- [ ] architecture-rules Skill の layer 規則に違反しない (`erre/` は schemas のみ
      import、bootstrap / world / cognition から `erre/` への依存はこの task では
      bootstrap のみ、残りは後続)

## 関連ドキュメント

- `.steering/20260420-m5-planning/design.md` §Schema 0.3.0-m5 追加内容 (Protocol
  signature の出処)、§3 新軸 (M 軸)
- `.steering/20260420-m5-contracts-freeze/design.md` (Protocol の interface freeze)
- `.claude/skills/persona-erre/SKILL.md` §ルール 5 (Zone → Default Mode table の
  正準版)
- `.claude/skills/architecture-rules/` (layer 依存方向の検証)
- `src/erre_sandbox/schemas.py` §7.5 `ERREModeTransitionPolicy` (Protocol 定義)
- `src/erre_sandbox/bootstrap.py:121` (移植元の静的マップ)

## 運用メモ

- **タスク種別**: 新機能追加 (新規パッケージ `erre/` + concrete policy)
- **破壊と構築 (/reimagine) 適用**: **Yes**
  - 理由: 複数の設計案が考えられる (遷移判定を純関数で書くか class 方式か、
    InternalEvent パターンマッチの粒度、sentinel mode vs None、既定マップを module
    定数 vs class 属性 など)。後続 3 sub-task が import する concrete class なので
    API 形状は慎重に決めたい。memory `feedback_reimagine_scope.md` 「迷ったら適用」
    ルールにも合致。
