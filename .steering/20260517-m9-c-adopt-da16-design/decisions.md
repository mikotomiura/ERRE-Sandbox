# 重要な設計判断 — DA-16 ADR (kant Plan B PHASE_E_A6 順序判断)

> 本 file は本 ADR セッション固有の設計判断を記録する。横断 ADR は
> `.steering/20260513-m9-c-adopt/decisions.md`、verdict 結果は
> `.steering/20260516-m9-c-adopt-plan-b-eval-gen/decisions.md` DR-1、
> WeightedTrainer 修正歴は `.steering/20260518-m9-c-adopt-plan-b-retrain/
> decisions.md` DR-5 / DR-6、ブロッカー記録は同 blockers.md ブロッカー 2 を
> 参照。

## DA16-1: 順序判断 — **候補 A** (WeightedTrainer fix → kant_r8_v4 retrain 先行)

- **判断日時**: 2026-05-17
- **背景**: PR #184 の `da14-verdict-plan-b-kant.json` で kant Plan B
  retrain (kant_r8_v3、rank=8) が REJECT、`PHASE_E_A6` 移行が確定
  (decisions.md DR-1)。根因仮説は 2 つ:
  1. **WeightedTrainer Blocker 2** (sample weight collapse、batch=1 で
     weight が数学的に相殺)
  2. **rank=8 capacity 不足** (Burrows/style 信号は de_monolog に集中、
     rank=8 では LoRA capacity 不十分)
  両仮説を切り分けるには次の retrain で どちらの変数を動かすか順序を
  決める必要がある。
- **選択肢**:
  - **A**: rank=8 のまま **WeightedTrainer Blocker 2 修正 → kant_r8_v4
    retrain → DA-14 rerun verdict** (低コスト ~50 行 diff、clean A/B、
    weight 効果のみを v3 と比較)
  - **B**: **rank=16 spike を先行** (capacity expansion 優先、weight 効果
    と交絡 — 結果が改善しても rank なのか weight なのか切り分け不能)
  - **C**: 両方同時 (rank=16 + WeightedTrainer fix、retrain 1 回で済む
    が root cause 切り分け不能、NOT recommended)
- **採用**: **A**
- **理由**:
  1. **根因仮説の優先順位**: Blocker 2 は "仮説" ではなく retrain
     blockers.md ブロッカー 2 + DR-5 調査で確認された **構造的バグ**
     (verbatim 引用):
     > 「`compute_weighted_causal_lm_loss` は
     > `(per_example_loss * weights).sum() / torch.clamp(weights.sum(),
     > min=1e-8)` で reduce する。`per_device_train_batch_size=1` で
     > micro-batch を作ると `per_example_loss` shape は `(1,)`、
     > `weights` shape も `(1,)` で、`(per_example_loss[0] * w) / w =
     > per_example_loss[0]` と weight が数学的に相殺される。」
     >
     > 「DA-14 weighting (`compute_example_weight`、coefficient
     > 0.35/0.20/0.15/0.30、normalise to mean=1) は採用したが、実
     > training 上は unweighted average と等価に振る舞っていた可能性。
     > DA-14 verdict REJECT の原因の一つが「weighting が効いていない」
     > だった可能性も否定できない。」

     known bug を未修正のまま他変数 (rank) を動かすのは因果切り分けの
     基本原則に反する。
  2. **direction disagreement は capacity 仮説より weighting 仮説に整合**:
     `da14-verdict-plan-b-kant.md` の per-encoder natural d:
     > MPNet: −0.5264 (negative direction, but std_pass=False due to CI)
     > E5-large: **+0.4781** (opposite sign — retrain shifted Vendi
     >          semantic ↑, not ↓)
     > lexical_5gram: +0.1805 (opposite sign)
     > BGE-M3 (exploratory): +0.3317

     capacity scaling (rank=16) は通常 "学習している方向" を **強める**
     だけで sign を encoder ごとに flip させない。direction
     disagreement は "training signal 自体が intended な persona style
     に集約していない" の症状で、weighting が効いていなければ corpus
     mode (de_monolog vs dialog vs aphorism vs quote) が **すべて等価**
     に学習され、encoder ごとに異なる mode へ感応する → 逆方向のシフトが
     並立する説明として自然。
  3. **コスト非対称性**: 候補 A は ~50 行 diff + ~3h retrain (DI-7 envelope
     と同条件)、追加 SGLang config 不要 (rank=8 のまま)。候補 B は同 retrain
     envelope + rank=16 で LoRA parameter 2 倍 → VRAM peak 増、SGLang launch
     invocation の `--max-total-tokens` 再検証が必要 (DR-4 fp8 構成下で
     rank=16 が乗るか未検証)。
  4. **情報価値**: A の outcome 4 パターンすべて解釈可能 — (i) ADOPT
     → Blocker 2 が dominant、weighting 修正で完了。(ii) REJECT, direction
     converged but |d| 不足 → capacity 仮説、PR-5 rank=16 を推進。(iii)
     REJECT, direction disagreement 残存 → corpus/encoder mismatch の
     深掘り (Plan C 候補)。(iv) REJECT, eval_loss 上昇 → fix 自体に
     regression、PR-2 を revert。B 単独は (i)-(iv) のどの仮説にも
     decisive evidence を与えない (weight が無効化されたまま rank だけ
     動くため)。
  5. **PR 分割の自然性**: A 採用なら本 ADR (doc-only) → PR-2 (fix 実装、
     ~50 行 + 新規 regression test) → PR-3 (retrain、~3h GPU) → PR-4
     (verdict 計算、PR #184 pipeline 再利用) → PR-5 (rank=16、PR-4
     REJECT 時のみ) と Plan-Execute 分離が綺麗。B/C 採用なら本 ADR
     段階で rank=16 + WeightedTrainer 両方の影響評価が必要で envelope 拡大。

