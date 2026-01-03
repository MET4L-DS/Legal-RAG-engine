"""
4-Stage Hierarchical Retrieval Pipeline for Legal RAG.
Implements: Document → Chapter → Section → Subsection retrieval.
"""

from typing import Optional
from dataclasses import dataclass, field
import numpy as np

from .models import SearchResult
from .vector_store import MultiLevelVectorStore
from .embedder import HierarchicalEmbedder


@dataclass
class RetrievalConfig:
    """Configuration for the retrieval pipeline."""
    # Number of results at each stage
    top_k_documents: int = 3
    top_k_chapters: int = 5
    top_k_sections: int = 8
    top_k_subsections: int = 15
    
    # Score thresholds for filtering (lowered for better recall)
    min_doc_score: float = 0.25
    min_chapter_score: float = 0.25
    min_section_score: float = 0.25
    min_subsection_score: float = 0.25
    
    # Enable/disable hybrid search
    use_hybrid_search: bool = True
    
    # Enable/disable hierarchical filtering
    use_hierarchical_filtering: bool = True


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
        
        # Generate query embedding
        query_embedding = self.embedder.embed_text(query)
        
        # Stage 1: Document Routing
        result.documents = self._stage1_document_routing(query_embedding, query)
        
        if not result.documents:
            return result
        
        # Get document filter for next stages
        doc_filter = None
        if self.config.use_hierarchical_filtering and result.documents:
            # Use top scoring document
            doc_filter = result.documents[0].doc_id
        
        # Stage 2: Chapter Search
        result.chapters = self._stage2_chapter_search(
            query_embedding, query, doc_filter
        )
        
        # Get chapter filter for next stages
        chapter_filter = None
        if self.config.use_hierarchical_filtering and result.chapters:
            chapter_filter = [c.chapter_no for c in result.chapters]
        
        # Stage 3: Section Search
        result.sections = self._stage3_section_search(
            query_embedding, query, doc_filter, chapter_filter
        )
        
        # Get section filter for final stage
        section_filter = None
        if self.config.use_hierarchical_filtering and result.sections:
            section_filter = [s.section_no for s in result.sections]
        
        # Stage 4: Subsection Search (Final Answer)
        result.subsections = self._stage4_subsection_search(
            query_embedding, query, doc_filter, chapter_filter, section_filter
        )
        
        # Build context
        result.get_context_for_llm()
        
        return result
    
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
    
    SYSTEM_PROMPT = """You are a legal assistant specializing in Indian law.
Your role is to answer questions based ONLY on the provided legal extracts.

Rules:
1. Answer ONLY from the provided legal extracts
2. Always cite the specific Section and Chapter
3. If the answer is not in the extracts, say: "I could not find this information in the provided legal documents."
4. Be precise and use legal terminology appropriately
5. If multiple sections are relevant, cite all of them
6. Format punishments, definitions, and explanations clearly"""
    
    def __init__(
        self,
        retriever: HierarchicalRetriever,
        llm_client = None,
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
                    response = self.llm_client.models.generate_content(
                        model=model,
                        contents=full_prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.1,
                            max_output_tokens=1000,
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
