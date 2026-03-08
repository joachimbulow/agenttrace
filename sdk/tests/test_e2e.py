"""End-to-End tests for SDK format validation.

These tests verify that the SDK produces events in the correct format
for the Backend API. They don't require a running backend - they test
the format conversion logic.
"""
import pytest

from agent_trace_sdk.domain.interfaces import ExportEvent, ExportBatch


class TestSDKFormatValidation:
    """Tests that verify SDK produces Backend-compatible format."""
    
    def test_export_event_span_start_format(self):
        """Test that span_start event has correct format."""
        event = ExportEvent(
            event_type="span_start",
            span_id="test-span-1",
            timestamp="2024-01-01T00:00:00Z",
            data={
                "parent_id": None,
                "name": "Test Span",
                "span_type": "step",
                "attributes": {"key": "value"},
            },
        )
        
        result = event.to_dict()
        
        # Backend expects 'type', not 'event_type'
        assert "type" in result, "SDK must use 'type' not 'event_type'"
        assert result["type"] == "span_start"
        
        # Backend expects nested 'data' with span_id and timestamp
        assert "data" in result, "SDK must nest fields in 'data'"
        assert "span_id" in result["data"], "span_id must be in data"
        assert "timestamp" in result["data"], "timestamp must be in data"
        assert "name" in result["data"]
        assert "span_type" in result["data"]
        
        # Should NOT have 'event_type' at top level
        assert "event_type" not in result, "SDK should not use 'event_type' at top level"
    
    def test_export_event_span_end_format(self):
        """Test that span_end event has correct format."""
        event = ExportEvent(
            event_type="span_end",
            span_id="test-span-1",
            timestamp="2024-01-01T00:00:05Z",
            data={
                "attributes": {"result": "success"},
            },
        )
        
        result = event.to_dict()
        
        assert result["type"] == "span_end"
        assert "span_id" in result["data"]
        assert "timestamp" in result["data"]
        assert "attributes" in result["data"]
    
    def test_export_event_span_event_format(self):
        """Test that span_event (custom event) has correct format."""
        event = ExportEvent(
            event_type="span_event",
            span_id="test-span-1",
            timestamp="2024-01-01T00:00:02Z",
            data={
                "event_type": "input",
                "payload": {"query": "hello"},
            },
        )
        
        result = event.to_dict()
        
        assert result["type"] == "span_event"
        assert "span_id" in result["data"]
        assert "timestamp" in result["data"]
        # Note: event_type in data is for the span event type (input/output/error)
        # This is different from the top-level 'type' field
    
    def test_export_batch_format(self):
        """Test that ExportBatch produces Backend IngestRequest-compatible format."""
        events = [
            ExportEvent(
                event_type="span_start",
                span_id="span-1",
                timestamp="2024-01-01T00:00:00Z",
                data={"name": "Test", "span_type": "step"},
            ),
            ExportEvent(
                event_type="span_end",
                span_id="span-1",
                timestamp="2024-01-01T00:00:05Z",
                data={},
            ),
        ]
        
        batch = ExportBatch(
            run_id="test-run-1",
            events=events,
            run_name="Test Run",
        )
        
        result = batch.to_dict()
        
        # Backend IngestRequest format
        assert "run_id" in result
        assert result["run_id"] == "test-run-1"
        
        assert "run_name" in result, "SDK should include run_name"
        assert result["run_name"] == "Test Run"
        
        assert "events" in result
        assert len(result["events"]) == 2
        
        # Each event must have 'type' and 'data'
        for event in result["events"]:
            assert "type" in event, "Each event must have 'type' field"
            assert "data" in event, "Each event must have 'data' field"
            assert "span_id" in event["data"], "span_id must be in data"
            assert "timestamp" in event["data"], "timestamp must be in data"
    
    def test_export_batch_without_run_name(self):
        """Test that run_name is optional."""
        events = [
            ExportEvent(
                event_type="span_start",
                span_id="span-1",
                timestamp="2024-01-01T00:00:00Z",
                data={"name": "Test", "span_type": "step"},
            ),
        ]
        
        batch = ExportBatch(
            run_id="test-run-2",
            events=events,
            # run_name is optional
        )
        
        result = batch.to_dict()
        
        assert "run_id" in result
        assert "events" in result
        # run_name should not be in result if not provided
        assert "run_name" not in result or result.get("run_name") is None
    
    def test_event_data_preserves_all_fields(self):
        """Test that all fields from data are preserved in output."""
        event = ExportEvent(
            event_type="span_start",
            span_id="span-1",
            timestamp="2024-01-01T00:00:00Z",
            data={
                "parent_id": "parent-1",
                "name": "MySpan",
                "span_type": "agent_run",
                "attributes": {"model": "gpt-4", "temperature": 0.7},
                "extra_field": "should_be_preserved",
            },
        )
        
        result = event.to_dict()
        
        # All original data fields should be in data
        assert result["data"]["parent_id"] == "parent-1"
        assert result["data"]["name"] == "MySpan"
        assert result["data"]["span_type"] == "agent_run"
        assert result["data"]["attributes"]["model"] == "gpt-4"
        assert result["data"]["extra_field"] == "should_be_preserved"


class TestSDKEventCreation:
    """Tests for SDK event creation flow."""
    
    def test_export_event_is_frozen(self):
        """Test that ExportEvent is immutable (frozen dataclass)."""
        event = ExportEvent(
            event_type="span_start",
            span_id="span-1",
            timestamp="2024-01-01T00:00:00Z",
            data={"name": "Test"},
        )
        
        # Should not be able to modify
        with pytest.raises(AttributeError):
            event.event_type = "span_end"
    
    def test_export_batch_is_frozen(self):
        """Test that ExportBatch is immutable (frozen dataclass)."""
        events = [
            ExportEvent(
                event_type="span_start",
                span_id="span-1",
                timestamp="2024-01-01T00:00:00Z",
                data={"name": "Test"},
            ),
        ]
        
        batch = ExportBatch(
            run_id="test-run",
            events=events,
            run_name="Test",
        )
        
        # Should not be able to modify
        with pytest.raises(AttributeError):
            batch.run_id = "different-run"