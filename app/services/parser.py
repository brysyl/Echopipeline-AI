"""
LLM Parameter Parser Service

Parses natural language voice inputs into structured parameters for RevOps MCP tools.
Primary provider: AWS Bedrock (Claude 3 or Llama). Fallback: Groq API (Llama-3.3-70b).
Robust error handling with regex/keyword extraction fallback to ensure zero thrown exceptions.

Supports fuzzy extraction of deal stage, ARR, risk severity, lead metadata, and more.
"""

import logging
import os
import re
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from enum import Enum
import asyncio

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    BEDROCK = "bedrock"
    GROQ = "groq"
    FALLBACK = "fallback"


class ParserConfig(BaseModel):
    """Configuration for LLM parameter parser."""
    groq_api_key: Optional[str] = Field(None, description="Groq API key")
    aws_region: Optional[str] = Field(default="us-west-2", description="AWS region for Bedrock")
    bedrock_model_id: str = Field(default="anthropic.claude-3-sonnet-20240229-v1:0", description="Bedrock model ID")
    groq_model_id: str = Field(default="llama-3.3-70b-versatile", description="Groq model ID")
    timeout_seconds: int = Field(default=10, description="LLM call timeout in seconds")
    enable_bedrock: bool = Field(default=True, description="Enable Bedrock provider")
    enable_groq: bool = Field(default=True, description="Enable Groq provider")
    fallback_only: bool = Field(default=False, description="Use only regex/keyword fallback")

    @field_validator("groq_api_key", mode="before")
    @classmethod
    def load_groq_key(cls, v):
        """Load GROQ_API_KEY from environment if not provided."""
        return v or os.getenv("GROQ_API_KEY")

    @field_validator("aws_region", mode="before")
    @classmethod
    def load_aws_region(cls, v):
        """Load AWS_REGION from environment if not provided."""
        return v or os.getenv("AWS_REGION", "us-west-2")


class DealStageExtractionResult(BaseModel):
    """Extracted deal stage from voice input."""
    stage: Optional[str] = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reasoning: str = ""


class RiskSeverityExtractionResult(BaseModel):
    """Extracted risk severity from voice input."""
    severity: Optional[int] = Field(None, ge=1, le=5)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reasoning: str = ""


