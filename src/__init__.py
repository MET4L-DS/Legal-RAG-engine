"""
Legal RAG CLI - Hierarchical Legal Document Search

A 3-tier Retrieval-Augmented Generation (RAG) system for Indian legal documents.

Tiers:
    - Tier-1: Sexual offence procedures (rape SOP) - MHA/BPR&D
    - Tier-2: Evidence & compensation (CSI Manual, NALSA Scheme)
    - Tier-3: General citizen procedures for all crimes (General SOP)

Packages:
    - models: Core data models for legal documents
    - parsers: Document parsers (PDF, SOP, Evidence, Compensation, General SOP)
    - indexing: Embedding and vector storage
    - retrieval: Hierarchical retrieval pipeline with tier routing
"""

__version__ = "1.0.0"
__author__ = "Legal RAG CLI"

# Core models
from .models import (
    LegalDocument,
    Chapter,
    Section,
    Subsection,
    SubsectionType,
    SearchResult,
)

# Parsers
from .parsers import (
    # PDF Parser
    LegalPDFParser,
    # Tier-1: Sexual Offence SOP
    SOPDocument,
    ProceduralBlock,
    ProceduralStage,
    Stakeholder,
    ActionType,
    SOPParser,
    # Tier-2: Evidence Manual
    EvidenceManualDocument,
    EvidenceBlock,
    EvidenceType,
    InvestigativeAction,
    FailureImpact,
    EvidenceManualParser,
    # Tier-2: Compensation Scheme
    CompensationSchemeDocument,
    CompensationBlock,
    CompensationType,
    ApplicationStage,
    Authority,
    CrimeCovered,
    CompensationSchemeParser,
    # Tier-3: General SOP
    GeneralSOPDocument,
    GeneralSOPBlock,
    SOPGroup,
    GeneralSOPParser,
)

# Indexing
from .indexing import (
    HierarchicalEmbedder,
    MultiLevelVectorStore,
    IndexMetadata,
    LevelIndex,
    SOPIndexEntry,
    EvidenceIndexEntry,
    CompensationIndexEntry,
    GeneralSOPIndexEntry,
)

# Retrieval
from .retrieval import (
    HierarchicalRetriever,
    LegalRAG,
    RetrievalConfig,
    RetrievalResult,
    detect_query_intent,
    detect_tier2_intent,
    detect_tier3_intent,
    extract_query_hints,
)

__all__ = [
    # Version
    "__version__",
    # Core models
    "LegalDocument",
    "Chapter",
    "Section",
    "Subsection",
    "SubsectionType",
    "SearchResult",
    # PDF Parser
    "LegalPDFParser",
    # Tier-1
    "SOPDocument",
    "ProceduralBlock",
    "ProceduralStage",
    "Stakeholder",
    "ActionType",
    "SOPParser",
    # Tier-2 Evidence
    "EvidenceManualDocument",
    "EvidenceBlock",
    "EvidenceType",
    "InvestigativeAction",
    "FailureImpact",
    "EvidenceManualParser",
    # Tier-2 Compensation
    "CompensationSchemeDocument",
    "CompensationBlock",
    "CompensationType",
    "ApplicationStage",
    "Authority",
    "CrimeCovered",
    "CompensationSchemeParser",
    # Tier-3
    "GeneralSOPDocument",
    "GeneralSOPBlock",
    "SOPGroup",
    "GeneralSOPParser",
    # Indexing
    "HierarchicalEmbedder",
    "MultiLevelVectorStore",
    "IndexMetadata",
    "LevelIndex",
    "SOPIndexEntry",
    "EvidenceIndexEntry",
    "CompensationIndexEntry",
    "GeneralSOPIndexEntry",
    # Retrieval
    "HierarchicalRetriever",
    "LegalRAG",
    "RetrievalConfig",
    "RetrievalResult",
    "detect_query_intent",
    "detect_tier2_intent",
    "detect_tier3_intent",
    "extract_query_hints",
]
