"""
Index entry dataclasses for vector storage.

This module defines the metadata structures stored alongside vectors:
- IndexMetadata: Legal document entries
- LevelIndex: Container for FAISS + BM25 indices
- SOPIndexEntry: Tier-1 SOP entries
- EvidenceIndexEntry: Tier-2 evidence entries
- CompensationIndexEntry: Tier-2 compensation entries
- GeneralSOPIndexEntry: Tier-3 general SOP entries
"""

from dataclasses import dataclass, field
from typing import Optional

import faiss
from rank_bm25 import BM25Okapi


@dataclass
class IndexMetadata:
    """Metadata for a single entry in the index."""
    idx: int
    doc_id: str
    chapter_no: str = ""
    chapter_title: str = ""
    section_no: str = ""
    section_title: str = ""
    subsection_no: str = ""
    text: str = ""
    page: int = 0
    type: str = ""
    # SOP-specific fields
    doc_type: str = "law"  # "law" or "sop"
    procedural_stage: str = ""
    stakeholders: list[str] = field(default_factory=list)
    action_type: str = ""
    time_limit: str = ""
    priority: int = 1


@dataclass
class LevelIndex:
    """Vector index for a single hierarchical level."""
    faiss_index: Optional[faiss.Index] = None  # type: ignore
    metadata: list[IndexMetadata] = field(default_factory=list)
    bm25_index: Optional[BM25Okapi] = None  # type: ignore
    texts: list[str] = field(default_factory=list)


@dataclass
class SOPIndexEntry:
    """Metadata for SOP procedural blocks in the index (Tier-1)."""
    idx: int
    doc_id: str
    block_id: str
    title: str
    text: str
    procedural_stage: str
    stakeholders: list[str]
    action_type: str
    time_limit: str
    bnss_sections: list[str]
    bns_sections: list[str]
    page: int
    priority: int


@dataclass
class EvidenceIndexEntry:
    """Metadata for evidence manual blocks in the index (Tier-2)."""
    idx: int
    doc_id: str
    block_id: str
    title: str
    text: str
    evidence_types: list[str]
    investigative_action: str
    stakeholders: list[str]
    failure_impact: str
    linked_stage: str
    case_types: list[str]
    page: int
    priority: int


@dataclass
class CompensationIndexEntry:
    """Metadata for compensation scheme blocks in the index (Tier-2)."""
    idx: int
    doc_id: str
    block_id: str
    title: str
    text: str
    compensation_type: str
    application_stage: str
    authority: str
    crimes_covered: list[str]
    eligibility_criteria: list[str]
    amount_range: str
    requires_conviction: bool
    time_limit: str
    documents_required: list[str]
    bnss_sections: list[str]
    page: int
    priority: int


@dataclass
class GeneralSOPIndexEntry:
    """Metadata for General SOP blocks in the index (Tier-3).
    
    Tier-3 provides citizen-centric procedural guidance for all crimes
    (robbery, theft, assault, murder, cybercrime, etc).
    """
    idx: int
    doc_id: str
    block_id: str
    title: str
    text: str
    sop_group: str  # fir, zero_fir, complaint, non_cognizable, etc.
    procedural_stage: str  # reuses existing stages: fir, investigation, etc.
    stakeholders: list[str]  # citizen, victim, police, io, sho, etc.
    applies_to: list[str]  # crime types: robbery, theft, assault, murder, cybercrime, all
    action_type: str  # procedure, duty, right, timeline, escalation, guideline, technical
    time_limit: str
    legal_references: list[str]  # BNSS/BNS/BSA section references
    page: int
    priority: int