class LeadMetadataExtractionResult(BaseModel):
    """Extracted lead metadata from ambient notes."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    industry: Optional[str] = None
    budget_range: Optional[str] = None
    decision_timeline: Optional[str] = None
    interest_areas: List[str] = []
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class LLMParameterParser:
    """
    Parses natural language voice inputs into structured RevOps parameters.
    
    Multi-provider architecture:
    1. Primary: AWS Bedrock (Claude/Llama models)
    2. Secondary: Groq API (Llama-3.3-70b)
    3. Fallback: Regex/keyword extraction (no external calls)
    
    All methods handle failures gracefully without throwing exceptions.
    """

    def __init__(self, config: Optional[ParserConfig] = None):
        """
        Initialize LLM parameter parser.
        
        Args:
            config: ParserConfig with provider settings (uses env vars if not provided)
        """
        self.config = config or ParserConfig()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Initialize providers
        self.bedrock_client = None
        self.groq_client = None
        
        self._init_bedrock()
        self._init_groq()
        
        self.logger.info(
            f"LLMParameterParser initialized: "
            f"bedrock={self.config.enable_bedrock}, "
            f"groq={self.config.enable_groq}, "
            f"fallback_only={self.config.fallback_only}"
        )

    def _init_bedrock(self) -> None:
        """Initialize AWS Bedrock client."""
        if not self.config.enable_bedrock or self.config.fallback_only:
            self.logger.info("Bedrock provider disabled")
            return
        
        try:
            import boto3
            self.bedrock_client = boto3.client(
                "bedrock-runtime",
                region_name=self.config.aws_region
            )
            self.logger.info("Bedrock client initialized successfully")
        except Exception as e:
            self.logger.warning(f"Failed to initialize Bedrock client: {str(e)}")
            self.bedrock_client = None

    def _init_groq(self) -> None:
        """Initialize Groq API client."""
        if not self.config.enable_groq or self.config.fallback_only:
            self.logger.info("Groq provider disabled")
            return
        
        if not self.config.groq_api_key:
            self.logger.warning("Groq API key not provided, Groq provider disabled")
            return
        
        try:
            from groq import Groq
            self.groq_client = Groq(api_key=self.config.groq_api_key)
            self.logger.info("Groq client initialized successfully")
        except Exception as e:
            self.logger.warning(f"Failed to initialize Groq client: {str(e)}")
            self.groq_client = None

    async def extract_deal_stage_from_voice(
        self,
        voice_input: str
    ) -> DealStageExtractionResult:
        """
        Extract deal stage from natural language voice input.
        
        Args:
            voice_input: Natural language voice transcription
            
        Returns:
            DealStageExtractionResult with extracted stage and confidence
        """
        try:
            # Try LLM providers first
            if not self.config.fallback_only:
                if self.bedrock_client:
                    try:
                        result = await self._extract_stage_bedrock(voice_input)
                        if result.stage:
                            self.logger.info(f"Bedrock extracted stage: {result.stage}")
                            return result
                    except Exception as e:
                        self.logger.debug(f"Bedrock extraction failed: {str(e)}")

                if self.groq_client:
                    try:
                        result = await self._extract_stage_groq(voice_input)
                        if result.stage:
                            self.logger.info(f"Groq extracted stage: {result.stage}")
                            return result
                    except Exception as e:
                        self.logger.debug(f"Groq extraction failed: {str(e)}")

            # Fallback to regex/keyword extraction
            return self._extract_stage_fallback(voice_input)

        except Exception as e:
            self.logger.error(f"Error in extract_deal_stage_from_voice: {str(e)}")
            return DealStageExtractionResult(
                stage=None,
                confidence=0.0,
                reasoning="Extraction failed, no stage detected"
            )

    async def extract_risk_severity_from_voice(
        self,
        voice_input: str
    ) -> RiskSeverityExtractionResult:
        """
        Extract risk severity (1-5) from natural language voice input.
        
        Args:
            voice_input: Natural language voice transcription
            
        Returns:
            RiskSeverityExtractionResult with extracted severity and confidence
        """
        try:
            # Try LLM providers first
            if not self.config.fallback_only:
                if self.bedrock_client:
                    try:
                        result = await self._extract_severity_bedrock(voice_input)
                        if result.severity:
                            self.logger.info(f"Bedrock extracted severity: {result.severity}")
                            return result
                    except Exception as e:
                        self.logger.debug(f"Bedrock extraction failed: {str(e)}")

                if self.groq_client:
                    try:
                        result = await self._extract_severity_groq(voice_input)
                        if result.severity:
                            self.logger.info(f"Groq extracted severity: {result.severity}")
                            return result
                    except Exception as e:
                        self.logger.debug(f"Groq extraction failed: {str(e)}")

            # Fallback to regex/keyword extraction
            return self._extract_severity_fallback(voice_input)

        except Exception as e:
            self.logger.error(f"Error in extract_risk_severity_from_voice: {str(e)}")
            return RiskSeverityExtractionResult(
                severity=None,
                confidence=0.0,
                reasoning="Extraction failed, no severity detected"
            )

    async def extract_lead_metadata_from_notes(
        self,
        ambient_notes: str
    ) -> LeadMetadataExtractionResult:
        """
        Extract structured lead metadata from ambient notes.
        
        Args:
            ambient_notes: Raw ambient notes or voice transcription
            
        Returns:
            LeadMetadataExtractionResult with extracted contact and company info
        """
        try:
            # Try LLM providers first
            if not self.config.fallback_only:
                if self.bedrock_client:
                    try:
                        result = await self._extract_lead_metadata_bedrock(ambient_notes)
                        if result.first_name or result.company_name:
                            self.logger.info(f"Bedrock extracted lead metadata")
                            return result
                    except Exception as e:
                        self.logger.debug(f"Bedrock extraction failed: {str(e)}")

                if self.groq_client:
                    try:
                        result = await self._extract_lead_metadata_groq(ambient_notes)
                        if result.first_name or result.company_name:
                            self.logger.info(f"Groq extracted lead metadata")
                            return result
                    except Exception as e:
                        self.logger.debug(f"Groq extraction failed: {str(e)}")

            # Fallback to regex/keyword extraction
            return self._extract_lead_metadata_fallback(ambient_notes)

        except Exception as e:
            self.logger.error(f"Error in extract_lead_metadata_from_notes: {str(e)}")
            return LeadMetadataExtractionResult(confidence=0.0)

    async def _extract_stage_bedrock(self, voice_input: str) -> DealStageExtractionResult:
        """Extract deal stage using AWS Bedrock."""
        prompt = f"""Extract the deal pipeline stage from this voice input. 
