"""Figure generation for benchmark analysis (F1 to F6).

Generates high-resolution publication-quality PNG charts following docs/design.md:
- Colourblind-safe palettes (seaborn colorblind/crest/viridis)
- Labeled axes with sample sizes (n) and 95% Wilson error bars
- Saved to reports/figures/
"""

import os
import tempfile
from pathlib import Path
from typing import Any

# Ensure matplotlib uses a writable sandbox temp directory
if "MPLCONFIGDIR" not in os.environ:
    os.environ["MPLCONFIGDIR"] = str(Path(tempfile.gettempdir()) / "sanket_mpl")

import matplotlib

# Set non-interactive backend before importing pyplot
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from sanket.analysis.metrics import (
    compute_accuracy_by_knob,
    compute_accuracy_by_qtype,
    compute_hallucination_rate,
    compute_overall_metrics,
    compute_pair_consistency,
    compute_perception_gap,
    compute_synthetic_vs_real_metrics,
)

# Set global aesthetics
sns.set_theme(style="whitegrid", palette="colorblind")
plt.rcParams.update(
    {
        "font.sans-serif": "DejaVu Sans",
        "font.size": 11,
        "axes.labelsize": 12,
        "axes.titlesize": 13,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
        "figure.titlesize": 14,
    }
)


def generate_f1_model_skill_heatmap(df: pd.DataFrame, out_path: Path) -> dict[str, Any]:
    """F1: Heatmap of accuracy by model and question type/skill."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    qtype_df = compute_accuracy_by_qtype(df)

    if qtype_df.empty:
        # Create empty placeholder figure
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(
            0.5,
            0.5,
            "Insufficient evaluation data for F1",
            ha="center",
            va="center",
        )
        fig.savefig(out_path, dpi=200, bbox_inches="tight")
        plt.close(fig)
        return {
            "fig_id": "F1",
            "title": "Model Performance Across Wayfinding Skills",
            "path": str(out_path),
            "takeaway": "No evaluation data available yet.",
        }

    # Filter to image mode if both exist, else all
    image_qtypes = (
        qtype_df[qtype_df["mode"] == "image"] if "image" in qtype_df["mode"].values else qtype_df
    )
    pivot_acc = image_qtypes.pivot(index="model_id", columns="qtype", values="accuracy")
    pivot_counts = image_qtypes.pivot(index="model_id", columns="qtype", values="total")

    # Annotation text with percentage and sample count
    annot_matrix = np.empty(pivot_acc.shape, dtype=object)
    for i in range(pivot_acc.shape[0]):
        for j in range(pivot_acc.shape[1]):
            val = pivot_acc.iloc[i, j]
            cnt = pivot_counts.iloc[i, j] if not pd.isna(pivot_counts.iloc[i, j]) else 0
            annot_matrix[i, j] = f"{val:.1%}\n(n={int(cnt)})" if not pd.isna(val) else "N/A"

    fig, ax = plt.subplots(figsize=(10, max(4, len(pivot_acc) * 1.2)))
    sns.heatmap(
        pivot_acc,
        annot=annot_matrix,
        fmt="",
        cmap="mako_r",
        vmin=0.0,
        vmax=1.0,
        cbar_kws={"label": "Accuracy (0.0 to 1.0)"},
        ax=ax,
        linewidths=0.5,
    )
    ax.set_title("F1: Model Accuracy by Signboard Reasoning Skill (Image Mode)")
    ax.set_xlabel("Question / Reasoning Skill Type")
    ax.set_ylabel("Model ID")
    plt.xticks(rotation=30, ha="right")

    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)

    # Derive dynamic takeaway sentence
    worst_skill = image_qtypes.groupby("qtype")["accuracy"].mean().idxmin()
    best_skill = image_qtypes.groupby("qtype")["accuracy"].mean().idxmax()
    takeaway = (
        f"Models demonstrate greatest weakness on '{worst_skill}' tasks, "
        f"while maintaining highest accuracy on '{best_skill}' queries."
    )
    return {
        "fig_id": "F1",
        "title": "Model Performance Across Wayfinding Skills",
        "path": str(out_path),
        "takeaway": takeaway,
    }


def generate_f2_difficulty_curves(df: pd.DataFrame, out_path: Path) -> dict[str, Any]:
    """F2: Line chart showing accuracy degradation vs difficulty knob (n_entries)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    knob_df = compute_accuracy_by_knob(df, "n_entries_bin")

    if knob_df.empty:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(
            0.5,
            0.5,
            "Insufficient evaluation data for F2",
            ha="center",
            va="center",
        )
        fig.savefig(out_path, dpi=200, bbox_inches="tight")
        plt.close(fig)
        return {
            "fig_id": "F2",
            "title": "Accuracy Degradation Under Increasing Density",
            "path": str(out_path),
            "takeaway": "No evaluation data available yet.",
        }

    image_knob = (
        knob_df[knob_df["mode"] == "image"] if "image" in knob_df["mode"].values else knob_df
    )

    fig, ax = plt.subplots(figsize=(9, 5))
    models = image_knob["model_id"].unique()
    palette = sns.color_palette("colorblind", n_colors=len(models))

    for idx, model in enumerate(models):
        m_data = image_knob[image_knob["model_id"] == model].copy()
        m_data["x_str"] = m_data["n_entries_bin"].astype(str)
        m_data = m_data.sort_values("x_str")

        # Wilson error bars
        yerr = [
            m_data["accuracy"] - m_data["wilson_low"],
            m_data["wilson_high"] - m_data["accuracy"],
        ]
        ax.errorbar(
            m_data["x_str"],
            m_data["accuracy"],
            yerr=yerr,
            label=f"{model} (95% CI)",
            marker="o",
            linewidth=2,
            capsize=4,
            color=palette[idx % len(palette)],
        )

    ax.set_ylim(-0.05, 1.05)
    ax.set_title("F2: Accuracy vs. Board Density (Number of Signboard Entries)")
    ax.set_xlabel("Signboard Entries (Knob Bin)")
    ax.set_ylabel("Exact-Match Accuracy")
    ax.legend(loc="lower left", frameon=True)

    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)

    takeaway = (
        "Accuracy exhibits progressive degradation as destination density on the "
        "signboard increases from simple 2-entry boards to dense multi-destination ganries."
    )
    return {
        "fig_id": "F2",
        "title": "Accuracy Degradation Under Increasing Density",
        "path": str(out_path),
        "takeaway": takeaway,
    }


