# M4 live 検証 handoff — G-GEAR で実行

本 PR (`feature/m4-multi-agent-orchestrator`) merge 後、G-GEAR 上で以下を
実施して M4 acceptance の 5 項目 evidence を収集する。MacBook で完結した
部分は unit/integration テストでカバー済。

## 前提

- G-GEAR で Ollama / model が pull 済
- main が latest で G-GEAR 側 `git pull` 済
- MacBook 側で Godot が起動準備完了
- evidence 出力先: `.steering/20260420-m4-acceptance-live/` (新規作成)

## コマンド

```bash
# G-GEAR 側 (推論 + 認知 + 記憶 + gateway)
uv run erre-sandbox \
  --personas kant,nietzsche,rikyu \
  --port 8000 \
  --db var/m4-live.db \
  --log-level info

# MacBook 側 (Godot)
# (1) Godot project を開き、gateway URL = ws://<g-gear-ip>:8000/ws/observe
# (2) Scene: peripatos + chashitsu のマルチゾーン構成で 3 avatar を描画
```

## 収集 evidence (5 項目)

### 1. 起動 + /health
```bash
curl -s http://<g-gear-ip>:8000/health | tee \
  .steering/20260420-m4-acceptance-live/gateway-health-$(date +%s).json
```
期待: `schema_version="0.2.0-m4"`, `active_sessions >= 0`。

### 2. 3 agent walking (60s 以上)
```bash
# websocat で envelope stream を tail
websocat -n ws://<g-gear-ip>:8000/ws/observe | \
  tee .steering/20260420-m4-acceptance-live/cognition-ticks-$(date +%s).log
```
期待: 60s 以内に各 agent について `agent_update` × 6 以上 (10s/tick)、
`move` で peripatos 内を巡回。

### 3. Reflection + semantic_memory
```bash
# 2-3 分走らせた後
sqlite3 var/m4-live.db \
  "SELECT agent_id, substr(content, 1, 60), origin_reflection_id FROM semantic_memory ORDER BY created_at" \
  | tee .steering/20260420-m4-acceptance-live/semantic-memory-dump-$(date +%s).txt
```
期待: 各 agent_id (kant/nietzsche/rikyu) について 1 行以上。
`origin_reflection_id` が NULL でないこと。

### 4. Dialog 往復
同一 zone で 2 agent の distance 満了時に `dialog_initiate` が envelope
stream に現れるはず。envelope log から:
```bash
grep -E "dialog_(initiate|turn|close)" \
  .steering/20260420-m4-acceptance-live/cognition-ticks-*.log \
  > .steering/20260420-m4-acceptance-live/dialog-trace-$(date +%s).log
```
期待: `dialog_initiate` × 1 以上 + `dialog_close` × 1 以上。
(DialogTurn 生成は M5 で LLM 配線予定、本タスクでは scheduler のみ)

### 5. Godot 3-avatar 30Hz
MacBook 側 Godot を 60s 録画:
```bash
# Godot editor の Recording あるいは OBS で capture
# 出力 .steering/20260420-m4-acceptance-live/godot-3avatar-$(date +%s).mp4
```
期待: 3 avatar が peripatos 上で描画、fps counter が 30 付近で維持。

## PASS 条件

| 項目 | PASS |
|---|---|
| 起動 + /health | `schema_version=0.2.0-m4` + HTTP 200 |
| 3-agent walking | 60s 以内に 3 agent 分の agent_update / move |
| Reflection | semantic_memory に各 agent の row |
| Dialog | dialog_initiate × 1 以上 (turn は M5) |
| Godot 30Hz | fps 28-32 を 60s 維持 |

## FAIL 時の切り分け

- `/health` 404 → bootstrap が上がっていない。log_level=debug で再起動
- agent_update が 1 つの agent しか来ない → gateway subscribe filter か
  register_agent のエラー (bootstrap log を確認)
- reflection が 0 行 → `ReflectionPolicy.tick_interval=10` で 100 秒必要。
  3 分以上走らせる
- dialog が発火しない → AUTO_FIRE_PROB_PER_TICK = 0.25 なので確率問題。
  CHASHITSU または GARDEN に 2 人同居すれば発火期待値 = 4 tick (40s)
- Godot が描画しない → subscribe URL が `?subscribe=a_kant_001,a_nietzsche_001,a_rikyu_001`
  になっているか確認、default は broadcast

## 次のマイルストーン (M5)

live 検証 PASS 後:
- PR #? で M4 終了タグ付与 (`v0.2.0-m4`)
- M5 `ERRE mode FSM` に着手 (peripatetic/chashitsu/zazen/shu/ha/ri の状態機械)
