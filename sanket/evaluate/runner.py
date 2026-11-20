"""Resumable and rate-limited evaluation runner.

Orchestrates model execution over tasks and modes, respecting requests-per-minute
limits, managing exponential backoff retries, and recording results incrementally
to SQLite cache and reports/results.jsonl.
"""

import json
import logging
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from sanket.config import ModelsConfig, load_models_config
from sanket.evaluate.adapters import (
    AlwaysAdapter,
    BaseAdapter,
    OracleAdapter,
    RandomAdapter,
    create_adapter,
)
from sanket.evaluate.cache import ResponseCache, get_cache
from sanket.evaluate.modes import MODES, EvalMode, validate_mode
from sanket.evaluate.parser import parse_answer
from sanket.evaluate.scorer import compute_metrics, score_single
from sanket.schema import EvaluationResult, RawResponse, Task

logger = logging.getLogger(__name__)

DEFAULT_RESULTS_FILE = Path("reports/results.jsonl")


def is_rate_limit_error(exc: BaseException) -> bool:
    """Determine whether an exception represents an API rate limit (HTTP 429 / Quota)."""
    msg = str(exc).lower()
    return (
        "429" in msg
        or "rate limit" in msg
        or "rate_limit" in msg
        or "quota" in msg
        or "resource_exhausted" in msg
        or "resourceexhausted" in msg
        or "too many requests" in msg
    )


def execute_with_retry(
    adapter: BaseAdapter,
    task: Task,
    mode: str,
    prompt_version: str,
    max_retries: int = 3,
    min_wait: float = 2.0,
    max_wait: float = 30.0,
) -> RawResponse:
    """Execute model query with exponential backoff on rate limits."""

    @retry(
        retry=retry_if_exception(is_rate_limit_error),
        wait=wait_exponential(multiplier=1.0, min=min_wait, max=max_wait),
        stop=stop_after_attempt(max_retries),
        reraise=True,
    )
    def _call() -> RawResponse:
        return adapter.answer(task, mode=mode, prompt_version=prompt_version)

    return _call()


