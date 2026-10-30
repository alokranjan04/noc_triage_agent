# 00 — Overview

## Problem
NOC (Network Operations Centre) engineers receive many alarms and spend time checking cell KPIs manually before deciding whether to open a ticket and at what priority. This is slow and inconsistent.

## Goal
A small **NOC Triage Agent** built with Google's **Agent Development Kit (ADK)** that:
1. Checks the latest KPIs for a mobile network cell (`get_cell_kpis`).
2. Decides whether the cell is breaching thresholds, using deterministic rules.
3. Opens a ticket with the correct priority when justified (`create_ticket`), and never opens a duplicate.
4. Explains its decision in plain language with the evidence (KPI values vs thresholds).

It runs locally in the ADK dev UI, is evaluated with **15 ADK eval cases**, and is deployed to **Agent Runtime** (formerly Vertex AI Agent Engine) or **Cloud Run**.

## Why this project (interview context)
It demonstrates, end to end: ADK agents and tools, deterministic guardrails around an LLM, unit tests, agent evaluation (trajectory + response), and deployment on Google Cloud — all in a telecom (NOC) setting.

## Scope
**In scope:** one ADK LLM agent, two tools, local CSV/JSON test data packaged with the agent, session-scoped ticket store, pytest unit tests, ADK evalset (15 cases), deployment to Agent Runtime and/or Cloud Run, a short README with screenshots.

**Out of scope (phase 2 ideas):** BigQuery-backed KPI repository, TM Forum TMF621 Trouble Ticket API adapter, alarm streaming via Pub/Sub, multi-agent design, authentication.

## Success criteria
| Measure | Target |
| --- | --- |
| Unit tests | 100% passing, cover every REQ in `01-requirements.md` that has deterministic logic |
| ADK eval: `tool_trajectory_avg_score` | ≥ 0.9 average across 15 cases |
| ADK eval: `response_match_score` | ≥ 0.5 average |
| Safety rules (never P1 without availability breach; never duplicate ticket; never act on network) | 15/15 cases, enforced in code |
| Deployed | Agent reachable on Agent Runtime or Cloud Run, one successful remote query shown |

## Glossary
| Term | Meaning |
| --- | --- |
| Cell | One radio coverage area of a mobile site, id format `CELL-NNNN` |
| KPI | Key Performance Indicator measured per cell per time window |
| Drop call rate | % of calls that ended abnormally (higher is worse) |
| PRB utilization | % of radio resources in use (high = congestion) |
| Availability | % of time the cell was in service (lower is worse) |
| Throughput | Average user download speed in Mbps (lower is worse) |
| Breach | A KPI value worse than its threshold |
| P1 / P2 / P3 | Ticket priority: critical / major / informational |
| Agent Runtime | Google Cloud's managed runtime for agents (formerly Vertex AI Agent Engine) |
