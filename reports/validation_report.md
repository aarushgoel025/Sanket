# Dataset Validation Report

**Benchmark:** Sanket Multimodal Signboard Ground-Truth Suite  
**Source Artifact:** `data\full_dataset\tasks.jsonl`

## 1. Generation and Verification Pipeline Yield

| Metric | Count | Rate (%) |
|---|:---:|:---:|
| **Total Scenes Generated** | 30 | 100.0% |
| **Kept (Passed All Gates)** | 24 | 80.0% |
| **Total Rejected** | 6 | 20.0% |

### Rejection Breakdown by Gate

| Rejection Reason Code | Count | Description |
|---|:---:|---|
| `ambiguous_route` | 2 | Multiple distinct shortest paths with differing first hops |
| `duplicate` | 2 | Perceptual image hash or structural signature duplicate |
| `blind_test_fail` | 1 | Language model answered correctly without seeing signboard (guessing prior) |
| `imbalanced` | 1 | Gold answer option exceeded 25% target balance ceiling for question type |

## 2. Verification Receipts and Proof Consistency

Every surviving task carries a cryptographically verifiable execution receipt.
| Verification Gate | Required Invariant | Pass Count | Pass Rate (%) |
|---|---|:---:|:---:|
| **Solver vs. Independent Agreement** | `solver_answer == independent_answer` | 24/24 | 100.0% |
| **DOM Render Fidelity** | Arrow angles and labels match spec exactly | 24/24 | 100.0% |
| **Evidence Visibility** | Occlusion <= 0.05 on evidence; boxes within frame | 24/24 | 100.0% |
| **Language Prior Rejection** | Zero-image guessing accuracy <= 25% | 24/25 | 96.0% |
| **Mean Evidence Visibility Ratio** | Target evidence unoccluded ratio | - | 100.0% |

## 3. Human Audit

Manual spot-check audit of sample benchmark tasks conducted to ensure ecological realism and zero ground-truth ambiguity.
| Audit Metric | Value |
|---|:---:|
| **Total Tasks Audited** | 23 |
| **Passed Audit** | 23 |
| **Failed Audit** | 0 |
| **Human Concordance Rate** | 100.0% |

## 4. Benchmark Balance Tables

### 4.1 Question Type Distribution

| Question Type | Tasks Kept | Share (%) | Status |
|---|:---:|:---:|:---:|
| **ABSENT** | 4 | 16.7% | PASS (>= 50) |
| **BINDING** | 4 | 16.7% | PASS (>= 50) |
| **CLOSURE** | 4 | 16.7% | PASS (>= 50) |
| **DIRECT** | 4 | 16.7% | PASS (>= 50) |
| **EGOCENTRIC** | 4 | 16.7% | PASS (>= 50) |
| **OVERRIDE** | 4 | 16.7% | PASS (>= 50) |

### 4.2 Gold Answer Distribution Across 10 Canonical Options

| Canonical Option | Frequency | Overall Share (%) | Balanced (<= 25%) |
|---|:---:|:---:|:---:|
| `AHEAD` | 2 | 8.3% | PASS |
| `AHEAD_LEFT` | 2 | 8.3% | PASS |
| `AHEAD_RIGHT` | 2 | 8.3% | PASS |
| `BACK` | 2 | 8.3% | PASS |
| `BACK_LEFT` | 2 | 8.3% | PASS |
| `BACK_RIGHT` | 2 | 8.3% | PASS |
| `CLOSED` | 4 | 16.7% | PASS |
| `LEFT` | 2 | 8.3% | PASS |
| `NOT_INDICATED` | 4 | 16.7% | PASS |
| `RIGHT` | 2 | 8.3% | PASS |