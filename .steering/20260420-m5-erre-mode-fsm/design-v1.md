# 設計 — m5-erre-mode-fsm (v1 初回案)

**/reimagine 対象**: 本タスクは公開 API (Protocol concrete 実装) を導入するので
design 段階で /reimagine を適用する。本 v1 を書いた後に `design-v1.md` へ退避して
v2 をゼロから再生成し、`design-comparison.md` で比較してから採用を決める。

## 実装アプローチ

`erre/` を新規パッケージとして src 配下に追加し、`fsm.py` に `DefaultERREModePolicy`
という単一 class を置く。`ERREModeTransitionPolicy` Protocol の `next_mode` を
実装する。

遷移判定の優先順位 (最初にマッチしたものを採用):

1. `ERREModeShiftEvent` with `reason="external"` があれば `current` mode を返す
   (=変更なし、外部由来の遷移は呼び出し側が既に `AgentState.erre` を更新済と仮定)
2. `InternalEvent` で `content.startswith("shuhari_promote:")` → shu → shu_kata、
   ha → ha_deviate、ri → ri_create (ShuhariStage から該当 ERRE mode を map)
3. `InternalEvent` で `content.startswith("fatigue:")` → CHASHITSU へ遷移 (回復の
   ための静的 zone default としての意味)
4. 最新の `ZoneTransitionEvent` があれば `to_zone` の default mode を返す
5. 上記いずれもなければ `None` を返す (現状維持)

`current` と同じ mode に "遷移" する場合は `None` を返す (= 呼び出し側が
`ERREModeShiftEvent` を emit しないで済ませる)。

## 変更対象

### 新規作成するファイル

- `src/erre_sandbox/erre/__init__.py` — `DefaultERREModePolicy`,
  `ZONE_TO_DEFAULT_ERRE_MODE` を re-export
- `src/erre_sandbox/erre/fsm.py` — `DefaultERREModePolicy` class + module-level
  定数 `ZONE_TO_DEFAULT_ERRE_MODE`
- `tests/test_erre/__init__.py` — 空 (package 宣言)
- `tests/test_erre/test_fsm.py` — 遷移 unit test 群

### 修正するファイル

- `src/erre_sandbox/bootstrap.py` — `_ZONE_TO_DEFAULT_ERRE_MODE` を削除し、
  `from erre_sandbox.erre import ZONE_TO_DEFAULT_ERRE_MODE` に置換

### 削除するファイル

- なし

## fsm.py のコード構造 (擬似コード)

```python
from collections.abc import Sequence
from typing import Final

from erre_sandbox.schemas import (
    ERREModeName,
    ERREModeShiftEvent,
    ERREModeTransitionPolicy,
    InternalEvent,
    Observation,
    ShuhariStage,
    Zone,
    ZoneTransitionEvent,
)

ZONE_TO_DEFAULT_ERRE_MODE: Final[dict[Zone, ERREModeName]] = {
    Zone.STUDY: ERREModeName.DEEP_WORK,
    Zone.PERIPATOS: ERREModeName.PERIPATETIC,
    Zone.CHASHITSU: ERREModeName.CHASHITSU,
    Zone.AGORA: ERREModeName.SHALLOW,
    Zone.GARDEN: ERREModeName.PERIPATETIC,
}
"""Zone → デフォルト ERRE mode の正準マップ.

persona-erre Skill §ルール 5 の table に 1:1 対応。
garden のみ ri_create ではなく peripatetic を採用 (bootstrap.py での既存挙動を踏襲)。
"""

_SHUHARI_TO_MODE: Final[dict[ShuhariStage, ERREModeName]] = {
    ShuhariStage.SHU: ERREModeName.SHU_KATA,
    ShuhariStage.HA: ERREModeName.HA_DEVIATE,
    ShuhariStage.RI: ERREModeName.RI_CREATE,
}


class DefaultERREModePolicy:
    """Default implementation of ERREModeTransitionPolicy.

    Event-driven FSM replacing the static map in bootstrap.
    """

    def next_mode(
        self,
        *,
        current: ERREModeName,
        zone: Zone,
        observations: Sequence[Observation],
        tick: int,
    ) -> ERREModeName | None:
        # 1. external manual override
        for ev in reversed(observations):
            if isinstance(ev, ERREModeShiftEvent) and ev.reason == "external":
                return None  # already updated by caller
        # 2. shuhari promotion
        for ev in reversed(observations):
            if isinstance(ev, InternalEvent) and ev.content.startswith(
                "shuhari_promote:"
            ):
                stage_str = ev.content.split(":", 1)[1]
                try:
                    stage = ShuhariStage(stage_str)
                except ValueError:
                    continue
                candidate = _SHUHARI_TO_MODE[stage]
                return None if candidate == current else candidate
        # 3. fatigue → chashitsu
        for ev in reversed(observations):
            if isinstance(ev, InternalEvent) and ev.content.startswith("fatigue:"):
                return None if current == ERREModeName.CHASHITSU else ERREModeName.CHASHITSU
        # 4. zone entry → zone default mode
        for ev in reversed(observations):
            if isinstance(ev, ZoneTransitionEvent):
                candidate = ZONE_TO_DEFAULT_ERRE_MODE.get(
                    ev.to_zone,
                    ERREModeName.DEEP_WORK,
                )
                return None if candidate == current else candidate
        # 5. nothing → hold
        return None
```

