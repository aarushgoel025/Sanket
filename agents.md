# AGENTS.md

Instructions for AI coding agents (Antigravity or any other) working in this repository.
Place this file at the repo root as `AGENTS.md`. Read `docs/rules.md` and `docs/architecture.md` before writing code.

---

## 1. Project in one paragraph

Sanket (working name) generates synthetic signboard images, questions about them and reference answers derived from a venue layout graph (never from a model). It then evaluates multimodal models on those tasks and reports where they fail. It is a Python package with a CLI and a Streamlit demo. It is not a hosted API and not a consumer app.

## 2. Commands

```
make setup      # pip install -r requirements.txt && playwright install chromium
make test       # pytest -q
make pilot      # build 20 tasks and evaluate one model on them (smoke test)
make build      # generate, verify, filter -> data/full_dataset
make eval       # run configured models in image and text modes (cached, resumable)
make report     # write reports/validation_report.md and findings_report.md
make demo       # streamlit run demo/app.py
```

Always run `make test` before declaring a task finished.

## 3. Directory map

See `docs/architecture.md` section 2 for the full tree. Key points:

- `sanket/schema.py` is the single source of truth for data models. Never duplicate model definitions elsewhere.
- `sanket/graph/` and `sanket/verify/independent.py` are **human-owned** (see section 5).
- `config/` holds YAML; `assets/` holds fonts, icons, templates; `data/` holds generated output; `data/cache/` is gitignored.

## 4. Core contracts (do not change without approval)

1. All bearings and headings are multiples of 45 degrees. `schema.py` rejects anything else.
2. The answer set is fixed and always in this order:
   `AHEAD, AHEAD_RIGHT, RIGHT, BACK_RIGHT, BACK, BACK_LEFT, LEFT, AHEAD_LEFT, CLOSED, NOT_INDICATED`.
3. `arrow_angle` is clockwise degrees from "up" in the viewer's frame; "up" means AHEAD.
4. The gold answer comes only from `graph/solver.py` plus `graph/orientation.py`. No model call may produce, change or confirm a gold answer.
5. Prompts built for models contain the question, the options and the image (or text description) only. Never include `gold`, `scene_path`, scene contents, receipts or file names that reveal the answer.
6. Every random draw uses a `numpy.random.Generator` created from the task seed and passed explicitly. No global `random`, no `np.random.*` module-level calls, no time-based values in generated data.
7. Generated PNG files have all metadata stripped.
8. Model responses are cached by `(model_id, task_id, mode, prompt_version)` and never re-requested if cached.

## 5. Human-owned modules

Do not edit these files except when the user explicitly asks, and then show the diff and the new tests before finishing:

- `sanket/graph/orientation.py`
- `sanket/graph/solver.py`
- `sanket/verify/independent.py`
- their tests: `tests/test_orientation.py`, `tests/test_solver.py`, `tests/test_verifier.py`

You may read them, write additional tests for them, and report suspected bugs. If you think one is wrong, explain why with a failing test instead of changing it.

## 6. Workflow for every task

1. Read the task prompt, `docs/architecture.md` and `docs/rules.md`.
2. If a planning mode is available, produce a short plan first and wait for approval on modules marked in the prompt.
3. Write or update tests first for any logic with a clear expected result.
4. Implement the smallest change that satisfies the acceptance criteria in the prompt.
5. Run `make test`. Fix failures. Do not delete or weaken tests to make them pass.
6. Report: files changed, tests added, commands run, anything unfinished.

## 7. Do and don't

**Do**
- Keep functions small and typed; use pydantic models for structured data.
- Raise clear errors with context (task id, file path) instead of silent fallbacks.
- Log rejected tasks with a reason into `data/full_dataset/rejected.jsonl`.
- Use the fonts in `assets/fonts` only.
- Ask the user when a requirement is ambiguous.

**Don't**
- Don't commit `.env`, API keys, `data/cache/` or any secret.
- Don't call external model APIs from tests (use fakes and recorded fixtures).
- Don't invent model ids; read them from `config/models.yaml` and leave a clear placeholder if missing.
- Don't add dependencies without listing them in `requirements.txt` and telling the user why.
- Don't fall back to system fonts, global randomness or silent exception swallowing.
- Don't refactor unrelated files while doing a task.

## 8. Definition of done

A task is done only when:
- acceptance criteria in the prompt are met,
- `make test` passes,
- new logic has tests,
- no rule in `docs/rules.md` is violated,
- the final report lists files changed and any follow-ups.

## 9. Reporting format

End each task with:
```
Files changed: ...
Tests added/updated: ...
Commands run and result: ...
Open issues / assumptions: ...
```
