"""
Response Adapter Layer.

Transforms internal RAG output into frontend-safe response format.
Handles clarification detection and confidence scoring.
"""

import re
from typing import Optional

from .schemas import (
    FrontendResponse,
    ClarificationNeeded,
    ClarificationType,
    TierType,
    ConfidenceLevel,
)


# ============================================================================
# AMBIGUOUS TERMS (Deterministic Clarification)
# ============================================================================

# Terms that have different legal procedures depending on context
AMBIGUOUS_TERMS = {
    "assault": {
        "type": ClarificationType.CASE_TYPE,
        "options": ["sexual_assault", "physical_assault"],
        "reason": "The term 'assault' has different legal procedures depending on whether it's sexual or physical assault",
    },
    "violence": {
        "type": ClarificationType.CASE_TYPE,
        "options": ["sexual_violence", "domestic_violence", "physical_violence"],
        "reason": "Different types of violence have different legal remedies and procedures",
    },
    "harassment": {
        "type": ClarificationType.CASE_TYPE,
        "options": ["sexual_harassment", "workplace_harassment", "cyber_harassment"],
        "reason": "Harassment cases follow different procedures based on the type",
    },
    "complaint": {
        "type": ClarificationType.STAGE,
        "options": ["file_new_complaint", "complaint_not_registered", "complaint_pending"],
        "reason": "Procedures differ based on whether you're filing a new complaint or following up",
    },
}

# Keywords that disambiguate assault
SEXUAL_CONTEXT_KEYWORDS = [
    "sexual", "rape", "molest", "touch", "grope", "pocso", "outraging modesty",
    "voyeurism", "stalking", "woman", "girl", "child"
]

PHYSICAL_CONTEXT_KEYWORDS = [
    "beat", "punch", "kick", "hit", "injury", "hurt", "bodily", "physical",
    "attack", "fight", "brawl"
]


# ============================================================================
# CLARIFICATION DETECTION
# ============================================================================

def detect_clarification_needed(query: str, tier: TierType, case_type: Optional[str]) -> Optional[ClarificationNeeded]:
    """
    Detect if clarification is needed for ambiguous terms.
    
    Rules:
    - Only ONE clarification per response
    - Only for predefined ambiguous terms
    - Skip if context already disambiguates
    
    Args:
        query: Original query text
        tier: Detected tier
        case_type: Detected case type (if any)
        
    Returns:
        ClarificationNeeded object if clarification is required, None otherwise
    """
    query_lower = query.lower()
    
    # If tier is already specific (tier1, tier2_*), no clarification needed
    if tier in (TierType.TIER1, TierType.TIER2_EVIDENCE, TierType.TIER2_COMPENSATION):
        return None
    
    # If case type is already detected, no clarification needed
    if case_type and case_type not in ("general", "unknown"):
        return None
    
    # Check for ambiguous terms
    for term, config in AMBIGUOUS_TERMS.items():
        if term in query_lower:
            # Check if context already disambiguates
            if term == "assault":
                if any(kw in query_lower for kw in SEXUAL_CONTEXT_KEYWORDS):
                    continue  # Sexual context is clear
                if any(kw in query_lower for kw in PHYSICAL_CONTEXT_KEYWORDS):
                    continue  # Physical context is clear
                    
            if term == "violence":
                if "sexual" in query_lower or "domestic" in query_lower:
                    continue  # Already specific
                    
            if term == "harassment":
                if any(x in query_lower for x in ["sexual", "workplace", "cyber", "online"]):
                    continue  # Already specific
            
            # Term is ambiguous, return clarification request
            return ClarificationNeeded(
                type=config["type"],
                options=config["options"],
                reason=config["reason"],
            )
    
    return None


# ============================================================================
# CONFIDENCE SCORING
# ============================================================================

