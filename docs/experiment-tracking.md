# 実験記録・再現性規約

科学的実験は `experiments/<YYYYMMDD>-<exp-name>/` に記録する。再現性の単一の真実源 (SSOT)。

## 本リポジトリにおける 3 系統の責務分離 (重要)

本プロジェクトには既に複数の記録系統が存在する。混ぜないこと:

| 系統 | 置き場所 | 責務 |
|---|---|---|
| **作業記録** | `.steering/<YYYYMMDD>-<task>/` | requirement / design / decisions / blockers / tasklist。**人間の意思決定の記録** (実験データではない) |
| **凍結 verdict apparatus** | `src/erre_sandbox/evidence/**` | 事前登録された測定器・定数・verdict ロジック。**コードとして凍結**され touch 禁止 (例: `es2_replay/`, `tier_a/`)。再現の **実装** |
| **実験ログ (本規約の対象)** | `experiments/<YYYYMMDD>-<exp-name>/` | 1 回の実験 run の config / seed / 環境 / 生成物 / metrics / 所感。**再現の起点と証跡** |

> 原則: apparatus (どう測るか) は `src/.../evidence/` に凍結、run (いつ何を測ったか) は
> `experiments/` に記録、判断 (なぜそうしたか) は `.steering/` に残す。

## ディレクトリ規約

```
experiments/<YYYYMMDD>-<exp-name>/
  config.(yaml|json)  — 全ハイパーパラメータ
  SEED                — 乱数 seed (固定)
  data.md             — データの version / hash (DVC / git-lfs / 直接 hash)
  env.md              — 環境固定 (lockfile 参照: uv.lock / pyproject.toml)
  run.sh              — 実行コマンド (再現の起点)
  results/            — 生成物
  metrics.json        — 主要指標
  notes.md            — 所感・逸脱・気づき
  # notes.md に必須記載:
  #   検証する仮説: research-positioning.md §5 の H? へのリンク
  #   借用した手法/apparatus: src/erre_sandbox/evidence/... または [n] (references.md)
```

## 再現性チェックリスト

- [ ] seed を固定したか
- [ ] データを version 管理 (hash 等) したか
- [ ] 環境を lockfile (uv.lock) で固定したか
- [ ] 1 コマンドで再走できるか (run.sh / scripts/repro.sh)
- [ ] 結果が research-positioning.md の主張 (§5 仮説) と対応づいているか
- [ ] 使用した凍結 apparatus を touch していないか (`src/.../evidence/` 不変性)

## scripts/repro.sh の方針

代表実験を 1 コマンドで再走できるエントリポイントを置く (中身はプロジェクトに応じて実装)。
既存の verdict run スクリプト (例: `scripts/es2_verdict_run.py`) は実験単位の run.sh から
呼ばれる再現起点になりうる。

## pre-push CI parity との関係

実験コードが `src/` を変更する場合は、push 前に `pwsh scripts/dev/pre-push-check.ps1`
(ruff format --check / ruff check / mypy src / pytest) を CI 等価で local 実行する
(`feedback_pre_push_ci_parity` 参照)。実験の再現性と CI parity は別軸だが両方必須。
