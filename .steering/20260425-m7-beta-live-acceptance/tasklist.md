# Tasklist — G-GEAR Live Acceptance Bundle (β + #87/#88/#89)

> G-GEAR に ssh / 直接触る。Plan mode 不要 (観察タスク)。
> 時間見積 2-3h (run × 2 本 + post-hoc CLI + 観察 + 記録)。

## Pre-flight

- [ ] G-GEAR 側で `feat/m8-baseline-quality-metric` が main に merge 済
      を確認、`git pull origin main` で `f5d5e7f` を取得
- [ ] `nvidia-smi` で VRAM 13GB 以上空きを確認
- [ ] `ollama list` で `qwen3:8b` + `nomic-embed-text` が存在
- [ ] `uv run erre-sandbox --help` と `uv run erre-sandbox export-log --help`
      と `uv run erre-sandbox baseline-metrics --help` が表示される
      (新 subcommand の存在確認)
- [ ] MacBook 側 Godot client の起動、WS 接続先が G-GEAR を向いていること

## PR #87 sanity (ブート前後、~5 min)

実装 confirmation のみ。unit test が緑なので低リスク、観察のみ。

- [ ] orchestrator をブート → stdout/log に例外なく起動ログ
- [ ] 別 shell で:
  ```bash
  uv run python -c "
  import asyncio
  from erre_sandbox.schemas import EpochPhase, RunLifecycleState
  s = RunLifecycleState()
  assert s.epoch_phase is EpochPhase.AUTONOMOUS
  print('OK:', s)
  "
  ```
  が `OK: epoch_phase=...AUTONOMOUS` を出す
- [ ] 同様に FSM 遷移の不正パスで `ValueError` 発生を Python REPL で確認

## Run 1 — bias_p=0.1 (60-90s)

- [ ] G-GEAR で orchestrator を起動:
  ```bash
  ERRE_ZONE_BIAS_P=0.1 uv run erre-sandbox \
    --db var/run-01-bias01.db \
    --personas kant,nietzsche,rikyu
  ```
- [ ] 別 shell で `uv run python evidence/_stream_probe_m6.py
  --out /tmp/run-01.jsonl --duration 80`
- [ ] 同時に Godot client 側で目視観察、スクショ 3 枚:
  - top-down hotkey `0` の 100m 全景
  - zone 拡大 (chashitsu / agora / garden のいずれか)
  - ReasoningPanel (MIND_PEEK 開いた状態)
- [ ] 80s 経過で Ctrl-C で orchestrator 停止
- [ ] 成果物を `.steering/20260425-m7-beta-live-acceptance/run-01-bias01/` に保存:
  - `run-01.jsonl` (stream probe 出力)
  - `run-01.jsonl.summary.json` (envelope_per_kind)
  - `screenshot-{topdown,zone,reasoning}.png`
  - `var/run-01-bias01.db` (sqlite、export-log / baseline-metrics の入力)

## Post-run 1 — #88 export-log + #89 baseline-metrics

- [ ] `uv run erre-sandbox export-log \
    --db var/run-01-bias01.db \
    --out run-01-bias01/dialog-turns.jsonl` が exit 0、行数をメモ
- [ ] persona 別 turn 数:
  ```bash
  for p in kant nietzsche rikyu; do
    uv run erre-sandbox export-log --db var/run-01-bias01.db --persona $p \
      --out - | wc -l
  done
  ```
- [ ] `uv run erre-sandbox baseline-metrics \
    --run-db var/run-01-bias01.db \
    --out run-01-bias01/baseline.json` が exit 0
- [ ] `jq .` で JSON shape を確認:
  - `schema == "baseline_metrics_v1"`
  - `turn_count`, `bias_event_count`, `num_agents`, `run_duration_s` 非ゼロ
  - 3 metric が null でない float

## Run 2 — bias_p=0.2 (同上、~10 min)

- [ ] 同手順を `ERRE_ZONE_BIAS_P=0.2`、DB は `var/run-02-bias02.db`、
      保存先は `run-02-bias02/`
- [ ] Post-run の export-log / baseline-metrics も同様に

## Analysis (30-45 min)

- [ ] 2 run の `summary.json` から agent ごとの zone 滞留 tick % を抽出
- [ ] β 受け入れ条件 6 項目 (Rikyū/Kant/Nietzsche 分布 + 目視 3 項目) を評価
- [ ] #88 受け入れ条件 2 項目 (export-log 完走 + persona filter 数)
- [ ] #89 受け入れ条件 4 項目 (baseline JSON shape + 3 metric 値)
- [ ] `bias.fired` 発火頻度比較 (run1 vs run2)、`bias_fired_rate` との整合

## 記録

### `observation.md` (β の 6 項目 + #87 sanity の 2 項目)

- [ ] β 観察の PASS/FAIL、スクショ添付
- [ ] bias_p production default の判断 (0.1 / 0.2 / 他)
- [ ] 気になった不具合 → hotfix PR 起票 or γ に送る

### `baseline.md` (#88 + #89 の 6 項目)

- [ ] 2 run の baseline JSON を table 化:

  | run | bias_p | turn_count | bias_event_count | self_repetition | cross_persona_echo | bias_fired_rate |
  |---|---|---|---|---|---|---|
  | 01 | 0.1 | ... | ... | ... | ... | ... |
  | 02 | 0.2 | ... | ... | ... | ... | ... |

- [ ] 平均 / 分散 / 代表値を記録
- [ ] CSDG 単著閾値 (0.30 / 0.50) を参照値として並記
- [ ] M9 LoRA 比較 run 時に diff する reference として「凍結」宣言

## Follow-up

- [ ] `observation.md` の結論を
      `.steering/20260424-m7-differentiation-observability/decisions.md`
      に D9 として追記
- [ ] `baseline.md` の凍結宣言を
      `.steering/20260424-steering-scaling-lora/decisions.md` の L6 D1 に
      「baseline 固定済 (n=2)、M9 比較準備完了」として追記
- [ ] memory `project_m7_beta_merged.md` を更新
      (acceptance 完了 → 次タスクは `m8-scaling-bottleneck-profiling`
      または Slice γ)
- [ ] 必要なら `ERRE_ZONE_BIAS_P` default 変更 hotfix PR
- [ ] γ 着手時に `observation.md` + `baseline.md` を Read (Plan 材料に)

## 想定される落とし穴

- **Ollama が 3 agent 並列で詰まる**: `OLLAMA_NUM_PARALLEL=4` 設定済を
  確認。詰まったら run を 60s に短縮
- **dialog が全く成立しない** (turn_count=0): zone 滞留が悪く agent 間
  co-location が発生していない可能性 → bias_p=0.2 の run で確認
- **bias_events が空** (bias_event_count=0): persona.preferred_zones に
  既に LLM が寄せているケース。bias_fired_rate が null で返るので
  `baseline.md` に「persona prompting の bias 側勝ち」と注記
- **export-log が空 JSONL**: sqlite に dialog_turns が書かれていない =
  bootstrap の turn_sink 配線漏れ可能性、issue 化