def run_evaluation(
    tasks: list[Task] | Path | str | None = None,
    models: list[str] | list[BaseAdapter] | None = None,
    modes: list[str] | None = None,
    prompt_version: str = "v1",
    cache: ResponseCache | None = None,
    results_file: Path | str = DEFAULT_RESULTS_FILE,
    limit: int | None = None,
    max_consecutive_rate_limits: int = 3,
    max_retries: int = 3,
    retry_min_wait: float = 2.0,
    models_config_path: Path | str | None = None,
    default_config_path: Path | str | None = None,
    show_progress: bool = True,
    task_set: str = "synthetic",
) -> tuple[list[EvaluationResult], dict[str, Any]]:
    """Run full evaluation batch across tasks, models, and modes.

    Fully resumable: checks SQLite cache and results JSONL, skipping any
    trial that has already been executed.

    Args:
        tasks: In-memory Task list or path to tasks.jsonl (defaults based on task_set).
        models: Optional list of model names or BaseAdapter instances.
        modes: Evaluation modes (defaults to ['image', 'text'], forced to ['image'] for real).
        prompt_version: Prompt version string ('v1').
        cache: ResponseCache instance.
        results_file: Path to reports/results.jsonl.
        limit: Maximum number of tasks to evaluate.
        max_consecutive_rate_limits: Number of rate-limit failures before aborting.
        models_config_path: Path to models.yaml.
        default_config_path: Path to default.yaml.
        show_progress: Whether to log evaluation progress.
        task_set: Evaluation dataset set: 'synthetic' or 'real'.

    Returns:
        Tuple of (all_results, summary_metrics).

    Raises:
        RuntimeError: If a model hits consecutive rate limit limit.
    """
    results_path = Path(results_file)
    results_path.parent.mkdir(parents=True, exist_ok=True)

    cache_instance = cache or get_cache()

    # Resolve default tasks path if None
    if tasks is None:
        if task_set.lower() == "real":
            real_p = Path("data/real_photos/real_tasks.jsonl")
            tasks = real_p if real_p.exists() else Path("data/real_photos/tasks.jsonl")
        else:
            full_p = Path("data/full_dataset/tasks.jsonl")
            sample_p = Path("data/sample_tasks/tasks.jsonl")
            tasks = full_p if full_p.exists() else sample_p

    # Load tasks
    task_list: list[Task] = []
    if isinstance(tasks, (Path, str)):
        t_path = Path(tasks)
        if not t_path.exists():
            raise FileNotFoundError(f"Tasks file not found: {t_path}")
        with open(t_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    t_dict = json.loads(line)
                    # Resolve relative image paths against task file parent directory
                    raw_img = Path(t_dict.get("image_path", ""))
                    if not raw_img.is_absolute() and not raw_img.exists():
                        candidate = t_path.parent / raw_img
                        if candidate.exists():
                            t_dict["image_path"] = str(candidate)
                        elif (t_path.parent / "images" / raw_img.name).exists():
                            t_dict["image_path"] = str(t_path.parent / "images" / raw_img.name)

                    is_real = task_set.lower() == "real" or str(
                        t_dict.get("task_id", "")
                    ).startswith("R")
                    if is_real:
                        t_dict.setdefault("task_set", "real")
                        t_dict.setdefault("qtype", "REAL")

                    task_list.append(Task.model_validate(t_dict))
    else:
        task_list = list(tasks)
        for t in task_list:
            if task_set.lower() == "real" or str(t.task_id).startswith("R"):
                t.task_set = "real"

    if limit is not None:
        task_list = task_list[:limit]

    # Resolve evaluation modes: real tasks are strictly image-mode only
    resolved_modes: list[EvalMode] = []
    is_real_run = (
        task_set.lower() == "real"
        or all(
            getattr(t, "task_set", "synthetic") == "real" or str(t.task_id).startswith("R")
            for t in task_list
        )
        if task_list
        else (task_set.lower() == "real")
    )

    if is_real_run:
        resolved_modes = ["image"]
        if modes and any(m != "image" for m in modes):
            logger.info("Real tasks do not support text mode; restricting evaluation to ['image'].")
    elif modes:
        resolved_modes = [validate_mode(m) for m in modes]
    else:
        resolved_modes = list(MODES)

    # Resolve adapters
    adapters: list[BaseAdapter] = []
    if models and all(isinstance(m, BaseAdapter) for m in models):
        adapters = list(models)  # type: ignore[arg-type]
    else:
        models_cfg: ModelsConfig = load_models_config(models_config_path)
        configured_models = {p.name: p for p in models_cfg.models if p.enabled}

        if models:
            for m_name in models:
                if isinstance(m_name, str):
                    if m_name in configured_models:
                        adapters.append(create_adapter(configured_models[m_name]))
                    elif m_name.lower() in ("oracle", "random") or m_name.lower().startswith(
                        "always"
                    ):
                        if m_name.lower().startswith("always_"):
                            opt = m_name[7:].upper()
                            adapters.append(AlwaysAdapter(option=opt))
                        elif m_name.lower() == "oracle":
                            adapters.append(OracleAdapter())
                        else:
                            adapters.append(RandomAdapter())
                    else:
                        raise ValueError(
                            f"Model '{m_name}' not found in enabled models in models.yaml."
                        )
        else:
            # All enabled models in models.yaml
            adapters = [create_adapter(p) for p in configured_models.values()]

    if not adapters:
        raise ValueError("No evaluation adapters configured or enabled.")

    # Read existing results from results.jsonl for fast resumption
    existing_results: list[EvaluationResult] = []
    existing_keys: set[tuple[str, str, str, str]] = set()
    if results_path.exists():
        with open(results_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        res = EvaluationResult.model_validate_json(line)
                        key = (res.model_id, res.task_id, res.mode, res.prompt_version)
                        if key not in existing_keys:
                            existing_keys.add(key)
                            existing_results.append(res)
                    except (ValueError, KeyError, json.JSONDecodeError) as parse_err:
                        logger.warning("Could not parse existing result: %s", parse_err)

    # Rate limiting tracking per model
    last_call_time: dict[str, float] = defaultdict(float)
    consecutive_rate_limits: dict[str, int] = defaultdict(int)

    all_results: list[EvaluationResult] = list(existing_results)

    total_combinations = len(task_list) * len(resolved_modes) * len(adapters)
    completed_steps = len(existing_keys)

    logger.info(
        "Starting evaluation: %d tasks x %d modes x %d models = %d total combinations (%d already completed)",
        len(task_list),
        len(resolved_modes),
        len(adapters),
        total_combinations,
        completed_steps,
    )

    with open(results_path, "a", encoding="utf-8") as out_f:
        for t_idx, task in enumerate(task_list):
            for mode in resolved_modes:
                for adapter in adapters:
                    item_key = (adapter.model_id, task.task_id, mode, prompt_version)

                    # Check if already processed and recorded
                    if item_key in existing_keys:
                        continue

                    raw_resp: RawResponse | None = None
                    # Check SQLite cache
                    cached_resp = cache_instance.get(
                        model_id=adapter.model_id,
                        task_id=task.task_id,
                        mode=mode,
                        prompt_version=prompt_version,
                    )

                    if cached_resp is not None:
                        raw_resp = cached_resp
                    else:
                        # Rate limit throttling
                        if adapter.rpm > 0:
                            interval = 60.0 / adapter.rpm
                            elapsed = time.time() - last_call_time[adapter.model_id]
                            if elapsed < interval:
                                sleep_time = interval - elapsed
                                time.sleep(sleep_time)

                        try:
                            raw_resp = execute_with_retry(
                                adapter=adapter,
                                task=task,
                                mode=mode,
                                prompt_version=prompt_version,
                                max_retries=max_retries,
                                min_wait=retry_min_wait,
                            )
                            last_call_time[adapter.model_id] = time.time()
                            consecutive_rate_limits[adapter.model_id] = 0

                            # Store in SQLite cache
                            cache_instance.set(
                                model_id=adapter.model_id,
                                task_id=task.task_id,
                                mode=mode,
                                prompt_version=prompt_version,
                                response=raw_resp,
                            )
                        except Exception as exc:
                            if is_rate_limit_error(exc):
                                consecutive_rate_limits[adapter.model_id] += 1
                                if (
                                    consecutive_rate_limits[adapter.model_id]
                                    >= max_consecutive_rate_limits
                                ):
                                    err_msg = (
                                        f"Model '{adapter.name}' ({adapter.model_id}) stopped "
                                        f"after {max_consecutive_rate_limits} consecutive rate-limit failures: {exc}"
                                    )
                                    logger.error(err_msg)
                                    raise RuntimeError(err_msg) from exc
                            logger.error(
                                "Execution failed for task '%s', model '%s': %s",
                                task.task_id,
                                adapter.model_id,
                                exc,
                            )
                            # Log as failed unparseable response
                            raw_resp = RawResponse(
                                text="",
                                latency_s=0.0,
                                meta={"error": str(exc)},
                            )

                    # Score response
                    parsed_answer = parse_answer(raw_resp.text)
                    correct = score_single(task, parsed_answer)

                    result = EvaluationResult(
                        task_id=task.task_id,
                        model_id=adapter.model_id,
                        mode=mode,
                        prompt_version=prompt_version,
                        gold=task.gold,
                        parsed_answer=parsed_answer,
                        correct=correct,
                        raw_text=raw_resp.text,
                        latency_s=raw_resp.latency_s,
                        error=raw_resp.meta.get("error") if raw_resp.meta else None,
                        timestamp=time.time(),
                        qtype=task.qtype,
                        difficulty=task.difficulty,
                        skill_tags=task.skill_tags,
                        pair_id=task.pair_id,
                        pair_role=task.pair_role,
                        target_dest_id=task.target_dest_id,
                        turn_cw=task.turn_cw,
                        task_set=getattr(
                            task, "task_set", "real" if task_set.lower() == "real" else "synthetic"
                        ),
                    )

                    all_results.append(result)
                    existing_keys.add(item_key)
                    out_f.write(result.model_dump_json() + "\n")
                    out_f.flush()

                    completed_steps += 1
                    if show_progress and (
                        completed_steps % 10 == 0 or completed_steps == total_combinations
                    ):
                        logger.info(
                            "Progress: %d / %d (latest: %s on %s [%s] -> %s | correct=%s)",
                            completed_steps,
                            total_combinations,
                            adapter.name,
                            task.task_id,
                            mode,
                            parsed_answer,
                            correct,
                        )

    metrics = compute_metrics(all_results)
    return all_results, metrics


__all__ = ["DEFAULT_RESULTS_FILE", "execute_with_retry", "is_rate_limit_error", "run_evaluation"]
