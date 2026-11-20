"""Blind guessing test filter for benchmark tasks.

Evaluates whether questions can be answered without the visual signage context
(detecting language prior bias). Tasks where a blind model guesses the correct
answer at or above the threshold are rejected with reason 'blind_test_fail'.
"""

import re
from typing import Any, Protocol

import numpy as np

from sanket.schema import ANSWER_OPTIONS, Answer, Task


class BlindAdapter(Protocol):
    """Protocol for model adapters supporting text-only querying."""

    def predict(self, prompt: str) -> str:
        """Query the model with a prompt and return the text output."""
        ...


def format_blind_prompt(question: str, options: list[Answer] | list[str]) -> str:
    """Format prompt for blind testing without image or visual description.

    Args:
        question: Question text naming the destination.
        options: Ordered list of allowed answer choices.

    Returns:
        Formatted prompt string.
    """
    options_str = ", ".join(str(opt) for opt in options)
    return (
        "You are looking at a signboard. Answer the question using only the board.\n"
        f"Question: {question}\n"
        f"Options: {options_str}\n"
        "Reply with exactly one line: ANSWER: <OPTION>"
    )


def parse_blind_answer(raw_reply: str) -> Answer | None:
    """Parse answer choice from raw model response text.

    Args:
        raw_reply: Raw text output from model.

    Returns:
        Parsed Answer option, or None if unparseable.
    """
    if not raw_reply:
        return None

    # First look for standard ANSWER: <OPTION> format
    match = re.search(r"ANSWER:\s*([A-Za-z_]+)", raw_reply, re.IGNORECASE)
    if match:
        candidate = match.group(1).strip().upper()
        if candidate in ANSWER_OPTIONS:
            return candidate  # type: ignore[return-value]

    # Fallback to searching for exact option tokens
    for token in raw_reply.strip().split():
        clean_token = token.strip(".,;:()[]\"'").upper()
        if clean_token in ANSWER_OPTIONS:
            return clean_token  # type: ignore[return-value]

    return None


class FakeBlindAdapter:
    """Synthetic model adapter for deterministic hermetic testing."""

    def __init__(
        self,
        mode: str = "random",
        fixed_choice: str = "AHEAD",
        rng: np.random.Generator | None = None,
        responses: list[str] | None = None,
    ) -> None:
        """Initialize fake adapter.

        Args:
            mode: 'random', 'oracle', 'fixed', or 'sequence'.
            fixed_choice: Choice returned when mode is 'fixed'.
            rng: Seeded random generator for 'random' mode.
            responses: Predefined responses for 'sequence' mode.
        """
        self.mode = mode
        self.fixed_choice = fixed_choice
        self.rng = rng or np.random.default_rng(42)
        self.responses = list(responses) if responses else []
        self._seq_idx = 0
        self.active_gold: str | None = None

    def predict(self, prompt: str) -> str:
        """Generate fake response based on configured mode."""
        if self.mode == "oracle" and self.active_gold is not None:
            return f"ANSWER: {self.active_gold}"
        if self.mode == "fixed":
            return f"ANSWER: {self.fixed_choice}"
        if self.mode == "sequence" and self.responses:
            resp = self.responses[self._seq_idx % len(self.responses)]
            self._seq_idx += 1
            return resp

        # Default random guessing across answer set
        idx = int(self.rng.integers(0, len(ANSWER_OPTIONS)))
        return f"ANSWER: {ANSWER_OPTIONS[idx]}"

    def __call__(self, prompt: str) -> str:
        """Allow calling adapter directly as a function."""
        return self.predict(prompt)


def run_blind_test(
    task: Task,
    adapter: Any,
    samples: int = 3,
    threshold: float = 0.67,
) -> tuple[bool, float, list[str]]:
    """Evaluate task against a blind model to detect language prior guessing bias.

    Args:
        task: Benchmark task to evaluate.
        adapter: Model adapter providing predict(prompt) or callable.
        samples: Number of blind sample queries (default 3).
        threshold: Rejection threshold for guessing accuracy (default 0.67).

    Returns:
        Tuple of (is_passed, correct_rate, raw_sample_replies).
        is_passed is True if task passes (correct_rate < threshold).
        is_passed is False if task fails blind test (correct_rate >= threshold).
    """
    if samples <= 0:
        return True, 0.0, []

    # If adapter is FakeBlindAdapter with oracle mode, set target gold
    if hasattr(adapter, "active_gold"):
        adapter.active_gold = str(task.gold)

    prompt = format_blind_prompt(task.question, task.options)
    replies: list[str] = []
    correct_count = 0

    for _ in range(samples):
        if hasattr(adapter, "predict") and callable(adapter.predict):
            raw = str(adapter.predict(prompt))
        elif hasattr(adapter, "answer") and callable(adapter.answer):
            raw = str(adapter.answer(prompt))
        elif callable(adapter):
            raw = str(adapter(prompt))
        else:
            raise TypeError(f"Adapter {type(adapter)} must provide predict() or be callable.")

        replies.append(raw)
        parsed = parse_blind_answer(raw)
        if parsed == task.gold:
            correct_count += 1

    correct_rate = float(correct_count / samples)
    is_passed = correct_rate < threshold

    # Update receipt audit fields
    task.receipt.blind_correct_rate = round(correct_rate, 4)
    task.receipt.blind_rejected = not is_passed

    return is_passed, round(correct_rate, 4), replies


__all__ = [
    "BlindAdapter",
    "FakeBlindAdapter",
    "format_blind_prompt",
    "parse_blind_answer",
    "run_blind_test",
]
