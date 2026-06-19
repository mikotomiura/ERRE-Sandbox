# 検証手法ドキュメント体系

> ERRE-Sandbox が**現状で生きて運用している検証手法**を、誰が見ても辿れる形に
> 体系化したもの。個別の `.steering/<task>/` ADR と auto-memory に散在していた
> 検証規律を、再利用可能な単位でまとめ直した。

## このディレクトリの位置づけ

| 置き場所 | 何が入るか |
|---|---|
| **`docs/verification/`** (ここ) | すでに採用し、現状も併せて具体的に活用する予定の検証手法。**結了（terminate）した手法**も、現役規律の由来（over-claim guard の根拠）として「結了・方法論的教訓」節に残す |
| **`.idea/verification/`** | まだ idea 段階で、具体的に活かすか未確定の検証手法（forward 研究候補 / M12+ gated） |

採用未確定の手法が GO 判定を通って実運用に入ったら、`.idea/verification/` から
このディレクトリへ昇格させる運用とする。

## 全体地図

```
新しい検証を始める
        │
        ▼
  00-methodology.md  ← まずここ。全研究 chain に通底する検証規律の核
        │
        ├──▶ 01-swm.md          SWM（主観世界モデル）系の検証手法
        ├──▶ 02-finetuning.md   Fine-Tuning（LoRA / 選好最適化）系の検証手法
        └──▶ 03-erre-overall.md ERRE-Sandbox 全体（メトリクス / 受け入れ / プロセス）
```

| ファイル | いつ読むか |
|---|---|
| [00-methodology.md](00-methodology.md) | **新しい検証を設計するとき最初に読む**。GO/NO-GO の組み方、freeze、null control、verdict 分類、敵対的検証、会計分離など全手法に共通する骨格 |
| [01-swm.md](01-swm.md) | エージェントの主観世界モデル（SWM）・個体化・carry 効果を測りたいとき |
| [02-finetuning.md](02-finetuning.md) | LoRA 再学習や選好最適化の妥当性を検証したいとき |
| [03-erre-overall.md](03-erre-overall.md) | 言語スタイル指標・milestone 受け入れ・汚染防御・スケーリング判定など、システム全体の検証をしたいとき |

## 読み方のルール

- **claim 境界を必ず確認する**: 各手法には「ここまでしか主張しない」という
  bounded envelope と caveat が付く。結論だけ抜き出して一般化しない。
- **出典 ADR を辿れる**: 各節は `.steering/<task>/` の ADR を出典として持つ。
  詳細・数値・反証履歴はそちらが正本（このドキュメントは index と要約）。
- **用語は重複定義しない**: ERRE 固有用語（peripatos, chashitsu, 守破離 等）は
  [../glossary.md](../glossary.md) を参照。

## 関連ドキュメント

- [../architecture.md](../architecture.md) — 技術スタック・レイヤー構成・Evidence Layer 実装
- [../functional-design.md](../functional-design.md) — ERRE パイプライン（Extract/Reverify/Reimplement/Express）の意図
- [../glossary.md](../glossary.md) — ユビキタス言語定義
