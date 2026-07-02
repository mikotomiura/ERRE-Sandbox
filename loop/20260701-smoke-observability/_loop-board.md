# Loop Board — smoke-observability   ⏱ updated 15:40 (UTC・サンプルデータ)
進捗 1/3 done · 🔄1 running · ⛔1 blocked · tokens ?/2.0M

| # | issue             | 状態 | phase   | try | verify   | branch   | note                | PR |
|---|-------------------|------|---------|-----|----------|----------|---------------------|----|
|001| (issue_done)      | ✅   | –       | 2   | test✓    | loop/001 | –                   | #12 |
|002| (attempt→verify)  | 🔄   | execute | 3   | test✗(1) | loop/002 | –                   | – |
|003| (no_progress_stop)| ⛔   | verify  | 4   | test✗    | loop/003 | 同一fingerprint×4→STOP | – |

状態機械: `queued(⏳) → running(🔄) → verifying → review → done(✅)` / 逸脱 `blocked(⛔)` / 断念 `abandoned`。
