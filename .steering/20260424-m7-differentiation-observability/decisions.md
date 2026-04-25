# Decisions — M7 First PR

このファイルは設計判断を記録する。**First PR** 期間中に出た判断のみ。
Follow-up track (A2/A3/B3/C/D) の判断は別タスク or 本ファイルの末尾セクション。

## D1. First PR を「優先 3」に絞る

- **選択肢**: (a) 4-track 全部同時, (b) Track A 全部, (c) 優先 3 のみ
- **採用**: (c) 優先 3 (V + A1 + B1 + B2)
- **理由**: 体感デルタ/工数比最大。`~8h` で 1 PR。残り track は merge 後に判断。
- **源**: AskUserQuestion 回答 2 (2026-04-24 plan 承認時)

## D2. L6 (LoRA / scaling / user-dialogue IF) は別 steering で並行起票

- **選択肢**: (a) 同タスクの decisions.md に書く, (b) 別 steering, (c) MASTER-PLAN 追記
- **採用**: (b) `.steering/20260424-steering-scaling-lora/`
- **理由**: コード作業と戦略文書を混ぜない。Track D4 の成長メトリクス実装後に
  閾値を確定する前提で初稿は定性記述。
- **源**: AskUserQuestion 回答 3

## D3. AffordanceEvent MVP は chashitsu 1 zone の 1-2 prop のみ

- **選択肢**: (a) 全 5 zone に prop 配置, (b) chashitsu のみ
- **採用**: (b)
- **理由**: PR 肥大化防止。schema/発火機構ができれば他 zone は機械的追加。
  アンチパターン回避 (plan file 末尾)。

## D4. A1 の prompt 追加は 2 行以内に抑制

- **選択肢**: (a) 全 personality field を形容詞化して文章で渡す,
  (b) 数値 1 行 + Wabi/Ma 1 行で計 2 行, (c) JSON object を dump
- **採用**: (b)
- **理由**: context 窓圧迫回避。形容詞化は LLM に委ねる（"openness=0.8 →
  好奇心旺盛" という解釈は LLM の役割）。
- **源**: plan file "アンチパターン回避メモ"

## D5. V は reflection.py を大改造しない (dialog_turn パターンの流用)

- **選択肢**: (a) language manager を新設, (b) system prompt tail +1 行のみ
- **採用**: (b)
- **理由**: PR #68 で dialog_turn.py が同パターンで成功している。First PR 範囲では
  同じ最小改修で十分。manager 抽出は languages が 2 箇所を超えた時に検討。

## D6. B2 の overlay は hardcode 座標で先行、WebSocket 配線は次 PR

- **選択肢**: (a) schema に PropSpec を足し、WebSocket で座標を送る,
  (b) Godot 側に同 prop 座標を hardcode し、後で配線
- **採用**: (b)
- **理由**: B1 と B2 の結合度を下げて並列開発しやすくする。prop 座標は M7 期間中に
  2-3 箇所しか動かない想定。schema 変更は B3 (ReasoningTrace 拡張) とまとめて
  次 PR で。

## 本 PR 外だが記録すべき判断 (deferred)

### C3 (agent anatomy visual) は Slice γ 実装後に要否判定

- ~~着手前 /reimagine 必須~~ ← D7 により条件分岐化
- v2 が提案した ReasoningPanel Relationships セクションで代替される可能性高い
- Slice γ 実装後に「まだ必要か」を判定。必要なら 3 案 (粒子/UI/shader) を
  /reimagine で比較、不要なら deprecation して close。

## D7. /reimagine 遡及適用による H1 採用

- **経緯**: 2026-04-24、First PR 着手中に B1 まで実装した時点でユーザーから
  「設計段階で破壊と構築は適用したの？」の指摘を受けた。メモリ記録「設計タスクでは
  必ず適用する」「迷ったら適用する」の不遵守を自認。
- **選択肢**: (α) B1 未コミットで破棄し全体 /reimagine, (β) B1 コミット確定後に
  B2 + Follow-up だけ /reimagine, (γ) 現状継続
- **採用**: (β) → design-v1.md / design-v2.md / design-comparison.md / design-final.md の
  4 ファイル生成
- **比較結果**: 4 候補 (v1 純 / v2 純 / H1 / H2 / H3) のうち **H1 (v2 骨格 + v1
  オペレーション詳細)** を採用
- **根拠**:
  - v2 の Vertical Slice 構造は「観察可能性の増分」単位で進められ、Slice γ で
    MASTER-PLAN 約束 (70/35/45) をまとめて埋める合目的性が高い
  - v1 の工数細分化 / Empirical Lite 実走 / Blender-as-backlog は個人開発運用に
    必須で捨てたくない
  - v2 の「成長 UI/anatomy 独立項目を捨てる」は合理的だが、C3 は念のため
    Slice γ 実装後の条件分岐として残す（無い物ねだりになる前にチェック）
