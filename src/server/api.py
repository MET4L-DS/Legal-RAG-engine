"""
API route definitions for Legal RAG Server.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from .config import get_settings, Settings
from .dependencies import get_rag, get_store_stats, is_llm_available, get_llm_client
from .adapter import adapt_response
from .schemas import (
    RAGQueryRequest,
    RAGQueryResponse,
    FrontendResponse,
    RetrievalResults,
    RetrievalItem,
    TierInfo,
    TierType,
    ConfidenceLevel,
    HealthResponse,
    StatsResponse,
    MetaResponse,
    ErrorResponse,
    SourceRequest,
    SourceResponse,
    SourceType,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _format_retrieval_item(item: dict) -> RetrievalItem:
    """Convert RAG result item to API response format."""
    return RetrievalItem(
        citation=item.get("citation", ""),
        text=item.get("text", ""),
        score=item.get("score", 0.0),
        level=item.get("level", ""),
        source_type=item.get("source_type", ""),
        metadata=item.get("metadata", {})
    )


# ============================================================================
# PRIMARY ENDPOINT (Frontend Contract)
# ============================================================================

@router.post(
    "/query",
    response_model=FrontendResponse,
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Query the Legal RAG System",
    description="""
Execute a legal query against the RAG system.

**This is the PRIMARY API contract for frontend applications.**

The system automatically detects query intent and routes to appropriate tier:
- **Tier-1**: Sexual offence procedures (SOP-backed)
- **Tier-2 Evidence**: Crime scene investigation standards
- **Tier-2 Compensation**: Victim relief and rehabilitation
- **Tier-3**: General citizen procedures for all crimes
- **Standard**: Traditional legal query (definitions, punishments, etc.)

