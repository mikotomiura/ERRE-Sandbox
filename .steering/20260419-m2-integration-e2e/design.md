# 設計 (v2 再生成案)

## 実装アプローチ

**「機械可読契約 + 人間向けナラティブ」の二層構造** — 契約の single source of truth を
Python モジュール `src/erre_sandbox/integration/` に置き、Markdown は背景・rational・
運用ナラティブに特化させる。

### 核となる着想

T05 `schemas-freeze` が `src/erre_sandbox/schemas.py` で Observation / ControlEnvelope /
AgentState を Pydantic v2 で凍結したのと**同じパターン**を integration 層でも適用する。
つまり、WS メッセージ型・シナリオ・メトリクス閾値を Python の型付き定数として配置し、
`from erre_sandbox.integration import WsTick, SCENARIO_WALKING, Thresholds` で
T14 実装者・試験コードの双方が **import して消費** できるようにする。

これにより:
1. **契約違反を mypy/pytest で機械検出** できる
2. T14 実装者が Markdown を読んで型を書き起こす作業がゼロになる
3. 契約スナップショット試験を今日から CI ガードに載せられる (T14 完成を待たない)
4. Markdown は「なぜこの設計か」に専念でき、型定義との二重メンテから解放される

## 変更対象

### 新規作成するファイル

**機械可読契約モジュール** (`src/erre_sandbox/integration/`):
```
src/erre_sandbox/integration/
├── __init__.py        — 公開 API (Scenario, IntegrationContract, Thresholds)
├── contract.py        — Pydantic v2: WsHandshake / WsTick / WsAck / WsError /
│                        SessionClose / MessageEnvelope (discriminated union)
├── scenarios.py       — 型付きシナリオ: Scenario dataclass、
│                        SCENARIO_WALKING / SCENARIO_MEMORY_WRITE /
│                        SCENARIO_TICK_ROBUSTNESS (frozen tuples)
├── metrics.py         — Thresholds Pydantic model (frozen):
│                        LATENCY_P50_MS_MAX=100 / P95=250 / TICK_JITTER_SIGMA_MAX=0.20 /
│                        MEMORY_WRITE_SUCCESS_RATE_MIN=0.98 / AROUSAL_RANGE=(0.0, 1.0)
└── acceptance.py      — T20 チェックリスト項目を type-safe Python list で列挙
                         (pytest-parametrize で将来展開可能な構造)
```

**試験 skeleton** (`tests/test_integration/`):
```
tests/test_integration/
├── __init__.py
├── conftest.py
├── test_contract_snapshot.py        — (常時 ON)
│                                      Pydantic model の json_schema() を固定し、
│                                      契約変更を早期検出。**skip しない。**
├── test_scenario_walking.py         — (@pytest.mark.skip) S1/S2
├── test_scenario_memory_write.py    — (@pytest.mark.skip) S3
└── test_scenario_tick_robustness.py — (@pytest.mark.skip) S4/S5
```

**人間向けナラティブ** (`.steering/20260419-m2-integration-e2e/`):
```
.steering/20260419-m2-integration-e2e/
├── requirement.md               (既存)
├── design.md                    (this)
├── design-v1.md                 (退避済)
├── design-comparison.md         (reimagine で生成)
├── tasklist.md
├── decisions.md
├── scenarios.md                 — 3-5 シナリオの日本語ナラティブ時系列記述
│                                  (型定義は scenarios.py、Markdown はユースケース説明)
├── integration-contract.md      — WS 契約の rational・エラー応答方針・セッション設計
│                                  (型定義は contract.py、Markdown は why)
├── metrics.md                   — 閾値の根拠・測定方法・調整記録
│                                  (数値定数は metrics.py、Markdown は背景)
└── t20-acceptance-checklist.md  — 運用 runbook (Python リストと対応)
```

### 修正するファイル
- `.steering/20260418-implementation-plan/tasklist.md`
  — T19 行に「設計フェーズ完了」マークと PR 番号を併記
- `src/erre_sandbox/__init__.py` (必要なら integration を含む export へ)

### 削除するファイル
- なし

## 影響範囲

| 領域 | 影響 | 対処 |
|---|---|---|
| `src/erre_sandbox/integration/` | 新規モジュール | architecture-rules Skill を参照、依存方向を schemas.py → integration → なし (下位レイヤー) で設計 |
| `src/erre_sandbox/schemas.py` | 変更なし (import のみ) | integration/contract.py から `Observation`, `ControlEnvelope` を import |
| `tests/test_integration/` | 新規 | `test_contract_snapshot.py` のみ常時 ON、他は skip |
| CI (`.github/workflows/ci.yml`) | 自動収集で追加 | `test_contract_snapshot.py` が通過すれば緑 |
| Godot 側 | なし | — |
| `.steering/` | 本タスクディレクトリ + MASTER-PLAN tasklist | 本タスクで完結 |
| docs/ | なし | — |

## 既存パターンとの整合性

