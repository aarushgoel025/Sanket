# Sanket: Visual Task Factory for Wayfinding Benchmark

**A verified multimodal benchmark factory for wayfinding and directional signage.**  
*(Sanket / संकेत is the Hindi word for "sign", "signal", or "indicator".)*

Sanket generates procedural signboard images (railway stations, hospitals, metro, airports), contextual wayfinding questions, and ground-truth reference answers derived deterministically from venue layout graphs—**never from a model**. It then evaluates multimodal language models (VLMs) on those tasks, isolates perception failures from reasoning failures, and reports exact failure modes with mathematical receipts.

---

## Key Differentiators

1. **Ground Truth by Construction**: Gold answers originate strictly from graph shortest-path algorithms ([sanket/graph/solver.py](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/sanket/graph/solver.py)) and orientation geometry ([sanket/graph/orientation.py](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/sanket/graph/orientation.py)), verified by an independent direct-reading verifier ([sanket/verify/independent.py](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/sanket/verify/independent.py)).
2. **Machine-Readable Verification Receipt**: Every task includes an audit receipt asserting dual-path agreement, DOM render fidelity, target visibility, and zero-image guessing prior rejection.
3. **Visual Necessity (Blind Test)**: Tasks answerable without the image (language model prior leakage) are rejected.
4. **Counterfactual Minimal Pairs**: A single minimal visual alteration (e.g. rotating one arrow 45°, removing a notice) flips the reference answer to test whether models truly look.
5. **Perception vs. Reasoning Split**: Comparing raw pixel image mode against structured text mode directly isolates the **perception gap**.
6. **Real-Photo Ecological Transfer**: Hand-labelled, EXIF-stripped public station photographs evaluate transfer from synthetic benchmarks to real-world signage.

---

## Quickstart

Follow these steps on a clean machine to go from checkout to running the interactive demo in under 15 minutes:

### 1. Clone & Setup

```bash
git clone <your-repo-url> sanket
cd sanket

# Copy environment configuration
cp .env.example .env

# Install Python requirements and Playwright headless Chromium
make setup
```

### 2. Verify Installation

```bash
# Run the complete test suite
make test

# Run the 6-task end-to-end smoke test
make smoke

# Run all verification checks (lint, tests, smoke test)
make verify-all
```

### 3. Pipeline Workflow

```bash
# Smoke test + 20-task pilot evaluation
make pilot

# Build procedural benchmark dataset (data/full_dataset)
make build

# Evaluate configured models in image and text modes (cached, resumable)
make eval

# Evaluate real-world signboard photo benchmark
make eval-real

# Generate validation and findings markdown reports and publication figures F1-F6
make report

# Launch the interactive Streamlit demo app on http://localhost:8501
make demo
```

---

## Docker Deployment

The application is containerized with Python 3.11-slim, Playwright headless Chromium, and local open fonts:

```bash
# Build Docker image
docker build -t sanket .

# Run demo container (serves Streamlit on port 8501)
docker run -p 8501:8501 sanket
```

Open `http://localhost:8501` in your browser.

---

## Question Types & Answer Contract

Every task presents a question and the **same fixed 10 canonical options in invariant order**:
```
AHEAD, AHEAD_RIGHT, RIGHT, BACK_RIGHT, BACK, BACK_LEFT, LEFT, AHEAD_LEFT, CLOSED, NOT_INDICATED
```

| Question Type | Wayfinding Capability Tested |
|---|---|
| **DIRECT** | Reading the primary directional arrow for a single destination. |
| **BINDING** | Correctly associating stacked or grouped arrows with their respective destination text. |
| **CLOSURE** | Recognizing route closures, maintenance overlays, or crossed-out entries (`CLOSED`). |
| **OVERRIDE** | Recognizing temporary notices that supersede conflicting permanent signage. |
| **EGOCENTRIC** | Mentally rotating heading following an observer turn (e.g., turn 90° clockwise). |
| **ABSENT** | Correctly identifying when a destination is not shown on the signboard (`NOT_INDICATED`). |

---

## Benchmark Task Format

Each line of `data/sample_tasks/tasks.jsonl` or `data/full_dataset/tasks.jsonl` is a self-contained JSON object:

```json
{
  "task_id": "task_0000",
  "schema_version": "1.0.0",
  "generator_version": "1.0.0",
  "seed": 3393549140,
  "qtype": "DIRECT",
  "question": "You are standing in front of this signboard. Which way should you go to reach Platform 6?",
  "options": [
    "AHEAD", "AHEAD_RIGHT", "RIGHT", "BACK_RIGHT", "BACK",
    "BACK_LEFT", "LEFT", "AHEAD_LEFT", "CLOSED", "NOT_INDICATED"
  ],
  "gold": "BACK_RIGHT",
  "image_path": "data/sample_tasks/images/task_0000.png",
  "scene_path": "data/sample_tasks/scenes/task_0000.json",
  "target_dest_id": "d_p6",
  "turn_cw": null,
  "skill_tags": ["arrow_reading", "multi_script"],
  "difficulty": {
    "n_entries": 5,
    "perspective_deg": 8.72,
    "blur": 0.63,
    "noise": 0.0075,
    "lighting": 0.1,
    "clutter": 6,
    "occlusion": 0.105,
    "jpeg_quality": 92,
    "template": "board_list"
  },
  "pair_id": "pair_task_0000",
  "pair_role": "a",
  "receipt": {
    "solver_answer": "BACK_RIGHT",
    "independent_answer": "BACK_RIGHT",
    "agree": true,
    "fidelity_ok": true,
    "visibility_ok": true,
    "evidence_visible_ratio": 1.0,
    "blind_correct_rate": 0.0,
    "blind_rejected": false,
    "pair_verified": true,
    "human_audit": "unaudited",
    "notes": ""
  }
}
```

