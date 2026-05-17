# 重要な設計判断 — PR-3 kant_r8_v4 forensic JSON commit (artifact-only)

> 本 file は本 PR セッション固有の設計判断を記録する。横断 ADR は
> `.steering/20260513-m9-c-adopt/decisions.md`、kant Plan B 順序判断は
> `.steering/20260517-m9-c-adopt-da16-design/decisions.md` DA16-1〜
> DA16-4、PR-2 実装局所判断は `.steering/20260517-m9-c-adopt-pr2-
> weighted-trainer-fix/decisions.md` DP2-1〜DP2-5 を参照。

## DP3-1: HuggingFace Hub upload を **PR-4 verdict ADOPT 確定後の PR-5** に後送り (本 PR では forensic JSON のみ commit)

- **判断日時**: 2026-05-17
- **背景**: 前身 next-session prompt
  (`.steering/20260517-m9-c-adopt-pr2-weighted-trainer-fix/
  next-session-prompt-FINAL-pr3-kant-r8-v4-retrain.md`) は PR-3 内で
  HF Hub push を行う想定 (PR-2 retrain artifact を即時公開、PR-4
  verdict 計算時に HF Hub 経由で adapter download)。

  しかし user feedback (2026-05-17 セッション):
  > 「verdict で ADOPT に判定が出てからの HuggingFace のほうが良いのでは？」

  → PR-3 scope を **forensic JSON commit only**、HF Hub push を PR-5
  に後送りして verdict 分岐 (ADOPT→HF push / REJECT→rank=16 spike) に
  pivot する方針が提案された。

- **選択肢**:
  - **A** (本採用): PR-3 で forensic JSON 4 file のみ commit、PR-5
    (PR-4 ADOPT 経路) で HF Hub push、REJECT 時は push skip
  - **B** (前身採用案、廃案): PR-3 で HF Hub push 先行 + forensic
    commit、PR-4 で HF Hub 経由 download して verdict 計算、REJECT
    時は HF Hub repo を delete or rename
  - **C**: HF Hub push 自体やめて local + 別 storage (G-GEAR) のみで
    完結、verdict 確定後も HF Hub に push しない

- **採用**: **A**

- **理由**:
  1. **verdict 結果に依存しない artefact は早期 commit、依存する公開
     行為は確定後**: forensic JSON 4 file は v3 と同 schema で reproducibility
     audit に必須、PR-4 で v4 adapter を load する際にも `train_metadata.json`
     の `best_step=2000` 情報が必要。一方 HF Hub push は **公開行為** で
     verdict 結果が ADOPT なら baseline 比較に有用、REJECT なら冗長。
     公開のタイミングを verdict 確定後に揃える方が論理的
  2. **REJECT 時の cleanup コストゼロ**: 案 B は REJECT 時に HF Hub repo
     を delete or rename する必要があり、組織管理コストが発生する。
     案 A は push 自体しないので cleanup 不要。HF Hub repo 命名規則
     (`mikotomiura/erre-kant-r8-v4-loraadapter`) を ADOPT 版のみに保持
     することで「HF Hub にある = ADOPT 確定版」という不変条件を得る
  3. **v3 残置は別件**: v3 adapter (`mikotomiura/erre-kant-r8-v3-
     loraadapter`) は当時の workflow で push したのが結果的に baseline
     比較用に役立っているだけ。v4 で同 pattern を踏襲する必要はない。
     PR-4 verdict 計算で v3 baseline 参照が必要な場合は既存 HF Hub
     repo から download 可能 (delete しない、本 PR の留意点で明示)
  4. **forensic 再現性は local + git で十分**: PR-4 verdict 計算は
     `data/lora/m9-c-adopt-v2/kant_r8_v4/adapter_model.safetensors` を
     local path で load すれば成立。HF Hub auto download は便利機能で
     あって必須ではない (本セッション 2026-05-17 で G-GEAR に既に
     adapter binary が存在)

- **トレードオフ**:
  - **PR-4 verdict 計算は local path 依存**: HF Hub からの自動 download
    が使えないため、PR-4 session マシン (本セッションでは G-GEAR) に
    `data/lora/m9-c-adopt-v2/kant_r8_v4/adapter_model.safetensors` が
    存在する必要あり。MacBook で PR-4 を実行する場合は事前 rsync が
    必要。**ただし** PR-4 は eval shard 採取 (~30 min GPU) + 4-encoder
    rescore で GPU 必須なので **G-GEAR 確定** であり実害は低い
  - **PR 数が 1 増える可能性**: PR-4 verdict ADOPT なら PR-5 (HF push)
    が必要、PR-4 REJECT なら PR-5 (rank=16 spike) が必要 — どちらの
    経路でも追加 PR は発生するため、本 DP3-1 で PR 数の純増は 0
  - **HF Hub の "結果に関わらず全 retrain 試行は公開する" semantic を
    放棄**: v3 (REJECT 後も残置) と v4 (ADOPT 時のみ push) で扱いが
    非対称になる。ただし v3 残置の理由は "当時の workflow で push 済"
    という path-dependence で意図的設計ではなかったため、DP3-1 で
    "verdict 後 push" 方針に切り替えることで以後の retrain は一貫した
    semantic で運用できる

- **影響範囲**:
  - 本 PR (PR-3) scope: forensic JSON 4 file commit のみ
  - PR-4 (DA-14 rerun verdict): v4 adapter を local path 経由で load、
    HF Hub からの auto download path 不採用
  - PR-5 scope は verdict 結果で分岐:
    - **ADOPT → PR-5 = HF Hub push** (本 DP3-1 で後送りした分を実施)
      + nietzsche / rikyu Plan B 展開準備
    - **REJECT → PR-5 = rank=16 spike retrain** (HF push skip、新規
      adapter `kant_r16_v1` 生成へ pivot)
  - `next-session-prompt-FINAL-pr4-da14-rerun-verdict.md` で PR-5 用
    conditional prompt 2 案を併記、PR-4 verdict 確定時にどちらを採用
    するか決定

- **見直しタイミング**:
  - PR-4 verdict ADOPT で PR-5 = HF push を起票する時、本 DP3-1 で
    確定した "ADOPT 後 push" 方針を再確認
  - PR-4 verdict REJECT で PR-5 = rank=16 へ pivot する時、HF Hub に
    v4 を push しないまま (rank=16 retrain) → PR-5b で再 verdict →
    その時点で ADOPT なら kant_r16_v1 を HF push という flow に
    なるが、その時点で本 DP3-1 を再評価 (rank=16 adapter は r=8 v4
    と別 file 名で並列共存可能、v4 push 検討は別案件)
  - nietzsche / rikyu Plan B 展開時に "WeightedTrainer fix 後 v4
    eval_loss 改善" の root-cause analysis が必要になった場合、
    "v4 が HF Hub にない" ことが外部研究者の再現実験で支障となる
    可能性 → その時点で別 PR で v4 push を検討
