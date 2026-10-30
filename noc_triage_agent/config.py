"""Application configuration loaded from environment variables."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

MODEL = os.getenv("NOC_AGENT_MODEL", "gemini-3.8-flash")
GOOGLE_GENAI_USE_VERTEXAI = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

if not GOOGLE_CLOUD_PROJECT:
    logger.warning(
        "GOOGLE_CLOUD_PROJECT is not set; some deployment features may fail until a project is configured."
    )
