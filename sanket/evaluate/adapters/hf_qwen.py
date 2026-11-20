"""Hugging Face / Qwen-VL open weights model adapter.

Supports either calling hosted Hugging Face Inference endpoints or importing
offline evaluation predictions produced by scripts/colab_qwen.py.
"""

import json
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

DEFAULT_PREDICTIONS_PATH = Path("data/cache/qwen_predictions.jsonl")


class HFQwenAdapter(BaseAdapter):
    """Adapter for Qwen-VL models via Hugging Face API or offline JSONL predictions."""

    def __init__(
        self,
        model_id: str = "Qwen/Qwen2-VL-7B-Instruct",
        rpm: int = 10,
        name: str = "qwen_vl",
        predictions_path: Path | str | None = None,
        hf_token: str | None = None,
        endpoint_url: str | None = None,
    ) -> None:
        """Initialize Hugging Face Qwen-VL adapter.

        Args:
            model_id: Hugging Face model repository ID.
            rpm: Requests per minute throttle limit.
            name: Model name.
            predictions_path: Optional path to imported predictions JSONL.
            hf_token: Optional Hugging Face access token.
            endpoint_url: Optional dedicated HF Inference Endpoint URL.
        """
        super().__init__(model_id=model_id, rpm=rpm, name=name)
        load_dotenv()
        self.hf_token = hf_token or os.environ.get("HF_TOKEN")
        self.endpoint_url = endpoint_url
        self.predictions_path = (
            Path(predictions_path)
            if predictions_path
            else (DEFAULT_PREDICTIONS_PATH if DEFAULT_PREDICTIONS_PATH.exists() else None)
        )
        self._predictions: dict[tuple[str, str], RawResponse] = {}
        if self.predictions_path and self.predictions_path.exists():
            self._load_predictions(self.predictions_path)

    def _load_predictions(self, path: Path) -> None:
        """Load offline prediction results from JSONL file."""
        logger.info("Loading offline Qwen predictions from %s", path)
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)
                task_id = data["task_id"]
                mode = data.get("mode", "image")
                text = data.get("text", "")
                latency = data.get("latency_s", 0.0)
                meta = data.get("meta", {})
                self._predictions[(task_id, mode)] = RawResponse(
                    text=text, latency_s=latency, meta=meta
                )

    def answer(self, task: Task, mode: str = "image", prompt_version: str = "v1") -> RawResponse:
        """Query Qwen-VL using offline predictions or Hugging Face API.

        Args:
            task: Benchmark task instance.
            mode: Evaluation mode ('image' or 'text').
            prompt_version: Prompt version string ('v1').

        Returns:
            RawResponse containing reply text and execution latency.
        """
        # 1. Check loaded offline predictions first
        key = (task.task_id, mode)
        if key in self._predictions:
            return self._predictions[key]

        # 2. Query Hugging Face endpoint if token/URL available
        if not self.hf_token and not self.endpoint_url:
            raise ValueError(
                f"No offline prediction found for task '{task.task_id}' ({mode}) "
                "and no HF_TOKEN or endpoint_url configured for HFQwenAdapter."
            )

        prompt_text = build_prompt(task, mode=mode, version=prompt_version)
        url = self.endpoint_url or f"https://api-inference.huggingface.co/models/{self.model_id}"
        headers = {
            "Authorization": f"Bearer {self.hf_token}",
            "Content-Type": "application/json",
        }
        payload = {"inputs": prompt_text}

        t0 = time.perf_counter()
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            latency = time.perf_counter() - t0
            if resp.status_code == 429:
                raise RuntimeError(f"Hugging Face rate limited (429): {resp.text}")
            resp.raise_for_status()

            data = resp.json()
            if isinstance(data, list) and len(data) > 0 and "generated_text" in data[0]:
                reply_text = data[0]["generated_text"]
            elif isinstance(data, dict) and "generated_text" in data:
                reply_text = data["generated_text"]
            else:
                reply_text = str(data)

        return RawResponse(
            text=reply_text,
            latency_s=round(latency, 3),
            meta={
                "model_id": self.model_id,
                "mode": mode,
                "prompt_version": prompt_version,
            },
        )


__all__ = ["DEFAULT_PREDICTIONS_PATH", "HFQwenAdapter"]
