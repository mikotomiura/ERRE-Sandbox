# ブロッカー — m9-c-adopt retrain v2 implementation

(本セッション中に発生したブロッカー + 持ち越し事項)

## (open)

### B-impl-1: Training kickoff + recapture + verdict は次セッションへ持ち越し

- **検出**: 2026-05-14 (本 PR、implementation 完了時点)
- **理由**: 本 PR 範囲では implementation + pre-training audit (dry-run) まで
  完遂。実際の training (3-5h G-GEAR overnight) + multi-turn pilot recapture
  (~1h) + consumer + matrix + ADOPT/REJECT 判定 (~30 min) は単一の
  Claude Code conversation 内では完結困難 (~5-7h envelope)。
- **影響**: 本 PR は **implementation + audit only** で merge。training
  artefacts (`data/lora/m9-c-adopt-v2/kant_r8_v2/`) と DA-14 verdict は
  次の overnight session で取得。
- **次セッション**: `next-session-prompt-FINAL-training.md` 参照 (本 PR 内で生成)
- **defer 判断**: HIGH-3 (post-hoc threshold movement 禁止) に抵触せず、
  仕様の段階的 delivery として acceptable。spec + implementation が
  landed すれば training 実行は機械的タスク。

### B-impl-2: de+en weighted mass が target 0.60 を下回る (0.501)

- **検出**: 2026-05-14 (pre-training audit dry-run)
- **重要度**: soft warning (training continue OK、Candidate C escalate 不要)
- **影響**: persona-discriminative signal の絶対量が design 想定より
  弱い可能性。training 後の Vendi/Burrows/ICC 4 軸判定で REJECT になった
  場合の re-design 候補として記録。
- **回避策**: Candidate C (targeted +2500 de/en/≥60 hybrid 採取) を
  REJECT 時の fallback として decisions.md D-1 で評価。

## (resolved)

なし
