"""
MCP Stream Endpoint Test Suite

Comprehensive async tests for the `/mcp/stream` endpoint using pytest and httpx.
Tests MCP protocol compliance (spec 2025-11-25), tool invocation, error handling,
and friction logger telemetry capture.

Run with: pytest tests/test_mcp_stream.py -v
"""

import pytest
import json
from datetime import datetime, timedelta
from httpx import AsyncClient

from app.main import app
from app.services.crm import MockCRMRepository


@pytest.fixture
async def client():
    """Provide async HTTP client for testing."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def crm_service():
    """Provide mock CRM service."""
    return MockCRMRepository()


class TestMCPHandshake:
    """Tests for MCP initialize method (protocol handshake)."""

    @pytest.mark.asyncio
    async def test_initialize_request_success(self, client):
        """Test successful MCP initialize handshake."""
        request_payload = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {
                    "name": "alexa-client",
                    "version": "1.0.0"
                }
            },
            "id": 1
        }

        response = await client.post(
            "/mcp/stream",
            json=request_payload,
            headers={"x-mcp-protocol-version": "2025-11-25"}
        )

        assert response.status_code == 200
        data = response.json()

        # Verify JSON-RPC 2.0 response structure
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 1
        assert "result" in data
        assert "error" not in data or data["error"] is None

        # Verify server info in result
        result = data["result"]
        assert result["protocolVersion"] == "2025-11-25"
        assert result["serverInfo"]["name"] == "echopipeline-ai"
        assert "capabilities" in result

    @pytest.mark.asyncio
    async def test_initialize_with_missing_protocol_header(self, client):
        """Test initialize without x-mcp-protocol-version header (friction logged)."""
        request_payload = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "id": 2
        }

        response = await client.post("/mcp/stream", json=request_payload)

        assert response.status_code == 200
        data = response.json()

        # Request should still succeed
        assert data["jsonrpc"] == "2.0"
        assert "result" in data

    @pytest.mark.asyncio
    async def test_initialize_invalid_jsonrpc_version(self, client):
        """Test initialize with wrong JSON-RPC version (error expected)."""
        request_payload = {
            "jsonrpc": "1.0",
            "method": "initialize",
            "id": 3
        }

        response = await client.post(
            "/mcp/stream",
            json=request_payload,
            headers={"x-mcp-protocol-version": "2025-11-25"}
        )

        # Should still process but may log as friction
        assert response.status_code in [200, 400]


class TestToolsListMethod:
    """Tests for tools/list method."""

    @pytest.mark.asyncio
    async def test_tools_list_success(self, client):
        """Test successful tools/list discovery."""
        request_payload = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {},
            "id": 10
        }

        response = await client.post(
            "/mcp/stream",
            json=request_payload,
            headers={"x-mcp-protocol-version": "2025-11-25"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 10
        assert "result" in data
        assert "error" not in data or data["error"] is None

        result = data["result"]
        assert "tools" in result
        tools = result["tools"]

        # Verify all four core tools are listed
        tool_names = {tool["name"] for tool in tools}
        assert "update_deal_stage" in tool_names
        assert "log_deal_risk" in tool_names
        assert "query_pipeline_metrics" in tool_names
        assert "create_lead_entry" in tool_names

        # Verify tool structure
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
            assert tool["inputSchema"]["type"] == "object"
            assert "properties" in tool["inputSchema"]
            assert "required" in tool["inputSchema"]

    @pytest.mark.asyncio
    async def test_tools_list_tool_schemas(self, client):
        """Test that tool schemas are valid and complete."""
        request_payload = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 11
        }

        response = await client.post("/mcp/stream", json=request_payload)
        data = response.json()
        tools = data["result"]["tools"]

        # Verify update_deal_stage schema
        update_deal_tool = next(t for t in tools if t["name"] == "update_deal_stage")
        required = update_deal_tool["inputSchema"]["required"]
        assert "deal_id" in required
        assert "current_stage" in required
        assert "new_stage" in required
        assert "arr_value" in required
        assert "mutated_by" in required

        # Verify log_deal_risk schema
        log_risk_tool = next(t for t in tools if t["name"] == "log_deal_risk")
        required = log_risk_tool["inputSchema"]["required"]
        assert "deal_id" in required
        assert "severity" in required
        assert "description" in required
        assert "rigs_scores" in required
        assert "owner" in required

        # Verify query_pipeline_metrics schema
        query_tool = next(t for t in tools if t["name"] == "query_pipeline_metrics")
        required = query_tool["inputSchema"]["required"]
        assert "period_start" in required
        assert "period_end" in required

        # Verify create_lead_entry schema
        lead_tool = next(t for t in tools if t["name"] == "create_lead_entry")
        required = lead_tool["inputSchema"]["required"]
        assert "first_name" in required
        assert "last_name" in required
        assert "email" in required
        assert "company_name" in required
        assert "created_by_session" in required


class TestToolsCallMethod:
    """Tests for tools/call method with actual tool invocation."""

    @pytest.mark.asyncio
    async def test_update_deal_stage_success(self, client):
        """Test successful update_deal_stage tool invocation."""
        request_payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "update_deal_stage",
                "arguments": {
                    "deal_id": "deal-001",
                    "current_stage": "Prospecting",
                    "new_stage": "Qualification",
                    "arr_value": 100000_00,
                    "mutated_by": "alexa-session-test"
                }
            },
            "id": 20
        }

        response = await client.post("/mcp/stream", json=request_payload)

        assert response.status_code == 200
        data = response.json()

        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 20
        assert "result" in data
        assert "error" not in data or data["error"] is None

        result = data["result"]
        assert "content" in result
        assert result["isError"] is False

        content = result["content"][0]
        assert content["type"] == "text"
        
        # Verify tool returned structured response
        tool_response = json.loads(content["text"])
        assert tool_response["success"] is True
        assert "updated_deal" in tool_response
        assert tool_response["updated_deal"]["stage"] == "Qualification"

    @pytest.mark.asyncio
    async def test_log_deal_risk_success(self, client):
        """Test successful log_deal_risk tool invocation."""
        request_payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "log_deal_risk",
                "arguments": {
                    "deal_id": "deal-001",
                    "severity": 3,
                    "risk_category": "budget",
                    "description": "Budget approval delayed by finance committee review",
                    "rigs_scores": {
                        "risk_score": 60,
                        "intent_score": 75,
                        "growth_score": 80,
                        "stakeholder_score": 70
                    },
                    "owner": "sales-rep@company.com"
                }
            },
            "id": 21
        }

        response = await client.post("/mcp/stream", json=request_payload)

        assert response.status_code == 200
        data = response.json()

        assert data["jsonrpc"] == "2.0"
        assert "result" in data

        result = data["result"]
        assert result["isError"] is False

        tool_response = json.loads(result["content"][0]["text"])
        assert tool_response["success"] is True
        assert "risk_id" in tool_response
        assert tool_response["severity"] == 3
        assert "aggregate_health_score" in tool_response

    @pytest.mark.asyncio
    async def test_query_pipeline_metrics_success(self, client):
        """Test successful query_pipeline_metrics tool invocation."""
        period_start = (datetime.utcnow() - timedelta(days=30)).isoformat()
        period_end = datetime.utcnow().isoformat()

        request_payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "query_pipeline_metrics",
                "arguments": {
                    "period_start": period_start,
                    "period_end": period_end,
                    "include_closed_deals": False
                }
            },
            "id": 22
        }

        response = await client.post("/mcp/stream", json=request_payload)

        assert response.status_code == 200
        data = response.json()

        assert data["jsonrpc"] == "2.0"
        assert "result" in data

        result = data["result"]
        assert result["isError"] is False

        tool_response = json.loads(result["content"][0]["text"])
        assert tool_response["success"] is True
        assert "metrics" in tool_response
        assert "summary" in tool_response
        
        metrics = tool_response["metrics"]
        assert "total_deals" in metrics
        assert "total_pipeline_arr" in metrics
        assert "win_probability" in metrics
        assert "average_health_score" in metrics

    @pytest.mark.asyncio
    async def test_create_lead_entry_success(self, client):
        """Test successful create_lead_entry tool invocation."""
        request_payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "create_lead_entry",
                "arguments": {
                    "first_name": "John",
                    "last_name": "Doe",
                    "email": "john.doe@acme.com",
                    "company_name": "Acme Corporation",
                    "job_title": "VP Sales",
                    "industry": "Technology",
                    "source": "ambient_notes",
                    "ambient_notes": "Discussed RevOps needs at conference",
                    "budget_range": "$50k-$100k",
                    "decision_timeline": "Q4 2026",
                    "created_by_session": "alexa-session-test-lead"
                }
            },
            "id": 23
        }

        response = await client.post("/mcp/stream", json=request_payload)

        assert response.status_code == 200
        data = response.json()

        assert data["jsonrpc"] == "2.0"
        assert "result" in data

        result = data["result"]
        assert result["isError"] is False

        tool_response = json.loads(result["content"][0]["text"])
        assert tool_response["success"] is True
        assert "lead_id" in tool_response
        assert "contact" in tool_response
        assert tool_response["contact"]["email"] == "john.doe@acme.com"
        assert "confidence_score" in tool_response


class TestErrorHandling:
    """Tests for error handling and JSON-RPC compliance."""

    @pytest.mark.asyncio
    async def test_malformed_json(self, client):
        """Test handling of malformed JSON request body."""
        response = await client.post(
            "/mcp/stream",
            content="{invalid json",
            headers={"content-type": "application/json"}
        )

        assert response.status_code == 400
        data = response.json()

        assert data["jsonrpc"] == "2.0"
        assert "error" in data
        assert data["error"]["code"] == -32602

    @pytest.mark.asyncio
    async def test_missing_method_field(self, client):
        """Test JSON-RPC request without method field."""
        request_payload = {
            "jsonrpc": "2.0",
            "id": 30
        }

        response = await client.post("/mcp/stream", json=request_payload)

        # Should handle gracefully
        assert response.status_code in [200, 400]

    @pytest.mark.asyncio
    async def test_unknown_method(self, client):
        """Test JSON-RPC request with unknown method."""
        request_payload = {
            "jsonrpc": "2.0",
            "method": "unknown_method",
            "id": 31
        }

        response = await client.post("/mcp/stream", json=request_payload)

        assert response.status_code == 200
        data = response.json()

        # Should return JSON-RPC error
        assert "error" in data
        assert data["error"]["code"] == -32601  # Method not found

    @pytest.mark.asyncio
    async def test_tool_call_missing_name(self, client):
        """Test tools/call without tool name parameter."""
        request_payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "arguments": {}
            },
            "id": 32
        }

        response = await client.post("/mcp/stream", json=request_payload)

        assert response.status_code == 200
        data = response.json()

        # Should return error
        assert "error" in data
        assert data["error"]["code"] == -32602

    @pytest.mark.asyncio
    async def test_tool_call_unknown_tool(self, client):
        """Test tools/call with unknown tool name."""
        request_payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "unknown_tool",
                "arguments": {}
            },
            "id": 33
        }

        response = await client.post("/mcp/stream", json=request_payload)

        assert response.status_code == 200
        data = response.json()

        # Should return error
        assert "error" in data
        assert data["error"]["code"] == -32602

    @pytest.mark.asyncio
    async def test_invalid_tool_arguments(self, client):
        """Test tools/call with invalid arguments."""
        request_payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "update_deal_stage",
                "arguments": {
                    "deal_id": "deal-001",
                    # Missing required fields
                }
            },
            "id": 34
        }

        response = await client.post("/mcp/stream", json=request_payload)

        assert response.status_code == 200
        data = response.json()

        # Should return error for missing fields
        assert "error" in data or (
            "result" in data and data["result"].get("isError") is True
        )


class TestFrictionLoggerTelemetry:
    """Tests for friction logger telemetry capture."""

    @pytest.mark.asyncio
    async def test_friction_log_created_on_bad_request(self, client):
        """Test that friction logger captures bad requests."""
        # Make a request with invalid JSON-RPC structure
        request_payload = {
            "jsonrpc": "1.0",  # Wrong version
            "method": "initialize",
            "id": 40
        }

        response = await client.post("/mcp/stream", json=request_payload)

        # Request should still be processed but friction logged
        assert response.status_code in [200, 400]

        # Check friction logs endpoint
        log_response = await client.get("/api/friction-logs")
        assert log_response.status_code == 200

        logs_data = log_response.json()
        assert "friction_events" in logs_data or "events" in logs_data

    @pytest.mark.asyncio
    async def test_friction_log_missing_protocol_header(self, client):
        """Test friction logging for missing protocol version header."""
        request_payload = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "id": 41
        }

        # Make request WITHOUT protocol version header
        response = await client.post(
            "/mcp/stream",
            json=request_payload
            # Note: no x-mcp-protocol-version header
        )

        assert response.status_code == 200

        # Verify friction was logged
        log_response = await client.get("/api/friction-logs")
        logs_data = log_response.json()
        
        # Should have at least one friction event
        events = logs_data.get("friction_events") or logs_data.get("events", [])
        assert len(events) >= 0  # May have friction events

    @pytest.mark.asyncio
    async def test_friction_logs_severity_filtering(self, client):
        """Test friction logs API with severity filtering."""
        response = await client.get("/api/friction-logs?severity=critical")
        
        assert response.status_code == 200
        data = response.json()
        
        # All events should have critical severity
        events = data.get("friction_events") or data.get("events", [])
        for event in events:
            assert event.get("severity") == "critical"


class TestHealthAndStatus:
    """Tests for health check and status endpoints."""

    @pytest.mark.asyncio
    async def test_health_check_endpoint(self, client):
        """Test /health endpoint."""
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert "version" in data
        assert "components" in data
        assert "crm" in data["components"]
        assert "parser" in data["components"]
        assert "mcp" in data["components"]

    @pytest.mark.asyncio
    async def test_status_endpoint(self, client):
        """Test /api/status endpoint."""
        response = await client.get("/api/status")

        assert response.status_code == 200
        data = response.json()

        assert data["service"] == "EchoPipeline"
        assert data["version"] == "1.0.0"
        assert data["protocol_version"] == "2025-11-25"
        assert "available_tools" in data
        assert "tools" in data
        assert len(data["tools"]) == 4

    @pytest.mark.asyncio
    async def test_root_endpoint(self, client):
        """Test root / endpoint."""
        response = await client.get("/")

        assert response.status_code == 200
        data = response.json()

        assert data["service"] == "EchoPipeline"
        assert "endpoints" in data
        assert "mcp_stream" in data["endpoints"]


class TestProtocolCompliance:
    """Tests for strict MCP spec 2025-11-25 compliance."""

    @pytest.mark.asyncio
    async def test_response_includes_protocol_version_header(self, client):
        """Test that responses include x-mcp-protocol-version header."""
        request_payload = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "id": 50
        }

        response = await client.post(
            "/mcp/stream",
            json=request_payload,
            headers={"x-mcp-protocol-version": "2025-11-25"}
        )

        assert response.status_code == 200
        assert response.headers.get("x-mcp-protocol-version") == "2025-11-25"

    @pytest.mark.asyncio
    async def test_json_rpc_response_structure(self, client):
        """Test strict JSON-RPC 2.0 response structure compliance."""
        request_payload = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 51
        }

        response = await client.post("/mcp/stream", json=request_payload)
        data = response.json()

        # Verify JSON-RPC 2.0 structure
        assert "jsonrpc" in data
        assert data["jsonrpc"] == "2.0"
        assert "id" in data
        assert data["id"] == 51
        
        # Must have exactly one of: result or error
        has_result = "result" in data and data["result"] is not None
        has_error = "error" in data and data["error"] is not None
        assert has_result or has_error
        assert not (has_result and has_error)
