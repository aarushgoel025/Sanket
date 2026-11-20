# Dataset Card: Sanket Wayfinding Signboard Benchmark

## 1. Dataset Summary & Purpose

**Sanket** (संकेत, Hindi for *sign*, *signal*, or *indicator*) is a rigorous multimodal benchmark factory evaluating vision-language models on wayfinding, directional sign reading, and egocentric spatial reasoning.

Wayfinding signage in complex public transit hubs (railway stations, metro interchanges, multi-building hospitals, and airport terminals) requires precise visual perception:
1. Grounding multi-lingual and multi-script text labels.
2. Resolving spatial arrow-to-label binding on stacked and grid signboards.
3. Accounting for route closures, maintenance cross-outs, and conflicting override notices.
4. Performing egocentric spatial transformations (re-orienting headings relative to observer position).
5. Detecting the absence of unlisted destinations rather than hallucinating paths.

Sanket provides ground truth **by construction**: reference answers are calculated deterministically via shortest-path graph search over verified venue layouts, guaranteed by dual-path verification, and validated against zero-image guessing priors.

---

## 2. Procedural Generation Methodology

Sanket tasks are procedurally synthesized using a multi-stage pipeline:

1. **Venue Graph Formulation**: Verified graph definitions ([config/venues/](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/config/venues/)) specify nodes (entrances, junctions, platforms, wings) and 8-way directed edges with bearings restricted to exact multiples of 45°.
2. **Scene & Signboard Placement**: A random observer pose $(u, \theta)$ is sampled. Directed signage entries are sampled from destinations reachable via valid outgoing corridors.
3. **Template Rendering**: HTML/CSS templates ([assets/templates/](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/assets/templates/)) are populated with authentic wayfinding iconography ([assets/icons/](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/assets/icons/)) and open-licensed typography (Noto Sans, Noto Sans Devanagari) and rendered headlessly via Playwright Chromium.
4. **Physical Augmentation**: Photorealistic transformations simulate real-world capture artifacts:
   - 3D homographic perspective tilt (0° to 35°).
   - Gaussian blur ($\sigma \in [0.2, 1.5]$) and additive sensor noise.
   - Non-uniform directional lighting gradients and shadow falloff.
   - Environmental clutter (surrounding walls, pillars, tiles).
   - Obstructions and occlusions (structural columns, overhead lamps).
5. **Deterministic Seeding**: Every random operation consumes an explicit `numpy.random.Generator` initialized from the task seed. Generated PNG files are stripped of all EXIF metadata.

---

## 3. Question Types

Sanket benchmarks six core wayfinding skills across distinct question types:

| Question Type | Wayfinding Capability Tested | Failure Mode Detected |
|---|---|---|
| **DIRECT** | Reading the primary directional arrow for a single listed destination. | Misreading arrow orientation or 45° bearing angles. |
| **BINDING** | Associating stacked or grouped arrows with their respective destination text blocks. | Spatial proximity misattribution across visual hierarchy. |
| **CLOSURE** | Detecting maintenance stickers, red cross-out badges, or closure banners. | Routing travellers toward shut down corridors or platforms (`CLOSED`). |
| **OVERRIDE** | Resolving temporary directional notices that supersede permanent signage. | Blindness to advisory notices posted adjacent to permanent boards. |
| **EGOCENTRIC** | Mentally rotating heading following an observer rotation (e.g., "turn 90° clockwise"). | Inability to perform viewer-relative coordinate frame transforms. |
| **ABSENT** | Recognizing when a destination is not indicated on the signboard. | Hallucinating directional arrows for unlisted destinations (`NOT_INDICATED`). |

---

## 4. Canonical Answer Options

To eliminate open-ended text evaluation ambiguity, every task presents the **same 10 canonical options in invariant order**:

```
AHEAD, AHEAD_RIGHT, RIGHT, BACK_RIGHT, BACK, BACK_LEFT, LEFT, AHEAD_LEFT, CLOSED, NOT_INDICATED
```

- Bearings are strictly 8-way multiples of 45°:
  - `AHEAD`: 0° (straight ahead)
  - `AHEAD_RIGHT`: 45° clockwise
  - `RIGHT`: 90° clockwise
  - `BACK_RIGHT`: 135° clockwise
  - `BACK`: 180° (turn around / behind)
  - `BACK_LEFT`: 225° clockwise (135° counter-clockwise)
  - `LEFT`: 270° clockwise (90° counter-clockwise)
  - `AHEAD_LEFT`: 315° clockwise (45° counter-clockwise)
