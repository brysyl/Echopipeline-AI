"""
RevOps Domain Models (Pydantic v2)

Defines complete type-safe data structures for deal management, risk assessment,
pipeline analytics, and lead generation. All models enforced with strict validation.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator, model_validator
import uuid


class DealStage(str, Enum):
    """Deal pipeline stage enumeration following standard RevOps lifecycle."""
    PROSPECTING = "Prospecting"
    QUALIFICATION = "Qualification"
    DISCOVERY = "Discovery"
    PROPOSAL = "Proposal"
    PROCUREMENT = "Procurement"
    NEGOTIATION = "Negotiation"
    CLOSED_WON = "Closed-Won"
    CLOSED_LOST = "Closed-Lost"


class RiskSeverity(int, Enum):
    """Risk severity scale for deal health assessment (1-5)."""
    LOW = 1
    MODERATE = 2
    MEDIUM = 3
    HIGH = 4
    CRITICAL = 5


class DealStatus(str, Enum):
    """Deal overall status."""
    ACTIVE = "active"
    STALLED = "stalled"
    AT_RISK = "at_risk"
    CLOSED = "closed"


class LeadSource(str, Enum):
    """Lead acquisition source channel."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    REFERRAL = "referral"
    PARTNER = "partner"
    EVENT = "event"
    AMBIENT_NOTES = "ambient_notes"


