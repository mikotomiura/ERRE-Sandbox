# ブロッカー記録 — DA-17 ADR (ドイツ語失敗 preflight)

本 ADR 開始時点で既知のブロッカーは無し。

forensic 分析中に新規ブロッカーが発生した場合、本 file に追記する
(発生日時 / 症状 / 試したこと / 原因 / 解決方法 / 教訓 の 6 項目)。

想定される潜在的ブロッカー (発生時の対応方針):

- **langdetect の deterministic 出力差異**: `DetectorFactory.seed=0` を
  `compute_burrows_delta.py:67` と同一設定にしているが、Python version
  / langdetect version 差で稀に出力が変わる。発生時は seed を別値
  (1, 42, 100) で robustness 確認、複数 seed で同 utterance が de 判定
  されるサブセットのみ採用する。

- **DuckDB shard の table 名差異**: schema は `raw_dialog.dialog` を
  想定するが、shard 生成時期によっては別 table 名の可能性あり。発生時
  は `con.execute("SHOW TABLES").fetchall()` で確認。

- **Codex CLI 401 再発**: PR-4 #189 と同 pattern で auth.json refresh
  必要。発生時は PR description に「Codex review は user 再認証後に
  本 PR or follow-up で実施」と defer 明示し、本 ADR の merge は止めない
  (DA-16 PR #186 と同 pattern)。

- **`/reimagine` Skill 起動の混乱**: Plan mode 外での `/reimagine` 起動
  は subagent 経由になる。混乱した場合は手動で別 Plan agent を 1 つ
  起動 + 別 ADR 結論を生成 + 採用案併記 で目的達成可能。
