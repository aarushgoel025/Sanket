# Architecture

**Project:** Sanket (working name)
**Style:** Python package plus CLI. Seeded, file-based, no database server, no hosted API required.

---

## 1. System overview

Two pipelines share one dataset:

1. **Build pipeline** (`sanket build`): venue graph, scene, render, augment, question, verify, filter, dataset.
2. **Evaluation pipeline** (`sanket eval`, `sanket report`): dataset, model adapters, scorer, analysis, reports and demo.

```
config.yaml + venue YAMLs
        |
        v
  Scene builder --> Renderer (HTML/SVG -> PNG) --> Augmenter
        |                    |                        |
        v                    v                        v
  Question builder      DOM geometry export       Final image
        \_______________________|________________________/
                                v
                    Verifier + filters (receipt)
                                v
                 data/full_dataset (images + tasks.jsonl + rejected.jsonl)
                                v
        Model adapters (image mode, text mode) --> cache --> Scorer
                                v
              Analysis --> reports, figures --> Streamlit demo
```

## 2. Repository structure

```
sanket/                          # repo root (suggested repo name: sanket-bench)
├── AGENTS.md                    # rules for Antigravity agents
├── README.md
├── Makefile
├── Dockerfile
├── pyproject.toml
├── requirements.txt
├── .env.example                 # GEMINI_API_KEY=, OPENROUTER_API_KEY=, HF_TOKEN=
├── .gitignore                   # .env, data/cache/, __pycache__/
├── config/
│   ├── default.yaml             # counts, seeds, knob ranges, thresholds
│   ├── models.yaml              # adapters, model ids, rate limits
│   └── venues/
│       ├── railway_station.yaml
│       └── hospital.yaml
├── assets/
│   ├── fonts/                   # Noto Sans, Noto Sans Devanagari, one regional script
│   ├── icons/                   # own SVG pictograms
│   └── templates/
│       ├── board_list.html.j2
│       ├── board_grid.html.j2
│       └── board_gantry.html.j2
├── sanket/
│   ├── __init__.py
│   ├── cli.py                   # build, verify, eval, report, pilot
│   ├── schema.py                # pydantic models (single source of truth)
│   ├── config.py                # YAML loading and validation
│   ├── graph/
│   │   ├── venue.py             # load venue, build networkx graph
│   │   ├── solver.py            # first hops, paths, ambiguity   [HUMAN-OWNED]
│   │   └── orientation.py       # bearings, octants, turns       [HUMAN-OWNED]
│   ├── generator/
│   │   ├── scene_builder.py     # venue + seed + qtype -> Scene
│   │   ├── distractors.py       # ads, unrelated icons, numbers
│   │   ├── renderer.py          # Jinja2 + Playwright -> PNG + geometry JSON
│   │   ├── augment.py           # OpenCV / Albumentations, seeded
│   │   └── text_description.py  # Scene -> structured text (text mode)
│   ├── questions/
│   │   ├── templates.py         # six question types
│   │   └── options.py           # fixed 10-option set, option order
│   ├── verify/
│   │   ├── independent.py       # second answer path from the Scene [HUMAN-OWNED]
│   │   ├── fidelity.py          # rendered DOM vs Scene spec
│   │   ├── visibility.py        # evidence visible and unoccluded
│   │   ├── blind_test.py        # answer without image
│   │   ├── pairs.py             # minimal-pair builder and checker
│   │   ├── dedupe.py            # structural + perceptual hash
│   │   └── receipt.py           # assemble Receipt
│   ├── pipeline/
│   │   └── build_dataset.py     # orchestrates the build, writes outputs
│   ├── evaluate/
│   │   ├── adapters/
│   │   │   ├── base.py          # BaseAdapter interface
│   │   │   ├── gemini.py
│   │   │   ├── openai_compat.py # OpenRouter / Groq style endpoints
│   │   │   ├── hf_qwen.py       # open VLM via Hugging Face or imported results
│   │   │   └── fake.py          # oracle / random / fixed adapters for tests
│   │   ├── prompts.py           # versioned prompt builder (no gold, no scene)
│   │   ├── parser.py            # strict "ANSWER: <OPTION>" parser
│   │   ├── modes.py             # image mode, text mode
│   │   ├── cache.py             # SQLite response cache
│   │   ├── runner.py            # resumable, rate-limited
│   │   └── scorer.py            # exact match, rule-based
│   └── analysis/
│       ├── metrics.py           # accuracy, Wilson CI, pair consistency, gap
│       ├── heatmaps.py
│       ├── failure_gallery.py
│       └── report.py            # writes reports/*.md
├── data/
│   ├── sample_tasks/            # about 20 tasks committed to git
│   ├── full_dataset/
│   │   ├── images/
│   │   ├── scenes/              # hidden scene specs (not given to models)
│   │   ├── tasks.jsonl
│   │   └── rejected.jsonl       # rejected tasks with reasons
│   ├── real_photos/
│   │   ├── images/
│   │   └── real_tasks.jsonl
│   └── cache/                   # gitignored
├── reports/
│   ├── validation_report.md
│   ├── findings_report.md
│   └── figures/
├── demo/
│   └── app.py                   # Streamlit
├── docs/
│   ├── prd.md  architecture.md  design.md  rules.md  dataset_card.md
├── scripts/
│   ├── smoke_test.py
│   ├── run_pilot.sh
│   ├── colab_qwen.py            # run an open VLM on free Kaggle/Colab GPU
│   └── strip_exif.py            # remove EXIF from real photos
└── tests/
    ├── test_orientation.py  test_solver.py  test_schema.py
    ├── test_determinism.py  test_renderer.py  test_verifier.py
    ├── test_scorer_oracle.py  test_parser.py  test_no_leakage.py
```

