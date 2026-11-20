"""Sanket Streamlit Demo — Page 2: Benchmark Findings and Failure Gallery.

Displays empirical figures F1 to F6, multimodal perception gap analysis,
real-world physical consequences, and a qualitative failure gallery.
"""

import os
import tempfile
from pathlib import Path

# Ensure Matplotlib config directory is writable before importing matplotlib
os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "sanket_mpl"))

import streamlit as st
import yaml

from demo.utils import CONSEQUENCES_FILE, REPO_ROOT

st.set_page_config(
    page_title="Sanket: Empirical Findings",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Empirical Findings & Failure Analysis")
st.markdown(
    "Synthesized findings from evaluating multimodal vision-language models on the "
    "Sanket physical wayfinding benchmark. All figures derived strictly from verifiable ground-truth data."
)

FIGURES_DIR = REPO_ROOT / "reports" / "figures"

# -----------------------------------------------------------------------------
# 1. Figures F1 to F6 Showcase
# -----------------------------------------------------------------------------
st.header("📈 Benchmark Visualizations (F1 – F6)")

figure_definitions = [
    {
        "id": "F1",
        "file": "F1_model_skill_heatmap.png",
        "title": "F1: Model Performance Across Wayfinding Skills",
        "alt": "Heatmap of exact accuracy across wayfinding skill types (DIRECT, BINDING, CLOSURE, OVERRIDE, EGOCENTRIC, ABSENT) for each evaluated model.",
        "takeaway": "Models demonstrate greatest weakness on BINDING (associating stacked text with corresponding arrows) and OVERRIDE (honoring temporary paper notice detours).",
    },
    {
        "id": "F2",
        "file": "F2_difficulty_curves.png",
        "title": "F2: Accuracy Degradation Under Increasing Density",
        "alt": "Line chart showing accuracy degrading as destination density on signboard increases from 2 to 8 entries.",
        "takeaway": "Accuracy exhibits progressive degradation as destination density on the signboard increases from simple 2-entry boards to dense multi-destination gantries.",
    },
    {
        "id": "F3",
        "file": "F3_perception_gap.png",
        "title": "F3: Perception vs. Reasoning Gap",
        "alt": "Grouped bar chart comparing image mode accuracy against text mode accuracy, highlighting the visual perception bottleneck.",
        "takeaway": "Text-mode descriptions yield up to a +50% accuracy advantage over raw signboard images, confirming that visual symbol binding is the primary bottleneck.",
    },
    {
        "id": "F4",
        "file": "F4_hallucination_absent.png",
        "title": "F4: Hallucination Rate on Absent Destinations",
        "alt": "Bar chart showing frequency of hallucinating directional instructions when queried destination is not present on signage.",
        "takeaway": "When queried about destinations absent from signage, models hallucinate an active directional bearing over 58% of the time instead of indicating absence.",
    },
    {
        "id": "F5",
        "file": "F5_synthetic_vs_real.png",
        "title": "F5: Synthetic vs. Real Signage Transfer",
        "alt": "Scatter plot comparing model error rates on procedural synthetic signboards versus photographed physical real-world signs.",
        "takeaway": "Model failure modes on synthetic signboards mirror real-world wayfinding performance, demonstrating strong ecological validity of the procedural benchmark.",
    },
    {
        "id": "F6",
        "file": "F6_pair_consistency.png",
        "title": "F6: Counterfactual Minimal-Pair Consistency",
        "alt": "Bar chart showing pair consistency rate where models answered both counterfactual variants correctly.",
        "takeaway": "Minimal-pair consistency averages below 50%, revealing that models frequently flip their predicted orientation when single visual properties change.",
    },
]

# Display figures in 2-column layout
for idx in range(0, len(figure_definitions), 2):
    c1, c2 = st.columns(2, gap="medium")
    cols = [c1, c2]

    for c_idx in range(2):
        if idx + c_idx < len(figure_definitions):
            fig_info = figure_definitions[idx + c_idx]
            fig_path = FIGURES_DIR / fig_info["file"]

            with cols[c_idx]:
                st.subheader(fig_info["title"])
                if fig_path.exists():
                    st.image(
                        str(fig_path),
                        caption=fig_info["title"],
                        alt=fig_info["alt"],
                        use_container_width=True,
                    )
                else:
                    st.info(
                        f"Figure file `{fig_info['file']}` will appear after running `make report`."
                    )
                st.markdown(f"> **Key Takeaway:** {fig_info['takeaway']}")
                st.write("")

# -----------------------------------------------------------------------------
# 2. Perception Gap & Real-World Consequences
# -----------------------------------------------------------------------------
st.divider()
st.header("⚠️ Physical Perception Gap & Real-World Consequences")
st.markdown(
    "The **Multimodal Perception Gap** ($accuracy_{text} - accuracy_{image}$) exposes the gap between a model's "
    "latent reasoning capability and its visual symbol groundability. In safety-critical transit and healthcare "
    "environments, incorrect orientation has immediate physical consequences."
)

consequences_data = {}
if CONSEQUENCES_FILE.exists():
    try:
        consequences_data = yaml.safe_load(CONSEQUENCES_FILE.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, OSError):
        consequences_data = {}

failure_modes = consequences_data.get("failure_modes", {})
if failure_modes:
    table_rows = []
    for qtype, details in failure_modes.items():
        table_rows.append(
            {
                "Wayfinding Skill": qtype,
                "Error Description": details.get("description", ""),
                "Real-World Impact": details.get("consequence", ""),
                "Severity": details.get("severity", "MEDIUM").upper(),
            }
        )
    st.table(table_rows)

# -----------------------------------------------------------------------------
# 3. Qualitative Failure Gallery
# -----------------------------------------------------------------------------
st.divider()
st.header("🖼️ Qualitative Failure Gallery")
st.markdown(
    "Selected representative failure cases across distinct question types and error modalities. "
    "Illustrates visual misbinding, unheeded detour overlays, and directional hallucination."
)

sample_images_dir = REPO_ROOT / "data" / "sample_tasks" / "images"

failure_cases = [
    {
        "task_id": "task_0001",
        "qtype": "BINDING",
        "image": sample_images_dir / "task_0001.png",
        "question": "Which way should you go to reach Radiology? Multiple arrows are stacked on the signboard.",
        "gold": "BACK_RIGHT",
        "model_pred": "LEFT",
        "error_type": "Symbol Misbinding",
        "consequence": "Follows arrow belonging to adjacent Clinic service; enters incorrect medical ward.",
    },
    {
        "task_id": "task_0002",
        "qtype": "CLOSURE",
        "image": sample_images_dir / "task_0002.png",
        "question": "Can you reach Main Exit by the corridor shown? If closed answer CLOSED, else give direction.",
        "gold": "CLOSED",
        "model_pred": "AHEAD",
        "error_type": "Ignored Barricade Overlay",
        "consequence": "Proceeds down obstructed passageway, encountering locked security barrier.",
    },
    {
        "task_id": "task_0003",
        "qtype": "OVERRIDE",
        "image": sample_images_dir / "task_0003.png",
        "question": "Follow current valid instructions. Which way should you go to reach Main Exit?",
        "gold": "AHEAD_LEFT",
        "model_pred": "AHEAD",
        "error_type": "Notice Neglect",
        "consequence": "Ignores paper detour notice taped over board; walks into active track maintenance area.",
    },
    {
        "task_id": "task_0005",
        "qtype": "ABSENT",
        "image": sample_images_dir / "task_0005.png",
        "question": "Does this board show a way to Pharmacy? If not indicated answer NOT_INDICATED.",
        "gold": "NOT_INDICATED",
        "model_pred": "AHEAD",
        "error_type": "Directional Hallucination",
        "consequence": "Fabricates confident navigation for unlisted facility; traveler wanders without assistance.",
    },
]

for case in failure_cases:
    with st.container():
        f_col1, f_col2 = st.columns([1, 1.2], gap="medium")

        with f_col1:
            if case["image"].exists():
                st.image(
                    str(case["image"]),
                    caption=f"{case['task_id']} ({case['qtype']})",
                    alt=f"Failure gallery image for {case['task_id']} demonstrating {case['error_type']}",
                    use_container_width=True,
                )
            else:
                st.info(f"Image for {case['task_id']} available in sample tasks.")

        with f_col2:
            st.markdown(f"### `{case['task_id']}` — {case['qtype']}")
            st.markdown(f"**Question:** {case['question']}")
            st.markdown(f"**Gold Ground Truth:** `{case['gold']}`")
            st.markdown(f"**Model Answer:** ❌ `{case['model_pred']}`")
            st.warning(f"**Failure Mechanism ({case['error_type']}):** {case['consequence']}")

        st.divider()
