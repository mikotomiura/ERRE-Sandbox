# 00 — 共通検証フレームワーク

> **いつ読むか**: 新しい検証（GO/NO-GO 判断・効果測定・gate 設計）を始める前に最初に読む。
> 本ドキュメントは特定の研究 chain に依存せず、すべての検証に通底する「検証の作法」を定義する。
>
> **出典**: III-a live GO/NO-GO ADR（`.steering/20260616-iiia-live-gonogo-adr/`）/
> cognition-loop-divergence ADR（`.steering/20260605-*`）/ individuation S-series
> （`.steering/20260603-m10a-*`）/ Plan B kant chain（`.steering/2026052*-*`）の共通骨格。

ERRE-Sandbox の検証は「**実装を急がず、まず反証可能な判定構造を凍結し、別モデルで
敵対的に潰してから走らせる**」という一貫した規律で動いている。以下の 11 原則は、
どの研究 chain でも繰り返し適用されてきた共通の型である。

---

## 1. 反証可能な GO/NO-GO ADR と結果前 freeze

検証は必ず「何が観測されたら GO で、何が観測されたら NO-GO か」を**結果が出る前に**
ADR として確定し凍結する（pre-registration）。

- 閾値の具体数値は GPU 実行や本走の**前に** freeze する。結果を見てから閾値を
  動かすこと（結果後 tuning）は禁止。
- ADR は「gate 構造 + null 方式 + 凍結方法」を確定する。設計のみのタスクは
  実装・GPU・retrain を**非 authorize**（design-first, not execution-first）とし、
  prompt 承認≠即実行を徹底する。

## 2. estimand の明示と primary / diagnostic-only の分離

「何を推定したいのか（estimand）」を一文で確定してから指標を選ぶ。

- **primary metric**（必要条件 gate）と **diagnostic-only metric**（gate にしない
  参考量）を明確に分ける。
- **tautology 回避**: treatment の内部変数（例: carry offset / cap-hit / carry-active
  tick）を primary に入れない。それらは「効果の定義に効果が埋め込まれている」自己循環に
  なるため、fidelity 診断（M0）へ回す。primary は treatment **下流の** distal な
  観測量のみで定義する。
- 例（III-a live）: estimand = "paired live carry trajectory contrast"。同 seed の
  ON/OFF を別 run で走らせ、carry が後続 prompt→LLM 出力→将来 floor を変える
  total-trajectory 効果を測る。

## 3. 非循環 null hierarchy（null control）

GO 判定は「効果あり」を null（効果なし基準）との比較で示す。null は循環しないように
事前設計する。

- stochasticity audit（同 seed が決定的か）で null を分岐: 決定論的なら seed-perturb
  null、確率的なら同 seed rerun null + sanity null。
- null の選び方・閾値は結果前 freeze。結果後の null 差し替え禁止。

## 4. verdict の 4 状態 taxonomy

判定は二値（成功/失敗）にせず、最低 4 状態で表す。precedence（優先順位）も固定する。

| verdict | 意味 |
|---|---|
| **CONFIRMED** | primary 全 gate ∧ N 充足。bounded な効果を確認。GO は次工程への warrant であって核命題の証明ではない |
| **NO_DETECTABLE_EFFECT** | primary FAIL。**ただし coverage + null sensitivity が十分なときのみ強い NO** として扱う |
| **INCONCLUSIVE_LOW_POWER** | power 不足 / N 不一致。**早期打ち切りの根拠に使わない** |
| **INVALID_MEASUREMENT** | fidelity（M0）や安全性（M2）が FAIL。測定そのものが無効 |

precedence: INVALID > INCONCLUSIVE > NO_DETECTABLE > CONFIRMED（無効・不確定が
優先され、安易な CONFIRMED を防ぐ）。

## 5. 会計分離と claim 境界（over-claim guard）

検証結果は二つのバイアスの**両側**を同時に guard する。

- **継続バイアス**: NON-SATURATED や S>0 を「発散の証明」「核命題確定」と誤読する側。
- **早期打ち切り**: 効果が未測定なのに「効果なし」と断じる側。
- disposition（処分判断）と forward research（次の研究）を**会計分離**する。
  「必要条件の充足」と「十分条件の証明」を混同しない（必要 ≠ 十分）。
