# Decisions — M7 Slice ζ (Live Resonance)

> 重要な設計判断とその根拠を記録。Plan mode + /reimagine 後に D1〜 を埋める。

## D0 — slice 名と発生経緯

**判断**: M7 slice ζ (zeta) として独立 slice 化する。

**根拠**: live 検証で 13 件の体感的違和感が同時期に集中。これらは個別バグでなく、
M7-α〜ε が backend 関係性ループを優先した結果として **Godot 視覚層と persona
機械化が背中合わせに遅延** したことの帰結。「ε で hygiene を集約した」のと
対称に **ζ で live 体感を集約** することで、M9-LoRA に進む前に「見える差分・
見える社会・見える成長」のうち **見える部分** を底上げする。

**根拠の根拠**: `~/.claude/projects/-Users-johnd-ERRE-Sand-Box/memory/project_m7_beta_merged.md`
で「次候補: ε scaffold / R4 post-merge review / m9-lora pre-plan / CLAUDE.md
empirical eval」と記録されており、live 検証は **当初の次候補にない 5 番目の
動因**。これは memory にない「実体験から来る要請」であり M9 より前置すべき。

## D1 — /reimagine の hybrid 採用根拠 (Plan A × Plan B)

**判断**: Plan B の framing (観察可能性 first / Godot 完結 first /
behavior_profile sub-doc 集約 / 3 PR 分割) を採用しつつ、separation の
場所と belief_kind 表面化方式は **Plan A の技術判断** を採用する。

**根拠 (8 軸の比較)**:
- ε との並走性: Plan B (3 PR で ζ-1 Godot 完結が ε review 中並走可) > A
- schema 集約度: Plan B `behavior_profile` sub-doc > A flat 3 fields
- separation の真因対処: Plan A (backend `world/tick.py:801` proximity pair
  走査 mirror) > B (Godot 押し戻しのみ — Python orchestrator の近接 waypoint
  発行が真因のため client 押し戻しでは server state と乖離)
- belief_kind wire 安全性: Plan A (schema bump 経由完全制御) > B
  (`extra="allow"` additive、リスク R2 残存)
- cognition rewire 安全性: Plan B 分割 (ζ-3a/b) > A 1 commit
- day/night driver 効率: Plan A (Timer 1Hz) > B (`_process` 全フレーム)
- live 体感 delivery 速度: Plan B (ζ-1 で UI 体感先行) > A (backend bump
  待ち)
- review 負荷: Plan A (2 PR) > Plan B (3 PR) — トレードオフ

**結論**: Plan B の framing と decomposition を採用、Plan A の technical
correctness (separation backend / belief_kind schema bump / Timer 1Hz) を
取り込む hybrid。

**根拠の根拠**: memory:plan_mode_gating で「Plan mode + /reimagine 強制」、
PR #81 #85 の 2 件 skip 実例の再発を防ぐ。

## D2 — D / A2-3 / C1-2 の defer 切り出し

**判断**: 以下 3 task を ζ scope 外として deferral、ζ merge 後に新規
slice scaffold を起こす。

- `m9-lora-pre-plan` — D1+D2 (成長機構 + LoRA gate + 全体プラン)
- `world-asset-blender-pipeline` — A2+A3 (Blender .glb pipeline 完成)
- `event-boundary-observability` — C1+C2 (event 境界線本格 UI)

**根拠**: ζ で全 13 issue を抱えると PR が肥り、live 体感の改善が後送り
される。D は M9 の主要 deliverable、A2/A3 はアセット制作タスクで時間
読めない、C1/C2 本格 UI は M10-11 evaluation layer の一部。defer すること
で ζ は「見える差分・見える社会」に集中できる。

## D3 — separation は backend で

**判断**: A5 (3 体一箇所 collapse) の対処は Godot client ではなく backend
`world/tick.py` の `_on_physics_tick` で `Kinematics.position` を XZ 平面
0.4m 押し離す。

**根拠**: Python orchestrator が同一 waypoint を 3 体に発行することが
collapse の真因。client 側で push back しても server state は collapse
したまま、proximity event が連続発火して dialog scheduler を撹乱しうる。
backend で kinematics を補正すれば agent_update.position に伝搬し
Godot の visual offset と co-exist できる。

**根拠の根拠**: 既存 `combinations(self._agents.values(), 2)` pair 走査
パターン (tick.py:801) が proximity events 用に存在、同パターンを mirror
することで新ループ無し・テスト容易。

## D4 — `PersonaSpec.behavior_profile` を sub-document として集約

**判断**: `movement_speed_factor` / `cognition_period_s` / `dwell_time_s` /
`separation_radius_m` を `BehaviorProfile(BaseModel, extra="forbid")` として
`PersonaSpec` 下に集約する。flat にフィールドを散らさない。

**根拠**: 後続 m9-lora で persona 別 sampling やトレーニングデータ閾値を
追加するとき、同じ sub-doc に同居させられる。既存 `default_sampling`
sub-doc がすでに同じパターン (PersonaSpec)。flat field 方式は schema
diff が読みにくく、persona YAML 側の人手編集も冗長になる。

**根拠の根拠**: Plan B framing (iii) と一致、Plan A flat 3 fields より
拡張性が高い。

## D5 — i18n は Strings.gd 静的 dict、`tr()` / `.csv` は導入しない

**判断**: ReasoningPanel + DebugOverlay の JP ラベル化は
`godot_project/scripts/i18n/Strings.gd` の `const LABELS: Dictionary` で
静的に解決、Godot 標準 `tr()` / `.csv` localisation 機構は **導入しない**。

**根拠**: live-resonance の対象は ≤15 ラベル。`.csv` パイプラインの cost
(.csv テーブル管理 + locale 切替 UI + import 設定) はラベル数に対して
過剰。将来 (post-M11) 全 i18n に踏み切るときに `tr()` への置換は
sed 1 発で済む (一元管理されているため)。

## D6 — 3 PR 直列 vs 並列

**判断**: ε と無関係に ζ-1 → ζ-2 → ζ-3 を **直列** で land する
(ε merge 後の現状、並列は不要)。

**根拠**: ζ-2 が schema bump (0.8.0-m7e → 0.9.0-m7z)、ζ-3 が PersonaSpec
additive (no bump、SCHEMA_VERSION 据え置き)。直列なら schema 衝突なし。
並列で進めるとリベース手戻りが発生する。

