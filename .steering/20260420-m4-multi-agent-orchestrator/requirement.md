# m4-multi-agent-orchestrator

## 背景

M4 最終タスク (#6)。Critical Path #1-#5 は全て merged (PR #43-#47) で、
foundation (`AgentSpec` / `DialogScheduler` Protocol) · personas
(kant/nietzsche/rikyu YAML) · memory (semantic layer) · gateway
(multi-agent routing) · cognition (reflection) が揃っている。
最後に **composition root で 3 agent を起動する** 結線と、
**`DialogScheduler` の具象実装** を追加して M4 acceptance を通す。

現在の `bootstrap.py` は Kant 1 体のみを register しており
(`_build_kant_initial_state` + `_load_kant_persona`)、`BootConfig.agents`
は空 tuple のまま使われていない。`DialogScheduler` は Protocol のみで
具象実装がないため、`dialog_initiate` / `dialog_turn` envelope を
実際に emit する術がない。

## ゴール

1. **multi-agent bootstrap**: `BootConfig.agents: tuple[AgentSpec, ...]` を
   受け取り、対応する `personas/*.yaml` を load して N 体の `AgentState`
   を構築 → `WorldRuntime.register_agent` を loop 実行
2. **CLI 拡張**: `--personas kant,nietzsche,rikyu` (または `--agents`)
   で `BootConfig.agents` を組み立てる。zone は persona の
   `preferred_zones[0]` を default 初期値として採用
3. **DialogScheduler 具象実装**: `src/erre_sandbox/world/dialog.py`
   (または `cognition/`) に `InMemoryDialogScheduler` を実装。
   `schedule_initiate` (cooldown + open-dialog dedup + zone match)、
   `record_turn`、`close_dialog` の 3 methods を具象化
4. **Scheduler を runtime 配線**: WorldRuntime (または gateway 層) に
   DialogScheduler を inject し、何らかの dialog 発火源を 1 本用意する
   (MVP は tick 経過 + 同 zone 同居で確率発火、簡易実装)
5. **M4 全体 acceptance の自動化可能部分 pass**: 
   - 起動: 3 agent を bootstrap で起動するスモーク test
   - cognition: 3 agent 並列で cognition cycle が回る
   - reflection: 各 agent の `semantic_memory` に row が入る unit test
   - dialog: DialogScheduler が正しく admit / reject / close できる unit test

## スコープ

### 含むもの
- `src/erre_sandbox/bootstrap.py` の multi-agent 化 (`_load_persona_for`,
  `_build_initial_state_for`, loop による register)
- `src/erre_sandbox/__main__.py` (CLI shell) の `--personas` / `--agents`
  option 追加
- `src/erre_sandbox/world/dialog.py` (新規) に `InMemoryDialogScheduler`
- `WorldRuntime` への DialogScheduler inject + 簡易 dialog 発火
  (同 zone + 隣接 agent + cooldown 満了時に `schedule_initiate` を呼ぶ)
- `tests/test_world/test_dialog_scheduler.py` (新規) unit tests
- `tests/test_bootstrap.py` の multi-agent smoke test 追加
- `docs/architecture.md` §Composition Root / §Dialog 追記
- `docs/functional-design.md` §4 M4 の追記
- M4 acceptance の自動化可能部分の evidence 出力
  (`.steering/20260420-m4-multi-agent-orchestrator/evidence/`)

### 含まないもの
- **live 検証 (G-GEAR 必須)**:
  - `uv run erre-sandbox --personas kant,nietzsche,rikyu` の実機起動
    → ユーザー側で実施
  - `gateway-health-*.json` / `cognition-ticks-*.log` /
    `semantic-memory-dump-*.txt` / `dialog-trace-*.log` /
    `godot-3avatar-*.mp4` の evidence 取得 → 別タスクで
  - Godot 3-avatar 30Hz 維持確認 → MacBook Godot + G-GEAR 両機必要
- Dialog の turn-taking LLM (発話を LLM で生成する部分) — scheduler は
  envelope プロトコルのみを管理、actual utterance 生成は後続タスク
- Persona 間の相性マトリクス / ERRE mode による dialog 発火条件の微調整
- `Retriever` の dialog-history への統合 (M5+)
- SCHEMA_VERSION bump (`0.2.0-m4` のまま)

## 受け入れ条件

- [ ] `BootConfig(agents=(AgentSpec(persona_id="kant", initial_zone=peripatos),
      AgentSpec(persona_id="nietzsche", initial_zone=peripatos),
      AgentSpec(persona_id="rikyu", initial_zone=chashitsu)))` で起動する
      (unit / integration level、Ollama は mock 可)
- [ ] CLI `--personas kant,nietzsche,rikyu` が `BootConfig.agents` に正しく expand
- [ ] `InMemoryDialogScheduler.schedule_initiate` が cooldown 未満 → None、
      cooldown 超過 + open dialog なし → `DialogInitiateMsg` を返す
- [ ] 同じ initiator+target ペアが open dialog 中は `None` (dedup)
- [ ] `record_turn` → `close_dialog` → 同ペアの再 initiate 可能
- [ ] `close_dialog(reason="timeout")` が `DialogCloseMsg` を emit
- [ ] 3-agent smoke test (pytest): bootstrap → 1 tick → 3 agent が register、
      3 envelope が drain できる (Ollama mock)
- [ ] 既存 462 PASS + 新 tests 継続 PASS
- [ ] ruff クリーン
- [ ] code-reviewer / security-checker HIGH=0
- [ ] docs/architecture.md + functional-design.md §4 M4 に反映
- [ ] live 検証は別タスクで実施可能な状態に整う (handoff メモを残す)

## 関連ドキュメント

- `.steering/20260420-m4-planning/design.md` §m4-multi-agent-orchestrator + §M4 acceptance
- `.steering/20260418-implementation-plan/MASTER-PLAN.md` §5.1
- `.steering/20260420-m4-cognition-reflection/decisions.md` (D10 Reflector 共有案)
- `src/erre_sandbox/bootstrap.py` (拡張対象)
- `src/erre_sandbox/__main__.py` (CLI 拡張)
- `src/erre_sandbox/schemas.py` §7.5 (DialogScheduler Protocol)
- `src/erre_sandbox/world/tick.py` (WorldRuntime register / inject hook)
- `docs/architecture.md` §Orchestrator / §ControlEnvelope / §Simulation Layer
- `docs/functional-design.md` §4 M4 (追記対象)

## 運用メモ

- 破壊と構築（/reimagine）適用: **Yes**
- 理由: (1) DialogScheduler の配置場所 (world / cognition / integration
  どこ所属?)、(2) dialog 発火の trigger 源 (cognition 内 / WorldRuntime
  内 / gateway 内 / explicit command?)、(3) InMemoryDialogScheduler の
  state 表現 (open dialog dict / event log / FSM)、(4) bootstrap の
  persona loader の責務 (dict / cache / lazy load)、(5) live 検証を
  どこまで自動化するか (smoke test only / full acceptance 準備)、
  に複数案があり、公開 API (DialogScheduler は Protocol 凍結済とはいえ
  その使われ方 = scheduler への参照経路) を決める前に破壊と構築を
  通す価値が高い。
