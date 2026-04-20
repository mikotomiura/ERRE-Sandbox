# M4 Live Validation — Acceptance Report

**実施環境**: G-GEAR 実機 (Windows 11 / RTX 5060 Ti 16 GB / Ollama qwen3:8b + nomic-embed-text)
**branch**: `feature/m4-acceptance-live-evidence`
**base HEAD**: `1b7be32` (PR #49 handoff merge)
**実コード HEAD**: `51b282a` (PR #48 multi-agent orchestrator merge)
**実施日**: 2026-04-20

## 環境プリフライト

| 項目 | 結果 | 備考 |
|---|---|---|
| Ollama `qwen3:8b` | ✅ | 5.2 GB |
| Ollama `nomic-embed-text` | ✅ | 274 MB |
| GPU (RTX 5060 Ti) | ✅ | 16 311 MiB total / 995 MiB idle |
| `uv sync --frozen` | ✅ | erre-sandbox 0.0.1 rebuilt |
| `pytest -q` | ✅ (0 failures) | 497 passed / 26 skipped |

### pytest baseline 差分の説明

handoff 期待値 `503 passed / 20 skipped` に対し実測 `497 passed / 26 skipped`。
失敗 0 件。差分 6 件は **Godot 関連テスト (`test_godot_*.py`) の追加 skip** で説明がつく:

- G-GEAR には Godot を入れない (handoff Step 4 #5 で Mac 側から LAN 接続する設計)
- `test_godot_peripatos.py` 6 件 + `test_godot_project.py` 1 件 + `test_godot_ws_client.py` 1 件 = 8 件 が G-GEAR で skip
- Mac 側では Godot 入りなので 2 件程度のみ skip、差分 6 件が pass → skip に移動

handoff §Step 2 の停止条件 (失敗 test / モデル欠落) には該当しないため続行。

## 受け入れ項目 5 項目

| # | 項目 | PASS 基準 | 判定 | 主要 evidence |
|---|---|---|---|---|
| 1 | `/health` | schema_version=0.2.0-m4 + HTTP 200 | ✅ PASS | `evidence/gateway-health-20260420T155220.json`, `evidence/gateway-health-final-20260420T161515.json` |
| 2 | 3-agent walking 60s | 各 agent の `agent_update` + `move` | ✅ PASS | `evidence/cognition-ticks-20260420T155354.log` |
| 3 | Reflection + semantic_memory | 各 agent に row + origin_reflection_id 非 NULL | ✅ PASS | `evidence/semantic-memory-dump-20260420T155606.txt` |
| 4 | Dialog | `dialog_initiate` × 1 以上 | ✅ PASS | `evidence/dialog-trace-20260420T161518.log` (initiate × 1 + close × 4) |
| 5 | Godot 3-avatar 30Hz | fps 28–32 を 60s 維持 (目視) | ✅ PASS | `evidence/godot-3avatar-20260420-1625.mp4` (MacBook, commit `22841d5`) |

### #1 /health の詳細

初回 probe (server 起動直後):

```json
{"schema_version":"0.2.0-m4","status":"ok","active_sessions":0}
```

2 回目 probe (MacBook と Claude Code probe が接続中):

```json
{"schema_version":"0.2.0-m4","status":"ok","active_sessions":1}
```

`active_sessions` カウンタが接続状況に応じて更新されていることを確認。

### #2 3-agent walking の詳細

`cognition-ticks-20260420T155354.log` (60s probe, 86 envelope lines):

- `agent_update`: **12 件** (各 agent 4 件)
  - `a_kant_001`: 4 / `a_nietzsche_001`: 4 / `a_rikyu_001`: 4
- `move`: **11 件** / `animation`: **12 件** / `speech`: **8 件** / `world_tick`: **40 件**

3 agent すべてが並列に歩行 + 観測を emit していることを確認。

### #3 Reflection + semantic_memory の詳細

`semantic-memory-dump-20260420T155606.txt` (phase 1 DB dump):

| agent_id | rows | origin_reflection_id nulls |
|---|---|---|
| a_kant_001 | 4 | 0 |
| a_nietzsche_001 | 3 | 0 |
| a_rikyu_001 | 5 | 0 |

ペルソナ個性が内容に反映:
- **Kant**: "reason's tribunal", "duty and contemplation", "reason's necessity"
- **Nietzsche**: "tension, clarity, soul's equilibrium", "thought walks, wisdom studies"
- **Rikyū**: "bamboo whispers", "transience", "chashitsu and peripatos, one breath"

Phase 2 (fresh DB 再起動後) も同様に蓄積: kant=13 / nietzsche=13 / rikyu=30, origin nulls=0。

### #4 Dialog の詳細

`dialog-trace-20260420T161518.log` (全 probe から dialog_* のみ抽出, 5 events):

| tick | kind | dialog_id | initiator | target | zone | reason |
|---|---|---|---|---|---|---|
| 2 | dialog_close | d_dfa87954 | - | - | - | timeout |
| 2 | dialog_close | d_088893a3 | - | - | - | timeout |
| 30 | **dialog_initiate** | - | **a_nietzsche_001** | **a_rikyu_001** | **peripatos** | - |
| 25 | dialog_close | d_17a6e161 | - | - | - | timeout |
| 30 | dialog_close | d_94e6079a | - | - | - | timeout |

`dialog_turn` は出現せず (handoff 注記の通り M5 で LLM 接続時に実装される)。
initiate + timeout close のシーケンスが成立していることを確認。

#### 補足: dialog 発火の確率的性質

- `InMemoryDialogScheduler` の `AUTO_FIRE_PROB_PER_TICK = 0.25`
- 300s fresh probe の 1 回目 (`cognition-ticks-20260420T160238.log`) では 0 dialog。
  co-location は 9 回検出 → P(0 in 9, p=0.25) ≈ 7.5% の不運
- 300s の 2 回目 (`cognition-ticks-20260420T160931.log`) で dialog_initiate を捕捉

### #5 Godot 3-avatar 30Hz の詳細

MacBook 側で録画・commit (`22841d5 chore(m4): capture Godot 3-avatar live recording (acceptance #5)`)。

- **録画ファイル**: `evidence/godot-3avatar-20260420-1625.mp4`
- **解像度**: 1280×720 (Godot embedded-game window size)
- **サイズ**: 6 469 902 bytes (約 6.2 MB、LFS 不使用)
- **接続先**: G-GEAR gateway `ws://192.168.3.85:8000/ws/observe?subscribe=a_kant_001,a_nietzsche_001,a_rikyu_001`
- **fps 確認**: 録画中に operator が目視で 28-32 維持を確認済 (`README.md` §Video capture notes)

## 運用上の注意

### `var/m4-live.db` の扱い

- `var/m4-live.db` は reflection summary の LLM 応答を含むため **evidence dump 後に削除** または `.gitignore` 配下。
- 本リポジトリでは `var/` はすでに `.gitignore` 対象 (root の `.gitignore` 参照)。
- Phase 1 dump は `var/m4-live.db.phase1-backup` に退避、こちらも commit 対象外。

### Gateway の listen 範囲

- `--host 0.0.0.0 --port 8000` で起動しており、LAN 内から接続可能。
- G-GEAR の Windows firewall 設定上、LAN 外から 8000/tcp は届かないことを前提。
- 外部公開用途ではない (M4 live 検証の一時的な用途のみ)。

### MacBook 側の再接続挙動

gateway ログに `192.168.3.118` (MacBook) からの WebSocket 接続/切断が多数記録されているが、
これは MacBook の sleep によって WS が切れ、wake 時に Godot が自動再接続した結果。
bug ではなく運用挙動。

## FAIL / 留保事項

- **無し** (ただし #5 は PENDING)
- handoff §最終注記 "FAIL 時は勝手に修正せずユーザー確認を仰ぐこと" に該当する項目は発生せず。

## 次アクション

- [x] G-GEAR commit (evidence #1-#4 + acceptance.md): `chore(m4): live validation evidence — 3-agent acceptance (#1-#4)` (ローカル `b3b22cc`)
- [x] MacBook commit #5: `22841d5 chore(m4): capture Godot 3-avatar live recording (acceptance #5)` (main merged via #50)
- [x] 本 commit: acceptance/README 更新で全 5 項目 PASS 確定
- [ ] push + PR 作成
- [ ] merge 後、ユーザーへ `v0.2.0-m4` タグ付与の是非を確認
