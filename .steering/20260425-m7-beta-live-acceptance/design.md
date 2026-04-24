# Design — G-GEAR Live Acceptance Bundle

> **G-GEAR セッション開始時に最初に Read する 1 枚**。
> 本 dir には設計判断は無い (観察タスク)。詳細は `requirement.md` の
> 14 受け入れ条件と `tasklist.md` の手順を見ること。

## 1. 何故 4-in-1 bundle か

2026-04-24 〜 25 に 4 PR が連続で merge され、それぞれ G-GEAR live
acceptance が残った:

- PR #83 (Slice β、`a76343c`)
- PR #87 (m8-session-phase-model、`447218c`)
- PR #88 (m8-episodic-log-pipeline、`0e2e50e`)
- PR #89 (m8-baseline-quality-metric、`62af762`)

これらは **同じ live run DB を共有できる**: β run の最中に dialog_turn
sink (#88) と bias_event sink (#89) が sqlite に書き込まれ、session-phase
FSM (#87) はブート時の default 確認 + Python REPL での遷移確認のみで済む。
個別に G-GEAR セッションを切ると最大 4 回往復 (各 ~1h)、bundle なら
1 セッション 2-3h で完結する。

## 2. 実行 flow (tasklist.md と対応)

```
Pre-flight (10 min)
  └─ git pull / Ollama / Godot 接続
PR #87 sanity (5 min)
  └─ Python REPL で RunLifecycleState の default + 遷移確認
Run 1: bias_p=0.1 (10-15 min)
  └─ orchestrator + _stream_probe_m6.py 並走、80s
  └─ Godot で目視 3 スクショ
Post-run 1 (5 min)
  └─ export-log (#88) + baseline-metrics (#89) を sqlite に対し実行
Run 2: bias_p=0.2 (10-15 min)
  └─ 同上
Post-run 2 (5 min)
  └─ 同上
Analysis (30-45 min)
  └─ summary.json から zone 滞留分布抽出
  └─ baseline JSON 2 本の平均 / 分散 / 代表値計算
記録 (30 min)
  └─ observation.md (β + #87)
  └─ baseline.md (#88 + #89、M9 reference として凍結宣言)
Follow-up (任意、~30 min)
  └─ 結論を decisions.md に逆流 (D9 + L6 D1)
  └─ 必要なら hotfix PR
```

## 3. 成果物

セッション完了時に本 dir に存在すべきファイル:

```
.steering/20260425-m7-beta-live-acceptance/
├── requirement.md             (既存、14 受け入れ条件)
├── tasklist.md                (既存、手順)
├── design.md                  (本ファイル)
├── observation.md             (新規、β 6 + #87 sanity 2 = 8 項目の判定)
├── baseline.md                (新規、#88 + #89 の数値 table、M9 reference)
├── run-01-bias01/
│   ├── run-01.jsonl           (stream probe)
│   ├── run-01.jsonl.summary.json
│   ├── dialog-turns.jsonl     (export-log 出力)
│   ├── baseline.json          (baseline-metrics 出力)
│   └── screenshot-{topdown,zone,reasoning}.png
└── run-02-bias02/             (同構造)
```

## 4. Plan mode を使わない理由

- 設計判断ゼロ — 既に merge 済の 4 PR の動作確認のみ
- 受け入れ条件は requirement.md に明文化済 (14 項目)
- 想定される落とし穴 (Ollama 詰まり / dialog 不成立 / bias_event ゼロ /
  export 空) は tasklist 末尾に列挙済
- /reimagine が役立つ「複数案ありうる設計」が存在しない
- CLAUDE.md の「Plan mode 必須」は **設計判断・新機能・リファクタリング**
  に対する規定で、観察 acceptance は対象外

## 5. 失敗時の判断ルール

| 失敗パターン | 判断 |
|---|---|
| β 6 項目のうち 1-2 個 FAIL (例: 滞留比率が 45%) | observation.md に記録、bias_p 値の hotfix で対応可 → `ERRE_ZONE_BIAS_P` default 変更 PR |
| β 4 項目以上 FAIL | bias 設計の根本見直し → γ 着手前に `m7-bias-redesign` 起票 |
| #87 で `ValueError` が想定外の遷移で出る | schema 修正 hotfix |
| #88 export-log で 0 行 (turn_count=0) | bootstrap の turn_sink 配線漏れ → blocker、即 issue 化 |
| #89 で 3 metric が全て null | run が短すぎ or sink 配線漏れ、再 run |
| #89 で `bias_fired_rate` のみ null | persona prompting が bias より強い → metric 解釈を baseline.md に注記 (失敗ではない) |

## 6. 関連 PR / dir

- PR #83: https://github.com/mikotomiura/ERRE-Sandbox/pull/83
- PR #87: https://github.com/mikotomiura/ERRE-Sandbox/pull/87
- PR #88: https://github.com/mikotomiura/ERRE-Sandbox/pull/88
- PR #89: https://github.com/mikotomiura/ERRE-Sandbox/pull/89
- PR #90 (本 bundle scaffold): https://github.com/mikotomiura/ERRE-Sandbox/pull/90
- 過去 acceptance 手順: `.steering/20260421-m5-acceptance-live/`
