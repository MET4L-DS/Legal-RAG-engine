"""
Query Intent Detection for Tier Routing.

This module detects query intent to route to appropriate tiers:
- Tier-1: Sexual offence procedural queries (rape SOP)
- Tier-2: Evidence queries (CSI Manual) & Compensation queries (NALSA Scheme)
- Tier-3: General procedural queries for all crimes (General SOP)
"""

import re

from ..parsers import ProceduralStage


# =============================================================================
# TIER-1: PROCEDURAL STAGE DETECTION (Sexual Offences)
# =============================================================================

# Case types that trigger procedural retrieval
PROCEDURAL_CASE_TYPES = {
    "rape": ["rape", "sexual assault", "sexual violence", "molestation", "pocso"],
    "sexual_assault": ["assault", "sexual", "molest", "touch"],
}

# Stage detection keywords
STAGE_KEYWORDS = {
    ProceduralStage.PRE_FIR: ["before fir", "before complaint", "initial", "first step", "what can", "what should", "how can", "how to"],
    ProceduralStage.FIR: ["fir", "first information report", "complaint", "lodge", "register", "police station"],
    ProceduralStage.INVESTIGATION: ["investigation", "investigate", "io", "investigating officer"],
    ProceduralStage.MEDICAL_EXAMINATION: ["medical", "examination", "doctor", "hospital", "forensic", "rape kit"],
    ProceduralStage.STATEMENT_RECORDING: ["statement", "164", "183", "record", "testimony"],
    ProceduralStage.EVIDENCE_COLLECTION: ["evidence", "collect", "scene", "forensic", "dna"],
    ProceduralStage.ARREST: ["arrest", "custody", "accused", "remand"],
    ProceduralStage.CHARGE_SHEET: ["charge sheet", "chargesheet", "173", "193"],
    ProceduralStage.TRIAL: ["trial", "court", "prosecution", "sessions", "judge"],
    ProceduralStage.VICTIM_RIGHTS: ["rights", "victim", "survivor", "entitled", "compensation"],
    ProceduralStage.POLICE_DUTIES: ["police", "duty", "shall", "must", "obligation"],
}

# Intent detection patterns
PROCEDURAL_INTENT_PATTERNS = [
    r"what can .* do",
    r"what should .* do",
    r"how can .* (file|lodge|report|complain)",
    r"what (happens|is the procedure|are the steps)",
    r"what if .* (refuse|fail|don't)",
    r"step.?by.?step",
    r"procedure for",
    r"process for",
    r"what are .* (rights|options)",
    r"how to (fight|take action|report)",
]


# ============================================================================
# TIER-2: EVIDENCE AND COMPENSATION INTENT DETECTION
# ============================================================================

# Evidence-related keywords (triggers Crime Scene Manual retrieval)
EVIDENCE_INTENT_KEYWORDS = [
    "evidence", "crime scene", "forensic", "collect", "preserve", "contaminate",
    "scene of crime", "dna", "fingerprint", "biological", "chain of custody",
    "first responder", "seal", "packaging", "laboratory", "fsl",
    "did police", "police collect", "investigation proper", "correct procedure",
    "evidence handling", "evidence collection"
]

# Evidence-related patterns
EVIDENCE_INTENT_PATTERNS = [
    r"(?:police|io|officer).*(?:collect|preserve|handle).*evidence",
    r"evidence.*(?:collect|preserve|handle|proper|correct)",
    r"crime\s+scene",
    r"forensic",
    r"what.*evidence.*(?:should|must|need)",
    r"(?:did|was).*(?:evidence|crime scene).*(?:proper|correct|legal)",
    r"chain\s+of\s+custody",
    r"(?:contaminate|tamper).*evidence",
]

# Compensation-related keywords (triggers NALSA Scheme retrieval)
COMPENSATION_INTENT_KEYWORDS = [
    "compensation", "money", "financial", "relief", "rehabilitation",
    "nalsa", "dlsa", "slsa", "legal services",
    "victim fund", "support", "interim", "final compensation",
    "pay", "payment", "amount", "entitled", "claim",
    "without conviction", "even if acquit"
]

# Compensation-related patterns
COMPENSATION_INTENT_PATTERNS = [
    r"(?:get|receive|claim|apply).*compensation",
    r"compensation.*(?:victim|survivor|rape|assault)",
    r"(?:financial|money).*(?:help|support|relief)",
    r"(?:even|without).*conviction",
    r"(?:who|how|where).*(?:apply|claim).*(?:compensation|relief)",
    r"rehabilitation",
    r"(?:interim|immediate).*(?:relief|compensation|help)",
    r"(?:dlsa|slsa|nalsa)",
]


# ============================================================================
# TIER-3: GENERAL SOP INTENT DETECTION
# ============================================================================

# Sexual offence keywords (these should trigger Tier-1 SOP, NOT Tier-3)
SEXUAL_OFFENCE_KEYWORDS = [
    "rape", "sexual assault", "sexual violence", "molestation", "pocso",
    "sexual harassment", "outraging modesty", "voyeurism", "stalking",
    "sexual", "molest", "survivor"
]

