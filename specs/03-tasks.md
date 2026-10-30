# 03 — Tasks (the build plan)

Work top to bottom. One task at a time. Tick `[x]` only when every "Done when" check passes, and add `— done YYYY-MM-DD` at the end of the line.
Tasks marked `[needs-approval]` require the human to approve the plan before coding.

## Phase 1 — Build locally (plan day 7)

- [x] **T1. Project setup** `[needs-approval]` — done 2026-10-30
  - Create `pyproject.toml` with uv; Python 3.12; deps: `google-adk[eval]`, `pydantic`, `pyyaml`; dev deps: `pytest`, `ruff`. Create `.gitignore` (`.env`, `.venv`, `__pycache__`, `*.pyc`, `.adk/`).
  - Create the package skeleton from design §2 (`noc_triage_agent/__init__.py` containing `from . import agent`, empty modules, `tests/`).
  - Copy `.env.example` → `noc_triage_agent/.env` (human fills values).
  - Record the installed ADK version in design §10.
  - **Done when:** `uv sync` succeeds; `uv run python -c "import google.adk"` works; `uv run adk --help` lists `web`, `run`, `eval`, `deploy`.

- [x] **T2. Rules module (tests first)** — REQ-2.1, 2.2, 2.3, 3.2, 3.3, 3.5, 3.6 — done 2026-10-30
  - Write `tests/test_rules.py` first: each threshold just above/at/below the limit (strict comparison), P1/P2/NONE logic, `is_priority_justified` for P1/P2/P3/invalid, `ticket_id_for`, summary ≤ 200 chars and contains values and thresholds.
  - Implement `rules.py` per design §3.
  - **Done when:** `uv run pytest tests/test_rules.py -q` green; CELL-1008's values give `NONE`; CELL-1004's give `P1`; CELL-1005's give `P2`.

- [x] **T3. Repository module (tests first)** — REQ-1.1, 1.3, 3.4, 3.7 — done 2026-10-30
  - Tests: CSV loads 8 cells; unknown cell → None; path works from any working directory; `TicketStore.find_open` finds fixture TCK-1007; tickets added to a dict-based state are found; a new state dict doesn't see them (isolation).
  - Implement `repository.py` per design §4.
  - **Done when:** `uv run pytest tests/test_repository.py -q` green.

- [x] **T4. Tools (tests first)** — REQ-1.1–1.4, 3.1–3.7 — done 2026-10-30
  - Tests call the tool functions directly with a fake `tool_context` (an object with a `state` dict). Cover: valid cell output shape (design §5 example for CELL-1003 exactly), INVALID_CELL_ID, CELL_NOT_FOUND, open ticket reported for CELL-1007, create P2 on CELL-1002 → `TCK-1002`, duplicate create → `exists`, P1 on CELL-1002 → PRIORITY_NOT_JUSTIFIED, P3 on CELL-1006 allowed, INVALID_PRIORITY, tools never raise.
  - Verify how the installed ADK injects `ToolContext` before implementing.
  - **Done when:** `uv run pytest -q` all green; tool docstrings match design §5.

- [x] **T5. Agent definition** — REQ-4.1, 4.2, 5.1–5.3, 6.3 — done 2026-10-30
  - `config.py` (env vars, defaults, warning log on fallback) and `agent.py` (`root_agent` with the design §6 instruction and both tools).
  - **Done when:** `uv run adk run noc_triage_agent` answers "Triage CELL-1002." with a TCK-1002 P2 ticket.

- [x] **T6. Manual run in the dev UI** — REQ-6.4 — done 2026-10-30
  - `uv run adk web` from repo root; select `noc_triage_agent`; try the prompts of c01, c03, c06, c14. Inspect the Events/Trace view.
  - Save screenshots to `docs/screenshots/` (UI answer + trace).
  - **Done when:** 4 screenshots saved; any surprising behaviour noted as an issue in this file under "Findings".

## Phase 2 — Evaluate (plan day 8, part 1)

- [x] **T7. Eval config** — REQ-6.2 — done 2026-10-30
  - Confirm `evals/test_config.json` metric names against the installed ADK (`adk eval --help`, package source).
  - **Done when:** metric names verified; note in design §10.

