# 重要な設計判断 — PR-4 kant_r8_v4 DA-14 rerun verdict (local-path load)

> 本 file は本 PR セッション固有の設計判断を記録する。横断 ADR は
> `.steering/20260513-m9-c-adopt/decisions.md`、kant Plan B 順序判断は
> `.steering/20260517-m9-c-adopt-da16-design/decisions.md` DA16-1〜
> DA16-4、PR-3 forensic JSON commit 判断は `.steering/20260517-m9-c-
> adopt-pr3-kant-r8-v4-retrain/decisions.md` DP3-1 を参照。

## 本 PR の設計判断ポリシー

本 PR-4 は既存 pipeline (v3 で確立した SGLang launch + eval-sequence +
post-eval pipeline) の adapter 識別子 / checkpoint path / 出力 path
差し替えのみで、**新規設計判断は基本的に発生しない**。

verdict 結果が borderline (例: 4-of-4 PASS but encoder 1 で direction
discipline FAIL、または encoder agreement 1-of-3 primary のみ pass) 等の
特殊 case で局所判断が発生した場合のみ、本 file に DP4-* として追記する。

## (将来追加する場合の番号予約)

- DP4-1: verdict 結果 borderline 時の ADOPT/REJECT 判定根拠 (未発生)
- DP4-2: SGLang launch で v3 と異なる挙動が観測された場合の対処 (未発生)
- DP4-3: post-eval pipeline の特定 step で v3 と異なる failure mode が
  出た場合の対処 (未発生)