Valid stages: Prospecting, Qualification, Discovery, Proposal, Procurement, Negotiation, Closed-Won, Closed-Lost

Voice input: "{voice_input}"

Respond with JSON:
{{
    "stage": "<stage or null>",
    "confidence": 0.0-1.0,
    "reasoning": "<brief explanation>"
}}"""

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.bedrock_client.invoke_model,
                    modelId=self.config.bedrock_model_id,
                    body=json.dumps({
                        "anthropic_version": "bedrock-2023-06-01",
                        "max_tokens": 256,
                        "messages": [
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ]
                    })
                ),
                timeout=self.config.timeout_seconds
            )

            result = json.loads(response["body"].read().decode())
            content = result.get("content", [{}])[0].get("text", "{}")
            data = json.loads(content)

            return DealStageExtractionResult(
                stage=data.get("stage"),
                confidence=float(data.get("confidence", 0.5)),
                reasoning=data.get("reasoning", "")
            )
        except asyncio.TimeoutError:
            self.logger.warning("Bedrock request timed out")
            raise
        except Exception as e:
            self.logger.error(f"Bedrock extraction error: {str(e)}")
            raise

    async def _extract_stage_groq(self, voice_input: str) -> DealStageExtractionResult:
        """Extract deal stage using Groq API."""
        prompt = f"""Extract the deal pipeline stage from this voice input. 
Valid stages: Prospecting, Qualification, Discovery, Proposal, Procurement, Negotiation, Closed-Won, Closed-Lost

Voice input: "{voice_input}"

Respond with JSON:
{{
    "stage": "<stage or null>",
    "confidence": 0.0-1.0,
    "reasoning": "<brief explanation>"
}}"""

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.groq_client.chat.completions.create,
                    model=self.config.groq_model_id,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.3,
                    max_tokens=256
                ),
                timeout=self.config.timeout_seconds
            )

            content = response.choices[0].message.content
            # Extract JSON from response (may be wrapped in markdown)
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if not json_match:
                raise ValueError("No JSON found in response")
            
            data = json.loads(json_match.group())

            return DealStageExtractionResult(
                stage=data.get("stage"),
                confidence=float(data.get("confidence", 0.5)),
                reasoning=data.get("reasoning", "")
            )
        except asyncio.TimeoutError:
            self.logger.warning("Groq request timed out")
            raise
        except Exception as e:
            self.logger.error(f"Groq extraction error: {str(e)}")
            raise

    def _extract_stage_fallback(self, voice_input: str) -> DealStageExtractionResult:
        """Fallback regex/keyword extraction for deal stage."""
        input_lower = voice_input.lower()
        
        stage_keywords = {
            "Prospecting": ["prospect", "lead", "outreach", "new opportunity"],
            "Qualification": ["qualify", "qualified", "discovery call", "understand needs"],
            "Discovery": ["discovery", "deep dive", "understand requirements", "needs analysis"],
            "Proposal": ["propose", "proposal", "quote", "estimate", "pricing"],
            "Procurement": ["procurement", "procurement process", "buy", "purchase"],
            "Negotiation": ["negotiate", "negotiation", "terms", "contract review"],
            "Closed-Won": ["closed", "won", "signed", "deal closed", "closed won"],
            "Closed-Lost": ["lost", "closed lost", "no deal"]
        }
        
        confidence = 0.0
        matched_stage = None
        
        for stage, keywords in stage_keywords.items():
            matches = sum(1 for kw in keywords if kw in input_lower)
            if matches > 0:
                stage_confidence = min(0.9, 0.5 + (matches * 0.15))
                if stage_confidence > confidence:
                    confidence = stage_confidence
                    matched_stage = stage
        
        return DealStageExtractionResult(
            stage=matched_stage,
            confidence=confidence,
            reasoning=f"Matched keyword-based extraction with confidence {confidence:.2f}"
        )

    async def _extract_severity_bedrock(self, voice_input: str) -> RiskSeverityExtractionResult:
        """Extract risk severity using AWS Bedrock."""
        prompt = f"""Extract the risk severity level (1-5) from this voice input.
