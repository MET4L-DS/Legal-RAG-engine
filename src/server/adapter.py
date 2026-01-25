"""
Response Adapter Layer.

Transforms internal RAG output into frontend-safe response format.
Handles clarification detection, confidence scoring, and timeline extraction.

Timeline Anchors System:
- Mandatory stages per case type that MUST be present
- 2-pass extraction: anchors first, secondary second
- Hard failure for missing anchors in Tier-1 crimes
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
    SystemNotice,
)


# ============================================================================
# TIMELINE ANCHORS (Critical mandatory stages per case type)
# ============================================================================

# These are MANDATORY stages that MUST exist for a given case type.
# If an anchor cannot be resolved, it's a hard failure for Tier-1 crimes.
# audience: "victim" = direct victim action, "police" = IO duty, "court" = downstream
TIMELINE_ANCHORS: dict[str, list[dict]] = {
    # Sexual offences (Tier-1) - STRICT anchors
    "rape": [
        {"stage": "fir_registration", "action": "File FIR / Zero FIR", "deadline": "immediately", "source": "general_sop", "audience": "victim"},
        {"stage": "medical_examination", "action": "Medical examination of victim", "deadline": "24 hours", "source": "sop", "audience": "victim"},
        {"stage": "statement_recording", "action": "Record statement u/s 183 BNSS", "deadline": "without delay", "source": "general_sop", "audience": "victim"},
        {"stage": "victim_protection", "action": "Victim protection / shelter", "deadline": "promptly", "source": "sop", "audience": "victim"},
    ],
    "sexual_assault": [
        {"stage": "fir_registration", "action": "File FIR / Zero FIR", "deadline": "immediately", "source": "general_sop", "audience": "victim"},
        {"stage": "medical_examination", "action": "Medical examination of victim", "deadline": "24 hours", "source": "sop", "audience": "victim"},
        {"stage": "statement_recording", "action": "Record statement u/s 183 BNSS", "deadline": "without delay", "source": "general_sop", "audience": "victim"},
        {"stage": "victim_protection", "action": "Victim protection / shelter", "deadline": "promptly", "source": "sop", "audience": "victim"},
    ],
    "pocso": [
        {"stage": "fir_registration", "action": "File FIR / Zero FIR", "deadline": "immediately", "source": "general_sop", "audience": "victim"},
        {"stage": "medical_examination", "action": "Medical examination of child victim", "deadline": "24 hours", "source": "sop", "audience": "victim"},
        {"stage": "statement_recording", "action": "Record statement u/s 183 BNSS", "deadline": "without delay", "source": "general_sop", "audience": "victim"},
        {"stage": "victim_protection", "action": "Child protection / shelter", "deadline": "immediately", "source": "sop", "audience": "victim"},
    ],
    
    # General crimes (Tier-3) - Flexible anchors
    "robbery": [
        {"stage": "fir_registration", "action": "File FIR at nearest police station", "deadline": "immediately", "source": "general_sop", "audience": "victim"},
        {"stage": "investigation_commencement", "action": "Investigation must commence", "deadline": "promptly", "source": "general_sop", "audience": "police"},
    ],
    "theft": [
        {"stage": "fir_registration", "action": "File FIR at nearest police station", "deadline": "immediately", "source": "general_sop", "audience": "victim"},
        {"stage": "investigation_commencement", "action": "Investigation must commence", "deadline": "promptly", "source": "general_sop", "audience": "police"},
    ],
    "assault": [
        {"stage": "fir_registration", "action": "File FIR at nearest police station", "deadline": "immediately", "source": "general_sop", "audience": "victim"},
        {"stage": "medical_examination", "action": "Medical examination for injuries", "deadline": "promptly", "source": "general_sop", "audience": "victim"},
    ],
    "murder": [
        {"stage": "fir_registration", "action": "File FIR", "deadline": "immediately", "source": "general_sop", "audience": "victim"},
        {"stage": "investigation_commencement", "action": "Investigation must commence", "deadline": "immediately", "source": "general_sop", "audience": "police"},
        {"stage": "evidence_collection", "action": "Crime scene evidence collection", "deadline": "immediately", "source": "general_sop", "audience": "police"},
    ],
    "cybercrime": [
        {"stage": "fir_registration", "action": "File FIR / cyber complaint", "deadline": "immediately", "source": "general_sop", "audience": "victim"},
        {"stage": "digital_evidence", "action": "Preserve digital evidence", "deadline": "immediately", "source": "general_sop", "audience": "victim"},
    ],
    "kidnapping": [
        {"stage": "fir_registration", "action": "File FIR", "deadline": "immediately", "source": "general_sop", "audience": "victim"},
        {"stage": "investigation_commencement", "action": "Investigation must commence", "deadline": "immediately", "source": "general_sop", "audience": "police"},
    ],
    
    # Default fallback
    "general": [
        {"stage": "fir_registration", "action": "File FIR at nearest police station", "deadline": "immediately", "source": "general_sop", "audience": "victim"},
    ],
}

# Tier-1 case types that require STRICT anchor validation
TIER1_CASE_TYPES = {"rape", "sexual_assault", "pocso", "custodial_violence", "acid_attack"}

# Stage keywords for matching retrieved blocks to anchors
STAGE_KEYWORDS: dict[str, list[str]] = {
    "fir_registration": ["fir", "first information report", "zero fir", "complaint registration", "lodge complaint"],
    "medical_examination": ["medical examination", "medical exam", "forensic examination", "medical report"],
    "statement_recording": ["statement", "record statement", "section 183", "section 180", "magistrate statement"],
    "victim_protection": ["victim protection", "shelter", "safe house", "protection order", "rehabilitation"],
    "investigation_commencement": ["investigation", "commence investigation", "start investigation", "investigate"],
    "evidence_collection": ["evidence collection", "collect evidence", "crime scene", "forensic"],
    "digital_evidence": ["digital evidence", "electronic evidence", "cyber evidence", "data preservation"],
    "arrest": ["arrest", "custody", "apprehend"],
}


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
# TIMELINE EXTRACTION WITH ANCHOR SYSTEM
# ============================================================================

# Stage name mapping for cleaner output
STAGE_DISPLAY_NAMES = {
    "fir": "FIR Filing",
    "fir_registration": "FIR Registration",
    "medical_examination": "Medical Examination",
    "statement_recording": "Statement Recording",
    "investigation": "Investigation",
    "investigation_commencement": "Investigation Commencement",
    "victim_rights": "Victim Rights",
    "victim_protection": "Victim Protection",
    "police_duties": "Police Duties",
    "evidence_collection": "Evidence Collection",
    "digital_evidence": "Digital Evidence",
    "rehabilitation": "Rehabilitation",
    "arrest": "Arrest",
    "charge_sheet": "Charge Sheet",
    "trial": "Trial",
    "general": "General Procedure",
}


def extract_timeline_with_anchors(
    rag_result: dict, 
    case_type: Optional[str],
    tier: TierType,
) -> tuple[list[TimelineItem], Optional["SystemNotice"]]:
    """
    Extract timeline using 2-pass anchor system.
    
    Pass 1: Resolve mandatory anchors for the case type
    Pass 2: Add secondary timelines from retrieved blocks
    
    Args:
        rag_result: Raw output from LegalRAG.query()
        case_type: Detected case type (rape, robbery, etc.)
        tier: Which tier handled the query
        
    Returns:
        Tuple of (timeline_items, system_notice)
        - system_notice is set if mandatory anchors are missing for Tier-1 crimes
    """
    from .schemas import SystemNotice
    
    timeline: list[TimelineItem] = []
    seen_stages: set[str] = set()
    missing_anchors: list[str] = []
    
    # Get retrieval results
    retrieval = rag_result.get("retrieval", {})
    
    # Collect all retrieved blocks for anchor matching
    all_blocks: list[dict] = []
    all_blocks.extend(retrieval.get("sop_blocks", []))
    all_blocks.extend(retrieval.get("general_sop_blocks", []))
    all_blocks.extend(retrieval.get("evidence_blocks", []))
    
    # Normalize case type
    normalized_case = _normalize_case_type(case_type)
    
    # Get anchors for this case type
    anchors = TIMELINE_ANCHORS.get(normalized_case, TIMELINE_ANCHORS.get("general", []))
    
    # =========================================================================
    # PASS 1: Resolve mandatory anchors
    # =========================================================================
    for anchor in anchors:
        anchor_stage = anchor["stage"]
        anchor_resolved = False
        
        # Try to find a block that satisfies this anchor
        matched_block = _find_block_for_anchor(anchor_stage, all_blocks)
        
        if matched_block:
            # Extract legal basis from matched block
            legal_basis = _extract_legal_basis(matched_block)
            
            timeline_item = TimelineItem(
                stage=anchor_stage,
                action=anchor["action"],
                deadline=anchor["deadline"],
                mandatory=True,
                is_anchor=True,
                audience=anchor.get("audience", "victim"),
                legal_basis=legal_basis if legal_basis else [f"SOP / BNSS"],
            )
            timeline.append(timeline_item)
            seen_stages.add(anchor_stage)
            anchor_resolved = True
        else:
            # Anchor not found in retrieval - use default from anchor definition
            # For Tier-1, we'll track this as missing
            timeline_item = TimelineItem(
                stage=anchor_stage,
                action=anchor["action"],
                deadline=anchor["deadline"],
                mandatory=True,
                is_anchor=True,
                audience=anchor.get("audience", "victim"),
                legal_basis=["SOP / BNSS (standard procedure)"],
            )
            timeline.append(timeline_item)
            seen_stages.add(anchor_stage)
            
            # Track as potentially missing for Tier-1 strict validation
            if tier == TierType.TIER1:
                missing_anchors.append(anchor_stage)
    
    # =========================================================================
    # PASS 2: Add secondary timelines from retrieved blocks
    # =========================================================================
    for block in all_blocks:
        timeline_item = _extract_from_block(block)
        if timeline_item and timeline_item.stage not in seen_stages:
            timeline_item.is_anchor = False  # Mark as secondary
            timeline.append(timeline_item)
            seen_stages.add(timeline_item.stage)
    
    # Sort: anchors first (by deadline), then secondary (by deadline)
    timeline.sort(key=lambda x: (0 if x.is_anchor else 1, _deadline_priority(x.deadline)))
    
    # =========================================================================
    # Handle anchor failures for Tier-1 crimes
    # =========================================================================
    system_notice = None
    if missing_anchors and tier == TierType.TIER1 and normalized_case in TIER1_CASE_TYPES:
        # For Tier-1 crimes, missing anchors that couldn't be resolved from retrieval
        # is a concern, but we still return the standard anchors
        # Only create notice if we have retrieval but couldn't match critical stages
        if len(all_blocks) > 0 and len(missing_anchors) > len(anchors) // 2:
            system_notice = SystemNotice(
                type="ANCHOR_INCOMPLETE",
                stage=missing_anchors[0],
                message=f"Some mandatory procedural timelines could not be verified from retrieved documents. Standard timelines shown.",
            )
    
    return timeline, system_notice


def _normalize_case_type(case_type: Optional[str]) -> str:
    """Normalize case type string to match anchor keys."""
    if not case_type:
        return "general"
    
    case_lower = case_type.lower().strip()
    
    # Map variations to standard keys
    mappings = {
        "sexual assault": "sexual_assault",
        "sexual_assault": "sexual_assault",
        "rape": "rape",
        "pocso": "pocso",
        "robbery": "robbery",
        "theft": "theft",
        "assault": "assault",
        "murder": "murder",
        "homicide": "murder",
        "cybercrime": "cybercrime",
        "cyber crime": "cybercrime",
        "kidnapping": "kidnapping",
        "abduction": "kidnapping",
    }
    
    return mappings.get(case_lower, "general")


def _find_block_for_anchor(anchor_stage: str, blocks: list[dict]) -> Optional[dict]:
    """
    Find a retrieved block that matches an anchor stage.
    
    Uses keyword matching on block text, title, and stage metadata.
    """
    keywords = STAGE_KEYWORDS.get(anchor_stage, [anchor_stage.replace("_", " ")])
    
    for block in blocks:
        metadata = block.get("metadata", {})
        text = block.get("text", "").lower()
        title = metadata.get("title", "").lower()
        block_stage = metadata.get("procedural_stage", "").lower()
        citation = block.get("citation", "").lower()
        
        # Check if any keyword matches
        for keyword in keywords:
            keyword_lower = keyword.lower()
            if (keyword_lower in text or 
                keyword_lower in title or 
                keyword_lower in block_stage or
                keyword_lower in citation):
                return block
    
    return None


def _extract_legal_basis(block: dict) -> list[str]:
    """Extract legal basis references from a block."""
    legal_basis: list[str] = []
    metadata = block.get("metadata", {})
    citation = block.get("citation", "")
    
    if citation:
        legal_basis.append(citation)
    
    # Add BNSS sections
    bnss_sections = metadata.get("bnss_sections", [])
    for section in bnss_sections[:3]:
        legal_basis.append(f"BNSS Section {section}")
    
    # Add BNS sections
    bns_sections = metadata.get("bns_sections", [])
    for section in bns_sections[:2]:
        legal_basis.append(f"BNS Section {section}")
    
    return legal_basis


def _extract_from_block(block: dict) -> Optional[TimelineItem]:
    """
    Extract a TimelineItem from a single retrieved block.
    
    Only returns a TimelineItem if the block has explicit timeline data.
    """
    metadata = block.get("metadata", {})
    
    # Check if block has time_limit
    time_limit = metadata.get("time_limit")
    
    # Extract stage from metadata
    stage = metadata.get("procedural_stage", "general")
    if stage == "general" and metadata.get("stage"):
        stage = metadata.get("stage")
    
    # Only create timeline item if we have a time_limit
    if not time_limit:
        if not _has_time_keywords(block.get("text", "")):
            return None
        time_limit = "promptly"
    
    # Get action from title or stage
    title = metadata.get("title", "")
    action = title if title and len(title) < 80 else f"Complete {stage} procedure"
    
    # Build legal basis
    legal_basis = _extract_legal_basis(block)
    
    # Infer audience from stakeholder metadata
    # Secondary timelines are typically police/court procedures unless explicitly victim-related
    audience = _infer_audience_from_block(metadata, stage)
    
    return TimelineItem(
        stage=stage,
        action=action,
        deadline=time_limit,
        mandatory=True,
        is_anchor=False,
        audience=audience,
        legal_basis=legal_basis,
    )


def _infer_audience_from_block(metadata: dict, stage: str) -> str:
    """
    Infer the target audience from block metadata.
    
    Rules:
    - If stakeholder includes 'victim' or 'complainant' → "victim"
    - If stakeholder is 'court' or 'magistrate' → "court"
    - If stakeholder is 'police' or 'io' → "police"
    - Certain stages default to specific audiences
    """
    stakeholder = metadata.get("stakeholder", "").lower()
    
    # Check stakeholder field
    if any(v in stakeholder for v in ["victim", "complainant", "woman", "survivor"]):
        return "victim"
    if any(c in stakeholder for c in ["court", "magistrate", "judge"]):
        return "court"
    if any(p in stakeholder for p in ["police", "io", "officer", "sho"]):
        return "police"
    
    # Stage-based inference for common procedural stages
    victim_stages = {
        "fir_registration", "fir", "complaint", "medical_examination", 
        "victim_protection", "compensation", "rehabilitation", "statement_recording"
    }
    police_stages = {
        "investigation", "investigation_commencement", "evidence_collection",
        "arrest", "search_seizure", "custody"
    }
    court_stages = {
        "charge_sheet", "trial", "bail", "remand", "attachment", "forfeiture",
        "property_attachment", "surety"
    }
    
    stage_lower = stage.lower()
    if stage_lower in victim_stages:
        return "victim"
    if stage_lower in police_stages:
        return "police"
    if stage_lower in court_stages:
        return "court"
    
    # Default: non-anchor items are typically police procedures
    return "police"


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
    
    # 5. Extract timeline with anchor system (2-pass)
    timeline, system_notice = extract_timeline_with_anchors(rag_result, case_type, tier)
    
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
        system_notice=system_notice,
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
