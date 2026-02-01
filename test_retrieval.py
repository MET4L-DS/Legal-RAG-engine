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
        print("Loading FAISS index...")
        self.index = faiss.read_index(str(self.store_dir / "index.faiss"))
        
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
        # Simple RRF or normalized combination
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

def test():
    engine = RetrievalEngine()
    
    queries = [
        "What is the procedure for Zero FIR?",
        "Compensation for victims of acid attack",
        "Definition of a public servant under BNS",
        "Procedure after arrest of a suspect in rape case"
    ]
    
    for q in queries:
        print(f"\n{'='*50}")
        print(f"QUERY: {q}")
        print(f"{'='*50}")
        results = engine.search(q, k=3)
        
        for i, res in enumerate(results):
            c = res["chunk"]
            print(f"\n[{i+1}] Score: {res['score']:.4f} (Sem: {res['semantic']:.2f}, Key: {res['keyword']:.2f})")
            print(f"CITATION: {c['canonical_header']}")
            # Truncate content for display
            content = c['text'].strip()
            if len(content) > 300:
                content = content[:300] + "..."
            print(f"CONTENT: {content}")

if __name__ == "__main__":
    test()
