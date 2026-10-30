# Deployment Architecture

> Evidence base: commit `f2c089c` plus the uncommitted working tree, 2026-10-30. Diagram: [deployment-architecture.html](diagrams/deployment-architecture.html).

**Bottom line: only local development is implemented. Nothing is deployed to Google Cloud.** `specs/03-tasks.md` leaves T11 (Agent Runtime), T12 (smoke test) and T13 (Cloud Run) unchecked, and the repository has no `deploy/` folder, `Dockerfile` or `noc_triage_agent/requirements.txt`. Both cloud targets are therefore drawn in red as **proposed**.

## 1. Local development (implemented)

| Piece | What it is | Evidence |
| --- | --- | --- |
| Developer machine | Windows, Python 3.12 (`>=3.12,<3.13`), `uv` for packages | `pyproject.toml:10`, `CLAUDE.md:22-30` |
| ADK app | The `noc_triage_agent` package; `__init__.py` imports `agent` so ADK finds `root_agent` | `noc_triage_agent/__init__.py` |
| Dev UI | `uv run adk web` (browser) or `uv run adk run noc_triage_agent` (terminal), run from the repo root | `CLAUDE.md:25-27`, task T6 done |
| Data | `data/cell_kpis.csv` and `data/open_tickets.json`, inside the package so a deploy would carry them | `specs/02-design.md:49` |
| Sessions and tickets | Ticket dict in session state. The dev server keeps sessions in `noc_triage_agent/.adk/session.db` (SQLite, git-ignored) | Inspected: 27 sessions |
| Config | `noc_triage_agent/.env`, copied from `.env.example`, git-ignored | `.env.example`, `.gitignore:1-3` |
| Custom dashboard (uncommitted) | FastAPI app, `uv run python ui/app.py`, `127.0.0.1:8501`, calls the tool functions directly | `ui/app.py` |
| Tests and evals | `uv run pytest -q`; `uv run adk eval ...` | See [QA diagram](diagrams/qa-evaluation-architecture.html) |

### Environment variables (names only; values are not recorded here)

| Variable | Read by | Purpose |
| --- | --- | --- |
| `NOC_AGENT_MODEL` | `config.py:10` | Model id, default `gemini-3.8-flash` |
| `GOOGLE_GENAI_USE_VERTEXAI` | `config.py:12`, read by the Google GenAI library | `TRUE` = Vertex AI, `FALSE` = API key |
| `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION` | `config.py:13-14` | Project and region; default location `us-central1` |
| `GOOGLE_API_KEY` | Google GenAI library | API-key mode |
| `OPEN_ROUTER_KEY`, `OPENROUTER_MODEL` | Working-tree `config.py` only | Routes the model through OpenRouter via `LiteLlm` |
| `STAGING_BUCKET`, `SERVICE_NAME` | `.env.example` only; used by deploy commands, not by code | Proposed deployment |

## 2. Google Cloud (proposed, not implemented)

| Target | Planned command | Status |
| --- | --- | --- |
| Agent Runtime (formerly Vertex AI Agent Engine) | `uv run adk deploy agent_engine --project --region --staging_bucket --display_name "NOC Triage Agent" noc_triage_agent` | **Proposed.** Specified in `specs/05-deploy.md:25-38`; T11 unchecked |
| Cloud Run | `uv run adk deploy cloud_run ... --with_ui noc_triage_agent -- --no-allow-unauthenticated` | **Proposed.** `specs/05-deploy.md:40-54`; T13 is optional and unchecked |
| Remote smoke test | `deploy/smoke_agent_runtime.py` | **Does not exist.** T12 |

Why the cloud path is also blocked today: the design notes record that the Vertex AI publisher models returned 404 for the project used (`specs/02-design.md:186`), so development fell back to an API key. A deployment would need working Vertex AI model access, a staging bucket, enabled APIs and permissions (`specs/05-deploy.md:7-16, 38`).

## 3. Local versus deployed execution path

| Aspect | Local (today) | Deployed (proposed) |
| --- | --- | --- |
| Entry point | `adk web` / `adk run` on one machine | Agent Runtime endpoint or authenticated Cloud Run service |
| Session storage | Local SQLite file | Managed by Agent Runtime, or the container's choice on Cloud Run. Not designed or configured here |
| Ticket state | Session dict | Same dict, but inside the managed session; still not a ticket system |
| Model access | API key (used in practice) or Vertex AI | Vertex AI service account, no API key (`specs/02-design.md:178`) |
| Data | Files in the package | Files packaged in the agent folder; read-only |
| Logging | `config.py` logs the model choice and a missing-project warning; ADK writes logs to the temp folder | Cloud logging and traces are *claimed* in the spec but nothing is configured |
| Evaluation | `adk eval` locally | "Re-run the 15 prompts against the endpoint" in the spec; `check_rubric.py --remote` does not exist |

## 4. Implementation Gap / Proposed Enhancement

* No Dockerfile, `requirements.txt`, `deploy/` folder, smoke test, or recorded resource name.
* Cloud Run example in the README omits `--app_name` and `--with_ui`, which the spec includes.
* No authentication in front of the custom dashboard (spec: out of scope).
* Proposal: finish T11/T12 first, record the resource name in `deploy/agent_runtime.txt`, and add a budget alert before deploying, as the spec already advises.
