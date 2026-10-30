# 02 — Design

## 1. Architecture

```
User (adk web / API)
   │
   ▼
noc_triage agent  (ADK LlmAgent, Gemini Flash model from env)
   │  instruction = triage rules in plain English
   ├── tool: get_cell_kpis(cell_id)              ──► KpiRepository (CSV fixture)  ──► rules.evaluate()
   └── tool: create_ticket(cell_id, priority,     ──► rules.evaluate() (re-check)  ──► TicketStore
                           tool_context)                                            (fixture + session state)
```

Principle: **the LLM decides what to do; Python decides what is allowed.** Thresholds, priority and duplicate checks are deterministic code. The prompt describes the same rules so the model behaves well, but the tools enforce them.

## 2. File layout (target)

```
noc-triage-agent/
├── CLAUDE.md
├── README.md
├── pyproject.toml                 # uv project; deps: google-adk[eval], pydantic, pyyaml, pytest, ruff
├── .env.example
├── specs/ ...
├── evals/
│   ├── cases.yaml                 # human-readable source of the 15 cases (spec)
│   ├── build_evalset.py           # converts cases.yaml -> ADK evalset JSON
│   ├── noc_triage.evalset.json    # generated, committed
│   └── test_config.json           # metric thresholds
├── noc_triage_agent/              # the ADK agent package (this folder is deployed)
│   ├── __init__.py                # from . import agent
│   ├── agent.py                   # root_agent definition + instruction
│   ├── tools.py                   # get_cell_kpis, create_ticket (thin, call rules/repos)
│   ├── rules.py                   # thresholds, evaluate(), priority logic (pure functions)
│   ├── repository.py              # KpiRepository (CSV) + TicketStore
│   ├── config.py                  # env vars with defaults
│   ├── .env                       # local only, git-ignored
│   └── data/
│       ├── cell_kpis.csv          # fixture KPI snapshot (provided)
│       └── open_tickets.json      # fixture open tickets (provided)
└── tests/
    ├── test_rules.py
    ├── test_repository.py
    └── test_tools.py
```

Test data lives **inside** `noc_triage_agent/` so `adk deploy` packages it.

## 3. Business rules (`rules.py`)

```python
THRESHOLDS = {
    "drop_call_rate_pct":  {"op": ">", "limit": 2.0},
    "prb_utilization_pct": {"op": ">", "limit": 85.0},
    "availability_pct":    {"op": "<", "limit": 99.0},
    "avg_throughput_mbps": {"op": "<", "limit": 5.0},
}
P1_AVAILABILITY_BELOW = 95.0
CELL_ID_PATTERN = r"^CELL-\d{4}$"

@dataclass(frozen=True)
class Breach:
    kpi: str
    value: float
    threshold: float
    rule: str            # e.g. "drop_call_rate_pct > 2.0"

def find_breaches(kpis: dict[str, float]) -> list[Breach]: ...        # REQ-2.1 (strict comparison)
def suggested_priority(kpis: dict[str, float]) -> str: ...            # REQ-2.2 -> "P1" | "P2" | "NONE"
def is_priority_justified(priority: str, kpis: dict[str, float]) -> bool: ...   # REQ-3.2, REQ-3.3
def ticket_id_for(cell_id: str) -> str: ...                          # REQ-3.5
def build_summary(cell_id: str, breaches: list[Breach]) -> str: ...  # REQ-3.6, <= 200 chars
```

`is_priority_justified`: P1 → availability < 95.0; P2 → at least one breach; P3 → always True (cell must exist); anything else → False.

## 4. Data access (`repository.py`)

- `KpiRepository` protocol with `get_latest(cell_id) -> dict | None`. `CsvKpiRepository` loads `data/cell_kpis.csv` once (path relative to the package via `pathlib`, not the working directory).
- `TicketStore`: combines fixture tickets (`data/open_tickets.json`, read-only) with tickets created in this session (`tool_context.state["tickets"]`, a dict keyed by ticket id). `find_open(cell_id)` checks both. `add(ticket, state)` writes only to session state. This gives isolation per conversation and per eval case (REQ-3.7).
- Phase 2 (not now): `BigQueryKpiRepository` with a parameterized query against a partitioned table.

## 5. Tool contracts (`tools.py`)

Docstrings matter: ADK sends the function name, docstring and typed parameters to the model as the tool schema. Write them as instructions to the model.

### `get_cell_kpis(cell_id: str) -> dict`
Docstring (draft): *"Get the latest KPIs for one mobile network cell and the breach analysis. Use this before any ticket decision. cell_id must look like CELL-1234."*

Success:
```json
{
  "status": "ok",
  "cell_id": "CELL-1003", "site_id": "SITE-02", "region": "Mumbai",
  "window_end": "2026-10-30T09:00:00+05:30",
  "kpis": {"drop_call_rate_pct": 1.1, "prb_utilization_pct": 93.0,
           "availability_pct": 99.9, "avg_throughput_mbps": 4.1},
  "breaches": [
    {"kpi": "prb_utilization_pct", "value": 93.0, "threshold": 85.0, "rule": "prb_utilization_pct > 85.0"},
    {"kpi": "avg_throughput_mbps", "value": 4.1, "threshold": 5.0, "rule": "avg_throughput_mbps < 5.0"}
  ],
  "suggested_priority": "P2",
  "open_ticket_id": null
}
```
Errors: `{"status": "error", "error_code": "INVALID_CELL_ID" | "CELL_NOT_FOUND", "message": "<actionable text>"}`.

### `create_ticket(cell_id: str, priority: str, tool_context: ToolContext) -> dict`

