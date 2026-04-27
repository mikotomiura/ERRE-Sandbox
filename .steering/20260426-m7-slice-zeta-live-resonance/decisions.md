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

**新ペルソナ追加時の運用** (M7ζ-2 c4 で persona display_name + 1-line
summary も Strings.gd に統合した結果): 新ペルソナを増やす際は
`personas/<id>.yaml` の追加と同時に
`PERSONA_NAME_<ID>` / `PERSONA_SUMMARY_<ID>` の 2 キーを Strings.gd
に追記する必要がある (`<ID>` は upper-case)。未追記の場合は
`PERSONA_NAME_UNKNOWN` / `PERSONA_SUMMARY_UNKNOWN` にフォールバック
する (= "(未知のペルソナ)" + "—") ので live は壊れないが、ペルソナ
identity が画面に出ない退行になる。M9 で persona expansion 線を
draw する際の checklist に含めること。

## D6 — 3 PR 直列 vs 並列

**判断**: ε と無関係に ζ-1 → ζ-2 → ζ-3 を **直列** で land する
(ε merge 後の現状、並列は不要)。

**根拠**: ζ-2 が schema bump (0.8.0-m7e → 0.9.0-m7z)、ζ-3 が PersonaSpec
additive (no bump、SCHEMA_VERSION 据え置き)。直列なら schema 衝突なし。
並列で進めるとリベース手戻りが発生する。

## D7 — 追加 issue F1〜F3 (2026-04-27) は ζ scope 外、F3 単独 + F1+F2 統合の 2 タスクに分割

> **改訂履歴** (2026-04-27): 初回 v1 案 (3 独立タスク = `dialog-visualization` /
> `agent-locomotion-animation` / `godot-viewport-layout`) を Plan mode +
> /reimagine 経ずに直接書いたため、ユーザー指摘 (CLAUDE.md 違反フラグ)
> を受けた事後 /reimagine validation で v2 案 (F3 単独 + F1+F2 統合) に
> 訂正。memory:plan_mode_gating の 3 件目 skip 実例として記録。

**判断**: ζ-1 部分マージ後の live 観察で浮上した F1 (agent 同士の直接会話
可視化) / F2 (FPS-style 歩行) / F3 (world viewport 拡張) は **いずれも ζ
scope 外** とし、以下 **2 本** の新タスクに切り出して `/finish-task` 時に
scaffold する:

- `agent-presence-visualization` (F1+F2 統合) — Label3D 吹き出し + dialog
  ticker (F1) と AnimationTree state machine + humanoid placeholder mesh
  (F2) を 1 タスクで集約。ζ-2 で wire される persona_id / dialog_turn
  payload を消費する後続。F2 placeholder mesh (CapsuleMesh + 簡易 rig) で
  Blender 共依存を先行緩和、本格 humanoid rig は
  `world-asset-blender-pipeline` 着手時に差し替え。
- `godot-viewport-layout` (F3) — project window size / ReasoningPanel
  split ratio / MainScene root anchor の見直し。schema/backend 非依存で
  1 PR 最速 land、M9-LoRA 着手前にユーザー live 体感を最速で底上げ。

**根拠**:
1. F1〜F3 はいずれも **既存 ζ-1〜3 PR が想定する diff 範囲を逸脱**
   (新規 Label3D シーン / AnimationTree / project.godot window 設定変更)。
   進行中 PR に詰めると review burden 急増 + schema bump 0.9.0-m7z の
   land が遅延する。
2. **F1+F2 統合の妥当性**: 「agent が喋りながら歩く」体感単位で意味的に
   同一、両者とも MainScene / AgentController に shared edit が発生する
   ため別 PR にすると merge conflict 連鎖。Plan agent の v1 不可視再生成案
   (Option E) と独立に同結論。
3. F3 は単独で 1 PR の方が anchor 設計の判断 (1280×720 固定 vs
   adaptive 全画面 + ReasoningPanel オーバーレイ) を /reimagine
   対象にしやすい。

**根拠の根拠** (Option A v1 vs Option E v2 の 8 軸比較):

| 軸 | A (3 独立 v1) | E (2 統合 v2) |
|---|---|---|
| F2↔Blender 共依存解消 | △ | ○ |
| F3 delivery 速度 | ◎ | ◎ |
| /reimagine 粒度 | ◎ | ○ |
| M9-LoRA 着手阻害 | 小 | 小 |
| review 負荷 | 中 | 小 |
| scaffold cost | 3 本 | 2 本 |
| F1↔F2 衝突回避 | × | ◎ |
| 体感単位の意味同居 | × | ○ |