## 3. Core data models (`schema.py`, pydantic)

```python
Octant = Literal[
    "AHEAD", "AHEAD_RIGHT", "RIGHT", "BACK_RIGHT", "BACK", "BACK_LEFT", "LEFT", "AHEAD_LEFT"
]
Answer = Literal[*Octant.__args__, "CLOSED", "NOT_INDICATED"]
Bearing = Literal[0, 45, 90, 135, 180, 225, 270, 315]  # all bearings multiples of 45


class Label(BaseModel):
    en: str
    hi: str | None = None
    regional: str | None = None
    regional_script: str | None = None


class Node(BaseModel):
    id: str
    kind: Literal["junction", "destination"]
    category: str | None
    label: Label


class Edge(BaseModel):
    a: str
    b: str
    bearing_ab: Bearing
    length: float
    status: Literal["open", "closed"] = "open"


class Venue(BaseModel):
    id: str
    name: str
    kind: Literal["railway", "hospital", "metro"]
    nodes: list[Node]
    edges: list[Edge]


class BoardEntry(BaseModel):
    dest_id: str
    label: Label
    arrow_angle: Bearing  # clockwise from "up" in the viewer's frame
    status: Literal["open", "closed"] = "open"
    source: Literal["permanent", "temporary_notice"] = "permanent"


class Knobs(BaseModel):
    n_entries: int
    scripts: list[str]
    perspective_deg: float
    blur: float
    noise: float
    lighting: float
    clutter: int
    occlusion: float
    jpeg_quality: int
    template: str


class Scene(BaseModel):
    scene_id: str
    venue_id: str
    junction_id: str
    heading: Bearing
    entries: list[BoardEntry]
    distractors: list[Distractor]
    knobs: Knobs
    closed_edges: list[tuple[str, str]] = []  # edges closed in this scene (CLOSURE, OVERRIDE)


class Receipt(BaseModel):
    solver_answer: Answer
    independent_answer: Answer
    agree: bool
    fidelity_ok: bool
    visibility_ok: bool
    evidence_visible_ratio: float
    blind_correct_rate: float | None
    blind_rejected: bool
    pair_verified: bool | None
    human_audit: Literal["pass", "fail", "unaudited"] = "unaudited"
    notes: str = ""


class Task(BaseModel):
    task_id: str
    schema_version: str
    generator_version: str
    seed: int
    qtype: Literal["DIRECT", "BINDING", "CLOSURE", "OVERRIDE", "EGOCENTRIC", "ABSENT"]
    question: str
    options: list[Answer]
    gold: Answer
    image_path: str
    scene_path: str
    target_dest_id: str
    turn_cw: int | None  # 90, 180, 270 for EGOCENTRIC
    skill_tags: list[str]
    difficulty: dict
    pair_id: str | None
    pair_role: Literal["a", "b"] | None
    receipt: Receipt
```

