# End-to-End Architecture

> Evidence base: commit `f2c089c` plus the uncommitted working tree on 2026-10-30. Where the two differ, this page says so. Every diagram below is generated with Archify from a JSON file next to it in [`diagrams/`](diagrams/) and cites source files and line ranges.

## 1. The story in one paragraph

A **NOC engineer** (someone who watches a mobile network) types a plain-English request such as *"Triage CELL-1002."* into the **ADK dev UI**. The request reaches an **ADK agent**, which asks a **Gemini model** what to do. The model chooses one of two **tools**. The tools are ordinary Python functions that read a CSV of cell measurements (**KPIs**) and a ticket store. A small **decision engine** (`rules.py`) compares the numbers with fixed thresholds and decides the priority. The tool results go back to the model, which writes a short answer. **The LLM decides what to do; deterministic Python decides what is allowed.**

## 2. Diagrams

| Diagram | What it shows | File |
| --- | --- | --- |
| Runtime architecture | Layers 1-6, numbered interactions [1]-[16], error results, data stores | [end-to-end-architecture.html](diagrams/end-to-end-architecture.html) |
| Sequence 1 of 2 | Request to KPI evaluation | [sequence-1-request-to-kpis.html](diagrams/sequence-1-request-to-kpis.html) |
| Sequence 2 of 2 | Guarded ticket creation to final answer | [sequence-2-ticket-to-answer.html](diagrams/sequence-2-ticket-to-answer.html) |
| Decision engine (KPIs) | Thresholds, breaches, priority order | [decision-kpi-priority.html](diagrams/decision-kpi-priority.html) |
| Decision engine (ticket guards) | Five ordered guards in `create_ticket` | [decision-ticket-guards.html](diagrams/decision-ticket-guards.html) |
| QA and evaluation | pytest, 15-case eval, success criteria | [qa-evaluation-architecture.html](diagrams/qa-evaluation-architecture.html) |
| Deployment | Local (implemented) vs Google Cloud (proposed) | [deployment-architecture.html](diagrams/deployment-architecture.html) |

**Colour mapping.** Archify has seven fixed colour kinds, so the requested palette is approximated through legend labels: blue = user interfaces, purple = ADK agent and LLM, orange = tools, yellow = deterministic rules, green = data and stores, red = errors / not implemented, grey = testing and infrastructure. Colour names come from the legend inside each diagram. Exact hues follow Archify's theme and cannot be set per node.

## 3. Layers and components

| Layer | Component | Source | What it does |
| --- | --- | --- | --- |
| 1 User | NOC engineer, ADK Dev UI / CLI | `CLAUDE.md:22-30` | Sends text and receives text. The UI creates the session id. |
| 2 Orchestration | `noc_triage_agent` (`root_agent`) | `noc_triage_agent/agent.py:34-40` | ADK `Agent` with an instruction (the triage procedure in English) and two tools. |
| 2 Orchestration | Gemini model | `noc_triage_agent/config.py:10` | Reads the instruction, picks tools, writes the answer. Model id from `NOC_AGENT_MODEL`. |
| 3 Tools | `get_cell_kpis` | `noc_triage_agent/tools.py:15-66` | Validates the id, reads the KPI row, asks the rules for breaches, looks up an open ticket. |
| 3 Tools | `create_ticket` | `noc_triage_agent/tools.py:69-133` | Five ordered guards, then builds and stores a ticket. |
| 4 Decision engine | `rules.py` | `noc_triage_agent/rules.py:8-81` | Thresholds, `find_breaches`, `suggested_priority`, `is_priority_justified`, `ticket_id_for`, `build_summary`. |
| 5 Data and state | `CsvKpiRepository` | `noc_triage_agent/repository.py:21-49` | Loads `data/cell_kpis.csv` once when constructed. |
| 5 Data and state | `TicketStore` | `noc_triage_agent/repository.py:52-85` | Reads fixture tickets and `state["tickets"]`; writes only to `state`. |
| 5 Data and state | Session state | `repository.py:55-58` | A dict owned by the ADK session. |
| 6 Output | Final model text | `agent.py:30-31` (committed) | Up to 120 words: cell id, healthy or breaching, each breach, action taken. |

### Who decides what

| Question | Decided by | Evidence |
| --- | --- | --- |
| Which tool to call, with which cell id | LLM | `agent.py` instruction; eval trajectory cases |
| Is the id well-formed, does the cell exist | Code | `tools.py:20-33`, `74-94` |
| Which KPIs breached, what priority is justified | Code | `rules.py:26-62` |
| Which priority to *request* in `create_ticket` | LLM, told to copy `suggested_priority` | `agent.py` instruction step 4 |
| Whether the requested priority is *accepted* | Code | `tools.py:113-120`, `rules.py:53-62` |
| Whether a duplicate is created | Code | `tools.py:100-103` |
| Ticket id and summary text | Code | `rules.py:65-81` |
| Wording of the final answer | LLM | `agent.py` instruction |
| Refusing a network change | LLM, prompt only; no tool could do it anyway | `agent.py:12-14`, eval c14 |

## 4. Every request and response across a boundary

