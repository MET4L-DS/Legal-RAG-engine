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


@dataclass
class LevelIndex:
    """Vector index for a single hierarchical level."""
    faiss_index: Optional[faiss.Index] = None
    metadata: list[IndexMetadata] = field(default_factory=list)
    bm25_index: Optional[BM25Okapi] = None
    texts: list[str] = field(default_factory=list)


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
        
        # Initialize FAISS indices
        self._init_faiss_indices()
    
    def _init_faiss_indices(self):
        """Initialize FAISS indices for each level."""
        # Using IndexFlatIP for inner product (cosine similarity with normalized vectors)
        self.doc_index.faiss_index = faiss.IndexFlatIP(self.embedding_dim)
        self.chapter_index.faiss_index = faiss.IndexFlatIP(self.embedding_dim)
        self.section_index.faiss_index = faiss.IndexFlatIP(self.embedding_dim)
        self.subsection_index.faiss_index = faiss.IndexFlatIP(self.embedding_dim)
    
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
    
    def _add_to_level(
        self, 
        level_index: LevelIndex, 
        embedding: np.ndarray,
        metadata: IndexMetadata
    ):
        """Add an entry to a level index."""
        # Normalize embedding for cosine similarity
        embedding = embedding / np.linalg.norm(embedding, axis=1, keepdims=True)
        
        level_index.faiss_index.add(embedding)
        level_index.metadata.append(metadata)
        level_index.texts.append(metadata.text)
    
    def build_bm25_indices(self):
        """Build BM25 indices for keyword search at each level."""
        print("Building BM25 indices...")
        
        for name, index in [
            ("documents", self.doc_index),
            ("chapters", self.chapter_index),
            ("sections", self.section_index),
            ("subsections", self.subsection_index)
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
        results = self._hybrid_search(
            self.subsection_index, query_embedding, query_text, k * 3, "subsection", use_hybrid
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
        if level_index.faiss_index.ntotal == 0:
            return []
        
        k = min(k, level_index.faiss_index.ntotal)
        
        # Normalize query embedding
        query_embedding = query_embedding.reshape(1, -1).astype(np.float32)
        query_embedding = query_embedding / np.linalg.norm(query_embedding)
        
        # Vector search
        vector_scores, vector_indices = level_index.faiss_index.search(query_embedding, k)
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
            
            # Simple weighted combination
            if use_hybrid and bm25_score > 0:
                combined_score = 0.7 * vector_score + 0.3 * min(bm25_score / 10, 1.0)
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
            ("subsection", self.subsection_index)
        ]:
            # Save FAISS index
            faiss_path = directory / f"{name}_index.faiss"
            faiss.write_index(index.faiss_index, str(faiss_path))
            
            # Save metadata
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
                    "type": m.type
                }
                for m in index.metadata
            ]
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta_data, f, ensure_ascii=False, indent=2)
            
            # Save texts for BM25
            texts_path = directory / f"{name}_texts.json"
            with open(texts_path, "w", encoding="utf-8") as f:
                json.dump(index.texts, f, ensure_ascii=False)
        
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
            ("subsection", self.subsection_index)
        ]:
            # Load FAISS index
            faiss_path = directory / f"{name}_index.faiss"
            index.faiss_index = faiss.read_index(str(faiss_path))
            
            # Load metadata
            meta_path = directory / f"{name}_metadata.json"
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
                        type=m.get("type", "")
                    )
                    for m in meta_data
                ]
            
            # Load texts
            texts_path = directory / f"{name}_texts.json"
            with open(texts_path, "r", encoding="utf-8") as f:
                index.texts = json.load(f)
        
        # Rebuild BM25 indices
        self.build_bm25_indices()
        
        print(f"Indices loaded from {directory}")
    
    def get_stats(self) -> dict:
        """Get statistics about the indices."""
        return {
            "documents": self.doc_index.faiss_index.ntotal,
            "chapters": self.chapter_index.faiss_index.ntotal,
            "sections": self.section_index.faiss_index.ntotal,
            "subsections": self.subsection_index.faiss_index.ntotal,
            "embedding_dim": self.embedding_dim
        }
