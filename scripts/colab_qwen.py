"""Standalone evaluation script for Qwen-VL on Google Colab or Kaggle GPU.

Loads benchmark tasks from tasks.jsonl, runs open-weights Qwen-VL model inference,
and exports results to a predictions JSONL file that can be loaded by HFQwenAdapter.

Usage on Colab/Kaggle:
    pip install transformers accelerate qwen-vl-utils torch torchvision
    python scripts/colab_qwen.py --tasks tasks.jsonl --out qwen_predictions.jsonl
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_qwen_inference(
    tasks_path: Path,
    out_path: Path,
    model_name: str = "Qwen/Qwen2-VL-7B-Instruct",
    modes: tuple[str, ...] = ("image", "text"),
    limit: int | None = None,
) -> None:
    """Run Qwen-VL inference across benchmark tasks and save predictions JSONL.

    Args:
        tasks_path: Path to input tasks.jsonl file.
        out_path: Destination path for output predictions JSONL.
        model_name: Hugging Face model repository identifier.
        modes: Evaluation modes to run ('image', 'text').
        limit: Optional limit on number of tasks.
    """
    try:
        import torch
        from PIL import Image
        from transformers import AutoProcessor, Qwen2VLForConditionalGeneration
    except ImportError:
        logger.error(
            "Transformers and Torch must be installed to run colab_qwen.py.\n"
            "Run: pip install transformers accelerate qwen-vl-utils torch torchvision"
        )
        sys.exit(1)

    logger.info("Loading model '%s' onto GPU/CPU...", model_name)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = Qwen2VLForConditionalGeneration.from_pretrained(
        model_name,
        torch_dtype=torch.bfloat16 if device == "cuda" else torch.float32,
        device_map="auto" if device == "cuda" else None,
    )
    processor = AutoProcessor.from_pretrained(model_name)

    tasks = []
    with open(tasks_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                tasks.append(json.loads(line))

    if limit is not None:
        tasks = tasks[:limit]

    logger.info("Evaluating %d tasks across modes: %s", len(tasks), modes)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as out_f:
        for idx, task in enumerate(tasks):
            task_id = task["task_id"]
            question = task["question"]
            options_str = ", ".join(task["options"])

            for mode in modes:
                t0 = time.perf_counter()
                if mode == "image":
                    prompt_text = (
                        "You are looking at a signboard. Answer the question using only the board.\n"
                        f"Question: {question}\n"
                        f"Options: {options_str}\n"
                        "Reply with exactly one line: ANSWER: <OPTION>"
                    )
                    image = Image.open(task["image_path"]).convert("RGB")
                    messages = [
                        {
                            "role": "user",
                            "content": [
                                {"type": "image", "image": image},
                                {"type": "text", "text": prompt_text},
                            ],
                        }
                    ]
                else:
                    prompt_text = (
                        "You are looking at a signboard.\n"
                        f"Question: {question}\n"
                        f"Options: {options_str}\n"
                        "Reply with exactly one line: ANSWER: <OPTION>"
                    )
                    messages = [
                        {
                            "role": "user",
                            "content": [{"type": "text", "text": prompt_text}],
                        }
                    ]

                text = processor.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True
                )
                if mode == "image":
                    inputs = processor(
                        text=[text],
                        images=[image],
                        padding=True,
                        return_tensors="pt",
                    )
                else:
                    inputs = processor(
                        text=[text],
                        padding=True,
                        return_tensors="pt",
                    )
                inputs = inputs.to(device)

                with torch.no_grad():
                    generated_ids = model.generate(**inputs, max_new_tokens=64)
                    generated_ids_trimmed = [
                        out_ids[len(in_ids) :]
                        for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
                    ]
                    output_text = processor.batch_decode(
                        generated_ids_trimmed,
                        skip_special_tokens=True,
                        clean_up_tokenization_spaces=False,
                    )[0]

                latency = round(time.perf_counter() - t0, 3)
                record = {
                    "task_id": task_id,
                    "mode": mode,
                    "text": output_text.strip(),
                    "latency_s": latency,
                    "meta": {"model": model_name},
                }
                out_f.write(json.dumps(record) + "\n")
                out_f.flush()

            if (idx + 1) % 10 == 0 or (idx + 1) == len(tasks):
                logger.info("Completed %d / %d tasks", idx + 1, len(tasks))

    logger.info("Exported predictions to %s", out_path)


def main() -> None:
    """CLI entrypoint for standalone script."""
    parser = argparse.ArgumentParser(description="Evaluate Qwen-VL on Colab/Kaggle")
    parser.add_argument("--tasks", type=Path, default=Path("tasks.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("qwen_predictions.jsonl"))
    parser.add_argument("--model", type=str, default="Qwen/Qwen2-VL-7B-Instruct")
    parser.add_argument("--modes", type=str, default="image,text")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    modes = tuple(m.strip() for m in args.modes.split(",") if m.strip())
    run_qwen_inference(
        tasks_path=args.tasks,
        out_path=args.out,
        model_name=args.model,
        modes=modes,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