- すべての結論に **bounded envelope** を明記する（例: kant / N=3 single-persona /
  frozen cap 下、など適用範囲の限定）。

## 6. 敵対的検証（`/reimagine` + Codex independent review）

高難度の設計判断は、同一エージェントの 1 発案で確定させない。

- **`/reimagine`**: 初回案（v1）を意図的に破棄し、ゼロから再生成した案（v2）と
  並べて比較してから採用案（またはハイブリッド）を決める。
- **Codex independent review**: 別モデル（`gpt-5.5` / `xhigh`）で同一モデルの構造的
  バイアスを閉じる。反映ルール:
  - **HIGH**: 実装前に必ず反映
  - **MEDIUM**: 採否を `decisions.md` に記録
  - **LOW**: `blockers.md` に defer 可（理由明示）
- 実績: Codex の independent review が、点推定 over-claim や多重比較誤りを複数 round
  かけて撤回させた事例が複数ある（早期打ち切りの自己補正）。

## 7. frozen 非接触原則

確定済みの基準（cap 値・値域・kernel・既存 scorer・閾値・ライブラリ pin）は
**USE のみ**で改変しない。

- frozen 対象に対して `git diff` が空であることを**テストで機械証明**する
  （sentinel exit=0）。
- 新しい検証は frozen 資産を再利用するだけで、こっそり変えてはならない。

## 8. 不可侵原則 — observable evidence only

LLM の自己宣言で内部状態（stage advance / belief promotion / personality drift）を
**動かさない**。

- LLM = 候補提示、Python = state transition。状態遷移は観測可能な evidence のみが
  駆動する（M7δ `maybe_promote_belief` パターン）。
- ME-9 trigger 擬陽性 incident と同型の構造（自己申告で状態が動く）を全工程で排除する。

## 9. 多重比較補正と N=3 での報告作法

- 複数の density / seed / 軸を同時に検定するときは多重比較補正を入れる
  （Šidák / Bonferroni、密度監査では scipy 非依存の**自前 Clopper-Pearson**）。
- **N=3 で p 値 significance theater をしない**。報告は effect-size ratio と
  null overlap で行う。
- 点推定で打ち切らない。min-of-K のような順序統計には片側信頼限界を使う
  （早期打ち切り over-claim を 2 段階で撤回させた個体化 S4 の教訓）。

## 10. encoder agreement gate

ベクトル encoder で効果方向を判定するときは、単一 encoder に依存しない。

- per-encoder median の床比（例 1.5×）+ min backstop + `direction_all_positive` /
  `direction_all_negative` を同時に課す。
- 一つの encoder でも符号が反転したら gate FAIL（Plan B kant の e5large 符号反転で
  REJECT 確定した教訓）。緩和は禁止。

## 11. pre-push CI parity

push / `gh pr create` の**前に必ず** local で CI と同条件のチェックを 4 段通す。

```
ruff format --check  →  ruff check  →  mypy src  →  pytest -q
```

`pwsh scripts/dev/pre-push-check.ps1`（Windows）/ `bash scripts/dev/pre-push-check.sh`
（WSL/macOS/Linux）。1 段でも fail なら push 禁止。extras-only 依存
（sentence-transformers / torch / sglang 等）を新規 import するときは **3 点セット**
（lazy import + mypy `ignore_missing_imports` + test `pytest.importorskip`）を欠落させない。

---

## まとめ — 検証の標準フロー

1. estimand を一文で確定（§2）
2. primary / diagnostic を分離、null を設計（§2, §3）
3. GO/NO-GO 閾値と verdict 4 状態を ADR に freeze（§1, §4）
4. `/reimagine` + Codex で敵対的に潰す（§6）
5. frozen 非接触・observable only を機械証明（§7, §8）
6. 実行は別 task（非 authorize / user GO 後）
7. 結果は会計分離・claim 境界・bounded envelope 付きで報告（§5, §9）
