"""
4-Stage Hierarchical Retrieval Pipeline for Legal RAG.
Implements: Document → Chapter → Section → Subsection retrieval.
Now supports procedural queries with SOP integration (Tier-1).
Now supports evidence and compensation queries (Tier-2).
"""

import re
from typing import Optional, Any
from dataclasses import dataclass, field
import numpy as np

from .models import SearchResult
from .vector_store import MultiLevelVectorStore
from .embedder import HierarchicalEmbedder
from .sop_parser import ProceduralStage


# ============================================================================
# PROCEDURAL STAGE DETECTION (Tier-1 Feature)
# ============================================================================

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


@dataclass
class RetrievalConfig:
    """Configuration for the retrieval pipeline."""
    # Number of results at each stage
    top_k_documents: int = 3
    top_k_chapters: int = 10  # Increased from 5 to capture more potentially relevant chapters
    top_k_sections: int = 12  # Increased from 8
    top_k_subsections: int = 20  # Increased from 15
    
    # Score thresholds for filtering
    # Lower thresholds to avoid filtering out relevant results
    # Document scores are typically low (0.05-0.15) for semantic similarity
    min_doc_score: float = 0.0  # Don't filter documents - let hierarchical filtering work
    min_chapter_score: float = 0.05  # Lowered from 0.1 to be less aggressive
    min_section_score: float = 0.1  # Lowered from 0.15
    min_subsection_score: float = 0.1  # Lowered from 0.15
    
    # Enable/disable hybrid search
    use_hybrid_search: bool = True
    
    # Enable/disable hierarchical filtering
    # When False, sections are searched across all chapters, not just top-k chapters
    use_hierarchical_filtering: bool = False  # Disabled to avoid missing relevant sections
    
    # SOP-specific settings (Tier-1)
    top_k_sop_blocks: int = 5  # Number of SOP blocks to retrieve
    sop_priority_weight: float = 1.5  # Boost factor for SOP results in procedural queries
    
    # Tier-2 settings
    top_k_evidence_blocks: int = 5  # Number of Evidence Manual blocks to retrieve
    top_k_compensation_blocks: int = 5  # Number of Compensation blocks to retrieve


