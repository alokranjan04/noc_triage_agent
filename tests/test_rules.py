"""Tests for deterministic breach and priority logic. Covers REQ-2.x and REQ-3.2/3.3/3.5/3.6."""

from noc_triage_agent.rules import (
    build_summary,
    find_breaches,
    is_priority_justified,
    suggested_priority,
    ticket_id_for,
)


def test_find_breaches_uses_strict_thresholds():
    exactly_at_threshold = {
        "drop_call_rate_pct": 2.0,
        "prb_utilization_pct": 85.0,
        "availability_pct": 99.0,
        "avg_throughput_mbps": 5.0,
    }
    assert find_breaches(exactly_at_threshold) == []

    breaching = {
        "drop_call_rate_pct": 3.4,
        "prb_utilization_pct": 93.0,
        "availability_pct": 97.5,
        "avg_throughput_mbps": 4.1,
    }
    breaches = find_breaches(breaching)
    assert [b.kpi for b in breaches] == [
        "drop_call_rate_pct",
        "prb_utilization_pct",
        "availability_pct",
        "avg_throughput_mbps",
    ]
    assert breaches[0].rule == "drop_call_rate_pct > 2.0"
    assert breaches[-1].rule == "avg_throughput_mbps < 5.0"


def test_suggested_priority_follows_rule_matrix():
    assert suggested_priority({"availability_pct": 94.9}) == "P1"
    assert suggested_priority({"availability_pct": 97.5, "drop_call_rate_pct": 3.4}) == "P2"
    assert suggested_priority({"availability_pct": 99.95}) == "NONE"
    assert suggested_priority({"availability_pct": 99.0, "avg_throughput_mbps": 3.1}) == "P2"


def test_is_priority_justified_for_p1_p2_p3_and_invalid():
    assert is_priority_justified("P1", {"availability_pct": 94.9}) is True
    assert is_priority_justified("P1", {"availability_pct": 95.0}) is False
    assert is_priority_justified("P2", {"drop_call_rate_pct": 2.5}) is True
    assert is_priority_justified("P2", {"availability_pct": 99.95}) is False
    assert is_priority_justified("P3", {"availability_pct": 99.95}) is True
    assert is_priority_justified("P9", {"availability_pct": 94.9}) is False


def test_ticket_id_and_summary_generation():
    assert ticket_id_for("CELL-1002") == "TCK-1002"

    breaches = find_breaches({
        "drop_call_rate_pct": 3.4,
        "prb_utilization_pct": 86.1,
        "avg_throughput_mbps": 4.8,
    })
    summary = build_summary("CELL-1002", breaches)
    assert len(summary) <= 200
    assert "CELL-1002" in summary
    assert "drop_call_rate_pct" in summary
    assert "3.4" in summary
    assert "2.0" in summary


def test_summary_handles_no_breach_packet_for_p3():
    assert build_summary("CELL-1006", []) == (
        "Informational check requested for CELL-1006; all KPIs within thresholds."
    )
