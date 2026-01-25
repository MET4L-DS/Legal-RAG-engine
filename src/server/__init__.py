"""
FastAPI Server for Legal RAG System.

This package provides a thin HTTP wrapper around the LegalRAG engine.
"""

from .main import app
from .adapter import adapt_response, detect_clarification_needed, calculate_confidence
from .schemas import (
    FrontendResponse,
    ClarificationNeeded,
    TierType,
    ConfidenceLevel,
    ClarificationType,
)

__all__ = [
    "app",
    # Adapter
    "adapt_response",
    "detect_clarification_needed", 
    "calculate_confidence",
    # Schemas
    "FrontendResponse",
    "ClarificationNeeded",
    "TierType",
    "ConfidenceLevel",
    "ClarificationType",
]