- Status options:
  - `CLOSED`: Corridor, gate, or destination is blocked or under maintenance.
  - `NOT_INDICATED`: Destination does not appear on the sign.

---

## 5. Verification Pipeline & Integrity Receipts

Every task in the benchmark must pass four automated verification gates before admission:

1. **Dual-Path Solver Agreement**:
   - Primary graph solver ([sanket/graph/solver.py](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/sanket/graph/solver.py)) computes shortest path and relative bearing from observer coordinate frame.
   - Independent direct-reading verifier ([sanket/verify/independent.py](file:///c:/Users/Aarush/OneDrive/Desktop/Sanket/sanket/verify/independent.py)) extracts arrow orientation directly from rendered scene entries.
   - Invariant: `solver_answer == independent_answer`. Any disagreement causes immediate task rejection.
2. **DOM Render Fidelity**:
   - Inspects rendered DOM bounding boxes to ensure arrow vector angles and destination text bounding boxes match the scene specification within tolerances.
3. **Evidence Visibility & Bounding Box Sanity**:
   - Computes target evidence pixel visibility after perspective warping and clutter occlusion. Requires unoccluded ratio $\ge 0.90$ and evidence completely contained within image boundaries.
4. **Blind-Test Language Prior Filtering**:
   - Zero-image text-only prompts evaluated against language baselines. Tasks where gold answers are guessable from language priors alone ($> 25\%$ chance) are discarded.
5. **Counterfactual Minimal Pair Verification**:
   - For every base task, an atomic visual variant is constructed (e.g. 45° arrow rotation, adding/removing closure notice). Both partners must pass all gates, ensuring answer changes are driven solely by visual differences.

---

## 6. Real-World Signboard Benchmark

To evaluate synthetic-to-real transfer, Sanket includes `data/real_photos/`:
- Hand-labelled photographs of public transit signage (metro stations, railway terminals, hospitals).
- Complete EXIF and sensor metadata stripped via `scripts/strip_exif.py`.
- Formatted with identical question schemas and the 10 canonical options.
- Evaluated under the same runner and scorer harness.

---

## 7. Known Limitations

1. **Planar Board Assumption**: Signboards are rendered as planar surfaces with 3D perspective homographies. Curved boards, digital LED ticker displays, and cylindrical pillars are not yet modeled.
2. **Single-Signboard Scope**: Each task models an observer standing before a single primary sign structure (with optional temporary override notices), rather than continuous video navigation through long corridor chains.
3. **Free-Tier Rate Limits**: Free model APIs (e.g. Gemini 1.5 Flash, OpenRouter) enforce rate limits (typically 10-15 RPM), requiring SQLite caching and exponential backoff during large-scale runs.
4. **Synthetic Rendering Domain**: While augmented with photorealistic noise, lighting, and blur, synthetic HTML-rendered signs exhibit cleaner font rendering than worn, weathered physical enamel signs.

---

## 8. Ethics, Privacy & Responsible AI

- **No Personal Data**: Real photographs contain public architectural wayfinding signage only. No human faces, personal identifiers, license plates, or private credentials are included.
- **Fictional Venues**: All procedural station names, facility names, and branding (e.g., "Kalyan Jn - Platform 6", "Ward 3 / Radiology") are synthetic or fictionalized.
- **Synthetic Watermarking**: Procedural images feature a discrete `"SYNTHETIC"` provenance watermark.
- **Fairness & Accessibility**: Signage incorporates bilingual scripts (English and Devanagari Hindi) and high-contrast color palettes adhering to transit accessibility standards.

---

## 9. Licence & Reproduction

- **Software Licence**: Sanket code and test suites are licensed under the MIT Licence.
- **Asset Licences**: Fonts (Noto Sans, Noto Sans Devanagari) are distributed under the SIL Open Font License 1.1. Icons are custom SVGs released to the public domain (CC0).
- **Reproduction**:
  ```bash
  # Reproduce sample tasks and dataset deterministically
  python -m sanket.cli build --out-dir data/sample_tasks --n-tasks 20 --seed 42
  
  # Run full verification and evaluation
  make verify-all
  make report
  ```

---

## 10. How to Cite

```bibtex
@software{sanket2026wayfinding,
  author = {Sanket Benchmark Team},
  title = {Sanket: A Verified Multimodal Signboard and Wayfinding Benchmark Factory},
  year = {2026},
  publisher = {GitHub},
  howpublished = {\url{https://github.com/sanket-benchmark/sanket}}
}
```