1 = Low, 2 = Moderate, 3 = Medium, 4 = High, 5 = Critical

Voice input: "{voice_input}"

Respond with JSON:
{{
    "severity": <1-5 or null>,
    "confidence": 0.0-1.0,
    "reasoning": "<brief explanation>"
}}"""

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.bedrock_client.invoke_model,
                    modelId=self.config.bedrock_model_id,
                    body=json.dumps({
                        "anthropic_version": "bedrock-2023-06-01",
                        "max_tokens": 256,
                        "messages": [
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ]
                    })
                ),
                timeout=self.config.timeout_seconds
            )

            result = json.loads(response["body"].read().decode())
            content = result.get("content", [{}])[0].get("text", "{}")
            data = json.loads(content)

            severity = data.get("severity")
            if severity:
                severity = max(1, min(5, int(severity)))

            return RiskSeverityExtractionResult(
                severity=severity,
                confidence=float(data.get("confidence", 0.5)),
                reasoning=data.get("reasoning", "")
            )
        except asyncio.TimeoutError:
            self.logger.warning("Bedrock request timed out")
            raise
        except Exception as e:
            self.logger.error(f"Bedrock extraction error: {str(e)}")
            raise

    async def _extract_severity_groq(self, voice_input: str) -> RiskSeverityExtractionResult:
        """Extract risk severity using Groq API."""
        prompt = f"""Extract the risk severity level (1-5) from this voice input.
1 = Low, 2 = Moderate, 3 = Medium, 4 = High, 5 = Critical

Voice input: "{voice_input}"

Respond with JSON:
{{
    "severity": <1-5 or null>,
    "confidence": 0.0-1.0,
    "reasoning": "<brief explanation>"
}}"""

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.groq_client.chat.completions.create,
                    model=self.config.groq_model_id,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.3,
                    max_tokens=256
                ),
                timeout=self.config.timeout_seconds
            )

            content = response.choices[0].message.content
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if not json_match:
                raise ValueError("No JSON found in response")
            
            data = json.loads(json_match.group())

            severity = data.get("severity")
            if severity:
                severity = max(1, min(5, int(severity)))

            return RiskSeverityExtractionResult(
                severity=severity,
                confidence=float(data.get("confidence", 0.5)),
                reasoning=data.get("reasoning", "")
            )
        except asyncio.TimeoutError:
            self.logger.warning("Groq request timed out")
            raise
        except Exception as e:
            self.logger.error(f"Groq extraction error: {str(e)}")
            raise

    def _extract_severity_fallback(self, voice_input: str) -> RiskSeverityExtractionResult:
        """Fallback regex/keyword extraction for risk severity."""
        input_lower = voice_input.lower()
        
        severity_keywords = {
            5: ["critical", "blocker", "showstopper", "deal killer", "stop"],
            4: ["high", "serious", "major", "concerning", "urgent"],
            3: ["medium", "moderate", "significant", "notable"],
            2: ["low", "minor", "manageable", "small"],
            1: ["minimal", "negligible", "tiny"]
        }
        
        for severity in range(5, 0, -1):
            keywords = severity_keywords.get(severity, [])
            if any(kw in input_lower for kw in keywords):
                confidence = min(0.9, 0.5 + (0.1 * severity))
                return RiskSeverityExtractionResult(
                    severity=severity,
                    confidence=confidence,
                    reasoning=f"Matched keyword-based extraction for severity {severity}"
                )
        
        return RiskSeverityExtractionResult(
            severity=None,
            confidence=0.0,
            reasoning="No severity indicators detected"
        )

    async def _extract_lead_metadata_bedrock(self, ambient_notes: str) -> LeadMetadataExtractionResult:
        """Extract lead metadata using AWS Bedrock."""
        prompt = f"""Extract structured lead information from these ambient notes.

