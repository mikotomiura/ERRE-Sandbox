# Design (Final, Hybrid H1) — M7

> `/reimagine` の採用判断: **Hybrid H1 — v2 骨格 + v1 オペレーション詳細**
> 経緯: design-v1.md（初回案）/ design-v2.md（再生成案）/ design-comparison.md（並べた比較）。
> 決定トレース: decisions.md D7。

## 採用した骨格 (v2 由来)

**3 Vertical Slice** 構造。横軸 4-track ではなく、縦切り 3 slice で
「backend 配線 + UI 可視化 + live 観察ログ」を 1 本で通す。

- **Slice α — Observability overlay (First PR)** — B2 + camera zoom preset + 真俯瞰 hotkey
- **Slice β — Behavioral differentiation** — A2 preferred_zones soft-weight + world 拡張 + zone primitive 建物
- **Slice γ — Dialogue & relationship loop** — D1-D4 + B3 を縦切り 1 本に統合

依存: α → β → γ。L6 steering は並走（コード無し文書）。

## 保持した v1 オペレーション詳細

- **工数見積もりを細かく残す** (1h / 2h / 3h / 4h) — 個人開発での進捗管理
- **Empirical prompt tuning Lite を V + A1 に適用** — First PR 直前
- **Blender export 待ちはバックログ** だが完全に捨てず、.glb 完成時に差し替え予約
- **C3 (agent anatomy) は条件分岐** — Slice γ の ReasoningPanel Relationships セクション実装後に
  「まだ必要か」判定。必要なら /reimagine、不要なら deprecation して closed

## First PR (Slice α) — 拡張 scope

V + A1 + B1 に加えて:

| ID | 変更 | 推定 | 依存 |
|---|---|---|---|
| V ✅ | reflection Japanese (commit `cab62df`) | done | — |
| A1 ✅ | personality inject (commit) | done | — |
| B1 ✅ | _fire_affordance_events (commit) | done | — |
| **B2** | `BoundaryLayer.gd` に affordance (yellow 2m) + proximity (cyan 5m) overlay | 3h | B1 |
| **α-cam1** | `CameraRig.gd` にホットキー `0` で真俯瞰 (pitch=-1.57) プリセット | 0.5h | — |
| **α-cam2** | `CameraRig.gd` に zoom preset (ホットキー `-`/`=` でステップズーム) | 0.5h | — |

合計残 ~4h。branch は継続 `feat/m7-priority3-differentiation-xai`。

## Slice β — Behavioral differentiation (次 PR)

| ID | 変更 | 推定 |
|---|---|---|
| β-A2 | `cognition/cycle.py:595 付近` に `_bias_target_zone(plan, persona)` 挿入、preferred_zones に +0.2 weighted resample。bias 値は env var で config 化 | 2h |
| β-world | `world/zones.py` ZONE_CENTERS を拡張（対角配置）、`scenes/zones/BaseTerrain.tscn` 60→100m | 1h |
| β-buildings | `scenes/zones/*.tscn` に MeshInstance3D + Box/Cylinder primitive で agora=低壁, chashitsu=小屋, zazen=石灯籠, study=本棚壁 | 2h |
| β-boundary-sync | `BoundaryLayer.gd` の zone_rects を新 ZONE_CENTERS に追従 | 0.5h |
| β-tests | A2 の「Rikyu は chashitsu を 60% 以上選ぶ」assert | 1h |

合計 ~6.5h。PR ブランチは別 (`feat/m7-slice-beta-differentiation`)。

## Slice γ — Dialogue & relationship loop (次々 PR)

1 PR で以下を縦切り束ね:

| ID | 変更 | 推定 |
|---|---|---|
| γ-D2 | `memory/store.py:310` relational_memory INSERT 経路に `record_dialog_interaction(agent_id, other_id, affinity_delta=0.02)` hook。DialogTurnMsg 受信時に発火 | 3h |
| γ-D1 | `cognition/reflection.py` system prompt に「直近 3 ターンの他 agent 発話」セクション。`MemoryStore.transcript_of` 経由で取得 | 2h |
| γ-D3 | `cognition/cycle.py:603` ReasoningTrace 生成時、`decision` に affinity 値と preferred_zones を根拠として埋める | 1h |
| γ-B3 | `ReasoningTrace` schema に `observed_objects` / `nearby_agents` / `retrieved_memories` 追加、埋める側は cycle.py | 2h |
| γ-UI | `ReasoningPanel.gd` に "Relationships" 折りたたみセクション。`RelationshipBond` を AgentState 経由で | 2h |
| γ-受入 | `evidence/<run>.summary.json` に dialog_turn kind 出現、relational_memory 3 行以上、ReasoningTrace.decision に "affinity" 文字列 | 1h |

合計 ~11h。affinity_delta は固定値 MVP（LLM 判定は繰越）。

## L6 Steering (並走、コード無し)

`.steering/20260424-steering-scaling-lora/`:

- `requirement.md`: 3 軸（LoRA / agent scaling / user-dialog IF）。**H2 が提案した運用予算節は L6 内に入れない** — CLAUDE.md と architecture-rules Skill に既記載のため DRY
- `decisions.md`: 軽量 ADR 形式（3 本、各 20 行以内）。**v2 が提案した 4 節 + ADR は盛りすぎ**、個人開発では 3 本の ADR を簡潔に
- `tasklist.md`: 探索 task のみ、実装は M8+

## 採用しなかった要素

- **v2 の Demo-first 脚本逆算** (H2 候補): scope 縛りとして有効だが、Slice α/β が小さいので過剰。Slice γ 着手時に判断
- **v1 の A3 独立 UI**: 成長は B3 の ReasoningTrace.decision で言語化される
- **v1 の D4 独立 UI** (reflection count 等): 同上、trace に吸収
- **v1 の C4 Blender-wait 明示的明記**: バックログに落として焦点ぼかさない
- **v2 の L6 4 節 + ADR 3 本**: 過剰、3 軸 + 軽量 ADR で十分

## リスク

- **Slice γ 規模**: 11h は個人 1 日限界超え、途中 /smart-compact と live 検証が必須
- **A2 bias 値 (+0.2) が強すぎる可能性**: env var で調整可能化
- **primitive 建物の美的劣化**: Blender export 完成時に差し替え、PR メモで予告
- **C3 判定タイミング**: Slice γ 実装後に judgement、先送りしすぎないこと

## Empirical prompt tuning の運用

- **First PR 直前**: V (reflection) + A1 (personality) を Lite tier で 1 回 (Slice α ではない、合流した First PR 全体)
- **Slice γ 直前**: 相互反省 prompt (D1) を Lite tier で 1 回
- **それ以外**: Structural-only tier で済ませる
