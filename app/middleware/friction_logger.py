"""
Friction Logger Middleware

FastAPI middleware that inspects incoming requests for protocol compliance issues,
latency anomalies, and missing headers. Auto-persists telemetry to friction_logs.json
for Devpost judging criteria (10% bonus eligibility).

Captures:
- Missing MCP protocol version headers
- Spec mismatches (JSON-RPC version, method names)
- Latency spikes (>1s)
- Content-Type validation
- Request size anomalies
"""

import json
import logging
import time
from typing import Callable, Optional, Dict, Any
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class FrictionLogEntry:
    """Represents a single friction event for logging."""

    def __init__(
        self,
        timestamp: str,
        event_type: str,
        severity: str,
        description: str,
        request_path: str,
        request_method: str,
        protocol_version: Optional[str] = None,
        latency_ms: Optional[float] = None,
        missing_headers: Optional[list[str]] = None,
        spec_mismatches: Optional[list[str]] = None,
        content_type: Optional[str] = None,
        request_size_bytes: Optional[int] = None,
        response_status: Optional[int] = None,
        remediation: Optional[str] = None
    ):
        """Initialize friction log entry."""
        self.timestamp = timestamp
        self.event_type = event_type
        self.severity = severity
        self.description = description
        self.request_path = request_path
        self.request_method = request_method
        self.protocol_version = protocol_version
        self.latency_ms = latency_ms
        self.missing_headers = missing_headers or []
        self.spec_mismatches = spec_mismatches or []
        self.content_type = content_type
        self.request_size_bytes = request_size_bytes
        self.response_status = response_status
        self.remediation = remediation

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "severity": self.severity,
            "description": self.description,
            "request": {
                "path": self.request_path,
                "method": self.request_method,
                "protocol_version": self.protocol_version,
                "content_type": self.content_type,
                "size_bytes": self.request_size_bytes
            },
            "performance": {
                "latency_ms": self.latency_ms,
                "latency_spike": self.latency_ms > 1000 if self.latency_ms else False
            },
            "compliance": {
                "missing_headers": self.missing_headers,
                "spec_mismatches": self.spec_mismatches
            },
            "response": {
                "status": self.response_status
            },
            "remediation": self.remediation
        }


class FrictionLogger:
    """
    Centralized friction logging service.
    
    Maintains in-memory log buffer and persists to friction_logs.json.
    Devpost judging criteria compliance:
    - Captures protocol violations
    - Tracks performance anomalies
    - Identifies SDK friction points
    - Provides actionable remediation suggestions
    """

    def __init__(self, log_file_path: str = "friction_logs.json"):
        """
        Initialize friction logger.
        
        Args:
            log_file_path: Path to friction_logs.json output file
        """
        self.log_file_path = Path(log_file_path)
        self.logs: list[Dict[str, Any]] = []
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        self._load_existing_logs()
        self.logger.info(f"FrictionLogger initialized, outputting to {self.log_file_path}")

    def _load_existing_logs(self) -> None:
        """Load existing friction logs from file."""
        if self.log_file_path.exists():
            try:
                with open(self.log_file_path, 'r') as f:
                    data = json.load(f)
                    self.logs = data.get("friction_events", [])
                    self.logger.info(f"Loaded {len(self.logs)} existing friction logs")
            except Exception as e:
                self.logger.warning(f"Failed to load existing friction logs: {str(e)}")
                self.logs = []

    def log_friction_event(self, entry: FrictionLogEntry) -> None:
        """
        Log a friction event and persist to disk.
        
        Args:
            entry: FrictionLogEntry to record
        """
        self.logs.append(entry.to_dict())
        self._persist_logs()
        
        log_level = (
            logging.ERROR if entry.severity == "critical"
            else logging.WARNING if entry.severity == "warning"
            else logging.INFO
        )
        self.logger.log(
            log_level,
            f"Friction event: {entry.event_type} - {entry.description}"
        )

    def _persist_logs(self) -> None:
        """Persist friction logs to friction_logs.json."""
        try:
            output_data = {
                "friction_logs_version": "1.0",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total_events": len(self.logs),
                "event_severity_summary": {
                    "critical": sum(1 for log in self.logs if log.get("severity") == "critical"),
                    "warning": sum(1 for log in self.logs if log.get("severity") == "warning"),
                    "info": sum(1 for log in self.logs if log.get("severity") == "info")
                },
                "friction_events": self.logs
            }
            
            with open(self.log_file_path, 'w') as f:
                json.dump(output_data, f, indent=2)
            
            self.logger.debug(f"Persisted {len(self.logs)} friction logs")
        except Exception as e:
            self.logger.error(f"Failed to persist friction logs: {str(e)}")

    def get_all_logs(self) -> list[Dict[str, Any]]:
        """Get all friction logs."""
        return self.logs.copy()

    def get_logs_by_severity(self, severity: str) -> list[Dict[str, Any]]:
        """Get friction logs filtered by severity."""
        return [log for log in self.logs if log.get("severity") == severity]

    def get_critical_issues(self) -> list[Dict[str, Any]]:
        """Get all critical friction issues."""
        return self.get_logs_by_severity("critical")


_friction_logger: Optional[FrictionLogger] = None


