"""
Data models for the Legal RAG system.

This package contains all data models organized by domain:
- legal: Core legal document models (LegalDocument, Chapter, Section, Subsection)
- search: Search result models
"""

from .legal import (
    SubsectionType,
    Subsection,
    Section,
    Chapter,
    LegalDocument,
)

from .search import SearchResult

__all__ = [
    # Legal document models
    "SubsectionType",
    "Subsection",
    "Section",
    "Chapter",
    "LegalDocument",
    # Search models
    "SearchResult",
]
