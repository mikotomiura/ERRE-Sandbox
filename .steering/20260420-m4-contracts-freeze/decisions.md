# Decisions — m4-contracts-freeze

本ドキュメントは `m4-contracts-freeze` タスク内で行った設計判断を記録する。
上位の planning 判断は `.steering/20260420-m4-planning/decisions.md` を参照。

---

## D1. `/reimagine` 非適用

### 判断
本タスクでは `/reimagine` を適用しない。

### 理由
- 設計分岐は `/20260420-m4-planning/` ですでに `/reimagine` 済み (v2 + hybrid 採用)
- 本タスクはその採用案を mechanically 具体化する実装タスクで、D3 (foundation
  小型化) の粒度も確定済み。複数案が考えられる領域は残っていない
- 破壊する対象 (初回案) が存在しないため、`/reimagine` を形式的に適用しても
  意味のある比較にならない

### 履歴
- `requirement.md` の「運用メモ」に適用判断 (No) を記載
- 実装中に当初想定外の設計選択肢が出た場合のみ、その時点で再考する方針

---

## D2. `SCHEMA_VERSION` bump の粒度: minor bump (`0.1.0-m2` → `0.2.0-m4`)

### 判断
- **minor** bump (0.1 → 0.2) を選択
- 末尾の `-m2` / `-m4` で milestone を明示的にラベリング

### 理由
- `AgentSpec` / `ReflectionEvent` / `SemanticMemoryRecord` は **追加のみ**
  (additive) であり、既存 `ControlEnvelope` 既存 variant のフィールドは
  変更していない → 厳密な semver では patch でも通る
- しかし M4 foundation の節目を明示し、fixture の大量刷新を伴うため
  minor bump を選択 (planning D4 で既決)
- M3 は MASTER-PLAN で意図的に skip されているため、`-m2` → `-m3` ではなく
  `-m2` → `-m4` とする (milestone labeling の semantic clarity)

### 代替案
- patch bump (0.1.1-m2 等) → milestone label の不整合を招くため不採用
- major bump (1.0.0) → 未だ MVP 段階であり時期尚早

---

## D3. `BootConfig.agents` を Pydantic ではなく `tuple[AgentSpec, ...]` にした

### 判断
`BootConfig` は既存 `@dataclass(frozen=True)` を維持し、`agents: tuple[AgentSpec, ...] = ()`
を field 追加 (Pydantic BaseModel に移行しない)。

### 理由
- `BootConfig` は CLI 引数から argparse で組み立てる in-process config であり、
  wire contract ではない → Pydantic にする必要なし
- 既存 `BootConfig` (`host`, `port`, `db_path` 等) はすべて dataclass 前提。
  これを BaseModel に変更すると `__main__.cli` と `test_bootstrap.py`
  の全テストが影響を受ける
- `AgentSpec` 自体は Pydantic BaseModel として `schemas.py` に凍結した
  (YAML / JSON から validation したい場面は存在する)
- planning design.md でも「既存 struct 拡張、別 API (`register_agents`) は作らない」
  と明記 (D3 / MASTER-PLAN §5.1)

### 代替案
- `BootConfig` を Pydantic 化 → 副作用大きすぎる。別タスクでやるなら `m4-multi-agent-orchestrator`
- `agents: list[AgentSpec]` (list) → frozen dataclass 上で mutable default を持つ
  と `default_factory` が必要かつ意味的には immutable が望ましい。tuple を採用

---

## D4. `DialogScheduler` を `typing.Protocol` (interface only) で凍結する

### 判断
- `DialogScheduler` は `typing.Protocol` のメソッドシグネチャのみを凍結
- `@runtime_checkable` は付けない
- 具象実装は `m4-multi-agent-orchestrator` で行う

### 理由
- turn-taking policy (cooldown、backpressure、同時対話禁止) は認知モデル依存で
  planning 段階では確定できない
- しかし `cognition` / `world` が型ヒントで依存するために interface は
  先に必要 (並列タスク間の型整合)
- `@runtime_checkable` は `isinstance` チェックを許すが、属性しか見ないため
  安全性が弱く、duck typing との混同リスクがある。必要になった段階で
  `m4-multi-agent-orchestrator` で付ける

