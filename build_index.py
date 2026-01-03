"""Quick test script to build indices"""
import sys
sys.path.insert(0, ".")

from pathlib import Path
import json

# Paths
BASE_DIR = Path(__file__).parent.resolve()
PARSED_DIR = BASE_DIR / "data" / "parsed"
INDEX_DIR = BASE_DIR / "data" / "indices"

from src.models import LegalDocument
from src.embedder import HierarchicalEmbedder
from src.vector_store import MultiLevelVectorStore

INDEX_DIR.mkdir(parents=True, exist_ok=True)

# Load parsed documents
json_files = list(PARSED_DIR.glob("*.json"))
print(f"Found {len(json_files)} parsed documents")

documents = []
for json_file in json_files:
    with open(json_file, "r", encoding="utf-8") as f:
        doc_dict = json.load(f)
        documents.append(LegalDocument.from_dict(doc_dict))
    print(f"Loaded: {json_file.name}")

# Initialize embedder
print("\nLoading embedding model...")
embedder = HierarchicalEmbedder(model_name="sentence-transformers/all-MiniLM-L6-v2")

# Generate embeddings for all documents
for doc in documents:
    embedder.embed_document(doc)

# Build vector store
print("\nBuilding vector store...")
store = MultiLevelVectorStore(embedding_dim=embedder.embedding_dim)

for doc in documents:
    store.add_document(doc)

# Build BM25 indices
store.build_bm25_indices()

# Save indices
store.save(INDEX_DIR)

# Print stats
stats = store.get_stats()
print("\nIndex Statistics:")
for level, count in stats.items():
    print(f"  {level}: {count}")

print(f"\n✓ Indices saved to {INDEX_DIR}")
