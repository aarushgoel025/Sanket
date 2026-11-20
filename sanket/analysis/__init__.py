"""Analysis and reporting module for benchmark evaluation results."""

from sanket.analysis.failure_gallery import (
    generate_failure_gallery_markdown,
    select_model_failures,
)
from sanket.analysis.heatmaps import (
    generate_all_figures,
    generate_f1_model_skill_heatmap,
    generate_f2_difficulty_curves,
    generate_f3_perception_gap,
    generate_f4_hallucination_rate,
    generate_f5_synthetic_vs_real,
    generate_f6_pair_consistency_graphic,
)
from sanket.analysis.metrics import (
    compute_accuracy_by_knob,
    compute_accuracy_by_qtype,
    compute_hallucination_rate,
    compute_overall_metrics,
    compute_pair_consistency,
    compute_perception_gap,
    load_dataset_and_results,
    wilson_interval,
)
from sanket.analysis.report import (
    generate_findings_report,
    generate_validation_report,
    run_reporting,
)

__all__ = [
    "compute_accuracy_by_knob",
    "compute_accuracy_by_qtype",
    "compute_hallucination_rate",
    "compute_overall_metrics",
    "compute_pair_consistency",
    "compute_perception_gap",
    "generate_all_figures",
    "generate_f1_model_skill_heatmap",
    "generate_f2_difficulty_curves",
    "generate_f3_perception_gap",
    "generate_f4_hallucination_rate",
    "generate_f5_synthetic_vs_real",
    "generate_f6_pair_consistency_graphic",
    "generate_failure_gallery_markdown",
    "generate_findings_report",
    "generate_validation_report",
    "load_dataset_and_results",
    "run_reporting",
    "select_model_failures",
    "wilson_interval",
]