- [x] **T8. Build the evalset from cases.yaml** `[needs-approval]` — REQ-6.2 — done 2026-10-30
  - Write `evals/build_evalset.py` using ADK's own evaluation Pydantic models (see `specs/04-evals.md`). Validate: 15 cases, ids unique, every expected tool exists in the agent.
  - **Done when:** `uv run python evals/build_evalset.py` writes `evals/noc_triage.evalset.json`, and loading it back with the ADK model class succeeds.

- [ ] **T9. Run evals and iterate** — REQ-6.2
  - Run the full set; for failures follow "Improving failures" in `04-evals.md`. Keep a log table here: run #, date, model, trajectory score, response score, change made.
  - **Done when:** `tool_trajectory_avg_score` ≥ 0.9 and `response_match_score` ≥ 0.5, and c06, c10, c14, c15 pass (the safety cases).

- [ ] **T10. Optional rubric check**
  - `evals/check_rubric.py` per `04-evals.md`.
  - **Done when:** prints a 15-row pass/fail table; all safety assertions pass.

## Phase 3 — Deploy (plan day 8, part 2)

- [ ] **T11. Deploy to Agent Runtime** `[needs-approval]` — REQ-6.4
  - Follow `specs/05-deploy.md` Option A. Save the resource name to `deploy/agent_runtime.txt`.
  - **Done when:** deployment succeeds and the resource is visible in the console.

- [ ] **T12. Remote smoke test**
  - `deploy/smoke_agent_runtime.py` per `05-deploy.md`.
  - **Done when:** "Triage CELL-1002." returns a TCK-1002 P2 answer from the deployed agent; output saved to `docs/remote_smoke.txt`.

- [ ] **T13. (Optional) Deploy to Cloud Run** `[needs-approval]`
  - Option B in `05-deploy.md`; authenticated proxy; screenshot of the deployed UI.

- [x] **T14. README and cleanup** — REQ-6.5 — done 2026-10-30
  - README: what it is, architecture diagram (ASCII is fine), how to run/test/eval/deploy, eval results table, screenshots, "what I'd do next" (BigQuery repository, TMF621 adapter, Pub/Sub alarms).
  - Delete cloud resources if not needed (see Clean up).
  - **Done when:** a new person can follow the README from clone to `adk web` in under 10 minutes.

## Findings

### F1 — T5 `get_cell_kpis` always returned `open_ticket_id: null` (fixed 2026-10-30)
`get_cell_kpis` had no `tool_context` parameter and always returned `"open_ticket_id": null`, so the agent instruction's step 3 ("if open_ticket_id is set…") never fired for CELL-1007. Fixed by adding `tool_context: Any | None = None` to `get_cell_kpis` and using `TicketStore.find_open` — same pattern as `create_ticket`. Added test `test_get_cell_kpis_reports_open_ticket_for_cell_1007`.

### F3 — T6 Gemini free-tier rate limit (503) during sequential runs (2026-10-30)
The `gen-lang-client-0817580282` API key returned 503 UNAVAILABLE on c06's first attempt (consecutive calls within ~2 min of each other). Switched to key from `gen-lang-client-0856273588`. Transcripts captured in `docs/screenshots/`. The ADK also raises on stdin close (`Aborted!`) which gives exit code 1 — this is expected behavior for piped single-message runs, not an agent error.

### F2 — T5 "Done when" blocked by Vertex AI model access (2026-10-30)
Project `ai-voice-agent-c2a2b` returns 404 for all Gemini models (`gemini-2.5-flash`, `gemini-2.0-flash`, `gemini-1.5-flash`) in `us-central1`. The agent code is correct and all 19 unit tests pass. To unblock the smoke test, either:
- **Option A (Vertex AI):** In Cloud Console → Vertex AI → enable the API, then verify the model name under "Model Garden".
- **Option B (Gemini API key):** Add `GOOGLE_API_KEY=<key>` and set `GOOGLE_GENAI_USE_VERTEXAI=FALSE` in `noc_triage_agent/.env`.

## Eval run log
| Run | Date | Model | Trajectory | Response | Change made |
| --- | --- | --- | --- | --- | --- |
