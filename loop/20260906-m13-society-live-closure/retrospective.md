# retrospective — M13 案 B: ミラー/society Layer2 を live 閉包経路へ

> 実装セッション (2026-09-06 〜 09-07)。設計は別セッションで FROZEN 済
> (`.steering/20260906-m13-society-live-closure/design-final.md`)。

## 結果

- **全 7 issue DONE_CONFIRMED** (I1〜I7)。
- **D1** (AC↔test 全 pass) / **D2** (pre-push CI parity 4 段 exit 0) 達成。
- **D3** (cross-platform 実測) は **user 裁定待ち**。
- Stop 条件 S1〜S5 は**いずれも非該当**。
- **real qwen3 実走は一度も行っていない** (user の明示 spend ratify が要る別ゲート)。

## 実行方式

CLAUDE.md の binding どおり **main はオーケストレータに徹し**、issue ごとに subagent を立てた。
各 attempt を `test-runner`(Haiku) → `loop-watchdog`(Haiku) で客観検証し、
**executor の自己申告を verdict にしなかった**。TASK-POST で `code-reviewer`(Opus) と
`Codex`(gpt-5.5) の二者レビュー。

## うまくいったこと

### 1. 二者レビューが実際に別々の欠陥を捕まえた

**指摘がほとんど重ならなかった**ことにこそ意味があった:

- **Opus** = 検査の実効性 (恒真性)。`target_agent_routing` seam の第二項を**削っても全 test が緑**という
  mutation 実験を実行して HIGH を実証した。
- **Codex** = 成果物の文言精度と gate の厳密さ。`scope_boundary` が rehearsal manifest にも入るのに
  **無条件で real qwen3 到達を主張**している over-read (HIGH)、provenance gate が digest 形式を
  検証せず `"abc"` が通る、など。

単独レビューならどちらか一方が丸ごと抜けていた。**同一モデル 1 発案の構造的バイアスを別モデルで
閉じる**という CLAUDE.md の狙いが、実測で裏付けられた事例。

さらに一致点にも価値があった: `detach()` の解放漏れは、Opus 指摘 → 修正 → **Codex が
「例外経路は依然として塞がっていない」**と捕まえた。修正が半分だったことを二者目が検出した。

### 2. watchdog の独立再実行が機能した

`verify_level: recheck` の規律どおり、watchdog が毎回独立に verify を再実行した。
executor の「done」宣言を exit code で打ち消す仕組みが実際に働いた
(I1 では executor が正直に赤を報告し、自己判断で回避しなかった)。

### 3. executor が orchestrator の誤りを 2 回捕まえた

- **I4**: orchestrator が prompt に書いた seam の等式
  `msg.target_agent_id == observation.agent_id` は、`world_perturbation_to_perception` が
  `agent_id` を無条件写像するため **恒真**だった。executor が独立に検出し `routed_agent_id` を
  additive 追加した (DA-SLC-8)。
- **I1**: orchestrator が prompt に書いた「触ってはいけない: 既存テスト」は ADR §4 に無い**過剰制約**
  だった。executor は自己判断で回避せず**報告に留め**、orchestrator が ADR を読み直して裁定した。

## 反省点 (次回に持ち越す教訓)

### R-1: acceptance の具体式を orchestrator が書くと恒真になりうる

**事象**: I4 の prompt に書いた seam の等式が恒真だった (DA-SLC-8)。さらに**それを修正した後も、
非恒真性が test で pin されていなかった** (TASK-POST HIGH で Opus が mutation 実験で発見)。
つまり**同じ穴を 2 回開けた**。

**教訓**: 「witness が非恒真であること」を**実装者の気付きに依存させない**。
issue の AC に **negative fixture を明示的に要求**し、さらに
**「その負例が実際に False を返すことを、同じ witness 関数を通して示せ」**まで書く。
I5 以降の prompt にはこれを binding として組み込み、実際に I5/I6 では全 AC に負例が付いた。