Numbers match the labels in the runtime diagram and in both sequence diagrams.

| # | From to To | Request | Parameters and format | Processing | Response | Failure |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | NOC engineer to ADK UI | Chat message | Free text, e.g. `Triage CELL-1002.` | None | None | None |
| 2 | ADK UI to Agent | New message | ADK `Content` (user role, text part) plus session id | ADK loads or creates the session | Event stream | Model errors surface in the UI |
| 3 | Agent to LLM | Model call | Instruction, user text, function declarations built from the two tool signatures and docstrings | Model reasons | Text or `function_call` | Quota or availability errors (503 seen in `specs/03-tasks.md` F3) |
| 4 | Agent to `get_cell_kpis` | Tool call | `{"cell_id": "CELL-1002"}`; ADK injects `tool_context` | Regex `^CELL-\d{4}$` | Dict (item 7) | `INVALID_CELL_ID` |
| 5 | `get_cell_kpis` to CSV repository | `get_latest(cell_id)` | Plain string | Linear scan of rows loaded at construction | Row dict or `None` (item 6) | `None` becomes `CELL_NOT_FOUND` |
| 6 | CSV repository to `get_cell_kpis` | Row | `cell_id, site_id, region, window_end`, four KPI floats | None | None | None |
| 7 | `get_cell_kpis` to Agent | Result | See contract below | Adds `breaches`, `suggested_priority`, `open_ticket_id` | Function response to the LLM | Error dict |
| 8 | Tool to decision engine | `find_breaches(kpis)`, `suggested_priority(kpis)` | Dict of four floats | Strict comparisons | See item 9 | None |
| 9 | Decision engine to tool | Verdict | List of `Breach(kpi, value, threshold, rule)`; `"P1"`, `"P2"` or `"NONE"` | None | None | None |
| 10 | Agent to `create_ticket` | Tool call | `{"cell_id": "CELL-1002", "priority": "P2"}`; no free-text field | Guards 1-5 | Dict (item 14) | Error dicts |
| 11 | `create_ticket` to duplicate check | `TicketStore.find_open(cell_id)` | String | Scans fixture tickets, then `state["tickets"]`, status `OPEN` | Ticket id or `None` | None |
| 12 | Duplicate check to ticket store | Reads | Fixture JSON and session dict | None | Ticket id or `None` | None |
| 13 | `create_ticket` to ticket store | `TicketStore.add(ticket)` | `{ticket_id, cell_id, priority, status: "OPEN", summary}` | Writes `state["tickets"][ticket_id]` | The ticket | None |
| 14 | `create_ticket` to Agent | Result | `created`, `exists` or `error` dict | None | Function response to the LLM | See contract |
| 15 | Agent to LLM | Second model call | Tool results as function responses | Model writes text | Final text | As item 3 |
| 16 | Agent to NOC engineer | Final event | Text, at most 120 words | Shown by the UI | None | None |

### Tool contracts (from `noc_triage_agent/tools.py`)

`get_cell_kpis(cell_id: str, tool_context=None) -> dict`. Real output captured by running the tool for `CELL-1004`:

```json
{ "status": "ok", "cell_id": "CELL-1004", "site_id": "SITE-03", "region": "Mumbai",
  "window_end": "2026-10-30T09:00:00+05:30",
  "kpis": { "drop_call_rate_pct": 6.0, "prb_utilization_pct": 10.0, "availability_pct": 82.0, "avg_throughput_mbps": 1.0 },
  "breaches": [
    { "kpi": "drop_call_rate_pct", "value": 6.0, "threshold": 2.0, "rule": "drop_call_rate_pct > 2.0" },
    { "kpi": "availability_pct", "value": 82.0, "threshold": 99.0, "rule": "availability_pct < 99.0" },
    { "kpi": "avg_throughput_mbps", "value": 1.0, "threshold": 5.0, "rule": "avg_throughput_mbps < 5.0" } ],
  "suggested_priority": "P1", "open_ticket_id": null }
```

Errors: `{"status": "error", "error_code": "INVALID_CELL_ID" | "CELL_NOT_FOUND", "message": "..."}`.

`create_ticket(cell_id: str, priority: str, tool_context=None) -> dict`

| Outcome | Shape |
| --- | --- |
| Created | `{"status": "created", "ticket_id": "TCK-1004", "priority": "P1", "summary": "CELL-1004 breaching: ..."}` |
| Duplicate | `{"status": "exists", "ticket_id": "TCK-1007", "priority": "P2"}` |
| Error | `{"status": "error", "error_code": "INVALID_CELL_ID" \| "INVALID_PRIORITY" \| "CELL_NOT_FOUND" \| "PRIORITY_NOT_JUSTIFIED", "message": "..."}` |

## 5. Illustrative input and output

Input, similar to eval case c01: `Check CELL-1001 and open a ticket if needed.`

Output taken from a real captured run, [`docs/screenshots/c03_outage_p1.txt`](../screenshots/c03_outage_p1.txt) (CELL-1004):

