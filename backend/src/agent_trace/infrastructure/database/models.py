from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class RunModel(Base):
    """SQLAlchemy ORM model for AgentRun."""

    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    trace_nodes: Mapped[list[TraceNodeModel]] = relationship(
        "TraceNodeModel", back_populates="run", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"RunModel(id={self.id!r}, name={self.name!r}, status={self.status!r})"


class TraceNodeModel(Base):
    """SQLAlchemy ORM model for TraceNode."""

    __tablename__ = "trace_nodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("runs.id"), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("trace_nodes.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    span_type: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    attributes_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # Relationships
    run: Mapped[RunModel] = relationship("RunModel", back_populates="trace_nodes")
    parent: Mapped[TraceNodeModel | None] = relationship(
        "TraceNodeModel", remote_side=[id], backref="children"
    )
    span_events: Mapped[list[SpanEventModel]] = relationship(
        "SpanEventModel", back_populates="node", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_trace_nodes_run_id", "run_id"),
        Index("idx_trace_nodes_parent_id", "parent_id"),
    )

    def __repr__(self) -> str:
        return f"TraceNodeModel(id={self.id!r}, name={self.name!r}, type={self.span_type!r})"


class SpanEventModel(Base):
    """SQLAlchemy ORM model for SpanEvent."""

    __tablename__ = "span_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    node_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("trace_nodes.id"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # Relationships
    node: Mapped[TraceNodeModel] = relationship("TraceNodeModel", back_populates="span_events")

    __table_args__ = (
        Index("idx_span_events_node_id", "node_id"),
    )

    def __repr__(self) -> str:
        return f"SpanEventModel(id={self.id!r}, type={self.event_type!r})"