"""Application configuration loaded from environment variables.

LLM provider priority:
  1. OpenRouter (via LiteLlm) — recommended, cheapest, no GCP model access needed.
     Set OPEN_ROUTER_KEY in .env.
  2. Google Gemini API — set GOOGLE_API_KEY + GOOGLE_GENAI_USE_VERTEXAI=FALSE.
  3. Vertex AI — set GOOGLE_CLOUD_PROJECT + GOOGLE_GENAI_USE_VERTEXAI=TRUE.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

# OpenRouter is the primary LLM provider (cheapest, no GCP model access needed).
OPEN_ROUTER_KEY = os.getenv("OPEN_ROUTER_KEY", "")

# LiteLLM expects OPENROUTER_API_KEY in the environment.
if OPEN_ROUTER_KEY and not os.getenv("OPENROUTER_API_KEY"):
    os.environ["OPENROUTER_API_KEY"] = OPEN_ROUTER_KEY

MODEL: Any  # str for Gemini, LiteLlm instance for OpenRouter
if OPEN_ROUTER_KEY:
    from google.adk.models.lite_llm import LiteLlm

    _or_model = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")
    # LiteLLM requires the openrouter/ prefix for routing.
    if not _or_model.startswith("openrouter/"):
        _or_model = f"openrouter/{_or_model}"
    MODEL = LiteLlm(model=_or_model)
    logger.info("Using OpenRouter model %s via LiteLlm", _or_model)
else:
    from google.adk.models.google_llm import Gemini

    _MODEL_NAME = os.getenv("NOC_AGENT_MODEL", "gemini-3.8-flash")
    # Use the global endpoint because regional endpoints may not have model
    # access enabled for all projects.
    MODEL = Gemini(model=_MODEL_NAME, client_kwargs={"location": "global"})
    logger.warning(
        "OPEN_ROUTER_KEY not set; falling back to Vertex AI model %s (global). "
        "Set OPEN_ROUTER_KEY for cheaper inference via OpenRouter.",
        _MODEL_NAME,
    )