### 代替案
- 抽象基底クラス (ABC) → Protocol の方が構造的 subtyping を許し、
  テストダブル (Mock) を書きやすい
- concrete class のスケルトン + `NotImplementedError` → 意図が「interface only」
  であることが型シグネチャから読み取りにくい

---

## D5. Fixture 配置: 既存 `fixtures/control_envelope/` に merge、新規 `tests/fixtures/m4/` 併存

### 判断
- ControlEnvelope variant (dialog_initiate / turn / close) の fixture は
  既存 `fixtures/control_envelope/` に追加 (7 → 10 ファイル)
- ControlEnvelope に属さない M4 primitive (AgentSpec 集合 / ReflectionEvent /
  SemanticMemoryRecord) は新規 `tests/fixtures/m4/` に置く

### 理由
- `test_envelope_fixtures.py::test_all_expected_kinds_have_fixture` は
  `ControlEnvelope` union の kind と `fixtures/control_envelope/*.json` の
  set equality を要求する。dialog_* variant を union に追加したら fixture も
  同じディレクトリにないと red になる
- planning design.md の「tests/fixtures/m4/」はこの制約を見逃していた
  記述。実装時に調整するのは適切 (D3「凍結しないもの = fixture 配置の詳細」
  の範疇)
- 一方、`BootConfig.agents` の 3-agent 例や `ReflectionEvent` サンプルは
  envelope ではないため既存ディレクトリには置けない → 新設 `tests/fixtures/m4/`

### 既存 fixture の `schema_version` bump
- 7 ファイル全てを `0.1.0-m2` → `0.2.0-m4` に更新
- `test_fixture_schema_version_matches` が強制するため、bump を忘れると
  即 red になる設計

---

## D6. `test_envelope_kind_sync.py` の定数化

### 判断
`test_python_side_has_seven_kinds` (ハードコード `7`) を
`test_python_side_covers_expected_kinds` に置き換え、
`_EXPECTED_KINDS` という frozenset で期待 kinds を明示 pin する。

### 理由
- 個数ベースの assertion は M5/M6 で kind 追加されるたびに数字を書き換える
  必要があり、変更漏れのリスクが高い
- set equality なら期待値と実態の差分 (diff) がエラーメッセージで明示される
- `_EXPECTED_KINDS` にコメントで M2 / M4 の区別を残したので、将来の
  bump 時にも意図が読み取れる

---

## D7. `personas/kant.yaml` の `schema_version` も bump する

### 判断
`personas/kant.yaml` 内の `schema_version: "0.1.0-m2"` を `"0.2.0-m4"` に更新。

### 理由
- `test_personas.py::test_kant_yaml_loads_into_persona_spec` が
  `kant.schema_version == SCHEMA_VERSION` を assertion している。
  YAML 側の値がハードコードのままだと red になる
- PersonaSpec 自体の shape は変更していないが、schema_version の一貫性
  維持のため YAML 側も同期
- `m4-personas-nietzsche-rikyu-yaml` タスクでも同じ値を書くことになる
  (テンプレート整合)

---

## D8. `fixtures/control_envelope/handshake.json` の capabilities を拡張

### 判断
`handshake.json` の `capabilities` 配列に `dialog_initiate`, `dialog_turn`,
`dialog_close` を追加 (7 → 10 要素)。

### 理由
- handshake fixture はクライアントがサーバに対して「自分が扱える envelope kind」
  を申告する用途。kind が 10 種に増えたら capabilities もそれを反映すべき
- 現時点で capabilities の enforcement (サーバ側がクライアントの capabilities
  をチェックして不足時に拒否するロジック) は未実装だが、fixture 値として
  真実を書いておく方が将来整合性が保たれる

---

## 参照

- `requirement.md` (本タスクの前提と受け入れ条件)
- `design.md` (採用アプローチ)
- `.steering/20260420-m4-planning/design.md` (M4 全体の採用案 v2 + hybrid)
- `.steering/20260420-m4-planning/decisions.md` D3 (foundation 小型化の粒度)
- `.steering/20260418-schemas-freeze/decisions.md` (M2 同等タスクの先例)
