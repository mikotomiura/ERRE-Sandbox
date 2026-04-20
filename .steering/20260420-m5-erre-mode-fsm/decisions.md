# Decisions — m5-erre-mode-fsm

本タスク (ERRE mode 遷移 FSM の concrete 実装) で下したユーザー決定および非自明な
設計判断の記録。

## 判断 1: /reimagine で v2 (latest-signal-wins) を採用

- **判断日時**: 2026-04-20
- **背景**: FSM の遷移モデルには複数案がある。v1 は priority-ordered backwards scan、
  v2 は chronological single-pass accumulation (latest wins)。
- **選択肢**:
  - A (v1): priority list 方式。各 rule が `reversed(observations)` を走査し最初に
    マッチしたものを採用。`external > shuhari > fatigue > zone > hold`
  - B (v2): chronological reduction 方式。`observations` を順方向に 1 度だけ走査、
    match で dispatch、最新の非 None 候補を採用 ← **採用**
- **理由**:
  1. Protocol 署名 `Sequence[Observation]` が chronological を自然に示唆
  2. handler が pure 関数で単体 test しやすく (parametrize が効く)
  3. `zone_defaults` を dataclass field で DI 可能、downstream の feature flag 拡張に優しい
  4. latest-wins が "fatigue を感じた後 peripatos に入る → peripatetic" という
     直感的挙動に合致 (v1 は fatigue が常に勝つ固定 semantics)
  5. `ERREModeShiftEvent.reason` の 4 literal 全てを明示的にハンドリングできる
  6. `match/case` は py3.11 target で正規に使える (既存 precedent はないが、
     discriminated union との親和性が高い)
- **トレードオフ**: コード行数が v1 の 2 倍弱 (60-70 行 → 110-130 行)、
  `match/case` と `@dataclass(frozen=True)` の新 precedent を要確認
  (後者は repo 内 7 ファイルで使用済みを確認、前者は本 task が最初)
- **影響範囲**: `src/erre_sandbox/erre/fsm.py` の構造、test 二層化 (handler 単体 +
  policy 統合)、後続 `m5-world-zone-triggers` での使い方
- **見直しタイミング**: `m5-world-zone-triggers` で observation 順序が tick 間に
  broken した場合、caller-side の contract として明示する (FSM を変えるのではなく
  world tick 側に順序保証を課す)

## 判断 2: `erre/__init__.py` の placeholder docstring を上書き

- **判断日時**: 2026-04-20
- **背景**: 既存 `src/erre_sandbox/erre/__init__.py` は
  `"""ERRE pipeline DSL (Extract / Reverify / Reimplement / Express)."""` という
  別概念 (ドキュメントレベルの ERRE フレームワーク) の placeholder だった。
  本タスクは同 package に **runtime の ERRE cognitive mode FSM** を置く。
- **選択肢**:
  - A: 同名 `erre/` package に FSM を追加し、docstring で「2 つの ERRE 概念の曖昧さ」
    を明示。pipeline DSL が将来実装される際は `erre_pipeline/` など別 package へ ← **採用**
  - B: `erre_mode/` or `mode_fsm/` など別名で package 作成
  - C: `cognition/erre_fsm.py` に置く (package を作らない)
- **理由**: (1) `m5-planning` design.md が既に `erre/` package を前提に
  サブタスク群を設計済、(2) `architecture-rules` Skill でも `erre/` が layer
  として挙げられている、(3) pipeline DSL は未実装で当面リバイバル予定なし、
  (4) 将来必要になった時に別 package に分けるのは低コスト
- **トレードオフ**: "ERRE" という略語が 2 意味持つので docstring / 用語集で
  明示する必要あり (`__init__.py` docstring に明記済)
- **影響範囲**: `src/erre_sandbox/erre/__init__.py` docstring の刷新のみ

## 判断 3: `match/case` を本 repo の最初の precedent として導入

- **判断日時**: 2026-04-20
- **背景**: `fsm.py::DefaultERREModePolicy.next_mode` で Observation
  discriminated union の dispatch に `match/case` を採用。repo 全体を grep しても
  `match/case` の使用例は 0 件。
- **選択肢**:
  - A: `match/case` を初導入 ← **採用**
  - B: `isinstance` chain の if-elif
- **理由**: (1) pyproject target が py3.11 で `match/case` は正規、(2) Pydantic
  discriminated union との親和性が高い、(3) v2 設計の "dispatch by type" 意図が
  match で読みやすい、(4) 将来 Observation 種別が増えた時の変更が 1 行追加で済む
- **トレードオフ**: 新しい syntax を precedent として確立するリスク (ただし py3.11
  は既に 3 年前のリリース (2022-10) で成熟)
- **影響範囲**: 本 task のみ。将来、他の discriminated union (ControlEnvelope など)
  で match を使う人への道を開く

## 判断 4: `world/ → erre/` layer 依存は本 task では追加しない (次タスクで決定)

- **判断日時**: 2026-04-20
- **背景**: impact-analyzer 指摘 (HIGH): `m5-world-zone-triggers` で
  `world/tick.py` が `erre.DefaultERREModePolicy` を呼ぶ設計にすると、
  architecture-rules の依存テーブルに `world/ → erre/` が明示されていない。
  (現在 `world/` の依存先は `cognition/`, `schemas.py` のみ)
- **選択肢**:
  - A: 本 task で architecture-rules SKILL.md を更新して `world/ → erre/` を許可
  - B: 本 task では `bootstrap/ → erre/` のみに留め、`world/ → erre/` の可否は
    `m5-world-zone-triggers` 着手時に判断 ← **採用**
  - C: FSM 呼び出しを `cognition/` 層に委譲 (cognition → erre は現状 allowed でない)
- **理由**: architecture-rules の変更は meta-level の決定で、他の layer 関係にも
  影響し得る。本 task のスコープ (concrete FSM の単体実装) から逸脱する。
  `m5-world-zone-triggers` 着手時に設計として再考し、user 確認を経て更新する方が
  筋が良い。本 task の import は `bootstrap → erre → schemas` のみで既存ルール適合
- **トレードオフ**: 次 task 開始時に layer 判断が追加されて若干遅れる (0.5 日内)
- **影響範囲**: 本 task のコード変更なし。`.steering/20260420-m5-world-zone-triggers/`
  の requirement で layer 判断を先にする
- **見直しタイミング**: `m5-world-zone-triggers` 着手時、どの layer で FSM を呼ぶか
  (world / cognition / 新 layer) を決定

## 判断 5: code-reviewer MEDIUM/LOW を反映

- **判断日時**: 2026-04-20
- **対応**:
  - MEDIUM 1 ("external" 生文字列) → `_REASON_EXTERNAL: Final = "external"` を
    module 定数化 (判断根拠: 下流 emitter が同定数を import できる)
  - MEDIUM 2 (match と inheritance) → `DefaultERREModePolicy` docstring に
    "Observation union は flat を維持せよ" の invariant を追記
  - LOW (test の type: ignore) → inline コメントで narrowing 意図を明記
  - LOW (default_factory の copy) → 現状維持 (reviewer も defensible と評価)
  - LOW (content prefix の brittleness) → 現時点で registry pattern は過剰、
    将来 `InternalEvent.content` に JSON 等が乗るようになれば再検討
