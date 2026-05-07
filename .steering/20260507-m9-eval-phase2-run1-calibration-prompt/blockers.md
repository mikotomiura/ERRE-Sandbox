# ブロッカー — m9-eval-phase2-run1-calibration-prompt

## 解消済 (本タスクで対応)

### B-1. v1 prompt の §Phase 1/2 が run0 incident 元凶のまま

- **解消**: `g-gear-p3-launch-prompt-v2.md` を新設、§Phase 0/A/B/C/D/E + 結果
  解析 + ブロッカー予測の 9 章構成で起票。Codex 7 回目 review (HIGH 3 / MEDIUM
  3 / LOW 1) を全反映。v1 冒頭に v2 リンクを追記。

### B-2. PR #140 反映後の stimulus `cycle_count=3` で fatal 化

- **解消**: Codex H1 で発覚 (kant/nietzsche/rikyu battery total_focal=264)。v2
  prompt §Phase B で `cycle_count=6` を default 化 (focal≈504、target 500
  クリア)。

## 持ち越し (本タスク外、後続 G-GEAR / Mac セッションで対応)

### D-1. run1 calibration 自体の実走

- 本タスクは **prompt 起票のみ**、実走は次の G-GEAR セッション
- 起動条件: PR (本タスク) merge 後、main 同期完了 + `git checkout main`
- 想定所要: kant 1 cell × 5 wall = 1800 min ≈ 30h、overnight×2

### D-2. run2-4 production 採取 + run0 再採取

- §Phase A 結果 (focal_per_min_observed) から wall budget 確定 → §Phase C 実行
- 想定所要: 24-48h (wall budget 次第)、kant drain timeout fallback あり

### D-3. p3_decide.py の Mac 側再実行

- production 30 cell + calibration 5 cell の rsync 受信後
- target ratio (Burrows / MATTR) 確定、ME-4 stage 3 close 候補

### D-4. ME-9 re-open trigger 該当時の child ADR 起票

- run1 で focal/min ≤ 0.92 (≤55/h) または ≥ 1.33 (≥80/h) 観測時
- v2 prompt §ブロッカー予測 B-1 の C 案に従い `/start-task
  m9-eval-cooldown-readjust-adr` を起票、Codex `gpt-5.5 xhigh` review で
  再評価
- 720 強行 (旧案 A) は禁止、trigger を空文化するため

### D-5. 3-parallel calibration cell 追加 (contention_factor 再校正)

- 本案では `contention_factor=1.76` を **固定仮定** (Codex M3、Q1 採用 A)
- 後続で empirical 再校正したい場合、kant + nietzsche + rikyu × 1 wall (例:
  600 min) を追加 calibration として実行 (run_idx=110..112) する option
- defer 理由: ADR 改訂 + 追加 wall 30h = +1day cost、本案で十分機能
- **trigger**: contention factor 仮定の妥当性に疑念が生じた場合 (例: run1
  observed が 1.5/min 等で予想 1.87 と乖離)

### D-6. CLI snapshot (`--snapshot-at-min`) 実装

- 本案では ADR 文言「single 600 min cell + intermediate samples」を **endpoint
  sweep で代替** (M1 採用)
- CLI `--snapshot-at-min 120,240,360,480` を追加すれば 1 cell で連続観測可能
  (memory growth の時系列を取れる)
- defer 理由: 別 PR で実装、本タスクは prompt 起票のみ
- **trigger**: memory growth の時系列観測が後続研究で要求された場合

### D-7. v1 prompt の `g-gear-p3-launch-prompt.md` の本格廃止

- 本案では v1 を冒頭注記で「legacy reference」化、本文は無傷
- 完全削除は github main から history を消す副作用 (rendered context 喪失)
- defer 理由: history archeology の価値を失う、git log だけだと旧運用の
  rendered context が読めない
- **trigger**: 半年以上参照ゼロ + git log で run0 incident 経緯が十分追える
  と判断時

### D-8. `.gitignore` に calibration / partial DuckDB の明示 ignore 追加

- 本案では v2 prompt §Phase 0 / §Phase A の前置きで「calibration 出力は
  commit しない、`git status` で確認」と注記
- `.gitignore` への `data/eval/calibration/` / `data/eval/partial/` 追加は
  別 PR
- defer 理由: cheap follow-up、本 PR の scope 外

## 監視中 (まだ起票されていない潜在課題)

### W-1. run1 calibration の単調性検査

- 5 wall endpoint で focal_per_min が wall 順に大きく変動する場合 (例:
  120 min で 2.1/min、600 min で 1.5/min)、cognition の memory growth が
  rate を低下させている可能性
- **観測点**: §Phase A.2 sidecar 検証時に focal_observed / wall を時系列で
  記録、傾向確認

### W-2. 3-parallel contention factor の wall 依存性

- contention_factor=1.76 は run0 (wall=360) 観測値。wall=600 等の longer run で
  factor が変動する可能性 (memory pressure 累積)
- **観測点**: Phase C 実行時に focal_per_min_parallel を記録、§Phase A
  predicted (1.06/min) との差を monitor
