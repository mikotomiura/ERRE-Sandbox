# m5-acceptance-live — M5 live 検証 (G-GEAR 実機 + MacBook 側 Godot)

## 背景

M5 Phase 2 の 7 本の PR (#56 contracts-freeze / #57 fsm / #58 world-zone-triggers /
#59 godot-visuals / #60 sampling-override / #61 dialog-turn-generator /
#62 orchestrator-integration) がすべて merge 済、main HEAD = `ff199d0` (#63
housekeeping 含む実コード HEAD は `3b9ee32`)。コード上の受け入れは完了しているが、
**実機 (G-GEAR の GPU + Ollama + sqlite-vec) + MacBook 側 Godot での live 動作と
acceptance 7 項目の evidence 収集は未実施**。M5 を正式クローズし `v0.3.0-m5` タグを
打つ前提として、live 検証が必要。

M4 acceptance (`.steering/20260420-m4-acceptance-live/`) のパターンを踏襲。差分:

- 5 項目 → 7 項目 (ERRE mode FSM / dialog_turn LLM 生成 / Godot bubble / Godot tint の 4 項目が追加)
- `schema_version` が `0.2.0-m4` → `0.3.0-m5` に bump
- Godot 側の視覚確認 2 項目 (5, 6) が追加で、MacBook 側の録画 evidence が必要
- bootstrap の 3 rollback flag (`--disable-erre-fsm` / `--disable-dialog-turn` /
  `--disable-mode-sampling`) は全 ON で本番挙動を検証

## ゴール

G-GEAR 実機で `uv run erre-sandbox --personas kant,nietzsche,rikyu` を走らせ、
M5 acceptance 7 項目すべてについて evidence (JSON / log / DB dump / 録画) を
`.steering/20260421-m5-acceptance-live/evidence/` 配下に収集し、
`acceptance.md` に PASS/FAIL 判定をまとめる。

PASS 後、ユーザー確認の上で `v0.3.0-m5` タグを main に付与する (本タスクでは付与しない、
user gate)。

## スコープ

### 含むもの

- **Step 0: Git 同期確認** (main HEAD = `ff199d0`)
- **Step 1: 環境プリフライト**
  - Ollama `qwen3:8b` / `nomic-embed-text` model 存在確認
  - VRAM 余裕確認 (`nvidia-smi`)
  - `uv sync --frozen`
  - baseline pytest (回帰なし確認)
- **Step 2: evidence ディレクトリ準備**
  - `.steering/20260421-m5-acceptance-live/evidence/{logs,json,db-dumps,recordings}/`
- **Step 3: 7 項目 evidence 収集**
  - **#1** 起動 + `/health` → `schema_version=0.3.0-m5` + HTTP 200
    → `evidence/json/gateway-health-*.json`
  - **#2** 3-agent walking 60s (各 agent の `agent_update` + `move` が M4 同等以上)
    → `evidence/logs/cognition-ticks-*.log`
  - **#3** ERRE mode FSM 遷移 (peripatos → chashitsu 遷移で
    `AgentState.erre.name` 更新 + 次 tick の sampling 変化が観測できる)
    → `evidence/logs/erre-transitions-*.log`, `evidence/logs/sampling-trace-*.log`
  - **#4** dialog_turn LLM 生成 (peripatos で initiate 後 N≥3 turn が 60s 以内に
    LLM から生成 + `turn_index` 単調増加 + close reason が `timeout`/`exhausted`)
    → `evidence/logs/dialog-trace-*.log`
  - **#5** Godot dialog bubble (MacBook で `dialog_turn_received` 受信 → avatar 頭上に bubble 表示、30Hz 維持)
    → `evidence/recordings/godot-dialog-*.mp4`
  - **#6** Godot ERRE mode tint (mode 切替時に avatar material 色変化が目視可能)
    → `evidence/recordings/godot-mode-tint-*.mp4`
  - **#7** Reflection 回帰なし (M4 の reflection + semantic_memory が継続動作、
    各 agent に row + `origin_reflection_id` 非 NULL)
    → `evidence/db-dumps/semantic-memory-dump-*.txt`
- **Step 4: `acceptance.md` で PASS/FAIL サマリ** (7 項目表、root cause 付き)
- **Step 5: commit + PR 作成** (branch: `feature/m5-acceptance-live-evidence`)

### 含まないもの

- **コード修正**: live 検証で FAIL が出ても本タスクでは修正しない。
  root cause を `acceptance.md` に記録し、修正 PR は別タスク
  (`m5-fix-<item>-<yyyymmdd>`) に切り出す
- `v0.3.0-m5` **タグ付与**: ユーザー確認を仰ぐ (auto で打たない)
- `m5-cleanup-rollback-flags` (次タスク、flag と `_ZERO_MODE_DELTAS` の除去)
- M6 以降のタスク (新規 persona 追加、LoRA 等)

## 受け入れ条件

- [ ] `.steering/20260421-m5-acceptance-live/evidence/` に 7 項目の生データが揃う
- [ ] `acceptance.md` に 7 項目の PASS/FAIL が表形式でまとまる
- [ ] FAIL 項目には root cause + 修正 PR 案 (または "deferred to M6+") を記載
- [ ] `feature/m5-acceptance-live-evidence` branch で PR 作成
- [ ] `var/m5-live.db` は dump 後削除 or `.gitignore` 済を確認
- [ ] gateway `0.0.0.0:8000` が LAN 外に露出していないことを確認
- [ ] MacBook 側 Godot viewer の録画 (#5, #6) が `godot_project/` 経由で
      `ws://g-gear.local:8000/stream` に接続できる

## 関連ドキュメント

- `.steering/20260420-m5-planning/design.md` §Live Acceptance (7 項目の原典)
- `.steering/20260420-m4-acceptance-live/` (パターン先例、5 項目版)
- `.steering/20260421-m5-orchestrator-integration/decisions.md` §判断 3 (rollback flag は全 ON で acceptance)
- `docs/architecture.md` §フロー 1 (cognition サイクル 10 step 更新版)
- `docs/architecture.md` §Composition Root (M5 wire 反映済)

## 運用メモ

- **タスク種別**: **その他** (live 検証 / evidence 収集。新機能追加・バグ修正・
  リファクタのいずれでもない)
- **破壊と構築 (`/reimagine`) 適用**: **No**
  - 理由: 手順は M4 acceptance のパターンで確定済、設計判断を伴わない。
    検収作業の evidence 収集に過ぎないため、代替案を比較する意義がない
- **FAIL 時の原則**: **勝手に修正せずユーザー確認を仰ぐ**。修正 PR は別タスクへ
- **tag 付与の原則**: PASS 確認後、ユーザー確認を明示的に求めてから
  `git tag v0.3.0-m5` を提案する (auto で打たない)
- **実行機**: G-GEAR (本作業ディレクトリ) で gateway + cognition + inference、
  MacBook で Godot 視覚 #5, #6 確認。MacBook 側作業は user 判断
