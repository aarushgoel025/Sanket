"""Test that all modules in the sanket package can be imported."""

import importlib

import pytest

MODULES = [
    "sanket",
    "sanket.cli",
    "sanket.schema",
    "sanket.config",
    "sanket.graph",
    "sanket.graph.venue",
    "sanket.graph.solver",
    "sanket.graph.orientation",
    "sanket.generator",
    "sanket.generator.scene_builder",
    "sanket.generator.distractors",
    "sanket.generator.renderer",
    "sanket.generator.augment",
    "sanket.generator.text_description",
    "sanket.questions",
    "sanket.questions.templates",
    "sanket.questions.options",
    "sanket.verify",
    "sanket.verify.independent",
    "sanket.verify.fidelity",
    "sanket.verify.visibility",
    "sanket.verify.blind_test",
    "sanket.verify.pairs",
    "sanket.verify.dedupe",
    "sanket.verify.receipt",
    "sanket.pipeline",
    "sanket.pipeline.build_dataset",
    "sanket.evaluate",
    "sanket.evaluate.prompts",
    "sanket.evaluate.parser",
    "sanket.evaluate.modes",
    "sanket.evaluate.cache",
    "sanket.evaluate.runner",
    "sanket.evaluate.scorer",
    "sanket.evaluate.adapters",
    "sanket.evaluate.adapters.base",
    "sanket.evaluate.adapters.gemini",
    "sanket.evaluate.adapters.openai_compat",
    "sanket.evaluate.adapters.hf_qwen",
    "sanket.evaluate.adapters.fake",
    "sanket.analysis",
    "sanket.analysis.metrics",
    "sanket.analysis.heatmaps",
    "sanket.analysis.failure_gallery",
    "sanket.analysis.report",
]


@pytest.mark.parametrize("module_name", MODULES)
def test_import_module(module_name: str) -> None:
    """Import the given module and assert it is loaded."""
    module = importlib.import_module(module_name)
    assert module is not None
