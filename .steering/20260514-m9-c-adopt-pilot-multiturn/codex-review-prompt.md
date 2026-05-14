# Codex independent review prompt — m9-c-adopt pilot multi-turn investigation

## あなたへの依頼

ERRE-Sandbox プロジェクト m9-c-adopt phase B の **DA-12 verdict = DEFER** を受けた
**multi-turn pilot investigation** PR の **設計内容** を independent review する。
特に **methodology confound vs LoRA failure の identifiability** を本当に
empirical に切り分けられるかを critical に審査する。

主な目標: pilot を multi-turn 採取に拡張して direction failure の主因が (a)
pilot single-turn vs baseline multi-turn の方法論 confound なのか、(b) LoRA が
IPIP self-report neutral midpoint を実質 shift しないのか、を切り分ける。

## 報告フォーマット

- **HIGH** (実装前に必ず反映): identifiability を本当に解消できない / direction
  failure が再現/反転しない empirical risk、protocol parity 欠陥、test 設計の
  根本欠陥など
- **MEDIUM** (採否を `decisions.md` に記録): 設計判断の代替案、追加 metric、
  scenario criteria の robust 化
- **LOW** (defer 可、`blockers.md` 持ち越し): nice-to-have、wording、明文化

## 必須参照ファイル

1. `.steering/20260514-m9-c-adopt-pilot-multiturn/requirement.md` (本 PR scope)
2. `.steering/20260514-m9-c-adopt-pilot-multiturn/design.md` (実装計画 + 5 設計判断)
3. `.steering/20260513-m9-c-adopt/decisions.md` DA-1 (4 軸 intersection) + DA-9
   (retrain v2 path) + DA-11 (Phase B scope narrowing) + **DA-12** (Phase B
   verdict = DEFER + direction failure hot decision)
