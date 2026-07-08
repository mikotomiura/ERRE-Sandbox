# Codex TASK-POST review 依頼 — M13 B 反復 frozen-context bank 実コード実装

あなたは read-only の independent reviewer（`.codex/agents/erre-reviewer.toml` の観点）。以下の統合 diff を
repo を実読してレビューし、**HIGH / MEDIUM / LOW + 良かった点** で報告せよ。実装変更は不要（read-only）。日本語で。

## 対象範囲
- branch `feat/m13-b-bank`、統合 diff = `git diff ec3979f..HEAD`（29 ファイル +5311 行、**全て新規 = organ 改変
  ゼロ**）。`git diff --stat ec3979f..HEAD` で全体像を確認できる。
- 実装 = FROZEN ADR `.steering/20260707-m13-b-impl-design/design-final.md` §I0-§I11 の忠実履行
  （**この契約を実読して基準にせよ**）。設計は凍結済で再設計対象でない。契約逸脱/穴/over-read の検出が主眼。

## 変更の意図（要約）
M13 arc の SECONDARY entropy lever「反復 frozen-context bank」の apparatus を construction 実装した。
enriched substrate（競合 destination Z_comp に構造同型な cue）から live 器官が canonical builder で 1 pass
render した凍結 prompt を、chat() へ M 回投入（bake-out）して 1-sample を M-sample marginal に変換する装置。
**construction であって measurement でない**（H/MDE/divergence/floor/landscape/verdict/CI を一切計算しない、
R-budget 未消費、holding 不可侵、mock-only ゆえ real Ollama 非起動）。

## 主要ファイル（実読対象）
- `src/erre_sandbox/integration/embodied/bank_fixtures.py` — competing-cue fixture（Z_comp 対称 cue、canonical
  inputs のみ model_validate 編集）+ provenance pass（1 full-cycle pass で凍結 prompt 生成、`ERRE_ZONE_BIAS_P=0`
  pin）+ mirror memory を store pre-load して canonical `format_memories` 経由で凍結 prompt に render。
- `src/erre_sandbox/integration/embodied/bank.py` — bake-out M-loop（凍結 prompt 直 chat、readout = pre-bias
  `parse_llm_plan(raw).destination_zone`）+ `BankLlmCallRecord`（bank 専用 8-field 閉集合、`EclDecisionRecord`
  非流用）+ `BankRecordReplayClient`（record-M、mc-index、全順序 tie-break）+ zone bias try/finally pin。
- `src/erre_sandbox/integration/embodied/bank_power.py` — a-priori categorical 5-way multinomial power
  （MC-calibrated null ゆえ scipy 不要、assumed dist のみ、bank data 非依存）。
- `scripts/ecl_bank_capture.py` — mock construction 検証 run + annotation side-file writer（raw row のみ）+
  golden bake（6桁量子化）。
- `tests/test_integration/_bank_spend_guard.py` — spend AST guard（Codex HIGH-4 拡張: math.log/Counter/
  set-over-zones/groupby/numpy/pandas/scipy/statistics 禁止 + import-allowlist + call cap + no-adaptive-topup）。
- `tests/test_integration/test_ecl_bank_*.py`（6 ファイル、82 test）。
- docs: `experiments/20260708-m13-b-bank/{power_worksheet.md, t3_materiality_desk_audit.md, env.md}`。

## 重点レビュー観点
1. **契約忠実性（§I1-§I7）**: 各条項が実コードで忠実履行されているか。特に §I1 lever（zone-pick-visible cue、
   memory-geometry 破棄）/ §I3 凍結 schema / §I5 BankLlmCallRecord + determinism / §I7 T3 materiality。
2. **construction≠measurement 境界の機械保証（§I4）**: spend ast-guard に集計を隠せる穴はないか。精密
   set-over-zones 判定（zone 集計のみ ban、prompt-set は許容）は過不足ないか。annotation は本当に opaque か。
3. **Codex 前回 review（事実誤認 HIGH）の反映の正しさ**: HIGH-1（zone bias off + pre-bias readout が
   `_bias_target_zone` の post-LLM 交絡を実際に殺しているか）/ HIGH-2（BankLlmCallRecord が EclDecisionRecord と
   真に分離）/ HIGH-3（T3 materiality criterion 4 の honest teeth）/ HIGH-4（spend 暗黙集計穴の封鎖）。
4. **determinism**: record→replay byte 一致、全順序 tie-break、N=1 byte 不変（organ 無改変）。
5. **honest deviation の妥当性（tune-to-narrative でないか）**:
   - (a) I6-G3: ADR 字面「provenance retrieve-count=1×K」に対し、実 organ は 2 call-site
     （`cycle._retrieve_safely` + `embodiment.resolve_destination`）× 2 condition = 4/context ゆえ、実装は
     「per-context 固定・非ゼロ・K に厳密比例」として test 化した。この解釈は §I5 意図（M-loop の構造ゼロと対比
     される非ゼロ channel）を満たすか、それとも問題か。
   - (b) I5-G6: cross-platform byte 一致を本機（WSL1 + repo 未同期）で empirical 実測できず。golden に libm 由来
     幾何 float 非在（sampling 3 float は固定定数、zone は categorical）ゆえ risk≈0 の analytical 論拠で
     defer した（`env.md`）。この closure は妥当か、それとも empirical 実測を merge 前に要求すべきか。
6. **architecture-rules**: GPL / クラウド API 非依存、レイヤー依存方向、`evidence`/`spdm`/`runningness` 非 import。
7. 通常観点: correctness / missing tests / エラーハンドリング。

## 報告フォーマット
- **HIGH**（最終 merge 前に必ず反映）/ **MEDIUM**（採否を記録）/ **LOW**（defer 可）/ **良かった点**。
- 各指摘に `file:line` or 契約条項番号 + 具体的な失敗シナリオ。
- construction≠measurement 逸脱・契約穴・organ 改変の混入は最優先（HIGH）。
- 前回 review（design-final §I11、事実誤認 HIGH 2 含む）の反映が正しいかを特に厳しく見よ。
