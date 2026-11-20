"""Unit tests for the strict response parser.

Verifies exact matching of the 'ANSWER: <OPTION>' format, case insensitivity,
space and underscore normalization, markdown bolding, multiline reasoning,
and strict rejection of unparseable or out-of-domain answers.
"""

import pytest

from sanket.evaluate.parser import parse_answer
from sanket.schema import ANSWER_OPTIONS


@pytest.mark.parametrize("option", ANSWER_OPTIONS)
def test_parse_all_canonical_options(option: str) -> None:
    """Every option in ANSWER_OPTIONS must be cleanly parsed when formatted as ANSWER: <OPTION>."""
    raw = f"ANSWER: {option}"
    assert parse_answer(raw) == option


@pytest.mark.parametrize(
    ("raw_input", "expected"),
    [
        # Case variations
        ("answer: ahead", "AHEAD"),
        ("Answer: RIGHT", "RIGHT"),
        ("aNsWeR: closed", "CLOSED"),
        # Spaces and underscores
        ("ANSWER: AHEAD RIGHT", "AHEAD_RIGHT"),
        ("answer: ahead_right", "AHEAD_RIGHT"),
        ("ANSWER: NOT INDICATED", "NOT_INDICATED"),
        ("answer: not_indicated", "NOT_INDICATED"),
        ("ANSWER: back left", "BACK_LEFT"),
        ("ANSWER: back-left", "BACK_LEFT"),
        ("ANSWER: ahead-left", "AHEAD_LEFT"),
        ("ANSWER: back right", "BACK_RIGHT"),
        # Extra whitespace
        ("  ANSWER:   LEFT   ", "LEFT"),
        ("ANSWER:\tBACK\t", "BACK"),
        # Markdown bolding
        ("**ANSWER:** RIGHT", "RIGHT"),
        ("ANSWER: **AHEAD**", "AHEAD"),
        ("**ANSWER: CLOSED**", "CLOSED"),
        ("**Answer**: **NOT_INDICATED**", "NOT_INDICATED"),
        # Multiline responses with reasoning before answer
        (
            "Based on the concourse layout, follow the arrow.\nANSWER: RIGHT",
            "RIGHT",
        ),
        (
            "1. Inspect board\n2. Locate Platform 5\n\n**ANSWER:** AHEAD_RIGHT\n",
            "AHEAD_RIGHT",
        ),
    ],
)
def test_parse_answer_variations(raw_input: str, expected: str) -> None:
    """Parser must robustly handle whitespace, casing, spaces, and markdown."""
    assert parse_answer(raw_input) == expected


@pytest.mark.parametrize(
    "invalid_input",
    [
        "",
        "   ",
        None,
        # Missing ANSWER: prefix
        "The answer is LEFT",
        "AHEAD",
        "CLOSED",
        # Non-standard options
        "ANSWER: UP",
        "ANSWER: DOWN",
        "ANSWER: NORTH",
        "ANSWER: SOUTHEAST",
        "ANSWER: FORWARD",
        "ANSWER: 90 DEGREES",
        # Empty option
        "ANSWER:",
        "ANSWER:   ",
        # Ambiguous / multiple answers
        "ANSWER: AHEAD or RIGHT",
        "ANSWER: LEFT / RIGHT",
        # ANSWER line followed by trailing text
        "ANSWER: LEFT\nHope this helps!",
        "ANSWER: AHEAD\nLet me know if you need more directions.",
    ],
)
def test_parse_answer_invalid_returns_none(invalid_input: str | None) -> None:
    """Strict parser must return None for any invalid, ambiguous, or non-terminal response."""
    assert parse_answer(invalid_input) is None
