# Decisions — L6 ADR Roadmap

採用方針は `/reimagine` で v1 を破棄して v2 に確定 (`design-comparison.md` 参照)。
各 ADR の evidence は `design.md` の §1-§4 を cite。5 節構造・各 ≤20 行で記述。

## D1. LoRA による persona 分化 — defer-and-measure

- **現状**: `qwen3:8b` 1 base + prompt injection で 3 persona 分化
  (`cognition/prompting.py:65-89`、`persona-erre` Skill L28-62)。LoRA 関連コード 0 件。
  M9 前提は ≥1000 turns/persona 対話ログ (MASTER-PLAN L146)、現 MVP は ~20 turns/persona。
- **選択肢**: A1-a 現状維持 / A1-b 全 persona LoRA / A1-c hybrid / A1-d 継続事前学習 /
  A1-e RAG (episodic memory からの in-context 例示) / A1-f instruction-tune
  (詳細は `design.md` §2 Axis 1)
- **採用**: architecture 確定は **M9 まで defer**。M8 では baseline 計測と
  episodic log pipeline 整備に専念、A1-a を暫定継続 (RadixAttention で KV prefix 共有)。
- **根拠**: データ量不足で A1-b-f の比較判断不能。先取り commit は覆った場合 ADR 再執筆。
  A1-a のコストは prompt token 以外無く、並行で log 蓄積すれば機会損失ゼロ。
- **次アクション** (M8 preconditions):
  - `m8-episodic-log-pipeline` — dialog_turn log 完全永続化、persona 別 turn count 計測
    (2026-04-24 PR #88 merge 済、scope を dialog_turn のみに縮小)
  - `m8-baseline-quality-metric` — prompt-only での対話 fidelity (self_repetition +
    cross_persona_echo の 2 次元) と `bias.fired` 頻度を定量指標化。**affinity は
    defer**、本節 residual の `m8-affinity-dynamics` に分離 (本 spike の Phase 1 で
    `RelationshipBond.affinity` に mutation logic ゼロが判明、mutation なしで測定
    すると baseline が常に 0.0 になり M9 比較が不能)
  - `m8-affinity-dynamics` (L6 D1 residual、新規) — `RelationshipBond.affinity` の
    mutation logic を設計・実装 (interaction 頻度 / dialog 応答長 / 共起 zone 等
    から derive)。完了後 baseline JSON の `affinity_trajectory` field を null から
    実数に昇格。M9 LoRA 効果測定の追加 reference 軸として活用
  - M9 着手条件: baseline data (fidelity + bias_fired_rate 固定) + ≥500 turns/persona
    到達 (M9 前提 ≥1000 の緩和は別 ADR)。affinity は M9 着手の必須ではないが、
    `m8-affinity-dynamics` が間に合えば比較精度が上がる
  - 関連 Skill: `llm-inference` (VRAM 予算)、`persona-erre` (system prompt 構造)

## D2. Agent scaling — observability-triggered

- **現状**: 3 agent hardcoded (`integration/dialog.py:113` "M4 targets N≤3")、
  dialog pair 列挙 `_iter_colocated_pairs` (`dialog.py:292-305`) が C(N,2)、
  N>4 で Ollama 逐次化 (`OLLAMA_NUM_PARALLEL=4`、`llm-inference` Skill L45)。
  VRAM は N=4 まで余裕 (16-13=3GB)。
- **選択肢**: A2-a 4th persona / A2-b 3 維持で深掘り / A2-c 同 persona 複数 /
  A2-d 2 persona-set 切替 / A2-e 1 入替 / A2-f user を 4 体目扱い (D3 と交叉)
  (詳細は `design.md` §2 Axis 2)
- **採用**: **3 維持 + scaling トリガー metric の定義**。metric 閾値超過が live で観測
  された時点で +1 persona を contrastive 選定で追加。量先行ではなく metric-first。
- **根拠**: 量を先行させる合理性なし。観察可能性の頭打ち (dialog pair saturation、
  observer fatigue、zone 滞留分布の flat 化) が科学的トリガー。交叉 A2-f は D3 で扱う。
- **次アクション** (M8 preconditions):
  - `m8-scaling-bottleneck-profiling` — 上記 3 metric 候補を N=3 の live data で計測、
    閾値案を 3 本提案
  - M9 着手条件: いずれかの metric が定量的に閾値超過、補完 persona 候補リストを起票
  - 関連 Skill: `llm-inference` (並列予算)、`persona-erre` (persona 追加手順)、
    `architecture-rules` (`dialog.py` の N 依存解消方針)

## D3. User-dialogue IF — two-phase methodology

- **現状**: ControlEnvelope 11 variants に user→agent channel 無し
  (`schemas.py:858-871`)。MIND_PEEK (`ReasoningPanel.gd:1-6`) /
  DialogBubble (`DialogBubble.gd:14-57`) は観察専用。research stance は
  「自律創発の観察」で user interaction は定義上介入 (`design.md` §4)。
- **選択肢**: A3-a user-as-special-agent / A3-b MIND_PEEK prompt injection /
  A3-c 別 WS channel / A3-d 2-phase methodology / A3-e pause-and-query /
  A3-f post-M10 繰越 (詳細は `design.md` §2 Axis 3)
- **採用**: **A3-d 2-phase methodology**。autonomous run と user-Q&A epoch を
  `session_phase` enum で時間分離、interface は Q&A epoch 内で既存 DialogTurnMsg 再利用。
  schema 増殖は 1 フィールド (`session_phase`) のみ。
- **根拠**: autonomous claim の汚染回避 (`design.md` §4)、既存 schema 最大利用で
  DRY 維持、M10-11 evaluation layer の 4 層設計と自然接続。A3-a は autonomous log に
  介入混入で統計主張を毀損、A3-b/c は可視性 / DRY で劣後。
- **次アクション** (M8 preconditions):
  - `m8-session-phase-model` — session_phase enum (autonomous / q_and_a / evaluation) と
    epoch 遷移 API、Q&A epoch 中の user 発話記録仕様を設計
  - M9 着手条件: Q&A epoch prototype で MacBook↔G-GEAR 往復遅延 <500ms を達成
  - 関連 Skill: `architecture-rules` (schemas 追記)、`persona-erre` (researcher YAML 雛形)

---

## 横断メモ

3 ADR の「次アクション」は M8 spike 4 本 (`m8-episodic-log-pipeline` /
`m8-baseline-quality-metric` / `m8-scaling-bottleneck-profiling` /
`m8-session-phase-model`) に cross-reference される。M8 planning セッションでは
これら 4 本を 1 spike として起票するか、2 本ずつに分割するかを最初に判断する。

親 task の decisions D2 に従い、本 branch diff は **docs のみ** で構成される。
運用予算節 (VRAM 予算 / Ollama 並列上限 / local-only 制約) は CLAUDE.md と
`architecture-rules` Skill に既記のため DRY により記載しない。
