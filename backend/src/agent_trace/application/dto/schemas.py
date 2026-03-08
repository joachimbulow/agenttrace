from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# === Enums ===


class SpanTypeSchema(str, Enum):
    """Schema enum for span type."""

    AGENT_RUN = "agent_run"
    STEP = "step"
    TOOL_CALL = "tool_call"
    LLM_CALL = "llm_call"


class RunStatusSchema(str, Enum):
    """Schema enum for run status."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# === Event Ingestion ===


class SpanStartEvent(BaseModel):
    """Event for span start."""

    model_config = ConfigDict(populate_by_name=True)

    span_id: str = Field(..., description="Unique span ID")
    parent_id: str | None = Field(None, description="Parent span ID")
    name: str = Field(..., description="Span name")
    span_type: SpanTypeSchema = Field(..., description="Type of span")
    timestamp: datetime = Field(..., description="Start timestamp")
    attributes: dict[str, Any] | None = Field(None, description="Span attributes")


class SpanEndEvent(BaseModel):
    """Event for span end."""

    model_config = ConfigDict(populate_by_name=True)

    span_id: str = Field(..., description="Unique span ID")
    timestamp: datetime = Field(..., description="End timestamp")
    attributes: dict[str, Any] | None = Field(None, description="Additional attributes")


class SpanEventPayload(BaseModel):
    """Event for arbitrary span event (input, output, error)."""

    model_config = ConfigDict(populate_by_name=True)

    span_id: str = Field(..., description="Unique span ID")
    event_type: str = Field(..., description="Event type (input, output, error)")
    timestamp: datetime = Field(..., description="Event timestamp")
    payload: dict[str, Any] | None = Field(None, description="Event payload")


class IngestEvent(BaseModel):
    """Union type for ingestion events."""

    # Discriminated union would be better, but keeping simple for now
    type: str = Field(..., description="Event type: span_start, span_end, span_event")
    data: dict[str, Any] = Field(..., description="Event data")


class IngestRequest(BaseModel):
    """Request body for POST /ingest/events."""

    model_config = ConfigDict(populate_by_name=True)

    run_id: str = Field(..., description="Unique run ID")
    run_name: str | None = Field(None, description="Run name (for new runs)")
    events: list[IngestEvent] = Field(
        default_factory=list, description="List of events to ingest"
    )


class IngestResponse(BaseModel):
    """Response for POST /ingest/events."""

    model_config = ConfigDict(populate_by_name=True)

    accepted: int = Field(..., description="Number of events accepted")
    run_id: str = Field(..., description="Run ID")


# === Run Management ===


class RunCreateRequest(BaseModel):
    """Request body for creating a new run."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., description="Run name")
    metadata: dict[str, Any] | None = Field(None, description="Run metadata")


class RunResponse(BaseModel):
    """Response for GET /runs/{id}."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Unique run ID")
    name: str = Field(..., description="Run name")
    status: RunStatusSchema = Field(..., description="Run status")
    started_at: datetime = Field(..., description="Start timestamp")
    ended_at: datetime | None = Field(None, description="End timestamp")
    duration_ms: float | None = Field(None, description="Duration in milliseconds")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Run metadata")
    node_count: int | None = Field(None, description="Number of trace nodes")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class RunListResponse(BaseModel):
    """Response for GET /runs."""

    model_config = ConfigDict(populate_by_name=True)

    runs: list[RunResponse] = Field(default_factory=list, description="List of runs")
    total: int = Field(..., description="Total count")
    limit: int = Field(..., description="Page size")
    offset: int = Field(..., description="Page offset")


# === Trace Tree ===


class SpanEventResponse(BaseModel):
    """Response for a span event."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Unique event ID")
    event_type: str = Field(..., description="Event type")
    timestamp: datetime = Field(..., description="Event timestamp")
    payload: dict[str, Any] = Field(default_factory=dict, description="Event payload")


class TraceNodeResponse(BaseModel):
    """Response for a single trace node."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Unique node ID")
    name: str = Field(..., description="Node name")
    span_type: SpanTypeSchema = Field(..., description="Type of span")
    started_at: datetime = Field(..., description="Start timestamp")
    ended_at: datetime | None = Field(None, description="End timestamp")
    duration_ms: float | None = Field(None, description="Duration in milliseconds")
    attributes: dict[str, Any] = Field(default_factory=dict, description="Node attributes")
    children: list[TraceNodeResponse] = Field(
        default_factory=list, description="Child nodes"
    )
    events: list[SpanEventResponse] = Field(
        default_factory=list, description="Events associated with this node"
    )


class TraceTreeResponse(BaseModel):
    """Response for GET /runs/{id}/tree."""

    model_config = ConfigDict(populate_by_name=True)

    run_id: str = Field(..., description="Run ID")
    root: TraceNodeResponse | None = Field(None, description="Root node of the tree")


# === Health ===


class HealthResponse(BaseModel):
    """Response for GET /health."""

    model_config = ConfigDict(populate_by_name=True)

    status: str = Field(..., description="Health status")
    version: str = Field(..., description="API version")
