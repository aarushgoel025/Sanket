"""Command Line Interface for Sanket.

Provides commands for building datasets, running evaluations,
generating reports, and smoke/pilot runs.
"""

from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(help="Sanket: visual benchmark factory for wayfinding signs.")


@app.command()
def build(
    n: Annotated[int | None, typer.Option("--n", help="Target number of tasks to keep")] = None,
    out: Annotated[Path, typer.Option("--out", help="Output directory path")] = Path(
        "data/full_dataset"
    ),
    total: Annotated[int | None, typer.Option("--total", help="Total tasks to generate")] = None,
    seed: Annotated[int | None, typer.Option("--seed", help="Master seed override")] = None,
    config: Annotated[Path | None, typer.Option("--config", help="Path to config file")] = None,
) -> None:
    """Build dataset from venues, render scenes, verify and filter tasks."""
    from sanket.pipeline.build_dataset import build_dataset

    typer.echo(f"Building dataset into '{out}' (target keep: {n or 'config default'})...")
    stats = build_dataset(
        out_dir=out,
        n_keep=n,
        total_tasks=total,
        master_seed=seed,
        config_path=config,
    )
    typer.echo(
        f"Build complete: kept {stats['total_kept']} tasks out of {stats['total_generated']} generated."
    )
    typer.echo(f"Pairs built: {stats['pairs_built']}")


@app.command()
def eval(
    tasks: Annotated[
        Path | None,
        typer.Option("--tasks", "-t", help="Path to tasks.jsonl file"),
    ] = None,
    models: Annotated[
        list[str] | None,
        typer.Option("--models", "-m", help="Model names to evaluate"),
    ] = None,
    modes: Annotated[
        list[str] | None,
        typer.Option("--modes", help="Evaluation modes (e.g. image, text)"),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option("--limit", "-l", help="Limit number of tasks"),
    ] = None,
    set_choice: Annotated[
        str,
        typer.Option("--set", help="Task set to evaluate: 'synthetic' or 'real'"),
    ] = "synthetic",
    out: Annotated[
        Path,
        typer.Option("--out", help="Output path for results JSONL"),
    ] = Path("reports/results.jsonl"),
    config: Annotated[
        Path | None,
        typer.Option("--config", help="Path to models.yaml"),
    ] = None,
) -> None:
    """Evaluate multimodal models in image and text modes with caching and rate limiting."""
    from sanket.evaluate.runner import run_evaluation

    # Resolve tasks path
    resolved_tasks: Path
    if tasks is not None:
        resolved_tasks = Path(tasks)
    elif set_choice.lower() == "real":
        real_p = Path("data/real_photos/real_tasks.jsonl")
        resolved_tasks = real_p if real_p.exists() else Path("data/real_photos/tasks.jsonl")
    else:
        full_p = Path("data/full_dataset/tasks.jsonl")
        sample_p = Path("data/sample_tasks/tasks.jsonl")
        resolved_tasks = full_p if full_p.exists() else sample_p

    if not resolved_tasks.exists():
        typer.echo(
            f"Error: Tasks file not found at '{resolved_tasks}'. "
            "Run 'sanket build' or 'sanket pilot' first to generate tasks.",
            err=True,
        )
        raise typer.Exit(code=1)

    effective_modes = ["image"] if set_choice.lower() == "real" else (modes or ["image", "text"])

    typer.echo(f"Running evaluation on '{resolved_tasks}' (set: {set_choice})...")
    typer.echo(f"Modes: {effective_modes} | Models: {models or 'all enabled'}")

    _results, metrics = run_evaluation(
        tasks=resolved_tasks,
        models=models,
        modes=effective_modes,
        results_file=out,
        limit=limit,
        models_config_path=config,
        task_set=set_choice.lower(),
    )

    typer.echo("\n--- Evaluation Complete ---")
    typer.echo(f"Total Trials: {metrics['total']} | Correct: {metrics['correct']}")
    typer.echo(
        f"Overall Accuracy: {metrics['accuracy'] * 100:.2f}% "
        f"(95% CI: [{metrics['wilson_95'][0] * 100:.1f}%, {metrics['wilson_95'][1] * 100:.1f}%])"
    )
    typer.echo(f"Unparseable Responses: {metrics['unparseable']}")

    if metrics.get("by_mode"):
        typer.echo("\nAccuracy by Mode:")
        for m_name, m_stats in metrics["by_mode"].items():
            typer.echo(
                f"  - {m_name}: {m_stats['accuracy'] * 100:.2f}% ({m_stats['correct']}/{m_stats['total']})"
            )

    if metrics.get("by_qtype"):
        typer.echo("\nAccuracy by Question Type:")
        for q_name, q_stats in metrics["by_qtype"].items():
            typer.echo(
                f"  - {q_name}: {q_stats['accuracy'] * 100:.2f}% ({q_stats['correct']}/{q_stats['total']})"
            )

    if metrics.get("hallucination_rate") is not None:
        typer.echo(f"Hallucination Rate (ABSENT): {metrics['hallucination_rate'] * 100:.2f}%")
    if metrics.get("pair_consistency") is not None:
        typer.echo(f"Counterfactual Pair Consistency: {metrics['pair_consistency'] * 100:.2f}%")
    if metrics.get("perception_gap") is not None:
        typer.echo(f"Perception Gap (image - text): {metrics['perception_gap'] * 100:.2f}%")

    typer.echo(f"\nResults appended to: {out}")

    # For real evaluation set, immediately produce/update Figure F5
    if set_choice.lower() == "real":
        try:
            from sanket.analysis.heatmaps import generate_f5_synthetic_vs_real
            from sanket.analysis.metrics import load_dataset_and_results

            df_all = load_dataset_and_results(results_path=out)
            f5_out = Path("reports/figures/F5_synthetic_vs_real.png")
            f5_meta = generate_f5_synthetic_vs_real(df_all, f5_out)
            typer.echo(f"Figure F5 produced at {f5_out}: {f5_meta.get('takeaway', '')}")
        except (RuntimeError, ValueError, OSError) as f5_err:
            typer.echo(f"Warning: could not generate Figure F5: {f5_err}", err=True)


