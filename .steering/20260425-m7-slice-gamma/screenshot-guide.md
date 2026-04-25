# MacBook Screenshot Capture Guide (γ + β 合算)

> G-GEAR ハンドオフ task #2 の手順書。ユーザーが MacBook の Godot GUI で
> 手動操作を行う必要があるため、orchestrator 起動以外は手作業。

## 撮影対象 (5 枚 + optional 1)

### γ 主目的 (1 枚)
- [ ] **`screenshot-relationships.png`** — ReasoningPanel の Relationships ブロックを
      展開した状態。3 persona すべてが少なくとも 1 turn 対話済で affinity != 0 の bond が
      表示されていること。"<persona> affinity ±0.NN (N turns, last @ tick T)" 形式が
      読めること
      → 保存先: `.steering/20260425-m7-slice-gamma/run-01-gamma/screenshot-relationships.png`

### β follow-up (3 枚、observation.md §6)
- [ ] **`screenshot-topdown.png`** — top-down hotkey `0` の 100m 全景。BaseTerrain
      100m + 5 zone Voronoi 配置が見えること
      → 保存先: `.steering/20260425-m7-beta-live-acceptance/run-01-bias01/screenshot-topdown.png`
- [ ] **`screenshot-zone.png`** — zone 拡大 (chashitsu / agora / garden のいずれか)。
      BoundaryLayer 5 zone rects + Study/Agora/Garden primitive buildings が visible
      → 同 dir 配下 `screenshot-zone.png`
- [ ] **`screenshot-reasoning.png`** — ReasoningPanel (MIND_PEEK 開いた状態)。
      observed_objects / nearby_agents / retrieved_memories の γ 拡張 fields が
      埋まっていること
      → 同 dir 配下 `screenshot-reasoning.png`

### γ optional (1 枚)
- [ ] **`screenshot-chashitsu-fixed.png`** — Chashitsu zone 内側 close-up。
      γ で位置補修 (0,0,15) → (33.33,0,-33.33) が反映されていること
      → 任意、撮ったら `.steering/20260425-m7-slice-gamma/run-01-gamma/`

## 手順

### 1. orchestrator を MacBook で起動 (1 terminal)

```bash
cd "/Users/johnd/ERRE-Sand Box"
ERRE_ZONE_BIAS_P=0.1 uv run erre-sandbox \
  --db var/run-screenshot.db \
  --personas kant,nietzsche,rikyu
```

→ stdout に `INFO: Uvicorn running on http://0.0.0.0:8000` が出れば OK。Ctrl-C 禁止
（screenshot 撮り終わるまで)。

### 2. Godot を別 terminal で起動

```bash
godot --path "/Users/johnd/ERRE-Sand Box/godot_project"
```

→ Godot エディタ起動 → MainScene を開いて `F5` で再生、または
`godot --path "/Users/johnd/ERRE-Sand Box/godot_project" -e` でエディタ起動後 F5

### 3. WS 接続確認

- Godot コンソールに `WebSocket connected` + `world_layout received` (γ で追加) ログが出る
- 5-10 秒待つと `agent_update` envelope が流れ込み、3 agent が peripatos / chashitsu /
  agora 周辺に出現する

### 4. screenshot 撮影 (順序推奨)

| # | hotkey | 操作 | 確認ポイント |
|---|---|---|---|
| 1 | `0` | top-down 全景 | 100m terrain + 5 zone outline |
| 2 | `1`-`5` | zone 拡大 (chashitsu/agora/garden 推奨) | primitive buildings + Voronoi rect 内側 |
| 3 | `m` (MIND_PEEK) | ReasoningPanel 開く | observed_objects + nearby_agents + retrieved_memories |
| 4 | (同上、Relationships block expand) | 1 agent focus したまま 60-120 秒待つ | bond 1 つ以上、affinity != 0、last @ tick 数字 |
| 5 | (任意) chashitsu close-up | zone hotkey + free-look | 茶室の正方形ベースが zone 中心 (33,0,-33) に居る |

screenshot は **macOS の `Cmd+Shift+4`** で領域選択 → 保存ファイル名を上記に rename
するのが速い。Godot 内蔵の `print_screen` も使えるが座標固定のスクショに弱い。

### 5. 後片付け

- orchestrator 側 Ctrl-C
- DB は `var/run-screenshot.db` に残るが分析対象外、削除 OK:
  ```bash
  rm var/run-screenshot.db
  ```

## 撮影完了後にやること

1. observation.md §6 の β.4-β.6 チェックボックスを tick
2. `.steering/20260425-m7-slice-gamma/decisions.md` の R1 か R3 の "evidence"
   subsection に `screenshot-relationships.png` への参照を追記
3. memory `project_m7_beta_merged.md` の "MacBook 側の残タスク" セクションを
   "完了済" に更新

## トラブルシュート

- **Godot が WS 接続しない**: orchestrator が `0.0.0.0:8000` で listen している
  ことを確認、Godot 側の WS URL が `ws://127.0.0.1:8000/ws` (or `localhost`) になって
  いることを確認
- **bond が永遠に 0 のまま**: 3 agent が co-locate しないと dialog が起きない →
  120 秒以上待つか、`ERRE_ZONE_BIAS_P=0.2` で再起動 (chashitsu に rikyu + kant が
  集まりやすくなる)
- **Relationships block が空**: ReasoningPanel が agent_focus を取得していない →
  Godot 側で agent をクリックして focus 状態にする
- **Godot のターミナル起動コマンドが古い**: `which godot` で `/opt/homebrew/bin/godot`
  になっていることを確認、`godot --version` で 4.4.x 系であること