There is deliberately **no free-text parameter**: the summary is generated from KPI data, so user text can never reach the ticket or influence priority, and eval trajectories stay deterministic (ADK compares tool arguments).
Docstring (draft): *"Open a NOC ticket for a cell. priority must be P1, P2 or P3. Call get_cell_kpis first. Use P3 only when the user explicitly asks for a low-priority or informational ticket."*

Behaviour, in order:
1. Validate cell id format → `INVALID_CELL_ID`.
2. Validate priority ∈ {P1, P2, P3} → `INVALID_PRIORITY`.
3. Load KPIs → `CELL_NOT_FOUND`.
4. If an open ticket exists for the cell (fixture or session) → `{"status": "exists", "ticket_id": ..., "priority": ...}` (REQ-3.4).
5. `is_priority_justified` false → `{"status": "error", "error_code": "PRIORITY_NOT_JUSTIFIED", "message": "P1 requires availability < 95%. Suggested priority for this cell: P2."}`.
6. Create `{"ticket_id": ticket_id_for(cell), "cell_id", "priority", "status": "OPEN", "summary": build_summary(...)}` in session state → `{"status": "created", "ticket_id", "priority", "summary"}`.

For P3 tickets on a healthy cell, the summary is `"Informational check requested for <cell_id>; all KPIs within thresholds."`

> **ToolContext:** in ADK, a tool function can declare a `tool_context: ToolContext` parameter; ADK injects it and hides it from the model's schema. Verify the import path and behaviour in the installed ADK version before relying on it (see CLAUDE.md rule 7).

## 6. Agent (`agent.py`)

```python
root_agent = Agent(                     # verify class name/args in installed ADK (Agent / LlmAgent)
    name="noc_triage_agent",
    model=config.MODEL,                 # env NOC_AGENT_MODEL
    description="Triage mobile network cells: check KPIs and open NOC tickets.",
    instruction=INSTRUCTION,
    tools=[get_cell_kpis, create_ticket],
)
```

### Instruction (draft — iterate using evals)
```
You are a NOC triage assistant for a mobile network operator.

You can only: (1) check a cell's KPIs with get_cell_kpis, (2) open a ticket with create_ticket.
You cannot change the network. If asked to reboot, reset, reconfigure or disable anything,
say you can't make network changes, offer to check KPIs or open a ticket, and do not call tools.

Cell ids look like CELL-1234. If the user gives an id in another format, ask for a valid id
and do not call tools.

Triage procedure for each cell the user mentions:
1. Call get_cell_kpis.
2. If status is error, tell the user what went wrong and stop for that cell.
3. If open_ticket_id is set, tell the user that ticket already exists. Do not create another.
4. If suggested_priority is P1 or P2 and the user asked to triage, check, or open a ticket,
   call create_ticket with exactly that priority — unless the user said not to open a ticket.
5. If suggested_priority is NONE, report the cell as healthy and do not open a ticket,
   unless the user explicitly asks for a low-priority/informational ticket (then use P3).
Never choose a priority higher than suggested_priority, even if the user insists.
Never invent KPI values or ticket ids.

Answer in at most 120 words: cell id, healthy or breaching, each breach as
"<kpi> <value> vs threshold <threshold>", and the action taken.
```

## 7. Configuration (`config.py`)
| Env var | Default | Used for |
| --- | --- | --- |
| `NOC_AGENT_MODEL` | `gemini-2.5-flash` (replace with the current GA Flash id) | model |
| `GOOGLE_GENAI_USE_VERTEXAI` | `TRUE` | use Google Cloud (Agent Platform) instead of an API key |
| `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION` | none / `us-central1` | project and region |

## 8. Error handling and logging
- Tools never raise to the model; unexpected exceptions are caught, logged with the cell id, and returned as `error_code = INTERNAL_ERROR`.
- Log every tool call (name, args, status) at INFO; ADK traces show them in the dev UI.

## 9. Security notes
- No secrets in code; `.env` git-ignored.
- Deployed service account needs only Agent Platform (Vertex AI) user permissions; no write access elsewhere.
- Cloud Run deploy: keep `--no-allow-unauthenticated` unless it's a throwaway demo.

## 10. Version notes
*(Claude Code: record here any differences found between this design and the installed ADK version, with the date.)*

- Installed ADK version: `google-adk==2.13.0` (checked on 2026-10-30). The CLI exposes `web`, `run`, `eval`, and `deploy` as expected; no design changes were required for the initial setup task.
- **Model (2026-10-30):** `gemini-2.5-flash` is no longer available to new users; the current GA Flash model is `gemini-3.8-flash`. Default in `config.py` updated accordingly.
- **Vertex AI model access (2026-10-30):** The `ai-voice-agent-c2a2b` project returns 404 for all Gemini publisher models via `us-central1-aiplatform.googleapis.com` even with billing enabled. Root cause: the project is an AI Studio prepayment project, not a standard Vertex AI project. Workaround: use `GOOGLE_GENAI_USE_VERTEXAI=FALSE` with `GOOGLE_API_KEY` pointing to project `gen-lang-client-0856273588`. The `.env` is updated accordingly.
- **Eval metric names (T7, 2026-10-30):** Verified against `google-adk==2.13.0` source (`google/adk/evaluation/eval_metrics.py`). Both names in `evals/test_config.json` are correct prebuilt metric names: `tool_trajectory_avg_score` = `PrebuiltMetrics.TOOL_TRAJECTORY_AVG_SCORE`; `response_match_score` = `PrebuiltMetrics.RESPONSE_MATCH_SCORE`. The config file validates cleanly via `EvalConfig.model_validate_json`. The ADK also adds four informational efficiency metrics automatically (`tool_call_count_v1`, `inference_call_count_v1`, `token_usage_v1`, `invocation_duration_v1`) — these never pass/fail. Optional upgrade: `final_response_match_v2` for LLM-judged semantic matching.
