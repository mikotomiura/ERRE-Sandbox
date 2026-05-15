# ブロッカー記録 — security-hardening-pre-m10

## M10-0 着手の go/no-go gate (Codex 13th META-1 由来)

**M10-0 (Individual layer schema + persona_id) 着手の前提条件として、本 task
の follow-up で SH-1 + SH-2 を消化する必要がある。**

Codex 13th 13th independent review META-1 verdict (`codex-review.md` 参照):

> P4/P5 を defer したまま **M10-0 に進む判断は不可**。特に SH-1 は元 HIGH で、
> 未対応のまま "pre-M10 hardening complete" とは言えません。一方、今回の
> 4 commits を "P0-P3 partial hardening PR" として push/PR 化する判断は、
> HIGH-1/HIGH-3 修正後なら妥当です。

### 残作業 (post-merge follow-up task)

| Section | ADR | 概要 | 工数 | M10-0 gate |
|---|---|---|---|---|
| §1 | SH-1 | Codex hook + CI shell-bypass policy gate | ~3h | **必須** (元 HIGH-1) |
| §2 | SH-2 | WS shared-token + Origin allow-list + session cap | ~5h | **必須** (元 MEDIUM-2) |

両者の ADR (`decisions.md` SH-1 / SH-2) は本 branch で起草済なので follow-up
task でゼロから設計し直す必要なし。`tasklist.md` の P4 / P5 セクションをそのまま
実行できる。

### Follow-up task scaffold 手順 (post-merge)

1. main を最新化、`/start-task security-hardening-pre-m10-followup` で
   作業ディレクトリ `.steering/20260516-security-hardening-pre-m10-followup/`
   (または当日日付) を新規作成
2. 本 branch の `decisions.md` から SH-1 / SH-2 を `decisions.md` に copy + linkback
3. 本 branch の `tasklist.md` P4 / P5 セクションを follow-up の `tasklist.md` に
   migrate
4. `requirement.md` は本 branch を Refs 引用 + M10-0 gate 文脈を追加
5. P0-P3 と同じ workflow (P0 scaffold → 各 P 実装 → Codex 14th review → close)

---

## ブロッカー 1: drain_envelopes 順序契約の implicit dependency (P3 実装時)

- **発生日時**: 2026-05-15
- **症状**: `world/tick.py` の `drain_envelopes` を 2-queue 化した際、Plan で
  「main → heartbeat の順」と書いていたが、既存 `test_drain_is_fifo`
  (`tests/test_world/test_tick.py:514`) と
  `test_heartbeat_emits_world_tick_msgs_periodically` (`test_tick.py:481`)
  で `kinds[0] == "world_tick"` と heartbeat 5 個を期待していた
- **試したこと**: Plan 起票時に既存 caller の audit を Step 7 で予定していたが
  既存テストの assertion を文字単位で確認していなかった
- **原因**: 「真の FIFO の旧契約」では (heartbeat は時系列で常に先行するため)
  drain の先頭が heartbeat に来る暗黙の保証があった。新 2-queue では明示的に
  order を選ぶ必要があった
- **解決方法**:
  - `drain_envelopes` の order を **heartbeat → main** に訂正
  - `test_heartbeat_emits_world_tick_msgs_periodically` の `len == 5` を
    `len == 1` に mechanical 調整 (heartbeat coalesce は SH-5 ADR の核心仕様)
- **教訓**: 既存 caller の audit は grep + 「呼出側 assertion の文字面」両方を
  確認する。queue semantics 変更時は order contract を docstring に明記する

## ブロッカー 2: recv_envelope の both-done race で heartbeat silent-drop (Codex 13th HIGH-1)

- **発生日時**: 2026-05-15 (Codex 13th review で切出)
- **症状**: 初版 `recv_envelope` (commit `9061173`) は `asyncio.wait(FIRST_COMPLETED)`
  で両 task が同時 done のとき main を return しつつ heartbeat result を
  捨てていた (silent-drop)。`except BaseException` でも cancel 後 await して
  おらず、loop close timing で pending task warning が出る余地があった
- **試したこと**: Plan の HIGH リスク欄で「両 done 時の判定漏れ」を予測して
  いたが、対処は「`if main_task in done` で順序保証」と書いていただけで
  heartbeat result を保護する仕組みは入れていなかった
- **原因**: Plan 段階で main 優先 + cancel only という single-axis 思考だった。
  Codex が independent review で「liveness signal が silent-drop されている」
  と切出
- **解決方法**:
  - `if hb_task in done and not hb_task.cancelled():` で heartbeat result を
    `_reinject_heartbeat()` で coalesce-requeue
  - `asyncio.gather(*pending, return_exceptions=True)` で cancel した task を
    必ず await
  - `except BaseException` 経路でも両 task を `gather(return_exceptions=True)`
    で吸収
  - `test_recv_envelope_returns_main_and_preserves_heartbeat` 追加
- **教訓**: race-merge の Plan 段階レビューでは「losing 側の result の行き先」を
  明示的に決める。Codex 独立 review が single-axis design bias を補正した
  empirical 実績 (W-7)

## ブロッカー 3: default branch broken symlink miss (Codex 13th HIGH-3)

- **発生日時**: 2026-05-15 (Codex 13th review で切出)
- **症状**: `_resolve_memory_db_path` の default branch が `Path.exists()` で
  存在チェックしていたが、`Path.exists()` は symlink を follow するため broken
  symlink は False 扱いとなり、`default.unlink()` が skip されて symlink
  そのものが返り、下流 `MemoryStore` が open() で symlink を辿る可能性
- **原因**: SH-4 ADR では `os.path.lexists` 使用を明記していたが実装で
  `Path.exists()` を使ってしまった (ADR と実装の drift)
- **解決方法**:
  - default branch を `os.path.lexists` + `is_symlink` ガードに書き換え
  - explicit branch も symmetry のため `os.path.lexists` に統一 (`is_symlink`
    で既に reject されているので semantics は変わらず、defence-in-depth)
  - `test_memory_db_default_path_rejects_broken_symlink` +
    `test_memory_db_explicit_path_rejects_broken_symlink` 追加
- **教訓**: ADR で `os.path.lexists` のような non-default API を指定したら、
  実装直後に grep で実機照合する。Codex 独立 review の fact-check が
  ADR↔実装 drift を構造的に閉じる empirical 実績 (W-6 / PR #159 と同型)
