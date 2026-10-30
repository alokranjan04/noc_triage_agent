"""NOC Triage Agent — Web Dashboard.

A beautiful web UI that visualises cell KPIs, breach status, and ticket
management. Calls the agent's tool functions directly (no LLM needed for
the dashboard). An optional chat panel uses the ADK agent when a Gemini
API key is configured.

Usage:
    uv run python ui/app.py
    # then open http://localhost:8501
"""

from __future__ import annotations

import asyncio
import json
import sys
import traceback
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

# Add project root to path so we can import the agent package.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from noc_triage_agent.repository import CsvKpiRepository, TicketStore
from noc_triage_agent.rules import find_breaches, suggested_priority
from noc_triage_agent.tools import get_cell_kpis, create_ticket

app = FastAPI(title="NOC Triage Agent Dashboard")

# In-memory session state (mimics ADK ToolContext.state).
_session_state: dict[str, Any] = {"tickets": {}}


class FakeToolContext:
    """Minimal stand-in for ADK ToolContext so tools work outside the agent."""

    def __init__(self, state: dict[str, Any]) -> None:
        self.state = state


def _all_cell_ids() -> list[str]:
    """Return all cell ids from the CSV fixture."""
    repo = CsvKpiRepository()
    return [row["cell_id"] for row in repo.rows]


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.get("/api/cells")
def api_list_cells() -> JSONResponse:
    """Return summary for every cell."""
    cells = []
    ctx = FakeToolContext(_session_state)
    for cell_id in _all_cell_ids():
        result = get_cell_kpis(cell_id, ctx)
        cells.append(result)
    return JSONResponse(cells)


@app.get("/api/cells/{cell_id}")
def api_get_cell(cell_id: str) -> JSONResponse:
    ctx = FakeToolContext(_session_state)
    return JSONResponse(get_cell_kpis(cell_id, ctx))


@app.post("/api/tickets")
async def api_create_ticket(request: Request) -> JSONResponse:
    body = await request.json()
    cell_id = body.get("cell_id", "")
    priority = body.get("priority", "")
    ctx = FakeToolContext(_session_state)
    result = create_ticket(cell_id, priority, ctx)
    return JSONResponse(result)


@app.post("/api/tickets/reset")
async def api_reset_tickets() -> JSONResponse:
    _session_state["tickets"] = {}
    return JSONResponse({"status": "ok", "message": "Session tickets cleared."})


@app.get("/api/tickets")
def api_list_tickets() -> JSONResponse:
    store = TicketStore(_session_state)
    all_tickets = {}
    all_tickets.update(store.fixture_tickets)
    all_tickets.update(_session_state.get("tickets", {}))
    return JSONResponse(list(all_tickets.values()))


@app.post("/api/chat")
async def api_chat(request: Request) -> JSONResponse:
    """Send a message to the ADK agent. Requires a working Gemini API key."""
    body = await request.json()
    user_message = body.get("message", "")
    if not user_message.strip():
        return JSONResponse({"status": "error", "reply": "Please enter a message."})

    try:
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types as genai_types
        from noc_triage_agent.agent import root_agent

        session_service = InMemorySessionService()
        runner = Runner(agent=root_agent, app_name="noc_triage_ui", session_service=session_service)

        session = await session_service.create_session(app_name="noc_triage_ui", user_id="ui_user")

        user_content = genai_types.Content(
            role="user", parts=[genai_types.Part(text=user_message)]
        )

        reply_parts: list[str] = []
        async for event in runner.run_async(
            user_id="ui_user", session_id=session.id, new_message=user_content
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        reply_parts.append(part.text)

        reply = "\n".join(reply_parts) if reply_parts else "(No response from agent)"
        return JSONResponse({"status": "ok", "reply": reply})

    except Exception as exc:
        tb = traceback.format_exc()
        return JSONResponse({
            "status": "error",
            "reply": f"Agent error: {exc}\n\nThis usually means the Gemini API key quota is exhausted. The dashboard still works without the chat.",
        })


# ---------------------------------------------------------------------------
# Serve the single-page frontend
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    html_path = Path(__file__).parent / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8501)
