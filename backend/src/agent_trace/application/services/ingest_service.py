"""Ingest service for processing trace events.

This module provides the IngestService which handles ingestion of trace events
from the SDK, validates data, and persists to repositories.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from ...domain.entities import AgentRun, SpanEvent, TraceNode
from ...domain.value_objects import RunStatus, SpanType
from ..dto.schemas import IngestRequest, IngestResponse

if TYPE_CHECKING:
    from ...domain.interfaces.clock import IClock
    from ...domain.interfaces.repositories import (
        IRunRepository,
        ISpanEventRepository,
        ITraceNodeRepository,
    )

logger = logging.getLogger(__name__)


class IngestService:
    """Application service for event ingestion.

    Handles the ingestion of trace events from the SDK.
    """

    def __init__(
        self,
        run_repo: IRunRepository,
        node_repo: ITraceNodeRepository,
        event_repo: ISpanEventRepository,
        clock: IClock,
    ) -> None:
        """Initialize service with repositories and clock.

        Args:
            run_repo: Repository for runs.
            node_repo: Repository for trace nodes.
            event_repo: Repository for span events.
            clock: Clock for timestamps.
        """
        self._run_repo = run_repo
        self._node_repo = node_repo
        self._event_repo = event_repo
        self._clock = clock

    async def ingest_events(self, request: IngestRequest) -> IngestResponse:
        """Ingest a batch of events.

        Args:
            request: Ingest request with run_id and events.

        Returns:
            Ingest response with count of accepted events.
        """
        # Ensure run exists
        run = await self._run_repo.get(request.run_id)
        if not run:
            # Create new run
            run = AgentRun(
                id=request.run_id,
                name=request.run_name or f"run-{request.run_id[:8]}",
                status=RunStatus.RUNNING,
                started_at=self._clock.utcnow(),
                metadata={},
                created_at=self._clock.utcnow(),
                updated_at=self._clock.utcnow(),
            )
            await self._run_repo.save(run)

        # Process events
        accepted_count = 0

        for event in request.events:
            event_type = event.type
            data = event.data

            try:
                if event_type == "span_start":
                    await self._process_span_start(data, request.run_id)
                elif event_type == "span_end":
                    await self._process_span_end(data)
                elif event_type == "span_event":
                    await self._process_span_event(data)
                else:
                    logger.warning(f"Unknown event type: {event_type}")

                accepted_count += 1
            except Exception as e:
                logger.error(f"Failed to process event {event_type}: {e}")
                # Continue processing other events rather than failing the batch
                # This prevents one bad event from breaking the entire batch

        return IngestResponse(accepted=accepted_count, run_id=request.run_id)

    async def _process_span_start(self, data: dict, run_id: str) -> None:
        """Process span_start event.

        Args:
            data: Event data containing span_id, parent_id, name, span_type, etc.
            run_id: The run ID for this span.
        """
        span_id = data.get("span_id") or str(uuid.uuid4())
        parent_id = data.get("parent_id")
        name = data.get("name", "unknown")
        span_type_str = data.get("span_type", "step")
        timestamp_str = data.get("timestamp")
        attributes = data.get("attributes", {})

        # Parse timestamp or use current
        started_at = self._parse_timestamp_safe(timestamp_str)

        # Map span type
        span_type = self._map_span_type(span_type_str)

        node = TraceNode(
            id=span_id,
            run_id=run_id,
            parent_id=parent_id,
            name=name,
            span_type=span_type,
            started_at=started_at,
            ended_at=None,
            attributes=attributes,
        )

        await self._node_repo.save(node)

    async def _process_span_end(self, data: dict) -> None:
        """Process span_end event.

        Args:
            data: Event data containing span_id, timestamp, attributes.
        """
        span_id = data.get("span_id")
        timestamp_str = data.get("timestamp")
        attributes = data.get("attributes", {})

        if not span_id:
            logger.warning("span_end event missing span_id, skipping")
            return

        # Get existing node
        node = await self._node_repo.get(span_id)
        if not node:
            logger.warning(f"span_end received for unknown span_id: {span_id}, skipping")
            return

        # Parse timestamp or use current
        ended_at = self._parse_timestamp_safe(timestamp_str)

        # Update node
        updated_node = TraceNode(
            id=node.id,
            run_id=node.run_id,
            parent_id=node.parent_id,
            name=node.name,
            span_type=node.span_type,
            started_at=node.started_at,
            ended_at=ended_at,
            attributes={**node.attributes, **attributes},
        )

        await self._node_repo.save(updated_node)

    async def _process_span_event(self, data: dict) -> None:
        """Process span_event (input, output, error).

        Args:
            data: Event data containing span_id, event_type, timestamp, payload.
        """
        span_id = data.get("span_id")
        event_type = data.get("event_type", "unknown")
        timestamp_str = data.get("timestamp")
        payload = data.get("payload", {})

        if not span_id:
            logger.warning("span_event missing span_id, skipping")
            return

        # Parse timestamp or use current
        timestamp = self._parse_timestamp_safe(timestamp_str)

        event = SpanEvent(
            id=str(uuid.uuid4()),
            node_id=span_id,
            event_type=event_type,
            timestamp=timestamp,
            payload=payload,
        )

        await self._event_repo.save(event)

    def _parse_timestamp_safe(self, timestamp_str: str | None) -> datetime:
        """Parse ISO timestamp string to datetime with error handling.

        Args:
            timestamp_str: ISO format timestamp string, or None.

        Returns:
            Parsed datetime object, or current UTC time if parsing fails.
        """
        if not timestamp_str:
            return self._clock.utcnow()

        try:
            # Handle 'Z' suffix for UTC
            if timestamp_str.endswith("Z"):
                timestamp_str = timestamp_str[:-1] + "+00:00"
            return datetime.fromisoformat(timestamp_str)
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse timestamp '{timestamp_str}': {e}, using current time")
            return self._clock.utcnow()

    def _map_span_type(self, span_type_str: str) -> SpanType:
        """Map string to SpanType enum.

        Args:
            span_type_str: String representation of span type.

        Returns:
            Corresponding SpanType enum value.
        """
        type_map = {
            "agent_run": SpanType.AGENT_RUN,
            "step": SpanType.STEP,
            "tool_call": SpanType.TOOL_CALL,
            "llm_call": SpanType.LLM_CALL,
        }
        return type_map.get(span_type_str, SpanType.STEP)