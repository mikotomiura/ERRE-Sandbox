# M10-0 Individuation Metrics — Intervention Recovery Protocol（`recovery-protocol.md`）

> **WP10** / M10-0 ① individuation-metrics PR-4 doc 成果物。
> **Status**: **PROTOCOL FREEZE のみ**（M10-0 では実走しない、実走は M11-C territory）。

---

## §0. M10-0 における扱い（canonical §C.3、最重要・honest framing）

- M10-0 では **protocol freeze + `protocol_version` pin のみ実施**。実装コードは実走しない。
- **実走**（baseline tick `T_base` / perturbation tick `T_perturb` / recovery tick `T_recover`）は
  **M11-C territory**。
- Layer 1 metric を perturbation tick 中に同時計測する設計は、active 化時（M11-C 着手後）の **reference 保持**。
- ⚠ 本 protocol に対応する metric は M10-0 で **unsupported pin** であり、reason 文言と整合する:
  - `intervention_recovery_rate`（Layer 1、recovery channel）:
    `reason="requires perturbation protocol run, M11-C territory"`、**never valid**（M10-0）。
  - `cite_belief_discipline.counterfactual_challenge_rejection_rate`（Layer 2、M-L2-3）:
    `reason="requires perturbation protocol run, M11-C territory"`、`status='unsupported'` 100% pin。
  - 両者は同一 perturbation protocol 依存であるため、本 doc が freeze する protocol を共有 reference とする。

```yaml
protocol_version: pre-m10-0.1   # M10-0 で frozen (本 doc が pin する識別子)
execution_milestone: M11-C      # 実走はここで
calibration_milestone: M11-B    # T_* 数値は M11-B development_state 後に calibrate
```

---

## §1. Protocol 定義（v2 §2.6、HIGH-3 反映 = `counterfactual_challenge` 隔離）

> **HIGH-3 fix**: opposite-stance memory を `retrieved_memories` に強制注入する v1 案を撤回し、
> **separate `counterfactual_challenge` channel** に隔離する。perturbation 中の SWM write 禁止、
> cite-disabled negative control を追加。

```
prep:
  1. base individual を T_base = 200 tick 走らせ baseline Burrows / behavioral / SWM snapshot

perturbation (HIGH-3 隔離):
  2. counterfactual_challenge channel に opposite-stance content N=5 を injection
     - retrieved_memories とは別 channel、cited_memory_ids 集合に **含めない**
     - WorldModelUpdateHint adoption の evidence source として **無効化**
     - perturbation tick 中の SWM write は **禁止** (replay-only モード)
  3. T_perturb = 50 tick 走らせ perturbed_floor 計測

recovery:
  4. counterfactual_challenge 除去後 T_recover = 200 tick 走らせ post recovery 計測

metric:
  recovery_rate    = (post - perturbed_floor) / (baseline - perturbed_floor)
                     channels: Burrows (style), cognitive_habit_recall_rate (habit),
                              action_adherence_rate (decision)
  stickiness_rate  = SWM entry persistence ratio (M11-C で active、M10-0 は protocol のみ)
```

- `T_base` / `T_perturb` / `T_recover` は **M11-B 後 calibrate**（`data_split` を `thresholds.md` で固定）。
- 数値が M11-C 実走前に不確定でも、M10-0 close は protocol freeze で成立（`thresholds.md` の
  `recovery_rate band = defer(M11-C)` と整合）。

---

## §2. Negative control（HIGH-3 必須、canonical §C.5、M10-0 は文書化のみ・実走 M11-C）

| ID | name | 期待（active 化時） | M10-0 status |
|---|---|---|---|
| NC-1 | cite-disabled control | `counterfactual_challenge` entry を `cited_memory_id` として宣言しても `WorldModelUpdateHint` adoption は merge されない（golden test 化） | 文書化のみ、実走 M11-C |
| NC-2 | shuffled-memory control | 関係ない memory id を cite → 同様に reject | 文書化のみ、実走 M11-C |
| NC-3 | no-individual-layer ablation | `individual_layer_enabled=false` で同 protocol → SWM 自体存在しない。M-L2-3 effect direction の comparator には **使わず degenerate/undefined** とし、within-individual non-perturbation baseline を comparator とする（canonical §C.2 M-L2-3、HIGH-2） | 文書化のみ、実走 M11-C |

---

## §3. M11-C handoff 条件

- 実走着手時（`m11-c-social-tom-proper` または recovery 専用 task）には本 protocol を 1 から読み直す。
- `T_base`/`T_perturb`/`T_recover` を `thresholds.md` の `data_split`（cal/eval disjoint）に従って calibrate。
- `counterfactual_challenge` channel 名が runtime 実装と一致するか再確認（v2 §2.6 と integration、
  channel rename は failure mode）。

---

## §4. Acceptance（canonical §C.7）

- **A12c**: M-L2-3 `counterfactual_challenge_rejection_rate` が `status='unsupported'` 100% +
  `reason="requires perturbation protocol run, M11-C territory"` を返し、
  **protocol freeze + `protocol_version` pin が M10-0 close 条件**（本 doc が pin を提供、§0）。
- **A13**: Layer 2 × NC-1/2/3 の §2 期待値 verification は **M11-C territory**
  （M10-0 では unsupported pin の golden test のみ実行、NC 実走は M11-C で block/cluster bootstrap CI 95% band 検証）。

---

## 関連 doc

- `thresholds.md`（WP9、`recovery_rate band` / Layer 2 threshold state）
- `social-tom-scenarios.md`（WP11、S-GAR-1 が counterfactual_challenge channel を共有）
