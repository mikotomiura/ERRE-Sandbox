# 設計 — m5-erre-mode-fsm (v2 reimagine 再生成案)

## 実装アプローチ

ERRE mode 遷移を "時系列イベント駆動の reduction" として定式化する。
`Observation` のシーケンスを観察順にたたみ込み、最後に確定した mode を返す
(= **latest signal wins**)。

この方針の核心:

1. **Priority table を持たない**。呼び出し側 (world tick) が observation を
   chronological に並べて渡すので、FSM はその順序を尊重するだけ。事前に決めた
   優先順位より callable の文脈 (どの signal が直前に起こったか) が意味を持つ。
2. **DI 可能なマップ**。`ZONE_TO_DEFAULT_ERRE_MODE` を class の **コンストラクタ
   引数** として注入する。既定値はモジュール定数だが test や downstream の
   feature flag が差し替え可能。
3. **Single `match` statement for dispatch**。`Observation` discriminated union を
   `match/case` でほどき、各 handler は純関数。handler 数 = 観察種別数 (4) に厳密
   に制約。priority list の "順序" を保守する余地がない設計。
4. **Idempotent return contract**: `next_mode` 内で `current` との比較はせず、
   caller-side でも safely 判定できるように "accumulated mode" のみ返す。ただし
   Protocol 定義 (`ERREModeName | None` で None が "no change") に合わせて、
   `current` と同値なら `None` を返す wrap を最後に 1 回だけ入れる。

## 変更対象

### 新規作成するファイル

- `src/erre_sandbox/erre/__init__.py` — 公開 symbol の re-export
  (`DefaultERREModePolicy`, `ZONE_TO_DEFAULT_ERRE_MODE`, `SHUHARI_TO_MODE`)
- `src/erre_sandbox/erre/fsm.py` — DefaultERREModePolicy (dataclass, frozen)
  + 2 module 定数 + 4 内部 handler 関数
- `tests/test_erre/__init__.py` — 空 (package 宣言)
- `tests/test_erre/test_fsm.py` — unit test (2 groups: per-handler, integration-over-fsm)

### 修正するファイル

- `src/erre_sandbox/bootstrap.py` — `_ZONE_TO_DEFAULT_ERRE_MODE` を削除し、
  `from erre_sandbox.erre import ZONE_TO_DEFAULT_ERRE_MODE` に置換

### 削除するファイル

- なし

## fsm.py のコード構造

```python
"""Event-driven ERRE mode FSM (M5)."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final

from erre_sandbox.schemas import (
    ERREModeName,
    ERREModeShiftEvent,
    InternalEvent,
    Observation,
    ShuhariStage,
    Zone,
    ZoneTransitionEvent,
)

# ---- module-level canonical maps ----

ZONE_TO_DEFAULT_ERRE_MODE: Final[Mapping[Zone, ERREModeName]] = {
    Zone.STUDY: ERREModeName.DEEP_WORK,
    Zone.PERIPATOS: ERREModeName.PERIPATETIC,
    Zone.CHASHITSU: ERREModeName.CHASHITSU,
    Zone.AGORA: ERREModeName.SHALLOW,
    Zone.GARDEN: ERREModeName.PERIPATETIC,
}

SHUHARI_TO_MODE: Final[Mapping[ShuhariStage, ERREModeName]] = {
    ShuhariStage.SHU: ERREModeName.SHU_KATA,
    ShuhariStage.HA: ERREModeName.HA_DEVIATE,
    ShuhariStage.RI: ERREModeName.RI_CREATE,
}

_SHUHARI_PROMOTE_PREFIX: Final = "shuhari_promote:"
_FATIGUE_PREFIX: Final = "fatigue:"


# ---- pure per-observation handlers ----

def _on_zone_transition(
    ev: ZoneTransitionEvent,
    *,
    zone_defaults: Mapping[Zone, ERREModeName],
) -> ERREModeName | None:
    return zone_defaults.get(ev.to_zone)


def _on_internal(ev: InternalEvent) -> ERREModeName | None:
    if ev.content.startswith(_SHUHARI_PROMOTE_PREFIX):
        stage_str = ev.content.removeprefix(_SHUHARI_PROMOTE_PREFIX)
        try:
            stage = ShuhariStage(stage_str)
        except ValueError:
            return None
        return SHUHARI_TO_MODE[stage]
    if ev.content.startswith(_FATIGUE_PREFIX):
        return ERREModeName.CHASHITSU
    return None


def _on_mode_shift(ev: ERREModeShiftEvent) -> ERREModeName | None:
    # external → caller has already updated AgentState.erre, treat as no-op.
    # scheduled/zone/fatigue/reflection → trust the event author
    # (but we still surface the canonical mode for completeness).
    if ev.reason == "external":
        return None
    return ev.current


# ---- concrete policy ----

@dataclass(frozen=True)
class DefaultERREModePolicy:
    """Event-driven ERRE mode FSM.

    Accumulates ``ERREModeName`` over the observation stream in chronological
    order (latest signal wins). Returns ``None`` when the aggregate result
    equals the caller's ``current`` mode.
    """

    zone_defaults: Mapping[Zone, ERREModeName] = field(
        default_factory=lambda: dict(ZONE_TO_DEFAULT_ERRE_MODE),
    )

    def next_mode(
        self,
        *,
        current: ERREModeName,
        zone: Zone,
        observations: Sequence[Observation],
        tick: int,
    ) -> ERREModeName | None:
        accumulated: ERREModeName = current
        for ev in observations:
            match ev:
                case ZoneTransitionEvent():
                    candidate = _on_zone_transition(
                        ev, zone_defaults=self.zone_defaults
                    )
                case InternalEvent():
                    candidate = _on_internal(ev)
                case ERREModeShiftEvent():
                    candidate = _on_mode_shift(ev)
                case _:
                    candidate = None
            if candidate is not None:
                accumulated = candidate
        return None if accumulated == current else accumulated
```