4. `.steering/20260513-m9-c-adopt/phase-b-report.md` (Phase B 完遂報告 + 実測 matrix)
5. `.steering/20260513-m9-c-adopt/da1-matrix-kant.json` (PR #165 baseline matrix)
6. `.steering/20260513-m9-c-adopt/blockers.md` U-6 (methodology confound)
7. `scripts/m9-c-adopt/tier_b_pilot.py` (拡張対象、現在 single-turn のみ)
8. `src/erre_sandbox/cli/eval_run_golden.py` `_make_stimulus_inference_fn` (line 439-498) +
   `_build_stimulus_system_prompt` (line 337-359) + `_build_stimulus_user_prompt` (line 362-386)
9. `src/erre_sandbox/evidence/golden_baseline.py` `GoldenBaselineDriver.run_stimulus()`
   (line 351-432) — baseline alternating speaker + same inference_fn protocol

## 重点審査項目 (HIGH 候補)

### 1. Identifiability 本当に切り分けられるか?

本 PR は **multi-turn pilot で direction が baseline と align**
(LoRA-on Vendi < baseline) すれば **methodology confound が主因** と認定する。
しかし以下の混在可能性:
- LoRA が methodology に conditional な effect を持つ (= multi-turn では機能、
  single-turn では機能しない)
- multi-turn 採取自体が新 confound を入れる (e.g. SGLang での coherence loss)
- baseline 5 shard (M9-eval P3 stimulus) 自体が本当に "multi-turn dialog" と
  呼べる構造か (turn=N marker のみ index 変動、prior_turns 削除なので
  各 turn は essentially i.i.d. 描画)

**質問**: direction の "align" が観察された場合、それを methodology confound
dominant と本当に呼べるか? シナリオ I (A 優位) の operational criterion は
robust か?

### 2. baseline の "same inference_fn for both speakers" 設計の意味

baseline driver は focal/interlocutor 両 speaker を **focal persona の system
prompt + 同じ stimulus user prompt (turn=N marker のみ index 変動、prior_turns
削除)** で生成。つまり baseline の "multi-turn" は本当の対話ではなく **kant
persona の i.i.d. monologue の連続**。

multi-turn pilot を **完全に同じ protocol** で再現する選択は妥当か? 代替:
- (A) baseline と同 protocol (本案、apples-to-apples)
- (B) interlocutor を独立 (no-op stimulus repeat、stage direction-like)
- (C) interlocutor を no-LoRA Ollama (multi-backend、混在)

A 案は apples-to-apples だが、もし baseline の multi-turn が **意図とは違って
de facto i.i.d. 多重描画** ならば、multi-turn pilot との比較で direction が
変わる原因が "並列 i.i.d. 描画の windowing effect" だけになる可能性がある。

**質問**: A 案で直接 protocol parity を取った場合、Vendi diversity / Burrows
distance は windowing artifact だけで direction 変化を見せる可能性がある。
これを fundamental identifiability 限界と認定すべきか、それとも別 protocol
(B / C) を試すべきか?

### 3. prior_turns を渡さない選択は妥当か?

baseline は `del persona_id, prior_turns` で context を完全に捨てる。multi-turn
pilot も同じく prior_turns を渡さない設計。しかしこれは **"本来の multi-turn
dialog 効果" を測れない** ことを意味する。

methodology confound の正体が "並列 i.i.d. 描画 → windowing diversity
inflation" だけなら、本 PR は実質 "ICC consumer 経由 protocol を multi-turn
samples で再走らせるだけ" になる。それで本当に LoRA effect の真の direction を
empirical に切り分けられるか?

**質問**: prior_turns を渡す変種 (本来の multi-turn dialog) を追加すべきか?
それとも本 PR scope では (apples-to-apples) を優先し、prior_turns inclusion は
Phase E A-6 で別途検討すべきか?

### 4. シナリオ判定の criteria robust 性

requirement.md と design.md にシナリオ I/II/III/IV を記載。

| シナリオ | criterion | 結論 |
|---|---|---|
| I (A 優位) | direction が逆転 (LoRA-on Vendi < baseline) | methodology dominant |
| II (B 優位) | direction 変わらず | LoRA failure dominant |
| III (両者) | direction 改善するが thresholds 未達 | 両因子寄与 |
| IV (新情報なし) | 採取 fail / CI 広すぎる | identifiability 不能 |

**質問**:
- "direction が逆転" の operational threshold は? Cohen's d < 0 で足りるか、
  CI lower bound < 0 を要求するか?
- "direction 改善するが thresholds 未達" の境界は? 改善幅で測るか、両者 mix の
  Bayesian model を立てるか?
- 全 3 rank で direction 一致しない場合 (mixed: 4 reverses but 8/16 stays) は
  どのシナリオ?

### 5. focal turn budget の数え方

baseline driver は per-stimulus `ceil(expected_turn_count / 2)` を focal speaker
が話す turn 数として stratified_slice。pilot 側も同じ計算を採用。kant 70 stim の
focal turn 合計 = 88 (10*1 + 42*1 + 18*2 = 70? いや、42*1 が間違い)。

実際: 1-turn × 10 = 5 focal、2-turn × 42 = 42 focal、3-turn × 18 = 36 focal、
合計 ~83 focal/battery。300 focal/run target = `target_per_cycle = 50` で
stratified slice。

**質問**: multi-turn 採取時の **total turn 数 (focal + interlocutor)** はどう
なるか? 300 focal + ~250 interlocutor = ~550 turn/shard × 6 shard = ~3300 turn
total。compute budget 見積もり (~1h G-GEAR SGLang) は現実的か?

### 6. SGLang adapter routing で interlocutor turn が "kant LoRA" を通る意味

multi-turn pilot 内では interlocutor turn も SGLang `model=kant_r{rank}_real` で
生成。これは "interlocutor が kant LoRA-on で speaking する" 意味になる
(baseline は no-LoRA Ollama)。direction 比較 (pilot multi-turn vs baseline) で
**interlocutor turn が LoRA を embeddings に通している**ことが direction を
追加で歪める可能性。

**質問**: Vendi/Burrows 計算で `speaker_persona_id = 'kant'` filter は focal turn
のみ抽出するため、interlocutor turn が LoRA で生成されること自体は metric には
直接影響しない。しかし shard 内に interlocutor turn が混在することで shard
全体の "context coherence" が変わる可能性は? (Vendi/Burrows は per-utterance で
function-word distribution を見るため、prior context 依存は限定的)

### 7. 既存 consumer の re-usability

`compute_baseline_vendi.py` / `compute_big5_icc.py` / `compute_burrows_delta.py` を
PR #165 と同じ呼び出しで multi-turn shard に対して走らせる計画。これら consumer は
`WHERE speaker_persona_id = ?` filter で focal turn のみ抽出する設計か?

**質問**: consumer 側で interlocutor turn を見ない filter が確実に発火することを
明示的に確認したか? もし全 turn を window に入れていたら、interlocutor の混在で
Vendi/Burrows が drastically 変わる artifact が出る。

## 追加検討事項

- multi-turn pilot 採取 ~1h 完遂後、もし採取 fail (SGLang OOM / network / adapter
  unload) が起きた場合の rescue policy
- 既存 single-turn pilot との **paired diff** (同 stimulus、turn_index 0 のみ
  vs turn_index 0..N-1) を計算して direction 変化の per-stimulus 寄与を見る
  optional analysis を入れるべきか
- ICC(A,1) も diagnostic として併報告 (MEDIUM-4 既定) し、persona-fit の
  multi-turn 効果も見るべきか

## 環境注意

- WSL2 → Windows-native Ollama 不通: ICC consumer は Windows native venv から
  走らせる必要 (PR #165 で確認、本 PR でも継承)
- SGLang VRAM ~10.5-11 GB peak (3 adapter pin)
- T=0.7 + per-call seed mutation (PR #165 で baseline ICC artefact、本 PR は
  再利用、multi-turn pilot ICC は同 T=0.7 で算出)
- main 直 push 禁止 / 50% 超セッション継続禁止

## 出力

各 HIGH/MEDIUM/LOW について:
- どの設計判断/箇所が問題か (file:line or section 参照)
- なぜ問題か (引用や勘案根拠)
- 提案する mitigation
- ADOPT / MODIFY / REJECT の verdict