- **決定影響**:
  - First PR scope が V+A1+B1+B2 (4 commit) から V+A1+B1+B2+α-cam1+α-cam2 (6 commit) に拡張
  - Follow-up track 構造が 4-track (A/B/C/D) から 3 slice (α/β/γ) に再編
  - A3 / D4 独立 UI を廃止、ReasoningTrace.decision に吸収
  - Blender export 待ちはバックログ化、建物は primitive 一本
- **v1 を否定したのではなく両案の美点をブレンドした点が重要**: 純 v2 だと
  Empirical 運用と C3 安全弁を失う、純 v1 だと観察可能性の縦切りを失う

## D8. Slice β 実装 — Plan mode 内 /reimagine で 5 軸決定

- **経緯**: 2026-04-24、Slice α (PR #81) merge 後、design-final.md 記載の β
  (β-A2 + β-world + β-buildings + β-boundary-sync + β-tests, ~6.5h) に着手。
  Plan mode で /reimagine 規律 (v1 → 破壊 → v2 → synthesis) を Plan agent に
  実行させ、5 軸それぞれの設計選択を決定。
- **採用** (plan file: `/Users/johnd/.claude/plans/zazzy-painting-petal.md`):
  - Axis 1 (bias): post-parse probabilistic resample + `bias.fired` 構造化ログ
  - Axis 2 (world scale): `WORLD_SIZE_M: Final[float] = 100.0` 定数導入、
    centers を `±WORLD_SIZE_M / 3` から派生
  - Axis 3 (buildings): Study / Agora / Garden の 3 scene を新規 authoring、
    Zazen 石灯籠は γ に延期
  - Axis 4 (boundary sync): BoundaryLayer 手 hardcode 再同期、WebSocket
    `WorldLayoutMsg` envelope は D6 通り γ に延期
  - Axis 5 (tests): Unit test (seeded RNG) + `bias.fired` trace log、
    slow probabilistic e2e は γ に延期
- **実装結果**: 5 commit (refactor + bias + 3 scenes + boundary/camera sync +
  code-review fixup for RNG persistence)、branch `feat/m7-slice-beta-differentiation`
- **変更範囲**:
  - Python: `world/zones.py`, `cognition/cycle.py` + new test_zone_bias.py
    (6 ケース)
  - Godot: 3 new .tscn (Study/Agora/Garden) + WorldManager.ZONE_MAP +
    BoundaryLayer.zone_rects/prop_coords + CameraRig.max_distance/zoom_steps
  - Tests: test_zones.py / test_physics.py / test_affordance_events.py を
    ZONE_CENTERS/ZONE_PROPS 派生に書き換え (座標 literal 解消)
- **γ へ送った負債**: WorldLayoutMsg envelope、Zazen 石灯籠、slow stochastic
  e2e、Chashitsu.tscn の pre-existing 座標 drift (scene root が Python center
  に一致しない既存問題)

## D9. Slice β live acceptance — 5/6 PASS, production default `ERRE_ZONE_BIAS_P=0.1`

- **経緯**: 2026-04-25、G-GEAR 上で 4-in-1 acceptance bundle (β + #87/#88/#89) を実行。
  詳細: `.steering/20260425-m7-beta-live-acceptance/observation.md` + `baseline.md`。
- **結果**:
  - β zone-residency 6 項目: **5 PASS / 1 FAIL** (Run 2 Rikyū 40%、small-sample
    n=4-5 ticks の noise と判断)
  - β visual 3 項目 (5 rect / 3 building / 100m terrain): **deferred** to MacBook
    Godot session (G-GEAR 側 display なし)
- **採用**: production default を `ERRE_ZONE_BIAS_P=0.1` とする。
  - **根拠**: Run 1 (0.1) は 3 persona 全 PASS、Run 2 (0.2) は Rikyū が
    threshold を割った。さらに Run 1 は dialog turn=12 / bias_event=1 だったのに
    Run 2 は dialog turn=4 / bias_event=0 と、bias_p を上げると却って dialog
    co-location が薄くなる傾向 (n=2 では確定できないが暗示はある)。
  - **コード変更なし**: env-var で渡す現状を維持。formal hotfix PR は n>=3 で
    再実証してから判断 (γ 着手と並行で良い)。
- **γ へ送った負債**:
  - β.4-β.6 (Godot 視覚 3 項目) は MacBook 側のスクショ撮影待ち、観察結果は
    behavioural pass/fail と独立
  - bias_p ↔ dialog co-location の関係: 80s では n が小さすぎて判定不能、
    M8 で 120-180s run が回せるようになったら再評価