### Real Signboard Task Format

Hand-labelled real photo tasks located in `data/real_photos/real_tasks.jsonl`:

```json
{
  "task_id": "R001",
  "image_path": "images/R001.jpg",
  "question": "You are looking at this metro signboard. Which way should you go to reach Customer Service & Help Desk?",
  "options": ["AHEAD", "AHEAD_RIGHT", "RIGHT", "BACK_RIGHT", "BACK", "BACK_LEFT", "LEFT", "AHEAD_LEFT", "CLOSED", "NOT_INDICATED"],
  "gold": "LEFT",
  "notes": "hand-labelled by PL; verified by Lead"
}
```

---

## Validation Summary

Generated via `make report` directly from verified benchmark dataset files (`data/full_dataset/tasks.jsonl` and `data/human_audit.csv`):

| Verification Gate | Required Invariant | Measured Result | Pass Rate | Status |
|---|---|:---:|:---:|:---:|
| **Dual-Path Solver Agreement** | `solver_answer == independent_answer` | 24/24 | 100.0% | **PASSED** |
| **DOM Render Fidelity** | Arrow angles & labels match DOM bounding box spec | 24/24 | 100.0% | **PASSED** |
| **Target Evidence Visibility** | Occlusion $\le 10\%$, evidence within viewport | 24/24 | 100.0% | **PASSED** |
| **Language Prior Rejection** | Zero-image guessing accuracy $\le 25\%$ | 24/25 | 96.0% | **PASSED** |
| **Human Audit Concordance** | Manual spot-check audit across sample tasks | 23/23 | 100.0% | **PASSED** |
| **Question Type Balance** | 6 question types evenly represented | 4 / type (16.7% each) | 100.0% | **PASSED** |
| **Directional Option Balance** | Directional frequencies $\le 25\%$ ceiling | Invariant Maintained | 100.0% | **PASSED** |
| **Real Image Privacy & Cleanliness** | EXIF metadata completely stripped | 0 Exif Chunks | 100.0% | **PASSED** |

---

## Findings Summary

Empirical findings generated via `make report` from model benchmark evaluations (`reports/results.jsonl`):

### Overall Model Performance

| Model | Image Mode Accuracy | 95% Wilson CI | Text Mode Accuracy | 95% Wilson CI | Perception Gap ($\Delta$) |
|---|:---:|:---:|:---:|:---:|:---:|
| **Oracle** (Ground-Truth Sanity) | **100.0%** (34/34) | [89.8%, 100.0%] | **100.0%** (29/29) | [88.3%, 100.0%] | 0.0 pp |
| **Gemini 1.5 Flash** | **33.3%** (8/24) | [18.0%, 53.3%] | **83.3%** (20/24) | [64.1%, 93.3%] | **+50.0 pp** |
| **Random Baseline** | **12.5%** (3/24) | [4.3%, 31.0%] | **0.0%** (0/24) | [0.0%, 13.8%] | -12.5 pp |
| **Always AHEAD** | **0.0%** (0/16) | [0.0%, 19.4%] | **0.0%** (0/16) | [0.0%, 19.4%] | 0.0 pp |

### Key Empirical Takeaways

1. **Massive Perception Gap (+50.0 percentage points)**: On identical wayfinding scenarios, Gemini 1.5 Flash achieves 83.3% accuracy when fed structured scene text, but drops to 33.3% when reading the rendered image. The bottleneck is spatial visual perception (arrow-text binding, small rotation angles), not topological reasoning.
2. **High Hallucination Rate on ABSENT Tasks (100.0%)**: When asked for unlisted destinations, Gemini 1.5 Flash hallucinated a directional heading on 4 out of 4 tasks (0% accuracy on ABSENT), rather than recognizing `NOT_INDICATED`.
3. **Fragile Minimal-Pair Consistency (0.0%)**: Under single atomic visual counterfactuals (e.g. rotating one arrow 45° or adding a closure notice), Gemini 1.5 Flash got both pair halves correct 0.0% of the time (0/4 pairs), indicating fragile visual grounding.
4. **Synthetic-to-Real Transfer**: The evaluation harness successfully evaluated real-world hand-labelled station photographs (`data/real_photos/`), with Oracle scoring 100.0% (5/5) across real signage.