- **トレードオフ**:
  - A は **連続 PR が増える** (PR-2/3/4 必須、PR-5 は条件付き)。GPU 占有
    + Codex review × 4 = ~12h overhead。B 採用なら PR 1 本で完結する
    可能性もあるが、その代償が「結果解釈不能」では本末転倒。
  - A の結果が ADOPT でも、rank=16 で更に gate margin を稼げる可能性を
    捨てる。ただし Plan B の目的は "ADOPT 確定" であり over-engineering
    の必要なし。
  - nietzsche / rikyu の Plan B 展開は最短で **PR-4 ADOPT 後** まで
    blocked (推定 +1〜2 週間)。ただし B 採用でも結果解釈に
    debug 1 round 入るので実時間差はほぼなし。
- **影響範囲**:
  - 本 PR は doc-only、後続 PR-2 で `src/erre_sandbox/training/
    weighting.py:411` + `train_kant_lora.py:1690-1715` を修正
  - PR-3 で kant_r8_v4 adapter 生成、PR-4 で `data/eval/m9-c-adopt-plan-
    b-verdict-v4/` shards + `da14-verdict-plan-b-kant-v4.json` を生成
  - nietzsche / rikyu Plan B 展開を PR-4 ADOPT まで保留
- **見直しタイミング**:
  - PR-4 verdict REJECT で direction disagreement が残った場合、
    本 DA16-1 を再評価 (rank=16 spike → corpus 分析 → Plan C 候補へ展開)
  - WeightedTrainer fix 実装で予期せぬ regression が出た場合 (eval_loss
    が initial を上回る 等)、本 DA16-1 の前提が崩れるので PR-2 を revert
    して再判断

## DA16-2: WeightedTrainer fix 実装方針 — **候補 (a)-refined** (`.mean()` reduce、`weights.sum()` 正規化を廃止)

- **判断日時**: 2026-05-17
- **背景**: DA16-1 で候補 A 採用に伴い、WeightedTrainer Blocker 2 の
  修正方針を本 ADR で確定する (retrain blockers.md ブロッカー 2 の暫定
  対応案 (a)/(b)/(c) のいずれを採るか、続 PR-2 で迷わないように事前確定)。
  Blocker 2 暫定対応案 (verbatim):
  > 候補 (a): `compute_loss` 内で `per_example_loss[0] * weights[0]` を
  >   返す (`weights.sum()` での割り戻しを止め、batch=1 でも weight が
  >   勾配 magnitude に直接乗る形)。ただしこれは batch>=2 のセマンティクス
  >   変更を伴うため別途検討
  > 候補 (b): `gradient_accumulation_steps` スコープで micro-batch の
  >   weight を合算してから正規化 (HF Trainer の callback hook で実装)
  > 候補 (c): `per_device_train_batch_size>=2` の VRAM-friendly な構成
  >   を探索 (Qwen3-8B + NF4 + rank=8 で batch=2 が乗るか要 spike、現状
  >   DI-7 では VRAM 98% でほぼ無理)
