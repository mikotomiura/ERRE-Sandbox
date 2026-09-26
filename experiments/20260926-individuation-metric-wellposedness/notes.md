# notes — 個性化 door 条件① weight-space seed floor spike

- 事前登録: `prereg.md` (計算前に commit で凍結、sha256 は results.json の `prereg_sha256`)
- 計算: `scripts/individuation_wellposedness.py` (CPU・numpy のみ)
- test: `tests/test_individuation_wellposedness/` (合成行列の陽性/陰性対照・UNDEFINED・判定 rule、判定行の変異試験済)
- 再計算: `bash experiments/20260926-individuation-metric-wellposedness/run.sh`
- ADR 本体はローカル `.steering/20260926-individuation-door-condition1/design.md`
