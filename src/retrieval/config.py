"""
Retrieval configuration and result dataclasses.

This module defines:
- RetrievalConfig: Configuration for the retrieval pipeline
- RetrievalResult: Complete result from retrieval with context building
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from ..models import SearchResult

logger = logging.getLogger(__name__)


@dataclass
class StructuredCitationData:
    """
    Internal dataclass for structured citation data.
    
    This is converted to the Pydantic StructuredCitation schema in the API layer.
    """
    source_type: str  # general_sop, sop, bnss, bns, bsa, evidence, compensation
    source_id: str    # GSOP_095, 183, SOP_RAPE_003, etc.
    display: str      # Human-readable display text
    context_snippet: Optional[str] = None  # Snippet of text used
    relevance_score: Optional[float] = None  # Retrieval score


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
    
    # Tier-3 settings (General SOP for all crimes)
    top_k_general_sop_blocks: int = 5  # Number of General SOP blocks to retrieve
    min_general_sop_score: float = 0.5  # Stricter threshold for citizen procedures

    # Citation Display Settings
    min_citation_score: float = 0.6  # Only show citations above this relevance score


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
    
    # Tier-3 results (General SOP for all crimes)
    general_sop_blocks: list[SearchResult] = field(default_factory=list)
    
    # Query intent (Tier-1)
    is_procedural: bool = False
    case_type: Optional[str] = None
    detected_stages: list[str] = field(default_factory=list)
    
    # Tier-2 query intent
    needs_evidence: bool = False
    needs_compensation: bool = False
    
    # Tier-3 query intent
    needs_general_sop: bool = False
    general_crime_type: Optional[str] = None
    
    # Final context for LLM
    context_text: str = ""
    citations: list[str] = field(default_factory=list)  # Legacy string citations for LLM context
    structured_citations: list[StructuredCitationData] = field(default_factory=list)  # Structured citations for API
    
    def _add_structured_citation(
        self,
        source_type: str,
        source_id: str,
        display: str,
        context_snippet: Optional[str] = None,
        relevance_score: Optional[float] = None
    ) -> None:
        """Add a structured citation, avoiding duplicates."""
        # Skip if source_id is empty (can't fetch without ID)
        if not source_id:
            logger.warning(f"[CITATION] Skipping citation with empty source_id: {source_type}/{display[:50]}")
            return
        
        # Check if this source_type + source_id combo already exists
        for existing in self.structured_citations:
            if existing.source_type == source_type and existing.source_id == source_id:
                logger.debug(f"[CITATION] Skipping duplicate: {source_type}/{source_id}")
                return  # Skip duplicate
        
        self.structured_citations.append(StructuredCitationData(
            source_type=source_type,
            source_id=source_id,
            display=display,
            context_snippet=context_snippet[:200] + "..." if context_snippet and len(context_snippet) > 200 else context_snippet,
            relevance_score=relevance_score
        ))
        display_preview = (display[:50] + "...") if len(display) > 50 else display
        logger.debug(f"[CITATION] Added: {source_type}/{source_id} → {display_preview}")
    
    def get_context_for_llm(self, max_tokens: int = 8000) -> str:
        """Get formatted context for LLM with citations.
        
        For procedural queries, SOP blocks come first, then law sections.
        For Tier-2 queries, evidence/compensation blocks are added where relevant.
        For Tier-3 queries, General SOP blocks provide citizen-centric guidance.
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
                # block_id is stored in section_no field for SOP results
                block_id = result.section_no or result.metadata.get("block_id", "")
                
                # Format SOP citation for LLM context
                citation = f"SOP (MHA/BPR&D) - {title}"
                if stage:
                    citation += f" [{stage.upper()}]"
                if time_limit:
                    citation += f" {time_limit}"
                
                text = result.text
                
                # Estimate tokens
                if len("\n".join(context_parts)) / 4 > max_tokens * 0.3:
                    break
                
                context_parts.append(f"[{citation}]\n{text}\n")
                
                if citation not in self.citations:
                    self.citations.append(citation)
                
                # Add structured citation
                self._add_structured_citation(
                    source_type="sop",
                    source_id=block_id if block_id else title[:50],
                    display=f"SOP: {title[:80]}{'...' if len(title) > 80 else ''}",
                    context_snippet=text[:200] if text else None,
                    relevance_score=result.score
                )
        
        # TIER-3: Add General SOP blocks for citizen-centric procedural guidance
        if self.needs_general_sop and self.general_sop_blocks:
            context_parts.append("\n=== CITIZEN PROCEDURAL GUIDANCE (General SOP) ===\n")
            for result in self.general_sop_blocks:
                title = result.metadata.get("title", "")
                sop_group = result.metadata.get("sop_group", "")
                procedural_stage = result.metadata.get("procedural_stage", "")
                time_limit = result.metadata.get("time_limit", "")
                applies_to = result.metadata.get("applies_to", [])
                # block_id is stored in section_no field for General SOP results
                block_id = result.section_no or result.metadata.get("block_id", "")
                
                # Format General SOP citation for LLM context
                citation = f"General SOP (BPR&D) - {title}"
                if sop_group:
                    citation += f" [{sop_group.replace('_', ' ').upper()}]"
                if time_limit:
                    citation += f" {time_limit}"
                
                text = result.text
                
                # Add applicability note if specific crimes
                if applies_to and "all" not in applies_to:
                    applies_note = f"Applicable to: {', '.join(applies_to)}"
                    text = f"{applies_note}\n\n{text}"
                
                # Estimate tokens
                if len("\n".join(context_parts)) / 4 > max_tokens * 0.4:
                    break
                
                context_parts.append(f"[{citation}]\n{text}\n")
                
                if citation not in self.citations:
                    self.citations.append(citation)
                
                # Add structured citation - block_id is required for General SOP
                # Fallback to title prefix if block_id not available
                source_id = block_id if block_id else f"GSOP_{title[:30]}"
                self._add_structured_citation(
                    source_type="general_sop",
                    source_id=source_id,  # e.g., "GSOP_095"
                    display=f"General SOP: {title[:70]}{'...' if len(title) > 70 else ''}",
                    context_snippet=result.text[:200] if result.text else None,
                    relevance_score=result.score
                )
        
        # TIER-2: Add Evidence Manual blocks if relevant
        if self.needs_evidence and self.evidence_blocks:
            context_parts.append("\n=== EVIDENCE & INVESTIGATION STANDARDS (Crime Scene Manual) ===\n")
            for result in self.evidence_blocks:
                title = result.metadata.get("title", "")
                action = result.metadata.get("investigative_action", "")
                failure_impact = result.metadata.get("failure_impact", "")
                # block_id is stored in section_no field for Evidence results
                block_id = result.section_no or result.metadata.get("block_id", "")
                
                # Format Evidence citation
                citation = f"Crime Scene Manual (DFS) - {title}"
                if action:
                    citation += f" [{action.replace('_', ' ').upper()}]"
                
                text = result.text
                
                # Add failure impact warning
                if failure_impact and failure_impact != "none":
                    text = f"If not followed: {failure_impact.replace('_', ' ')}\n\n{text}"
                
                # Estimate tokens
                if len("\n".join(context_parts)) / 4 > max_tokens * 0.5:
                    break
                
                context_parts.append(f"[{citation}]\n{text}\n")
                
                if citation not in self.citations:
                    self.citations.append(citation)
                
                # Add structured citation
                self._add_structured_citation(
                    source_type="evidence",
                    source_id=block_id if block_id else title[:50],
                    display=f"Evidence Manual: {title[:70]}{'...' if len(title) > 70 else ''}",
                    context_snippet=result.text[:200] if result.text else None,
                    relevance_score=result.score
                )
        
        # TIER-2: Add Compensation Scheme blocks if relevant
        if self.needs_compensation and self.compensation_blocks:
            context_parts.append("\n=== COMPENSATION & REHABILITATION (NALSA Scheme) ===\n")
            for result in self.compensation_blocks:
                title = result.metadata.get("title", "")
                comp_type = result.metadata.get("compensation_type", "")
                authority = result.metadata.get("authority", "")
                amount_range = result.metadata.get("amount_range", "")
                requires_conviction = result.metadata.get("requires_conviction", False)
                # block_id is stored in section_no field for Compensation results
                block_id = result.section_no or result.metadata.get("block_id", "")
                
                # Format Compensation citation
                citation = f"NALSA Scheme (2018) - {title}"
                if comp_type:
                    citation += f" [{comp_type.upper()}]"
                
                text = result.text
                
                # Add key eligibility info
                eligibility_note = []
                if not requires_conviction:
                    eligibility_note.append("Conviction NOT required")
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
                
                # Add structured citation
                self._add_structured_citation(
                    source_type="compensation",
                    source_id=block_id if block_id else title[:50],
                    display=f"NALSA: {title[:70]}{'...' if len(title) > 70 else ''}",
                    context_snippet=result.text[:200] if result.text else None,
                    relevance_score=result.score
                )
        
        # Add legal provisions section header if we have SOP/Tier-2/Tier-3 content
        if self.sop_blocks or self.evidence_blocks or self.compensation_blocks or self.general_sop_blocks:
            context_parts.append("\n=== LEGAL PROVISIONS ===\n")
        
        # Add section-level context (legal provisions)
        for result in self.sections:
            section_key = f"{result.doc_id}-{result.section_no}"
            if section_key in seen_sections:
                continue
            seen_sections.add(section_key)
            
            # Format law citation
            citation = result.get_citation()
            text = result.text
            
            # Estimate tokens (rough: 4 chars per token)
            if len("\n".join(context_parts)) / 4 > max_tokens * 0.7:
                break
            
            context_parts.append(f"[{citation}]\n{text}\n")
            
            if citation not in self.citations:
                self.citations.append(citation)
            
            # Add structured citation for legal sections
            # Determine source type from doc_id
            source_type = self._get_source_type_from_doc_id(result.doc_id)
            if source_type:
                self._add_structured_citation(
                    source_type=source_type,
                    source_id=result.section_no,  # e.g., "183", "351"
                    display=f"{result.doc_id} Section {result.section_no}",
                    context_snippet=text[:200] if text else None,
                    relevance_score=result.score
                )
        
        # Then add subsection details for more specific content
        for result in self.subsections:
            citation = result.get_citation()
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
            
            # Add structured citation for subsections (same section, different subsection)
            source_type = self._get_source_type_from_doc_id(result.doc_id)
            if source_type:
                # For subsections, use section_no as primary ID (subsection is detail)
                self._add_structured_citation(
                    source_type=source_type,
                    source_id=result.section_no,  # Section number
                    display=f"{result.doc_id} Section {result.section_no}" + (f" ({result.subsection_no})" if result.subsection_no else ""),
                    context_snippet=text[:200] if text else None,
                    relevance_score=result.score
                )
        
        self.context_text = "\n---\n".join(context_parts)
        
        # Log citation summary
        by_type = {}
        for sc in self.structured_citations:
            by_type[sc.source_type] = by_type.get(sc.source_type, 0) + 1
        logger.info(f"[CITATION] Built {len(self.structured_citations)} structured citations: {by_type}")
        
        return self.context_text
    
    def _get_source_type_from_doc_id(self, doc_id: str) -> Optional[str]:
        """Map document ID to source type."""
        doc_id_upper = doc_id.upper()
        if "BNSS" in doc_id_upper:
            return "bnss"
        elif "BNS" in doc_id_upper:
            return "bns"
        elif "BSA" in doc_id_upper:
            return "bsa"
        elif "GENERAL_SOP" in doc_id_upper or "GSOP" in doc_id_upper:
            return "general_sop"
        elif "SOP" in doc_id_upper:
            return "sop"
        elif "EVIDENCE" in doc_id_upper or "CRIME_SCENE" in doc_id_upper:
            return "evidence"
        elif "COMPENSATION" in doc_id_upper or "NALSA" in doc_id_upper:
            return "compensation"
        return None
