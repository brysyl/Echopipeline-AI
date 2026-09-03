"""
MCP Tool Declarations (JSON-RPC)

Defines the four core RevOps automation tools exposed to Alexa+ via the MCP protocol.
Each tool includes complete JSON Schema validation for inputs and output specifications.

Tools:
1. update_deal_stage: Mutate deal pipeline stage with ARR tracking
2. log_deal_risk: Flag deal risks with RIGS framework scoring
3. query_pipeline_metrics: Aggregate pipeline analytics and forecasting
4. create_lead_entry: Ingest ambient notes into structured lead records
"""

import logging
from typing import Dict, Any, Optional, List
from app.mcp.protocol import MCPTool, ToolInputSchema, ToolInputType

logger = logging.getLogger(__name__)


def create_update_deal_stage_tool() -> MCPTool:
    """
    Create update_deal_stage MCP tool definition.
    
    This tool enables Alexa+ to advance deals through pipeline stages,
    updating ARR, close dates, and transition notes. Validates stage transitions
    and ensures data consistency.
    
    Returns:
        MCPTool: Tool declaration with complete input schema
    """
    return MCPTool(
        name="update_deal_stage",
        description="Advance a deal through RevOps pipeline stages (Prospecting -> Procurement -> Closed-Won). Updates ARR, close date, and transition notes. Returns updated deal with new stage and timestamps.",
        inputSchema=ToolInputSchema(
            type=ToolInputType.OBJECT,
            properties={
                "deal_id": {
                    "type": "string",
                    "description": "Unique deal identifier (alphanumeric, max 50 chars)",
                    "pattern": "^[a-zA-Z0-9\\-_]{1,50}$"
                },
                "current_stage": {
                    "type": "string",
                    "description": "Deal's current pipeline stage",
                    "enum": [
                        "Prospecting",
                        "Qualification",
                        "Discovery",
                        "Proposal",
                        "Procurement",
                        "Negotiation",
                        "Closed-Won",
                        "Closed-Lost"
                    ]
                },
                "new_stage": {
                    "type": "string",
                    "description": "Target pipeline stage after mutation",
                    "enum": [
                        "Prospecting",
                        "Qualification",
                        "Discovery",
                        "Proposal",
                        "Procurement",
                        "Negotiation",
                        "Closed-Won",
                        "Closed-Lost"
                    ]
                },
                "arr_value": {
                    "type": "integer",
                    "description": "Annual Recurring Revenue in USD cents (0-1000000000)",
                    "minimum": 0,
                    "maximum": 1000000000
                },
                "close_date": {
                    "type": "string",
                    "description": "Expected close date (ISO 8601 format, future date required)",
                    "format": "date-time"
                },
                "notes": {
                    "type": "string",
                    "description": "Optional transition notes or context (max 1000 chars)",
                    "maxLength": 1000
                },
                "mutated_by": {
                    "type": "string",
                    "description": "Alexa+ session ID or user identifier (max 256 chars)",
                    "maxLength": 256
                }
            },
            required=["deal_id", "current_stage", "new_stage", "arr_value", "mutated_by"]
        )
    )


