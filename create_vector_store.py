import json
import os
import faiss
import numpy as np
import pickle
from tqdm import tqdm
from pathlib import Path
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi
from dotenv import load_dotenv

load_dotenv()

def create_vector_store():
    # 1. Load Chunks
    chunks_path = Path("legal_chunks.json")
    if not chunks_path.exists():
        print(f"Error: {chunks_path} not found. Run ingest_legal_docs.py first.")
        return

    print(f"Loading chunks from {chunks_path}...")
    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    if not chunks:
        print("No chunks to process.")
        return

    # 2. Initialize Models
    # Using a fast local model for default. 
    model_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    print(f"Initializing embedding model: {model_name}...")
    model = SentenceTransformer(model_name)
    embedding_dim = model.get_sentence_embedding_dimension()

    # 3. Generate Embeddings
    texts = [c["text"] for c in chunks]
    print(f"Generating embeddings for {len(texts)} chunks...")
    
    # Process in batches
    batch_size = 64
    all_embeddings = []
    for i in tqdm(range(0, len(texts), batch_size)):
        batch_texts = texts[i:i+batch_size]
        embeddings = model.encode(batch_texts, convert_to_numpy=True)
        all_embeddings.append(embeddings)
    
    embeddings_matrix = np.vstack(all_embeddings).astype('float32')
    
    # Normalize for cosine similarity
    faiss.normalize_L2(embeddings_matrix)

    # 4. Create FAISS Index
    print("Building FAISS index...")
    index = faiss.IndexFlatIP(embedding_dim)
    index.add(embeddings_matrix)

    # 5. Create BM25 Index
    print("Building BM25 index...")
    tokenized_corpus = [text.lower().split() for text in texts]
    bm25 = BM25Okapi(tokenized_corpus)

    # 6. Save Everything
    save_dir = Path("data/vector_store")
    save_dir.mkdir(parents=True, exist_ok=True)

    print(f"Saving store to {save_dir}...")
    
    # Save FAISS index
    faiss.write_index(index, str(save_dir / "index.faiss"))
    
    # Save BM25 index
    with open(save_dir / "bm25.pkl", "wb") as f:
        pickle.dump(bm25, f)
    
    # Save Metadata (Chunks themselves for retrieval)
    with open(save_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2)

    print("\n✅ Vector store created successfully!")
    print(f"Location: {save_dir}")
    print(f"Total Chunks: {len(chunks)}")
    print(f"Embedding Dimension: {embedding_dim}")

if __name__ == "__main__":
    create_vector_store()
