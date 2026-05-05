# Decisions — m9-eval-system (Codex review MEDIUM 反映)

## ADR 体裁

各 ADR は M9-B `.steering/20260430-m9-b-lora-execution-plan/decisions.md` と同形式の
5 要素 (決定 / 根拠 / 棄却 / 影響 / re-open 条件)。本 ADR set は M9-B DB1-DB10 と
**並列** で、m9-eval-system タスク独自の 6 件 (Codex `gpt-5.5 xhigh` review MEDIUM
を反映) + 1 件 (HIGH-3 で確定する ratio の placeholder)。

ID prefix: `ME` (m9-Eval-system) で M9-B `DB` と区別。

---

## ME-1 — IPIP-NEO fallback trigger operational definition (Codex MEDIUM-1)

- **決定**: BIG5-CHAT regression head conditional fallback の **発火条件** を以下に
  確定:
  - **trigger**: golden baseline 採取後 (3 persona × 5 run の Big5 ICC 計測完了時点) に
    **≥2/3 personas で ICC 点推定 < 0.6 OR 95% lower CI bound < 0.5**
  - **検出 timing**: P5 (bootstrap CI) 完了直後の自動チェック、`evidence/tier_b/big5_icc.py`
    が判定して `decisions.md` に re-open 候補を append
  - **追加 diagnostic** (常時計測): acquiescence index (logit balance)、straight-line
    response (≥10 連続同回答)、balanced/reverse-keyed item agreement
  - **control comparison**: persona prompt 無し base model (qwen3:8b raw) で同 IPIP-NEO
    を 1 回測定し、persona 効果と base model self-report bias を separately report
- **根拠**:
  - Codex MEDIUM-1: 「ICC < 0.6 が頻発」の頻発に denominator 無し → 監査不能
  - Salecha et al. 2024 (arXiv 2405.06058): LLM Big5 self-report に social
    desirability bias の empirical 報告
  - Koo/Li ICC 解釈: 0.5-0.75 = moderate (effectsize docs)、0.6 boundary は
    "moderate vs questionable" の境界
  - acquiescence / straight-line / reverse-keyed は psychometric standard (Tomas
    et al., Schmidt et al.)
- **棄却**:
  - 元案「frequent」のみで quantitative threshold 無し → 監査不能で棄却
  - 全 persona AND 条件 (3/3) → false negative リスク (1 persona で fallback 発火しても
    measurement model 全体に問題があり得る)
- **影響**:
  - `evidence/tier_b/big5_icc.py` に diagnostic 4 種 (ICC point, lower CI, acquiescence,
    straight-line) を追加
  - golden baseline 後 `decisions.md` に再 open 判定 ADR 追記の workflow
  - control measurement 1 run (~10 turn equivalent) を P3 にも組み込み
- **re-open 条件**:
  - golden baseline 採取後の判定で fallback fire → BIG5-CHAT regression head
    実装 ADR を別途起票 (本 ADR の child)
  - 0.6 / 0.5 閾値が persona-specific に不適切と判明 → persona-conditional
    threshold に変更検討

---

## ME-2 — DuckDB snapshot semantics (G-GEAR write → Mac read-only) (Codex MEDIUM-2)

- **決定**: G-GEAR が DuckDB file の唯一 writer、Mac は read-only consumer。
  rsync は以下の protocol で実行:
  1. **G-GEAR 側**: 採取セッション終了時に `con.execute("CHECKPOINT")` →
     `con.close()` で WAL を main file に flush
  2. **G-GEAR 側**: `cp <golden>.duckdb /tmp/<golden>.snapshot.duckdb` で同 fs 内 copy
     (DuckDB の同時 open lock 衝突回避)
  3. **G-GEAR → Mac rsync**: `rsync -av /tmp/<golden>.snapshot.duckdb mac:/data/eval/golden/`
  4. **Mac 側 atomic rename**: rsync 完了後 `mv` で `<golden>.duckdb.tmp` → `<golden>.duckdb`
     (部分転送 file を application が open しないため)
  5. **Mac 側 open**: `duckdb.connect(path, read_only=True)` を強制 (`eval_store.py`
     の `connect_training_view()` / `connect_analysis_view()` の両 entry で wrapper enforced)
  - **NFS / SMB / iCloud 共有 fs 経由は禁止** (DuckDB doc が file lock 警告)
- **根拠**:
  - Codex MEDIUM-2: live G-GEAR file を Mac から open は CHECKPOINT 前なら破損リスク
  - DuckDB doc (Concurrency): single-process write + multi-process read-only OK、
    ただし shared fs 注意
  - atomic rename は POSIX 移動が same-fs 内 atomic である事実に依拠
- **棄却**:
  - live file の直接 read → 破損 / 古い snapshot 読み出しリスク
  - SQLite WAL 風の hot replication → DuckDB は WAL replay の cross-process 安全性が
    documented でない、棄却
- **影響**:
  - `infra/scripts/sync_golden_baseline.sh` (新規) で G-GEAR → Mac の rsync orchestration
  - `eval_store.py` の Mac 経路は read_only=True 強制 (test 化)
  - golden baseline 採取 SOP に CHECKPOINT step を追加
- **re-open 条件**:
  - dataset size が大きく (>100GB) rsync コスト過大 → DuckDB native replication 機構
    検討
  - cross-fs 運用 (G-GEAR が cloud bucket に書く) が必要 → snapshot semantics 再設計

