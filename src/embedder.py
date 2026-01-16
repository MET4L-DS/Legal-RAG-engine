"""
Hierarchical Embedding Generator for Legal Documents.
Creates embeddings at Document, Chapter, Section, and Subsection levels.
Supports SOP documents (Tier-1) and Evidence/Compensation documents (Tier-2).
"""

import numpy as np
from typing import Optional
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from .models import LegalDocument, Chapter, Section, Subsection, SubsectionType
from .sop_parser import SOPDocument, ProceduralBlock
from .evidence_parser import EvidenceManualDocument, EvidenceBlock
from .compensation_parser import CompensationSchemeDocument, CompensationBlock


class HierarchicalEmbedder:
    """Generate embeddings at all hierarchical levels."""
    
    # Weights for different subsection types when aggregating to section level
    TYPE_WEIGHTS = {
        SubsectionType.PUNISHMENT: 0.35,
        SubsectionType.DEFINITION: 0.25,
        SubsectionType.PROVISION: 0.20,
        SubsectionType.EXPLANATION: 0.10,
        SubsectionType.EXCEPTION: 0.05,
        SubsectionType.ILLUSTRATION: 0.03,
        SubsectionType.GENERAL: 0.02
    }
    
    def __init__(
        self, 
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        device: Optional[str] = None
    ):
        """Initialize the embedder with a sentence transformer model.
        
        Args:
            model_name: Name of the sentence transformer model.
                       Recommended models for legal text:
                       - "sentence-transformers/all-MiniLM-L6-v2" (fast, good)
                       - "sentence-transformers/all-mpnet-base-v2" (better quality)
                       - "BAAI/bge-base-en-v1.5" (state-of-the-art)
            device: Device to use ('cpu', 'cuda', or None for auto)
        """
        print(f"Loading embedding model: {model_name}...")
        self.model = SentenceTransformer(model_name, device=device)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        print(f"Model loaded. Embedding dimension: {self.embedding_dim}")
    
    def embed_text(self, text: str) -> np.ndarray:
        """Generate embedding for a single text."""
        return self.model.encode(text, convert_to_numpy=True)
    
    def embed_texts(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        """Generate embeddings for multiple texts."""
        return self.model.encode(
            texts, 
            convert_to_numpy=True, 
            batch_size=batch_size,
            show_progress_bar=True
        )
    
    def embed_document(self, doc: LegalDocument) -> LegalDocument:
        """Generate embeddings at all levels for a document."""
        
        print(f"\nGenerating embeddings for: {doc.title}")
        
        # Level 1: Subsection embeddings (leaf nodes)
        print("  → Embedding subsections...")
        self._embed_subsections(doc)
        
        # Level 2: Section embeddings (weighted mean of subsections)
        print("  → Embedding sections...")
        self._embed_sections(doc)
        
        # Level 3: Chapter embeddings (weighted mean of sections)
        print("  → Embedding chapters...")
        self._embed_chapters(doc)
        
        # Level 4: Document embedding (mean of chapters)
        print("  → Embedding document...")
        self._embed_document_level(doc)
        
        return doc
    
    def _embed_subsections(self, doc: LegalDocument):
        """Generate embeddings for all subsections."""
        for chapter in tqdm(doc.chapters, desc="Chapters"):
            for section in chapter.sections:
                for subsection in section.subsections:
                    # Create embedding text with context
                    embed_text = self._create_subsection_embed_text(
                        doc, chapter, section, subsection
                    )
                    subsection.embedding = self.embed_text(embed_text).tolist()
    
    def _create_subsection_embed_text(
        self, 
        doc: LegalDocument,
        chapter: Chapter, 
        section: Section, 
        subsection: Subsection
    ) -> str:
        """Create the text to embed for a subsection with context."""
        # Include hierarchical context for better retrieval
        context_parts = [
            f"{doc.short_name}",
            f"Chapter {chapter.chapter_no}: {chapter.chapter_title}",
            f"Section {section.section_no}: {section.section_title}",
        ]
        
        if subsection.subsection_no != "main":
            context_parts.append(f"({subsection.subsection_no})")
        
        context = " | ".join(context_parts)
        
        # Combine context with actual text
        return f"{context}\n{subsection.text}"
    
    def _embed_sections(self, doc: LegalDocument):
        """Generate embeddings for sections using weighted mean of subsections."""
        for chapter in doc.chapters:
            for section in chapter.sections:
                if not section.subsections:
                    # No subsections, embed the full text directly
                    embed_text = f"Section {section.section_no}: {section.section_title}\n{section.full_text}"
                    section.embedding = self.embed_text(embed_text).tolist()
                else:
                    # Weighted mean pooling of subsection embeddings
                    section.embedding = self._weighted_mean_pooling(
                        section.subsections
                    ).tolist()
    
    def _weighted_mean_pooling(self, subsections: list[Subsection]) -> np.ndarray:
        """Compute weighted mean of subsection embeddings based on type."""
        if not subsections:
            return np.zeros(self.embedding_dim)  # type: ignore
        
        embeddings = []
        weights = []
        
        for sub in subsections:
            if sub.embedding is not None:
                embeddings.append(np.array(sub.embedding))
                weights.append(self.TYPE_WEIGHTS.get(sub.type, 0.1))
        
        if not embeddings:
            return np.zeros(self.embedding_dim)  # type: ignore
        
        embeddings = np.array(embeddings)
        weights = np.array(weights)
        
        # Normalize weights
        weights = weights / weights.sum()
        
        # Weighted mean
        weighted_embedding = np.average(embeddings, axis=0, weights=weights)
        
        # Normalize the result
        norm = np.linalg.norm(weighted_embedding)
        if norm > 0:
            weighted_embedding = weighted_embedding / norm
        
        return weighted_embedding
    
    def _embed_chapters(self, doc: LegalDocument):
        """Generate embeddings for chapters using mean of section embeddings."""
        for chapter in doc.chapters:
            if not chapter.sections:
                # No sections, embed the summary
                embed_text = f"Chapter {chapter.chapter_no}: {chapter.chapter_title}\n{chapter.summary}"
                chapter.embedding = self.embed_text(embed_text).tolist()
            else:
                # Mean pooling of section embeddings
                section_embeddings = [
                    np.array(s.embedding) 
                    for s in chapter.sections 
                    if s.embedding is not None
                ]
                
                if section_embeddings:
                    mean_embedding = np.mean(section_embeddings, axis=0)
                    # Normalize
                    norm = np.linalg.norm(mean_embedding)
                    if norm > 0:
                        mean_embedding = mean_embedding / norm
                    chapter.embedding = mean_embedding.tolist()
                else:
                    embed_text = f"Chapter {chapter.chapter_no}: {chapter.chapter_title}"
                    chapter.embedding = self.embed_text(embed_text).tolist()
    
    def _embed_document_level(self, doc: LegalDocument):
        """Generate embedding for the entire document."""
        if not doc.chapters:
            doc.embedding = self.embed_text(f"{doc.title}\n{doc.summary}").tolist()
        else:
            # Mean pooling of chapter embeddings
            chapter_embeddings = [
                np.array(c.embedding) 
                for c in doc.chapters 
                if c.embedding is not None
            ]
            
            if chapter_embeddings:
                mean_embedding = np.mean(chapter_embeddings, axis=0)
                # Normalize
                norm = np.linalg.norm(mean_embedding)
                if norm > 0:
                    mean_embedding = mean_embedding / norm
                doc.embedding = mean_embedding.tolist()
            else:
                doc.embedding = self.embed_text(f"{doc.title}\n{doc.summary}").tolist()
    
    def embed_sop_document(self, sop: SOPDocument) -> SOPDocument:
        """Generate embeddings for SOP document and all its procedural blocks.
        
        Args:
            sop: SOP document to embed
            
        Returns:
            The same document with embeddings populated
        """
        print(f"\nGenerating embeddings for SOP: {sop.title}")
        
        # Embed each procedural block
        print(f"  → Embedding {len(sop.blocks)} procedural blocks...")
        for block in tqdm(sop.blocks, desc="SOP Blocks"):
            embed_text = self._create_sop_block_embed_text(sop, block)
            block.embedding = self.embed_text(embed_text).tolist()
        
        # Create document-level embedding from blocks
        print("  → Embedding SOP document...")
        if sop.blocks:
            block_embeddings = [
                np.array(b.embedding)
                for b in sop.blocks
                if b.embedding is not None
            ]
            
            if block_embeddings:
                # Weighted mean by priority
                weights = np.array([b.priority for b in sop.blocks if b.embedding is not None])
                weights = weights / weights.sum()
                mean_embedding = np.average(block_embeddings, axis=0, weights=weights)
                
                # Normalize
                norm = np.linalg.norm(mean_embedding)
                if norm > 0:
                    mean_embedding = mean_embedding / norm
                sop.embedding = mean_embedding.tolist()
            else:
                sop.embedding = self.embed_text(sop.title).tolist()
        else:
            sop.embedding = self.embed_text(sop.title).tolist()
        
        return sop
    
    def _create_sop_block_embed_text(self, sop: SOPDocument, block: ProceduralBlock) -> str:
        """Create text to embed for an SOP block with context.
        
        Includes procedural stage and stakeholder info for better retrieval.
        """
        # Build context header
        context_parts = [
            f"SOP ({sop.source})",
            f"Stage: {block.procedural_stage.value.replace('_', ' ').title()}",
        ]
        
        if block.stakeholders:
            stakeholder_str = ", ".join(s.value for s in block.stakeholders)
            context_parts.append(f"For: {stakeholder_str}")
        
        if block.time_limit:
            context_parts.append(f"Time: {block.time_limit}")
        
        context = " | ".join(context_parts)
        
        # Add referenced sections for better cross-referencing
        refs = []
        if block.bnss_sections:
            refs.append(f"BNSS Sections: {', '.join(block.bnss_sections)}")
        if block.bns_sections:
            refs.append(f"BNS Sections: {', '.join(block.bns_sections)}")
        
        ref_text = " | ".join(refs) if refs else ""
        
        # Combine all parts
        if ref_text:
            return f"{context}\n{block.title}\n{ref_text}\n{block.text}"
        else:
            return f"{context}\n{block.title}\n{block.text}"
    
    # =========================================================================
    # TIER-2: EVIDENCE MANUAL EMBEDDING
    # =========================================================================
    
    def embed_evidence_document(self, evidence_doc: EvidenceManualDocument) -> EvidenceManualDocument:
        """Generate embeddings for Evidence Manual document and all its blocks.
        
        Args:
            evidence_doc: Evidence Manual document to embed
            
        Returns:
            The same document with embeddings populated
        """
        print(f"\nGenerating embeddings for Evidence Manual: {evidence_doc.title}")
        
        # Embed each evidence block
        print(f"  → Embedding {len(evidence_doc.blocks)} evidence blocks...")
        for block in tqdm(evidence_doc.blocks, desc="Evidence Blocks"):
            embed_text = self._create_evidence_block_embed_text(evidence_doc, block)
            block.embedding = self.embed_text(embed_text).tolist()
        
        # Create document-level embedding from blocks
        print("  → Embedding Evidence Manual document...")
        if evidence_doc.blocks:
            block_embeddings = [
                np.array(b.embedding)
                for b in evidence_doc.blocks
                if b.embedding is not None
            ]
            
            if block_embeddings:
                # Weighted mean by priority
                weights = np.array([b.priority for b in evidence_doc.blocks if b.embedding is not None])
                weights = weights / weights.sum()
                mean_embedding = np.average(block_embeddings, axis=0, weights=weights)
                
                # Normalize
                norm = np.linalg.norm(mean_embedding)
                if norm > 0:
                    mean_embedding = mean_embedding / norm
                evidence_doc.embedding = mean_embedding.tolist()
            else:
                evidence_doc.embedding = self.embed_text(evidence_doc.title).tolist()
        else:
            evidence_doc.embedding = self.embed_text(evidence_doc.title).tolist()
        
        return evidence_doc
    
    def _create_evidence_block_embed_text(self, evidence_doc: EvidenceManualDocument, block: EvidenceBlock) -> str:
        """Create text to embed for an Evidence block with context.
        
        Includes evidence type and investigative action for better retrieval.
        """
        # Build context header
        context_parts = [
            f"Crime Scene Manual ({evidence_doc.source})",
            f"Action: {block.investigative_action.value.replace('_', ' ').title()}",
        ]
        
        if block.evidence_types:
            evidence_str = ", ".join(e.value for e in block.evidence_types)
            context_parts.append(f"Evidence: {evidence_str}")
        
        if block.failure_impact.value != "none":
            context_parts.append(f"If failed: {block.failure_impact.value.replace('_', ' ')}")
        
        context = " | ".join(context_parts)
        
        # Add case types for better filtering
        case_info = ""
        if block.case_types and "all" not in block.case_types:
            case_info = f"Applies to: {', '.join(block.case_types)}"
        
        # Combine all parts
        if case_info:
            return f"{context}\n{block.title}\n{case_info}\n{block.text}"
        else:
            return f"{context}\n{block.title}\n{block.text}"
    
    # =========================================================================
    # TIER-2: COMPENSATION SCHEME EMBEDDING
    # =========================================================================
    
    def embed_compensation_document(self, comp_doc: CompensationSchemeDocument) -> CompensationSchemeDocument:
        """Generate embeddings for Compensation Scheme document and all its blocks.
        
        Args:
            comp_doc: Compensation Scheme document to embed
            
        Returns:
            The same document with embeddings populated
        """
        print(f"\nGenerating embeddings for Compensation Scheme: {comp_doc.title}")
        
        # Embed each compensation block
        print(f"  → Embedding {len(comp_doc.blocks)} compensation blocks...")
        for block in tqdm(comp_doc.blocks, desc="Compensation Blocks"):
            embed_text = self._create_compensation_block_embed_text(comp_doc, block)
            block.embedding = self.embed_text(embed_text).tolist()
        
        # Create document-level embedding from blocks
        print("  → Embedding Compensation Scheme document...")
        if comp_doc.blocks:
            block_embeddings = [
                np.array(b.embedding)
                for b in comp_doc.blocks
                if b.embedding is not None
            ]
            
            if block_embeddings:
                # Weighted mean by priority
                weights = np.array([b.priority for b in comp_doc.blocks if b.embedding is not None])
                weights = weights / weights.sum()
                mean_embedding = np.average(block_embeddings, axis=0, weights=weights)
                
                # Normalize
                norm = np.linalg.norm(mean_embedding)
                if norm > 0:
                    mean_embedding = mean_embedding / norm
                comp_doc.embedding = mean_embedding.tolist()
            else:
                comp_doc.embedding = self.embed_text(comp_doc.title).tolist()
        else:
            comp_doc.embedding = self.embed_text(comp_doc.title).tolist()
        
        return comp_doc
    
    def _create_compensation_block_embed_text(self, comp_doc: CompensationSchemeDocument, block: CompensationBlock) -> str:
        """Create text to embed for a Compensation block with context.
        
        Includes compensation type, authority, and eligibility for better retrieval.
        """
        # Build context header
        context_parts = [
            f"NALSA Scheme ({comp_doc.source})",
            f"Type: {block.compensation_type.value.replace('_', ' ').title()}",
        ]
        
        if block.authority.value != "general":
            context_parts.append(f"Authority: {block.authority.value.upper()}")
        
        if block.application_stage.value != "anytime":
            context_parts.append(f"Stage: {block.application_stage.value.replace('_', ' ').title()}")
        
        context = " | ".join(context_parts)
        
        # Add key eligibility info
        eligibility_parts = []
        if block.crimes_covered:
            crimes_str = ", ".join(c.value for c in block.crimes_covered if c.value != "other")
            if crimes_str:
                eligibility_parts.append(f"Crimes: {crimes_str}")
        
        if not block.requires_conviction:
            eligibility_parts.append("Conviction NOT required")
        
        if block.amount_range:
            eligibility_parts.append(f"Amount: {block.amount_range}")
        
        eligibility_info = " | ".join(eligibility_parts) if eligibility_parts else ""
        
        # Combine all parts
        if eligibility_info:
            return f"{context}\n{block.title}\n{eligibility_info}\n{block.text}"
        else:
            return f"{context}\n{block.title}\n{block.text}"


def embed_all_documents(
    documents: list[LegalDocument],
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
) -> list[LegalDocument]:
    """Generate embeddings for all documents at all levels."""
    embedder = HierarchicalEmbedder(model_name=model_name)
    
    for doc in documents:
        embedder.embed_document(doc)
    
    return documents
