"""Model adapters package for evaluation.

Provides adapters for Gemini, OpenAI-compatible APIs, Hugging Face / Qwen,
and synthetic test adapters (Oracle, Random, Always).
"""

from sanket.config import ModelProfile
from sanket.evaluate.adapters.base import BaseAdapter
from sanket.evaluate.adapters.fake import (
    AlwaysAdapter,
    FakeBlindAdapter,
    OracleAdapter,
    RandomAdapter,
    make_fake_adapter,
)
from sanket.evaluate.adapters.gemini import GeminiAdapter
from sanket.evaluate.adapters.hf_qwen import HFQwenAdapter
from sanket.evaluate.adapters.openai_compat import OpenAICompatAdapter


def create_adapter(profile: ModelProfile) -> BaseAdapter:
    """Instantiate adapter instance from a configured ModelProfile.

    Args:
        profile: Model profile loaded from models.yaml.

    Returns:
        Configured BaseAdapter instance.

    Raises:
        ValueError: If adapter type is unknown.
    """
    adapter_type = profile.adapter.strip().lower()
    if adapter_type == "gemini":
        return GeminiAdapter(model_id=profile.model_id, rpm=profile.rpm, name=profile.name)
    if adapter_type in ("openai_compat", "openai"):
        base_url = profile.base_url or "https://openrouter.ai/api/v1"
        return OpenAICompatAdapter(
            model_id=profile.model_id,
            base_url=base_url,
            rpm=profile.rpm,
            name=profile.name,
        )
    if adapter_type in ("hf_qwen", "hf", "qwen"):
        return HFQwenAdapter(model_id=profile.model_id, rpm=profile.rpm, name=profile.name)
    if adapter_type == "oracle":
        return OracleAdapter(rpm=profile.rpm)
    if adapter_type == "random":
        return RandomAdapter(rpm=profile.rpm)
    if adapter_type == "always":
        return AlwaysAdapter(option=profile.model_id or "AHEAD", rpm=profile.rpm)

    raise ValueError(
        f"Unknown adapter type '{profile.adapter}' for model profile '{profile.name}'."
    )


__all__ = [
    "AlwaysAdapter",
    "BaseAdapter",
    "FakeBlindAdapter",
    "GeminiAdapter",
    "HFQwenAdapter",
    "OpenAICompatAdapter",
    "OracleAdapter",
    "RandomAdapter",
    "create_adapter",
    "make_fake_adapter",
]