## 影響範囲

- **新パッケージ**: `src/erre_sandbox/erre/` — layer 依存方向は
  `schemas ← erre ← bootstrap` (cognition / world / integration は本 task では触れず、
  後続 sub-task で逆依存を追加)
- **bootstrap.py**: import 先が 1 行変わるだけで既存挙動は unchanged (boot 時の
  default mode 決定は ZONE_TO_DEFAULT_ERRE_MODE の同値を使う)
- **downstream sub-task**:
  - `m5-world-zone-triggers` が `DefaultERREModePolicy` を import して `WorldRuntime`
    の tick で呼び出す (本 task の merge 後)
  - `m5-orchestrator-integration` が feature flag でインスタンス化 (`--disable-erre-fsm`)

## 既存パターンとの整合性

- `_ZONE_TO_DEFAULT_ERRE_MODE` の既存 entry を完全移植 (値は unchanged)
- `integration/dialog.py::InMemoryDialogScheduler` 同様、Protocol に対する concrete
  class を layer の中に置く (schemas には Protocol のみ)
- test 配置は `tests/test_erre/` 新設 (既存 `tests/test_memory/` / `tests/test_world/`
  と同パターン)
- `bootstrap.py` は `cognition/` / `integration/` から具体クラスを import している既存
  パターンと同じく、`erre/` からも import できる

## テスト戦略

### Unit (`tests/test_erre/test_fsm.py`)

- `test_zone_entry_moves_to_zone_default_mode` (5 zone 全てで検証)
- `test_zone_entry_returns_none_when_already_in_default_mode`
- `test_external_override_returns_none_when_current_already_reflects`
- `test_shuhari_promote_shu_to_shu_kata`
- `test_shuhari_promote_ha_to_ha_deviate`
- `test_shuhari_promote_ri_to_ri_create`
- `test_shuhari_promote_with_invalid_stage_is_ignored`
- `test_fatigue_internal_event_moves_to_chashitsu`
- `test_fatigue_noop_when_already_in_chashitsu`
- `test_priority_external_over_internal_over_zone`
- `test_no_observations_returns_none`
- `test_unknown_observation_kind_returns_none`

parametrize で 8 mode → 5 zone を組み合わせ覆う。

### 回帰

- `uv run pytest -q` 全体 PASS (既存 513 + 新規 ~15)
- `bootstrap.py` の既存 test (_build_initial_state) は ZONE_TO_DEFAULT_ERRE_MODE の
  import 元が変わっても PASS (値は unchanged)

### 統合

なし (本 task は concrete policy 単独で閉じる。統合 test は
`m5-world-zone-triggers` / `m5-orchestrator-integration` で追加)

## ロールバック計画

- 単一 PR `feature/m5-erre-mode-fsm`
- 問題時は `git revert` で `erre/` パッケージごと削除。bootstrap.py の 1 行だけ
  戻せば元の静的 map に復帰
- feature flag は `m5-orchestrator-integration` 側で `--disable-erre-fsm` を導入
  するので、本 task の merge 時点では FSM は呼び出されない (dead code = 安全)

## 制約・リマインダ

- `erre/` は `schemas` のみ import (architecture-rules 準拠)
- GPL 依存を追加しない
- Pydantic v2 BaseModel は本 task では不要 (Protocol 実装は plain class で充分)
- `from __future__ import annotations` を冒頭に置く (python-standards)
