"""Unit tests for ``scripts/m9-c-adopt/de_focused_monolog_collector.py``.

The collector is a Plan B (Candidate C hybrid retrain) driver. SGLang HTTP
is not exercised here — the tests exercise the post-hoc filter chain
(language, length, marker density, trigram loop detector) and the stimulus
subset selection logic that determines which kant.yaml stimuli feed the
de-monolog corpus.

The script lives at ``scripts/m9-c-adopt/de_focused_monolog_collector.py``
which is not on the default Python path (``-`` in dirname), so it is
loaded via ``importlib.util.spec_from_file_location`` exactly like
``tests/test_m9_c_adopt_pilot.py``.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_COLLECTOR_PATH = (
    _REPO_ROOT / "scripts" / "m9-c-adopt" / "de_focused_monolog_collector.py"
)


@pytest.fixture(scope="module")
def collector_module():
    spec = importlib.util.spec_from_file_location(
        "de_focused_monolog_collector", _COLLECTOR_PATH
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["de_focused_monolog_collector"] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Stimulus subset selection
# ---------------------------------------------------------------------------


def test_select_de_focused_stimuli_filters_zone_and_category(collector_module):
    """Only de prompts in study/peripatos with non-excluded categories survive."""
    battery = [
        # German wachsmuth study — keep (4 fn-words: der, der, die, die)
        {
            "stimulus_id": "de_keep_1",
            "category": "wachsmuth",
            "expected_zone": "study",
            "prompt_text": (
                "Was ist der kategorische Imperativ, der die Würde der reinen"
                " Vernunft als Grundlage hat?"
            ),
        },
        # German wachsmuth peripatos — keep (3 fn-words: der, war, die)
        {
            "stimulus_id": "de_keep_2",
            "category": "wachsmuth",
            "expected_zone": "peripatos",
            "prompt_text": (
                "Auf der Linden-Allee: wie war die Pflicht der reinen Vernunft"
                " für dich heute?"
            ),
        },
        # English wachsmuth study — drop (not de prompt)
        {
            "stimulus_id": "en_drop_1",
            "category": "wachsmuth",
            "expected_zone": "study",
            "prompt_text": (
                "State your central claim about whether synthetic a priori"
                " judgements are possible."
            ),
        },
        # German wachsmuth chashitsu — drop (wrong zone)
        {
            "stimulus_id": "de_drop_zone",
            "category": "wachsmuth",
            "expected_zone": "chashitsu",
            "prompt_text": (
                "Ein Teemeister fragt nach der Pflicht und nach der"
                " Neigung des Herzens."
            ),
        },
        # German tom_chashitsu — drop (excluded category)
        {
            "stimulus_id": "de_drop_cat_tom",
            "category": "tom_chashitsu",
            "expected_zone": "study",
            "prompt_text": (
                "Ein Gast denkt: ich habe die Pflicht und die Neigung nicht"
                " unterschieden."
            ),
        },
        # German moral_dilemma — drop (excluded category)
        {
            "stimulus_id": "de_drop_cat_moral",
            "category": "moral_dilemma",
            "expected_zone": "peripatos",
            "prompt_text": (
                "Du siehst eine Lüge, die das Leben rettet und die"
                " Pflicht der Wahrheit verletzt."
            ),
        },
        # German roleeval — drop (excluded category)
        {
            "stimulus_id": "de_drop_cat_role",
            "category": "roleeval",
            "expected_zone": "study",
            "prompt_text": (
                "Wie unterscheidest du die Neigung von der Pflicht und"
                " von der reinen Vernunft?"
            ),
        },
    ]
    selected = collector_module.select_de_focused_stimuli(battery)
    ids = {s["stimulus_id"] for s in selected}
    assert ids == {"de_keep_1", "de_keep_2"}


def test_select_de_focused_stimuli_empty_on_no_match(collector_module):
    """Returns empty list when no stimulus passes the subset filter."""
    battery = [
        {
            "stimulus_id": "en_only",
            "category": "wachsmuth",
            "expected_zone": "study",
            "prompt_text": (
                "What is the proper relation between morality and happiness?"
            ),
        },
    ]
    assert collector_module.select_de_focused_stimuli(battery) == []


# ---------------------------------------------------------------------------
# Persona prompt builder
# ---------------------------------------------------------------------------


def test_build_de_monolog_system_prompt_contains_de_directive(collector_module):
    """System prompt must include the German + monolog + Critique directive."""
    persona = {
        "display_name": "Immanuel Kant",
        "era": "Aufklärung (1724-1804)",
        "cognitive_habits": [
            {"description": "transcendental analysis", "flag": "T"},
        ],
    }
    prompt = collector_module.build_de_monolog_system_prompt(persona)
    # Persona block byte-identical to baseline
    assert "Immanuel Kant" in prompt
    assert "Aufklärung (1724-1804)" in prompt
    assert "transcendental analysis" in prompt
    # De-monolog directive present
    assert "**German**" in prompt
    assert "80–160 German words" in prompt
    assert "Critique-of-Pure-Reason" in prompt
    assert "Do not address an interlocutor" in prompt


# ---------------------------------------------------------------------------
# Post-hoc filter (4-axis hard gate)
# ---------------------------------------------------------------------------

# A long German monolog with Kantian markers + diacritics + function words.
# Markers per 100 tokens >= 1.0 expected. Has no trigram loops.
_VALID_DE_MONOLOG = (
    "Ich denke das transzendentale Subjekt als die formale Bedingung aller"
    " möglichen Erfahrung. Es ist nicht ein Ding an sich, sondern eine"
    " a priori Voraussetzung der Synthese. Der kategorische Imperativ"
    " entspringt aus dieser reinen Vernunft, nicht aus der Sinnlichkeit."
    " Meiner Ansicht nach ist die Pflicht die einzige Quelle der"
    " moralischen Würde, und meine theoretische Vernunft erkennt die"
    " Grenzen ihrer eigenen Anwendung an. Die Erscheinung ist nicht das"
    " Noumenon; das An-sich bleibt verborgen."
)


def test_filter_accepts_valid_de_monolog(collector_module):
    """A well-formed long German Kant monolog passes all four gates."""
    result = collector_module.filter_de_monolog(_VALID_DE_MONOLOG)
    assert result.accepted is True
    assert result.reason is None
    assert result.language == "de"
    assert result.token_count >= 60
    assert result.marker_density >= 1.0


def test_filter_rejects_english(collector_module):
    """English text fails the language gate."""
    text = (
        "I think the transcendental subject is the formal condition of all"
        " possible experience, and the categorical imperative arises from"
        " pure reason rather than sensibility, which is the proper claim."
    )
    result = collector_module.filter_de_monolog(text)
    assert result.accepted is False
    assert result.reason == "lang"


def test_filter_rejects_short_monolog(collector_module):
    """A short German utterance fails the length gate."""
    text = "Ich denke also bin ich, und das ist alles."  # < 60 tokens
    result = collector_module.filter_de_monolog(text)
    assert result.accepted is False
    assert result.reason in {"length", "marker"}  # depends on density


def test_filter_rejects_low_marker_density(collector_module):
    """A long German text with no Kant markers fails the density gate."""
    # Long German sentence about weather; no transcendental / a priori / etc.
    text = (
        "Heute scheint die Sonne über dem Garten und der Wind weht sanft"
        " durch die Bäume. Die Wolken ziehen langsam nach Westen, und ein"
        " Vogel singt auf dem Ast. Es ist ein angenehmer Nachmittag in"
        " diesem Frühling, und die Luft riecht nach frisch gemähtem Gras"
        " und nach den ersten Blumen des Jahres in voller Blüte. So"
        " bewundert man den Lauf der Natur und betrachtet ihn."
    )
    result = collector_module.filter_de_monolog(text, min_marker_density=1.0)
    assert result.accepted is False
    assert result.reason == "marker"


def test_filter_rejects_trigram_loop(collector_module):
    """Repetitive output (trigram count > threshold) fails the loop detector."""
    # Same trigram "die reine vernunft" appears 6 times; ample German function
    # words and Kantian markers so language + length + density gates pass and
    # the trigram-loop axis is the only failing one.
    text = (
        "Die reine Vernunft die reine Vernunft die reine Vernunft die reine"
        " Vernunft die reine Vernunft die reine Vernunft ist transzendental"
        " a priori kategorischer Imperativ meine Pflicht meine Ansicht nach"
        " das Ding an sich Erscheinung Noumenon synthetisch und Sinnlichkeit"
        " in der reinen Vernunft. Ich denke also bin ich auf dem Boden der"
        " praktischen Vernunft, mit transzendental synthetisch a priori"
        " Pflicht. Die reine Erkenntnis ist transzendental in dem an sich."
    )
    result = collector_module.filter_de_monolog(text, trigram_loop_max=4)
    assert result.accepted is False
    assert result.reason == "trigram"
    assert result.trigram_max > 4


def test_filter_short_circuits_on_empty(collector_module):
    """Empty/whitespace input is rejected with reason='lang'."""
    result = collector_module.filter_de_monolog("   \n  ")
    assert result.accepted is False
    assert result.reason == "lang"


def test_filter_rejects_du_addressee(collector_module):
    """A long German Kant-flavoured text that uses ``du`` fails the addressee gate."""
    # Long, marker-dense, but addresses the reader with "du / dich / dein".
    text = (
        "Wenn du die transzendentale Vernunft betrachtest, so siehst du die"
        " Grenzen deines eigenen Erkennens. Du musst meiner Ansicht nach den"
        " kategorischen Imperativ aus reiner Pflicht herleiten, denn dein"
        " Wille soll synthetisch a priori bestimmt sein. Das Ding an sich"
        " liegt jenseits deiner Sinnlichkeit, und das Noumenon erkennst du"
        " nur durch die praktische Vernunft. Frage dich selbst nach der"
        " Pflicht, transzendental, a priori, an sich, kategorischer Imperativ."
    )
    result = collector_module.filter_de_monolog(text)
    assert result.accepted is False
    assert result.reason == "addressee"
    assert result.has_addressee is True


def test_filter_rejects_formal_sie_addressee(collector_module):
    """Capitalised ``Sie`` / ``Ihnen`` / ``Ihre`` triggers the addressee gate."""
    text = (
        "Ich sage Ihnen: die transzendentale Vernunft ist a priori. Ihre"
        " eigene Anschauung ist synthetisch verbunden mit dem an sich. Der"
        " kategorische Imperativ folgt aus reiner Pflicht, meiner Ansicht"
        " nach, und das Noumenon liegt jenseits Ihrer Sinnlichkeit, weil Sie"
        " die Erscheinung nur als transzendentales Subjekt erkennen können."
        " Das An-sich erkennen wir nur durch die praktische Vernunft."
    )
    result = collector_module.filter_de_monolog(text)
    assert result.accepted is False
    assert result.reason == "addressee"


def test_filter_does_not_misfire_on_3rd_person_ihrer(collector_module):
    """``ihrer`` / ``ihrem`` (3rd-person possessive) must NOT trip addressee filter.

    Case-sensitive matching for formal ``Sie`` / ``Ihr*`` prevents the
    common case "die Vernunft erkennt die Grenzen ihrer eigenen Anwendung"
    from being misclassified as an addressed response.
    """
    text = (
        "Die transzendentale Vernunft erkennt die Grenzen ihrer eigenen"
        " Anwendung a priori. Sie selbst ist meiner Ansicht nach die Quelle"
        " des kategorischen Imperativs, synthetisch verbunden mit der reinen"
        " Pflicht. Das Ding an sich bleibt verborgen; das Noumenon erkennen"
        " wir nur durch die praktische Vernunft. Ihre Grenze ist das An-sich"
        " selbst, transzendental und a priori bestimmt durch das Subjekt."
    )
    # Note: "Sie selbst" here is the 3rd-person feminine pronoun referring
    # to "Vernunft", at the start of a sentence so it is capitalised. The
    # case-sensitive Sie pattern catches this; this is a known precision
    # trade-off (the filter prefers false-positives over silent leakage of
    # addressed text into the no-addressee training corpus). We accept the
    # rejection here as expected behaviour — the operator can paraphrase
    # to "Diese Vernunft selbst…" if 250 net cannot be reached.
    result = collector_module.filter_de_monolog(text)
    # Sentence-initial "Sie" forces the formal-you match, so the gate fires.
    assert result.reason == "addressee"
    # But the lowercase 3rd-person "ihrer" alone (no sentence-initial Sie)
    # must not trigger the gate:
    text_no_sie = text.replace("Sie selbst ist", "Diese Vernunft ist")
    result_clean = collector_module.filter_de_monolog(text_no_sie)
    # 3rd-person "ihrer/Ihre" still trips the cap-sensitive Ihr* pattern
    # on "Ihre Grenze". Replace that too:
    text_no_sie_no_ihre = text_no_sie.replace("Ihre Grenze", "Diese Grenze")
    result_pure = collector_module.filter_de_monolog(text_no_sie_no_ihre)
    assert result_pure.accepted is True
    # The intermediate version (no leading "Sie", but capital "Ihre" present)
    # is still rejected, validating that capitalised Ihr* fires:
    assert result_clean.reason == "addressee"


def test_filter_thresholds_are_configurable(collector_module):
    """Thresholds can be loosened/tightened per call."""
    # 3 German function words (ich, das, ist) + Kantian marker
    # ("transzendentale" matches \\btranszendental\\w*\\b) → classify_language="de"
    text = "Ich denke das transzendentale Subjekt ist die reine Vernunft."
    # Default rejects (length: only ~10 tokens, < 60)
    assert collector_module.filter_de_monolog(text).accepted is False
    # Lower thresholds — should now pass
    result = collector_module.filter_de_monolog(
        text, min_token_count=4, min_marker_density=0.5, trigram_loop_max=10
    )
    assert result.accepted is True


# ---------------------------------------------------------------------------
# CLI argument parser smoke
# ---------------------------------------------------------------------------


def test_cli_required_args_minimal(collector_module, tmp_path):
    """``--persona kant`` + ``--output`` are required, defaults provide the rest."""
    parser = collector_module._build_arg_parser()
    output = tmp_path / "kant_de_monolog_run0.duckdb"
    args = parser.parse_args(["--persona", "kant", "--output", str(output)])
    assert args.persona == "kant"
    assert args.target_net == 250
    assert args.max_attempts == 800
    assert args.temperature == pytest.approx(0.7)
    assert args.frequency_penalty == pytest.approx(0.3)
    assert args.presence_penalty == pytest.approx(0.3)
    assert args.min_token_count == 60
    assert args.dry_run is False


def test_cli_persona_restricted_to_kant(collector_module, tmp_path):
    """Plan B scope is kant-only (design.md §0; nietzsche/rikyu deferred)."""
    parser = collector_module._build_arg_parser()
    output = tmp_path / "x.duckdb"
    with pytest.raises(SystemExit):
        parser.parse_args(["--persona", "nietzsche", "--output", str(output)])