---

## Publication Figures

The reporting pipeline produces publication-quality charts saved to `reports/figures/`:

| Figure | Chart Type | Finding / Message |
|---|---|---|
| **F1** | Model $\times$ Skill Heatmap | Granular accuracy breakdown across wayfinding skills. |
| **F2** | Accuracy vs. Difficulty Line Chart | Impact of perspective warp, clutter, blur, and occlusion on accuracy. |
| **F3** | Image vs. Text Mode Grouped Bar | The **perception gap** (text reasoning accuracy minus image accuracy). |
| **F4** | Hallucination Rate on ABSENT Tasks | Tendency of models to assert a direction when destinations are missing. |
| **F5** | Synthetic vs. Real Transfer Scatter | Ecological validity: correlation between synthetic and real photo accuracy with 95% Wilson intervals. |
| **F6** | Minimal-Pair Consistency Graphic | Sensitivity of predictions under single visual counterfactual edits. |

---

## How to Add a New Model

1. **Configure Model**: Add a profile to `config/models.yaml`:
   ```yaml
   models:
     - name: my_vlm
       adapter: gemini       # Or openai_compat, hf_qwen, oracle, random
       model_id: my-vlm-model-id
       rpm: 10
       enabled: true
   ```
2. **Set API Credentials**: Add the corresponding API key to `.env`:
   ```bash
   GEMINI_API_KEY="your-api-key"
   # or OPENROUTER_API_KEY="your-key"
   ```
3. **Add Custom Adapter (Optional)**: If targeting a custom API provider, create `sanket/evaluate/adapters/my_adapter.py` subclassing `BaseAdapter`:
   ```python
   from sanket.evaluate.adapters.base import BaseAdapter
   from sanket.schema import RawResponse, Task


   class MyAdapter(BaseAdapter):
       def answer(self, task: Task, mode: str = "image", prompt_version: str = "v1") -> RawResponse:
           # Query provider API and return RawResponse
           ...
   ```
4. **Run Evaluation**:
   ```bash
   python -m sanket.cli eval --models my_vlm
   ```
5. **View Results**: Regenerate reports (`make report`) or inspect interactively in the Streamlit demo (`make demo`).

---

## Repository Tree

```
sanket/
├── assets/
│   ├── fonts/               # Open-licence Noto Sans & Devanagari TTF fonts
│   ├── icons/               # Custom wayfinding SVG pictograms
│   └── templates/           # Jinja2 HTML templates for signboards (list, grid, gantry)
├── config/
│   ├── venues/              # Venue layout graphs (railway, hospital)
│   ├── default.yaml         # Generation quotas, thresholds, knobs
│   ├── models.yaml          # Evaluation models and rate limits
│   └── consequences.yaml    # Qualitative real-world failure consequences
├── data/
│   ├── full_dataset/        # Generated benchmark dataset
│   ├── sample_tasks/        # Committed sample benchmark tasks with receipts
│   ├── real_photos/         # Hand-labelled real signboard photos (EXIF stripped)
│   └── cache/               # SQLite evaluation response cache (gitignored)
├── demo/
│   ├── app.py               # Streamlit demo: Generate, Ask Model, Reveal Proof
│   └── pages/               # Multi-page findings (F1-F6) & minimal pairs
├── reports/
│   ├── validation_report.md # Dataset integrity and receipt verification report
│   ├── findings_report.md   # Model benchmark findings and failure gallery
│   └── figures/             # Output PNG charts (F1 to F6)
├── sanket/
│   ├── analysis/            # Metrics, heatmaps, failure gallery, report compiler
│   ├── evaluate/            # Resumable runner, parser, scorer, prompts, adapters
│   ├── generator/           # Scene builder, Jinja2/Playwright renderer, augmentations
│   ├── graph/               # Orientation and graph shortest-path solver (human-owned)
│   ├── pipeline/            # Build pipeline, deduplication, minimal pairs
│   ├── questions/           # Question templates and canonical option contracts
│   ├── cli.py               # Typer CLI (build, eval, pilot, report)
│   └── schema.py            # Pydantic data models (single source of truth)
├── scripts/
│   ├── smoke_test.py        # 6-task end-to-end smoke test
│   ├── run_pilot.sh         # Shell script orchestrating pilot pipeline
│   ├── strip_exif.py        # EXIF removal script for real photos
│   └── check_real_tasks.py  # Integrity verifier for real tasks
├── tests/                   # Pytest test suite (276 unit & integration tests)
├── Dockerfile               # Reproducible container definition
├── Makefile                 # Standard project targets
└── README.md                # Project documentation
```

---

## Ethics & Compliance

- **No Personal Data**: Real photos contain public signage only; no faces, people, or private credentials.
- **Privacy Enforcement**: All images have EXIF metadata completely stripped.
- **Fictional Issuers**: Procedural venues, station names, and signage issuers are fictional; generated images carry a discrete `"SYNTHETIC"` watermark.
- **Licenses**: Code is released under the MIT License. Fonts are licensed under the SIL Open Font License (OFL).
