import json
import os
import faiss
import numpy as np
import pickle
from pathlib import Path
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi
from dotenv import load_dotenv

load_dotenv()

class RetrievalEngine:
    def __init__(self, store_dir: str = "data/vector_store"):
        self.store_dir = Path(store_dir)
        
        # 1. Load Model
        model_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        print(f"Loading model: {model_name}...")
        self.model = SentenceTransformer(model_name)
        
        # 2. Load FAISS
        index_path = self.store_dir / "index.faiss"
        print(f"Loading FAISS index from {index_path}...")
        # Ensure path exists, if not, try resolving relative to project root
        if not index_path.exists():
            print(f"Warning: {index_path} not found. Trying absolute match or relative fallback...")
            # If running from src/server, data might be ../../data. 
            # But usually we run from root. We'll trust the input for now.
        
        self.index = faiss.read_index(str(index_path))
        
        # 3. Load BM25
        print("Loading BM25 index...")
        with open(self.store_dir / "bm25.pkl", "rb") as f:
            self.bm25 = pickle.load(f)
            
        # 4. Load Metadata
        print("Loading metadata...")
        with open(self.store_dir / "metadata.json", "r", encoding="utf-8") as f:
            self.chunks = json.load(f)

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
