# 設計判断 — T20 M2 Acceptance

## 判断 1: T20 を "closeout only" に限定し、コード変更ゼロとする

### 背景

T19 ライブ検証で発覚した GAP-1 (WorldRuntime↔Gateway 配線欠落) は
`_NullRuntime` 依存が原因で Avatar 視覚移動が検証不能だった。
T20 で同時に GAP-1 を修正する選択肢もあった。

### 選択肢

| 案 | 内容 | 評価 |
|---|---|---|
| A | T20 で `src/erre_sandbox/main.py` を作り full-stack orchestrator を実装 | **却下**: GAP-1 は MASTER-PLAN §5 の **M4** タスク。T20 (M2 closeout) に取り込むと M2 スコープの意図 (contract-level layering) が崩れ、かつ T19 の layer-scoped evidence の有効性が失われる |
| B | T20 を closeout (docs / runbook / checklist) に限定し、GAP-1 は M4 で正式対応 | **採用** |
| C | T20 を skip して M4 に直接進む | 却下: MVP M2 を formally 閉じないと `v0.1.0-m2` タグが付かず、段階的進行の節目が曖昧になる |

### 採用理由

1. **レイヤー設計の尊重**: M2 は "contract layer" の達成、M4 は
   "full-stack orchestration" の達成という責務分離が MASTER-PLAN で明示済。
   T20 で横断すると両 milestone の成果物が混ざる
2. **T19 evidence の有効性維持**: コード変更ゼロなら T19 ライブ検証 (layer-scoped
   PASS) がそのまま T20 の evidence として使える。コード変更すると再検証が必要
3. **時間見積との整合**: MASTER-PLAN では T20 = 0.5d。GAP-1 実装 (100-200 行の
   async orchestrator) は最低 1d 以上、contract 違反
4. **下流効果の明確化**: T20 を小さく閉じることで M4 の kickoff スコープ
   (full-stack-orchestrator) が明確になる

### 帰結

- T20 の成果物は **ドキュメントとランブックのみ**: `docs/architecture.md` 1 箇所、
  `.steering/20260419-m2-acceptance/` 以下の 5 ファイル、
  `known-gaps.md` と `MASTER-PLAN.md` のマーキング更新
- Avatar 視覚移動 / 30Hz 描画 / WorldTickMsg 受信の視認検収は
  **M4 `gateway-multi-agent-stream` 完了後に再実施** (ACC-SCENARIO-WALKING 延長)
- `v0.1.0-m2` タグは本 T20 の closeout commit 後に付与する運用

## 判断 2: M2 検収条件の `[x]` は最小限にとどめ、GAP-1 依存項目に notation を付与

### 背景

MASTER-PLAN §4.4 の MVP 検収条件 7 項目のうち、

- 「Kant エージェントが peripatos を周回移動」
- 「`sqlite-vec` に `episodic_memory` レコードが追加される」
- 「Godot でアバターが 30Hz で歩く」
- 「ollama serve 起動 + inference server listen」

の 4 項目は GAP-1 (real runtime orchestrator 欠落) のため current state では PASS できない。

### 選択肢

| 案 | 内容 | 評価 |
|---|---|---|
| A | 全項目 `[x]` に marking して M2 完了を宣言 | **却下**: 実際には未達成。現実との乖離を記録に残してしまう |
| B | GAP-1 依存 4 項目を `[ ]` のまま残し、"(GAP-1 → M4 待ち)" notation を付加 | **採用** |
| C | M2 検収条件自体を書き換えて contract-level のみにする | 却下: MASTER-PLAN は MVP goal の source of truth。書き換えは大きすぎる |

### 採用理由

- **記録の正確性**: `[ ]` のままにすることで M2 が partial close であることが明示される
- **M4 planning への情報提供**: M4 kickoff 時に「M2 で未達の項目」が一目で確認できる
- **T20 closeout は acceptance-checklist.md への参照で明確化**: M2 の "layer scope 達成" の
  evidence は本タスクの checklist.md にあり、検収条件 `[x]` 数ではない

## 判断 3: `v0.1.0-m2` タグは T20 commit 後の運用判断として保留

### 背景

MASTER-PLAN §4.4 最終行 "作業ブランチ経由で main に merge 後、`v0.1.0-m2` タグを付与"。
T20 finish 時点で tag を打つかどうか選択が必要。

### 選択

- **保留**: T20 commit → PR → main merge のフローを経てから tag を打つ
- 理由: `main` 直接 push 禁止 (CLAUDE.md §禁止事項)。
  PR merge 後に tag が付く運用に統一
- T20 は feature branch `feature/t19-macbook-godot-integration` 上で commit まで
