# v1 / v2 Comparison — B2 + Follow-up

> `/reimagine` (破壊と構築) の比較レポート。v1 = 初回案、v2 = v1 不可視で再生成した案。
> 下表は差異の抜粋。3 分類で整理 — "原本のみ" / "v2 のみ" / "両方あるが異なる"。

## 主要な設計判断の差異

| 軸 | v1 | v2 |
|---|---|---|
| track 構造 | **4-track (A/B/C/D) + V vertical** | **3 vertical slice (α/β/γ)** |
| Slice の中身 | 横軸分割 (A= 差別化, B=xAI, C=world, D=対話) | 縦切り (α=UI可視化, β=行動差別化, γ=対話+関係+trace) |
| First PR scope | V + A1 + B1 + **B2** (4 commit, ~8h) | Slice α = B2 + **camera zoom preset + 俯瞰 hotkey** (2-3 日) |
| xAI 位置付け | Track B (3 item 分散: B1/B2/B3) | Slice γ の中核、B3 は γ に統合 |
| A3 (shuhari progression) | **独立 track item** (A3: Godot StateBar 進捗 bar) | **B3 の ReasoningTrace.decision に吸収**、専用 UI 無し |
| C3 (agent anatomy 視覚化) | **独立 /reimagine 必須項目** (粒子/UI/shader 3 案) | **無し** (ReasoningPanel Relationships 折りたたみに置換) |
| Blender 建物アセット | 待ちの繋ぎ (C4 primitive) | **完全に捨てる**、primitive 一本勝負 (MultiMeshInstance3D) |
| 対話 (D 系) | 4 item 分割 (D1 相互反省 / D2 affinity 更新 / D3 prompt flow / D4 成長 UI) | **1 vertical slice γ に統合**、成長 UI は ReasoningTrace に吸収 |
| 成長メトリクス UI | D4 独立 (reflection count, dialog cumulative, shuhari bar) | **無し**、ReasoningTrace.decision で言語化 |
| L6 steering | 3 軸 (LoRA / scaling / user-dialog) | 4 節 (+ 運用予算制約) + **ADR 3 本** + design.md の acceptance gate |
| 代替提案 | 無し | **Demo-first 5 分動画脚本逆算** |

## 原本 (v1) のみの要素 — v2 が落とした

- C3 の独立性（粒子 / UI / shader 3 案比較という表現の探索）
- A3 専用 UI (StateBar 進捗 bar)
- D4 成長メトリクス UI（reflection count / dialog cumulative）
- Blender export 待ちを明示的な「繋ぎ」として扱う戦略
- 各 track の細かい工数見積もり（1h / 2h / 3h / 4h）
- Empirical prompt tuning Lite tier を V + A1 に走らせる記述（operations 側）

## v2 のみの要素 — v1 が書き漏らした

- **Vertical slice 思想**: 各 slice で backend 配線 + UI + live log をペア
- **Demo-first 脚本逆算** 代替アプローチ（scope を先に縛る方法）
- **xAI 最優先 positioning**: γ を最重量に置き、β を「γ の舞台」として最小限化
- **primitive 建物による "体積の違い" 差別化** (agora=低壁, chashitsu=小屋, zazen=石灯籠, study=本棚壁)
- **ADR 形式** の decisions.md (LoRA backend / agent cap / dialogue IF modality)
- **A2 bias config 化** (env var、強すぎると zone 貼り付き失敗モード)
- **affinity_delta 固定値 MVP** と B3 トレースで事後言語化する設計
- **L6 の運用予算制約** 節 (Ollama 並列上限、ローカル限定)
- **受入基準の `evidence/<run>.summary.json` 具体化**（dialog_turn kind 出現、relational_memory 3 行、ReasoningTrace.decision に "affinity" 文字列）

## 両方あるが異なる

