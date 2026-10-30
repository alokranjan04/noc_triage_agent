"""Deterministic KPI rules for breach detection and priority selection."""

from __future__ import annotations

import re
from dataclasses import dataclass

THRESHOLDS = {
    "drop_call_rate_pct": {"op": ">", "limit": 2.0},
    "prb_utilization_pct": {"op": ">", "limit": 85.0},
    "availability_pct": {"op": "<", "limit": 99.0},
    "avg_throughput_mbps": {"op": "<", "limit": 5.0},
}
P1_AVAILABILITY_BELOW = 95.0
CELL_ID_PATTERN = r"^CELL-\d{4}$"


@dataclass(frozen=True)
class Breach:
    kpi: str
    value: float
    threshold: float
    rule: str


def find_breaches(kpis: dict[str, float]) -> list[Breach]:
    """Return all KPI breaches using strict threshold comparisons."""
    breaches: list[Breach] = []
    for kpi, config in THRESHOLDS.items():
        if kpi not in kpis:
            continue

        value = float(kpis[kpi])
        limit = float(config["limit"])
        op = config["op"]

        if op == ">" and value > limit:
            breaches.append(Breach(kpi=kpi, value=value, threshold=limit, rule=f"{kpi} > {limit}"))
        elif op == "<" and value < limit:
            breaches.append(Breach(kpi=kpi, value=value, threshold=limit, rule=f"{kpi} < {limit}"))
    return breaches


def suggested_priority(kpis: dict[str, float]) -> str:
    """Return the priority justified by the current KPI values."""
    if float(kpis.get("availability_pct", 100.0)) < P1_AVAILABILITY_BELOW:
        return "P1"
    if find_breaches(kpis):
        return "P2"
    return "NONE"


def is_priority_justified(priority: str, kpis: dict[str, float]) -> bool:
    """Check whether a requested priority is supported by the KPI values."""
    priority_name = str(priority).upper()
    if priority_name == "P1":
        return float(kpis.get("availability_pct", 100.0)) < P1_AVAILABILITY_BELOW
    if priority_name == "P2":
        return bool(find_breaches(kpis))
    return priority_name == "P3"


def ticket_id_for(cell_id: str) -> str:
    """Return the deterministic ticket id for a valid cell id."""
    if not re.fullmatch(CELL_ID_PATTERN, cell_id):
        raise ValueError(f"Cell id must match {CELL_ID_PATTERN}: {cell_id}")
    return f"TCK-{cell_id.split('-')[-1]}"


def build_summary(cell_id: str, breaches: list[Breach]) -> str:
    """Build the ticket summary from breached KPIs, capped to 200 chars."""
    if not breaches:
        return f"Informational check requested for {cell_id}; all KPIs within thresholds."

    text = "; ".join(f"{b.kpi} {b.value} vs threshold {b.threshold}" for b in breaches)
    summary = f"{cell_id} breaching: {text}"
    if len(summary) > 200:
        summary = summary[:197] + "..."
    return summary
