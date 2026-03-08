from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any
import json

from .domain.interfaces import IEventExporter, ExportBatch, ExportError


class HTTPExporter(IEventExporter):
    """HTTP exporter that sends events to the Agent Trace backend.
    
    Uses httpx for async HTTP requests.
    """
    
    def __init__(
        self,
        endpoint: str = "http://localhost:8000/api/v1/ingest/events",
        timeout: float = 5.0,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize HTTP exporter.
        
        Args:
            endpoint: URL to send events to.
            timeout: Request timeout in seconds.
            headers: Additional headers to send.
        """
        self._endpoint = endpoint
        self._timeout = timeout
        self._headers = headers or {}
        self._client: Any = None  # httpx.AsyncClient, lazy loaded
    
    async def _get_client(self) -> Any:
        """Get or create HTTP client.
        
        Returns:
            Async HTTP client.
        """
        if self._client is None:
            try:
                import httpx
                self._client = httpx.AsyncClient(timeout=self._timeout)
            except ImportError:
                raise ImportError(
                    "httpx is required for HTTPExporter. "
                    "Install it with: pip install httpx"
                )
        return self._client
    
    async def export(self, batch: ExportBatch) -> bool:
        """Export a batch of events.
        
        Args:
            batch: The batch of events to export.
            
        Returns:
            True if export succeeded, False otherwise.
            
        Raises:
            ExportError: If export fails.
        """
        client = await self._get_client()
        
        try:
            response = await client.post(
                self._endpoint,
                json=batch.to_dict(),
                headers={
                    "Content-Type": "application/json",
                    **self._headers,
                },
            )
            response.raise_for_status()
            return True
        except Exception as e:
            # Handle httpx errors gracefully
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                error_msg = f"HTTP error: {e.response.status_code}"
            raise ExportError(f"Export failed: {error_msg}") from e
    
    async def flush(self) -> None:
        """Flush any pending events.
        
        For HTTP exporter, this is a no-op since events are sent immediately.
        """
        pass
    
    async def close(self) -> None:
        """Close the exporter and release resources.
        
        Closes the HTTP client.
        """
        if self._client:
            await self._client.aclose()
            self._client = None


class ConsoleExporter(IEventExporter):
    """Console exporter for debugging.
    
    Prints events to stdout instead of sending them over HTTP.
    """
    
    def __init__(self, output_format: str = "json") -> None:
        """Initialize console exporter.
        
        Args:
            output_format: Output format ('json' or 'pretty').
        """
        self._output_format = output_format
    
    async def export(self, batch: ExportBatch) -> bool:
        """Export a batch of events to console.
        
        Args:
            batch: The batch of events to export.
            
        Returns:
            Always returns True.
        """
        if self._output_format == "json":
            print(json.dumps(batch.to_dict(), indent=2))
        else:
            print(f"Run ID: {batch.run_id}")
            for event in batch.events:
                print(f"  {event.event_type}: {event.span_id} - {event.timestamp}")
        
        return True
    
    async def flush(self) -> None:
        """Flush - no-op for console."""
        pass
    
    async def close(self) -> None:
        """Close - no-op for console."""
        pass