- **Pydantic v2 での型凍結**: `src/erre_sandbox/schemas.py` (T05) と同じ流儀で `integration/contract.py` を書く
- **モジュール分割**: `src/erre_sandbox/cognition/` `memory/` `world/` `inference/` と同階層に `integration/` を配置
- **test ディレクトリ命名**: `tests/test_cognition/` `test_memory/` 等と同様に `tests/test_integration/`
- **frozen 定数**: CSDG の「3 層 Critic 重み `0.40/0.35/0.25`」のような明示数値化思想を継承
- **docstring**: llm-inference / cognition モジュール内の rST docstring 規約を踏襲 (一行目要約 + `Attributes:` / `Examples:`)
- **architecture-rules**: integration/ は **schemas.py に依存するが、cognition/memory/world/inference には依存しない** (テスト側は全層 import 可)

## テスト戦略

| テスト | 稼働 | 内容 |
|---|---|---|
| `test_contract_snapshot.py` | **常時 ON** | `WsTick.model_json_schema()` 等の dict 表現を固定 JSON と照合。契約ドリフト検出 |
| `test_scenario_walking.py` | skip | S1 Kant 起動 → Peripatos 入室、S2 Shallow → Peripatetic 遷移 |
| `test_scenario_memory_write.py` | skip | S3 記憶書込み 4 件 + semantic 1 件 |
| `test_scenario_tick_robustness.py` | skip | S4/S5 tick 抜け検知 + disconnect/reconnect |
| 型検査 (mypy) | 常時 ON | integration モジュールが strict mypy 通過 |
| `pytest --collect-only` | 常時 ON | skeleton 件数が 3 件以上収集される (設計の下限保証) |

### skeleton の skip 方針

```python
import pytest

pytestmark = pytest.mark.skip(reason="T19 実行フェーズ待ち (T14 完成後に点灯)")
```

ファイル全体 skip で `pytestmark` を使い、実行時に `-k` で個別選択も可能にする。

## ロールバック計画

本タスクは「新規モジュール追加 + skeleton テスト追加 + 設計ドキュメント追加」のみ。

```bash
git checkout main
git branch -D feature/m2-integration-e2e
rm -rf src/erre_sandbox/integration/ tests/test_integration/ \
       .steering/20260419-m2-integration-e2e/
```

MASTER-PLAN 直下 tasklist.md の T19 マーク更新は**別コミット**に分け、部分ロールバックを可能にする。

## リスク

| リスク | 影響 | 緩和策 |
|---|---|---|
| 契約が T14 実装時に不足 | T14 実装者が `integration/contract.py` を修正したくなる | `integration-contract.md` に「未決事項」セクションを設け明示、スナップショット試験は初回 T14 実装時のみ更新可とする運用ルールを decisions.md に明記 |
| メトリクス閾値が厳しすぎる | T19 実行時に赤 | `metrics.py` の値は保守的に、調整は decisions.md に履歴化 |
| skeleton テストの陳腐化 | T14 完成時に API ズレ | test_contract_snapshot.py が CI ガード、ズレれば即検出 |
| Godot ヘッドレス実行の複雑さ | E2E が不安定 | skeleton では WS client stub のみ、Godot 実機は T19 実行フェーズで扱う |
| 過設計リスク | `integration/` モジュールが T14 実装時に形を変えすぎる | **最小限** の型のみ定義。詳細 (内部 state machine 等) は T14 実装時に追加する前提で decisions.md に記録 |
| architecture-rules 違反 | integration/ の依存方向が不明瞭 | 設計時に architecture-rules Skill を起動し、依存方向を明記 |

## 設計判断の履歴

- **初回案 (`design-v1.md`) と再生成案 (v2) を比較** → 比較表は `design-comparison.md` 参照
- **採用: v2** (2026-04-19)
- **根拠**:
  1. T05 schemas-freeze (Pydantic で Observation / ControlEnvelope / AgentState を凍結) との
     一貫性が決定的。integration 層だけ Markdown 契約にする非対称は長期的な保守を混乱させる。
  2. 契約ドリフトを `test_contract_snapshot.py` が CI で自動検出 (常時 ON)。
     T14 完成までの数週間〜数ヶ月で schemas.py が変わるリスクに対して今日からガードが効く。
  3. T14 実装者 (将来の G-GEAR セッション) が `from erre_sandbox.integration import WsTick`
     で即着手できる価値が大きい。PR 差分が v1 の約 1.5 倍になる点を上回る。
  4. 過設計リスクは「最小限の型のみ先行定義、詳細は T14 実装時に追加」の原則を
     `decisions.md` に明記することで緩和可能。
- **v1 から取り込んだ要素**:
  Markdown 4 枚 (`scenarios.md` / `integration-contract.md` / `metrics.md` /
  `t20-acceptance-checklist.md`) は v1 の構成を踏襲し、責務を
  「人間向け rational / ナラティブ」に限定してハイブリッド採用。