def get_friction_logger() -> FrictionLogger:
    """Get global friction logger instance (singleton)."""
    global _friction_logger
    if _friction_logger is None:
        _friction_logger = FrictionLogger()
    return _friction_logger


class FrictionLoggerMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for capturing SDK/protocol friction.
    
    Inspects all requests for:
    - MCP protocol compliance (version headers, JSON-RPC structure)
    - Latency anomalies (spikes > 1 second)
    - Missing required headers
    - Content-Type validation
    - Request size anomalies
    
    Auto-persists violations to friction_logs.json for audit and improvement tracking.
    """

    def __init__(self, app: ASGIApp):
        """Initialize middleware."""
        super().__init__(app)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.friction_logger = get_friction_logger()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Intercept request/response and check for friction points.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler
            
        Returns:
            HTTP response with friction logging
        """
        request_start_time = time.time()
        
        request_path = request.url.path
        request_method = request.method
        content_type = request.headers.get("content-type", "unknown")
        
        request_body = await request.body()
        request_size_bytes = len(request_body)
        
        friction_events = []
        protocol_version = None
        missing_headers = []
        spec_mismatches = []

        if request_path == "/mcp/stream":
            protocol_version = request.headers.get("x-mcp-protocol-version")
            
            if not protocol_version:
                missing_headers.append("x-mcp-protocol-version")
                friction_events.append({
                    "type": "missing_protocol_header",
                    "severity": "warning",
                    "description": "MCP protocol version header missing",
                    "remediation": "Include 'x-mcp-protocol-version: 2025-11-25' header"
                })

        if request_path.startswith("/mcp") or request_path.startswith("/api"):
            if request_method in ["POST", "PUT", "PATCH"]:
                if content_type != "application/json":
                    friction_events.append({
                        "type": "invalid_content_type",
                        "severity": "warning",
                        "description": f"Expected application/json, got {content_type}",
                        "remediation": "Set Content-Type: application/json header"
                    })

        if request_path == "/mcp/stream" and request_method == "POST" and request_body:
            try:
                request_json = json.loads(request_body)
                
                jsonrpc_version = request_json.get("jsonrpc")
                if jsonrpc_version != "2.0":
                    spec_mismatches.append(f"Expected jsonrpc=2.0, got {jsonrpc_version}")
                
                if not request_json.get("method"):
                    spec_mismatches.append("Missing required 'method' field")
                
                valid_methods = ["initialize", "tools/list", "tools/call"]
                method = request_json.get("method")
                if method and method not in valid_methods:
                    spec_mismatches.append(f"Unknown method: {method}")
                
                if spec_mismatches:
                    friction_events.append({
                        "type": "json_rpc_mismatch",
                        "severity": "warning",
                        "description": "JSON-RPC structure mismatch",
                        "details": spec_mismatches
                    })
            except json.JSONDecodeError as e:
                friction_events.append({
                    "type": "malformed_json",
                    "severity": "warning",
                    "description": f"Invalid JSON in request body: {str(e)}",
                    "remediation": "Ensure request body is valid JSON"
                })

        if request_path.startswith("/mcp") and request_size_bytes > 1_000_000:
            friction_events.append({
                "type": "large_request",
                "severity": "info",
                "description": f"Large request: {request_size_bytes / 1000:.1f} KB",
                "remediation": "Consider chunking large inputs"
            })

        try:
            response = await call_next(request)
        except Exception as e:
            latency_ms = (time.time() - request_start_time) * 1000
            
            friction_entry = FrictionLogEntry(
                timestamp=datetime.now(timezone.utc).isoformat(),
                event_type="request_exception",
                severity="critical",
                description=f"Request handler exception: {str(e)}",
                request_path=request_path,
                request_method=request_method,
                protocol_version=protocol_version,
                latency_ms=latency_ms,
                missing_headers=missing_headers,
                spec_mismatches=spec_mismatches,
                content_type=content_type,
                request_size_bytes=request_size_bytes,
                remediation="Check server logs for detailed error"
            )
            
            self.friction_logger.log_friction_event(friction_entry)
            raise

        latency_ms = (time.time() - request_start_time) * 1000

        if latency_ms > 1000:
            friction_events.append({
                "type": "latency_spike",
                "severity": "warning" if latency_ms < 3000 else "critical",
                "description": f"High latency: {latency_ms:.1f}ms",
                "remediation": "Check backend service health and database performance"
            })

        for event in friction_events:
            friction_entry = FrictionLogEntry(
                timestamp=datetime.now(timezone.utc).isoformat(),
                event_type=event.get("type", "unknown"),
                severity=event.get("severity", "info"),
                description=event.get("description", ""),
                request_path=request_path,
                request_method=request_method,
                protocol_version=protocol_version,
                latency_ms=latency_ms,
                missing_headers=missing_headers if event.get("type") == "missing_protocol_header" else None,
                spec_mismatches=spec_mismatches if event.get("type") == "json_rpc_mismatch" else None,
                content_type=content_type,
                request_size_bytes=request_size_bytes,
                response_status=response.status_code,
                remediation=event.get("remediation")
            )
            
            self.friction_logger.log_friction_event(friction_entry)

        return response