Ambient notes: "{ambient_notes}"

Respond with JSON:
{{
    "first_name": "<first name or null>",
    "last_name": "<last name or null>",
    "email": "<email or null>",
    "company_name": "<company name or null>",
    "job_title": "<job title or null>",
    "industry": "<industry or null>",
    "budget_range": "<budget range or null>",
    "decision_timeline": "<timeline or null>",
    "interest_areas": ["<topic1>", "<topic2>"],
    "confidence": 0.0-1.0
}}"""

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.bedrock_client.invoke_model,
                    modelId=self.config.bedrock_model_id,
                    body=json.dumps({
                        "anthropic_version": "bedrock-2023-06-01",
                        "max_tokens": 512,
                        "messages": [
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ]
                    })
                ),
                timeout=self.config.timeout_seconds
            )

            result = json.loads(response["body"].read().decode())
            content = result.get("content", [{}])[0].get("text", "{}")
            data = json.loads(content)

            return LeadMetadataExtractionResult(
                first_name=data.get("first_name"),
                last_name=data.get("last_name"),
                email=data.get("email"),
                company_name=data.get("company_name"),
                job_title=data.get("job_title"),
                industry=data.get("industry"),
                budget_range=data.get("budget_range"),
                decision_timeline=data.get("decision_timeline"),
                interest_areas=data.get("interest_areas", []),
                confidence=float(data.get("confidence", 0.5))
            )
        except asyncio.TimeoutError:
            self.logger.warning("Bedrock request timed out")
            raise
        except Exception as e:
            self.logger.error(f"Bedrock extraction error: {str(e)}")
            raise

    async def _extract_lead_metadata_groq(self, ambient_notes: str) -> LeadMetadataExtractionResult:
        """Extract lead metadata using Groq API."""
        prompt = f"""Extract structured lead information from these ambient notes.

Ambient notes: "{ambient_notes}"

