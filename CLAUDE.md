# CLAUDE.md — NOC Triage Agent (spec-driven)

You are working in a **spec-driven** project. The specs are the source of truth. Code follows the specs, never the other way round.

## Read first, in this order
1. `specs/00-overview.md` — goal, scope, glossary
2. `specs/01-requirements.md` — user stories + acceptance criteria (REQ-x.y)
3. `specs/02-design.md` — architecture, tool contracts, business rules, file layout
4. `specs/03-tasks.md` — the ordered task list (the plan)
5. `specs/04-evals.md` + `evals/cases.yaml` — the 15 evaluation cases
6. `specs/05-deploy.md` — Agent Runtime and Cloud Run deployment

## Workflow rules (follow strictly)
1. **One task at a time.** Pick the first unchecked task in `specs/03-tasks.md`. Do not start the next until the current one is done.
2. **Plan before code.** For each task, state in 3–6 bullets what you will change and which REQ ids it satisfies. Wait for approval if the task is marked `[needs-approval]`.
3. **Tests first where possible.** For tool logic, write the pytest tests from the acceptance criteria, see them fail, then implement.
4. **Done means verified.** A task is done only when its "Done when" checks pass (tests green, command output shown). Then tick it `[x]` in `specs/03-tasks.md` and add a one-line note with the date.
5. **Spec changes are explicit.** If the spec is wrong or ambiguous, stop and propose a spec edit (show the diff). Never silently implement something different from the spec.
6. **Traceability.** Every test name or docstring references the REQ id it covers, e.g. `test_req_2_3_p1_requires_availability_breach`.
7. **Don't trust memory for ADK APIs.** ADK changes quickly. Before using an ADK API (Agent class args, ToolContext, eval file schema, CLI flags), check the installed version (`pip show google-adk`, read the package source, or run `adk <cmd> --help`) or the official docs at https://adk.dev. If something differs from the design doc, follow the installed version and note it in `specs/02-design.md` under "Version notes".

## Commands
```bash
uv sync                                   # install deps
uv run pytest -q                          # unit tests (no LLM calls, must be fast)
uv run adk web                            # local dev UI (run from repo root; pick noc_triage_agent)
uv run adk run noc_triage_agent           # terminal chat
uv run adk eval noc_triage_agent evals/noc_triage.evalset.json \
  --config_file_path=evals/test_config.json --print_detailed_results
```

## Engineering standards
- Python 3.12, type hints everywhere, `ruff` clean.
- Tools return **small, structured dicts** with a `status` field. Errors are returned as data (`status: "error"`, `error_code`, `message`), never raised to the model.
- Business rules (thresholds, priority logic, ticket guard) live in **plain Python** (`rules.py`), not in the prompt. The prompt explains them; the code enforces them.
- No hardcoded project ids, secrets or model names in code: read from env with safe defaults.
- No silent fallbacks: log a warning when falling back.
- Unit tests never call the LLM or the network.

## Out of scope (do not build unless a task says so)
Real ticketing systems, real BigQuery, authentication UI, multi-agent orchestration, Terraform.
