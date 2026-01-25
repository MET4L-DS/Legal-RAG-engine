"""
Response Adapter Layer.

Transforms internal RAG output into frontend-safe response format.
Handles clarification detection, confidence scoring, and timeline extraction.
"""

import re
from typing import Optional

from .schemas import (
    FrontendResponse,
    ClarificationNeeded,
    ClarificationType,
    TierType,
    ConfidenceLevel,
    TimelineItem,
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
# TIMELINE EXTRACTION (A1-A3 from UPDATES.md)
# ============================================================================

# Stage name mapping for cleaner output
STAGE_DISPLAY_NAMES = {
    "fir": "FIR Filing",
    "medical_examination": "Medical Examination",
    "statement_recording": "Statement Recording",
    "investigation": "Investigation",
    "victim_rights": "Victim Rights",
    "police_duties": "Police Duties",
    "evidence_collection": "Evidence Collection",
    "rehabilitation": "Rehabilitation",
    "arrest": "Arrest",
    "charge_sheet": "Charge Sheet",
    "trial": "Trial",
    "general": "General Procedure",
}

# Action templates based on stage
STAGE_ACTIONS = {
    "fir": "File FIR at any police station",
    "medical_examination": "Medical examination of victim",
    "statement_recording": "Record victim's statement",
    "investigation": "Complete investigation",
    "victim_rights": "Inform victim of their rights",
    "police_duties": "Police must fulfill duties",
    "evidence_collection": "Collect and preserve evidence",
    "rehabilitation": "Provide rehabilitation support",
    "arrest": "Arrest of accused",
    "charge_sheet": "File charge sheet",
    "trial": "Court trial proceedings",
    "general": "Follow standard procedure",
}


def extract_timeline(rag_result: dict) -> list[TimelineItem]:
    """
    Extract timeline items from retrieved SOP/Evidence/General SOP blocks.
    
    This extracts structured timeline data from block METADATA, not LLM output.
    Only blocks with explicit time_limit fields are included.
    
    Args:
        rag_result: Raw output from LegalRAG.query()
        
    Returns:
        List of TimelineItem objects (may be empty)
    """
    timeline: list[TimelineItem] = []
    seen_stages: set[str] = set()  # Deduplicate by stage
    
    # Get retrieval results
    retrieval = rag_result.get("retrieval", {})
    
    # Process SOP blocks (Tier-1)
    for block in retrieval.get("sop_blocks", []):
        timeline_item = _extract_from_block(block, "SOP")
        if timeline_item and timeline_item.stage not in seen_stages:
            timeline.append(timeline_item)
            seen_stages.add(timeline_item.stage)
    
    # Process Evidence blocks (Tier-2)
    for block in retrieval.get("evidence_blocks", []):
        timeline_item = _extract_from_block(block, "Crime Scene Manual")
        if timeline_item and timeline_item.stage not in seen_stages:
            timeline.append(timeline_item)
            seen_stages.add(timeline_item.stage)
    
    # Process General SOP blocks (Tier-3)
    for block in retrieval.get("general_sop_blocks", []):
        timeline_item = _extract_from_block(block, "General SOP")
        if timeline_item and timeline_item.stage not in seen_stages:
            timeline.append(timeline_item)
            seen_stages.add(timeline_item.stage)
    
    # Sort by priority: immediately > hours > days > no deadline
    timeline.sort(key=lambda x: _deadline_priority(x.deadline))
    
    return timeline


def _extract_from_block(block: dict, source_prefix: str) -> Optional[TimelineItem]:
    """
    Extract a TimelineItem from a single retrieved block.
    
    Only returns a TimelineItem if the block has explicit timeline data.
    """
    metadata = block.get("metadata", {})
    
    # Check if block has time_limit (required for timeline)
    time_limit = metadata.get("time_limit")
    
    # Also check for deadline keywords in citation/title
    citation = block.get("citation", "")
    
    # Extract stage from metadata or citation
    stage = metadata.get("procedural_stage", "general")
    if stage == "general" and metadata.get("stage"):
        stage = metadata.get("stage")
    
    # Build legal basis from BNSS/BNS references
    legal_basis: list[str] = []
    
    # Add source citation
    if citation:
        legal_basis.append(citation)
    
    # Add BNSS sections if available
    bnss_sections = metadata.get("bnss_sections", [])
    for section in bnss_sections[:3]:  # Limit to 3 sections
        legal_basis.append(f"BNSS Section {section}")
    
    # Add BNS sections if available  
    bns_sections = metadata.get("bns_sections", [])
    for section in bns_sections[:2]:  # Limit to 2 sections
        legal_basis.append(f"BNS Section {section}")
    
    # Only create timeline item if we have a time_limit
    if not time_limit:
        # Check if deadline info in title/text
        if not _has_time_keywords(block.get("text", "")):
            return None
        # Infer "promptly" as default if time keywords present
        time_limit = "promptly"
    
    # Get action from metadata or generate from stage
    action = metadata.get("action", STAGE_ACTIONS.get(stage, f"Complete {stage} procedure"))
    
    # If we have a title, use it to make action more specific
    title = metadata.get("title", "")
    if title and len(title) < 80:
        action = title
    
    # Determine if mandatory (default true for SOP items)
    mandatory = metadata.get("mandatory", True)
    
    return TimelineItem(
        stage=stage,
        action=action,
        deadline=time_limit,
        mandatory=mandatory,
        legal_basis=legal_basis,
    )


def _has_time_keywords(text: str) -> bool:
    """Check if text contains time-related keywords."""
    time_patterns = [
        r'\d+\s*hours?',
        r'\d+\s*days?',
        r'within\s+\d+',
        r'immediately',
        r'without\s+delay',
        r'forthwith',
        r'at\s+once',
        r'promptly',
        r'as\s+soon\s+as',
    ]
    text_lower = text.lower()
    return any(re.search(pattern, text_lower) for pattern in time_patterns)


def _deadline_priority(deadline: Optional[str]) -> int:
    """
    Return sort priority for deadline (lower = more urgent).
    """
    if not deadline:
        return 100  # No deadline, lowest priority
    
    deadline_lower = deadline.lower()
    
    if "immediate" in deadline_lower or "forthwith" in deadline_lower:
        return 0
    elif "at once" in deadline_lower:
        return 1
    elif "hour" in deadline_lower:
        # Extract number of hours
        match = re.search(r'(\d+)', deadline_lower)
        if match:
            return 10 + int(match.group(1))
        return 15
    elif "day" in deadline_lower:
        match = re.search(r'(\d+)', deadline_lower)
        if match:
            return 50 + int(match.group(1))
        return 60
    elif "prompt" in deadline_lower:
        return 30
    else:
        return 80


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
    
    # 5. Extract timeline from retrieved blocks (A2 from UPDATES.md)
    timeline = extract_timeline(rag_result)
    
    # 6. Check for clarification needs
    clarification = detect_clarification_needed(query, tier, case_type)
    
    # 7. Get answer (None if clarification needed)
    answer = rag_result.get("answer") if not clarification else None
    
    # 8. Calculate confidence
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
        timeline=timeline,
        clarification_needed=clarification,
        confidence=confidence,
        api_version="1.0",
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