- **選択肢**:
  - **(a)-refined**: `compute_weighted_causal_lm_loss` の最終 reduce 式を
    `(per_example_loss * weights).mean()` に変更 (現行
    `.sum() / weights.sum()` 廃止)。batch=1 でも weight が直接 loss
    magnitude → gradient に乗る。batch≥2 では unweighted ではなく
    weighted-mean (`mean = sum/N`、N=batch_size で正規化) のセマン
    ティクスに変更される。weights が mean=1 正規化済 (`compute_example_
    weight` で保証) なら期待値は元の式と一致 (大数では同じ scale)
  - **(b)**: HF Trainer callback hook で grad_accum スコープの weight 合算
    + 正規化を実装 (`on_pre_optimizer_step` 等で全 micro-batch の weight
    sum を集約してから 1 回 backward)。Trainer 内部の loop に介入する
    ため diff 大、HF API 仕様変更耐性 ↓
  - **(c)**: VRAM 構成探索で batch>=2 化 (NF4 量子化を更に強化、または
    seq_len 短縮)。DR-5 PR で既に batch=1 確定 (DI-7 VRAM 98%)、再 spike
    は本 PR scope 外で時間コスト大
- **採用**: **(a)-refined**
- **理由**:
  1. **batch=1 + grad_accum 経路で weight が gradient に乗る最小 diff**:
     HF Trainer は各 micro-batch 独立に `loss.backward()` を呼び、
     accumulated gradient を grad_accum steps 後に optimizer.step() で
     消費する。`.mean()` reduce なら batch=1 の `loss = l[0] * w[0]` が
     そのまま勾配の magnitude に乗り、grad_accum スコープで自動的に
     weight-aware な gradient 平均が形成される。
  2. **batch≥2 セマンティクスは "weights が mean=1 正規化済" 前提では
     ほぼ不変**: 元の式 `sum(l*w)/sum(w)` も `weights.mean() ≈ 1` なら
     近似的に `mean(l*w)` に近い (差は分散項のみ)。`compute_example_
     weight` が pool 全体で mean=1 正規化を保証しているため、batch≥2 の
     local mean も 1 周辺。意味論変更の実害は微小。
  3. **既存 test (`test_weighted_trainer.py`) の更新範囲が局所的**:
     2 件の数式 assert は `expected = (per_example_loss * weights).sum()
     / weights.sum()` で計算しているので、`(per_example_loss * weights).
     mean()` に書き換えるだけで pass する (batch=2 で `sum/2 = mean`
     なので既存 fixture 数値は同じ scale)。新規 test (gradient-response-
     to-weights, batch=1) を 1 件追加して bug を回帰検出する。
  4. **(b) は Trainer 内部 loop に介入** → HF 4.57.6 → 4.58 で API
     破壊変更があれば追従 cost、本プロジェクトの "extras-only dep" 方針
     (memory `feedback_pre_push_ci_parity.md` 言及) と相反
  5. **(c) は DI-7 spike を再実施するコストが本 ADR envelope を逸脱**、
     かつ NF4 強化は accuracy regression 懸念