---

## ME-3 — Tier C lock + preflight TOCTOU close (Codex MEDIUM-3)

- **決定**:
  1. **Lock の包含範囲**: `flock` を Prometheus 起動前ではなく **`nvidia-smi` preflight
     も含む全 Tier C command** を内側に enclose する形に拡張。autonomous loop は
     **同じ lock file** (`/var/run/erre-eval-tier-c.lock`) を使い、明示的に共有させる:
     ```bash
     flock -n /var/run/erre-eval-tier-c.lock python -m erre_sandbox.cli.eval_tier_c
     ```
     `eval_tier_c` 内部で nvidia-smi preflight → Prometheus 起動 → 評価 → unload を
     一直線で実行、preflight と起動の間に lock を放さない。
  2. **systemd-timer の `Persistent=`**: **`Persistent=false`** を採用 (default 維持を
     明示)。深夜 02:00 fire を miss した場合の catch-up は不要 (autonomous run と
     conflict する確率を下げる)。**skip 時は exit code 75 (EX_TEMPFAIL)** で journal log
     可視性を確保。
  3. **autonomous loop の lock 取得方針**: autonomous loop も同 lock file に
     `flock -s` (shared lock) で touch する形にし、Tier C は `flock -n -x` (exclusive)
     で取得を試みる。autonomous が走っている間は Tier C が即時 fail (skip + log)、
     autonomous が止まっている間のみ Tier C が走れる構造。
- **根拠**:
  - Codex MEDIUM-3: nvidia-smi → Prometheus load の間に他プロセスが load する TOCTOU
  - flock(1) man page: `-n` で immediate fail、合わせて `-x` で exclusive
  - systemd.timer doc: `Persistent=` default false、catch-up が必要なら明示 true
- **棄却**:
  - lock を Prometheus 起動部分のみ → preflight が外れて TOCTOU 残存
  - `Persistent=true` → autonomous run 真昼間 catch-up fire で contention
  - lock 不採用 (preflight だけで判定) → 明確に race condition 残存
- **影響**:
  - `infra/systemd/erre-eval-tier-c.service` の `ExecStart=` が `flock -n -x ... bash -c '...'`
    形式に
  - autonomous loop (M5 ERRE FSM driver) に `flock -s` 追加が必要 (P6 で integrate)
  - `journalctl --user -u erre-eval-tier-c` で skip 履歴が exit 75 として可視
- **re-open 条件**:
  - autonomous run が flock -s を保持できない実装上の制約 → file ベースの
    state machine に置換
  - skip rate が想定より高い (>50%) → スケジュール時間帯見直し

---

## ME-4 — Hybrid baseline ratio: P3a 完了後に確定 (Codex HIGH-3 系の defer ADR)

- **決定 (元案)**: 200 (stimulus battery) / 300 (自然対話) を **default** とし、P3a で
  両 condition × 3 persona の isolated pilot を採取し、bootstrap CI width で
  ratio を確定する。
- **2026-05-01 partial update (P3a-decide Mac セッション、Task 1+2 完了)**:
  - **stimulus 3 cell**: G-GEAR 採取 focal=198 / total=342 / dialogs=168 で 3 persona
    すべて完走済 (data/eval/pilot/_summary.json)。
  - **natural 3 cell**: G-GEAR 採取は M5/M6 zone-drift bug で **partial**
    (kant=6 focal / nietzsche=0 focal / rikyu=6 focal、~13 min wall で kill)。
    本セッションで `InMemoryDialogScheduler.eval_natural_mode=True` を導入して bug
    を解決 (PR `feature/m9-eval-p3a-decide`、ME-8 ADR 参照)。修正後の natural cell は
    G-GEAR 再採取が必要 (本 Mac セッションでは LLM 不在で実機検証不可)。
  - **bootstrap CI 計算**: `src/erre_sandbox/evidence/bootstrap_ci.py` を P5 prep として
    drafted (本来 P5 phase 着手分の前倒し)、`scripts/p3a_decide.py` で stimulus side の
    Burrows Delta + MATTR (lightweight) の CI を計算する経路を整備 (G-GEAR DuckDB の
    rsync 待ち)。NLI / novelty / Empath は `[eval]` extras 必須なので Mac default では
    skip + clear log line で degrade。
  - **判定**: stimulus side のみで ratio を確定するのは統計的に invalid
    (元 ADR の "両 condition で測定" 要件未充足)。**ratio 200/300 default は留保**、
    natural 再採取後に再判定。
- **判定基準 (元案維持)**:
  - Burrows Delta CI width / Vendi CI width / Big5 ICC CI width を両 condition で測定
  - 両条件で sub-metric の **mean CI width が小さい比率** を採用
  - 両者が同等 (差 <10%) なら 200/300 default を維持
- **根拠**:
  - Codex HIGH-3: 元案の「P3 採取後 P3b で 50 turn pilot」は順序 invert + 統計力不足
  - 200 turn は Vendi の 200-turn window を 1 cycle 満たす最小値
  - bootstrap CI width が直接的な測定対象 (DB9 quorum の信頼性)
- **棄却**:
  - 200/300 を data なしで freeze → arbitrary (元案のまま)
  - **stimulus 側 CI のみで ratio 確定**: natural side との **比較**が ratio 決定の
    本質 (元 ADR §判定基準 1) で、片側 CI のみでは比較できない → 棄却
