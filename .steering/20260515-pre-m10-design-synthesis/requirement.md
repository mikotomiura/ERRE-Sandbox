# pre-M10 design synthesis

## 背景

M10 実装着手前に、現行 M10-0 design draft v2 (`.steering/20260508-cognition-deepen-7point-proposal/m10-0-concrete-design-draft.md`、PR #159 merged) と、後から起草された 2 件の調査メモ (`idea_judgement.md` Corpus2Skill 型 source_navigator、`idea_judgement_2.md` LLM 研究開発手法と評価調査) との gap を埋める design synthesis が必要になった。

調査で次が判明:

- v2 draft は idea_judgement_2.md の **大半を既に吸収済** (individuation metrics 3 件、`metrics.individuation` namespace、`AnalysisView` loader、`thresholds.md` calibrate_before_unblinding、QDoRA M12+ defer、persona checklist M10-A defer)
- v2 draft に **未吸収**:
  - idea_judgement.md (source_navigator 全 4 idea)
  - idea_judgement_2.md §2 Social-ToM minimum spec
  - idea_judgement_2.md §4 PEFT ablation registry の linkback
- 当初予定 slug `m10-0-individual-layer-schema-add` は M9 task で実装完了 (`evidence/eval_store.py:88` 等) — 新規 schema 追加作業は不要、slug 自体破棄

User の合意した本セッション scope: **synthesis 文書 4 件起票のみ**。コード変更なし、次 task scaffold (M10-0 main / source_navigator MVP) は本 task では起こさず、design.md 内に inline 草稿で持つ。

**追加方針 (2026-05-15 User 直接指示)**: 「m10 では具体的に ToM などを含めた評価体制を具体的に強固に設計してから決めてください」。
→ B-2 Social-ToM を「WP11 ~150 行 doc」で軽く済ます当初方針を撤回。M10-0 で動かす **評価体制全体 (Social-ToM を中心に、Counterfactual / Emotional alignment / 個体化 metrics 統合)** を本 synthesis で concrete + robust に設計してから、サブタスク配置を確定する。配置は設計のサイズと依存関係から自然に決まるべきで、placement-first ではなく **design-first** に逆転させる。

## ゴール

M10-0 評価体制を robust に固めた上で、次セッション以降の M10-0 sub-task 群を即起票可能な状態に持ち込む:

1. **M10-0 評価体制を concrete に設計** (本 synthesis 出力):
   - **Social-ToM eval harness** (zone × scenario × metric channel × negative control の格子設計、v2 draft §2.6 `counterfactual_challenge` と統合)
   - **Counterfactual perturbation protocol** の v2 draft §2.6 を拡張 (negative control の Social-ToM 拡張、acceptance + schema)
   - **Emotional/cognitive alignment (HEART/MentalAlign 系)** の M10-0 取り扱い (採否含む)
   - **既存 individuation metrics** との依存・直交性・統合点
2. idea_judgement.md / idea_judgement_2.md の未吸収項目について、上記設計に基づいて配置を確定 (ADR-PM-1〜PM-5)
3. v2 draft `m10-0-concrete-design-draft.md` への Addendum patch がそのまま貼り付け可能な体裁で synthesis 文書に保持
4. 次 task scaffold 3 件 (`m10-0-individuation-metrics` / `m10-0-social-tom-eval` / `m10-0-source-navigator-mvp`) の requirement.md 草稿が inline で揃う
5. memo 2 件が `.steering/` 配下に rename move され git 管理に取り込み可能 (現在 root の untracked から外す)

## スコープ

### 含むもの

- `.steering/20260515-pre-m10-design-synthesis/` 配下 4 文書の起票:
  - `requirement.md` (本ファイル)
  - `design.md` — §1 memo 要旨 / §2 v2 draft 既吸収項目 mapping / **§3 M10-0 評価体制 concrete robust design (Social-ToM 中心、~ メイン本文の大半を占める)** / §4 配置決定 / §5 v2 draft Addendum patch ドラフト / §6 次 task scaffold inline 草稿 (3 件) / §7 memo 最終配置案
  - `decisions.md` — ADR-PM-1〜PM-5 (PM-2 は **Social-ToM を独立 sub-task `m10-0-social-tom-eval` に格上げ** の決定)
  - `tasklist.md` — 本 task の実行手順
- `idea_judgement.md` / `idea_judgement_2.md` を `.steering/20260515-pre-m10-design-synthesis/` 配下に rename move
- (任意) `code-reviewer` agent による 4 文書のレビュー

### 含まないもの

- v2 draft 本体 (`m10-0-concrete-design-draft.md`) の編集 — Addendum patch ドラフトのみ design.md §4 に保持、本体への commit は次 task `m10-0-individuation-metrics` scaffold 時に同時 commit
- 次 task scaffold 作成 (`m10-0-individuation-metrics` / `m10-0-source-navigator-mvp` の `.steering/` ディレクトリ作成) — design.md §5 で草稿のみ
- Codex 13th review — 本セッション defer
- コード変更 (schemas.py / contracts/ / evidence/ / training/ / tests/) — 一切なし
- M10-0 main の `thresholds.md` / `tier_b/` 等の具体実装 — 次 task 担当

## 受け入れ条件

- [ ] `requirement.md` (本ファイル) が起票済
- [ ] `design.md` §1-§7 が埋まる:
  - §1 idea_judgement.md / idea_judgement_2.md 要旨
  - §2 v2 draft 既吸収項目 mapping 表
  - **§3 M10-0 評価体制 concrete robust design (Social-ToM 中心)** — 以下を全部含む:
    - §3.1 評価体制の上位構造 (4 layer: Individuation / Social-ToM / Counterfactual perturbation / Emotional alignment)
    - §3.2 Social-ToM scenario 設計 (chashitsu / agora / garden × 3 base scenarios × counterfactual variants)
    - §3.3 Social-ToM metric set (false_belief_recovery / info_asymmetry_handling / counterfactual_resistance 等、独立 channel として定義)
    - §3.4 Schema (DuckDB `metrics.social_tom` table + sidecar JSON、v2 draft §2.3 namespace に追加)
    - §3.5 Counterfactual perturbation protocol v3 (v2 draft §2.6 を Social-ToM 統合へ拡張)
    - §3.6 Negative control 拡張 (3 種 → 5 種、Social-ToM 用 cite-disabled + shuffled-recipient + perspective-isolation 追加)
    - §3.7 Acceptance preregister (`thresholds.md` への追記項目)
    - §3.8 既存 metric との直交性 (相関行列の Social-ToM 拡張、|r| ≥ 0.85 detection)
    - §3.9 Emotional alignment (HEART/MentalAlign) の M10-0 取り扱い (defer 採否)
    - §3.10 Out-of-scope の明示 (multi-agent runtime / production scale / clinical 主張)
  - §4 配置決定 (B-1/B-2/B-3 + 新規 B-4 Emotional alignment) — §3 設計サイズから自然に確定
  - §5 v2 draft Addendum patch ドラフト (貼り付け可能な体裁)
  - §6 次 task scaffold 草稿 3 件 (M10-0 main / Social-ToM eval / source_navigator MVP)
  - §7 memo 最終配置案
- [ ] `decisions.md` に ADR-PM-1 (source_navigator 並列 task) / ADR-PM-2 (**Social-ToM を独立 sub-task に格上げ**) / ADR-PM-3 (PEFT registry linkback) / ADR-PM-4 (memo 最終配置) / ADR-PM-5 (Emotional alignment は M10-0 範囲外 = M11+ defer) が成立
- [ ] `tasklist.md` が起票済
- [ ] `idea_judgement.md` / `idea_judgement_2.md` を `.steering/20260515-pre-m10-design-synthesis/idea-judgement-source-navigator.md` / `idea-judgement-pdf-survey.md` に rename move、`git status` で root untracked から外れる
- [ ] (任意) `code-reviewer` agent で HIGH 指摘ゼロ
- [ ] commit (docs+steering only、Conventional Commits)

## 関連ドキュメント

- `.steering/20260508-cognition-deepen-7point-proposal/m10-0-concrete-design-draft.md` — synthesis の起点
- `.steering/20260508-cognition-deepen-7point-proposal/reasoning-model-judgment.md` — weight-level intervention M12+ defer の根拠
- `.steering/20260430-m9-b-lora-execution-plan/` — DB11 ADR (PR #145)
- `idea_judgement.md` (root、untracked) — source_navigator scope
- `idea_judgement_2.md` (root、untracked) — Social-ToM scenario / PEFT yaml registry
- `docs/development-guidelines.md` — Conventional Commits / .steering/ 規約
- `/Users/johnd/.claude/plans/start-task-m10-0-individual-layer-schem-quiet-umbrella.md` — 本 task の plan (承認済)
