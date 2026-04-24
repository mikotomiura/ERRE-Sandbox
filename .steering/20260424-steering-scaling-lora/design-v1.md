# Plan — L6 ADR Roadmap (Scaling / LoRA / User-Dialogue IF)

Task dir: `/Users/johnd/ERRE-Sand Box/.steering/20260424-steering-scaling-lora/`
Branch (to create): `feat/steering-scaling-lora` from `main`

## Context

M7 Slice β が main に merge された直後 (PR #83, commit `a76343c`, 2026-04-24)。親タスク `20260424-m7-differentiation-observability` の decisions D2 により、L6 (LoRA / agent scaling / user-dialogue IF) は **コード作業と戦略文書を混ぜない** ために別 steering として並走起票される運びとなった。現状 M8+ の意思決定材料が存在せず、γ 着手時に「何故この schema/輪郭か」の参照が欠落する。本タスクでこの gap を埋め、M8 以降の spike task が preconditions を持って起票できる状態にする。

docs-only、~1-2h、Plan mode 不要という軽量タスク (tasklist.md 冒頭にて明記)。コード差分は **ゼロ**。

## ゴールと受け入れ条件 (requirement.md より)

- `decisions.md` に 3 本の ADR、各 20 行以内、5 節構造 (現状 / 選択肢 / 採用 / 根拠 / 次アクション)
- 各 ADR は `llm-inference` / `persona-erre` / `architecture-rules` Skill と整合
- 各 ADR で M8+ task の preconditions が明示される
- `git diff --stat main...feat/steering-scaling-lora` が `.md` のみ
- H2 が提案した "運用予算節" は **書かない** (CLAUDE.md + architecture-rules に既記、DRY)

## 実行フロー (tasklist.md 準拠)

### Step 0 — Pre-write verification
- `src/erre_sandbox/inference/ollama_adapter.py:37` を Read して base model 名を確定 → **`qwen3:8b`** (tasklist.md line 14 の "gpt-oss:20b MoE" は古いメモ、ADR 1 では正しい値を使う)
- `llm-inference` Skill (`.claude/skills/llm-inference/SKILL.md`) を Read、VRAM 予算 (~13GB/16GB on RTX 5060 Ti) と M9 前提を把握
- `persona-erre` Skill を Read、ERRE mode と persona system prompt の現状を把握

### Step 1 — Branch + design.md
- `feat/steering-scaling-lora` を main から切る
- **新規**: `.steering/20260424-steering-scaling-lora/design.md` を作成。内容は簡潔 (≤50 行):
  - 本タスクのアプローチ (ADR 5 節形式、各 ≤20 行、docs-only)
  - 親 D2 制約の明記 (コード変更なし、qualitative、H2 運用予算節は不採用)
  - 依存 Skill の列挙 (llm-inference / persona-erre / architecture-rules)
  - MASTER-PLAN への影響 (M8 行追加、M9 LoRA 前提の再確認)
- これで preflight の `WARN: missing design.md` が解消

### Step 2 — decisions.md (3 ADR)
**書式**: 既存 M7 `20260424-m7-differentiation-observability/decisions.md` の tight pattern に寄せつつ、requirement の 5 節名を採用。各 ADR ≤20 行。採用は tasklist の「暫定」に追従 (ユーザー review で変更可)。

**ADR 1 — LoRA による persona 分化**
- 現状: `qwen3:8b` 1 base + prompt injection (`cognition/prompting.py:65-89`) で 3 persona 分化。LoRA への参照はコードゼロ、MASTER-PLAN.md:146 で M9 (vLLM + `--enable-lora`) 目標。
- 選択肢: (a) 現状維持 (b) persona ごとに LoRA (c) hybrid — 高分散 persona のみ LoRA、他 prompt
- 採用: (c) M8 spike で hybrid 試作、判定は 3 agent 以上に拡張したあとの差異観察に委ねる
- 根拠: LoRA 学習には ≥1000 turns/persona が必要 (MASTER-PLAN M9 行)。現 MVP は ~20 turns/persona、M4-M7 の live log で調達可能。prompt injection は RadixAttention (`cognition/prompting.py:6`) で KV prefix 共有でき現状コスト小、LoRA swap 実装は M9 adapter pipeline に委譲
- 次アクション: M8 spike task "LoRA training cost benchmark" の preconditions (DPO ペア抽出、adapter hot-swap 遅延測定) を列挙

**ADR 2 — Agent scaling (4 体目以降)**
- 現状: 3 agent 前提が `integration/dialog.py:113` (`M4 targets N≤3`) と `_iter_colocated_pairs` (`dialog.py:292-305`) に内在。`world/tick.py:668,771` で asyncio.gather 並列。`OLLAMA_NUM_PARALLEL=4` (llm-inference SKILL) で N>4 は serialization。dialog pair は C(N,2) 爆発。
- 選択肢: (a) 4th persona 追加 (思想史的補完) (b) 同 persona 複数 (c) 3 で深掘り
- 採用: (a) M8 で 1 体追加、persona は既存 3 と補完的な系譜 (候補列挙は M8 起票時)
- 根拠: 4 agent = 6 pair で dialog 観察可能性が維持される境界。同 persona 複数は個体差検証には有用だが、本プロジェクトの目的 (異質な認知習慣の相互作用) から外れる。VRAM 余裕は 16GB - 13GB = 3GB で 4 agent は share model のまま収まる
- 次アクション: M8 起票時の候補 persona list (Socrates / Confucius / Aurelius ...)、dialog_turn pairing scheduler 設計 (現 O(N²) を tier / cooldown で緩和するか)

**ADR 3 — User-dialogue IF**
- 現状: ControlEnvelope (`schemas.py:858-871`) 11 variants に user→agent channel なし。MIND_PEEK (`ReasoningPanel.gd:1-6`) は observability only。DialogBubble (`DialogBubble.gd:14-57`) は agent 発話表示専用。
- 選択肢: (a) Godot text input → DialogTurnMsg + 特殊 agent "user" (b) MIND_PEEK 経由 prompt injection (c) 別 WebSocket channel
- 採用: (a) 既存 dialog_turn loop に user を特殊 agent として乗せる、schema 追加は最小
- 根拠: 既存 DialogTurnMsg (`schemas.py:795`) と turn_index 機構を再利用、affinity 測定の整合性が保たれる。(b) は debug 用途に留める (invisible injection で再現性が損なわれる)。(c) は schema 増殖、DRY 違反
- 次アクション: user persona YAML 雛形、turn-taking policy (user 発話後にどの agent が先に応答するか)、MacBook↔G-GEAR 往復遅延測定 (目標 <500ms)

### Step 3 — MASTER-PLAN.md 更新
- `.steering/20260418-implementation-plan/MASTER-PLAN.md` に **M8 行を追加** (現状 M7 と M9 の間が空白)。内容: M8 = "hybrid LoRA spike + 4th agent onboarding + user-dialogue IF contract"、前提に本 L6 ADR 3 本を参照
- M9 LoRA 行 (line ~146) に "前提: L6 ADR1 採用 (c) hybrid、M8 spike 結果" を追記
- L6 完了行 (docs) を milestone 表に追加

### Step 4 — Review + PR
- 3 ADR を読み直し、llm-inference / persona-erre / architecture-rules Skill との不整合なしを確認
- `git diff --stat main...feat/steering-scaling-lora` が `.md` のみを確認 (コード差分があれば revert)
- tasklist.md のチェックボックスを閉じる
- `git push -u origin feat/steering-scaling-lora`
- `gh pr create` — title: `docs(steering): L6 — scaling / LoRA / user-dialogue IF roadmap`
- body: ゴール / 3 ADR の採用要約 / docs-only の strong assertion / 親 D2 への Ref

## 変更対象ファイル一覧

| Path | 変更種別 |
|---|---|
| `.steering/20260424-steering-scaling-lora/design.md` | **新規** |
| `.steering/20260424-steering-scaling-lora/decisions.md` | **新規** (3 ADR) |
| `.steering/20260424-steering-scaling-lora/tasklist.md` | 既存 checkbox を順次閉じる + L14 の "gpt-oss:20b MoE" を `qwen3:8b` に修正 |
| `.steering/20260418-implementation-plan/MASTER-PLAN.md` | 既存編集 (M8 行追加、M9 前提追記、L6 milestone 行) |

**再利用する既存資産**:
- ADR 書式参照: `.steering/20260424-m7-differentiation-observability/decisions.md` (tight pattern, 3-15 行/決定)
- 親制約参照: 上記ファイル D2 (lines 13-19)
- 依存 Skill: `.claude/skills/{llm-inference,persona-erre,architecture-rules}/SKILL.md`
- M9 LoRA 前提: `.steering/20260418-implementation-plan/MASTER-PLAN.md` L146 付近

## 検証

- `wc -l .steering/20260424-steering-scaling-lora/decisions.md` → 3 ADR × ≤20 行 + header で ~80 行以下想定
- 各 ADR が 5 節 (現状 / 選択肢 / 採用 / 根拠 / 次アクション) を全て持つことを grep 目視
- `git diff --stat origin/main...HEAD` の出力が `.md` 拡張子のみであることを確認 (正規表現チェック: `grep -v '\.md ' → 空)
- `grep -E '(llm-inference|persona-erre|architecture-rules)' .steering/20260424-steering-scaling-lora/decisions.md` で各 Skill 参照が残っていることを確認
- M8 preconditions が各 ADR の「次アクション」節に箇条で列挙されていること

## Out of Scope

- コード変更 (いかなる意味でも) — 親 D2 制約
- 運用予算節 (Ollama 並列 / local-only) — CLAUDE.md + architecture-rules に既記、DRY
- M8 spike task の起票そのもの (preconditions 記述のみ)
- Slice γ の設計 / live acceptance (別 task dir)

## Post-Plan フロー

Plan 承認後:
1. 本 plan と `.steering/20260424-steering-scaling-lora/{requirement,tasklist}.md` を参照しながら Step 0 → 4 を順に実行
2. context 使用率 30% 未満の想定 (docs のみ、軽量) なので `/clear` せず一気に完走可
3. PR 作成後は merge をユーザー確認に委ね、merge 後に `project_m7_beta_merged.md` memory を「L6 完了、次は β live-acceptance (G-GEAR 必要) or γ」に更新