Response includes:
- `answer`: LLM-generated response (may be null if clarification needed)
- `tier`: Which tier handled the query
- `case_type`: Detected crime/case type
- `stage`: Primary procedural stage (if applicable)
- `citations`: Legal citations used
- `clarification_needed`: If set, frontend should prompt user for clarification
- `confidence`: Response confidence level (high/medium/low)
"""
)
async def query_rag(
    request: RAGQueryRequest,
    rag=Depends(get_rag)
) -> FrontendResponse:
    """
    Query the legal document database.
    
    Returns a frontend-safe response with clarification and confidence scoring.
    """
    try:
        logger.info(f"Processing query: {request.query[:100]}...")
        
        # Execute RAG query
        result = rag.query(
            question=request.query,
            generate_answer=not request.no_llm
        )
        
        # Get LLM client for sentence attribution
        llm_client = get_llm_client()
        
        # Adapt to frontend-safe response (includes sentence attribution)
        response = adapt_response(result, request.query, llm_client=llm_client)
        
        logger.info(
            f"Query completed - Tier: {response.tier.value}, "
            f"Confidence: {response.confidence.value}, "
            f"Clarification: {'Yes' if response.clarification_needed else 'No'}"
        )
        
        return response
        
    except Exception as e:
        logger.exception(f"Error processing query: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "query_error", "message": str(e)}
        )


# ============================================================================
# DEBUG ENDPOINT (Internal/Admin Only)
# ============================================================================

def _determine_tier(result: dict) -> str:
    """Determine which tier handled the query based on result flags."""
    if result.get("needs_evidence"):
        return "tier2_evidence"
    elif result.get("needs_compensation"):
        return "tier2_compensation"
    elif result.get("is_procedural") and not result.get("needs_general_sop"):
        return "tier1"
    elif result.get("needs_general_sop"):
        return "tier3"
    else:
        return "standard"


@router.post(
    "/query/debug",
    response_model=RAGQueryResponse,
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Query with Debug Info (Internal)",
    description="Returns full internal retrieval details. For debugging only.",
    include_in_schema=False,  # Hide from public docs
)
async def query_rag_debug(
    request: RAGQueryRequest,
    rag=Depends(get_rag)
) -> RAGQueryResponse:
    """
    Query with full debug information.
    
    This endpoint exposes internal structures for debugging.
    NOT intended for frontend use.
    """
    try:
        result = rag.query(
            question=request.query,
            generate_answer=not request.no_llm
        )
        
        # Build retrieval results
        retrieval = RetrievalResults(
            documents=[_format_retrieval_item(r) for r in result["retrieval"]["documents"]],
            chapters=[_format_retrieval_item(r) for r in result["retrieval"]["chapters"]],
            sections=[_format_retrieval_item(r) for r in result["retrieval"]["sections"]],
            subsections=[_format_retrieval_item(r) for r in result["retrieval"]["subsections"][:request.top_k]],
            sop_blocks=[_format_retrieval_item(r) for r in result["retrieval"]["sop_blocks"]],
            evidence_blocks=[_format_retrieval_item(r) for r in result["retrieval"]["evidence_blocks"]],
            compensation_blocks=[_format_retrieval_item(r) for r in result["retrieval"]["compensation_blocks"]],
            general_sop_blocks=[_format_retrieval_item(r) for r in result["retrieval"]["general_sop_blocks"]],
        )
        
        # Build tier info
        tier_info = TierInfo(
            tier=_determine_tier(result),
            is_procedural=result.get("is_procedural", False),
            case_type=result.get("case_type"),
            detected_stages=result.get("detected_stages", []),
            needs_evidence=result.get("needs_evidence", False),
            needs_compensation=result.get("needs_compensation", False),
            needs_general_sop=result.get("needs_general_sop", False),
            general_crime_type=result.get("general_crime_type"),
        )
        
        return RAGQueryResponse(
            question=result["question"],
            answer=result.get("answer"),
            tier_info=tier_info,
            retrieval=retrieval,
            citations=result.get("citations", []),
            context_length=len(result.get("context", "") or ""),
        )
        
    except Exception as e:
        logger.exception(f"Error processing debug query: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "query_error", "message": str(e)}
        )


# ============================================================================
# META & HEALTH ENDPOINTS
# ============================================================================

@router.get(
    "/meta",
    response_model=MetaResponse,
    summary="API Metadata",
    description="Get supported values for tiers, case types, and stages. Frontend can use this for validation.",
)
async def get_meta() -> MetaResponse:
    """Get API metadata - supported tiers, case types, and stages."""
    return MetaResponse(
        tiers=[t.value for t in TierType],
        case_types=[
            "rape", "sexual_assault", "robbery", "theft", "assault",
            "murder", "cybercrime", "cheating", "extortion", "kidnapping", "general"
        ],
        stages=[
            "pre_fir", "fir", "investigation", "medical_examination",
            "statement_recording", "evidence_collection", "arrest",
            "charge_sheet", "trial", "victim_rights", "police_duties"
        ],
        confidence_levels=[c.value for c in ConfidenceLevel],
    )


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Check if the service is healthy and indices are loaded."
)
async def health_check(
    settings: Annotated[Settings, Depends(get_settings)]
) -> HealthResponse:
    """Check service health status."""
    try:
        # Try to get RAG instance (will be None if not initialized)
        from .dependencies import _is_initialized
        
        return HealthResponse(
            status="healthy" if _is_initialized else "initializing",
            version=settings.app_version,
            indices_loaded=_is_initialized,
            llm_available=is_llm_available(),
        )
    except Exception as e:
        logger.exception(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            version=settings.app_version,
            indices_loaded=False,
            llm_available=False,
        )


@router.get(
    "/stats",
    response_model=StatsResponse,
    responses={
        503: {"model": ErrorResponse, "description": "Service not ready"}
    },
    summary="Index Statistics",
    description="Get statistics about the indexed documents."
)
async def get_stats(
    rag=Depends(get_rag)
) -> StatsResponse:
    """Get index statistics."""
    try:
        stats = get_store_stats()
        
        return StatsResponse(
            documents=stats.get("documents", 0),
            chapters=stats.get("chapters", 0),
            sections=stats.get("sections", 0),
            subsections=stats.get("subsections", 0),
            sop_blocks=stats.get("sop_blocks", 0),
            evidence_blocks=stats.get("evidence_blocks", 0),
            compensation_blocks=stats.get("compensation_blocks", 0),
            general_sop_blocks=stats.get("general_sop_blocks", 0),
            embedding_dim=stats.get("embedding_dim", 384),
            tier1_enabled=stats.get("sop_blocks", 0) > 0,
            tier2_evidence_enabled=stats.get("evidence_blocks", 0) > 0,
            tier2_compensation_enabled=stats.get("compensation_blocks", 0) > 0,
            tier3_enabled=stats.get("general_sop_blocks", 0) > 0,
        )
    except Exception as e:
        logger.exception(f"Error getting stats: {e}")
        raise HTTPException(
            status_code=503,
            detail={"error": "service_not_ready", "message": str(e)}
        )


# ============================================================================
# SOURCE FETCH ENDPOINT (for citation → view source)
# ============================================================================

@router.post(
    "/source",
    response_model=SourceResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Source not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Fetch Source Content",
    description="""
Fetch verbatim source content for a citation.

**This endpoint returns exact source text - NO LLM summarization.**

Use this when a user clicks on a citation to view the original source.
The response includes:
- `content`: Verbatim text from the source document
- `title`: Section/block title
- `legal_references`: Related legal citations
- `metadata`: Additional context (stage, stakeholders, time_limit, etc.)

**Source Types:**
- `general_sop`: BPR&D General SOP blocks (GSOP_001, etc.)
- `sop`: MHA Rape SOP blocks
- `bnss`: BNSS sections (Section 183, etc.)
- `bns`: BNS sections
- `bsa`: BSA sections
- `evidence`: Crime Scene Manual blocks
- `compensation`: NALSA Compensation blocks
"""
)
async def fetch_source(
    request: SourceRequest,
    rag=Depends(get_rag)
) -> SourceResponse:
    """
    Fetch verbatim source content for a citation.
    
    No LLM involved - returns exact parsed content.
    
    Optionally pass `highlight_snippet` (from the citation's context_snippet)
    to get highlight offsets for auto-scrolling and text highlighting.
    """
    from .source_fetcher import fetch_source_content
    
    try:
        result = fetch_source_content(
            source_type=request.source_type,
            source_id=request.source_id,
            highlight_snippet=request.highlight_snippet,
        )
        
        if result is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "source_not_found",
                    "message": f"Source '{request.source_id}' not found in {request.source_type.value}"
                }
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error fetching source: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "source_fetch_error", "message": str(e)}
        )
