"""Base adapter abstract class for model evaluation.

Defines the common interface for querying multimodal and text-only models
with unified input/output contracts.
"""

from abc import ABC, abstractmethod

from sanket.schema import RawResponse, Task


class BaseAdapter(ABC):
    """Abstract base class for all model evaluation adapters."""

    def __init__(self, model_id: str, rpm: int = 10, name: str = "") -> None:
        """Initialize adapter configuration.

        Args:
            model_id: Specific model provider identifier.
            rpm: Requests per minute throttle limit.
            name: Human-friendly adapter name.
        """
        self.model_id = model_id
        self.rpm = rpm
        self.name = name or model_id

    @abstractmethod
    def answer(self, task: Task, mode: str = "image", prompt_version: str = "v1") -> RawResponse:
        """Query model with task prompt and return raw response.

        Args:
            task: Benchmark task instance.
            mode: Evaluation mode ('image' or 'text').
            prompt_version: Prompt version string ('v1').

        Returns:
            RawResponse containing text, latency_s, and metadata.
        """
        raise NotImplementedError("Subclasses must implement answer().")


__all__ = ["BaseAdapter"]