def create_log_deal_risk_tool() -> MCPTool:
    """
    Create log_deal_risk MCP tool definition.
    
    This tool enables Alexa+ to flag deal risks with severity levels (1-5),
    capture RIGS framework scoring (Risk, Intent, Growth, Stakeholder),
    and track mitigation strategies. Generates audit trail for deal health.
    
    Returns:
        MCPTool: Tool declaration with complete input schema
    """
    return MCPTool(
        name="log_deal_risk",
        description="Flag deal risks with severity (1-5), RIGS framework scoring, and mitigation plans. Generates risk audit trail and updates deal health indicators. Returns risk_id and aggregated health score.",
        inputSchema=ToolInputSchema(
            type=ToolInputType.OBJECT,
            properties={
                "deal_id": {
                    "type": "string",
                    "description": "Associated deal identifier",
                    "pattern": "^[a-zA-Z0-9\\-_]{1,50}$"
                },
                "severity": {
                    "type": "integer",
                    "description": "Risk severity level (1=Low, 2=Moderate, 3=Medium, 4=High, 5=Critical)",
                    "enum": [1, 2, 3, 4, 5]
                },
                "risk_category": {
                    "type": "string",
                    "description": "Type of risk (budget, timeline, competition, technical, stakeholder, etc.)",
                    "maxLength": 100
                },
                "description": {
                    "type": "string",
                    "description": "Detailed risk description (10-2000 chars)",
                    "minLength": 10,
                    "maxLength": 2000
                },
                "rigs_scores": {
                    "type": "object",
                    "description": "RIGS framework assessment (Risk, Intent, Growth, Stakeholder each 0-100)",
                    "properties": {
                        "risk_score": {
                            "type": "integer",
                            "description": "Risk mitigation confidence (0-100, higher is better)",
                            "minimum": 0,
                            "maximum": 100
                        },
                        "intent_score": {
                            "type": "integer",
                            "description": "Buyer intent clarity (0-100)",
                            "minimum": 0,
                            "maximum": 100
                        },
                        "growth_score": {
                            "type": "integer",
                            "description": "Growth potential and ARR uplift (0-100)",
                            "minimum": 0,
                            "maximum": 100
                        },
                        "stakeholder_score": {
                            "type": "integer",
                            "description": "Executive sponsorship and alignment (0-100)",
                            "minimum": 0,
                            "maximum": 100
                        }
                    },
                    "required": ["risk_score", "intent_score", "growth_score", "stakeholder_score"]
                },
                "mitigation_plan": {
                    "type": "string",
                    "description": "Mitigation strategy or action plan (max 1500 chars)",
                    "maxLength": 1500
                },
                "owner": {
                    "type": "string",
                    "description": "Risk owner email or identifier (max 256 chars)",
                    "maxLength": 256
                }
            },
            required=["deal_id", "severity", "risk_category", "description", "rigs_scores", "owner"]
        )
    )


def create_query_pipeline_metrics_tool() -> MCPTool:
    """
    Create query_pipeline_metrics MCP tool definition.
    
    This tool enables Alexa+ to query aggregated pipeline analytics including
    total ARR, deal counts by stage, win probability, health scores, and
    forecast confidence. Returns point-in-time snapshot of pipeline state.
    
    Returns:
        MCPTool: Tool declaration with complete input schema
    """
    return MCPTool(
        name="query_pipeline_metrics",
        description="Query aggregated pipeline analytics: total ARR, deal counts, win probability, health scores, and forecast confidence. Returns point-in-time pipeline snapshot with KPIs and stage breakdown.",
        inputSchema=ToolInputSchema(
            type=ToolInputType.OBJECT,
            properties={
                "period_start": {
                    "type": "string",
                    "description": "Start of reporting period (ISO 8601 format)",
                    "format": "date-time"
                },
                "period_end": {
                    "type": "string",
                    "description": "End of reporting period (ISO 8601 format)",
                    "format": "date-time"
                },
                "include_closed_deals": {
                    "type": "boolean",
                    "description": "Include closed deals in aggregation (default: false)",
                    "default": False
                },
                "filter_by_owner": {
                    "type": "string",
                    "description": "Optional filter: sales rep email or identifier",
                    "maxLength": 256
                },
                "min_arr_threshold": {
                    "type": "integer",
                    "description": "Optional minimum ARR filter in USD cents (default: 0)",
                    "minimum": 0,
                    "default": 0
                }
            },
            required=["period_start", "period_end"]
        )
    )


