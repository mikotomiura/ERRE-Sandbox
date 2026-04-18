# T05 schemas-freeze — 設計案比較

## v1（初回案）の要旨

CSDG `csdg/schemas.py` の 3 階層 (HumanCondition / CharacterState / DailyEvent)
を平行移植し、`AgentState` は Biography / Traits / Physical / Emotion / ERREMode /
Relationships / Goals の 6-7 サブモデルを並列に持つ。`ControlEnvelope` は
`kind: Literal + payload: dict[str, object]` の汎用エンベロープ。
`Observation` は単一 BaseModel で `description: str + emotional_impact: float`。
`MemoryEntry` に `embedding: list[float] | None` を含める。

## v2（再生成案）の要旨

schemas.py を「2 台の OS が信じ合うためのワイヤー境界」と定義し直す。
(a) **静的ペルソナ (PersonaSpec) と動的状態 (AgentState) を完全分離**、
(b) **Observation と ControlEnvelope を Pydantic discriminated union** にして
弱型 `payload: dict` を排除、(c) **SCHEMA_VERSION を protocol レベル**で持ち、
`HandshakeMsg` で G-GEAR/MacBook/Godot 間のバージョン差分を早期検知、
(d) **MemoryEntry から embedding を除外** して実装詳細の漏洩を防ぐ。

## 主要な差異

| 観点 | v1 | v2 |
|---|---|---|
| 核となる設計思想 | 「CSDG の構造を Pydantic v2 化する」翻訳的 | 「2 機の間のワイヤー契約」protocol-first |
| AgentState の構造 | 6-7 サブモデル並列 (Biography/Traits/Physical/Emotion/ERREMode/Relationships/Goals) | Physical + Cognitive + ERREMode + RelationshipBond の 4 サブモデル。Traits は PersonaSpec に移動 |
| 静的/動的の分離 | 曖昧 (Traits と Physical が同列) | 明示的 (PersonaSpec=静的、AgentState=動的、橋渡しは persona_id のみ) |
| Observation の型 | 単一 BaseModel + `description: str` 汎用 | 5 種の discriminated union (PerceptionEvent / SpeechEvent / ZoneTransitionEvent / ERREModeShiftEvent / InternalEvent) |
| ControlEnvelope の型 | `kind: Literal + payload: dict[str, object]` 汎用 | 7 種の discriminated union (Handshake/AgentUpdate/Speech/Move/Animation/WorldTick/Error) 各 kind が typed フィールド |
| バージョニング | なし | `SCHEMA_VERSION: Final[str]` + `HandshakeMsg` でネゴシエーション |
| MemoryEntry | embedding を含む (`list[float] \| None`) | embedding を除外 (T10 の store で内部型 StoredMemory を作る前提) |
| mood_baseline と valence | Physical.mood_baseline と Emotion.valence が並立、意味境界曖昧 | 時間スケールで明示分離 (Physical=日単位基調 / Cognitive=tick 即時) |
| ShuhariStage | Traits (静的) に配置 | Cognitive (動的) に配置 — 学習で変わる概念として整理 |
| 変更規模 (schemas.py) | ~200 行 | ~300-400 行 |
| 型安全性 (mypy strict) | `payload: dict[str, object]` が弱い | 全経路が型付き。TypeAdapter で JSON decode も型安全 |
| Godot 側の扱いやすさ | JSON Schema 出力しても payload 中身不明 | kind ごとに専用フィールドで GDScript 側も typed 受信可能 |
| テスト戦略 | smoke 3 種 (インスタンス化・extra=forbid・enum dump) | smoke 6 種 (上記 + discriminated union の decode 成功/失敗 + SCHEMA_VERSION) |
| 後続タスクへのインパクト | T11/T12 が `payload` の中身を別途規約化する必要 | T11/T12 は union メンバを使うだけで typed |
| リスク | ControlEnvelope が弱型のまま T07 で fixture を作ると後戻りコストが大 | discriminated union が Pydantic v2 の遅延評価 + TypeAdapter と相性が悪い場面あり (decisions.md で対処方針を明記) |

