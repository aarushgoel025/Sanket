"""Strict output parser for model responses.

Extracts the selected option from model outputs following the
'ANSWER: <OPTION>' contract. Handles unparseable responses deterministically.
"""

import logging
import re

from sanket.schema import ANSWER_OPTIONS, Answer

logger = logging.getLogger(__name__)

# Canonical map: uppercase with underscores
VALID_OPTIONS_MAP: dict[str, Answer] = {opt: opt for opt in ANSWER_OPTIONS}
# Also support space-separated variants (e.g. 'AHEAD RIGHT' -> 'AHEAD_RIGHT')
for opt in ANSWER_OPTIONS:
    VALID_OPTIONS_MAP[opt.replace("_", " ")] = opt
    VALID_OPTIONS_MAP[opt.replace("_", "-")] = opt

# Regex to match final line: 'ANSWER: <OPTION>'
# Case-insensitive, allowing extra spaces, hyphens, and underscores
ANSWER_PATTERN = re.compile(
    r"^\s*ANSWER\s*:\s*([A-Za-z0-9_\-\s]+?)\s*$",
    re.IGNORECASE,
)


def parse_answer(raw_text: str | None) -> Answer | None:
    """Strictly parse option from the final line of model response text.

    Contract:
    The final non-empty line must match 'ANSWER: <OPTION>' (case-insensitive,
    spaces and underscores permitted). Returns canonical Answer or None.

    Args:
        raw_text: Model response text.

    Returns:
        Canonical Answer option string, or None if unparseable or invalid.
    """
    if not raw_text or not raw_text.strip():
        logger.debug("Empty or whitespace model response; cannot parse answer.")
        return None

    # Get non-empty lines
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not lines:
        return None

    final_line = lines[-1]
    # Strip markdown bolding / formatting asterisks and backticks
    cleaned_line = re.sub(r"[\*`]+", "", final_line).strip()
    match = ANSWER_PATTERN.match(cleaned_line)
    if not match:
        logger.debug("Final line does not match 'ANSWER: <OPTION>': '%s'", final_line)
        return None

    raw_opt = match.group(1).strip()
    # Normalize: replace multiple spaces/dashes with single underscore
    normalized = re.sub(r"[\s\-]+", "_", raw_opt).upper()

    if normalized in VALID_OPTIONS_MAP:
        return VALID_OPTIONS_MAP[normalized]

    logger.debug(
        "Parsed option '%s' (normalized: '%s') is not in valid answer set.",
        raw_opt,
        normalized,
    )
    return None


__all__ = ["parse_answer"]
