"""
Hierarchical Embedding Generator for Legal Documents.
Creates embeddings at Document, Chapter, Section, and Subsection levels.
"""

import numpy as np
from typing import Optional
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from .models import LegalDocument, Chapter, Section, Subsection, SubsectionType


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
            return np.zeros(self.embedding_dim)
        
        embeddings = []
        weights = []
        
        for sub in subsections:
            if sub.embedding is not None:
                embeddings.append(np.array(sub.embedding))
                weights.append(self.TYPE_WEIGHTS.get(sub.type, 0.1))
        
        if not embeddings:
            return np.zeros(self.embedding_dim)
        
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


def embed_all_documents(
    documents: list[LegalDocument],
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
) -> list[LegalDocument]:
    """Generate embeddings for all documents at all levels."""
    embedder = HierarchicalEmbedder(model_name=model_name)
    
    for doc in documents:
        embedder.embed_document(doc)
    
    return documents
