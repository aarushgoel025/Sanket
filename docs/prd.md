# Product Requirements Document (PRD)

**Project:** Sanket (working name) — a verified visual benchmark factory for wayfinding signs
**Event:** Innodata hackathon on Hack2Skill, Track 2 (Visual Task Factory)
**Team:** 3 members (builder/lead, technical assistant, pitch lead)
**Build window:** about 12 days
**Status:** Draft v1

> The working name is **Sanket** (Hindi for "sign/signal"). If the team picks another name, find-and-replace `Sanket`, `sanket` and `sanket-bench` across all files.

---

## 1. Summary

Sanket is an automated pipeline that generates synthetic signboard images (railway stations, hospitals, metro stations), questions that require reading those signs, and reference answers that are **derived from a venue layout graph, never from a model**. It then uses the generated tasks to test frontier multimodal models and reports where they fail.

It is a **test-paper factory**, not a consumer app. The "customer" is a team that builds or evaluates a vision assistant (for example a Lens-style tool or an assistive app for visually impaired users) and wants to know whether the model reads signs correctly.

## 2. Problem

- People rely on signboards in stations, hospitals and transit hubs. Elderly people, first-time travellers, visitors who cannot read the local script and visually impaired users of AI assistants increasingly ask AI tools to read signs for them.
- A wrong reading has real cost: a missed train, or going the wrong way to an emergency ward.
- Existing checks focus on text recognition and translation. Few evaluations test the reasoning that follows: which arrow belongs to which text, whether a route is closed, whether a temporary notice overrides a permanent sign, and where something is after the person turns around.
- Multi-script signage (Hindi, English, regional scripts together) is rarely measured.

## 3. Goals and non-goals

### Goals
1. Generate at least 400 validated tasks across six question types with controlled difficulty.
2. Prove answer correctness independently of any model (graph solver, second independent code path, render-fidelity check, human audit).
3. Prove each task needs the image (blind test) and that single visual changes flip answers (minimal pairs).
4. Evaluate at least three multimodal models in two modes (image, structured text) and report strengths and weaknesses by skill and difficulty.
5. Check synthetic-to-real transfer with 20-30 hand-labelled real sign photos.
6. Ship a reusable, reproducible pipeline and a 3-minute live demo.

### Non-goals
- Not a navigation app, not a hosted API service, not a model-training project.
- No imitation of real organisations' branding; all venues and issuers are fictional.
- No claim that models are "good" or "bad" in general; findings are limited to what the data shows.

## 4. Users and use cases

| User | Need | How Sanket helps |
|---|---|---|
| AI evaluator at a lab or data company | Reliable, verifiable test data for multimodal models | Tasks with machine-checkable answers and a verification receipt per task |
| Assistive-app developer | Know where a model misreads signs | Skill-by-difficulty heatmaps and failure examples |
| Hackathon judges (Innodata) | Evidence of rigour, variety, reusability | Validation report, findings report, reproducible pipeline, live demo |

## 5. Unique selling points

1. **Ground truth by construction.** Answers come from a layout graph solver, re-derived by a second independent path.
2. **Verification receipt per task.** Every task carries machine-readable proof of its own validity.
3. **Visual-necessity filter.** Tasks answerable without the image are rejected (blind test).
4. **Minimal pairs.** Two images differing in one visual detail whose correct answers differ, exposing guessing.
5. **Perception versus reasoning split.** Each task is evaluated in image mode and structured-text mode; the gap isolates vision failures.
6. **India-specific multi-script coverage** and a **synthetic-to-real check** on hand-labelled photos.

## 6. Functional requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-1 | Define venues as YAML graphs (junctions, destinations, bearings in multiples of 45 degrees, lengths, open/closed status, bilingual labels) | Must |
| FR-2 | Solver computes first-hop bearing and path on open edges; reports ambiguity when equal-length shortest paths have different first hops | Must |
| FR-3 | Scene builder produces a board spec (entries, arrow angles, closure marks, temporary notices, distractors) from a venue, junction and seed | Must |
| FR-4 | Renderer produces PNG boards from HTML/SVG templates (three templates) with embedded fonts and exports per-element geometry | Must |
| FR-5 | Augmentation applies seeded difficulty knobs (perspective, blur, noise, lighting, clutter, occlusion that never covers evidence) | Must |
| FR-6 | Six question types: DIRECT, BINDING, CLOSURE, OVERRIDE, EGOCENTRIC, ABSENT, using a fixed 10-option answer set | Must |
| FR-7 | Independent verifier re-derives answers from the board spec; render-fidelity check compares rendered DOM against the spec; visibility check confirms evidence is visible | Must |
| FR-8 | Blind-test filter, minimal-pair builder, structural and perceptual de-duplication | Must |
| FR-9 | Model adapters (at least three models), response cache, resumable runner, strict answer parser, rule-based scorer | Must |
| FR-10 | Two evaluation modes: image and structured text | Must |
| FR-11 | Analysis: accuracy by question type and knob, Wilson 95% intervals, pair consistency, hallucination rate on ABSENT, perception gap, heatmaps, failure gallery | Must |
| FR-12 | Streamlit demo: generate a task, ask a model, auto-score, show the graph route and receipt | Must |
| FR-13 | Real-photo set loader and evaluation with the same scorer | Should |
| FR-14 | Second text script (regional) and second venue type | Should |
| FR-15 | Optional FastAPI wrapper (`/generate`, `/score`) | Could |