`tasks.jsonl` is the public release format. It contains `gold` (for scoring) but the evaluation code never places `gold`, `scene_path` or scene contents in a prompt.

## 4. Core algorithms

### 4.1 Orientation (human-owned)
All venue bearings and headings are multiples of 45 degrees, so octant boundaries never occur.

```python
OCTANTS = ["AHEAD", "AHEAD_RIGHT", "RIGHT", "BACK_RIGHT", "BACK", "BACK_LEFT", "LEFT", "AHEAD_LEFT"]


def norm(deg):
    return deg % 360


def relative_bearing(target_bearing, heading):
    return norm(target_bearing - heading)  # clockwise


def to_octant(rel):
    assert rel % 45 == 0
    return OCTANTS[int(norm(rel) // 45)]


def apply_turn(rel, turn_cw):
    return norm(rel - turn_cw)  # turn clockwise by turn_cw degrees
```
A board faces the viewer, so `arrow_angle == relative_bearing(edge_bearing, heading)` and "up" on the board means AHEAD.

### 4.2 Solver (human-owned)
```python
def build_graph(venue):       # DiGraph, both directions, reverse bearing = (b + 180) % 360
def first_hop_bearings(G, src, dst, open_only=True):
    # all shortest paths by length on open edges; return (set of first-hop bearings, paths) or None
```
- More than one distinct first-hop bearing means the route is **ambiguous**; the task is rejected.
- No open path but a path in the full graph means `CLOSED`.

### 4.3 Gold rule per question type

| Type | Scene construction | Gold |
|---|---|---|
| DIRECT | Entries from the open graph; target listed | `to_octant(arrow_angle of target)` |
| BINDING | DIRECT with stacked or grouped layout, 4+ similar labels | same as DIRECT |
| CLOSURE | Every route to the target closed; entry has closed mark | `CLOSED` |
| OVERRIDE | A main-route edge closed; permanent entry shows the stale full-graph route; a temporary notice shows the new open route | octant of the open-graph first hop |
| EGOCENTRIC | DIRECT plus a turn in the question | `to_octant(apply_turn(rel, turn_cw))` |
| ABSENT | Target exists in venue but has no entry | `NOT_INDICATED` |

### 4.4 Verification layers (the receipt)

1. **Solver answer:** from the venue graph and scene (`graph/solver.py`).
2. **Independent answer:** from the Scene entries only (`verify/independent.py`), written as a separate code path (reads displayed arrow angle, status, source, turn).
3. **Render fidelity:** after rendering, read the DOM (arrow rotations, label text, closed marks) and compare with the Scene spec.
4. **Visibility:** every evidence element (target label, its arrow, closure mark or notice) must be inside the viewport and at least 90% unoccluded, sampled with `elementFromPoint`.
5. **Blind test:** ask a cheap model the question with options but no image, three samples; reject if the correct-rate is at or above the configured threshold (default 0.67).
6. **Pairs:** a pair differs in exactly one scene field path, images differ, and the golds differ.
7. **Human audit:** 50 sampled tasks, labelled pass or fail by a teammate.
A task is kept only if 2, 3 and 4 pass and 1 equals 2.

### 4.5 Text mode
`generator/text_description.py` converts the Scene to a plain description that uses the same arrow words as the answer options, for example: "Entry 1: Platform 5 (Hindi label also shown), arrow AHEAD_RIGHT, status open. Temporary notice (yellow): ...". Image-mode accuracy minus text-mode accuracy is the **perception gap**.

