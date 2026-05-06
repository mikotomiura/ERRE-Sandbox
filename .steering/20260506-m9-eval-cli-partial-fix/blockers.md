# ブロッカー — m9-eval-cli-partial-fix

## 解消済 (本タスクで対応)

### B-1. ME-9 ADR 実装の hand-off に CLI fix 詳細仕様が不足
- **解消**: `cli-fix-and-audit-design.md` を起点に Plan mode + 案 A/B/C 比較で
  採用案 A' を確定、Codex review (Verdict: Adopt-with-changes) で HIGH 2 /
  MEDIUM 4 / LOW 3 を反映済 (`decisions.md`)。
- **2026-05-06**: 全 tests PASS、ruff / mypy clean。

## 持ち越し (本タスク外)

### D-1. `g-gear-p3-launch-prompt-v2.md` の本格起票
- 本 PR では launch prompt §Phase 3 (audit step) のみ新 contract に書き換え。
  §Phase 1 (stimulus) / §Phase 2 (natural、wall budget / parallel 戦略) /
  §empirical 工数推計 は ME-9 ADR の run1 calibration 結果が出てから v2 として
  起票する (Mac セッションで実施予定)。
- **defer 理由**: run1 calibration 自体が本タスク外 (CLI 整備のみがスコープ)、
  empirical wall budget が確定するまで Phase 1/2 改訂は推測に頼ることになる。

### D-2. `docs/development-guidelines.md` の CLI return-code 規約節
- 本 PR で `eval_run_golden` の return 0/2/3、`eval_audit` の 0/4/5/6 を
  spec として確定。development-guidelines.md にも transverse な規約として
  追記すべき (他 CLI の return code policy と整合させる)。
- **defer 理由**: 本 PR の scope は m9-eval 系のみ。他 CLI
  (`baseline_metrics` / `scaling_metrics` / `export_log`) の return code は
  既に 0/2 慣習が確立しており、横断 audit gate のような構造は無い。
  development-guidelines.md 追記は CLI 全体を横断する次タスクで扱う。

### D-3. M9-B `event_log` 追加時の sidecar schema 進化
- 本 PR の `SidecarV1.model_config = ConfigDict(extra="allow")` は M9-B の
  `event_log` field 追加を additive で許容する設計 (Codex Q2)。
- **defer 理由**: `event_log` の正式 schema は M9-B / M10 の audit-trail 要求
  が確定してから v2 (`SidecarV2`) として起票する。現時点では未要件。

### D-5. sidecar `duckdb_path` 絶対パス → 公開時 redact (Security MEDIUM-Sec2)
- 本 PR の `SidecarV1.duckdb_path` は `final_path.resolve()` 結果 (絶対 path)
  を文字列で記録。OSF / supplementary に sidecar を含めて配布する場合、
  `/Users/<username>/...` がそのまま漏洩する。
- **defer 理由**: 本 CLI は local artefact 用の audit gate であり、配布前の
  sidecar redact は publish-time tooling (現状未実装) で対応すべき。
  本 CLI に redact を組み込むと、運用上 audit 中の絶対 path 検証ができなくなる。
- **対応案**: M9 後の release-tooling 起票時に `scripts/sidecar_redact.py`
  を新設、`duckdb_path` を `<duckdb_basename>` に置換、`captured_at` の精度
  落とし (秒 → 日)、必要に応じて `git_sha` 削除。

### D-6. `eval_audit --report-json` の `--strict` flag (Security MEDIUM-Sec3)
- 本 PR は training-ish path への `--report-json` 出力で stderr warn する
  だけで refuse はしない (Codex M3 の意図的設計)。
- **defer 理由**: M3 採用根拠どおり、operator が non-conventional path に
  opt-in できる柔軟性を維持したい。
- **対応案**: 運用上 typo 起因の training corpus 混入が観測されたら
  `--strict` flag を追加 (training-ish path で refuse + non-zero exit)。

### D-4. partial diagnostic 運用の `data/eval/partial/` 隔離
- launch prompt §Phase 3 で `--allow-partial` 経由の diagnostic mode を documented
  したが、`data/eval/partial/` への自動隔離は未実装。CLI 側は `--output` 任意。
- **defer 理由**: 隔離自体は launch prompt の運用ルールで担えるため CLI 側に
  refactor は不要。M9-B での diagnostic 強化時に再評価。

## 監視中 (まだ起票されていない潜在課題)

### W-1. `_RUNTIME_DRAIN_GRACE_S = 60.0` の empirical 妥当性
- Codex M2 で 30 → 60s に引き上げたが、cognition tick が 120s/tick より長い
  ケース (大型 model / loaded VRAM) では再 false fatal リスク。
- **観測点**: Phase 2 run1 calibration で `runtime_drain_timeout=true` の
  sidecar 件数を計測。10% 以上なら 90s 検討。

### W-2. `--force-rescue` が運用で過剰に使われるリスク
- 壊れた sidecar の rescue が cheap になると、operator が手抜きで使う傾向。
  本来 sidecar 破損は inotify で気付くべき低頻度事象。
- **観測点**: `--force-rescue` の使用回数を運用ログで monitor、月 1 回以上
  なら sidecar 破損の root cause を再調査。