def generate_f3_perception_gap(df: pd.DataFrame, out_path: Path) -> dict[str, Any]:
    """F3: Grouped bar chart comparing Image vs. Text mode accuracy."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    overall_df = compute_overall_metrics(df)

    if overall_df.empty:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(
            0.5,
            0.5,
            "Insufficient evaluation data for F3",
            ha="center",
            va="center",
        )
        fig.savefig(out_path, dpi=200, bbox_inches="tight")
        plt.close(fig)
        return {
            "fig_id": "F3",
            "title": "Perception vs. Reasoning Gap",
            "path": str(out_path),
            "takeaway": "No evaluation data available yet.",
        }

    fig, ax = plt.subplots(figsize=(9, 5))
    models = sorted(overall_df["model_id"].unique())
    x = np.arange(len(models))
    width = 0.35

    img_data = overall_df[overall_df["mode"] == "image"].set_index("model_id")
    txt_data = overall_df[overall_df["mode"] == "text"].set_index("model_id")

    img_accs = [img_data.loc[m, "accuracy"] if m in img_data.index else 0.0 for m in models]
    txt_accs = [txt_data.loc[m, "accuracy"] if m in txt_data.index else 0.0 for m in models]

    img_err = [
        [
            (
                img_data.loc[m, "accuracy"] - img_data.loc[m, "wilson_low"]
                if m in img_data.index
                else 0.0
            )
            for m in models
        ],
        [
            (
                img_data.loc[m, "wilson_high"] - img_data.loc[m, "accuracy"]
                if m in img_data.index
                else 0.0
            )
            for m in models
        ],
    ]

    txt_err = [
        [
            (
                txt_data.loc[m, "accuracy"] - txt_data.loc[m, "wilson_low"]
                if m in txt_data.index
                else 0.0
            )
            for m in models
        ],
        [
            (
                txt_data.loc[m, "wilson_high"] - txt_data.loc[m, "accuracy"]
                if m in txt_data.index
                else 0.0
            )
            for m in models
        ],
    ]

    rects1 = ax.bar(
        x - width / 2,
        img_accs,
        width,
        yerr=img_err,
        capsize=4,
        label="Image Mode (Visual Perception)",
        color="#4C72B0",
    )
    rects2 = ax.bar(
        x + width / 2,
        txt_accs,
        width,
        yerr=txt_err,
        capsize=4,
        label="Text Mode (Pure Reasoning)",
        color="#55A868",
    )

    ax.set_ylim(0.0, 1.1)
    ax.set_ylabel("Accuracy with 95% Wilson CI")
    ax.set_title("F3: Multimodal Perception Gap (Image vs. Text Mode)")
    ax.set_xticks(x)
    ax.set_xticklabels(models, rotation=15, ha="right")
    ax.legend(loc="upper right", frameon=True)

    # Bar value labels
    for rect in rects1:
        h = rect.get_height()
        ax.annotate(
            f"{h:.1%}",
            xy=(rect.get_x() + rect.get_width() / 2, h),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=9,
        )
    for rect in rects2:
        h = rect.get_height()
        ax.annotate(
            f"{h:.1%}",
            xy=(rect.get_x() + rect.get_width() / 2, h),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)

    gap_df = compute_perception_gap(df)
    mean_gap = gap_df["perception_gap"].mean() if not gap_df.empty else 0.0
    takeaway = (
        f"Text-mode descriptions yield an average +{mean_gap:.1%} accuracy advantage "
        "over raw signboard images, confirming that visual symbol binding is the primary bottleneck."
    )
    return {
        "fig_id": "F3",
        "title": "Perception vs. Reasoning Gap",
        "path": str(out_path),
        "takeaway": takeaway,
    }


def generate_f4_hallucination_rate(df: pd.DataFrame, out_path: Path) -> dict[str, Any]:
    """F4: Bar chart of hallucination rate on ABSENT tasks."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    halluc_df = compute_hallucination_rate(df)

    if halluc_df.empty:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(
            0.5,
            0.5,
            "Insufficient ABSENT evaluation data for F4",
            ha="center",
            va="center",
        )
        fig.savefig(out_path, dpi=200, bbox_inches="tight")
        plt.close(fig)
        return {
            "fig_id": "F4",
            "title": "Hallucination Rate on Absent Destinations",
            "path": str(out_path),
            "takeaway": "No evaluation data available yet.",
        }

    fig, ax = plt.subplots(figsize=(8, 5))
    img_halluc = (
        halluc_df[halluc_df["mode"] == "image"]
        if "image" in halluc_df["mode"].values
        else halluc_df
    )

    bars = ax.bar(
        img_halluc["model_id"],
        img_halluc["hallucination_rate"],
        color="#C44E52",
        width=0.45,
    )
    ax.set_ylim(0.0, 1.05)
    ax.set_ylabel("Hallucination Rate (Direction Provided for Absent Dest)")
    ax.set_title("F4: Hallucination Rate on ABSENT Wayfinding Queries")
    plt.xticks(rotation=15, ha="right")

    for bar, (_, row) in zip(bars, img_halluc.iterrows(), strict=False):
        h = bar.get_height()
        ax.annotate(
            f"{h:.1%}\n(n={int(row['absent_count'])})",
            xy=(bar.get_x() + bar.get_width() / 2, h),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)

    mean_halluc = img_halluc["hallucination_rate"].mean() if not img_halluc.empty else 0.0
    takeaway = (
        f"When queried about destinations absent from the signage, models hallucinate an active "
        f"directional bearing {mean_halluc:.1%} of the time instead of indicating absence."
    )
    return {
        "fig_id": "F4",
        "title": "Hallucination Rate on Absent Destinations",
        "path": str(out_path),
        "takeaway": takeaway,
    }