5 軸で v2 優越、3 軸で同等。v1 採用は「各 issue が独立体感」と早合点した
バイアス。/reimagine が実際に結論を覆した (memory:plan_mode_gating の
v1 バイアス典型形に該当)。

## D8 — ζ-3 着手時 /reimagine: phase wheel + 3-commit split を採用、6 軸は v1 維持

**判断**: ζ-3 着手前 (2026-04-27) の Plan mode で v1 (素直案 = Plan A
hybrid を line 数字に正規化) と v2 (/reimagine ゼロ再生成、v1 不可視) を
独立 Plan agent で並列 dispatch、5-8 軸比較の結果、**hybrid を採用**。
v2 が 2 軸を覆し、6 軸は v1 維持の根拠が成立した。

**根拠 (8 軸比較)**:

| 軸 | v1 (Plan A hybrid) | v2 (re-imagined) | 採用 |
|---|---|---|---|
| A. field 集合 | 4 scalars | 5 fields (stride×cadence + phase + jitter + bubble) | **v1** — scalar speed の live histogram 直接観察、wire round 不要、test simple |
| B. **cognition 実装** | per-agent ScheduledEvent heap n 個 + dialog tick 別 event 化 | **phase wheel** (heap 1 個維持、`next_cognition_due` per-agent select、asyncio.gather 並列性維持) | **v2 (覆る)** — heap 構造変更なし、ManualClock test 自然動作、dialog tick 分離リスク回避 |
| C. movement speed | scalar `DEFAULT × factor` | derived `stride × cadence` + round(.,3) | **v1** — wire round hack 不要、test/live 直接観察 |
| D. separation 数式 | 一様 0.4m 押し離し + 単位ベクトル | `(bubble−r)²/bubble² × cadence × 0.3` potential | **v1** — 初期実装は単純で十分、velocity-aligned/cadence 依存は m9-lora で persona 学習が入った後の自然な拡張 |
| E. **split / commits** | 6 commits (c1-c6, split-A/B 分離) | **3 commits** (A schema / B cognition+speed / C separation) | **v2 (覆る)** — review 単位 clear、各 commit 独立 green、phase wheel 採用で heap 操作分離が不要に |
| F. dwell 表現 | 明示 `dwell_time_s` + dwell_until slot | `burst_idle_phase` で動的延長 | **v1** — Rikyū seiza 90s が要件 §B で明示、phase 表現では解像度不足 |
| G. yaml 数値 | (0.85/14/30/1.5) (1.25/7/5/1.5) (0.70/18/90/1.2) | (0.50/2.20/0.30/0.0/1.5) etc. 5 値 | **v1** — speed mode 0.91/1.625/0.910 が M5 fixture range 中央寄りで安全 |
| H. risks | R3 (heap 侵襲) / R4 / R7 | R1 (burst 過密) / R2 (round) / R5 (golden) | phase wheel で R3 は本質的に解消 |

**hybrid 結論**: v1 の field 集合 + speed scalar + dwell 明示 + 単純
separation を保ちつつ、**v2 の phase wheel cognition と 3-commit split
を採用**。覆ったのは B (cognition 実装) と E (split scheme) の 2 軸、
6 軸は v1 維持の根拠が成立。

**重要: v1 維持判断は /reimagine が validate**。「v1 が覆らなかった」=
バイアス除去後も v1 の判断が成立する独立検証になっており、
memory:plan_mode_gating の "1 発案バイアスは構造的に残る" を裏返した
形で価値を出している (覆らないことで v1 confidence が上がる)。

**実装結果との整合性**:
- 実装中、phase wheel は global cognition heap 10s grid に lock される
  挙動を test で確認 (kant 14s と rikyu 18s が同 20s 実効)。dwell 90s
  で rikyu を更に dampen することで 3 mode 分離が live で確保される
  見込み (test では cognition 周期分離 + dwell 単独抑制を別 test で
  gate)。
- 既存 `test_llm_fell_back_result_does_not_stop_loop` で `clock.advance(30.0)`
  を 3 段階分割に変更が必要だった (phase wheel が `monotonic()` を
  handler entry 毎に読むため、ManualClock advance の意味論が phase
  wheel 採用で変わった)。これは v1 (per-agent heap) では起きなかった
  regression で、v2 採用の trade-off。

**参照**:
- `~/.claude/plans/reflective-bouncing-bumblebee.md` (採用 plan、3 commits 構成)
- main commits: cfc6449 (commit A) / 0f3727f (commit B) / c7eed76 (commit C) / 61671b4 (chore)

