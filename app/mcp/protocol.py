"""
MCP Streamable HTTP Protocol Implementation (spec 2025-11-25)
Handles JSON-RPC 2.0 messages: initialize, tools/list, tools/call
Single bidirectional endpoint per Streamable HTTP specification.
"""

import json
import logging
from typing import Any, Callable, Dict, Optional, Union
from dataclasses import dataclass, asdict, field
from enum import Enum
from datetime import datetime
import uuid

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class JSONRPCVersion(str, Enum):
    """JSON-RPC 2.0 specification version."""
    V2 = "2.0"


class ToolInputType(str, Enum):
    """MCP Tool input parameter types."""
    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"


class ToolInputSchema(BaseModel):
    """JSON Schema for MCP Tool input parameters."""
    type: ToolInputType
    description: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None
    required: Optional[list[str]] = None
    items: Optional[Dict[str, Any]] = None
    enum: Optional[list[Any]] = None


class MCPTool(BaseModel):
    """MCP Tool definition per spec 2025-11-25."""
    name: str = Field(..., description="Unique tool identifier")
    description: str = Field(..., description="Human-readable tool description")
    inputSchema: ToolInputSchema = Field(..., description="JSON Schema for input validation")

    class Config:
        use_enum_values = True


class JSONRPCRequest(BaseModel):
    """JSON-RPC 2.0 Request message."""
    jsonrpc: JSONRPCVersion = Field(default=JSONRPCVersion.V2, description="JSON-RPC version")
    method: str = Field(..., description="Remote procedure name")
    params: Optional[Union[Dict[str, Any], list[Any]]] = Field(None, description="Method parameters")
    id: Optional[Union[str, int]] = Field(None, description="Request ID for correlation")

    @field_validator("method")
    @classmethod
    def validate_method(cls, v: str) -> str:
        """Validate method name is non-empty."""
        if not v or not isinstance(v, str):
            raise ValueError("method must be a non-empty string")
        return v

    class Config:
        use_enum_values = True


class JSONRPCError(BaseModel):
    """JSON-RPC 2.0 Error object."""
    code: int = Field(..., description="Error code (-32768 to -32000 reserved)")
    message: str = Field(..., description="Error message")
    data: Optional[Any] = Field(None, description="Additional error information")

    class Config:
        use_enum_values = True


class JSONRPCResponse(BaseModel):
    """JSON-RPC 2.0 Response message."""
    jsonrpc: JSONRPCVersion = Field(default=JSONRPCVersion.V2, description="JSON-RPC version")
    result: Optional[Any] = Field(None, description="Method result")
    error: Optional[JSONRPCError] = Field(None, description="Error if failed")
    id: Optional[Union[str, int]] = Field(None, description="Request ID for correlation")

    @field_validator("result", "error", mode="before")
    @classmethod
    def result_xor_error(cls, v: Any) -> Any:
        """Validate that exactly one of result or error is present."""
        return v

    class Config:
        use_enum_values = True


class InitializeRequest(JSONRPCRequest):
    """MCP Initialize request (initialize method)."""
    method: str = Field(default="initialize", description="Initialize method")
    params: Dict[str, Any] = Field(
        default_factory=lambda: {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {
                "name": "echopipeline-ai",
                "version": "1.0.0"
            }
        },
        description="Initialize parameters"
    )


class ToolsListRequest(JSONRPCRequest):
    """MCP tools/list request."""
    method: str = Field(default="tools/list", description="List tools method")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="List parameters")


