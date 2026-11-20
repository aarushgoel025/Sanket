# Antigravity Prompt Pack

**Project:** Sanket (working name) — verified visual benchmark factory for wayfinding signs
Paste the prompts in order, one per task or conversation. Each prompt contains its own file structure, requirements, acceptance criteria and test command.

---

## How to use this pack

1. Create an empty folder `sanket/` and open it as the Antigravity workspace.
2. Copy the documents in before Prompt 0:
   - `agents.md` to the repo root, renamed `AGENTS.md`
   - `readme.md` to the repo root, renamed `README.md`
   - `prd.md`, `architecture.md`, `design.md`, `rules.md` into a new `docs/` folder
3. Paste Prompt 0, let the agent finish, run `make test`, commit.
4. Continue with Prompts 1 to 14 in order. Do not skip ahead; each prompt depends on the previous ones.
5. After every prompt: read the diff, run `make test`, then commit with a short message.
6. **Review gates** are marked `GATE`. Stop there, review with a teammate and fix before continuing.
7. If your Antigravity version has a planning mode, use it for Prompts 3 to 9 and approve the plan before it writes code.
8. Free-tier quota is limited and can run out. Use agents for boilerplate, tests, templates and the demo. For ground-truth logic (Prompts 2 and 7), you or your lead should write or carefully review the code yourselves.
9. Keep API keys only in `.env`. Never paste keys into a prompt.

Utility prompts (review, debug, low-quota fallback) are at the end.

### Full project file structure (also used in Prompt 0)

```
sanket/
├── AGENTS.md
├── README.md
├── Makefile
├── Dockerfile
├── pyproject.toml
├── requirements.txt
├── .env.example
├── .gitignore
├── config/
│   ├── default.yaml
│   ├── models.yaml
│   └── venues/
│       ├── railway_station.yaml
│       └── hospital.yaml
├── assets/
│   ├── fonts/
│   ├── icons/
│   └── templates/
│       ├── board_list.html.j2
│       ├── board_grid.html.j2
│       └── board_gantry.html.j2
├── sanket/
│   ├── __init__.py
│   ├── cli.py
│   ├── schema.py
│   ├── config.py
│   ├── graph/        (venue.py, solver.py, orientation.py)
│   ├── generator/    (scene_builder.py, distractors.py, renderer.py, augment.py, text_description.py)
│   ├── questions/    (templates.py, options.py)
│   ├── verify/       (independent.py, fidelity.py, visibility.py, blind_test.py, pairs.py, dedupe.py, receipt.py)
│   ├── pipeline/     (build_dataset.py)
│   ├── evaluate/     (prompts.py, parser.py, modes.py, cache.py, runner.py, scorer.py,
│   │                  adapters/ base.py gemini.py openai_compat.py hf_qwen.py fake.py)
│   └── analysis/     (metrics.py, heatmaps.py, failure_gallery.py, report.py)
├── data/             (sample_tasks/, full_dataset/{images,scenes}, real_photos/images, cache/)
├── reports/          (validation_report.md, findings_report.md, figures/)
├── demo/app.py
├── docs/             (prd.md, architecture.md, design.md, rules.md, dataset_card.md)
├── scripts/          (smoke_test.py, run_pilot.sh, colab_qwen.py)
└── tests/            (test_*.py)
```

---

## Prompt 0 — Bootstrap the repository

~~~~
ROLE: You are a careful Python engineer setting up a new repository.

READ FIRST: AGENTS.md, docs/architecture.md, docs/rules.md.

GOAL
Create the repository skeleton for the project "Sanket" exactly as in the file structure below. Every Python module is an empty stub with a docstring describing its responsibility (from docs/architecture.md) and `raise NotImplementedError` bodies where logic will go later. No real logic yet.

FILE STRUCTURE (create all; ► = new)
sanket/
► AGENTS.md and README.md already exist (do not overwrite)
► Makefile, Dockerfile (skeleton only), pyproject.toml, requirements.txt, .env.example, .gitignore
► config/default.yaml, config/models.yaml, config/venues/ (empty folder with .gitkeep)
► assets/fonts/ assets/icons/ assets/templates/ (with .gitkeep)
► sanket/__init__.py, cli.py, schema.py, config.py
► sanket/graph/{__init__,venue,solver,orientation}.py
► sanket/generator/{__init__,scene_builder,distractors,renderer,augment,text_description}.py
► sanket/questions/{__init__,templates,options}.py
► sanket/verify/{__init__,independent,fidelity,visibility,blind_test,pairs,dedupe,receipt}.py
► sanket/pipeline/{__init__,build_dataset}.py
► sanket/evaluate/{__init__,prompts,parser,modes,cache,runner,scorer}.py
► sanket/evaluate/adapters/{__init__,base,gemini,openai_compat,hf_qwen,fake}.py
► sanket/analysis/{__init__,metrics,heatmaps,failure_gallery,report}.py
► data/sample_tasks/.gitkeep, data/full_dataset/images/.gitkeep, data/full_dataset/scenes/.gitkeep,
  data/real_photos/images/.gitkeep, data/cache/.gitkeep
► reports/figures/.gitkeep
► demo/app.py (stub that shows a title)
► scripts/smoke_test.py, scripts/run_pilot.sh, scripts/colab_qwen.py (stubs)
► tests/test_import.py

REQUIREMENTS
1. Python 3.11. requirements.txt with these packages (pin to the exact versions you install and test with):
   pydantic, pyyaml, networkx, jinja2, playwright, pillow, opencv-python-headless, albumentations,
   numpy, pandas, matplotlib, seaborn, streamlit, pytest, ruff, tenacity, httpx, python-dotenv,
   typer, imagehash, google-genai
