# Release Notes: v1.0-dataset

**Release:** `v1.0-dataset`  
**Date:** November 20, 2026  
**Status:** Frozen Benchmark Submission Package

---

## Overview

The `v1.0-dataset` release tags the complete, verified, and reproducible release of the **Sanket** multimodal signboard and wayfinding benchmark factory. All data contracts, schema models, venue graphs, question templates, verification receipts, evaluation reports, and sample datasets are frozen.

---

## What Is Frozen

### 1. Data Contracts & Schema Models
- **Canonical Option Order**: Invariant 10-option set in exact order:
  `AHEAD, AHEAD_RIGHT, RIGHT, BACK_RIGHT, BACK, BACK_LEFT, LEFT, AHEAD_LEFT, CLOSED, NOT_INDICATED`.
- **Discrete Bearings**: Headings and arrow rotations strictly quantized to 8-way multiples of 45° in [sanket/schema.py](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/sanket/schema.py).
- **Zero Prompt Leakage**: Zero-image and image prompts contain strictly question text, option choices, and optional visual pixel buffer. No ground-truth answers, scene graphs, or receipts in model prompts.

### 2. Human-Owned Core Modules
- Graph orientation engine: [sanket/graph/orientation.py](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/sanket/graph/orientation.py)
- Graph shortest-path solver: [sanket/graph/solver.py](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/sanket/graph/solver.py)
- Independent direct-reading verifier: [sanket/verify/independent.py](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/sanket/verify/independent.py)

### 3. Frozen Datasets & Assets
- **Sample Benchmark Dataset** ([data/sample_tasks/](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/data/sample_tasks/)): 23 tasks balanced across 6 question types with 5 counterfactual minimal pairs, images, scene specs, and cryptographic verification receipts.
- **Human Audit Records** ([data/human_audit.csv](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/data/human_audit.csv)): 23 audited tasks showing 100% human concordance.
- **Real Signboard Photo Benchmark** ([data/real_photos/](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/data/real_photos/)): Public transit photos with EXIF metadata stripped.
- **Venues & Templates**: Railway station and hospital venue graphs ([config/venues/](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/config/venues/)), Jinja2 HTML templates, and open-license Noto fonts.

### 4. Verified Reports & Visualizations
- Dataset validation report ([reports/validation_report.md](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/reports/validation_report.md)): 100% solver-independent agreement, 100% render fidelity, 100% evidence visibility.
- Findings and evaluation report ([reports/findings_report.md](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/reports/findings_report.md)): Complete evaluation results across image and text modalities, failure gallery, and perception gap quantification.
- Publication charts: Figures `F1` through `F6` in [reports/figures/](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/reports/figures/).

### 5. Application & Execution Harness
- Streamlit interactive demo ([demo/app.py](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/demo/app.py)) with offline fallback mode.
- Playwright Chromium headless renderer and PIL augmentation pipeline.
- SQLite evaluation response cache.
- Complete automated test suite (283 passing unit and integration tests).