Respond with JSON:
{{
    "first_name": "<first name or null>",
    "last_name": "<last name or null>",
    "email": "<email or null>",
    "company_name": "<company name or null>",
    "job_title": "<job title or null>",
    "industry": "<industry or null>",
    "budget_range": "<budget range or null>",
    "decision_timeline": "<timeline or null>",
    "interest_areas": ["<topic1>", "<topic2>"],
    "confidence": 0.0-1.0
}}"""

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.groq_client.chat.completions.create,
                    model=self.config.groq_model_id,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.3,
                    max_tokens=512
                ),
                timeout=self.config.timeout_seconds
            )

            content = response.choices[0].message.content
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if not json_match:
                raise ValueError("No JSON found in response")
            
            data = json.loads(json_match.group())

            return LeadMetadataExtractionResult(
                first_name=data.get("first_name"),
                last_name=data.get("last_name"),
                email=data.get("email"),
                company_name=data.get("company_name"),
                job_title=data.get("job_title"),
                industry=data.get("industry"),
                budget_range=data.get("budget_range"),
                decision_timeline=data.get("decision_timeline"),
                interest_areas=data.get("interest_areas", []),
                confidence=float(data.get("confidence", 0.5))
            )
        except asyncio.TimeoutError:
            self.logger.warning("Groq request timed out")
            raise
        except Exception as e:
            self.logger.error(f"Groq extraction error: {str(e)}")
            raise

    def _extract_lead_metadata_fallback(self, ambient_notes: str) -> LeadMetadataExtractionResult:
        """Fallback regex/keyword extraction for lead metadata."""
        result = LeadMetadataExtractionResult(confidence=0.4)
        
        # Extract email
        email_match = re.search(r'([a-zA-Z0-9._%\-+]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})', ambient_notes)
        if email_match:
            result.email = email_match.group(1)
        
        # Extract names (simple pattern: capitalized words)
        name_pattern = r'\b([A-Z][a-z]+)\s+([A-Z][a-z]+)\b'
        name_match = re.search(name_pattern, ambient_notes)
        if name_match:
            result.first_name = name_match.group(1)
            result.last_name = name_match.group(2)
        
        # Extract company names (pattern: "at <company>" or "<company> company")
        company_patterns = [
            r'at\s+([A-Z][a-zA-Z0-9\s&]+)',
            r'from\s+([A-Z][a-zA-Z0-9\s&]+)',
            r'at\s+the\s+([A-Z][a-zA-Z0-9\s&]+)'
        ]
        for pattern in company_patterns:
            company_match = re.search(pattern, ambient_notes)
            if company_match:
                result.company_name = company_match.group(1).strip()
                break
        
        # Extract job titles
        title_keywords = [
            "VP", "Director", "Manager", "Head", "Lead", "Officer", "Engineer",
            "Architect", "Specialist", "Analyst", "Coordinator"
        ]
        for keyword in title_keywords:
            if keyword.lower() in ambient_notes.lower():
                title_match = re.search(rf'(\w+\s+{keyword}\s+\w+|\w+\s+{keyword})', ambient_notes, re.IGNORECASE)
                if title_match:
                    result.job_title = title_match.group(0)
                    break
        
        # Extract budget indicators
        budget_keywords = {
            "<$10k": [r'\$[0-9]k', r'under.*10k'],
            "$10k-$50k": [r'10k.*50k', r'\$[0-9]{2}k'],
            "$50k-$100k": [r'50k.*100k', r'\$[0-9]{2,3}k'],
            "$100k-$500k": [r'100k.*500k', r'6 figure'],
            ">$500k": [r'over.*500k', r'million', r'7 figure']
        }
        for budget_range, patterns in budget_keywords.items():
            for pattern in patterns:
                if re.search(pattern, ambient_notes, re.IGNORECASE):
                    result.budget_range = budget_range
                    break
        
        # Extract industry
        industries = [
            "Technology", "SaaS", "Finance", "Healthcare", "Retail", "Manufacturing",
            "Automotive", "Education", "Real Estate", "Hospitality", "Enterprise"
        ]
        for industry in industries:
            if industry.lower() in ambient_notes.lower():
                result.industry = industry
                break
        
        # Extract decision timeline
        timeline_keywords = {
            "ASAP": ["urgent", "immediately", "right now"],
            "This Week": ["this week", "within days"],
            "This Month": ["this month", "end of month"],
            "Q4 2026": ["Q4", "fourth quarter", "end of year"],
            "Next Quarter": ["next quarter", "Q1"]
        }
        for timeline, keywords in timeline_keywords.items():
            for keyword in keywords:
                if keyword.lower() in ambient_notes.lower():
                    result.decision_timeline = timeline
                    break
        
        # Extract interest areas
        interest_keywords = ["automation", "analytics", "integration", "reporting", "forecasting", "pipeline"]
        result.interest_areas = [
            keyword for keyword in interest_keywords
            if keyword in ambient_notes.lower()
        ]
        
        return result