# General crime types that should trigger Tier-3 (not Tier-1)
GENERAL_CRIME_TYPES = {
    "robbery": ["robbery", "robbed", "loot", "looted", "snatch", "snatched"],
    "theft": ["theft", "stolen", "thief", "steal", "stole", "burglary", "housebreaking"],
    "assault": ["assault", "beaten", "beat", "attack", "attacked", "hurt", "injury", "injured"],
    "murder": ["murder", "killed", "death", "homicide", "dead body", "body found"],
    "cybercrime": ["cyber", "online fraud", "hacking", "phishing", "identity theft", "internet"],
    "cheating": ["cheating", "fraud", "deceive", "deceived", "duped"],
    "extortion": ["extortion", "blackmail", "threat", "threatened"],
    "kidnapping": ["kidnapping", "kidnapped", "abducted", "missing person"],
    "general": ["crime", "offence", "incident", "case", "complaint", "fir"]
}

# General procedural intent patterns (citizen-centric queries)
GENERAL_PROCEDURAL_PATTERNS = [
    r"what (?:do|should|can) (?:i|we) do",
    r"how (?:do|can|to) (?:i|we)",
    r"what (?:happens|is the procedure|are the steps)",
    r"(?:file|lodge|register).*(?:fir|complaint)",
    r"police.*(?:refuse|refused|not taking|won't)",
    r"(?:after|once).*fir",
    r"step.?by.?step",
    r"procedure for",
    r"process for",
    r"what if.*(?:police|refuse)",
    r"where to go",
    r"whom to contact",
    r"what next",
    r"what are my (?:rights|options)",
]


# =============================================================================
# INTENT DETECTION FUNCTIONS
# =============================================================================


def detect_tier3_intent(query: str, tier2_intent: dict) -> dict:
    """Detect if query requires Tier-3 retrieval (General SOP).
    
    Tier-3 is triggered when:
    - Query is procedural (citizen seeking guidance)
    - NOT a sexual offence (those go to Tier-1)
    - NOT evidence/compensation focused (those go to Tier-2)
    - About a general crime OR general procedural question
    
    Returns:
        dict with keys:
        - needs_general_sop: bool - whether to search General SOP
        - crime_type: str or None - detected crime type
        - is_sexual_offence: bool - whether this should go to Tier-1 instead
    """
    query_lower = query.lower()
    
    result = {
        "needs_general_sop": False,
        "crime_type": None,
        "is_sexual_offence": False
    }
    
    # Check if this is a sexual offence query (should go to Tier-1, not Tier-3)
    for kw in SEXUAL_OFFENCE_KEYWORDS:
        if kw in query_lower:
            result["is_sexual_offence"] = True
            return result  # Don't trigger Tier-3 for sexual offences
    
    # If Tier-2 is strongly triggered for evidence/compensation, don't also trigger Tier-3
    # (But we CAN have Tier-3 + Tier-2 for queries like "robbery + compensation")
    evidence_only = tier2_intent.get("needs_evidence") and not tier2_intent.get("needs_compensation")
    
    # Detect crime type
    for crime_type, keywords in GENERAL_CRIME_TYPES.items():
        if any(kw in query_lower for kw in keywords):
            result["crime_type"] = crime_type
            break
    
    # Check for general procedural intent patterns
    has_procedural_pattern = any(
        re.search(pattern, query_lower) 
        for pattern in GENERAL_PROCEDURAL_PATTERNS
    )
    
    # Trigger Tier-3 if:
    # 1. It's a general crime type AND has procedural pattern
    # 2. OR it's a general procedural question (what to do, how to file FIR, etc.)
    if result["crime_type"] and has_procedural_pattern:
        result["needs_general_sop"] = True
    elif has_procedural_pattern and not evidence_only:
        # General procedural question without specific crime
        result["needs_general_sop"] = True
        result["crime_type"] = "general"
    
    return result


def detect_tier2_intent(query: str) -> dict:
    """Detect if query requires Tier-2 retrieval (evidence or compensation).
    
    Returns:
        dict with keys:
        - needs_evidence: bool - whether to search Evidence Manual
        - needs_compensation: bool - whether to search Compensation Scheme
        - evidence_keywords: list[str] - matched evidence keywords
        - compensation_keywords: list[str] - matched compensation keywords
    """
    query_lower = query.lower()
    
    result = {
        "needs_evidence": False,
        "needs_compensation": False,
        "evidence_keywords": [],
        "compensation_keywords": []
    }
    
    # Check for evidence intent
    for kw in EVIDENCE_INTENT_KEYWORDS:
        if kw in query_lower:
            result["needs_evidence"] = True
            result["evidence_keywords"].append(kw)
    
    for pattern in EVIDENCE_INTENT_PATTERNS:
        if re.search(pattern, query_lower):
            result["needs_evidence"] = True
            break
    
    # Check for compensation intent
    for kw in COMPENSATION_INTENT_KEYWORDS:
        if kw in query_lower:
            result["needs_compensation"] = True
            result["compensation_keywords"].append(kw)
    
    for pattern in COMPENSATION_INTENT_PATTERNS:
        if re.search(pattern, query_lower):
            result["needs_compensation"] = True
            break
    
    return result