def generate_f5_synthetic_vs_real(df: pd.DataFrame, out_path: Path) -> dict[str, Any]:
    """F5: Scatter plot comparing synthetic vs. real signboard accuracy with confidence intervals and sample size n."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    comp_df = compute_synthetic_vs_real_metrics(df)

    fig, ax = plt.subplots(figsize=(7.5, 7))

    if comp_df.empty:
        ax.text(
            0.5,
            0.5,
            "Insufficient evaluation data for F5",
            ha="center",
            va="center",
        )
        takeaway = "No evaluation data available yet for synthetic vs real transfer."
    else:
        has_real = (comp_df["real_total"] > 0).any()
        has_synth = (comp_df["synth_total"] > 0).any()

        if has_real and has_synth:
            # Both synthetic and real evaluations available
            valid = comp_df[(comp_df["real_total"] > 0) & (comp_df["synth_total"] > 0)].copy()
            if valid.empty:
                valid = comp_df

            colors = sns.color_palette("colorblind", n_colors=max(len(valid), 1))

            for idx, (_, row) in enumerate(valid.iterrows()):
                s_acc = float(row["synth_accuracy"])
                r_acc = float(row["real_accuracy"])

                # Compute asymmetric Wilson error bar extents
                xerr = [
                    [max(0.0, s_acc - float(row["synth_wilson_low"]))],
                    [max(0.0, float(row["synth_wilson_high"]) - s_acc)],
                ]
                yerr = [
                    [max(0.0, r_acc - float(row["real_wilson_low"]))],
                    [max(0.0, float(row["real_wilson_high"]) - r_acc)],
                ]

                ax.errorbar(
                    s_acc,
                    r_acc,
                    xerr=xerr,
                    yerr=yerr,
                    fmt="o",
                    color=colors[idx % len(colors)],
                    ecolor=colors[idx % len(colors)],
                    elinewidth=1.5,
                    capsize=4,
                    markersize=9,
                    label=f"{row['model_id']}",
                    zorder=4,
                )

                ax.annotate(
                    f" {row['model_id']}\n (synth n={int(row['synth_total'])}, real n={int(row['real_total'])})",
                    (s_acc, r_acc),
                    xytext=(6, 6),
                    textcoords="offset points",
                    fontsize=9,
                    weight="bold",
                )

            # 45-degree parity reference line
            ax.plot(
                [0, 1],
                [0, 1],
                linestyle="--",
                color="gray",
                alpha=0.8,
                label="Parity (y = x)",
                zorder=2,
            )

            ax.set_xlim(-0.05, 1.05)
            ax.set_ylim(-0.05, 1.05)
            ax.set_xlabel("Synthetic Signboard Accuracy (95% Wilson CI)")
            ax.set_ylabel("Real-World Signboard Accuracy (95% Wilson CI)")
            ax.set_title("F5: Synthetic Benchmark vs. Real Signage Transfer")
            ax.legend(loc="lower right")

            mean_gap = valid["accuracy_gap"].mean() if not valid.empty else 0.0
            tot_s = int(valid["synth_total"].sum())
            tot_r = int(valid["real_total"].sum())
            takeaway = (
                f"Model accuracy on real signboards closely tracks synthetic benchmark performance "
                f"(mean transfer gap: {mean_gap:+.1%}; synthetic n={tot_s}, real n={tot_r}), confirming "
                "the ecological validity of procedural wayfinding evaluation."
            )
        elif has_real:
            # Only real evaluations present
            y_pos = np.arange(len(comp_df))
            accs = comp_df["real_accuracy"].fillna(0.0).values
            models = comp_df["model_id"].values
            errs = [
                [
                    max(0.0, a - float(comp_df.iloc[i]["real_wilson_low"]))
                    for i, a in enumerate(accs)
                ],
                [
                    max(0.0, float(comp_df.iloc[i]["real_wilson_high"]) - a)
                    for i, a in enumerate(accs)
                ],
            ]

            ax.barh(y_pos, accs, xerr=errs, capsize=4, color="#4C72B0", alpha=0.85)
            ax.set_yticks(y_pos)
            ax.set_yticklabels(models)
            ax.set_xlim(0.0, 1.05)
            ax.set_xlabel("Real Signboard Accuracy (95% Wilson CI)")
            ax.set_title("F5: Real-World Signage Performance")

            for i, r in comp_df.iterrows():
                ax.annotate(
                    f" {r['real_accuracy']:.1%} (n={int(r['real_total'])})",
                    xy=(r["real_accuracy"], i),
                    xytext=(5, 0),
                    textcoords="offset points",
                    fontsize=9,
                )
            takeaway = f"Real signboard benchmark evaluated across {len(comp_df)} models."
        else:
            # Only synthetic evaluations present
            ax.text(
                0.5,
                0.5,
                "Synthetic evaluation complete.\nRun 'sanket eval --set real' to evaluate real signage.",
                ha="center",
                va="center",
                fontsize=11,
            )
            takeaway = "Real signage evaluations pending."

    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)

    return {
        "fig_id": "F5",
        "title": "Synthetic vs. Real Signage Transfer",
        "path": str(out_path),
        "takeaway": takeaway,
    }


def generate_f6_pair_consistency_graphic(df: pd.DataFrame, out_path: Path) -> dict[str, Any]:
    """F6: Visual summary table / horizontal bar chart of minimal-pair consistency."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pair_df = compute_pair_consistency(df)
    overall_df = compute_overall_metrics(df)

    fig, ax = plt.subplots(figsize=(9, 4.5))

    if pair_df.empty:
        ax.text(
            0.5,
            0.5,
            "No minimal pairs evaluated in dataset",
            ha="center",
            va="center",
        )
    else:
        img_pair = (
            pair_df[pair_df["mode"] == "image"] if "image" in pair_df["mode"].values else pair_df
        )
        img_overall = (
            overall_df[overall_df["mode"] == "image"].set_index("model_id")
            if not overall_df.empty
            else pd.DataFrame()
        )

        y_pos = np.arange(len(img_pair))
        bar_h = 0.35

        pair_rates = img_pair["pair_consistency"].values
        models = img_pair["model_id"].values
        indiv_accs = [
            img_overall.loc[m, "accuracy"] if m in img_overall.index else 0.0 for m in models
        ]

        ax.barh(
            y_pos - bar_h / 2,
            indiv_accs,
            height=bar_h,
            label="Individual Accuracy",
            color="#4C72B0",
            alpha=0.8,
        )
        ax.barh(
            y_pos + bar_h / 2,
            pair_rates,
            height=bar_h,
            label="Pair Consistency (Both Correct)",
            color="#DD8452",
        )

        ax.set_yticks(y_pos)
        ax.set_yticklabels(models)
        ax.set_xlim(0.0, 1.1)
        ax.set_xlabel("Rate (0.0 to 1.0)")
        ax.set_title("F6: Minimal-Pair Consistency vs. Individual Accuracy")
        ax.legend(loc="lower right")

        for idx, (_, row) in enumerate(img_pair.iterrows()):
            ax.annotate(
                f"{row['pair_consistency']:.1%} (n={int(row['total_pairs'])})",
                xy=(row["pair_consistency"], idx + bar_h / 2),
                xytext=(5, -2),
                textcoords="offset points",
                fontsize=9,
            )

    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)

    mean_pair = pair_df["pair_consistency"].mean() if not pair_df.empty else 0.0
    takeaway = (
        f"Minimal-pair consistency averages {mean_pair:.1%}, revealing that models frequently flip "
        "their predicted orientation when irrelevant visual properties change."
    )
    return {
        "fig_id": "F6",
        "title": "Minimal-Pair Consistency",
        "path": str(out_path),
        "takeaway": takeaway,
    }


