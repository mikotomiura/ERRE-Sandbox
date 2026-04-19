# 設計案比較 (v1 vs v2)

## v1 (初回案) の要旨

**「Contract 文書を積み上げる」Markdown 中心アプローチ**。
設計成果物を `.steering/20260419-m2-integration-e2e/` 内に 5 種の独立 Markdown
(`scenarios.md` / `integration-contract.md` / `metrics.md` / `t20-acceptance-checklist.md` /
`design.md`) として並列配置し、型情報は Markdown にのみ記述する。
`tests/test_integration/` に skeleton テストを配置し全件 `@pytest.mark.skip` で一時停止。
T14 実装者は Markdown を読んで Python 側の型を書き起こす。

## v2 (再生成案) の要旨

**「機械可読契約 + 人間向けナラティブ」の二層構造**。
契約の single source of truth を Python モジュール `src/erre_sandbox/integration/`
(contract.py / scenarios.py / metrics.py / acceptance.py) に配置し、
Markdown は background / rational / operator 向けナラティブに特化。
`test_contract_snapshot.py` を **skip せず常時 ON** にし、
Pydantic model の json_schema 固定で契約ドリフトを早期検出。
T14 実装者は `from erre_sandbox.integration import WsTick, Thresholds` で即消費。

## 主要な差異

| 観点 | v1 | v2 |
|---|---|---|
| 契約の Single Source of Truth | Markdown (`integration-contract.md`) | Python (`src/erre_sandbox/integration/contract.py`) |
| T14 実装者の消費方法 | Markdown を読んで型を書き起こす | `import` して使う |
| 契約変更検出 | 人の目レビュー | `test_contract_snapshot.py` が CI 上で機械検出 (常時 ON) |
| メトリクス値の場所 | `metrics.md` (Markdown テキスト) | `metrics.py` (frozen Pydantic model) + `metrics.md` (rational) |
| シナリオ定義 | `scenarios.md` (日本語ナラティブ) | `scenarios.py` (Scenario dataclass) + `scenarios.md` (ユースケース説明) |
| 新規モジュール追加 | なし (Markdown のみ) | `src/erre_sandbox/integration/` (5 Python ファイル) |
| Markdown 数 | 5 枚 (active) | 4 枚 (rational 中心) |
| Python ファイル増 | 約 5 個 (tests のみ) | 約 10 個 (src 5 + tests 5) |
| mypy/ruff の対象拡大 | 最小 | `integration/` が strict mypy 対象に追加 |
| CI 上の稼働試験 | 0 件 (全 skip) | 1 件 (contract_snapshot は skip しない) |
| 運用時の契約ドリフト耐性 | レビュー依存 | CI ガードで機械的に検出 |
| Markdown ↔ Python 二重管理 | 発生 (v1 は Markdown に型、Python に skeleton) | 最小化 (型は Python のみ、Markdown は rational のみ) |
| T14 実装時の柔軟性 | 高 (Python 側未定義なので自由) | やや低 (事前定義済み型を破らないよう慎重になる) |
| 過設計リスク | 低 | 中 (T14 未実装時に型を先行定義) |
| Contract-First 思想との整合 | 間接的 (Markdown 契約) | 直接 (型が契約そのもの) |
| T05 schemas-freeze との一貫性 | パターンが異なる (Python vs Markdown) | パターンが一致 (両方 Pydantic で凍結) |

## 評価

### v1 の長所
- **軽量**: Python モジュール追加なし、PR 差分が Markdown 中心で小さい
- **柔軟性**: T14 実装者が契約を自由に設計でき、事前型定義の制約なし
- **シンプル**: Markdown だけ読めば全貌が把握でき、新規参加者に優しい
- **過設計リスク回避**: 未実装の T14 に対して過剰な型を先行決定しない

### v1 の短所
- **契約ドリフト検出が人力**: Markdown とコードの乖離は CI で検出できない
- **二重管理**: T19 実行フェーズで Python 側に型を書き起こす時、Markdown と不一致のリスク
- **T14 実装者の負荷**: Markdown → 型変換を手作業で行う必要
- **T05 との非対称**: schemas.py は Pydantic で凍結されているのに、integration は Markdown のみという非対称性

### v2 の長所
- **機械検証可能**: mypy + pytest で契約違反を早期検出
- **Single source of truth**: 型は Python のみ、Markdown は rational のみという明確な責務分担
- **T14 実装者の負荷軽減**: `import` して使える
- **CI ガードが今日から稼働**: `test_contract_snapshot.py` が常時 ON
- **T05 schemas-freeze と一貫**: 既存プロジェクトの型凍結パターンを継承
- **Contract-First 思想に直結**: 型が契約そのもの

### v2 の短所
- **PR 差分が大きい**: Python モジュール 5 + test 5 + Markdown 4 = 約 14 ファイル
- **過設計リスク**: T14 未実装時に型を先行定義するため、実装時に変えたくなる可能性
- **T14 実装者の柔軟性がやや低下**: 事前型を破らないよう慎重になる
- **architecture-rules の確認要**: integration/ の依存方向を明確化する必要

## 推奨案

### **v2 を推奨 (部分的 v1 の要素を取り込む)**

**根拠**:

1. **T05 schemas-freeze との一貫性が決定的**
   プロジェクトは既に「契約は Pydantic で凍結する」という思想で動いている (T05/T07/T10)。
   integration 層だけ Markdown 契約にする非対称は、長期的な保守を混乱させる。
   reimagine の本質は「前提を疑う」ことだが、**プロジェクトの既存パターンとの整合性**
   は疑うべきでない要素と判断。

2. **契約ドリフト検出の価値**
   T19 実行フェーズは T14 完成後 (数週間〜数ヶ月先)。その間に schemas.py が変更される
   リスクは現実的で、CI ガードの価値が大きい。

3. **T14 実装者の負荷軽減**
   G-GEAR セッションで T14 実装者 (将来の自分) が `from erre_sandbox.integration import
   WsTick` で即着手できる価値は、PR 差分の大きさを正当化する。

4. **過設計リスクの緩和可能性**
   「最小限の型のみ定義し、詳細は T14 実装時に追加する前提」を decisions.md に明記
   することで緩和可能。初期定義を破壊しなくて済む粒度で設計する。

### v1 から取り込む要素 (ハイブリッドの部分)

- **Markdown 4 枚**: `scenarios.md` / `integration-contract.md` / `metrics.md` /
  `t20-acceptance-checklist.md` は **v1 の構成を踏襲**。ただし責務を「人間向けナラティブ」に限定
- **skeleton テスト 3 件**: v1 のファイル分割 (walking / memory_write / tick_robustness) を踏襲
- **受け入れ条件の網羅**: requirement.md の条件は v1/v2 共に全て満たす

### v2 採用で破棄する v1 の要素

- **「Markdown が契約本体」の思想**: 契約の single source of truth は Python に移す
- **skeleton 全件 skip**: contract_snapshot は常時 ON にする

## 最終採用: v2 (ただし v1 の Markdown 構成を「rational 層」として流用)
