# ブロッカー — DA-15 Phase 1 implementation

## 解決済

なし (本 PR 内に解決済 blocker は未発生)

## 未解決 (defer または別 PR)

### B-1: philosophy-domain BERT exploratory analysis

- **状態**: defer to future exploratory work
- **背景**: Codex HIGH-1 で「philosophy-domain BERT は ADOPT primary に含めて
  はならない」が mandate。一方で、長期的には domain-specific encoder が
  persona-style discrimination に有用な可能性がある。
- **対処**: 本 PR scope 外。Phase 2 (Plan B) または Phase E A-6 で必要なら
  別途 exploratory analysis を起票。

### B-2: Heidegger 邦訳 corpus の license clean 確保

- **状態**: D-1 で対処 (Aozora 公領 + Wikipedia CC-BY-SA で代替)
- **対処**: 本 PR で確定済。corpus metadata に attribution 記載。

### B-3: Plan B (Phase 2) trigger 条件

- **状態**: Plan A 完了後判定
- **背景**: Plan A の verdict が REJECT (両 candidate encoder で AUC ≥ 0.75
  または balanced d ≤ -0.5 を満たさない) の場合、Phase 2 を別 PR で起票。
- **対処**: Plan A 完了時の verdict 文書で明示。