## 7. Non-functional requirements

- **Reproducibility:** same seed and config produce identical images and task files; one command runs the demo from a clean checkout.
- **Determinism:** no unseeded randomness anywhere in generation.
- **No leakage:** gold answers and scene specs never appear in prompts or image metadata.
- **Cost:** only free tiers; every model response cached; runs resumable after rate-limit errors.
- **Performance:** render under about 1.5 seconds per image; full 500-task build under about 20 minutes on a laptop.
- **Safety and ethics:** fictional venues and issuers, "SYNTHETIC" mark on images, no faces or personal data in real photos.

## 8. Question types and answer set

Fixed options for every question (so options never reveal the question type):
`AHEAD, AHEAD_RIGHT, RIGHT, BACK_RIGHT, BACK, BACK_LEFT, LEFT, AHEAD_LEFT, CLOSED, NOT_INDICATED`

| Type | What it tests | Gold rule |
|---|---|---|
| DIRECT | Reading the arrow for the target | Octant of the arrow for the target |
| BINDING | Matching arrows to the correct text in stacked or grouped boards | Same as DIRECT, harder layout |
| CLOSURE | Reading a closed or crossed-out route | `CLOSED` when no open route exists |
| OVERRIDE | A temporary notice beats a stale permanent sign | Octant of the first hop on the open shortest path |
| EGOCENTRIC | Reasoning after the person turns 90 left, 90 right or 180 | Octant after applying the turn |
| ABSENT | Destination not on the board | `NOT_INDICATED` |

## 9. Success metrics

| Metric | Target |
|---|---|
| Validated tasks | 400 or more, roughly balanced across six types |
| Solver versus independent verifier agreement | 100% on kept tasks (disagreements are rejected and logged) |
| Render-fidelity pass rate | 100% on kept tasks |
| Human audit (50 sampled tasks) | 95% or more pass |
| Oracle answerer score | 100% (scorer sanity check) |
| Random guesser score | Near chance (about 10%) |
| Models evaluated | 3 or more, two modes each |
| Real photos | 20 or more, hand-labelled |
| Clean-machine setup | Under 15 minutes |
| Demo length | 3 minutes |

## 10. Deliverables (mapped to the track brief)

| Track asks for | Sanket delivers |
|---|---|
| Reusable generation and evaluation pipeline | Python package, CLI, Makefile, Dockerfile |
| Sample tasks with validation evidence | `data/sample_tasks`, full dataset, validation report with receipts |
| Findings on model strengths and weaknesses | Findings report, heatmaps, failure gallery |
| Demo where scoring separates right from wrong | Streamlit demo with live scoring and route highlight |
| Explain application, why errors matter, how references are validated | Pitch deck, validation report, consequence stories |

## 11. Scope

- **MVP (must finish):** FR-1 to FR-12.
- **Stretch (in this order):** real-photo check, second script, second venue, minimal-pair extras, FastAPI wrapper.
- **Cut order if late:** third script, second venue, real-photo check, extra question types. Never cut the verifier, blind test or evaluation.

## 12. Timeline (12 days)

| Day | Outcome |
|---|---|
| 1 | Repo, schema, keys, one end-to-end smoke test (board, question, model call, score) |
| 2-3 | Graph, solver, scene builder, renderer, two venues |
| 4 | Question templates, text descriptions, independent verifier |
| 5 | Difficulty knobs, augmentation, scripts |
| 6 | Filters, pairs, de-duplication, build about 500 tasks |
| 7-8 | Evaluate models in both modes, real-photo set |
| 9 | Analysis, heatmaps, failure gallery |
| 10 | Demo, README, validation report |
| 11 | Deck, video, rehearsal, clean-machine test |
| 12 | Buffer and submission |

## 13. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Free-tier rate limits | Cache everything, resumable runner, small pilots first |
| Models ace easy tasks | Hard knobs from day 5; report whatever results appear |
| Agent-written ground-truth bug poisons the dataset | Human-owned critical modules, oracle test, human audit |
| Synthetic signs look unlike real ones | Augmentation plus real-photo comparison, stated openly as a limitation |
| Antigravity quota exhausted | Use agents for boilerplate and tests; keep fallback chat tools |
| Earlier deadline than planned | Check event page on day 1; cut order in section 11 |

## 14. Open questions

1. Official evaluation criteria and deadline on the event page (not yet read).
2. Whether specific models must be evaluated.
3. Dataset size or format requirements, and whether a video or deck is mandatory.
4. Which regional script to add as the third script.

## 15. Acceptance criteria

- `make test` passes, including the oracle, random-guesser, determinism, schema and no-leakage tests.
- `make build` creates at least 400 validated tasks with receipts.
- `make eval` produces cached results for at least three models in both modes.
- `make report` generates the validation and findings reports with figures.
- `make demo` starts the Streamlit app and a full generate-ask-score cycle works.
- A clean-machine run follows the README without help.
