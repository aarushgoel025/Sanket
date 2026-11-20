"""Sanket Streamlit Demo — Page 1: Generate, Ask Model, and Reveal Proof.

Interactive demo for synthetic wayfinding signage generation, multimodal model
evaluation against graph-grounded reference answers, and verifiable proof visualization.
Works 100% offline from cached sample tasks without API keys.
"""

import os
import tempfile
from pathlib import Path

# Ensure Matplotlib config directory is writable before importing matplotlib
os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "sanket_mpl"))

import numpy as np
import streamlit as st

from demo.utils import (
    REPO_ROOT,
    get_venue_map,
    load_scene,
    load_tasks,
    plot_venue_route,
    query_model,
)
from sanket.generator.augment import augment
from sanket.generator.renderer import render_scene
from sanket.generator.scene_builder import build_scene
from sanket.graph.solver import gold_answer
from sanket.questions.templates import make_task
from sanket.schema import ANSWER_OPTIONS, Knobs, Task, Venue

st.set_page_config(
    page_title="Sanket: Wayfinding Sign Benchmark",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🧭 Sanket: Wayfinding Sign Benchmark Demo")
st.markdown(
    "Ground-truth multimodal evaluation for physical wayfinding signs. "
    "All references derived strictly from venue graph topology—never from language models."
)

# -----------------------------------------------------------------------------
# 1. Sidebar Controls & Offline Mode
# -----------------------------------------------------------------------------
st.sidebar.header("⚙️ Benchmark Controls")

offline_mode = st.sidebar.checkbox(
    "📦 Use saved sample tasks (Offline Mode)",
    value=True,
    help="Load verified sample tasks and cached responses without requiring browser rendering or API keys.",
)

venue_map = get_venue_map()
if not venue_map:
    st.error("No venue configuration files found in `config/venues/`.")
    st.stop()

QUESTION_TYPES = ["DIRECT", "BINDING", "CLOSURE", "OVERRIDE", "EGOCENTRIC", "ABSENT"]

current_task: Task | None = None
current_scene = None
current_venue: Venue | None = None
current_image_path: Path | None = None

if offline_mode:
    st.sidebar.info("Offline mode active: browsing pre-generated verified tasks.")
    sample_tasks = load_tasks()

    if not sample_tasks:
        st.sidebar.warning("No sample tasks found in `data/sample_tasks/tasks.jsonl`.")
    else:
        qtype_filter = st.sidebar.selectbox("Filter by Question Type", ["All", *QUESTION_TYPES])
        filtered_tasks = (
            sample_tasks
            if qtype_filter == "All"
            else [t for t in sample_tasks if t.qtype == qtype_filter]
        )

        task_labels = [
            f"[{t.qtype}] {t.task_id} (Target: {t.target_dest_id})" for t in filtered_tasks
        ]
        selected_idx = st.sidebar.selectbox(
            "Select Sample Task",
            range(len(filtered_tasks)),
            format_func=lambda i: task_labels[i] if i < len(task_labels) else "",
        )

        if filtered_tasks and selected_idx is not None and selected_idx < len(filtered_tasks):
            current_task = filtered_tasks[selected_idx]
            # Resolve image path
            img_p = Path(current_task.image_path)
            if not img_p.is_absolute():
                img_p = REPO_ROOT / img_p
            current_image_path = img_p

            # Resolve scene and venue
            current_scene = load_scene(current_task.scene_path)
            if current_scene and current_scene.venue_id in venue_map:
                current_venue = venue_map[current_scene.venue_id]
            else:
                current_venue = next(iter(venue_map.values()))
else:
    st.sidebar.subheader("Live Generation")
    venue_choice = st.sidebar.selectbox(
        "Venue Layout",
        list(venue_map.keys()),
        format_func=lambda k: venue_map[k].name,
    )
    current_venue = venue_map[venue_choice]

    qtype_choice = st.sidebar.selectbox("Question Type", QUESTION_TYPES)

    seed_val = st.sidebar.number_input("Task Seed", min_value=0, max_value=999999, value=42, step=1)

    with st.sidebar.expander("🛠️ Environmental & Difficulty Knobs", expanded=False):
        n_entries = st.slider("Destination Entries", min_value=2, max_value=8, value=4)
        template_choice = st.selectbox(
            "Signboard Template", ["board_list", "board_grid", "board_gantry"]
        )
        scripts_choice = st.multiselect("Visible Scripts", ["en", "hi", "regional"], default=["en"])
        perspective_deg = st.slider("Perspective Warp (deg)", 0.0, 25.0, 5.0, 1.0)
        blur_val = st.slider("Gaussian Blur", 0.0, 2.5, 0.0, 0.1)
        noise_val = st.slider("Sensor Noise", 0.0, 0.06, 0.0, 0.005)
        lighting_val = st.slider("Lighting Gradient", 0.0, 0.4, 0.0, 0.05)
        clutter_val = st.slider("Distractor Stickers / Ads", 0, 6, 0, 1)
        occlusion_val = st.slider("Board Occlusion Ratio", 0.0, 0.15, 0.0, 0.01)
        jpeg_quality = st.slider("JPEG Compression Quality", 60, 95, 90, 5)

    if st.sidebar.button("🚀 Generate Signboard", type="primary", use_container_width=True):
        knobs = Knobs(
            n_entries=n_entries,
            scripts=scripts_choice or ["en"],
            perspective_deg=perspective_deg,
            blur=blur_val,
            noise=noise_val,
            lighting=lighting_val,
            clutter=clutter_val,
            occlusion=occlusion_val,
            jpeg_quality=jpeg_quality,
            template=template_choice,
        )
        rng = np.random.default_rng(int(seed_val))

        with st.spinner("Generating procedural signboard scene..."):
            try:
                sb = build_scene(current_venue, qtype_choice, rng, knobs)
                tmp_dir = Path(tempfile.gettempdir()) / "sanket_demo"
                tmp_dir.mkdir(parents=True, exist_ok=True)

                raw_png = tmp_dir / f"live_{seed_val}_raw.png"
                final_png = tmp_dir / f"live_{seed_val}.png"
                scene_json = tmp_dir / f"live_{seed_val}.json"

                geo = render_scene(sb.scene, current_venue, raw_png)
                augment(
                    raw_png, geo, sb.scene.knobs, np.random.default_rng(int(seed_val)), final_png
                )
                raw_png.unlink(missing_ok=True)

                task = make_task(
                    sb=sb,
                    venue=current_venue,
                    rng=np.random.default_rng(int(seed_val)),
                    task_id=f"live_{seed_val}",
                    seed=int(seed_val),
                    image_path=str(final_png),
                    scene_path=str(scene_json),
                )
                gold_ans = gold_answer(
                    venue=current_venue,
                    closed_edges=sb.scene.closed_edges,
                    junction=sb.scene.junction_id,
                    heading=sb.scene.heading,
                    dest=sb.target_dest_id,
                    turn_cw=task.turn_cw,
                    listed=(qtype_choice != "ABSENT"),
                )
                task.gold = gold_ans

                st.session_state["live_task"] = task
                st.session_state["live_scene"] = sb.scene
                st.session_state["live_image_path"] = final_png
                st.session_state["live_venue"] = current_venue
            except (RuntimeError, ValueError, OSError) as exc:
                st.error(f"Live generation encountered error: {exc}. Try using offline mode.")

    if "live_task" in st.session_state:
        current_task = st.session_state["live_task"]
        current_scene = st.session_state["live_scene"]
        current_image_path = st.session_state["live_image_path"]
        current_venue = st.session_state.get("live_venue", current_venue)

# -----------------------------------------------------------------------------
# 2. Main Display: Signboard & Question
# -----------------------------------------------------------------------------
if current_task is None or current_scene is None or current_venue is None:
    st.info("👈 Please select a sample task from the sidebar or click 'Generate Signboard'.")
    st.stop()

col_img, col_info = st.columns([1.1, 0.9], gap="large")

with col_img:
    st.subheader("🖼️ Signboard Image")
    alt_text = (
        f"Wayfinding signboard rendered at junction {current_scene.junction_id} "
        f"in {current_venue.name} facing heading {current_scene.heading} degrees."
    )
    if current_image_path and current_image_path.exists():
        st.image(
            str(current_image_path),
            caption=f"Task: {current_task.task_id}",
            alt=alt_text,
            use_container_width=True,
        )
    else:
        st.warning(f"Image not found at {current_image_path}.")

with col_info:
    st.subheader("📋 Task Metadata")
    st.markdown(
        f"**Venue:** {current_venue.name}  \n"
        f"**Observer Location:** Junction `{current_scene.junction_id}` (Heading: `{current_scene.heading}°`)  \n"
        f"**Question Type:** `{current_task.qtype}`  \n"
        f"**Target Destination:** `{current_task.target_dest_id}`"
    )

    st.markdown("### ❓ Question")
    st.info(f"**{current_task.question}**")

    st.markdown("### 🎯 Canonical Options (Fixed 10-Way Set)")
    opt_cols = st.columns(5)
    for idx, opt in enumerate(ANSWER_OPTIONS):
        opt_cols[idx % 5].markdown(f"`{opt}`")

# -----------------------------------------------------------------------------
# 3. Model Evaluation ("Ask Model")
# -----------------------------------------------------------------------------
st.divider()
st.subheader("🤖 Model Evaluation")

eval_c1, eval_c2, eval_c3 = st.columns([1.2, 0.8, 0.8])

with eval_c1:
    model_choice = st.selectbox(
        "Choose Model",
        [
            ("oracle", "Oracle (Ground Truth - Offline)"),
            ("random", "Random Baseline (Offline)"),
            ("always_ahead", "Always AHEAD (Offline Bias Check)"),
            ("gemini_flash", "Google Gemini Flash (Multimodal)"),
            ("or_vision", "OpenRouter Vision (Multimodal)"),
        ],
        format_func=lambda x: x[1],
    )[0]

with eval_c2:
    mode_choice = st.radio(
        "Query Mode",
        ["image", "text"],
        horizontal=True,
        help="Image mode sends raw pixels; text mode sends structured textual descriptions.",
    )

with eval_c3:
    st.write("")
    st.write("")
    ask_button = st.button("🔮 Ask Model", type="primary", use_container_width=True)

if ask_button:
    with st.spinner(f"Evaluating {model_choice} in {mode_choice} mode..."):
        parsed_ans, is_correct, latency, raw_text, source_tag = query_model(
            task=current_task,
            model_name=model_choice,
            mode=mode_choice,
        )

        st.session_state["last_eval"] = {
            "model": model_choice,
            "mode": mode_choice,
            "parsed": parsed_ans,
            "is_correct": is_correct,
            "latency": latency,
            "raw": raw_text,
            "source": source_tag,
        }

if "last_eval" in st.session_state:
    res = st.session_state["last_eval"]
    res_c1, res_c2, res_c3 = st.columns([1, 1, 1])

    with res_c1:
        st.markdown(f"**Model Answer:** `{res['parsed']}`")
    with res_c2:
        st.markdown(f"**Gold Ground Truth:** `{current_task.gold}`")
    with res_c3:
        if res["is_correct"]:
            st.success("✅ CORRECT")
        else:
            st.error("❌ WRONG")

    st.caption(f"⏱️ Latency: {res['latency']:.3f}s | Source: {res['source']}")

    with st.expander("📄 View Raw Model Response"):
        st.code(res["raw"], language="text")

# -----------------------------------------------------------------------------
# 4. "Reveal Proof": Venue Graph & Receipt Table
# -----------------------------------------------------------------------------
st.divider()
st.subheader("🔍 Verification Proof & Route Grounding")

with st.expander("📍 View Venue Topology Graph with Shortest Route Highlighted", expanded=False):
    fig = plot_venue_route(venue=current_venue, task=current_task, scene=current_scene)
    st.pyplot(fig)

with st.expander("📜 View Cryptographic Verification Receipt", expanded=False):
    receipt = current_task.receipt
    if receipt:
        receipt_data = [
            {
                "Verification Gate": "Solver Decision",
                "Status": receipt.solver_answer,
                "Condition": "Graph shortest-path first hop",
            },
            {
                "Verification Gate": "Independent Resolver",
                "Status": receipt.independent_answer,
                "Condition": "Direct board arrow reading",
            },
            {
                "Verification Gate": "Dual Agreement Invariant",
                "Status": "✅ PASSED" if receipt.agree else "❌ FAILED",
                "Condition": "solver == independent",
            },
            {
                "Verification Gate": "DOM Render Fidelity",
                "Status": "✅ PASSED" if receipt.fidelity_ok else "❌ FAILED",
                "Condition": "Arrow & text DOM bounds match spec",
            },
            {
                "Verification Gate": "Evidence Visibility",
                "Status": f"✅ PASSED ({receipt.evidence_visible_ratio * 100:.1f}%)"
                if receipt.visibility_ok
                else "❌ FAILED",
                "Condition": "Evidence occlusion <= 5%",
            },
            {
                "Verification Gate": "Blind Prior Filter",
                "Status": "✅ PASSED (No leakage)" if not receipt.blind_rejected else "❌ FAILED",
                "Condition": "Zero-image guessing accuracy <= 25%",
            },
            {
                "Verification Gate": "Counterfactual Pair Verified",
                "Status": "✅ VERIFIED" if receipt.pair_verified else "N/A (Standard task)",
                "Condition": "Single visual change flipped gold answer",
            },
            {
                "Verification Gate": "Human Audit Status",
                "Status": receipt.human_audit.upper(),
                "Condition": "Ecological validity spot-check",
            },
        ]
        st.table(receipt_data)
    else:
        st.info("Task receipt not assembled for this synthetic instance.")

st.set_page_config(
    page_title="Sanket: Wayfinding Sign Benchmark",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🧭 Sanket: Wayfinding Sign Benchmark Demo")
st.markdown(
    "Ground-truth multimodal evaluation for physical wayfinding signs. "
    "All references derived strictly from venue graph topology—never from language models."
)

# -----------------------------------------------------------------------------
# 1. Sidebar Controls & Offline Mode
# -----------------------------------------------------------------------------
st.sidebar.header("⚙️ Benchmark Controls")

offline_mode = st.sidebar.checkbox(
    "📦 Use saved sample tasks (Offline Mode)",
    value=True,
    help="Load verified sample tasks and cached responses without requiring browser rendering or API keys.",
)

venue_map = get_venue_map()
if not venue_map:
    st.error("No venue configuration files found in `config/venues/`.")
    st.stop()

QUESTION_TYPES = ["DIRECT", "BINDING", "CLOSURE", "OVERRIDE", "EGOCENTRIC", "ABSENT"]

current_task: Task | None = None
current_scene = None
current_venue: Venue | None = None
current_image_path: Path | None = None

if offline_mode:
    st.sidebar.info("Offline mode active: browsing pre-generated verified tasks.")
    sample_tasks = load_tasks()

    if not sample_tasks:
        st.sidebar.warning("No sample tasks found in `data/sample_tasks/tasks.jsonl`.")
    else:
        qtype_filter = st.sidebar.selectbox("Filter by Question Type", ["All", *QUESTION_TYPES])
        filtered_tasks = (
            sample_tasks
            if qtype_filter == "All"
            else [t for t in sample_tasks if t.qtype == qtype_filter]
        )

        task_labels = [
            f"[{t.qtype}] {t.task_id} (Target: {t.target_dest_id})" for t in filtered_tasks
        ]
        selected_idx = st.sidebar.selectbox(
            "Select Sample Task",
            range(len(filtered_tasks)),
            format_func=lambda i: task_labels[i] if i < len(task_labels) else "",
        )

        if filtered_tasks and selected_idx is not None and selected_idx < len(filtered_tasks):
            current_task = filtered_tasks[selected_idx]
            # Resolve image path
            img_p = Path(current_task.image_path)
            if not img_p.is_absolute():
                img_p = REPO_ROOT / img_p
            current_image_path = img_p

            # Resolve scene and venue
            current_scene = load_scene(current_task.scene_path)
            if current_scene and current_scene.venue_id in venue_map:
                current_venue = venue_map[current_scene.venue_id]
            else:
                current_venue = next(iter(venue_map.values()))
else:
    st.sidebar.subheader("Live Generation")
    venue_choice = st.sidebar.selectbox(
        "Venue Layout",
        list(venue_map.keys()),
        format_func=lambda k: venue_map[k].name,
    )
    current_venue = venue_map[venue_choice]

    qtype_choice = st.sidebar.selectbox("Question Type", QUESTION_TYPES)

    seed_val = st.sidebar.number_input("Task Seed", min_value=0, max_value=999999, value=42, step=1)

    with st.sidebar.expander("🛠️ Environmental & Difficulty Knobs", expanded=False):
        n_entries = st.slider("Destination Entries", min_value=2, max_value=8, value=4)
        template_choice = st.selectbox(
            "Signboard Template", ["board_list", "board_grid", "board_gantry"]
        )
        scripts_choice = st.multiselect("Visible Scripts", ["en", "hi", "regional"], default=["en"])
        perspective_deg = st.slider("Perspective Warp (deg)", 0.0, 25.0, 5.0, 1.0)
        blur_val = st.slider("Gaussian Blur", 0.0, 2.5, 0.0, 0.1)
        noise_val = st.slider("Sensor Noise", 0.0, 0.06, 0.0, 0.005)
        lighting_val = st.slider("Lighting Gradient", 0.0, 0.4, 0.0, 0.05)
        clutter_val = st.slider("Distractor Stickers / Ads", 0, 6, 0, 1)
        occlusion_val = st.slider("Board Occlusion Ratio", 0.0, 0.15, 0.0, 0.01)
        jpeg_quality = st.slider("JPEG Compression Quality", 60, 95, 90, 5)

    if st.sidebar.button("🚀 Generate Signboard", type="primary", use_container_width=True):
        knobs = Knobs(
            n_entries=n_entries,
            scripts=scripts_choice or ["en"],
            perspective_deg=perspective_deg,
            blur=blur_val,
            noise=noise_val,
            lighting=lighting_val,
            clutter=clutter_val,
            occlusion=occlusion_val,
            jpeg_quality=jpeg_quality,
            template=template_choice,
        )
        rng = np.random.default_rng(int(seed_val))

        with st.spinner("Generating procedural signboard scene..."):
            try:
                sb = build_scene(current_venue, qtype_choice, rng, knobs)
                tmp_dir = Path(tempfile.gettempdir()) / "sanket_demo"
                tmp_dir.mkdir(parents=True, exist_ok=True)

                raw_png = tmp_dir / f"live_{seed_val}_raw.png"
                final_png = tmp_dir / f"live_{seed_val}.png"
                scene_json = tmp_dir / f"live_{seed_val}.json"

                geo = render_scene(sb.scene, current_venue, raw_png)
                augment(
                    raw_png, geo, sb.scene.knobs, np.random.default_rng(int(seed_val)), final_png
                )
                raw_png.unlink(missing_ok=True)

                task = make_task(
                    sb=sb,
                    venue=current_venue,
                    rng=np.random.default_rng(int(seed_val)),
                    task_id=f"live_{seed_val}",
                    seed=int(seed_val),
                    image_path=str(final_png),
                    scene_path=str(scene_json),
                )
                gold_ans = gold_answer(
                    venue=current_venue,
                    closed_edges=sb.scene.closed_edges,
                    junction=sb.scene.junction_id,
                    heading=sb.scene.heading,
                    dest=sb.target_dest_id,
                    turn_cw=task.turn_cw,
                    listed=(qtype_choice != "ABSENT"),
                )
                task.gold = gold_ans

                st.session_state["live_task"] = task
                st.session_state["live_scene"] = sb.scene
                st.session_state["live_image_path"] = final_png
                st.session_state["live_venue"] = current_venue
            except (RuntimeError, ValueError, OSError) as exc:
                st.error(f"Live generation encountered error: {exc}. Try using offline mode.")

    if "live_task" in st.session_state:
        current_task = st.session_state["live_task"]
        current_scene = st.session_state["live_scene"]
        current_image_path = st.session_state["live_image_path"]
        current_venue = st.session_state.get("live_venue", current_venue)

# -----------------------------------------------------------------------------
# 2. Main Display: Signboard & Question
# -----------------------------------------------------------------------------
if current_task is None or current_scene is None or current_venue is None:
    st.info("👈 Please select a sample task from the sidebar or click 'Generate Signboard'.")
    st.stop()

col_img, col_info = st.columns([1.1, 0.9], gap="large")

with col_img:
    st.subheader("🖼️ Signboard Image")
    alt_text = (
        f"Wayfinding signboard rendered at junction {current_scene.junction_id} "
        f"in {current_venue.name} facing heading {current_scene.heading} degrees."
    )
    if current_image_path and current_image_path.exists():
        st.image(
            str(current_image_path),
            caption=f"Task: {current_task.task_id}",
            alt=alt_text,
            use_container_width=True,
        )
    else:
        st.warning(f"Image not found at {current_image_path}.")

with col_info:
    st.subheader("📋 Task Metadata")
    st.markdown(
        f"**Venue:** {current_venue.name}  \n"
        f"**Observer Location:** Junction `{current_scene.junction_id}` (Heading: `{current_scene.heading}°`)  \n"
        f"**Question Type:** `{current_task.qtype}`  \n"
        f"**Target Destination:** `{current_task.target_dest_id}`"
    )

    st.markdown("### ❓ Question")
    st.info(f"**{current_task.question}**")

    st.markdown("### 🎯 Canonical Options (Fixed 10-Way Set)")
    opt_cols = st.columns(5)
    for idx, opt in enumerate(ANSWER_OPTIONS):
        opt_cols[idx % 5].markdown(f"`{opt}`")

# -----------------------------------------------------------------------------
# 3. Model Evaluation ("Ask Model")
# -----------------------------------------------------------------------------
st.divider()
st.subheader("🤖 Model Evaluation")

eval_c1, eval_c2, eval_c3 = st.columns([1.2, 0.8, 0.8])

with eval_c1:
    model_choice = st.selectbox(
        "Choose Model",
        [
            ("oracle", "Oracle (Ground Truth - Offline)"),
            ("random", "Random Baseline (Offline)"),
            ("always_ahead", "Always AHEAD (Offline Bias Check)"),
            ("gemini_flash", "Google Gemini Flash (Multimodal)"),
            ("or_vision", "OpenRouter Vision (Multimodal)"),
        ],
        format_func=lambda x: x[1],
    )[0]

with eval_c2:
    mode_choice = st.radio(
        "Query Mode",
        ["image", "text"],
        horizontal=True,
        help="Image mode sends raw pixels; text mode sends structured textual descriptions.",
    )

with eval_c3:
    st.write("")
    st.write("")
    ask_button = st.button("🔮 Ask Model", type="primary", use_container_width=True)

if ask_button:
    with st.spinner(f"Evaluating {model_choice} in {mode_choice} mode..."):
        parsed_ans, is_correct, latency, raw_text, source_tag = query_model(
            task=current_task,
            model_name=model_choice,
            mode=mode_choice,
        )

        st.session_state["last_eval"] = {
            "model": model_choice,
            "mode": mode_choice,
            "parsed": parsed_ans,
            "is_correct": is_correct,
            "latency": latency,
            "raw": raw_text,
            "source": source_tag,
        }

if "last_eval" in st.session_state:
    res = st.session_state["last_eval"]
    res_c1, res_c2, res_c3 = st.columns([1, 1, 1])

    with res_c1:
        st.markdown(f"**Model Answer:** `{res['parsed']}`")
    with res_c2:
        st.markdown(f"**Gold Ground Truth:** `{current_task.gold}`")
    with res_c3:
        if res["is_correct"]:
            st.success("✅ CORRECT")
        else:
            st.error("❌ WRONG")

    st.caption(f"⏱️ Latency: {res['latency']:.3f}s | Source: {res['source']}")

    with st.expander("📄 View Raw Model Response"):
        st.code(res["raw"], language="text")

# -----------------------------------------------------------------------------
# 4. "Reveal Proof": Venue Graph & Receipt Table
# -----------------------------------------------------------------------------
st.divider()
st.subheader("🔍 Verification Proof & Route Grounding")

with st.expander("📍 View Venue Topology Graph with Shortest Route Highlighted", expanded=False):
    fig = plot_venue_route(venue=current_venue, task=current_task, scene=current_scene)
    st.pyplot(fig)

with st.expander("📜 View Cryptographic Verification Receipt", expanded=False):
    receipt = current_task.receipt
    if receipt:
        receipt_data = [
            {
                "Verification Gate": "Solver Decision",
                "Status": receipt.solver_answer,
                "Condition": "Graph shortest-path first hop",
            },
            {
                "Verification Gate": "Independent Resolver",
                "Status": receipt.independent_answer,
                "Condition": "Direct board arrow reading",
            },
            {
                "Verification Gate": "Dual Agreement Invariant",
                "Status": "✅ PASSED" if receipt.agree else "❌ FAILED",
                "Condition": "solver == independent",
            },
            {
                "Verification Gate": "DOM Render Fidelity",
                "Status": "✅ PASSED" if receipt.fidelity_ok else "❌ FAILED",
                "Condition": "Arrow & text DOM bounds match spec",
            },
            {
                "Verification Gate": "Evidence Visibility",
                "Status": f"✅ PASSED ({receipt.evidence_visible_ratio * 100:.1f}%)"
                if receipt.visibility_ok
                else "❌ FAILED",
                "Condition": "Evidence occlusion <= 5%",
            },
            {
                "Verification Gate": "Blind Prior Filter",
                "Status": "✅ PASSED (No leakage)" if not receipt.blind_rejected else "❌ FAILED",
                "Condition": "Zero-image guessing accuracy <= 25%",
            },
            {
                "Verification Gate": "Counterfactual Pair Verified",
                "Status": "✅ VERIFIED" if receipt.pair_verified else "N/A (Standard task)",
                "Condition": "Single visual change flipped gold answer",
            },
            {
                "Verification Gate": "Human Audit Status",
                "Status": receipt.human_audit.upper(),
                "Condition": "Ecological validity spot-check",
            },
        ]
        st.table(receipt_data)
    else:
        st.info("Task receipt not assembled for this synthetic instance.")
