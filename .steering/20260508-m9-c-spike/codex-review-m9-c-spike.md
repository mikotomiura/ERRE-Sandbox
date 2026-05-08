Reading prompt from stdin...
OpenAI Codex v0.125.0 (research preview)
--------
workdir: /Users/johnd/ERRE-Sand Box
model: gpt-5.5
provider: openai
approval: never
sandbox: workspace-write [workdir, /tmp, $TMPDIR, /Users/johnd/.codex/memories] (network access enabled)
reasoning effort: xhigh
reasoning summaries: none
session id: 019e06fd-3a7e-7df2-9274-d18678bc301e
--------
user
# Codex independent review request — m9-c-spike (bounded Kant LoRA spike on SGLang)

## 役割

あなたは ERRE-Sandbox プロジェクトの **independent reviewer**。Claude が起草
した m9-c-spike 設計案 (v1 + v2 + comparison v3) を **同一モデル 1 発生成の
構造的バイアス** から救出するために招かれている。Verdict + 優先度付き finding
+ web-search-based prior art 引用で reply してほしい。要約禁止、verbatim 保存
される。

## 報告フォーマット (厳守)

1. **Verdict**: 一行 — `APPROVE` / `ADOPT-WITH-CHANGES` / `REJECT`
2. **HIGH** finding (must reflect before merge): `[HIGH-N] title` +
   ≥3 行 rationale + 引用 (URL or paper)
3. **MEDIUM** finding (decisions.md ADR 反映): `[MEDIUM-N]`
4. **LOW** finding (blockers.md defer 可): `[LOW-N]`
5. **Prior art summary** (web search 必須): 下記 §「Prior art 必須調査」全件
6. **Closing note**: v3 hybrid を採用すべきか / v1 / v2 / 別案

## Mission の再掲

