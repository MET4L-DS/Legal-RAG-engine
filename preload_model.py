# Pre-download the SentenceTransformer model during build
# Cache to /app/.hf_cache which persists in the container
import os

# Set cache directory to absolute path (matches Dockerfile ENV)
os.environ["HF_HOME"] = "/app/.hf_cache"
os.environ["TRANSFORMERS_CACHE"] = "/app/.hf_cache"

from sentence_transformers import SentenceTransformer

model_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
print(f"Pre-downloading model: {model_name}")
print(f"Cache directory: {os.environ['HF_HOME']}")
model = SentenceTransformer(model_name)
print("Model downloaded and cached successfully!")
print(f"Cache contents: {os.listdir(os.environ['HF_HOME'])}")
