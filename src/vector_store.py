"""
Multi-Index Vector Storage using FAISS.
Maintains separate indices for each hierarchical level.
"""

import json
import faiss
import numpy as np
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from rank_bm25 import BM25Okapi

from .models import LegalDocument, SearchResult
from .sop_parser import SOPDocument, ProceduralBlock, ProceduralStage
from .evidence_parser import EvidenceManualDocument, EvidenceBlock
from .compensation_parser import CompensationSchemeDocument, CompensationBlock
from .general_sop_parser import GeneralSOPDocument, GeneralSOPBlock


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
    """Metadata for SOP procedural blocks in the index."""
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


class MultiLevelVectorStore:
    """Multi-level vector store with FAISS indices and BM25."""
    
    def __init__(self, embedding_dim: int = 384):
        """Initialize the multi-level store.
        
        Args:
            embedding_dim: Dimension of the embeddings (384 for MiniLM)
        """
        self.embedding_dim = embedding_dim
        
        # Separate indices for each level
        self.doc_index = LevelIndex()
        self.chapter_index = LevelIndex()
        self.section_index = LevelIndex()
        self.subsection_index = LevelIndex()
        
        # SOP-specific index (procedural blocks at same level as sections)
        self.sop_index = LevelIndex()
        self.sop_metadata: list[SOPIndexEntry] = []
        
        # Tier-2: Evidence Manual index (conditional depth layer)
        self.evidence_index = LevelIndex()
        self.evidence_metadata: list[EvidenceIndexEntry] = []
        
        # Tier-2: Compensation Scheme index (conditional depth layer)
        self.compensation_index = LevelIndex()
        self.compensation_metadata: list[CompensationIndexEntry] = []
        
        # Tier-3: General SOP index (citizen-centric guidance for all crimes)
        self.general_sop_index = LevelIndex()
        self.general_sop_metadata: list[GeneralSOPIndexEntry] = []
        
        # Initialize FAISS indices
        self._init_faiss_indices()
    
    def _init_faiss_indices(self):
        """Initialize FAISS indices for each level."""
        # Using IndexFlatIP for inner product (cosine similarity with normalized vectors)
        self.doc_index.faiss_index = faiss.IndexFlatIP(self.embedding_dim)
        self.chapter_index.faiss_index = faiss.IndexFlatIP(self.embedding_dim)
        self.section_index.faiss_index = faiss.IndexFlatIP(self.embedding_dim)
        self.subsection_index.faiss_index = faiss.IndexFlatIP(self.embedding_dim)
        self.sop_index.faiss_index = faiss.IndexFlatIP(self.embedding_dim)
        # Tier-2 indices
        self.evidence_index.faiss_index = faiss.IndexFlatIP(self.embedding_dim)
        self.compensation_index.faiss_index = faiss.IndexFlatIP(self.embedding_dim)
        # Tier-3 index
        self.general_sop_index.faiss_index = faiss.IndexFlatIP(self.embedding_dim)
    
    def add_document(self, doc: LegalDocument):
        """Add a document with all its hierarchy to the indices."""
        
        # Add document level
        if doc.embedding:
            self._add_to_level(
                self.doc_index,
                np.array([doc.embedding], dtype=np.float32),
                IndexMetadata(
                    idx=len(self.doc_index.metadata),
                    doc_id=doc.doc_id,
                    text=doc.summary or doc.title
                )
            )
        
        # Add chapters
        for chapter in doc.chapters:
            if chapter.embedding:
                self._add_to_level(
                    self.chapter_index,
                    np.array([chapter.embedding], dtype=np.float32),
                    IndexMetadata(
                        idx=len(self.chapter_index.metadata),
                        doc_id=doc.doc_id,
                        chapter_no=chapter.chapter_no,
                        chapter_title=chapter.chapter_title,
                        text=chapter.summary or f"Chapter {chapter.chapter_no}: {chapter.chapter_title}",
                        page=chapter.page_start
                    )
                )
            
            # Add sections
            for section in chapter.sections:
                if section.embedding:
                    self._add_to_level(
                        self.section_index,
                        np.array([section.embedding], dtype=np.float32),
                        IndexMetadata(
                            idx=len(self.section_index.metadata),
                            doc_id=doc.doc_id,
                            chapter_no=chapter.chapter_no,
                            chapter_title=chapter.chapter_title,
                            section_no=section.section_no,
                            section_title=section.section_title,
                            text=f"Section {section.section_no}: {section.section_title}\n{section.full_text[:2000]}",
                            page=section.page_start
                        )
                    )
                
                # Add subsections
                for subsection in section.subsections:
                    if subsection.embedding:
                        self._add_to_level(
                            self.subsection_index,
                            np.array([subsection.embedding], dtype=np.float32),
                            IndexMetadata(
                                idx=len(self.subsection_index.metadata),
                                doc_id=doc.doc_id,
                                chapter_no=chapter.chapter_no,
                                chapter_title=chapter.chapter_title,
                                section_no=section.section_no,
                                section_title=section.section_title,
                                subsection_no=subsection.subsection_no,
                                text=subsection.text,
                                page=subsection.page,
                                type=subsection.type.value
                            )
                        )
    
    def add_sop_document(self, sop: SOPDocument):
        """Add an SOP document with all its procedural blocks to the index."""
        
        # Add SOP document level
        if sop.embedding:
            self._add_to_level(
                self.doc_index,
                np.array([sop.embedding], dtype=np.float32),
                IndexMetadata(
                    idx=len(self.doc_index.metadata),
                    doc_id=sop.doc_id,
                    text=sop.title,
                    doc_type="sop"
                )
            )
        
        # Add procedural blocks (treated at section level for retrieval)
        for block in sop.blocks:
            if block.embedding:
                # Add to SOP index
                embedding = np.array([block.embedding], dtype=np.float32)
                embedding = embedding / np.linalg.norm(embedding, axis=1, keepdims=True)
                
                self.sop_index.faiss_index.add(embedding)  # type: ignore
                
                # Store SOP-specific metadata
                sop_entry = SOPIndexEntry(
                    idx=len(self.sop_metadata),
                    doc_id=sop.doc_id,
                    block_id=block.block_id,
                    title=block.title,
                    text=block.text,
                    procedural_stage=block.procedural_stage.value,
                    stakeholders=[s.value for s in block.stakeholders],
                    action_type=block.action_type.value,
                    time_limit=block.time_limit or "",
                    bnss_sections=block.bnss_sections,
                    bns_sections=block.bns_sections,
                    page=block.page,
                    priority=block.priority
                )
                self.sop_metadata.append(sop_entry)
                self.sop_index.texts.append(f"{block.title}\n{block.text}")
    
    def search_sop_blocks(
        self,
        query_embedding: np.ndarray,
        query_text: str = "",
        k: int = 5,
        stage_filter: Optional[list[str]] = None,
        stakeholder_filter: Optional[list[str]] = None,
        use_hybrid: bool = True
    ) -> list[SearchResult]:
        """Search SOP procedural blocks.
        
        Args:
            query_embedding: Query vector
            query_text: Query text for BM25
            k: Number of results
            stage_filter: Filter by procedural stages (e.g., ["fir", "investigation"])
            stakeholder_filter: Filter by stakeholders (e.g., ["victim", "police"])
            use_hybrid: Whether to use hybrid search
        
        Returns:
            List of SearchResult with SOP-specific metadata
        """
        if self.sop_index.faiss_index.ntotal == 0:  # type: ignore
            return []
        
        search_k = min(k * 3, self.sop_index.faiss_index.ntotal)  # type: ignore
        
        # Normalize query embedding
        query_embedding = query_embedding.reshape(1, -1).astype(np.float32)
        query_embedding = query_embedding / np.linalg.norm(query_embedding)
        
        # Vector search
        vector_scores, vector_indices = self.sop_index.faiss_index.search(query_embedding, search_k)  # type: ignore
        vector_scores = vector_scores[0]
        vector_indices = vector_indices[0]
        
        # Create results map
        results_map = {}
        for score, idx in zip(vector_scores, vector_indices):
            if idx >= 0 and idx < len(self.sop_metadata):
                results_map[idx] = {
                    "vector_score": float(score),
                    "bm25_score": 0.0
                }
        
        # BM25 search if enabled
        if use_hybrid and self.sop_index.bm25_index and query_text:
            query_tokens = query_text.lower().split()
            bm25_scores = self.sop_index.bm25_index.get_scores(query_tokens)
            
            bm25_top_indices = np.argsort(bm25_scores)[::-1][:search_k]
            
            for idx in bm25_top_indices:
                if bm25_scores[idx] > 0:
                    if idx in results_map:
                        results_map[idx]["bm25_score"] = float(bm25_scores[idx])
                    else:
                        results_map[idx] = {
                            "vector_score": 0.0,
                            "bm25_score": float(bm25_scores[idx])
                        }
        
        # Build results with SOP metadata
        results = []
        for idx, scores in results_map.items():
            meta = self.sop_metadata[idx]
            
            # Apply filters
            if stage_filter and meta.procedural_stage not in stage_filter:
                continue
            if stakeholder_filter and not any(s in meta.stakeholders for s in stakeholder_filter):
                continue
            
            # Calculate combined score with priority boost
            vector_score = scores["vector_score"]
            bm25_score = scores["bm25_score"]
            
            if use_hybrid and bm25_score > 0:
                combined_score = 0.4 * vector_score + 0.6 * min(bm25_score / 10, 1.0)
            else:
                combined_score = vector_score
            
            # Boost by priority (normalized)
            priority_boost = meta.priority / 10.0
            combined_score = combined_score * (1 + priority_boost)
            
            results.append(SearchResult(
                doc_id=meta.doc_id,
                chapter_no="",  # SOPs don't have chapters
                section_no=meta.block_id,  # Use block_id as section identifier
                subsection_no="",
                text=meta.text,
                score=combined_score,
                level="sop_block",
                metadata={
                    "title": meta.title,
                    "procedural_stage": meta.procedural_stage,
                    "stakeholders": meta.stakeholders,
                    "action_type": meta.action_type,
                    "time_limit": meta.time_limit,
                    "bnss_sections": meta.bnss_sections,
                    "bns_sections": meta.bns_sections,
                    "page": meta.page,
                    "priority": meta.priority,
                    "doc_type": "sop",
                    "vector_score": scores["vector_score"],
                    "bm25_score": scores["bm25_score"]
                }
            ))
        
        # Sort by score
        results.sort(key=lambda x: x.score, reverse=True)
        
        return results[:k]
    
    # =========================================================================
    # TIER-2: EVIDENCE MANUAL SUPPORT
    # =========================================================================
    
    def add_evidence_document(self, evidence_doc: EvidenceManualDocument):
        """Add an Evidence Manual document with all its blocks to the index (Tier-2)."""
        
        # Add evidence document level
        if evidence_doc.embedding:
            self._add_to_level(
                self.doc_index,
                np.array([evidence_doc.embedding], dtype=np.float32),
                IndexMetadata(
                    idx=len(self.doc_index.metadata),
                    doc_id=evidence_doc.doc_id,
                    text=evidence_doc.title,
                    doc_type="evidence_manual"
                )
            )
        
        # Add evidence blocks
        for block in evidence_doc.blocks:
            if block.embedding:
                embedding = np.array([block.embedding], dtype=np.float32)
                embedding = embedding / np.linalg.norm(embedding, axis=1, keepdims=True)
                
                self.evidence_index.faiss_index.add(embedding)  # type: ignore
                
                # Store evidence-specific metadata
                evidence_entry = EvidenceIndexEntry(
                    idx=len(self.evidence_metadata),
                    doc_id=evidence_doc.doc_id,
                    block_id=block.block_id,
                    title=block.title,
                    text=block.text,
                    evidence_types=[e.value for e in block.evidence_types],
                    investigative_action=block.investigative_action.value,
                    stakeholders=block.stakeholders,
                    failure_impact=block.failure_impact.value,
                    linked_stage=block.linked_stage,
                    case_types=block.case_types,
                    page=block.page,
                    priority=block.priority
                )
                self.evidence_metadata.append(evidence_entry)
                self.evidence_index.texts.append(f"{block.title}\n{block.text}")
    
    def search_evidence_blocks(
        self,
        query_embedding: np.ndarray,
        query_text: str = "",
        k: int = 5,
        evidence_type_filter: Optional[list[str]] = None,
        case_type_filter: Optional[list[str]] = None,
        use_hybrid: bool = True
    ) -> list[SearchResult]:
        """Search Evidence Manual blocks (Tier-2).
        
        Args:
            query_embedding: Query vector
            query_text: Query text for BM25
            k: Number of results
            evidence_type_filter: Filter by evidence types (e.g., ["biological", "digital"])
            case_type_filter: Filter by case types (e.g., ["rape", "murder"])
            use_hybrid: Whether to use hybrid search
        
        Returns:
            List of SearchResult with evidence-specific metadata
        """
        if self.evidence_index.faiss_index.ntotal == 0:  # type: ignore
            return []
        
        search_k = min(k * 3, self.evidence_index.faiss_index.ntotal)  # type: ignore
        
        # Normalize query embedding
        query_embedding = query_embedding.reshape(1, -1).astype(np.float32)
        query_embedding = query_embedding / np.linalg.norm(query_embedding)
        
        # Vector search
        vector_scores, vector_indices = self.evidence_index.faiss_index.search(query_embedding, search_k)  # type: ignore
        vector_scores = vector_scores[0]
        vector_indices = vector_indices[0]
        
        # Create results map
        results_map = {}
        for score, idx in zip(vector_scores, vector_indices):
            if idx >= 0 and idx < len(self.evidence_metadata):
                results_map[idx] = {
                    "vector_score": float(score),
                    "bm25_score": 0.0
                }
        
        # BM25 search if enabled
        if use_hybrid and self.evidence_index.bm25_index and query_text:
            query_tokens = query_text.lower().split()
            bm25_scores = self.evidence_index.bm25_index.get_scores(query_tokens)
            
            bm25_top_indices = np.argsort(bm25_scores)[::-1][:search_k]
            
            for idx in bm25_top_indices:
                if bm25_scores[idx] > 0:
                    if idx in results_map:
                        results_map[idx]["bm25_score"] = float(bm25_scores[idx])
                    else:
                        results_map[idx] = {
                            "vector_score": 0.0,
                            "bm25_score": float(bm25_scores[idx])
                        }
        
        # Build results with evidence metadata
        results = []
        for idx, scores in results_map.items():
            meta = self.evidence_metadata[idx]
            
            # Apply filters
            if evidence_type_filter and not any(e in meta.evidence_types for e in evidence_type_filter):
                continue
            if case_type_filter and not any(c in meta.case_types for c in case_type_filter) and "all" not in meta.case_types:
                continue
            
            # Calculate combined score with priority boost
            vector_score = scores["vector_score"]
            bm25_score = scores["bm25_score"]
            
            if use_hybrid and bm25_score > 0:
                combined_score = 0.4 * vector_score + 0.6 * min(bm25_score / 10, 1.0)
            else:
                combined_score = vector_score
            
            # Boost by priority
            priority_boost = meta.priority / 10.0
            combined_score = combined_score * (1 + priority_boost)
            
            results.append(SearchResult(
                doc_id=meta.doc_id,
                chapter_no="",
                section_no=meta.block_id,
                subsection_no="",
                text=meta.text,
                score=combined_score,
                level="evidence_block",
                metadata={
                    "title": meta.title,
                    "evidence_types": meta.evidence_types,
                    "investigative_action": meta.investigative_action,
                    "stakeholders": meta.stakeholders,
                    "failure_impact": meta.failure_impact,
                    "linked_stage": meta.linked_stage,
                    "case_types": meta.case_types,
                    "page": meta.page,
                    "priority": meta.priority,
                    "doc_type": "evidence_manual",
                    "vector_score": scores["vector_score"],
                    "bm25_score": scores["bm25_score"]
                }
            ))
        
        # Sort by score
        results.sort(key=lambda x: x.score, reverse=True)
        
        return results[:k]
    
    # =========================================================================
    # TIER-2: COMPENSATION SCHEME SUPPORT
    # =========================================================================
    
    def add_compensation_document(self, comp_doc: CompensationSchemeDocument):
        """Add a Compensation Scheme document with all its blocks to the index (Tier-2)."""
        
        # Add compensation document level
        if comp_doc.embedding:
            self._add_to_level(
                self.doc_index,
                np.array([comp_doc.embedding], dtype=np.float32),
                IndexMetadata(
                    idx=len(self.doc_index.metadata),
                    doc_id=comp_doc.doc_id,
                    text=comp_doc.title,
                    doc_type="compensation_scheme"
                )
            )
        
        # Add compensation blocks
        for block in comp_doc.blocks:
            if block.embedding:
                embedding = np.array([block.embedding], dtype=np.float32)
                embedding = embedding / np.linalg.norm(embedding, axis=1, keepdims=True)
                
                self.compensation_index.faiss_index.add(embedding)  # type: ignore
                
                # Store compensation-specific metadata
                comp_entry = CompensationIndexEntry(
                    idx=len(self.compensation_metadata),
                    doc_id=comp_doc.doc_id,
                    block_id=block.block_id,
                    title=block.title,
                    text=block.text,
                    compensation_type=block.compensation_type.value,
                    application_stage=block.application_stage.value,
                    authority=block.authority.value,
                    crimes_covered=[c.value for c in block.crimes_covered],
                    eligibility_criteria=block.eligibility_criteria,
                    amount_range=block.amount_range or "",
                    requires_conviction=block.requires_conviction,
                    time_limit=block.time_limit or "",
                    documents_required=block.documents_required,
                    bnss_sections=block.bnss_sections,
                    page=block.page,
                    priority=block.priority
                )
                self.compensation_metadata.append(comp_entry)
                self.compensation_index.texts.append(f"{block.title}\n{block.text}")
    
    def search_compensation_blocks(
        self,
        query_embedding: np.ndarray,
        query_text: str = "",
        k: int = 5,
        crime_filter: Optional[list[str]] = None,
        compensation_type_filter: Optional[list[str]] = None,
        use_hybrid: bool = True
    ) -> list[SearchResult]:
        """Search Compensation Scheme blocks (Tier-2).
        
        Args:
            query_embedding: Query vector
            query_text: Query text for BM25
            k: Number of results
            crime_filter: Filter by crimes covered (e.g., ["rape", "acid_attack"])
            compensation_type_filter: Filter by compensation type (e.g., ["interim", "final"])
            use_hybrid: Whether to use hybrid search
        
        Returns:
            List of SearchResult with compensation-specific metadata
        """
        if self.compensation_index.faiss_index.ntotal == 0:  # type: ignore
            return []
        
        search_k = min(k * 3, self.compensation_index.faiss_index.ntotal)  # type: ignore
        
        # Normalize query embedding
        query_embedding = query_embedding.reshape(1, -1).astype(np.float32)
        query_embedding = query_embedding / np.linalg.norm(query_embedding)
        
        # Vector search
        vector_scores, vector_indices = self.compensation_index.faiss_index.search(query_embedding, search_k)  # type: ignore
        vector_scores = vector_scores[0]
        vector_indices = vector_indices[0]
        
        # Create results map
        results_map = {}
        for score, idx in zip(vector_scores, vector_indices):
            if idx >= 0 and idx < len(self.compensation_metadata):
                results_map[idx] = {
                    "vector_score": float(score),
                    "bm25_score": 0.0
                }
        
        # BM25 search if enabled
        if use_hybrid and self.compensation_index.bm25_index and query_text:
            query_tokens = query_text.lower().split()
            bm25_scores = self.compensation_index.bm25_index.get_scores(query_tokens)
            
            bm25_top_indices = np.argsort(bm25_scores)[::-1][:search_k]
            
            for idx in bm25_top_indices:
                if bm25_scores[idx] > 0:
                    if idx in results_map:
                        results_map[idx]["bm25_score"] = float(bm25_scores[idx])
                    else:
                        results_map[idx] = {
                            "vector_score": 0.0,
                            "bm25_score": float(bm25_scores[idx])
                        }
        
        # Build results with compensation metadata
        results = []
        for idx, scores in results_map.items():
            meta = self.compensation_metadata[idx]
            
            # Apply filters
            if crime_filter and not any(c in meta.crimes_covered for c in crime_filter) and "other" not in meta.crimes_covered:
                continue
            if compensation_type_filter and meta.compensation_type not in compensation_type_filter:
                continue
            
            # Calculate combined score with priority boost
            vector_score = scores["vector_score"]
            bm25_score = scores["bm25_score"]
            
            if use_hybrid and bm25_score > 0:
                combined_score = 0.4 * vector_score + 0.6 * min(bm25_score / 10, 1.0)
            else:
                combined_score = vector_score
            
            # Boost by priority
            priority_boost = meta.priority / 10.0
            combined_score = combined_score * (1 + priority_boost)
            
            results.append(SearchResult(
                doc_id=meta.doc_id,
                chapter_no="",
                section_no=meta.block_id,
                subsection_no="",
                text=meta.text,
                score=combined_score,
                level="compensation_block",
                metadata={
                    "title": meta.title,
                    "compensation_type": meta.compensation_type,
                    "application_stage": meta.application_stage,
                    "authority": meta.authority,
                    "crimes_covered": meta.crimes_covered,
                    "eligibility_criteria": meta.eligibility_criteria,
                    "amount_range": meta.amount_range,
                    "requires_conviction": meta.requires_conviction,
                    "time_limit": meta.time_limit,
                    "documents_required": meta.documents_required,
                    "bnss_sections": meta.bnss_sections,
                    "page": meta.page,
                    "priority": meta.priority,
                    "doc_type": "compensation_scheme",
                    "vector_score": scores["vector_score"],
                    "bm25_score": scores["bm25_score"]
                }
            ))
        
        # Sort by score
        results.sort(key=lambda x: x.score, reverse=True)
        
        return results[:k]
    
    # =========================================================================
    # TIER-3: GENERAL SOP SUPPORT (Citizen-Centric Procedural Guidance)
    # =========================================================================
    
    def add_general_sop_document(self, general_sop_doc: GeneralSOPDocument):
        """Add a General SOP document with all its blocks to the index (Tier-3).
        
        Tier-3 provides citizen-centric procedural guidance for all crimes
        (robbery, theft, assault, murder, cybercrime, etc).
        """
        
        # Add General SOP document level
        if general_sop_doc.embedding:
            self._add_to_level(
                self.doc_index,
                np.array([general_sop_doc.embedding], dtype=np.float32),
                IndexMetadata(
                    idx=len(self.doc_index.metadata),
                    doc_id=general_sop_doc.doc_id,
                    text=general_sop_doc.title,
                    doc_type="general_sop"
                )
            )
        
        # Add General SOP blocks
        for block in general_sop_doc.blocks:
            if block.embedding:
                embedding = np.array([block.embedding], dtype=np.float32)
                embedding = embedding / np.linalg.norm(embedding, axis=1, keepdims=True)
                
                self.general_sop_index.faiss_index.add(embedding)  # type: ignore
                
                # Store General SOP-specific metadata
                general_sop_entry = GeneralSOPIndexEntry(
                    idx=len(self.general_sop_metadata),
                    doc_id=general_sop_doc.doc_id,
                    block_id=block.block_id,
                    title=block.title,
                    text=block.text,
                    sop_group=block.sop_group.value,
                    procedural_stage=block.procedural_stage.value,
                    stakeholders=[s.value for s in block.stakeholders],
                    applies_to=block.applies_to,
                    action_type=block.action_type.value,
                    time_limit=block.time_limit or "",
                    legal_references=block.legal_references,
                    page=block.page,
                    priority=block.priority
                )
                self.general_sop_metadata.append(general_sop_entry)
                self.general_sop_index.texts.append(f"{block.title}\n{block.text}")
    
    def search_general_sop_blocks(
        self,
        query_embedding: np.ndarray,
        query_text: str = "",
        k: int = 5,
        crime_type_filter: Optional[list[str]] = None,
        sop_group_filter: Optional[list[str]] = None,
        stakeholder_filter: Optional[list[str]] = None,
        use_hybrid: bool = True
    ) -> list[SearchResult]:
        """Search General SOP blocks (Tier-3).
        
        Args:
            query_embedding: Query vector
            query_text: Query text for BM25
            k: Number of results
            crime_type_filter: Filter by applicable crimes (e.g., ["robbery", "theft"])
            sop_group_filter: Filter by SOP groups (e.g., ["fir", "zero_fir"])
            stakeholder_filter: Filter by stakeholders (e.g., ["citizen", "victim"])
            use_hybrid: Whether to use hybrid search
        
        Returns:
            List of SearchResult with General SOP-specific metadata
        """
        if self.general_sop_index.faiss_index.ntotal == 0:  # type: ignore
            return []
        
        search_k = min(k * 3, self.general_sop_index.faiss_index.ntotal)  # type: ignore
        
        # Normalize query embedding
        query_embedding = query_embedding.reshape(1, -1).astype(np.float32)
        query_embedding = query_embedding / np.linalg.norm(query_embedding)
        
        # Vector search
        vector_scores, vector_indices = self.general_sop_index.faiss_index.search(query_embedding, search_k)  # type: ignore
        vector_scores = vector_scores[0]
        vector_indices = vector_indices[0]
        
        # Create results map
        results_map = {}
        for score, idx in zip(vector_scores, vector_indices):
            if idx >= 0 and idx < len(self.general_sop_metadata):
                results_map[idx] = {
                    "vector_score": float(score),
                    "bm25_score": 0.0
                }
        
        # BM25 search if enabled
        if use_hybrid and self.general_sop_index.bm25_index and query_text:
            query_tokens = query_text.lower().split()
            bm25_scores = self.general_sop_index.bm25_index.get_scores(query_tokens)
            
            bm25_top_indices = np.argsort(bm25_scores)[::-1][:search_k]
            
            for idx in bm25_top_indices:
                if bm25_scores[idx] > 0:
                    if idx in results_map:
                        results_map[idx]["bm25_score"] = float(bm25_scores[idx])
                    else:
                        results_map[idx] = {
                            "vector_score": 0.0,
                            "bm25_score": float(bm25_scores[idx])
                        }
        
        # Build results with General SOP metadata
        results = []
        for idx, scores in results_map.items():
            meta = self.general_sop_metadata[idx]
            
            # Apply filters
            if crime_type_filter:
                # Check if any specified crime matches or if block applies to "all"
                if not any(c in meta.applies_to for c in crime_type_filter) and "all" not in meta.applies_to:
                    continue
            if sop_group_filter and meta.sop_group not in sop_group_filter:
                continue
            if stakeholder_filter and not any(s in meta.stakeholders for s in stakeholder_filter):
                continue
            
            # Calculate combined score with priority boost
            vector_score = scores["vector_score"]
            bm25_score = scores["bm25_score"]
            
            if use_hybrid and bm25_score > 0:
                combined_score = 0.4 * vector_score + 0.6 * min(bm25_score / 10, 1.0)
            else:
                combined_score = vector_score
            
            # Boost by priority (normalized)
            priority_boost = meta.priority / 10.0
            combined_score = combined_score * (1 + priority_boost)
            
            results.append(SearchResult(
                doc_id=meta.doc_id,
                chapter_no="",
                section_no=meta.block_id,
                subsection_no="",
                text=meta.text,
                score=combined_score,
                level="general_sop_block",
                metadata={
                    "title": meta.title,
                    "sop_group": meta.sop_group,
                    "procedural_stage": meta.procedural_stage,
                    "stakeholders": meta.stakeholders,
                    "applies_to": meta.applies_to,
                    "action_type": meta.action_type,
                    "time_limit": meta.time_limit,
                    "legal_references": meta.legal_references,
                    "page": meta.page,
                    "priority": meta.priority,
                    "doc_type": "general_sop",
                    "vector_score": scores["vector_score"],
                    "bm25_score": scores["bm25_score"]
                }
            ))
        
        # Sort by score
        results.sort(key=lambda x: x.score, reverse=True)
        
        return results[:k]
    
    def _add_to_level(
        self, 
        level_index: LevelIndex, 
        embedding: np.ndarray,
        metadata: IndexMetadata
    ):
        """Add an entry to a level index."""
        # Normalize embedding for cosine similarity
        embedding = embedding / np.linalg.norm(embedding, axis=1, keepdims=True)
        
        level_index.faiss_index.add(embedding)  # type: ignore
        level_index.metadata.append(metadata)
        level_index.texts.append(metadata.text)
    
    def build_bm25_indices(self):
        """Build BM25 indices for keyword search at each level."""
        print("Building BM25 indices...")
        
        for name, index in [
            ("documents", self.doc_index),
            ("chapters", self.chapter_index),
            ("sections", self.section_index),
            ("subsections", self.subsection_index),
            ("sop_blocks", self.sop_index),
            ("evidence_blocks", self.evidence_index),
            ("compensation_blocks", self.compensation_index),
            ("general_sop_blocks", self.general_sop_index)
        ]:
            if index.texts:
                # Tokenize texts
                tokenized = [text.lower().split() for text in index.texts]
                index.bm25_index = BM25Okapi(tokenized)
                print(f"  → {name}: {len(index.texts)} entries")
    
    def search_documents(
        self, 
        query_embedding: np.ndarray, 
        query_text: str = "",
        k: int = 3,
        use_hybrid: bool = True
    ) -> list[SearchResult]:
        """Search at document level."""
        return self._hybrid_search(
            self.doc_index, query_embedding, query_text, k, "document", use_hybrid
        )
    
    def search_chapters(
        self, 
        query_embedding: np.ndarray, 
        query_text: str = "",
        k: int = 5,
        doc_filter: Optional[str] = None,
        use_hybrid: bool = True
    ) -> list[SearchResult]:
        """Search at chapter level with optional document filter."""
        results = self._hybrid_search(
            self.chapter_index, query_embedding, query_text, k * 2, "chapter", use_hybrid
        )
        
        if doc_filter:
            results = [r for r in results if r.doc_id == doc_filter]
        
        return results[:k]
    
    def lookup_section_by_number(
        self,
        section_no: str,
        doc_filter: Optional[str] = None
    ) -> list[SearchResult]:
        """Direct lookup of sections by section number (no semantic search).
        
        Use this when user explicitly references a section number.
        """
        results = []
        for meta in self.section_index.metadata:
            if meta.section_no == section_no:
                if doc_filter is None or meta.doc_id == doc_filter:
                    results.append(SearchResult(
                        doc_id=meta.doc_id,
                        chapter_no=meta.chapter_no,
                        section_no=meta.section_no,
                        subsection_no=meta.subsection_no,
                        text=meta.text,
                        score=1.0,  # Exact match
                        level="section",
                        metadata={
                            "chapter_title": meta.chapter_title,
                            "section_title": meta.section_title,
                            "page": meta.page,
                            "type": meta.type
                        }
                    ))
        return results
    
    def lookup_subsections_by_section(
        self,
        section_no: str,
        doc_filter: Optional[str] = None
    ) -> list[SearchResult]:
        """Direct lookup of subsections by section number (no semantic search).
        
        Use this when user explicitly references a section number.
        """
        results = []
        for meta in self.subsection_index.metadata:
            if meta.section_no == section_no:
                if doc_filter is None or meta.doc_id == doc_filter:
                    results.append(SearchResult(
                        doc_id=meta.doc_id,
                        chapter_no=meta.chapter_no,
                        section_no=meta.section_no,
                        subsection_no=meta.subsection_no,
                        text=meta.text,
                        score=1.0,  # Exact match
                        level="subsection",
                        metadata={
                            "chapter_title": meta.chapter_title,
                            "section_title": meta.section_title,
                            "page": meta.page,
                            "type": meta.type
                        }
                    ))
        return results
    
    def search_sections(
        self, 
        query_embedding: np.ndarray, 
        query_text: str = "",
        k: int = 10,
        doc_filter: Optional[str] = None,
        chapter_filter: Optional[list[str]] = None,
        use_hybrid: bool = True
    ) -> list[SearchResult]:
        """Search at section level with optional filters."""
        results = self._hybrid_search(
            self.section_index, query_embedding, query_text, k * 3, "section", use_hybrid
        )
        
        if doc_filter:
            results = [r for r in results if r.doc_id == doc_filter]
        
        if chapter_filter:
            results = [r for r in results if r.chapter_no in chapter_filter]
        
        return results[:k]
    
    def search_subsections(
        self, 
        query_embedding: np.ndarray, 
        query_text: str = "",
        k: int = 10,
        doc_filter: Optional[str] = None,
        chapter_filter: Optional[list[str]] = None,
        section_filter: Optional[list[str]] = None,
        use_hybrid: bool = True
    ) -> list[SearchResult]:
        """Search at subsection level with optional filters."""
        # Search with higher k when filters are applied to ensure we get enough results
        search_k = k * 10 if section_filter else k * 3
        
        results = self._hybrid_search(
            self.subsection_index, query_embedding, query_text, search_k, "subsection", use_hybrid
        )
        
        if doc_filter:
            results = [r for r in results if r.doc_id == doc_filter]
        
        if chapter_filter:
            results = [r for r in results if r.chapter_no in chapter_filter]
        
        if section_filter:
            results = [r for r in results if r.section_no in section_filter]
        
        return results[:k]
    
    def _hybrid_search(
        self,
        level_index: LevelIndex,
        query_embedding: np.ndarray,
        query_text: str,
        k: int,
        level: str,
        use_hybrid: bool = True
    ) -> list[SearchResult]:
        """Perform hybrid vector + BM25 search."""
        if level_index.faiss_index.ntotal == 0:  # type: ignore
            return []
        
        k = min(k, level_index.faiss_index.ntotal)  # type: ignore
        
        # Normalize query embedding
        query_embedding = query_embedding.reshape(1, -1).astype(np.float32)
        query_embedding = query_embedding / np.linalg.norm(query_embedding)
        
        # Vector search
        vector_scores, vector_indices = level_index.faiss_index.search(query_embedding, k)  # type: ignore
        vector_scores = vector_scores[0]
        vector_indices = vector_indices[0]
        
        # Create results map
        results_map = {}
        for score, idx in zip(vector_scores, vector_indices):
            if idx >= 0 and idx < len(level_index.metadata):
                results_map[idx] = {
                    "vector_score": float(score),
                    "bm25_score": 0.0
                }
        
        # BM25 search if enabled and available
        if use_hybrid and level_index.bm25_index and query_text:
            query_tokens = query_text.lower().split()
            bm25_scores = level_index.bm25_index.get_scores(query_tokens)
            
            # Get top k BM25 results
            bm25_top_indices = np.argsort(bm25_scores)[::-1][:k]
            
            for idx in bm25_top_indices:
                if bm25_scores[idx] > 0:
                    if idx in results_map:
                        results_map[idx]["bm25_score"] = float(bm25_scores[idx])
                    else:
                        results_map[idx] = {
                            "vector_score": 0.0,
                            "bm25_score": float(bm25_scores[idx])
                        }
        
        # Combine scores (RRF-style fusion)
        final_results = []
        for idx, scores in results_map.items():
            # Normalize and combine scores
            # Vector scores are already similarity (0-1), BM25 needs normalization
            vector_score = scores["vector_score"]
            bm25_score = scores["bm25_score"]
            
            # Weighted combination - increased BM25 weight for better keyword matching
            if use_hybrid and bm25_score > 0:
                combined_score = 0.4 * vector_score + 0.6 * min(bm25_score / 10, 1.0)
            else:
                combined_score = vector_score
            
            meta = level_index.metadata[idx]
            final_results.append(SearchResult(
                doc_id=meta.doc_id,
                chapter_no=meta.chapter_no,
                section_no=meta.section_no,
                subsection_no=meta.subsection_no,
                text=meta.text,
                score=combined_score,
                level=level,
                metadata={
                    "chapter_title": meta.chapter_title,
                    "section_title": meta.section_title,
                    "page": meta.page,
                    "type": meta.type,
                    "vector_score": scores["vector_score"],
                    "bm25_score": scores["bm25_score"]
                }
            ))
        
        # Sort by combined score
        final_results.sort(key=lambda x: x.score, reverse=True)
        
        return final_results[:k]
    
    def save(self, directory: str | Path):
        """Save all indices to disk."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        
        for name, index in [
            ("doc", self.doc_index),
            ("chapter", self.chapter_index),
            ("section", self.section_index),
            ("subsection", self.subsection_index),
            ("sop", self.sop_index),
            ("evidence", self.evidence_index),
            ("compensation", self.compensation_index),
            ("general_sop", self.general_sop_index)
        ]:
            # Save FAISS index
            faiss_path = directory / f"{name}_index.faiss"
            faiss.write_index(index.faiss_index, str(faiss_path))
            
            # Save metadata (for standard indices only)
            if name not in ["sop", "evidence", "compensation", "general_sop"]:
                meta_path = directory / f"{name}_metadata.json"
                meta_data = [
                    {
                        "idx": m.idx,
                        "doc_id": m.doc_id,
                        "chapter_no": m.chapter_no,
                        "chapter_title": m.chapter_title,
                        "section_no": m.section_no,
                        "section_title": m.section_title,
                        "subsection_no": m.subsection_no,
                        "text": m.text,
                        "page": m.page,
                        "type": m.type,
                        "doc_type": m.doc_type
                    }
                    for m in index.metadata
                ]
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(meta_data, f, ensure_ascii=False, indent=2)
            
            # Save texts for BM25
            texts_path = directory / f"{name}_texts.json"
            with open(texts_path, "w", encoding="utf-8") as f:
                json.dump(index.texts, f, ensure_ascii=False)
        
        # Save SOP metadata separately
        sop_meta_path = directory / "sop_metadata.json"
        sop_data = [
            {
                "idx": m.idx,
                "doc_id": m.doc_id,
                "block_id": m.block_id,
                "title": m.title,
                "text": m.text,
                "procedural_stage": m.procedural_stage,
                "stakeholders": m.stakeholders,
                "action_type": m.action_type,
                "time_limit": m.time_limit,
                "bnss_sections": m.bnss_sections,
                "bns_sections": m.bns_sections,
                "page": m.page,
                "priority": m.priority
            }
            for m in self.sop_metadata
        ]
        with open(sop_meta_path, "w", encoding="utf-8") as f:
            json.dump(sop_data, f, ensure_ascii=False, indent=2)
        
        # Save Evidence metadata (Tier-2)
        evidence_meta_path = directory / "evidence_metadata.json"
        evidence_data = [
            {
                "idx": m.idx,
                "doc_id": m.doc_id,
                "block_id": m.block_id,
                "title": m.title,
                "text": m.text,
                "evidence_types": m.evidence_types,
                "investigative_action": m.investigative_action,
                "stakeholders": m.stakeholders,
                "failure_impact": m.failure_impact,
                "linked_stage": m.linked_stage,
                "case_types": m.case_types,
                "page": m.page,
                "priority": m.priority
            }
            for m in self.evidence_metadata
        ]
        with open(evidence_meta_path, "w", encoding="utf-8") as f:
            json.dump(evidence_data, f, ensure_ascii=False, indent=2)
        
        # Save Compensation metadata (Tier-2)
        compensation_meta_path = directory / "compensation_metadata.json"
        compensation_data = [
            {
                "idx": m.idx,
                "doc_id": m.doc_id,
                "block_id": m.block_id,
                "title": m.title,
                "text": m.text,
                "compensation_type": m.compensation_type,
                "application_stage": m.application_stage,
                "authority": m.authority,
                "crimes_covered": m.crimes_covered,
                "eligibility_criteria": m.eligibility_criteria,
                "amount_range": m.amount_range,
                "requires_conviction": m.requires_conviction,
                "time_limit": m.time_limit,
                "documents_required": m.documents_required,
                "bnss_sections": m.bnss_sections,
                "page": m.page,
                "priority": m.priority
            }
            for m in self.compensation_metadata
        ]
        with open(compensation_meta_path, "w", encoding="utf-8") as f:
            json.dump(compensation_data, f, ensure_ascii=False, indent=2)
        
        # Save General SOP metadata (Tier-3)
        general_sop_meta_path = directory / "general_sop_metadata.json"
        general_sop_data = [
            {
                "idx": m.idx,
                "doc_id": m.doc_id,
                "block_id": m.block_id,
                "title": m.title,
                "text": m.text,
                "sop_group": m.sop_group,
                "procedural_stage": m.procedural_stage,
                "stakeholders": m.stakeholders,
                "applies_to": m.applies_to,
                "action_type": m.action_type,
                "time_limit": m.time_limit,
                "legal_references": m.legal_references,
                "page": m.page,
                "priority": m.priority
            }
            for m in self.general_sop_metadata
        ]
        with open(general_sop_meta_path, "w", encoding="utf-8") as f:
            json.dump(general_sop_data, f, ensure_ascii=False, indent=2)
        
        # Save config
        config_path = directory / "config.json"
        with open(config_path, "w") as f:
            json.dump({"embedding_dim": self.embedding_dim}, f)
        
        print(f"Indices saved to {directory}")
    
    def load(self, directory: str | Path):
        """Load all indices from disk."""
        directory = Path(directory)
        
        # Load config
        config_path = directory / "config.json"
        with open(config_path, "r") as f:
            config = json.load(f)
            self.embedding_dim = config["embedding_dim"]
        
        for name, index in [
            ("doc", self.doc_index),
            ("chapter", self.chapter_index),
            ("section", self.section_index),
            ("subsection", self.subsection_index),
            ("sop", self.sop_index),
            ("evidence", self.evidence_index),
            ("compensation", self.compensation_index),
            ("general_sop", self.general_sop_index)
        ]:
            # Load FAISS index
            faiss_path = directory / f"{name}_index.faiss"
            if faiss_path.exists():
                index.faiss_index = faiss.read_index(str(faiss_path))
            else:
                # Initialize empty index for backwards compatibility
                index.faiss_index = faiss.IndexFlatIP(self.embedding_dim)
            
            # Load metadata (for standard indices only)
            if name not in ["sop", "evidence", "compensation", "general_sop"]:
                meta_path = directory / f"{name}_metadata.json"
                if meta_path.exists():
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta_data = json.load(f)
                        index.metadata = [
                            IndexMetadata(
                                idx=m["idx"],
                                doc_id=m["doc_id"],
                                chapter_no=m.get("chapter_no", ""),
                                chapter_title=m.get("chapter_title", ""),
                                section_no=m.get("section_no", ""),
                                section_title=m.get("section_title", ""),
                                subsection_no=m.get("subsection_no", ""),
                                text=m.get("text", ""),
                                page=m.get("page", 0),
                                type=m.get("type", ""),
                                doc_type=m.get("doc_type", "law")
                            )
                            for m in meta_data
                        ]
            
            # Load texts
            texts_path = directory / f"{name}_texts.json"
            if texts_path.exists():
                with open(texts_path, "r", encoding="utf-8") as f:
                    index.texts = json.load(f)
        
        # Load SOP metadata
        sop_meta_path = directory / "sop_metadata.json"
        if sop_meta_path.exists():
            with open(sop_meta_path, "r", encoding="utf-8") as f:
                sop_data = json.load(f)
                self.sop_metadata = [
                    SOPIndexEntry(
                        idx=m["idx"],
                        doc_id=m["doc_id"],
                        block_id=m["block_id"],
                        title=m["title"],
                        text=m["text"],
                        procedural_stage=m["procedural_stage"],
                        stakeholders=m["stakeholders"],
                        action_type=m["action_type"],
                        time_limit=m.get("time_limit", ""),
                        bnss_sections=m.get("bnss_sections", []),
                        bns_sections=m.get("bns_sections", []),
                        page=m.get("page", 0),
                        priority=m.get("priority", 1)
                    )
                    for m in sop_data
                ]
        
        # Load Evidence metadata (Tier-2)
        evidence_meta_path = directory / "evidence_metadata.json"
        if evidence_meta_path.exists():
            with open(evidence_meta_path, "r", encoding="utf-8") as f:
                evidence_data = json.load(f)
                self.evidence_metadata = [
                    EvidenceIndexEntry(
                        idx=m["idx"],
                        doc_id=m["doc_id"],
                        block_id=m["block_id"],
                        title=m["title"],
                        text=m["text"],
                        evidence_types=m.get("evidence_types", []),
                        investigative_action=m.get("investigative_action", "general"),
                        stakeholders=m.get("stakeholders", []),
                        failure_impact=m.get("failure_impact", "none"),
                        linked_stage=m.get("linked_stage", "evidence_collection"),
                        case_types=m.get("case_types", ["all"]),
                        page=m.get("page", 0),
                        priority=m.get("priority", 1)
                    )
                    for m in evidence_data
                ]
        
        # Load Compensation metadata (Tier-2)
        compensation_meta_path = directory / "compensation_metadata.json"
        if compensation_meta_path.exists():
            with open(compensation_meta_path, "r", encoding="utf-8") as f:
                compensation_data = json.load(f)
                self.compensation_metadata = [
                    CompensationIndexEntry(
                        idx=m["idx"],
                        doc_id=m["doc_id"],
                        block_id=m["block_id"],
                        title=m["title"],
                        text=m["text"],
                        compensation_type=m.get("compensation_type", "general"),
                        application_stage=m.get("application_stage", "anytime"),
                        authority=m.get("authority", "dlsa"),
                        crimes_covered=m.get("crimes_covered", []),
                        eligibility_criteria=m.get("eligibility_criteria", []),
                        amount_range=m.get("amount_range", ""),
                        requires_conviction=m.get("requires_conviction", False),
                        time_limit=m.get("time_limit", ""),
                        documents_required=m.get("documents_required", []),
                        bnss_sections=m.get("bnss_sections", []),
                        page=m.get("page", 0),
                        priority=m.get("priority", 1)
                    )
                    for m in compensation_data
                ]
        
        # Load General SOP metadata (Tier-3)
        general_sop_meta_path = directory / "general_sop_metadata.json"
        if general_sop_meta_path.exists():
            with open(general_sop_meta_path, "r", encoding="utf-8") as f:
                general_sop_data = json.load(f)
                self.general_sop_metadata = [
                    GeneralSOPIndexEntry(
                        idx=m["idx"],
                        doc_id=m["doc_id"],
                        block_id=m["block_id"],
                        title=m["title"],
                        text=m["text"],
                        sop_group=m.get("sop_group", "general"),
                        procedural_stage=m.get("procedural_stage", "fir"),
                        stakeholders=m.get("stakeholders", []),
                        applies_to=m.get("applies_to", ["all"]),
                        action_type=m.get("action_type", "procedure"),
                        time_limit=m.get("time_limit", ""),
                        legal_references=m.get("legal_references", []),
                        page=m.get("page", 0),
                        priority=m.get("priority", 1)
                    )
                    for m in general_sop_data
                ]
        
        # Rebuild BM25 indices
        self.build_bm25_indices()
        
        print(f"Indices loaded from {directory}")
    
    def get_stats(self) -> dict:
        """Get statistics about the indices."""
        return {
            "documents": self.doc_index.faiss_index.ntotal,  # type: ignore
            "chapters": self.chapter_index.faiss_index.ntotal,  # type: ignore
            "sections": self.section_index.faiss_index.ntotal,  # type: ignore
            "subsections": self.subsection_index.faiss_index.ntotal,  # type: ignore
            "sop_blocks": self.sop_index.faiss_index.ntotal,  # type: ignore
            "evidence_blocks": self.evidence_index.faiss_index.ntotal,  # type: ignore
            "compensation_blocks": self.compensation_index.faiss_index.ntotal,  # type: ignore
            "general_sop_blocks": self.general_sop_index.faiss_index.ntotal,  # type: ignore
            "embedding_dim": self.embedding_dim
        }
    
    def has_sop_data(self) -> bool:
        """Check if SOP data is loaded."""
        return self.sop_index.faiss_index.ntotal > 0  # type: ignore
    
    def has_evidence_data(self) -> bool:
        """Check if Evidence Manual data is loaded (Tier-2)."""
        return self.evidence_index.faiss_index.ntotal > 0  # type: ignore
    
    def has_compensation_data(self) -> bool:
        """Check if Compensation Scheme data is loaded (Tier-2)."""
        return self.compensation_index.faiss_index.ntotal > 0  # type: ignore
    
    def has_general_sop_data(self) -> bool:
        """Check if General SOP data is loaded (Tier-3)."""
        return self.general_sop_index.faiss_index.ntotal > 0  # type: ignore
