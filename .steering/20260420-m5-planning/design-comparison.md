# 設計比較 — 案 A vs 案 B vs 採用 hybrid

> **/reimagine 作法**: 初回案 (A) を意図的に破棄し、異なる分解軸の対抗案 (B) を立てて
> 並べ、採用案を決定した記録。最終確定は `design.md`。

## 対比する 2 つの分解軸

### 案 A: Contract-First 水平分解 (`design-v1.md`)

- Phase 1 schema freeze → Phase 2 並列 4 本 → Phase 3 integration → Phase 4 live
- M4 で実証済のテンプレートをそのまま M5 の 3 軸 (Mode / Dialog / Visuals) に適用
- 並列効率を最大化、contract の凍結で手戻りを抑制

### 案 B: Risk-First Vertical Slicing (対抗案、本節でのみ参照)

M5 で最も不確実性が高い **LLM プロンプト品質** を先に潰すため、1 ペア (Kant-Rikyu) ×
1 モード (peripatetic) だけで vertical slice を end-to-end に通してから残り軸を薄く広げる。
案 A と意図的に異なる分解軸 (横方向の並列 → 縦方向のリスク解消) を採用。

**Phase 構成**:

1. `m5-walking-skeleton` (垂直スライス, 2-3 日) — 凍結せず inline で dirty patch。
   1 pair × peripatetic だけで 1 対話を実機 LLM で成立させる
2. `m5-prompt-hardening` (直列, 1-2 日) — Phase 1 で発見した破綻パターン (幻覚名 / 無限繰返し / 長さ) を対策
3. `m5-contracts-retrofit` (直列, 0.5 日) — dirty patch を `0.3.0-m5` に後付け整形
4. `m5-erre-mode-expansion` (並列 3 本, 2-3 日) — FSM / sampling / zone-triggers
5. `m5-visuals-layer` (並列, 1-2 日) — Godot tint + bubble
6. `m5-live-acceptance` (0.5 日)

**Critical Path**: skeleton → hardening → retrofit → mode-expansion → live ≒ **6-9 日**。

## 観点別比較

| 観点 | 案 A (Contract-First 水平) | 案 B (Risk-First 垂直) |
|---|---|---|
| **schema freeze 手戻りリスク** | 低 (M4 で実証済) | **高** (Phase 1 で触った struct を Phase 3 で再整形する必然) |
| **LLM プロンプト品質リスク** | **高** (integration 時点で初確認、手戻り大) | 低 (Phase 1-2 で品質検証を先行) |
| **Godot 視覚確認の不確実性** | 中 (Phase 4 live 時点で初確認) | 中-低 (Phase 1 で最小 bubble を既に実機通し) |
| **並列化可能度 (G-GEAR+Mac 2 機)** | **高** (Phase 2 で 4 本並列、LLM + Godot で自然分担) | 低 (Phase 1-3 は直列、Phase 4 で初めて並列化) |
| **中間 demo 可能性** | Phase 3 integration まで動かない | **Phase 1 で 1 対話 demo 可能** |
| **Scope 削減の柔軟性** | 軸単位で削れる (例: visuals を後回し) | Phase 単位でしか削れない、Phase 1 は必須 |
| **M4 パターン連続性** | **高** (テンプレートそのまま)、学習コスト 0 | 低、新パターンで steering 記録も新規化 |
| **予想所要日数** | 4-6 日 | 6-9 日 |
| **sub-task 数** | 7 | 6 |
| **リスク露呈タイミング** | 後半 (integration 時) | 前半 (Phase 1 時) |

## 採用: hybrid (案 A 骨格 + 案 B の「Phase 0 LLM spike」先行)

### 根拠

1. **案 A の Contract-First は M4 で実証済**。`0.3.0-m5` schema freeze 後の並列度は
   実装コストの最短経路。steering テンプレート・agent 資産・test パターンをそのまま流用できる。
2. 一方で案 B が警告する **dialog_turn プロンプト品質不確実性は本物**。M5 成功基準 #4
   (dialog_turn が Godot bubble で N ターン流れる) は LLM の発話が「persona-ish で
   会話として破綻しない」ことが暗黙の前提、これは mock では検証できない。
3. **解決**: `m5-contracts-freeze` の前に半日の throwaway タスク `m5-llm-spike` を挿入。
   Kant-Rikyu で LLM を叩いて発話長・停止条件・turn_index 上限を経験的に決定し、
   その結果を `m5-contracts-freeze` の schema 決定 (例: `DialogTurnMsg.turn_index` 必要性、
   `dialog_turn_budget` の初期値) と `m5-dialog-turn-generator` の prompt 設計に反映する。
   spike コードは破棄、steering 記録に知見だけ残す。

### 採用案の位置づけ

| 観点 | hybrid の位置 |
|---|---|
| schema freeze 手戻りリスク | 案 A 並 (低) — spike で決定根拠が揃ってから freeze するため |
| LLM プロンプト品質リスク | 案 B 並 (低) — spike で早期確認 |
| 並列化可能度 | 案 A 並 (高) — Phase 2 の並列 4 本を維持 |
| 予想所要日数 | **4-6 日 + 0.5 日 (spike) = 4.5-6.5 日** — 案 A とほぼ同等、案 B より短い |
| sub-task 数 | 9 (spike 追加 + acceptance を独立) |

案 A の並列効率と案 B のリスク早期解消を両立。M5 成功基準 (live acceptance 7 項目 PASS)
に対して最短経路かつ品質リスクが最も抑制される。

## 比較で採用しなかった選択肢

- **案 B 完全採用**: 日数が 1.5-3 日長い。2 機並列の利点を殺す。M4 パターンから逸脱するので
  steering 記録が新規化し文書コストが上がる。
- **案 A 完全採用**: LLM プロンプトが破綻した場合の手戻り影響範囲が大きい。Phase 3
  integration で初めて「破綻」を観測すると、schema bump のやり直し + prompting 設計変更 +
  複数 sub-task の巻き直し、が連鎖する。
- **Godot 視覚化を後続マイルストーンへ分離**: M5 acceptance #5, #6 の live evidence が
  成立しなくなり、M5 完了判定が不透明になる。M4 が Godot 側の評価も含めて完全クローズ
  した前例に倣う。