def detect_query_intent(query: str) -> dict:
    """Detect if query is procedural and what case type/stage it relates to.
    
    Returns:
        dict with keys:
        - is_procedural: bool - whether query seeks procedural guidance
        - case_type: str - type of case (rape, theft, murder, etc.)
        - detected_stages: list[ProceduralStage] - relevant procedure stages
        - stakeholder_focus: str - victim, police, court, etc.
    """
    query_lower = query.lower()
    
    result = {
        "is_procedural": False,
        "case_type": None,
        "detected_stages": [],
        "stakeholder_focus": "victim"  # Default to victim-centric
    }
    
    # Check for procedural intent patterns
    for pattern in PROCEDURAL_INTENT_PATTERNS:
        if re.search(pattern, query_lower):
            result["is_procedural"] = True
            break
    
    # Detect case type
    for case_type, keywords in PROCEDURAL_CASE_TYPES.items():
        if any(kw in query_lower for kw in keywords):
            result["case_type"] = case_type
            result["is_procedural"] = True  # Case-specific queries are procedural
            break
    
    # Detect stages
    for stage, keywords in STAGE_KEYWORDS.items():
        if any(kw in query_lower for kw in keywords):
            result["detected_stages"].append(stage)
    
    # Default to PRE_FIR if procedural but no specific stage
    if result["is_procedural"] and not result["detected_stages"]:
        result["detected_stages"] = [ProceduralStage.PRE_FIR, ProceduralStage.FIR, ProceduralStage.VICTIM_RIGHTS]
    
    # Detect stakeholder focus
    if any(word in query_lower for word in ["woman", "victim", "survivor", "girl", "she", "her"]):
        result["stakeholder_focus"] = "victim"
    elif any(word in query_lower for word in ["police", "officer", "sho"]):
        result["stakeholder_focus"] = "police"
    elif any(word in query_lower for word in ["accused", "defendant"]):
        result["stakeholder_focus"] = "accused"
    
    return result


def extract_query_hints(query: str) -> dict:
    """Extract explicit document/section references from the query.
    
    Handles queries like:
    - "What does section 103 of BNS say?"
    - "BNS section 45"
    - "Section 123 BNSS"
    - "procedure for rape in BNSS"
    """
    hints = {
        "doc_id": None,
        "section_no": None,
        "topic_keywords": [],  # Additional keywords to boost search
    }
    
    query_upper = query.upper()
    query_lower = query.lower()
    
    # Detect document references
    if "BNS" in query_upper and "BNSS" not in query_upper:
        hints["doc_id"] = "BNS_2023"
    elif "BNSS" in query_upper:
        hints["doc_id"] = "BNSS_2023"
    elif "BSA" in query_upper:
        hints["doc_id"] = "BSA_2023"
    elif "NYAYA" in query_upper or "SANHITA" in query_upper:
        hints["doc_id"] = "BNS_2023"
    elif "SURAKSHA" in query_upper or "NAGARIK" in query_upper:
        hints["doc_id"] = "BNSS_2023"
    elif "SAKSHYA" in query_upper or "EVIDENCE" in query_upper.split():
        hints["doc_id"] = "BSA_2023"
    
    # Detect section number references
    section_patterns = [
        r'section\s+(\d+)',
        r'sec\.?\s*(\d+)',
        r'§\s*(\d+)',
    ]
    
    for pattern in section_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            hints["section_no"] = match.group(1)
            break
    
    # Detect topic keywords to enhance search
    # Map common terms to legal terminology
    topic_mappings = {
        'sexual harassment': ['rape', 'victim', 'sexual', 'woman', 'examination', 'medical', 'complaint', 'fir'],
        'rape survivor': ['rape', 'victim', 'sexual', 'woman', 'examination', 'medical', 'complaint', 'fir', 'investigation', 'accused'],
        'rape': ['rape', 'victim', 'sexual', 'woman', 'examination', 'medical', 'complaint', 'fir'],
        'survivor': ['victim', 'rape', 'sexual', 'examination', 'medical', 'treatment', 'complaint'],
        'victim': ['victim', 'examination', 'medical', 'treatment', 'complaint'],
        'theft': ['theft', 'stolen', 'property', 'movable'],
        'murder': ['murder', 'death', 'homicide', 'culpable'],
        'arrest': ['arrest', 'custody', 'detention', 'bail'],
        'bail': ['bail', 'bond', 'surety', 'release'],
        'evidence': ['evidence', 'witness', 'testimony', 'examination'],
        'fir': ['information', 'complaint', 'cognizance', 'police'],
        'complaint': ['complaint', 'cognizance', 'magistrate'],
        'fight back': ['complaint', 'fir', 'information', 'accused', 'prosecution', 'trial'],
        'legal action': ['complaint', 'fir', 'information', 'cognizance', 'trial', 'court'],
    }
    
    for term, keywords in topic_mappings.items():
        if term in query_lower:
            hints["topic_keywords"].extend(keywords)
    
    return hints
