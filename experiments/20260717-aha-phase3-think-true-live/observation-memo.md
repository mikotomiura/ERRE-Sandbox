# observation-memo — aha Phase 3 think=True 存在確認（**非 verdict human memo**）

> **これは記述的観察であって verdict / scorer / floor / aha 判定ではない**（design-final §Guard、§(b) 原則4/5）。
> 二相の「存在有無」を離散判定しない。以下は封印実走 trace を人手で読んだ記述的所見。
> 実走 = real qwen3:8b、Ollama 0.32.0、kant・N=32 think=True、num_predict=2048（construction spend、
> `artifacts/manifest.json` + `think_traces.jsonl`）。

## A. §(b) technical verification（door 条件③ の enabler が動くか）— 記述的事実

- **think=True は qwen3:8b（Ollama 0.32.0）で動作する**。32/32 の応答で reasoning trace が取得できた。
- **trace 経路 = `message.thinking` field**（32/32 が `thinking_source="field"`）。Ollama 0.32.0 は think を
  `<think>...</think>` 埋め込みでなく **独立 field** で返す（modern path）。§(b)(b) が問うた「parseable か」は
  **機械的に parseable（32/32）** = 抽出できた。
- **truncation なし**（`finish_reason` 全 `stop`、`finish_length=0`）。num_predict=2048 は十分だった。
- thinking 長は 921〜2374 字（median 1313）= **非空の reasoning trace が取得された**（char count は技術事実で
  あり reasoning の実質性を保証しない、Codex TASK-POST LOW-2）。
- → **二相捕捉 regime（apparatus）は real qwen3 の think=True trace を additive に capture でき、trace は
  観察に足る**。これは door 条件③ を判断する **材料**（apparatus + trace の可観測性）であって、③ の成立断定でも
  aha の測定でもない。

## B. 生成相↔評価相 二相構造の**記述的観察**（非 verdict）

trace を読むと、多くの窓で「**候補の生成 → その候補の評価/再考**」という往復が **記述的に見て取れる**。
断定でなく、読み手の記述として:

- **trace #0**（例）: 生成「maybe he should stay here」「the forage step might relate to some task」→
  評価「**But** the forage step might be a distraction. **However**, the intensity is 0.40, which isn't very
  high.」→ 決定「focus on the forage step」。= 提案してから反対材料で weigh している往復が読める。
- 評価相は多く **soft な評価的接続**（"But …", "However …", "maybe X but Y"）で現れ、これは 32 trace に
  **広く分布**（記述的印象）。

**over-read guard**: 上を「二相が *起きた*」と boolean/score で断定しない。「生成→評価の往復が記述的に
*読み取れる* 窓が多い」という観察に留める。これが aha（洞察のジャンプ）である、とは **主張しない**
（deliberation 的な weighing であって insight の跳ねの証拠ではない。Yang [24] epoch-0 反例の教訓を継承）。

## C. 再考マーカーの**出現有無 + 例示**（§(b) 原則4 (ii)、記述統計に限る・非 aha proxy）

- apparatus の **狭い lexical inventory**（"wait"/"actually"/"hmm"/… `RECONSIDERATION_MARKERS`）で excerpt が
  出た trace = **7/32**（indices 3,6,7,8,20,24,31）。**これは閾値/合否/aha proxy でなく、narrow な語彙 inventory の
  出現有無に過ぎない**（apparatus manifest は marker count を emit しない = Codex H4）。
- 例示 excerpt:
  - #3: 「… maybe he's on his way back to study after the walk. **Wait**, the last memory is the transition
    from study to peripatos. …」
  - #7: 「… so maybe he's moving back to study? **Wait**, the current location is peripatos, and the next
    intent mig… 」
  - #8: 「… maybe he's moving on to the next step. **Wait**, the forage steps might be part of a task. …」
- **記述的補足**: 上記 explicit marker（7/32）は soft な評価的接続（"But"/"However"、B 節）より **狭い**。
  「7/32」を二相の頻度・強度の **measure として扱わない**（narrow lexical subset の出現有無）。

## D. door 条件③ の位置づけ（honest）

- **③（`<think>` 二相捕捉 enabler）の判断材料が得られた**（Codex TASK-POST MEDIUM-1、over-read hygiene で
  「建った/成立」を避ける）: think=True trace は capture 可能・parseable で、生成↔評価の往復が記述的に読める
  substrate 素材が実データで得られた。これは door 条件③ を判断する **材料**であって、③ の成立を断定する verdict
  ではない。
- ただし **これは「観察に足る素材が得られた」までで、aha の測定ではない**。二相を「起きた/起きない」で離散化
  したり scorer 化したりは **していない**（over-read guard）。
- **② 壁2（非循環 trace-scorer）は UNMET のまま不変**。二相を aha proxy に離散化すれば C-proper 第2リンク
  circularity の aha 版が再来する。**door は開けない**（door-open は user 裁定）。
- **construction-only fallback も満たす**: 仮に二相的な素材が読めなくても「読めなかった」こと自体が Phase 2
  反証条件(1) の入力だった。本実走では二相的に **読める素材が得られた**（記述的に）= Phase 2 反証条件(1) に
  抵触する所見ではない（gate 判定でなく所見）。

## E. まとめ（非 verdict）

think=True 稼働検証は **技術的に動作**（think=True 動作・trace parseable 32/32・truncation なし）、かつ
生成↔評価の二相構造は real qwen3 の embodied cognition prompt 上で **記述的に読み取れた**。これは door 条件③
（二相捕捉 enabler）を判断する **材料**であって、③ の成立断定でも aha の測定でも door を開ける判断でもない。
② UNMET・holding・R-budget=0・measurement-line CLOSE は不変。次工程・merge・door は **user 裁定**。