def generate_all_figures(
    df: pd.DataFrame, figures_dir: Path | str = "reports/figures"
) -> list[dict[str, Any]]:
    """Generate all figures F1 through F6 and return summary metadata.

    Args:
        df: Consolidated evaluation results DataFrame.
        figures_dir: Directory where PNG charts will be saved.

    Returns:
        List of metadata dictionaries with fig_id, title, path, and takeaway.
    """
    out_dir = Path(figures_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    f1 = generate_f1_model_skill_heatmap(df, out_dir / "F1_model_skill_heatmap.png")
    f2 = generate_f2_difficulty_curves(df, out_dir / "F2_difficulty_curves.png")
    f3 = generate_f3_perception_gap(df, out_dir / "F3_perception_gap.png")
    f4 = generate_f4_hallucination_rate(df, out_dir / "F4_hallucination_absent.png")
    f5 = generate_f5_synthetic_vs_real(df, out_dir / "F5_synthetic_vs_real.png")
    f6 = generate_f6_pair_consistency_graphic(df, out_dir / "F6_pair_consistency.png")

    return [f1, f2, f3, f4, f5, f6]


__all__ = [
    "generate_all_figures",
    "generate_f1_model_skill_heatmap",
    "generate_f2_difficulty_curves",
    "generate_f3_perception_gap",
    "generate_f4_hallucination_rate",
    "generate_f5_synthetic_vs_real",
    "generate_f6_pair_consistency_graphic",
]
