"""Repository layer for KPI and ticket data."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent / "data"


class KpiRepository:
    """Interface for retrieving the latest cell KPI records."""

    def get_latest(self, cell_id: str) -> dict[str, Any] | None:
        raise NotImplementedError


class CsvKpiRepository(KpiRepository):
    """Load cell KPI snapshots from the bundled CSV fixture."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else DATA_DIR / "cell_kpis.csv"
        self.rows = self._load_rows()

    def _load_rows(self) -> list[dict[str, Any]]:
        with self.path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            records: list[dict[str, Any]] = []
            for row in reader:
                normalized = dict(row)
                for key in (
                    "drop_call_rate_pct",
                    "prb_utilization_pct",
                    "availability_pct",
                    "avg_throughput_mbps",
                ):
                    if key in normalized:
                        normalized[key] = float(normalized[key])
                records.append(normalized)
            return records

    def get_latest(self, cell_id: str) -> dict[str, Any] | None:
        for row in self.rows:
            if row.get("cell_id") == cell_id:
                return row
        return None


class TicketStore:
    """Combine fixture tickets with per-session tickets in a dict-based state."""

    def __init__(self, state: dict[str, Any] | None = None):
        self.state = state if state is not None else {}
        self.state.setdefault("tickets", {})
        self.fixture_tickets = self._load_fixture_tickets()

    def _load_fixture_tickets(self) -> dict[str, dict[str, Any]]:
        fixture_path = DATA_DIR / "open_tickets.json"
        with fixture_path.open("r", encoding="utf-8") as handle:
            tickets = json.load(handle)
        return {ticket["ticket_id"]: ticket for ticket in tickets}

    def find_open(self, cell_id: str) -> str | None:
        for ticket in self.fixture_tickets.values():
            if ticket.get("cell_id") == cell_id and ticket.get("status") == "OPEN":
                return ticket["ticket_id"]

        for ticket_id, ticket in self.state.get("tickets", {}).items():
            if ticket.get("cell_id") == cell_id and ticket.get("status") == "OPEN":
                return ticket_id

        return None

    def add(self, ticket: dict[str, Any]) -> dict[str, Any]:
        ticket_id = ticket.get("ticket_id") or next(
            (key for key, value in self.state.get("tickets", {}).items() if value is ticket),
            None,
        )
        if ticket_id is None:
            ticket_id = ticket["ticket_id"]
        self.state.setdefault("tickets", {})[ticket_id] = ticket
        return ticket
