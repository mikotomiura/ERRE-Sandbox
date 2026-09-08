# Retrospective — 20260908-paper01-scope-condition

## 到達点

事前登録した scope condition 測定の**装置**を建設し、統合 CI 緑まで到達した。
**測定そのもの (I-007b) は未実行** — Ocsai のネットワーク再取得を伴うため user 認可待ち。

- issue: 001 / 001b / 002 / 003 / 004 / 005 / 006 / 007a = **8 本統合**
- 統合 CI: `ALL CHECKS PASSED` (4235 passed / 53 skipped / 4 段)、緑 SHA = `8593e26`
- TASK-PRE (Codex) / TASK-POST (Opus ∥ Codex) 両ゲート実施

## 効いたこと

### 1. TASK-PRE が「都合よく倒れる」穴を実装前に潰した

Codex TASK-PRE HIGH-3 = **`design-final.md:165` が凍結する「判定不能」を
`Stage1Result` が表現できていない**。判定不能が `deflation_supported=False` へ潰れ、
`:251` の出口表ではそれが「deflation 棄却」= **書く方向の前提**として通る構造だった。

**事前登録が防ごうとしたバイアスそのもの**が契約の穴として残っていた。
I-001b で `STAGE1_OUTCOME_ENUM` の三状態化により閉じた
(config.json に載るため **事前登録の修正**。DA-SC-19 に明示記録)。

**self-check では見つからなかった** — DA-SC-14 の「issue は凍結 ADR を機械的に
写しただけ」という前提が、契約の穴には効かなかった。

### 2. witness を実際に壊して確かめる規律

`feedback_witness_needs_mutation_testing` を全 issue に適用したが、
**それでも 1 件、docstring が kill 経路を過大申告していた** (AC 001b-4)。
「enum メンバから構築しているので不等号 assertion が kill する」と書いてあったが、
実装は生リテラルで、M1 を当てると membership assertion が先に落ちた。

→ **mutation ログが全件 KILL でも、説明が事実と食い違いうる。**
以降の executor プロンプトに「**mutant を実際に当てて、どの assertion で落ちるかを
観測してからログに書く**」を明記した。

オーケストレータ側も、研究倫理に直結する 2 点は自分で mutant を当てて確認した:
- I-004: `INCONCLUSIVE` → `DEFLATION_REJECTED` の丸め → **5 test が kill**
- I-005: `not deflation_supported` から書く権利を導出 → **専用 test が単独 kill**

### 3. 二者レビューの MEDIUM が重複ゼロ

TASK-POST の MEDIUM 4 件は **Opus と Codex で完全に別**だった (PR #92 と同じ所見)。
特に Codex 側の 2 件は**判定規則の fail-closed 性**に触れていた:
片側 split だけで「両分割合意」と読める / `Stage1Result` が矛盾 artifact を作れる。

## 失敗したこと (次に持ち込む)

### A. 記録済み決定を読まずに上書きした (DA-SC-16)

**DA-SC-14 は「TASK-PRE を起動しない」を予算配分の理由で採用済**だった。
再開セッションが `decisions.md` を読む前に起動し、191,098 tokens を消費した。
収穫は大きかったが**手続きとしては違反**であり、TASK-POST の再レビュー余地を
削った (日次 895,179 / 1,000,000 で着地)。

→ **教訓: 中断セッションの再開時は、プロトコルの穴を埋める前に `decisions.md` を読む。**
「未実施のゲートがある」ことと「そのゲートを実施すべき」ことは別。

### B. 30 分の suite を issue executor に持たせた設計が事故を生んだ (DA-SC-20)

- I-001 の executor: フルスイートを背景起動し「完走しなかった」と自己申告して done にした
- I-001b の executor: 完了通知を待って **3 回停止**、さらに
  **重複プロセスと誤認して他者の pytest を強制終了**した (オーケストレータの検証実行が
  `exit 127` で死んだ)

→ フルスイート gate を **per-issue から統合点へ移動**。
executor プロンプトに「**バックグラウンドに回して通知を待たない**」
「**自分が起動していないプロセスに触らない**」を binding で明記した。

### C. worktree の base が古いまま着手される事故が 4 回起きた

I-005 (attempt 1) / I-003 / I-004 / I-006 / I-007a のすべてで、
worktree の HEAD が `9a13b6c` (task 開始前) に座っていた。
attempt 1 の I-005 はそれに気づかず着手し、破棄になった。

→ **手順 0 として「base 検証 → 不一致なら `git reset --hard <sha>`」を
executor プロンプトの先頭に置いた**。以降は全 executor が自力で復旧した。

### D. 並列 fan-out は「入力形状」も凍結しないと合流点に負債が集まる

I-001b が **dataclass の中身**を凍結したが、**関数の入力形状**は開いていた。
I-005 が `decide_scope()` の 3 引数の形と `SplitCells` を自分で決め、
I-006 がそれに合わせる負債になった (ブロッカー 2)。

### E. 訂正は波及先を全部たどらないと残る

Codex HIGH-1 (「C4 は raw curated であり dedupe されていない」) は
ADR には反映されたが、**`docs/glossary.md` には届いていなかった**。
TASK-POST で Opus が拾った。

## 残 (I-007b)

- **Ocsai のネットワーク再取得** (ローカルに無い。encoder 4 本と Cambridge は在庫あり)
- **実走** → `results/scope.json` → verdict
- **fidelity pin (b) (AC 006-1) はまだ一度も走っていない** (ブロッカー 3)。
  `run.sh` の `--fidelity` が緑にならないうちは verdict を読まない
- `notes.md` の結果節記入 / `mutation-log.md` の統合 / `.steering` 最終化
- Opus LOW-2/3/4 の defer 分 (blockers.md)
