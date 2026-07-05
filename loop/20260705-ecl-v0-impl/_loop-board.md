# Loop Board — ecl-v0-impl

task: ECL v0 実コード実装 (Embodied Cognition Loop v0)
更新: dashboard 端末のみ (single writer)。events を issue ごとに畳んだ表示。

| issue | title | state | verify_level | attempt | 最終 event |
|---|---|---|---|---|---|
| 001 | contracts/geometry SSOT 昇格 + zones shim | ✅ done | recheck | 1 | issue_done |
| 002 | cognition/embodiment 履歴依存幾何 + continuity control | ✅ done | recheck | 1 | issue_done |
| 003 | ECL live seam foundation (cycle+world seam 全所有) | ✅ done | recheck | 1 | issue_done |
| 004 | integration determinism harness + replay checksum | ✅ done | recheck | 1 | issue_done |
| 005 | handoff converter/manifest/golden + Godot dev player | ✅ done | recheck | 1 | issue_done |

依存順 (直列): I1 → I2 → I3 → I4 → I5
状態機械: queued(⏳) → running(🔄) → verifying → review → done(✅) / blocked(⛔) / abandoned
