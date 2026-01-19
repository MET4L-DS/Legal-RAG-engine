"""
Dependency injection for FastAPI.

Provides singleton RAG engine and LLM client instances.
"""

import logging
from typing import TYPE_CHECKING, Optional

from .config import get_settings

if TYPE_CHECKING:
    from ..retrieval import LegalRAG

logger = logging.getLogger(__name__)

# Global singleton instances
_rag_instance: Optional["LegalRAG"] = None
_llm_client: Optional[object] = None
_is_initialized: bool = False


def _init_llm_client():
    """Initialize Google Gemini LLM client."""
    global _llm_client
    
    settings = get_settings()
    
    if settings.gemini_api_key:
        try:
            from google import genai
            _llm_client = genai.Client(api_key=settings.gemini_api_key)
            logger.info("Gemini LLM client initialized")
        except Exception as e:
            logger.warning(f"Could not initialize Gemini client: {e}")
            _llm_client = None
    else:
        logger.warning("GEMINI_API_KEY not set - LLM answers disabled")
        _llm_client = None
    
    return _llm_client


def _init_rag_engine():
    """Initialize the RAG engine (singleton)."""
    global _rag_instance, _is_initialized
    
    if _is_initialized:
        return _rag_instance
    
    settings = get_settings()
    
    logger.info(f"Loading RAG engine...")
    logger.info(f"  Index dir: {settings.index_dir}")
    logger.info(f"  Model: {settings.embedding_model}")
    
    # Import here to avoid circular imports
    from ..indexing import HierarchicalEmbedder, MultiLevelVectorStore
    from ..retrieval import HierarchicalRetriever, RetrievalConfig, LegalRAG
    
    # Initialize embedder
    embedder = HierarchicalEmbedder(model_name=settings.embedding_model)
    
    # Load vector store
    assert embedder.embedding_dim is not None, "Embedding dimension not initialized"
    store = MultiLevelVectorStore(embedding_dim=embedder.embedding_dim)
    store.load(settings.index_dir)
    
    # Configure retriever
    config = RetrievalConfig(
        top_k_subsections=10,  # Server returns more, let client filter
        use_hybrid_search=True
    )
    
    retriever = HierarchicalRetriever(store, embedder, config)
    
    # Initialize LLM client
    llm_client = _init_llm_client()
    
    # Create RAG instance
    _rag_instance = LegalRAG(retriever, llm_client)
    _is_initialized = True
    
    logger.info("RAG engine loaded successfully")
    
    return _rag_instance


def get_rag() -> "LegalRAG":
    """
    Get the singleton RAG engine instance.
    
    This is the main dependency for API endpoints.
    Indices are loaded once on first call.
    """
    global _rag_instance
    
    if _rag_instance is None:
        _init_rag_engine()
    
    assert _rag_instance is not None, "RAG engine failed to initialize"
    return _rag_instance


def get_llm_client():
    """Get the LLM client (may be None if not configured)."""
    global _llm_client
    return _llm_client


def is_llm_available() -> bool:
    """Check if LLM client is available."""
    return _llm_client is not None


def get_store_stats() -> dict:
    """Get statistics from the loaded vector store."""
    rag = get_rag()
    return rag.retriever.store.get_stats()


def startup_load():
    """
    Pre-load the RAG engine on server startup.
    
    Call this in FastAPI's lifespan to ensure indices are loaded
    before handling requests.
    """
    logger.info("Pre-loading RAG engine on startup...")
    _init_rag_engine()
    logger.info("Startup complete")
