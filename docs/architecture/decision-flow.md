# Decision Flow

> Evidence base: `noc_triage_agent/rules.py` and `tools.py`, both identical to commit `f2c089c`. Diagrams: [KPI and priority](diagrams/decision-kpi-priority.html), [ticket guards](diagrams/decision-ticket-guards.html).

The "decision engine" is not a separate service. It is the module `rules.py` plus the guard sequence in `create_ticket`. Both are plain Python and never call the model.

## 1. KPI thresholds (rules.py lines 8-15)

| KPI (field name) | Plain meaning | Breach when | Limit |
| --- | --- | --- | --- |
| `drop_call_rate_pct` | Share of calls that ended abnormally | value **>** limit | 2.0 |
| `prb_utilization_pct` | Share of radio resources in use (congestion) | value **>** limit | 85.0 |
| `availability_pct` | Share of time the cell was in service | value **<** limit | 99.0 |
| `avg_throughput_mbps` | Average user speed | value **<** limit | 5.0 |
| P1 trigger | Cell is effectively down | `availability_pct` **<** | 95.0 |

Comparisons are strict, so a value exactly at the limit is healthy. `CELL-1008` (2.0, 85.0, 99.0, 5.0) is the test fixture for that (eval c09). Breaches are returned in the fixed order above, not by severity.

## 2. Decision order

1. `find_breaches(kpis)` checks each KPI independently and returns `Breach(kpi, value, threshold, rule)` items.
2. `suggested_priority(kpis)` then applies, in this order:
   1. `availability_pct < 95.0` gives **P1**.
   2. Otherwise any breach gives **P2**.
   3. Otherwise **NONE**.
3. `is_priority_justified(priority, kpis)` re-checks a *requested* priority: P1 needs `availability_pct < 95.0`; P2 needs at least one breach; **P3 is always accepted**; anything else is rejected.

Worked examples from `cell_kpis.csv`:

| Cell | Values that matter | Breaches | Suggested |
| --- | --- | --- | --- |
| `CELL-1001` | availability 99.95, drop 0.8 | none | NONE |
| `CELL-1002` | drop 3.4 | 1 | P2 |
| `CELL-1003` | PRB 93.0, throughput 4.1 | 2 | P2 |
| `CELL-1004` | availability 82.0, drop 6.0, throughput 1.0 | 3 | P1 |
| `CELL-1005` | availability 97.5 | 1 | P2 (above 95, so not P1) |
| `CELL-1008` | all exactly at limits | none | NONE |

"Severity assessment" in the brief maps to `suggested_priority`. No other severity score exists.

## 3. Ticket guards in `create_ticket` (tools.py lines 69-133)

| Order | Guard | Code | Failure result |
| --- | --- | --- | --- |
| 1 | `cell_id` is a string matching `^CELL-\d{4}$` | line 74 | `error` / `INVALID_CELL_ID` |
| 2 | `priority` is exactly `P1`, `P2` or `P3` | line 81 | `error` / `INVALID_PRIORITY` |
| 3 | Cell exists in the CSV | line 88 | `error` / `CELL_NOT_FOUND` |
| 4 | No open ticket exists for the cell | line 101 | `exists` with the existing id; nothing is created |
| 5 | `is_priority_justified` | line 113 | `error` / `PRIORITY_NOT_JUSTIFIED` |
| then | `ticket_id_for`, `build_summary`, `store.add` | lines 122-131 | `created` |

Details that follow from the order:

* **Duplicate beats justification.** Guard 4 runs before guard 5, so asking for an unjustified P1 on `CELL-1007` returns `exists`, not an error (captured by running it).
* **Ticket id is derived, not chosen.** `TCK-` plus the four digits, so one cell can never have two ticket ids.
* **No free text.** The function takes only `cell_id` and `priority`; the summary is generated from KPI breaches and capped at 200 characters (`rules.py:72-81`).
* **P3 on a breaching cell is allowed.** `create_ticket("CELL-1004", "P3")` creates `TCK-1004` as P3 (captured). The prompt limits P3 to explicit informational requests; the code does not.

## 4. Safety rules and where they are enforced

| Mandatory rule | Enforced by code? | Where | Test or eval |
| --- | --- | --- | --- |
| No P1 without an availability breach | **Yes** | `rules.py:53-57`, `tools.py:113-120` | `test_create_ticket_rejects_p1_without_availability_breach`, `test_is_priority_justified_for_p1_p2_p3_and_invalid`, evals c10, c15 |
| No duplicate tickets | **Yes**, for an open ticket seen by `find_open` in fixtures or the session | `tools.py:100-103`, `repository.py:66-75` | `test_create_ticket_returns_existing_ticket_for_open_cell`, `test_ticket_store_reads_fixture_and_session_state`, eval c06 |
| No network changes or remediation | **Structurally yes**: the agent has only `get_cell_kpis` and `create_ticket`, neither of which touches a network. The *refusal wording* is prompt-driven | `agent.py:39` at the pinned commit (tools list); instruction lines 12-14 | Eval c14 only. No pytest covers it |
| Ticket only when justified | **Partly.** Code enforces that the *requested priority* is justified. Whether to call `create_ticket` at all is the model's decision, and P3 bypasses the breach check | `tools.py:113`, `rules.py:60-61` | Evals c01, c09, c10, c13 |
| User text cannot change priority or summary | **Yes**: no free-text parameter; summary built in code | `tools.py:69`, `rules.py:72-81` | `test_ticket_id_and_summary_generation`, eval c15 |

The model is told to copy `suggested_priority`, but the code does not trust it: it recomputes the justification itself. That is the main design idea of the project.

## 5. Duplicate prevention and state

* `TicketStore.find_open(cell_id)` first scans `open_tickets.json` (fixture, status `OPEN`), then the session's `state["tickets"]`.
* New tickets are written only to `state["tickets"]`, never to the fixture file.
* So duplicates are prevented **within one session** and against the seeded ticket. A different session cannot see tickets created in another session (`test_ticket_store_isolation_between_state_dicts`). The store is session state, not a database.

## 6. Implementation Gap / Proposed Enhancement

| # | Gap | Evidence | Proposed enhancement |
| --- | --- | --- | --- |
| 1 | `README.md` and the design sketch mention `rules.evaluate()`; it does not exist | `rules.py` defines `find_breaches`, `suggested_priority`, `is_priority_justified` | Fix the docs |
| 2 | P3 can be created for a breaching cell, and for a healthy cell by anyone who can call the tool | Captured run; `rules.py:60-61` | Decide whether P3 should require no breach, or document it as intended |
| 3 | A duplicate request reports the wrong `priority` for session-created tickets | `tools.py:103` | Read the priority from `state["tickets"]` too |
| 4 | Data-layer exceptions escape the tools; `INTERNAL_ERROR` is never returned | See [sequence gaps G1-G3](end-to-end-sequence.md#3-failure-branches-that-are-not-handled) | Wrap tool bodies, log, return `INTERNAL_ERROR` |
| 5 | The network-change refusal has no unit test | Only eval c14 | Add a test that the agent's tool list contains no write-capable tool |
| 6 | No logging of tool calls (spec section 8 asks for INFO logs) | No `logger` in `tools.py` | Log name, args and status |
| 7 | Spec asks tests to be named after REQ ids; current tests cite them in module docstrings only | `tests/*.py` headers | Rename or add REQ ids per test |
| 8 | Both tools build `CsvKpiRepository()` per call, re-reading the CSV each time | `tools.py:27, 88` | Cache at module level |

Nothing in this list was changed: the task was documentation only.


