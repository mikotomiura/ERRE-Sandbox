# retrospective — M13 B 反復 frozen-context bank 実コード実装 (Loop Engineering)

> FROZEN ADR `.steering/20260707-m13-b-impl-design/design-final.md` §I0-§I11 (PR #63, main=ec3979f) の忠実履行。
> branch = feat/m13-b-bank。construction であって measurement でない (H/MDE/divergence/floor/verdict 非計算、
> R-budget 未消費、holding 不可侵、mock-only D-10)。

## 成果 (I1-I6 全 done + TASK-POST /cross-review 反映)

| Issue | commit | 内容 |
|---|---|---|
| I1 | 8e4b3e7 | competing-cue fixture + provenance pass (lever 4 次元、canonical inputs のみ) |
| I2 | 99851a1 | bake-out M-loop + BankLlmCallRecord + record-M (pre-bias readout, zone bias pin) |
| I3 | 67f4d9a | spend ast-guard (Codex HIGH-4 拡張、精密 set-over-zones) + capture script scan |
| I4 | 2efe407 | power apparatus + worksheet (MC-calibrated、scipy 不要、閾値 proposal と乖離ゼロ) |
| I5 | ff79235 | annotation side-file (opaque) + mock golden + replay (Ollama-free) |
| I6 | 344889e | continuity-gate 4 test + T3 materiality desk-audit |
| cross-review 反映 | 80dba05 | HIGH 4 + MEDIUM 2 |

- 最終: bank suite 100 passed、pre-push ALL CHECKS PASSED (3505 passed / 66 skipped)、organ 無改変 (bank は
  全て新規ファイル)、golden bank_checksum d3689afc。

## 一致/相違要点 (二者 /cross-review)
- **一致 HIGH**: replay 非決定 (unsorted 入力) — code-reviewer MEDIUM + Codex HIGH → 統合 HIGH → sorted iterate。
- **code-reviewer 固有 HIGH**: M-loop think=False 非強制 (provenance と非対称、C-proper で load-bearing)。
- **Codex 固有 HIGH**: spend guard の穴 (alias/subscript/keyword-only/scan) + created_at 非 pin (cross-platform
  非決定)。
- **決定的**: H4 (created_at) は理論でなく**実発火していた** — 旧 golden は G-GEAR の microsecond tie→id
  fallback で garden 先、修正後は構築順で study 先。cross-review が無ければ silent に platform 依存の golden が
  出荷されていた。

## 教訓
1. **cross-review が real bug を捕捉**: 全 82 test + pre-push を通過した実装に、二者 static/semantic レビューで
   4 HIGH。特に created_at の動的 timestamp channel は test では見えない determinism 穴だった。二者 (code-reviewer
   の semantic + Codex の static 別視点) の相補性が効いた。
2. **subagent 報告不備の exit-code 独立監査**: I2 の agent が正常な完了報告を返さなかった (meta 発言で停止) が、
   main が exit-code + 契約要点 grep で独立監査し Done 確定。自己申告を打ち消す loop-watchdog 精神が機能。
3. **session 上限中断のリカバリ**: I3/I5 subagent が Claude session 上限で早期終了 (書込前) → tree クリーンゆえ
   fresh 再スピンで安全に回復。部分成果の後始末不要な粒度が効いた。
4. **guard scope の後追い拡張**: I3 は I5 の capture script commit 前に走ったため scan 対象に含まず、main が
   後追いで `_BANK_AGG_FILES` を拡張。cross-review で更に golden test も追加。並行実装では guard の scan 対象が
   後発ファイルを取りこぼす — 統合時の scan-set 監査が要る。

## defer (decisions.md)
- **M3**: continuity self-scan が divergence 識別子ゆえ narrower guard に格下げ (honest 記載済、full guard 回復は
  allowlist 除外 helper で可、defer)。
- **L2**: §I1 字面「retriever 非呼出」vs 実装 (store preload → 実 retriever surface) の honest deviation。
- **I5-G6 empirical closure**: 本機 WSL1 + repo 未同期で WSL byte 一致未実測。golden は libm float 非在 +
  created_at pin で cross-platform 決定的 (analytical + H4 で timestamp channel も閉鎖)。empirical closure
  (WSL/Linux repro or Linux 再bake CI test) は user 裁定へ。
- **I4 閾値 ratify (DA-BIMPL-6)**: power worksheet の named 閾値は proposal と乖離ゼロ。最終 ratify は user 裁定。
- **T3 criterion 4 (stimulus 判定)**: desk-audit sign-off = criterion 1-3 充足で substrate enrichment と暫定
  判定。最終 stimulus/substrate 判定は user 裁定 (T3 fail なら line-close→arc-close の honest teeth)。

## 次工程
実 spend の powered bank sampling run は **C-proper AUTHORIZE 後のみ** (本タスク非対象)。B の annotation (raw
row) を次 C-design が empirical audit し go/no-go を再判定する前件。(i) 条件付き zone entropy 下限は B 単独
doc-only 保証不能を維持 (未達なら line-close → 両 family exhaust → arc-close 自動執行)。