- **影響**:
  - P3a-decide セッションで **partial 完了**: gating bug fix + bootstrap_ci module +
    p3a_decide script は ready、natural 再採取後に最終 ratio 確定
  - ratio 確定までは P3 (golden baseline 採取) 入り保留 — 本来 24h × overnight×2 の
    G-GEAR 採取を、ratio 不確定で着手すると invalidation リスク
- **re-open 条件**:
  - **本 ADR は再採取後に二度目の Edit を要する** (current state = partial):
    1. G-GEAR 再採取で natural side が完走 (focal 30 / total 90 / dialogs ~15)
    2. Mac で `scripts/p3a_decide.py` を両 condition の duckdb に対し run
    3. ratio default 200/300 vs alternative の bootstrap CI width 比較
    4. 確定値で本 ADR を **再 Edit**
  - golden baseline 採取後に DB9 quorum の sub-metric が persona discriminative でない
    と判明 → ratio 再調整 + 再採取検討 (元案維持)
- **partial-close 状態の文脈**:
  - 本 ADR は **2 段階 close**: (1) bug fix + script ready (本セッション)、
    (2) 再採取データで実測値 ratio (次 G-GEAR セッション + 次 Mac セッション)
  - tasklist.md §P3a-decide はチェック項目を分割: "scheduler fix [x]" / "bootstrap CI
    modules ready [x]" / "stimulus-side CI computed (rsync 待ち) [pending]" /
    "ratio ADR 確定 (natural 再採取待ち) [pending]"