class DealStageUpdate(BaseModel):
    """
    Deal stage mutation request model.
    
    Represents a single deal advancing through pipeline stages with ARR tracking.
    Used by Alexa+ intent handler to mutate deal stage in RevOps system.
    
    Attributes:
        deal_id: Unique deal identifier (UUID format)
        current_stage: Deal's current pipeline stage
        new_stage: Target pipeline stage after mutation
        arr_value: Annual Recurring Revenue in USD cents (to avoid float precision issues)
        close_date: Expected close date for forecasting
        notes: Optional stage transition notes or context
        mutated_by: Alexa+ session ID or user identifier
        timestamp: Timestamp of mutation request
    """
    
    deal_id: str = Field(
        ...,
        description="Unique deal identifier",
        pattern=r"^[a-zA-Z0-9\-_]{1,50}$"
    )
    current_stage: DealStage = Field(
        ...,
        description="Current pipeline stage before mutation"
    )
    new_stage: DealStage = Field(
        ...,
        description="Target pipeline stage after mutation"
    )
    arr_value: int = Field(
        ...,
        ge=0,
        le=10_000_000_00,  # Max 10M USD
        description="Annual Recurring Revenue in USD cents"
    )
    close_date: Optional[datetime] = Field(
        None,
        description="Expected deal close date"
    )
    notes: Optional[str] = Field(
        None,
        max_length=1000,
        description="Optional transition notes or context"
    )
    mutated_by: str = Field(
        ...,
        max_length=256,
        description="Alexa+ session ID or user identifier"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of mutation request"
    )

    @field_validator("new_stage")
    @classmethod
    def validate_stage_transition(cls, v: DealStage, info) -> DealStage:
        """Validate that new_stage differs from current_stage."""
        if "current_stage" in info.data and v == info.data["current_stage"]:
            raise ValueError("new_stage must differ from current_stage")
        return v

    @field_validator("close_date")
    @classmethod
    def validate_close_date(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Ensure close_date is in the future if provided."""
        if v is not None and v <= datetime.utcnow():
            raise ValueError("close_date must be in the future")
        return v

    class Config:
        use_enum_values = False
        json_schema_extra = {
            "example": {
                "deal_id": "deal-abc123",
                "current_stage": "Prospecting",
                "new_stage": "Qualification",
                "arr_value": 50000_00,
                "close_date": "2026-12-31T23:59:59Z",
                "notes": "Qualified after discovery call",
                "mutated_by": "alexa-session-xyz"
            }
        }


class RIGSScore(BaseModel):
    """
    RIGS Framework scoring model for deal health assessment.
    
    RIGS = Risk, Intent, Growth, Stakeholder
    Each component scored 0-100, with aggregate weighting for overall deal health.
    
    Attributes:
        risk_score: Risk mitigation confidence (0-100, higher is better)
        intent_score: Buyer intent clarity (0-100)
        growth_score: Growth potential/ARR uplift (0-100)
        stakeholder_score: Executive sponsorship & alignment (0-100)
        aggregate_health: Weighted health score (0-100)
    """
    
    risk_score: int = Field(
        default=50,
        ge=0,
        le=100,
        description="Risk mitigation confidence (0-100, higher is better)"
    )
    intent_score: int = Field(
        default=50,
        ge=0,
        le=100,
        description="Buyer intent clarity (0-100)"
    )
    growth_score: int = Field(
        default=50,
        ge=0,
        le=100,
        description="Growth potential and ARR uplift (0-100)"
    )
    stakeholder_score: int = Field(
        default=50,
        ge=0,
        le=100,
        description="Executive sponsorship and alignment (0-100)"
    )

    @property
    def aggregate_health(self) -> int:
        """Calculate weighted aggregate health score."""
        # RIGS weights: Risk 40%, Intent 30%, Growth 20%, Stakeholder 10%
        weighted = (
            (self.risk_score * 0.40) +
            (self.intent_score * 0.30) +
            (self.growth_score * 0.20) +
            (self.stakeholder_score * 0.10)
        )
        return int(weighted)

    class Config:
        json_schema_extra = {
            "example": {
                "risk_score": 75,
                "intent_score": 85,
                "growth_score": 60,
                "stakeholder_score": 70
            }
        }


class DealRiskLog(BaseModel):
    """
    Deal risk assessment and logging model.
    
    Captures risk events, severity levels, and RIGS framework scoring.
    Generates audit trail for deal health tracking over time.
    
    Used by Alexa+ to flag deal risks and update health signals.
    
    Attributes:
        risk_id: Unique risk event identifier
        deal_id: Associated deal identifier
        severity: Risk severity level (1-5 scale)
        risk_category: Type of risk (e.g., budget, timeline, competition, technical)
        description: Detailed risk description
        rigs_scores: RIGS framework assessment
        mitigation_plan: Optional mitigation strategy
        owner: Risk owner (sales rep, account manager)
        created_at: Risk identification timestamp
        updated_at: Last update timestamp
        resolved_at: Optional resolution timestamp
        resolution_notes: Optional notes on resolution
    """
    
    risk_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique risk event identifier"
    )
    deal_id: str = Field(
        ...,
        description="Associated deal identifier",
        pattern=r"^[a-zA-Z0-9\-_]{1,50}$"
    )
    severity: RiskSeverity = Field(
        ...,
        description="Risk severity level (1-5)"
    )
    risk_category: str = Field(
        ...,
        max_length=100,
        description="Type of risk (budget, timeline, competition, technical, etc.)"
    )
    description: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Detailed risk description"
    )
    rigs_scores: RIGSScore = Field(
        default_factory=RIGSScore,
        description="RIGS framework assessment"
    )
    mitigation_plan: Optional[str] = Field(
        None,
        max_length=1500,
        description="Mitigation strategy or action plan"
    )
    owner: str = Field(
        ...,
        max_length=256,
        description="Risk owner (sales rep, account manager)"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Risk identification timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last update timestamp"
    )
    resolved_at: Optional[datetime] = Field(
        None,
        description="Optional resolution timestamp"
    )
    resolution_notes: Optional[str] = Field(
        None,
        max_length=1000,
        description="Notes on risk resolution"
    )

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def validate_timestamps(cls, v):
        """Ensure timestamps are valid datetime objects."""
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace('Z', '+00:00'))
        return v

    @model_validator(mode="after")
    def validate_resolution_consistency(self):
        """Ensure resolved_at and resolution_notes are consistent."""
        if self.resolved_at is not None and self.resolution_notes is None:
            raise ValueError("resolved_at requires resolution_notes")
        if self.resolved_at is None and self.resolution_notes is not None:
            raise ValueError("resolution_notes requires resolved_at")
        return self

    class Config:
        use_enum_values = False
        json_schema_extra = {
            "example": {
                "risk_id": "risk-001",
                "deal_id": "deal-abc123",
                "severity": 4,
                "risk_category": "budget",
                "description": "Buyer's budget approval delayed by finance committee",
                "rigs_scores": {
                    "risk_score": 40,
                    "intent_score": 80,
                    "growth_score": 75,
                    "stakeholder_score": 55
                },
                "mitigation_plan": "Escalate to CFO, prepare ROI analysis",
                "owner": "john.doe@company.com"
            }
        }


class PipelineMetrics(BaseModel):
    """
    Aggregated pipeline metrics snapshot for forecasting and health reporting.
    
    Captures current state of RevOps pipeline including revenue, deal counts,
    probability-weighted metrics, and health indicators.
    
    Used by Alexa+ query_pipeline_metrics tool for real-time pipeline status.
    
    Attributes:
        period_start: Start of reporting period
        period_end: End of reporting period
        total_deals: Count of active deals in pipeline
        total_pipeline_arr: Sum of ARR across all active deals (USD cents)
        weighted_arr: Probability-weighted pipeline ARR
        average_deal_arr: Mean ARR per deal
        deal_stages: Breakdown of deals by stage
        win_probability: Aggregate win probability (0-100)
        average_health_score: Mean RIGS health score across deals
        at_risk_deals: Count of deals with severity >= 4
        stalled_deals: Count of deals stalled > 30 days
        forecast_confidence: Forecast confidence level (0-100)
        generated_at: Timestamp of metric calculation
    """
    
    period_start: datetime = Field(
        ...,
        description="Start of reporting period"
    )
    period_end: datetime = Field(
        ...,
        description="End of reporting period"
    )
    total_deals: int = Field(
        default=0,
        ge=0,
        description="Count of active deals in pipeline"
    )
    total_pipeline_arr: int = Field(
        default=0,
        ge=0,
        description="Sum of ARR across all active deals (USD cents)"
    )
    weighted_arr: int = Field(
        default=0,
        ge=0,
        description="Probability-weighted pipeline ARR (USD cents)"
    )
    average_deal_arr: int = Field(
        default=0,
        ge=0,
        description="Mean ARR per deal (USD cents)"
    )
    deal_stages: Dict[str, int] = Field(
        default_factory=dict,
        description="Breakdown of deal counts by stage"
    )
    win_probability: int = Field(
        default=50,
        ge=0,
        le=100,
        description="Aggregate win probability (0-100)"
    )
    average_health_score: int = Field(
        default=50,
        ge=0,
        le=100,
        description="Mean RIGS health score across deals"
    )
    at_risk_deals: int = Field(
        default=0,
        ge=0,
        description="Count of deals with severity >= 4"
    )
    stalled_deals: int = Field(
        default=0,
        ge=0,
        description="Count of deals stalled > 30 days"
    )
    forecast_confidence: int = Field(
        default=50,
        ge=0,
        le=100,
        description="Forecast confidence level (0-100)"
    )
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of metric calculation"
    )

    @field_validator("average_deal_arr")
    @classmethod
    def validate_average_deal_arr(cls, v, info):
        """Validate average_deal_arr is consistent with total and count."""
        if "total_deals" in info.data and info.data["total_deals"] > 0:
            if "total_pipeline_arr" in info.data:
                calculated = info.data["total_pipeline_arr"] // info.data["total_deals"]
                if v != 0 and abs(v - calculated) > 100:  # Allow 100 cent tolerance
                    raise ValueError("average_deal_arr inconsistent with total_pipeline_arr and total_deals")
        return v

    @model_validator(mode="after")
    def validate_period_range(self):
        """Ensure period_end > period_start."""
        if self.period_end <= self.period_start:
            raise ValueError("period_end must be after period_start")
        return self

    class Config:
        json_schema_extra = {
            "example": {
                "period_start": "2026-09-01T00:00:00Z",
                "period_end": "2026-09-30T23:59:59Z",
                "total_deals": 25,
                "total_pipeline_arr": 5_000_000_00,
                "weighted_arr": 3_500_000_00,
                "average_deal_arr": 200_000_00,
                "deal_stages": {
                    "Prospecting": 8,
                    "Qualification": 7,
                    "Proposal": 6,
                    "Procurement": 4
                },
                "win_probability": 72,
                "average_health_score": 68,
                "at_risk_deals": 3,
                "stalled_deals": 2,
                "forecast_confidence": 75
            }
        }


class LeadEntry(BaseModel):
    """
    Structured lead metadata ingestion model.
    
    Converts ambient notes and voice input from Alexa+ into structured
    lead records for CRM integration. Supports auto-population from
    fuzzy voice parameter extraction.
    
    Used by Alexa+ create_lead_entry tool for lead generation.
    
    Attributes:
        lead_id: Unique lead identifier (auto-generated if not provided)
        first_name: Lead contact first name
        last_name: Lead contact last name
        email: Lead email address (validated)
        phone: Lead phone number (E.164 format preferred)
        company_name: Lead's company
        company_size: Company employee count range
        industry: Industry vertical
        job_title: Lead's job title
        department: Lead's department
        source: Lead acquisition source channel
        source_detail: Additional source context from ambient notes
        ambient_notes: Raw ambient notes or voice transcription
        interest_category: Product/service interest area
        budget_range: Estimated budget indicator
        decision_timeline: Expected purchase timeline
        additional_context: Arbitrary key-value metadata
        created_at: Lead record creation timestamp
        created_by_session: Alexa+ session ID that generated this lead
        confidence_score: Data quality/completeness confidence (0-100)
    """
    
    lead_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique lead identifier"
    )
    first_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Lead contact first name"
    )
    last_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Lead contact last name"
    )
    email: str = Field(
        ...,
        description="Lead email address",
        pattern=r"^[a-zA-Z0-9._%\-+]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    )
    phone: Optional[str] = Field(
        None,
        max_length=20,
        description="Lead phone number (E.164 format preferred)"
    )
    company_name: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Lead's company name"
    )
    company_size: Optional[str] = Field(
        None,
        description="Company employee count range (e.g., '1-10', '11-50', '51-200', '201-500', '501-1000', '1000+')"
    )
    industry: Optional[str] = Field(
        None,
        max_length=100,
        description="Industry vertical"
    )
    job_title: Optional[str] = Field(
        None,
        max_length=150,
        description="Lead's job title"
    )
    department: Optional[str] = Field(
        None,
        max_length=100,
        description="Lead's department"
    )
    source: LeadSource = Field(
        default=LeadSource.AMBIENT_NOTES,
        description="Lead acquisition source channel"
    )
    source_detail: Optional[str] = Field(
        None,
        max_length=500,
        description="Additional source context from ambient notes"
    )
    ambient_notes: Optional[str] = Field(
        None,
        max_length=5000,
        description="Raw ambient notes or voice transcription"
    )
    interest_category: Optional[str] = Field(
        None,
        max_length=200,
        description="Product/service interest area"
    )
    budget_range: Optional[str] = Field(
        None,
        description="Estimated budget indicator (e.g., '<$10k', '$10k-$50k', '$50k-$100k', '>$100k')"
    )
    decision_timeline: Optional[str] = Field(
        None,
        max_length=200,
        description="Expected purchase timeline"
    )
    additional_context: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Arbitrary key-value metadata from voice extraction"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Lead record creation timestamp"
    )
    created_by_session: str = Field(
        ...,
        max_length=256,
        description="Alexa+ session ID that generated this lead"
    )
    confidence_score: int = Field(
        default=50,
        ge=0,
        le=100,
        description="Data quality/completeness confidence (0-100)"
    )

    @field_validator("confidence_score")
    @classmethod
    def calculate_confidence(cls, v, info):
        """Auto-calculate confidence based on field completion if not explicitly set."""
        data = info.data
        # Count filled optional fields
        optional_fields = [
            data.get("phone"),
            data.get("company_size"),
            data.get("industry"),
            data.get("job_title"),
            data.get("department"),
            data.get("ambient_notes"),
            data.get("interest_category"),
            data.get("budget_range"),
            data.get("decision_timeline"),
        ]
        filled = sum(1 for f in optional_fields if f is not None)
        total_optional = len(optional_fields)
        # Base confidence on required fields + optional field completion
        base_confidence = 60  # Required fields provide base 60%
        optional_contribution = (filled / total_optional * 40) if total_optional > 0 else 0
        calculated = int(base_confidence + optional_contribution)
        return v if v > 0 else calculated

    class Config:
        use_enum_values = False
        json_schema_extra = {
            "example": {
                "lead_id": "lead-20260903-001",
                "first_name": "Alice",
                "last_name": "Johnson",
                "email": "alice.johnson@acmecorp.com",
                "phone": "+1-415-555-0123",
                "company_name": "Acme Corporation",
                "company_size": "501-1000",
                "industry": "Technology",
                "job_title": "VP of Sales Operations",
                "department": "Sales",
                "source": "ambient_notes",
                "source_detail": "Mentioned during industry conference networking session",
                "ambient_notes": "Very interested in RevOps automation. Budget approved for Q4 2026.",
                "interest_category": "Sales Automation & Analytics",
                "budget_range": "$50k-$100k",
                "decision_timeline": "Q4 2026",
                "created_by_session": "alexa-session-xyz789",
                "confidence_score": 85
            }
        }