```
Cell ID: CELL-1004   Status: Breaching
Breaches: drop_call_rate_pct 6 vs threshold 2; availability_pct 82 vs threshold 99; avg_throughput_mbps 1 vs threshold 5
Action Taken: Opened P1 ticket TCK-1004.
```

Model wording varies from run to run. Tool results do not.

## 6. State and persistence

| Question | Answer | Evidence |
| --- | --- | --- |
| Where do new tickets live | `state["tickets"]` of the current ADK session | `repository.py:55-58, 77-85` |
| Seeded ticket | `TCK-1007` for `CELL-1007`, read-only, loaded from JSON by each `TicketStore` | `open_tickets.json`, `repository.py:60-64` |
| Across requests in one session | Yes, the dict is part of the session | `tests/test_tools.py` ticket tests |
| Across sessions | No. A new state dict does not see earlier tickets | `tests/test_repository.py:39-47` |
| Across restarts | The ADK dev server writes sessions to `noc_triage_agent/.adk/session.db` (SQLite). Inspection found 27 sessions, 2 holding `TCK-` entries. A new session still starts empty, so there is no shared ticket list | Inspected `session.db` |
| Is this a ticketing database | No. There is no central ticket system in the repository | `specs/00-overview.md` (out of scope) |

## 7. Technology stack

Python 3.12 (`pyproject.toml`), `uv`, `google-adk[eval]` (2.13.0 noted in `specs/02-design.md`), `pydantic`, `pyyaml`, `pytest`, `ruff`, Gemini via Google GenAI. Uncommitted extras in the working tree: FastAPI + uvicorn dashboard (`ui/app.py`) and OpenRouter through ADK `LiteLlm` (`config.py`).

## 8. Implementation gaps and proposed enhancements

* **Documentation drift.** `README.md` and the design sketch mention `rules.evaluate()`. No such function exists; the real ones are `find_breaches` and `suggested_priority`.
* **No separate severity score.** "Severity assessment" is only `suggested_priority` (P1, P2, NONE).
* **Dashboard chat differs from the agent.** In the working tree it runs its own OpenRouter tool loop instead of the ADK `Runner` used in the committed version, so orchestration exists twice.
* **Session id.** The tools never read it; it only scopes `state`. No code logs or returns it.

More gaps: [decision-flow.md](decision-flow.md) and [deployment-architecture.md](deployment-architecture.md).

## 9. Testing and evaluation (development time only)

Diagram: [qa-evaluation-architecture.html](diagrams/qa-evaluation-architecture.html). None of this runs on a user request.

| Layer | Command | Calls the LLM | What it proves |
| --- | --- | --- | --- |
| Unit tests | `uv run pytest -q` (19 tests, all passing on 2026-10-30) | No | Rules, repository and tool guards behave as specified |
| ADK evaluation | `uv run adk eval noc_triage_agent evals/noc_triage.evalset.json --config_file_path=evals/test_config.json` | Yes | The model picks the right tools and arguments and answers close to the reference |

**Unit tests by file.** `test_rules.py` (5): strict thresholds, P1/P2/NONE matrix, priority justification, ticket id and summary. `test_repository.py` (4): CSV loads 8 cells, package-relative path, fixture plus session tickets, isolation between sessions. `test_tools.py` (10): output shape, error codes, duplicate, P1 rejected, P3 allowed, invalid priority, tools never raise for malformed input. Requirement ids appear in each file's docstring, not in each test name.

**Eval pipeline.** `evals/cases.yaml` (15 cases) is converted by `evals/build_evalset.py` into `evals/noc_triage.evalset.json` using ADK's own models. Each case stores the prompt, the expected tool calls and a reference answer. `adk eval` runs a fresh session per case, compares actual and expected tool calls, scores the answer against the reference, and applies `evals/test_config.json`.

| Metric | Threshold | How it is computed |
| --- | --- | --- |
| `tool_trajectory_avg_score` | 0.9 | Names and arguments of tool calls, in order, expected versus actual; averaged over cases |
| `response_match_score` | 0.5 | ROUGE word overlap between the final answer and `reference_response` |
| Safety rules | All 15 cases | Cases c06 (duplicate), c10 (pressure for P1), c14 (network change), c15 (injection) |

**Recorded results.** The local `noc_triage_agent/.adk/eval_history` (git-ignored) holds nine result files. In the latest, 15 of 15 cases passed with trajectory 1.000 and response 0.739 (lowest case 0.500, c10). The model was `gemini-2.5-flash` through OpenRouter in the uncommitted working tree. Earlier runs passed 11 to 14 of 15, and the first two files are partial (7 scored cases, then none), so they are not comparable. `specs/03-tasks.md` logs the same four runs, and the README table matches. These numbers come from the local history and the project's own log; they were **not re-run** for this documentation (that needs paid model calls).

**Gaps.** The optional `evals/check_rubric.py` (a must-include / must-not-include check, T10) appeared as an untracked file after this analysis; it calls OpenRouter in its own loop rather than the ADK agent, and it was not run or reviewed here. The reference answers in `cases.yaml` were reworded during iteration to raise ROUGE scores (see `git diff`). ROUGE cannot detect a wrong but similarly worded answer, so safety is judged from the case outcomes, not from the score.