## 評価（各案の長所・短所）

### v1 の長所
- CSDG との 1-1 対応が維持され、参照コードを追いやすい
- 実装量が少ない (モデル数が少ない)
- 汎用 `payload: dict` で新しいメッセージ種を足す際に schema 変更なしで追加可能

### v1 の短所
- **Contract としては弱い**: `payload: dict[str, object]` は wire の型を表現しない
- 静的/動的が混在しており、永続化戦略 (毎 tick スナップショット) がいたずらに重くなる
- Observation の `event_type: Literal[…]` が分かれているのに `description: str` が汎用なので、分岐ロジックが結局文字列マッチに戻る
- MemoryEntry.embedding が schema に居座るため、将来 Qdrant に差し替える時 (architecture.md §8 拡張ポイント) に contract 破壊になる

### v2 の長所
- **Contract-First の核心要件を満たす**: 「両機が独立実装して致命的手戻りが出る」リスク W2 への正面対応
- Pydantic discriminated union により **JSON Schema から GDScript クラスを生成可能**
- 静的/動的の境界が明示され、ペルソナ YAML 書き換え時に AgentState 履歴と干渉しない
- SCHEMA_VERSION + Handshake で将来の仕様ドリフトが観測可能になる
- MemoryEntry の schema 純度が高く、store バックエンド差し替えに強い

### v2 の短所
- 実装量が 1.5-2 倍 (union メンバが 12 モデル増える)
- Pydantic v2 の `Annotated[Union[...], Field(discriminator=...)]` は version-sensitive で、
  稀に `mypy + __future__.annotations` で型解決が壊れる (decisions.md で対処明記予定)
- 新しいメッセージ種を足す時、union 定義 + `Literal[...]` の 2 箇所の編集が必要
- `SamplingBase` 型を `default_sampling` (絶対値) と `sampling_overrides` (差分) の両方で
  使うため、セマンティクスの混在を Field description と T11 テストで担保する必要

## 推奨案

**v2 を採用** — 理由:

1. **Contract-First の本質的要求**: 本タスクの `requirement.md` §背景は
   「`ControlEnvelope` と `AgentState` の仕様を固めないまま両機が独立実装すると
   末期に致命的な手戻り」と明記。v1 の `payload: dict[str, object]` は
   この要求に対して **契約として未完成**。discriminated union でしか
   「仕様が固まった」と言えない。

2. **後続 T07 fixture との整合**: T07 で Godot 側が読む JSON fixture を作る際、
   v1 の `payload: dict` では fixture ファイルが "例示" に留まり、形式的契約にならない。
   v2 なら JSON Schema 出力 → GDScript 型生成が現実的に可能。

3. **MemoryEntry の実装漏洩排除**: 後続 T10 で memory 層を Qdrant 等に差し替える
   可能性が architecture.md §8 に記載。embedding を schema に持つと contract 破壊になる。
   v2 で予防的に除外する方が将来の柔軟性が高い。

4. **静的/動的分離の価値**: ペルソナ YAML の書き換えで AgentState 互換が
   壊れないという不変条件は、長期実験 (12 時間ラン) のリプレイ可能性を保証する上で重要。

5. **v2 の短所は対処可能**: Pydantic の union 型解決の問題は `TypeAdapter` 使用で
   回避でき、decisions.md で明記すれば後続タスクで迷わない。
   実装量の増加は 1 回のコストで、以降の T06-T14 の全てで "契約が固い" 恩恵を受ける。

**ハイブリッド不採用の理由**: v1 の "汎用 payload" を一部残す設計 (ハイブリッド) は
v2 の "契約の固さ" という長所を薄める。discriminated union は全てか無かで、
部分採用すると中途半端になる。
