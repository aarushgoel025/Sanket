"""Sanket Streamlit Demo — Page 3: Counterfactual Minimal Pairs Explorer.

Displays counterfactual minimal pairs side by side with both gold reference answers
and model evaluations, demonstrating how single visual perturbations expose guessing.
"""

import os
import tempfile
from pathlib import Path

# Ensure Matplotlib config directory is writable before importing matplotlib
os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "sanket_mpl"))

import streamlit as st

from demo.utils import (
    REPO_ROOT,
    get_minimal_pairs,
    load_scene,
    load_tasks,
    query_model,
)
from sanket.verify.pairs import find_scene_field_differences

st.set_page_config(
    page_title="Sanket: Minimal Pairs Explorer",
    page_icon="⚖️",
    layout="wide",
)

st.title("⚖️ Counterfactual Minimal Pairs Explorer")
st.markdown(
    "A **counterfactual minimal pair** consists of two signboards differing by **exactly one physical detail** "
    "(such as an arrow orientation rotated by 45° or a corridor status toggled). Both variants ask the identical "
    "question. A model relying on visual grounding must flip its answer accordingly; a model guessing from language "
    "priors fails."
)

# -----------------------------------------------------------------------------
# 1. Load Minimal Pairs
# -----------------------------------------------------------------------------
tasks = load_tasks()
pair_dict = get_minimal_pairs(tasks)

if not pair_dict:
    st.warning(
        "No verified minimal pairs found in current dataset. "
        "Run `python -m sanket.cli build --n 12` to generate counterfactual pairs."
    )
    st.stop()

selected_pair_id = st.selectbox(
    "Select Minimal Pair",
    list(pair_dict.keys()),
    format_func=lambda pid: (
        f"{pid} ({pair_dict[pid][0].qtype}) — Target: {pair_dict[pid][0].target_dest_id}"
    ),
)

pair_members = pair_dict[selected_pair_id]
task_a, task_b = pair_members[0], pair_members[1]

# -----------------------------------------------------------------------------
# 2. Side-by-Side Visual Comparison
# -----------------------------------------------------------------------------
col_a, col_b = st.columns(2, gap="large")

with col_a:
    st.subheader(f"🅰️ Variant A ({task_a.task_id})")
    img_a_path = Path(task_a.image_path)
    if not img_a_path.is_absolute():
        img_a_path = REPO_ROOT / img_a_path

    alt_a = f"Variant A of minimal pair {selected_pair_id} targeting {task_a.target_dest_id}."
    if img_a_path.exists():
        st.image(
            str(img_a_path),
            caption=f"Variant A (Role: {task_a.pair_role})",
            alt=alt_a,
            use_container_width=True,
        )
    else:
        st.info(f"Image for {task_a.task_id} not found at {img_a_path}.")

    st.markdown(f"**Question:** {task_a.question}")
    st.info(f"**Gold Ground Truth A:** `{task_a.gold}`")

with col_b:
    st.subheader(f"🅱️ Variant B ({task_b.task_id})")
    img_b_path = Path(task_b.image_path)
    if not img_b_path.is_absolute():
        img_b_path = REPO_ROOT / img_b_path

    alt_b = f"Variant B of minimal pair {selected_pair_id} targeting {task_b.target_dest_id} with perturbed attribute."
    if img_b_path.exists():
        st.image(
            str(img_b_path),
            caption=f"Variant B (Role: {task_b.pair_role})",
            alt=alt_b,
            use_container_width=True,
        )
    else:
        st.info(f"Image for {task_b.task_id} not found at {img_b_path}.")

    st.markdown(f"**Question:** {task_b.question}")
    st.info(f"**Gold Ground Truth B:** `{task_b.gold}`")

# -----------------------------------------------------------------------------
# 3. Exact Counterfactual Difference
# -----------------------------------------------------------------------------
st.divider()
st.subheader("🔬 Single Visual Change Invariant")

scene_a = load_scene(task_a.scene_path)
scene_b = load_scene(task_b.scene_path)

if scene_a and scene_b:
    diffs = find_scene_field_differences(scene_a, scene_b)
    diff_text = ", ".join(diffs) if diffs else "None"
    st.success(
        f"✅ **Verifiable Invariant:** Exactly **{len(diffs)}** scene attribute differs between variants: `{diff_text}`"
    )
else:
    st.info("Scene JSON specifications not available for detailed field difference inspection.")

# -----------------------------------------------------------------------------
# 4. Multi-Model Pair Consistency Evaluation
# -----------------------------------------------------------------------------
st.divider()
st.subheader("🤖 Model Consistency Comparison")
st.markdown(
    "A model is **CONSISTENT** on a minimal pair if and only if it answers **both** counterfactual variants correctly. "
    "If a model answers identically to both despite the sign changing, or succeeds on only one, it reveals guessing."
)

models_to_test = [
    ("oracle", "Oracle (Ground Truth)"),
    ("random", "Random Baseline"),
    ("always_ahead", "Always AHEAD Baseline"),
    ("gemini_flash", "Google Gemini Flash"),
]

table_rows = []

for m_id, m_label in models_to_test:
    ans_a, cor_a, _, _, _ = query_model(task_a, m_id, mode="image")
    ans_b, cor_b, _, _, _ = query_model(task_b, m_id, mode="image")

    if cor_a and cor_b:
        consistency_status = "✅ CONSISTENT (Both Correct)"
    elif cor_a and not cor_b:
        consistency_status = "⚠️ INCONSISTENT (A Correct, B Failed)"
    elif not cor_a and cor_b:
        consistency_status = "⚠️ INCONSISTENT (A Failed, B Correct)"
    else:
        consistency_status = "❌ INACCURATE (Both Failed)"

    table_rows.append(
        {
            "Evaluated Model": m_label,
            "Variant A Pred": f"`{ans_a}`" + (" (✅)" if cor_a else " (❌)"),
            "Variant B Pred": f"`{ans_b}`" + (" (✅)" if cor_b else " (❌)"),
            "Pair Consistency Verdict": consistency_status,
        }
    )

st.table(table_rows)
