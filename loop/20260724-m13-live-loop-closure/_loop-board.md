# Loop Board — 20260724-m13-live-loop-closure

> 単一書き手（dashboard 端末）。events を issue ごとに畳んだ表示。`/loop-status` で再描画。
> honest = 配線であって aha/emergence/effect でない。

| Issue | title | verify_level | deps | state |
|---|---|---|---|---|
| 001 | InboundEnvelope + WorldPerturbationMsg + →PerceptionEvent 写像 | recheck | — | ✅ done |
| 002 | gateway inbound_sink opt-in（None で observational identity） | recheck | 001 | ✅ done |
| 003 | live_loop.py 閉包 root（knob-on cycle + driven ループ + capture） | recheck | 001,002 | ✅ done |
| 004 | Plane G capture→run_two_phase_capture replay byte-parity golden | recheck | 003 | ✅ done |
| 005 | Godot send_perturbation + inbound UI trigger | parse | 001 | ✅ done |
| 006 | W-live correlation-id 到達性 witness | recheck | 003 | ✅ done |

依存順: **I1 → {I2, I5} → I3 → {I4, I6}**。file 重複（inbound.py=I1/I2、live_loop.py=I3/I4/I6）ゆえ
shared-tree-sequential（parallel=1）。

状態機械: `queued(⏳) → running(🔄) → verifying → review → done(✅)` / 逸脱 `blocked(⛔)` / 断念 `abandoned`。

## TASK-POST（統合 diff）

- 統合フル CI parity: ✅ 全 4 段 PASS（pytest 3863 passed, 52 skipped pre-existing）。
- cross-review: Codex(gpt-5.5) **Adopt-with-changes**（HIGH2/MED2）+ code-reviewer(Opus) **Approve**（MED2/LOW3）。
- 採用 7 件反映済（Codex HIGH×2 の honest-framing 絞り込み含む）→ 再 CI 全 4 段 PASS。
- 残: push / PR 作成（outward-facing = user 確認）、最終 merge・real spend(I7)・WSL byte-parity 実測 = **user 裁定**。
