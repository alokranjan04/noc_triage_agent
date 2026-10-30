"""Tool implementations for KPI lookup and ticket creation."""

from __future__ import annotations

import re
from typing import Any

from .repository import CsvKpiRepository, TicketStore
from .rules import CELL_ID_PATTERN, build_summary, find_breaches, is_priority_justified, suggested_priority, ticket_id_for


CELL_ID_RE = re.compile(CELL_ID_PATTERN)


def get_cell_kpis(cell_id: str, tool_context: Any | None = None) -> dict[str, Any]:
    """Get the latest KPIs for one mobile network cell and the breach analysis. Use this before any ticket decision. cell_id must look like CELL-1234.

    Returns a dict with the latest KPI snapshot, breached metrics, suggested priority, and any open ticket for the cell.
    """
    if not isinstance(cell_id, str) or not CELL_ID_RE.fullmatch(cell_id):
        return {
            "status": "error",
            "error_code": "INVALID_CELL_ID",
            "message": "Please give the cell id in the format CELL-1234 so I can check its KPIs.",
        }

    record = CsvKpiRepository().get_latest(cell_id)
    if record is None:
        return {
            "status": "error",
            "error_code": "CELL_NOT_FOUND",
            "message": f"I couldn't find {cell_id}. Please check the cell id. No ticket was opened.",
        }

    state = getattr(tool_context, "state", None) if tool_context is not None else None
    if state is None:
        state = {"tickets": {}}
    store = TicketStore(state)
    open_ticket_id = store.find_open(cell_id)

    kpis = {
        "drop_call_rate_pct": float(record["drop_call_rate_pct"]),
        "prb_utilization_pct": float(record["prb_utilization_pct"]),
        "availability_pct": float(record["availability_pct"]),
        "avg_throughput_mbps": float(record["avg_throughput_mbps"]),
    }
    breaches = [
        {
            "kpi": breach.kpi,
            "value": breach.value,
            "threshold": breach.threshold,
            "rule": breach.rule,
        }
        for breach in find_breaches(kpis)
    ]
    return {
        "status": "ok",
        "cell_id": record["cell_id"],
        "site_id": record["site_id"],
        "region": record["region"],
        "window_end": record["window_end"],
        "kpis": kpis,
        "breaches": breaches,
        "suggested_priority": suggested_priority(kpis),
        "open_ticket_id": open_ticket_id,
    }


def create_ticket(cell_id: str, priority: str, tool_context: Any | None = None) -> dict[str, Any]:
    """Open a NOC ticket for a cell. priority must be P1, P2 or P3. Call get_cell_kpis first. Use P3 only when the user explicitly asks for a low-priority or informational ticket.

    This tool does not accept free-form text for the ticket summary. The summary is generated from KPI data so user input cannot change priority or text.
    """
    if not isinstance(cell_id, str) or not CELL_ID_RE.fullmatch(cell_id):
        return {
            "status": "error",
            "error_code": "INVALID_CELL_ID",
            "message": "Please give the cell id in the format CELL-1234 so I can check its KPIs.",
        }

    if priority not in {"P1", "P2", "P3"}:
        return {
            "status": "error",
            "error_code": "INVALID_PRIORITY",
            "message": "Priority must be one of P1, P2 or P3.",
        }

    record = CsvKpiRepository().get_latest(cell_id)
    if record is None:
        return {
            "status": "error",
            "error_code": "CELL_NOT_FOUND",
            "message": f"I couldn't find {cell_id}. Please check the cell id. No ticket was opened.",
        }

    state = getattr(tool_context, "state", None) if tool_context is not None else None
    if state is None:
        state = {"tickets": {}}

    store = TicketStore(state)
    existing_ticket_id = store.find_open(cell_id)
    if existing_ticket_id is not None:
        return {"status": "exists", "ticket_id": existing_ticket_id, "priority": store.fixture_tickets.get(existing_ticket_id, {}).get("priority", "P2")}

    kpis = {
        "drop_call_rate_pct": float(record["drop_call_rate_pct"]),
        "prb_utilization_pct": float(record["prb_utilization_pct"]),
        "availability_pct": float(record["availability_pct"]),
        "avg_throughput_mbps": float(record["avg_throughput_mbps"]),
    }
    breaches = find_breaches(kpis)

    if not is_priority_justified(priority, kpis):
        suggested = suggested_priority(kpis)
        message = f"{priority} requires a justified condition. Suggested priority for this cell: {suggested}."
        if priority == "P1":
            message = "P1 requires availability < 95%. Suggested priority for this cell: P2."
        elif priority == "P2":
            message = "P2 requires a breach. Suggested priority for this cell: NONE."
        return {"status": "error", "error_code": "PRIORITY_NOT_JUSTIFIED", "message": message}

    ticket_id = ticket_id_for(cell_id)
    summary = build_summary(cell_id, breaches)
    ticket = {
        "ticket_id": ticket_id,
        "cell_id": cell_id,
        "priority": priority,
        "status": "OPEN",
        "summary": summary,
    }
    store.add(ticket)

    return {"status": "created", "ticket_id": ticket_id, "priority": priority, "summary": summary}
