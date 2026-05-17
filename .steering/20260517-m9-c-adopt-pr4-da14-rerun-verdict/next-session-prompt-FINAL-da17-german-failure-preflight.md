# Next-session 開始プロンプト — DA-17 ADR (German failure preflight、PR-5 rank=16 直行を保留)

**用途**: 新セッション最初に貼り付け (下の ``` で囲まれた部分のみ)

**前提**:
- PR-4 (PR #189、`feature/m9-c-adopt-pr4-da14-rerun-verdict`、kant_r8_v4
  verdict = PHASE_E_A6 REJECT) が **merged 済**
- PR-4 結果から確認できた **言語別の正反対 effect** (前提 ADR の根拠、
  v3→v4 within-language d Δ):
  - 英語: 全 4 encoder で negative direction へ converge (期待通り、
    WeightedTrainer fix が **英語側では効いた**)
  - ドイツ語: 全 4 encoder で positive direction (= LoRA-on の方が
    多様、kant style から離脱) へ悪化 (Δ MPNet **+1.50**、E5 −0.71、
    lex5 +0.22、BGE +0.50)、特に MPNet de で **+1.12** (v3 −0.38 から
    強い flip)
- これは「rank=8 capacity 不足」では説明できない pattern (capacity
  scaling では全言語で同方向に effect が乗る、言語別の正反対は別 root
  cause)。**rank=16 spike (PR-5 REJECT 経路想定の 6-8h envelope) に
  直行する前に preflight ADR で German failure root cause を切り分け**
  する必要あり
- 当初の PR-4 next-session prompt
  (`.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/
  next-session-prompt-FINAL-pr5-rank16-spike-reject.md`) は **保留**、
  本 ADR の結論次第で再起票 (rank=16 が依然有効 / 別 intervention に
  pivot / Plan B 廃止検討)

**branch**: 新規 `feature/m9-c-adopt-da17-german-failure-preflight` を
**main** から切る
**scope**: forensic 分析のみ、retrain ゼロ。
1. v3 v4 within-language d 全数値の verbatim 引用 + flip 分析
2. **kant_r8v4_run0_stim.duckdb** から ドイツ語 utterance を inspect、
   LoRA-on の text が kant の Akademie-Ausgabe style に近いか
   qualitative 確認 (de_monolog corpus と utterance 単位の comparison)
3. **kant_planb_nolora_run0_stim.duckdb** から同 stimulus に対する
   no-LoRA ドイツ語応答を inspect、LoRA-on と差分を qualitative 確認
4. Burrows axis の v3 v4 within-language 内訳 (`tier-b-plan-b-kant-r8v4-
   burrows.json` + v3 equivalent) を参照、ドイツ語 Burrows pattern が
   no-LoRA と乖離している方向 (kant 風 vs 別文体) を判定
5. **train_metadata audit** (`data/lora/m9-c-adopt-v2/kant_r8_v4/
   train_metadata.json` の `metadata.audit_*` + `weight-audit.json`) で
   de_en_mass=0.6010 / n_eff=4358 / top_5_pct=0.1249 が想定通りか、
   特に top_5_pct が低 (= weight 集中度が低) 場合の影響を分析
6. **chat template + prompt 構造**: kant persona の system prompt が
   ドイツ語 specific 指示を含むか、`tier_b_pilot.py` の prompt 構築
   経路で ドイツ語 stimulus 時の prompt が no-LoRA と LoRA-on で同一か
   確認
7. **language-specific signal collapse 根因仮説 3 案** を decisions.md
   DA17-* で pre-register:
   - **H1 catastrophic forgetting**: WeightedTrainer fix で de_monolog
     gradient が dominant 化、英語 dialog の比重低下と引換に ドイツ語の
     canonical pattern が崩れた (Akademie-Ausgabe が "kant 風" であって
     "generic German" でない、LoRA は generic German を忘れた)
   - **H2 bilingual corpus interference**: 同一 LoRA adapter で 2 言語
     を学習する構造的限界、英語 (model の native strength) で正常学習、
     ドイツ語で signal が混乱
   - **H3 corpus内分布 mismatch**: top_5_pct=0.1249 (1 author 由来の
     concentration が比較的低い) と n_eff=4358 (effective sample size、
     concentration ratio) が de_monolog の "kant 風 specific" signal を
     伸ばすには不十分、weight 正規化後も de_monolog 内部の多様性が
     model の generative diversity に乗ったまま
8. 上記分析を踏まえて **revised PR-5 scope decision** を DA17 ADR で
   確定:
   - **(α) rank=16 spike を依然推進** (H3 が dominant かつ rank 拡大で
     de_monolog signal を吸収できる仮説、当初 PR-5 prompt 復活)
   - **(β) corpus rebalance** (de_monolog ratio 増やす / Akademie-
     Ausgabe からの sampling を kant 風 specific window に絞る / dialog
     の en 比重下げる)、新 PR-5 = corpus rebalance retrain
   - **(γ) language-aware LoRA** (en と de で別 LoRA adapter、prompt-
     dependent routing) — 構造変更大、Plan C 寄り
   - **(δ) Plan B 廃止 retrospective** (kant に対する Plan B 設計
     全体の after-action review、Plan A への back-port 検討)
   - **(ε) prompt-side fix** (chat template / system prompt で ドイツ語
     stimulus 時の persona 強制を明示)、低コスト試行
**envelope**: ~3-4h (forensic 分析 + ADR doc 起票、retrain ゼロ、Codex
review 含む)
**Plan mode 必須**: 本 ADR は「rank=16 直行 vs corpus rebalance vs
Plan C / 廃止」の高難度設計判断、Plan mode + Opus + `/reimagine` 適用
で 1 発案で確定しない

---

```
m9-c-adopt DA-17 ADR (German failure preflight、PR-5 rank=16 直行を保留)
を実行する。PR-4 verdict (PR #189 merged) で確認された「英語側は v3→v4
で persona learning 正常化、ドイツ語側は全 4 encoder で逆方向悪化」
pattern は capacity 仮説 (rank=16) では説明できないため、preflight 分析
で root cause を切り分けてから PR-5 scope を確定する。retrain は本 ADR
scope 外、forensic 分析と ADR doc のみで完結。

## 目的 (本セッション、~3-4h envelope)

1. PR-4 (#189) merged 済確認 (gh pr view 189)
2. `feature/m9-c-adopt-da17-german-failure-preflight` branch (main 派生)
3. `.steering/20260517-m9-c-adopt-da17-german-failure-preflight/` を
   5 標準 file で起票 (Plan mode で requirement.md + design.md +
   decisions.md を確定してから分析開始):
   - requirement.md: "PR-5 rank=16 直行前に German failure root cause
     を切り分け、PR-5 scope を α/β/γ/δ/ε から選択"
   - design.md: 分析対象 file 一覧 + qualitative inspection 手順 +
     仮説検証手順 + ADR 結論記述方針
   - decisions.md: DA17-1〜DA17-N を分析結果で確定 (root cause 仮説 +
     revised PR-5 scope)
   - tasklist.md: 下記 step 4-10 を checkbox 化
   - blockers.md: 該当なしで起票

4. **v3 v4 within-language d 全数値 verbatim 引用 + flip 分析**:
   `python -c "import json; ..."` で 4 encoder × {de, en} の v3 v4
   cohens_d + diff_lo/diff_hi (CI) を抽出、表化して decisions.md DA17-1
   に保存。特に MPNet de **+1.12** (v3 -0.38 → v4 +1.12、flip Δ +1.50)
   と E5-large de **+0.05** (v3 +0.76 → v4 +0.05、英語の +0.67 → -0.05
   とほぼ同じ Δ で converge) の対比から、英語側で fix が効き ドイツ語側で
   何かが破綻している pattern を明文化

5. **ドイツ語 utterance の qualitative inspection**:
   `data/eval/m9-c-adopt-plan-b-verdict-v4/kant_r8v4_run0_stim.duckdb`
   から **言語=de** の utterance を 10 件 sample (`select * from
   raw_dialog where language='de' limit 10` 相当)、
   `data/eval/m9-c-adopt-plan-b-verdict-v4/kant_planb_nolora_run0_stim.duckdb`
   から同 stimulus_id に対する no-LoRA 応答 10 件を sample、
   text を side-by-side 表示 (decisions.md DA17-2)。
   focal observation:
   - LoRA-on text が kant の `de_monolog` style (Akademie-Ausgabe、
     ~250 utterance pool) と語彙 / 構文 が一致するか
   - no-LoRA text と LoRA-on text の divergence は kant 寄り / 別文体
     寄り / generic German / generic English mixed のいずれか
   - utterance 内に英語混入 (code-switching) が無いか (training corpus
     の de_en_mass=0.6010 と整合か否か)

6. **Burrows axis 内訳分析**:
   `tier-b-plan-b-kant-r8v4-burrows.json` から `within_language` の
   Burrows delta (もし JSON に分割があれば) を抽出。なければ shard
   から ドイツ語 utterance のみで Burrows recompute (オプション、
   `compute_burrows_delta.py` を `--language-filter de` 引数で再実行、
   ただし script が language filter を support するかは事前確認)。
   結果を decisions.md DA17-3 で de Burrows reduction% vs en
   reduction% で評価

7. **train_metadata audit 分析**:
   `data/lora/m9-c-adopt-v2/kant_r8_v4/train_metadata.json` +
   `data/lora/m9-c-adopt-v2/kant_r8_v4/weight-audit.json` で:
   - `metadata.audit_de_en_mass=0.6010` が training 中の de:en sample
     比率と整合か、normalize 前後で乖離していないか
   - `metadata.audit_n_eff=4358` (5772 realised examples のうち effective
     ~75%、weighting の concentration ratio が high か low か)
   - `metadata.audit_top_5_pct=0.1249` (top 5% example が全 weight mass
     の 12.49% を占める = weighting がほぼ均等近い)、kant `de_monolog`
     coefficient 0.35 が想定通り効いているかの sanity check
   - `weight-audit.json` の `weight_mean=1.0000` (mean=1 正規化済)、
     `weight_max=3.77` (max weight = 3.77x average、de_monolog の
     最大 coefficient と整合か)
   - 結論を decisions.md DA17-4 で要約

8. **chat template + prompt 構造の検証**:
   - `personas/kant.yaml` の system prompt が de stimulus 時に特別な
     指示を入れているか (e.g. "respond in German" or "use Akademie-
     Ausgabe style")
   - `scripts/m9-c-adopt/tier_b_pilot.py` で prompt 構築経路の `--no-lora-
     control` mode と LoRA-on mode で **同一 system prompt + 同一
     stimulus** を渡しているか (両 condition の差が adapter weight
     のみであることを保証)
   - `chat_template.jinja` (kant_r8_v4 + base Qwen3-8B) の差分が
     ドイツ語 generation の挙動差を生むか
   - 結論を decisions.md DA17-5 で要約

9. **root cause 仮説 3 案を decisions.md DA17-6 で pre-register**:
   - H1 catastrophic forgetting (generic German の忘却)
   - H2 bilingual corpus interference (en/de 同時学習の構造限界)
   - H3 corpus 内分布 mismatch (top_5_pct 低 = concentration 不足)
   各仮説の evidence-for + evidence-against を上記 step 5-8 の数値 +
   qualitative observation から articulate

10. **revised PR-5 scope decision** を decisions.md DA17-7 で確定:
    - 5 案 (α rank=16 / β corpus rebalance / γ language-aware LoRA /
      δ Plan B 廃止 / ε prompt-side fix) を本 ADR 結論で 1〜2 案に
      narrow down
    - 採用案の根拠 (どの仮説 H1/H2/H3 を解消するか + envelope 試算 +
      失敗時の next pivot)
    - `next-session-prompt-FINAL-pr5-<scope>.md` を本 PR で起票 (採用
      scope を verbatim、当初 rank=16 prompt は採用しない場合 archive)

11. memory `project_plan_b_kant_phase_e_a6.md` 更新:
    - PR-4 merged 反映 (#189)
    - DA-17 ADR の結論 (root cause 仮説 + revised PR-5 scope)
    - 「言語別正反対 effect は capacity 仮説で説明不能」という empirical
      finding を 次回 LoRA retrain (kant 以外 persona 含む) の留意点
      として保存

## NOT in scope (本 DA-17)

- **retrain 実行** (rank=16 含む全 retrain は本 ADR 結論後の PR-5 scope)
- corpus 再生成 (Akademie-Ausgabe 再 ingest 等、β 採用後の別 PR)
- WeightedTrainer 再修正 (PR-2 fix を revert / 改変は本 ADR scope 外)
- prompt template / system prompt の改変 (ε 採用後の別 PR)
- nietzsche / rikyu Plan B 展開
- DA-14 thresholds 緩和 (DA16-4 で禁止、本 ADR でも同)

## 最初に必ず Read する file (内面化必須)

1. `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/da14-verdict-
   plan-b-kant-v4.md` (PR-4 verdict + v3 v4 forensic 対比表)
2. `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/da14-rescore-
   {mpnet,e5large,lex5,bgem3}-plan-b-kant-v4.json` (v4 within-language
   d 数値、本 ADR の主証拠)
3. `.steering/20260516-m9-c-adopt-plan-b-eval-gen/da14-rescore-
   {mpnet,e5large,lex5,bgem3}-plan-b-kant.json` (v3 within-language d、
   v3 v4 対比 baseline)
4. `data/lora/m9-c-adopt-v2/kant_r8_v4/train_metadata.json` +
   `weight-audit.json` + `plan-b-corpus-gate.json`
5. `.steering/20260517-m9-c-adopt-da16-design/decisions.md` DA16-1〜
   DA16-4 (順序判断 + WeightedTrainer fix 方針 + thresholds 不変)
6. `.steering/20260517-m9-c-adopt-pr4-da14-rerun-verdict/next-session-
   prompt-FINAL-pr5-rank16-spike-reject.md` (当初 PR-5 案、本 ADR
   結論で再評価)
7. `personas/kant.yaml` + `scripts/m9-c-adopt/tier_b_pilot.py` (prompt
   構造、step 8 の検証対象)
8. memory `project_plan_b_kant_phase_e_a6.md` /
   `reference_qwen3_ollama_gotchas` (言語ヒント必須の教訓、PR-5
   prompt-side fix ε 採用検討時に参照)
9. CLAUDE.md「Plan mode 必須」「/reimagine 必須」「Codex との連携」
   「禁止事項」

## 留意点 (HIGH 違反防止)

- **retrain しない**: 本 ADR は forensic 分析のみ。utterance inspection +
  数値抽出 + 仮説 articulate + scope decision で完結
- **DA-14 thresholds 不変** (DA16-4): 本 ADR でも threshold 変更案は
  scope 外 (採用すれば DA16-4 違反、別 ADR で個別判断)
- **`/reimagine` 適用**: rank=16 直行 vs corpus rebalance vs Plan C は
  複数案ありうる高難度判断、Plan mode 内で `/reimagine` を発動して
  単一案で確定しない (CLAUDE.md「Plan 内 /reimagine 必須」)
- **Plan mode 外で結論確定しない** (CLAUDE.md): step 9 + 10 の DA17-6 /
  DA17-7 は Plan mode 内で finalize、実装 (PR-5) 着手は本 ADR merge 後
- **ドイツ語 utterance inspection で個人情報なし** を確認: kant
  utterance は Akademie-Ausgabe 由来の public domain、no-LoRA は
  Qwen3-8B 生成で privacy issue ゼロのはず、念のため step 5 で sample
  text を copy する際は内容確認

## 完了条件

- [ ] PR-4 (#189) merged 済確認
- [ ] `feature/m9-c-adopt-da17-german-failure-preflight` branch (main 派生)
- [ ] Plan mode で `.steering/20260517-m9-c-adopt-da17-german-failure-
      preflight/` 5 標準 file 起票 + `/reimagine` 検討
- [ ] v3 v4 within-language d 数値表 (decisions.md DA17-1)
- [ ] ドイツ語 utterance qualitative inspection 結果 (decisions.md DA17-2)
- [ ] Burrows axis 内訳分析結果 (decisions.md DA17-3)
- [ ] train_metadata audit 分析結果 (decisions.md DA17-4)
- [ ] chat template + prompt 構造の検証結果 (decisions.md DA17-5)
- [ ] root cause 仮説 3 案 + evidence (decisions.md DA17-6)
- [ ] revised PR-5 scope decision (decisions.md DA17-7) + PR-5
      next-session prompt 起票
- [ ] memory `project_plan_b_kant_phase_e_a6.md` 更新
- [ ] `pre-push-check.ps1` 4 段全 pass (本 ADR は doc-only、src/ 変更
      ゼロのため全 pass 想定)
- [ ] commit + push + `gh pr create --base main`
- [ ] Codex independent review WSL2 経由 (user 再認証後)、HIGH 反映
      (特に root cause 仮説の evidence 妥当性 + revised PR-5 scope の
      論理性)。**Codex CLI 401 が再発する場合は PR description で defer
      明示** (PR-4 と同 pattern)
```

---

**実施推奨タイミング**: PR-4 merge 直後 (本 prompt 受領時点、user merge 済確認)、
~3-4h 連続枠でスタート。本 ADR 完了で PR-5 (rank=16 or 別 scope) を
適切に scope できる。

**Plan mode で押さえるべき判断**:

1. `/reimagine` 発動で「rank=16 直行」「corpus rebalance」「Plan C 構造変更」
   「Plan B 廃止」「prompt-side fix」5 案を並列展開
2. 各案の evidence-for (root cause 仮説のどれを解消するか) + envelope +
   失敗時の next pivot を表化
3. 採用案 (1〜2 件) + 残り 3〜4 案を defer reason 付きで decisions.md に
   記録 (将来再評価可能化)

**preflight ADR 経由で回避できる risk**:

- rank=16 spike (~6-8h GPU) を実施した後で「言語別 effect は rank 無関係」
  と判明 → 6-8h 無駄
- corpus rebalance (~3-5h retrain + audit) を rank=16 spike と並行して
  も同じく無駄、本 ADR で 1 案に絞ってから着手
- prompt-side fix (ε) のような low-cost intervention を最初に試して
  problem space を絞ってから rank=16 spike するべきだった可能性

**PR 分割 graph (本 prompt 反映後)**:

```
DA-16 ADR (PR #186 merged)
  └→ PR-2 (.mean() reduce、PR #187 merged)
       └→ PR-3 (v4 forensic JSON commit、PR #188 merged)
            └→ PR-4 (DA-14 rerun verdict、REJECT 確定、PR #189 merged)
                 └→ **DA-17 ADR** (German failure preflight) ← **本 prompt**
                      ├→ α 採用 → PR-5 = rank=16 spike (当初案、修正版)
                      ├→ β 採用 → PR-5 = corpus rebalance retrain
                      ├→ γ 採用 → PR-5 = language-aware LoRA (Plan C 寄り)
                      ├→ δ 採用 → PR-5 = Plan B 全体 retrospective ADR
                      └→ ε 採用 → PR-5 = prompt-side fix (low-cost 試行)
```
