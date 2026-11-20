"""OpenAI-compatible model adapter for OpenRouter, Groq, and standard APIs.

Sends chat completions requests with base64 encoded images for vision tasks.
Reads credentials strictly from the environment.
"""

import base64
import logging
import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

from sanket.evaluate.adapters.base import BaseAdapter
from sanket.evaluate.prompts import build_prompt
from sanket.schema import RawResponse, Task

logger = logging.getLogger(__name__)


class OpenAICompatAdapter(BaseAdapter):
    """Adapter querying OpenAI-compatible endpoints (e.g. OpenRouter)."""

    def __init__(
        self,
        model_id: str,
        base_url: str = "https://openrouter.ai/api/v1",
        rpm: int = 10,
        name: str = "openai_compat",
        api_key: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        """Initialize OpenAI-compatible adapter.

        Args:
            model_id: Model identifier (e.g. 'anthropic/claude-3.5-sonnet').
            base_url: API base URL.
            rpm: Requests per minute throttle limit.
            name: Model name.
            api_key: Optional explicit API key.
            timeout: HTTP request timeout in seconds.
        """
        super().__init__(model_id=model_id, rpm=rpm, name=name)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        load_dotenv()
        self._api_key = (
            api_key or os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
        )

    def _get_api_key(self) -> str:
        """Retrieve API key from instance or environment."""
        if not self._api_key:
            load_dotenv()
            self._api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not self._api_key:
            raise ValueError(
                "API key not set for OpenAI-compatible endpoint. "
                "Set OPENROUTER_API_KEY or OPENAI_API_KEY in environment."
            )
        return self._api_key

    def answer(self, task: Task, mode: str = "image", prompt_version: str = "v1") -> RawResponse:
        """Query OpenAI-compatible endpoint with multimodal or text payload.

        Args:
            task: Benchmark task instance.
            mode: Evaluation mode ('image' or 'text').
            prompt_version: Prompt version string ('v1').

        Returns:
            RawResponse containing reply text and execution latency.
        """
        key = self._get_api_key()
        prompt_text = build_prompt(task, mode=mode, version=prompt_version)

        if mode == "image":
            img_path = Path(task.image_path)
            if not img_path.exists():
                candidate = Path("data/real_photos") / img_path
                if candidate.exists():
                    img_path = candidate
                else:
                    candidate2 = Path("data/real_photos/images") / img_path.name
                    if candidate2.exists():
                        img_path = candidate2
            if not img_path.exists():
                raise FileNotFoundError(f"Image not found at {task.image_path}")
            b64_image = base64.b64encode(img_path.read_bytes()).decode("utf-8")
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64_image}"},
                        },
                    ],
                }
            ]
        else:
            messages = [{"role": "user", "content": prompt_text}]

        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_id,
            "messages": messages,
            "temperature": 0.0,
        }

        endpoint = f"{self.base_url}/chat/completions"
        t0 = time.perf_counter()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(endpoint, json=payload, headers=headers)
                latency = time.perf_counter() - t0

                if resp.status_code == 429:
                    raise RuntimeError(f"Rate limited (429): {resp.text}")
                resp.raise_for_status()

                data = resp.json()
                reply_text = data["choices"][0]["message"]["content"] or ""
        except Exception as exc:
            latency = time.perf_counter() - t0
            logger.error(
                "OpenAI-compatible query failed for model '%s', task '%s': %s",
                self.model_id,
                task.task_id,
                exc,
            )
            raise

        return RawResponse(
            text=reply_text,
            latency_s=round(latency, 3),
            meta={
                "model_id": self.model_id,
                "mode": mode,
                "prompt_version": prompt_version,
            },
        )


__all__ = ["OpenAICompatAdapter"]