**さらに強い教訓**: **mutation testing を acceptance の一部にする**。
「この行を消したら test が落ちるか」を機械的に確認する工程を、witness を land する issue の
Done 条件に入れるべきだった。TASK-POST まで発見が遅れた。

### R-2: 「主張」と「保証」の乖離は artifact に焼き込まれると危険

Codex HIGH の `scope_boundary` は、**commit 済みの rehearsal manifest** に
「real qwen3 に到達した」と読める文言を残していた。同種の `L1` は Opus 指摘で直したが、
**共有 annotation を条件形にする、という一般化ができていなかった**ため別箇所が残った。

**教訓**: over-claim の修正は**箇所ごとの潰し込みでなく、経路ごとに一般化して潰す**。
「capture_mode に依らず共有される annotation」というカテゴリ全体を見直すべきだった。

### R-3: rate limit で 2 回中断した

- I4 attempt 1: Sonnet の session limit (429、reset 19:20)。**ファイル編集前**に落ちたので影響ゼロ。
- I7 attempt 1: Opus の session limit (429、reset 01:10)。**test ファイル作成直後**に落ち、
  部分適用が残った。

**対処**: いずれも Stop 条件ではない外部要因として扱い、**executor のモデルを振替えて継続** (DA-SLC-7)。
I7 では部分適用を**破棄せず活かし**、orchestrator が自分で pytest を回して残作業 3 件を特定してから
差し戻した。

**教訓**: 長時間タスクではモデル枠の枯渇が起きる。**部分適用が残る中断**に備えて、
再開時はまず `git status` / `git diff` で状態を確定し、**自分でテストを回して残作業を特定**してから
差し戻すのが速い (executor に「状況を調べ直させる」より確実で安い)。

### R-4: フルスイートが 10 分かかるので検証の配置が重要

per-issue でフルスイートを回すと wall-clock が伸びる。scoped verify + watchdog の recheck を
per-issue に、フルスイートは節目 (I1 / I3 / I6 / 最終 pre-push) に置いた。
**executor がファイルを編集中にフルスイートを回すと結果が曖昧になる**ので、
起動タイミングを直列化する必要があった。

## 設計判断の記録

実装中に生じた判断はすべて `.steering/20260906-m13-society-live-closure/decisions.md` に
DA-SLC-4 〜 DA-SLC-9 として記録した。**いずれも orchestrator 判断であって user 裁定ではない**:

| # | 判断 |
|---|---|
| DA-SLC-4 | §M8 spend guard の閉 allowlist に `erre_sandbox.erre.two_phase` を 1 語追加 |
| DA-SLC-5 | lint の binding は CI parity (`ruff check src tests`)、`scripts/` の 184 errors は pre-existing |
| DA-SLC-6 | `gateway_serve` 署名の変更 + readiness barrier が保証する範囲/しない範囲の明示 |
| DA-SLC-7 | rate limit により per-issue executor のモデルを一時振替 |
| DA-SLC-8 | `routed_agent_id` の additive 追加 (恒真だった seam の修正) |
| DA-SLC-9 | consume 側 ledger を `Registry.reserve_slot` + lifespan で取る経路 |

## 持ち越し

`.steering/20260906-m13-society-live-closure/blockers.md` を参照。
主なもの: `society_live_loop.py` の 3 分割 (follow-up `/refactor` として起票)、LOW 5 件、
real qwen3 実走 / WSL byte-parity 実測 / 実 Godot end-to-end / `dialog_envelope_sink` (別 ADR) /
M4 の `memory_centroid` collapse (**未解決のまま**)。

## honest な到達点

land したのは **配線 / construction** であって **aha / emergence / effect ではない**。
「N 体が live で相互作用した」は**配線到達性の boolean** であって社会的創発の実証ではない。
ミラーは **prompt-level self-other context** であって心の理論ではない。
**wall-clock real-time session ではない** (ManualClock + scripted in-process 摂動)。
door② UNMET・計測ライン CLOSE・R-budget=0・holding は**いずれも不変**。
