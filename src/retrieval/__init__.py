"""
Retrieval components for the Legal RAG system.

This package contains:
- intent: Query intent detection for tier routing
- config: Retrieval configuration and result classes
- retriever: Hierarchical retrieval pipeline
- rag: Complete RAG system with LLM integration
"""

from .intent import (
    detect_query_intent,
    detect_tier2_intent,
    detect_tier3_intent,
    extract_query_hints,
)

from .config import (
    RetrievalConfig,
    RetrievalResult,
)

from .retriever import HierarchicalRetriever

from .rag import LegalRAG

__all__ = [
    # Intent detection
    "detect_query_intent",
    "detect_tier2_intent",
    "detect_tier3_intent",
    "extract_query_hints",
    # Config
    "RetrievalConfig",
    "RetrievalResult",
    # Retriever
    "HierarchicalRetriever",
    # RAG
    "LegalRAG",
]
