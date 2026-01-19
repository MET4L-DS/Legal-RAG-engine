"""
Indexing and embedding components for the Legal RAG system.

This package contains:
- entries: Index entry dataclasses
- embedder: Hierarchical embedding generator
- store: Multi-level FAISS vector store
"""

from .entries import (
    IndexMetadata,
    LevelIndex,
    SOPIndexEntry,
    EvidenceIndexEntry,
    CompensationIndexEntry,
    GeneralSOPIndexEntry,
)

from .embedder import HierarchicalEmbedder

from .store import MultiLevelVectorStore

__all__ = [
    # Index entries
    "IndexMetadata",
    "LevelIndex",
    "SOPIndexEntry",
    "EvidenceIndexEntry",
    "CompensationIndexEntry",
    "GeneralSOPIndexEntry",
    # Embedder
    "HierarchicalEmbedder",
    # Vector store
    "MultiLevelVectorStore",
]
