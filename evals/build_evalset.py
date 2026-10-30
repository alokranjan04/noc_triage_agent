"""Build evals/noc_triage.evalset.json from evals/cases.yaml.

Uses ADK's own Pydantic models so the schema always matches the installed version.

Usage:
    uv run python evals/build_evalset.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from google.adk.evaluation.eval_case import EvalCase, IntermediateData, Invocation
from google.adk.evaluation.eval_set import EvalSet
from google.genai import types as genai_types

REPO_ROOT = Path(__file__).resolve().parent.parent
CASES_PATH = REPO_ROOT / "evals" / "cases.yaml"
OUTPUT_PATH = REPO_ROOT / "evals" / "noc_triage.evalset.json"


def _known_tool_names() -> set[str]:
    """Return the set of tool function names registered on root_agent."""
    sys.path.insert(0, str(REPO_ROOT))
    from noc_triage_agent.agent import root_agent  # noqa: PLC0415

    names: set[str] = set()
    for tool in root_agent.tools:
        # ADK wraps plain functions; the underlying callable is at .func or the
        # tool itself is callable with a __name__ attribute.
        name = getattr(tool, "name", None) or getattr(
            getattr(tool, "func", tool), "__name__", None
        )
        if name:
            names.add(name)
    return names


def build_invocation(case: dict) -> Invocation:
    """Convert one cases.yaml entry to an ADK Invocation."""
    tool_uses = [
        genai_types.FunctionCall(name=t["name"], args=t.get("args", {}))
        for t in case.get("expected_tools", [])
    ]
    return Invocation(
        user_content=genai_types.Content(
            role="user",
            parts=[genai_types.Part(text=case["prompt"])],
        ),
        final_response=genai_types.Content(
            role="model",
            parts=[genai_types.Part(text=case["reference_response"])],
        ),
        intermediate_data=IntermediateData(tool_uses=tool_uses) if tool_uses else None,
    )


def validate(eval_set: EvalSet, known_tools: set[str]) -> None:
    """Raise ValueError if any structural invariant is violated."""
    cases = eval_set.eval_cases
    if len(cases) != 15:
        raise ValueError(f"Expected 15 cases, got {len(cases)}")

    ids = [c.eval_id for c in cases]
    if len(ids) != len(set(ids)):
        duplicates = [i for i in ids if ids.count(i) > 1]
        raise ValueError(f"Duplicate eval ids: {duplicates}")

    for case in cases:
        for inv in case.conversation or []:
            if inv.intermediate_data:
                for fc in inv.intermediate_data.tool_uses:
                    if fc.name not in known_tools:
                        raise ValueError(
                            f"Case {case.eval_id!r}: tool {fc.name!r} not found in"
                            f" root_agent.tools {sorted(known_tools)}"
                        )


def main() -> None:
    raw = yaml.safe_load(CASES_PATH.read_text(encoding="utf-8"))
    known_tools = _known_tool_names()
    print(f"Agent tools: {sorted(known_tools)}")

    eval_cases = [
        EvalCase(eval_id=case["id"], conversation=[build_invocation(case)])
        for case in raw["cases"]
    ]

    eval_set = EvalSet(
        eval_set_id=raw["eval_set_id"],
        name=raw.get("name"),
        eval_cases=eval_cases,
    )

    validate(eval_set, known_tools)
    print(f"Validation passed: {len(eval_cases)} cases, ids unique, all tools found.")

    # Serialise via Pydantic so field aliases and types are handled correctly.
    output = json.loads(eval_set.model_dump_json())
    OUTPUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Written to {OUTPUT_PATH}")

    # Reload and round-trip check.
    reloaded = EvalSet.model_validate_json(OUTPUT_PATH.read_text(encoding="utf-8"))
    assert reloaded.eval_set_id == eval_set.eval_set_id
    assert len(reloaded.eval_cases) == 15
    print("Round-trip load OK.")


if __name__ == "__main__":
    main()
