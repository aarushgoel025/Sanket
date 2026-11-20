"""Evaluation package for running and scoring multimodal models.

Provides model adapters, caching, strict parsing, metrics calculation,
and the evaluation execution runner.
"""

from sanket.evaluate.cache import ResponseCache, get_cache
from sanket.evaluate.modes import MODES, EvalMode, validate_mode
from sanket.evaluate.parser import parse_answer
from sanket.evaluate.prompts import build_prompt
from sanket.evaluate.runner import run_evaluation
from sanket.evaluate.scorer import compute_metrics, score_single, wilson_score_interval

__all__ = [
    "MODES",
    "EvalMode",
    "ResponseCache",
    "build_prompt",
    "compute_metrics",
    "get_cache",
    "parse_answer",
    "run_evaluation",
    "score_single",
    "validate_mode",
    "wilson_score_interval",
]
