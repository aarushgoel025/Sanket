# Rules

Project rules for everyone on the team and for every AI agent. Place at `docs/rules.md`. If Antigravity offers a workspace rules setting, paste a copy there as well (check the current Antigravity settings for where rules go).

---

## 1. Correctness rules (highest priority)

1. **The gold answer never comes from a model.** Only the solver and orientation modules produce it.
2. **Two independent paths must agree.** A task is kept only if the solver answer equals the independent answer, render fidelity passes, and visibility passes. Disagreements go to `rejected.jsonl` with a reason.
3. **Ambiguity is rejection.** Equal-length shortest paths with different first hops reject the task.
4. **No leakage.** Prompts contain question, options and image or text description only. Tests enforce this.
5. **Bearings are multiples of 45.** Validate at load time.
6. **Never weaken a test to make it pass.** Fix the code or discuss the test.

## 2. Reproducibility rules

7. One master seed in config; per-task seeds derived from it.
8. Pass a `numpy.random.Generator` explicitly; no global randomness.
9. Fixed render viewport, device scale factor and fonts from `assets/fonts`.
10. Strip PNG metadata.
11. Pin dependency versions in `requirements.txt`.
12. Same seed and config must produce byte-identical `tasks.jsonl` and identical image hashes (tested).

## 3. Code rules

13. Python 3.11, type hints on public functions, `ruff` clean.
14. Data models live only in `sanket/schema.py`.
15. Functions do one thing; modules stay under about 300 lines.
16. Errors carry context (task id, path, model id); no bare `except`, no silent fallback.
17. No hard-coded absolute paths; use paths from config.
18. Model ids and rate limits come from `config/models.yaml`.
19. Comments explain why, not what.

## 4. Data and file rules

20. Generated data goes under `data/`; `data/cache/` is gitignored.
21. `data/sample_tasks/` (about 20 tasks) is committed; the full dataset may be committed or shared by link.
22. Rejected tasks are logged with a reason code: `solver_independent_mismatch`, `fidelity_fail`, `visibility_fail`, `blind_test_fail`, `ambiguous_route`, `duplicate`, `imbalanced`.
23. Real photos: public signage only, no faces or people, EXIF stripped, labelled by hand.
24. Fonts must be open licence (Noto family). Pictograms are our own SVG. No third-party logos or real organisation branding. Venues and issuers are fictional; images carry a small "SYNTHETIC" mark.

## 5. Secrets and API rules

25. API keys live only in `.env` (never committed). `.env.example` lists names without values.
26. Agents must not print, log or commit keys.
27. Tests never call real model APIs; use fakes or recorded fixtures.
28. All model calls go through the cache and the rate-limited runner; never call an adapter directly from analysis or demo code except for the live demo "Ask model" button, which also uses the cache.
29. Retry with exponential backoff; stop and report after repeated rate-limit failures instead of looping.

## 6. Evaluation rules

30. Scoring is exact match on the parsed option; no LLM judge.
31. Unparseable replies count as wrong and are logged.
32. Report sample sizes and 95% Wilson intervals with every accuracy figure.
33. Report results as measured; do not tune tasks to make a model look good or bad.
34. Prompt text is versioned; changing it bumps `prompt_version` and invalidates the cache for that version only.

## 7. Git and review rules

35. One feature per branch; short, imperative commit messages.
36. Human-owned modules (`graph/orientation.py`, `graph/solver.py`, `verify/independent.py`) change only with a second teammate reviewing the diff and tests.
37. Merge only when `make test` passes.
38. Review every AI-agent diff before merging; read the tests, not just the code.
39. Tag a release when the dataset is frozen (`v1.0-dataset`); never edit a frozen dataset in place.

## 8. Using AI coding agents

40. Give agents a clear goal, the file structure for the step, acceptance criteria and the test command.
41. Run planning mode (if available) for the generator, renderer, verifier and pipeline steps and approve the plan first.
42. Keep quota for hard parts: use agents for boilerplate, tests, templates and the demo; write or review the ground-truth logic yourself.
43. If an agent's output touches human-owned files or the contracts in `AGENTS.md`, reject it and restate the rule.

## 9. Team roles

| Role | Owns |
|---|---|
| Lead (builder) | schema, graph, solver, orientation, independent verifier, pipeline |
| Technical assistant | templates, fonts and assets, augmentation checks, running evaluation batches, clean-machine test, data QA |
| Pitch lead | domain research, consequence stories, real-photo collection and labelling, human audit of 50 tasks, deck, demo script |

## 10. Definition of done (project level)

- All acceptance criteria in `docs/prd.md` section 15 met.
- Validation report numbers regenerated from the final dataset.
- README quickstart works on a clean machine.
- Demo rehearsed with an offline fallback (cached results).
