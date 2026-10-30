# 05 — Deployment

Two targets. Do **Agent Runtime** first (it's what the JD names); Cloud Run is the alternative.

> Command names and flags change between ADK versions. Run `uv run adk deploy --help`, `uv run adk deploy agent_engine --help` and `uv run adk deploy cloud_run --help` first and follow the installed version. (Agent Runtime was called Vertex AI Agent Engine; the CLI subcommand is still `agent_engine` at the time of writing.)

## Prerequisites (once)
```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project $GOOGLE_CLOUD_PROJECT
gcloud services enable aiplatform.googleapis.com cloudbuild.googleapis.com \
  run.googleapis.com artifactregistry.googleapis.com storage.googleapis.com
gcloud storage buckets create $STAGING_BUCKET --location=$GOOGLE_CLOUD_LOCATION   # Agent Runtime staging
```
Set a **budget alert** on the project before deploying.

Checklist before deploying:
- [ ] `uv run pytest -q` green
- [ ] `adk eval` meets the thresholds
- [ ] `noc_triage_agent/requirements.txt` exists if the deploy command needs it (check `--help`); include only runtime deps
- [ ] `noc_triage_agent/data/*` present (the fixtures ship with the agent)
- [ ] No secrets in the agent folder except the git-ignored `.env`

## Option A — Agent Runtime (formerly Agent Engine)
```bash
uv run adk deploy agent_engine \
  --project=$GOOGLE_CLOUD_PROJECT \
  --region=$GOOGLE_CLOUD_LOCATION \
  --staging_bucket=$STAGING_BUCKET \
  --display_name="NOC Triage Agent" \
  noc_triage_agent
```
The command packages the agent, wraps it in an ADK app and deploys it to the managed runtime; it prints a resource name (`projects/.../reasoningEngines/...`). Save it to `deploy/agent_runtime.txt`.

**Smoke test** (`deploy/smoke_agent_runtime.py`, task T12): use the Vertex AI / Agent Platform SDK to get the deployed agent by resource name, create a session, send "Triage CELL-1002." and print the streamed events. Expected: a `get_cell_kpis` call, a `create_ticket` call with P2, and a final answer mentioning TCK-1002. Check the current SDK method names in the docs before writing it.

Permissions: if the deployed agent can't call the model, grant the Agent Runtime (Reasoning Engine) service agent the required Agent Platform / Vertex AI user role, as described in the deploy docs.

## Option B — Cloud Run
```bash
uv run adk deploy cloud_run \
  --project=$GOOGLE_CLOUD_PROJECT \
  --region=$GOOGLE_CLOUD_LOCATION \
  --service_name=$SERVICE_NAME \
  --app_name=noc_triage_agent \
  --with_ui \
  noc_triage_agent \
  -- --no-allow-unauthenticated
```
Flags after `--` are passed to `gcloud run deploy`. `--with_ui` adds the ADK web UI (fine for a demo). Open it through an authenticated proxy:
```bash
gcloud run services proxy $SERVICE_NAME --region=$GOOGLE_CLOUD_LOCATION --port=8080
```

## Evaluate the deployed agent
Run the same 15 prompts against the deployed endpoint (extend `evals/check_rubric.py` with a `--remote` option) and compare with local results. Record both in the README.

## Clean up (avoid charges)
```bash
# Agent Runtime: delete the deployed agent by resource name (SDK or console)
gcloud run services delete $SERVICE_NAME --region=$GOOGLE_CLOUD_LOCATION
gcloud storage rm -r $STAGING_BUCKET
```

## What to say in the interview
"I deployed the same ADK agent to Agent Runtime for managed sessions, scaling and tracing, and to Cloud Run as a container option. I ran my 15-case eval locally before deploying and re-ran the prompts against the deployed agent to confirm the behaviour matched."
