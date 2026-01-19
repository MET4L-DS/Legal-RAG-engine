"""
Retrieval configuration and result dataclasses.

This module defines:
- RetrievalConfig: Configuration for the retrieval pipeline
- RetrievalResult: Complete result from retrieval with context building
"""

from dataclasses import dataclass, field
from typing import Optional

from ..models import SearchResult


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
    citations: list[str] = field(default_factory=list)
    
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
                
                # Format SOP citation
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
        
        # TIER-3: Add General SOP blocks for citizen-centric procedural guidance
        if self.needs_general_sop and self.general_sop_blocks:
            context_parts.append("\n=== CITIZEN PROCEDURAL GUIDANCE (General SOP) ===\n")
            for result in self.general_sop_blocks:
                title = result.metadata.get("title", "")
                sop_group = result.metadata.get("sop_group", "")
                procedural_stage = result.metadata.get("procedural_stage", "")
                time_limit = result.metadata.get("time_limit", "")
                applies_to = result.metadata.get("applies_to", [])
                
                # Format General SOP citation
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
        
        # TIER-2: Add Evidence Manual blocks if relevant
        if self.needs_evidence and self.evidence_blocks:
            context_parts.append("\n=== EVIDENCE & INVESTIGATION STANDARDS (Crime Scene Manual) ===\n")
            for result in self.evidence_blocks:
                title = result.metadata.get("title", "")
                action = result.metadata.get("investigative_action", "")
                failure_impact = result.metadata.get("failure_impact", "")
                
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
        
        self.context_text = "\n---\n".join(context_parts)
        return self.context_text