## v1 との違い (明確化)

| 観点 | v1 (退避済) | v2 (本案) |
|---|---|---|
| **優先順位** | external > shuhari > fatigue > zone の固定 4 段 | 時系列 (observation 順)、latest wins |
| **走査方向** | `reversed(observations)` で各 rule 毎に逆スキャン (O(n·rules)) | 順方向 single pass (O(n)) |
| **dispatch** | 各 rule が if-isinstance で分離 | `match/case` で unified dispatch |
| **ZONE map** | module const (直参照) | dataclass field で DI (テスト・flag で差替可能) |
| **handler 実装** | メソッド内インライン | モジュールレベル純関数 (単体テスト可能) |
| **ERREModeShiftEvent(reason="external")** | `current` 返却で no-op | 明示的に `None` 返却、他 reason は ev.current を尊重 |
| **idempotency** | 各 rule 内で current 比較 (重複) | 末尾 1 回 wrap |
| **テスト surface** | FSM の組み合わせ test が主 | handler 単体 + FSM 統合 の 2 層 |

## 影響範囲

- **新パッケージ**: `src/erre_sandbox/erre/` — 層依存は `schemas ← erre ← bootstrap`。
  cognition / world / integration は本 task で触れず、後続 sub-task で逆依存追加
- **bootstrap.py**: 1 line import 置換のみ。boot 時挙動 unchanged
- **downstream sub-task**:
  - `m5-world-zone-triggers` が `DefaultERREModePolicy()` をインスタンス化して tick
    ループで呼ぶ
  - `m5-orchestrator-integration` が feature flag で FSM を on/off (disable 時は
    static map のみ使用)

## 既存パターンとの整合性

- `@dataclass(frozen=True)` はプロジェクト内で既に使われているか: Grep で
  確認する (使用 precedent があればそれに合わせる; なければ初導入として判断を
  decisions.md に記録)
- `match/case` は Python 3.11 の機能で pyproject target `py311`。既存コードに
  match 使用 precedent があるか確認して判断を記録
- test 配置は `tests/test_memory/` / `tests/test_world/` と同パターンの
  `tests/test_erre/`
- `integration/dialog.py::InMemoryDialogScheduler` 同様、schemas の Protocol に
  対する concrete class を layer 内に配置

## テスト戦略

### Unit (per-handler)

`_on_zone_transition` / `_on_internal` / `_on_mode_shift` を直接呼び:

- `_on_zone_transition`:
  - 5 zone × to_zone それぞれで default mode を返すこと (parametrize)
  - zone_defaults に無い zone → `None`
- `_on_internal`:
  - `content="shuhari_promote:shu"` → `SHU_KATA`
  - `content="shuhari_promote:ha"` → `HA_DEVIATE`
  - `content="shuhari_promote:ri"` → `RI_CREATE`
  - `content="shuhari_promote:xyz"` → `None` (ValueError)
  - `content="fatigue: soft"` → `CHASHITSU`
  - `content="fatigue:"` (empty) → `CHASHITSU` (prefix 一致のみ要求)
  - `content="idle"` → `None`
- `_on_mode_shift`:
  - `reason="external"` → `None`
  - `reason="scheduled" / "zone" / "fatigue" / "reflection"` → `ev.current`

### Integration (FSM-level)

- **empty observations** → `None`
- **zone entry only** → default mode (若しくは current と同じなら None)
- **latest wins**: `[zone_entry(peripatos), fatigue]` → `CHASHITSU`
  (fatigue が最後に来たので)
- **latest wins reverse**: `[fatigue, zone_entry(peripatos)]` → `PERIPATETIC`
  (zone_entry が最後)
- **current 同一 → None**: `current=PERIPATETIC` + `[zone_entry(peripatos)]`
- **external override 混在**: `[fatigue, external_shift]` → `None`
  (external は no-op で accumulated は fatigue 由来の CHASHITSU。ただし caller は
  既に state を更新済なので `current` が CHASHITSU と仮定。その場合 `None`)
- **unknown observation types**: `PerceptionEvent` 単独 → `None`
- **DI の確認**: custom `zone_defaults={Zone.STUDY: ERREModeName.SHALLOW}` で
  STUDY 入場 → `SHALLOW`

### 回帰

- 既存 `tests/test_bootstrap*.py` が `ZONE_TO_DEFAULT_ERRE_MODE` の import 置換後
  も PASS (値 unchanged)

## ロールバック計画

- 単一 PR `feature/m5-erre-mode-fsm`
- 問題時は `git revert` で `erre/` パッケージ削除、bootstrap.py 1 行戻して完了
- 本 task 単独では FSM は呼ばれないので merge 時点では dead code (安全)

## 設計判断の履歴

- 初回案 (`design-v1.md`) と再生成案 (v2) を `design-comparison.md` で比較
- **採用: v2 (再生成案)**
- 根拠:
  1. Protocol 署名 `Sequence[Observation]` と最も整合 (chronological を活用)
  2. handler 単体 test の価値 (InternalEvent content prefix の多バリエーション)
  3. `m5-orchestrator-integration` の feature flag 拡張で DI が活きる
  4. latest-signal-wins が caller (world/tick.py) の observation 発行順と素直に
     対応する
  5. `ERREModeShiftEvent` の `reason` 4 種全てに挙動が明示される
  6. `match/case` / `@dataclass(frozen=True)` は py3.11 target で正規に使える