| 項目 | v1 | v2 |
|---|---|---|
| world 拡張 | 120m + proximity 5→8m + stress clamp | **100m + ZONE_CENTERS 再配置**（対角配置）、proximity 閾値は別枠で議論 |
| A2 実装 | `cycle.py` Step 5 で destination_zone に penalty/bonus (importance_hint ±0.1) | `cycle.py:595` 付近に `_bias_target_zone(plan, persona)` 挿入、+0.2 weighted resample |
| relationship 実装 | D2 (ProximityEvent/SpeechEvent → bond 更新) + D3 (AgentState.relationships 追加) | `memory/store.py:310` に `record_dialog_interaction` hook、schema 追加せず relational_memory table に直接書く |
| 相互反省 | D1 で reflection.py が他 agent の直近 reflection を episodic_window に混ぜる | reflection.py system prompt に「直近 3 ターンの他 agent 発話」セクション、`MemoryStore.transcript_of` 経由 |
| First PR milestone | 4 commit (V/A1/B1/B2) ~8h | Slice α = B2 + camera 2 item ~2-3 日 |

## 評価観点

### v1 の強み
- 工数が細かく見積もられ、依存エッジで厳密 → 進捗管理しやすい
- C3 の /reimagine を明示的に予約 → アート判断を先送りしつつ失わない
- Empirical prompt tuning への言及 → 新 Skill の実走スケジュールが具体的
- Blender パイプラインを捨てず共存させる現実解

### v2 の強み
- Vertical slice ごとに live 観察まで通るので **観察可能性の増分がはっきり**
- Slice γ で MASTER-PLAN の 70/35/45 約束をまとめて埋めに行く **合目的性**
- Demo-first 脚本という **scope を先に縛る具体的手法** を代替として提示
- primitive 建物で Blender 依存を外す **プロジェクト外資源への依存削減**
- ADR 形式 L6 で **将来の判断追跡可能性**
- A3/D4/C3 の統合で **milestone 数を半分に** (5+→3)

### v1 の弱み
- 4-track 均等配分で「何が先に体感に効くか」の優先が曖昧
- C3 を独立で残したことで anatomy デザインが blocker 化する危険
- D1-D4 分割で依存エッジが重く、 1 つ詰まると連鎖停滞

### v2 の弱み
- Slice γ (7-10 日) が大きすぎる → context 管理と live 検証サイクルに挑戦
- A3 専用 UI を捨てることで「shuhari の成長が目視できない」批判が出うる
- Blender 全面後回しで見栄え面の初回 demo 印象が下がる
- Empirical prompt tuning への言及が無い（運用手順の欠落）

## Hybrid 案 (v1 + v2 の良いとこどり候補)

### H1: v2 骨格 + v1 operational 詳細
- 3 vertical slice 構造を採用 (v2)
- 各 slice 内の工数は v1 の細かさを採用 (A2=1h, world=2h 等)
- First PR は Slice α に拡張 (B2 + camera preset) → v1 の 4-commit から 5-commit へ
- Empirical prompt tuning Lite を V+A1 に適用（v1 由来、PR 直前）
- C3 は v1 の /reimagine 必須指定を引き継ぐが、Slice γ の ReasoningPanel 実装後に**適用するかどうかを判定**する条件分岐化（v2 が C3 を暗に不要扱いしたのを formal に確認する手順）

### H2: v2 骨格 + Demo-first pre-step + v1 L6 コンパクト版
- v2 の 3 slice + Demo-first 脚本を Slice β 着手前に書く（scope 縛り）
- L6 は v1 の 3 軸に簡略化（ADR 形式は盛り込みすぎ、個人開発なら README 風が軽い）

### H3: v1 骨格 + v2 観点を吸収
- 4-track 構造は維持
- ただし各 track 内に「live 観察成果物」を mandatory にする（v2 の vertical slice 精神だけ借りる）
- C3 は v1 のまま独立 /reimagine
- A3/D4 は独立項目を維持（成長の目視は捨てたくない、という判断）

## 採用候補

- **v1 純**: 初回案。track 構造の均等配分、C3/A3/D4 を独立項目として残す
- **v2 純**: vertical slice に完全に切り替える。成長 UI/anatomy を捨てる勇気を示す
- **Hybrid H1**: v2 骨格 + v1 細部（推奨候補 1）
- **Hybrid H2**: v2 骨格 + Demo-first 先行 + L6 簡略化（推奨候補 2）
- **Hybrid H3**: v1 骨格 + v2 精神吸収（保守的）