@dataclass
class RetrievalResult:
    """Complete result from the retrieval pipeline."""
    query: str
    
    # Results at each level
    documents: list[SearchResult] = field(default_factory=list)
    chapters: list[SearchResult] = field(default_factory=list)
    sections: list[SearchResult] = field(default_factory=list)
    subsections: list[SearchResult] = field(default_factory=list)
    
    # SOP results (Tier-1)
    sop_blocks: list[SearchResult] = field(default_factory=list)
    
    # Tier-2 results
    evidence_blocks: list[SearchResult] = field(default_factory=list)
    compensation_blocks: list[SearchResult] = field(default_factory=list)
    
    # Query intent (Tier-1)
    is_procedural: bool = False
    case_type: Optional[str] = None
    detected_stages: list[str] = field(default_factory=list)
    
    # Tier-2 query intent
    needs_evidence: bool = False
    needs_compensation: bool = False
    
    # Final context for LLM
    context_text: str = ""
    citations: list[str] = field(default_factory=list)
    
    def get_context_for_llm(self, max_tokens: int = 8000) -> str:
        """Get formatted context for LLM with citations.
        
        For procedural queries, SOP blocks come first, then law sections.
        For Tier-2 queries, evidence/compensation blocks are added where relevant.
        """
        context_parts = []
        seen_sections = set()
        
        # For procedural queries, add SOP blocks FIRST (they have procedural guidance)
        if self.is_procedural and self.sop_blocks:
            context_parts.append("=== PROCEDURAL GUIDANCE (SOP) ===\n")
            for result in self.sop_blocks:
                # Get SOP-specific metadata
                title = result.metadata.get("title", "")
                stage = result.metadata.get("procedural_stage", "")
                time_limit = result.metadata.get("time_limit", "")
                
                # Format SOP citation
                citation = f"📘 SOP (MHA/BPR&D) - {title}"
                if stage:
                    citation += f" [{stage.upper()}]"
                if time_limit:
                    citation += f" ⏱️ {time_limit}"
                
                text = result.text
                
                # Estimate tokens
                if len("\n".join(context_parts)) / 4 > max_tokens * 0.3:
                    break
                
                context_parts.append(f"[{citation}]\n{text}\n")
                
                if citation not in self.citations:
                    self.citations.append(citation)
        
        # TIER-2: Add Evidence Manual blocks if relevant
        if self.needs_evidence and self.evidence_blocks:
            context_parts.append("\n=== EVIDENCE & INVESTIGATION STANDARDS (Crime Scene Manual) ===\n")
            for result in self.evidence_blocks:
                title = result.metadata.get("title", "")
                action = result.metadata.get("investigative_action", "")
                failure_impact = result.metadata.get("failure_impact", "")
                
                # Format Evidence citation
                citation = f"🧪 Crime Scene Manual (DFS) - {title}"
                if action:
                    citation += f" [{action.replace('_', ' ').upper()}]"
                
                text = result.text
                
                # Add failure impact warning
                if failure_impact and failure_impact != "none":
                    text = f"⚠️ If not followed: {failure_impact.replace('_', ' ')}\n\n{text}"
                
                # Estimate tokens
                if len("\n".join(context_parts)) / 4 > max_tokens * 0.5:
                    break
                
                context_parts.append(f"[{citation}]\n{text}\n")
                
                if citation not in self.citations:
                    self.citations.append(citation)
        
        # TIER-2: Add Compensation Scheme blocks if relevant
        if self.needs_compensation and self.compensation_blocks:
            context_parts.append("\n=== COMPENSATION & REHABILITATION (NALSA Scheme) ===\n")
            for result in self.compensation_blocks:
                title = result.metadata.get("title", "")
                comp_type = result.metadata.get("compensation_type", "")
                authority = result.metadata.get("authority", "")
                amount_range = result.metadata.get("amount_range", "")
                requires_conviction = result.metadata.get("requires_conviction", False)
                
                # Format Compensation citation
                citation = f"💰 NALSA Scheme (2018) - {title}"
                if comp_type:
                    citation += f" [{comp_type.upper()}]"
                
                text = result.text
                
                # Add key eligibility info
                eligibility_note = []
                if not requires_conviction:
                    eligibility_note.append("✔ Conviction NOT required")
                if authority:
                    eligibility_note.append(f"Authority: {authority.upper()}")
                if amount_range:
                    eligibility_note.append(f"Amount: {amount_range}")
                
                if eligibility_note:
                    text = " | ".join(eligibility_note) + "\n\n" + text
                
                # Estimate tokens
                if len("\n".join(context_parts)) / 4 > max_tokens * 0.6:
                    break
                
                context_parts.append(f"[{citation}]\n{text}\n")
                
                if citation not in self.citations:
                    self.citations.append(citation)
        
        # Add legal provisions section header if we have SOP/Tier-2 content
        if self.sop_blocks or self.evidence_blocks or self.compensation_blocks:
            context_parts.append("\n=== LEGAL PROVISIONS ===\n")
        
        # Add section-level context (legal provisions)
        for result in self.sections:
            section_key = f"{result.doc_id}-{result.section_no}"
            if section_key in seen_sections:
                continue
            seen_sections.add(section_key)
            
            # Format law citation with icon
            doc_icon = "⚖️" if "BNSS" in result.doc_id else "📕" if "BNS" in result.doc_id else "📗"
            citation = f"{doc_icon} {result.get_citation()}"
            text = result.text
            
            # Estimate tokens (rough: 4 chars per token)
            if len("\n".join(context_parts)) / 4 > max_tokens * 0.7:
                break
            
            context_parts.append(f"[{citation}]\n{text}\n")
            
            if citation not in self.citations:
                self.citations.append(citation)
        
        # Then add subsection details for more specific content
        for result in self.subsections:
            doc_icon = "⚖️" if "BNSS" in result.doc_id else "📕" if "BNS" in result.doc_id else "📗"
            citation = f"{doc_icon} {result.get_citation()}"
            text = result.text
            
            # Skip if text is too short (likely a fragment)
            if len(text) < 50:
                continue
            
            # Estimate tokens
            if len("\n".join(context_parts)) / 4 > max_tokens:
                break
            
            context_parts.append(f"[{citation}]\n{text}\n")
            
            if citation not in self.citations:
                self.citations.append(citation)
        
        self.context_text = "\n---\n".join(context_parts)
        return self.context_text


