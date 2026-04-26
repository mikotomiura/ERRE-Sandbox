# Tasklist — M8 Scaling Bottleneck Profiling

> L6 D2 precondition、~1d 見込 (半日 metric+script、半日 live run + 閾値確定)。
> 開始前に **Plan mode + /reimagine 必須** ("observer fatigue" の操作定義は
> 複数案ありうる、主観 proxy / 客観 proxy の切り分けが判断どころ)。

## 準備
- [x] L6 ADR D2 を Read (PR #94 pre-plan-research.md 内に集約)
- [x] `architecture-rules` / `python-standards` / `test-standards` /
      `implementation-workflow` Skill を Read
- [x] `integration/dialog.py:315-328` の pair enumeration を調査
- [x] `world/tick.py:836-841` の並列 tick (asyncio.gather) 位置を確認
- [x] 上流 spike `m8-episodic-log-pipeline` の merge 状況を確認 (PR #88 merged)

## metric 定義 (decisions.md に記録)
- [x] **M1 pair_information_gain**: H(pair) - H(pair|history_k=3) (bits/turn)
      → decisions.md D1
- [x] **M2 late_turn_fraction**: turn_index > budget/2 の dialog_turn 割合
      → decisions.md D2
- [x] **M3 zone_kl_from_uniform**: KL(observed||uniform) (bits)
      → decisions.md D3
- [x] **D5**: D3 (`session_phase`) との metric scope 分離 (filter は AUTONOMOUS で
      動作、Q&A は実装時に追加)

## 実装
- [x] `src/erre_sandbox/evidence/scaling_metrics.py` を追加 (~580 行、5 公開関数)
- [x] 閾値判定 (`evaluate_thresholds`): TSV log 追記 + 違反 metric 名 list 返却
- [x] fixture-based unit test (`tests/test_evidence/test_scaling_metrics.py`) — 31 tests

## テスト (MacBook で完走可)
- [x] 単体: 3 metric 関数が固定 fixture で期待値を返す (entropy は pytest.approx)
- [x] 単体: 閾値判定の境界条件 (=閾値 / <閾値 / >閾値)
- [x] 統合: temp sqlite + temp jsonl から scaling_metrics.json が生成される e2e
- [x] graceful degradation: --journal 欠落で M3=None, alert は M1/M2 のみ

## live run (G-GEAR 必須)
- [x] G-GEAR で N=3 の 90-120s run × 3 本 (sample B/C/D、bias_p=0.1) +
      δ run-02 reuse (sample A, 360s) = 計 4 sample
- [x] 3 metric の暫定分布を `profile.md` に記録
- [x] 各 metric の閾値を profile から確定 (M1=30%/M3=30% 確定、M2=60% provisional)

## レビュー
- [ ] `code-reviewer` で metric 関数と閾値判定をレビュー (PR 起票時に実施)
- [ ] `impact-analyzer` 不要 (新規ファイル限定、Plan で影響範囲確認済み)

## ドキュメント
- [x] `docs/architecture.md` の Evidence Layer に scaling metric を追記
- [x] `docs/glossary.md` に observability-triggered scaling + 3 metric 用語を追加
- [x] `docs/functional-design.md` 機能 6 として M8 metric を追記
- [x] `docs/repository-structure.md` に `evidence/` と `cli/` ツリーを追加

## 完了処理
- [x] `design.md` 最終化、`decisions.md` に 3 metric 定義 + 確定閾値を固定
- [ ] commit → PR (`feat(evidence): M8 scaling bottleneck profiling`)
- [ ] merge 後、L6 D2 status を「閾値案確定、M9 以降のトリガー判定に使用可」に更新
