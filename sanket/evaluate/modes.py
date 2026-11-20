"""Evaluation mode definitions (image mode vs text mode).

Defines execution strategies for vision-language evaluation (image mode)
and text-only baseline evaluation (text mode).
"""

from sanket.schema import EvalMode

MODES: tuple[EvalMode, ...] = ("image", "text")


def validate_mode(mode: str) -> EvalMode:
    """Validate and normalize evaluation mode string.

    Args:
        mode: Raw evaluation mode string ('image' or 'text').

    Returns:
        Canonical EvalMode literal.

    Raises:
        ValueError: If mode is not supported.
    """
    mode_normalized = mode.strip().lower()
    if mode_normalized not in MODES:
        raise ValueError(f"Unsupported evaluation mode '{mode}'. Supported modes: {list(MODES)}")
    return mode_normalized  # type: ignore[return-value]


__all__ = ["MODES", "EvalMode", "validate_mode"]
