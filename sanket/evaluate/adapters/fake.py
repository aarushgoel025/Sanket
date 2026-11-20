"""Synthetic fake adapters for hermetic testing.

Provides OracleAdapter (returns gold), RandomAdapter (seeded random options),
and AlwaysAdapter (fixed choice) for zero-network testing.
"""

from typing import Any

import numpy as np

from sanket.evaluate.adapters.base import BaseAdapter
from sanket.schema import ANSWER_OPTIONS, RawResponse, Task
from sanket.verify.blind_test import FakeBlindAdapter


class OracleAdapter(BaseAdapter):
    """Adapter that returns the gold answer for testing."""

    def __init__(self, rpm: int = 1000) -> None:
        super().__init__(model_id="oracle", rpm=rpm, name="OracleAdapter")

    def answer(self, task: Task, mode: str = "image", prompt_version: str = "v1") -> RawResponse:
        """Return ground truth answer directly."""
        return RawResponse(
            text=f"ANSWER: {task.gold}",
            latency_s=0.001,
            meta={"model": "oracle", "mode": mode, "prompt_version": prompt_version},
        )

    def predict(self, prompt: str) -> str:
        """Compatibility method for blind test."""
        return "ANSWER: AHEAD"


class AlwaysAdapter(BaseAdapter):
    """Adapter that returns a fixed choice option for testing."""

    def __init__(self, option: str = "AHEAD", rpm: int = 1000) -> None:
        super().__init__(
            model_id=f"always_{option.lower()}",
            rpm=rpm,
            name=f"AlwaysAdapter({option})",
        )
        self.choice = option.strip().upper()

    def answer(self, task: Task, mode: str = "image", prompt_version: str = "v1") -> RawResponse:
        """Return fixed choice answer."""
        return RawResponse(
            text=f"ANSWER: {self.choice}",
            latency_s=0.001,
            meta={
                "model": self.model_id,
                "mode": mode,
                "prompt_version": prompt_version,
            },
        )

    def predict(self, prompt: str) -> str:
        """Compatibility method for blind test."""
        return f"ANSWER: {self.choice}"


class RandomAdapter(BaseAdapter):
    """Adapter that randomly selects options using a seeded generator."""

    def __init__(self, seed: int = 42, rpm: int = 1000) -> None:
        super().__init__(model_id="random", rpm=rpm, name="RandomAdapter")
        self.seed = seed
        self.rng = np.random.default_rng(seed)

    def answer(self, task: Task, mode: str = "image", prompt_version: str = "v1") -> RawResponse:
        """Return randomly sampled option."""
        idx = int(self.rng.integers(0, len(ANSWER_OPTIONS)))
        chosen = ANSWER_OPTIONS[idx]
        return RawResponse(
            text=f"ANSWER: {chosen}",
            latency_s=0.001,
            meta={"model": "random", "mode": mode, "prompt_version": prompt_version},
        )

    def predict(self, prompt: str) -> str:
        """Compatibility method for blind test."""
        idx = int(self.rng.integers(0, len(ANSWER_OPTIONS)))
        return f"ANSWER: {ANSWER_OPTIONS[idx]}"


def make_fake_adapter(mode: str = "random", **kwargs: Any) -> BaseAdapter:
    """Factory creating a synthetic test adapter."""
    if mode == "oracle":
        return OracleAdapter(**kwargs)
    if mode in ("always", "fixed"):
        opt = kwargs.get("option") or kwargs.get("choice") or "AHEAD"
        return AlwaysAdapter(option=opt)
    seed = kwargs.get("seed", 42)
    return RandomAdapter(seed=seed)


__all__ = [
    "AlwaysAdapter",
    "BaseAdapter",
    "FakeBlindAdapter",
    "OracleAdapter",
    "RandomAdapter",
    "make_fake_adapter",
]
