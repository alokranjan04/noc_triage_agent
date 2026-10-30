# NOC Triage Agent

A Google ADK agent that triages mobile-network cell KPIs, detects threshold breaches, and opens NOC tickets with the correct priority -- all enforced by deterministic Python rules, not the LLM alone.

Built with **Google Agent Development Kit (ADK) 2.13.0**, **Gemini 3.8 Flash**, and **Python 3.12**.

## Architecture

```
User  (adk web / adk run / API)
  |
  v
noc_triage_agent          LlmAgent (Gemini Flash)
  |  instruction = triage rules in plain English
  |
  |-- tool: get_cell_kpis(cell_id)
  |     |-> CsvKpiRepository  (data/cell_kpis.csv)
  |     |-> rules.evaluate()  (thresholds, breach detection)
  |     '-> TicketStore        (check for existing ticket)
  |
  '-- tool: create_ticket(cell_id, priority)
        |-> rules.evaluate()  (re-check: priority justified?)
        '-> TicketStore        (fixture + session state)

Key principle: the LLM decides what to do; Python decides what is allowed.
Thresholds, priority checks, and duplicate guards are deterministic code.
The prompt describes the same rules so the model behaves well, but the
tools enforce them.
```

### File layout

```
noc-triage-agent/
├── pyproject.toml               # uv project; Python 3.12
├── CLAUDE.md                    # spec-driven workflow rules
├── specs/                       # source-of-truth specifications
│   ├── 00-overview.md           #   goal, scope, glossary
│   ├── 01-requirements.md       #   user stories (REQ-x.y)
│   ├── 02-design.md             #   architecture & tool contracts
│   ├── 03-tasks.md              #   ordered build plan (T1-T14)
│   ├── 04-evals.md              #   eval strategy & metrics
│   └── 05-deploy.md             #   deployment options
├── noc_triage_agent/            # the ADK agent package
│   ├── __init__.py
│   ├── agent.py                 #   root_agent + instruction
│   ├── tools.py                 #   get_cell_kpis, create_ticket
│   ├── rules.py                 #   thresholds, breaches, priority
│   ├── repository.py            #   KpiRepository (CSV) + TicketStore
│   ├── config.py                #   env-based configuration
│   ├── .env                     #   local secrets (git-ignored)
│   └── data/
│       ├── cell_kpis.csv        #   8-cell KPI fixture
│       └── open_tickets.json    #   1 pre-existing open ticket
├── tests/
│   ├── test_rules.py            #   threshold & priority logic
│   ├── test_repository.py       #   CSV loading & ticket store
│   └── test_tools.py            #   tool function contracts
├── evals/
│   ├── cases.yaml               #   15 eval cases (source)
│   ├── build_evalset.py         #   converts cases.yaml -> ADK JSON
│   ├── noc_triage.evalset.json  #   generated evalset
│   └── test_config.json         #   metric thresholds
└── docs/screenshots/            # manual run transcripts
```

## Quick start (clone to `adk web` in under 10 minutes)

### Prerequisites

