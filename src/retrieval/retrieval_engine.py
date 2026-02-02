import json
import os
import sys
import logging

# Set HuggingFace cache to project directory BEFORE importing sentence_transformers
# This ensures we use the model cached during build phase
os.environ["HF_HOME"] = os.path.join(os.getcwd(), ".hf_cache")
os.environ["TRANSFORMERS_CACHE"] = os.path.join(os.getcwd(), ".hf_cache")

import faiss
import numpy as np
import pickle
from pathlib import Path
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("LegalRAG-RetrievalEngine")

class RetrievalEngine:
    def __init__(self, store_dir: str = "data/vector_store"):
        self.store_dir = Path(store_dir)
        
        # 1. Load Model
        model_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        logger.info(f"Loading SentenceTransformer model: {model_name}...")
        sys.stdout.flush()
        self.model = SentenceTransformer(model_name)
        logger.info("SentenceTransformer model loaded!")
        sys.stdout.flush()
        
        # 2. Load FAISS
        index_path = self.store_dir / "index.faiss"
        logger.info(f"Loading FAISS index from {index_path}...")
        sys.stdout.flush()
        self.index = faiss.read_index(str(index_path))
        logger.info("FAISS index loaded!")
        sys.stdout.flush()
        
        # 3. Load BM25
        logger.info("Loading BM25 index...")
        sys.stdout.flush()
        with open(self.store_dir / "bm25.pkl", "rb") as f:
            self.bm25 = pickle.load(f)
        logger.info("BM25 index loaded!")
        sys.stdout.flush()
            
        # 4. Load Metadata
        logger.info("Loading metadata...")
        sys.stdout.flush()
        with open(self.store_dir / "metadata.json", "r", encoding="utf-8") as f:
            self.chunks = json.load(f)
        logger.info(f"Metadata loaded! {len(self.chunks)} chunks.")
        sys.stdout.flush()

    def search(self, query: str, k: int = 5, hybrid_weight: float = 0.5):
        # Semantic Search
        query_vector = self.model.encode([query], convert_to_numpy=True)
        faiss.normalize_L2(query_vector)
        
        distances, indices = self.index.search(query_vector, k * 2)
        
        # BM25 Search
        tokenized_query = query.lower().split()
        bm25_scores = self.bm25.get_scores(tokenized_query)
        
        # Hybrid Ranking
        combined_results = []
        
        # Normalize BM25 scores
        max_bm25 = max(bm25_scores) if max(bm25_scores) > 0 else 1.0
        
        seen_indices = set()
        
        # Add Semantic hits
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1: continue
            semantic_score = float(dist)
            bm25_score = bm25_scores[idx] / max_bm25
            
            combined_score = (semantic_score * (1 - hybrid_weight)) + (bm25_score * hybrid_weight)
            
            combined_results.append({
                "chunk": self.chunks[idx],
                "score": combined_score,
                "semantic": semantic_score,
                "keyword": bm25_score
            })
            seen_indices.add(idx)
            
        # Sort and return
        combined_results.sort(key=lambda x: x["score"], reverse=True)
        return combined_results[:k]
