# m2-functional-closure — MVP 機能的完了 (1 Kant walker full-stack wiring)

## 背景

`v0.1.0-m2` (2026-04-19) で **Contract layer** (WS / Handshake / Session FSM /
Schema `0.1.0-m2`) は完全動作し T20 acceptance 5 ACC 全 PASS となった。しかし
MASTER-PLAN §4.4 MVP 検収条件のうち以下 4 項目は **GAP-1** (`_NullRuntime`
依存 / WorldRuntime↔Gateway 配線欠落) により未 PASS:

1. G-GEAR で `ollama serve` + inference server listen
2. Kant エージェントが peripatos 周回 + 10s ごと LLM 応答
3. `sqlite-vec` に `episodic_memory` 追加 + `recall_count>0` 再検索
4. MacBook Godot でアバターが peripatos を 30Hz で歩く

これらは functional-design.md §4 の MVP 定義「1 体の Kant エージェントが
peripatos を歩行し、Memory Stream に記憶を書き、Godot 4.4 で 30Hz 描画される」
の中核であり、本タスクで **機能的 MVP を closeout** する。

MASTER-PLAN §5 の M4 (`gateway-multi-agent-stream`) は 3 agent + reflection +
relationships を含む広域タスクであり、1-Kant walker に絞ればずっと小さく終わる。
本タスクは M2 と M4 の間に **patch 位置** で挟み、`v0.1.1-m2` tag で機能的 MVP
完了を明示する。

## ゴール

MASTER-PLAN §4.4 の **4 項目を all PASS** にし、`v0.1.1-m2` タグで MVP 機能的
完了を formalize する。

完了条件:
- MacBook Godot で Kant avatar が peripatos 周回を視認できる
- G-GEAR ログで 10s ごとの LLM 応答 1 行が流れる
- `sqlite-vec` の `episodic_memory` テーブルに少なくとも 5 レコード以上
- `git tag v0.1.1-m2` が main に付与される

## スコープ

### 含むもの

- `src/erre_sandbox/runtime.py` または `__main__.py` の新規作成 (orchestrator)
  - T10 memory store / T11 ollama adapter / T12 cognition cycle / T13 world tick
    を実インスタンスで wire
- `integration/gateway.py:444-458` の `_NullRuntime` を real WorldRuntime に置換
  する **依存注入導線** の整備 (既存 DI 設計を活用、再設計しない)
- 30Hz WorldTickMsg を world → gateway → Godot へ実流させる
- 10s cognition loop が ollama → memory write を実行することを確認するテスト
- MVP 4 検収項目の実測 evidence (`.steering/20260419-m2-functional-closure/evidence/`)
- `v0.1.1-m2` tag
- MASTER-PLAN §4.4 の 4 チェックボックスを `[x]` に更新

### 含まないもの

- **3-agent 拡張**: Nietzsche / Rikyu persona 追加は M4 スコープ
- **reflection / semantic memory layer**: M4 スコープ
- **ERRE モード 6 種切替**: M5 スコープ
- **観測性ログ基盤整備**: M7 スコープ
- **SGLang 移行 / LoRA**: M7+ スコープ
- **既存 T10-T14 モジュールの内部リファクタ**: 最低限の API 追加のみ許容
- GAP-2 (live 自動化) / GAP-4 (Godot 4.6 diff): 本タスクでは扱わない

## 受け入れ条件

- [ ] `uv run python -m erre_sandbox` (または `erre_sandbox.main`) で G-GEAR 上
      orchestrator が起動し、`ollama serve` と接続、`ws://g-gear.local:8000/stream`
      で listen する
- [ ] MacBook Godot で接続後、Kant avatar が peripatos を **30Hz 更新** で周回
      移動することを視認 (evidence: screen-recording or screenshots per tick)
- [ ] G-GEAR ログに 10s ごと 1 回 `[cognition] Kant responded: ...` が出る
      (evidence: gateway log 60s 抜粋)
- [ ] `sqlite-vec` の `episodic_memory` テーブルに >= 5 行、`recall_count`
      カラムに > 0 のレコードが存在
- [ ] `uv run pytest` が緑 (新規テスト含む)
- [ ] `.steering/20260419-m2-functional-closure/acceptance-evidence.md` に 4 項目
      の evidence pointer を記録
- [ ] `v0.1.1-m2` annotated tag が main に push される
- [ ] MASTER-PLAN §4.4 の 4 checkbox を `[x]` に更新

## 関連ドキュメント

- `docs/functional-design.md` §4 (MVP 定義)
- `docs/architecture.md` §Gateway (`_NullRuntime` 注意書き、本タスクで cleanup)
- `.steering/20260418-implementation-plan/MASTER-PLAN.md` §4.4 (MVP 検収条件)
  + §5 M4 (本タスクとの責務分離)
- `.steering/20260419-m2-integration-e2e-execution/known-gaps.md` GAP-1
- `.steering/20260419-m2-acceptance/acceptance-checklist.md` (layer-scope 達成済)
- `src/erre_sandbox/integration/gateway.py:444-458` (`_NullRuntime` 差替 point)

## 運用メモ

- 破壊と構築（/reimagine）適用: **Yes**
- 理由: orchestrator の配置 (`__main__.py` vs `runtime.py` vs 分割) と DI 境界
  (gateway が WorldRuntime を受け取る形 vs WorldRuntime が gateway を起動する形)
  は複数案が自然であり、素直な初回案は後からの M4 拡張で歪む可能性が高い。
  `/reimagine` で初回案を破棄し、M4 (3-agent / multi-stream) への拡張容易性を
  含めた対案との比較を行う。
- タスク種別: **新機能追加** (`/add-feature`)。ただし既存 T10-T14 モジュールを
  組み合わせるのが主で、新規コードは orchestrator と tests に集中する
- patch milestone 位置付け: `v0.1.0-m2` → 本タスク完了で `v0.1.1-m2`。M4 は
  その後 `v0.2.0-m4` 相当で multi-agent 拡張
