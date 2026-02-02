# Pre-download the SentenceTransformer model during build
# This ensures the model is cached before the server starts
from sentence_transformers import SentenceTransformer
import os

model_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
print(f"Pre-downloading model: {model_name}")
model = SentenceTransformer(model_name)
print("Model downloaded and cached successfully!")