2. Makefile targets: setup (pip install -r requirements.txt && playwright install chromium), test (pytest -q),
   lint (ruff check .), pilot, build, eval, report, demo (streamlit run demo/app.py). Targets that depend on
   unfinished code should print "not implemented yet" and exit 0.
3. .gitignore must include: .env, data/cache/*, __pycache__/, .pytest_cache/, .venv/, *.sqlite
   (keep .gitkeep files).
4. .env.example lists GEMINI_API_KEY=, OPENROUTER_API_KEY=, HF_TOKEN= with no values.
5. config/default.yaml: master_seed: 1234, total_tasks: 500, keep_tasks: 400, blind_threshold: 0.67,
   blind_samples: 3, pair_fraction: 0.3, prompt_version: "v1", plus a quotas section with one entry per question
   type (DIRECT, BINDING, CLOSURE, OVERRIDE, EGOCENTRIC, ABSENT) of 83 each.
6. config/models.yaml: placeholder entries (see Prompt 9) with REPLACE_WITH_MODEL_ID.
7. tests/test_import.py imports every module in the package.
8. cli.py uses Typer with commands: build, eval, report, pilot (each prints "not implemented yet").

ACCEPTANCE CRITERIA
- `make setup` and `make test` succeed on a clean machine.
- `ruff check .` passes.
- The tree matches the structure above (no extra top-level files).

Finish with the report format from AGENTS.md section 9.
~~~~

---

## Prompt 1 — Schema, config loader and venues

~~~~
ROLE: Python engineer implementing data models and configuration.

READ FIRST: AGENTS.md, docs/architecture.md (sections 3 and 8), docs/rules.md.

GOAL
Implement sanket/schema.py, sanket/config.py and the two venue YAML files.

FILE STRUCTURE FOR THIS STEP
sanket/
├── sanket/
│   ├── ► schema.py
│   ├── ► config.py
│   └── graph/
│       └── ► venue.py          (only load_venue(path) -> Venue)
├── config/
│   ├── ✎ default.yaml
│   └── venues/
│       ├── ► railway_station.yaml
│       └── ► hospital.yaml
└── tests/
    └── ► test_schema.py

REQUIREMENTS
1. schema.py: pydantic v2 models exactly as in docs/architecture.md section 3: Label, Node, Edge, Venue,
   BoardEntry, Distractor, Knobs, Scene, Receipt, Task. Add to Scene: closed_edges: list[tuple[str, str]] = [].
   Bearing is a Literal of 0,45,...,315. Add validators:
   - Edge endpoints must exist in Venue.nodes.
   - Node ids unique.
   - Every destination node has a Label with at least en and hi.
   - A venue graph must be connected when all edges are open.
   Answer options order constant ANSWER_OPTIONS = [AHEAD, AHEAD_RIGHT, RIGHT, BACK_RIGHT, BACK, BACK_LEFT,
   LEFT, AHEAD_LEFT, CLOSED, NOT_INDICATED].
2. config.py: load_default_config(), load_models_config() returning typed pydantic models; error with a clear
   message on missing keys.
3. venue.py: load_venue(path) -> Venue (validates).
4. railway_station.yaml: fictional "Central Junction Station" with at least 4 junction nodes (concourse,
   foot-over-bridge, platform-end hall, exit hall) and at least 10 destinations: platforms 1 to 6, main exit,
   ticket counter, toilets, lift, waiting hall. Edge bearings multiples of 45. Lengths in metres, realistic.
5. hospital.yaml: fictional "City General Hospital" with at least 3 junctions and at least 9 destinations:
   emergency, pharmacy, OPD, radiology, lab, reception, canteen, lift, main exit.
6. Every destination has labels en and hi. Hindi examples to use: Exit = निकास, Ticket counter = टिकट खिड़की,
   Platform 5 = प्लेटफ़ॉर्म 5, Toilets = शौचालय, Lift = लिफ्ट, Closed = बंद. For other labels write best-effort
   Hindi and add a YAML comment "# VERIFY HINDI" on that line.
7. Design venues so that, from each junction, every destination used in tasks has a unique shortest path first
   hop, and at least a few destinations have an alternate (longer) route so OVERRIDE tasks are possible.
   Also include a few destinations with only one route so CLOSURE tasks are possible.

ACCEPTANCE CRITERIA
- Both venue files load and validate.
- test_schema.py covers: bearing not multiple of 45 rejected, unknown edge endpoint rejected, missing Hindi label
  on a destination rejected, disconnected venue rejected, valid venues load.
- `make test` passes.

GATE (human): a Hindi-speaking teammate verifies every line marked VERIFY HINDI; the lead sanity-checks
venue geometry (bearings and lengths) on paper before Prompt 2.

Finish with the report format from AGENTS.md section 9.
~~~~

---

## Prompt 2 — Orientation and solver (human-owned)

~~~~
ROLE: Python engineer. These two modules are HUMAN-OWNED ground-truth code. Do not improvise.

READ FIRST: AGENTS.md (sections 4 and 5), docs/architecture.md section 4.

GOAL
Create sanket/graph/orientation.py and sanket/graph/solver.py using EXACTLY the reference code below, then write
thorough tests. Do not change the logic; you may add type hints and docstrings.

FILE STRUCTURE FOR THIS STEP
sanket/
├── sanket/graph/
│   ├── ► orientation.py
│   └── ► solver.py
└── tests/
    ├── ► test_orientation.py
    └── ► test_solver.py

REFERENCE: orientation.py
  OCTANTS = ["AHEAD","AHEAD_RIGHT","RIGHT","BACK_RIGHT","BACK","BACK_LEFT","LEFT","AHEAD_LEFT"]
  def norm(deg): return deg % 360
  def relative_bearing(target_bearing, heading): return norm(target_bearing - heading)   # clockwise
  def to_octant(rel):
      assert rel % 45 == 0, "bearings must be multiples of 45"
      return OCTANTS[int(norm(rel) // 45)]
  def apply_turn(rel, turn_cw): return norm(rel - turn_cw)   # viewer turns clockwise by turn_cw degrees

REFERENCE: solver.py
  import networkx as nx
  def build_graph(venue):
      G = nx.DiGraph()
      for e in venue.edges:   # venue is the pydantic Venue; apply Scene.closed_edges before calling if needed
          G.add_edge(e.a, e.b, bearing=e.bearing_ab, length=e.length, status=e.status)
          G.add_edge(e.b, e.a, bearing=(e.bearing_ab + 180) % 360, length=e.length, status=e.status)
      return G
  def open_subgraph(G):
      return G.edge_subgraph([(u, v) for u, v, d in G.edges(data=True) if d["status"] == "open"])
  def first_hop_bearings(G, src, dst, open_only=True):
      if src == dst: return None
      H = open_subgraph(G) if open_only else G
      try:
          paths = list(nx.all_shortest_paths(H, src, dst, weight="length"))
      except (nx.NetworkXNoPath, nx.NodeNotFound):
          return None
      return {G[p[0]][p[1]]["bearing"] for p in paths}, paths

Also add in solver.py:
  def apply_closed_edges(venue, closed_edges) -> Venue   # returns a copy with those edges set to "closed"
  def gold_answer(venue, closed_edges, junction, heading, dest, turn_cw=None, listed=True) -> str
    Rules: if not listed -> "NOT_INDICATED"; build graph with closed edges applied; if no open path but a path
    exists in the full graph -> "CLOSED"; if the set of first-hop bearings has more than one element ->
    raise AmbiguousRoute; else rel = relative_bearing(bearing, heading); if turn_cw is not None:
    rel = apply_turn(rel, turn_cw); return to_octant(rel).

TESTS (write all of these)
- 30+ orientation cases as a table: (target, heading, expected). Include: (90,0)->RIGHT, (0,90)->LEFT,
  (180,0)->BACK, (315,0)->AHEAD_LEFT, (45,0)->AHEAD_RIGHT, (0,0)->AHEAD, wrap-around cases such as
  (0,270)->RIGHT and (270,90)->BACK.
- Turn cases: rel 0 turn 180 -> BACK; rel 0 turn 90 -> LEFT; rel 90 turn 90 -> AHEAD; rel 180 turn 270 -> LEFT.
- A non-multiple of 45 raises AssertionError.
- Solver: unique shortest path; closed edge forces the detour; all edges to target closed -> CLOSED;
  equal-length shortest paths with different first hops -> AmbiguousRoute; same src and dst -> None;
  unknown node -> None.
- Arrow semantics check: for a venue edge bearing b and heading h, arrow octant equals to_octant(relative_bearing(b, h)).

ACCEPTANCE CRITERIA
- `pytest tests/test_orientation.py tests/test_solver.py -q` passes.
- No other files modified.

GATE (human): the lead reads both files and all tests line by line. A second teammate re-derives five test
cases by hand. Only then continue.

Finish with the report format from AGENTS.md section 9.
~~~~

---

## Prompt 3 — Scene builder and distractors

~~~~
ROLE: Python engineer implementing deterministic scene generation.

READ FIRST: AGENTS.md, docs/architecture.md (sections 3, 4.3), docs/design.md (sections 2 and 3).

GOAL
Implement sanket/generator/scene_builder.py and sanket/generator/distractors.py.

FILE STRUCTURE FOR THIS STEP
sanket/
├── sanket/generator/
│   ├── ► scene_builder.py
│   └── ► distractors.py
├── sanket/graph/   (read-only: orientation.py, solver.py, venue.py)
└── tests/
    └── ► test_scene_builder.py

API
  class RejectScene(Exception): reason: str
  @dataclass class SceneBuild: scene: Scene; target_dest_id: str
  def sample_knobs(rng, qtype, cfg) -> Knobs
  def build_scene(venue: Venue, qtype: str, rng: numpy.random.Generator, knobs: Knobs) -> SceneBuild

REQUIREMENTS
1. Choose a junction and a heading (multiple of 45) with rng. Choose n_entries destinations (knobs.n_entries).
   Build permanent entries from the solver: arrow_angle = relative_bearing(first-hop bearing, heading) using the
   FULL open graph. Labels come from the venue (only scripts listed in knobs.scripts are shown).
2. Per question type (see docs/architecture.md 4.3):
   - DIRECT: target listed; open routes only.
   - BINDING: pick destinations with similar labels (for example Platform 4, 5, 6 and 14 if available);
     template grid or gantry; at least 4 entries.
   - CLOSURE: close every route to the target (close the edge or edges so no open path exists but a path exists
     in the full graph); record scene.closed_edges; the target's entry gets status "closed".
   - OVERRIDE: close one edge on the target's main route so an alternate open route exists with a unique first hop;
     the permanent entry shows the stale full-graph arrow; add a temporary_notice entry for the target showing the
     open-route arrow; record scene.closed_edges.
   - EGOCENTRIC: same as DIRECT (the turn is chosen by the question builder).
   - ABSENT: choose a reachable target that exists in the venue but do not list it.
3. Every candidate must pass the solver ambiguity check (AmbiguousRoute -> try another; after 20 tries raise
   RejectScene("ambiguous_route")).
4. distractors.py: seeded distractors (fictional ads, unrelated icons, unrelated numbers) count = knobs.clutter,
   with positions only in non-evidence areas of the chosen template.
5. All randomness uses the passed rng. Same inputs and same seed give an identical Scene (tested).

ACCEPTANCE CRITERIA
- For each question type, 50 seeds build without error or raise RejectScene with a reason.
- For DIRECT scenes the target entry's arrow octant equals gold_answer(...) from the solver.
- CLOSURE scenes: solver returns CLOSED. OVERRIDE scenes: permanent arrow differs from notice arrow and
  the solver's first hop equals the notice arrow. ABSENT scenes: target not in entries.
- Determinism test passes. `make test` passes.

Finish with the report format from AGENTS.md section 9.
~~~~

---

## Prompt 4 — Renderer (HTML/SVG to PNG with geometry export)

~~~~
ROLE: Python and front-end engineer building a reliable headless renderer.

READ FIRST: AGENTS.md, docs/design.md (sections 2 and 4), docs/architecture.md (4.4, 5).

GOAL
Render a Scene to a PNG and export per-element geometry for verification.

FILE STRUCTURE FOR THIS STEP
sanket/
├── assets/
│   ├── fonts/            ► Noto Sans, Noto Sans Devanagari (download open-licence TTFs)
│   ├── icons/            ► simple own SVG pictograms (train, cross, exit, toilet, lift, ticket, pharmacy)
│   └── templates/
│       ├── ► board_list.html.j2
│       ├── ► board_grid.html.j2
│       └── ► board_gantry.html.j2
├── sanket/generator/
│   └── ► renderer.py
└── tests/
    └── ► test_renderer.py

API
  class Geometry(BaseModel): elements: list[ElementGeo]   # put in schema.py if not already there
  ElementGeo: role, dest_id, angle (float|None), text, bbox [x, y, w, h], occluded_ratio, source
  def render_scene(scene: Scene, venue: Venue, out_png: Path) -> Geometry

REQUIREMENTS
1. Jinja2 templates; fonts loaded with @font-face from assets/fonts via file URLs; never system fonts.
2. Playwright Chromium, viewport 1280x720, device scale factor 1. Wait for document.fonts.ready and assert every
   font used reports loaded; otherwise raise (a missing glyph is a build error).
3. Colours, arrows, notice and closed overlay follow docs/design.md section 2. Add a small "SYNTHETIC" mark.
4. Required HTML attributes: board root id="board"; per entry data-role="entry" data-dest-id; label
   data-role="label"; arrow data-role="arrow" data-angle (CSS rotate by arrow_angle); closed overlay
   data-role="closed_mark"; notice data-role="notice" data-source="temporary_notice"; distractors
   data-role="distractor".
5. Geometry export via page.evaluate: for each data-role element, bbox from getBoundingClientRect, rotation angle
   parsed from the computed transform matrix, text content, and occluded_ratio computed by sampling a 5x5 grid of
   points with document.elementFromPoint (a point counts as occluded if the top element is neither the element
   nor its descendant).
6. Save PNG with all metadata removed (re-save with Pillow without exif or text chunks).
7. Template selection from scene.knobs.template. Same Scene gives identical pixels (tested).

ACCEPTANCE CRITERIA
- Render 3 scenes (one per template) with Hindi text; fonts check passes; no empty glyph boxes.
- Geometry contains one arrow per entry whose angle equals the entry's arrow_angle within 1 degree.
- A deliberately overlapping distractor makes occluded_ratio > 0 in a test.
- PNG has no metadata. `make test` passes.

Finish with the report format from AGENTS.md section 9.
~~~~

---

## Prompt 5 — Augmentation

~~~~
ROLE: Python engineer using OpenCV and Albumentations with strict determinism.

READ FIRST: AGENTS.md, docs/design.md (sections 3 and 4).

GOAL
Implement seeded pixel-level augmentation that never destroys evidence and returns transformed geometry.

FILE STRUCTURE FOR THIS STEP
sanket/
├── sanket/generator/
│   └── ► augment.py
└── tests/
    └── ► test_augment.py

API
  def augment(png_in: Path, geometry: Geometry, knobs: Knobs, rng: Generator, out_png: Path) -> Geometry

REQUIREMENTS
1. Order: lighting gradient and shadow, perspective warp, blur, noise, JPEG compression, save PNG, strip metadata.
2. Stickers or occluders (knobs.occlusion up to 0.15 of board area) are placed only outside bounding boxes of
   evidence roles (label, arrow, closed_mark, notice for the target).
3. The perspective homography is applied to the geometry bounding boxes too; return the transformed geometry
   (axis-aligned box of the warped corners).
4. All randomness from rng; no cv2.setRNGSeed or global numpy randomness.
5. Same inputs give identical output pixels (tested).

ACCEPTANCE CRITERIA
- With perspective 25 degrees, transformed evidence boxes stay inside the image.
- Occluders never intersect evidence boxes in 100 random trials.
- Determinism test passes. Output PNG has no metadata. `make test` passes.

Finish with the report format from AGENTS.md section 9.
~~~~

---

## Prompt 6 — Questions, options and text mode

~~~~
ROLE: Python engineer building question generation and structured text descriptions.

READ FIRST: AGENTS.md, docs/architecture.md (4.3, 4.5, 4.6), docs/prd.md section 8.

GOAL
Implement question generation (six types), the fixed option set, and the text-mode description.

FILE STRUCTURE FOR THIS STEP
sanket/
├── sanket/questions/
│   ├── ► options.py
│   └── ► templates.py
├── sanket/generator/
│   └── ► text_description.py
└── tests/
    ├── ► test_questions.py
    └── ► test_text_description.py

API
  options.py: ANSWER_OPTIONS (reuse from schema); def options_for_task() -> list[str]  (always the same order)
  templates.py: def make_task(sb: SceneBuild, venue: Venue, rng: Generator, task_id: str, seed: int,
                              image_path: str, scene_path: str) -> Task      # receipt filled later
  text_description.py: def describe_scene(scene: Scene, venue: Venue) -> str

REQUIREMENTS
1. Question wording (English), always naming the destination by its English label:
   DIRECT: "You are standing in front of this signboard. Which way should you go to reach {dest}?"
   BINDING: same plus "Several signs are stacked; use only the arrow that belongs to {dest}."
   CLOSURE: "Can you reach {dest} by the route shown? If the route is closed answer CLOSED, otherwise give the direction."
   OVERRIDE: "Follow the instructions that are currently valid. Which way should you go to reach {dest}?"
   EGOCENTRIC: "First work out which way {dest} is from this board. Then you {turn_phrase}. Which way is {dest} relative to you now?"
     with turn_phrase one of "turn around (180 degrees)", "turn 90 degrees to your right", "turn 90 degrees to your left"
     mapped to turn_cw 180, 90, 270.
   ABSENT: "Does this board show a way to {dest}? If it does, give the direction; if the board does not mention it, answer NOT_INDICATED."
2. gold comes only from solver.gold_answer (never from the scene entries or a model).
3. skill_tags and difficulty dict are filled from the question type and knobs.
4. describe_scene returns plain text listing each entry with its label, arrow word (same words as the options),
   status and source, e.g. "Entry 1: Platform 5, arrow AHEAD_RIGHT, status open." and a line for each temporary notice.
   It must be deterministic and must not mention the question or gold.
5. options always equal ANSWER_OPTIONS in the same order for every type.

ACCEPTANCE CRITERIA
- 100 tasks across types: golds computed by the solver match hand-computed expectations for 12 fixed examples.
- EGOCENTRIC turn mapping tested for all three turns.
- describe_scene output contains no gold string and no question text. `make test` passes.

Finish with the report format from AGENTS.md section 9.
~~~~

---

## Prompt 7 — Verifier (independent path, fidelity, visibility, receipt)

~~~~
ROLE: Python engineer building independent verification. Correctness matters more than speed.

READ FIRST: AGENTS.md (sections 4 and 5), docs/architecture.md section 4.4.

GOAL
Implement the independent answer path, render-fidelity check, visibility check and receipt assembly.

FILE STRUCTURE FOR THIS STEP
sanket/
├── sanket/verify/
│   ├── ► independent.py      (HUMAN-OWNED: show diff and tests before finishing)
│   ├── ► fidelity.py
│   ├── ► visibility.py
│   └── ► receipt.py
└── tests/
    └── ► test_verifier.py

REQUIREMENTS
1. independent.py: def independent_answer(scene: Scene, task: Task) -> str. Use ONLY the scene entries and the
   task (target, turn). Do not import solver.py or the venue graph. Rules: if a temporary_notice entry exists for the
   target, use its arrow; else use the permanent entry; no entry -> NOT_INDICATED; entry status closed ->
   CLOSED; otherwise to_octant of the arrow angle (import only orientation.py), applying turn_cw for EGOCENTRIC.
2. fidelity.py: def fidelity_ok(scene: Scene, geometry: Geometry) -> tuple[bool, str]. For every entry: label
   text contains the English label, arrow angle matches within 1 degree, a closed_mark exists iff status is
   closed, a notice exists iff a temporary_notice entry exists.
3. visibility.py: def visibility_ok(scene, task, geometry_after_augment, image_size) -> tuple[bool, float].
   Evidence set: label, arrow, closed_mark (if closed), notice (if OVERRIDE) for the target; for ABSENT, all
   entry labels. Each evidence bbox must lie inside the image and have occluded_ratio <= 0.10.
4. receipt.py: def build_receipt(task, scene, solver_answer, independent_answer, fidelity, visibility, ...) -> Receipt.
   agree = solver_answer == independent_answer == task.gold.
5. A task is kept only if agree, fidelity_ok and visibility_ok are all true.

TESTS (inject bugs and make sure they are caught)
- Scene with a wrong arrow angle -> independent differs from solver.
- Geometry with a missing closed_mark -> fidelity fails.
- Evidence bbox outside the image or occluded 30% -> visibility fails.
- 20 correct tasks of each type pass all three checks.

ACCEPTANCE CRITERIA
- `make test` passes; independent.py imports nothing from solver.py.

GATE (human): the lead reviews independent.py and the injected-bug tests with a teammate.

Finish with the report format from AGENTS.md section 9.
~~~~

---

## Prompt 8 — Filters, pairs, de-duplication and the build pipeline

~~~~
ROLE: Python engineer building the dataset pipeline.

READ FIRST: AGENTS.md, docs/architecture.md (4.4, 5), docs/prd.md (sections 6 and 9), docs/rules.md.

GOAL
Implement blind test, minimal pairs, de-duplication and the full build pipeline with the CLI command `build`.

FILE STRUCTURE FOR THIS STEP
sanket/
├── sanket/verify/
│   ├── ► blind_test.py
│   ├── ► pairs.py
│   └── ► dedupe.py
├── sanket/pipeline/
│   └── ► build_dataset.py
├── sanket/cli.py                 (✎ wire `build`)
├── data/full_dataset/
│   ├── images/   scenes/         (outputs)
│   ├── tasks.jsonl               (output)
│   ├── rejected.jsonl            (output)
│   └── build_stats.json          (output)
└── tests/
    └── ► test_pipeline.py

REQUIREMENTS
1. blind_test.py: ask the configured blind_model the question and options with NO image and NO board text,
   blind_samples times (default 3), through the cached runner interface (use the adapter interface from Prompt 9
   or a temporary protocol class now). correct_rate >= blind_threshold -> reject with reason "blind_test_fail".
   Tests use the fake adapter.
2. pairs.py: build a minimal pair by editing a COPY of the venue (change one edge bearing at the junction to
   another multiple of 45 with no duplicate outgoing bearing, or toggle one edge open/closed), rebuild the scene
   with the same seed and knobs, then verify: exactly one scene field path differs, images differ, gold answers
   differ. Both tasks get the same pair_id with pair_role a and b. If any check fails, drop the pair (keep the
   original task).
3. dedupe.py: structural signature = (qtype, n_entries, target index on board, gold, template, scripts); cap
   10 per signature. Perceptual hash (imagehash phash) near-duplicates (distance <= 4) removed.
4. build_dataset.py order: for each index, derive task seed from master_seed, choose qtype by quotas, sample
   knobs, build_scene, render, augment, make_task, solver answer, independent answer, fidelity, visibility,
   dedupe; then run blind test on survivors; then balance (no gold answer above 25% within a type); then build
   pairs for pair_fraction of tasks; write images, scenes (hidden specs), tasks.jsonl, rejected.jsonl (reason
   codes from docs/rules.md section 4), build_stats.json (generated, kept, rejected by reason, per-type counts).
5. Over-generate (total_tasks 500) and keep keep_tasks (400) with per-type balance.
6. Same master_seed gives identical tasks.jsonl bytes (tested on a 12-task build).
7. `sanket build --n 12 --out /tmp/test_build` works for quick tests.

ACCEPTANCE CRITERIA
- A 60-task build completes, with every kept task having agree, fidelity_ok and visibility_ok true.
- rejected.jsonl exists with reasons. Pair checks pass on at least some pairs.
- `make test` passes.

GATE (human): open 20 random images with the lead and the pitch lead. Do the boards look right, are the Hindi
labels legible, do arrows and answers make sense? Fix generator problems before running the full build.

Finish with the report format from AGENTS.md section 9.
~~~~

---

## Prompt 9 — Evaluator (adapters, cache, runner, scorer)

~~~~
ROLE: Python engineer building a resumable, rate-limited evaluation harness.

READ FIRST: AGENTS.md, docs/architecture.md (4.5, 4.6, 6), docs/rules.md (sections 5 and 6).

GOAL
Implement model adapters, prompts, parser, cache, runner, scorer and the CLI command `eval`.

FILE STRUCTURE FOR THIS STEP
sanket/
├── config/
│   └── ✎ models.yaml
├── sanket/evaluate/
│   ├── ► prompts.py   ► parser.py   ► modes.py   ► cache.py   ► runner.py   ► scorer.py
│   └── adapters/
│       ├── ► base.py   ► gemini.py   ► openai_compat.py   ► hf_qwen.py   ► fake.py
├── scripts/
│   └── ✎ colab_qwen.py
├── sanket/cli.py             (✎ wire `eval`)
└── tests/
    ├── ► test_parser.py   ► test_scorer_oracle.py   ► test_no_leakage.py   ► test_runner.py

config/models.yaml
  models:
    - {name: gemini_flash, adapter: gemini, model_id: REPLACE_WITH_MODEL_ID, rpm: 10, enabled: true}
    - {name: or_vision, adapter: openai_compat, base_url: "https://openrouter.ai/api/v1",
       model_id: REPLACE_WITH_MODEL_ID, rpm: 10, enabled: true}
    - {name: qwen_vl, adapter: hf_qwen, model_id: REPLACE_WITH_MODEL_ID, rpm: 10, enabled: false}
  blind_model: gemini_flash

REQUIREMENTS
1. adapters/base.py: BaseAdapter.answer(task, mode, prompt_version) -> RawResponse(text, latency_s, meta).
   Real adapters read keys from the environment (python-dotenv). No key in code or logs.
2. fake.py: OracleAdapter (returns gold), RandomAdapter (seeded), AlwaysAdapter(option). For tests only.
3. prompts.py: build_prompt(task, mode, version) using the format in docs/architecture.md 4.6. It may use only the
   question, options, the image (image mode) or describe_scene text (text mode). Never gold, scene_path,
   receipt or file names.
4. parser.py: strict parse of a final line "ANSWER: <OPTION>" (case-insensitive, allow spaces and underscores),
   returns option or None. None is scored wrong and logged.
5. cache.py: SQLite keyed by (model_id, task_id, mode, prompt_version); stores raw text, latency, timestamp.
6. runner.py: iterate tasks x modes, skip cached, throttle to rpm, tenacity exponential backoff, stop and report
   after N consecutive rate-limit failures, show progress, append results to reports/results.jsonl, resumable.
   Flags: --models, --modes, --limit, --set (synthetic or real).
7. scorer.py: exact match on parsed option; no LLM judge.
8. hf_qwen.py: either call a Hugging Face endpoint or import answers from a JSONL produced by
   scripts/colab_qwen.py (which runs the open VLM on a free Kaggle or Colab GPU and writes the same result format).

ACCEPTANCE CRITERIA
- OracleAdapter scores 100%; RandomAdapter scores near 10% on 400 tasks; AlwaysAdapter("AHEAD") shows its
  per-type bias.
- test_no_leakage: prompts never contain gold, scene data or answer-revealing paths; saved PNGs have no metadata.
- Runner resumes after an interrupted run without repeating cached calls.
- `make test` passes without any network access.

GATE (human): run a 20-task pilot with one real model (`make pilot`), read 5 raw responses and check parsing.

Finish with the report format from AGENTS.md section 9.
~~~~

---

## Prompt 10 — Analysis and reports

~~~~
ROLE: Data analyst engineer.

READ FIRST: AGENTS.md, docs/design.md section 6, docs/rules.md section 6.

GOAL
Implement metrics, figures and the two reports, and wire the CLI command `report`.

FILE STRUCTURE FOR THIS STEP
sanket/
├── sanket/analysis/
│   ├── ► metrics.py   ► heatmaps.py   ► failure_gallery.py   ► report.py
├── sanket/cli.py             (✎ wire `report`)
├── reports/
│   ├── validation_report.md  (output)
│   ├── findings_report.md    (output)
│   └── figures/              (output PNGs F1-F6)
└── tests/
    └── ► test_metrics.py

REQUIREMENTS
1. metrics.py with pandas: accuracy overall, by qtype, by knob bin (n_entries, perspective, clutter, scripts), by
   model and mode; Wilson 95% intervals; pair consistency (both members correct); hallucination rate (a direction
   given when gold is NOT_INDICATED); perception gap = accuracy(text) minus accuracy(image).
2. heatmaps.py: figures F1 to F6 from docs/design.md section 6 (colourblind-safe palette, axis labels, n and CI).
3. failure_gallery.py: pick 3 to 5 failures per model with image, question, gold and model answer; save a
   markdown table with relative image paths.
4. report.py writes:
   - validation_report.md: generated, kept, rejected by reason, solver vs independent agreement, fidelity pass
     rate, blind-test reject rate, human audit counts (read from a CSV data/human_audit.csv with task_id and
     pass/fail), balance tables.
   - findings_report.md: for each figure, one data-driven sentence generated from the numbers, plus the
     perception gap table and a "consequence" column filled from a hand-written YAML (config/consequences.yaml).
5. Reports are generated only from files (tasks.jsonl, results.jsonl); no numbers typed by hand.

ACCEPTANCE CRITERIA
- Wilson interval tested on known values (e.g. 8/10 at 95%).
- Running `make report` with fake-adapter results produces both reports and six figures.
- `make test` passes.

Finish with the report format from AGENTS.md section 9.
~~~~

---

## Prompt 11 — Streamlit demo

~~~~
ROLE: Python engineer building a simple, reliable demo.

READ FIRST: AGENTS.md, docs/design.md section 5.

GOAL
Build the Streamlit demo that works offline from cached data.

FILE STRUCTURE FOR THIS STEP
sanket/
├── demo/
│   ├── ► app.py
│   └── pages/
│       ├── ► 2_Findings.py
│       └── ► 3_Pairs.py
├── data/sample_tasks/        (read)
└── reports/figures/          (read)

REQUIREMENTS
1. Page 1 (app.py): choose venue, question type and knobs, press Generate (uses build_scene, render_scene,
   augment, make_task and the solver with a fresh seed), show the image, the question and the options.
2. "Ask model": choose a model and mode, call through the cache and runner, show the model answer, the gold
   answer and CORRECT or WRONG with icon and text (not colour alone).
3. "Reveal proof": draw the venue graph (matplotlib or networkx) with the route highlighted, and show the
   receipt table (solver, independent, fidelity, visibility, blind test).
4. Offline mode: a toggle "Use saved sample tasks" loads data/sample_tasks and cached model answers so the demo
   works without internet or API keys.
5. Page 2: figures F1 to F6 and the failure gallery from reports/. Page 3: a minimal pair side by side with both
   golds and each model's answers.
6. Alt text for every image. No login, no database.

ACCEPTANCE CRITERIA
- `make demo` starts the app; a full generate, ask, score, reveal cycle works with the fake adapter and offline.
- No crash when no API key is set.

Finish with the report format from AGENTS.md section 9.
~~~~

---

## Prompt 12 — Real-photo set

~~~~
ROLE: Python engineer adding a real-image evaluation set.

READ FIRST: AGENTS.md, docs/rules.md (section 4), docs/design.md section 7.

GOAL
Load hand-labelled real sign photos and evaluate them with the same runner and scorer.

FILE STRUCTURE FOR THIS STEP
sanket/
├── data/real_photos/
│   ├── images/              (photos taken by the pitch lead: no faces, public signage only)
│   └── ► real_tasks.jsonl    (hand-written tasks)
├── sanket/analysis/
│   └── ✎ metrics.py, ✎ heatmaps.py     (add synthetic-vs-real comparison, figure F5)
├── sanket/evaluate/
│   └── ✎ runner.py                      (support --set real)
└── scripts/
    └── ► strip_exif.py

REQUIREMENTS
1. real_tasks.jsonl line: {"task_id": "R001", "image_path": "images/R001.jpg", "question": "...",
   "options": same fixed options, "gold": "LEFT", "notes": "hand-labelled by <initials>"}.
2. scripts/strip_exif.py removes EXIF from every image in data/real_photos/images.
3. Runner and scorer treat real tasks exactly like synthetic ones (image mode only).
4. Figure F5: per-model accuracy on synthetic versus real tasks, with confidence intervals and n.
5. A check script verifies every real task has an image, a valid gold option and no EXIF.

ACCEPTANCE CRITERIA
- With 5 sample real tasks and the fake adapter, `sanket eval --set real` runs and F5 is produced.
- `make test` passes.

HUMAN TASK (pitch lead): photograph 20 to 30 signboards in stations, hospitals or metro stations, with no
people or faces in frame; write the question and gold answer by hand for each; a second teammate double-checks.

Finish with the report format from AGENTS.md section 9.
~~~~

---

## Prompt 13 — Hardening, Docker and documentation

~~~~
ROLE: Release engineer.

READ FIRST: AGENTS.md, docs/rules.md, docs/prd.md section 15.

GOAL
Make the project reproducible on a clean machine and prove it with tests.

FILE STRUCTURE FOR THIS STEP
sanket/
├── ✎ Dockerfile
├── ✎ Makefile
├── ✎ README.md
├── scripts/
│   ├── ✎ smoke_test.py
│   └── ✎ run_pilot.sh
└── tests/
    ├── ✎ test_determinism.py
    ├── ✎ test_scorer_oracle.py
    └── ✎ test_no_leakage.py

REQUIREMENTS
1. Dockerfile: python 3.11 slim, system packages needed by Chromium, requirements installed, Playwright Chromium
   installed, fonts copied from assets/fonts, default command `make demo` on port 8501.
2. smoke_test.py: generate 6 tasks (one per type), render, verify, run the oracle adapter, print a summary,
   exit non-zero on any failure. `make pilot` runs it and then one real-model pilot of 20 tasks if keys exist.
3. Determinism test: two builds with the same seed produce identical tasks.jsonl and image hashes.
4. Strengthen the oracle, random and leakage tests as described in docs/architecture.md section 9.
5. Update README: real commands, task format, validation table placeholders, add-a-model steps.
6. Add `make verify-all` that runs lint, tests and the smoke test.

ACCEPTANCE CRITERIA
- `docker build` and `docker run` start the demo.
- `make verify-all` passes.
- Clean checkout to running demo in under 15 minutes following README only (a teammate measures this).

Finish with the report format from AGENTS.md section 9.
~~~~

---

## Prompt 14 — Submission packaging

~~~~
ROLE: Technical writer and release engineer.

READ FIRST: AGENTS.md, docs/prd.md (sections 9, 10), the generated reports.

GOAL
Prepare the final submission package.

FILE STRUCTURE FOR THIS STEP
sanket/
├── docs/
│   └── ► dataset_card.md
├── reports/
│   ├── ✎ validation_report.md   (regenerate)
│   └── ✎ findings_report.md     (regenerate)
├── data/
│   ├── ✎ sample_tasks/          (about 20 tasks, balanced across types)
│   └── ► human_audit.csv        (filled by teammates)
└── ✎ README.md

REQUIREMENTS
1. dataset_card.md: purpose, how tasks are generated, the six question types, answer options, validation steps,
   known limitations (rendered versus real, single board, free-tier limits), ethics (fictional venues, synthetic
   mark, real photos policy), licence, how to cite, how to reproduce.
2. Regenerate both reports from the frozen dataset (`make report`); check every number is generated from files.
3. Select about 20 sample tasks (balanced across question types and difficulties) into data/sample_tasks with
   their receipts.
4. Update README with final validation and findings summaries (numbers from the reports only).
5. Create a git tag v1.0-dataset and a short RELEASE_NOTES.md listing what is frozen.
6. Create a checklist file docs/submission_checklist.md mapping each item the event requires (pipeline, sample tasks
   with validation evidence, findings, live demo, explanation of the application and why errors matter) to the file or
   link that satisfies it.

ACCEPTANCE CRITERIA
- Every deliverable in docs/prd.md section 10 has a path in submission_checklist.md.
- `make verify-all` passes after regeneration.

Finish with the report format from AGENTS.md section 9.
~~~~

---

## Utility prompts

### U1 — Review and audit (run in a fresh conversation after each major step)

~~~~
ROLE: Strict code reviewer. Do not modify files; only report.

READ: AGENTS.md, docs/rules.md, docs/architecture.md, and the git diff of the last commit.

CHECK AND REPORT, with file and line references:
1. Any gold answer computed anywhere other than sanket/graph/solver.py and orientation.py.
2. Any prompt, log or file that could leak gold, scene data or receipts to a model.
3. Any use of global randomness, time-based values, system fonts or absolute paths.
4. Any change to human-owned files (orientation.py, solver.py, verify/independent.py).
5. Tests that were weakened, skipped or removed.
6. Missing tests for new logic.
7. Secrets or keys in code, config or logs.
Return a table: severity (high, medium, low), location, problem, suggested fix.
~~~~

### U2 — Debug a failing test

~~~~
ROLE: Debugging engineer.

CONTEXT: The test <TEST NAME> fails with the output pasted below.
<PASTE OUTPUT>

TASK: Find the root cause. Explain it in three sentences. Propose the smallest fix. Do not edit tests to make
them pass and do not touch human-owned files (orientation.py, solver.py, verify/independent.py); if you
believe one of them is wrong, show a failing test that proves it and stop. After the fix run `make test` and report.
~~~~

### U3 — Low-quota fallback

If the agent quota runs out:
1. Finish the current prompt by hand using the pattern in the nearest finished module.
2. Use a normal chat assistant for single functions: paste the function signature, the relevant part of docs/architecture.md and the test you want to pass.
3. Keep Prompts 2 and 7 (ground truth) for last-resort manual work by the lead; do not rush them.
4. Skip optional polish (second script, FastAPI wrapper) before skipping any test.
