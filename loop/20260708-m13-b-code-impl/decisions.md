# decisions — M13 B 反復 frozen-context bank (TASK-POST /cross-review 反映)

対象: `loop/20260708-m13-b-code-impl/cross-review-synthesis.md` の統合 MEDIUM/LOW 記録。
H1-H4/M1/M2 は反映済み（本タスクの実装差分）。本ファイルは defer 判断の記録専用。

## M3 — continuity self-scan の narrower guard（code-reviewer、defer）

**指摘**: `tests/test_integration/test_ecl_bank_continuity.py` の continuity self-scan
（§I2/§I6 の decision-record field 非流出ガード）が、共有 `_measurement_guard.py` の
divergence 系識別子 allowlist から一部除外された narrower 版になっている（full guard を
そのまま適用すると本ファイル自身の正当な identifier（例: continuity gate 文脈で使う語）が
false-trip するため）。

**採否**: **defer**。理由 — (a) narrower 化は honest に記載済み（コード中に理由コメントあり、
本 loop で再確認）、(b) B の construction≠measurement 境界は `_bank_spend_guard.py`
（本タスクで H1 全 4 穴を塞いだ）が独立に担保しており、continuity self-scan は追加の
belt-and-suspenders 層であって唯一の防御線ではない、(c) full guard 復元には
divergence 識別子 allowlist 除外 helper の新規実装が要り、本 TASK-POST の H/M スコープ
（merge 前必須 4 HIGH + cheap 2 MEDIUM）を超える。次回 B 系の re-entry（もしあれば）で
再検討する。

## L2 — §I1 字面「retriever 非呼出」vs 実装（store preload）の honest deviation（code-reviewer）

**指摘**: FROZEN ADR `.steering/20260707-m13-b-impl-design/design-final.md` §I1 の字面は
「retriever 非呼出」だが、実装（`bank_fixtures._preload_mirror_memories`）は mirror memory を
`MemoryStore` に preload し、provenance pass 内の untouched cycle が自身の
`retriever.retrieve` を実際に呼び出す（retrieve-count=1×K、`test_ecl_bank_continuity.py::
test_bank_provenance_retrieve_count_one` が独立確認）。

**採否**: **honest deviation として妥当、そのまま維持**。`bank_fixtures.py` 冒頭 docstring
（`_preload_mirror_memories` docstring内）に既に "「retriever 非呼出」（§I1/§I3.1）は
「no result-dependent selection over a large corpus」を意味し、「format_memories を
bypass する」ことではない" という解釈が明記されている。字面の「非呼出」は「result-dependent
selection の不在」の意で、store には mirror memory のみを厳密に preload しているため
retrieval は static pin（result-independent）——ADR の意図（zone-pick-visible prompt cue が
canonical builder 経由で render されること）に忠実。ADR 文言そのものは変更しない
（superseding-ADR 相当の変更ではないため）。本欄は「実装が ADR 文言から一見乖離して見える点」を
明記するための記録のみ。
