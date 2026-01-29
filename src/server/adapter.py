"""
Response Adapter Layer.

Transforms internal RAG output into frontend-safe response format.
Handles clarification detection, confidence scoring, and timeline extraction.

Timeline Anchors System:
- Mandatory stages per case type that MUST be present
- 2-pass extraction: anchors first, secondary second
- Hard failure for missing anchors in Tier-1 crimes

Span-Based Attribution (Option B):
- Answer units classified as verbatim/derived
- Span resolution for verbatim quotes
- Only verbatim units can be highlighted
"""

import logging
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
    StructuredCitation,
    SourceType,
    AnswerSentence,
    SentenceCitations,
    # Span-based attribution
    SourceSpanSchema,
    AnswerUnitSchema,
    AnswerUnitsResponse,
)
from .sentence_attribution import compute_sentence_attribution
from .answer_units import (
    AnswerUnit,
    SourceSpan,
    ChunkWithOffsets,
    resolve_all_spans,
    chunks_from_retrieval_result,
)

logger = logging.getLogger(__name__)


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
    anchors_resolved: bool = True,
    has_system_notice: bool = False,
    clarification_needed: bool = False,
    timeline_count: int = 0,
) -> ConfidenceLevel:
    """
    Calculate response confidence using deterministic anchor-based rules.
    
    Confidence Rules (hardened):
    - HIGH: All anchors resolved + citations present + answer generated
    - MEDIUM: Anchors resolved, but weak secondary coverage (few citations/timelines)
    - LOW: Anchor missing OR clarification needed OR system notice
    
    Args:
        tier: Which tier handled the query
        case_type: Detected case type
        detected_stages: List of detected procedural stages
        has_citations: Whether citations were found
        has_answer: Whether LLM generated an answer
        anchors_resolved: Whether all mandatory anchors were resolved
        has_system_notice: Whether a system notice was generated (anchor failure)
        clarification_needed: Whether clarification was requested
        timeline_count: Number of timeline items extracted
        
    Returns:
        ConfidenceLevel enum value
    """
    # Rule 1: LOW if anchor missing OR clarification needed OR system notice
    if not anchors_resolved or clarification_needed or has_system_notice:
        return ConfidenceLevel.LOW
    
    # Rule 2: HIGH if all anchors resolved + citations + answer
    if anchors_resolved and has_citations and has_answer:
        # Additional check: need some secondary coverage for HIGH
        if timeline_count >= 2 or tier in (TierType.TIER1, TierType.TIER2_EVIDENCE, TierType.TIER2_COMPENSATION):
            return ConfidenceLevel.HIGH
    
    # Rule 3: MEDIUM - anchors resolved but weak secondary coverage
    # (missing citations, few timelines, or no answer)
    return ConfidenceLevel.MEDIUM


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
    llm_client=None,
) -> FrontendResponse:
    """
    Adapt internal RAG result to frontend-safe response format.
    
    This is the main adapter function. It:
    1. Extracts the tier from internal flags
    2. Selects the primary stage (if multiple detected)
    3. Checks for clarification needs
    4. Calculates confidence score
    5. Processes answer units with span resolution (Option B)
    6. Falls back to sentence-level citation mapping if no answer units
    7. Returns a clean, frontend-safe response
    
    Args:
        rag_result: Raw output from LegalRAG.query()
        query: Original query string
        llm_client: Optional LLM client for sentence attribution
        
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
    
    # 4. Get structured citations (new format) or fallback to legacy
    structured_citations = _convert_to_structured_citations(rag_result)
    
    # 5. Extract timeline with anchor system (2-pass)
    timeline, system_notice = extract_timeline_with_anchors(rag_result, case_type, tier)
    
    # 6. Check for clarification needs
    clarification = detect_clarification_needed(query, tier, case_type)
    
    # 7. Get answer (None if clarification needed)
    answer = rag_result.get("answer") if not clarification else None
    
    # 8. Calculate confidence (anchor-based hardened rules)
    confidence = calculate_confidence(
        tier=tier,
        case_type=case_type,
        detected_stages=detected_stages,
        has_citations=len(structured_citations) > 0,
        has_answer=answer is not None,
        anchors_resolved=(system_notice is None),  # No notice means anchors OK
        has_system_notice=(system_notice is not None),
        clarification_needed=(clarification is not None),
        timeline_count=len(timeline),
    )
    
    # 9. Process answer units (Option B - span-based attribution)
    answer_units_response = None
    raw_answer_units = rag_result.get("answer_units")
    
    if raw_answer_units and not clarification:
        # Get threshold from results if present, otherwise default to 0.6
        min_cit_score = rag_result.get("min_citation_score", 0.6)
        
        answer_units_response = _process_answer_units(raw_answer_units, rag_result, min_citation_score=min_cit_score)
        if answer_units_response:
            logger.info(
                f"[UNITS] Processed {len(answer_units_response.units)} answer units "
                f"({answer_units_response.verbatim_count} verbatim, {answer_units_response.derived_count} derived)"
            )
    
    # 10. Compute sentence-level citation mapping (fallback if no answer units)
    sentence_citations = None
    if answer and structured_citations and not answer_units_response:
        # Convert StructuredCitation to dict for sentence attribution
        cit_dicts = [
            {
                "source_type": cit.source_type.value,
                "source_id": cit.source_id,
                "display": cit.display,
                "context_snippet": cit.context_snippet,
                "relevance_score": cit.relevance_score,
            }
            for cit in structured_citations
        ]
        
        # Get threshold from results if present, otherwise default to 0.6
        min_cit_score = rag_result.get("min_citation_score", 0.6)
        
        attribution_result = compute_sentence_attribution(
            answer=answer,
            structured_citations=cit_dicts,
            llm_client=llm_client,
            min_citation_score=min_cit_score,
        )
        
        if attribution_result:
            sentence_citations = SentenceCitations(
                sentences=[
                    AnswerSentence(sid=s["sid"], text=s["text"])
                    for s in attribution_result["sentences"]
                ],
                mapping=attribution_result["mapping"]
            )
            logger.info(f"[SENTENCE] Sentence citations computed: {len(sentence_citations.sentences)} sentences")
    
    return FrontendResponse(
        answer=answer,
        tier=tier,
        case_type=case_type,
        stage=primary_stage,
        citations=structured_citations,
        timeline=timeline,
        clarification_needed=clarification,
        confidence=confidence,
        api_version="2.0",
        system_notice=system_notice,
        sentence_citations=sentence_citations,
        answer_units=answer_units_response,
    )


def _process_answer_units(
    raw_units: list[dict],
    rag_result: dict,
    min_citation_score: float = 0.6
) -> Optional[AnswerUnitsResponse]:
    """
    Process raw answer units from RAG: resolve spans and convert to schema.
    
    This implements span resolution from Option B in UPDATES.md:
    - For verbatim units, find exact quote in retrieved chunks
    - If quote not found, downgrade to derived
    - Convert to Pydantic schema for API response
    """
    if not raw_units:
        return None
    
    try:
        # Convert raw dicts to AnswerUnit objects
        units = []
        for u in raw_units:
            unit = AnswerUnit(
                id=u.get("id", f"S{len(units)+1}"),
                text=u.get("text", ""),
                kind=u.get("kind", "derived"),
                quote=u.get("quote"),
                supporting_sources=u.get("supporting_sources", [])
            )
            units.append(unit)
        
        # Convert retrieval results to chunks for span resolution (filtering by score)
        chunks = chunks_from_retrieval_result(rag_result, min_score=min_citation_score)
        
        # Resolve spans for verbatim units
        if chunks:
            units = resolve_all_spans(units, chunks)
        
        # Convert to schema
        schema_units = []
        for unit in units:
            schema_unit = AnswerUnitSchema(
                id=unit.id,
                text=unit.text,
                kind=unit.kind,
                source_spans=[
                    SourceSpanSchema(
                        doc_id=span.doc_id,
                        section_id=span.section_id,
                        start_char=span.start_char,
                        end_char=span.end_char,
                        quote=span.quote
                    )
                    for span in unit.source_spans
                ],
                supporting_sources=unit.supporting_sources
            )
            schema_units.append(schema_unit)
        
        return AnswerUnitsResponse(units=schema_units)
        
    except Exception as e:
        logger.error(f"[UNITS] Failed to process answer units: {e}")
        return None


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


# Minimum relevance score for citations to be included
# Citations below this threshold are filtered out to reduce noise
MIN_RELEVANCE_THRESHOLD = 0.35


def _convert_to_structured_citations(rag_result: dict) -> list[StructuredCitation]:
    """
    Convert RAG result citations to structured format.
    
    Tries to use pre-built structured_citations from retrieval layer.
    Falls back to parsing legacy string citations if needed.
    
    Citations are:
    1. Filtered by minimum relevance threshold
    2. Sorted by relevance score (highest first)
    """
    # First, try to use pre-built structured citations from retrieval
    structured_data = rag_result.get("structured_citations", [])
    
    if structured_data:
        logger.debug(f"[CITATION] Using {len(structured_data)} pre-built structured citations")
        citations = []
        for item in structured_data:
            try:
                # Convert StructuredCitationData (dataclass) to StructuredCitation (Pydantic)
                source_type_str = item.get("source_type") if isinstance(item, dict) else item.source_type
                source_id = item.get("source_id") if isinstance(item, dict) else item.source_id
                display = item.get("display") if isinstance(item, dict) else item.display
                context_snippet = item.get("context_snippet") if isinstance(item, dict) else getattr(item, "context_snippet", None)
                relevance_score = item.get("relevance_score") if isinstance(item, dict) else getattr(item, "relevance_score", None)
                
                # Skip if source_id is empty (can't fetch without ID)
                if not source_id:
                    display_preview = (display[:50] + "...") if display else "(no display)"
                    logger.warning(f"[CITATION] Skipping citation with empty source_id: {display_preview}")
                    continue
                
                # Skip if display is missing
                if not display:
                    logger.warning(f"[CITATION] Skipping citation with empty display: {source_type_str}/{source_id}")
                    continue
                
                # Filter by minimum relevance threshold (if score is available)
                if relevance_score is not None and relevance_score < MIN_RELEVANCE_THRESHOLD:
                    logger.debug(f"[CITATION] Filtering low-relevance citation ({relevance_score:.2f}): {source_id}")
                    continue
                
                citations.append(StructuredCitation(
                    source_type=SourceType(source_type_str),
                    source_id=source_id,
                    display=display,
                    context_snippet=context_snippet,
                    relevance_score=relevance_score,
                ))
                display_preview = (display[:50] + "...") if len(display) > 50 else display
                logger.debug(f"[CITATION] ✓ {source_type_str}/{source_id}: {display_preview}")
            except (ValueError, KeyError, AttributeError) as e:
                # Skip malformed citations
                logger.warning(f"[CITATION] Skipping malformed citation: {e}")
                continue
        
        # Sort by relevance score (highest first)
        citations.sort(key=lambda c: c.relevance_score or 0.0, reverse=True)
        
        logger.info(f"[CITATION] Converted {len(citations)} structured citations")
        return citations
    
    # Fallback: parse legacy string citations
    legacy_citations = rag_result.get("citations", [])
    logger.debug(f"[CITATION] Falling back to parsing {len(legacy_citations)} legacy citations")
    return _parse_legacy_citations(legacy_citations)


def _parse_legacy_citations(citations: list[str]) -> list[StructuredCitation]:
    """
    Parse legacy string citations into structured format.
    
    This is a fallback for backward compatibility.
    Best-effort parsing - may not work for all citation formats.
    """
    result = []
    
    for cit in citations:
        structured = _parse_single_citation(cit)
        if structured:
            result.append(structured)
    
    return result


def _parse_single_citation(citation: str) -> StructuredCitation | None:
    """Parse a single citation string into structured format."""
    import re
    
    text_upper = citation.upper()
    source_type: SourceType | None = None
    source_id = ""
    display = citation
    
    # Try to determine source type and extract ID
    if "BNSS" in text_upper:
        source_type = SourceType.BNSS
        # Extract section number: "Section 183", "BNSS_2023 - Chapter XIII - Section 183"
        section_match = re.search(r'Section\s+(\d+[A-Za-z]*)', citation, re.IGNORECASE)
        if section_match:
            source_id = section_match.group(1)
            display = f"BNSS Section {source_id}"
    
    elif "BNS" in text_upper and "BNSS" not in text_upper:
        source_type = SourceType.BNS
        section_match = re.search(r'Section\s+(\d+[A-Za-z]*)', citation, re.IGNORECASE)
        if section_match:
            source_id = section_match.group(1)
            display = f"BNS Section {source_id}"
    
    elif "BSA" in text_upper:
        source_type = SourceType.BSA
        section_match = re.search(r'Section\s+(\d+[A-Za-z]*)', citation, re.IGNORECASE)
        if section_match:
            source_id = section_match.group(1)
            display = f"BSA Section {source_id}"
    
    elif "GSOP" in text_upper or "GENERAL SOP" in text_upper:
        source_type = SourceType.GENERAL_SOP
        # Try to extract GSOP_XXX pattern
        gsop_match = re.search(r'(GSOP_\d+)', citation, re.IGNORECASE)
        if gsop_match:
            source_id = gsop_match.group(1).upper()
        else:
            # Can't reliably extract ID from title-only citation
            # Use the title as a fallback display but mark source_id as unknown
            source_id = ""
        display = citation[:100] + "..." if len(citation) > 100 else citation
    
    elif "SOP" in text_upper:
        source_type = SourceType.SOP
        sop_match = re.search(r'(SOP_[A-Z]+_\d+)', citation, re.IGNORECASE)
        if sop_match:
            source_id = sop_match.group(1).upper()
        display = citation[:100] + "..." if len(citation) > 100 else citation
    
    elif "EVIDENCE" in text_upper or "DFS" in text_upper or "CRIME SCENE" in text_upper:
        source_type = SourceType.EVIDENCE
        evid_match = re.search(r'(EVID_\d+)', citation, re.IGNORECASE)
        if evid_match:
            source_id = evid_match.group(1).upper()
        display = citation[:100] + "..." if len(citation) > 100 else citation
    
    elif "COMPENSATION" in text_upper or "NALSA" in text_upper:
        source_type = SourceType.COMPENSATION
        comp_match = re.search(r'(COMP_\d+)', citation, re.IGNORECASE)
        if comp_match:
            source_id = comp_match.group(1).upper()
        display = citation[:100] + "..." if len(citation) > 100 else citation
    
    if source_type and source_id:
        return StructuredCitation(
            source_type=source_type,
            source_id=source_id,
            display=display,
        )
    
    # Can't parse - return None (will be filtered out)
    return None
