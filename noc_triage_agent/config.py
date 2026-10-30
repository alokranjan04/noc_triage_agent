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

    _or_model = os.getenv("OPENROUTER_MODEL", "openrouter/google/gemini-2.5-flash")
    MODEL = LiteLlm(model=_or_model)
    logger.info("Using OpenRouter model %s via LiteLlm", _or_model)
else:
    _MODEL_NAME = os.getenv("NOC_AGENT_MODEL", "gemini-2.5-flash")
    MODEL = _MODEL_NAME
    logger.warning(
        "OPEN_ROUTER_KEY not set; falling back to Google GenAI model %s. "
        "Set OPEN_ROUTER_KEY for cheaper inference via OpenRouter.",
        MODEL,
    )
