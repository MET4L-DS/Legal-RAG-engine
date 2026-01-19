"""
4-Stage Hierarchical Retrieval Pipeline for Legal RAG.

Implements: Document -> Chapter -> Section -> Subsection retrieval.

Tier Routing:
- Tier-1: Procedural queries for sexual offences (rape SOP) 
- Tier-2: Evidence queries (CSI Manual) & Compensation queries (NALSA Scheme)
- Tier-3: General procedural queries for all crimes (General SOP)
"""

from typing import Optional

import numpy as np

from ..indexing import HierarchicalEmbedder, MultiLevelVectorStore
from ..models import SearchResult
from ..parsers import ProceduralStage
from .config import RetrievalConfig, RetrievalResult
from .intent import (
    detect_query_intent,
    detect_tier2_intent,
    detect_tier3_intent,
    extract_query_hints,
)


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
        
        # Detect Tier-3 intent (General SOP for all crimes)
        tier3_intent = detect_tier3_intent(query, tier2_intent)
        result.needs_general_sop = tier3_intent["needs_general_sop"]
        result.general_crime_type = tier3_intent["crime_type"]
        
        # Extract explicit hints from query (e.g., "section 103 of BNS")
        hints = extract_query_hints(query)
        
        # Enhance query text with topic keywords for better BM25 matching
        enhanced_query = query
        if hints["topic_keywords"]:
            enhanced_query = query + " " + " ".join(hints["topic_keywords"])
        
        # Generate query embedding
        query_embedding = self.embedder.embed_text(query)
        
        # For procedural queries about sexual offences, search SOP blocks FIRST (Tier-1)
        # Note: Tier-1 is for sexual offences ONLY, not for general crimes
        if result.is_procedural and self.store.has_sop_data() and not tier3_intent["is_sexual_offence"]:
            # Tier-1 is only for sexual offences - if this is general crime, don't use Tier-1
            pass
        elif result.is_procedural and self.store.has_sop_data():
            # Sexual offence detected - use Tier-1 SOP
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
        
        # TIER-3: Search General SOP blocks for general crimes (citizen-centric guidance)
        # Routing: procedural + NOT sexual_offence + NOT pure evidence query = Tier-3
        if result.needs_general_sop and self.store.has_general_sop_data():
            # Detect crime type filter (if specified)
            crime_type_filter = None
            if result.general_crime_type and result.general_crime_type != "general":
                crime_type_filter = [result.general_crime_type]
            
            result.general_sop_blocks = self.store.search_general_sop_blocks(
                query_embedding,
                enhanced_query,
                k=self.config.top_k_general_sop_blocks,
                crime_type_filter=crime_type_filter,
                sop_group_filter=None,  # Don't filter by SOP group - retrieve all relevant
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
            # If no documents found but we have SOP/Tier-2/Tier-3 results, return those
            if result.sop_blocks or result.evidence_blocks or result.compensation_blocks or result.general_sop_blocks:
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
