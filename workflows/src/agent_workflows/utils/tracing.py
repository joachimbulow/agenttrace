"""Workflow tracing config. The LangChain bridge lives in agent_trace_sdk.langchain."""

from __future__ import annotations

import os

DEFAULT_INGEST_ENDPOINT = "http://localhost:8000/api/v1/ingest/events"


def ingest_endpoint() -> str:
    return os.environ.get("AGENTTRACE_ENDPOINT", DEFAULT_INGEST_ENDPOINT)
