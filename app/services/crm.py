"""
CRM Repository Layer (Abstract + Implementations)

Defines abstract BaseCRMRepository interface and provides two implementations:
1. SupabaseCRMRepository: Production Supabase PostgreSQL backend
2. MockCRMRepository: In-memory mock for local development and testing (MOCK_MODE=true)

All async methods enforce strict Pydantic v2 validation against RevOps domain models.
Supports Deals, Accounts, Risk Logs, and Lead entries with full audit trail.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import logging
import json
import uuid
from decimal import Decimal

from pydantic import BaseModel, ValidationError

from app.models.revops import (
    DealStageUpdate,
    DealRiskLog,
    RIGSScore,
    PipelineMetrics,
    LeadEntry,
    DealStage,
    RiskSeverity,
    LeadSource,
    DealStatus
)

logger = logging.getLogger(__name__)


class Deal(BaseModel):
    """Internal Deal model for persistence."""
    id: str
    account_id: str
    name: str
    stage: DealStage
    arr_value: int  # USD cents
    close_date: Optional[datetime] = None
    status: DealStatus
    owner_email: str
    health_score: int = 50
    created_at: datetime
    updated_at: datetime
    notes: Optional[str] = None


class Account(BaseModel):
    """Internal Account model for persistence."""
    id: str
    name: str
    industry: Optional[str] = None
    company_size: Optional[str] = None
    annual_revenue: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class BaseCRMRepository(ABC):
    """
    Abstract base class for CRM repository implementations.
    
    Defines contract for all CRM operations. Implementations must handle:
    - Deal CRUD and stage mutations
    - Risk logging with RIGS scoring
    - Pipeline metrics aggregation
    - Lead entry creation
    - Account management
    """

    @abstractmethod
    async def get_deal(self, deal_id: str) -> Optional[Deal]:
        """
        Retrieve deal by ID.
        
        Args:
            deal_id: Unique deal identifier
            
        Returns:
            Deal object if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_deal_by_name(self, deal_name: str) -> Optional[Deal]:
        """
        Retrieve deal by name.
        
        Args:
            deal_name: Deal name
            
        Returns:
            Deal object if found, None otherwise
        """
        pass

    @abstractmethod
    async def update_deal_stage(self, update_request: DealStageUpdate) -> Optional[Deal]:
        """
        Update deal stage with validation and audit trail.
        
        Args:
            update_request: DealStageUpdate with stage transition and metadata
            
        Returns:
            Updated Deal object if successful, None otherwise
        """
        pass

    @abstractmethod
    async def get_deal_health_score(self, deal_id: str) -> int:
        """
        Calculate current deal health score (0-100).
        
        Aggregates RIGS scores from latest risk logs for deal.
        
        Args:
            deal_id: Deal identifier
            
        Returns:
            Health score 0-100
        """
        pass

    @abstractmethod
    async def log_deal_risk(self, risk_log: DealRiskLog) -> Optional[DealRiskLog]:
        """
        Log risk event for deal with RIGS framework scoring.
        
        Args:
            risk_log: DealRiskLog with severity, category, and RIGS scores
            
        Returns:
            Created DealRiskLog if successful, None otherwise
        """
        pass

    @abstractmethod
    async def query_pipeline_metrics(
        self,
        period_start: datetime,
        period_end: datetime,
        include_closed_deals: bool = False,
        owner_filter: Optional[str] = None,
        min_arr_threshold: int = 0
    ) -> Optional[PipelineMetrics]:
        """
        Aggregate pipeline metrics for reporting period.
        
        Args:
            period_start: Start of reporting period
            period_end: End of reporting period
            include_closed_deals: Include closed deals in aggregation
            owner_filter: Optional filter by deal owner email
            min_arr_threshold: Optional minimum ARR filter (cents)
            
        Returns:
            PipelineMetrics snapshot if data found, None otherwise
        """
        pass

    @abstractmethod
    async def create_lead_entry(self, lead: LeadEntry) -> Optional[LeadEntry]:
        """
        Create structured lead record from ambient notes.
        
        Args:
            lead: LeadEntry with contact info and metadata
            
        Returns:
            Created LeadEntry if successful, None otherwise
        """
        pass

    @abstractmethod
    async def get_account(self, account_id: str) -> Optional[Account]:
        """
        Retrieve account by ID.
        
        Args:
            account_id: Unique account identifier
            
        Returns:
            Account object if found, None otherwise
        """
        pass

    @abstractmethod
    async def create_account(
        self,
        name: str,
        industry: Optional[str] = None,
        company_size: Optional[str] = None,
        annual_revenue: Optional[int] = None
    ) -> Optional[Account]:
        """
        Create new account record.
        
        Args:
            name: Account name
            industry: Industry vertical
            company_size: Employee count range
            annual_revenue: Annual revenue in USD cents
            
        Returns:
            Created Account if successful, None otherwise
        """
        pass