def create_lead_entry_tool() -> MCPTool:
    """
    Create create_lead_entry MCP tool definition.
    
    This tool enables Alexa+ to ingest ambient notes and voice transcriptions
    into structured lead records. Supports fuzzy extraction with confidence scoring
    and auto-population from LLM parsing.
    
    Returns:
        MCPTool: Tool declaration with complete input schema
    """
    return MCPTool(
        name="create_lead_entry",
        description="Ingest ambient notes and voice input into structured lead records. Auto-extracts contact info, company details, budget, timeline. Returns lead_id with confidence score and extracted metadata.",
        inputSchema=ToolInputSchema(
            type=ToolInputType.OBJECT,
            properties={
                "first_name": {
                    "type": "string",
                    "description": "Lead contact first name (1-100 chars)",
                    "minLength": 1,
                    "maxLength": 100
                },
                "last_name": {
                    "type": "string",
                    "description": "Lead contact last name (1-100 chars)",
                    "minLength": 1,
                    "maxLength": 100
                },
                "email": {
                    "type": "string",
                    "description": "Lead email address (valid email format)",
                    "format": "email"
                },
                "phone": {
                    "type": "string",
                    "description": "Lead phone number (E.164 format preferred, max 20 chars)",
                    "maxLength": 20
                },
                "company_name": {
                    "type": "string",
                    "description": "Lead's company name (1-256 chars)",
                    "minLength": 1,
                    "maxLength": 256
                },
                "company_size": {
                    "type": "string",
                    "description": "Company employee count range",
                    "enum": ["1-10", "11-50", "51-200", "201-500", "501-1000", "1000+"]
                },
                "industry": {
                    "type": "string",
                    "description": "Industry vertical (max 100 chars)",
                    "maxLength": 100
                },
                "job_title": {
                    "type": "string",
                    "description": "Lead's job title (max 150 chars)",
                    "maxLength": 150
                },
                "department": {
                    "type": "string",
                    "description": "Lead's department (max 100 chars)",
                    "maxLength": 100
                },
                "source": {
                    "type": "string",
                    "description": "Lead acquisition source channel",
                    "enum": ["inbound", "outbound", "referral", "partner", "event", "ambient_notes"]
                },
                "source_detail": {
                    "type": "string",
                    "description": "Additional source context (max 500 chars)",
                    "maxLength": 500
                },
                "ambient_notes": {
                    "type": "string",
                    "description": "Raw ambient notes or voice transcription (max 5000 chars)",
                    "maxLength": 5000
                },
                "interest_category": {
                    "type": "string",
                    "description": "Product/service interest area (max 200 chars)",
                    "maxLength": 200
                },
                "budget_range": {
                    "type": "string",
                    "description": "Estimated budget indicator",
                    "enum": ["<$10k", "$10k-$50k", "$50k-$100k", "$100k-$500k", ">$500k"]
                },
                "decision_timeline": {
                    "type": "string",
                    "description": "Expected purchase timeline (max 200 chars)",
                    "maxLength": 200
                },
                "additional_context": {
                    "type": "object",
                    "description": "Arbitrary key-value metadata from voice extraction",
                    "additionalProperties": True
                },
                "created_by_session": {
                    "type": "string",
                    "description": "Alexa+ session ID that generated this lead (max 256 chars)",
                    "maxLength": 256
                }
            },
            required=["first_name", "last_name", "email", "company_name", "created_by_session"]
        )
    )


def get_all_tools() -> List[MCPTool]:
    """
    Get complete list of all available MCP tools.
    
    Returns:
        List of all MCPTool definitions ready for registration with MCP server
    """
    return [
        create_update_deal_stage_tool(),
        create_log_deal_risk_tool(),
        create_query_pipeline_metrics_tool(),
        create_lead_entry_tool()
    ]


def get_tool_by_name(tool_name: str) -> Optional[MCPTool]:
    """
    Retrieve tool definition by name.
    
    Args:
        tool_name: Name of the tool to retrieve
        
    Returns:
        MCPTool if found, None otherwise
    """
    tools = get_all_tools()
    for tool in tools:
        if tool.name == tool_name:
            return tool
    return None
