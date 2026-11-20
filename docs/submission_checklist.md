# Sanket Submission Checklist & Deliverables Matrix

This document maps each required deliverable from the track brief and [docs/prd.md Section 10](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/docs/prd.md#L116-L126) to its exact repository path, verification status, and evidence artifact.

---

## Deliverables Matrix

| # | Event Requirement | Sanket Deliverable | Canonical Path(s) | Verification Command / Evidence | Status |
|:---:|---|---|---|---|:---:|
| **1** | **Reusable Generation and Evaluation Pipeline** | Standalone Python package, Typer CLI, Makefile automation, Docker container | • [sanket/cli.py](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/sanket/cli.py)<br>• [Makefile](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/Makefile)<br>• [Dockerfile](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/Dockerfile)<br>• [scripts/smoke_test.py](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/scripts/smoke_test.py) | `make verify-all`<br>`docker build -t sanket .` | **READY** |
| **2** | **Sample Tasks with Validation Evidence** | Balanced sample task set with dual-path verification receipts, scenes, images, and human audit log | • [data/sample_tasks/](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/data/sample_tasks/)<br>• [data/sample_tasks/tasks.jsonl](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/data/sample_tasks/tasks.jsonl)<br>• [data/human_audit.csv](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/data/human_audit.csv)<br>• [reports/validation_report.md](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/reports/validation_report.md) | `python -m sanket.cli report`<br>Receipt checks: 100% solver agreement, 100% human concordance (23/23) | **READY** |
| **3** | **Findings on Model Strengths and Weaknesses** | Comprehensive evaluation findings report, perception gap analysis, publication figures (F1–F6), failure gallery | • [reports/findings_report.md](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/reports/findings_report.md)<br>• [reports/figures/](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/reports/figures/)<br>• [sanket/analysis/](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/sanket/analysis/) | Inspect F1 to F6 in `reports/figures/`<br>Failure gallery in `findings_report.md` Section 5 | **READY** |
| **4** | **Interactive Demo Distinguishing Right from Wrong** | Offline-capable Streamlit app with live generation, model queries, ground-truth reveal, venue graph route drawing, and receipt audit | • [demo/app.py](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/demo/app.py)<br>• [demo/pages/2_Findings.py](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/demo/pages/2_Findings.py)<br>• [demo/pages/3_Pairs.py](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/demo/pages/3_Pairs.py) | `make demo`<br>Access http://localhost:8501 (works offline with sample tasks) | **READY** |
| **5** | **Explanation of Application, Error Severity & Ground-Truth Rigour** | Dataset documentation card, real-world consequence mappings, mathematical proof of ground truth by construction | • [docs/dataset_card.md](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/docs/dataset_card.md)<br>• [config/consequences.yaml](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/config/consequences.yaml)<br>• [reports/validation_report.md](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/reports/validation_report.md)<br>• [README.md](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/README.md) | Documented in Dataset Card & Findings Report Section 4 | **READY** |

---

## Detailed Item Breakdown

### Item 1: Generation & Evaluation Pipeline
- **Package Implementation**:
  - Generator: [sanket/generator/](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/sanket/generator/) (Scene builder, Playwright DOM renderer, PIL augmentation pipeline).
  - Graph Engine: [sanket/graph/](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/sanket/graph/) (Orientation geometry and shortest-path graph solver).
  - Evaluator: [sanket/evaluate/](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/sanket/evaluate/) (Resumable runner, SQLite cache, adapters for Gemini, OpenRouter, Qwen, and oracles).
- **Automation & CLI**:
  - `sanket/cli.py` exposes `build`, `eval`, `pilot`, `report`.
  - `Makefile` standard targets: `setup`, `test`, `lint`, `smoke`, `pilot`, `build`, `eval`, `eval-real`, `report`, `demo`, `verify-all`.
  - `Dockerfile` containerizes the complete setup with headless Chromium and fonts.

### Item 2: Sample Tasks & Verification Evidence
- **Sample Dataset**:
  - 23 fully realized tasks in [data/sample_tasks/tasks.jsonl](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/data/sample_tasks/tasks.jsonl).
  - Balanced across all 6 question types: `DIRECT` (6), `BINDING` (5), `CLOSURE` (3), `OVERRIDE` (3), `EGOCENTRIC` (3), `ABSENT` (3).
  - 5 counterfactual minimal pairs included.
  - Rendered images in [data/sample_tasks/images/](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/data/sample_tasks/images/).
  - Structured scenes in [data/sample_tasks/scenes/](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/data/sample_tasks/scenes/).
- **Verification Evidence**:
  - Cryptographic verification receipts embedded in every task record.
  - Solver vs. Independent verifier agreement: **100.0%**.
  - DOM Render Fidelity: **100.0%**.
  - Target Evidence Visibility: **100.0%**.
  - Language Prior Guessing Filter: **96.0%** rejection of language-guessable tasks.
  - Human Audit Concordance: **100.0%** across 23 audited tasks logged in [data/human_audit.csv](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/data/human_audit.csv).

### Item 3: Findings & Visualizations
- **Empirical Findings Report**:
  - Published in [reports/findings_report.md](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/reports/findings_report.md).
  - Evaluated on image and text modalities with 95% Wilson confidence intervals.
  - Perception Gap quantified: e.g. Gemini 1.5 Flash drops from 83.3% on text to 33.3% on raw images (50.0% gap).
  - Failure gallery categorizing real error cases (arrow binding confusion, unlisted destination hallucinations).
- **Publication Figures**:
  - [reports/figures/F1_model_skill_heatmap.png](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/reports/figures/F1_model_skill_heatmap.png)
  - [reports/figures/F2_difficulty_curves.png](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/reports/figures/F2_difficulty_curves.png)
  - [reports/figures/F3_perception_gap.png](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/reports/figures/F3_perception_gap.png)
  - [reports/figures/F4_hallucination_rates.png](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/reports/figures/F4_hallucination_rates.png)
  - [reports/figures/F5_synthetic_vs_real.png](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/reports/figures/F5_synthetic_vs_real.png)
  - [reports/figures/F6_pair_consistency.png](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/reports/figures/F6_pair_consistency.png)

### Item 4: Interactive Streamlit Demo
- **App Features**:
  - Page 1 ([demo/app.py](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/demo/app.py)): Live task generation from venue graphs, interactive "Ask Model" query, instant CORRECT/WRONG evaluation badge, and "Reveal Proof" rendering the venue layout graph with route highlighting and verification receipts.
  - Offline Mode: Toggle "Use saved sample tasks" runs seamlessly without active network connection or API keys.
  - Page 2 ([demo/pages/2_Findings.py](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/demo/pages/2_Findings.py)): Interactive viewer for publication figures F1–F6 and curated failure gallery.
  - Page 3 ([demo/pages/3_Pairs.py](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/demo/pages/3_Pairs.py)): Side-by-side inspection of counterfactual minimal pairs.

### Item 5: Domain Application & Error Severity
- **Why Wayfinding Errors Matter**:
  - Grounded consequences mapped in [config/consequences.yaml](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/config/consequences.yaml).
  - Missing a `CLOSED` sign sends a traveller into a dangerous construction zone or locked emergency fire exit.
  - Hallucinating directions on `ABSENT` destinations causes missed flights or delayed medical attention in hospitals.
  - Egocentric rotation errors cause wheelchair users to take stairs or wrong-way escalators.
- **Methodological Documentation**:
  - Comprehensive dataset card in [docs/dataset_card.md](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/docs/dataset_card.md).
  - Architectural proof in [docs/architecture.md](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/docs/architecture.md).

---

## Acceptance Verification

```powershell
# 1. Run all checks (ruff lint, pytest test suite, smoke test)
make verify-all

# 2. Verify dataset card and checklist existence
Test-Path docs/dataset_card.md
Test-Path docs/submission_checklist.md

# 3. Check git tag
git tag -l "v1.0-dataset"
```