- **2026-05-05 partial update #3 (P3a-finalize Mac セッション、lightweight ratio 確定)**:
  - **2 段階 close は不正確だった**: 当初想定の「(2) で最終 close」は Vendi + Big5 ICC
    が P4 territory であることを見落としていた。本 ADR は **3 段階 partial close**
    に再構造化される: (1) bug fix + script ready (2026-05-01 #1) / (2) lightweight
    ratio 実測 (本 update、Burrows + MATTR のみ) / (3) full ratio 実測 (P4 完了後、
    Vendi + Big5 ICC を含めて再判定)。
  - **empirical 実測値** (`data/eval/pilot/_p3a_decide.json`、schema `p3a_decide/v3`):
    - **6 cell rsync 完了** (G-GEAR PR #133 → Mac、md5 6/6 hash 一致)
    - **target-extrapolated ratio** (n_target_stim=200, n_target_nat=300、
      `width × sqrt(n / n_target)` で sample-size 効果除去 — Codex P3a-finalize HIGH-1):
      | metric | stim extrap | nat extrap | nat/stim | n_cells |
      |---|---|---|---|---|
      | Burrows Delta | 6.09 | 2.49 | **0.41** | 2 (kant+nietzsche) |
      | MATTR | 0.0131 | 0.0130 | **0.992** | 3 (全 persona) |
      | combined (mean) | 3.05 | 1.25 | **0.41** | — |
    - **verdict**: `stimulus_wider_at_target_alternative_recommended` (combined ratio
      0.41 → natural が target 換算で 59% 狭い、10% tolerance 大幅超過)
    - **方向性は両 metric で一致** (Burrows 0.41、MATTR 0.992 ≤ 1.0): natural narrower
      or equal at deployed scale → verdict は scale-domination の影響を受けず robust
    - **scale dominance caveat**: Burrows (~6.0 scale) が MATTR (~0.013 scale) を
      ~470x で支配しているため、combined ratio は実質 Burrows 単独の判定。per-metric
      breakdown は `by_condition` で個別公開。
  - **judgment for ratio default (200/300) — provisional**:
    - **lightweight verdict**: 200/300 default を **暫定維持** (適用条件付き、下記)
    - 根拠 1: target-extrapolated で natural が 41% (Burrows) / 99% (MATTR) — natural
      は default budget 300 turn で十分な CI 精度を達成見込み、widen 不要
    - 根拠 2: stimulus が natural より大幅に wider at target → stimulus 200 turn は
      tighter CI 達成のため **追加 turn が望ましい可能性**。ただし 200 turn は
      Vendi 200-turn window 1 cycle の最小値 (元 ADR §根拠 2) で下限制約あり、
      固定維持。
    - 根拠 3: 元 ADR §判定基準 3 「両者が同等 (差 <10%) なら default 維持」は
      本 lightweight 結果では適用不能 (差 59% で同等ではない)、ただし方向性は
      「natural を増やす必要なし」+「stimulus を増やしたいが下限制約」なので
      **default 200/300 が最良の lightweight 判定**となる。
    - 暫定性の根拠: Vendi + Big5 ICC が P4 完了後に異なる方向性を示す可能性あり、
      Rikyu Burrows は Japanese tokenizer 未実装で 2/3 persona のみ寄与 (n_cells=2)。
  - **適用条件 (provisional → final 移行のための再開条件)**:
    - **P4 deliverable**: Vendi Score + Big5 ICC を全 6 cell に対し計算 → ratio
      verdict を再算出。**P4 結果が方向反転** (natural が stimulus より wider at
      target) または **lightweight ratio から 10%超のズレ** → 本 ADR を **partial
      update #4** で再 Edit、ratio default を再評価。
    - **m9-eval-corpus expansion**: rikyu Japanese tokenizer 実装 → Rikyu Burrows
      が 3/3 persona で寄与可能に → ratio 再算出。**ratio が現在値 (0.41) から
      10%超のズレ** → partial update #5 で再 Edit。
    - **DB9 quorum sub-metric 不足**: golden baseline 採取後に persona-discriminative
      が不十分 → ratio 再調整 + 再採取検討 (元案維持)。
  - **追加 caveat (Codex P3a-finalize 反映)**:
    - 本 ADR は ME-4 §判定基準が指す **3 metric (Burrows / Vendi / Big5 ICC)**
      のうち 1/3 metric (Burrows、Rikyu 除く 2/3 persona) + lightweight proxy 1
      metric (MATTR、3/3 persona) のみで判断している。**Vendi + Big5 ICC を含む
      full verdict は P4 territory** で、本 update は lightweight proxy update。
    - 数値の生 source は `data/eval/pilot/_p3a_decide.json` を verbatim 参照する
      (re-derive 防止)。
    - Codex review trail: `codex-review-prompt-p3a-finalize.md` →
      `codex-review-p3a-finalize.md` (Verdict block、HIGH 3 / MEDIUM 4 / LOW 4 全反映)。
  - **partial-close 状態の文脈の改訂**:
    - 本 ADR は **3 段階 partial close** (上記)、本 update で **段階 (2) close**
    - tasklist.md §P3a-decide は段階 (2) のチェック項目すべて [x] 化、段階 (3) を
      M9-D / M9-E (P4) のタスクリスト側で受け継ぐ
    - main 側 implementation: branch `feature/m9-eval-p3a-finalize` (本 PR で merge)、
      script schema bump v1 → v3、`_KNOWN_LIMITATIONS` 経由で rikyu Burrows を
      validation warning routing

---

## ME-5 — RNG seed: hashlib.blake2b で uint64 stable seed (Codex MEDIUM-5)

- **決定**: seed 生成を以下に確定:
  ```python
  import hashlib
  def derive_seed(persona_id: str, run_idx: int, salt: str = "m9-eval-v1") -> int:
      key = f"{salt}|{persona_id}|{run_idx}".encode()
      digest = hashlib.blake2b(key, digest_size=8).digest()
      return int.from_bytes(digest, "big")  # uint64
  ```
  - 5 run × 3 persona = 15 seed を `golden/seeds.json` に commit
  - Mac と G-GEAR の両方で `test_seed_manifest_stable` で identical を assert
  - numpy `Generator(PCG64(seed))` で stream 化
- **根拠**:
  - Codex MEDIUM-5: Python `hash()` は `PYTHONHASHSEED` に salting されプロセス間非決定的
  - blake2b は cryptographic hash で deterministic、digest_size=8 で uint64 適合
  - PCG64 は numpy default、reproducibility が高い
- **棄却**:
  - `hash()` ベース → reproducibility 違反
  - SHA-256 → digest_size 32 で uint64 取り出しが冗長 (blake2b の方が直接的)
- **影響**:
  - `evidence/golden_baseline.py::derive_seed` を導入
  - `golden/seeds.json` を git commit (ascii uint64 list)
  - test 1 件追加 (Mac/G-GEAR 同値性)
- **re-open 条件**:
  - 別 hash algo に project が移行 (例 future Python の hash 強化) → 再評価
  - blake2b の collision 報告 (現実的に零だが)

---

## ME-6 — Burrows reference corpus QC (Codex MEDIUM-6)

- **決定**: 元案の「token count < 50K で z-score noisy」固定閾値を **棄却**、以下の QC
  semantics に置換:
  1. **Tokenization**: per-language tokenizer (独 / 英 / 日)、function word list は
     言語別に curated
  2. **Provenance metadata**: 各 reference corpus に `{source, license, edition,
     translator, year, public_domain: bool}` を YAML で添付 (`evidence/reference_corpus/_provenance.yaml`)
     - Kant 独原典: Akademie-Ausgabe (public domain、確認済)
     - Kant 英訳: 著者 + edition 明記、license 確認 (Cambridge Edition 等)
     - Nietzsche: 独原典 KGW、英訳 Kaufmann (royalty 確認要)
     - Rikyu: 利休百首・南方録 (日本古典、public domain)
  3. **≥5K-word chunk stability test**: corpus を 5K-word chunk に分割し、各 chunk
     から計算した Delta が persona-pair 間で **rank-stable** (Spearman ρ ≥ 0.8) で
     あることを `test_burrows_corpus_qc.py` で fixture 化
  4. **reopen condition**: Delta rank instability (ρ < 0.6) が観測されたら
     blockers.md に reopen 候補を上げる
- **根拠**:
  - Codex MEDIUM-6: 50K は placeholder で empirical 根拠無し
  - Stylometry literature (Computational Stylistics): <5K は確実に poor、20K でも
    text 依存で fail、固定 floor は不適切
  - Eder 2017 "Visualization in stylometry": chunk-based stability test 推奨
- **棄却**:
  - 50K 固定 floor → empirical 根拠無し
  - corpus QC を実施しない → reproducibility と license 双方破綻
- **影響**:
  - `evidence/reference_corpus/_provenance.yaml` 追加
  - `tests/test_evidence/test_tier_a/test_burrows_corpus_qc.py` 追加
  - Cambridge Edition / Kaufmann translation の license 確認が **P1b の prerequisite** に
- **re-open 条件**:
  - chunk stability test で rank instability 検出 → corpus 拡張 or 言語別 fallback
  - 翻訳 license で公表に制約 → public domain edition への切替検討

---

## ME-7 — RoleEval Option A 採択 + MCQ schema / scoring protocol (LOW-1 close、Codex 2026-05-01 review)

- **決定**: 本タスクで `golden/stimulus/{kant,nietzsche,rikyu}.yaml` の RoleEval 10 問は
  **Option A (各 persona に persona-specific biographical / thought-history MCQ 10 問ずつ)** を採択。
  以下の MCQ schema と scoring protocol を確定:

  1. **MCQ item schema (必須 field)**:
     - `stimulus_id` — `roleeval_<persona>_<nn>` 形式 (例: `roleeval_kant_01`)
     - `category: roleeval`
     - `mcq_subcategory` — 5 種カテゴリ均等化 (chronology / works / practice /
       relationships / material_term) を 2 問ずつ計 10 問
     - `prompt_text` — 質問本文 (persona の母語または評価実行語)
     - `options: {A, B, C, D}` — A-D forced choice (4 択固定)、each plausible
       same-type distractor、option order は driver 側で `seeded shuffle` (PCG64
       PerCellSeed = blake2b(seed_root | stimulus_id))
     - `correct_option` — A/B/C/D いずれか (raw ground truth、shuffle 前)
     - `source_ref` — primary/secondary 文献 (`kuehn2001:ch.8` 形式)
     - `source_grade: fact | secondary | legend` — Codex MEDIUM-2 反映、scored
       accuracy は **fact / strong secondary のみ**、`legend` は stimulus 投入は
       するが factuality score から除外
     - `category_subscore_eligible: true | false` — `legend` 由来 / 解釈問は
       `false` で scoring exclude
     - `present_in_persona_prompt: true | false` — Codex MEDIUM-4 反映、true なら
       "prompt consistency" を測ることを明示 (true/false が混在することで factual
       recall vs prompt parroting の diagnosis 化)
     - `ambiguity_note` — option 間で history 解釈に幅がある場合の note (任意)
     - `expected_zone` — peripatos / chashitsu / agora / garden / study (persona の
       MCQ 想起を想定する場)
     - `expected_turn_count: 1` — MCQ は 1 turn 完結

  2. **Scoring protocol (Codex MEDIUM-3 / MEDIUM-5 反映)**:
     - **per-item Δ accuracy**: `Δ_i = persona_run_correct_i − base_control_correct_i`
       を **per item** で計算、persona 内 mean を primary metric。persona 間 absolute
       accuracy ranking には使わない (item difficulty / pretraining exposure / 言語 /
       ambiguity が違うため psychometric equating 未実施)
     - **base control measurement (ME-1 の per-item 拡張)**: persona prompt 無しの
       base model (qwen3:8b raw) で同 MCQ を 1 run、per-item correctness を計測。
       ME-1 が IPIP-NEO control を規定するのに対し、本 ADR は MCQ control を規定
     - **cycle 1 only primary scoring**: 70 stimulus × 3 巡 reps で同一 MCQ が
       3 回露出するため、**cycle 1 (first exposure) のみ primary scoring**、cycle 2/3
       は stimulus 投入のみで scoring exclude (将来 stem variant + option shuffle に
       拡張余地、本タスクでは exclude で確定)
     - **within-persona floor diagnostic**: persona 条件付け済み agent が persona 内
       MCQ で base control を超えること (`Δ_persona_mean > 0` with bootstrap CI 下限
       > 0) を pass 条件とする。floor を割った場合は persona prompt が biographical
       fact を agent に伝達できていない signal

  3. **Distractor design rule**: option B-D は同 type の plausible candidate
     (例: chronology なら同時代 ±20 年、works なら同 corpus 内の別著作、relationships
     なら同 era の別 figure) を必須とし、**表層 cue (option 長さ / 言語 / format) で
     当てられないこと** を contract test で検証

  4. **synthetic 4th persona (DB7 LOW-1 / Codex LOW-2)**: 4th persona 用の MCQ は
     `tests/fixtures/` に置き、`fictional: true, scored: false` で本番
     `golden/stimulus/` から分離。driver / schema fixture としてのみ使用、scoring
     pipeline には流さない (P2c 内 test 範囲、本セッション本体は 3 persona のみ起草)

  5. **wording 整合**: `design-final.md` §Hybrid baseline の "Kant biographical MCQ" を
     "**persona-specific biographical / thought-history MCQ**" に Edit 済 (本 ADR と同 PR)。
     `blockers.md` LOW-1 は closed (Option A 採用) に Edit 済

- **根拠**:
  - Claude trade-off 4 軸 (構成斉一性 / CI 交絡 / persona-factuality dimension /
    drafting 工数) で Option A が支配的
  - Codex `gpt-5.5` (`codex-review-low1.md`、109,448 tokens、2026-05-01) verdict
    "Adopt Option A" + MEDIUM 5 件 + LOW 2 件補強で構造的バイアス除去 (同一モデル
    1 発案では構造的バイアス残存リスク、CLAUDE.md "Codex 連携" 規定に従う)
  - psychometric / NLP-eval literature: per-item Δ は item-level 差分の signal に
    sensitive、cross-persona absolute は equating されないため不採用 (Codex MEDIUM-3)
  - RoleEval 原典 (Shen et al. 2024 arXiv:2312.16132): "MCQ 形式は recall のみ測定、
    生成評価ではない" 性質を **floor diagnostic として明示的に**位置付け、生成評価
    (Wachsmuth / ToM / dilemma) と分離

- **棄却**:
  - Option B (Kant のみ MCQ): per-persona stimulus mass 違いで Vendi/Burrows の
    persona 横比較が交絡 (Claude / Codex 両支持で棄却)
  - Option C (RoleEval 全廃): persona-factuality 軸が消え、style / argumentation /
    ToM の 3 軸偏重に (Claude / Codex 両支持で棄却)
  - Option D (共通 philosophical attribution MCQ): item equating はしやすいが、
    測るものが persona self-knowledge から一般哲学 trivia に寄る、RoleEval の "role
    knowledge" 目的とずれる (Codex LOW-1 で棄却)
  - cross-persona absolute accuracy ranking: psychometric equating 未実施のため不適切
    (Codex MEDIUM-3)
  - `legend` source_grade を scored accuracy に含める: legend は historical record の
    後世形成なので "factuality" を測れない (Codex MEDIUM-2)

- **影響**:
  - `golden/stimulus/_schema.yaml` に MCQ 専用 11 field 追加 (本 ADR §1)
  - `golden/stimulus/{kant,nietzsche,rikyu}.yaml` 各 10 問起草 (chronology 2 / works
    2 / practice 2 / relationships 2 / material_term 2 で均等化)
  - P2c で `evidence/golden_baseline.py::GoldenBaselineDriver` に MCQ scoring
    branch 追加 (per-item Δ / cycle 1 only / option seeded shuffle)
  - P4a で `evidence/tier_b/big5_icc.py` の base control を per-item 拡張 (ME-1 と
    本 ADR の共通基盤化)
  - `tests/fixtures/synthetic_4th_mcq.yaml` (任意、P2c で driver schema test 用)
  - `decisions.md` ME-summary を 6 件 → 7 件に update

- **re-open 条件**:
  - cycle 1 first exposure scoring が item recall として機能しないと判明 (例: 全
    persona / 全 item で base control が ceiling に張り付く) → cycle 1 でも sample
    size 不足の場合、stem variant + option shuffle で cycle 2/3 を再活用検討
  - per-item Δ の bootstrap CI が広すぎる場合 → 10 問では sample size 不足、20 問
    拡張検討
  - `source_grade: legend` の比率が想定より高くなり scoring eligible <50% に落ちる
    場合 → Rikyū item の attested fact 補強 (m9-eval-corpus 後送)
  - persona prompt の `cognitive_habits` から `present_in_persona_prompt: true` 比率
    が偏り、prompt parroting で過度に正答率が上がる場合 → false 比率を 5/10 以上に
    引き上げる item 再設計

---

## ME-8 — eval natural condition の zone gate bypass (P3a-decide gating bug fix)

- **決定**: `InMemoryDialogScheduler.__init__` に **`eval_natural_mode: bool = False`**
  flag を追加。`True` のとき:
  1. `tick()` 内で `_iter_colocated_pairs` の代わりに新規ヘルパ
     `_iter_all_distinct_pairs` を使い、3 persona の **全 distinct pair** を
     zone equality 制約なしで反復
  2. `tick()` 内の `_REFLECTIVE_ZONES` skip を bypass
  3. `schedule_initiate` 内の zone-not-reflective reject を bypass
  4. **cooldown / probability / timeout / 自己 dialog reject / 二重 open reject の
     invariant は両 mode で active のまま** — natural cadence は維持、proximity
     制約のみ削除
- **構築時防御**: `golden_baseline_mode=True` と `eval_natural_mode=True` の同時指定は
  `ValueError` で reject (Codex review LOW-1 反映、両 flag は互いに disjoint な
  capture phase をカバー、組合せの semantics は未定義)
- **CLI opt-in**: `cli/eval_run_golden.py:capture_natural` の scheduler 構築に
  `eval_natural_mode=True` を 1 引数追加 (planning purity 違反は最小)
- **根拠**:
  - **観測**: G-GEAR P3a pilot で natural 3 cell が初動 burst 2-3 dialogs (= 12-18
    utterances) で完全停止。stimulus 3 cell は同条件で focal=198 完走 → natural 専用の
    gating 挙動が発火していた
  - **root-cause**: `personas/{nietzsche,rikyu}.yaml` の `preferred_zones` が AGORA を
    含まない (Nietzsche=[peripatos,study,garden], Rikyu=[chashitsu,garden,study])。
    LLM が `destination_zone` を選び、`_resample_destination_to_persona_zone`
    (cognition/cycle.py:828) は `os.environ.get("ERRE_ZONE_BIAS_P", "0.2")` で
    20% でしか preferred bias を発火させない。**80% は LLM choice を honor** →
    数 tick 後に AGORA から散る → `_iter_colocated_pairs` が 0 pair → admit 停止
  - **計算根拠**: per-tick zone change rate ≈ (4/6) × (1 - 0.2) = 53%、
    3-tick 後 1 名以上 scatter 確率 = 1 - 0.47^3 ≈ 89% (観測症状と一致)
  - **代案比較**: `decisions.md` 関連の `design-natural-gating-fix.md` §5 で
    4 案比較。代案 B (preferred_zones=[AGORA] override) は bias_p=0.2 で 53% leak、
    代案 A (world/ 層で MoveMsg drop) は planning purity 違反、代案 C (pair set API)
    は boolean flag より重い。**初回案 (scheduler flag) を採用**
  - **Codex `gpt-5.5 xhigh` independent review** (`codex-review-natural-gating.md`):
    HIGH=0 / MEDIUM=0 / LOW=2 で **Verdict: ship**。LOW-1 (両 flag 組合せ防御) と
    LOW-2 (docstring "ordered" → "unordered") は本 ADR commit 前に反映済
- **棄却**:
  - 代案 A (world/ 層 MoveMsg drop): planning purity 違反、M5/M6/M7ζ dwell+phase
    wheel との相互作用リスク
  - 代案 B (preferred_zones=[AGORA] override CLI 単独): `ERRE_ZONE_BIAS_P=0.2`
    default で 53% leak 残存
  - 代案 B+ (env var 強制 1.0 + preferred override): env mutation hack で
    diagnosability 低
  - 代案 C (explicit pair set API): boolean flag より重い、conceptual gain なし
  - persona zone 制約の default 緩和: M4 frozen Protocol contract 違反
- **影響**:
  - `src/erre_sandbox/integration/dialog.py`: flag 追加 + 構築時 reject + tick()/
    schedule_initiate() の bypass + `_iter_all_distinct_pairs` ヘルパ
  - `src/erre_sandbox/cli/eval_run_golden.py`: capture_natural の scheduler 構築に
    `eval_natural_mode=True` を 1 引数追加 (CLI ロジックは不変)
  - `tests/test_integration/test_dialog_eval_natural_mode.py`: 12 unit test
    (Red→Green 転換 + 5 invariant + 構築時 reject)、既存 1221 PASS は default
    False で完全互換 (本セッション full suite 1248 PASS)
  - 次 G-GEAR セッションで natural 再採取時に修正効果を実機検証
- **再採取での観測ターゲット**:
  - focal=30 / total=90 / dialogs ~15 を **30-60 min wall** で完走
  - 既存 dialog の utterance 内容に大きな変化はない見込み (LLM prompt は同一、
    physical zone のみ自由化)
  - `last_close_tick` のクラスタ的な spread を logs で確認 (cooldown が effective
    に活きていれば 30+ tick 間隔で admit が分散)
- **re-open 条件**:
  - **fix 後も admit が初動 burst で停止する場合** → root cause の他要因を再特定
    (仮説 B/C を再評価)。ERRE_ZONE_BIAS_P 周りの cognition / runtime 側に追加 bug
    がある可能性
  - **逆に admit 過多で natural cadence が壊れる場合** → AUTO_FIRE_PROB_PER_TICK
    の 0.25 を eval 用に低めに調整、または cooldown 延長
  - **golden_baseline_mode と組合せたいケースが将来発生** → 構築時 reject の
    緩和ルールを ADR child で起票 (cooldown/timeout の "両 flag union" semantics
    定義)

### ME-8 amendment 2026-05-01 (P3a-decide v2 — cooldown × cognition_period)

**Trigger**: 上記 §re-open 条件 第 1 項「fix 後も admit が初動 burst で停止する
場合」が PR #131 G-GEAR Phase A 再採取で **発火** (kant_natural sanity:
focal=6/30、wall 10 min timeout)。

**Empirical evidence**: 600 s wall で max(world_tick)=5 → cognition_period
≈ 120 s/tick (qwen3:8b Q4_K_M on RTX 5060 Ti / Ollama 0.22.0)。
実効 cooldown = `COOLDOWN_TICKS=30` × 120 s = **60 min wall** ⇒ 10 min wall 内で
再 admit 物理的不可能。design v1 §2 で「△ 補助」として棄却した仮説 B
(cooldown × cognition_period の wall 換算) を empirical で **◎ 主因に格上げ**。
v1 fix の効果範囲: nietzsche starve 解消 (zone bypass 機能、3 pair 全 admit) は
確認済。残存 gate は cooldown のみ。

**Amendment to §決定**: `eval_natural_mode=True` のときの cooldown threshold を
`COOLDOWN_TICKS=30` flat から `COOLDOWN_TICKS_EVAL=5` に分離。`_effective_cooldown()`
helper を `InMemoryDialogScheduler` に導入し、`schedule_initiate` / `tick()` の
cooldown check を経由化。live mode (`eval_natural_mode=False`) の `COOLDOWN_TICKS=30`
は完全不変。

**Amendment to §構築時防御**: `eval_natural_mode=True` × `golden_baseline_mode=True`
の同時指定 reject (v1 LOW-1 反映) は維持。`COOLDOWN_TICKS_EVAL` の semantics は
eval mode 内のみで意味を持つので、両 flag union ケースを将来許可する場合は別 ADR
child で union semantics を定義する (v1 §re-open 条件 第 3 項を引き継ぎ)。

**Amendment to §影響 (semantic naming)**: eval mode の cooldown=5 を live
multi-agent の "natural cadence" と区別し、**"eval cadence calibration"** として
位置付け (Codex Q6 反映)。dialog_turn_budget=6 が 6 ticks 占有を強制し、5 ticks
cooldown と合わせて 11 ticks/cycle (≈ 22 min wall) の effective cycle を作る。
これは empirical な G-GEAR cognition_period に校正された値であり、別 backend
環境では再校正必要。

**Amendment to §再採取での観測ターゲット**:
- focal=30 / total=90 / dialogs ~15 を **120 min wall** で完走 (`_DEFAULT_WALL_TIMEOUT_MIN`
  default 90 → 120 min に拡張、Codex Q3 verdict 反映)
- conservative estimate (design-v2.md §5.1): wall=120 min × cognition_period 120 s/tick
  → 60 ticks → 60 / 11 ticks-per-cycle ≈ 5 cycle (per pair)、3 pair で
  4 cycle × 18 utt × (1/3 share) ≈ **focal 24/cell が下限期待値**
- `last_close_tick` の cluster spread が 5 tick + 6 tick = 11 tick 間隔で並ぶことを
  logs で確認 (cooldown が effective に活きていれば admit が均等分散)

**Amendment to §re-open 条件 (三度目)**:
- **fix v2 後も focal<25 で stop** → 別 dominant gate (prob 0.25 variance / 推論
  deadlock / world_tick 進行停止) を再特定。Codex Q7 反映で γ (prob=1.0) を新規
  ADR child で起票
- **推論 backend が変わって cognition_period が 60s 以下 / 240s 以上に変動** →
  COOLDOWN_TICKS_EVAL=5 の妥当性を再評価 (60s なら cooldown=10 候補、240s なら
  cooldown=3 候補、empirical 再採取で確定)
- **wall=120 min × 3 cell parallel で run-time が 6h overnight に伸びた場合** →
  ι (1 cell 逐次) への切り替え検討 (Codex Q1 reference、conceptually clean だが
  運用コスト trade-off)

**Codex `gpt-5.5 xhigh` independent review v2**: `codex-review-natural-gating-v2.md`
(145,717 tokens) verbatim 保存。Verdict: **revise** → HIGH 2 / MEDIUM 2 / LOW 1
全反映後 ship 相当。HIGH-1 (wall default 不整合) と HIGH-2 (既存 cooldown test
rewrite) は本 PR の改訂で解消、MEDIUM-1 (ME-8 explicit amendment) は本 amendment
block 自体、MEDIUM-2 (conservative estimate primary 化) は design-v2.md §5.1。
LOW-1 は cosmetic、prompt artifact は historical record として保持。

**Test 影響**: `test_dialog_eval_natural_mode.py` 既存 12 件のうち
`test_eval_natural_mode_preserves_cooldown_via_tick` と
`test_eval_natural_mode_sustains_admission_after_initial_burst` の 2 件は
`COOLDOWN_TICKS_EVAL=5` 参照に rewrite (test 件数不変)。新規 3 件
(`test_effective_cooldown_returns_eval_value_when_flag_true` /
`test_effective_cooldown_returns_live_value_when_flag_false` /
`test_live_mode_cooldown_unchanged_via_tick`) を `test_dialog_eval_natural_mode.py`
に追加。CLI test 1 件 (`test_wall_timeout_min_default_is_120`) を
`tests/test_cli/test_eval_run_golden.py` に追加 (このファイルは
`pytestmark = pytest.mark.eval` でモジュール全体が default CI から deselect される
既存規約、`-m eval` で個別実行可)。

**Full suite 数値** (baseline = origin/main 491db4b: 1248 passed / 31 skipped /
26 deselected): 本 PR では **1251 passed (+3)** / 31 skipped / 27 deselected (+1、
CLI test の eval marker 経由)。dialog test 3 件は default CI に組み込まれ、CLI
test 1 件は `-m eval` で別途検証 (single-shot 実測 PASS 確認済)。

---

## ME-summary

- 本 ADR **8 件** で Codex `gpt-5.5 xhigh` **4 回** review (2026-04-30 design.md MEDIUM 6 +
  LOW 1 / 2026-05-01 LOW-1 RoleEval MEDIUM 5 + LOW 2 / 2026-05-01 P3a-decide gating
  fix LOW 2 / 2026-05-01 P3a-decide v2 cooldown × cognition_period HIGH 2 / MEDIUM 2 /
  LOW 1) 全件に対応
- ME-4 は P3a-decide セッションで **partial update**、natural 再採取後に **二度目の
  Edit が必要** (current state = bug fix done + script ready, ratio 確定は次回)
- ME-7 は本タスク P2a で確定、stimulus YAML schema と MCQ scoring protocol を規定
- ME-8 は **二度目の partial update** (2026-05-01 amendment block):
  v1 fix (zone bypass) は ship 済だが G-GEAR Phase A 再採取で cooldown × cognition_period
  の wall 換算が dominant gate と判明。`COOLDOWN_TICKS_EVAL=5` 別定数化 + wall default
  90→120 min で v2 fix。Codex v2 review で revise → HIGH/MEDIUM 全反映済
- LOW-1 (RoleEval wording) は ME-7 で close、本 ADR set 範囲内に取り込み済
- 既存 M9-B DB1-DB10 ADR との衝突: 無し
- M2_THRESHOLDS / SCHEMA_VERSION / DialogTurnMsg / RunLifecycleState への破壊変更: 無し
