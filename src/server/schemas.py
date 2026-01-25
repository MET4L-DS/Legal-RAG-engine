"""
Request and response schemas for the Legal RAG API.
"""

from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field


# ============================================================================
# Enums for Frontend Contract
# ============================================================================

class TierType(str, Enum):
    """Query tier types."""
    TIER1 = "tier1"
    TIER2_EVIDENCE = "tier2_evidence"
    TIER2_COMPENSATION = "tier2_compensation"
    TIER3 = "tier3"
    STANDARD = "standard"


class ConfidenceLevel(str, Enum):
    """Response confidence levels."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ClarificationType(str, Enum):
    """Types of clarification needed."""
    CASE_TYPE = "case_type"
    STAGE = "stage"


class AudienceType(str, Enum):
    """
    Target audience for a timeline item.
    
    This classifies WHO the timeline is primarily relevant for:
    - victim: Immediate action the victim needs to take/know
    - police: Police/IO duties (important but not victim's direct action)
    - court: Court/magistrate procedures (downstream)
    """
    VICTIM = "victim"
    POLICE = "police"
    COURT = "court"


# ============================================================================
# Timeline Schema (PART A of UPDATES.md)
# ============================================================================

class TimelineItem(BaseModel):
    """
    A single timeline item representing a procedural step with deadline.
    
    Timeline items are extracted from SOP/BNSS metadata, NOT from LLM output.
    They provide structured, deterministic procedural timelines.
    """
    
    stage: str = Field(
        ..., 
        description="Procedural stage (e.g., 'fir', 'medical_examination')"
    )
    action: str = Field(
        ..., 
        description="Human-readable action to take"
    )
    deadline: str | None = Field(
        None, 
        description="Time limit (e.g., '24 hours', 'immediately')"
    )
    mandatory: bool = Field(
        default=True, 
        description="Whether this is a legal obligation (anchor = always true)"
    )
    is_anchor: bool = Field(
        default=False,
        description="Whether this is a primary anchor timeline (vs secondary)"
    )
    audience: str = Field(
        default="victim",
        description="Target audience: 'victim' (immediate action), 'police' (IO duties), 'court' (downstream)"
    )
    legal_basis: list[str] = Field(
        default_factory=list, 
        description="BNSS/SOP references for this timeline item"
    )


class SystemNotice(BaseModel):
    """
    System notice for critical failures (e.g., missing timeline anchors).
    
    Used when the system cannot reliably determine mandatory information.
    Frontend should display this prominently.
    """
    
    type: str = Field(
        ..., 
        description="Notice type (ANCHOR_MISSING, RETRIEVAL_FAILED, etc.)"
    )
    stage: str | None = Field(
        None, 
        description="Which stage failed (if applicable)"
    )
    message: str = Field(
        ..., 
        description="Human-readable explanation"
    )


# ============================================================================
# Clarification Schema
# ============================================================================

class ClarificationNeeded(BaseModel):
    """Schema for when clarification is needed before processing."""
    
    type: ClarificationType = Field(..., description="Type of clarification needed")
    options: list[str] = Field(..., description="Predefined options to choose from")
    reason: str = Field(..., description="Why clarification is needed")


# ============================================================================
# Request Schemas
# ============================================================================

class RAGQueryRequest(BaseModel):
    """Request schema for RAG query endpoint."""
    
    query: str = Field(
        ...,
        description="The legal question to answer",
        min_length=1,
        max_length=2000,
        examples=["What is the punishment for murder?"]
    )
    no_llm: bool = Field(
        default=False,
        description="Skip LLM answer generation and return only retrieved context"
    )
    top_k: int = Field(
        default=5,
        description="Number of results to return per level",
        ge=1,
        le=20
    )


# ============================================================================
# Frontend-Safe Response Schema (Primary Contract)
# ============================================================================

class FrontendResponse(BaseModel):
    """
    Frontend-safe response schema.
    
    This is the PRIMARY API contract. Frontend should ONLY depend on this shape.
    Internal structures (retrieval, flags) are hidden from this response.
    """
    
    answer: Optional[str] = Field(
        None, 
        description="LLM-generated answer (null if no_llm=true or clarification needed)"
    )
    tier: TierType = Field(
        ..., 
        description="Which tier handled the query"
    )
    case_type: Optional[str] = Field(
        None, 
        description="Detected case type (rape, robbery, theft, etc.)"
    )
    stage: Optional[str] = Field(
        None, 
        description="Primary detected procedural stage (if any)"
    )
    citations: list[str] = Field(
        default_factory=list, 
        description="Legal citations used in the answer"
    )
    timeline: list[TimelineItem] = Field(
        default_factory=list,
        description="Structured procedural timeline with deadlines (extracted from SOP/BNSS metadata)"
    )
    clarification_needed: Optional[ClarificationNeeded] = Field(
        None, 
        description="If set, frontend should ask user for clarification"
    )
    system_notice: Optional[SystemNotice] = Field(
        None,
        description="Critical system notice (e.g., missing mandatory timeline anchor)"
    )
    confidence: ConfidenceLevel = Field(
        ..., 
        description="Confidence level of the response"
    )
    api_version: str = Field(
        default="1.0",
        description="API contract version"
    )


# ============================================================================
# Internal Response Schemas (for debugging/admin only)
# ============================================================================

class RetrievalItem(BaseModel):
    """A single retrieved item (subsection, SOP block, etc.)."""
    
    citation: str = Field(..., description="Legal citation reference")
    text: str = Field(..., description="Retrieved text content (truncated)")
    score: float = Field(..., description="Relevance score")
    level: str = Field(..., description="Hierarchy level")
    source_type: str = Field(..., description="Source type label")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")


class RetrievalResults(BaseModel):
    """All retrieval results organized by level."""
    
    documents: list[RetrievalItem] = Field(default_factory=list)
    chapters: list[RetrievalItem] = Field(default_factory=list)
    sections: list[RetrievalItem] = Field(default_factory=list)
    subsections: list[RetrievalItem] = Field(default_factory=list)
    sop_blocks: list[RetrievalItem] = Field(default_factory=list)
    evidence_blocks: list[RetrievalItem] = Field(default_factory=list)
    compensation_blocks: list[RetrievalItem] = Field(default_factory=list)
    general_sop_blocks: list[RetrievalItem] = Field(default_factory=list)


class TierInfo(BaseModel):
    """Information about which tier handled the query."""
    
    tier: str = Field(..., description="Which tier handled the query: standard, tier1, tier2_evidence, tier2_compensation, tier3")
    is_procedural: bool = Field(..., description="Whether query is procedural")
    case_type: Optional[str] = Field(None, description="Detected case type (rape, assault, etc.)")
    detected_stages: list[str] = Field(default_factory=list, description="Detected procedural stages")
    needs_evidence: bool = Field(default=False, description="Whether evidence context was included")
    needs_compensation: bool = Field(default=False, description="Whether compensation context was included")
    needs_general_sop: bool = Field(default=False, description="Whether general SOP context was included")
    general_crime_type: Optional[str] = Field(None, description="Detected general crime type")


class RAGQueryResponse(BaseModel):
    """
    Full response schema for RAG query endpoint (internal/debug).
    
    NOTE: Frontend should use FrontendResponse instead.
    This schema exposes internal structures for debugging.
    """
    
    question: str = Field(..., description="Original question")
    answer: Optional[str] = Field(None, description="LLM-generated answer (null if no_llm=true)")
    tier_info: TierInfo = Field(..., description="Tier routing information")
    retrieval: RetrievalResults = Field(..., description="Retrieved documents and blocks")
    citations: list[str] = Field(default_factory=list, description="Legal citations used")
    context_length: int = Field(..., description="Length of context sent to LLM")


# ============================================================================
# Health & Stats Schemas
# ============================================================================

class HealthResponse(BaseModel):
    """Response schema for health check endpoint."""
    
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    indices_loaded: bool = Field(..., description="Whether vector indices are loaded")
    llm_available: bool = Field(..., description="Whether LLM client is available")


class StatsResponse(BaseModel):
    """Response schema for stats endpoint."""
    
    documents: int = Field(..., description="Total indexed documents")
    chapters: int = Field(..., description="Total indexed chapters")
    sections: int = Field(..., description="Total indexed sections")
    subsections: int = Field(..., description="Total indexed subsections")
    sop_blocks: int = Field(..., description="Total SOP blocks (Tier-1)")
    evidence_blocks: int = Field(..., description="Total evidence blocks (Tier-2)")
    compensation_blocks: int = Field(..., description="Total compensation blocks (Tier-2)")
    general_sop_blocks: int = Field(..., description="Total general SOP blocks (Tier-3)")
    embedding_dim: int = Field(..., description="Embedding dimension")
    tier1_enabled: bool = Field(..., description="Tier-1 SOP support enabled")
    tier2_evidence_enabled: bool = Field(..., description="Tier-2 evidence support enabled")
    tier2_compensation_enabled: bool = Field(..., description="Tier-2 compensation support enabled")
    tier3_enabled: bool = Field(..., description="Tier-3 general SOP support enabled")


# ============================================================================
# Meta Schema (for frontend configuration)
# ============================================================================

class MetaResponse(BaseModel):
    """Response schema for meta endpoint - exposes supported values."""
    
    tiers: list[str] = Field(..., description="Supported tier types")
    case_types: list[str] = Field(..., description="Supported case types")
    stages: list[str] = Field(..., description="Supported procedural stages")
    confidence_levels: list[str] = Field(..., description="Possible confidence levels")


class ErrorResponse(BaseModel):
    """Response schema for error responses."""
    
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")