class HierarchicalRetriever:
    """4-stage hierarchical retrieval pipeline with SOP support (Tier-1)."""
    
    def __init__(
        self,
        vector_store: MultiLevelVectorStore,
        embedder: HierarchicalEmbedder,
        config: Optional[RetrievalConfig] = None
    ):
        """Initialize the retriever.
        
        Args:
            vector_store: Multi-level vector store with indexed documents
            embedder: Embedding model for query encoding
            config: Retrieval configuration
        """
        self.store = vector_store
        self.embedder = embedder
        self.config = config or RetrievalConfig()
    
    def retrieve(self, query: str) -> RetrievalResult:
        """Execute the retrieval pipeline.
        
        For procedural queries (Tier-1), retrieves SOP blocks first, then law sections.
        For Tier-2 queries, adds evidence/compensation blocks when relevant.
        For non-procedural queries, uses standard 4-stage hierarchical retrieval.
        
        Args:
            query: User's legal question
            
        Returns:
            RetrievalResult with results at all levels
        """
        result = RetrievalResult(query=query)
        
        # Detect query intent (Tier-1 feature)
        intent = detect_query_intent(query)
        result.is_procedural = intent["is_procedural"]
        result.case_type = intent["case_type"]
        result.detected_stages = [s.value for s in intent.get("detected_stages", [])]
        
        # Detect Tier-2 intent (evidence/compensation)
        tier2_intent = detect_tier2_intent(query)
        result.needs_evidence = tier2_intent["needs_evidence"]
        result.needs_compensation = tier2_intent["needs_compensation"]
        
        # Extract explicit hints from query (e.g., "section 103 of BNS")
        hints = extract_query_hints(query)
        
        # Enhance query text with topic keywords for better BM25 matching
        enhanced_query = query
        if hints["topic_keywords"]:
            enhanced_query = query + " " + " ".join(hints["topic_keywords"])
        
        # Generate query embedding
        query_embedding = self.embedder.embed_text(query)
        
        # For procedural queries, search SOP blocks FIRST (Tier-1 feature)
        if result.is_procedural and self.store.has_sop_data():
            stage_filter = [s.value for s in intent.get("detected_stages", [])] if intent.get("detected_stages") else None
            # Don't filter by stakeholder - SOP blocks are useful for all stakeholders
            # The blocks describe both victim rights AND police duties
            
            result.sop_blocks = self.store.search_sop_blocks(
                query_embedding,
                enhanced_query,
                k=self.config.top_k_sop_blocks,
                stage_filter=None,  # Don't filter by stage either - retrieve all relevant blocks
                stakeholder_filter=None,
                use_hybrid=self.config.use_hybrid_search
            )
        
        # TIER-2: Search evidence blocks if relevant
        if result.needs_evidence and self.store.has_evidence_data():
            result.evidence_blocks = self.store.search_evidence_blocks(
                query_embedding,
                enhanced_query,
                k=self.config.top_k_evidence_blocks,
                evidence_type_filter=None,  # Don't filter - retrieve all relevant
                case_type_filter=None,
                use_hybrid=self.config.use_hybrid_search
            )
        
        # TIER-2: Search compensation blocks if relevant
        if result.needs_compensation and self.store.has_compensation_data():
            result.compensation_blocks = self.store.search_compensation_blocks(
                query_embedding,
                enhanced_query,
                k=self.config.top_k_compensation_blocks,
                compensation_type_filter=None,
                crime_filter=None,
                use_hybrid=self.config.use_hybrid_search
            )
        
        # Stage 1: Document Routing
        result.documents = self._stage1_document_routing(query_embedding, enhanced_query)
        
        if not result.documents:
            # If no documents found but we have SOP/Tier-2 results, return those
            if result.sop_blocks or result.evidence_blocks or result.compensation_blocks:
                result.get_context_for_llm()
            return result
        
        # Get document filter for next stages
        doc_filter = None
        if hints["doc_id"]:
            # Use explicitly mentioned document
            doc_filter = hints["doc_id"]
        elif self.config.use_hierarchical_filtering and result.documents:
            # Use top scoring document
            doc_filter = result.documents[0].doc_id
        
        # If explicit section is mentioned, do direct lookup (bypass semantic search)
        if hints["section_no"]:
            # Direct lookup by section number
            result.sections = self.store.lookup_section_by_number(
                hints["section_no"], 
                doc_filter=hints["doc_id"]  # Use hint doc_id, not filtered doc_id
            )
            result.subsections = self.store.lookup_subsections_by_section(
                hints["section_no"],
                doc_filter=hints["doc_id"]
            )
            
            # If found, build context and return
            if result.sections or result.subsections:
                result.get_context_for_llm()
                return result
        
        # Stage 2: Chapter Search
        result.chapters = self._stage2_chapter_search(
            query_embedding, enhanced_query, doc_filter
        )
        
        # Get chapter filter for next stages
        # Skip chapter filtering if a specific document was mentioned in the query
        # This allows broader section search within that document
        chapter_filter = None
        if self.config.use_hierarchical_filtering and result.chapters and not hints["doc_id"]:
            chapter_filter = [c.chapter_no for c in result.chapters]
        
        # Stage 3: Section Search
        result.sections = self._stage3_section_search(
            query_embedding, enhanced_query, doc_filter, chapter_filter
        )
        
        # Get section filter for final stage
        # Skip section filtering when document is explicitly mentioned
        section_filter = None
        if self.config.use_hierarchical_filtering and result.sections and not hints["doc_id"]:
            section_filter = [s.section_no for s in result.sections]
        
        # Stage 4: Subsection Search (Final Answer)
        result.subsections = self._stage4_subsection_search(
            query_embedding, enhanced_query, doc_filter, chapter_filter, section_filter
        )
        
        # Build context
        result.get_context_for_llm()
        
        return result
    
    def _direct_section_lookup(
        self,
        query_embedding: np.ndarray,
        query_text: str,
        doc_filter: Optional[str],
        section_no: str
    ) -> list[SearchResult]:
        """Directly look up a specific section by number."""
        # Search sections with higher k to find the specific section
        results = self.store.search_sections(
            query_embedding,
            query_text,
            k=50,  # Search more to ensure we find the right one
            doc_filter=doc_filter,
            chapter_filter=None,
            use_hybrid=True
        )
        
        # Filter to exact section number match
        exact_matches = [r for r in results if r.section_no == section_no]
        
        if exact_matches:
            return exact_matches
        
        # If no exact match, return top results
        return results[:self.config.top_k_sections]
    
    def _stage1_document_routing(
        self, 
        query_embedding: np.ndarray, 
        query_text: str
    ) -> list[SearchResult]:
        """Stage 1: Find relevant documents."""
        results = self.store.search_documents(
            query_embedding,
            query_text,
            k=self.config.top_k_documents,
            use_hybrid=self.config.use_hybrid_search
        )
        
        # Filter by score threshold
        return [r for r in results if r.score >= self.config.min_doc_score]
    
    def _stage2_chapter_search(
        self,
        query_embedding: np.ndarray,
        query_text: str,
        doc_filter: Optional[str]
    ) -> list[SearchResult]:
        """Stage 2: Find relevant chapters within documents."""
        results = self.store.search_chapters(
            query_embedding,
            query_text,
            k=self.config.top_k_chapters,
            doc_filter=doc_filter,
            use_hybrid=self.config.use_hybrid_search
        )
        
        # Filter by score threshold
        return [r for r in results if r.score >= self.config.min_chapter_score]
    
    def _stage3_section_search(
        self,
        query_embedding: np.ndarray,
        query_text: str,
        doc_filter: Optional[str],
        chapter_filter: Optional[list[str]]
    ) -> list[SearchResult]:
        """Stage 3: Find relevant sections within chapters."""
        results = self.store.search_sections(
            query_embedding,
            query_text,
            k=self.config.top_k_sections,
            doc_filter=doc_filter,
            chapter_filter=chapter_filter,
            use_hybrid=self.config.use_hybrid_search
        )
        
        # Filter by score threshold
        return [r for r in results if r.score >= self.config.min_section_score]
    
    def _stage4_subsection_search(
        self,
        query_embedding: np.ndarray,
        query_text: str,
        doc_filter: Optional[str],
        chapter_filter: Optional[list[str]],
        section_filter: Optional[list[str]]
    ) -> list[SearchResult]:
        """Stage 4: Find relevant subsections (final answer sources)."""
        results = self.store.search_subsections(
            query_embedding,
            query_text,
            k=self.config.top_k_subsections,
            doc_filter=doc_filter,
            chapter_filter=chapter_filter,
            section_filter=section_filter,
            use_hybrid=self.config.use_hybrid_search
        )
        
        # Filter by score threshold
        return [r for r in results if r.score >= self.config.min_subsection_score]
    
    def retrieve_flat(self, query: str, k: int = 10) -> RetrievalResult:
        """Flat retrieval without hierarchical filtering (for comparison).
        
        This bypasses the 4-stage process and searches subsections directly.
        """
        result = RetrievalResult(query=query)
        
        query_embedding = self.embedder.embed_text(query)
        
        # Direct subsection search without filters
        result.subsections = self.store.search_subsections(
            query_embedding,
            query,
            k=k,
            use_hybrid=self.config.use_hybrid_search
        )
        
        result.get_context_for_llm()
        
        return result


