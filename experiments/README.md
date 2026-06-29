# experiments/ — 科学的実験ログのルート

ここには 1 回ごとの実験 run を `experiments/<YYYYMMDD>-<exp-name>/` で記録する。
規約の SSOT は `docs/experiment-tracking.md`。

## 他系統との違い (混ぜない)

- `.steering/` … 人間の意思決定の作業記録 (実験データではない)
- `src/erre_sandbox/evidence/**` … 凍結された測定器・verdict apparatus (再現の実装、touch 禁止)
- `experiments/` … **いつ・何を・どの seed/env で測ったか** の run 単位の証跡 (このディレクトリ)

## 各 run の必須構成

`config` / `SEED` / `data.md` / `env.md` / `run.sh` / `results/` / `metrics.json` / `notes.md`。
`notes.md` には検証する仮説 (`research-positioning.md` §5 H?) と借用 apparatus/出典 `[n]` を必ず記す。

実験を回す・記録する作業では `reproducibility-discipline` skill が自動発火する。