@app.command()
def pilot(
    model: Annotated[
        str | None,
        typer.Option("--model", "-m", help="Model name to test (defaults to first enabled)"),
    ] = None,
    out_dir: Annotated[
        Path,
        typer.Option("--out-dir", help="Directory for sample tasks"),
    ] = Path("data/sample_tasks"),
) -> None:
    """Run pilot smoke test: build 20 tasks and evaluate one model on them."""
    import os

    from sanket.config import load_models_config
    from sanket.evaluate.adapters.fake import OracleAdapter
    from sanket.evaluate.runner import run_evaluation
    from sanket.pipeline.build_dataset import build_dataset

    typer.echo(f"Running pilot: generating 20 tasks into '{out_dir}'...")
    build_dataset(out_dir=out_dir, n_keep=20, master_seed=42)

    tasks_file = out_dir / "tasks.jsonl"
    models_cfg = load_models_config()

    # Determine pilot model
    adapter_to_run = None
    target_model_name = model
    if not target_model_name:
        enabled_profiles = [p for p in models_cfg.models if p.enabled]
        if enabled_profiles:
            target_model_name = enabled_profiles[0].name
        else:
            target_model_name = "oracle"

    # Check if API key is present for real provider
    if target_model_name == "gemini_flash" and not os.environ.get("GEMINI_API_KEY"):
        typer.echo(
            "Note: GEMINI_API_KEY not found in environment. Using OracleAdapter for offline pilot test."
        )
        adapter_to_run = [OracleAdapter()]
        model_names = None
    else:
        model_names = [target_model_name] if target_model_name != "oracle" else None
        if target_model_name == "oracle":
            adapter_to_run = [OracleAdapter()]

    typer.echo(f"Evaluating model '{target_model_name}' on pilot tasks...")
    results, metrics = run_evaluation(
        tasks=tasks_file,
        models=adapter_to_run or model_names,
        modes=["image"],
        results_file=Path("reports/pilot_results.jsonl"),
        limit=20,
    )

    typer.echo("\n--- Pilot Results (5 Sample Raw Responses) ---")
    for r in results[:5]:
        typer.echo(
            f"Task ID: {r.task_id} | Gold: {r.gold} | Parsed: {r.parsed_answer} | Match: {r.correct}"
        )
        typer.echo(f"Raw Response: {r.raw_text.strip()[:100]}")
        typer.echo("-" * 40)

    typer.echo(
        f"Pilot Accuracy: {metrics['accuracy'] * 100:.2f}% ({metrics['correct']}/{metrics['total']})"
    )


@app.command()
def report(
    tasks: Annotated[
        Path,
        typer.Option(
            "--tasks",
            "-t",
            help="Path to tasks.jsonl benchmark dataset",
        ),
    ] = Path("data/full_dataset/tasks.jsonl"),
    results: Annotated[
        Path,
        typer.Option(
            "--results",
            "-r",
            help="Path to evaluation results.jsonl",
        ),
    ] = Path("reports/results.jsonl"),
    reports_dir: Annotated[
        Path,
        typer.Option(
            "--reports-dir",
            "-o",
            help="Output directory for reports and figures",
        ),
    ] = Path("reports"),
) -> None:
    """Generate validation and findings reports and figures."""
    from sanket.analysis.report import run_reporting

    typer.echo("Generating benchmark validation and findings reports...")
    val_file, find_file = run_reporting(
        tasks_path=tasks,
        results_path=results,
        reports_dir=reports_dir,
    )
    typer.echo(f"Validation report generated: {val_file}")
    typer.echo(f"Findings report generated:   {find_file}")
    typer.echo(f"Figures exported to:         {reports_dir / 'figures'}")


if __name__ == "__main__":
    app()
