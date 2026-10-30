"""Tests for KPI repository and session-scoped ticket tracking. Covers REQ-1.1, 1.3, 3.4, 3.7."""

from pathlib import Path

from noc_triage_agent.repository import CsvKpiRepository, TicketStore


def test_csv_kpi_repository_loads_8_cells_and_unknown_returns_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = CsvKpiRepository()

    assert repo.get_latest("CELL-1001")["cell_id"] == "CELL-1001"
    assert repo.get_latest("CELL-1003")["region"] == "Mumbai"
    assert repo.get_latest("CELL-9999") is None
    assert len(repo.rows) == 8


def test_csv_kpi_repository_uses_package_relative_path_from_any_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = CsvKpiRepository()
    record = repo.get_latest("CELL-1008")

    assert record is not None
    assert record["site_id"] == "SITE-05"
    assert record["avg_throughput_mbps"] == 5.0


def test_ticket_store_reads_fixture_and_session_state():
    state = {"tickets": {"TCK-1002": {"cell_id": "CELL-1002", "priority": "P2", "status": "OPEN"}}}
    store = TicketStore(state)

    assert store.find_open("CELL-1007") == "TCK-1007"
    assert store.find_open("CELL-1002") == "TCK-1002"

    store.add({"ticket_id": "TCK-1006", "cell_id": "CELL-1006", "priority": "P3", "status": "OPEN"})
    assert store.find_open("CELL-1006") == "TCK-1006"


def test_ticket_store_isolation_between_state_dicts():
    first_state = {"tickets": {"TCK-1001": {"cell_id": "CELL-1001", "priority": "P2", "status": "OPEN"}}}
    second_state = {"tickets": {}}

    first_store = TicketStore(first_state)
    second_store = TicketStore(second_state)

    assert first_store.find_open("CELL-1001") == "TCK-1001"
    assert second_store.find_open("CELL-1001") is None
