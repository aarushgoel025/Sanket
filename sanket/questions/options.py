"""Standardized answer options and ordering for wayfinding questions.

Defines the fixed 10-option answer set (8 octants, CLOSED, NOT_INDICATED)
and enforces invariant option ordering.
"""

from sanket.schema import ANSWER_OPTIONS, Answer


def options_for_task() -> list[str]:
    """Return the fixed wayfinding option set in standard canonical order."""
    return list(ANSWER_OPTIONS)


__all__ = ["ANSWER_OPTIONS", "Answer", "options_for_task"]
