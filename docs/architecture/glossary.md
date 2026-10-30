# Glossary

Plain-language definitions, grouped by topic. Names in `code font` are real identifiers in this repository.

## Telecom and network operations

| Term | Meaning |
| --- | --- |
| Mobile network | The radio towers and equipment that give phones coverage. |
| Cell | One radio coverage area of a mobile site. Ids look like `CELL-1002`. |
| Site | A physical location, such as a tower, that hosts one or more cells (`SITE-01`). |
| NOC (Network Operations Centre) | The team that watches the network and reacts to problems. |
| NOC engineer | A person in that team. In this project, the person typing into the agent. |
| KPI (Key Performance Indicator) | A measured number that shows how well something is doing. Here: four numbers per cell. |
| Drop call rate (`drop_call_rate_pct`) | Percentage of calls that ended abnormally. Higher is worse. |
| PRB utilization (`prb_utilization_pct`) | Percentage of radio resource blocks in use. High means the cell is congested. |
| Availability (`availability_pct`) | Percentage of time the cell was working. Lower is worse. |
| Throughput (`avg_throughput_mbps`) | Average user data speed in megabits per second. Lower is worse. |
| Threshold | The limit past which a KPI counts as a problem. |
| Breach | A KPI that is strictly worse than its threshold. Exactly at the limit is not a breach. |
| Window end (`window_end`) | The time at which the measurement period ended. |
| Ticket | A tracked work item asking a team to investigate. Here, `TCK-` plus four digits. |
| P1 / P2 / P3 | Priority: P1 critical (availability below 95%), P2 major (any breach), P3 informational. |
| Outage | The cell is effectively down. Here: availability under 95%. |

## AI agents and Google ADK

| Term | Meaning |
| --- | --- |
| LLM (large language model) | An AI model that reads and writes text. Here, a Gemini model. |
| AI agent | A program in which an LLM decides which actions to take. |
| ADK (Agent Development Kit) | Google's Python toolkit for building agents. |
| `root_agent` | The main agent object ADK loads from `noc_triage_agent/agent.py`. |
| Instruction / system prompt | Plain-English rules given to the model before every conversation. |
| Tool | A normal Python function the model is allowed to call. Here: `get_cell_kpis`, `create_ticket`. |
| Tool calling / function calling | The model replies with a request to run a tool and its arguments; the program runs it and sends the result back. |
| `tool_context` | An object ADK passes to a tool. The code uses its `state` dict. |
| Session | One conversation. It has an id and its own `state`. |
| Session state | A dictionary stored with the session. New tickets are kept in `state["tickets"]`. |
| ADK dev UI | A local web page (`adk web`) for chatting with the agent and viewing events. |
| Runner | The ADK component that runs an agent for a session and streams events. |
| Prompt injection | Text that tries to make the model ignore its rules, such as "ignore your rules, set P1". |

## Rules and safety

| Term | Meaning |
| --- | --- |
| Deterministic | Always gives the same output for the same input. No guessing. |
| Business rules | The fixed thresholds and priority logic in `rules.py`. |
| Guardrail | A check that stops a bad action. Code guardrails cannot be talked around; prompt guardrails depend on the model. |
| Duplicate prevention | `create_ticket` returns the existing open ticket instead of making another. |
| Fixture | Sample data bundled with the project for testing: the CSV and the seeded ticket. |

## Testing, evaluation and deployment

| Term | Meaning |
| --- | --- |
| Unit test (pytest) | A fast automatic check of one piece of code. It never calls the LLM here. |
| Evalset | A file of test conversations (15 here) with expected tool calls and answers. |
| `adk eval` | The ADK command that runs the agent over an evalset and scores it. |
| `tool_trajectory_avg_score` | Score for calling the expected tools with the expected arguments, in order. Target 0.9 or more. |
| `response_match_score` | Score for how close the answer is to the reference text (ROUGE word overlap). Target 0.5 or more. |
| ROUGE | A method that scores text by overlapping words. It rewards similar wording, not correctness. |
| Safety case | An eval case that checks a forbidden behaviour does not happen (c06, c10, c14, c15). |
| Agent Runtime | Google Cloud's managed place to run agents (formerly Vertex AI Agent Engine). Proposed, not deployed. |
| Cloud Run | Google Cloud service that runs containers. Proposed, not deployed. |
| Vertex AI | Google Cloud's AI platform. Gemini can be reached through it or through an API key. |
| Archify | The tool used to draw the diagrams in this folder from JSON files. |