class LegalRAG:
    """Complete Legal RAG system combining retrieval with Gemini LLM generation.
    
    Supports procedural queries (Tier-1) with SOP-backed answers.
    """
    
    # Standard legal Q&A prompt
    SYSTEM_PROMPT = """You are a legal assistant specializing in Indian law (BNS, BNSS, BSA).
Your task is to answer questions using the provided legal extracts.

Instructions:
1. Carefully read ALL the provided legal extracts
2. Synthesize information from multiple sections if relevant
3. Always cite the specific Section and Chapter (e.g., "BSA Section 57")
4. If the extracts contain relevant information, provide a comprehensive answer
5. Only say you cannot find information if the extracts are truly unrelated to the question
6. Format your answer clearly with sections for: Definition, Procedure, Key Points (as applicable)"""
    
    # Procedural guidance prompt (Tier-1 feature)
    PROCEDURAL_PROMPT = """You are a legal assistant helping victims of crime in India understand their rights and the legal process.
Your task is to provide step-by-step procedural guidance using the provided materials.

The context contains:
- 📘 SOP (Standard Operating Procedure) blocks: Official police procedures and victim rights
- ⚖️ BNSS sections: Criminal procedure laws
- 📕 BNS sections: Criminal offense definitions

CRITICAL INSTRUCTIONS:
1. Structure your answer as STEP-BY-STEP GUIDANCE for the victim
2. Start with what the victim CAN DO IMMEDIATELY
3. Then explain what POLICE MUST DO (their duties)
4. Include TIME LIMITS where mentioned (e.g., "within 24 hours")
5. Cite sources using: 📘 SOP, ⚖️ BNSS Section X, 📕 BNS Section X
6. If police fail their duties, explain ESCALATION options
7. Use simple, empowering language - the reader is likely in distress
8. Prioritize SOP guidance over raw legal text

OUTPUT FORMAT:
## 🚨 Immediate Steps
[What victim can do right now]

## 👮 Police Duties
[What police MUST do - cite SOP]

## ⚖️ Legal Rights
[Relevant law sections]

## ⏱️ Time Limits
[Any deadlines that apply]

## ⚠️ If Police Refuse
[Escalation steps]"""
    
    # Evidence & Investigation prompt (Tier-2 feature)
    EVIDENCE_PROMPT = """You are a legal assistant helping victims understand evidence collection and investigation standards in India.
Your task is to explain what proper evidence handling looks like and what happens if police fail to follow procedures.

The context contains:
- 🧪 Crime Scene Manual: Official evidence collection and preservation procedures
- 📘 SOP: Standard Operating Procedures for investigations
- ⚖️ BNSS: Criminal procedure laws

CRITICAL INSTRUCTIONS:
1. Explain WHAT EVIDENCE should be collected for the specific crime
2. Describe HOW evidence should be properly collected and preserved
3. Highlight TIME LIMITS for evidence collection
4. Explain CONSEQUENCES if evidence is not properly handled (contamination, inadmissibility)
5. Cite sources: 🧪 Crime Scene Manual, 📘 SOP, ⚖️ BNSS
6. If police failed, explain what legal recourse the victim has
7. Use technical terms but explain them simply

OUTPUT FORMAT:
## 🔬 Required Evidence
[What evidence should be collected for this crime]

## 📋 Proper Procedure
[How evidence should be collected - cite Manual]

## ⏱️ Time Limits
[Critical time windows for evidence collection]

## ⚠️ If Procedure Not Followed
[Consequences - contamination, inadmissibility, case weakness]

## ⚖️ Legal Recourse
[What victim can do if evidence mishandled]"""
    
    # Compensation & Rehabilitation prompt (Tier-2 feature)
    COMPENSATION_PROMPT = """You are a legal assistant helping victims of crime in India understand their compensation and rehabilitation rights.
Your task is to explain what financial relief and support is available to victims.

The context contains:
- 💰 NALSA Compensation Scheme (2018): Victim compensation guidelines
- ⚖️ BNSS Section 396: Legal provision for victim compensation
- Other legal provisions

CRITICAL INSTRUCTIONS:
1. FIRST state whether conviction is required (IMPORTANT: for most schemes, conviction is NOT required)
2. List ALL types of compensation/support available (interim relief, final compensation, rehabilitation)
3. Explain the APPLICATION PROCESS step by step
4. State AMOUNT RANGES where mentioned
5. List DOCUMENTS REQUIRED for application
6. Mention AUTHORITIES to approach (DLSA, SLSA, etc.)
7. Include TIME LIMITS for applying
8. Cite sources: 💰 NALSA Scheme, ⚖️ BNSS

KEY FACT TO EMPHASIZE: Under NALSA Scheme, victim compensation does NOT require conviction of accused. Even if accused is acquitted or case is pending, victim can get compensation.

OUTPUT FORMAT:
## ✅ Eligibility
[Who can apply - emphasize conviction NOT required if applicable]

## 💰 Types of Compensation
[Interim relief, final compensation, rehabilitation support]

## 📝 How to Apply
[Step-by-step application process]

## 📄 Documents Required
[List of required documents]

## 💵 Amount Ranges
[Compensation amounts for different crimes]

## 🏛️ Where to Apply
[DLSA, SLSA, court - with contacts if available]

## ⏱️ Time Limits
[Deadlines for application]"""
    
    def __init__(
        self,
        retriever: HierarchicalRetriever,
        llm_client: Optional[Any] = None,
        model: str = "gemini-1.5-flash"
    ):
        """Initialize the RAG system.
        
        Args:
            retriever: Hierarchical retriever for document search
            llm_client: Google Gemini GenerativeModel (optional, for answer generation)
            model: LLM model to use (gemini-1.5-flash, gemini-1.5-pro, etc.)
        """
        self.retriever = retriever
        self.llm_client = llm_client
        self.model = model
    
    def query(self, question: str, generate_answer: bool = True) -> dict:
        """Answer a legal question using RAG.
        
        For procedural queries (Tier-1), uses SOP-backed procedural prompt.
        For Tier-2 queries, includes evidence/compensation context.
        
        Args:
            question: User's legal question
            generate_answer: Whether to generate LLM answer (requires llm_client)
            
        Returns:
            Dictionary with retrieval results and optional LLM answer
        """
        # Retrieve relevant context
        retrieval_result = self.retriever.retrieve(question)
        
        response = {
            "question": question,
            "is_procedural": retrieval_result.is_procedural,
            "case_type": retrieval_result.case_type,
            "detected_stages": retrieval_result.detected_stages,
            # Tier-2 intent flags
            "needs_evidence": retrieval_result.needs_evidence,
            "needs_compensation": retrieval_result.needs_compensation,
            "retrieval": {
                "documents": [self._format_result(r) for r in retrieval_result.documents],
                "chapters": [self._format_result(r) for r in retrieval_result.chapters],
                "sections": [self._format_result(r) for r in retrieval_result.sections],
                "subsections": [self._format_result(r) for r in retrieval_result.subsections],
                "sop_blocks": [self._format_result(r) for r in retrieval_result.sop_blocks],
                # Tier-2 results
                "evidence_blocks": [self._format_result(r) for r in retrieval_result.evidence_blocks],
                "compensation_blocks": [self._format_result(r) for r in retrieval_result.compensation_blocks]
            },
            "context": retrieval_result.context_text,
            "citations": retrieval_result.citations,
            "answer": None
        }
        
        # Generate answer if LLM client is available
        if generate_answer and self.llm_client and retrieval_result.context_text:
            response["answer"] = self._generate_answer(
                question, 
                retrieval_result.context_text,
                is_procedural=retrieval_result.is_procedural,
                needs_evidence=retrieval_result.needs_evidence,
                needs_compensation=retrieval_result.needs_compensation
            )
        
        return response
    
    def _format_result(self, result: SearchResult) -> dict:
        """Format a search result for output."""
        formatted = {
            "citation": result.get_citation(),
            "text": result.text[:500] + "..." if len(result.text) > 500 else result.text,
            "score": round(result.score, 4),
            "level": result.level,
            "metadata": result.metadata
        }
        
        # Add doc_type indicator
        doc_type = result.metadata.get("doc_type", "")
        if doc_type == "sop":
            formatted["source_type"] = "📘 SOP"
        elif doc_type == "evidence_manual":
            formatted["source_type"] = "🧪 Evidence Manual"
        elif doc_type == "compensation_scheme":
            formatted["source_type"] = "💰 NALSA Scheme"
        elif "BNSS" in result.doc_id:
            formatted["source_type"] = "⚖️ BNSS"
        elif "BNS" in result.doc_id:
            formatted["source_type"] = "📕 BNS"
        elif "BSA" in result.doc_id:
            formatted["source_type"] = "📗 BSA"
        else:
            formatted["source_type"] = "📄 Law"
        
        return formatted
    
    def _generate_answer(
        self, 
        question: str, 
        context: str, 
        is_procedural: bool = False,
        needs_evidence: bool = False,
        needs_compensation: bool = False
    ) -> str:
        """Generate answer using Google Gemini with retry logic.
        
        Uses specialized prompts based on query type:
        - Procedural (Tier-1): SOP-backed guidance
        - Evidence (Tier-2): Crime scene/investigation standards
        - Compensation (Tier-2): Victim relief and rehabilitation
        """
        import time
        
        # Select appropriate prompt based on query type
        if needs_evidence:
            system_prompt = self.EVIDENCE_PROMPT
        elif needs_compensation:
            system_prompt = self.COMPENSATION_PROMPT
        elif is_procedural:
            system_prompt = self.PROCEDURAL_PROMPT
        else:
            system_prompt = self.SYSTEM_PROMPT
        
        full_prompt = f"""{system_prompt}

Based on the following materials, answer the question.

Materials:
{context}

Question: {question}

Answer:"""
        
        # Models to try in order (based on free tier rate limits)
        # gemini-2.5-flash-lite: 30 RPM, 1500 RPD (best for development)
        # gemini-2.0-flash: 10 RPM, 1000 RPD (legacy stable)
        # gemini-2.5-flash: 2 RPM, 20 RPD (general purpose, limited)
        models_to_try = ["gemini-2.5-flash-lite", "gemini-2.0-flash"]
        max_retries = 2
        
        for model in models_to_try:
            for attempt in range(max_retries):
                try:
                    from google.genai import types
                    assert self.llm_client is not None, "LLM client not initialized"
                    response = self.llm_client.models.generate_content(
                        model=model,
                        contents=full_prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.1,  # type: ignore
                            max_output_tokens=1000,  # type: ignore
                        )
                    )
                    return response.text
                except Exception as e:
                    error_str = str(e)
                    if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                        # Rate limited - wait and retry or try next model
                        if attempt < max_retries - 1:
                            wait_time = (attempt + 1) * 10  # 10s, 20s, 30s
                            time.sleep(wait_time)
                            continue
                        else:
                            # Try next model
                            break
                    else:
                        # Non-rate-limit error
                        return f"Error generating answer: {error_str}"
        
        return "Error: Rate limit exceeded on all models. Please wait a minute and try again."
