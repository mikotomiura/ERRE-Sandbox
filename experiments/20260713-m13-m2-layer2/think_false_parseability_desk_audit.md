# think=False parseability desk-audit — M2 Layer2 SimToM self-other segment

> 対象: M2 Layer2（ミラー・シム）の SimToM prompt segment（`build_self_other_context` /
> `_render_self_other` / `_SELF_OTHER_FRAMING`、`src/erre_sandbox/integration/embodied/society.py`）。
> 位置づけ: **construction desk-audit（doc-only）**。NOT a structural-floor verdict; verdict は holding。
> R-budget=0（measurement 非再入）。§L7/§L11（code phase の前件）+ 文献
> `docs/literature/20260707-affect-appraisal-utility-integration.md` §9-ii。

## 1. リスク（文献 §9-ii）

qwen3:8b は本 repo で **think=False 必須**（`reference_qwen3_ollama_gotchas`）。think=False は
reasoning trace を抑止するため低エントロピー decode になりやすく、複雑・自由記述的な prompt segment を
与えると **SimToM の内的状態シミュレーション指示が縮退**（無視・定型反復・parse 不能な出力）する risk が
文献 §9-ii に記録されている。self-other segment がこの縮退を招けば、observer の行動が他者観察に依存する
という causal wiring が prompt-level で成立しなくなる。

## 2. 設計上の緩和（bounded / imperative / structured、functional analog）

`_render_self_other` の segment は縮退 risk を構造的に抑えるよう設計している:

- **bounded**: observed 他者数は N体 society の実在他者数に限られ、各行に `zone=` / `moved_toward=` /
  `said="…"` / `was_near_you` の **key=value 構造**のみを載せる（自由記述の増殖なし）。utterance は
  Layer1 dialog の <=80 字制約を継承。
- **imperative / 単一命令**: framing は「各他者の内的状態を simulate し自己の次行動に反映せよ」の 1 命令。
  think=False の低エントロピー decode でも解釈分岐が少ない。
- **structured list**: `- <agent_id>: <k=v, …>` の決定的 render。parse 対象は既存の
  `RESPONSE_SCHEMA_HINT`（JSON 応答契約）であり、self-other segment は **入力 context** に載るのみで
  応答 schema を増やさない（world_model block と同型、USER 側 additive）。
- **functional analog 語彙のみ**（規律 b）: 「mirror neuron / neural mechanism / ミラーニューロン実装 /
  神経機構再現」を使わず、"functional analog of taking their perspective, not a claim about their true
  mind" と明示。誇大主張を prompt 文面レベルで排除。

## 3. honest 見送り path（縮退した場合、bounded close）

Layer2 は **bounded construction attempt**（scoping §2.3.1、GATING は Layer1）。もし実 qwen3 shakedown で
think=False により SimToM segment が縮退し continuity gate（causal wiring）が prompt-level で clean に
建たない場合:

- それは **construction finding**（M2 を invalidate しない、measurement verdict でもない）。
- **honest 見送り**: Layer2 を bounded close し、**Layer1 が既に valid milestone**（PR #72）である事実を
  正典とする。scoping / 契約を「Layer2 を成立させるため」に tune しない（§L1 binding）。
- 縮退は over-read で substrate 否定へ昇格させない（firing⇔detectability 混同禁止、5 機序分離継承）。

## 4. 現時点の判断（sign-off）

- gating CI は **replay/mock only**（exact-oracle routing mock、`test_self_other_wiring_continuity_*`）で
  causal wiring を boolean 検証する。ここでは think=False の実 decode 縮退は評価対象外（mock は context
  presence で決定的に route する）。
- 実 qwen3 での think=False parseability は **非 gating な manual shakedown** の観察事項（R-budget=0、
  powered run なし）。本 desk-audit は「縮退 risk を認識し、bounded / imperative / structured / functional
  analog 語彙で緩和し、縮退時は honest 見送り」という construction 判断を **事前に記録**するもの。
- この desk-audit の存在自体は `test_self_other_think_false_desk_audit_present` が presence-grep で担保する
  （quality 判定はしない = 縮退の有無判断は human 観察に委ねる）。

---
NOT a structural-floor verdict; verdict は holding。本 doc は measurement を authorize しない（R-budget=0）。