def calculate_confidence(
    tier: TierType,
    case_type: Optional[str],
    detected_stages: list[str],
    has_citations: bool,
    has_answer: bool,
) -> ConfidenceLevel:
    """
    Calculate response confidence using deterministic heuristics.
    
    Confidence Levels:
    - HIGH: Clear tier routing + specific case type + citations
    - MEDIUM: General tier or weak intent signals
    - LOW: Ambiguous intent or no clear routing
    
    Args:
        tier: Which tier handled the query
        case_type: Detected case type
        detected_stages: List of detected procedural stages
        has_citations: Whether citations were found
        has_answer: Whether LLM generated an answer
        
    Returns:
        ConfidenceLevel enum value
    """
    score = 0
    
    # Specific tier routing is a strong signal
    if tier == TierType.TIER1:
        score += 3  # Sexual offence SOP - very specific
    elif tier == TierType.TIER2_EVIDENCE:
        score += 3  # Evidence manual - specific
    elif tier == TierType.TIER2_COMPENSATION:
        score += 3  # Compensation scheme - specific
    elif tier == TierType.TIER3:
        score += 2  # General SOP - moderately specific
    else:
        score += 1  # Standard tier - generic
    
    # Case type detection
    if case_type and case_type not in ("general", "unknown", None):
        score += 2
    
    # Stage detection (procedural queries)
    if detected_stages:
        score += 1
        if len(detected_stages) == 1:
            score += 1  # Single stage is more specific
    
    # Citations found
    if has_citations:
        score += 1
    
    # LLM answer generated
    if has_answer:
        score += 1
    
    # Map score to confidence level
    # Max possible: 3 (tier) + 2 (case) + 2 (stages) + 1 (citations) + 1 (answer) = 9
    if score >= 6:
        return ConfidenceLevel.HIGH
    elif score >= 3:
        return ConfidenceLevel.MEDIUM
    else:
        return ConfidenceLevel.LOW


# ============================================================================
# RESPONSE ADAPTER
# ============================================================================

def adapt_response(
    rag_result: dict,
    query: str,
) -> FrontendResponse:
    """
    Adapt internal RAG result to frontend-safe response format.
    
    This is the main adapter function. It:
    1. Extracts the tier from internal flags
    2. Selects the primary stage (if multiple detected)
    3. Checks for clarification needs
    4. Calculates confidence score
    5. Returns a clean, frontend-safe response
    
    Args:
        rag_result: Raw output from LegalRAG.query()
        query: Original query string
        
    Returns:
        FrontendResponse object
    """
    # 1. Determine tier
    tier = _determine_tier(rag_result)
    
    # 2. Extract case type
    case_type = rag_result.get("case_type") or rag_result.get("general_crime_type")
    
    # 3. Get primary stage (first detected stage, or None)
    detected_stages = rag_result.get("detected_stages", [])
    primary_stage = detected_stages[0] if detected_stages else None
    
    # 4. Get citations
    citations = rag_result.get("citations", [])
    
    # 5. Check for clarification needs
    clarification = detect_clarification_needed(query, tier, case_type)
    
    # 6. Get answer (None if clarification needed)
    answer = rag_result.get("answer") if not clarification else None
    
    # 7. Calculate confidence
    confidence = calculate_confidence(
        tier=tier,
        case_type=case_type,
        detected_stages=detected_stages,
        has_citations=len(citations) > 0,
        has_answer=answer is not None,
    )
    
    return FrontendResponse(
        answer=answer,
        tier=tier,
        case_type=case_type,
        stage=primary_stage,
        citations=citations,
        clarification_needed=clarification,
        confidence=confidence,
    )


def _determine_tier(result: dict) -> TierType:
    """Determine which tier handled the query based on result flags."""
    if result.get("needs_evidence"):
        return TierType.TIER2_EVIDENCE
    elif result.get("needs_compensation"):
        return TierType.TIER2_COMPENSATION
    elif result.get("is_procedural") and not result.get("needs_general_sop"):
        return TierType.TIER1
    elif result.get("needs_general_sop"):
        return TierType.TIER3
    else:
        return TierType.STANDARD