- **Python 3.12** (3.12.x exactly)
- **[uv](https://docs.astral.sh/uv/)** package manager
- A **Google API key** with access to Gemini models (free tier works for manual runs)

### 1. Clone and install

```bash
git clone <repo-url> noc-triage-agent
cd noc-triage-agent
uv sync
```

### 2. Configure environment

```bash
cp .env.example noc_triage_agent/.env
```

Edit `noc_triage_agent/.env`:

```ini
# Option A: Gemini API key (recommended for getting started)
GOOGLE_GENAI_USE_VERTEXAI=FALSE
GOOGLE_API_KEY=<your-gemini-api-key>

# Option B: Vertex AI (requires project with Gemini model access)
# GOOGLE_GENAI_USE_VERTEXAI=TRUE
# GOOGLE_CLOUD_PROJECT=your-project-id
# GOOGLE_CLOUD_LOCATION=us-central1

NOC_AGENT_MODEL=gemini-3.8-flash
```

To get an API key: go to [Google AI Studio](https://aistudio.google.com/apikey) and create one.

### 3. Verify installation

```bash
uv run python -c "import google.adk; print('ADK OK')"
uv run adk --help          # should list: web, run, eval, deploy
```

### 4. Run tests (no LLM calls, fast)

```bash
uv run pytest -q
```

Expected: **19 passed**.

### 5. Launch the dev UI

```bash
uv run adk web
```

Open the URL shown (usually `http://localhost:8000`), select **noc_triage_agent**, and try:

| Prompt | Expected behaviour |
| --- | --- |
| "Triage CELL-1002." | Checks KPIs, finds drop_call_rate breach, creates P2 ticket TCK-1002 |
| "Triage CELL-1004." | Availability 82% -> P1 ticket TCK-1004 |
| "Triage CELL-1007." | Detects existing ticket TCK-1007, no duplicate created |
| "Reboot CELL-1004." | Refuses network change, offers to check KPIs instead |

### 6. Terminal chat (alternative)

```bash
uv run adk run noc_triage_agent
```

Type "Triage CELL-1002." and verify a P2 ticket is created.

## Business rules

All rules are enforced in `noc_triage_agent/rules.py` (deterministic Python, no LLM involvement):

| KPI | Breach condition | Threshold |
| --- | --- | --- |
| `drop_call_rate_pct` | > 2.0% | 2.0 |
| `prb_utilization_pct` | > 85.0% | 85.0 |
| `availability_pct` | < 99.0% | 99.0 |
| `avg_throughput_mbps` | < 5.0 Mbps | 5.0 |

**Priority logic:**
- **P1** -- availability < 95.0% (critical outage)
- **P2** -- at least one breach exists
- **P3** -- always allowed (informational, only when user explicitly requests)
- **NONE** -- no breaches, cell is healthy

**Safety guards (code-enforced):**
- P1 is rejected unless availability < 95% (`PRIORITY_NOT_JUSTIFIED`)
- Duplicate tickets are blocked (`status: "exists"`)
- Network change requests are refused by the agent instruction
- Ticket summaries are generated from KPI data only (no user-supplied text)

## Test data

| Cell | Situation | Expected outcome |
| --- | --- | --- |
| CELL-1001 | All KPIs healthy | No ticket |
| CELL-1002 | Drop rate 3.4% (> 2.0) | P2 ticket TCK-1002 |
| CELL-1003 | PRB 93%, throughput 4.1 Mbps | P2 ticket TCK-1003 |
| CELL-1004 | Availability 82% (< 95) | P1 ticket TCK-1004 |
| CELL-1005 | Availability 97.5% (< 99, >= 95) | P2 ticket TCK-1005 |
| CELL-1006 | All KPIs healthy | P3 only if explicitly requested |
| CELL-1007 | Drop rate 2.8%, ticket TCK-1007 open | No duplicate |
| CELL-1008 | Every KPI exactly at threshold | Healthy (strict comparison) |

## Evaluation

15 eval cases are defined in `evals/cases.yaml` and compiled to ADK format:

```bash
# Rebuild the evalset from cases.yaml (if you change cases)
uv run python evals/build_evalset.py

# Run evals (requires LLM calls -- uses your configured model/API key)
uv run adk eval noc_triage_agent evals/noc_triage.evalset.json \
  --config_file_path=evals/test_config.json --print_detailed_results
```

**Metrics and thresholds** (from `evals/test_config.json`):

| Metric | Target | Description |
| --- | --- | --- |
| `tool_trajectory_avg_score` | >= 0.9 | Did the agent call the right tools in the right order? |
| `response_match_score` | >= 0.5 | Does the final response match the reference? |

**Eval results:**

| Run | Date | Model | Trajectory | Response | Notes |
| --- | --- | --- | --- | --- | --- |
| *(pending)* | -- | gemini-3.8-flash | -- | -- | Blocked by free-tier API quota (20 req/day). Run with pay-as-you-go billing for full results. |

> **Note:** The eval run requires ~35-45 LLM API calls. The free-tier Gemini API has a 20 requests/day limit per project. Enable pay-as-you-go billing or wait for the daily quota to reset to run the full eval suite.

## Deployment

Two deployment options are documented in `specs/05-deploy.md`:

**Option A -- Agent Runtime** (managed):
```bash
uv run adk deploy agent_engine \
  --project=$GOOGLE_CLOUD_PROJECT \
  --region=$GOOGLE_CLOUD_LOCATION \
  --staging_bucket=$STAGING_BUCKET \
  noc_triage_agent
```

**Option B -- Cloud Run** (containerised):
```bash
uv run adk deploy cloud_run \
  --project=$GOOGLE_CLOUD_PROJECT \
  --region=$GOOGLE_CLOUD_LOCATION \
  --service_name=$SERVICE_NAME \
  noc_triage_agent
```

See `specs/05-deploy.md` for full instructions, smoke tests, and cleanup steps.

## Screenshots

Manual run transcripts captured during development are in `docs/screenshots/`:

| File | Scenario |
| --- | --- |
| `c01_healthy_cell.txt` | CELL-1001 -- healthy cell, no ticket |
| `c03_outage_p1.txt` | CELL-1004 -- availability outage, P1 ticket created |
| `c06_existing_ticket.txt` | CELL-1007 -- existing ticket detected, no duplicate |
| `c14_network_change_refusal.txt` | "Reboot CELL-1004" -- refused, offered KPI check |

## What I'd do next

1. **BigQuery KPI repository** -- Replace the CSV fixture with a `BigQueryKpiRepository` querying a partitioned table of real cell KPI measurements, enabling the agent to work with live production data.

2. **TM Forum TMF621 adapter** -- Integrate with a real trouble-ticketing system via the [TMF621 Trouble Ticket API](https://www.tmforum.org/resources/standard/tmf621-trouble-ticket-api-rest-specification-r19-0-0/), replacing the in-memory ticket store with actual NOC workflow.

3. **Pub/Sub alarm streaming** -- Subscribe to a Google Cloud Pub/Sub topic carrying real-time cell alarms, so the agent can proactively triage incoming alarms rather than waiting for manual prompts.

4. **Multi-agent orchestration** -- Split into specialised sub-agents (KPI analyser, ticket manager, escalation handler) coordinated by an ADK orchestrator agent for more complex NOC workflows.

5. **Authentication and RBAC** -- Add identity-aware proxy and role-based access control so only authorised NOC engineers can create tickets through the deployed agent.

## Cost note

Local runs and evals call a Gemini model via your configured API key or GCP project (small cost per run). Deployed resources on Agent Runtime or Cloud Run cost money while they exist; follow the cleanup steps in `specs/05-deploy.md` when you're done.

## License

This project was built as an interview demonstration. See individual spec files for requirements and design rationale.
