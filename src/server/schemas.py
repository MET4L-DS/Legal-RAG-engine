"""
Request and response schemas for the Legal RAG API.
"""

from typing import Optional
from pydantic import BaseModel, Field


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
# Response Schemas
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
    """Response schema for RAG query endpoint."""
    
    question: str = Field(..., description="Original question")
    answer: Optional[str] = Field(None, description="LLM-generated answer (null if no_llm=true)")
    tier_info: TierInfo = Field(..., description="Tier routing information")
    retrieval: RetrievalResults = Field(..., description="Retrieved documents and blocks")
    citations: list[str] = Field(default_factory=list, description="Legal citations used")
    context_length: int = Field(..., description="Length of context sent to LLM")


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


class ErrorResponse(BaseModel):
    """Response schema for error responses."""
    
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")
