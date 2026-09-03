"""
MCP Tool Execution Handlers

Async handlers that execute the four core RevOps automation tools against
the CRM service layer. Each handler validates inputs, applies business logic,
and returns structured results compatible with MCP response format.

Handlers integrate seamlessly with MCP protocol engine for Alexa+ execution.
"""

import logging
from typing import Any, Dict, Optional
from datetime import datetime
import json

from app.models.revops import (
    DealStageUpdate,
    DealRiskLog,
    RIGSScore,
    PipelineMetrics,
    LeadEntry,
    DealStage,
    RiskSeverity,
    LeadSource
)

logger = logging.getLogger(__name__)


class ToolHandlerException(Exception):
    """Base exception for tool handler errors."""
    pass


class UpdateDealStageHandler:
    """
    Handler for update_deal_stage MCP tool.
    
    Validates stage transition, updates deal record in CRM, and returns
    updated deal with new stage and timestamps for Alexa+ confirmation.
    """

    def __init__(self, crm_service):
        """
        Initialize handler with CRM service reference.
        
        Args:
            crm_service: CRM repository implementation (SupabaseCRMRepository or MockCRMRepository)
        """
        self.crm = crm_service
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def handle(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute update_deal_stage tool logic.
        
        Validates input parameters, constructs DealStageUpdate model,
        persists to CRM, and returns updated deal state.
        
        Args:
            arguments: Tool arguments containing deal_id, stage transition, ARR, etc.
            
        Returns:
            Dictionary with updated_deal, transition_timestamp, and confirmation details
            
        Raises:
            ToolHandlerException: On validation or CRM operation failure
        """
        try:
            # Parse and validate input
            update_request = DealStageUpdate(**arguments)
            self.logger.info(
                f"Handling deal stage update: {update_request.deal_id} "
                f"({update_request.current_stage} -> {update_request.new_stage})"
            )

            # Call CRM to update deal
            updated_deal = await self.crm.update_deal_stage(update_request)

            if not updated_deal:
                raise ToolHandlerException(
                    f"Failed to update deal {update_request.deal_id} in CRM"
                )

            # Format response
            response = {
                "success": True,
                "updated_deal": json.loads(updated_deal.model_dump_json()),
                "transition_timestamp": datetime.utcnow().isoformat(),
                "message": f"Deal {update_request.deal_id} advanced to {update_request.new_stage}",
                "new_arr_value": update_request.arr_value
            }

            self.logger.info(f"Deal stage update successful: {update_request.deal_id}")
            return response

        except ValueError as ve:
            self.logger.error(f"Validation error in update_deal_stage: {str(ve)}")
            raise ToolHandlerException(f"Invalid parameters: {str(ve)}")
        except Exception as e:
            self.logger.error(f"Error updating deal stage: {str(e)}", exc_info=True)
            raise ToolHandlerException(f"Failed to update deal stage: {str(e)}")


class LogDealRiskHandler:
    """
    Handler for log_deal_risk MCP tool.
    
    Captures deal risk events with severity levels, RIGS framework scoring,
    and mitigation strategies. Updates deal health indicators in CRM.
    """

    def __init__(self, crm_service):
        """
        Initialize handler with CRM service reference.
        
        Args:
            crm_service: CRM repository implementation
        """
        self.crm = crm_service
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def handle(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute log_deal_risk tool logic.
        
        Validates risk parameters, constructs DealRiskLog model,
        persists to CRM, and returns risk_id with updated deal health.
        
        Args:
            arguments: Tool arguments containing deal_id, severity, risk details, RIGS scores
            
        Returns:
            Dictionary with risk_id, aggregate_health_score, and confirmation
            
        Raises:
            ToolHandlerException: On validation or CRM operation failure
        """
        try:
            # Extract and parse RIGS scores
            rigs_data = arguments.get("rigs_scores", {})
            rigs_scores = RIGSScore(
                risk_score=rigs_data.get("risk_score", 50),
                intent_score=rigs_data.get("intent_score", 50),
                growth_score=rigs_data.get("growth_score", 50),
                stakeholder_score=rigs_data.get("stakeholder_score", 50)
            )

            # Parse and validate risk log
            risk_log = DealRiskLog(
                deal_id=arguments.get("deal_id"),
                severity=RiskSeverity(arguments.get("severity")),
                risk_category=arguments.get("risk_category"),
                description=arguments.get("description"),
                rigs_scores=rigs_scores,
                mitigation_plan=arguments.get("mitigation_plan"),
                owner=arguments.get("owner")
            )

            self.logger.info(
                f"Logging deal risk: deal={risk_log.deal_id}, "
                f"severity={risk_log.severity}, health={rigs_scores.aggregate_health}"
            )

            # Persist risk log to CRM
            created_risk = await self.crm.log_deal_risk(risk_log)

            if not created_risk:
                raise ToolHandlerException(
                    f"Failed to log risk for deal {risk_log.deal_id}"
                )

            # Query updated deal health
            deal_health = await self.crm.get_deal_health_score(risk_log.deal_id)

            response = {
                "success": True,
                "risk_id": created_risk.risk_id,
                "deal_id": risk_log.deal_id,
                "severity": risk_log.severity.value,
                "rigs_scores": json.loads(rigs_scores.model_dump_json()),
                "aggregate_health_score": rigs_scores.aggregate_health,
                "deal_health_after_risk": deal_health,
                "created_at": created_risk.created_at.isoformat(),
                "message": f"Risk logged with ID {created_risk.risk_id}"
            }

            self.logger.info(f"Risk logged successfully: {created_risk.risk_id}")
            return response

        except ValueError as ve:
            self.logger.error(f"Validation error in log_deal_risk: {str(ve)}")
            raise ToolHandlerException(f"Invalid parameters: {str(ve)}")
        except Exception as e:
            self.logger.error(f"Error logging deal risk: {str(e)}", exc_info=True)
            raise ToolHandlerException(f"Failed to log deal risk: {str(e)}")


class QueryPipelineMetricsHandler:
    """
    Handler for query_pipeline_metrics MCP tool.
    
    Aggregates pipeline analytics including total ARR, deal counts,
    win probability, health scores, and forecast confidence.
    """

    def __init__(self, crm_service):
        """
        Initialize handler with CRM service reference.
        
        Args:
            crm_service: CRM repository implementation
        """
        self.crm = crm_service
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def handle(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute query_pipeline_metrics tool logic.
        
        Queries CRM for aggregated pipeline data, calculates KPIs,
        and returns point-in-time snapshot for Alexa+ reporting.
        
        Args:
            arguments: Tool arguments with period_start, period_end, optional filters
            
        Returns:
            Dictionary with complete pipeline metrics snapshot
            
        Raises:
            ToolHandlerException: On validation or CRM query failure
        """
        try:
            # Parse period dates
            period_start = datetime.fromisoformat(
                arguments.get("period_start", "").replace('Z', '+00:00')
            )
            period_end = datetime.fromisoformat(
                arguments.get("period_end", "").replace('Z', '+00:00')
            )
            include_closed = arguments.get("include_closed_deals", False)
            owner_filter = arguments.get("filter_by_owner")
            min_arr = arguments.get("min_arr_threshold", 0)

            self.logger.info(
                f"Querying pipeline metrics: {period_start} to {period_end}, "
                f"include_closed={include_closed}, owner={owner_filter}"
            )

            # Query CRM for aggregated metrics
            metrics = await self.crm.query_pipeline_metrics(
                period_start=period_start,
                period_end=period_end,
                include_closed_deals=include_closed,
                owner_filter=owner_filter,
                min_arr_threshold=min_arr
            )

            if not metrics:
                # Return empty metrics if no deals found
                metrics = PipelineMetrics(
                    period_start=period_start,
                    period_end=period_end
                )

            response = {
                "success": True,
                "metrics": json.loads(metrics.model_dump_json()),
                "period": {
                    "start": period_start.isoformat(),
                    "end": period_end.isoformat()
                },
                "summary": {
                    "total_deals": metrics.total_deals,
                    "total_pipeline_arr_usd": metrics.total_pipeline_arr / 100,  # Convert cents to dollars
                    "weighted_arr_usd": metrics.weighted_arr / 100,
                    "win_probability": f"{metrics.win_probability}%",
                    "average_health_score": metrics.average_health_score,
                    "at_risk_deals": metrics.at_risk_deals,
                    "stalled_deals": metrics.stalled_deals,
                    "forecast_confidence": f"{metrics.forecast_confidence}%"
                },
                "generated_at": datetime.utcnow().isoformat()
            }

            self.logger.info(
                f"Pipeline metrics query successful: "
                f"{metrics.total_deals} deals, ${metrics.total_pipeline_arr / 100:.2f} ARR"
            )
            return response

        except ValueError as ve:
            self.logger.error(f"Validation error in query_pipeline_metrics: {str(ve)}")
            raise ToolHandlerException(f"Invalid parameters: {str(ve)}")
        except Exception as e:
            self.logger.error(f"Error querying pipeline metrics: {str(e)}", exc_info=True)
            raise ToolHandlerException(f"Failed to query pipeline metrics: {str(e)}")


class CreateLeadEntryHandler:
    """
    Handler for create_lead_entry MCP tool.
    
    Converts ambient notes and voice input into structured lead records.
    Supports fuzzy extraction with confidence scoring.
    """

    def __init__(self, crm_service, parser_service=None):
        """
        Initialize handler with CRM and optional parser service.
        
        Args:
            crm_service: CRM repository implementation
            parser_service: Optional LLM parser for voice extraction
        """
        self.crm = crm_service
        self.parser = parser_service
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def handle(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute create_lead_entry tool logic.
        
        Validates lead parameters, optionally enhances with LLM parsing,
        constructs LeadEntry model, persists to CRM.
        
        Args:
            arguments: Tool arguments with contact info, company details, ambient notes
            
        Returns:
            Dictionary with lead_id, confidence_score, and extracted metadata
            
        Raises:
            ToolHandlerException: On validation or CRM operation failure
        """
        try:
            # Extract optional metadata
            additional_context = arguments.get("additional_context", {})

            # If ambient notes provided and parser available, enhance extraction
            if arguments.get("ambient_notes") and self.parser:
                try:
                    enhanced_data = await self.parser.extract_from_notes(
                        arguments.get("ambient_notes")
                    )
                    if enhanced_data:
                        # Merge LLM-extracted fields (without overwriting explicit values)
                        for key, value in enhanced_data.items():
                            if key not in arguments or arguments[key] is None:
                                arguments[key] = value
                        additional_context.update({"llm_extracted": True})
                except Exception as e:
                    self.logger.warning(f"LLM parsing failed, proceeding with manual data: {str(e)}")

            arguments["additional_context"] = additional_context

            # Parse and validate lead entry
            lead_entry = LeadEntry(**arguments)

            self.logger.info(
                f"Creating lead entry: {lead_entry.first_name} {lead_entry.last_name} "
                f"({lead_entry.email}), confidence={lead_entry.confidence_score}%"
            )

            # Persist lead to CRM
            created_lead = await self.crm.create_lead_entry(lead_entry)

            if not created_lead:
                raise ToolHandlerException(
                    f"Failed to create lead {lead_entry.email} in CRM"
                )

            response = {
                "success": True,
                "lead_id": created_lead.lead_id,
                "contact": {
                    "first_name": created_lead.first_name,
                    "last_name": created_lead.last_name,
                    "email": created_lead.email,
                    "phone": created_lead.phone
                },
                "company": {
                    "name": created_lead.company_name,
                    "size": created_lead.company_size,
                    "industry": created_lead.industry
                },
                "engagement": {
                    "source": created_lead.source,
                    "interest_category": created_lead.interest_category,
                    "budget_range": created_lead.budget_range,
                    "decision_timeline": created_lead.decision_timeline
                },
                "confidence_score": created_lead.confidence_score,
                "created_at": created_lead.created_at.isoformat(),
                "message": f"Lead created with ID {created_lead.lead_id}"
            }

            self.logger.info(f"Lead entry created successfully: {created_lead.lead_id}")
            return response

        except ValueError as ve:
            self.logger.error(f"Validation error in create_lead_entry: {str(ve)}")
            raise ToolHandlerException(f"Invalid parameters: {str(ve)}")
        except Exception as e:
            self.logger.error(f"Error creating lead entry: {str(e)}", exc_info=True)
            raise ToolHandlerException(f"Failed to create lead entry: {str(e)}")


async def bind_handlers_to_server(mcp_server, crm_service, parser_service=None) -> None:
    """
    Bind all tool handlers to MCP protocol server.
    
    This function registers the async handlers for all four tools with the
    MCPStreamableHTTPServer, enabling Alexa+ to invoke them via JSON-RPC.
    
    Args:
        mcp_server: MCPStreamableHTTPServer instance
        crm_service: CRM repository implementation
        parser_service: Optional LLM parser service for voice extraction
    """
    # Create handler instances
    update_deal_handler = UpdateDealStageHandler(crm_service)
    log_risk_handler = LogDealRiskHandler(crm_service)
    query_metrics_handler = QueryPipelineMetricsHandler(crm_service)
    create_lead_handler = CreateLeadEntryHandler(crm_service, parser_service)

    # Register handlers with server
    mcp_server.register_tool_handler(
        "update_deal_stage",
        update_deal_handler.handle
    )
    mcp_server.register_tool_handler(
        "log_deal_risk",
        log_risk_handler.handle
    )
    mcp_server.register_tool_handler(
        "query_pipeline_metrics",
        query_metrics_handler.handle
    )
    mcp_server.register_tool_handler(
        "create_lead_entry",
        create_lead_handler.handle
    )

    logger.info("All MCP tool handlers bound to server successfully")