class SupabaseCRMRepository(BaseCRMRepository):
    """
    Production CRM repository using Supabase PostgreSQL backend.
    
    Implements all async methods with direct Supabase client operations.
    Requires SUPABASE_URL and SUPABASE_KEY environment variables.
    """

    def __init__(self, supabase_client):
        """
        Initialize Supabase repository.
        
        Args:
            supabase_client: Initialized Supabase async client
        """
        self.db = supabase_client
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.logger.info("SupabaseCRMRepository initialized")

    async def get_deal(self, deal_id: str) -> Optional[Deal]:
        """Retrieve deal by ID from Supabase."""
        try:
            result = await self.db.table("deals").select("*").eq("id", deal_id).single()
            if result.data:
                return Deal(**result.data)
            return None
        except Exception as e:
            self.logger.error(f"Error retrieving deal {deal_id}: {str(e)}")
            return None

    async def get_deal_by_name(self, deal_name: str) -> Optional[Deal]:
        """Retrieve deal by name from Supabase."""
        try:
            result = await self.db.table("deals").select("*").eq("name", deal_name).single()
            if result.data:
                return Deal(**result.data)
            return None
        except Exception as e:
            self.logger.error(f"Error retrieving deal by name {deal_name}: {str(e)}")
            return None

    async def update_deal_stage(self, update_request: DealStageUpdate) -> Optional[Deal]:
        """Update deal stage in Supabase with audit trail."""
        try:
            # Get current deal
            current_deal = await self.get_deal(update_request.deal_id)
            if not current_deal:
                self.logger.error(f"Deal {update_request.deal_id} not found")
                return None

            # Update deal record
            update_data = {
                "stage": update_request.new_stage.value,
                "arr_value": update_request.arr_value,
                "close_date": update_request.close_date.isoformat() if update_request.close_date else None,
                "notes": update_request.notes,
                "updated_at": datetime.utcnow().isoformat()
            }

            result = await self.db.table("deals").update(update_data).eq("id", update_request.deal_id)
            
            if result.data:
                # Create audit log entry
                audit_entry = {
                    "id": str(uuid.uuid4()),
                    "deal_id": update_request.deal_id,
                    "action": "stage_update",
                    "from_stage": update_request.current_stage.value,
                    "to_stage": update_request.new_stage.value,
                    "performed_by": update_request.mutated_by,
                    "timestamp": datetime.utcnow().isoformat(),
                    "metadata": json.dumps({
                        "arr_value": update_request.arr_value,
                        "close_date": update_request.close_date.isoformat() if update_request.close_date else None
                    })
                }
                await self.db.table("audit_logs").insert(audit_entry)
                
                # Return updated deal
                return await self.get_deal(update_request.deal_id)
            
            return None
        except Exception as e:
            self.logger.error(f"Error updating deal stage: {str(e)}", exc_info=True)
            return None

    async def get_deal_health_score(self, deal_id: str) -> int:
        """Calculate deal health score from latest risk logs."""
        try:
            # Query latest risk logs for deal
            result = await self.db.table("risk_logs") \
                .select("*") \
                .eq("deal_id", deal_id) \
                .order("created_at", ascending=False) \
                .limit(10)
            
            if not result.data or len(result.data) == 0:
                return 75  # Default healthy score if no risks
            
            # Aggregate RIGS scores from latest risks
            risk_scores = [r.get("rigs_scores", {}) for r in result.data]
            
            if not risk_scores:
                return 75
            
            # Average RIGS scores
            avg_risk = sum(r.get("risk_score", 50) for r in risk_scores) / len(risk_scores)
            avg_intent = sum(r.get("intent_score", 50) for r in risk_scores) / len(risk_scores)
            avg_growth = sum(r.get("growth_score", 50) for r in risk_scores) / len(risk_scores)
            avg_stakeholder = sum(r.get("stakeholder_score", 50) for r in risk_scores) / len(risk_scores)
            
            # Calculate weighted health (same as RIGSScore)
            health = int(
                (avg_risk * 0.40) +
                (avg_intent * 0.30) +
                (avg_growth * 0.20) +
                (avg_stakeholder * 0.10)
            )
            
            return max(0, min(100, health))
        except Exception as e:
            self.logger.error(f"Error calculating deal health: {str(e)}")
            return 50  # Conservative default

    async def log_deal_risk(self, risk_log: DealRiskLog) -> Optional[DealRiskLog]:
        """Log deal risk in Supabase."""
        try:
            # Verify deal exists
            deal = await self.get_deal(risk_log.deal_id)
            if not deal:
                self.logger.error(f"Deal {risk_log.deal_id} not found")
                return None

            # Insert risk log
            risk_data = {
                "id": risk_log.risk_id,
                "deal_id": risk_log.deal_id,
                "severity": risk_log.severity.value,
                "risk_category": risk_log.risk_category,
                "description": risk_log.description,
                "rigs_scores": json.dumps(json.loads(risk_log.rigs_scores.model_dump_json())),
                "mitigation_plan": risk_log.mitigation_plan,
                "owner": risk_log.owner,
                "created_at": risk_log.created_at.isoformat(),
                "updated_at": risk_log.updated_at.isoformat(),
                "resolved_at": risk_log.resolved_at.isoformat() if risk_log.resolved_at else None,
                "resolution_notes": risk_log.resolution_notes
            }

            result = await self.db.table("risk_logs").insert(risk_data)
            
            if result.data:
                self.logger.info(f"Risk logged: {risk_log.risk_id}")
                return risk_log
            
            return None
        except Exception as e:
            self.logger.error(f"Error logging risk: {str(e)}", exc_info=True)
            return None

    async def query_pipeline_metrics(
        self,
        period_start: datetime,
        period_end: datetime,
        include_closed_deals: bool = False,
        owner_filter: Optional[str] = None,
        min_arr_threshold: int = 0
    ) -> Optional[PipelineMetrics]:
        """Query aggregated pipeline metrics from Supabase."""
        try:
            # Build query
            query = self.db.table("deals").select("*")
            
            # Apply filters
            if not include_closed_deals:
                query = query.in_("stage", [
                    DealStage.PROSPECTING.value,
                    DealStage.QUALIFICATION.value,
                    DealStage.DISCOVERY.value,
                    DealStage.PROPOSAL.value,
                    DealStage.PROCUREMENT.value,
                    DealStage.NEGOTIATION.value
                ])
            
            if owner_filter:
                query = query.eq("owner_email", owner_filter)
            
            result = await query
            deals = result.data or []
            
            # Filter by ARR threshold
            deals = [d for d in deals if d.get("arr_value", 0) >= min_arr_threshold]
            
            # Aggregate metrics
            total_deals = len(deals)
            total_arr = sum(d.get("arr_value", 0) for d in deals)
            
            # Calculate stage breakdown
            deal_stages = {}
            for stage in DealStage:
                count = sum(1 for d in deals if d.get("stage") == stage.value)
                if count > 0:
                    deal_stages[stage.value] = count
            
            # Calculate weighted ARR (simple: 50% for Proposal+, 25% for Discovery+, etc.)
            weights = {
                DealStage.PROSPECTING.value: 0.10,
                DealStage.QUALIFICATION.value: 0.25,
                DealStage.DISCOVERY.value: 0.40,
                DealStage.PROPOSAL.value: 0.60,
                DealStage.PROCUREMENT.value: 0.80,
                DealStage.NEGOTIATION.value: 0.90,
            }
            weighted_arr = sum(
                d.get("arr_value", 0) * weights.get(d.get("stage"), 0.5)
                for d in deals
            )
            weighted_arr = int(weighted_arr)
            
            # Calculate average deal ARR
            average_deal_arr = (total_arr // total_deals) if total_deals > 0 else 0
            
            # Get health scores
            health_scores = [d.get("health_score", 50) for d in deals]
            average_health = sum(health_scores) // len(health_scores) if health_scores else 50
            
            # Count at-risk deals (health < 50)
            at_risk = sum(1 for h in health_scores if h < 50)
            
            # Count stalled deals (no update in 30 days)
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            stalled = sum(
                1 for d in deals
                if datetime.fromisoformat(d.get("updated_at", "2000-01-01").replace('Z', '+00:00'))
                < thirty_days_ago
            )
            
            # Estimate win probability based on stage
            stage_win_prob = {
                DealStage.PROSPECTING.value: 10,
                DealStage.QUALIFICATION.value: 25,
                DealStage.DISCOVERY.value: 40,
                DealStage.PROPOSAL.value: 60,
                DealStage.PROCUREMENT.value: 75,
                DealStage.NEGOTIATION.value: 85,
            }
            if deals:
                win_prob = sum(
                    stage_win_prob.get(d.get("stage"), 50)
                    for d in deals
                ) // len(deals)
            else:
                win_prob = 50
            
            metrics = PipelineMetrics(
                period_start=period_start,
                period_end=period_end,
                total_deals=total_deals,
                total_pipeline_arr=total_arr,
                weighted_arr=weighted_arr,
                average_deal_arr=average_deal_arr,
                deal_stages=deal_stages,
                win_probability=win_prob,
                average_health_score=average_health,
                at_risk_deals=at_risk,
                stalled_deals=stalled,
                forecast_confidence=75
            )
            
            self.logger.info(f"Pipeline metrics calculated: {total_deals} deals")
            return metrics
        except Exception as e:
            self.logger.error(f"Error querying pipeline metrics: {str(e)}", exc_info=True)
            return None

    async def create_lead_entry(self, lead: LeadEntry) -> Optional[LeadEntry]:
        """Create lead entry in Supabase."""
        try:
            lead_data = {
                "id": lead.lead_id,
                "first_name": lead.first_name,
                "last_name": lead.last_name,
                "email": lead.email,
                "phone": lead.phone,
                "company_name": lead.company_name,
                "company_size": lead.company_size,
                "industry": lead.industry,
                "job_title": lead.job_title,
                "department": lead.department,
                "source": lead.source.value,
                "source_detail": lead.source_detail,
                "ambient_notes": lead.ambient_notes,
                "interest_category": lead.interest_category,
                "budget_range": lead.budget_range,
                "decision_timeline": lead.decision_timeline,
                "additional_context": json.dumps(lead.additional_context or {}),
                "created_at": lead.created_at.isoformat(),
                "created_by_session": lead.created_by_session,
                "confidence_score": lead.confidence_score
            }

            result = await self.db.table("leads").insert(lead_data)
            
            if result.data:
                self.logger.info(f"Lead created: {lead.lead_id}")
                return lead
            
            return None
        except Exception as e:
            self.logger.error(f"Error creating lead entry: {str(e)}", exc_info=True)
            return None

    async def get_account(self, account_id: str) -> Optional[Account]:
        """Retrieve account from Supabase."""
        try:
            result = await self.db.table("accounts").select("*").eq("id", account_id).single()
            if result.data:
                return Account(**result.data)
            return None
        except Exception as e:
            self.logger.error(f"Error retrieving account: {str(e)}")
            return None

    async def create_account(
        self,
        name: str,
        industry: Optional[str] = None,
        company_size: Optional[str] = None,
        annual_revenue: Optional[int] = None
    ) -> Optional[Account]:
        """Create account in Supabase."""
        try:
            account_data = {
                "id": str(uuid.uuid4()),
                "name": name,
                "industry": industry,
                "company_size": company_size,
                "annual_revenue": annual_revenue,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }

            result = await self.db.table("accounts").insert(account_data)
            
            if result.data:
                return Account(**result.data[0])
            
            return None
        except Exception as e:
            self.logger.error(f"Error creating account: {str(e)}", exc_info=True)
            return None


class MockCRMRepository(BaseCRMRepository):
    """
    In-memory mock CRM repository for local development and testing.
    
    Pre-seeded with realistic deal, account, and risk log data.
    Enabled via MOCK_MODE=true environment variable.
    No external dependencies required; runs out-of-the-box in Codespaces.
    """

    def __init__(self):
        """Initialize mock repository with pre-seeded data."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Pre-seeded accounts
        self.accounts: Dict[str, Account] = {
            "acct-001": Account(
                id="acct-001",
                name="Acme Corporation",
                industry="Technology",
                company_size="501-1000",
                annual_revenue=500_000_000_00,
                created_at=datetime.utcnow() - timedelta(days=180),
                updated_at=datetime.utcnow()
            ),
            "acct-002": Account(
                id="acct-002",
                name="TechVentures Inc",
                industry="SaaS",
                company_size="201-500",
                annual_revenue=250_000_000_00,
                created_at=datetime.utcnow() - timedelta(days=120),
                updated_at=datetime.utcnow()
            ),
            "acct-003": Account(
                id="acct-003",
                name="Enterprise Solutions LLC",
                industry="Enterprise Software",
                company_size="1000+",
                annual_revenue=1_000_000_000_00,
                created_at=datetime.utcnow() - timedelta(days=90),
                updated_at=datetime.utcnow()
            )
        }

        # Pre-seeded deals
        self.deals: Dict[str, Deal] = {
            "deal-001": Deal(
                id="deal-001",
                account_id="acct-001",
                name="Acme RevOps Platform",
                stage=DealStage.PROCUREMENT,
                arr_value=500_000_00,
                close_date=datetime.utcnow() + timedelta(days=30),
                status=DealStatus.ACTIVE,
                owner_email="alice@company.com",
                health_score=85,
                created_at=datetime.utcnow() - timedelta(days=60),
                updated_at=datetime.utcnow() - timedelta(hours=6),
                notes="Waiting on legal review"
            ),
            "deal-002": Deal(
                id="deal-002",
                account_id="acct-001",
                name="Acme Analytics Integration",
                stage=DealStage.DISCOVERY,
                arr_value=150_000_00,
                close_date=datetime.utcnow() + timedelta(days=90),
                status=DealStatus.ACTIVE,
                owner_email="bob@company.com",
                health_score=72,
                created_at=datetime.utcnow() - timedelta(days=45),
                updated_at=datetime.utcnow() - timedelta(days=5),
                notes="Engaged with procurement team"
            ),
            "deal-003": Deal(
                id="deal-003",
                account_id="acct-002",
                name="TechVentures Multi-Year Contract",
                stage=DealStage.PROPOSAL,
                arr_value=750_000_00,
                close_date=datetime.utcnow() + timedelta(days=45),
                status=DealStatus.ACTIVE,
                owner_email="alice@company.com",
                health_score=78,
                created_at=datetime.utcnow() - timedelta(days=30),
                updated_at=datetime.utcnow() - timedelta(hours=12),
                notes="Pricing proposal sent"
            ),
            "deal-004": Deal(
                id="deal-004",
                account_id="acct-003",
                name="Enterprise Full Suite Implementation",
                stage=DealStage.NEGOTIATION,
                arr_value=2_000_000_00,
                close_date=datetime.utcnow() + timedelta(days=21),
                status=DealStatus.AT_RISK,
                owner_email="charlie@company.com",
                health_score=55,
                created_at=datetime.utcnow() - timedelta(days=120),
                updated_at=datetime.utcnow() - timedelta(days=15),
                notes="Stalled on budget approval"
            ),
            "deal-005": Deal(
                id="deal-005",
                account_id="acct-002",
                name="TechVentures Pilot Program",
                stage=DealStage.QUALIFICATION,
                arr_value=50_000_00,
                close_date=datetime.utcnow() + timedelta(days=60),
                status=DealStatus.ACTIVE,
                owner_email="bob@company.com",
                health_score=68,
                created_at=datetime.utcnow() - timedelta(days=14),
                updated_at=datetime.utcnow() - timedelta(hours=48),
                notes="Initial discovery meeting scheduled"
            )
        }

        # Pre-seeded risk logs
        self.risk_logs: Dict[str, DealRiskLog] = {
            "risk-001": DealRiskLog(
                risk_id="risk-001",
                deal_id="deal-004",
                severity=RiskSeverity.HIGH,
                risk_category="budget",
                description="Buyer's budget approval delayed by finance committee, approval required by CFO",
                rigs_scores=RIGSScore(
                    risk_score=40,
                    intent_score=80,
                    growth_score=75,
                    stakeholder_score=55
                ),
                mitigation_plan="Escalate to CFO level, prepare detailed ROI analysis with 3-year projections",
                owner="charlie@company.com",
                created_at=datetime.utcnow() - timedelta(days=15),
                updated_at=datetime.utcnow() - timedelta(days=15)
            ),
            "risk-002": DealRiskLog(
                risk_id="risk-002",
                deal_id="deal-002",
                severity=RiskSeverity.MODERATE,
                risk_category="competition",
                description="Competitor gaining traction with technical POC, timeline pressure increasing",
                rigs_scores=RIGSScore(
                    risk_score=65,
                    intent_score=70,
                    growth_score=60,
                    stakeholder_score=75
                ),
                mitigation_plan="Schedule executive briefing, emphasize integration advantages",
                owner="bob@company.com",
                created_at=datetime.utcnow() - timedelta(days=8),
                updated_at=datetime.utcnow() - timedelta(days=8)
            )
        }

        # Pre-seeded leads
        self.leads: Dict[str, LeadEntry] = {
            "lead-001": LeadEntry(
                lead_id="lead-001",
                first_name="Sarah",
                last_name="Chen",
                email="sarah.chen@newtech.com",
                phone="+1-415-555-0101",
                company_name="NewTech Ventures",
                company_size="51-200",
                industry="AI/ML",
                job_title="VP Sales Operations",
                department="Sales",
                source=LeadSource.AMBIENT_NOTES,
                source_detail="Generated from Alexa+ ambient call notes",
                ambient_notes="Sarah discussed expanding RevOps team, budget approved for Q4 2026",
                interest_category="Sales Automation",
                budget_range="$50k-$100k",
                decision_timeline="Q4 2026",
                created_at=datetime.utcnow() - timedelta(days=3),
                created_by_session="alexa-session-abc123",
                confidence_score=82
            )
        }

        self.logger.info("MockCRMRepository initialized with pre-seeded data")

    async def get_deal(self, deal_id: str) -> Optional[Deal]:
        """Retrieve deal from mock store."""
        deal = self.deals.get(deal_id)
        if deal:
            self.logger.debug(f"Mock: Retrieved deal {deal_id}")
        else:
            self.logger.debug(f"Mock: Deal {deal_id} not found")
        return deal

    async def get_deal_by_name(self, deal_name: str) -> Optional[Deal]:
        """Retrieve deal by name from mock store."""
        for deal in self.deals.values():
            if deal.name == deal_name:
                self.logger.debug(f"Mock: Retrieved deal by name {deal_name}")
                return deal
        self.logger.debug(f"Mock: Deal with name {deal_name} not found")
        return None

    async def update_deal_stage(self, update_request: DealStageUpdate) -> Optional[Deal]:
        """Update deal stage in mock store."""
        deal = self.deals.get(update_request.deal_id)
        if not deal:
            self.logger.error(f"Mock: Deal {update_request.deal_id} not found")
            return None

        # Update deal
        deal.stage = update_request.new_stage
        deal.arr_value = update_request.arr_value
        if update_request.close_date:
            deal.close_date = update_request.close_date
        if update_request.notes:
            deal.notes = update_request.notes
        deal.updated_at = datetime.utcnow()

        self.logger.info(
            f"Mock: Updated deal {update_request.deal_id} to stage {update_request.new_stage}"
        )
        return deal

    async def get_deal_health_score(self, deal_id: str) -> int:
        """Calculate health score from mock risk logs."""
        risks = [r for r in self.risk_logs.values() if r.deal_id == deal_id]
        
        if not risks:
            return 75
        
        # Average RIGS scores
        avg_risk = sum(r.rigs_scores.risk_score for r in risks) / len(risks)
        avg_intent = sum(r.rigs_scores.intent_score for r in risks) / len(risks)
        avg_growth = sum(r.rigs_scores.growth_score for r in risks) / len(risks)
        avg_stakeholder = sum(r.rigs_scores.stakeholder_score for r in risks) / len(risks)
        
        health = int(
            (avg_risk * 0.40) +
            (avg_intent * 0.30) +
            (avg_growth * 0.20) +
            (avg_stakeholder * 0.10)
        )
        
        self.logger.debug(f"Mock: Calculated health score {health} for deal {deal_id}")
        return max(0, min(100, health))

    async def log_deal_risk(self, risk_log: DealRiskLog) -> Optional[DealRiskLog]:
        """Log risk in mock store."""
        deal = self.deals.get(risk_log.deal_id)
        if not deal:
            self.logger.error(f"Mock: Deal {risk_log.deal_id} not found")
            return None

        self.risk_logs[risk_log.risk_id] = risk_log
        
        # Update deal health
        deal.health_score = await self.get_deal_health_score(risk_log.deal_id)
        
        self.logger.info(f"Mock: Logged risk {risk_log.risk_id} for deal {risk_log.deal_id}")
        return risk_log

    async def query_pipeline_metrics(
        self,
        period_start: datetime,
        period_end: datetime,
        include_closed_deals: bool = False,
        owner_filter: Optional[str] = None,
        min_arr_threshold: int = 0
    ) -> Optional[PipelineMetrics]:
        """Query aggregated metrics from mock store."""
        # Filter deals
        deals = list(self.deals.values())
        
        if not include_closed_deals:
            deals = [d for d in deals if d.stage not in [
                DealStage.CLOSED_WON, DealStage.CLOSED_LOST
            ]]
        
        if owner_filter:
            deals = [d for d in deals if d.owner_email == owner_filter]
        
        deals = [d for d in deals if d.arr_value >= min_arr_threshold]
        
        # Aggregate metrics
        total_deals = len(deals)
        total_arr = sum(d.arr_value for d in deals)
        
        # Stage breakdown
        deal_stages = {}
        for stage in DealStage:
            count = sum(1 for d in deals if d.stage == stage)
            if count > 0:
                deal_stages[stage.value] = count
        
        # Weighted ARR
        weights = {
            DealStage.PROSPECTING: 0.10,
            DealStage.QUALIFICATION: 0.25,
            DealStage.DISCOVERY: 0.40,
            DealStage.PROPOSAL: 0.60,
            DealStage.PROCUREMENT: 0.80,
            DealStage.NEGOTIATION: 0.90,
        }
        weighted_arr = sum(
            d.arr_value * weights.get(d.stage, 0.5)
            for d in deals
        )
        weighted_arr = int(weighted_arr)
        
        # Average deal ARR
        average_deal_arr = (total_arr // total_deals) if total_deals > 0 else 0
        
        # Health scores
        health_scores = [d.health_score for d in deals]
        average_health = sum(health_scores) // len(health_scores) if health_scores else 50
        
        # At-risk deals
        at_risk = sum(1 for h in health_scores if h < 50)
        
        # Stalled deals
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        stalled = sum(1 for d in deals if d.updated_at < thirty_days_ago)
        
        # Win probability
        stage_prob = {
            DealStage.PROSPECTING: 10,
            DealStage.QUALIFICATION: 25,
            DealStage.DISCOVERY: 40,
            DealStage.PROPOSAL: 60,
            DealStage.PROCUREMENT: 75,
            DealStage.NEGOTIATION: 85,
        }
        win_prob = sum(stage_prob.get(d.stage, 50) for d in deals) // len(deals) if deals else 50
        
        metrics = PipelineMetrics(
            period_start=period_start,
            period_end=period_end,
            total_deals=total_deals,
            total_pipeline_arr=total_arr,
            weighted_arr=weighted_arr,
            average_deal_arr=average_deal_arr,
            deal_stages=deal_stages,
            win_probability=win_prob,
            average_health_score=average_health,
            at_risk_deals=at_risk,
            stalled_deals=stalled,
            forecast_confidence=80
        )
        
        self.logger.info(f"Mock: Queried pipeline metrics: {total_deals} deals, ${total_arr / 100:.2f} ARR")
        return metrics

    async def create_lead_entry(self, lead: LeadEntry) -> Optional[LeadEntry]:
        """Create lead in mock store."""
        self.leads[lead.lead_id] = lead
        self.logger.info(f"Mock: Created lead {lead.lead_id}")
        return lead

    async def get_account(self, account_id: str) -> Optional[Account]:
        """Retrieve account from mock store."""
        account = self.accounts.get(account_id)
        if account:
            self.logger.debug(f"Mock: Retrieved account {account_id}")
        else:
            self.logger.debug(f"Mock: Account {account_id} not found")
        return account

    async def create_account(
        self,
        name: str,
        industry: Optional[str] = None,
        company_size: Optional[str] = None,
        annual_revenue: Optional[int] = None
    ) -> Optional[Account]:
        """Create account in mock store."""
        account_id = f"acct-{str(uuid.uuid4())[:8]}"
        account = Account(
            id=account_id,
            name=name,
            industry=industry,
            company_size=company_size,
            annual_revenue=annual_revenue,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        self.accounts[account_id] = account
        self.logger.info(f"Mock: Created account {account_id}")
        return account