### 4.6 Prompt format
```
You are looking at a signboard. Answer the question using only the board.
Question: <question>
Options: AHEAD, AHEAD_RIGHT, RIGHT, BACK_RIGHT, BACK, BACK_LEFT, LEFT, AHEAD_LEFT, CLOSED, NOT_INDICATED
Reply with exactly one line: ANSWER: <OPTION>
```
Prompts are versioned (`prompt_version` in config). Unparseable replies are scored wrong and logged.

## 5. Determinism and reproducibility

- A master seed in `config/default.yaml`; each task gets `seed = hash(master_seed, index)`.
- All random draws use a `numpy.random.Generator` created from the task seed and passed down explicitly; no global `random` or `np.random`.
- Playwright renders at a fixed viewport and device scale factor; fonts are loaded from `assets/fonts`, never system fonts.
- PNG metadata is stripped before saving. Tests compare file hashes for two runs with the same seed.

## 6. Evaluation architecture

- **Adapters** implement `answer(task, mode, prompt_version) -> RawResponse`. Adding a model means one new file and one entry in `config/models.yaml`.
- **Cache** is SQLite keyed by `(model_id, task_id, mode, prompt_version)`; responses are stored raw.
- **Runner** is resumable and rate-limited (requests per minute from config), with exponential backoff (tenacity). It writes results incrementally to `data/cache` and `reports/results.jsonl`.
- **Scorer** is rule-based exact match on the parsed option.
- **Metrics:** accuracy overall, by question type, by knob bin and by script; Wilson 95% intervals; pair consistency (both members correct); hallucination rate (a direction given when gold is `NOT_INDICATED`); perception gap.

## 7. Demo architecture

`demo/app.py` (Streamlit) imports the package directly (no server): choose venue, question type and knobs, generate a board, ask a model, score it, then reveal the gold answer with the route highlighted on the venue graph and the receipt. A second page loads cached results for heatmaps and the failure gallery, so the demo works offline.

## 8. Configuration

- `config/default.yaml`: master seed, total tasks, per-type quotas, knob ranges, thresholds (blind-test, visibility), template weights.
- `config/models.yaml`: for each model: adapter, model id (fill in from the provider), requests per minute, enabled flag.
- Secrets only in `.env`.

## 9. Testing strategy

| Test | Purpose |
|---|---|
| `test_orientation.py` | Hand-made table of 30+ bearing, octant and turn cases |
| `test_solver.py` | Hand-made graphs: shortest path, closure, ties (ambiguity), missing nodes |
| `test_schema.py` | Reject bearings not multiples of 45, missing fields |
| `test_determinism.py` | Same seed gives identical image hash and task JSON |
| `test_renderer.py` | Fonts load (no empty glyph boxes), geometry export present |
| `test_verifier.py` | Injected bugs (wrong arrow, hidden label) are caught |
| `test_scorer_oracle.py` | Oracle answerer scores 100%; random guesser near 10% |
| `test_parser.py` | Strict parsing, unparseable replies handled |
| `test_no_leakage.py` | Prompts never contain gold or scene data; PNG metadata empty |

## 10. Deployment

- Local: `pip install -r requirements.txt && playwright install chromium`.
- Docker: image with Chromium and fonts; `make demo` runs Streamlit.
- Demo hosting: Streamlit Community Cloud or Hugging Face Spaces, loading `data/sample_tasks` and cached results.

## 11. Decisions and trade-offs

| Decision | Reason | Cost |
|---|---|---|
| HTML/SVG rendering via Playwright | Exact control and DOM geometry for verification | Heavier than Pillow alone |
| 45-degree bearings only | No octant boundary ambiguity | Less angular realism |
| Fixed 10-option answers | Deterministic scoring, no LLM judge | Less open-ended |
| Streamlit demo, no web app | Fast to build, enough for judges | Less polished UI |
| Files plus SQLite cache | No infrastructure | Not for large scale |
| Human-owned critical modules | Protects dataset correctness | Slower than full automation |

## 12. Known limitations

- Rendered signs are cleaner than real photographs; the real-photo check measures the remaining gap.
- Single-board scenes only (no multi-junction routes) in the MVP.
- Free-tier rate limits cap how many models and repeats fit in the window.
