"""parse rule (prereg v2 §4): 入力に現れうる値の各クラスを pin する."""

from __future__ import annotations

import pytest
from scripts.skill_lever_scorer import parse_choice


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # 厳密一致と表記揺れ
        ("read_book", "read_book"),
        ("  walk_path\n", "walk_path"),
        ("Tend_Moss", "tend_moss"),
        ("read book", "read_book"),
        ("read-book", "read_book"),
        ("ｒｅａｄ＿ｂｏｏｋ", "read_book"),  # 全角 (NFKC)
        # 引用符・強調・句読点・括弧
        ('"sit_quiet"', "sit_quiet"),
        ("`rest_eyes`", "rest_eyes"),
        ("**talk_peer**", "talk_peer"),
        ("「walk_path」。", "walk_path"),
        ("walk_path.", "walk_path"),
        # 文中にちょうど 1 種
        ("行動: read_book", "read_book"),
        ("I choose tend_moss because it is windy.", "tend_moss"),
        ("read_book read_book", "read_book"),  # 同じ label の繰り返しは 1 種
        # think ブロック (閉じている) は除去
        ("<think>\nwalk_path?\n</think>\nread_book", "read_book"),
        ("<think></think>sit_quiet", "sit_quiet"),
        ("<THINK>walk_path</THINK>read_book", "read_book"),  # 大文字の tag
    ],
)
def test_accepted(raw: str, expected: str) -> None:
    assert parse_choice(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",  # 空応答
        "   \n\t",  # 空白のみ
        "。",  # 句読点のみ
        "本を読む",  # 日本語訳は label ではない
        "reading",  # 語彙外
        "read_books",  # 単語境界 (英数字が続く)
        "xread_book",
        "read_book or walk_path",  # 2 種以上
        "not read_book, walk_path",
        "<think>read_book",  # 閉じていない think
        "read_book</think>",
        "<think>walk_path</think>",  # 除去後に空
        "<THINK>walk_path</THINK>",  # 大文字の tag (Codex MEDIUM-2)
        "＜think＞walk_path＜/think＞",  # 全角の tag (NFKC で同じ形)
        "<Think>tend_moss",  # 閉じていない (大文字混じり)
    ],
)
def test_bottom(raw: str) -> None:
    assert parse_choice(raw) is None


def test_parse_two_labels_is_bottom() -> None:
    """2 種以上の label を含む応答は先頭を採らず ⊥ (変異 p1 の kill 対象)."""
    assert parse_choice("walk_path then read_book") is None


def test_unclosed_think_is_bottom() -> None:
    """閉じていない think タグは中身の label を採らず ⊥ (変異 p2 の kill 対象)."""
    assert parse_choice("<think>tend_moss") is None
