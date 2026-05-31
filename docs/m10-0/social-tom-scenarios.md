# M10-0 — Social-ToM Scenario Spec（M11-C handoff、`social-tom-scenarios.md`）

> **WP11** / M10-0 ① individuation-metrics PR-4 doc 成果物。
> **Status**: SPEC ONLY（M10-0 では active 計測しない。実装 + 実走は M11-C task `m11-c-social-tom-proper`）。

---

## §0. ⚠ Claim boundary（canonical §0 / A16）

> 本 4 scenario は **Social-ToM proper の評価素材**であり、**M10-0 では active 計測しない**。
> M10-0 の Layer 2（Cite-Belief Discipline）は Social-ToM proper の sufficient statistic ではなく、
> process-trace prerequisite / proxy にすぎない。M11-C 着手時に Codex review + `/reimagine` を
> 再度実施した上で実走に進む。

---

## §1. 共通 handoff metadata（A14、各 scenario に cross-cutting で適用）

```yaml
freshness_date: 2026-05-15
protocol_version: pre-m10-0.1
dependencies:
  - M9-eval Phase B+C capture format (*.duckdb)
  - ERREMode FSM (zone routing)
  - 5 zone definitions (docs/glossary.md)
  - cited_memory_ids schema (M10-C territory、stub なしで実走 M11-C 着手時に解決)
  - SemanticMemoryRecord.belief_kind schema (値域 trust/clash/wary/curious/ambivalent は active 化時に再確認)
rereview_gate: "M11-C task start (m11-c-social-tom-proper scaffold 時に本 spec を 1 から読み直す)"
expected_inputs: "multi-agent dialog with zone routing, observation event log per agent, testimony channel separation"
failure_modes:
  - zone definition change (5 zone schema 改訂)
  - agent_id schema change (A/B/C の identity model 変更)
  - cited_memory_ids schema が M10-C で本書と異なる shape で決着した場合
  - capture format break (*.duckdb の raw_dialog.dialog 列定義変更)
  - counterfactual_challenge channel name 変更 (recovery-protocol.md と integration)
  - belief_kind 値域変更
```

⚠ 上記 metadata は M11-C 着手時に **独立読解可能**であること（M10-0 文脈なしで本 doc 単体から実走設計に入れる）。

---

## §2. Scenario spec（4 件、各 setup / probe(M11-C 実走) / M10-0 spec）

### S-CHA-1: private witness asymmetry
- **Setup**: chashitsu zone、agent A 単独で observation event（例: 茶器移動）、後で agent B が入室。
- **Probe（M11-C で実走）**: A→B testimony 後、B の belief が update するか / 嘘の testimony 下で B の
  belief stability。
- **M10-0 spec**: scenario rule + zone constraint + observation event categorisation **のみ**。
  - zone constraint: chashitsu（observation の private witness を成立させる隔離空間）。
  - observation event categorisation: A の単独 perception を「private witness」tag、B 入室後の event を
    「post-arrival shared」tag に分離。
- **Layer 2 接続**: M-L2-2 `cited_memory_id_source_distribution`（testimony が self_observation 由来か
  others 由来かの source tagging）。M10-0 では unsupported pin。

### S-AGO-1: false rumor
- **Setup**: agora zone、A は C と直接対話歴あり、B は C の伝聞（rumor）を信じる、A と B が C について discuss。
- **Probe（M11-C で実走）**: testimony 階層（direct experience vs second-hand）を model するか。
- **M10-0 spec**: testimony hierarchy rule + rumor 注入 channel + memory_id source tagging **のみ**。
  - testimony hierarchy: direct（A→C 直接） > second-hand（B が受けた rumor）の優先順位規則。
  - rumor 注入 channel: `counterfactual_challenge` とは別の「伝聞」channel として分離（混同禁止）。
- **Layer 2 接続**: M-L2-2 source distribution（direct vs second-hand の分布）。M10-0 では unsupported pin。

### S-GAR-1: counterfactual in solitude
- **Setup**: garden zone、A 単独 reflection、external `counterfactual_challenge` channel で
  opposite-stance evidence injection（`recovery-protocol.md` と同 channel）。
- **Probe（M11-C で実走）**: A の reflection が counterfactual evidence を採用するか。
- **M10-0 spec**: `recovery-protocol.md`（§C.3 perturbation）との overlap 区別、scenario-specific は
  M11-C で具体化。
  - overlap 区別: recovery protocol は「style/habit/decision の回復率」、本 scenario は「belief 採否」を見る。
    同一 `counterfactual_challenge` channel を共有するが metric 目的が異なる。
- **Layer 2 接続**: M-L2-3 `counterfactual_challenge_rejection_rate`。M10-0 では unsupported pin
  （`reason="requires perturbation protocol run, M11-C territory"`）。

### S-GAR-2: cited source asymmetry
- **Setup**: garden zone、retrieved memory に「自身が cite した source」と「他者が cite した source」が混在。
- **Probe（M11-C で実走）**: source attribution の retention が belief revision priority を持つか
  （M10-C `WorldModelUpdateHint.cited_memory_ids` 前段）。
- **M10-0 spec**: source-of-cite metadata schema + retention priority rule **のみ**。
  - source-of-cite metadata: 各 retrieved memory に `cited_by`（self / other）tag を付す schema 案。
  - retention priority rule: self-cited source が belief revision で優先される、という仮説の記述のみ
    （実測は M11-C + M10-C schema 確定後）。
- **Layer 2 接続**: M-L2-2 source distribution + M-L2-1 `provisional_to_promoted_rate`（belief lifecycle、
  M10-C schema 拡張待ち）。M10-0 では unsupported pin。

---

## §3. M11-C への handoff（実装は本 doc を素材に新規 scaffold）

- M10-0 では本 4 scenario の **spec のみ**を保持。実装 + 実走 + Social-ToM-specific metric 設計は M11-C。
- `m11-c-social-tom-proper` 着手時に Layer 4（Social-ToM proper）を新規 scaffold し、本 spec を継承。
- NC-4/NC-5（旧 design-original）は scenario lib 縮小で **廃止**（無理に残さない、canonical §B.3）。

---

## §4. Acceptance（canonical §C.7 A14）

- **A14**: 本 doc が §1 handoff metadata（`freshness_date` / `protocol_version` / `dependencies` /
  `rereview_gate` / `expected_inputs` / `failure_modes`）を含み、M11-C task 着手時に独立読解可能。
- ⚠ A5（cache benchmark）は別 PR へ defer のため、本 doc 完了は **M10-0 close を意味しない**
  （`tasklist.md` PR-5 参照）。

---

## 関連 doc

- `thresholds.md`（WP9、Layer 4 defer entry）
- `recovery-protocol.md`（WP10、S-GAR-1 が共有する counterfactual_challenge channel）
