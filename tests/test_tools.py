"""Tests for the ADK tool layer. Covers REQ-1.1-1.4 and REQ-3.1-3.7."""

from noc_triage_agent.tools import create_ticket, get_cell_kpis


class FakeToolContext:
    def __init__(self, state=None):
        self.state = state if state is not None else {"tickets": {}}


def test_get_cell_kpis_for_valid_cell_has_expected_shape():
    response = get_cell_kpis("CELL-1003")

    assert response["status"] == "ok"
    assert response["cell_id"] == "CELL-1003"
    assert response["site_id"] == "SITE-02"
    assert response["region"] == "Mumbai"
    assert response["window_end"] == "2026-10-30T09:00:00+05:30"
    assert response["kpis"]["drop_call_rate_pct"] == 1.1
    assert response["suggested_priority"] == "P2"
    assert response["open_ticket_id"] is None
    assert response["breaches"][0]["kpi"] == "prb_utilization_pct"
    assert response["breaches"][1]["kpi"] == "avg_throughput_mbps"


def test_get_cell_kpis_rejects_invalid_cell_format_without_tool_call():
    response = get_cell_kpis("cell-1003")

    assert response["status"] == "error"
    assert response["error_code"] == "INVALID_CELL_ID"
    assert "CELL-1234" in response["message"]


def test_get_cell_kpis_handles_unknown_cell():
    response = get_cell_kpis("CELL-9999")

    assert response["status"] == "error"
    assert response["error_code"] == "CELL_NOT_FOUND"


def test_get_cell_kpis_reports_open_ticket_for_cell_1007():
    """REQ-1.2: get_cell_kpis must surface open_ticket_id from fixture so agent instruction step 3 fires."""
    ctx = FakeToolContext()
    response = get_cell_kpis("CELL-1007", ctx)

    assert response["status"] == "ok"
    assert response["open_ticket_id"] == "TCK-1007"


def test_create_ticket_returns_existing_ticket_for_open_cell():
    ctx = FakeToolContext()
    response = create_ticket("CELL-1007", "P2", ctx)

    assert response["status"] == "exists"
    assert response["ticket_id"] == "TCK-1007"
    assert response["priority"] == "P2"


def test_create_ticket_creates_new_p2_ticket_for_valid_cell():
    ctx = FakeToolContext()
    response = create_ticket("CELL-1002", "P2", ctx)

    assert response["status"] == "created"
    assert response["ticket_id"] == "TCK-1002"
    assert response["priority"] == "P2"
    assert ctx.state["tickets"]["TCK-1002"]["cell_id"] == "CELL-1002"


def test_create_ticket_rejects_p1_without_availability_breach():
    ctx = FakeToolContext()
    response = create_ticket("CELL-1002", "P1", ctx)

    assert response["status"] == "error"
    assert response["error_code"] == "PRIORITY_NOT_JUSTIFIED"
    assert "P2" in response["message"]


def test_create_ticket_allows_p3_for_healthy_cell_when_requested():
    ctx = FakeToolContext()
    response = create_ticket("CELL-1006", "P3", ctx)

    assert response["status"] == "created"
    assert response["ticket_id"] == "TCK-1006"
    assert response["priority"] == "P3"


def test_create_ticket_rejects_invalid_priority():
    ctx = FakeToolContext()
    response = create_ticket("CELL-1002", "P9", ctx)

    assert response["status"] == "error"
    assert response["error_code"] == "INVALID_PRIORITY"


def test_tools_never_raise_for_malformed_or_guarded_inputs():
    for bad_cell in ["abc", "CELL-12", "CELL-12345", "CELL-2B22"]:
        assert "status" in get_cell_kpis(bad_cell)

    for bad_priority in ["P0", "p2", "", None]:
        response = create_ticket("CELL-1002", bad_priority, FakeToolContext())
        assert response["status"] in {"error", "exists", "created"}
