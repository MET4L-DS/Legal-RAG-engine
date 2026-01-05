"""
4-Stage Hierarchical Retrieval Pipeline for Legal RAG.
Implements: Document → Chapter → Section → Subsection retrieval.
"""

import re
from typing import Optional, Any
from dataclasses import dataclass, field
import numpy as np

from .models import SearchResult
from .vector_store import MultiLevelVectorStore
from .embedder import HierarchicalEmbedder


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


@dataclass
class RetrievalResult:
    """Complete result from the retrieval pipeline."""
    query: str
    
    # Results at each level
    documents: list[SearchResult] = field(default_factory=list)
    chapters: list[SearchResult] = field(default_factory=list)
    sections: list[SearchResult] = field(default_factory=list)
    subsections: list[SearchResult] = field(default_factory=list)
    
    # Final context for LLM
    context_text: str = ""
    citations: list[str] = field(default_factory=list)
    
    def get_context_for_llm(self, max_tokens: int = 8000) -> str:
        """Get formatted context for LLM with citations.
        
        Includes both section-level and subsection-level content for better context.
        """
        context_parts = []
        seen_sections = set()
        
        # First, add section-level context (more complete text)
        for result in self.sections:
            section_key = f"{result.doc_id}-{result.section_no}"
            if section_key in seen_sections:
                continue
            seen_sections.add(section_key)
            
            citation = result.get_citation()
            text = result.text
            
            # Estimate tokens (rough: 4 chars per token)
            if len("\n".join(context_parts)) / 4 > max_tokens * 0.6:
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


class HierarchicalRetriever:
    """4-stage hierarchical retrieval pipeline."""
    
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
        """Execute the 4-stage hierarchical retrieval.
        
        Args:
            query: User's legal question
            
        Returns:
            RetrievalResult with results at all levels
        """
        result = RetrievalResult(query=query)
        
        # Extract explicit hints from query (e.g., "section 103 of BNS")
        hints = extract_query_hints(query)
        
        # Enhance query text with topic keywords for better BM25 matching
        enhanced_query = query
        if hints["topic_keywords"]:
            enhanced_query = query + " " + " ".join(hints["topic_keywords"])
        
        # Generate query embedding
        query_embedding = self.embedder.embed_text(query)
        
        # Stage 1: Document Routing
        result.documents = self._stage1_document_routing(query_embedding, enhanced_query)
        
        if not result.documents:
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
    """Complete Legal RAG system combining retrieval with Gemini LLM generation."""
    
    SYSTEM_PROMPT = """You are a legal assistant specializing in Indian law (BNS, BNSS, BSA).
Your task is to answer questions using the provided legal extracts.

Instructions:
1. Carefully read ALL the provided legal extracts
2. Synthesize information from multiple sections if relevant
3. Always cite the specific Section and Chapter (e.g., "BSA Section 57")
4. If the extracts contain relevant information, provide a comprehensive answer
5. Only say you cannot find information if the extracts are truly unrelated to the question
6. Format your answer clearly with sections for: Definition, Procedure, Key Points (as applicable)"""
    
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
            "retrieval": {
                "documents": [self._format_result(r) for r in retrieval_result.documents],
                "chapters": [self._format_result(r) for r in retrieval_result.chapters],
                "sections": [self._format_result(r) for r in retrieval_result.sections],
                "subsections": [self._format_result(r) for r in retrieval_result.subsections]
            },
            "context": retrieval_result.context_text,
            "citations": retrieval_result.citations,
            "answer": None
        }
        
        # Generate answer if LLM client is available
        if generate_answer and self.llm_client and retrieval_result.context_text:
            response["answer"] = self._generate_answer(
                question, 
                retrieval_result.context_text
            )
        
        return response
    
    def _format_result(self, result: SearchResult) -> dict:
        """Format a search result for output."""
        return {
            "citation": result.get_citation(),
            "text": result.text[:500] + "..." if len(result.text) > 500 else result.text,
            "score": round(result.score, 4),
            "level": result.level,
            "metadata": result.metadata
        }
    
    def _generate_answer(self, question: str, context: str) -> str:
        """Generate answer using Google Gemini with retry logic."""
        import time
        
        full_prompt = f"""{self.SYSTEM_PROMPT}

Based on the following legal extracts, answer the question.

Legal Extracts:
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
