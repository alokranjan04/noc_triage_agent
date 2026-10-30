"""Smoke test for the deployed Agent Runtime (Reasoning Engine).

Sends "Triage CELL-1002." to the deployed agent and checks that the response
mentions TCK-1002 with priority P2.

Uses the ADK Agent Engine REST API:
  1. Create a session (async_create_session)
  2. Stream-query the agent (async_stream_query)

Usage:
    uv run python deploy/smoke_agent_runtime.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESOURCE_NAME = (PROJECT_ROOT / "deploy" / "agent_runtime.txt").read_text().strip()
REGION = "us-central1"


def get_access_token() -> str:
    """Get access token from gcloud CLI."""
    gcloud_cmd = "gcloud.cmd" if sys.platform == "win32" else "gcloud"
    return subprocess.check_output(
        [gcloud_cmd, "auth", "print-access-token"],
        text=True,
    ).strip()


def _api_call(token: str, endpoint: str, payload: dict) -> str:
    """Make an API call and return the raw response text."""
    import urllib.request

    url = f"https://{REGION}-aiplatform.googleapis.com/v1/{RESOURCE_NAME}:{endpoint}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read().decode()


def create_session(token: str, user_id: str) -> str:
    """Create a session and return its ID."""
    raw = _api_call(token, "query", {
        "class_method": "async_create_session",
        "input": {"user_id": user_id},
    })
    result = json.loads(raw)
    return result["output"]["id"]


def stream_query(token: str, user_id: str, session_id: str, message: str) -> str:
    """Stream-query the agent and return the full response text."""
    raw = _api_call(token, "streamQuery", {
        "class_method": "async_stream_query",
        "input": {
            "user_id": user_id,
            "session_id": session_id,
            "message": message,
        },
    })
    return raw


def main() -> None:
    print(f"Agent Runtime: {RESOURCE_NAME}")
    print("Getting access token...")
    token = get_access_token()

    try:
        print("Creating session...")
        session_id = create_session(token, "smoke-user")
        print(f"Session: {session_id}")

        print("Sending: 'Triage CELL-1002.'")
        raw = stream_query(token, "smoke-user", session_id, "Triage CELL-1002.")

        # Extract the final text response from the NDJSON stream events.
        # Use splitlines() to handle both \n and \r\n.
        final_text = ""
        for line in raw.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                parts = event.get("content", {}).get("parts", [])
                for part in parts:
                    if "text" in part:
                        final_text += part["text"]
            except (json.JSONDecodeError, KeyError):
                continue

        print(f"\nFinal response:\n  {final_text!r}")

        # Build output for saving
        output_lines = [
            "Remote Smoke Test — Agent Runtime",
            "Date: 2026-10-30",
            f"Resource: {RESOURCE_NAME}",
            "Model: gemini-3.8-flash via Vertex AI (global endpoint)",
            "",
            'Prompt: "Triage CELL-1002."',
            "",
            "Final response:",
            f"  {final_text!r}",
            "",
        ]

        # Check for expected content
        output_lower = (final_text + raw).lower()
        checks = {
            "TCK-1002": "tck-1002" in output_lower,
            "P2": "p2" in output_lower,
            "CELL-1002": "cell-1002" in output_lower,
        }

        output_lines.append("Checks:")
        all_passed = True
        for label, passed in checks.items():
            status = "PASS" if passed else "FAIL"
            output_lines.append(f"  {label}: {status}")
            print(f"  {label}: {status}")
            if not passed:
                all_passed = False

        output_lines.append("")
        output_lines.append(f"Result: SMOKE TEST {'PASSED' if all_passed else 'FAILED'}")

        # Save output
        output_path = PROJECT_ROOT / "docs" / "remote_smoke.txt"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(output_lines) + "\n", encoding="utf-8")
        print(f"\nSaved to {output_path}")

        if all_passed:
            print("\nSmoke test PASSED.")
        else:
            print("\nSmoke test FAILED — see response above.")
            sys.exit(1)

    except (OSError, ValueError, KeyError) as exc:
        error_msg = f"Agent Runtime query failed: {exc}"
        print(f"\n{error_msg}")

        output_path = PROJECT_ROOT / "docs" / "remote_smoke.txt"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(error_msg, encoding="utf-8")
        print(f"Saved to {output_path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
