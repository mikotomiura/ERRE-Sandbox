# M5 Live Acceptance Evidence — README

2026-04-21 に G-GEAR 実機で実行した M5 acceptance の生データ。
ファイル単位の解説と再現手順を示す。サマリ判定は
[`acceptance.md`](acceptance.md) を参照。

## ディレクトリ

```
20260421-m5-acceptance-live/
├── README.md                     # 本ファイル
├── requirement.md                # 背景 / ゴール / スコープ / 受け入れ条件
├── design.md                     # 7 項目 evidence 収集手順
├── tasklist.md                   # 進捗 checkbox
├── acceptance.md                 # 7 項目 PASS/FAIL サマリ + 総括
├── dialog_probe.py               # #4 deterministic LLM probe (real Ollama)
└── evidence/
    ├── json/
    │   ├── gateway-health-20260421-141410.json   # #1 /health 応答
    │   └── dialog-probe-envelopes.json            # #4 initiate + close envelope dump
    ├── logs/
    │   ├── cognition-ticks-20260421-141410.log   # #2 raw 7min run ログ (すべての元)
    │   ├── erre-transitions-20260421-141410.log  # #3 FSM 遷移抽出 (32 行)
    │   ├── sampling-trace-20260421-141410.log    # #3 reflection + sampling 関連
    │   └── dialog-probe-20260421-141410.log      # #4 6-turn LLM 生成 log
    ├── db-dumps/
    │   └── semantic-memory-dump-20260421-141410.txt  # #7 semantic_memory + episodic_memory 集計
    └── recordings/
        ├── godot-dialog-20260421-*.mp4            # #5 MacBook Godot bubble (TBD)
        └── godot-mode-tint-20260421-*.mp4         # #6 MacBook Godot tint (TBD)
```

## 各項目への evidence マッピング

| # | 項目 | 主 evidence | 補助 evidence |
|---|---|---|---|
| 1 | `/health` | `json/gateway-health-*.json` | `logs/cognition-ticks-*.log` の起動ログ |
| 2 | 3-agent walking | `logs/cognition-ticks-*.log` (86 chat + 100 embed call) | — |
| 3 | ERRE mode FSM | `logs/erre-transitions-*.log` (32 lines, 3 agents) | `logs/sampling-trace-*.log` |
| 4 | dialog_turn LLM | `logs/dialog-probe-*.log` (6 turns generated) | `json/dialog-probe-envelopes.json` |
| 5 | Godot dialog bubble | `recordings/godot-dialog-*.mp4` (TBD) | `logs/cognition-ticks-*.log` (WS 接続試行ログ) |
| 6 | Godot ERRE tint | `recordings/godot-mode-tint-*.mp4` (TBD) | — |
| 7 | Reflection 回帰 | `db-dumps/semantic-memory-dump-*.txt` | `logs/cognition-ticks-*.log` (22 Reflection trigger) |

## 再現手順

### G-GEAR 側 (本ディレクトリ)

```bash
# 1. 前提: Ollama + qwen3:8b + nomic-embed-text が起動済
ollama list   # 2 モデル確認
curl -s http://127.0.0.1:11434/api/tags   # HTTP 200

# 2. baseline pytest
uv run pytest -q   # 658 passed 確認

# 3. orchestrator 起動
rm -f var/m5-live.db   # clean slate
uv run erre-sandbox --personas kant,nietzsche,rikyu --db var/m5-live.db --log-level debug \
    > .steering/20260421-m5-acceptance-live/evidence/logs/cognition-ticks-$(date +%Y%m%d-%H%M%S).log 2>&1 &

# 4. /health probe (#1)
sleep 5
curl -s http://127.0.0.1:8000/health | tee \
    .steering/20260421-m5-acceptance-live/evidence/json/gateway-health-$(date +%Y%m%d-%H%M%S).json

# 5. 5-7 分待機 (cognition ticks + reflection + FSM transitions が溜まる)
# 6. 停止 (Ctrl+C or taskkill //PID <pid>)

# 7. filtered log 抽出 (#3)
LOG=.steering/20260421-m5-acceptance-live/evidence/logs/cognition-ticks-*.log
grep -a "ERRE mode transition" $LOG > .steering/20260421-m5-acceptance-live/evidence/logs/erre-transitions-$(date +%Y%m%d-%H%M%S).log
grep -a "Reflection trigger\|sampling" $LOG > .steering/20260421-m5-acceptance-live/evidence/logs/sampling-trace-$(date +%Y%m%d-%H%M%S).log

# 8. deterministic dialog probe (#4)
uv run python .steering/20260421-m5-acceptance-live/dialog_probe.py \
    2>&1 | tee .steering/20260421-m5-acceptance-live/evidence/logs/dialog-probe-$(date +%Y%m%d-%H%M%S).log

# 9. semantic memory dump (#7)
PYTHONIOENCODING=utf-8 uv run python -c "<inline script — see acceptance.md>" \
    > .steering/20260421-m5-acceptance-live/evidence/db-dumps/semantic-memory-dump-$(date +%Y%m%d-%H%M%S).txt

# 10. (optional) DB cleanup
rm var/m5-live.db   # var/ は .gitignore 済
```

### MacBook 側 (user 作業)

```bash
# 1. Godot 4.4 で erre-sandbox/godot_project/project.godot を開く
# 2. WebSocket 接続先を ws://g-gear.local:8000/stream に設定
# 3. Run (F5) して 3 avatar (kant / nietzsche / rikyu) が表示されることを確認
# 4. OBS (or QuickTime screen recording) で 60 秒以上の動画を取得
# 5. 成果物を evidence/recordings/godot-{dialog|mode-tint}-$(date).mp4 に配置
```

## メモ

- `var/m5-live.db` は `.gitignore` 済 (`var/` エントリ経由)。evidence 抽出後に削除しても OK
- `dialog_probe.py` は deterministic (scheduler RNG seed=0 + forced admission) で、
  Live run の auto-fire 不発を補完する。Live と probe の両 evidence 併用で #4 判定
- `cognition-ticks-*.log` は ~7000 行で重い。必要に応じて gzip 検討
  (`.gitattributes` で git-lfs 候補)