- **トレードオフ**:
  - **意味論変更の説明責任**: docstring + decisions.md で
    "`.mean()` reduce は batch=1 + grad_accum で weight を gradient に
    伝えるための明示的選択であり、`compute_example_weight` の mean=1
    正規化に依存する" と明記する必要あり。Codex review HIGH-2 指摘:
    "既存 test fixture (`weights=[3.0, 1.0]`、`_build_logits_targeting`
    で全 example 同一 margin=2.0) は per-example loss が両 example
    identical で weight 検出力ゼロ → expected 式書き換えに加えて
    "per-example loss が異なる fixture" の新規 test を 1 件追加する。
  - **train_loss scale の変化**: 既存 v3 retrain の train_loss と v4
    retrain の train_loss は **直接比較不可** (新式 `(l*w).mean()` で
    weight が gradient に乗るぶん scale が変動)。v4 train_loss
    trajectory は v4 内部での収束確認に限定し、v3 absolute value との
    対比は避ける。**学習軌道の意味論も変わる** (weighted vs unweighted
    gradient による convergence path 差) ため、step pace や best step
    位置の v3 v4 直接比較も避ける。
  - **eval_loss は比較可能** (Codex review HIGH-1 指摘で修正): eval
    examples は `sample_weight=1.0` (`train_kant_lora.py:761-765`、
    eval batch=1 (`per_device_eval_batch_size=1`、DR-6) のため
    旧式 `(l[0]*1.0)/1.0 = l[0]` と新式 `(l[0]*1.0).mean() = l[0]` が
    数値一致する。v3 eval_loss (`0.18259`) と v4 eval_loss は標準 CE
    として直接比較可能。EarlyStoppingCallback の `eval_loss` 経路 +
    `train_metadata.json` 記録 + dashboards 比較に副作用なし。
- **影響範囲**:
  - `src/erre_sandbox/training/weighting.py:411-462` (`compute_weighted_
    causal_lm_loss` の最終行 + docstring)
  - `tests/test_training/test_weighted_trainer.py` (既存 2 件の expected
    式書き換え + 新規 gradient-response test 1 件追加)
  - `src/erre_sandbox/training/train_kant_lora.py:1690-1715`
    (WeightedTrainer.compute_loss は無変更、内部関数の数式変更のみ)
  - retrain script (`scripts/m9-c-adopt/train_plan_b_kant.sh` 等) の
    invocation は無変更、新 adapter 名は `kant_r8_v4`
- **見直しタイミング**:
  - PR-2 implementation で gradient-response regression test が pass
    しない場合、(a)-refined の数式自体を再検討 (`.sum() / batch_size`
    形にして元式との backward compat を取る選択肢が残る)
  - PR-3 retrain で eval_loss が initial 上昇 (regression) する場合、
    (a)-refined の意味論変更が training stability を壊した可能性 → 再
    Plan mode で (a)-refined / (b) / (c) の choice を再評価

## DA16-3: 続 PR scope 分割 — **PR-2 (fix) → PR-3 (retrain) → PR-4 (verdict) → PR-5 (rank=16, 条件付き)**

- **判断日時**: 2026-05-17
- **背景**: DA16-1 で候補 A 採用、DA16-2 で WeightedTrainer fix 方針確定。
  本 ADR は doc-only なので、後続実装を 1 PR で束ねるか分割するかを
  確定する必要がある。Plan-Execute 分離原則 (CLAUDE.md "Plan mode 外で
  設計判断を確定しない") と review cost、blast radius を考慮した最適分割
  を採用する。
- **選択肢**:
  - **A**: PR-2 (fix + retrain + verdict + rank=16 を 1 PR で完結)
    — review cost ↓、blast radius ↑↑、Codex review が巨大 PR に対して
    HIGH 検出能力 ↓
  - **B**: PR-2 (fix) → PR-3 (retrain + verdict) → PR-4 (rank=16)
    の 3 分割 — retrain と verdict を 1 PR で束ねる
  - **C**: PR-2 (fix) → PR-3 (retrain) → PR-4 (verdict) → PR-5 (rank=16)
    の 4 分割 — 各 PR の責務が単一、review + Codex review が manageable
- **採用**: **C**
- **理由**:
  1. **PR-2 (fix) は コード変更のみ**で local PASS 可能 (gradient-response
     test が batch=1 で pass する)。GPU 不要、review は code-reviewer +
     Codex で fully local 完結
  2. **PR-3 (retrain) は GPU 占有 (~3h)** + adapter artifact 生成、
     verdict 計算 (~30 min) と性質が異なる。retrain 中に session 中断する
     ケースが多いため (DI-7, DR-7 で経験済)、retrain 完了点を明示的に
     PR 境界にする方が状態管理が安全
  3. **PR-4 (verdict) は再現性が肝**: `rescore_vendi_alt_kernel.py` +
     `aggregate_plan_b_axes.py` の invocation を PR-3 adapter に対して
     固定し、forensic JSON + verdict.md を生成 → ADOPT/REJECT 判定を
     明示的な PR 境界にする。これにより PR-5 (rank=16) を起動するか
     どうかの **明示的判断点** が PR-4 merge で確定する
  4. **PR-5 (rank=16) は条件付き**: PR-4 ADOPT なら不要 (Skill `start-
     task` で開始時に判断)。事前に PR を切らないことで scope creep
     防止
  5. **Codex review 効率**: PR ごとに ~30 行〜~300 行 diff に収まり、
     Codex HIGH-C verbatim level の精査が現実的
- **トレードオフ**:
  - PR overhead が増える (Codex review × 4 = ~12h、ただし retrain GPU と
    並行可能)
  - PR-3 と PR-4 を分割するため、retrain artifact が PR-3 で commit
    → PR-4 で再利用する dependency が発生。adapter binary は
    `.steering/20260516-m9-c-adopt-plan-b-eval-gen/decisions.md` DV-3
    "forensic JSON のみ git commit、binary は別" 方針に従い HuggingFace
    Hub or 別 storage に push (PR-3 で確定)
- **影響範囲**:
  - 本 ADR で PR-2 用 next-session prompt を起票 (PR-3 用は PR-2 finish-
    task で起票、PR-4 用は PR-3 finish-task で起票、PR-5 用は PR-4
    REJECT 時のみ起票)
  - main ブランチへの merge 順序: PR-2 → PR-3 → PR-4 → (PR-5 条件付き)
  - 各 PR 完走目標: PR-2 ~2h、PR-3 ~5h (retrain + commit、verdict 含まず)、
    PR-4 ~3h (eval shard 採取 + 4-encoder rescore + Burrows + verdict)、
    PR-5 ~6h (rank=16 retrain + eval shard + verdict)
- **見直しタイミング**:
  - PR-2 で gradient-response test が即 pass しない (実装に dependency
    bug が見つかる) 場合、PR-2 を spike PR に降格して再 ADR を切る
  - PR-4 verdict が ADOPT なら PR-5 を起こさず nietzsche / rikyu 展開へ
    pivot (別 ADR で確定)

## DA16-4: DA-14 thresholds は Plan B でも不変 — 本 ADR で再確認のみ (変更しない)

- **判断日時**: 2026-05-17
- **背景**: kant Plan B retrain が REJECT になった事実から、
  "thresholds が厳しすぎたのでは" という疑問が出る可能性がある (Codex
  review でも LOW 指摘の余地)。本 ADR で thresholds 不変方針を明示的に
  再確認することで、続 PR で誰かが threshold を緩めて見かけ ADOPT を
  作ることを防ぐ。
- **選択肢**:
  - A: DA-14 thresholds (Vendi natural d ≤ −0.5、Burrows reduction% ≥
    5pt + CI lower > 0、ICC ≥ 0.55、Throughput pct ≥ 70%) を Plan B
    でも不変
  - B: encoder agreement axis のみ thresholds 緩和 (3-of-4 → 2-of-4)
  - C: Vendi d gate を −0.5 → −0.3 に緩和
- **採用**: **A**
- **理由**:
  1. DA-14 thresholds は M9 c-adopt の **acceptance gate として
     pre-registered** (`.steering/20260513-m9-c-adopt/decisions.md` +
     `d2-encoder-allowlist-plan-b.json`)。threshold 移動は post-hoc
     p-hacking の典型例
  2. PR #184 prompt の留意点 verbatim:
     > 「DA-14 thresholds 不変: rank=16 spike や WeightedTrainer fix で
     > retrain 結果が borderline でも threshold 移動禁止 (Plan B でも厳守)」
  3. WeightedTrainer fix で weight が実効化された state での verdict が
     "正しい" gate 評価。fix 前の v3 verdict を threshold 緩和で
     ADOPT 化することは因果切り分けと逆行
- **トレードオフ**:
  - PR-4 verdict が borderline ADOPT-fail (例: encoder agreement 1-of-3
    primary しか pass しない) でも ADOPT 化できない → PR-5 必須
  - thresholds が厳しすぎて Plan B 全体が dead end になる可能性は残るが、
    その判断は Plan B 全体の after-action review で行うべきで、kant 個別
    の verdict で threshold 動かす根拠にならない
- **影響範囲**:
  - PR-2/3/4/5 全体で thresholds 不変、`d2-encoder-allowlist-plan-b.json`
    + `da14-verdict-plan-b-kant-v4.json` の gate 数値は v3 と同一
  - nietzsche / rikyu Plan B 展開でも同じ thresholds 適用
- **見直しタイミング**:
  - Plan B 全 persona (kant / nietzsche / rikyu) が REJECT に終わった
    after-action review で、Plan B 設計全体の再評価の一部として thresholds
    再検討 (本 ADR ではなく Plan B retrospective ADR の scope)
