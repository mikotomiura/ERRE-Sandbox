# Retrospective: 20260712-m13-m4-society-enrichment

## Task
M13 建設 pivot の可視化 substrate（M4）enrichment。ECL v0 live-capture(N=1) を society scope に 1:1 mirror し、
N=3 agent（kant/nietzsche/rikyu、初期 zone=study/peripatos/chashitsu）society run を real qwen3:8b sealed
capture（record-mode, think=False, seed=0, horizon=12）で封印記録 → 新 golden `tests/fixtures/m4_society_live_golden/`
+ Godot viewer 可視化 + headless placement byte-parity 検証。**construction であって measurement でない**
（verdict/floor/scorer/divergence 非 emit、R-budget=0、measurement line CLOSE 済で非再入）。

実行方式: Opus オーケストレータは実装コードを書かず、I1-I3 を分離 context の Sonnet subagent が実装（各 attempt を
test-runner→loop-watchdog で客観 gate）。I4=sealed capture（human-run）。I5=cross-platform closure。

## Issues Completed
- **I1** society_live.py harness（fcd2b24）+ **determinism 修正**（0f8684f）: `_SEALED_WALL_CLOCK` で wall_clock 決定論 pin。
- **I2** m4_society_live_capture.py --capture/--verify + R3 decoder（e461733）。
- **I3** SocietyReplayScene Avatar2 + replay test parametrize [m2,m4]（44c7fd5）+ m4 有効化（c3ffb4b）。
- **I4** sealed real-qwen3:8b golden（9d37ae6）: honest single rendered-zone 報告。
- **I5** cross-platform closure（AC5-G1 WSL parity + AC5-G2 pre-push 4段）。
- **判断3（superseding ADR）** event_log_checksum の envelope_provenance 量子化（dd9e01b）+ cross-review 反映（90421df）。

## Deferred
- fidelity Wave 2（CC0 humanoid/HDRI、要 network DL 承認）。
- M2 Layer2 mirror-sim ADR。
- real embedding 導入（memory_centroid collapse 解消、rendered multi-zone を genuine に出す）＝別 ADR。
- code-reviewer LOW-2（fingerprint tick-0 のみ）/ LOW-3（manifest_version renderer 共有）。

## What Worked
- **ECL track determinism 保証の無償転移**: byte-parity / inner_invocations==0 / manifest 再render witness を society に 1:1 mirror。
- **test-runner→loop-watchdog の二段 gate**: 各 issue の done 自己申告を exit code で客観化。I1 の wall_clock 欠陥を I2 中に検出できたのはこの gate 由来。
- **empirical 診断の徹底**: BLOCKER-2（event_log_checksum drift）を per-category → field-level diff で完全 localize（`envelope_provenance` の cognitive float last-ULP drift）。修正方向（量子化 b7dfac40 / 除外 74bf4432）を society.py 未改変の read-only probe で cross-platform 実証してから ADR 化。
- **honest outcome の受容**: real qwen3:8b が 5 distinct destination_zone を genuine に author（R1 反証）したが rendered zone は memory_centroid resolver で単一 peripatos に collapse。over-read せず honest single rendered-zone を first-class pass として land。
- **既存 helper の再利用**: 判断3 の fix は `handoff._quantize_embedded_json`（rendered decisions で proven）を再利用 → serializer 一致で M2 regression 回避。

## What Failed
- **I1 の wall_clock 非決定欠陥**: 固定 constructor が `default_factory=_utc_now` を pin せず fingerprint 非決定。Windows clock 粒度で AC1-G6 が偶然 pass、Linux/WSL/I4 で破綻する latent bug。I2 worker が script 側 workaround で回避 → orchestrator が source 修正（0f8684f）に是正、workaround 除去。
- **event_log_checksum cross-platform drift（BLOCKER-2）**: `_decision_projection` が envelope_provenance を生 model_dump_json で載せ full-precision cognitive float が last-ULP drift。M2 Layer1 の latent gap（static state ゆえ露見せず）を M4 live run が初検出。frozen society.py 改変ゆえ Stop→superseding ADR→user 裁定（A）→Codex→実装。

## Repeated Failure Patterns
- **決定性 witness に非決定フィールド（wall_clock / cognitive dynamics float）が混入**: `feedback_golden_crossplatform_float_drift` の系譜。6桁量子化が効くのは「emitted float を量子化してから hash」する経路のみ。生 model_dump_json 埋め込み文字列は量子化を素通りする → 「every float quantised」invariant を projection 境界で機械 test 化（M-d）する必要。
- **worker の workaround が divergent second-source-of-truth を作る**: I2 の fingerprint workaround。source 修正が正道。orchestrator gate で捕捉。

## Docs Updates
- `docs/research-positioning.md` §8 に M4 society enrichment landed を追記（予定）。
- memory 新規 `project_m4_society_enrichment`（親 project_m13_m4_code、measurement 非再入継承）。

## Skill・Command Updates
- なし（既存 Loop 資産で完走）。cross-review skill の Codex sandbox が file 読取不能（MCP error / powershell 起動失敗）→ 内部整合 review に degrade したが指摘は有効。既知の degrade 経路として許容。

## Next Loop
- memory `project_m4_society_enrichment` 記録 + docs §8 追記。
- 次工程候補: real embedding で rendered multi-zone を genuine に出す ADR（memory_centroid collapse 解消）/ M2 Layer2 mirror-sim / fidelity Wave 2。
