# m4-acceptance-live — M4 live 検証 (G-GEAR 実機)

## 背景

M4 (3-agent reflection / dialog / orchestrator) の Critical Path + 並列タスク全
6 本 (#1-#6) は MacBook 側で merge 済 (PR #43/#44/#45/#46/#47/#48)、
main HEAD = `1b7be32` (#49 handoff merge 含む、実コード HEAD は `51b282a`)。
コード上の受け入れは完了しているが、**実機 (G-GEAR の GPU + Ollama +
sqlite-vec) での live 動作と acceptance 5 項目の evidence 収集は未実施**。
M4 を正式クローズし `v0.2.0-m4` タグを打つ前提として、live 検証が必要。

handoff (MacBook ↔ G-GEAR の一時的な作業引き渡し文書) は M4 完了後に削除。
手順・期待値は本 requirement / design / tasklist に吸収済。

## ゴール

G-GEAR 実機で `uv run erre-sandbox --personas kant,nietzsche,rikyu` を走らせ、
M4 acceptance 5 項目すべてについて evidence (JSON / log / dump / 録画) を
`.steering/20260420-m4-acceptance-live/evidence/` 配下に収集し、
`acceptance.md` に PASS/FAIL 判定をまとめる。

## スコープ

### 含むもの
- Step 0: Git 同期確認 (完了済、HEAD = `1b7be32`)
- Step 2: 環境プリフライト (Ollama model / VRAM / `uv sync` / baseline pytest)
- Step 3: evidence ディレクトリ準備
- Step 4: 5 項目 evidence 収集
  - #1 起動 + `/health` (schema_version=0.2.0-m4)
  - #2 3-agent walking 60s (各 agent の agent_update × 6+)
  - #3 Reflection + semantic_memory (各 agent の row + origin_reflection_id)
  - #4 Dialog 発火 (`dialog_initiate` × 1+)
  - #5 Godot 3-avatar 30Hz (MacBook 側 Godot を LAN 越しに接続、60s 録画)
- Step 5: `acceptance.md` で PASS/FAIL サマリ
- Step 7: commit + PR 作成 (branch: `feature/m4-acceptance-live-evidence`)

### 含まないもの
- **コード修正**: live 検証で FAIL が出ても本タスクでは修正しない。
  root cause を `acceptance.md` に記録し、修正 PR は MacBook 側で別タスクに
  切り出す (handoff §Step 6)。
- `v0.2.0-m4` タグ付与: ユーザー確認を仰ぐ (auto で打たない、handoff §Step 8)
- M5 以降のタスク (dialog turn の LLM 接続など)

## 受け入れ条件

- [ ] `.steering/20260420-m4-acceptance-live/evidence/` に 5 項目の生データが揃う
- [ ] `acceptance.md` に 5 項目の PASS/FAIL が表形式でまとまる
- [ ] FAIL 項目には root cause + 修正 PR 案 (または "deferred to M5+") を記載
- [ ] `feature/m4-acceptance-live-evidence` branch で PR 作成
- [ ] `var/m4-live.db` は dump 後削除 or `.gitignore` 済を確認
- [ ] gateway `0.0.0.0:8000` が LAN 外に露出していないことを確認

## 関連ドキュメント

- `.steering/20260420-m4-multi-agent-orchestrator/live-checklist.md` (#1-#5 詳細)
- `.steering/20260420-m4-planning/design.md` §M4 全体の検収条件
- `docs/architecture.md` §Composition Root (CLI + bootstrap の新フロー)

## 運用メモ

- タスク種別: **その他** (live 検証 / evidence 収集。新機能追加・バグ修正・
  リファクタのいずれでもない)
- 破壊と構築 (`/reimagine`) 適用: **No**
  - 理由: 手順は handoff で確定済、設計判断を伴わない。検収作業の evidence
    収集に過ぎないため、代替案を比較する意義がない。
- FAIL 時の原則: **勝手に修正せずユーザー確認を仰ぐ** (handoff §最終注記)