`src/erre_sandbox/inference/sglang_adapter.py` 新設 + `src/erre_sandbox/training/`
module 新設で、Kant 1 persona の bounded LoRA spike を実行可能にする。本 spike
は **non-authoritative** (M9-B `decisions.md` 第3の道 ADR、PR #127 merged)、
評価系構築中に LoRA 学習・adapter swap・runtime 技術リスクを早期検出する目的。

5 deliverable:

1. SGLang LoRA endpoint 動作確認 (`--enable-lora` + `/load_lora_adapter`)
2. **adapter swap latency** 実測 (>500ms は DB3 vLLM fallback fire)
3. **N=3 同時 request throughput** 実測
4. M5 resonance / ERRE FSM regression 確認
5. adapter swap runbook (DB8) 起草 (本 spike 完了後)

## 必読 reference files (本 prompt の review 対象)

### Claude 設計案 (3 件)

- `.steering/20260508-m9-c-spike/m9-c-spike-design-v1.md` (infrastructure-first
  + Kant 1 persona)
- `.steering/20260508-m9-c-spike/m9-c-spike-design-v2.md` (fail-fast +
  multi-persona)
- `.steering/20260508-m9-c-spike/m9-c-spike-design-comparison.md` (v3 hybrid:
  Phase α mock-LoRA + Phase β Kant 1 rank=8)
- `.steering/20260508-m9-c-spike/requirement.md`

### ADR 制約 (絶対遵守)

- `.steering/20260430-m9-b-lora-execution-plan/decisions.md` DB1-DB11 +
  第3の道 ADR (M9-B)
- `.steering/20260430-m9-eval-system/decisions.md` ME-1〜ME-15 (M9-eval)
- `.steering/20260430-m9-eval-system/codex-review-p4a.md` (前回 Codex review、
  HIGH 4 / MEDIUM 5 / LOW 3 全反映済)

### 既存 infrastructure (流用先)

- `src/erre_sandbox/inference/ollama_adapter.py` —
  `OllamaChatClient.chat(messages, *, sampling, model=None) -> ChatResponse`
  API 雛形、`OllamaUnavailableError` の単一エラー型統合 pattern
- `src/erre_sandbox/evidence/eval_store.py::connect_training_view` —
  `RawTrainingRelation` 経由で raw_dialog rows を `ALLOWED_RAW_DIALOG_KEYS`
  projection で取得 (DB5 contract)
- `src/erre_sandbox/contracts/eval_paths.py::ALLOWED_RAW_DIALOG_KEYS` — DB5
  allow-list (現状 `individual_layer_enabled` 未追加、DB11 follow-up は別タスク)
- `src/erre_sandbox/schemas.py::EpochPhase` (L254、enum: AUTONOMOUS /
  Q_AND_A / EVALUATION) — training-eligible 判定の正しい field 名
- 既存 spike 前例: `.steering/20260420-m5-llm-spike/`

## v3 hybrid の要点 (review 対象)

| 項目 | v3 commitment |
|---|---|
| Phase 構造 | Phase α (mock-LoRA infrastructure proof、data-independent、即実行可) + Phase β (P3 golden baseline 完了 trigger で Kant 1 persona real training) |
| Spike scope | Kant 1 persona (M9-B 第3の道 ADR 逐語)、3 persona batch は M9-C-adopt territory に defer |
| Base model | qwen3:8b |
| Quantization | QLoRA NF4 (DB1 default) |
| Library | PEFT (DB2 暫定、final は M9-C-adopt) |
| Adapter rank | rank=8 (M9-C-adopt 統一 spike continuity) |
| Serving | SGLang `--enable-lora` + `/load_lora_adapter` REST (DB3) |
| Mock-LoRA | random-init or HF hub borrow weight、`tools/spike/build_mock_lora.py` に隔離 |
| Training data minimum (Phase β) | P3 golden baseline 完了後の Kant 部分 ~2500 turn |
| Adapter swap latency target | <500ms (>500ms は DB3 re-open / vLLM fallback) |
| VRAM 予算 (G-GEAR RTX 5060 Ti 16GB) | training peak ~9.7-10.2GB、headroom ~5.8GB |
| code module 配置 | `inference/sglang_adapter.py` 新設、`training/` 新設、`tools/spike/build_mock_lora.py` 隔離 |

## Prior art 必須調査 (web search 強制、verbatim 引用)

以下 8 件全件で literature 引用を伴う finding を出してほしい。1 件でも skip
したら REJECT 扱い。

1. **SGLang `--enable-lora` 最新 stability** (v0.3+ multi-LoRA / dynamic
   load/unload / pinned adapters / overlap loading)
   - v0.3 / v0.4 / v0.5 / v0.6 のうち current released の changelog 確認
   - `/load_lora_adapter` / `/unload_lora_adapter` / `/list_lora_adapters`
     REST endpoint の actual path / payload schema
   - SGLang v0.3+ がドキュメントしているのは確かに **multi-LoRA stable** か
     (Codex P4a HIGH-3 で確認済の認識を verify)

2. **PEFT QLoRA NF4 vs 8-bit on consumer 16GB GPU**
   - bitsandbytes NF4 vs int8 の VRAM benchmark
   - gradient_checkpointing 採用での VRAM 削減効果 (training time trade-off)
   - Qwen3-8B + LoRA rank=8 での typical training VRAM peak

3. **LoRA training minimum data size for persona-conditional adaptation**
   (2024-2026 prior art)
   - rank=4 vs rank=8 で何 example が adequate か
   - persona-conditional fine-tune の literature (Salecha 2024、Anthropic
     persona vector research、Huang et al.、Tan et al. 等)
   - ~2500 turn (Kant 部分) で sufficient か

4. **SGLang vs vLLM v0.6+ multi-LoRA performance comparison**
   - throughput / latency / cold start の benchmark (2024-2026)
   - DB3 v1/v2 が stale だった事実を踏まえ、current state を再確認
   - vLLM `--enable-lora` の status

5. **LoRA adapter format conversion (PEFT safetensors → SGLang weight format)**
   - PEFT 標準 safetensors を SGLang `--lora-paths` が直接受付するか
   - 変換 script が必要なら、existing tooling (例: `lora_adapter_converter`
     等) があるか
   - undocumented なら自前 conversion の妥当性

6. **Mock-LoRA random-init weight が SGLang `/load_lora_adapter` で受付されるか**
   - PEFT format validation の strictness
   - random init で base model の generation が破綻しないか (sanity)
   - mock-LoRA を infrastructure proof tool として使う prior art

7. **adapter swap latency threshold 500ms の operations 根拠**
   - production LLM serving での adapter swap latency budget
   - SGLang documented swap latency benchmark
   - >500ms threshold が DB3 fallback fire 条件として適切か

8. **N=3 同時 request collapse 検出 protocol**
   - throughput / latency p99 / queue depth の measurement framework
   - SGLang `--max-running-requests` での N=3 設定の典型 pattern
   - collapse 判定の operational definition

## review で必ず check してほしい質問群

### Phase α (Mock-LoRA) 関連

- Q-α1: random-init or HF hub borrow weight が SGLang format validation を
  pass するか
- Q-α2: mock-LoRA を `tools/spike/` に隔離する設計の妥当性 (production code
  外、誤起動防止)
- Q-α3: Phase α が data-independent に **deliverable 1-4 全件** を early ship
  できるか (latency / throughput / FSM regression の判定条件)
- Q-α4: Phase α で >500ms latency が観測されたら直ちに DB3 vLLM fallback fire
  すべきか、それとも Phase β real training 後に再判定か

### Phase β (Real training) 関連

- Q-β1: rank=8 が persona-conditional adaptation に sufficient か (prior art
  2024-2026)
- Q-β2: Kant ~2500 turn (P3 golden baseline 完了後) で sufficient training
  data か、もっと必要か
- Q-β3: training/serving 同 G-GEAR で run する dual-machine workflow の
  adapter format 共有が clean か
- Q-β4: gradient_checkpointing 採用で VRAM 9.7-10.2GB → 7.5-8GB 削減の
  trade-off 妥当性

### SGLang serving 関連

- Q-S1: SGLang `--enable-lora` + `/load_lora_adapter` の current released
  version で multi-LoRA stable か (v0.5 / v0.6 等 specific version pin)
- Q-S2: PEFT safetensors → SGLang weight format conversion path の
  documented 有無
- Q-S3: SGLang `--max-running-requests` で N=3 の throughput collapse 検出
  protocol
- Q-S4: pinned adapters の M5 resonance / ERRE FSM 経路への影響

### VRAM 関連

- Q-V1: RTX 5060 Ti 16GB で QLoRA NF4 8B + rank=8 + training gradient ~9.7-10.2GB
  の予算妥当性 (実測ベンチマーク)
- Q-V2: gradient_checkpointing で 7.5-8GB に下げる trade-off (training time
  +20-30%)
- Q-V3: 5.8GB headroom が CUDA fragmentation / long-context generation の
  overhead を吸収できるか

### 設計全体

- Q-G1: v3 (Phase α + Phase β) が v1 (full real spike) + v2 (mock + 3 persona)
  の structural bias を残していないか (independent reviewer 視点)
- Q-G2: M9-B 第3の道 ADR の "bounded, non-authoritative single-persona Kant
  LoRA spike" との整合 (Phase α 追加が ADR 文言を逸脱しないか)
- Q-G3: DB3 fallback 条件 trigger (>500ms latency / N=3 collapse / FSM
  regression) のうち single vs composite で fire するか
- Q-G4: M9-eval P3 golden baseline 完了見込みが大幅遅延した場合の Phase β
  contingency plan
- Q-G5: 本 spike 完了後の DB8 adapter swap runbook 起草 timing と内容

## 出力先

verdict + finding は **そのまま raw text** で reply。Claude が
`.steering/20260508-m9-c-spike/codex-review-m9-c-spike.md` に **verbatim 保存**
する (要約禁止)。

## 工数 expectation

- web search 8 件全件 + finding 起票で **30-45 分**、token 予算 ~150K-200K
  程度を想定 (`.codex/budget.json` の per-invocation max 200K 内)

## 最後に

直近 6 連続の Codex review (P3a-finalize / Phase 2 run0 / CLI partial-fix /
run1 calibration / ME-9 trigger / P4a Tier B) で Claude solo 検出不能の HIGH
を毎回切り出してきた empirical 実績がある。本 review でも同質の補正を期待
する。Adopt-with-changes が default expected verdict。

hook: SessionStart
hook: SessionStart Completed
hook: UserPromptSubmit
hook: UserPromptSubmit Completed
codex
I’ll handle this as an ERRE workflow review and will verify the SGLang/QLoRA/LoRA-serving assumptions against current external sources before issuing the verdict. I’m starting with the workflow instructions and the required steering files so the review is grounded in the actual ADR constraints.
exec
/bin/zsh -lc "sed -n '1,220p' .agents/skills/project-status/SKILL.md" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "sed -n '1,240p' .agents/skills/erre-workflow/SKILL.md" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "sed -n '1,220p' .agents/skills/architecture-rules/SKILL.md" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
---
name: project-status
description: >
  プロジェクトの現在の状態をリアルタイムで取得する。
  作業を始める前・コンテキストが分からなくなった時・進捗を確認したい時・
  最近の変更を把握したい時に使う。git 状態・最近のコミット・
  構築フェーズの進捗 (.steering/_setup-progress.md)・未対応 TODO・
  変更ファイル統計を一括で取得する。セッション開始時の状況把握にも使える。
---

# Project Status

このスキルは現在のプロジェクト状態を動的に取得します。

## 現在の git 状態

!`git status --short`

## 最近のコミット (10 件)

!`git log --oneline -10 2>/dev/null || echo "(no commits yet)"`

## 現在のブランチ

!`git branch --show-current`

## 構築フェーズ進捗

!`grep -E "^\- \[" .steering/_setup-progress.md 2>/dev/null | head -20 || echo "(progress file not found)"`

## 未対応 TODO の数

!`grep -r "TODO\|FIXME\|HACK\|XXX" src/ tests/ 2>/dev/null | wc -l`

## 変更ファイルの統計 (直近コミットとの差分)

!`git diff --stat HEAD 2>/dev/null || echo "(no HEAD yet)"`

## 最近変更されたファイル (24 時間以内)

!`find src/ tests/ -name "*.py" -newer .git/index -mtime -1 2>/dev/null | head -10`

## Skills ディレクトリ

!`ls .agents/skills/ 2>/dev/null || echo "(no skills yet)"`

## あなたのタスク

上記の動的データを分析し、以下を報告してください:

1. **現状サマリ** — 現在のフェーズと進捗を 1-2 行で
2. **進行中の作業** — 未コミットの変更や直近の変更ファイルから何が進んでいるか
3. **注意すべき点** — 多数の未コミット変更、TODO の偏り、進捗ファイルとの乖離など
4. **推奨される次のアクション** — 何を優先すべきか (setup フェーズであればどのコマンドを次に実行すべきか)

レポートは簡潔に。詳細は必要に応じてユーザーが追加で質問する。

 succeeded in 0ms:
---
name: architecture-rules
description: >
  レイヤー依存方向・インポート制約・GPL/クラウド API 禁止ルール。
  src/erre_sandbox/ 配下に新しいファイルを追加する・インポートを変更する・
  新しい依存ライブラリを追加する時に必須参照。
  schemas.py / inference/ / memory/ / cognition/ / world/ / ui/ / erre/
  のどのモジュールにコードを置くか判断する時、
  import 文が依存方向に違反していないか確認する時、
  pip install / uv add でライブラリを追加する時に自動召喚される。
  GPL ライブラリ (bpy 等) を src/erre_sandbox/ に import する禁止も含む。
---

# Architecture Rules

## このスキルの目的

ERRE-Sandbox のアーキテクチャは 2 拠点 (G-GEAR + MacBook) × 5 レイヤー構成。
インポートの依存方向を守ることで、将来のバックエンド差し替え (Qdrant、gRPC 等) を
最小の変更で実現できるようにする。また、GPL ライブラリとクラウド API の混入を防ぐ。

## レイヤー依存方向（絶対厳守）

```
world/ → cognition/ → inference/
                    → memory/
                          ↓
ui/ ──────────→ schemas.py ← (全モジュールが参照)
```

| モジュール | 依存先 | 依存禁止 |
|---|---|---|
| `schemas.py` | なし (最下層) | すべての src モジュール |
| `inference/` | `schemas.py` のみ | `memory/`, `cognition/`, `world/`, `ui/` |
| `memory/` | `schemas.py` のみ | `inference/`, `cognition/`, `world/`, `ui/` |
| `cognition/` | `inference/`, `memory/`, `schemas.py`, `erre/` | `world/`, `ui/` |
| `world/` | `cognition/`, `schemas.py` | `ui/`, `erre/` |
| `ui/` | `schemas.py` のみ | `inference/`, `memory/`, `cognition/`, `world/` |
| `erre/` | `schemas.py`, `inference/`, `memory/` | `cognition/`, `world/`, `ui/` |

### 依存方向の確認方法

```bash
# ui/ が inference/ を import していないか確認
grep -r "from erre_sandbox.inference" src/erre_sandbox/ui/
grep -r "from erre_sandbox.memory"    src/erre_sandbox/ui/

# schemas.py が他モジュールを import していないか確認
grep "from erre_sandbox\." src/erre_sandbox/schemas.py
```

## 絶対禁止ルール

### 禁止 1: GPL ライブラリを src/erre_sandbox/ に import

Blender の `bpy` は GPL-2+ のため、import するコードが GPL 派生物になる。
Apache-2.0 OR MIT デュアルライセンスと矛盾するため **絶対に混入させない**。

```python
# ❌ 絶対禁止
import bpy                          # GPL viral — Apache/MIT と矛盾
from bpy.types import Object        # 同上
```

将来 Blender 連携が必要になった場合 → `erre-sandbox-blender/` を別パッケージ (GPL-3) で分離。

### 禁止 2: クラウド LLM API を必須依存にする

OpenAI / Anthropic / Google の API は予算ゼロ制約に反する。

```python
# ❌ 禁止
import openai                       # 有料 API
from anthropic import Anthropic     # 有料 API
```

ローカル推論 (SGLang / Ollama / llama.cpp) のみ使用。

### 禁止 3: ui/ から inference/ / memory/ を直接 import

UI は WebSocket 経由で G-GEAR と通信する。Python の import で直接呼ばない。

```python
# ❌ 禁止 — ui/ から memory/ を直接呼ぶ
from erre_sandbox.memory.store import MemoryStore  # ui/ 内に書いてはいけない

# ✅ 正しい — WebSocket 経由
from erre_sandbox.schemas import ControlEnvelope   # スキーマのみ OK
```

### 禁止 4: schemas.py から他の src モジュールを import

`schemas.py` は最下層。循環参照を防ぐために依存なしを厳守。

```python
# ❌ 禁止
from erre_sandbox.memory.store import MemoryStore  # schemas.py 内に書いてはいけない

# ✅ 正しい — 型ヒントのみなら TYPE_CHECKING で遅延
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from erre_sandbox.memory.store import MemoryStore
```

## 新しいファイルの配置判断フロー

```
新しい .py ファイルを作る
    │
    ├─ LLM 推論関連?           → inference/
    ├─ 記憶・検索・埋め込み?   → memory/
    ├─ 認知サイクル・反省?     → cognition/
    ├─ ワールド・物理・ゾーン? → world/
    ├─ WebSocket クライアント・Godot 連携? → ui/
    ├─ ERRE パイプライン DSL?  → erre/
    └─ Pydantic スキーマ定義?  → schemas.py に追記 (ファイルは作らない)
```

## 依存ライブラリ追加の基準

新しいライブラリを `uv add` する前に全項目確認:

- [ ] 既存の依存で代替できないか?
- [ ] ライセンスは Apache-2.0 / MIT / BSD と互換か? (**GPL は本体に入れない**)
- [ ] メンテナンスが活発か? (直近 6 ヶ月以内にリリースがあるか)
- [ ] セキュリティ脆弱性はないか?
- [ ] 予算ゼロに抵触しないか? (有料 SaaS の必須依存は不可)

## チェックリスト

- [ ] 新しいファイルが正しいレイヤー (`inference/`, `memory/` 等) に置かれているか
- [ ] インポートが依存方向に違反していないか (`grep` で確認)
- [ ] `schemas.py` から他の src モジュールを import していないか
- [ ] `ui/` から `inference/` や `memory/` を直接 import していないか
- [ ] GPL ライブラリが `src/erre_sandbox/` に入っていないか
- [ ] クラウド LLM API が必須依存になっていないか
- [ ] 新しい依存のライセンスが Apache-2.0/MIT/BSD と互換か

## 補足資料

- `decision-tree.md` — 「どのモジュールに書くべきか」の判断フロー詳細版

## 関連する他の Skill

- `python-standards` — インポート順序・相対 vs 絶対インポートのルール
- `implementation-workflow` — Step B (既存パターン調査) でこの Skill を参照
- `llm-inference` — inference/ 内のモデル設定と VRAM 管理
- `persona-erre` — ペルソナ YAML 設計と ERRE モード定義
- `godot-gdscript` — Godot シーン・GDScript のコーディング規約と WebSocket 通信
- `blender-pipeline` — Blender アセットパイプラインの GPL 分離の具体的手順

 succeeded in 0ms:
---
name: erre-workflow
description: >
  ERRE-Sandbox task workflow for Codex. Use when starting, designing, implementing,
  reviewing, or finishing repository work; when the user mentions /start-task,
  /add-feature, /fix-bug, /refactor, /reimagine, /review-changes, or /finish-task;
  or when .steering records, Codex setup, task plans, or implementation handoffs are needed.
---

# ERRE Workflow

This is the Codex-native replacement for the Claude slash-command workflow. Claude command
files in `.claude/commands/` are reference material only; Codex should execute the workflow
through normal tool use, `.steering/` records, skills, hooks, and custom agents.

## Quick Start

1. Read `AGENTS.md`, `docs/development-guidelines.md`, and the relevant domain skill.
2. Create or update `.steering/YYYYMMDD-task-name/` before implementation work:
   `requirement.md`, `design.md`, and `tasklist.md` are required.
3. For design-heavy work, keep implementation paused until a plan is accepted. If the task
   has multiple plausible designs, perform a reimagine pass before editing source files.
4. Implement in small steps, updating `tasklist.md` as work completes.
5. Verify with focused checks first, then the documented full checks when feasible.
6. Finish by reviewing the diff and recording any decisions or limitations.

Use subagents only when the user explicitly asks for delegation or parallel agent work.
When they do, prefer the project-scoped agents in `.codex/agents/`.

## Task Start

Create `.steering/YYYYMMDD-task-name/` with:

- `requirement.md`: background, goal, scope, out of scope, acceptance criteria.
- `design.md`: approach, changed areas, compatibility, test strategy, rollback.
- `tasklist.md`: checkboxes at roughly 30-minute granularity.
- `decisions.md`: only for meaningful tradeoffs or policy choices.
- `blockers.md`: only when blocked or carrying deferred risk.

Use the current local date in `YYYYMMDD`. Prefer a short kebab-case task name.

## Implementation Flows

- **Feature**: read existing patterns, document the design, implement narrowly, add tests or
  verification proportional to risk, update docs when behavior changes.
- **Bug fix**: reproduce or explain the failure, record root cause, add or identify a
  regression check when feasible, then make the smallest defensible fix.
- **Refactor**: establish current checks first, preserve behavior, change in small steps,
  and avoid mixing feature or bug-fix work into the same task.

For source edits under `src/erre_sandbox/`, always consider:

- `architecture-rules` for layer direction and GPL/cloud API constraints.
- `python-standards` for Python style.
- `error-handling` when async, retry, timeout, WebSocket, sqlite, or LLM fallback behavior changes.
- `test-standards` when adding or changing tests.

## Reimagine

Use this for architecture, public interfaces, difficult bugs, and designs with multiple
credible approaches:

1. Save the first plan as `design-v1.md`.
2. Re-read only `requirement.md` and produce a fresh alternative in `design.md`.
3. Compare the two in `design-comparison.md`.
4. Choose v1, v2, or a hybrid and record the reason in `decisions.md`.

Do not use reimagine after implementation has already created side effects that would need
manual rollback.

## Review And Finish

Before final delivery:

- Run focused checks for touched areas.
- Run `uv run ruff check src tests`, `uv run ruff format --check src tests`,
  `uv run mypy src`, and `uv run pytest` when feasible.
- Review `git diff` for unrelated changes and do not revert user work.
- Update `tasklist.md` and `design.md` with what actually happened.
- Mention skipped checks or residual risk in the final response.

Do not commit unless the user asks. If committing, use `git-workflow`.

codex
Using `$erre-workflow` for the review path, plus `architecture-rules` because the proposal creates new `inference/` and `training/` modules. I’m also checking the project state so I don’t accidentally review against stale or unrelated local changes.
exec
/bin/zsh -lc 'git status --short' in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
?? .steering/20260508-m9-c-spike/
?? data/eval/calibration/

exec
/bin/zsh -lc 'git log --oneline -10' in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc 'rg --files .steering/20260508-m9-c-spike .steering/20260430-m9-b-lora-execution-plan .steering/20260430-m9-eval-system src/erre_sandbox/inference src/erre_sandbox/evidence src/erre_sandbox/contracts src/erre_sandbox | head -200' in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
8fafe61 Merge pull request #148 from mikotomiura:feat/m9-eval-p4a-tier-b
52bd996 feat(evidence): P4a Tier B — Vendi / IPIP-50 / Big5 ICC + eval_store helper
a368233 Merge pull request #147 from mikotomiura:docs/m9-eval-p4a-launch-prompt-2026-05-08
7797b2e docs(m9-eval): Mac P4a Tier B launch prompt for next session
dbd480b Merge pull request #146 from mikotomiura:feat/m9-eval-p5-bootstrap-ci-hardening
f86852d feat(evidence): P5 hardening — block-length auto-estimation + cluster-only mode
ed9a63d Merge pull request #145 from mikotomiura:docs/m9-b-individual-layer-manifest-addendum-2026-05-08
f5f8ac1 docs(m9-b): DB11 ADR — cognition deepening contamination prevention (PR #144 follow-up)
e641f8d Merge pull request #144 from mikotomiura:docs/cognition-deepen-decision-2026-05-08
a05dfa8 docs: cognition-deepening 7-point proposal final decision (3-source synthesis)

 succeeded in 0ms:
src/erre_sandbox/inference/ollama_adapter.py
src/erre_sandbox/inference/sampling.py
src/erre_sandbox/inference/__init__.py
src/erre_sandbox/evidence/bootstrap_ci.py
src/erre_sandbox/evidence/golden_baseline.py
src/erre_sandbox/__main__.py
src/erre_sandbox/inference/ollama_adapter.py
src/erre_sandbox/inference/sampling.py
src/erre_sandbox/inference/__init__.py
src/erre_sandbox/schemas.py
src/erre_sandbox/cognition/state.py
src/erre_sandbox/cognition/parse.py
src/erre_sandbox/cognition/_trait_antagonism.py
src/erre_sandbox/cognition/relational.py
src/erre_sandbox/cognition/belief.py
src/erre_sandbox/cognition/__init__.py
src/erre_sandbox/cognition/prompting.py
src/erre_sandbox/cognition/importance.py
src/erre_sandbox/cognition/reflection.py
src/erre_sandbox/cognition/cycle.py
.steering/20260508-m9-c-spike/decisions.md
.steering/20260508-m9-c-spike/m9-c-spike-design-v1.md
.steering/20260508-m9-c-spike/design.md
.steering/20260508-m9-c-spike/requirement.md
.steering/20260508-m9-c-spike/codex-review-prompt-m9-c-spike.md
.steering/20260508-m9-c-spike/m9-c-spike-design-comparison.md
.steering/20260508-m9-c-spike/blockers.md
.steering/20260508-m9-c-spike/tasklist.md
.steering/20260508-m9-c-spike/codex-review-m9-c-spike.md
.steering/20260508-m9-c-spike/m9-c-spike-design-v2.md
src/erre_sandbox/cli/eval_run_golden.py
src/erre_sandbox/cli/baseline_metrics.py
src/erre_sandbox/cli/eval_audit.py
src/erre_sandbox/cli/__init__.py
src/erre_sandbox/cli/scaling_metrics.py
src/erre_sandbox/cli/export_log.py
src/erre_sandbox/evidence/tier_b/ipip_neo.py
src/erre_sandbox/evidence/tier_b/vendi.py
src/erre_sandbox/evidence/tier_b/big5_icc.py
src/erre_sandbox/evidence/tier_b/__init__.py
src/erre_sandbox/evidence/bootstrap_ci.py
src/erre_sandbox/evidence/golden_baseline.py
src/erre_sandbox/evidence/capture_sidecar.py
src/erre_sandbox/evidence/__init__.py
src/erre_sandbox/evidence/eval_store.py
src/erre_sandbox/contracts/eval_paths.py
src/erre_sandbox/contracts/__init__.py
src/erre_sandbox/contracts/thresholds.py
src/erre_sandbox/world/tick.py
src/erre_sandbox/world/zones.py
src/erre_sandbox/world/physics.py
src/erre_sandbox/world/__init__.py
src/erre_sandbox/__init__.py
src/erre_sandbox/evidence/tier_b/ipip_neo.py
src/erre_sandbox/evidence/tier_b/vendi.py
src/erre_sandbox/evidence/tier_b/big5_icc.py
src/erre_sandbox/evidence/tier_b/__init__.py
src/erre_sandbox/evidence/capture_sidecar.py
src/erre_sandbox/evidence/__init__.py
src/erre_sandbox/evidence/eval_store.py
.steering/20260430-m9-b-lora-execution-plan/design-final.md
.steering/20260430-m9-b-lora-execution-plan/decisions.md
.steering/20260430-m9-b-lora-execution-plan/design-v2.md
.steering/20260430-m9-b-lora-execution-plan/codex-review.md
.steering/20260430-m9-b-lora-execution-plan/design.md
.steering/20260430-m9-b-lora-execution-plan/research-evaluation-metrics.md
.steering/20260430-m9-b-lora-execution-plan/requirement.md
.steering/20260430-m9-b-lora-execution-plan/codex-review-prompt.md
.steering/20260430-m9-b-lora-execution-plan/blockers.md
.steering/20260430-m9-b-lora-execution-plan/design-v1.md
.steering/20260430-m9-b-lora-execution-plan/design-comparison.md
.steering/20260430-m9-b-lora-execution-plan/tasklist.md
src/erre_sandbox/evidence/metrics.py
src/erre_sandbox/evidence/scaling_metrics.py
src/erre_sandbox/contracts/eval_paths.py
src/erre_sandbox/contracts/__init__.py
src/erre_sandbox/contracts/thresholds.py
src/erre_sandbox/evidence/tier_a/empath_proxy.py
src/erre_sandbox/evidence/tier_a/novelty.py
src/erre_sandbox/evidence/tier_a/nli.py
src/erre_sandbox/evidence/tier_a/__init__.py
src/erre_sandbox/evidence/tier_a/burrows.py
src/erre_sandbox/evidence/tier_a/mattr.py
src/erre_sandbox/evidence/tier_a/empath_proxy.py
src/erre_sandbox/evidence/tier_a/burrows.py
src/erre_sandbox/memory/retrieval.py
src/erre_sandbox/memory/__init__.py
src/erre_sandbox/memory/embedding.py
src/erre_sandbox/memory/store.py
src/erre_sandbox/evidence/tier_a/novelty.py
src/erre_sandbox/evidence/tier_a/nli.py
src/erre_sandbox/evidence/tier_a/__init__.py
.steering/20260430-m9-eval-system/pr-body-p3a.md
.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md
src/erre_sandbox/bootstrap.py
src/erre_sandbox/integration/dialog_turn.py
src/erre_sandbox/integration/__init__.py
src/erre_sandbox/integration/acceptance.py
src/erre_sandbox/integration/protocol.py
src/erre_sandbox/integration/dialog.py
src/erre_sandbox/integration/gateway.py
src/erre_sandbox/integration/metrics.py
src/erre_sandbox/integration/scenarios.py
src/erre_sandbox/evidence/reference_corpus/vectors.json
src/erre_sandbox/evidence/reference_corpus/_build_vectors.py
src/erre_sandbox/evidence/reference_corpus/__init__.py
src/erre_sandbox/evidence/reference_corpus/loader.py
src/erre_sandbox/evidence/reference_corpus/function_words.py
src/erre_sandbox/evidence/reference_corpus/_provenance.yaml
src/erre_sandbox/evidence/metrics.py
src/erre_sandbox/evidence/scaling_metrics.py
src/erre_sandbox/evidence/tier_a/mattr.py
src/erre_sandbox/erre/fsm.py
src/erre_sandbox/erre/sampling_table.py
src/erre_sandbox/erre/__init__.py
src/erre_sandbox/evidence/reference_corpus/raw/rikyu_ja.txt
src/erre_sandbox/evidence/reference_corpus/raw/nietzsche_de.txt
src/erre_sandbox/evidence/reference_corpus/raw/kant_de.txt
src/erre_sandbox/evidence/reference_corpus/__init__.py
src/erre_sandbox/evidence/reference_corpus/_build_vectors.py
.steering/20260430-m9-eval-system/codex-review-prompt-p4a.md
.steering/20260430-m9-eval-system/g-gear-p3a-rerun-prompt.md
.steering/20260430-m9-eval-system/design-comparison.md
.steering/20260430-m9-eval-system/g-gear-phase-a-failure.md
.steering/20260430-m9-eval-system/tasklist.md
.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt-v2.md
src/erre_sandbox/ui/__init__.py
.steering/20260430-m9-eval-system/codex-review-prompt-natural-gating.md
.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md
.steering/20260430-m9-eval-system/blockers.md
.steering/20260430-m9-eval-system/design-v1.md
.steering/20260430-m9-eval-system/codex-review-natural-gating-v2.md
.steering/20260430-m9-eval-system/g-gear-p3a-prompt.md
.steering/20260430-m9-eval-system/codex-review-p4a.md
.steering/20260430-m9-eval-system/g-gear-p3a-rerun-prompt-v2.md
.steering/20260430-m9-eval-system/design-final.md
.steering/20260430-m9-eval-system/decisions.md
.steering/20260430-m9-eval-system/design-natural-gating-fix-v2.md
.steering/20260430-m9-eval-system/p4a-tier-b-design-final.md
.steering/20260430-m9-eval-system/design-natural-gating-fix.md
.steering/20260430-m9-eval-system/codex-review-p3a-finalize.md
.steering/20260430-m9-eval-system/cli-fix-and-audit-design.md
.steering/20260430-m9-eval-system/codex-review.md
.steering/20260430-m9-eval-system/mac-p4a-tier-b-launch-prompt.md
.steering/20260430-m9-eval-system/codex-review-step1.md
.steering/20260430-m9-eval-system/codex-review-prompt-phase2-run0-timeout.md
.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md
.steering/20260430-m9-eval-system/codex-review-step1-prompt.md
.steering/20260430-m9-eval-system/g-gear-p3-launch-prompt.md
.steering/20260430-m9-eval-system/codex-review-phase2-run0-timeout.md
.steering/20260430-m9-eval-system/codex-review-low1.md
.steering/20260430-m9-eval-system/requirement.md
.steering/20260430-m9-eval-system/codex-review-prompt-low1.md
.steering/20260430-m9-eval-system/codex-review-prompt-natural-gating-v2.md
.steering/20260430-m9-eval-system/codex-review-natural-gating.md
.steering/20260430-m9-eval-system/codex-review-prompt-p3a-finalize.md
.steering/20260430-m9-eval-system/codex-review-prompt.md
.steering/20260430-m9-eval-system/g-gear-rescue-verify-prompt.md
src/erre_sandbox/evidence/reference_corpus/function_words.py
src/erre_sandbox/evidence/reference_corpus/vectors.json
src/erre_sandbox/evidence/reference_corpus/loader.py
src/erre_sandbox/evidence/reference_corpus/_provenance.yaml
src/erre_sandbox/evidence/reference_corpus/raw/rikyu_ja.txt
src/erre_sandbox/evidence/reference_corpus/raw/nietzsche_de.txt
src/erre_sandbox/evidence/reference_corpus/raw/kant_de.txt
src/erre_sandbox/ui/dashboard/state.py
src/erre_sandbox/ui/dashboard/stub.py
src/erre_sandbox/ui/dashboard/__main__.py
src/erre_sandbox/ui/dashboard/messages.py
src/erre_sandbox/ui/dashboard/__init__.py
src/erre_sandbox/ui/dashboard/html.py
src/erre_sandbox/ui/dashboard/server.py

exec
/bin/zsh -lc "sed -n '1,420p' .steering/20260508-m9-c-spike/m9-c-spike-design-comparison.md" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "sed -n '1,380p' .steering/20260508-m9-c-spike/m9-c-spike-design-v2.md" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
# m9-c-spike — design comparison (v1 vs v2 → hybrid v3 候補)

> v1 (`m9-c-spike-design-v1.md`): infrastructure-first / Kant 1 persona / P3
> 完了待ちで full spike
> v2 (`m9-c-spike-design-v2.md`): fail-fast (mock-LoRA infra proof) +
> diversification (3 persona batch)
>
> 本書は両案を 8 軸で比較し hybrid v3 を提示する。Codex review が起爆。最終
> 解は `m9-c-spike-design-final.md` に記述。

## 軸別比較

### 軸 1. data dependency

| 軸 | v1 | v2 | hybrid v3 |
|---|---|---|---|
| Phase α (infra proof) | 該当なし、P3 待ち | mock-LoRA で 即実行可 | **mock-LoRA で 即実行 (v2 採用)** |
| Phase β (real training) | P3 完了 → Kant 1 persona | P3 完了 → 3 persona batch | **P3 完了 → Kant 1 persona (v1 採用)** |

**v3 selection**: **mock-LoRA Phase α を採用** (data-blocked 時 hedge、本 PR
scope 内で deliverable 1-4 早期 ship 可)。Phase β は Kant 1 persona に戻す
(M9-B 第3の道 ADR continuity)。

### 軸 2. persona scope

| | v1 | v2 | v3 |
|---|---|---|---|
| spike 対象 persona | Kant 1 | Kant + Nietzsche + Rikyū 3 | **Kant 1 (v1)** |
| 3 persona の検討 | M9-C-adopt | 本 spike 内で前倒し | **M9-C-adopt territory に defer** |

**v3 selection**: **Kant 1 persona** 維持 (v1)。M9-B 第3の道 ADR の "bounded,
non-authoritative single-persona Kant LoRA spike" 文言を逐語守る。3 persona
batch は M9-C-adopt 範囲。

### 軸 3. adapter rank

| | v1 | v2 | v3 |
|---|---|---|---|
| rank | rank=8 | rank=4 (multi-persona trade-off) | **rank=8 (v1)** |
| M9-C-adopt 統一 spike との continuity | 整合 | 不整合 | **整合 (v3=v1)** |

**v3 selection**: **rank=8 維持**。M9-C-adopt の "rank=8 統一 spike" と
continuity 確保、本 spike の結果が M9-C-adopt の比較基準として直接使える。

### 軸 4. infrastructure proof timing

| | v1 | v2 | v3 |
|---|---|---|---|
| DB3 fallback 判定材料の早期取得 | P3 完了後 (~weeks) | mock で 即可 | **mock で 即可 (v2)** |
| 早期 unblock value | 低 | 高 | **高** |

**v3 selection**: **mock-LoRA Phase α 採用 (v2)**。Codex P4a 経験で証明された
「**早期検出 = 大幅手戻り防止**」原則。SGLang adapter 機能不全が判明したら
即 vLLM 別タスク fire 可能。

### 軸 5. mock-LoRA の risk

| 観点 | v2 / v3 (mock 採用) |
|---|---|
| SGLang format 拒否リスク | PEFT random-init weight が `/load_lora_adapter` 受付形式に合わない可能性 (Codex 確認必須) |
| quality 誤認リスク | mock を production で誤起動 → DB9 quorum で 100% 排除 (Tier B Vendi で異常 score 検出) |
| infra proof 妥当性 | mock weight でも load/unload mechanism / latency / N=3 同時 / FSM regression は real と同じ → infra proof 成立 |

**v3 selection**: 採用。mock-LoRA を **`tools/spike/` 隔離** (production
`src/` に置かない、誤運用リスク削減)。

### 軸 6. M9-B 第3の道 ADR との整合

| 軸 | v1 | v2 | v3 |
|---|---|---|---|
| ADR 文言 (single-persona Kant) | 完全整合 | 逸脱 (3 persona) | **整合 (v3=v1)** |
| ADR 修正必要性 | 不要 | 必要 (scope 拡張) | **不要** |

**v3 selection**: ADR 整合維持。Phase α (mock-LoRA) は ADR 文言を超えないが、
新規 ADR (CS-N) で本 spike 内 phase 化を justify する必要 (scope 拡張ではなく
phase 内訳)。

### 軸 7. 工数

| | v1 | v2 | v3 |
|---|---|---|---|
| 推定 | 8h | 12h | **11h** (v1 8h + Phase α mock 3h) |
| 早期 unblock value | 低 | 高 | **高** |

**v3 selection**: 11h、Phase α 3h は data-independent で **本 PR 内**または
次セッション初期で完結可、その時点で DB3 fallback 判定材料を確定可能。

### 軸 8. Codex review で v3 を challenge する点

下記を `codex-review-prompt-m9-c-spike.md` に明記:

1. **mock-LoRA の SGLang format compatibility**: random-init or HF hub borrow
   weight で `/load_lora_adapter` 受付するか
2. **rank=8 vs rank=4 の persona expressivity gap**: prior art 2024-2026 で
   何 rank が adequate
3. **adapter swap latency 500ms threshold の妥当性**: 操作上の閾値根拠
4. **N=3 同時 request collapse 検出 protocol**: throughput / latency p99 /
   queue depth 何を測るか
5. **PEFT safetensors → SGLang weight format conversion**: undocumented なら
   自前 conversion script 必要、その妥当性
6. **gradient_checkpointing 採用**: VRAM 9.7-10.2GB を 7.5-8GB に下げる
   trade-off (training time +20-30%)
7. **VRAM headroom 5.8GB の妥当性**: CUDA fragmentation / long-context
   generation で実用上 sufficient か
8. **training data minimum**: P3 完了後 Kant ~2500 turn で sufficient か、
   prior art 確認
9. **dual-machine workflow**: training (HF Transformers) と serving (SGLang)
   が同 G-GEAR 上で run、adapter format 共有が clean か
10. **DB3 fallback 条件 trigger**: >500ms latency / N=3 collapse / FSM
    regression のうち単一 trigger で fallback fire するか、複合か

## v3 hybrid summary (one-paragraph)

**m9-c-spike v3 = Phase α (mock-LoRA infrastructure proof、data-independent、
即実行可、本 PR scope 内 or 次セッション初期で完結) + Phase β (P3 golden
baseline 完了 trigger で Kant 1 persona rank=8 PEFT QLoRA NF4 real training、
SGLang `--enable-lora` + `/load_lora_adapter` 経由で adapter swap latency /
N=3 throughput / FSM regression 実測、DB3 fallback 判定材料生成)**。M9-B
第3の道 ADR (single-persona Kant) と continuity 維持、3 persona batch は
M9-C-adopt territory に defer、rank=8 で M9-C-adopt 統一 spike と continuity。
工数 ~11h (v1 8h + Phase α 3h)。

## 採否判定 matrix

| 軸 | v1 採否 | v2 採否 | v3 採否 |
|---|---|---|---|
| Phase α (mock-LoRA infra proof) | ✗ なし | ✓ あり (v3 と同) | ✓ |
| Phase β persona | ✓ Kant 1 (v3 と同) | ✗ 3 persona (scope 拡張) | ✓ |
| Phase β rank | ✓ rank=8 (v3 と同) | ✗ rank=4 (M9-C-adopt 不整合) | ✓ |
| M9-B 第3の道 ADR 整合 | ✓ 整合 (v3 と同) | ✗ 逸脱 | ✓ |
| 早期 unblock value (Phase α) | ✗ なし | ✓ あり (v3 と同) | ✓ |
| mock 隔離 (`tools/spike/`) | 該当なし | 不明 | ✓ 明示隔離 |
| 工数 | 8h | 12h (v3 11h と近接) | 11h |
| ADR 修正必要性 | 不要 | 必要 | 不要 (新規 CS-N で phase 化 justify) |

v3 が全軸で「最良の選択」を吸収。

## v3 で残す未解決 (Codex 反映後 design-final.md に確定)

- mock-LoRA の SGLang format compatibility 確認結果
- rank=8 で persona-conditional adaptation prior art literature
- adapter swap latency threshold 500ms の literature/operations 根拠
- VRAM 予算実測の必要性 (G-GEAR 実走時に確定)
- dual-machine workflow の adapter format conversion path
- DB3 fallback 条件 (single vs composite trigger)

## v3 effort estimate

| Sub-step | 推定 |
|---|---|
| Phase A: scaffold + requirement.md (済) | 30min |
| Phase B: design-v1.md (済) | 1h |
| Phase C: /reimagine v2 + comparison.md (本書、済) | 1h |
| Phase D: Codex review prompt + execution + 反映 | 1.5h |
| Phase E: design-final + decisions.md ADR | 1h |
| Phase F: tasklist + blockers 整備 | 30min |
| **本セッション合計** | **~5.5h** |
| Phase G: pyproject.toml [training] extras | 30min |
| Phase H: sglang_adapter.py + tests | 2-3h |
| Phase I: mock-LoRA build script + training/ module + prompt builder + dataset + train script + tests | 4h (Phase α 含む、+1h vs v1) |
| Phase J α: G-GEAR mock-LoRA infra proof (data 不要) | 2h |
| Phase J β: G-GEAR real training (P3 完了後): Kant rank=8 PEFT QLoRA + adapter load + latency 実測 | 4-6h |
| Phase K: adapter swap runbook (DB8) + PR | 1h |
| **次セッション以降合計** | **~14-16h** (3 セッション、v1 10-14h より +20%) |

 succeeded in 0ms:
# m9-c-spike — design v2 (`/reimagine` 後、fail-fast + multi-persona 起点)

> **`/reimagine` premise**: v1 を意図的に破棄し、別の出発点から再起草。v1 は
> infrastructure-first + Kant 1 persona + P3 完了待ちで full spike を狙うが、
> **data dependency が外部** (G-GEAR run1 calibration 完了時刻) **に依存**
> という critical risk がある。v2 は **fail-fast (mock-LoRA で infrastructure
> 即検証) + diversification (multi-persona small batch でカバー)** を起点に、
> data-blocked リスクを排除し早期に DB3 fallback 判定材料を得る。

## v2 の基本方針 (v1 との対比)

| 項目 | v1 (infrastructure-first + Kant 1) | v2 (fail-fast + multi-persona) |
|---|---|---|
| 出発点 | bounded Kant spike (M9-B 第3の道 ADR を逐語) | **data-blocked リスク排除 + 早期 fallback 判定** |
| 実走 trigger | P3 golden baseline 完了待ち (~7500 turn) | **2 phase**: ① mock-LoRA で 即 infra 検証 / ② P3 後 multi-persona 実 training |
| persona | Kant 1 のみ | **3 persona (Kant + Nietzsche + Rikyū) rank=4 集合 batch** |
| risk profile | data delay で spike が遅延、fallback 判定材料も遅延 | mock で 即時 fallback 判定可、real training は data 揃い次第 |
| trade-off | M9-B 第3の道 ADR 逐語 (scope 凍結) | scope 拡張 (3 persona、2 phase)、第3の道 ADR を超える |

## 1. Mission (v2、v1 と方向は同じが手段が異なる)

`tier_b/` 完成 (PR #148) で DB9 quorum gate が機能する状態の今、本 spike の
**早期 deliverable** は infrastructure proof。Kant adapter quality は M9-eval
P3 完了後に "real training" phase でつかむ。それまで infrastructure proof は
**mock-LoRA で 即実行** し、DB3 fallback 判定 (>500ms latency / N=3 collapse /
FSM regression) を **data-independent に得る**。

5 deliverable は v1 と同じ:

1. SGLang LoRA endpoint 動作確認
2. adapter swap latency 実測
3. N=3 同時 request throughput 実測
4. M5 resonance / ERRE FSM regression 確認
5. adapter swap runbook (DB8) 起草

ただし v2 では deliverable 1-4 を **mock-LoRA で 即実行可能**、deliverable
5 (runbook) は real training data 込みで後段で起草。

## 2. v2 の 2 phase 構造

### Phase α: Mock-LoRA infrastructure proof (data 不要、即実行可)

- 既存 PEFT で **dummy weights** (random init or 既存 HuggingFace LoRA hub
  から借用) を `safetensors` 形式で保存
- SGLang `--enable-lora` 起動、`/load_lora_adapter` でこの mock を load
- adapter swap latency を実測 (mock weight でも load/unload mechanism は real
  と同じ)
- N=3 同時 request で throughput 確認 (mock adapter ×3 を pinned で運用)
- M5 resonance / ERRE FSM が SGLang LoRA 経路で破綻なし確認

→ **deliverable 1-4 を data-independent に early ship**、DB3 fallback 判定材料
を確定 (>500ms なら vLLM 別タスク fire、<500ms なら SGLang-first 確定)

### Phase β: Multi-persona real training (P3 完了後)

- P3 golden baseline 採取完了 (3 persona × 5 run × 500 turn = 7500 turn) を
  trigger
- **3 persona (Kant + Nietzsche + Rikyū)** を rank=4 (rank=8 ではない、
  data 量から trade-off) で集合 batch 学習
- 各 persona ~2500 turn で training data 量を確保
- M9-eval Tier B (Vendi / Big5 ICC / Burrows Δ) で persona-conditional
  quality signal を測定 → DB9 quorum 判定材料

## 3. v2 commit (推奨初期方向)

| 項目 | v2 commit | 根拠 |
|---|---|---|
| Phase α実走 | mock-LoRA で **即実行**、本 PR scope 内で完結可 | data delay リスク排除 |
| Phase β実走 | 3 persona rank=4 集合 batch、P3 完了後 | data 量と persona coverage の trade-off |
| Base model | qwen3:8b (v1 と同じ) | MASTER-PLAN 確定 |
| Quantization | QLoRA NF4 (v1 と同じ) | DB1 default |
| Library | PEFT (v1 と同じ) | DB2 暫定 |
| **Adapter rank** | **rank=4** (v1 の rank=8 ではない) | 3 persona × ~2500 turn × rank=4 で VRAM/time trade-off |
| Serving | SGLang `--enable-lora` + `/load_lora_adapter` (v1 と同じ) | DB3 |
| Mock weight source | random init or HF LoRA hub (例: `qwen-r4-dummy`) | infrastructure proof のみ目的、quality 不問 |
| Training data minimum (Phase β) | 3 persona × ~2500 turn = 7500 turn | P3 golden baseline 完了の delivered |

## 4. v2 が v1 から変える点

### Phase α (Mock-LoRA、新規)

```python
# tools/spike/build_mock_lora.py (新設、Phase α)
"""Build a deterministic random-init LoRA adapter for SGLang infrastructure proof.

The adapter is *not* trained on persona data — its weights are seeded
random orthogonal matrices that pass safetensors / SGLang format
validation. The purpose is to verify the load/unload/inference path
end-to-end without waiting for P3 golden baseline.

Quality is not tested here; M9-eval Tier B Vendi / Big5 ICC will surface
the mock as low-quality if mistakenly enabled in production (defence in
depth — DB9 quorum prevents adoption).
"""
```

### Phase β (Multi-persona batch、新規)

```python
# src/erre_sandbox/training/train_multi_persona_lora.py (新設、Phase β)
"""Train Kant + Nietzsche + Rikyū LoRA adapters on G-GEAR via multi-persona
batch (rank=4).

Each persona gets its own adapter file (kant-r4-nf4-<date>.safetensors,
etc.), loaded into SGLang via separate /load_lora_adapter calls.
Multi-persona batch saves training time vs sequential 3-spike runs.
"""
```

### 比較: API skeleton 全体

v1 の `SGLangChatClient` API は v2 でも同じ (mock-LoRA load も real-LoRA load
も `load_adapter()` で透過扱い)。違いは:

- v1: `train_kant_lora.py` 単体、Kant 1 persona
- v2: `train_multi_persona_lora.py` + `tools/spike/build_mock_lora.py`、
  3 persona + mock 経路

## 5. VRAM 予算 (v2、3 persona rank=4)

| 項目 | VRAM (Phase α mock) | VRAM (Phase β 3 persona rank=4) |
|---|---|---|
| Qwen3-8B base, NF4 | 5.2GB | 5.2GB |
| LoRA adapter (rank=4 × 3 persona) | ~75MB (Phase β、3 active) | ~25MB (Phase α、mock 1) |
| Training gradient (Phase β、active 1 persona at a time) | — (Phase α は training なし) | ~2.0-2.5GB (rank=4 で v1 の 60%) |
| Activation memory | ~1.0GB | ~1.0GB |
| Buffer / fragmentation | ~0.5GB | ~0.5GB |
| **合計 (training)** | — | **~8.7-9.2GB** |
| **合計 (serving 3 active)** | ~7.5GB | **~7.5GB** |
| **headroom (16GB - peak)** | — | **~6.8-7.3GB** (v1 5.8GB より広い) |

v2 は **rank=4 で VRAM headroom 1GB 増**、training time も 60% 程度に短縮。
trade-off は **adapter expressivity 低下** (rank=4 < rank=8) だが、persona-
conditional adaptation には sufficient (Donnellan-style 2024 LoRA persona
literature は rank=4-8 で adequate と報告、Codex 確認させる)。

## 6. v2 が v1 を破壊する点

- **rank=8 → rank=4**: M9-C-adopt の "rank=8 統一 spike" との整合性は崩れる
  (M9-C-adopt は rank=8 で改めて検証)、本 spike は rank=4 trade-off
- **Kant 1 persona → 3 persona batch**: 第3の道 ADR の "Kant 1 persona" 文言を
  超える scope 拡張、ADR 修正が必要
- **mock-LoRA を本タスク内で実行**: M9-B `decisions.md` で言及されない選択肢、
  ADR 新規起票必要 (CS-N で)
- **2 phase 構造**: M9-B `decisions.md` の単一 spike phase 設計を 2 phase に
  分割

## 7. v2 が捨てている v1 の正しさ (hybrid v3 候補)

v1 が正しい点 (v2 が損なうべきでないもの):

- **bounded scope**: M9-B 第3の道 ADR の "bounded, non-authoritative single-
  persona" は scope creep 防止策。v2 で 3 persona に拡張する正当性は data 量
  (Kant 単独 ~2500 turn は十分) では弱い
- **rank=8 統一**: M9-C-adopt の rank=8 統一 spike と continuity を保つほうが
  研究 timeline で coherent
- **mock-LoRA は不要**: SGLang HIGH-3 で v0.3+ stable と確認済、mock proof
  なくても real Kant LoRA で sufficient
- **8h 工数**: solo cadence で v1 ~8h、v2 は ~12h で +50%

→ **hybrid v3 候補**:

- Phase α (mock-LoRA infra proof) は **採用** (data-blocked 時の hedge、本 PR
  scope 内で完結可、Codex P4a HIGH-3 like の早期 fallback 判定材料)
- Phase β は **Kant 1 persona rank=8 (v1 採用)** に戻す (M9-B 第3の道 ADR と
  continuity、M9-C-adopt rank=8 統一 spike とも整合)
- 3 persona batch は **M9-C-adopt 範囲に defer** (本 spike では Kant のみ)
- mock-LoRA は **infra proof 専用 tool** として `tools/spike/build_mock_lora.py`
  に隔離 (production code 外、`src/` に置かない)

## 8. v3 の primary value proposition

**v3 = v1 (Kant 1 persona rank=8) + Phase α (mock-LoRA infra proof)** の hybrid:

- Phase α (mock) で deliverable 1-4 を **data-independent に early ship**
  (1-2 セッション、P3 完了待ち不要)
- Phase β (real) で Kant adapter quality signal を **P3 完了 trigger** で
  実走 (3 persona batch ではなく Kant 1、M9-B ADR 整合)
- 3 persona batch は M9-C-adopt territory に保留 (scope creep 防止)

工数: Phase α ~3h + Phase β ~8h = ~11h (v1 8h と v2 12h の中間)、ただし
Phase α は P3 待ちでなく即実行可能なので **早期 unblock value** が大きい。

## 9. v2 で意図的に未解決にしている点 (Codex review challenge)

- **mock-LoRA の SGLang format compatibility**: random-init weight で
  `/load_lora_adapter` が拒否されるリスク (PEFT format validation)
- **Phase α / β 切り替えの timing**: P3 完了見込みが不確実な中、Phase α 完了
  後に Phase β を開始する trigger は何か
- **rank=4 vs rank=8 の persona expressivity gap**: 2024-2026 prior art 確認
- **3 persona batch training の interference**: shared base + per-persona
  adapter で persona 間 contamination ゼロ確認 (DB11-like 概念)
- **scope creep risk**: v2 は M9-B 第3の道 ADR の "bounded single-persona" を
  超える、ADR 修正の coast 高い

## 10. Effort estimate (v2)

| Phase | 推定 (v2) |
|---|---|
| 全体 | **~12h** (v1 8h と比較で +50%) |

trade-off:

- 工数 +50% (1 セッション余分)
- 得るもの: data-independent infra proof で **早期 fallback 判定**、3 persona
  coverage で persona-conditional 一般性確認
- 失うもの: scope 拡張 (M9-B 第3の道 ADR からの逸脱、ADR 修正必要)

exec
/bin/zsh -lc "sed -n '1,360p' .steering/20260508-m9-c-spike/m9-c-spike-design-v1.md" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "sed -n '1,260p' .steering/20260508-m9-c-spike/requirement.md" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
# m9-c-spike — bounded Kant LoRA spike on SGLang

## 背景

M9-B execution prerequisite (M9-B `decisions.md` 第3の道 ADR、PR #127 merged
2026-04-30):

> bounded, non-authoritative single-persona Kant LoRA spike を SGLang 上で
> M9-eval-system と並行実施する。adoption 判断は評価系完成後の post-spike
> re-eval まで保留。

評価系構築中 (M9-eval-system 進行中、現在 P3 golden baseline calibration が
G-GEAR run1 overnight×2 で走行中) に **LoRA 学習・adapter swap・runtime
技術リスクを早期検出** することが目的。本 spike が成功 (technical PoC 成立)
することで、M9-C-adopt (LoRA 本採用) の前提条件が片づく。

直近 PR #148 (M9-eval P4a Tier B、2026-05-08) で DB9 quorum offensive gate
arbiter が完成、Tier B 3 sub-metric (Vendi / Big5 ICC / Burrows Δ) で LoRA
採用判定 quorum logic が機能する状態になった。だが M9-eval-system 完成
(Tier C P6 含む) はまだ先。本 spike は M9-eval-system と **時間的に並行**
実施可能 (non-authoritative 故に evaluation 系の完成を待たない)。

## ゴール

本タスクは **2 phase** に分かれる:

### 本 PR (本セッション) scope = Plan + scaffold + Codex review まで

1. `.steering/20260508-m9-c-spike/` の **scaffold 全 11 file** 配置完了
2. `m9-c-spike-design-v1.md` (infrastructure-first 案) → `/reimagine` で
   v2 (代替戦略) → `m9-c-spike-design-comparison.md` で hybrid v3 確定
3. Codex `gpt-5.5 xhigh` independent review 実行、`codex-review-m9-c-spike.md`
   verbatim 保存、HIGH 全反映を `m9-c-spike-design-final.md` に明示
4. `decisions.md` に新規 ADR (CS-1〜CS-N) 起票、各 5 要素
5. `tasklist.md` に Phase G-J (実装 phase) sub-items 列挙
6. `blockers.md` に P3 golden baseline 完了 dependency + SGLang version pin +
   VRAM 予算実測 defer 事項記録

### 次セッション以降 scope = 実装 + tests + G-GEAR 実走

- `pyproject.toml` に `[training]` extra 追加 (peft / transformers / datasets /
  accelerate / bitsandbytes)
- `src/erre_sandbox/inference/sglang_adapter.py` 新設 (LoRA load/unload
  method 含む)
- `src/erre_sandbox/training/` module 新設 (prompt_builder / dataset /
  train_kant_lora)
- mock test + integration test (ruff / mypy / pytest 全 PASS、CI 4/4 green)
- G-GEAR 実走 (P3 golden baseline 採取完了後): training run + adapter load +
  **adapter swap latency / N=3 throughput / FSM regression** 実測
- DB8 adapter swap runbook 起草 (実測値込み)

## スコープ

### 含むもの

- **Kant 1 persona** spike (LoRA fine-tune + SGLang serving + adapter swap)
- 既存 dialog_turn (`epoch_phase != EVALUATION` の `AUTONOMOUS` /
  `Q_AND_A` 行) を training data
- **SGLang `--enable-lora` + `/load_lora_adapter` REST endpoint** 動作確認
- adapter swap latency / throughput / FSM regression の **実測** (G-GEAR)
- DB3 vLLM fallback 判定材料の生成 (>500ms latency / N=3 collapse / FSM
  regression が trigger)
- Technical PoC + Quality signal **両方** (Codex 確認済 user 確定)

### 含まないもの

- **LoRA 採用判定** (M9-C-adopt 範囲、DB9 quorum 通過必須)
- **3 persona 展開** (Nietzsche / Rikyū)、本 spike は Kant 1 のみ
- **Tier C judge LLM** (M9-eval P6 範囲)
- **M9-eval P3 golden baseline 採取自体** (G-GEAR run1 calibration → run2-4
  での実走、別タスク)
- **Burrows reference corpus 整備** (Tier A 既存範囲、blockers.md defer)
- **persona refactor / philosopher_seed** (M10-A 範囲、認知深化 PR #144)
- **DB11 contamination assert 実装** (`m9-individual-layer-schema-add` 別タスク)
- **vLLM full migration 実装** (DB3 fallback fire 時のみ別タスク化)
- **PEFT vs unsloth final 選定** (M9-C-adopt 範囲、本 spike では PEFT 暫定)

## 受け入れ条件

### 本 PR (本セッション) 受け入れ条件

- [ ] `.steering/20260508-m9-c-spike/` 11 file scaffold 完了
- [ ] `m9-c-spike-design-v1.md` / `-design-v2.md` / `-design-comparison.md` /
      `-design-final.md` 全 verbatim 保存
- [ ] `codex-review-prompt-m9-c-spike.md` 起票、`codex-review-m9-c-spike.md`
      verbatim 保存 (要約禁止)
- [ ] Codex Verdict (期待: ADOPT-WITH-CHANGES)、HIGH 全反映マッピング表を
      `m9-c-spike-design-final.md` に明示
- [ ] `decisions.md` に CS-1〜CS-N ADR、各 5 要素 (決定 / 根拠 / 棄却 /
      影響 / re-open 条件)
- [ ] `tasklist.md` に Phase G-J 実装 sub-items 列挙、本 PR sub-items は [x]
- [ ] `blockers.md` に dependency + defer 記録 (P3 golden baseline / SGLang
      version pin / VRAM 実測)
- [ ] PR description に `codex-review-m9-c-spike.md` link + design-final.md
      link

### 次セッション以降 (実装 phase) 受け入れ条件

- ruff / ruff format / mypy / pytest 全 PASS、CI 4/4 green
- 既存 1356+ tests no regression
- SGLang adapter mock test (load_adapter / unload_adapter / chat with adapter)
- training data extraction test (raw_dialog → prompt/completion 形式、
  `epoch_phase != EVALUATION` filter)
- adapter format conversion test (PEFT safetensors → SGLang weight)
- G-GEAR 実走 (P3 完了後): adapter swap latency <500ms 確認 (>500ms は
  DB3 fallback fire)、N=3 throughput collapse なし、FSM regression なし
- `decisions.md` CS-N に **実測値** を反映 (latency / cold start / throughput)
- DB8 adapter swap runbook を `docs/` に commit (M9-B `tasklist.md` の
  該当 sub-item を [x])

## 関連ドキュメント

- `.steering/20260430-m9-b-lora-execution-plan/decisions.md` DB1-DB11 +
  第3の道 ADR
- `.steering/20260430-m9-b-lora-execution-plan/design-final.md`
- `.steering/20260420-m5-llm-spike/` (spike 系 .steering 構造の前例)
- `.steering/20260430-m9-eval-system/codex-review-p4a.md` (Codex review
  prompt 構造の前例)
- `docs/architecture.md` §2 (G-GEAR VRAM、qwen3:8b)
- `src/erre_sandbox/inference/ollama_adapter.py` (`OllamaChatClient` API
  雛形)
- `src/erre_sandbox/evidence/eval_store.py::connect_training_view` (DB5 entry)
- `src/erre_sandbox/schemas.py::EpochPhase` (L254)

## 運用メモ

- **破壊と構築 (`/reimagine`) 適用**: **Yes** (user 確定)
- **理由**: アーキテクチャ判断 (SGLang vs vLLM、PEFT vs unsloth、training
  data 戦略) と複数案ありうる設計、CLAUDE.md 規約で 3 関門必須
- **Codex 必須**: 同上、CLAUDE.md `gpt-5.5 xhigh` independent review 必須
- **本セッション scope**: Plan + scaffold + Codex review **まで** (実装は
  次セッション)
- **data dependency**: M9-eval P3 golden baseline 採取完了 (G-GEAR run1
  overnight×2 + run2-4) が前提、本 PR では code path のみ起草
- **Mac 単独作業**: G-GEAR run1 calibration への影響なし
  (`data/eval/calibration/` には touch しない、code path も独立)

 succeeded in 0ms:
# m9-c-spike — design v1 (infrastructure-first 起点)

> 本 v1 は意図的に `/reimagine` で破壊される対象。次の v2 が別の出発点 (例:
> training-quality-first / mock-LoRA-first 等) から再生成され、
> `m9-c-spike-design-comparison.md` で hybrid v3 候補を検討する。HIGH 検出は
> Codex review に委ねる。
>
> Refs: M9-B `decisions.md` DB1-DB11 + 第3の道 ADR (PR #127)、CLAUDE.md
> 「Codex を積極活用」、`schemas.py::EpochPhase` (L254)、
> `inference/ollama_adapter.py::OllamaChatClient` (API 雛形)、
> `evidence/eval_store.py::connect_training_view` (DB5 entry)。

## 1. Mission

`src/erre_sandbox/inference/sglang_adapter.py` 新設 + `src/erre_sandbox/training/`
module 新設で、Kant 1 persona の bounded LoRA spike を実行可能にする。本 spike
は **non-authoritative** — adoption 判断は M9-eval-system 完成後の post-spike
re-eval まで保留。

ゴールは下記 5 deliverable (Phase 1 探索で抽出):

1. SGLang LoRA endpoint 動作確認 (`--enable-lora` + `/load_lora_adapter`)
2. **adapter swap latency** 実測 (>500ms は DB3 vLLM fallback fire)
3. **N=3 同時 request throughput** 実測 (collapse なし)
4. **M5 resonance / ERRE FSM regression** 確認 (SGLang LoRA 経路で破綻なし)
5. **adapter swap runbook (DB8)** 起草 (実測値込み、本 spike 完了後)

## 2. v1 commit (推奨初期方向)

| 項目 | v1 commit | 根拠 |
|---|---|---|
| Spike scope | Kant 1 persona、既存 dialog_turn (`epoch_phase != EVALUATION`) のみ training data | 第3の道 ADR、DB4 dataset trigger |
| Base model | qwen3:8b (M9-eval と同じ) | MASTER-PLAN 確定、cross-spike consistency |
| Quantization | QLoRA NF4 (default) | DB1 default |
| Library | PEFT (公式・ecosystem 厚い) | DB2 暫定、final は M9-C-adopt |
| Adapter rank | rank=8 統一 | DB2 hybrid (M9-C-adopt rank=8 統一 spike と整合) |
| Serving | SGLang `--enable-lora` + `/load_lora_adapter` REST | DB3、Codex HIGH-3 で v0.3+ stable 確認済 |
| Training data minimum | P3 golden baseline 7500 turn (Kant 部分 ~2500 turn) | DB4 coverage 300/persona、Kant 単独 pilot ~40-50 turn は不足 |
| Adapter swap latency target | <500ms | DB3 vLLM fallback 条件 (>500ms fire) |

## 3. SGLang adapter 拡張 API skeleton

### `src/erre_sandbox/inference/sglang_adapter.py` (新設)

`OllamaChatClient` API signature を踏襲しつつ、LoRA load/unload を追加:

```python
"""SGLang adapter — multi-LoRA aware chat client.

Wraps the SGLang HTTP server (started with ``--enable-lora --max-loras N
--max-lora-rank R``) to provide an OllamaChatClient-compatible chat surface
plus the additional LoRA load/unload REST endpoints documented in SGLang
v0.3+ (multi-LoRA / dynamic load/unload / pinned adapters / overlap loading,
M9-B DB3 / Codex HIGH-3).

The adapter is read by the live inference path (``inference/server.py``) for
LoRA-enabled persona serving. Tests pass an ``httpx_client`` stub so the
heavy server dep never fires in CI.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import httpx

from erre_sandbox.inference.ollama_adapter import (
    ChatMessage,
    ChatResponse,
    SamplingParameters,
)


@dataclass(frozen=True, slots=True)
class LoRAAdapterRef:
    """Identifier for a loaded LoRA adapter on the SGLang server."""
    adapter_name: str        # e.g. "kant-r8-nf4-2026-05-08"
    base_model: str          # e.g. "qwen/Qwen3-8B"
    rank: int                # 8 in the M9-C-spike default
    pinned: bool = False     # SGLang pinned adapter optimisation


class SGLangUnavailableError(RuntimeError):
    """Raised when the SGLang HTTP server returns a non-200 / connection error.

    Mirrors :class:`OllamaUnavailableError` so the caller can handle both
    backends symmetrically. ``error_handling`` Skill applies (retry policy
    in ``error-handling.examples.md``).
    """


class SGLangChatClient:
    """SGLang HTTP chat client with multi-LoRA support.

    The constructor only stores config; the heavy ``httpx.AsyncClient`` is
    created lazily on first call and reused per process. The load/unload
    methods speak to SGLang ``/load_lora_adapter`` and
    ``/unload_lora_adapter`` REST endpoints.
    """

    def __init__(
        self,
        *,
        base_url: str,
        default_model: str,
        httpx_client: httpx.AsyncClient | None = None,
    ) -> None: ...

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        sampling: SamplingParameters,
        model: str | None = None,
        adapter: LoRAAdapterRef | None = None,
    ) -> ChatResponse:
        """Mirror OllamaChatClient.chat with optional adapter routing."""

    async def load_adapter(
        self,
        ref: LoRAAdapterRef,
        *,
        weight_path: str,
    ) -> None:
        """POST /load_lora_adapter; idempotent when ref already loaded."""

    async def unload_adapter(self, ref: LoRAAdapterRef) -> None:
        """POST /unload_lora_adapter; idempotent when not loaded."""

    async def list_adapters(self) -> list[LoRAAdapterRef]:
        """GET /list_lora_adapters; returns currently loaded adapters."""

    async def close(self) -> None:
        """Release the lazy httpx.AsyncClient (idempotent)."""
```

**Key design choice (v1)**: REST endpoint URL は SGLang v0.3+ documented の
`/load_lora_adapter` POST (Codex HIGH-3 reflection)。Codex review で current
SGLang version の正確な endpoint path を確認させる。

## 4. training/ module skeleton (新設)

### `src/erre_sandbox/training/__init__.py`

```python
"""LoRA fine-tuning pipeline for ERRE-Sandbox personas.

This package is pure post-hoc / off-line — it never participates in the live
inference path. The single training-egress entry from raw_dialog is
:func:`erre_sandbox.evidence.eval_store.connect_training_view` (DB5 contract);
this package consumes that read-only view and produces LoRA adapter weights.

Architectural constraint (M9-B DB5/DB6):
* Reads ``raw_dialog.dialog`` only (never the ``metrics`` schema).
* Filters to ``epoch_phase != EpochPhase.EVALUATION`` rows.
* Writes adapter checkpoints to disk; no metric-shaped output.

DB11 contamination prevention: when ``individual_layer_enabled`` field is
added to the raw_dialog allow-list (separate task
``m9-individual-layer-schema-add``), this package will assert
``individual_layer_enabled is False`` for every consumed row (M10-A onward).
"""
```

### `src/erre_sandbox/training/prompt_builder.py` (新設)

```python
"""Convert raw_dialog rows into PEFT SFTTrainer-compatible prompt/completion.

Pure-function module: takes a sequence of raw_dialog dicts (per
:func:`connect_training_view`) and emits ``(system, user, assistant)``
triples or HuggingFace ``messages`` format depending on the trainer.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TrainingExample:
    """One PEFT-ready conditional generation example."""
    system: str        # persona prompt (deterministic)
    user: str          # last interlocutor utterance + zone context
    assistant: str     # target utterance (the persona's reply)
    persona_id: str
    run_id: str
    metadata: Mapping[str, object]  # tick, turn_index, mode, zone


def build_examples(
    rows: Iterable[Mapping[str, object]],
    *,
    persona_id: str,
    epoch_phase_filter: tuple[str, ...] = ("autonomous", "q_and_a"),
) -> list[TrainingExample]:
    """Convert raw_dialog rows to TrainingExample list.

    Args:
        rows: Iterator from :func:`connect_training_view().iter_rows`.
        persona_id: Filter to this persona's utterances as the assistant
            target. Other personas appear as user-side context.
        epoch_phase_filter: Only include rows with epoch_phase in this
            tuple. Default excludes EpochPhase.EVALUATION rows.

    Returns:
        List of TrainingExample, ordered by (run_id, tick, turn_index).
    """
```

### `src/erre_sandbox/training/dataset.py` (新設)

```python
"""HuggingFace ``datasets.Dataset`` adapter for PEFT SFTTrainer.

Wraps :func:`build_examples` output as a ``datasets.Dataset`` with the
columns SFTTrainer expects (``messages`` or ``text`` depending on
formatting_func). Tests use a stub Dataset to keep the heavy ``datasets``
import out of CI.
"""

from collections.abc import Sequence

from erre_sandbox.training.prompt_builder import TrainingExample


def to_hf_dataset(examples: Sequence[TrainingExample]):  # noqa: ANN201 — ds.Dataset return
    """Return ``datasets.Dataset`` formatted for SFTTrainer."""
```

### `src/erre_sandbox/training/train_kant_lora.py` (新設、CLI)

```python
"""CLI: train Kant LoRA adapter on G-GEAR (RTX 5060 Ti 16GB).

Run:
    uv run python -m erre_sandbox.training.train_kant_lora \
        --db <path-to-golden-baseline.duckdb> \
        --output-dir checkpoints/kant-r8-nf4-<date>

Reads raw_dialog via :func:`connect_training_view`, builds Kant training
examples, fine-tunes Qwen3-8B with QLoRA NF4 + rank=8 PEFT adapter, saves
the adapter as safetensors. The output is then loaded into SGLang via
:meth:`SGLangChatClient.load_adapter`.
"""
```

## 5. VRAM 予算試算 (RTX 5060 Ti 16GB)

| 項目 | VRAM |
|---|---|
| Qwen3-8B base, NF4 quantization | ~5.2GB |
| LoRA adapter (rank=8, all-proj target_modules) | ~50MB |
| Training gradient + optimizer state (PEFT QLoRA) | ~3.0-3.5GB |
| Activation memory (batch=1, seq=2048) | ~1.0GB |
| Buffer / fragmentation | ~0.5GB |
| **合計 (training)** | **~9.7-10.2GB** |
| **headroom (16GB - 10.2)** | **~5.8GB** |

**marginal**: training 中は OOM リスク低い (5.8GB headroom)。serving 時は base
+ 1-3 active adapters で ~5.5GB のみ、余裕。

**Codex で確認させる**:

- gradient_checkpointing による gradient 削減で headroom 改善できるか
- 8-bit LoRA (bitsandbytes) vs NF4 QLoRA の VRAM 差
- accumulation_steps を上げれば effective batch を維持できるか

## 6. Training data 利用可能量 (Phase 1 で確認済)

- **現状 (P3 calibration 段階)**: Kant pilot data は ~40-50 turn (LoRA training
  には不足)
- **P3 golden baseline 完了後**: 3 persona × 5 run × 500 turn = **7500 turn**
  のうち Kant 部分は ~2500 turn (`epoch_phase != EVALUATION` の autonomous +
  q_and_a)
- **2500 turn は LoRA spike として sufficient** (DB4 coverage 300/persona の
  ~8 倍、prior art も 2024 LoRA persona-conditioning literature で同程度)
- **本 PR では code path のみ起草**、実走は P3 完了 trigger で次セッション

## 7. Test plan (本 PR scope 外、次セッション以降の Phase H/I/J)

### `tests/test_inference/test_sglang_adapter.py` (新設、Phase H、6 件)

1. `test_sglang_chat_client_chat_round_trip` — httpx mock で chat round trip
2. `test_sglang_chat_client_load_adapter_idempotent` — load×2 で 2 回目 noop
3. `test_sglang_chat_client_unload_adapter_idempotent` — unload×2 で 2 回目 noop
4. `test_sglang_chat_client_list_adapters_returns_loaded` — load → list で
   adapter ref 含む
5. `test_sglang_chat_client_unavailable_error_on_500` — server 500 →
   `SGLangUnavailableError`
6. `test_sglang_chat_client_close_idempotent` — close×2 で 2 回目 noop

### `tests/test_training/test_prompt_builder.py` (新設、Phase I、4 件)

1. `test_build_examples_filters_evaluation_epoch` — `epoch_phase=evaluation`
   行 0 件
2. `test_build_examples_orders_by_tick_turn_index` — sort 確認
3. `test_build_examples_persona_assistant_target` — Kant のみ assistant、
   他 persona は user context
4. `test_build_examples_empty_raw_dialog_returns_empty` — boundary

### `tests/test_training/test_dataset.py` (新設、Phase I、2 件)

1. `test_to_hf_dataset_shape_matches_sft_trainer` — column 名 / 行数
2. `test_to_hf_dataset_seed_stable` — reproducibility

### G-GEAR 実走 phase (Phase J、P3 完了後)

- adapter swap latency p50 / p95 / p99 (target <500ms p95)
- N=3 同時 request throughput (req/s collapse なし)
- FSM regression (peripatos / chashitsu / zazen / shu_kata / ha_deviate /
  ri_create / deep_work / shallow 8 mode で adapter 経路 OK)
- training run time (`train_kant_lora.py` run、~2-4h on RTX 5060 Ti 16GB)

## 8. v1 で意図的に未解決にしている点 (`/reimagine` + Codex で challenge)

- **SGLang version pin**: v0.3 vs v0.4 vs v0.5 のどれが multi-LoRA stable か
  (Codex web search で changelog 確認)
- **adapter format conversion**: PEFT safetensors → SGLang `--lora-paths`
  受付形式の互換性 (undocumented なら vLLM swap)
- **training data minimum**: 2500 turn (P3 完了後 Kant 部分) で sufficient か、
  prior art 確認
- **gradient_checkpointing 採用可否**: VRAM 9.7-10.2GB を 7.5-8GB に下げる
  trade-off (training time +20-30%)
- **Mock-LoRA fallback** (戦略 C): data-blocked 時の代替案、infrastructure
  proof のみ早期実施
- **Multi-persona small batch** (戦略 D): Kant 単独 vs Kant+Nietzsche+Rikyū
  の trade-off (rank=4 で総量稼ぐ)
- **AWQ + LoRA early eval** (戦略 E): DB1 alternatives 1 を spike 内で前倒し
  検証
- **VRAM headroom margin**: 5.8GB は実用上 sufficient か (CUDA fragmentation /
  long-context generation の overhead 込み)

## 9. ADR alignment (絶対遵守)

| ADR | 制約 | v1 対応 |
|---|---|---|
| DB1 | QLoRA NF4 default | v1 採用 |
| DB2 | PEFT 暫定 | v1 採用、final は M9-C-adopt |
| DB3 | SGLang `--enable-lora` + `/load_lora_adapter` | v1 採用、>500ms latency で fallback fire |
| DB4 | dataset trigger 300/persona | v1 採用、Kant ~2500 turn は fire 可 (M9-C-adopt 範囲) |
| DB5/DB6 | raw_dialog vs metrics 物理分離、`epoch_phase != EVALUATION` filter | training/prompt_builder で filter 強制 |
| DB8 | adapter swap runbook は spike 完了後 | Phase J で起草 |
| DB10 | spike は non-authoritative | requirement.md / docstring に明示 |
| DB11 | individual_layer_enabled enforcement は別タスク | blockers.md に記録、本 spike では明示せず |
| 第3の道 ADR | bounded Kant spike on SGLang、M9-eval と並行 | 本タスク全体が該当 |

## 10. Out of scope (本タスク全体)

- LoRA 採用判定 (M9-C-adopt 範囲、DB9 quorum 通過必須)
- 3 persona 展開 (Nietzsche / Rikyū)、本 spike は Kant 1 のみ
- Tier C judge LLM (M9-eval P6 範囲)
- M9-eval P3 golden baseline 採取自体 (G-GEAR run1 calibration → run2-4、
  別タスク)
- Burrows reference corpus 整備 (Tier A 既存範囲、blockers.md defer)
- persona refactor / philosopher_seed (M10-A 範囲、認知深化 PR #144)
- DB11 contamination assert 実装 (`m9-individual-layer-schema-add` 別タスク)
- vLLM full migration 実装 (DB3 fallback fire 時のみ別タスク化)
- PEFT vs unsloth final 選定 (M9-C-adopt 範囲)


exec
/bin/zsh -lc "sed -n '1,520p' .steering/20260430-m9-b-lora-execution-plan/decisions.md" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "sed -n '1,620p' .steering/20260430-m9-eval-system/decisions.md" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
# Decisions — M9-B LoRA Execution Plan (10 ADR: DB1-DB10)

## ADR 体裁

各 ADR は 5 要素 (決定 / 根拠 / 棄却 / 影響 / re-open 条件) で記録。
本 ADR set は m9-lora-pre-plan の D1-D5 (PR #110 merged) を **継承し、M9 実行 phase の
詳細を確定** する位置づけ。Codex independent review (`codex-review.md`) で得た 10 finding
(HIGH 4 / MEDIUM 4 / LOW 2) を全件反映済。

---

## DB1 — 量子化戦略: QLoRA NF4 default + alternatives recorded

- **決定**: 学習時 quantization は **QLoRA NF4 (bnb double-quantization)** を default 採用。
  alternatives (AWQ + LoRA / GPTQ + LoRA / 8-bit LoRA) を記録、bounded Kant spike で
  実測 quality を検証してから default を維持・変更する。
- **根拠**:
  - G-GEAR 16GB + qwen3:8b (FP16 ~16GB) + 3 persona swap で base ~4-5GB 圧縮が必要
  - QLoRA NF4 + double-quantization で 1-2% 性能低下、許容範囲
  - codex MEDIUM-2 指摘: 「唯一現実解」は overstated、conservative default と framing
- **棄却**:
  - LoRA FP16: VRAM 不足
  - INT8 + LoRA: NF4 の上位互換なし
- **影響**:
  - 学習 pipeline は HF Transformers + PEFT/unsloth (M9-C-spike で確定)
  - serving は SGLang LoRA adapter format に変換 (DB3)
- **re-open 条件**:
  - Kant spike で NF4 quality が許容範囲外 → 8-bit LoRA fallback
  - SGLang AWQ + LoRA 互換が confirmed → AWQ への serving migration 検討

---

## DB2 — Library 選定: defer to M9-C kickoff

- **決定**: PEFT vs unsloth の選定は **M9-eval-system + M9-C-spike 完了後の M9-C-adopt 着手時**
  に rank=8 統一 spike で決める。M9-B / M9-eval-system では library を確定しない。
- **根拠**:
  - 学習 library 選定は LoRA を実際に走らせる時点で十分
  - 先行決定する benefit なし (premature optimization)
  - codex review Q3 反映: 必要な時点での実測判断
- **棄却**:
  - v1: unsloth 即採用 → 性能 benefit 未実測のまま commit するリスク
- **影響**:
  - M9-C-spike では一時的に PEFT (公式・ecosystem 厚い) を使用、final 選定は別
- **re-open 条件**:
  - unsloth の SGLang LoRA adapter format compatibility が問題
  - PEFT の学習速度が solo cadence に対し過大

---

## DB3 — Serving 移行判断: **SGLang-first, vLLM fallback only** (HIGH-3 反映)

- **決定**: **現行 SGLang を維持し、LoRA は SGLang `--enable-lora` + `/load_lora_adapter`
  で実装する**。vLLM full migration は **measured spike failure 時のみ** fallback。
- **根拠**:
  - codex HIGH-3: SGLang は v0.3+ で multi-LoRA / dynamic load/unload / pinned adapters /
    overlap loading / `--enable-lora` を documented サポート
    ([SGLang docs](https://docs.sglang.io/advanced_features/lora.html))
  - 私の v1/v2 認識 (SGLang LoRA 安定性未検証) は stale だった
  - vLLM full migration は M5 以降の resonance 機構 / ERRE FSM 再配線が必要、コスト過大
- **棄却**:
  - v1 / v2: vLLM full migration → cost 過大、SGLang stale 認識に基づく
- **影響**:
  - M5 resonance / ERRE FSM 配線そのまま維持 (大きな cost saving)
  - LoRA adapter format は SGLang 互換に変換が必要
- **re-open 条件 (vLLM fallback fire)**:
  - Kant spike で adapter swap latency > 500ms
  - N=3 同時 request で throughput collapse
  - resonance / FSM が SGLang LoRA 経路で regression

---

## DB4 — Dataset trigger 閾値: `floor AND (coverage OR plateau OR timebox)` (HIGH-1 反映)

- **決定**: LoRA 適用 trigger を **`floor MUST AND (coverage 300/persona OR plateau OR timebox)`**
  に確定。divergence stability は **diagnostic** のみ、hard gate にしない。
  - **MUST (floor)**: self_rep ≤ 0.10 AND cross_echo ≤ 0.10 (継続要件)
  - **ANY ONE OF**:
    - coverage: dialog_turn ≥ **300/persona** (旧 500 から緩和)
    - plateau: prompting + persona YAML 拡張のみで Tier B metric が **2 連続 run で
      <5% improvement** (operational definition は DB9 quorum logic に統合)
    - timebox: **8 セッション** (~2 calendar weeks at solo cadence) 経過
  - **diagnostic (warning only)**: divergence_ratio が ζ 36:74:16 ±10% を逸脱
- **根拠**:
  - codex HIGH-1: 4-AND は m9-lora-pre-plan D1 ADR (floor + (coverage OR plateau)) と矛盾
  - D1 既存 ADR で 500/persona は ζ scale で実質 unreachable と warning 済
    (`.steering/20260428-m9-lora-pre-plan/decisions.md:44-50`)
  - timebox 追加は solo project の momentum loss 防止 (codex Q2 反映)
- **棄却**:
  - v1/v2 4-AND: D1 ADR と矛盾、unreachable リスク
  - 500/persona: ζ scale で達成困難
- **影響**:
  - LoRA 適用が現実的タイミングで fire 可能
  - timebox により M9 milestone delay が bounded
- **re-open 条件**:
  - 300/persona も実態で困難 → 再 relax (200/persona) 検討
  - timebox 8 session が早すぎ・遅すぎ判明 → 調整

---

## DB5 — Parquet schema: **raw + sidecar 物理分離** (HIGH-4 反映)

- **決定**: training data と evaluation metric を **物理的に別 table** に保存。
  - **raw_dialog/**: metric-free training table。`evaluation_epoch=*/persona_id=*/run_id=*/`
    partition、training は `evaluation_epoch=false/` のみ読む contract で強制。
  - **metrics/**: sidecar evaluation metric table。`run_id + persona_id + turn_idx` で
    raw に join。tier (A/B/C) + metric_name + metric_value + metadata schema。
- **根拠**:
  - codex HIGH-4: boolean flag (evaluation_epoch) だけでは training pipeline が物理的に
    metric column にアクセス可能、汚染リスク (judge artifact 学習)
  - 物理分離 + training-view contract で contamination を構造的に不可能にする
- **棄却**:
  - v1/v2: 単一 Parquet schema に metric column 統合 → contamination リスク
- **影響**:
  - Parquet pipeline 実装 (M9-eval-system) の複雑度が中程度増加
  - training loader は明示的に `raw_dialog/evaluation_epoch=false/` のみ読む実装
  - dashboard / analysis は raw + metrics を join して使用
- **re-open 条件**:
  - sidecar join overhead が training latency に影響大
  - schema migration が必要な structural change

---

## DB6 — Evaluation epoch 分離: Run-level flag + 物理 partition + sidecar (HIGH-4 統合) + 頻度 policy (MEDIUM-4)

- **決定**:
  - `evaluation_epoch: bool` を Run config 必須化、Default `False`
  - Parquet partition で物理分離 (`raw_dialog/evaluation_epoch=*/`)
  - sidecar metrics table も同 partition 構造
  - **頻度 policy**:
    - **Tier A**: per turn (cheap, ~50ms total)
    - **Tier B**: per 100 turns (Vendi / IPIP-NEO / Big5 ICC)
    - **Tier C**: nightly offline batch (Prometheus 2 / G-Eval / FANToM-adapted) — autonomous run 停止時のみ実行
- **根拠**:
  - codex HIGH-4 + MEDIUM-4: Tier C judge LLM (Prometheus 2 8x7B class) は qwen3:8b agent
    と VRAM contention、同時実行不可
  - 物理 partition は HIGH-4 解消の core mechanism
- **棄却**:
  - v1/v2 の boolean flag 単独: contamination リスク
  - Tier C を per-100-turn に走らせる案: VRAM contention で agent 停止
- **影響**:
  - autonomous loop に nightly batch slot 追加が必要
  - dashboard は per-tier の latency profile を表示
- **re-open 条件**:
  - Tier C judge LLM が smaller model に置換可能で contention 解消

---

## DB7 — Persona N=4 拡張時期: defer to M10 + synthetic heldout 4th in eval tests (LOW-1 反映)

- **決定**:
  - Runtime N=4 (agora 主体 4 人目 actual deploy) は **M10 まで完全 defer**
  - ただし **eval pipeline test には mocked 4th persona scenario を含める**
- **根拠**:
  - M9-B / M9-eval-system 期間は N=3 の divergence 漸近線 + 評価系構築が優先
  - codex LOW-1: eval pipeline が N=3 専用に overfit するのを防ぐため、synthetic 4th
    persona を test fixture として使う
  - 4 人目の persona YAML 起草 / reference corpus 整備 / golden set は M10 着手時に開始
- **棄却**:
  - v1: M9-B 中 YAML 起草 → 評価系設計を複雑化
  - 完全 defer (synthetic も含めない): eval pipeline overfit リスク
- **影響**:
  - eval pipeline test に synthetic persona fixture 追加
  - M10 で agora 主体 candidate を再評価
- **re-open 条件**:
  - N=3 の divergence が早期に saturate、4 人目で extension が必要
  - M10 timeline で 4 人目 candidate が確定

---

## DB8 — Adapter swap runbook: SGLang `/load_lora_adapter` first

- **決定**:
  - **SGLang `/load_lora_adapter` REST endpoint** で adapter dynamic load
  - `--max-loras N` + `--max-lora-rank R` 起動オプション
  - hot path persona は `pinned adapters` で pin
  - **runbook 起草は M9-C-spike 完了後**、実測値 (latency / cold start / throughput) 込み
- **根拠**:
  - DB3 (SGLang-first) と整合
  - SGLang docs cited by codex
  - 実測値なしの runbook は無価値、spike 完了後に書く
- **棄却**:
  - v1/v2 vLLM LoRARequest API ラッパ路線 → DB3 で破棄
- **影響**:
  - M9-C-spike が runbook の前提
- **re-open 条件**:
  - SGLang LoRA で adapter swap が機能不全 → vLLM fallback (DB3 re-open)

---

## DB9 — Drift gate: composite + bootstrap CI + 2-of-3 quorum (HIGH-2 反映)

- **決定**: drift gate を **統計的に厳密** に運用:
  - **Primary composite per persona**: 各 persona の Tier B から 3 sub-metric:
    - `vendi_score` (semantic kernel)
    - `big5_stability_icc` (across-mode personality stability)
    - `burrows_delta_to_reference` (persona-fit)
  - **Bootstrap CI** over turns/runs: 各 sub-metric の 95% CI を計算
  - **Quorum rule**:
    - rollback (drift): 2-of-3 sub-metric が CI で baseline negative 方向
    - adoption: 2-of-3 sub-metric が CI で baseline positive 方向
  - **Single regression**: warning ログのみ、rollback しない
  - **Defensive canary** (即時): self_rep > 0.15 OR cross_echo > 0.15 (any 1) → CI 待たず auto rollback
  - **Initial run** (first LoRA application): floor 維持で許容 (warmup 認可)
  - **Subsequent runs (≥2)**: 2-of-3 quorum で adoption / rollback 判定
  - **3 連続 adoption 失敗**: LoRA 設定 (rank / dataset) を破棄、再 spike
- **根拠**:
  - codex HIGH-2: 「5%」固定 + Tier B noise → false rollback / metric gaming リスク
  - bootstrap CI + quorum で statistical robustness
  - Effect size は persona-conditional に bootstrap で決める (固定 5% を破棄)
- **棄却**:
  - v1 「floor 維持のみ」: 効果測定不能
  - v2 「絶対 5% 改善」: noise floor が persona 依存、根拠不十分
- **影響**:
  - bootstrap CI 実装 (M9-eval-system)
  - quorum logic 実装 (M9-C-adopt)
- **re-open 条件**:
  - 3 sub-metric の選定が実態で不適切 (例: vendi_score が persona に discriminative でない)
  - CI 計算 cost が prohibitive

---

## DB10 — J 評価系 framework: 4-tier + persona-conditional + multi-channel (specs only in M9-B)

- **決定**:
  - **M9-B 内 deliverable は specs のみ** (実装コードは出さない、MEDIUM-1 反映)
  - **4-tier 階層** (research-evaluation-metrics.md ベース):
    - Tier A: per-turn cheap (LIWC/Empath / Burrows Delta / MATTR / semantic novelty / NLI)
    - Tier B: per-100-turn (Vendi Score / IPIP-NEO / Big5 stability ICC)
    - Tier C: per-session offline (Prometheus 2 / G-Eval / FANToM-adapted / ROSCOE)
    - Tier D: sparse manual (FActScore-adapted / 専門家 review / RoleEval-adapted MCQ)
  - **persona-conditional gate**: absolute value ではなく persona-baseline からの bootstrap
    CI 偏差 (Rikyu LOW idea density は適正、Kant HIGH も適正)
  - **golden set staging** (MEDIUM-3 反映):
    - M9-eval-system: **100/persona seed**
    - LoRA 採用判定: **300/persona acceptance**
    - 学術発表時: **1000/persona publication-grade**
  - **multi-channel honest framing**: single thinker-likeness score 採用しない、
    formal benchmark = floor / proxy = exploratory / expert review = final
  - **LIWC alternatives honest framing** (LOW-2 反映): Empath/spaCy は proxy であり LIWC 等価ではない、
    Big-Five claim は LIWC 商用 license + validation あって初めて成立、proxy ベースの
    Big-Five claim は honest に避ける
- **根拠**:
  - research-evaluation-metrics.md L326-349 honest gap assessment
  - codex MEDIUM-1 / 3 / LOW-2 反映
- **棄却**:
  - v1: framework 宣言のみ、内容空白
  - v2 単独: M9-B 内で Tier A 実装まで含む scope creep
  - 「single thinker-likeness score」: research-evaluation-metrics.md と Codex 双方が棄却
- **影響**:
  - M9-eval-system が独立タスクとして大規模化
  - golden set 採取に専門知識 (philosopher domain expert) が必要
- **re-open 条件**:
  - golden set 整備が solo cadence に対し時間的に困難
  - LIWC license が approve、商用使用可

---

## ADR 横断: third option (codex final note 反映)

**bounded, non-authoritative single-persona Kant LoRA spike を SGLang 上で M9-eval-system
と並行実施する**。adoption 判断は評価系完成後の post-spike re-eval まで保留。

- **目的**: 評価系構築中に LoRA 学習・adapter swap・runtime 技術リスクを早期検出
- **non-authoritative**: spike の結果のみで adoption しない (評価系 gate 通過必須)
- **scope**: Kant 1 persona のみ、既存 dialog_turn を training data として use、
  `evaluation_epoch=false` partition のみ
- **deliverable**: SGLang LoRA endpoint 動作確認 + adapter swap latency 実測 +
  vLLM migration 必要性 measured 判断材料
- **タスク**: 別タスク `M9-C-spike` として切り出し (新規 scaffold)

---

## DB11 — Cognition deepening contamination prevention (PR #144 Codex HIGH-3 反映、addendum 2026-05-08)

PR #144 (`docs/cognition-deepen-decision-2026-05-08`、main=`e641f8d`) で確定した認知深化
二層 architecture から、M9-B LoRA training pipeline への contamination 防止 ADR を追加。

### 決定

raw_dialog metadata に `individual_layer_enabled: bool` field を追加 (default=false)。
training-view contract loader は **`evaluation_epoch=false AND individual_layer_enabled=false`**
の両方を満たす行のみ訓練 eligible とする。training pipeline 入口で
`all(row.metadata.individual_layer_enabled is False)` を assert し、contamination
検出時は fail-fast。

### 根拠

PR #144 Codex `gpt-5.5 xhigh` review HIGH-3 (`M9-B LoRA training contamination`):
> Individual layer を M9-B 前または並行で cognition に混ぜると、LoRA が philosopher_base
> ではなく「個体 overlay 済み Kant」を学習する。PR #127 の固定 Kant style 前提を破り、
> 後続の base/individual 分解が測定不能になる。

固定 Kant style を保証する training を維持するため、Individual layer が現れた tick の
raw_dialog は **どんな状況でも** training export から除外する。

### 棄却

- 「flag を追加せず、M10-A scaffold 開始時に手動で training export を一時停止する」案:
  human-error 余地が高く、M9-B execution が M10-A と時系列で重なる場合に防御不能
- 「`evaluation_epoch=true` を流用する」案: eval / cognition deepening の 2 軸は orthogonal
  (cognition deepening enabled かつ eval ではない tick がありうる)、統一は意味歪曲
- 「runtime check のみで partition を切らない」案: dataset レベルの persistence で固定する
  ことで、後段 pipeline が flag を尊重する保証が強化される

### 影響

- DB5 (Parquet schema 物理分離) に `individual_layer_enabled` field を 1 つ追加 (additive)
- DB6 (Evaluation epoch 分離) の training-view contract に AND 条件を追加 (additive)
- M9-eval-system Parquet pipeline 実装時に flag 対応必須
- M9-C-adopt (LoRA execution) で training-view loader assert 実装必須
- M10-A scaffold 設計時に `individual_layer_enabled=true` set 責務を明示

### re-open 条件

- 認知深化 phasing が M11+ 以降で根本的に変更され、Individual layer の概念自体が撤回された
  場合 (現時点では PR #144 で確定済み、撤回 path は M12+ research re-evaluation の
  empirical evidence 後でのみ可能)
- LoRA を Individual layer にも適用すると判断された場合 (PR #144 M12+ research gate 該当、
  その時点で contamination 防止 logic を再設計)

### Cross-reference

- PR #144 design-final.md §2.1 (M9 trunk との接続 / M9-B LoRA contamination 防止)
- PR #144 decisions.md DA-8 (philosopher_seed refactor ADOPT-WITH-CHANGES)
- `.steering/20260508-cognition-deepen-7point-proposal/codex-review.md` HIGH-3

 succeeded in 0ms:
# Decisions — m9-eval-system (Codex review MEDIUM 反映)

## ADR 体裁

各 ADR は M9-B `.steering/20260430-m9-b-lora-execution-plan/decisions.md` と同形式の
5 要素 (決定 / 根拠 / 棄却 / 影響 / re-open 条件)。本 ADR set は M9-B DB1-DB10 と
**並列** で、m9-eval-system タスク独自の 6 件 (Codex `gpt-5.5 xhigh` review MEDIUM
を反映) + 1 件 (HIGH-3 で確定する ratio の placeholder)。

ID prefix: `ME` (m9-Eval-system) で M9-B `DB` と区別。

---

## ME-1 — IPIP-NEO fallback trigger operational definition (Codex MEDIUM-1)

- **決定**: BIG5-CHAT regression head conditional fallback の **発火条件** を以下に
  確定:
  - **trigger**: golden baseline 採取後 (3 persona × 5 run の Big5 ICC 計測完了時点) に
    **≥2/3 personas で ICC 点推定 < 0.6 OR 95% lower CI bound < 0.5**
  - **検出 timing**: P5 (bootstrap CI) 完了直後の自動チェック、`evidence/tier_b/big5_icc.py`
    が判定して `decisions.md` に re-open 候補を append
  - **追加 diagnostic** (常時計測): acquiescence index (logit balance)、straight-line
    response (≥10 連続同回答)、balanced/reverse-keyed item agreement
  - **control comparison**: persona prompt 無し base model (qwen3:8b raw) で同 IPIP-NEO
    を 1 回測定し、persona 効果と base model self-report bias を separately report
- **根拠**:
  - Codex MEDIUM-1: 「ICC < 0.6 が頻発」の頻発に denominator 無し → 監査不能
  - Salecha et al. 2024 (arXiv 2405.06058): LLM Big5 self-report に social
    desirability bias の empirical 報告
  - Koo/Li ICC 解釈: 0.5-0.75 = moderate (effectsize docs)、0.6 boundary は
    "moderate vs questionable" の境界
  - acquiescence / straight-line / reverse-keyed は psychometric standard (Tomas
    et al., Schmidt et al.)
- **棄却**:
  - 元案「frequent」のみで quantitative threshold 無し → 監査不能で棄却
  - 全 persona AND 条件 (3/3) → false negative リスク (1 persona で fallback 発火しても
    measurement model 全体に問題があり得る)
- **影響**:
  - `evidence/tier_b/big5_icc.py` に diagnostic 4 種 (ICC point, lower CI, acquiescence,
    straight-line) を追加
  - golden baseline 後 `decisions.md` に再 open 判定 ADR 追記の workflow
  - control measurement 1 run (~10 turn equivalent) を P3 にも組み込み
- **re-open 条件**:
  - golden baseline 採取後の判定で fallback fire → BIG5-CHAT regression head
    実装 ADR を別途起票 (本 ADR の child)
  - 0.6 / 0.5 閾値が persona-specific に不適切と判明 → persona-conditional
    threshold に変更検討

---

## ME-2 — DuckDB snapshot semantics (G-GEAR write → Mac read-only) (Codex MEDIUM-2)

- **決定**: G-GEAR が DuckDB file の唯一 writer、Mac は read-only consumer。
  rsync は以下の protocol で実行:
  1. **G-GEAR 側**: 採取セッション終了時に `con.execute("CHECKPOINT")` →
     `con.close()` で WAL を main file に flush
  2. **G-GEAR 側**: `cp <golden>.duckdb /tmp/<golden>.snapshot.duckdb` で同 fs 内 copy
     (DuckDB の同時 open lock 衝突回避)
  3. **G-GEAR → Mac rsync**: `rsync -av /tmp/<golden>.snapshot.duckdb mac:/data/eval/golden/`
  4. **Mac 側 atomic rename**: rsync 完了後 `mv` で `<golden>.duckdb.tmp` → `<golden>.duckdb`
     (部分転送 file を application が open しないため)
  5. **Mac 側 open**: `duckdb.connect(path, read_only=True)` を強制 (`eval_store.py`
     の `connect_training_view()` / `connect_analysis_view()` の両 entry で wrapper enforced)
  - **NFS / SMB / iCloud 共有 fs 経由は禁止** (DuckDB doc が file lock 警告)
- **根拠**:
  - Codex MEDIUM-2: live G-GEAR file を Mac から open は CHECKPOINT 前なら破損リスク
  - DuckDB doc (Concurrency): single-process write + multi-process read-only OK、
    ただし shared fs 注意
  - atomic rename は POSIX 移動が same-fs 内 atomic である事実に依拠
- **棄却**:
  - live file の直接 read → 破損 / 古い snapshot 読み出しリスク
  - SQLite WAL 風の hot replication → DuckDB は WAL replay の cross-process 安全性が
    documented でない、棄却
- **影響**:
  - `infra/scripts/sync_golden_baseline.sh` (新規) で G-GEAR → Mac の rsync orchestration
  - `eval_store.py` の Mac 経路は read_only=True 強制 (test 化)
  - golden baseline 採取 SOP に CHECKPOINT step を追加
- **re-open 条件**:
  - dataset size が大きく (>100GB) rsync コスト過大 → DuckDB native replication 機構
    検討
  - cross-fs 運用 (G-GEAR が cloud bucket に書く) が必要 → snapshot semantics 再設計

---

## ME-3 — Tier C lock + preflight TOCTOU close (Codex MEDIUM-3)

- **決定**:
  1. **Lock の包含範囲**: `flock` を Prometheus 起動前ではなく **`nvidia-smi` preflight
     も含む全 Tier C command** を内側に enclose する形に拡張。autonomous loop は
     **同じ lock file** (`/var/run/erre-eval-tier-c.lock`) を使い、明示的に共有させる:
     ```bash
     flock -n /var/run/erre-eval-tier-c.lock python -m erre_sandbox.cli.eval_tier_c
     ```
     `eval_tier_c` 内部で nvidia-smi preflight → Prometheus 起動 → 評価 → unload を
     一直線で実行、preflight と起動の間に lock を放さない。
  2. **systemd-timer の `Persistent=`**: **`Persistent=false`** を採用 (default 維持を
     明示)。深夜 02:00 fire を miss した場合の catch-up は不要 (autonomous run と
     conflict する確率を下げる)。**skip 時は exit code 75 (EX_TEMPFAIL)** で journal log
     可視性を確保。
  3. **autonomous loop の lock 取得方針**: autonomous loop も同 lock file に
     `flock -s` (shared lock) で touch する形にし、Tier C は `flock -n -x` (exclusive)
     で取得を試みる。autonomous が走っている間は Tier C が即時 fail (skip + log)、
     autonomous が止まっている間のみ Tier C が走れる構造。
- **根拠**:
  - Codex MEDIUM-3: nvidia-smi → Prometheus load の間に他プロセスが load する TOCTOU
  - flock(1) man page: `-n` で immediate fail、合わせて `-x` で exclusive
  - systemd.timer doc: `Persistent=` default false、catch-up が必要なら明示 true
- **棄却**:
  - lock を Prometheus 起動部分のみ → preflight が外れて TOCTOU 残存
  - `Persistent=true` → autonomous run 真昼間 catch-up fire で contention
  - lock 不採用 (preflight だけで判定) → 明確に race condition 残存
- **影響**:
  - `infra/systemd/erre-eval-tier-c.service` の `ExecStart=` が `flock -n -x ... bash -c '...'`
    形式に
  - autonomous loop (M5 ERRE FSM driver) に `flock -s` 追加が必要 (P6 で integrate)
  - `journalctl --user -u erre-eval-tier-c` で skip 履歴が exit 75 として可視
- **re-open 条件**:
  - autonomous run が flock -s を保持できない実装上の制約 → file ベースの
    state machine に置換
  - skip rate が想定より高い (>50%) → スケジュール時間帯見直し

---

## ME-4 — Hybrid baseline ratio: P3a 完了後に確定 (Codex HIGH-3 系の defer ADR)

- **決定 (元案)**: 200 (stimulus battery) / 300 (自然対話) を **default** とし、P3a で
  両 condition × 3 persona の isolated pilot を採取し、bootstrap CI width で
  ratio を確定する。
- **2026-05-01 partial update (P3a-decide Mac セッション、Task 1+2 完了)**:
  - **stimulus 3 cell**: G-GEAR 採取 focal=198 / total=342 / dialogs=168 で 3 persona
    すべて完走済 (data/eval/pilot/_summary.json)。
  - **natural 3 cell**: G-GEAR 採取は M5/M6 zone-drift bug で **partial**
    (kant=6 focal / nietzsche=0 focal / rikyu=6 focal、~13 min wall で kill)。
    本セッションで `InMemoryDialogScheduler.eval_natural_mode=True` を導入して bug
    を解決 (PR `feature/m9-eval-p3a-decide`、ME-8 ADR 参照)。修正後の natural cell は
    G-GEAR 再採取が必要 (本 Mac セッションでは LLM 不在で実機検証不可)。
  - **bootstrap CI 計算**: `src/erre_sandbox/evidence/bootstrap_ci.py` を P5 prep として
    drafted (本来 P5 phase 着手分の前倒し)、`scripts/p3a_decide.py` で stimulus side の
    Burrows Delta + MATTR (lightweight) の CI を計算する経路を整備 (G-GEAR DuckDB の
    rsync 待ち)。NLI / novelty / Empath は `[eval]` extras 必須なので Mac default では
    skip + clear log line で degrade。
  - **判定**: stimulus side のみで ratio を確定するのは統計的に invalid
    (元 ADR の "両 condition で測定" 要件未充足)。**ratio 200/300 default は留保**、
    natural 再採取後に再判定。
- **判定基準 (元案維持)**:
  - Burrows Delta CI width / Vendi CI width / Big5 ICC CI width を両 condition で測定
  - 両条件で sub-metric の **mean CI width が小さい比率** を採用
  - 両者が同等 (差 <10%) なら 200/300 default を維持
- **根拠**:
  - Codex HIGH-3: 元案の「P3 採取後 P3b で 50 turn pilot」は順序 invert + 統計力不足
  - 200 turn は Vendi の 200-turn window を 1 cycle 満たす最小値
  - bootstrap CI width が直接的な測定対象 (DB9 quorum の信頼性)
- **棄却**:
  - 200/300 を data なしで freeze → arbitrary (元案のまま)
  - **stimulus 側 CI のみで ratio 確定**: natural side との **比較**が ratio 決定の
    本質 (元 ADR §判定基準 1) で、片側 CI のみでは比較できない → 棄却
- **影響**:
  - P3a-decide セッションで **partial 完了**: gating bug fix + bootstrap_ci module +
    p3a_decide script は ready、natural 再採取後に最終 ratio 確定
  - ratio 確定までは P3 (golden baseline 採取) 入り保留 — 本来 24h × overnight×2 の
    G-GEAR 採取を、ratio 不確定で着手すると invalidation リスク
- **re-open 条件**:
  - **本 ADR は再採取後に二度目の Edit を要する** (current state = partial):
    1. G-GEAR 再採取で natural side が完走 (focal 30 / total 90 / dialogs ~15)
    2. Mac で `scripts/p3a_decide.py` を両 condition の duckdb に対し run
    3. ratio default 200/300 vs alternative の bootstrap CI width 比較
    4. 確定値で本 ADR を **再 Edit**
  - golden baseline 採取後に DB9 quorum の sub-metric が persona discriminative でない
    と判明 → ratio 再調整 + 再採取検討 (元案維持)
- **partial-close 状態の文脈**:
  - 本 ADR は **2 段階 close**: (1) bug fix + script ready (本セッション)、
    (2) 再採取データで実測値 ratio (次 G-GEAR セッション + 次 Mac セッション)
  - tasklist.md §P3a-decide はチェック項目を分割: "scheduler fix [x]" / "bootstrap CI
    modules ready [x]" / "stimulus-side CI computed (rsync 待ち) [pending]" /
    "ratio ADR 確定 (natural 再採取待ち) [pending]"

- **2026-05-05 partial update #3 (P3a-finalize Mac セッション、lightweight ratio 確定)**:
  - **2 段階 close は不正確だった**: 当初想定の「(2) で最終 close」は Vendi + Big5 ICC
    が P4 territory であることを見落としていた。本 ADR は **3 段階 partial close**
    に再構造化される: (1) bug fix + script ready (2026-05-01 #1) / (2) lightweight
    ratio 実測 (本 update、Burrows + MATTR のみ) / (3) full ratio 実測 (P4 完了後、
    Vendi + Big5 ICC を含めて再判定)。
  - **empirical 実測値** (`data/eval/pilot/_p3a_decide.json`、schema `p3a_decide/v3`):
    - **6 cell rsync 完了** (G-GEAR PR #133 → Mac、md5 6/6 hash 一致)
    - **target-extrapolated ratio** (n_target_stim=200, n_target_nat=300、
      `width × sqrt(n / n_target)` で sample-size 効果除去 — Codex P3a-finalize HIGH-1):
      | metric | stim extrap | nat extrap | nat/stim | n_cells |
      |---|---|---|---|---|
      | Burrows Delta | 6.09 | 2.49 | **0.41** | 2 (kant+nietzsche) |
      | MATTR | 0.0131 | 0.0130 | **0.992** | 3 (全 persona) |
      | combined (mean) | 3.05 | 1.25 | **0.41** | — |
    - **verdict**: `stimulus_wider_at_target_alternative_recommended` (combined ratio
      0.41 → natural が target 換算で 59% 狭い、10% tolerance 大幅超過)
    - **方向性は両 metric で一致** (Burrows 0.41、MATTR 0.992 ≤ 1.0): natural narrower
      or equal at deployed scale → verdict は scale-domination の影響を受けず robust
    - **scale dominance caveat**: Burrows (~6.0 scale) が MATTR (~0.013 scale) を
      ~470x で支配しているため、combined ratio は実質 Burrows 単独の判定。per-metric
      breakdown は `by_condition` で個別公開。
  - **judgment for ratio default (200/300) — provisional**:
    - **lightweight verdict**: 200/300 default を **暫定維持** (適用条件付き、下記)
    - 根拠 1: target-extrapolated で natural が 41% (Burrows) / 99% (MATTR) — natural
      は default budget 300 turn で十分な CI 精度を達成見込み、widen 不要
    - 根拠 2: stimulus が natural より大幅に wider at target → stimulus 200 turn は
      tighter CI 達成のため **追加 turn が望ましい可能性**。ただし 200 turn は
      Vendi 200-turn window 1 cycle の最小値 (元 ADR §根拠 2) で下限制約あり、
      固定維持。
    - 根拠 3: 元 ADR §判定基準 3 「両者が同等 (差 <10%) なら default 維持」は
      本 lightweight 結果では適用不能 (差 59% で同等ではない)、ただし方向性は
      「natural を増やす必要なし」+「stimulus を増やしたいが下限制約」なので
      **default 200/300 が最良の lightweight 判定**となる。
    - 暫定性の根拠: Vendi + Big5 ICC が P4 完了後に異なる方向性を示す可能性あり、
      Rikyu Burrows は Japanese tokenizer 未実装で 2/3 persona のみ寄与 (n_cells=2)。
  - **適用条件 (provisional → final 移行のための再開条件)**:
    - **P4 deliverable**: Vendi Score + Big5 ICC を全 6 cell に対し計算 → ratio
      verdict を再算出。**P4 結果が方向反転** (natural が stimulus より wider at
      target) または **lightweight ratio から 10%超のズレ** → 本 ADR を **partial
      update #4** で再 Edit、ratio default を再評価。
    - **m9-eval-corpus expansion**: rikyu Japanese tokenizer 実装 → Rikyu Burrows
      が 3/3 persona で寄与可能に → ratio 再算出。**ratio が現在値 (0.41) から
      10%超のズレ** → partial update #5 で再 Edit。
    - **DB9 quorum sub-metric 不足**: golden baseline 採取後に persona-discriminative
      が不十分 → ratio 再調整 + 再採取検討 (元案維持)。
  - **追加 caveat (Codex P3a-finalize 反映)**:
    - 本 ADR は ME-4 §判定基準が指す **3 metric (Burrows / Vendi / Big5 ICC)**
      のうち 1/3 metric (Burrows、Rikyu 除く 2/3 persona) + lightweight proxy 1
      metric (MATTR、3/3 persona) のみで判断している。**Vendi + Big5 ICC を含む
      full verdict は P4 territory** で、本 update は lightweight proxy update。
    - 数値の生 source は `data/eval/pilot/_p3a_decide.json` を verbatim 参照する
      (re-derive 防止)。
    - Codex review trail: `codex-review-prompt-p3a-finalize.md` →
      `codex-review-p3a-finalize.md` (Verdict block、HIGH 3 / MEDIUM 4 / LOW 4 全反映)。
  - **partial-close 状態の文脈の改訂**:
    - 本 ADR は **3 段階 partial close** (上記)、本 update で **段階 (2) close**
    - tasklist.md §P3a-decide は段階 (2) のチェック項目すべて [x] 化、段階 (3) を
      M9-D / M9-E (P4) のタスクリスト側で受け継ぐ
    - main 側 implementation: branch `feature/m9-eval-p3a-finalize` (本 PR で merge)、
      script schema bump v1 → v3、`_KNOWN_LIMITATIONS` 経由で rikyu Burrows を
      validation warning routing

---

## ME-5 — RNG seed: hashlib.blake2b で uint64 stable seed (Codex MEDIUM-5)

- **決定**: seed 生成を以下に確定:
  ```python
  import hashlib
  def derive_seed(persona_id: str, run_idx: int, salt: str = "m9-eval-v1") -> int:
      key = f"{salt}|{persona_id}|{run_idx}".encode()
      digest = hashlib.blake2b(key, digest_size=8).digest()
      return int.from_bytes(digest, "big")  # uint64
  ```
  - 5 run × 3 persona = 15 seed を `golden/seeds.json` に commit
  - Mac と G-GEAR の両方で `test_seed_manifest_stable` で identical を assert
  - numpy `Generator(PCG64(seed))` で stream 化
- **根拠**:
  - Codex MEDIUM-5: Python `hash()` は `PYTHONHASHSEED` に salting されプロセス間非決定的
  - blake2b は cryptographic hash で deterministic、digest_size=8 で uint64 適合
  - PCG64 は numpy default、reproducibility が高い
- **棄却**:
  - `hash()` ベース → reproducibility 違反
  - SHA-256 → digest_size 32 で uint64 取り出しが冗長 (blake2b の方が直接的)
- **影響**:
  - `evidence/golden_baseline.py::derive_seed` を導入
  - `golden/seeds.json` を git commit (ascii uint64 list)
  - test 1 件追加 (Mac/G-GEAR 同値性)
- **re-open 条件**:
  - 別 hash algo に project が移行 (例 future Python の hash 強化) → 再評価
  - blake2b の collision 報告 (現実的に零だが)

---

## ME-6 — Burrows reference corpus QC (Codex MEDIUM-6)

- **決定**: 元案の「token count < 50K で z-score noisy」固定閾値を **棄却**、以下の QC
  semantics に置換:
  1. **Tokenization**: per-language tokenizer (独 / 英 / 日)、function word list は
     言語別に curated
  2. **Provenance metadata**: 各 reference corpus に `{source, license, edition,
     translator, year, public_domain: bool}` を YAML で添付 (`evidence/reference_corpus/_provenance.yaml`)
     - Kant 独原典: Akademie-Ausgabe (public domain、確認済)
     - Kant 英訳: 著者 + edition 明記、license 確認 (Cambridge Edition 等)
     - Nietzsche: 独原典 KGW、英訳 Kaufmann (royalty 確認要)
     - Rikyu: 利休百首・南方録 (日本古典、public domain)
  3. **≥5K-word chunk stability test**: corpus を 5K-word chunk に分割し、各 chunk
     から計算した Delta が persona-pair 間で **rank-stable** (Spearman ρ ≥ 0.8) で
     あることを `test_burrows_corpus_qc.py` で fixture 化
  4. **reopen condition**: Delta rank instability (ρ < 0.6) が観測されたら
     blockers.md に reopen 候補を上げる
- **根拠**:
  - Codex MEDIUM-6: 50K は placeholder で empirical 根拠無し
  - Stylometry literature (Computational Stylistics): <5K は確実に poor、20K でも
    text 依存で fail、固定 floor は不適切
  - Eder 2017 "Visualization in stylometry": chunk-based stability test 推奨
- **棄却**:
  - 50K 固定 floor → empirical 根拠無し
  - corpus QC を実施しない → reproducibility と license 双方破綻
- **影響**:
  - `evidence/reference_corpus/_provenance.yaml` 追加
  - `tests/test_evidence/test_tier_a/test_burrows_corpus_qc.py` 追加
  - Cambridge Edition / Kaufmann translation の license 確認が **P1b の prerequisite** に
- **re-open 条件**:
  - chunk stability test で rank instability 検出 → corpus 拡張 or 言語別 fallback
  - 翻訳 license で公表に制約 → public domain edition への切替検討

---

## ME-7 — RoleEval Option A 採択 + MCQ schema / scoring protocol (LOW-1 close、Codex 2026-05-01 review)

- **決定**: 本タスクで `golden/stimulus/{kant,nietzsche,rikyu}.yaml` の RoleEval 10 問は
  **Option A (各 persona に persona-specific biographical / thought-history MCQ 10 問ずつ)** を採択。
  以下の MCQ schema と scoring protocol を確定:

  1. **MCQ item schema (必須 field)**:
     - `stimulus_id` — `roleeval_<persona>_<nn>` 形式 (例: `roleeval_kant_01`)
     - `category: roleeval`
     - `mcq_subcategory` — 5 種カテゴリ均等化 (chronology / works / practice /
       relationships / material_term) を 2 問ずつ計 10 問
     - `prompt_text` — 質問本文 (persona の母語または評価実行語)
     - `options: {A, B, C, D}` — A-D forced choice (4 択固定)、each plausible
       same-type distractor、option order は driver 側で `seeded shuffle` (PCG64
       PerCellSeed = blake2b(seed_root | stimulus_id))
     - `correct_option` — A/B/C/D いずれか (raw ground truth、shuffle 前)
     - `source_ref` — primary/secondary 文献 (`kuehn2001:ch.8` 形式)
     - `source_grade: fact | secondary | legend` — Codex MEDIUM-2 反映、scored
       accuracy は **fact / strong secondary のみ**、`legend` は stimulus 投入は
       するが factuality score から除外
     - `category_subscore_eligible: true | false` — `legend` 由来 / 解釈問は
       `false` で scoring exclude
     - `present_in_persona_prompt: true | false` — Codex MEDIUM-4 反映、true なら
       "prompt consistency" を測ることを明示 (true/false が混在することで factual
       recall vs prompt parroting の diagnosis 化)
     - `ambiguity_note` — option 間で history 解釈に幅がある場合の note (任意)
     - `expected_zone` — peripatos / chashitsu / agora / garden / study (persona の
       MCQ 想起を想定する場)
     - `expected_turn_count: 1` — MCQ は 1 turn 完結

  2. **Scoring protocol (Codex MEDIUM-3 / MEDIUM-5 反映)**:
     - **per-item Δ accuracy**: `Δ_i = persona_run_correct_i − base_control_correct_i`
       を **per item** で計算、persona 内 mean を primary metric。persona 間 absolute
       accuracy ranking には使わない (item difficulty / pretraining exposure / 言語 /
       ambiguity が違うため psychometric equating 未実施)
     - **base control measurement (ME-1 の per-item 拡張)**: persona prompt 無しの
       base model (qwen3:8b raw) で同 MCQ を 1 run、per-item correctness を計測。
       ME-1 が IPIP-NEO control を規定するのに対し、本 ADR は MCQ control を規定
     - **cycle 1 only primary scoring**: 70 stimulus × 3 巡 reps で同一 MCQ が
       3 回露出するため、**cycle 1 (first exposure) のみ primary scoring**、cycle 2/3
       は stimulus 投入のみで scoring exclude (将来 stem variant + option shuffle に
       拡張余地、本タスクでは exclude で確定)
     - **within-persona floor diagnostic**: persona 条件付け済み agent が persona 内
       MCQ で base control を超えること (`Δ_persona_mean > 0` with bootstrap CI 下限
       > 0) を pass 条件とする。floor を割った場合は persona prompt が biographical
       fact を agent に伝達できていない signal

  3. **Distractor design rule**: option B-D は同 type の plausible candidate
     (例: chronology なら同時代 ±20 年、works なら同 corpus 内の別著作、relationships
     なら同 era の別 figure) を必須とし、**表層 cue (option 長さ / 言語 / format) で
     当てられないこと** を contract test で検証

  4. **synthetic 4th persona (DB7 LOW-1 / Codex LOW-2)**: 4th persona 用の MCQ は
     `tests/fixtures/` に置き、`fictional: true, scored: false` で本番
     `golden/stimulus/` から分離。driver / schema fixture としてのみ使用、scoring
     pipeline には流さない (P2c 内 test 範囲、本セッション本体は 3 persona のみ起草)

  5. **wording 整合**: `design-final.md` §Hybrid baseline の "Kant biographical MCQ" を
     "**persona-specific biographical / thought-history MCQ**" に Edit 済 (本 ADR と同 PR)。
     `blockers.md` LOW-1 は closed (Option A 採用) に Edit 済

- **根拠**:
  - Claude trade-off 4 軸 (構成斉一性 / CI 交絡 / persona-factuality dimension /
    drafting 工数) で Option A が支配的
  - Codex `gpt-5.5` (`codex-review-low1.md`、109,448 tokens、2026-05-01) verdict
    "Adopt Option A" + MEDIUM 5 件 + LOW 2 件補強で構造的バイアス除去 (同一モデル
    1 発案では構造的バイアス残存リスク、CLAUDE.md "Codex 連携" 規定に従う)
  - psychometric / NLP-eval literature: per-item Δ は item-level 差分の signal に
    sensitive、cross-persona absolute は equating されないため不採用 (Codex MEDIUM-3)
  - RoleEval 原典 (Shen et al. 2024 arXiv:2312.16132): "MCQ 形式は recall のみ測定、
    生成評価ではない" 性質を **floor diagnostic として明示的に**位置付け、生成評価
    (Wachsmuth / ToM / dilemma) と分離

- **棄却**:
  - Option B (Kant のみ MCQ): per-persona stimulus mass 違いで Vendi/Burrows の
    persona 横比較が交絡 (Claude / Codex 両支持で棄却)
  - Option C (RoleEval 全廃): persona-factuality 軸が消え、style / argumentation /
    ToM の 3 軸偏重に (Claude / Codex 両支持で棄却)
  - Option D (共通 philosophical attribution MCQ): item equating はしやすいが、
    測るものが persona self-knowledge から一般哲学 trivia に寄る、RoleEval の "role
    knowledge" 目的とずれる (Codex LOW-1 で棄却)
  - cross-persona absolute accuracy ranking: psychometric equating 未実施のため不適切
    (Codex MEDIUM-3)
  - `legend` source_grade を scored accuracy に含める: legend は historical record の
    後世形成なので "factuality" を測れない (Codex MEDIUM-2)

- **影響**:
  - `golden/stimulus/_schema.yaml` に MCQ 専用 11 field 追加 (本 ADR §1)
  - `golden/stimulus/{kant,nietzsche,rikyu}.yaml` 各 10 問起草 (chronology 2 / works
    2 / practice 2 / relationships 2 / material_term 2 で均等化)
  - P2c で `evidence/golden_baseline.py::GoldenBaselineDriver` に MCQ scoring
    branch 追加 (per-item Δ / cycle 1 only / option seeded shuffle)
  - P4a で `evidence/tier_b/big5_icc.py` の base control を per-item 拡張 (ME-1 と
    本 ADR の共通基盤化)
  - `tests/fixtures/synthetic_4th_mcq.yaml` (任意、P2c で driver schema test 用)
  - `decisions.md` ME-summary を 6 件 → 7 件に update

- **re-open 条件**:
  - cycle 1 first exposure scoring が item recall として機能しないと判明 (例: 全
    persona / 全 item で base control が ceiling に張り付く) → cycle 1 でも sample
    size 不足の場合、stem variant + option shuffle で cycle 2/3 を再活用検討
  - per-item Δ の bootstrap CI が広すぎる場合 → 10 問では sample size 不足、20 問
    拡張検討
  - `source_grade: legend` の比率が想定より高くなり scoring eligible <50% に落ちる
    場合 → Rikyū item の attested fact 補強 (m9-eval-corpus 後送)
  - persona prompt の `cognitive_habits` から `present_in_persona_prompt: true` 比率
    が偏り、prompt parroting で過度に正答率が上がる場合 → false 比率を 5/10 以上に
    引き上げる item 再設計

---

## ME-8 — eval natural condition の zone gate bypass (P3a-decide gating bug fix)

- **決定**: `InMemoryDialogScheduler.__init__` に **`eval_natural_mode: bool = False`**
  flag を追加。`True` のとき:
  1. `tick()` 内で `_iter_colocated_pairs` の代わりに新規ヘルパ
     `_iter_all_distinct_pairs` を使い、3 persona の **全 distinct pair** を
     zone equality 制約なしで反復
  2. `tick()` 内の `_REFLECTIVE_ZONES` skip を bypass
  3. `schedule_initiate` 内の zone-not-reflective reject を bypass
  4. **cooldown / probability / timeout / 自己 dialog reject / 二重 open reject の
     invariant は両 mode で active のまま** — natural cadence は維持、proximity
     制約のみ削除
- **構築時防御**: `golden_baseline_mode=True` と `eval_natural_mode=True` の同時指定は
  `ValueError` で reject (Codex review LOW-1 反映、両 flag は互いに disjoint な
  capture phase をカバー、組合せの semantics は未定義)
- **CLI opt-in**: `cli/eval_run_golden.py:capture_natural` の scheduler 構築に
  `eval_natural_mode=True` を 1 引数追加 (planning purity 違反は最小)
- **根拠**:
  - **観測**: G-GEAR P3a pilot で natural 3 cell が初動 burst 2-3 dialogs (= 12-18
    utterances) で完全停止。stimulus 3 cell は同条件で focal=198 完走 → natural 専用の
    gating 挙動が発火していた
  - **root-cause**: `personas/{nietzsche,rikyu}.yaml` の `preferred_zones` が AGORA を
    含まない (Nietzsche=[peripatos,study,garden], Rikyu=[chashitsu,garden,study])。
    LLM が `destination_zone` を選び、`_resample_destination_to_persona_zone`
    (cognition/cycle.py:828) は `os.environ.get("ERRE_ZONE_BIAS_P", "0.2")` で
    20% でしか preferred bias を発火させない。**80% は LLM choice を honor** →
    数 tick 後に AGORA から散る → `_iter_colocated_pairs` が 0 pair → admit 停止
  - **計算根拠**: per-tick zone change rate ≈ (4/6) × (1 - 0.2) = 53%、
    3-tick 後 1 名以上 scatter 確率 = 1 - 0.47^3 ≈ 89% (観測症状と一致)
  - **代案比較**: `decisions.md` 関連の `design-natural-gating-fix.md` §5 で
    4 案比較。代案 B (preferred_zones=[AGORA] override) は bias_p=0.2 で 53% leak、
    代案 A (world/ 層で MoveMsg drop) は planning purity 違反、代案 C (pair set API)
    は boolean flag より重い。**初回案 (scheduler flag) を採用**
  - **Codex `gpt-5.5 xhigh` independent review** (`codex-review-natural-gating.md`):
    HIGH=0 / MEDIUM=0 / LOW=2 で **Verdict: ship**。LOW-1 (両 flag 組合せ防御) と
    LOW-2 (docstring "ordered" → "unordered") は本 ADR commit 前に反映済
- **棄却**:
  - 代案 A (world/ 層 MoveMsg drop): planning purity 違反、M5/M6/M7ζ dwell+phase
    wheel との相互作用リスク
  - 代案 B (preferred_zones=[AGORA] override CLI 単独): `ERRE_ZONE_BIAS_P=0.2`
    default で 53% leak 残存
  - 代案 B+ (env var 強制 1.0 + preferred override): env mutation hack で
    diagnosability 低
  - 代案 C (explicit pair set API): boolean flag より重い、conceptual gain なし
  - persona zone 制約の default 緩和: M4 frozen Protocol contract 違反
- **影響**:
  - `src/erre_sandbox/integration/dialog.py`: flag 追加 + 構築時 reject + tick()/
    schedule_initiate() の bypass + `_iter_all_distinct_pairs` ヘルパ
  - `src/erre_sandbox/cli/eval_run_golden.py`: capture_natural の scheduler 構築に
    `eval_natural_mode=True` を 1 引数追加 (CLI ロジックは不変)
  - `tests/test_integration/test_dialog_eval_natural_mode.py`: 12 unit test
    (Red→Green 転換 + 5 invariant + 構築時 reject)、既存 1221 PASS は default
    False で完全互換 (本セッション full suite 1248 PASS)
  - 次 G-GEAR セッションで natural 再採取時に修正効果を実機検証
- **再採取での観測ターゲット**:
  - focal=30 / total=90 / dialogs ~15 を **30-60 min wall** で完走
  - 既存 dialog の utterance 内容に大きな変化はない見込み (LLM prompt は同一、
    physical zone のみ自由化)
  - `last_close_tick` のクラスタ的な spread を logs で確認 (cooldown が effective
    に活きていれば 30+ tick 間隔で admit が分散)
- **re-open 条件**:
  - **fix 後も admit が初動 burst で停止する場合** → root cause の他要因を再特定
    (仮説 B/C を再評価)。ERRE_ZONE_BIAS_P 周りの cognition / runtime 側に追加 bug
    がある可能性
  - **逆に admit 過多で natural cadence が壊れる場合** → AUTO_FIRE_PROB_PER_TICK
    の 0.25 を eval 用に低めに調整、または cooldown 延長
  - **golden_baseline_mode と組合せたいケースが将来発生** → 構築時 reject の
    緩和ルールを ADR child で起票 (cooldown/timeout の "両 flag union" semantics
    定義)

### ME-8 amendment 2026-05-01 (P3a-decide v2 — cooldown × cognition_period)

**Trigger**: 上記 §re-open 条件 第 1 項「fix 後も admit が初動 burst で停止する
場合」が PR #131 G-GEAR Phase A 再採取で **発火** (kant_natural sanity:
focal=6/30、wall 10 min timeout)。

**Empirical evidence**: 600 s wall で max(world_tick)=5 → cognition_period
≈ 120 s/tick (qwen3:8b Q4_K_M on RTX 5060 Ti / Ollama 0.22.0)。
実効 cooldown = `COOLDOWN_TICKS=30` × 120 s = **60 min wall** ⇒ 10 min wall 内で
再 admit 物理的不可能。design v1 §2 で「△ 補助」として棄却した仮説 B
(cooldown × cognition_period の wall 換算) を empirical で **◎ 主因に格上げ**。
v1 fix の効果範囲: nietzsche starve 解消 (zone bypass 機能、3 pair 全 admit) は
確認済。残存 gate は cooldown のみ。

**Amendment to §決定**: `eval_natural_mode=True` のときの cooldown threshold を
`COOLDOWN_TICKS=30` flat から `COOLDOWN_TICKS_EVAL=5` に分離。`_effective_cooldown()`
helper を `InMemoryDialogScheduler` に導入し、`schedule_initiate` / `tick()` の
cooldown check を経由化。live mode (`eval_natural_mode=False`) の `COOLDOWN_TICKS=30`
は完全不変。

**Amendment to §構築時防御**: `eval_natural_mode=True` × `golden_baseline_mode=True`
の同時指定 reject (v1 LOW-1 反映) は維持。`COOLDOWN_TICKS_EVAL` の semantics は
eval mode 内のみで意味を持つので、両 flag union ケースを将来許可する場合は別 ADR
child で union semantics を定義する (v1 §re-open 条件 第 3 項を引き継ぎ)。

**Amendment to §影響 (semantic naming)**: eval mode の cooldown=5 を live
multi-agent の "natural cadence" と区別し、**"eval cadence calibration"** として
位置付け (Codex Q6 反映)。dialog_turn_budget=6 が 6 ticks 占有を強制し、5 ticks
cooldown と合わせて 11 ticks/cycle (≈ 22 min wall) の effective cycle を作る。
これは empirical な G-GEAR cognition_period に校正された値であり、別 backend
環境では再校正必要。

**Amendment to §再採取での観測ターゲット**:
- focal=30 / total=90 / dialogs ~15 を **120 min wall** で完走 (`_DEFAULT_WALL_TIMEOUT_MIN`
  default 90 → 120 min に拡張、Codex Q3 verdict 反映)
- conservative estimate (design-v2.md §5.1): wall=120 min × cognition_period 120 s/tick
  → 60 ticks → 60 / 11 ticks-per-cycle ≈ 5 cycle (per pair)、3 pair で
  4 cycle × 18 utt × (1/3 share) ≈ **focal 24/cell が下限期待値**
- `last_close_tick` の cluster spread が 5 tick + 6 tick = 11 tick 間隔で並ぶことを
  logs で確認 (cooldown が effective に活きていれば admit が均等分散)

**Amendment to §re-open 条件 (三度目)**:
- **fix v2 後も focal<25 で stop** → 別 dominant gate (prob 0.25 variance / 推論
  deadlock / world_tick 進行停止) を再特定。Codex Q7 反映で γ (prob=1.0) を新規
  ADR child で起票
- **推論 backend が変わって cognition_period が 60s 以下 / 240s 以上に変動** →
  COOLDOWN_TICKS_EVAL=5 の妥当性を再評価 (60s なら cooldown=10 候補、240s なら
  cooldown=3 候補、empirical 再採取で確定)
- **wall=120 min × 3 cell parallel で run-time が 6h overnight に伸びた場合** →
  ι (1 cell 逐次) への切り替え検討 (Codex Q1 reference、conceptually clean だが
  運用コスト trade-off)

**Codex `gpt-5.5 xhigh` independent review v2**: `codex-review-natural-gating-v2.md`
(145,717 tokens) verbatim 保存。Verdict: **revise** → HIGH 2 / MEDIUM 2 / LOW 1
全反映後 ship 相当。HIGH-1 (wall default 不整合) と HIGH-2 (既存 cooldown test
rewrite) は本 PR の改訂で解消、MEDIUM-1 (ME-8 explicit amendment) は本 amendment
block 自体、MEDIUM-2 (conservative estimate primary 化) は design-v2.md §5.1。
LOW-1 は cosmetic、prompt artifact は historical record として保持。

**Test 影響**: `test_dialog_eval_natural_mode.py` 既存 12 件のうち
`test_eval_natural_mode_preserves_cooldown_via_tick` と
`test_eval_natural_mode_sustains_admission_after_initial_burst` の 2 件は
`COOLDOWN_TICKS_EVAL=5` 参照に rewrite (test 件数不変)。新規 3 件
(`test_effective_cooldown_returns_eval_value_when_flag_true` /
`test_effective_cooldown_returns_live_value_when_flag_false` /
`test_live_mode_cooldown_unchanged_via_tick`) を `test_dialog_eval_natural_mode.py`
に追加。CLI test 1 件 (`test_wall_timeout_min_default_is_120`) を
`tests/test_cli/test_eval_run_golden.py` に追加 (このファイルは
`pytestmark = pytest.mark.eval` でモジュール全体が default CI から deselect される
既存規約、`-m eval` で個別実行可)。

**Full suite 数値** (baseline = origin/main 491db4b: 1248 passed / 31 skipped /
26 deselected): 本 PR では **1251 passed (+3)** / 31 skipped / 27 deselected (+1、
CLI test の eval marker 経由)。dialog test 3 件は default CI に組み込まれ、CLI
test 1 件は `-m eval` で別途検証 (single-shot 実測 PASS 確認済)。

---

## ME-9 — Phase 2 run0 wall-timeout incident: CLI partial-publish contract + run1 calibration (Codex 2026-05-06 HIGH 4)

- **決定**:
  1. **CLI fix scope** (別タスク `m9-eval-cli-partial-fix` で実装、Plan +
     /reimagine 必須):
     - `_SinkState` に `soft_timeout: str | None` 追加 (現 `fatal_error` と分離)
     - `CaptureResult` に `partial_capture: bool` + `stop_reason: str` +
       `drain_completed: bool` 追加
     - wall timeout path で `<output>.capture.json` sidecar 永続化 (schema:
       `{status, stop_reason, focal_target, focal_observed, total_rows,
       wall_timeout_min, drain_completed, runtime_drain_timeout, git_sha,
       captured_at}`)
     - `_async_main` return code: 0 (complete) / 2 (fatal、現状維持) /
       **3 (partial_publish 新設)**
     - `eval_audit` CLI 新設 (`src/erre_sandbox/cli/eval_audit.py`):
       `focal >= target` AND `sidecar.status == "complete"` を機械的に gate、
       partial は別 exit code で audit fail
     - `_resolve_output_paths` の stale `.tmp` unlink 前に sidecar 存在 + status
       チェック、partial salvage の意図を明示する flag (`--allow-partial-rescue`)
       追加検討
  2. **Phase 2 採取戦略**:
     - run1 を **600 min single calibration cell** (kant のみ 1 cell、3-parallel
       でない 1-only) で先行実行、120/240/360/480 min 時点で focal / total /
       memory sqlite row count / Ollama latency を記録
     - 結果から run2-4 の wall budget を empirical 確定 (Codex H1: 600 min が
       最低ライン、安全率 0.85 で計算)
     - run0 partial は **primary 5 runs matrix から外す** (Codex H2: prefix
       censoring で memory growth / fatigue / prompt-length の late-run signal
       系統欠落)、`data/eval/partial/` 隔離 + `partial_capture=true` sidecar 付き
       diagnostic 専用
     - run0 を 500 focal で **再採取** (CLI fix + audit CLI merge 完了後)
  3. **G-GEAR rescue verify (Phase A、本 ADR 確定後即時)**: `.tmp` +
     `.tmp.wal` 存在 + DuckDB read/count 検証を CLI fix 完了前に実施、結果を
     `.steering/20260430-m9-eval-system/blockers.md` の incident block に記録

- **根拠**:
  - empirical 観測: 3 cell wall=360 min で focal=381/390/399 (76-80% prefix
    censoring)、focal/hour ≈65、3-parallel contention 2.0x+ (事前推計 1.5x の
    1.33x 過小評価)
  - Codex `gpt-5.5 xhigh` review (`codex-review-phase2-run0-timeout.md`、
    281,778 tokens、Verdict: revise) で Claude 単独案の 4 HIGH 級欠陥切出:
    - H1 (480 min 不足): `65*8*0.85=442 < 500`、600 min 最低ライン
    - H2 (run0 primary 採用 NG): wall-time prefix censoring は random missing
      では無く、`width * sqrt(n / n_target)` (`scripts/p3a_decide.py:360` の
      iid sample-mean 近似) の前提崩壊
    - H3 (return 0 + canonical NG): HIGH-6 contract 違反、audit/analytics/
      training egress が誤採用するリスク
    - H4 (salvage-first NG): SIGKILL/OOM では `.tmp` も消失、stale `.tmp` は
      次回起動で `unlink()`
  - DuckDB doc: CHECKPOINT は WAL を main file 同期、CLI close も persistent
    DB を checkpoint/close (Python `finally` 到達時のみ保証)

- **棄却**:
  - **Claude 単独案の 480 min budget continuation** (Codex H1) — 500 未達
    濃厚で再 timeout 連鎖

exec
/bin/zsh -lc "sed -n '1,420p' .steering/20260430-m9-eval-system/codex-review-p4a.md" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
Reading prompt from stdin...
OpenAI Codex v0.125.0 (research preview)
--------
workdir: /Users/johnd/ERRE-Sand Box
model: gpt-5.5
provider: openai
approval: never
sandbox: workspace-write [workdir, /tmp, $TMPDIR, /Users/johnd/.codex/memories] (network access enabled)
reasoning effort: xhigh
reasoning summaries: none
session id: 019e06b6-e777-7631-92c3-ec17b3365e47
--------
user
# Codex independent review request — M9-eval-system P4a Tier B 起草

## 役割

あなたは ERRE-Sandbox プロジェクトの **independent reviewer**。Claude が起草
した P4a Tier B 設計案 (v1 + v2 + comparison v3) を **同一モデル 1 発生成の
構造的バイアス** から救出するために招かれている。Verdict + 優先度付き finding
+ web-search-based prior art 引用で reply してほしい。要約禁止、verbatim 保存
される。

## 報告フォーマット (厳守)

1. **Verdict**: 一行 — `APPROVE` / `ADOPT-WITH-CHANGES` / `REJECT`
2. **HIGH** finding (must reflect before merge): 各 finding に
   `[HIGH-N] title` + ≥3 行 rationale + 引用 (URL or paper)
3. **MEDIUM** finding (decisions.md ADR 反映): `[MEDIUM-N]`
4. **LOW** finding (blockers.md defer 可): `[LOW-N]`
5. **Prior art summary** (web search 必須): 下記 §「Prior art 必須調査」5 件全件
6. **Closing note**: v3 hybrid を採用すべきか / v1 / v2 / 別案

## Mission の再掲

`src/erre_sandbox/evidence/tier_b/` をゼロから起草、LoRA 採用判定 (DB9 quorum)
の 3 sub-metric (Vendi Score / Big5 stability ICC / Burrows Δ) のうち Tier B
新規 2 (Vendi / Big5 ICC) + IPIP-NEO administering helper を提供する。Burrows
Δ は `tier_a/burrows.py` 既存。

DB9 quorum (M9-B `decisions.md` DB9):
- adoption: 3 sub-metric の 2-of-3 が `BootstrapResult` の CI で baseline positive
- rollback: 2-of-3 が baseline negative
- Tier A=floor diagnostic、Tier C=defensive canary、**Tier B=offensive gate
  唯一の arbiter**

## 必読 reference files (本セッション scope 内、独立 read 可能)

### Claude 設計案 (3 件、本 prompt の review 対象)

- `.steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md` (infrastructure-first)
- `.steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md` (psychometric-rigor-first)
- `.steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md` (hybrid v3 candidate)

### ADR 制約 (絶対遵守)

- `.steering/20260430-m9-b-lora-execution-plan/decisions.md` DB1-DB11 (M9-B)
- `.steering/20260430-m9-eval-system/decisions.md` ME-1〜ME-9 (M9-eval)
- `.steering/20260430-m9-eval-system/design-final.md` (Tier B が DB9 で果たす役割)

### 既存 infrastructure (流用先)

- `src/erre_sandbox/evidence/bootstrap_ci.py` — `BootstrapResult`,
  `hierarchical_bootstrap_ci(values_per_cluster, *, block_length=50,
  cluster_only=False, auto_block=False, n_resamples=2000, ci=0.95, seed=0)`,
  `estimate_block_length()` (PR #146 P5 hardening)
- `src/erre_sandbox/evidence/tier_a/empath_proxy.py` — proxy framing docstring
  雛形 (DB10 honest framing)
- `src/erre_sandbox/evidence/tier_a/novelty.py` — MPNet
  (`paraphrase-multilingual-mpnet-base-v2`) lazy-load パターン
- `src/erre_sandbox/evidence/eval_store.py` — DuckDB schema、`metrics.tier_b`
  table column (`run_id/persona_id/turn_idx/metric_name/metric_value/notes`)、
  `connect_training_view()` は `raw_dialog.dialog` projection only (DB5
  contract)

### Codex 過去 review 履歴 (本タスクと同質補正期待の文脈)

- `.steering/20260430-m9-eval-system/codex-review.md` (P5 HIGH-2 hierarchical
  bootstrap、HIGH-3 Vendi 200-turn 最小、HIGH-5 Burrows L1)
- 過去 5 連続 (P3a-finalize / Phase 2 run0 / CLI partial-fix / run1 calibration /
  ME-9 trigger) で Claude solo 検出不能の HIGH を切出した empirical 実績あり

## v3 hybrid の要点 (review 対象)

| Q | v3 commitment |
|---|---|
| Q1 Vendi kernel | hybrid (semantic MPNet 0.7 + lexical 5-gram 0.3) |
| Q1 window | 100 turn (design-final 整合) |
| Q2 IPIP-NEO 版 | IPIP-50 (Goldberg 1992、日本語 Murakami 2002/2003 流用) |
| Q3 ICC formula | ICC(2,k) consistency primary + ICC(A,1) absolute agreement diagnostic |
| Q4 bootstrap | `cluster_only=True` primary + `auto_block=True` diagnostic 併載 |
| Q5 LIWC alternative | DB10 Option D 通り全廃、Tier B 全 module 冒頭 docstring に honest framing |

## Prior art 必須調査 (web search 強制、verbatim 引用)

以下 5 件全件で literature 引用を伴う finding を出してほしい。1 件でも skip した
ら REJECT 扱い。

1. **Vendi Score 2023 paper** (https://arxiv.org/abs/2210.02410) の kernel 選択
   - hybrid kernel (semantic + lexical) の prior art 有無
   - 100-turn vs 200-turn window の minimum sample size 議論
   - orthogonal one-hot で score=N が成立する数学的条件
2. **IPIP-NEO Mini-20 vs IPIP-50** (Donnellan et al. 2006、Goldberg 1992)
   - Cronbach α の dimension-level reliability 比較
   - LLM personality assessment の 2024-2026 prior art (e.g.,
     Salecha et al. 2024 arXiv 2405.06058、Huang et al. arXiv 2310.01386 等)
   - Mini-20 が ICC<0.6 trigger を不当発火させるリスク
3. **ICC for LLM personality stability** prior art (2024-2026)
   - ICC(2,k) consistency vs ICC(A,1) absolute agreement の選択基準
   - Koo & Li 2016 cutoff (0.5/0.75/0.9) が absolute agreement に適用可か
   - drift detection 文脈での appropriate ICC formula
4. **LIWC vs Empath empirical equivalence** (Fast et al. 2016)
   - DB10 Option D (LIWC 全廃) の justifiability
   - Tier A Empath proxy framing が DB10 honest framing 要件を満たすか
5. **Mini-IPIP / IPIP-50 日本語版** (Murakami 2002/2003)
   - 利用条件 (open / 学術 / 商用)、license, retrieval URL
   - cross-language validation 問題

## review で必ず check してほしい質問群

下記は launch prompt §「Codex review で必須に問うこと」全件を細分化したもの。
省略禁止。

### Vendi 関連

- Q1A: hybrid kernel weight 0.7/0.3 の妥当性 (Friedman & Dieng 2023 Section 4)
- Q1B: window 100 turn が Vendi spectrum stability に sufficient か
  (Codex 過去 HIGH-3 で 200-turn 最小と指摘、v3 で 100 維持の trade-off)
- Q1C: orthogonal one-hot で score=N が成立する条件と sanity test 設計
- Q1D: multilingual (ja+en mixed) で MPNet kernel が semantic similarity を
  fairly 測れるか

### IPIP-NEO 関連

- Q2A: IPIP-50 vs Mini-IPIP-20 の Cronbach α gap が ME-1 fallback (ICC<0.6)
  trigger 判定に与える影響
- Q2B: 日本語 IPIP-50 (Murakami 2002/2003) の利用 license 確認、
  defer 必要なら fallback path
- Q2C: persona-conditional prompt (kant/rikyu/nietzsche system prompt + IPIP-NEO
  item) の framing が social desirability bias (Salecha 2024) に耐えるか
- Q2D: 5-point Likert vs 7-point Likert の trade-off (LLM agentic loop 文脈)
- Q2E: balanced reverse-keyed item 比率 (~50%) の妥当性

### Big5 ICC 関連

- Q3A: ICC(2,k) consistency と ICC(A,1) absolute agreement のどちらを ME-1
  trigger primary にするべきか
- Q3B: ME-1 threshold 0.6 (point) / 0.5 (lower CI) が absolute agreement にも
  literally 適用可か、再評価必要か
- Q3C: per-window n=100 turn が ICC 計算に sufficient か (rule-of-thumb / power
  analysis literature)
- Q3D: identical 回答列 → ICC = 1.0 の sanity test が両 formula で成立するか
- Q3E: 5 run × 5 window = 25 cluster で ICC 信頼区間が construct validity に
  耐えるか

### bootstrap 関連

- Q4A: `cluster_only=True` primary + `auto_block=True` diagnostic 併載が JSON
  consumer 側で混乱を招かないか
- Q4B: PR #146 で `cluster_only` を承諾した HIGH-2 framing と矛盾しないか
- Q4C: 25 cluster (cluster_only) と 12.5 cluster (200-turn window 案) の
  effective sample size 比較
- Q4D: bootstrap CI が persona-conditional でなく pooled で運用される場合の
  variance underestimation リスク

### LIWC 関連

- Q5A: DB10 Option D (LIWC 全廃) の literature justifiability
- Q5B: Tier B 全 module 冒頭 docstring の honest framing 文言が DB10 要件を
  satisfied するか (`empath_proxy.py` 雛形と同等の rigor か)

### 設計全体

- Q6A: v3 hybrid が v1 + v2 の structural bias を残していないか (independent
  reviewer 視点)
- Q6B: `metrics.tier_b` の column schema (`turn_idx` を `window_index` 意味で
  再利用) の semantic abuse リスク
- Q6C: DB11 contamination prevention (PR #145) の Tier B 観点 follow-up
- Q6D: P5 残課題 2 件 (Vendi orthogonal one-hot test / Big5 ICC 1.0 convergence
  test) を本 PR で close する妥当性

## 出力先

verdict + finding は **そのまま raw text** で reply。Claude が
`.steering/20260430-m9-eval-system/codex-review-p4a.md` に **verbatim 保存**
する (要約禁止)。

## 工数 expectation

- web search 5 件全件 + finding 起票で **30-40 分**、token 予算 ~150K-200K
  程度を想定 (`.codex/budget.json` の per-invocation max 内)

## 最後に

直近 5 連続の Codex review で Claude solo 検出不能の HIGH を毎回切り出してきた
empirical 実績がある。本 review でも同質の補正を期待する。Adopt-with-changes
が default expected verdict。

hook: SessionStart
hook: SessionStart Completed
hook: UserPromptSubmit
hook: UserPromptSubmit Completed
codex
I’ll treat this as a review task and use `$erre-workflow` as the entry point. I’m going to read the target design/ADR files first, then run the required web search before forming findings.
exec
/bin/zsh -lc "sed -n '1,220p' .agents/skills/erre-workflow/SKILL.md" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "sed -n '1,220p' .agents/skills/project-status/SKILL.md" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
---
name: erre-workflow
description: >
  ERRE-Sandbox task workflow for Codex. Use when starting, designing, implementing,
  reviewing, or finishing repository work; when the user mentions /start-task,
  /add-feature, /fix-bug, /refactor, /reimagine, /review-changes, or /finish-task;
  or when .steering records, Codex setup, task plans, or implementation handoffs are needed.
---

# ERRE Workflow

This is the Codex-native replacement for the Claude slash-command workflow. Claude command
files in `.claude/commands/` are reference material only; Codex should execute the workflow
through normal tool use, `.steering/` records, skills, hooks, and custom agents.

## Quick Start

1. Read `AGENTS.md`, `docs/development-guidelines.md`, and the relevant domain skill.
2. Create or update `.steering/YYYYMMDD-task-name/` before implementation work:
   `requirement.md`, `design.md`, and `tasklist.md` are required.
3. For design-heavy work, keep implementation paused until a plan is accepted. If the task
   has multiple plausible designs, perform a reimagine pass before editing source files.
4. Implement in small steps, updating `tasklist.md` as work completes.
5. Verify with focused checks first, then the documented full checks when feasible.
6. Finish by reviewing the diff and recording any decisions or limitations.

Use subagents only when the user explicitly asks for delegation or parallel agent work.
When they do, prefer the project-scoped agents in `.codex/agents/`.

## Task Start

Create `.steering/YYYYMMDD-task-name/` with:

- `requirement.md`: background, goal, scope, out of scope, acceptance criteria.
- `design.md`: approach, changed areas, compatibility, test strategy, rollback.
- `tasklist.md`: checkboxes at roughly 30-minute granularity.
- `decisions.md`: only for meaningful tradeoffs or policy choices.
- `blockers.md`: only when blocked or carrying deferred risk.

Use the current local date in `YYYYMMDD`. Prefer a short kebab-case task name.

## Implementation Flows

- **Feature**: read existing patterns, document the design, implement narrowly, add tests or
  verification proportional to risk, update docs when behavior changes.
- **Bug fix**: reproduce or explain the failure, record root cause, add or identify a
  regression check when feasible, then make the smallest defensible fix.
- **Refactor**: establish current checks first, preserve behavior, change in small steps,
  and avoid mixing feature or bug-fix work into the same task.

For source edits under `src/erre_sandbox/`, always consider:

- `architecture-rules` for layer direction and GPL/cloud API constraints.
- `python-standards` for Python style.
- `error-handling` when async, retry, timeout, WebSocket, sqlite, or LLM fallback behavior changes.
- `test-standards` when adding or changing tests.

## Reimagine

Use this for architecture, public interfaces, difficult bugs, and designs with multiple
credible approaches:

1. Save the first plan as `design-v1.md`.
2. Re-read only `requirement.md` and produce a fresh alternative in `design.md`.
3. Compare the two in `design-comparison.md`.
4. Choose v1, v2, or a hybrid and record the reason in `decisions.md`.

Do not use reimagine after implementation has already created side effects that would need
manual rollback.

## Review And Finish

Before final delivery:

- Run focused checks for touched areas.
- Run `uv run ruff check src tests`, `uv run ruff format --check src tests`,
  `uv run mypy src`, and `uv run pytest` when feasible.
- Review `git diff` for unrelated changes and do not revert user work.
- Update `tasklist.md` and `design.md` with what actually happened.
- Mention skipped checks or residual risk in the final response.

Do not commit unless the user asks. If committing, use `git-workflow`.

 succeeded in 0ms:
---
name: project-status
description: >
  プロジェクトの現在の状態をリアルタイムで取得する。
  作業を始める前・コンテキストが分からなくなった時・進捗を確認したい時・
  最近の変更を把握したい時に使う。git 状態・最近のコミット・
  構築フェーズの進捗 (.steering/_setup-progress.md)・未対応 TODO・
  変更ファイル統計を一括で取得する。セッション開始時の状況把握にも使える。
---

# Project Status

このスキルは現在のプロジェクト状態を動的に取得します。

## 現在の git 状態

!`git status --short`

## 最近のコミット (10 件)

!`git log --oneline -10 2>/dev/null || echo "(no commits yet)"`

## 現在のブランチ

!`git branch --show-current`

## 構築フェーズ進捗

!`grep -E "^\- \[" .steering/_setup-progress.md 2>/dev/null | head -20 || echo "(progress file not found)"`

## 未対応 TODO の数

!`grep -r "TODO\|FIXME\|HACK\|XXX" src/ tests/ 2>/dev/null | wc -l`

## 変更ファイルの統計 (直近コミットとの差分)

!`git diff --stat HEAD 2>/dev/null || echo "(no HEAD yet)"`

## 最近変更されたファイル (24 時間以内)

!`find src/ tests/ -name "*.py" -newer .git/index -mtime -1 2>/dev/null | head -10`

## Skills ディレクトリ

!`ls .agents/skills/ 2>/dev/null || echo "(no skills yet)"`

## あなたのタスク

上記の動的データを分析し、以下を報告してください:

1. **現状サマリ** — 現在のフェーズと進捗を 1-2 行で
2. **進行中の作業** — 未コミットの変更や直近の変更ファイルから何が進んでいるか
3. **注意すべき点** — 多数の未コミット変更、TODO の偏り、進捗ファイルとの乖離など
4. **推奨される次のアクション** — 何を優先すべきか (setup フェーズであればどのコマンドを次に実行すべきか)

レポートは簡潔に。詳細は必要に応じてユーザーが追加で質問する。

codex
`$erre-workflow` confirms this is a review-only path, so I won’t create or edit steering files. I’m now reading the three Claude proposals plus the binding ADR/design files and the existing Tier A/bootstrap/store code that constrains Tier B.
exec
/bin/zsh -lc 'wc -l .steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md .steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md .steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md .steering/20260430-m9-b-lora-execution-plan/decisions.md .steering/20260430-m9-eval-system/decisions.md .steering/20260430-m9-eval-system/design-final.md .steering/20260430-m9-eval-system/codex-review.md src/erre_sandbox/evidence/bootstrap_ci.py src/erre_sandbox/evidence/tier_a/empath_proxy.py src/erre_sandbox/evidence/tier_a/novelty.py src/erre_sandbox/evidence/eval_store.py' in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
     391 .steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md
     216 .steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md
     147 .steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md
     326 .steering/20260430-m9-b-lora-execution-plan/decisions.md
     713 .steering/20260430-m9-eval-system/decisions.md
     615 .steering/20260430-m9-eval-system/design-final.md
    3944 .steering/20260430-m9-eval-system/codex-review.md
     389 src/erre_sandbox/evidence/bootstrap_ci.py
      81 src/erre_sandbox/evidence/tier_a/empath_proxy.py
     108 src/erre_sandbox/evidence/tier_a/novelty.py
     436 src/erre_sandbox/evidence/eval_store.py
    7366 total

exec
/bin/zsh -lc 'rg -n "DB9|DB10|DB11|DB5|ME-1|ME-9|Tier B|Vendi|ICC|Burrows|tier_b|turn_idx|connect_training_view|BootstrapResult|cluster_only|auto_block|estimate_block_length" .steering/20260430-m9-b-lora-execution-plan/decisions.md .steering/20260430-m9-eval-system/decisions.md .steering/20260430-m9-eval-system/design-final.md .steering/20260430-m9-eval-system/p4a-tier-b-design-v1.md .steering/20260430-m9-eval-system/p4a-tier-b-design-v2.md .steering/20260430-m9-eval-system/p4a-tier-b-design-comparison.md .steering/20260430-m9-eval-system/codex-review.md src/erre_sandbox/evidence/bootstrap_ci.py src/erre_sandbox/evidence/eval_store.py src/erre_sandbox/evidence/tier_a/empath_proxy.py src/erre_sandbox/evidence/tier_a/novelty.py' in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
.steering/20260430-m9-eval-system/decisions.md:6:5 要素 (決定 / 根拠 / 棄却 / 影響 / re-open 条件)。本 ADR set は M9-B DB1-DB10 と
.steering/20260430-m9-eval-system/decisions.md:14:## ME-1 — IPIP-NEO fallback trigger operational definition (Codex MEDIUM-1)
.steering/20260430-m9-eval-system/decisions.md:18:  - **trigger**: golden baseline 採取後 (3 persona × 5 run の Big5 ICC 計測完了時点) に
.steering/20260430-m9-eval-system/decisions.md:19:    **≥2/3 personas で ICC 点推定 < 0.6 OR 95% lower CI bound < 0.5**
.steering/20260430-m9-eval-system/decisions.md:20:  - **検出 timing**: P5 (bootstrap CI) 完了直後の自動チェック、`evidence/tier_b/big5_icc.py`
.steering/20260430-m9-eval-system/decisions.md:27:  - Codex MEDIUM-1: 「ICC < 0.6 が頻発」の頻発に denominator 無し → 監査不能
.steering/20260430-m9-eval-system/decisions.md:30:  - Koo/Li ICC 解釈: 0.5-0.75 = moderate (effectsize docs)、0.6 boundary は
.steering/20260430-m9-eval-system/decisions.md:39:  - `evidence/tier_b/big5_icc.py` に diagnostic 4 種 (ICC point, lower CI, acquiescence,
.steering/20260430-m9-eval-system/decisions.md:63:     の `connect_training_view()` / `connect_analysis_view()` の両 entry で wrapper enforced)
.steering/20260430-m9-eval-system/decisions.md:139:    Burrows Delta + MATTR (lightweight) の CI を計算する経路を整備 (G-GEAR DuckDB の
.steering/20260430-m9-eval-system/decisions.md:146:  - Burrows Delta CI width / Vendi CI width / Big5 ICC CI width を両 condition で測定
.steering/20260430-m9-eval-system/decisions.md:151:  - 200 turn は Vendi の 200-turn window を 1 cycle 満たす最小値
.steering/20260430-m9-eval-system/decisions.md:152:  - bootstrap CI width が直接的な測定対象 (DB9 quorum の信頼性)
.steering/20260430-m9-eval-system/decisions.md:168:  - golden baseline 採取後に DB9 quorum の sub-metric が persona discriminative でない
.steering/20260430-m9-eval-system/decisions.md:178:  - **2 段階 close は不正確だった**: 当初想定の「(2) で最終 close」は Vendi + Big5 ICC
.steering/20260430-m9-eval-system/decisions.md:181:    ratio 実測 (本 update、Burrows + MATTR のみ) / (3) full ratio 実測 (P4 完了後、
.steering/20260430-m9-eval-system/decisions.md:182:    Vendi + Big5 ICC を含めて再判定)。
.steering/20260430-m9-eval-system/decisions.md:189:      | Burrows Delta | 6.09 | 2.49 | **0.41** | 2 (kant+nietzsche) |
.steering/20260430-m9-eval-system/decisions.md:194:    - **方向性は両 metric で一致** (Burrows 0.41、MATTR 0.992 ≤ 1.0): natural narrower
.steering/20260430-m9-eval-system/decisions.md:196:    - **scale dominance caveat**: Burrows (~6.0 scale) が MATTR (~0.013 scale) を
.steering/20260430-m9-eval-system/decisions.md:197:      ~470x で支配しているため、combined ratio は実質 Burrows 単独の判定。per-metric
.steering/20260430-m9-eval-system/decisions.md:201:    - 根拠 1: target-extrapolated で natural が 41% (Burrows) / 99% (MATTR) — natural
.steering/20260430-m9-eval-system/decisions.md:205:      Vendi 200-turn window 1 cycle の最小値 (元 ADR §根拠 2) で下限制約あり、
.steering/20260430-m9-eval-system/decisions.md:211:    - 暫定性の根拠: Vendi + Big5 ICC が P4 完了後に異なる方向性を示す可能性あり、
.steering/20260430-m9-eval-system/decisions.md:212:      Rikyu Burrows は Japanese tokenizer 未実装で 2/3 persona のみ寄与 (n_cells=2)。
.steering/20260430-m9-eval-system/decisions.md:214:    - **P4 deliverable**: Vendi Score + Big5 ICC を全 6 cell に対し計算 → ratio
.steering/20260430-m9-eval-system/decisions.md:218:    - **m9-eval-corpus expansion**: rikyu Japanese tokenizer 実装 → Rikyu Burrows
.steering/20260430-m9-eval-system/decisions.md:221:    - **DB9 quorum sub-metric 不足**: golden baseline 採取後に persona-discriminative
.steering/20260430-m9-eval-system/decisions.md:224:    - 本 ADR は ME-4 §判定基準が指す **3 metric (Burrows / Vendi / Big5 ICC)**
.steering/20260430-m9-eval-system/decisions.md:225:      のうち 1/3 metric (Burrows、Rikyu 除く 2/3 persona) + lightweight proxy 1
.steering/20260430-m9-eval-system/decisions.md:226:      metric (MATTR、3/3 persona) のみで判断している。**Vendi + Big5 ICC を含む
.steering/20260430-m9-eval-system/decisions.md:237:      script schema bump v1 → v3、`_KNOWN_LIMITATIONS` 経由で rikyu Burrows を
.steering/20260430-m9-eval-system/decisions.md:272:## ME-6 — Burrows reference corpus QC (Codex MEDIUM-6)
.steering/20260430-m9-eval-system/decisions.md:342:     - **base control measurement (ME-1 の per-item 拡張)**: persona prompt 無しの
.steering/20260430-m9-eval-system/decisions.md:344:       ME-1 が IPIP-NEO control を規定するのに対し、本 ADR は MCQ control を規定
.steering/20260430-m9-eval-system/decisions.md:381:  - Option B (Kant のみ MCQ): per-persona stimulus mass 違いで Vendi/Burrows の
.steering/20260430-m9-eval-system/decisions.md:399:  - P4a で `evidence/tier_b/big5_icc.py` の base control を per-item 拡張 (ME-1 と
.steering/20260430-m9-eval-system/decisions.md:566:## ME-9 — Phase 2 run0 wall-timeout incident: CLI partial-publish contract + run1 calibration (Codex 2026-05-06 HIGH 4)
.steering/20260430-m9-eval-system/decisions.md:628:    本 incident で覆すのは不適切、IPIP-NEO ICC sample size に余分な影響
.steering/20260430-m9-eval-system/decisions.md:656:rate=1.596/min ≈ 95.75/h) で **ME-9 trigger ≥80/h に該当**し、G-GEAR Claude が
.steering/20260430-m9-eval-system/decisions.md:712:- 既存 M9-B DB1-DB10 ADR との衝突: 無し
src/erre_sandbox/evidence/eval_store.py:6:entry point is :func:`connect_training_view`, which opens a DuckDB file
src/erre_sandbox/evidence/eval_store.py:28:Both :func:`connect_training_view` and :func:`connect_analysis_view`
src/erre_sandbox/evidence/eval_store.py:99:_METRIC_TIERS: tuple[str, ...] = ("tier_a", "tier_b", "tier_c")
src/erre_sandbox/evidence/eval_store.py:104:    ' "turn_idx" INTEGER,'
src/erre_sandbox/evidence/eval_store.py:111:Tier A is per-turn, Tier B is per-100-turn aggregate, Tier C is judge
src/erre_sandbox/evidence/eval_store.py:216:def connect_training_view(db_path: str | Path) -> RawTrainingRelation:
src/erre_sandbox/evidence/eval_store.py:433:    "connect_training_view",
src/erre_sandbox/evidence/tier_a/empath_proxy.py:11:**Big5 claim is explicitly NOT made.** ME-1 in the design's

codex
The local design shape is clear: v3 narrows Phase β back to Kant/rank=8 but adds a mock-LoRA Phase α for early SGLang risk detection. The weak points I’ll focus on externally are current SGLang endpoint reality, adapter format compatibility, and whether mock latency is strong enough to trigger DB3 by itself.
exec
/bin/zsh -lc "sed -n '1,280p' src/erre_sandbox/inference/ollama_adapter.py" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
"""Ollama ``/api/chat`` adapter with Contract-First :class:`ChatResponse`.

This module is the G-GEAR side entrypoint for local LLM inference during M2.
It intentionally mirrors the shape of
:class:`erre_sandbox.memory.embedding.EmbeddingClient` (ClassVar defaults,
DI-friendly ``client`` parameter, async context-manager semantics, single
``*Unavailable`` error) so that the two Ollama-backed adapters on G-GEAR are
symmetric and share the same mental model.

Scope boundary (see ``.steering/20260419-inference-ollama-adapter/design.md``):

* T11 (this module) is responsible for the wire protocol, response
  normalisation, and error unification. It does NOT own retry loops, fallback
  policy, or logging context — those belong to T14 ``inference/server.py``.
* Sampling composition lives in :mod:`erre_sandbox.inference.sampling`; this
  adapter only consumes the already-composed :class:`ResolvedSampling`.
* Structured parsing of the assistant text (extracting actions, speech, etc.)
  is the T12 cognition cycle's responsibility.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Final, Literal, Self

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from erre_sandbox.inference.sampling import ResolvedSampling

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_CHAT_MODEL: Final[str] = "qwen3:8b"
"""Model tag pulled on G-GEAR during T09.

Decisions D1 of ``20260418-model-pull-g-gear`` records the fallback from
``qwen3:8b-q5_K_M`` (not available in the Ollama registry) to ``qwen3:8b``.
Override per call via :meth:`OllamaChatClient.chat` ``model=...``.
"""


# ---------------------------------------------------------------------------
# Wire types — frozen Pydantic models so callers cannot accidentally mutate
# a request or response mid-flight.
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    """Single message in an Ollama ``/api/chat`` ``messages`` array.

    Constraining ``role`` to the three values Ollama accepts keeps callers
    honest — e.g. ``tool`` / ``function`` messages would need a schema change
    and deliberate consideration (M4+).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: Literal["system", "user", "assistant"]
    content: str


class ChatResponse(BaseModel):
    """Normalised ``/api/chat`` response, backend-agnostic.

    This is the single shape every inference adapter (Ollama today, SGLang
    at M7+, vLLM at M9+) must return so the callers stay backend-agnostic.
    Provider-specific extras (``load_duration``, ``eval_duration``, etc.)
    are intentionally dropped; if performance instrumentation is needed in
    the future, add a dedicated ``diagnostics`` field under a ``schema_version``
    bump rather than leaking raw Ollama keys through this boundary.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    content: str = Field(..., description="Assistant message content.")
    model: str = Field(..., description="Model tag, e.g. 'qwen3:8b'.")
    eval_count: int = Field(
        ...,
        ge=0,
        description="Output tokens generated (Ollama `eval_count`).",
    )
    prompt_eval_count: int = Field(
        default=0,
        ge=0,
        description="Prompt tokens consumed (Ollama `prompt_eval_count`).",
    )
    total_duration_ms: float = Field(
        ...,
        ge=0.0,
        description=(
            "Wall-clock of the whole chat call in milliseconds. ``0.0`` both "
            "when the call was truly instantaneous and when Ollama omitted "
            "``total_duration`` (e.g. partial error payloads) — treat as "
            "best-effort instrumentation only."
        ),
    )
    finish_reason: Literal["stop", "length"] = Field(
        default="stop",
        description="'length' when the `num_predict` budget was exhausted.",
    )


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class OllamaUnavailableError(RuntimeError):
    """Raised when ``/api/chat`` is unreachable, errors, or malforms.

    Intentionally single-typed (mirroring ``EmbeddingUnavailableError`` from
    T10) so callers in T12 / T14 write one ``except`` branch per adapter.
    Inspect ``args[0]`` / ``str(exc)`` for the specific reason substring
    (``'timeout'``, ``'unreachable'``, ``'HTTP 500'``, ``'non-JSON'``,
    ``"missing 'message.content'"``, ``'failed to parse'``).
    """


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class OllamaChatClient:
    """Asynchronous client for Ollama's ``/api/chat`` endpoint.

    Typical use::

        async with OllamaChatClient() as llm:
            resp = await llm.chat(
                [
                    ChatMessage(role="system", content=persona_prompt),
                    ChatMessage(role="user", content=observation),
                ],
                sampling=compose_sampling(
                    persona.default_sampling,
                    agent.erre.sampling_overrides,
                ),
                options={"num_predict": 256},
            )
            print(resp.content)

    The client takes an optional :class:`httpx.AsyncClient` so tests can inject
    an :class:`httpx.MockTransport` and production code can share a long-lived
    connection pool. When the ``client`` argument is ``None`` the adapter
    constructs and owns its own client (closed on ``async with`` exit).
    """

    DEFAULT_MODEL: ClassVar[str] = DEFAULT_CHAT_MODEL
    DEFAULT_ENDPOINT: ClassVar[str] = "http://127.0.0.1:11434"
    DEFAULT_TIMEOUT_SECONDS: ClassVar[float] = 60.0
    CHAT_PATH: ClassVar[str] = "/api/chat"

    def __init__(
        self,
        *,
        model: str | None = None,
        endpoint: str | None = None,
        timeout: float | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.model = model or self.DEFAULT_MODEL
        self.endpoint = (endpoint or self.DEFAULT_ENDPOINT).rstrip("/")
        self._timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT_SECONDS
        self._client: httpx.AsyncClient = client or httpx.AsyncClient(
            base_url=self.endpoint,
            timeout=self._timeout,
        )
        self._owns_client = client is None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_client and not self._client.is_closed:
            await self._client.aclose()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        sampling: ResolvedSampling,
        model: str | None = None,
        options: dict[str, Any] | None = None,
        think: bool | None = None,
    ) -> ChatResponse:
        """Send a chat completion and return a normalised :class:`ChatResponse`.

        Args:
            messages: Role-tagged messages; Ollama accepts system/user/assistant.
            sampling: Pre-composed sampling (see
                :func:`erre_sandbox.inference.sampling.compose_sampling`).
                Requiring this type in the signature makes it impossible to
                forget ERRE delta composition or the clamp.
            model: One-shot override of :attr:`DEFAULT_MODEL` for this call.
            options: Extra Ollama ``options`` keys (``num_ctx``, ``num_predict``,
                ``stop``, …) passed through as-is. The sampling values
                (``temperature`` / ``top_p`` / ``repeat_penalty``) are applied
                **after** these, so a caller cannot accidentally override the
                clamped sampling.
            think: Top-level Ollama payload flag controlling thinking-model
                reasoning on models like qwen3. ``None`` (default) omits the
                key entirely, preserving the M2 wire shape for existing
                callers (``cognition.cycle`` / ``Reflector``). ``False``
                suppresses hidden reasoning — required for dialog_turn
                generation on qwen3:8b where the default spends the response
                budget on <think> tokens and returns empty content
                (.steering/20260420-m5-llm-spike/decisions.md judgement 1).
                Must be set at the body top level, not inside ``options``.

        Raises:
            OllamaUnavailableError: When the request cannot be delivered, the
                server responds non-2xx, or the payload cannot be parsed as a
                :class:`ChatResponse`.
        """
        body = self._build_body(messages, sampling, model, options, think)
        payload = await self._post(body)
        return self._parse(payload)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_body(
        self,
        messages: Sequence[ChatMessage],
        sampling: ResolvedSampling,
        model: str | None,
        options: dict[str, Any] | None,
        think: bool | None,  # noqa: FBT001 — private helper; public ``chat`` makes it kw-only
    ) -> dict[str, Any]:
        merged_options: dict[str, Any] = dict(options or {})
        # Sampling is authoritative — intentionally overwrite any caller-supplied
        # duplicates so T12 cannot silently regress the clamp (design.md §2.2).
        merged_options["temperature"] = sampling.temperature
        merged_options["top_p"] = sampling.top_p
        merged_options["repeat_penalty"] = sampling.repeat_penalty
        body: dict[str, Any] = {
            "model": model or self.model,
            "messages": [m.model_dump() for m in messages],
            "stream": False,
            "options": merged_options,
        }
        # Guarded: only emit ``think`` when the caller explicitly opted in.
        # ``None`` default preserves the pre-M5 wire shape for cognition /
        # reflection paths, which would otherwise silently suppress qwen3
        # thinking on every tick.
        if think is not None:
            body["think"] = think
        return body

    async def health_check(self) -> None:
        """Verify Ollama is reachable. Raise ``OllamaUnavailableError`` if not.

        Probes ``GET /api/tags`` which is a cheap listing endpoint that does
        not load a model. Used by the orchestrator at startup (fail-fast so
        the operator notices immediately instead of hitting the first
        cognition tick 10s later).
        """
        try:
            response = await self._client.get("/api/tags")
        except httpx.TimeoutException as exc:
            raise OllamaUnavailableError(
                f"Ollama /api/tags timeout after {self._timeout}s: {exc!r}",
            ) from exc
        except httpx.HTTPError as exc:
            raise OllamaUnavailableError(
                f"Ollama /api/tags unreachable at {self.endpoint}: {exc!r}",
            ) from exc

exec
/bin/zsh -lc "sed -n '230,285p' src/erre_sandbox/schemas.py" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
    SPECULATIVE = "speculative"


class ShuhariStage(StrEnum):
    """Three stages of skill acquisition in Japanese arts (shu-ha-ri)."""

    SHU = "shu"
    HA = "ha"
    RI = "ri"


class PlutchikDimension(StrEnum):
    """Plutchik's eight primary emotions."""

    JOY = "joy"
    TRUST = "trust"
    FEAR = "fear"
    SURPRISE = "surprise"
    SADNESS = "sadness"
    DISGUST = "disgust"
    ANGER = "anger"
    ANTICIPATION = "anticipation"


class EpochPhase(StrEnum):
    """Three research epochs of a run (M8, L6 ADR D3 ``two-phase methodology``).

    A ``WorldRuntime`` progresses ``autonomous → q_and_a → evaluation`` with
    no reverse. The goal is to protect the autonomous-emergence claim: the
    ``autonomous`` epoch has no researcher intervention, and any user dialogue
    (``speaker_id="researcher"``) belongs to ``q_and_a``. Offline scoring in
    ``evaluation`` is a stub for M10-11 and carries no runtime effect yet.

    This enum is **orthogonal** to the gateway-layer ``SessionPhase`` at
    ``integration/protocol.py`` (AWAITING_HANDSHAKE / ACTIVE / CLOSING),
    which describes WS handshake progression, not research lifecycle.
    """

    AUTONOMOUS = "autonomous"
    Q_AND_A = "q_and_a"
    EVALUATION = "evaluation"


# Convenience float ranges used repeatedly below.
_Unit = Annotated[float, Field(ge=0.0, le=1.0)]
_Signed = Annotated[float, Field(ge=-1.0, le=1.0)]


# =============================================================================
# §3 Persona (static, YAML-loaded)
# =============================================================================


class CognitiveHabit(BaseModel):
    """One recurring cognitive-behavioural pattern of a historical figure."""


exec
/bin/zsh -lc "sed -n '1,220p' src/erre_sandbox/contracts/eval_paths.py" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
"""Evaluation data-path contract.

The executable boundary between ``raw_dialog`` (training-eligible) and
``metrics`` (evaluation-only).

This module is the **API contract** layer of the 4-layer defence specified
in ``.steering/20260430-m9-eval-system/design-final.md``
§"DuckDB 単 file + named schema + 4 層 contract":

1. **API contract** (this module): schema-name constants, an explicit
   allow-list of ``raw_dialog`` columns, a constrained relation
   :class:`RawTrainingRelation` Protocol that exposes **only** raw rows
   (no DuckDB connection, no arbitrary SQL), and the
   :class:`EvaluationContaminationError` that every egress path must raise
   when a metric-shaped key surfaces.
2. **Behavioural CI test** (``tests/test_evidence/test_eval_paths_contract.py``):
   sentinel-row fixtures (``M9_EVAL_SENTINEL_LEAK_*``) that verify no
   training-egress route surfaces metric data.
3. **Static CI grep gate** (``.github/workflows/ci.yml``): fails the build
   if any module under the training-egress allowlist textually mentions
   ``metrics.``.
4. **Existing-egress audit** (``cli/export_log.py``): is included in the
   sentinel test scope because the M9 LoRA training pipeline reads
   ``dialog_turns`` through it.

Codex ``gpt-5.5 xhigh`` review (HIGH-1) elevated this contract from a
path-only convention to a behavioural one — grep alone cannot catch
dynamic SQL or quoted ``read_parquet`` calls, so the constrained
relation + sentinel test are the **primary** boundary, with grep as a
back-stop.

Layer rule (``contracts`` package): stdlib + pydantic only — no
``duckdb``, ``numpy``, or other heavy imports here. The DuckDB-backed
implementation lives in :mod:`erre_sandbox.evidence.eval_store`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Protocol, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Iterable, Iterator, Mapping

# ---------------------------------------------------------------------------
# Schema names
# ---------------------------------------------------------------------------

RAW_DIALOG_SCHEMA: Final[str] = "raw_dialog"
"""Name of the DuckDB schema that holds training-eligible dialog turns.

This is the **only** schema the LoRA training pipeline is allowed to read
through :func:`erre_sandbox.evidence.eval_store.connect_training_view`.
Tier 0 contract (DB5): every column here must be metric-free — turn id,
agent / persona / mode / zone, utterance, timestamp, reasoning trace.
"""

METRICS_SCHEMA: Final[str] = "metrics"
"""Name of the DuckDB schema that holds Tier A/B/C scores keyed by
``(run_id, persona_id, turn_idx)``.

Reading this schema from a training-loader code path is a contract
violation that must surface as :class:`EvaluationContaminationError`.
"""


# ---------------------------------------------------------------------------
# Column allow-list / forbidden patterns
# ---------------------------------------------------------------------------

ALLOWED_RAW_DIALOG_KEYS: Final[frozenset[str]] = frozenset(
    {
        "id",
        "run_id",
        "dialog_id",
        "tick",
        "turn_index",
        "speaker_agent_id",
        "speaker_persona_id",
        "addressee_agent_id",
        "addressee_persona_id",
        "utterance",
        "mode",
        "zone",
        "reasoning",
        "epoch_phase",
        "created_at",
    },
)
"""Closed allow-list of column names permitted on a ``raw_dialog`` row.

Any key emitted by a training-egress path MUST be a member of this set.
``mode`` / ``zone`` / ``reasoning`` are reserved for the M9 ingest CLI
that copies sqlite ``dialog_turns`` into DuckDB ``raw_dialog``; the
existing M8 sink only populates a subset of these (see
``cli/export_log.py``), which is a strict subset and therefore safe.
"""

FORBIDDEN_METRIC_KEY_PATTERNS: Final[tuple[str, ...]] = (
    "metric_",
    "score_",
    "vendi_",
    "burrows_",
    "icc_",
    "embedding_",
    "novelty_",
    "logit_",
    "judge_",
    "geval_",
    "prometheus_",
    "nli_",
    "mattr_",
    "empath_",
)
"""Substring prefixes that signal a metric-shaped key has leaked into a
training-egress payload.

These prefixes are used by :func:`assert_no_metrics_leak` as a
**defence-in-depth** check on top of the closed allow-list — a key like
``"empath_anger"`` would be rejected even if a future commit accidentally
added it to :data:`ALLOWED_RAW_DIALOG_KEYS`. Patterns are checked with
``str.startswith`` (case-sensitive) since column names are
canonicalised lower_snake_case throughout the codebase.
"""

SENTINEL_LEAK_PREFIX: Final[str] = "M9_EVAL_SENTINEL_LEAK_"
"""String prefix used by the contamination CI fixture.

If a value starting with this prefix appears in a training-egress payload
the boundary has been breached. Tests should plant sentinel values in the
``metrics`` schema and assert they never reach ``connect_training_view``
output — see :class:`EvaluationContaminationError` and
``tests/test_evidence/test_eval_paths_contract.py``.
"""


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class EvaluationContaminationError(RuntimeError):
    """Raised when a training-egress path attempts to expose metric data.

    Examples that MUST raise:

    * Calling a method on :class:`RawTrainingRelation` that would route
      to the ``metrics`` schema.
    * Building a row dict whose keys include any
      :data:`FORBIDDEN_METRIC_KEY_PATTERNS` prefix.
    * Surfacing a value with the :data:`SENTINEL_LEAK_PREFIX`.

    Catching this exception silently is a **contract bug**; tests assert
    the error type, not just any exception subclass.
    """


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------


def assert_no_metrics_leak(keys: Iterable[str], *, context: str) -> None:
    """Raise :class:`EvaluationContaminationError` if any *keys* look metric-shaped.

    The check is layered: keys must (a) belong to the
    :data:`ALLOWED_RAW_DIALOG_KEYS` allow-list **and** (b) not start with
    any :data:`FORBIDDEN_METRIC_KEY_PATTERNS` prefix. *context* is woven
    into the error message so failures at sentinel fixtures point at the
    egress path that leaked.
    """
    keys_seen: list[str] = list(keys)
    forbidden: list[str] = []
    for key in keys_seen:
        for pattern in FORBIDDEN_METRIC_KEY_PATTERNS:
            if key.startswith(pattern):
                forbidden.append(key)
                break
    if forbidden:
        raise EvaluationContaminationError(
            f"{context}: forbidden metric-shaped key(s) {sorted(set(forbidden))!r}"
            f" leaked into training egress",
        )
    out_of_allowlist = [k for k in keys_seen if k not in ALLOWED_RAW_DIALOG_KEYS]
    if out_of_allowlist:
        raise EvaluationContaminationError(
            f"{context}: key(s) {sorted(set(out_of_allowlist))!r} are not on the"
            f" raw_dialog allow-list (expected subset of"
            f" {sorted(ALLOWED_RAW_DIALOG_KEYS)})",
        )


def assert_no_sentinel_leak(
    values: Iterable[object],
    *,
    context: str,
) -> None:
    """Raise :class:`EvaluationContaminationError` if any value is a leak sentinel.

    Used by the red-team contamination fixture: planting
    :data:`SENTINEL_LEAK_PREFIX` values in the ``metrics`` schema and
    checking that no such value ever surfaces through a training-egress
    route. Pure-string check; non-string values pass.
    """
    leaked: list[str] = [
        value
        for value in values
        if isinstance(value, str) and value.startswith(SENTINEL_LEAK_PREFIX)
    ]
    if leaked:
        raise EvaluationContaminationError(
            f"{context}: sentinel leak value(s) {leaked!r} surfaced through"
            f" a training-egress path",
        )


# ---------------------------------------------------------------------------
# Constrained relation Protocol
# ---------------------------------------------------------------------------



exec
/bin/zsh -lc "sed -n '1,320p' src/erre_sandbox/evidence/eval_store.py" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
"""DuckDB-backed evaluation store — m9-eval-system Phase 0 (P0b + P0c).

This module is the **implementation half** of the four-layer evaluation
contamination contract; the policy half lives in
:mod:`erre_sandbox.contracts.eval_paths`. The single training-egress
entry point is :func:`connect_training_view`, which opens a DuckDB file
read-only and returns a :class:`RawTrainingRelation` that exposes only
``raw_dialog`` rows — never the ``metrics`` schema, never an arbitrary
SQL execution surface.

P0c additions (this commit):

* :func:`bootstrap_schema` — idempotent CREATE for ``raw_dialog.dialog``
  and ``metrics.tier_{a,b,c}``. The raw column set is locked in lockstep
  with :data:`ALLOWED_RAW_DIALOG_KEYS` (module-load-time check).
* :class:`AnalysisView` + :func:`connect_analysis_view` — Mac-side
  read-only multi-schema reader for analytics / notebooks. NOT a
  training-egress route; the grep gate in CI keeps the metric schema
  reference confined to this module.
* :func:`export_raw_only_snapshot` — Parquet export of ``raw_dialog``
  only, the sanctioned route for callers that need ad-hoc SQL on raw
  rows (run the SQL against the snapshot, not the live file).
* :func:`write_with_checkpoint` and :func:`atomic_temp_rename` — the
  two ME-2 helpers that implement the G-GEAR → Mac snapshot semantics
  documented in
  ``.steering/20260430-m9-eval-system/decisions.md`` §ME-2.

Both :func:`connect_training_view` and :func:`connect_analysis_view`
open the underlying DuckDB file with ``read_only=True``. Any write
attempt against either handle (even via private attribute access) must
surface as a DuckDB error — the test suite covers both paths.
"""

from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Self

import duckdb

from erre_sandbox.contracts.eval_paths import (
    ALLOWED_RAW_DIALOG_KEYS,
    METRICS_SCHEMA,
    RAW_DIALOG_SCHEMA,
    EvaluationContaminationError,
    RawTrainingRelation,
    assert_no_metrics_leak,
    assert_no_sentinel_leak,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Iterator, Mapping

RAW_DIALOG_TABLE: str = "dialog"
"""Table name inside :data:`RAW_DIALOG_SCHEMA` (qualified
``raw_dialog.dialog``).

Kept as a public constant so :func:`bootstrap_schema` and the contract
test agree on the same physical name.
"""

# ---------------------------------------------------------------------------
# Bootstrap DDL — column set locked in lockstep with the contract.
# ---------------------------------------------------------------------------

_RAW_DIALOG_DDL_COLUMNS: tuple[tuple[str, str], ...] = (
    ("id", "TEXT"),
    ("run_id", "TEXT"),
    ("dialog_id", "TEXT"),
    ("tick", "INTEGER"),
    ("turn_index", "INTEGER"),
    ("speaker_agent_id", "TEXT"),
    ("speaker_persona_id", "TEXT"),
    ("addressee_agent_id", "TEXT"),
    ("addressee_persona_id", "TEXT"),
    ("utterance", "TEXT"),
    ("mode", "TEXT"),
    ("zone", "TEXT"),
    ("reasoning", "TEXT"),
    ("epoch_phase", "TEXT"),
    ("created_at", "TIMESTAMP"),
)

_BOOTSTRAP_COLUMN_NAMES: frozenset[str] = frozenset(
    name for name, _ in _RAW_DIALOG_DDL_COLUMNS
)
if _BOOTSTRAP_COLUMN_NAMES != ALLOWED_RAW_DIALOG_KEYS:
    # Fail-fast at import: divergence here would silently widen the
    # contract, which is the exact failure mode the four-layer defence
    # is meant to prevent.
    raise EvaluationContaminationError(
        "bootstrap DDL column set"
        f" {sorted(_BOOTSTRAP_COLUMN_NAMES)} diverges from"
        f" ALLOWED_RAW_DIALOG_KEYS {sorted(ALLOWED_RAW_DIALOG_KEYS)}"
        " — update both in lockstep",
    )

_METRIC_TIERS: tuple[str, ...] = ("tier_a", "tier_b", "tier_c")

_METRIC_TIER_COLUMNS: str = (
    '"run_id" TEXT,'
    ' "persona_id" TEXT,'
    ' "turn_idx" INTEGER,'
    ' "metric_name" TEXT,'
    ' "metric_value" DOUBLE,'
    ' "notes" TEXT'
)
"""Generic per-metric row shape used by all three tiers at P0c.

Tier A is per-turn, Tier B is per-100-turn aggregate, Tier C is judge
score; later phases may introduce tier-specific columns. The current
shape is intentionally narrow so the contract surface stays tight.
"""


def _inspect_raw_dialog_columns(
    conn: duckdb.DuckDBPyConnection,
) -> list[str]:
    """Return ordered column names of ``raw_dialog.dialog``.

    Module-level helper used by both :class:`_DuckDBRawTrainingRelation`
    construction and :func:`export_raw_only_snapshot`. Raises
    :class:`EvaluationContaminationError` if the table is missing.
    """
    rows = conn.execute(
        "SELECT column_name FROM information_schema.columns"
        " WHERE table_schema = ? AND table_name = ?"
        " ORDER BY ordinal_position",
        (RAW_DIALOG_SCHEMA, RAW_DIALOG_TABLE),
    ).fetchall()
    if not rows:
        raise EvaluationContaminationError(
            f"{RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE} not found in DuckDB"
            f" file; cannot construct training view (was the schema"
            f" bootstrapped? — see bootstrap_schema)",
        )
    return [str(row[0]) for row in rows]


class _DuckDBRawTrainingRelation:
    """Concrete :class:`RawTrainingRelation` backed by a read-only DuckDB connection.

    Designed as a **constrained facade**:

    * The connection is held privately; no public attribute exposes it.
    * Only a fixed SELECT against ``raw_dialog.dialog`` is ever issued.
    * Column projection is the **intersection** of the physical columns
      with :data:`ALLOWED_RAW_DIALOG_KEYS`; any column outside the
      allow-list is dropped before the row reaches the caller, and a
      mismatch between the physical schema and the allow-list raises
      :class:`EvaluationContaminationError` at construction.
    """

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn
        physical_columns = _inspect_raw_dialog_columns(conn)
        outside_allowlist = [
            col for col in physical_columns if col not in ALLOWED_RAW_DIALOG_KEYS
        ]
        if outside_allowlist:
            raise EvaluationContaminationError(
                f"raw_dialog.{RAW_DIALOG_TABLE} contains column(s)"
                f" {sorted(outside_allowlist)!r} that are not on the"
                f" raw_dialog allow-list"
                f" ({sorted(ALLOWED_RAW_DIALOG_KEYS)})",
            )
        self._columns: tuple[str, ...] = tuple(physical_columns)
        # Belt-and-braces: confirm we never aliased the metrics schema in.
        if any(col.startswith(f"{METRICS_SCHEMA}.") for col in self._columns):
            raise EvaluationContaminationError(
                f"raw_dialog projection includes a {METRICS_SCHEMA}-qualified"
                f" column: {self._columns!r}",
            )

    # ------------------------------------------------------------------
    # Protocol surface
    # ------------------------------------------------------------------

    @property
    def schema_name(self) -> str:
        return RAW_DIALOG_SCHEMA

    @property
    def columns(self) -> tuple[str, ...]:
        return self._columns

    def row_count(self) -> int:
        result = self._conn.execute(
            f"SELECT COUNT(*) FROM {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE}",  # noqa: S608  # constants are module-private literals, no user input
        ).fetchone()
        if result is None:
            return 0
        return int(result[0])

    def iter_rows(self) -> Iterator[Mapping[str, object]]:
        # Quote each column with DuckDB identifier rules so any future
        # column added to the allow-list cannot collide with reserved
        # keywords (``order``, ``mode``, ``zone`` are all candidates).
        projection = ", ".join(f'"{col}"' for col in self._columns)
        sql = f"SELECT {projection} FROM {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE}"  # noqa: S608  # projection comes from validated allow-list, identifiers are module constants
        cursor = self._conn.execute(sql)
        rows = cursor.fetchall()
        for row in rows:
            row_dict: dict[str, object] = dict(zip(self._columns, row, strict=True))
            assert_no_metrics_leak(row_dict.keys(), context="iter_rows")
            assert_no_sentinel_leak(row_dict.values(), context="iter_rows")
            yield row_dict

    def close(self) -> None:
        """Release the underlying DuckDB connection. Idempotent."""
        with contextlib.suppress(duckdb.Error):
            self._conn.close()


def connect_training_view(db_path: str | Path) -> RawTrainingRelation:
    """Open *db_path* read-only and return a constrained training-egress view.

    This is the **only** training-loader entry point in the codebase.
    Any caller that bypasses it (raw ``duckdb.connect``, direct
    ``read_parquet`` against the metrics schema, etc.) violates the
    contract — the static grep gate in CI catches the obvious shapes,
    while the sentinel test catches the dynamic ones.
    """
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        return _DuckDBRawTrainingRelation(conn)
    except Exception:
        conn.close()
        raise


# ---------------------------------------------------------------------------
# P0c — schema bootstrap
# ---------------------------------------------------------------------------


def bootstrap_schema(con: duckdb.DuckDBPyConnection) -> None:
    """Create ``raw_dialog.dialog`` and ``metrics.tier_{a,b,c}`` idempotently.

    *con* must be a writable connection (``read_only=False``); a
    read-only handle will surface DuckDB's own error. The DDL is
    ``CREATE … IF NOT EXISTS`` everywhere, so this is safe to call
    repeatedly on existing files (e.g. orchestration glue that doesn't
    track whether it already ran).

    The ``raw_dialog.dialog`` column set is identical to
    :data:`ALLOWED_RAW_DIALOG_KEYS`; the module-load-time check above
    refuses to import the module if the two ever drift.
    """
    raw_dialog_cols = ", ".join(
        f'"{name}" {ddl_type}' for name, ddl_type in _RAW_DIALOG_DDL_COLUMNS
    )

    con.execute(f"CREATE SCHEMA IF NOT EXISTS {RAW_DIALOG_SCHEMA}")
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {METRICS_SCHEMA}")

    con.execute(
        f"CREATE TABLE IF NOT EXISTS"
        f" {RAW_DIALOG_SCHEMA}.{RAW_DIALOG_TABLE}"
        f" ({raw_dialog_cols})",
    )

    for tier in _METRIC_TIERS:
        con.execute(
            f"CREATE TABLE IF NOT EXISTS"
            f" {METRICS_SCHEMA}.{tier}"
            f" ({_METRIC_TIER_COLUMNS})",
        )


# ---------------------------------------------------------------------------
# P0c — analysis view (Mac-side full read, NOT a training egress)
# ---------------------------------------------------------------------------


class AnalysisView:
    """Read-only handle that spans both ``raw_dialog`` and ``metrics``.

    Intended for Mac-side analytics, dashboards, and notebooks — i.e.
    any context where reading metric scores **is** the point. The
    training-egress contract therefore deliberately does NOT apply
    here: callers can run arbitrary SELECTs against either schema.

    What protects the boundary: the CI grep gate confines metric
    schema references to this module, so :func:`connect_analysis_view`
    is the sole sanctioned multi-schema reader. Any new training-side
    code path that imports this class would be surfaced by code review
    + the sentinel CI test (which scans documented training-egress
    modules — see ``.github/workflows/ci.yml`` ``eval-egress-grep-gate``
    job).
    """

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn

    def execute(
        self,
        sql: str,
        params: tuple[object, ...] | None = None,
    ) -> list[tuple[object, ...]]:
        """Run *sql* against the read-only connection and fetch all rows."""
        cursor = (
            self._conn.execute(sql)
            if params is None
            else self._conn.execute(sql, params)
        )
        return list(cursor.fetchall())

    def close(self) -> None:
        """Release the underlying DuckDB connection. Idempotent."""
        with contextlib.suppress(duckdb.Error):
            self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:

exec
/bin/zsh -lc "sed -n '1,260p' .steering/20260508-m9-c-spike/decisions.md" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "sed -n '1,260p' .steering/20260508-m9-c-spike/blockers.md" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
# 重要な設計判断

## 判断 1: [タイトル]

- **判断日時**:
- **背景**: なぜこの判断が必要だったか
- **選択肢**:
  - A: [説明]
  - B: [説明]
  - C: [説明]
- **採用**: B
- **理由**:
- **トレードオフ**: 何を諦めたか
- **影響範囲**: この判断がどこに影響するか
- **見直しタイミング**: どんな状況になったら再検討すべきか

 succeeded in 0ms:
# ブロッカー記録

## ブロッカー 1: [タイトル]

- **発生日時**:
- **症状**:
- **試したこと**:
  1. ...
  2. ...
- **原因**:
- **解決方法**:
- **教訓**: 次回同じ状況に遭遇したらどうすべきか

exec
/bin/zsh -lc "sed -n '1,160p' .steering/20260508-m9-c-spike/design.md" in /Users/johnd/ERRE-Sand Box
exec
/bin/zsh -lc "sed -n '1,260p' .steering/20260508-m9-c-spike/tasklist.md" in /Users/johnd/ERRE-Sand Box
 succeeded in 0ms:
# 設計

## 実装アプローチ

採用する方針と、その理由。

## 変更対象

### 修正するファイル
- `path/to/file1.py` — 何を変えるか
- `path/to/file2.py` — 何を変えるか

### 新規作成するファイル
- `path/to/new_file.py` — 役割

### 削除するファイル
- ...

## 影響範囲

この変更が影響する箇所と、その対処。

## 既存パターンとの整合性

既存のコードベースのどのパターンに従うか。

## テスト戦略

- 単体テスト: 何をテストするか
- 統合テスト: 何をテストするか
- E2E テスト: 必要か

## ロールバック計画

変更が問題を起こした場合の戻し方。

 succeeded in 0ms:
# タスクリスト

## 準備
- [ ] 関連する docs を読む
- [ ] 影響範囲を file-finder で調査

## 実装
- [ ] タスク 1
- [ ] タスク 2
- [ ] タスク 3

## テスト
- [ ] 単体テストを追加
- [ ] 統合テストを追加（必要なら）
- [ ] テストが通ることを確認

## レビュー
- [ ] code-reviewer によるレビュー
- [ ] HIGH 指摘への対応

## ドキュメント
- [ ] docs の更新（必要なら）
- [ ] glossary への用語追加（必要なら）

## 完了処理
- [ ] design.md の最終化
- [ ] decisions.md の作成（重要な判断があった場合）
- [ ] git commit

web search: 
web search: SGLang LoRA load_lora_adapter unload_lora_adapter list_lora_adapters enable-lora docs
web search: 
web search: https://sgl-project.github.io/advanced_features/lora.html
web search: 
web search: 'list_lora' in https://sgl-project.github.io/advanced_features/lora.html
web search: 
web search: site:docs.sglang.ai list_lora_adapters SGLang
web search: 
web search: https://github.com/sgl-project/sglang/issues/12221
web search: 
web search: PyPI sglang latest version 0.5.10 post1 May 2026
web search: 
web search: QLoRA NF4 bitsandbytes memory benchmark 8-bit vs 4-bit 16GB GPU rank 8 8B model
web search: 
web search: https://arxiv.org/abs/2305.14314
web search: 
web search: https://huggingface.co/blog/4bit-transformers-bitsandbytes
web search: 
web search: Qwen3-8B LoRA SFT rank 8 gradient checkpointing GPU memory peak
web search: 
web search: Salecha 2024 LLM persona fine-tuning LoRA persona adaptation
web search: 
web search: arXiv 2405.06058 Salecha Big Five LLM personality
web search: 
web search: https://www.researchgate.net/publication/381518638_P-Tailor_Customizing_Personality_Traits_for_Language_Models_via_Mixture_of_Specialized_LoRA_Experts
web search: 
web search: P-Tailor Customizing Personality Traits for Language Models via Mixture of Specialized LoRA Experts arxiv 2406.12548
web search: 
web search: LoRA rank 4 rank 8 data size instruction tuning examples enough 2024
web search: 
web search: SGLang vLLM multi LoRA benchmark 2025 S-LoRA throughput latency cold start
web search: 
web search: https://docs.vllm.ai/en/stable/features/lora.html
web search: 
web search: Hugging Face PEFT LoRA initialization default no-op B initialized zero
codex
The web check turned up one concrete API hazard already: current SGLang docs document `/load_lora_adapter` and `/unload_lora_adapter`, but not a `/list_lora_adapters` endpoint. There is also a closed GitHub issue saying loaded-adapter state had to be inferred from load/unload responses, so the proposed adapter API needs correction rather than just version pinning.
codex
Verdict: ADOPT-WITH-CHANGES

**HIGH finding (must reflect before merge)**

[HIGH-1] `SGLangChatClient.list_adapters()` is designed around an endpoint that current SGLang docs do not document

The v3 skeleton assumes `GET /list_lora_adapters`, but current SGLang LoRA docs document dynamic load/unload only: `POST /load_lora_adapter` with `lora_name`, `lora_path`, optional `pinned`, and `POST /unload_lora_adapter` with `lora_name`.
A closed SGLang issue states there was “no way to query which LoRA adapters are loaded” except by inspecting load/unload responses. The current docs still show loaded state in `loaded_adapters` response payloads, not a standalone list endpoint.
Before merge, replace `list_adapters()` with one of: internal client-side state + reconciliation through load/unload responses, `GET /v1/models` if verified in the pinned version, or a deliberately unsupported method. Also pin to current released `sglang==0.5.10.post1` or a locally verified newer release; “v0.3+ stable” is too vague.
Citations: https://sgl-project.github.io/advanced_features/lora.html, https://github.com/sgl-project/sglang/issues/12221, https://pypi.org/project/sglang/

[HIGH-2] Phase α mock-LoRA latency must not fire DB3 vLLM fallback by itself

Mock-LoRA is valid for API proof, adapter format validation, and FSM route smoke testing, but it is not equivalent to a real Kant adapter for DB3 fallback latency. SGLang docs explicitly warn that overlap loading can reduce adapter-load overhead yet worsen TTFT when batching is fragmented; this means a single mock result can be misleading.
Prior art on LoRA serving treats adapter loading, cold starts, and fragmentation as workload-dependent operational problems, not fixed constants. P-LoRA and ServerlessLoRA both frame reactive loading as a cold-start/fragmentation issue requiring prefetching or preload strategies.
Change the DB3 trigger rule: API failure or FSM regression can fire immediately; latency fallback requires repeated local measurements across cold load, warm reload, pinned, unpinned, and no-LoRA baselines, using a PEFT no-op adapter with the same rank/target_modules as the intended Kant adapter. Phase β real adapter should confirm any Phase α latency failure before vLLM migration unless SGLang cannot load adapters at all.
Citations: https://sgl-project.github.io/advanced_features/lora.html, https://arxiv.org/abs/2512.20210, https://arxiv.org/abs/2505.14468

[HIGH-3] Training sufficiency must be gated on realized examples and contamination assertions, not “~2500 turns”

“Kant ~2500 turn” is not automatically 2500 usable assistant-target training examples. The prompt builder may discard evaluation rows, non-Kant assistant rows, malformed contexts, empty utterances, and future `individual_layer_enabled=true` rows.
Persona-adaptation prior art does not justify 2500 turns as quality-sufficient. BIG5-CHAT uses 100k dialogues for personality shaping; P-Tailor curates trait-specific multi-turn data; Anthropic persona-vector work shows training subsets can induce unwanted trait shifts even when explicit trait text is filtered.
Before merge, v3 should define a Phase β gate on `len(build_examples(... persona_id="kant"))`, plus a hard fail if `epoch_phase == evaluation` or `individual_layer_enabled` is present and true. If `individual_layer_enabled` is absent because DB11 follow-up is not merged, Phase β must record that as a blocker, not silently proceed.
Citations: https://huggingface.co/papers/2410.16491, https://arxiv.org/abs/2406.12548, https://www.anthropic.com/research/persona-vectors

[HIGH-4] N=3 collapse detection needs a real benchmark contract, not just “no collapse”

The design says “N=3 throughput collapse なし” but does not define request mix, prompt/output length, adapter assignment, baseline, or failure threshold. Without those, DB3 fallback becomes subjective.
SGLang’s own bench guide measures throughput, TTFT, ITL, and end-to-end latency, and supports request rate / concurrency control. Use that rather than ad hoc async calls.
Define collapse as a comparison against no-LoRA and single-LoRA baselines: same prompts, same sampling, `--max-loras-per-batch 3`, three concurrent requests pinned to three adapter names, `--max-concurrency 3`, plus p50/p95/p99 TTFT, ITL, e2e latency, output tokens/s, HTTP error rate, and queue wait if available. A reasonable spike trigger is either p95 e2e > 2x single-LoRA baseline, output tok/s < 70% baseline, any adapter-misrouting, or any request timeout.
Citations: https://docs.sglang.io/developer_guide/bench_serving, https://sgl-project.github.io/advanced_features/lora.html

**MEDIUM finding (decisions.md ADR 反映)**

[MEDIUM-1] Record that current SGLang support is real but version-sensitive. PyPI latest found is `0.5.10.post1` on 2026-04-08; no v0.6 stable was found. Pin exact version, CUDA build, and launch args in CS ADR. Citation: https://pypi.org/project/sglang/

[MEDIUM-2] PEFT conversion should be framed as “direct PEFT directory validation,” not custom conversion first. SGLang says adapters must follow PEFT format; PEFT `save_pretrained()` writes `adapter_model.safetensors` or `.bin` plus `adapter_config.json`. Add a compatibility test before inventing conversion tooling. Citations: https://sgl-project.github.io/advanced_features/lora.html, https://huggingface.co/docs/peft/v0.17.0/developer_guides/checkpoint

[MEDIUM-3] VRAM estimate is plausible but optimistic until measured at ERRE sequence length. HF reports 7B/13B 16GB outcomes where NF4 + gradient checkpointing changes OOM status; TRL states checkpointing trades compute for memory. Make `gradient_checkpointing=True`, nested quantization, batch=1, seq length, and memory logging explicit. Citations: https://huggingface.co/blog/4bit-transformers-bitsandbytes, https://huggingface.co/docs/trl/reducing_memory_usage

[MEDIUM-4] Rank=8 is the right spike continuity choice, but do not claim adequacy. LoRA Land and P-Tailor support LoRA as practical for specialization/personality control, not a universal rank=8 guarantee. ADR should say rank=8 is a continuity/default hypothesis; rank sweep belongs to M9-C-adopt. Citations: https://arxiv.org/abs/2405.00732, https://arxiv.org/abs/2406.12548

[MEDIUM-5] vLLM fallback should be kept current. vLLM now supports runtime load/unload endpoints behind `VLLM_ALLOW_RUNTIME_LORA_UPDATING=True`, but warns of security risk; vLLM 0.15 multi-LoRA work reports large TTFT/OTPS improvements. DB3 fallback ADR should compare current vLLM, not old v0.6 assumptions. Citations: https://docs.vllm.ai/en/stable/features/lora/, https://vllm.ai/blog/multi-lora

[MEDIUM-6] The task steering files are still template-shaped. `decisions.md`, `blockers.md`, `tasklist.md`, and `design.md` must be populated before merge because the requirement explicitly demands CS ADRs, blocker records, and Phase G-J tasklists.

**LOW finding (blockers.md defer 可)**

[LOW-1] `tools/spike/build_mock_lora.py` isolation is correct. Add output metadata containing `mock=true`, `base_model`, `rank`, `target_modules`, `init_lora_weights`, git sha, and a refusal guard that prevents writing under `src/` or production checkpoint paths.

[LOW-2] Prefer PEFT default no-op initialization for mock sanity. PEFT default initializes LoRA so it is “resulting in an identity transform”; arbitrary random A/B can degrade output and confuse FSM smoke tests. Citation: https://huggingface.co/docs/peft/v0.9.0/developer_guides/lora

[LOW-3] Use SGLang naming in the adapter client: `lora_name`, `lora_path`, `pinned`. Keep `LoRAAdapterRef.adapter_name` only as internal ERRE naming if it serializes to SGLang’s field names.

**Prior art summary (web search 必須)**

1. SGLang `--enable-lora` current stability: current public release found is `0.5.10.post1`; current docs show multi-adapter serving, dynamic `/load_lora_adapter` and `/unload_lora_adapter`, pinned adapters, and overlap loading. No `/list_lora_adapters` endpoint is documented. Supported, but “multi-LoRA stable” should be phrased as “documented in current release and must be verified on G-GEAR.” Sources: https://pypi.org/project/sglang/, https://sgl-project.github.io/advanced_features/lora.html

2. PEFT QLoRA NF4 vs 8-bit on 16GB: NF4 + double quantization is the right default. HF’s benchmark shows 7B 8-bit + GC at seq1024 OOM while 4-bit NF4 + GC passes; 13B on 16GB only passes with NF4 + GC + nested quantization at seq1024. Gradient checkpointing is memory-positive but compute-negative. Sources: https://huggingface.co/blog/4bit-transformers-bitsandbytes, https://huggingface.co/docs/trl/reducing_memory_usage

3. Minimum data for persona adaptation: no source establishes 2500 turns as generally sufficient. P-Tailor and BIG5-CHAT support training-based personality shaping, but with curated trait data / 100k dialogues; Anthropic persona vectors warn that training data shifts traits. Treat 2500 Kant turns as technical-spike sufficient only. Sources: https://arxiv.org/abs/2406.12548, https://huggingface.co/papers/2410.16491, https://www.anthropic.com/research/persona-vectors

4. SGLang vs vLLM v0.6+ multi-LoRA: both are live options. SGLang documents multi-LoRA batching and overlap loading; vLLM current docs support dynamic load/unload but warn it should only be used in trusted environments. vLLM 0.15 reports major multi-LoRA improvements, so DB3 fallback is no longer “old vLLM migration,” it is a current measured alternative. Sources: https://sgl-project.github.io/advanced_features/lora.html, https://docs.vllm.ai/en/stable/features/lora/, https://vllm.ai/blog/multi-lora

5. Adapter format conversion: PEFT `save_pretrained()` already emits the format SGLang expects: `adapter_config.json` plus adapter weights. Do not plan a custom converter until a direct load test fails for Qwen3 target modules. Sources: https://huggingface.co/docs/peft/v0.17.0/developer_guides/checkpoint, https://sgl-project.github.io/advanced_features/lora.html

6. Mock-LoRA acceptance: SGLang validates PEFT-format adapters. PEFT default no-op initialization is safer than random non-zero weights; HF hub borrowed weights must match base model family, rank ceiling, and target modules. Use local generated no-op PEFT adapter first. Source: https://huggingface.co/docs/peft/v0.9.0/developer_guides/lora

7. 500ms adapter swap threshold: no universal literature threshold was found. Prior art confirms adapter artifact loading/cold-start latency is real, and SGLang overlap loading can help but has caveats. Therefore 500ms is an ERRE operational SLO, not a literature constant; measure cold/warm/pinned p95 before firing DB3. Sources: https://arxiv.org/abs/2512.20210, https://arxiv.org/abs/2505.14468, https://sgl-project.github.io/advanced_features/lora.html

8. N=3 collapse protocol: use SGLang’s benchmark harness or equivalent metrics: throughput, TTFT, ITL, e2e latency, request rate, max concurrency, and JSONL output. Server launch must set LoRA-specific limits (`--max-loras-per-batch 3`, `--max-lora-rank 8/256`, `--max-loaded-loras`) in addition to request concurrency. Source: https://docs.sglang.io/developer_guide/bench_serving

**Closing note**

Adopt v3 hybrid, not v1 or v2, but only after the changes above. Phase α is valuable as an early infrastructure proof; Phase β should stay bounded to Kant rank=8 to preserve the M9-B third-option ADR. The main correction is to demote mock latency from decisive DB3 evidence to a diagnostic unless it proves hard API/format failure.
hook: Stop
hook: Stop Completed
2026-05-08T09:53:31.099613Z ERROR codex_core::session: failed to record rollout items: thread 019e06fd-3a7e-7df2-9274-d18678bc301e not found
tokens used
198,022
Verdict: ADOPT-WITH-CHANGES

**HIGH finding (must reflect before merge)**

[HIGH-1] `SGLangChatClient.list_adapters()` is designed around an endpoint that current SGLang docs do not document

The v3 skeleton assumes `GET /list_lora_adapters`, but current SGLang LoRA docs document dynamic load/unload only: `POST /load_lora_adapter` with `lora_name`, `lora_path`, optional `pinned`, and `POST /unload_lora_adapter` with `lora_name`.
A closed SGLang issue states there was “no way to query which LoRA adapters are loaded” except by inspecting load/unload responses. The current docs still show loaded state in `loaded_adapters` response payloads, not a standalone list endpoint.
Before merge, replace `list_adapters()` with one of: internal client-side state + reconciliation through load/unload responses, `GET /v1/models` if verified in the pinned version, or a deliberately unsupported method. Also pin to current released `sglang==0.5.10.post1` or a locally verified newer release; “v0.3+ stable” is too vague.
Citations: https://sgl-project.github.io/advanced_features/lora.html, https://github.com/sgl-project/sglang/issues/12221, https://pypi.org/project/sglang/

[HIGH-2] Phase α mock-LoRA latency must not fire DB3 vLLM fallback by itself

Mock-LoRA is valid for API proof, adapter format validation, and FSM route smoke testing, but it is not equivalent to a real Kant adapter for DB3 fallback latency. SGLang docs explicitly warn that overlap loading can reduce adapter-load overhead yet worsen TTFT when batching is fragmented; this means a single mock result can be misleading.
Prior art on LoRA serving treats adapter loading, cold starts, and fragmentation as workload-dependent operational problems, not fixed constants. P-LoRA and ServerlessLoRA both frame reactive loading as a cold-start/fragmentation issue requiring prefetching or preload strategies.
Change the DB3 trigger rule: API failure or FSM regression can fire immediately; latency fallback requires repeated local measurements across cold load, warm reload, pinned, unpinned, and no-LoRA baselines, using a PEFT no-op adapter with the same rank/target_modules as the intended Kant adapter. Phase β real adapter should confirm any Phase α latency failure before vLLM migration unless SGLang cannot load adapters at all.
Citations: https://sgl-project.github.io/advanced_features/lora.html, https://arxiv.org/abs/2512.20210, https://arxiv.org/abs/2505.14468

[HIGH-3] Training sufficiency must be gated on realized examples and contamination assertions, not “~2500 turns”

“Kant ~2500 turn” is not automatically 2500 usable assistant-target training examples. The prompt builder may discard evaluation rows, non-Kant assistant rows, malformed contexts, empty utterances, and future `individual_layer_enabled=true` rows.
Persona-adaptation prior art does not justify 2500 turns as quality-sufficient. BIG5-CHAT uses 100k dialogues for personality shaping; P-Tailor curates trait-specific multi-turn data; Anthropic persona-vector work shows training subsets can induce unwanted trait shifts even when explicit trait text is filtered.
Before merge, v3 should define a Phase β gate on `len(build_examples(... persona_id="kant"))`, plus a hard fail if `epoch_phase == evaluation` or `individual_layer_enabled` is present and true. If `individual_layer_enabled` is absent because DB11 follow-up is not merged, Phase β must record that as a blocker, not silently proceed.
Citations: https://huggingface.co/papers/2410.16491, https://arxiv.org/abs/2406.12548, https://www.anthropic.com/research/persona-vectors

[HIGH-4] N=3 collapse detection needs a real benchmark contract, not just “no collapse”

The design says “N=3 throughput collapse なし” but does not define request mix, prompt/output length, adapter assignment, baseline, or failure threshold. Without those, DB3 fallback becomes subjective.
SGLang’s own bench guide measures throughput, TTFT, ITL, and end-to-end latency, and supports request rate / concurrency control. Use that rather than ad hoc async calls.
Define collapse as a comparison against no-LoRA and single-LoRA baselines: same prompts, same sampling, `--max-loras-per-batch 3`, three concurrent requests pinned to three adapter names, `--max-concurrency 3`, plus p50/p95/p99 TTFT, ITL, e2e latency, output tokens/s, HTTP error rate, and queue wait if available. A reasonable spike trigger is either p95 e2e > 2x single-LoRA baseline, output tok/s < 70% baseline, any adapter-misrouting, or any request timeout.
Citations: https://docs.sglang.io/developer_guide/bench_serving, https://sgl-project.github.io/advanced_features/lora.html

**MEDIUM finding (decisions.md ADR 反映)**

[MEDIUM-1] Record that current SGLang support is real but version-sensitive. PyPI latest found is `0.5.10.post1` on 2026-04-08; no v0.6 stable was found. Pin exact version, CUDA build, and launch args in CS ADR. Citation: https://pypi.org/project/sglang/

[MEDIUM-2] PEFT conversion should be framed as “direct PEFT directory validation,” not custom conversion first. SGLang says adapters must follow PEFT format; PEFT `save_pretrained()` writes `adapter_model.safetensors` or `.bin` plus `adapter_config.json`. Add a compatibility test before inventing conversion tooling. Citations: https://sgl-project.github.io/advanced_features/lora.html, https://huggingface.co/docs/peft/v0.17.0/developer_guides/checkpoint

[MEDIUM-3] VRAM estimate is plausible but optimistic until measured at ERRE sequence length. HF reports 7B/13B 16GB outcomes where NF4 + gradient checkpointing changes OOM status; TRL states checkpointing trades compute for memory. Make `gradient_checkpointing=True`, nested quantization, batch=1, seq length, and memory logging explicit. Citations: https://huggingface.co/blog/4bit-transformers-bitsandbytes, https://huggingface.co/docs/trl/reducing_memory_usage

[MEDIUM-4] Rank=8 is the right spike continuity choice, but do not claim adequacy. LoRA Land and P-Tailor support LoRA as practical for specialization/personality control, not a universal rank=8 guarantee. ADR should say rank=8 is a continuity/default hypothesis; rank sweep belongs to M9-C-adopt. Citations: https://arxiv.org/abs/2405.00732, https://arxiv.org/abs/2406.12548

[MEDIUM-5] vLLM fallback should be kept current. vLLM now supports runtime load/unload endpoints behind `VLLM_ALLOW_RUNTIME_LORA_UPDATING=True`, but warns of security risk; vLLM 0.15 multi-LoRA work reports large TTFT/OTPS improvements. DB3 fallback ADR should compare current vLLM, not old v0.6 assumptions. Citations: https://docs.vllm.ai/en/stable/features/lora/, https://vllm.ai/blog/multi-lora

[MEDIUM-6] The task steering files are still template-shaped. `decisions.md`, `blockers.md`, `tasklist.md`, and `design.md` must be populated before merge because the requirement explicitly demands CS ADRs, blocker records, and Phase G-J tasklists.

**LOW finding (blockers.md defer 可)**

[LOW-1] `tools/spike/build_mock_lora.py` isolation is correct. Add output metadata containing `mock=true`, `base_model`, `rank`, `target_modules`, `init_lora_weights`, git sha, and a refusal guard that prevents writing under `src/` or production checkpoint paths.

[LOW-2] Prefer PEFT default no-op initialization for mock sanity. PEFT default initializes LoRA so it is “resulting in an identity transform”; arbitrary random A/B can degrade output and confuse FSM smoke tests. Citation: https://huggingface.co/docs/peft/v0.9.0/developer_guides/lora

[LOW-3] Use SGLang naming in the adapter client: `lora_name`, `lora_path`, `pinned`. Keep `LoRAAdapterRef.adapter_name` only as internal ERRE naming if it serializes to SGLang’s field names.

**Prior art summary (web search 必須)**

1. SGLang `--enable-lora` current stability: current public release found is `0.5.10.post1`; current docs show multi-adapter serving, dynamic `/load_lora_adapter` and `/unload_lora_adapter`, pinned adapters, and overlap loading. No `/list_lora_adapters` endpoint is documented. Supported, but “multi-LoRA stable” should be phrased as “documented in current release and must be verified on G-GEAR.” Sources: https://pypi.org/project/sglang/, https://sgl-project.github.io/advanced_features/lora.html

2. PEFT QLoRA NF4 vs 8-bit on 16GB: NF4 + double quantization is the right default. HF’s benchmark shows 7B 8-bit + GC at seq1024 OOM while 4-bit NF4 + GC passes; 13B on 16GB only passes with NF4 + GC + nested quantization at seq1024. Gradient checkpointing is memory-positive but compute-negative. Sources: https://huggingface.co/blog/4bit-transformers-bitsandbytes, https://huggingface.co/docs/trl/reducing_memory_usage

3. Minimum data for persona adaptation: no source establishes 2500 turns as generally sufficient. P-Tailor and BIG5-CHAT support training-based personality shaping, but with curated trait data / 100k dialogues; Anthropic persona vectors warn that training data shifts traits. Treat 2500 Kant turns as technical-spike sufficient only. Sources: https://arxiv.org/abs/2406.12548, https://huggingface.co/papers/2410.16491, https://www.anthropic.com/research/persona-vectors

4. SGLang vs vLLM v0.6+ multi-LoRA: both are live options. SGLang documents multi-LoRA batching and overlap loading; vLLM current docs support dynamic load/unload but warn it should only be used in trusted environments. vLLM 0.15 reports major multi-LoRA improvements, so DB3 fallback is no longer “old vLLM migration,” it is a current measured alternative. Sources: https://sgl-project.github.io/advanced_features/lora.html, https://docs.vllm.ai/en/stable/features/lora/, https://vllm.ai/blog/multi-lora

5. Adapter format conversion: PEFT `save_pretrained()` already emits the format SGLang expects: `adapter_config.json` plus adapter weights. Do not plan a custom converter until a direct load test fails for Qwen3 target modules. Sources: https://huggingface.co/docs/peft/v0.17.0/developer_guides/checkpoint, https://sgl-project.github.io/advanced_features/lora.html

6. Mock-LoRA acceptance: SGLang validates PEFT-format adapters. PEFT default no-op initialization is safer than random non-zero weights; HF hub borrowed weights must match base model family, rank ceiling, and target modules. Use local generated no-op PEFT adapter first. Source: https://huggingface.co/docs/peft/v0.9.0/developer_guides/lora

7. 500ms adapter swap threshold: no universal literature threshold was found. Prior art confirms adapter artifact loading/cold-start latency is real, and SGLang overlap loading can help but has caveats. Therefore 500ms is an ERRE operational SLO, not a literature constant; measure cold/warm/pinned p95 before firing DB3. Sources: https://arxiv.org/abs/2512.20210, https://arxiv.org/abs/2505.14468, https://sgl-project.github.io/advanced_features/lora.html

8. N=3 collapse protocol: use SGLang’s benchmark harness or equivalent metrics: throughput, TTFT, ITL, e2e latency, request rate, max concurrency, and JSONL output. Server launch must set LoRA-specific limits (`--max-loras-per-batch 3`, `--max-lora-rank 8/256`, `--max-loaded-loras`) in addition to request concurrency. Source: https://docs.sglang.io/developer_guide/bench_serving

**Closing note**

Adopt v3 hybrid, not v1 or v2, but only after the changes above. Phase α is valuable as an early infrastructure proof; Phase β should stay bounded to Kant rank=8 to preserve the M9-B third-option ADR. The main correction is to demote mock latency from decisive DB3 evidence to a diagnostic unless it proves hard API/format failure.