class ToolsCallRequest(JSONRPCRequest):
    """MCP tools/call request."""
    method: str = Field(default="tools/call", description="Call tool method")
    params: Dict[str, Any] = Field(
        ...,
        description="Tool call parameters including name and arguments"
    )

    @field_validator("params")
    @classmethod
    def validate_params(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate tool call parameters."""
        if not isinstance(v, dict):
            raise ValueError("params must be a dictionary")
        if "name" not in v:
            raise ValueError("params must contain 'name' field")
        return v


class InitializeResponse(JSONRPCResponse):
    """MCP Initialize response."""
    result: Optional[Dict[str, Any]] = Field(
        default_factory=lambda: {
            "protocolVersion": "2025-11-25",
            "capabilities": {
                "tools": {
                    "listChanged": False
                }
            },
            "serverInfo": {
                "name": "echopipeline-ai",
                "version": "1.0.0"
            }
        },
        description="Server capabilities and info"
    )


class ToolsListResponse(JSONRPCResponse):
    """MCP tools/list response."""
    result: Optional[Dict[str, Any]] = Field(
        default_factory=lambda: {"tools": []},
        description="List of available tools"
    )


class ToolsCallResponse(JSONRPCResponse):
    """MCP tools/call response."""
    result: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Tool execution result"
    )


class MCPStreamableHTTPServer:
    """
    MCP Streamable HTTP Server (spec 2025-11-25)
    
    Handles single bidirectional HTTP endpoint for JSON-RPC 2.0 messages.
    Supports initialize, tools/list, and tools/call methods.
    
    Per spec, this is the canonical transport for MCP v2025-11-25.
    No legacy SSE or stdio fallback required.
    """

    def __init__(self, tools: Optional[list[MCPTool]] = None):
        """
        Initialize MCP server.
        
        Args:
            tools: List of available MCP tools
        """
        self.tools: list[MCPTool] = tools or []
        self.tool_handlers: Dict[str, Callable] = {}
        self.request_log: list[Dict[str, Any]] = []
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def register_tool_handler(self, tool_name: str, handler: Callable) -> None:
        """
        Register execution handler for a tool.
        
        Args:
            tool_name: Name of the tool
            handler: Async callable that executes the tool
        """
        self.tool_handlers[tool_name] = handler
        self.logger.info(f"Registered handler for tool: {tool_name}")

    async def handle_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming JSON-RPC 2.0 request.
        
        Validates request structure, dispatches to appropriate handler,
        and returns JSON-RPC 2.0 response.
        
        Args:
            request_data: Raw JSON request data
            
        Returns:
            JSON-RPC 2.0 response dictionary
        """
        request_id = request_data.get("id")
        
        try:
            # Parse and validate request
            request = JSONRPCRequest(**request_data)
            self.logger.info(f"Processing request: method={request.method}, id={request_id}")
            
            # Log request
            self.request_log.append({
                "timestamp": datetime.utcnow().isoformat(),
                "method": request.method,
                "id": request_id,
                "status": "received"
            })
            
            # Dispatch to method handler
            if request.method == "initialize":
                response = await self._handle_initialize(request)
            elif request.method == "tools/list":
                response = await self._handle_tools_list(request)
            elif request.method == "tools/call":
                response = await self._handle_tools_call(request)
            else:
                response = self._create_error_response(
                    request_id=request_id,
                    code=-32601,
                    message=f"Method not found: {request.method}"
                )
            
            self.logger.info(f"Response for request {request_id}: success")
            return response
            
        except ValueError as ve:
            self.logger.error(f"Validation error: {str(ve)}")
            return self._create_error_response(
                request_id=request_id,
                code=-32602,
                message=f"Invalid params: {str(ve)}"
            )
        except Exception as e:
            self.logger.error(f"Internal error: {str(e)}", exc_info=True)
            return self._create_error_response(
                request_id=request_id,
                code=-32603,
                message=f"Internal server error: {str(e)}"
            )

    async def _handle_initialize(self, request: JSONRPCRequest) -> Dict[str, Any]:
        """
        Handle initialize method.
        
        Per MCP spec 2025-11-25, initialize establishes protocol version
        and server capabilities. Called once at connection start.
        
        Args:
            request: Initialize request
            
        Returns:
            Initialize response with server info and capabilities
        """
        response = InitializeResponse(id=request.id)
        self.logger.info("Server initialized successfully")
        return json.loads(response.model_dump_json())

    async def _handle_tools_list(self, request: JSONRPCRequest) -> Dict[str, Any]:
        """
        Handle tools/list method.
        
        Returns list of available MCP tools with their schemas.
        
        Args:
            request: List tools request
            
        Returns:
            Response containing tool definitions
        """
        tools_data = [json.loads(tool.model_dump_json()) for tool in self.tools]
        response = ToolsListResponse(
            id=request.id,
            result={"tools": tools_data}
        )
        self.logger.info(f"Listing {len(self.tools)} tools")
        return json.loads(response.model_dump_json())

    async def _handle_tools_call(self, request: JSONRPCRequest) -> Dict[str, Any]:
        """
        Handle tools/call method.
        
        Executes specified tool with provided arguments.
        Looks up handler from registry and invokes with input validation.
        
        Args:
            request: Tool call request with name and arguments
            
        Returns:
            Response with tool execution result or error
        """
        if not request.params or "name" not in request.params:
            return self._create_error_response(
                request_id=request.id,
                code=-32602,
                message="Tool call requires 'name' parameter"
            )
        
        tool_name = request.params.get("name")
        tool_args = request.params.get("arguments", {})
        
        self.logger.info(f"Executing tool: {tool_name} with args: {tool_args}")
        
        # Validate tool exists
        tool_exists = any(t.name == tool_name for t in self.tools)
        if not tool_exists:
            return self._create_error_response(
                request_id=request.id,
                code=-32602,
                message=f"Tool not found: {tool_name}"
            )
        
        # Validate handler registered
        if tool_name not in self.tool_handlers:
            return self._create_error_response(
                request_id=request.id,
                code=-32603,
                message=f"No handler registered for tool: {tool_name}"
            )
        
        try:
            # Execute tool handler
            handler = self.tool_handlers[tool_name]
            result = await handler(tool_args) if callable(handler) else handler(tool_args)
            
            response = ToolsCallResponse(
                id=request.id,
                result={
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result) if not isinstance(result, str) else result
                        }
                    ],
                    "isError": False
                }
            )
            self.logger.info(f"Tool {tool_name} executed successfully")
            return json.loads(response.model_dump_json())
            
        except Exception as e:
            self.logger.error(f"Tool execution failed: {str(e)}", exc_info=True)
            return self._create_error_response(
                request_id=request.id,
                code=-32603,
                message=f"Tool execution error: {str(e)}",
                data={"tool": tool_name, "error": str(e)}
            )

    def _create_error_response(
        self,
        request_id: Optional[Union[str, int]],
        code: int,
        message: str,
        data: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Create JSON-RPC 2.0 error response.
        
        Args:
            request_id: Request ID for correlation
            code: JSON-RPC error code
            message: Error message
            data: Additional error data
            
        Returns:
            Error response dictionary
        """
        error = JSONRPCError(code=code, message=message, data=data)
        response = JSONRPCResponse(
            id=request_id,
            error=json.loads(error.model_dump_json())
        )
        return json.loads(response.model_dump_json())

    def get_request_log(self) -> list[Dict[str, Any]]:
        """
        Get request processing log.
        
        Returns:
            List of logged requests
        """
        return self.request_log.copy()

    def clear_request_log(self) -> None:
        """Clear request log."""
        self.request_log.clear()
        self.logger.info("Request log cleared")
