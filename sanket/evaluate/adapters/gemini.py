"""Google Gemini API model adapter using google-genai SDK.

Connects to Gemini multimodal models with image and text query support.
Keys read strictly from environment via python-dotenv.
"""

import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image

from sanket.evaluate.adapters.base import BaseAdapter
from sanket.evaluate.prompts import build_prompt
from sanket.schema import RawResponse, Task

logger = logging.getLogger(__name__)


class GeminiAdapter(BaseAdapter):
    """Google Gemini model evaluation adapter."""

    def __init__(
        self,
        model_id: str = "gemini-2.5-flash",
        rpm: int = 10,
        name: str = "gemini_flash",
        api_key: str | None = None,
    ) -> None:
        """Initialize Gemini adapter.

        Args:
            model_id: Gemini model identifier.
            rpm: Requests per minute throttle limit.
            name: Model name.
            api_key: Optional explicit API key (defaults to GEMINI_API_KEY from environment).
        """
        super().__init__(model_id=model_id, rpm=rpm, name=name)
        load_dotenv()
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY")

    def _get_client(self):
        """Lazy initialization of google-genai Client."""
        if not self._api_key:
            load_dotenv()
            self._api_key = os.environ.get("GEMINI_API_KEY")
        if not self._api_key:
            raise ValueError(
                "GEMINI_API_KEY environment variable not set. Add it to .env or environment."
            )
        from google import genai

        return genai.Client(api_key=self._api_key)

    def answer(self, task: Task, mode: str = "image", prompt_version: str = "v1") -> RawResponse:
        """Query Gemini with multimodal or text prompt.

        Args:
            task: Benchmark task instance.
            mode: Evaluation mode ('image' or 'text').
            prompt_version: Prompt version string ('v1').

        Returns:
            RawResponse containing reply text and execution latency.
        """
        client = self._get_client()
        prompt_text = build_prompt(task, mode=mode, version=prompt_version)

        contents = []
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
            img = Image.open(img_path)
            contents.append(img)
            contents.append(prompt_text)
        else:
            contents.append(prompt_text)

        t0 = time.perf_counter()
        try:
            response = client.models.generate_content(model=self.model_id, contents=contents)
            latency = time.perf_counter() - t0
            reply_text = response.text or ""
        except Exception as exc:
            latency = time.perf_counter() - t0
            logger.error(
                "Gemini query failed for model '%s', task '%s': %s",
                self.model_id,
                task.task_id,
                exc,
            )
            raise

        return RawResponse(
            text=reply_text,
            latency_s=round(latency, 3),
            meta={"model_id": self.model_id, "mode": mode, "prompt_version": prompt_version},
        )


__all__ = ["GeminiAdapter"]
